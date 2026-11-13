"""The only table mapping repository paths to live configuration paths."""

from __future__ import annotations

import hashlib
import importlib.util
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

MEMORY_SOURCE = "claude/global-CLAUDE.md"
MEMORY_TARGET = "CLAUDE.md"
SETTINGS_TARGET = "settings.json"
PLUGINS_DIR = "plugins"
VENDOR_DIR = "claude/vendor"
PLUGIN_MARKER = ".claude-plugin/plugin.json"
CATEGORIES = ("memory", "agent", "output-style", "skill", "plugin", "settings")

NOISE_NAMES = frozenset(
    {"__pycache__", ".git", ".DS_Store", "Thumbs.db", ".pytest_cache", ".in_use"}
)
NOISE_SUFFIXES = frozenset({".pyc", ".pyo"})

_BUNDLES_PATH = Path(__file__).resolve().parents[1] / "build" / "bundles.py"
_BUNDLES_MODULE = "_claude_code_kit_bundles"


class PayloadError(Exception):
    """The repository tree cannot be mapped to a live layout."""


@dataclass(frozen=True)
class Placement:
    """One repository file and the live path it deploys to."""

    source: Path
    target: str
    category: str
    unit: str


@dataclass(frozen=True)
class Selection:
    """What a deployment installs."""

    plugins: tuple[str, ...]
    extras: tuple[str, ...] = ()
    claude_md: bool = True


@dataclass
class Layout:
    """Placements plus the paths that were seen and deliberately not placed."""

    placements: list[Placement] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)


def sha256_file(path: Path) -> str:
    """Return the hex SHA-256 of a file's bytes."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    """Return the hex SHA-256 of a string encoded as UTF-8."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def is_noise(path: Path) -> bool:
    """Whether a path, or any parent component of it, is build or editor debris."""
    if path.suffix in NOISE_SUFFIXES:
        return True
    return any(part in NOISE_NAMES for part in path.parts)


