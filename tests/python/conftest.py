"""Shared pytest fixtures and configuration."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "slow: spawns a subprocess or deploys a full tree; excluded by default"
    )


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _write_json(path: Path, data: object) -> None:
    _write(path, json.dumps(data, indent=2) + "\n")


@pytest.fixture()
def case_sensitive_fs(tmp_path: Path) -> None:
    """Skip unless ``tmp_path`` can hold two names differing only by case."""
    (tmp_path / "case-probe").touch()
    if (tmp_path / "CASE-PROBE").exists():
        pytest.skip("filesystem is case-insensitive; two names differing by case cannot coexist")
    (tmp_path / "case-probe").unlink()


@pytest.fixture()
def repo_root() -> Path:
    """Absolute path of the repository root."""
    return _REPO_ROOT


@pytest.fixture()
def tmp_claude_home(tmp_path: Path) -> Path:
    """An empty fake live config directory under ``tmp_path``."""
    home = tmp_path / ".claude"
    home.mkdir()
    return home


@pytest.fixture()
def fake_repo(tmp_path: Path) -> Path:
    """A minimal repository tree: generated plugins, authored sources and settings.

    Plugins: ``sphexi-core`` (two agents, one output style, one skill, plus the
    hook, notices and README that are never deployed), ``sphexi-review`` and
    ``sphexi-python``. One extra, ``pyright-lsp``, lives under ``claude/vendor``.
    """
    repo = tmp_path / "repo"
    _write_json(repo / "build" / "kit.json", {"marketplace": "sphexi", "version": "0.1.0"})
    _write(repo / "claude" / "global-CLAUDE.md", "# Global\n")
    _write_json(
        repo / "claude" / "settings.base.json",
        {"outputStyle": "Terse (Full)", "permissions": {"deny": ["Bash(git push *)"]}},
    )
    _write_json(
        repo / "claude" / "settings.linux.json", {"permissions": {"deny": ["Bash(rm -rf /*)"]}}
    )
    _write_json(
        repo / "claude" / "settings.macos.json", {"permissions": {"deny": ["Bash(csrutil *)"]}}
    )
    _write_json(
        repo / "claude" / "settings.windows.json", {"permissions": {"deny": ["Bash(diskpart *)"]}}
    )

    plugins = repo / "plugins"
    for name in ("sphexi-core", "sphexi-review", "sphexi-python"):
        _write_json(plugins / name / ".claude-plugin" / "plugin.json", {"name": name})
        _write(plugins / name / "README.md", f"# {name}\n")

    core = plugins / "sphexi-core"
    _write(core / "agents" / "alpha.md", "---\nname: alpha\n---\nAlpha.\n")
    _write(core / "agents" / "beta.md", "---\nname: beta\n---\nBeta.\n")
    _write(core / "output-styles" / "terse.md", "---\nname: Terse\n---\nTerse.\n")
    _write(core / "skills" / "own-skill" / "SKILL.md", "---\nname: own-skill\n---\nOwn.\n")
    _write(core / "hooks" / "hooks.json", "{}\n")
    _write(core / "notices" / "skill-creator" / "LICENSE", "license\n")

    review = plugins / "sphexi-review"
    _write(review / "agents" / "reviewer.md", "---\nname: reviewer\n---\nReviewer.\n")
    _write(review / "skills" / "helper" / "SKILL.md", "---\nname: helper\n---\nHelper.\n")
    _write(review / "notices" / "demo-member" / "LICENSE", "license\n")

    _write(plugins / "sphexi-python" / "agents" / "py.md", "---\nname: py\n---\nPy.\n")

    extra = repo / "claude" / "vendor" / "pyright-lsp"
    _write_json(extra / ".claude-plugin" / "plugin.json", {"name": "pyright-lsp"})
    _write(extra / "skills" / "lsp" / "SKILL.md", "---\nname: lsp\n---\nLSP.\n")
    return repo


@pytest.fixture()
def state(tmp_claude_home: Path):
    """Read and write the state file of ``tmp_claude_home``."""
    from helpers import StateFile

    return StateFile(tmp_claude_home)
