"""Command-line interface for the reconcile engine.

    python -m tools.reconcile [--dry-run|--apply] [--config-dir PATH] [--plugins LIST]
                              [--extra NAME]... [--yes-safe] [--adopt-unmanaged]
                              [--report PATH] [--verbose] [--show-matched]
                              [--show-unmanaged]

Reporting is the default. Under ``--apply`` every decision is prompted for
except ``missing`` and ``behind`` units with ``--yes-safe``. Without a TTY
nothing is prompted, so an unattended run never removes or overwrites anything.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .. import payload, state
from . import VERSION, actions, diff, inventory, report, settings_merge

REPO_ROOT = Path(__file__).resolve().parents[2]

PROMPTS = {
    "missing": ("install", {"i": "install", "s": "skip"}),
    "behind": ("update", {"u": "update", "s": "skip"}),
    "modified": ("update (backs up first) / adopt", {"u": "update", "a": "adopt", "s": "skip"}),
    "retired": ("remove", {"r": "remove", "s": "skip"}),
    "unmanaged": ("adopt", {"a": "adopt", "s": "skip"}),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.reconcile",
        description=(
            "Reconcile claude-code-kit against a live config directory. Reports by "
            "default; writes nothing without --apply."
        ),
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="report only (the default)")
    mode.add_argument("--apply", action="store_true", help="act on the diff, prompting per unit")
    parser.add_argument(
        "--config-dir",
        metavar="PATH",
        help="live config dir (default: $CLAUDE_CONFIG_DIR, else ~/.claude)",
    )
    parser.add_argument(
        "--plugins", metavar="LIST", help="comma-separated plugins (default: those last deployed)"
    )
    parser.add_argument(
        "--extra", action="append", default=None, metavar="NAME", help="opt-in vendored plugin"
    )
    parser.add_argument(
        "--yes-safe",
        action="store_true",
        help="auto-confirm installs of missing units and updates of behind units",
    )
    parser.add_argument(
        "--adopt-unmanaged",
        action="store_true",
        help="with --apply, prompt to adopt each unmanaged unit into this clone",
    )
    parser.add_argument("--report", metavar="PATH", help="also write the report to this file")
    parser.add_argument("--verbose", action="store_true", help="expand units to per-file detail")
    parser.add_argument("--show-matched", action="store_true", help="list matched units")
    parser.add_argument("--show-unmanaged", action="store_true", help="list unmanaged units")
    parser.add_argument("--version", action="version", version=f"reconcile {VERSION}")
    return parser


def load_live_settings(config_dir: Path) -> dict | None:
    """The decoded live ``settings.json``, or ``None`` when absent or unreadable."""
    path = config_dir / inventory.SETTINGS_TARGET
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def _ask(unit: diff.UnitVerdict, interactive: bool) -> str:
    label, answers = PROMPTS[unit.klass]
    if not interactive:
        return "skip"
    options = " / ".join(f"[{k}]{v}" for k, v in answers.items())
    while True:
        print(f"\n  {unit.klass}: {unit.category} {unit.unit}")
        if unit.detail:
            print(f"    {unit.detail}")
        try:
            answer = input(f"    {label}? {options} > ").strip().lower()
        except EOFError:
            return "skip"
        if answer in answers:
            return answers[answer]
        print(f"    not one of {sorted(answers)}")


def _selection(
    args: argparse.Namespace, repo_root: Path, recorded: state.State | None
) -> payload.Selection:
    if args.plugins is not None:
        plugins = tuple(n.strip() for n in args.plugins.split(",") if n.strip())
    elif recorded is not None:
        plugins = tuple(recorded.plugins)
    else:
        plugins = tuple(payload.available_plugins(repo_root))
    extras = tuple(args.extra) if args.extra is not None else tuple(recorded.extras if recorded else ())
    return payload.Selection(plugins, extras, recorded.claude_md if recorded else True)


def run(argv: list[str] | None = None, repo_root: Path = REPO_ROOT) -> int:
    """Entry point. Returns 0 when the run completed and 2 when it could not."""
    args = build_parser().parse_args(argv)
    apply = bool(args.apply)
    config_dir = inventory.resolve_config_dir(args.config_dir)

    try:
        recorded = state.load(state.state_path(config_dir))
        selection = _selection(args, repo_root, recorded)
        track_settings = recorded.settings if recorded else True
        composed = settings_merge.compose(repo_root / "claude", sys.platform)
        repo_inv = inventory.scan_repo(repo_root, selection, composed.render())
    except (state.StateError, payload.PayloadError, settings_merge.SettingsError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if apply and repo_inv.collisions:
        print(
            "error: payload paths collide case-insensitively: " + ", ".join(repo_inv.collisions),
            file=sys.stderr,
        )
        return 2

    live_inv = inventory.scan_live(config_dir)
    result = diff.compare(
        repo_inv,
        live_inv,
        recorded.files if recorded else {},
        composed.settings if track_settings else None,
        load_live_settings(config_dir),
    )

    rendered = report.render(
        result,
        apply=apply,
        config_dir=str(config_dir),
        repo_root=str(repo_root),
        verbose=args.verbose,
        show_matched=args.show_matched,
        show_unmanaged=args.show_unmanaged,
    )
    print(rendered, end="")

    records: list[actions.ActionRecord] = []
    if apply or result.has_actionable():
        records = _act(result, args, repo_root, config_dir, composed.settings, apply)
        summary = report.render_actions(records, apply=apply)
        if summary:
            print(summary, end="")
    if apply:
        _record_state(config_dir, recorded, selection, repo_root, records, track_settings)

    if args.report:
        report_path = Path(args.report).expanduser()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            rendered + report.render_actions(records, apply=apply), encoding="utf-8", newline="\n"
        )
        print(f"report written to {report_path}")
    return 0


def _act(
    result: diff.DiffResult,
    args: argparse.Namespace,
    repo_root: Path,
    config_dir: Path,
    composed_settings: dict,
    apply: bool,
) -> list[actions.ActionRecord]:
    """Plan, and under ``--apply`` perform, one action per unit."""
    interactive = apply and sys.stdin is not None and sys.stdin.isatty()
    log: actions.Logger = print if (apply or args.verbose) else (lambda _line: None)
    records: list[actions.ActionRecord] = []

    for unit in result.units:
        if unit.klass == "unmanaged":
            if not (apply and args.adopt_unmanaged):
                continue
            choice = _ask(unit, interactive)
        elif unit.klass not in diff.ACTIONABLE:
            continue
        elif not apply:
            choice = {"missing": "install", "behind": "update"}.get(unit.klass, "skip")
        elif unit.klass in ("missing", "behind") and args.yes_safe:
            choice = "install" if unit.klass == "missing" else "update"
        else:
            choice = _ask(unit, interactive)

        if choice == "skip":
            continue
        try:
            if choice == "install":
                records.append(actions.install(unit, config_dir, apply=apply, log=log))
            elif choice == "update":
                records.append(actions.update(unit, config_dir, apply=apply, log=log))
            elif choice == "remove":
                records.append(actions.remove(unit, config_dir, apply=apply, log=log))
            elif choice == "adopt":
                records.append(actions.adopt(unit, repo_root, apply=apply, log=log))
        except actions.ActionError as exc:
            log(f"    SKIP   {unit.unit} - {exc}")

    if result.settings_class in ("missing", "behind"):
        write = not apply or (result.settings_class == "missing" and args.yes_safe)
        if apply and not write and interactive:
            print(f"\n  {result.settings_class}: settings.json")
            try:
                answer = input("    merge kit settings into settings.json? [y]es / [n]o > ")
            except EOFError:
                answer = ""
            write = answer.strip().lower() in {"y", "yes"}
        if write:
            records.append(
                actions.merge_settings(composed_settings, config_dir, apply=apply, log=log)
            )
    return records


def _record_state(
    config_dir: Path,
    existing: state.State | None,
    selection: payload.Selection,
    repo_root: Path,
    records: list[actions.ActionRecord],
    track_settings: bool,
) -> None:
    done = [r for r in records if r.applied and not r.refused]
    if not done:
        return
    record = existing or state.State(
        plugins=list(selection.plugins),
        extras=list(selection.extras),
        claude_md=selection.claude_md,
        settings=track_settings,
    )
    record.kit_version = state.read_kit_version(repo_root)
    record.repo = str(repo_root.resolve())
    for item in done:
        record.files.update(item.recorded)
        for rel in item.forgotten:
            record.files.pop(rel, None)
        if item.verb == "settings":
            record.settings_added = settings_merge.merge_added(
                record.settings_added, item.settings_added
            )
            record.settings_created = record.settings_created or item.settings_created
    state.save(state.state_path(config_dir), record)


if __name__ == "__main__":
    sys.exit(run())
