"""Scan the repository layout and a live config directory into comparable inventories.

Both sides are keyed by the path a file occupies under the live config dir. The
repository side comes from ``payload.layout``; the live scan reads only
``agents/``, ``output-styles/``, ``skills/``, ``CLAUDE.md`` and ``settings.json``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .. import payload
from ..payload import SETTINGS_TARGET, Selection

is_noise = payload.is_noise
sha256_file = payload.sha256_file
sha256_text = payload.sha256_text
CATEGORIES = (*payload.CATEGORIES, "other")
MANAGED_DIRS = ("agents", "output-styles", "skills")
MANAGED_FILES = (payload.MEMORY_TARGET, SETTINGS_TARGET)
GLOBAL_MEMORY_TARGET = payload.MEMORY_TARGET
PLUGIN_MARKER = Path(payload.PLUGIN_MARKER)
SKILL_MARKER = "SKILL.md"


@dataclass(frozen=True)
class FileEntry:
    """One file, described identically on either side.

    ``source`` is the file on disk, or ``None`` for the synthetic composed-settings entry.
    """

    rel: str
    sha256: str
    category: str
    unit: str
    source: Path | None = None


@dataclass(frozen=True)
class SkillDir:
    """A directory under ``skills/``; ``kind`` is ``plugin``, ``skill`` or ``None``."""

    name: str
    kind: str | None


@dataclass
class Inventory:
    """One side of the comparison."""

    side: str
    root: Path
    files: dict[str, FileEntry] = field(default_factory=dict)
    skill_dirs: dict[str, SkillDir] = field(default_factory=dict)
    collisions: list[str] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)


def classify_skill_dir(path: Path) -> str | None:
    """``plugin`` when it has a plugin manifest, ``skill`` when it has ``SKILL.md``, else ``None``."""
    if (path / PLUGIN_MARKER).is_file():
        return "plugin"
    if (path / SKILL_MARKER).is_file():
        return "skill"
    return None


def _add_files(
    inv: Inventory, root: Path, prefix: str, category: str, unit: str
) -> None:
    found, skipped = payload.tree_files(root, prefix)
    inv.skipped.extend(skipped)
    for path, rel in found:
        try:
            digest = sha256_file(path)
        except OSError as exc:
            inv.skipped.append((rel, f"unreadable: {exc.strerror or exc}"))
            continue
        inv.files[rel] = FileEntry(rel, digest, category, unit, path)


def _add_flat(inv: Inventory, root: Path, prefix: str, category: str) -> None:
    if not root.is_dir():
        return
    for path in sorted(root.glob("*.md")):
        rel = f"{prefix}/{path.name}"
        if path.is_symlink():
            inv.skipped.append((rel, "symlink"))
        else:
            inv.files[rel] = FileEntry(rel, sha256_file(path), category, path.stem, path)


def scan_repo(
    repo_root: Path, selection: Selection, settings_text: str | None = None
) -> Inventory:
    """Inventory the repository's layout for a selection.

    ``settings_text`` adds a ``settings.json`` entry carrying the composed hash.
    """
    inv = Inventory(side="repo", root=repo_root)
    built = payload.build_layout(
        repo_root, selection.plugins, selection.extras, selection.claude_md
    )
    inv.skipped.extend(built.skipped)
    inv.collisions = payload.find_collisions(built.placements)
    for placement in built.placements:
        inv.files[placement.target] = FileEntry(
            placement.target,
            sha256_file(placement.source),
            placement.category,
            placement.unit,
            placement.source,
        )
        if placement.category in ("plugin", "skill"):
            inv.skill_dirs[placement.unit] = SkillDir(placement.unit, placement.category)
    if settings_text is not None:
        inv.files[SETTINGS_TARGET] = FileEntry(
            SETTINGS_TARGET, sha256_text(settings_text), "settings", SETTINGS_TARGET
        )
    return inv


def scan_live(config_dir: Path) -> Inventory:
    """Inventory a live config dir. A missing directory yields an empty inventory."""
    inv = Inventory(side="live", root=config_dir)
    if not config_dir.is_dir():
        return inv

    for name in MANAGED_FILES:
        path = config_dir / name
        if not path.is_file():
            continue
        if path.is_symlink():
            inv.skipped.append((name, "symlink"))
            continue
        category = "settings" if name == SETTINGS_TARGET else "memory"
        inv.files[name] = FileEntry(name, sha256_file(path), category, name, path)

    _add_flat(inv, config_dir / "agents", "agents", "agent")
    _add_flat(inv, config_dir / "output-styles", "output-styles", "output-style")

    skills = config_dir / "skills"
    if skills.is_dir():
        for entry in sorted(skills.iterdir()):
            rel = f"skills/{entry.name}"
            if entry.is_symlink():
                inv.skipped.append((rel, "symlink"))
                continue
            if not entry.is_dir() or is_noise(Path(entry.name)):
                continue
            kind = classify_skill_dir(entry)
            before = len(inv.files)
            if kind is None:
                _add_files(inv, entry, rel, "other", rel)
            else:
                _add_files(inv, entry, rel, kind, entry.name)
            if len(inv.files) > before:
                inv.skill_dirs[entry.name] = SkillDir(entry.name, kind)
    return inv


def resolve_config_dir(explicit: str | None = None) -> Path:
    """``--config-dir``, else ``CLAUDE_CONFIG_DIR``, else ``~/.claude``, as an absolute path."""
    if explicit:
        return Path(explicit).expanduser().resolve()
    from_env = os.environ.get("CLAUDE_CONFIG_DIR")
    if from_env:
        return Path(from_env).expanduser().resolve()
    return (Path.home() / ".claude").resolve()
