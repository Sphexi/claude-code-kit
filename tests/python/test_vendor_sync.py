"""Tests for the actions, license handling and rendering in ``tools/vendor_sync.py``.

Every test builds a throwaway plugin tree under ``tmp_path``; nothing reads or
writes ``claude/vendor/``.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

AGENT = "---\nname: {name}\ndescription: {desc}\nmodel: {model}\n---\n\nBody of {name}.\n"


@pytest.fixture()
def vs(repo_root: Path) -> ModuleType:
    """The ``tools/vendor_sync.py`` module, loaded by path."""
    path = repo_root / "tools" / "vendor_sync.py"
    spec = importlib.util.spec_from_file_location("vendor_sync_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["vendor_sync_under_test"] = module
    spec.loader.exec_module(module)
    return module


def make_agent(root: Path, stem: str, *, name: str | None = None, model: str = "sonnet",
               desc: str = "Does a thing.", body: str | None = None) -> Path:
    """Write one agent file into ``root/agents``."""
    path = root / "agents" / f"{stem}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    text = AGENT.format(name=name or stem, desc=desc, model=model)
    if body is not None:
        text = text.replace(f"Body of {name or stem}.", body)
    path.write_text(text, encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# frontmatter helpers and set_field
# --------------------------------------------------------------------------- #


def test_replace_field_swallows_a_block_scalar(vs: ModuleType) -> None:
    text = "---\nname: a\ndescription: |\n  line one\n\n  line two\nmodel: opus\n---\nBody\n"
    out = vs.replace_field(text, "description", "Short.")
    assert out == "---\nname: a\ndescription: Short.\nmodel: opus\n---\nBody\n"


def test_set_field_overrides_any_upstream_model(vs: ModuleType, tmp_path: Path) -> None:
    path = make_agent(tmp_path, "x", model="opus")
    vs.Modification(reason="r", set_field=("x", "model", "sonnet")).apply(tmp_path)
    assert vs.frontmatter_field(path.read_text(encoding="utf-8"), "model") == "sonnet"
    assert "Body of x." in path.read_text(encoding="utf-8")


@pytest.mark.parametrize("value", ["Use for X: Y", "Trailing # comment", "|"])
def test_set_field_rejects_unsafe_yaml(vs: ModuleType, tmp_path: Path, value: str) -> None:
    make_agent(tmp_path, "x")
    with pytest.raises(SystemExit):
        vs.Modification(reason="r", set_field=("x", "description", value)).apply(tmp_path)


def test_set_field_fails_when_upstream_dropped_the_key(vs: ModuleType, tmp_path: Path) -> None:
    make_agent(tmp_path, "x")
    with pytest.raises(SystemExit, match="no longer declares"):
        vs.Modification(reason="r", set_field=("x", "tools", "Read")).apply(tmp_path)


# --------------------------------------------------------------------------- #
# rename_agent and insert_note
# --------------------------------------------------------------------------- #


def test_rename_agent_rewrites_bare_references_only(vs: ModuleType, tmp_path: Path) -> None:
    agent = make_agent(tmp_path, "code-reviewer")
    command = tmp_path / "commands" / "run.md"
    command.parent.mkdir()
    command.write_text(
        "Launch code-reviewer agents. See agents/code-reviewer.md. "
        "Not other-code-reviewer or code-reviewer-x.\n",
        encoding="utf-8",
    )
    vs.Modification(reason="r", rename_agent=("code-reviewer", "fd-code-reviewer")).apply(tmp_path)

    assert vs.frontmatter_field(agent.read_text(encoding="utf-8"), "name") == "fd-code-reviewer"
    assert command.read_text(encoding="utf-8") == (
        "Launch fd-code-reviewer agents. See agents/code-reviewer.md. "
        "Not other-code-reviewer or code-reviewer-x.\n"
    )


def test_rename_agent_fails_on_unexpected_upstream_name(vs: ModuleType, tmp_path: Path) -> None:
    make_agent(tmp_path, "code-reviewer", name="something-else")
    with pytest.raises(SystemExit, match="upstream changed"):
        vs.Modification(reason="r", rename_agent=("code-reviewer", "fd-x")).apply(tmp_path)


def test_insert_note_lands_after_frontmatter_once(vs: ModuleType, tmp_path: Path) -> None:
    path = make_agent(tmp_path, "x")
    mod = vs.Modification(reason="r", insert_note=("agents/x.md", "> Note."))
    mod.apply(tmp_path)
    mod.apply(tmp_path)
    text = path.read_text(encoding="utf-8")
    assert text.count("> Note.") == 1
    assert text.index("> Note.") > text.index("model: sonnet\n---")


# --------------------------------------------------------------------------- #
# selection
# --------------------------------------------------------------------------- #


def test_selection_removes_unlisted_components(vs: ModuleType, tmp_path: Path) -> None:
    for stem in ("keep", "drop"):
        make_agent(tmp_path, stem)
    for skill in ("s-keep", "s-drop"):
        (tmp_path / "skills" / skill).mkdir(parents=True)
    removed = vs.apply_selection(tmp_path, vs.Selection(agents=("keep",), skills=("s-keep",)))

    assert removed == ["agents/drop", "skills/s-drop"]
    assert (tmp_path / "agents" / "keep.md").is_file()
    assert not (tmp_path / "skills" / "s-drop").exists()


def test_selection_fails_when_a_kept_item_vanished(vs: ModuleType, tmp_path: Path) -> None:
    make_agent(tmp_path, "present")
    with pytest.raises(SystemExit, match="not present upstream"):
        vs.apply_selection(tmp_path, vs.Selection(agents=("gone",)))


# --------------------------------------------------------------------------- #
# duplicate collapse
# --------------------------------------------------------------------------- #


@pytest.fixture()
def collapse_world(vs: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An upstream clone with an owner plugin, plus a vendored duplicate carrier."""
    owner = tmp_path / "market" / "src" / "plugins" / "owner"
    make_agent(owner, "auditor", name="owner-auditor", body="Shared body.")
    carrier = tmp_path / "vendor" / "carrier"
    make_agent(carrier, "auditor", name="carrier-auditor", body="Shared body.")
    command = carrier / "commands" / "go.md"
    command.parent.mkdir()
    command.write_text(
        f'{vs.LOCAL_AGENTS_CLAIM}\nsubagent_type: "carrier-auditor"\n', encoding="utf-8"
    )

    monkeypatch.setattr(vs, "MARKETPLACES", tmp_path / "market")
    monkeypatch.setitem(vs.SOURCES, "src", vs.Source("src", "r", "a", "n"))
    monkeypatch.setattr(vs, "PLUGINS", [("owner", "src"), ("carrier", "src")])
    monkeypatch.setattr(vs, "COLLAPSE", {"auditor": vs.Collapse("owner", ("carrier",))})
    return carrier


