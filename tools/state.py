"""Read and write the deploy state file that records what the kit owns."""

from __future__ import annotations

import json
import os
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

STATE_FILENAME = "claude-code-kit-state.json"
SCHEMA = 1

Clock = Callable[[], str]


class StateError(Exception):
    """The state file exists but cannot be used."""


def utc_now() -> str:
    """Current UTC time as ``YYYY-MM-DDTHH:MM:SSZ``."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


@dataclass
class State:
    """Every path and settings entry the kit wrote, with the hashes written."""

    kit_version: str = "unknown"
    repo: str = ""
    updated: str = ""
    plugins: list[str] = field(default_factory=list)
    extras: list[str] = field(default_factory=list)
    claude_md: bool = True
    settings: bool = True
    files: dict[str, str] = field(default_factory=dict)
    settings_added: dict[str, object] = field(default_factory=dict)
    settings_created: bool = False

    def to_dict(self) -> dict:
        return {
            "schema": SCHEMA,
            "kit_version": self.kit_version,
            "repo": self.repo,
            "updated": self.updated,
            "plugins": self.plugins,
            "extras": self.extras,
            "claude_md": self.claude_md,
            "settings": self.settings,
            "files": dict(sorted(self.files.items())),
            "settings_added": self.settings_added,
            "settings_created": self.settings_created,
        }


def state_path(config_dir: Path) -> Path:
    """Location of the state file inside a config dir."""
    return config_dir / STATE_FILENAME


def read_kit_version(repo: Path) -> str:
    """Version from ``build/kit.json``, or ``unknown`` when it cannot be read."""
    try:
        data = json.loads((repo / "build" / "kit.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "unknown"
    version = data.get("version") if isinstance(data, dict) else None
    return version if isinstance(version, str) else "unknown"


def _strings(value: object, key: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise StateError(f"state key {key!r} must be a list of strings")
    return list(value)


def load(path: Path) -> State | None:
    """Read a state file; ``None`` when absent.

    Raises:
        StateError: The file is not valid JSON or does not match the schema.
    """
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StateError(f"{path} is unreadable: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise StateError(f"{path} is not a schema {SCHEMA} state file")
    files = data.get("files", {})
    if not isinstance(files, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in files.items()
    ):
        raise StateError(f"{path}: 'files' must map paths to hashes")
    added = data.get("settings_added", {})
    if not isinstance(added, dict):
        raise StateError(f"{path}: 'settings_added' must be an object")
    return State(
        kit_version=str(data.get("kit_version", "unknown")),
        repo=str(data.get("repo", "")),
        updated=str(data.get("updated", "")),
        plugins=_strings(data.get("plugins", []), "plugins"),
        extras=_strings(data.get("extras", []), "extras"),
        claude_md=bool(data.get("claude_md", True)),
        settings=bool(data.get("settings", True)),
        files=dict(files),
        settings_added=added,
        settings_created=bool(data.get("settings_created", False)),
    )


def save(path: Path, state: State, now: Clock = utc_now) -> None:
    """Write the state file atomically, stamping ``updated`` from ``now``."""
    state.updated = now()
    text = json.dumps(state.to_dict(), indent=2, ensure_ascii=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{STATE_FILENAME}.")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.replace(temp_name, path)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise
