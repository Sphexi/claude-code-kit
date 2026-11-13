#!/usr/bin/env python3
"""Deploy the kit into a live Claude Code config directory, or remove it again.

    python -m tools.deploy [--apply] [--config-dir PATH] [--plugins LIST]
                           [--extra NAME]... [--overwrite] [--no-settings]
                           [--no-claude-md] [--uninstall] [--quiet]

Without ``--apply`` nothing is written, backed up or removed.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import sys
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from . import payload, state
from .reconcile import inventory, settings_merge

REPO_ROOT = Path(__file__).resolve().parents[1]
MARKETPLACE = "sphexi"
WORKFLOWS_MARKETPLACE = "claude-code-workflows"
UNIT_CATEGORIES = frozenset({"plugin", "skill"})

MANAGED_DIRS = {
    "windows": Path(r"C:\Program Files\ClaudeCode"),
    "macos": Path("/Library/Application Support/ClaudeCode"),
    "linux": Path("/etc/claude-code"),
}

Logger = Callable[[str], None]


class DeployError(Exception):
    """Deployment cannot proceed safely."""


@dataclass
class DeployPlan:
    """Everything a run did, or would do."""

    written: list[Path] = field(default_factory=list)
    backups: list[Path] = field(default_factory=list)
    removed: list[Path] = field(default_factory=list)
    conflicts: list[Path] = field(default_factory=list)
    unchanged: int = 0
    kept_values: list[settings_merge.KeptValue] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    applied: bool = False

    def summary(self) -> str:
        """One-line count of what changed."""
        will = "" if self.applied else "would "
        return (
            f"{will}write {len(self.written)} file(s), {will}back up {len(self.backups)}, "
            f"{will}remove {len(self.removed)}; {self.unchanged} unchanged, "
            f"{len(self.conflicts)} conflict(s) skipped"
        )


@dataclass
class _Item:
    placement: payload.Placement
    source_hash: str
    status: str
    blocked: bool = False


def managed_settings_files(directory: Path) -> list[Path]:
    """The managed settings file and its drop-ins, in the order Claude Code merges them."""
    files: list[Path] = []
    main = directory / "managed-settings.json"
    if main.is_file():
        files.append(main)
    drop_ins = directory / "managed-settings.d"
    if drop_ins.is_dir():
        files.extend(
            p for p in sorted(drop_ins.glob("*.json")) if not p.name.startswith(".") and p.is_file()
        )
    return files


def check_managed_settings(files: list[Path]) -> list[str]:
    """Warn about managed settings that disable plugins loaded from ``skills-dir``."""
    merged: dict = {}
    warnings: list[str] = []
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            warnings.append(f"managed settings at {path} could not be read ({exc}); check it by hand")
            continue
        if isinstance(data, dict):
            merged.update(data)

    strict = merged.get("strictKnownMarketplaces")
    if strict is not None and not any(
        isinstance(entry, dict) and entry.get("source") == "skills-dir"
        for entry in (strict if isinstance(strict, list) else [])
    ):
        warnings.append(
            "managed settings set strictKnownMarketplaces without a "
            '{"source": "skills-dir"} entry, which disables every plugin deployed '
            "under skills/ with no visible cause"
        )
    blocked = merged.get("blockedMarketplaces")
    if isinstance(blocked, list):
        for entry in blocked:
            source = entry.get("source") if isinstance(entry, dict) else entry
            if source == "skills-dir":
                warnings.append(
                    "managed settings block the skills-dir source; every plugin "
                    "deployed under skills/ will be inert"
                )
                break
    if merged.get("strictPluginOnlyCustomization"):
        warnings.append(
            "managed settings set strictPluginOnlyCustomization, which blocks skills "
            "and agents from user sources such as ~/.claude"
        )
    return warnings


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def duplicate_warnings(
    repo: Path, config_dir: Path, plugins: list[str], extras: list[str]
) -> list[str]:
    """Read-only warnings about marketplace installs that duplicate this deployment."""
    installed = _read_json(config_dir / "plugins" / "installed_plugins.json")
    ids: set[str] = set()
    if isinstance(installed, dict) and isinstance(installed.get("plugins"), dict):
        ids.update(installed["plugins"])
    live = _read_json(config_dir / payload.SETTINGS_TARGET)
    if isinstance(live, dict) and isinstance(live.get("enabledPlugins"), dict):
        ids.update(live["enabledPlugins"])

    core = payload.core_plugin()
    vendored = set(extras)
    for name in plugins:
        notices = repo / payload.PLUGINS_DIR / name / "notices"
        if notices.is_dir():
            vendored.update(entry.name for entry in notices.iterdir() if entry.is_dir())

    warnings: list[str] = []
    for plugin_id in sorted(ids):
        name, _, market = plugin_id.rpartition("@")
        if not name:
            continue
        if market == MARKETPLACE:
            if name == core and core in plugins:
                warnings.append(
                    f"{plugin_id} is installed from the marketplace, so the agents this "
                    f"deployment writes will appear twice (python-engineer and "
                    f"{core}:python-engineer). Deploy with --plugins excluding {core}, "
                    f"or run: claude plugin uninstall {plugin_id}"
                )
            elif name in plugins:
                warnings.append(
                    f"{plugin_id} is installed from the marketplace; the marketplace copy "
                    f"loads and the deployed skills/{name} copy shows 'Not loaded'"
                )
        elif name in vendored or market == WORKFLOWS_MARKETPLACE:
            warnings.append(
                f"{plugin_id} duplicates content this deployment installs under another "
                f"namespace. To load it once: claude plugin uninstall {plugin_id}"
            )
    return warnings


def _inspect(path: Path) -> tuple[str, str | None]:
    if path.is_symlink():
        return "symlink", None
    if not path.exists():
        return "absent", None
    if not path.is_file():
        return "notfile", None
    try:
        return "file", payload.sha256_file(path)
    except OSError:
        return "unreadable", None


def _safe_path(config_dir: Path, rel: str) -> Path:
    parts = rel.split("/")
    if not rel or rel.startswith("/") or ".." in parts or ":" in parts[0] or "\\" in rel:
        raise DeployError(f"refusing path outside the config dir: {rel!r}")
    return config_dir.joinpath(*parts)


def _classify(
    placement: payload.Placement, config_dir: Path, recorded: dict[str, str]
) -> _Item:
    source_hash = payload.sha256_file(placement.source)
    kind, live_hash = _inspect(_safe_path(config_dir, placement.target))
    if kind == "absent":
        return _Item(placement, source_hash, "write")
    if kind != "file":
        return _Item(placement, source_hash, "conflict", blocked=True)
    if live_hash == source_hash:
        return _Item(placement, source_hash, "unchanged")
    if placement.target in recorded and live_hash == recorded[placement.target]:
        return _Item(placement, source_hash, "update")
    return _Item(placement, source_hash, "conflict")


def _resolve_conflicts(items: list[_Item], overwrite: bool) -> None:
    groups: dict[tuple[str, str], list[_Item]] = defaultdict(list)
    for item in items:
        if item.placement.category in UNIT_CATEGORIES:
            groups[(item.placement.category, item.placement.unit)].append(item)
        else:
            groups[(item.placement.category, item.placement.target)].append(item)
    for group in groups.values():
        conflicts = [i for i in group if i.status == "conflict"]
        if not conflicts:
            continue
        if overwrite and not any(i.blocked for i in conflicts):
            for item in conflicts:
                item.status = "overwrite"
            continue
        for item in group:
            if item.status in ("write", "update"):
                item.status = "skip"


def _backup_path(path: Path, stamp: str) -> Path:
    candidate = path.with_name(f"{path.name}.bak-{stamp}")
    counter = 1
    while candidate.exists():
        candidate = path.with_name(f"{path.name}.bak-{stamp}-{counter}")
        counter += 1
    return candidate


def _unlink(path: Path) -> None:
    try:
        path.unlink()
    except PermissionError:
        os.chmod(path, stat.S_IWRITE)
        path.unlink()


def _prune_empty(start: Path, stop: Path) -> None:
    current = start
    while current != stop and stop in current.parents:
        try:
            current.rmdir()
        except OSError:
            return
        current = current.parent


def _deploy_settings(
    repo: Path,
    config_dir: Path,
    plan: DeployPlan,
    *,
    apply: bool,
    platform_id: str,
    stamp: str,
    log: Logger,
) -> tuple[dict, bool] | None:
    """Merge composed settings into the live file; returns ``(added, created)``."""
    try:
        composed = settings_merge.compose(repo / "claude", platform_id)
    except settings_merge.SettingsError as exc:
        raise DeployError(str(exc)) from exc
    plan.notes.append(
        "settings composed from " + ", ".join(p.name for p in composed.sources)
    )

    target = config_dir / payload.SETTINGS_TARGET
    created = not target.exists()
    live: dict = {}
    if not created:
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            plan.warnings.append(f"{target} is not valid JSON ({exc}); settings left untouched")
            return None
        if not isinstance(data, dict):
            plan.warnings.append(f"{target} is not a JSON object; settings left untouched")
            return None
        live = data

    new_live, added, kept = settings_merge.apply_to_live(composed.settings, live)
    plan.kept_values.extend(kept)
    if not created and new_live == live:
        return {}, False

    if not created:
        backup = _backup_path(target, stamp)
        plan.backups.append(backup)
        log(f"    backup {backup}")
        if apply:
            shutil.copy2(target, backup)
    plan.written.append(target)
    log(f"    write  {target}")
    if apply:
        config_dir.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(new_live, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return added, created


def resolve_plugins(repo: Path, requested: list[str] | None, plan: DeployPlan) -> list[str]:
    """Selected plugin names; every generated plugin when none are requested."""
    try:
        available = payload.available_plugins(repo)
    except payload.PayloadError as exc:
        raise DeployError(str(exc)) from exc
    if requested is None:
        missing = [n for n in payload.bundle_names() if n not in available]
        if missing:
            plan.warnings.append(f"plugins not found under plugins/: {', '.join(missing)}")
        return available
    unknown = [name for name in requested if name not in available]
    if unknown:
        raise DeployError(
            f"unknown plugin(s): {', '.join(unknown)}. Available: {', '.join(available)}"
        )
    return list(dict.fromkeys(requested))


def run_deploy(
    repo: Path,
    config_dir: Path,
    *,
    apply: bool = False,
    plugins: list[str] | None = None,
    extras: list[str] | None = None,
    overwrite: bool = False,
    settings: bool = True,
    claude_md: bool = True,
    log: Logger = print,
    platform_id: str | None = None,
    managed_dir: Path | None = None,
    timestamp: str | None = None,
    now: state.Clock = state.utc_now,
) -> DeployPlan:
    """Deploy the selection into ``config_dir``.

    Raises:
        DeployError: The selection or the state file is unusable.
    """
    plan = DeployPlan(applied=apply)
    platform_id = platform_id or sys.platform
    stamp = timestamp or time.strftime("%Y%m%d-%H%M%S")
    extras = list(dict.fromkeys(extras or []))

    try:
        prior = state.load(state.state_path(config_dir))
    except state.StateError as exc:
        raise DeployError(f"{exc}; fix or delete it before deploying") from exc

    chosen = resolve_plugins(repo, plugins, plan)
    try:
        built = payload.build_layout(repo, chosen, extras, claude_md)
    except payload.PayloadError as exc:
        raise DeployError(str(exc)) from exc
    collisions = payload.find_collisions(built.placements)
    if collisions:
        raise DeployError(
            "targets collide on a case-insensitive filesystem: " + ", ".join(collisions)
        )
    for target, reason in built.skipped:
        plan.notes.append(f"{target} is a {reason}; not deployed")

    directory = managed_dir or MANAGED_DIRS[settings_merge.overlay_for(platform_id)]
    plan.warnings.extend(check_managed_settings(managed_settings_files(directory)))
    plan.warnings.extend(duplicate_warnings(repo, config_dir, chosen, extras))

    recorded = dict(prior.files) if prior else {}
    items = [_classify(p, config_dir, recorded) for p in built.placements]
    _resolve_conflicts(items, overwrite)

    new_files = dict(recorded)
    log("files:")
    for item in items:
        target_path = _safe_path(config_dir, item.placement.target)
        match item.status:
            case "unchanged":
                plan.unchanged += 1
                new_files[item.placement.target] = item.source_hash
            case "conflict" | "skip":
                if item.status == "conflict":
                    plan.conflicts.append(target_path)
                    log(f"    CONFLICT {target_path}")
                else:
                    log(f"    skip   {target_path} (unit has a conflict)")
            case "write" | "update" | "overwrite":
                if item.status == "overwrite":
                    backup = _backup_path(target_path, stamp)
                    plan.backups.append(backup)
                    log(f"    backup {backup}")
                    if apply:
                        shutil.copy2(target_path, backup)
                log(f"    {item.status:<6} {target_path}")
                plan.written.append(target_path)
                if apply:
                    try:
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(item.placement.source, target_path)
                    except OSError as exc:
                        plan.written.remove(target_path)
                        plan.warnings.append(f"could not write {target_path}: {exc.strerror or exc}")
                        continue
                new_files[item.placement.target] = item.source_hash

    if plan.conflicts:
        plan.notes.append(
            f"{len(plan.conflicts)} conflicting file(s) were not written; units containing one "
            "were skipped whole. Re-run with --overwrite to replace them (each is backed up first)."
        )

    wanted = {p.target for p in built.placements}
    for rel in sorted(set(recorded) - wanted):
        if rel == payload.MEMORY_TARGET and not claude_md:
            continue
        path = _safe_path(config_dir, rel)
        kind, live_hash = _inspect(path)
        if kind == "absent":
            new_files.pop(rel, None)
        elif kind == "file" and live_hash == recorded[rel]:
            log(f"    DELETE {path} (no longer shipped)")
            plan.removed.append(path)
            new_files.pop(rel, None)
            if apply:
                _unlink(path)
                _prune_empty(path.parent, config_dir)
        else:
            plan.warnings.append(f"{path} is no longer shipped but was modified; left in place")

    settings_added: dict = prior.settings_added if prior else {}
    settings_created = prior.settings_created if prior else False
    if settings:
        log("settings:")
        merged = _deploy_settings(
            repo, config_dir, plan, apply=apply, platform_id=platform_id, stamp=stamp, log=log
        )
        if merged is not None:
            added, created = merged
            settings_added = settings_merge.merge_added(settings_added, added)
            settings_created = settings_created or created
        for kept in plan.kept_values:
            plan.notes.append(
                f"kept user value for {kept.key}: {kept.live!r} (kit sets {kept.kit!r})"
            )

    if apply:
        record = prior or state.State()
        record.kit_version = state.read_kit_version(repo)
        record.repo = str(repo.resolve())
        record.plugins = chosen
        record.extras = extras
        record.claude_md = claude_md or (prior.claude_md if prior else False)
        record.files = new_files
        record.settings_added = settings_added
        record.settings_created = settings_created
        record.settings = settings or (prior.settings if prior else False)
        state.save(state.state_path(config_dir), record, now)
    return plan


def run_uninstall(
    config_dir: Path,
    *,
    apply: bool = False,
    log: Logger = print,
    timestamp: str | None = None,
    now: state.Clock = state.utc_now,
) -> DeployPlan:
    """Remove what the state file records, keeping anything the user changed."""
    plan = DeployPlan(applied=apply)
    stamp = timestamp or time.strftime("%Y%m%d-%H%M%S")
    path = state.state_path(config_dir)
    try:
        record = state.load(path)
    except state.StateError as exc:
        raise DeployError(f"{exc}; fix or delete it before uninstalling") from exc
    if record is None:
        plan.notes.append(f"no state file at {path}; nothing was deployed by the kit")
        return plan

    log("files:")
    remaining: dict[str, str] = {}
    for rel, recorded_hash in sorted(record.files.items()):
        target = _safe_path(config_dir, rel)
        kind, live_hash = _inspect(target)
        if kind == "absent":
            continue
        if kind == "file" and live_hash == recorded_hash:
            log(f"    DELETE {target}")
            plan.removed.append(target)
            if apply:
                _unlink(target)
                _prune_empty(target.parent, config_dir)
        else:
            remaining[rel] = recorded_hash
            plan.warnings.append(f"{target} was modified since deploy; left in place")

    settings_pending = False
    settings_path = config_dir / payload.SETTINGS_TARGET
    if (record.settings_added or record.settings_created) and settings_path.is_file():
        log("settings:")
        live = _read_json(settings_path)
        if not isinstance(live, dict):
            settings_pending = True
            plan.warnings.append(f"{settings_path} is not a JSON object; settings left untouched")
        else:
            new_live, reverted, left = settings_merge.revert_from_live(live, record.settings_added)
            plan.notes.extend(f"left in place: {entry}" for entry in left)
            if not new_live and record.settings_created:
                log(f"    DELETE {settings_path}")
                plan.removed.append(settings_path)
                if apply:
                    _unlink(settings_path)
            elif new_live != live:
                backup = _backup_path(settings_path, stamp)
                plan.backups.append(backup)
                log(f"    backup {backup}")
                log(f"    write  {settings_path}")
                plan.written.append(settings_path)
                if apply:
                    shutil.copy2(settings_path, backup)
                    settings_path.write_text(
                        json.dumps(new_live, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8",
                        newline="\n",
                    )

    if remaining or settings_pending:
        record.files = remaining
        record.plugins = []
        record.extras = []
        record.claude_md = False
        if not settings_pending:
            record.settings_added = {}
            record.settings_created = False
        log(f"    write  {path}")
        plan.written.append(path)
        if apply:
            state.save(path, record, now)
    else:
        log(f"    DELETE {path}")
        plan.removed.append(path)
        if apply:
            _unlink(path)
    return plan


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.deploy",
        description=(
            "Deploy claude-code-kit into a Claude Code config directory. Reports by "
            "default; writes nothing without --apply."
        ),
    )
    parser.add_argument("--apply", action="store_true", help="write; required to change anything")
    parser.add_argument(
        "--config-dir",
        metavar="PATH",
        help="live config dir (default: $CLAUDE_CONFIG_DIR, else ~/.claude)",
    )
    parser.add_argument(
        "--plugins", metavar="LIST", help="comma-separated plugins to deploy (default: all)"
    )
    parser.add_argument(
        "--extra",
        action="append",
        default=[],
        metavar="NAME",
        help="also deploy an opt-in vendored plugin (repeatable)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="replace conflicting files the kit did not write, backing each up first",
    )
    parser.add_argument("--no-settings", action="store_true", help="leave settings.json alone")
    parser.add_argument("--no-claude-md", action="store_true", help="leave CLAUDE.md alone")
    parser.add_argument(
        "--uninstall", action="store_true", help="remove what the state file records"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="summarise instead of listing every path (never applies under --apply)",
    )
    return parser


def run(argv: list[str] | None = None, repo_root: Path = REPO_ROOT) -> int:
    """CLI entry point. Returns 0 on success and 2 when deployment cannot proceed."""
    args = build_parser().parse_args(argv)
    config_dir = inventory.resolve_config_dir(args.config_dir)
    requested = None
    if args.plugins is not None:
        requested = [name.strip() for name in args.plugins.split(",") if name.strip()]
        if not requested:
            print("error: --plugins needs at least one name", file=sys.stderr)
            return 2

    banner = "APPLY - writing to disk" if args.apply else "DRY RUN - nothing will change"
    print("=" * 74)
    print(banner)
    print("=" * 74)
    print(f"repo        : {repo_root}")
    print(f"live config : {config_dir}")
    print()

    log: Logger = (lambda _line: None) if (args.quiet and not args.apply) else print
    try:
        if args.uninstall:
            plan = run_uninstall(config_dir, apply=args.apply, log=log)
        else:
            plan = run_deploy(
                repo_root,
                config_dir,
                apply=args.apply,
                plugins=requested,
                extras=args.extra,
                overwrite=args.overwrite,
                settings=not args.no_settings,
                claude_md=not args.no_claude_md,
                log=log,
            )
    except DeployError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print()
    if plan.warnings:
        print("WARNINGS")
        for warning in plan.warnings:
            print(f"  !! {warning}")
        print()
    if plan.notes:
        print("Notes")
        for note in plan.notes:
            print(f"  -  {note}")
        print()
    print(plan.summary())
    print("=" * 74)
    print(banner)
    print("=" * 74)
    if not args.apply:
        print("Re-run with --apply to make these changes.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