def test_collapse_drops_the_copy_and_retargets(vs: ModuleType, collapse_world: Path) -> None:
    notes = vs.collapse_duplicates("carrier", collapse_world)
    command = (collapse_world / "commands" / "go.md").read_text(encoding="utf-8")

    assert not (collapse_world / "agents" / "auditor.md").exists()
    assert 'subagent_type: "owner-auditor"' in command
    assert vs.LOCAL_AGENTS_CLAIM not in command
    assert vs.LOCAL_AGENTS_REWRITE in command
    assert len(notes) == 1 and "owner-auditor" in notes[0]


def test_collapse_refuses_a_diverged_copy(vs: ModuleType, collapse_world: Path) -> None:
    make_agent(collapse_world, "auditor", name="carrier-auditor", body="Edited body.")
    with pytest.raises(SystemExit, match="diverged"):
        vs.collapse_duplicates("carrier", collapse_world)
    assert (collapse_world / "agents" / "auditor.md").is_file()


# --------------------------------------------------------------------------- #
# tiers, provenance, rendering
# --------------------------------------------------------------------------- #


def test_check_tiers_rejects_inherit_outside_the_allow_list(
    vs: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    make_agent(tmp_path, "x", model="inherit")
    with pytest.raises(SystemExit, match="inherit"):
        vs.check_tiers("some-plugin", tmp_path)
    monkeypatch.setattr(vs, "INHERIT_ALLOWED", frozenset({"allowed-plugin"}))
    vs.check_tiers("allowed-plugin", tmp_path)


def test_tables_name_only_vendored_plugins(vs: ModuleType) -> None:
    vendored = {name for name, _ in vs.PLUGINS}
    for table in (vs.TIERS, vs.DESCRIPTIONS, vs.SELECTION):
        assert set(table) <= vendored, f"unknown plugins: {sorted(set(table) - vendored)}"
    for stem, rule in vs.COLLAPSE.items():
        assert {rule.owner, *rule.duplicates} <= vendored, stem


def test_commit_reads_packed_refs(vs: ModuleType, tmp_path: Path,
                                  monkeypatch: pytest.MonkeyPatch) -> None:
    git = tmp_path / "src" / ".git"
    git.mkdir(parents=True)
    sha = "a" * 40
    (git / "packed-refs").write_text(f"# pack-refs\n{sha} refs/heads/main\n", encoding="utf-8")
    monkeypatch.setattr(vs, "MARKETPLACES", tmp_path)
    assert vs.Source("src", "r", "a", "n").commit() == sha


def make_provenance(vs: ModuleType, **overrides: object) -> object:
    fields = {"commit": "c" * 40, "retrieved": "2026-01-01", "stripped": [],
              "not_vendored": [], "collapsed": []}
    return vs.Provenance(**(fields | overrides))


def test_upstream_md_records_omissions_collapses_and_additions(vs: ModuleType, tmp_path: Path) -> None:
    source = vs.Source("src", "r", "a", "n")
    prov = make_provenance(vs, not_vendored=["agents/c-pro"], collapsed=["`agents/x.md` — collapsed."])
    text = vs.upstream_md("p", source, prov, tmp_path, [], "MIT", ["a.json"])

    assert "## Not vendored" in text and "- `agents/c-pro`" in text
    assert "## Collapsed into canonical copies" in text and "collapsed." in text
    assert text.split("## Local modifications", 1)[1].lstrip().startswith("None")
    assert "| License | MIT (`LICENSE` in this directory) |" in text
    assert "- `a.json`" in text.split("## Files added", 1)[1]


def test_upstream_md_survives_a_parse_and_re_render(vs: ModuleType, tmp_path: Path) -> None:
    source = vs.Source("src", "r", "a", "n")
    prov = make_provenance(vs, stripped=[".codex-plugin/plugin.json"], not_vendored=["agents/x"],
                           collapsed=["`agents/y.md` — dropped."])
    first = vs.upstream_md("p", source, prov, tmp_path, [], "MIT", [])
    assert vs.upstream_md("p", source, vs.parse_upstream(first), tmp_path, [], "MIT", []) == first


# --------------------------------------------------------------------------- #
# license detection and notices
# --------------------------------------------------------------------------- #

APACHE_HEAD = "\n                                 Apache License\n" \
              "                           Version 2.0, January 2004\n"


@pytest.mark.parametrize(("text", "spdx"), [
    ("MIT License\n\nCopyright (c) 2024 X\n", "MIT"),
    (APACHE_HEAD, "Apache-2.0"),
])
def test_detect_license_reads_the_leading_lines(vs: ModuleType, text: str, spdx: str) -> None:
    assert vs.detect_license(text) == spdx


@pytest.mark.parametrize("text", ["", "GNU GENERAL PUBLIC LICENSE\nVersion 3\n",
                                  "Apache License\nVersion 1.1\n"])
def test_detect_license_rejects_anything_else(vs: ModuleType, text: str) -> None:
    with pytest.raises(ValueError):
        vs.detect_license(text)


def test_ensure_license_copies_the_source_root_license_once(
    vs: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "market" / "src").mkdir(parents=True)
    (tmp_path / "market" / "src" / "LICENSE").write_text(
        vs.MIT_TEXT.format(year=2024, holder="Holder"), encoding="utf-8")
    monkeypatch.setattr(vs, "MARKETPLACES", tmp_path / "market")
    plugin = tmp_path / "p"
    plugin.mkdir()
    source = vs.Source("src", "r", "a", "n")

    assert vs.ensure_license("p", plugin, source) == "MIT"
    (plugin / "LICENSE").write_text(vs.MIT_TEXT.format(year=1999, holder="Own"), encoding="utf-8")
    assert vs.ensure_license("p", plugin, source) == "MIT"
    assert "Own" in (plugin / "LICENSE").read_text(encoding="utf-8")


def test_ensure_license_falls_back_then_fails_without_either(
    vs: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(vs, "MARKETPLACES", tmp_path / "none")
    plugin = tmp_path / "p"
    plugin.mkdir()
    fallback = vs.Source("src", "r", "a", "n", fallback_license=vs.MIT_TEXT.format(year=2024, holder="H"))
    assert vs.ensure_license("p", plugin, fallback) == "MIT"

    bare = tmp_path / "q"
    bare.mkdir()
    with pytest.raises(SystemExit, match="no root license"):
        vs.ensure_license("q", bare, vs.Source("src", "r", "a", "n"))


def test_apache_notice_goes_into_changed_markdown_only_and_only_once(
    vs: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plugin = tmp_path / "vendor" / "p"
    make_agent(plugin, "x", model="opus")
    (plugin / "agents" / "untouched.md").write_text("Body.\n", encoding="utf-8")
    (plugin / ".claude-plugin").mkdir()
    (plugin / ".claude-plugin" / "plugin.json").write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(vs, "MODIFICATIONS", {"p": [
        vs.Modification(reason="r", set_field=("x", "model", "sonnet")),
        vs.Modification(reason="r", replace=(".claude-plugin/plugin.json", "{}", "{ }")),
    ]})

    vs.MODIFICATIONS["p"][0].apply(plugin)
    assert vs.apply_notices("p", plugin, "MIT") == []
    vs.apply_notices("p", plugin, "Apache-2.0")
    vs.apply_notices("p", plugin, "Apache-2.0")

    changed = (plugin / "agents" / "x.md").read_text(encoding="utf-8")
    assert changed.count(vs.MODIFIED_NOTICE) == 1
    assert changed.index(vs.MODIFIED_NOTICE) > changed.index("model: sonnet\n---")
    assert vs.MODIFIED_NOTICE not in (plugin / "agents" / "untouched.md").read_text(encoding="utf-8")
    assert (plugin / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8") == "{}\n"


# --------------------------------------------------------------------------- #
# --render-upstream
# --------------------------------------------------------------------------- #


def test_render_upstream_needs_no_clone_and_never_edits_content(
    vs: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    plugin = repo / "claude" / "vendor" / "p"
    make_agent(plugin, "x")
    (plugin / "skills" / "s").mkdir(parents=True)
    (plugin / "skills" / "s" / "SKILL.md").write_text("Skill.\n", encoding="utf-8")
    (plugin / ".claude-plugin").mkdir()
    (plugin / ".claude-plugin" / "plugin.json").write_text('{"name": "p"}\n', encoding="utf-8")
    source = vs.Source("src", "https://example.test/r", "a", "n",
                       fallback_license=vs.MIT_TEXT.format(year=2024, holder="H"))
    monkeypatch.setattr(vs, "SOURCES", {"src": source})
    monkeypatch.setattr(vs, "PLUGINS", [("p", "src")])
    monkeypatch.setattr(vs, "MARKETPLACES", tmp_path / "no-clones")
    monkeypatch.setattr(vs, "MODIFICATIONS", {})
    (plugin / "UPSTREAM.md").write_text(
        vs.upstream_md("p", source, make_provenance(vs), plugin, [], "MIT", []), encoding="utf-8")
    manifest = repo / "claude" / "plugins.manifest.json"
    manifest.write_text('{"generated": "2026-01-01", "upstream_sources": '
                        f'{{"src": {{"vendored_at": "{"c" * 40}"}}}}}}\n', encoding="utf-8")
    content = {p: p.read_bytes() for p in plugin.rglob("*")
               if p.is_file() and p.name not in ("UPSTREAM.md",)}

    assert vs.render_upstream(repo, "2030-01-01") == 0
    first = {p.name: p.read_bytes() for p in plugin.rglob("*") if p.is_file()}
    assert vs.render_upstream(repo, "2030-01-01") == 0

    assert all(p.read_bytes() == data for p, data in content.items())
    assert "Copyright (c) 2024 H" in (plugin / "LICENSE").read_text(encoding="utf-8")
    assert {p.name: p.read_bytes() for p in plugin.rglob("*") if p.is_file()} == first
    written = json.loads(manifest.read_text(encoding="utf-8"))
    assert written["generated"] == "2026-01-01"
    assert written["plugins"][0]["license"] == "MIT"
    assert "2030" not in (plugin / "UPSTREAM.md").read_text(encoding="utf-8")


def test_apply_vendors_from_a_clone_with_license_notice_and_manifest(
    vs: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    market = tmp_path / "market"
    clone = market / "src"
    (clone / ".git" / "refs" / "heads").mkdir(parents=True)
    sha = "d" * 40
    (clone / ".git" / "refs" / "heads" / "main").write_text(sha + "\n", encoding="utf-8")
    (clone / "LICENSE").write_text(APACHE_HEAD, encoding="utf-8")
    upstream = clone / "plugins" / "p"
    make_agent(upstream, "x", model="opus")
    (upstream / ".claude-plugin").mkdir()
    (upstream / ".claude-plugin" / "plugin.json").write_text('{"name": "p", "version": "2.0"}\n',
                                                              encoding="utf-8")
    (upstream / "__pycache__").mkdir()
    (upstream / "__pycache__" / "junk.pyc").write_bytes(b"x")

    repo = tmp_path / "repo"
    monkeypatch.setattr(vs, "REPO_ROOT", repo)
    monkeypatch.setattr(vs, "VENDOR", repo / "claude" / "vendor")
    monkeypatch.setattr(vs, "MANIFEST", repo / "claude" / "plugins.manifest.json")
    monkeypatch.setattr(vs, "SOURCES", {"src": vs.Source("src", "https://example.test/r", "a", "n")})
    monkeypatch.setattr(vs, "PLUGINS", [("p", "src")])
    monkeypatch.setattr(vs, "COLLAPSE", {})
    monkeypatch.setattr(vs, "MODIFICATIONS", {"p": [
        vs.Modification(reason="model", set_field=("x", "model", "sonnet"))]})

    assert vs.main(["--apply", "--marketplaces", str(market), "--date", "2030-02-03"]) == 0

    plugin = repo / "claude" / "vendor" / "p"
    agent_text = (plugin / "agents" / "x.md").read_text(encoding="utf-8")
    assert "model: sonnet" in agent_text and vs.MODIFIED_NOTICE in agent_text
    assert (plugin / "LICENSE").read_text(encoding="utf-8") == APACHE_HEAD
    assert not (plugin / "__pycache__").exists()
    upstream_md = (plugin / "UPSTREAM.md").read_text(encoding="utf-8")
    assert f"| Upstream commit | `{sha}` |" in upstream_md
    assert "| Retrieval date | 2030-02-03 |" in upstream_md
    assert "- `__pycache__/junk.pyc`" in upstream_md
    manifest = json.loads(vs.MANIFEST.read_text(encoding="utf-8"))
    entry = manifest["plugins"][0]
    assert (manifest["schema"], entry["license"], entry["files_modified"]) == (
        "plugins-manifest.v3", "Apache-2.0", ["agents/x.md"])
