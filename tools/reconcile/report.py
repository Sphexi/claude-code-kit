"""Human-readable rendering of a diff, with a banner that separates dry runs from applies."""

from __future__ import annotations

from .diff import CLASSES, DiffResult, UnitVerdict

BANNER_DRY = "DRY RUN - nothing changed. Re-run with --apply to act."
BANNER_APPLY = "APPLY - changes were written to disk."
WIDTH = 74

CATEGORY_LABELS = {
    "memory": "Global memory",
    "agent": "Agents",
    "output-style": "Output styles",
    "skill": "Skills",
    "plugin": "Plugins",
    "other": "Other",
}
CLASS_MARKERS = {
    "matched": "  ok",
    "missing": " MISS",
    "behind": "BEHND",
    "modified": " MOD",
    "retired": " RETD",
    "unmanaged": "  UNM",
    "unclassifiable": "  ???",
}


def rule(char: str = "-") -> str:
    return char * WIDTH


def banner(apply: bool) -> list[str]:
    return [rule("="), BANNER_APPLY if apply else BANNER_DRY, rule("=")]


def _unit_line(unit: UnitVerdict, show_matched: bool, show_unmanaged: bool) -> str | None:
    if unit.klass == "matched" and not show_matched:
        return None
    if unit.klass == "unmanaged" and not show_unmanaged:
        return None
    line = f"  [{CLASS_MARKERS[unit.klass]}] {unit.unit}"
    if unit.detail:
        line += f"  - {unit.detail}"
    return line


def _file_detail(unit: UnitVerdict) -> list[str]:
    return [
        f"        [{CLASS_MARKERS[v.klass]}] {v.rel}"
        for v in unit.files
        if v.klass != "matched"
    ]


def render(
    result: DiffResult,
    *,
    apply: bool,
    config_dir: str,
    repo_root: str,
    verbose: bool = False,
    show_matched: bool = False,
    show_unmanaged: bool = False,
) -> str:
    """Render the whole diff, newline-terminated."""
    lines: list[str] = list(banner(apply))
    lines.append(f"repo        : {repo_root}")
    lines.append(f"live config : {config_dir}")
    lines.append("")

    counts = result.counts()
    lines.append("units: " + "  ".join(f"{k}={counts[k]}" for k in CLASSES))
    lines.append("")

    lines.append("Settings (kit entries missing from the live file)")
    lines.append(f"  [{CLASS_MARKERS.get(result.settings_class, '  ??')}] settings.json")
    for entry in result.settings_diffs:
        if entry.kind == "missing":
            lines.append(f"        + {entry.key}: {entry.expected!r}")
        else:
            lines.append(
                f"        = {entry.key}: kept user value {entry.actual!r} (kit sets {entry.expected!r})"
            )
    lines.append("")

    for category in ("memory", "agent", "output-style", "skill", "plugin", "other"):
        units = [u for u in result.units if u.category == category]
        if not units:
            continue
        shown = [u for u in units if u.klass not in ("matched", "unmanaged")]
        unmanaged = [u for u in units if u.klass == "unmanaged"]
        heading = f"{CATEGORY_LABELS[category]} ({len(units)} units, {len(shown)} to review"
        heading += f", {len(unmanaged)} unmanaged)" if unmanaged else ")"
        lines.append(heading)
        for unit in units:
            line = _unit_line(unit, show_matched, show_unmanaged)
            if line is None:
                continue
            lines.append(line)
            if verbose and unit.rolled_up and unit.klass != "matched":
                lines.extend(_file_detail(unit))
        if not show_matched and not shown:
            lines.append("  all matched")
        lines.append("")

    if result.collisions:
        lines.append("NAME COLLISIONS - two payload paths map to one live path")
        lines.extend(f"  !! {name}" for name in result.collisions)
        lines.append("")

    if result.skipped:
        lines.append("Skipped (reported, never acted on)")
        lines.extend(f"  ?? {path} - {reason}" for path, reason in result.skipped)
        lines.append("")

    lines.extend(banner(apply))
    return "\n".join(lines) + "\n"


def render_actions(records: list, *, apply: bool) -> str:
    """Summarise what a set of actions did, or would have done."""
    if not records:
        return ""
    lines = ["", rule(), "Actions" if apply else "Actions (planned - nothing written)"]
    live = [r for r in records if not r.refused]
    refused = [r for r in records if r.refused]
    written = sum(len(r.written) for r in live)
    removed = sum(len(r.removed) for r in live)

    for record in live:
        lines.append(
            f"  {record.verb:<8} {record.unit}  (+{len(record.written)} / -{len(record.removed)})"
        )
    if refused:
        lines.append("")
        lines.append("Refused")
        for record in refused:
            lines.append(f"  {record.verb:<8} {record.unit}")
            lines.append(f"           {record.reason}")

    adopted = [r for r in live if r.verb == "adopt"]
    if adopted:
        lines.append("")
        lines.append("Adopted into the repo - review, run build/build_plugins.py, then commit:")
        for record in adopted:
            lines.extend(f"  {hint}" for hint in record.commit_hint)

    lines.append("")
    verb = "wrote" if apply else "would write"
    lines.append(f"{verb} {written} file(s), {'removed' if apply else 'would remove'} {removed}")
    lines.append(rule())
    return "\n".join(lines) + "\n"