def _bundles() -> ModuleType:
    """Load ``build/bundles.py`` by path so no other ``build`` package can shadow it."""
    cached = sys.modules.get(_BUNDLES_MODULE)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(_BUNDLES_MODULE, _BUNDLES_PATH)
    if spec is None or spec.loader is None:
        raise PayloadError(f"cannot load {_BUNDLES_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_BUNDLES_MODULE] = module
    spec.loader.exec_module(module)
    return module


def core_plugin() -> str:
    """Name of the plugin whose agents, skills and output styles deploy as user files."""
    return str(_bundles().CORE)


def bundle_names() -> tuple[str, ...]:
    """Every marketplace plugin name, in bundle-table order."""
    return tuple(_bundles().bundle_names())


def known_extras() -> tuple[str, ...]:
    """Vendored plugins that ship in no bundle and install only on request."""
    return tuple(sorted(_bundles().EXTRAS))


def available_plugins(repo: Path) -> list[str]:
    """Generated plugin directories under ``plugins/``, in bundle-table order."""
    root = repo / PLUGINS_DIR
    if not root.is_dir():
        raise PayloadError(
            f"{root} does not exist; run 'python build/build_plugins.py' to generate it"
        )
    present = {
        entry.name
        for entry in root.iterdir()
        if entry.is_dir() and (entry / PLUGIN_MARKER).is_file()
    }
    ordered = [name for name in _bundles().bundle_names() if name in present]
    return ordered + sorted(present - set(ordered))


def _walk(root: Path, prefix: str, layout: Layout) -> list[tuple[Path, str]]:
    """List regular files under ``root`` as ``(path, target)``, recording symlinks."""
    found: list[tuple[Path, str]] = []
    for current, dirs, files in os.walk(root, followlinks=False):
        here = Path(current)
        dirs.sort()
        for name in list(dirs):
            if (here / name).is_symlink():
                dirs.remove(name)
                layout.skipped.append(
                    (f"{prefix}/{(here / name).relative_to(root).as_posix()}", "symlink")
                )
        dirs[:] = [d for d in dirs if not is_noise(Path(d))]
        for name in sorted(files):
            path = here / name
            relative = path.relative_to(root)
            if is_noise(relative):
                continue
            target = f"{prefix}/{relative.as_posix()}"
            if path.is_symlink():
                layout.skipped.append((target, "symlink"))
                continue
            found.append((path, target))
    return found


def tree_files(root: Path, prefix: str) -> tuple[list[tuple[Path, str]], list[tuple[str, str]]]:
    """Regular files under ``root`` as ``(path, target)``, plus skipped symlinks."""
    scratch = Layout()
    return _walk(root, prefix, scratch), scratch.skipped


def _add_tree(layout: Layout, root: Path, prefix: str, category: str, unit: str) -> None:
    for path, target in _walk(root, prefix, layout):
        layout.placements.append(Placement(path, target, category, unit))


def _add_flat(layout: Layout, root: Path, prefix: str, category: str) -> None:
    if not root.is_dir():
        return
    for path in sorted(root.glob("*.md")):
        target = f"{prefix}/{path.name}"
        if path.is_symlink():
            layout.skipped.append((target, "symlink"))
        elif path.is_file():
            layout.placements.append(Placement(path, target, category, path.stem))


def _add_core(layout: Layout, core_root: Path) -> None:
    _add_flat(layout, core_root / "agents", "agents", "agent")
    _add_flat(layout, core_root / "output-styles", "output-styles", "output-style")
    skills = core_root / "skills"
    if not skills.is_dir():
        return
    for entry in sorted(skills.iterdir()):
        if entry.is_symlink():
            layout.skipped.append((f"skills/{entry.name}", "symlink"))
        elif entry.is_dir() and not is_noise(Path(entry.name)):
            _add_tree(layout, entry, f"skills/{entry.name}", "skill", entry.name)


def build_layout(
    repo: Path,
    plugins: tuple[str, ...] | list[str],
    extras: tuple[str, ...] | list[str] = (),
    include_claude_md: bool = True,
) -> Layout:
    """Map the repository to live paths, collecting what was skipped.

    Raises:
        PayloadError: A selected plugin, extra or source file does not exist.
    """
    layout = Layout()
    core = core_plugin()

    if include_claude_md:
        memory = repo / MEMORY_SOURCE
        if not memory.is_file():
            raise PayloadError(f"{memory} not found")
        layout.placements.append(Placement(memory, MEMORY_TARGET, "memory", MEMORY_TARGET))

    for name in plugins:
        root = repo / PLUGINS_DIR / name
        if not (root / PLUGIN_MARKER).is_file():
            raise PayloadError(f"plugin {name!r} not found under {repo / PLUGINS_DIR}")
        if name == core:
            _add_core(layout, root)
        else:
            _add_tree(layout, root, f"skills/{name}", "plugin", name)

    for name in extras:
        if name not in known_extras():
            raise PayloadError(
                f"{name!r} is not an extra; known extras: {', '.join(known_extras())}"
            )
        root = repo / VENDOR_DIR / name
        if not root.is_dir():
            raise PayloadError(f"extra {name!r} not found at {root}")
        _add_tree(layout, root, f"skills/{name}", "plugin", name)

    return layout


def layout(
    repo: Path,
    plugins: tuple[str, ...] | list[str],
    extras: tuple[str, ...] | list[str] = (),
    include_claude_md: bool = True,
) -> list[Placement]:
    """Return every file placement for a selection."""
    return build_layout(repo, plugins, extras, include_claude_md).placements


def find_collisions(placements: list[Placement]) -> list[str]:
    """Targets that map to the same live path on a case-insensitive filesystem."""
    groups: dict[str, list[str]] = {}
    for placement in placements:
        groups.setdefault(placement.target.casefold(), []).append(placement.target)
    return sorted({t for group in groups.values() if len(group) > 1 for t in group})


def default_selection(repo: Path) -> Selection:
    """Every generated plugin, no extras, with the global ``CLAUDE.md``."""
    return Selection(tuple(available_plugins(repo)))
