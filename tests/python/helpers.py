"""Plain helpers shared by the deploy and reconcile tests."""

from __future__ import annotations

from pathlib import Path

from tools import deploy as deploy_module
from tools import payload, state
from tools.reconcile import diff, inventory

STAMP = "20260101-000000"
FIXED_NOW = "2026-01-01T00:00:00Z"


def snapshot(root: Path) -> dict[str, str]:
    """Relative POSIX path to SHA-256 for every file under a directory."""
    if not root.is_dir():
        return {}
    return {
        path.relative_to(root).as_posix(): inventory.sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def deploy_repo(repo: Path, home: Path, **kwargs) -> deploy_module.DeployPlan:
    """Run a deployment into ``home`` with no output, no managed settings and Linux overlay."""
    kwargs.setdefault("apply", True)
    kwargs.setdefault("platform_id", "linux")
    kwargs.setdefault("managed_dir", home.parent / "no-managed-settings")
    kwargs.setdefault("timestamp", STAMP)
    kwargs.setdefault("now", lambda: FIXED_NOW)
    kwargs.setdefault("log", lambda _line: None)
    return deploy_module.run_deploy(repo, home, **kwargs)


def compare_repo(
    repo: Path,
    home: Path,
    plugins: tuple[str, ...] = ("sphexi-core", "sphexi-review"),
    extras: tuple[str, ...] = (),
) -> diff.DiffResult:
    """Compare a repository selection against a live home, using its state file."""
    recorded = state.load(state.state_path(home))
    selection = payload.Selection(plugins, extras)
    return diff.compare(
        inventory.scan_repo(repo, selection),
        inventory.scan_live(home),
        recorded.files if recorded else {},
    )


def unit(result: diff.DiffResult, name: str) -> diff.UnitVerdict:
    """Fetch one unit by name, failing with the available names if absent."""
    matches = [u for u in result.units if u.unit == name]
    assert matches, f"no unit named {name!r} in {sorted(u.unit for u in result.units)}"
    return matches[0]


class StateFile:
    """Read and write the state file inside one config directory."""

    def __init__(self, home: Path) -> None:
        self.path = state.state_path(home)

    def read(self) -> state.State:
        loaded = state.load(self.path)
        assert loaded is not None, f"no state file at {self.path}"
        return loaded

    def write(self, **fields) -> state.State:
        record = state.State(**fields)
        state.save(self.path, record, lambda: FIXED_NOW)
        return record
