"""Structural tests for ``claude/plugins.manifest.json`` and ``claude/vendor/`` as committed."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType

import pytest

NOISE_NAMES = {".in_use", "__pycache__", "tests", ".github", ".git", ".orphaned_at"}
SPDX_BY_FIRST_LINE = {"MIT License": "MIT", "Apache License": "Apache-2.0"}
MODIFIED_NOTICE = "<!-- Modified from the upstream version; changes are listed in UPSTREAM.md. -->"
SUBAGENT_REF = re.compile(r'subagent_type\s*[=:]\s*"([A-Za-z0-9:_-]+)"')
BUILTIN_AGENTS = {"general-purpose", "Explore", "Plan"}


@pytest.fixture(scope="module")
def root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def vendor_dir(root: Path) -> Path:
    return root / "claude" / "vendor"


@pytest.fixture(scope="module")
def manifest(root: Path) -> dict:
    return json.loads((root / "claude" / "plugins.manifest.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def vs(root: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("vendor_sync_manifest_test",
                                                  root / "tools" / "vendor_sync.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def frontmatter(text: str) -> dict[str, str]:
    """Top-level ``key: value`` pairs of a file's frontmatter."""
    lines = text.split("\n")
    assert lines[0] == "---", "file does not open with frontmatter"
    pairs = {}
    for line in lines[1:lines.index("---", 1)]:
        key, sep, value = line.partition(":")
        if sep and not line.startswith((" ", "\t")):
            pairs[key] = value.strip()
    return pairs


def agent_files(vendor_dir: Path) -> list[Path]:
    return sorted(vendor_dir.glob("*/agents/*.md"))


def license_spdx(path: Path) -> str:
    first = next(line.strip() for line in path.read_text(encoding="utf-8").splitlines()
                 if line.strip())
    return SPDX_BY_FIRST_LINE[first]


# --------------------------------------------------------------------------- #
# the manifest
# --------------------------------------------------------------------------- #


def test_manifest_declares_schema_and_top_level_keys(manifest: dict) -> None:
    assert manifest["schema"] == "plugins-manifest.v3"
    for key in ("generated", "generated_by", "upstream_sources", "canonical_agents",
                "accepted_duplicate_agents", "plugins"):
        assert key in manifest, key
    assert not {"usage", "removed", "deployment", "marketplaces"} & set(manifest)


def test_every_plugin_has_the_required_fields_and_appears_once(manifest: dict) -> None:
    required = {"name", "upstream_marketplace", "source_repo", "source_path", "upstream_commit",
                "upstream_version", "license", "bundle", "local_modifications",
                "files_modified", "files_added", "components"}
    names = [p["name"] for p in manifest["plugins"]]
    for plugin in manifest["plugins"]:
        assert required <= set(plugin), plugin["name"]
        assert plugin["upstream_marketplace"] in manifest["upstream_sources"], plugin["name"]
        assert re.fullmatch(r"[0-9a-f]{40}", plugin["upstream_commit"]), plugin["name"]
    assert len(names) == len(set(names))


def test_every_plugin_is_in_one_bundle_or_is_an_extra(manifest: dict, root: Path) -> None:
    sys.path.insert(0, str(root / "build"))
    import bundles

    for plugin in manifest["plugins"]:
        if plugin["name"] in bundles.EXTRAS:
            assert plugin["bundle"] is None, plugin["name"]
        else:
            assert plugin["bundle"] == bundles.bundle_of(plugin["name"]) is not None, plugin["name"]


def test_manifest_equals_a_fresh_render(vs: ModuleType, vendor_dir: Path, manifest: dict) -> None:
    commits = {k: v["vendored_at"] for k, v in manifest["upstream_sources"].items()}
    assert vs.build_manifest(vendor_dir, commits, manifest["generated"]) == manifest


# --------------------------------------------------------------------------- #
# the vendored tree
# --------------------------------------------------------------------------- #


