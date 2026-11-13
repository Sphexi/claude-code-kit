"""Install, update, remove, adopt and merge settings: the only reconcile code that writes.

Every function takes ``apply`` defaulting to ``False``; without it each prints the
absolute path of every file it would touch and returns without changing anything.
"""

from __future__ import annotations

import json
import shutil
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from . import settings_merge
from .diff import UnitVerdict
from .inventory import GLOBAL_MEMORY_TARGET, SETTINGS_TARGET

Logger = Callable[[str], None]

ADOPT_REFUSAL_PLUGIN = (
    "adopt refused: plugins and extras are generated from claude/vendor by "
    "tools/vendor_sync.py and build/build_plugins.py. Change bundle membership or "
    "declare a modification there instead."
)
ADOPT_REFUSAL_UNCLASSIFIABLE = (
    "adopt refused: this content could not be classified, so there is no correct "
    "claude/ subdirectory to copy it into."
)
ADOPT_REFUSAL_SETTINGS = (
    "adopt refused: settings.json is composed from settings.base.json plus an OS "
    "overlay. Edit those files instead."
)
ADOPT_REFUSAL_NOT_AUTHORED = (
    "adopt refused: this content is not authored under claude/ (it is vendored), so a "
    "copy there would collide with the vendored original."
)
REMOVE_REFUSAL = "remove refused: only retired content is ever removed."


class ActionError(Exception):
    """An action cannot be performed safely."""


@dataclass
class ActionRecord:
    """What one verb did, or would have done.

    ``recorded`` and ``forgotten`` are the state-file changes the caller applies;
    ``settings_added`` is the settings entries inserted.
    """

    verb: str
    unit: str
    written: list[Path] = field(default_factory=list)
    removed: list[Path] = field(default_factory=list)
    backups: list[Path] = field(default_factory=list)
    applied: bool = False
    refused: bool = False
    reason: str = ""
    commit_hint: list[str] = field(default_factory=list)
    recorded: dict[str, str] = field(default_factory=dict)
    forgotten: list[str] = field(default_factory=list)
    settings_added: dict = field(default_factory=dict)
    settings_created: bool = False

    @property
    def touched(self) -> int:
        return len(self.written) + len(self.removed)


def _assert_within(path: Path, root: Path, what: str) -> Path:
    resolved = Path(path).resolve()
    root_resolved = Path(root).resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise ActionError(f"refusing to touch {what} outside {root_resolved}: {resolved}")
    return resolved


def _copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _prune_empty_dirs(start: Path, stop: Path) -> None:
    current = start
    stop_resolved = stop.resolve()
    while current.resolve() != stop_resolved:
        if not current.is_dir() or any(current.iterdir()):
            return
        current.rmdir()
        current = current.parent


def _backup_path(path: Path, stamp: str) -> Path:
    candidate = path.with_name(f"{path.name}.bak-{stamp}")
    counter = 1
    while candidate.exists():
        candidate = path.with_name(f"{path.name}.bak-{stamp}-{counter}")
        counter += 1
    return candidate


def _log_plan(log: Logger, record: ActionRecord) -> None:
    for path in record.backups:
        log(f"    backup {path}")
    for path in record.written:
        log(f"    write  {path}")
    for path in record.removed:
        log(f"    DELETE {path}")


def _refuse(record: ActionRecord, reason: str, log: Logger) -> ActionRecord:
    record.refused = True
    record.reason = reason
    log(f"    REFUSE {record.unit} - {reason}")
    return record


def _apply_removals(record: ActionRecord, config_dir: Path) -> None:
    for path in record.removed:
        if path.is_file():
            path.unlink()
            _prune_empty_dirs(path.parent, config_dir)


def _deploy_files(
    unit: UnitVerdict,
    config_dir: Path,
    verb: str,
    *,
    apply: bool,
    log: Logger,
    timestamp: str | None,
) -> ActionRecord:
    """Write the repo's version of a unit; back up live content the kit did not write."""
    record = ActionRecord(verb=verb, unit=unit.unit)
    stamp = timestamp or time.strftime("%Y%m%d-%H%M%S")
    copies: list[tuple[Path, Path]] = []
    backups: list[tuple[Path, Path]] = []

    for verdict in unit.files:
        dst = _assert_within(config_dir / verdict.rel, config_dir, "live file")
        if verdict.repo is not None and verdict.repo.source is not None:
            record.recorded[verdict.rel] = verdict.repo.sha256
            if verdict.klass == "matched":
                continue
            if verdict.live is not None and verdict.live.sha256 != verdict.recorded:
                backup = _backup_path(dst, stamp)
                record.backups.append(backup)
                backups.append((dst, backup))
            record.written.append(dst)
            copies.append((verdict.repo.source, dst))
        elif (
            verb == "update"
            and verdict.klass == "retired"
            and verdict.live is not None
            and verdict.live.sha256 == verdict.recorded
        ):
            record.removed.append(dst)
            record.forgotten.append(verdict.rel)

    _log_plan(log, record)
    if not apply:
        return record
    for original, backup in backups:
        shutil.copy2(original, backup)
    for src, dst in copies:
        _copy(src, dst)
    _apply_removals(record, config_dir)
    record.applied = True
    return record


