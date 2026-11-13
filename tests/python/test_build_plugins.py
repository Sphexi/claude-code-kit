"""Tests for ``build/build_plugins.py``: chunking, validation, composition, check mode, zips."""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import zipfile
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_LIMIT = 9500
CORE_NAME = "sphexi-core"
DEMO_NAME = "sphexi-demo"
RESERVED_PREFIXES = ("claude-", "anthropic-", "anthropics-", "cc-plugin-")

MIT_HEAD = "MIT License\n\nCopyright (c) 2024 Holder\n"
APACHE_HEAD = "                                 Apache License\n                           Version 2.0\n"


def load_module() -> ModuleType:
    path = REPO_ROOT / "build" / "build_plugins.py"
    spec = importlib.util.spec_from_file_location("build_plugins_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def bp() -> ModuleType:
    return load_module()


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def agent(name: str, model: str = "sonnet") -> str:
    return f"---\nname: {name}\ndescription: Does {name}.\nmodel: {model}\n---\n\nBody of {name}.\n"


def vendor_plugin(root: Path, name: str, license_head: str, **parts: str) -> Path:
    plugin = root / "claude" / "vendor" / name
    write(plugin / ".claude-plugin" / "plugin.json", json.dumps({"name": name}) + "\n")
    write(plugin / "LICENSE", license_head)
    write(plugin / "UPSTREAM.md", f"# UPSTREAM — `{name}`\n")
    for rel, text in parts.items():
        write(plugin / rel, text)
    return plugin


@pytest.fixture()
def fake_repo(bp: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A two-plugin repo (core plus ``sphexi-demo``) with a table patched to match."""
    root = tmp_path / "repo"
    write(root / "LICENSE", MIT_HEAD)
    write(root / "claude" / "agents" / "alpha.md", agent("alpha"))
    write(root / "claude" / "agents" / "beta.md", agent("beta"))
    write(root / "claude" / "skills" / "own-skill" / "SKILL.md", "---\nname: own-skill\n---\n")
    for stem in ("terse-low", "terse-medium", "terse-full"):
        write(root / "claude" / "output-styles" / f"{stem}.md",
              f"---\nname: {stem}\n---\n\n# {stem}\n\n## Rule\n\nRule for {stem}.\n")
    for name in ("terseness-main.md", "terseness-subagent.md"):
        write(root / "shared" / name, "Shared terseness.\n")
    write(root / "shared" / "code-standards.md",
          "## Comments\n\nA comment says why.\n\n## Tests\n\nTests earn their place.\n")
    write(root / "cowork" / "skills" / "terseness" / "SKILL.md", "---\nname: terseness\n---\n")
    write(root / "shared" / "session-rules.header.md", "Level terse-full is in effect.\n")

    vendor_plugin(root, "core-lib", APACHE_HEAD,
                  **{"skills/lib-skill/SKILL.md": "---\nname: lib-skill\n---\n"})
    vendor_plugin(root, "demo", MIT_HEAD,
                  **{"agents/reviewer.md": agent("demo-reviewer"),
                     "commands/do-thing.md": "Run do-thing.\n",
                     "skills/demo-skill/SKILL.md": "---\nname: demo-skill\n---\n"})
    write(root / "claude" / "plugins.manifest.json", json.dumps({
        "upstream_sources": {"src": {"repo": "https://github.com/o/r", "author": "A",
                                     "vendored_at": "a" * 40}},
        "plugins": [
            {"name": n, "upstream_marketplace": "src", "source_repo": "https://github.com/o/r",
             "license": lic, "bundle": b, "local_modifications": False,
             "files_modified": [], "files_added": []}
            for n, lic, b in (("core-lib", "Apache-2.0", CORE_NAME), ("demo", "MIT", DEMO_NAME))],
    }))
    write(root / "build" / "kit.json", json.dumps({
        "marketplace": "sphexi", "version": "0.1.0", "description": "Demo.",
        "owner": {"name": "sphexi", "url": "https://github.com/sphexi"},
        "homepage": "https://example.test", "repository": "https://github.com/sphexi/kit",
        "license": "MIT", "zip_prefix": "kit",
        "external": [{"name": "ext-plugin", "source": {"source": "github", "repo": "o/ext"},
                      "description": "External.", "category": "x", "homepage": "https://ext.test",
                      "license": "Apache-2.0"}],
    }))
    shutil.copytree(REPO_ROOT / "build" / "templates", root / "build" / "templates")

    monkeypatch.setattr(bp, "BUNDLES", (
        bp.Bundle(CORE_NAME, "Core.", ("core-lib",), category="workflow", tags=("agents",)),
        bp.Bundle(DEMO_NAME, "Demo.", ("demo",), depends_on=(CORE_NAME,), category="demo",
                  tags=("demo",)),
    ))
    monkeypatch.setattr(bp, "EXTRAS", {})
    return root


# --------------------------------------------------------------------------- #
# chunking
# --------------------------------------------------------------------------- #


def sections(count: int, size: int) -> str:
    return "".join(f"## Section {n}\n\n{'x' * size}\n\n" for n in range(count))


def test_chunk_text_packs_whole_sections_and_titles_every_chunk(bp: ModuleType) -> None:
    chunks = bp.chunk_text(sections(5, 4000), "Code Standards")

    assert len(chunks) == 3
    assert all(len(c) <= HOOK_LIMIT for c in chunks)
    assert chunks[1].startswith("# Code Standards (part 2 of 3) — applied for this session\n\n## ")
    assert "".join(c.split("\n\n", 1)[1] for c in chunks).count("## Section") == 5


def test_chunk_text_fails_naming_a_section_over_the_limit(bp: ModuleType) -> None:
    with pytest.raises(bp.BuildError, match="Section 1"):
        bp.chunk_text(sections(1, 100) + "## Section 1 huge\n\n" + "y" * 9600 + "\n", "T")


def test_chunk_text_does_not_split_at_a_heading_inside_a_code_fence(bp: ModuleType) -> None:
    text = "## A\n\n```\n## not a heading\n```\n\n## B\n\nBody.\n"
    assert [s.splitlines()[0] for s in bp.split_sections(text)] == ["## A", "## B"]


def test_level_substitution_that_no_longer_matches_fails(
    bp: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bp, "LEVEL_SUBSTITUTIONS", (("terse-full", "gone text", "new"),))
    with pytest.raises(bp.BuildError, match="no longer matches"):
        bp.apply_substitutions("terse-full", "other text")
    assert bp.apply_substitutions("terse-low", "other text") == "other text"


# --------------------------------------------------------------------------- #
# validation
# --------------------------------------------------------------------------- #


def test_validation_rejects_unassigned_unknown_and_double_assigned_plugins(
    bp: ModuleType, fake_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bp.validate_bundles(fake_repo)

    vendor_plugin(fake_repo, "orphan", MIT_HEAD)
    with pytest.raises(bp.BuildError, match="orphan: vendored but in no bundle"):
        bp.validate_bundles(fake_repo)
    monkeypatch.setattr(bp, "EXTRAS", {"orphan": "extra"})
    bp.validate_bundles(fake_repo)

    monkeypatch.setattr(bp, "BUNDLES", (
        bp.Bundle(CORE_NAME, "c", ("core-lib", "demo")),
        bp.Bundle(DEMO_NAME, "d", ("demo", "ghost"), depends_on=("nope",)),
    ))
    with pytest.raises(bp.BuildError) as error:
        bp.validate_bundles(fake_repo)
    message = str(error.value)
    assert "demo: in both" in message and "'ghost' does not exist" in message
    assert "unknown bundle 'nope'" in message


def test_bundle_index_fails_on_colliding_names_but_collapses_identical_commands(
    bp: ModuleType, fake_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    second = vendor_plugin(fake_repo, "demo-two", MIT_HEAD, **{
        "agents/other.md": agent("Demo-Reviewer"),
        "commands/do-thing.md": "Run do-thing.\n",
        "skills/demo-skill/SKILL.md": "x",
    })
    monkeypatch.setattr(bp, "BUNDLES", (
        bp.Bundle(CORE_NAME, "c", ("core-lib",)),
        bp.Bundle(DEMO_NAME, "d", ("demo", "demo-two"), depends_on=(CORE_NAME,)),
    ))
    with pytest.raises(bp.BuildError) as error:
        bp.bundle_index(fake_repo, bp.BUNDLES[1])
    assert "agent Demo-Reviewer" in str(error.value) and "skill demo-skill" in str(error.value)
    assert "command" not in str(error.value)

    write(second / "commands" / "do-thing.md", "Different.\n")
    with pytest.raises(bp.BuildError, match="command do-thing"):
        bp.bundle_index(fake_repo, bp.BUNDLES[1])


@pytest.mark.parametrize("entry", ["hooks/hooks.json", "bin/tool"])
def test_bundle_member_with_an_unrelocatable_entry_fails(
    bp: ModuleType, fake_repo: Path, entry: str
) -> None:
    write(fake_repo / "claude" / "vendor" / "demo" / entry, "{}")
    with pytest.raises(bp.BuildError, match=entry.split("/")[0]):
        bp.bundle_index(fake_repo, bp.BUNDLES[1])


def test_subagent_references_resolve_through_dependencies_core_and_builtins(
    bp: ModuleType, fake_repo: Path
) -> None:
    command = fake_repo / "claude" / "vendor" / "demo" / "commands" / "do-thing.md"
    write(command, 'subagent_type: "demo-reviewer"\nsubagent_type="alpha"\nsubagent_type: "Explore"\n')
    indexes = {b.name: bp.bundle_index(fake_repo, b) for b in bp.BUNDLES}
    bp.check_references(indexes)

    write(command, 'subagent_type: "ghost-agent"\n')
    indexes = {b.name: bp.bundle_index(fake_repo, b) for b in bp.BUNDLES}
    with pytest.raises(bp.BuildError, match="ghost-agent.*no bundle provides it"):
        bp.check_references(indexes)


# --------------------------------------------------------------------------- #
# composition, determinism, check mode
# --------------------------------------------------------------------------- #


def test_core_and_bundle_trees_have_the_designed_file_lists_and_licenses(
    bp: ModuleType, fake_repo: Path
) -> None:
    outputs, trees = bp.generate(fake_repo)

    assert sorted(trees[CORE_NAME]) == [
        ".claude-plugin/plugin.json", "LICENSE", "README.md", "agents/alpha.md", "agents/beta.md",
        "hooks/code-standards-1.md", "hooks/hooks.json", "hooks/session-rules-1.md",
        "notices/core-lib/LICENSE",
        "notices/core-lib/UPSTREAM.md", "output-styles/terse-full.md",
        "output-styles/terse-low.md", "output-styles/terse-medium.md",
        "skills/lib-skill/SKILL.md", "skills/own-skill/SKILL.md",
    ]
    assert sorted(trees[DEMO_NAME]) == [
        ".claude-plugin/plugin.json", "LICENSE", "README.md", "agents/demo-reviewer.md",
        "commands/do-thing.md", "notices/demo/LICENSE", "notices/demo/UPSTREAM.md",
        "skills/demo-skill/SKILL.md",
    ]
    licenses = {n: json.loads(t[".claude-plugin/plugin.json"])["license"] for n, t in trees.items()}
    assert licenses == {CORE_NAME: "MIT AND Apache-2.0", DEMO_NAME: "MIT"}
    assert trees[CORE_NAME]["agents/alpha.md"] == (fake_repo / "claude/agents/alpha.md").read_bytes()
    assert "plugins/README.md" in outputs and "docs/plugins.md" in outputs
    assert "/plugin install sphexi-demo@sphexi" in trees[DEMO_NAME]["README.md"].decode()


def test_generation_is_deterministic_and_check_reports_stale_missing_extra(
    bp: ModuleType, fake_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first, _ = bp.generate(fake_repo)
    second, _ = bp.generate(fake_repo)
    assert first == second

    assert bp.main(["--repo-root", str(fake_repo)]) == 0
    assert bp.main(["--check", "--repo-root", str(fake_repo)]) == 0

    plugin = fake_repo / "plugins" / DEMO_NAME
    (plugin / "README.md").write_text("edited\n", encoding="utf-8")
    (plugin / "commands" / "do-thing.md").unlink()
    write(plugin / "stray.md", "stray\n")
    capsys.readouterr()
    assert bp.main(["--check", "--repo-root", str(fake_repo)]) == 1
    err = capsys.readouterr().err
    assert f"stale: plugins/{DEMO_NAME}/README.md" in err
    assert f"missing: plugins/{DEMO_NAME}/commands/do-thing.md" in err
    assert f"extra: plugins/{DEMO_NAME}/stray.md" in err
    assert (plugin / "stray.md").exists(), "--check must not write"

    assert bp.main(["--repo-root", str(fake_repo)]) == 0
    assert not (plugin / "stray.md").exists()
    assert bp.main(["--check", "--repo-root", str(fake_repo)]) == 0


# --------------------------------------------------------------------------- #
# zips
# --------------------------------------------------------------------------- #


def test_zips_are_reproducible_and_core_carries_the_cowork_overlay(
    bp: ModuleType, fake_repo: Path, tmp_path: Path
) -> None:
    bp.main(["--repo-root", str(fake_repo)])
    first, second = tmp_path / "z1", tmp_path / "z2"
    assert bp.main(["--zip", "--version", "v0.1.0", "--output-dir", str(first),
                    "--repo-root", str(fake_repo)]) == 0
    assert bp.main(["--zip", "--output-dir", str(second), "--repo-root", str(fake_repo)]) == 0

    names = sorted(p.name for p in first.iterdir())
    assert names == [f"kit-{CORE_NAME}-0.1.0.zip", f"kit-{DEMO_NAME}-0.1.0.zip"]
    for name in names:
        assert (first / name).read_bytes() == (second / name).read_bytes()

    with zipfile.ZipFile(first / names[0]) as core, zipfile.ZipFile(first / names[1]) as demo:
        core_names = set(core.namelist())
        demo_names = set(demo.namelist())
        committed_core = {p.relative_to(fake_repo / "plugins" / CORE_NAME).as_posix()
                          for p in (fake_repo / "plugins" / CORE_NAME).rglob("*") if p.is_file()}
        hooks = json.loads(core.read("hooks/hooks.json"))["hooks"]["SessionStart"][0]["hooks"]
        assert core_names - committed_core == {
            "skills/terseness/SKILL.md", "skills/terseness/levels/terse-full.md",
            "skills/terseness/levels/terse-low.md", "skills/terseness/levels/terse-medium.md"}
        assert [h["command"].rsplit("/", 1)[1].rstrip('"') for h in hooks] == [
            "code-standards-1.md", "session-rules-1.md"]
        assert core.read("skills/terseness/levels/terse-full.md").decode().startswith("# terse-full")
        assert demo_names == {p.relative_to(fake_repo / "plugins" / DEMO_NAME).as_posix()
                              for p in (fake_repo / "plugins" / DEMO_NAME).rglob("*") if p.is_file()}


def test_zip_refuses_a_version_mismatch_and_a_drifted_tree(
    bp: ModuleType, fake_repo: Path, tmp_path: Path
) -> None:
    out = tmp_path / "zips"
    assert bp.main(["--repo-root", str(fake_repo)]) == 0

    assert bp.main(["--zip", "--version", "9.9.9", "--output-dir", str(out),
                    "--repo-root", str(fake_repo)]) == 2
    (fake_repo / "plugins" / DEMO_NAME / "README.md").write_text("edited\n", encoding="utf-8")
    assert bp.main(["--zip", "--output-dir", str(out), "--repo-root", str(fake_repo)]) == 1
    assert not out.exists()


# --------------------------------------------------------------------------- #
# the real repository
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def real() -> tuple[ModuleType, dict[str, bytes], dict[str, dict[str, bytes]]]:
    module = load_module()
    outputs, trees = module.generate(REPO_ROOT)
    return module, outputs, trees


def test_committed_outputs_equal_a_fresh_build(real: tuple) -> None:
    module, outputs, _ = real
    stale, missing, extra = module.compare(REPO_ROOT, outputs)
    assert (stale, missing, extra) == ([], [], [])


def test_hook_payloads_fit_the_cap_and_every_hook_command_names_a_real_file(real: tuple) -> None:
    _, _, trees = real
    core = trees[CORE_NAME]
    payloads = [n for n in core if n.startswith("hooks/") and n.endswith(".md")]
    assert payloads
    assert all(len(core[n].decode("utf-8")) <= HOOK_LIMIT for n in payloads)
    hooks = json.loads(core["hooks/hooks.json"])["hooks"]["SessionStart"][0]["hooks"]
    assert sorted(f"hooks/{h['command'].split('/hooks/')[1].rstrip(chr(34))}" for h in hooks) == sorted(payloads)
    assert all('"${CLAUDE_PLUGIN_ROOT}' in h["command"] for h in hooks)


def test_marketplace_json_invariants_hold(real: tuple) -> None:
    _, _, trees = real
    marketplace = json.loads((REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text("utf-8"))
    kit = json.loads((REPO_ROOT / "build" / "kit.json").read_text("utf-8"))
    entries = {e["name"]: e for e in marketplace["plugins"]}

    assert marketplace["name"] == "sphexi" and marketplace["version"] == kit["version"]
    external = {e["name"]: e for e in kit["external"]}
    assert set(entries) == set(trees) | set(external)
    for name, entry in entries.items():
        assert not name.startswith(RESERVED_PREFIXES)
        assert "version" not in entry
        assert all(dep in entries for dep in entry.get("dependencies", []))
        source = entry["source"]
        if isinstance(source, str):
            assert source.startswith("./") and ".." not in source and "\\" not in source
            assert (REPO_ROOT / source).is_dir()
            plugin = json.loads((REPO_ROOT / source / ".claude-plugin" / "plugin.json").read_text("utf-8"))
            assert plugin["name"] == name and plugin["version"] == kit["version"]
            assert "dependencies" not in plugin
    for name, entry in external.items():
        assert entries[name] == entry
        assert entry["source"]["source"] == "github" and "path" not in entry["source"]


def test_every_real_plugin_carries_notice_licenses_and_no_bin(real: tuple) -> None:
    module, _, trees = real
    manifest = json.loads((REPO_ROOT / "claude" / "plugins.manifest.json").read_text("utf-8"))
    licenses = {p["name"]: p["license"] for p in manifest["plugins"]}
    for bundle in module.BUNDLES:
        tree = trees[bundle.name]
        for member in bundle.plugins:
            assert f"notices/{member}/LICENSE" in tree and f"notices/{member}/UPSTREAM.md" in tree
        expected = {"MIT"} | {licenses[m] for m in bundle.plugins}
        declared = json.loads(tree[".claude-plugin/plugin.json"])["license"]
        assert set(declared.split(" AND ")) == expected
        assert not any(n.split("/", 1)[0] == "bin" for n in tree)


def test_real_core_ships_thirteen_agents_four_skills_and_three_styles(real: tuple) -> None:
    _, _, trees = real
    core = trees[CORE_NAME]
    assert len([n for n in core if n.startswith("agents/")]) == 13
    assert {n.split("/")[1] for n in core if n.startswith("skills/")} == {
        "code-comments", "skill-creator", "systematic-debugging", "test-discipline"}
    assert len([n for n in core if n.startswith("output-styles/")]) == 3
