"""Scanning the repository layout and a live config directory."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import payload
from tools.reconcile import inventory

CORE = "sphexi-core"
REVIEW = "sphexi-review"


def _write(path: Path, text: str = "x\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


@pytest.mark.parametrize(
    ("files", "expected"),
    [
        ([".claude-plugin/plugin.json", "SKILL.md"], "plugin"),
        (["SKILL.md"], "skill"),
        (["README.md"], None),
    ],
)
def test_classify_skill_dir(tmp_path: Path, files: list[str], expected: str | None) -> None:
    for name in files:
        _write(tmp_path / name)

    assert inventory.classify_skill_dir(tmp_path) == expected


def test_scan_repo_keys_files_by_live_path_with_categories_and_units(fake_repo: Path) -> None:
    selection = payload.Selection((CORE, REVIEW), ("pyright-lsp",))

    inv = inventory.scan_repo(fake_repo, selection)

    assert inv.files["CLAUDE.md"].category == "memory"
    assert inv.files["agents/alpha.md"].unit == "alpha"
    assert inv.files["skills/own-skill/SKILL.md"].category == "skill"
    assert inv.files["skills/sphexi-review/agents/reviewer.md"].unit == REVIEW
    assert inv.files["skills/pyright-lsp/skills/lsp/SKILL.md"].category == "plugin"
    assert {n: d.kind for n, d in inv.skill_dirs.items()} == {
        "own-skill": "skill",
        REVIEW: "plugin",
        "pyright-lsp": "plugin",
    }
    assert inv.files["agents/alpha.md"].source == fake_repo / "plugins" / CORE / "agents" / "alpha.md"


def test_scan_repo_settings_entry_only_when_composed(fake_repo: Path) -> None:
    selection = payload.Selection((CORE,))

    without = inventory.scan_repo(fake_repo, selection)
    with_text = inventory.scan_repo(fake_repo, selection, "{}\n")

    assert "settings.json" not in without.files
    assert with_text.files["settings.json"].sha256 == inventory.sha256_text("{}\n")
    assert with_text.files["settings.json"].source is None


def test_scan_repo_reports_case_insensitive_collisions(
    fake_repo: Path, case_sensitive_fs: None
) -> None:
    _write(fake_repo / "plugins" / CORE / "agents" / "Alpha.md")

    inv = inventory.scan_repo(fake_repo, payload.Selection((CORE,)))

    assert inv.collisions == ["agents/Alpha.md", "agents/alpha.md"]


def test_scan_live_reads_only_managed_roots_and_classifies_skill_dirs(
    tmp_claude_home: Path,
) -> None:
    _write(tmp_claude_home / "sessions" / "abc.jsonl", "{}")
    _write(tmp_claude_home / "history.jsonl", "{}")
    _write(tmp_claude_home / "CLAUDE.md")
    _write(tmp_claude_home / "settings.json", "{}")
    _write(tmp_claude_home / "agents" / "live-only.md")
    _write(
        tmp_claude_home / "skills" / "bundle" / ".claude-plugin" / "plugin.json",
        json.dumps({"name": "bundle"}),
    )
    _write(tmp_claude_home / "skills" / "hand-written" / "SKILL.md")
    _write(tmp_claude_home / "skills" / "mystery" / "README.md")

    inv = inventory.scan_live(tmp_claude_home)

    assert inv.files["CLAUDE.md"].category == "memory"
    assert inv.files["settings.json"].category == "settings"
    assert inv.files["agents/live-only.md"].category == "agent"
    assert inv.files["skills/mystery/README.md"].category == "other"
    assert not [rel for rel in inv.files if rel.startswith(("sessions", "history"))]
    assert {n: d.kind for n, d in inv.skill_dirs.items()} == {
        "bundle": "plugin",
        "hand-written": "skill",
        "mystery": None,
    }


def test_scan_live_missing_config_dir_is_empty(tmp_path: Path) -> None:
    inv = inventory.scan_live(tmp_path / "nope")

    assert inv.files == {} and inv.skill_dirs == {}


def test_is_noise_excludes_build_debris() -> None:
    assert inventory.is_noise(Path("hooks/__pycache__/llm.cpython-312.pyc"))
    assert inventory.is_noise(Path(".DS_Store"))
    assert not inventory.is_noise(Path("hooks/llm.py"))


def test_resolve_config_dir_prefers_explicit_then_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    explicit = tmp_path / "explicit"
    from_env = tmp_path / "from-env"
    explicit.mkdir()
    from_env.mkdir()

    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(from_env))
    assert inventory.resolve_config_dir(str(explicit)) == explicit.resolve()
    assert inventory.resolve_config_dir(None) == from_env.resolve()

    monkeypatch.delenv("CLAUDE_CONFIG_DIR")
    assert inventory.resolve_config_dir(None) == (Path.home() / ".claude").resolve()