def install(
    unit: UnitVerdict,
    config_dir: Path,
    *,
    apply: bool = False,
    log: Logger = print,
    timestamp: str | None = None,
) -> ActionRecord:
    """Install a ``missing`` unit."""
    return _deploy_files(unit, config_dir, "install", apply=apply, log=log, timestamp=timestamp)


def update(
    unit: UnitVerdict,
    config_dir: Path,
    *,
    apply: bool = False,
    log: Logger = print,
    timestamp: str | None = None,
) -> ActionRecord:
    """Bring a ``behind`` or ``modified`` unit in line with the repo.

    Live files the kit did not write, or that were edited since, are backed up first.
    """
    return _deploy_files(unit, config_dir, "update", apply=apply, log=log, timestamp=timestamp)


def remove(
    unit: UnitVerdict, config_dir: Path, *, apply: bool = False, log: Logger = print
) -> ActionRecord:
    """Remove the retired files of a unit whose live copy still matches the state hash."""
    record = ActionRecord(verb="remove", unit=unit.unit)
    if unit.klass != "retired":
        return _refuse(record, REMOVE_REFUSAL, log)

    kept = 0
    for verdict in unit.files:
        if verdict.klass != "retired" or verdict.live is None:
            continue
        if verdict.live.sha256 != verdict.recorded:
            kept += 1
            continue
        record.removed.append(_assert_within(config_dir / verdict.rel, config_dir, "live file"))
        record.forgotten.append(verdict.rel)
    if kept:
        record.reason = f"{kept} modified file(s) left in place"

    _log_plan(log, record)
    if not apply:
        return record
    _apply_removals(record, config_dir)
    record.applied = True
    return record


def repo_destination(rel: str, repo_root: Path) -> Path:
    """Map a live-relative path to its authored home under ``<repo>/claude/``."""
    claude = repo_root / "claude"
    if rel == GLOBAL_MEMORY_TARGET:
        return _assert_within(claude / "global-CLAUDE.md", claude, "repo file")
    if rel == SETTINGS_TARGET:
        raise ActionError(ADOPT_REFUSAL_SETTINGS)
    parts = rel.split("/")
    if parts[0] in {"agents", "output-styles", "skills"} and len(parts) >= 2:
        return _assert_within(claude.joinpath(*parts), claude, "repo file")
    raise ActionError(f"no repo destination for {rel!r}")


def adopt(
    unit: UnitVerdict,
    repo_root: Path,
    *,
    apply: bool = False,
    log: Logger = print,
) -> ActionRecord:
    """Copy live content into the clone's ``claude/`` directory and record it as kit-owned."""
    record = ActionRecord(verb="adopt", unit=unit.unit)
    if unit.category == "plugin":
        return _refuse(record, ADOPT_REFUSAL_PLUGIN, log)
    if unit.klass == "unclassifiable":
        return _refuse(record, ADOPT_REFUSAL_UNCLASSIFIABLE, log)
    if unit.category == "settings":
        return _refuse(record, ADOPT_REFUSAL_SETTINGS, log)

    copies: list[tuple[Path, Path]] = []
    for verdict in unit.files:
        if verdict.live is None or verdict.live.source is None:
            continue
        try:
            dst = repo_destination(verdict.rel, repo_root)
        except ActionError as exc:
            return _refuse(record, str(exc), log)
        if verdict.repo is not None and not dst.exists():
            return _refuse(record, ADOPT_REFUSAL_NOT_AUTHORED, log)
        copies.append((verdict.live.source, dst))
        record.written.append(dst)
        record.recorded[verdict.rel] = verdict.live.sha256
        try:
            hint = dst.relative_to(repo_root.resolve()).as_posix()
        except ValueError:
            hint = dst.as_posix()
        record.commit_hint.append(hint)

    _log_plan(log, record)
    if not apply:
        return record
    for src, dst in copies:
        _copy(src, dst)
    record.applied = True
    return record


def merge_settings(
    composed: dict,
    config_dir: Path,
    *,
    apply: bool = False,
    log: Logger = print,
    timestamp: str | None = None,
) -> ActionRecord:
    """Merge composed settings into the live ``settings.json``, adding only."""
    record = ActionRecord(verb="settings", unit=SETTINGS_TARGET)
    target = _assert_within(config_dir / SETTINGS_TARGET, config_dir, "live file")
    created = not target.exists()
    live: dict = {}
    if not created:
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return _refuse(record, f"{target} is not valid JSON; fix it by hand", log)
        if not isinstance(data, dict):
            return _refuse(record, f"{target} is not a JSON object; fix it by hand", log)
        live = data

    new_live, added, _kept = settings_merge.apply_to_live(composed, live)
    record.settings_added = added
    record.settings_created = created
    if not created and new_live == live:
        return record

    backup: Path | None = None
    if not created:
        backup = _backup_path(target, timestamp or time.strftime("%Y%m%d-%H%M%S"))
        record.backups.append(backup)
    record.written.append(target)
    _log_plan(log, record)
    if not apply:
        return record

    config_dir.mkdir(parents=True, exist_ok=True)
    if backup is not None:
        shutil.copy2(target, backup)
    target.write_text(
        json.dumps(new_live, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    record.applied = True
    return record
