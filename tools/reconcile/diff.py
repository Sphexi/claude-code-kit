"""Classify the difference between the repository layout and a live config dir.

========== ====================================== =========================
matched    live equals repo                       none
missing    in the layout, absent live             install
behind     live equals the state hash, not repo   update (safe)
modified   live differs from repo and state       update (backup) / adopt
retired    in state, no longer in the layout      remove (unmodified only)
unmanaged  live, in neither state nor layout      adopt; never removed
========== ====================================== =========================

``skill`` and ``plugin`` units roll up to one verdict per unit. Settings are
compared as a subset check: kit entries missing from the live file.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from . import settings_merge
from .inventory import FileEntry, Inventory

CLASSES = ("matched", "missing", "behind", "modified", "retired", "unmanaged", "unclassifiable")
ACTIONABLE = ("missing", "behind", "modified", "retired")
ROLLED_UP_CATEGORIES = frozenset({"plugin", "skill"})
DRIFT_SAMPLE = 3

_PRECEDENCE = {"modified": 0, "behind": 1, "missing": 2, "retired": 3, "matched": 4}
_DETAIL_ORDER = ("modified", "behind", "missing", "retired", "unmanaged", "unclassifiable")


@dataclass(frozen=True)
class FileVerdict:
    """One file's classification, with the hash the state file recorded for it."""

    rel: str
    klass: str
    category: str
    unit: str
    repo: FileEntry | None = None
    live: FileEntry | None = None
    recorded: str | None = None


@dataclass
class UnitVerdict:
    """A logical unit's rolled-up classification."""

    unit: str
    category: str
    klass: str
    files: list[FileVerdict] = field(default_factory=list)
    detail: str = ""

    @property
    def rolled_up(self) -> bool:
        return self.category in ROLLED_UP_CATEGORIES

    @property
    def file_count(self) -> int:
        return len(self.files)


@dataclass
class DiffResult:
    """The full comparison."""

    units: list[UnitVerdict] = field(default_factory=list)
    settings_class: str = "matched"
    settings_diffs: list[settings_merge.SettingsDiff] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)
    collisions: list[str] = field(default_factory=list)

    def by_class(self, klass: str) -> list[UnitVerdict]:
        return [u for u in self.units if u.klass == klass]

    def counts(self) -> dict[str, int]:
        return {k: len(self.by_class(k)) for k in CLASSES}

    def has_actionable(self) -> bool:
        if self.settings_class in ("missing", "behind"):
            return True
        return any(u.klass in ACTIONABLE for u in self.units)


def _classify_file(
    repo: FileEntry | None, live: FileEntry | None, recorded: str | None
) -> str:
    if repo is not None and live is None:
        return "missing"
    if repo is None:
        return "retired" if recorded is not None else "unmanaged"
    assert live is not None
    if repo.sha256 == live.sha256:
        return "matched"
    if recorded is not None and live.sha256 == recorded:
        return "behind"
    return "modified"


def _roll_up(files: list[FileVerdict]) -> str:
    classes = {f.klass for f in files}
    if not classes:
        return "matched"
    decisive = classes - {"unmanaged"}
    if not decisive:
        return "unmanaged"
    return min(decisive, key=lambda c: _PRECEDENCE[c])


def _describe(klass: str, files: list[FileVerdict]) -> str:
    if klass == "matched":
        return f"{len(files)} files match"
    buckets: dict[str, list[str]] = {}
    for verdict in files:
        if verdict.klass != "matched":
            buckets.setdefault(verdict.klass, []).append(verdict.rel)
    parts: list[str] = []
    for name in _DETAIL_ORDER:
        paths = buckets.get(name)
        if not paths:
            continue
        sample = ", ".join(paths[:DRIFT_SAMPLE])
        if len(paths) > DRIFT_SAMPLE:
            sample += f", +{len(paths) - DRIFT_SAMPLE} more"
        parts.append(f"{len(paths)} {name} ({sample})")
    return "; ".join(parts)


def compare(
    repo: Inventory,
    live: Inventory,
    recorded: Mapping[str, str] | None = None,
    composed_settings: dict | None = None,
    live_settings: dict | None = None,
) -> DiffResult:
    """Compare two inventories against the hashes the state file recorded.

    ``composed_settings=None`` skips the settings comparison; ``live_settings=None``
    means the live machine has no usable settings file.
    """
    recorded = recorded or {}
    result = DiffResult()
    result.skipped = sorted(
        [(f"repo:{p}", r) for p, r in repo.skipped]
        + [(f"live:{p}", r) for p, r in live.skipped]
    )
    result.collisions = sorted(set(repo.collisions) | set(live.collisions))

    unclassifiable: dict[str, UnitVerdict] = {}
    for info in live.skill_dirs.values():
        if info.kind is None:
            name = f"skills/{info.name}"
            unclassifiable[name] = UnitVerdict(
                unit=name,
                category="other",
                klass="unclassifiable",
                detail="directory under skills/ has neither .claude-plugin/plugin.json nor SKILL.md",
            )
    excluded = tuple(f"{u}/" for u in unclassifiable)

    paths = sorted(
        {
            rel
            for rel in set(repo.files) | set(live.files)
            if rel != "settings.json" and not rel.startswith(excluded)
        }
    )

    units: dict[tuple[str, str], UnitVerdict] = {}
    for rel in paths:
        repo_entry = repo.files.get(rel)
        live_entry = live.files.get(rel)
        klass = _classify_file(repo_entry, live_entry, recorded.get(rel))
        known = repo_entry or live_entry
        assert known is not None
        verdict = FileVerdict(
            rel, klass, known.category, known.unit, repo_entry, live_entry, recorded.get(rel)
        )
        unit = units.setdefault(
            (known.category, known.unit),
            UnitVerdict(unit=known.unit, category=known.category, klass=klass),
        )
        unit.files.append(verdict)

    for unit in units.values():
        unit.files.sort(key=lambda f: f.rel)
        unit.klass = _roll_up(unit.files)
        if unit.rolled_up:
            unit.detail = _describe(unit.klass, unit.files)

    result.units = sorted(
        list(units.values()) + list(unclassifiable.values()),
        key=lambda u: (u.category, u.unit),
    )

    if composed_settings is None:
        result.settings_class = "matched"
    elif live_settings is None:
        result.settings_class = "missing"
        result.settings_diffs = settings_merge.diff_settings(composed_settings, {})
    else:
        result.settings_diffs = settings_merge.diff_settings(composed_settings, live_settings)
        result.settings_class = (
            "behind" if any(d.kind == "missing" for d in result.settings_diffs) else "matched"
        )
    return result