def test_vendor_directories_match_the_manifest_and_carry_provenance(
    vendor_dir: Path, manifest: dict
) -> None:
    on_disk = {p.name for p in vendor_dir.iterdir() if p.is_dir()}
    recorded = {p["name"] for p in manifest["plugins"]}
    assert on_disk == recorded

    by_name = {p["name"]: p for p in manifest["plugins"]}
    for name in sorted(on_disk):
        plugin = vendor_dir / name
        upstream = (plugin / "UPSTREAM.md").read_text(encoding="utf-8")
        assert by_name[name]["upstream_commit"] in upstream, name
        assert "Retrieval date" in upstream and "## Local modifications" in upstream, name
        data = json.loads((plugin / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        assert data["name"] == name
        assert by_name[name]["upstream_version"] == data.get("version", "commit-sha"), name
        agents = sorted(p.stem for p in (plugin / "agents").glob("*.md"))
        assert by_name[name]["components"].get("agents", []) == agents, name


def test_vendored_tree_carries_no_noise(vendor_dir: Path) -> None:
    offenders = [str(p.relative_to(vendor_dir)) for p in vendor_dir.rglob("*")
                 if p.name in NOISE_NAMES or p.suffix in {".pyc", ".pyo"}]
    assert not offenders


def test_unmodified_plugins_say_so_and_changed_files_set_the_flag(
    vendor_dir: Path, manifest: dict
) -> None:
    for plugin in manifest["plugins"]:
        text = (vendor_dir / plugin["name"] / "UPSTREAM.md").read_text(encoding="utf-8")
        section = text.split("## Local modifications", 1)[1].lstrip()
        if not plugin["local_modifications"]:
            assert section.startswith("None"), plugin["name"]
            assert not plugin["files_modified"] and not plugin["files_added"], plugin["name"]
        if plugin["files_modified"] or plugin["files_added"]:
            assert plugin["local_modifications"], plugin["name"]


# --------------------------------------------------------------------------- #
# licensing
# --------------------------------------------------------------------------- #


def test_every_vendored_plugin_has_a_license_matching_its_manifest_spdx(
    vendor_dir: Path, manifest: dict
) -> None:
    for plugin in manifest["plugins"]:
        license_file = vendor_dir / plugin["name"] / "LICENSE"
        assert license_file.is_file(), f"{plugin['name']} has no LICENSE"
        assert license_spdx(license_file) == plugin["license"], plugin["name"]
    spdx_by_source = {}
    for plugin in manifest["plugins"]:
        spdx_by_source.setdefault(plugin["upstream_marketplace"], set()).add(plugin["license"])
    assert spdx_by_source == {"claude-code-workflows": {"MIT"},
                              "claude-plugins-official": {"Apache-2.0"}}


def test_wshobson_plugins_carry_the_upstream_mit_text(vendor_dir: Path, manifest: dict) -> None:
    for plugin in manifest["plugins"]:
        if plugin["license"] != "MIT":
            continue
        text = (vendor_dir / plugin["name"] / "LICENSE").read_text(encoding="utf-8")
        assert "Copyright (c) 2024 Seth Hobson" in text, plugin["name"]


def test_apache_modified_markdown_files_carry_the_notice(vendor_dir: Path, manifest: dict) -> None:
    missing = []
    for plugin in manifest["plugins"]:
        if plugin["license"] != "Apache-2.0":
            continue
        for rel in plugin["files_modified"]:
            if rel.endswith(".md"):
                text = (vendor_dir / plugin["name"] / rel).read_text(encoding="utf-8")
                if MODIFIED_NOTICE not in text:
                    missing.append(f"{plugin['name']}/{rel}")
    assert not missing


def test_files_added_are_listed_in_upstream_md(vendor_dir: Path, manifest: dict) -> None:
    for plugin in manifest["plugins"]:
        text = (vendor_dir / plugin["name"] / "UPSTREAM.md").read_text(encoding="utf-8")
        for rel in plugin["files_added"]:
            assert f"- `{rel}`" in text.split("## Files added", 1)[1], plugin["name"]


def test_every_upstream_md_equals_a_fresh_render(vs: ModuleType, vendor_dir: Path,
                                                 manifest: dict) -> None:
    for plugin in manifest["plugins"]:
        committed = (vendor_dir / plugin["name"] / "UPSTREAM.md").read_text(encoding="utf-8")
        assert vs.rendered_upstream(plugin["name"], plugin["upstream_marketplace"],
                                    vendor_dir) == committed, plugin["name"]


# --------------------------------------------------------------------------- #
# vendored agents
# --------------------------------------------------------------------------- #


def test_vendored_agents_declare_frontmatter_a_pinned_model_and_a_valid_name(
    vendor_dir: Path,
) -> None:
    problems = []
    for path in agent_files(vendor_dir):
        plugin = path.parent.parent.name
        try:
            fields = frontmatter(path.read_text(encoding="utf-8"))
        except (AssertionError, ValueError):
            problems.append(f"{plugin}/{path.name}: no frontmatter")
            continue
        if fields.get("model", "inherit") == "inherit":
            problems.append(f"{plugin}/{path.name}: model is {fields.get('model')!r}")
        if fields.get("name") not in (path.stem, f"{plugin}-{path.stem}"):
            problems.append(f"{plugin}/{path.name}: declares name {fields.get('name')!r}")
        if "<example>" in fields.get("description", ""):
            problems.append(f"{plugin}/{path.name}: description carries <example>")
    assert not problems, problems


def test_declared_agent_names_are_unique_and_duplicate_stems_are_accepted(
    vendor_dir: Path, manifest: dict
) -> None:
    names: dict[str, list[str]] = {}
    stems: dict[str, list[str]] = {}
    for path in agent_files(vendor_dir):
        plugin = path.parent.parent.name
        names.setdefault(frontmatter(path.read_text(encoding="utf-8"))["name"], []).append(plugin)
        stems.setdefault(path.stem, []).append(plugin)
    assert not {n: p for n, p in names.items() if len(p) > 1}

    duplicates = {s: sorted(p) for s, p in stems.items() if len(p) > 1}
    assert duplicates == manifest["accepted_duplicate_agents"]["agents"]


def test_collapsed_agent_copies_are_absent(vendor_dir: Path, manifest: dict) -> None:
    for stem, rule in manifest["canonical_agents"]["agents"].items():
        assert (vendor_dir / rule["owner"] / "agents" / f"{stem}.md").is_file(), stem
        for plugin in rule["collapsed_from"]:
            assert not (vendor_dir / plugin / "agents" / f"{stem}.md").exists(), (plugin, stem)


def test_pr_review_toolkit_and_pyright_lsp_carry_their_declared_changes(vendor_dir: Path) -> None:
    expected = {"comment-analyzer": "sonnet", "pr-test-analyzer": "sonnet",
                "silent-failure-hunter": "opus", "type-design-analyzer": "opus",
                "code-simplifier": "sonnet", "code-reviewer": "opus"}
    agents = vendor_dir / "pr-review-toolkit" / "agents"
    for name, model in expected.items():
        assert frontmatter((agents / f"{name}.md").read_text(encoding="utf-8"))["model"] == model

    simplifier = (agents / "code-simplifier.md").read_text(encoding="utf-8")
    assert not any(p in simplifier for p in ("ES modules", "arrow functions", "Props types"))
    hunter = frontmatter((agents / "silent-failure-hunter.md").read_text(encoding="utf-8"))
    assert "\\n" not in hunter["description"]

    pyright = json.loads((vendor_dir / "pyright-lsp" / ".claude-plugin" / "plugin.json")
                         .read_text(encoding="utf-8"))
    assert "pyright" in pyright["lspServers"]


def test_command_subagent_references_resolve_to_a_vendored_agent(vendor_dir: Path) -> None:
    declared = {frontmatter(p.read_text(encoding="utf-8"))["name"] for p in agent_files(vendor_dir)}
    dangling = [f"{p.relative_to(vendor_dir).as_posix()}: {ref}"
                for p in sorted(vendor_dir.glob("*/commands/*.md"))
                for ref in SUBAGENT_REF.findall(p.read_text(encoding="utf-8"))
                if ref not in declared and ref not in BUILTIN_AGENTS]
    assert not dangling
