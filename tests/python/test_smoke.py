"""Deploy, refresh and uninstall through the platform wrapper, against the real repository."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from helpers import snapshot

from tools import payload

pytestmark = pytest.mark.slow

ROOT = Path(__file__).resolve().parents[2]
TIMEOUT = 300
ACTIONABLE_ZERO = re.compile(r"units: .*missing=0\s+behind=0\s+modified=0\s+retired=0")


def _wrapper(name: str) -> list[str]:
    if sys.platform == "win32":
        shell = shutil.which("powershell") or shutil.which("pwsh")
        if shell is None:
            pytest.skip("no PowerShell on PATH")
        return [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / f"{name}.ps1")]
    shell = "/bin/bash" if sys.platform == "darwin" else "bash"
    return [shell, str(ROOT / f"{name}.sh")]


def _run(name: str, config: Path, cwd: Path, env: dict[str, str], *args: str):
    return subprocess.run(
        [*_wrapper(name), "--config-dir", str(config), *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=TIMEOUT,
        check=False,
    )


def test_wrapper_round_trip_deploy_refresh_uninstall(tmp_path: Path) -> None:
    if not (ROOT / "plugins").is_dir():
        pytest.skip("plugins/ has not been generated")
    home = tmp_path / "home"
    config = tmp_path / "claude"
    (config / "agents").mkdir(parents=True)
    (config / "agents" / "mine.md").write_text("mine\n", encoding="utf-8")
    (config / "settings.json").write_text(json.dumps({"theme": "dark"}), encoding="utf-8")
    home.mkdir()
    env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home)}
    env.pop("CLAUDE_CONFIG_DIR", None)
    before = snapshot(config)
    expected = {
        p.target
        for p in payload.layout(ROOT, payload.default_selection(ROOT).plugins, [], True)
    }

    dry = _run("deploy", config, tmp_path, env)
    assert dry.returncode == 0, dry.stderr
    assert snapshot(config) == before

    applied = _run("deploy", config, tmp_path, env, "--apply")
    assert applied.returncode == 0, applied.stderr
    assert expected <= set(snapshot(config))

    refreshed = _run("refresh", config, tmp_path, env)
    assert refreshed.returncode == 0, refreshed.stderr
    assert ACTIONABLE_ZERO.search(refreshed.stdout), refreshed.stdout

    removed = _run("deploy", config, tmp_path, env, "--uninstall", "--apply")
    assert removed.returncode == 0, removed.stderr
    after = snapshot(config)
    added = set(after) - set(before)
    assert [p for p in added if ".bak-" not in p] == []
    assert all(after[p] == before[p] for p in before if p != "settings.json")
    assert json.loads((config / "settings.json").read_text(encoding="utf-8")) == {"theme": "dark"}
