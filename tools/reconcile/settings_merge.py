"""Compose base settings with an OS overlay, and merge the result into a live file."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path

BASE_NAME = "settings.base.json"
OVERLAY_NAMES = {
    "linux": "settings.linux.json",
    "macos": "settings.macos.json",
    "windows": "settings.windows.json",
}

TOP_LEVEL_ORDER = (
    "$schema",
    "model",
    "theme",
    "autoUpdatesChannel",
    "effortLevel",
    "switchModelsOnFlag",
    "outputStyle",
    "permissions",
    "env",
    "enabledPlugins",
    "extraKnownMarketplaces",
)
PERMISSIONS_ORDER = ("allow", "ask", "deny", "additionalDirectories", "defaultMode")
LIST_UNION_KEYS = frozenset({"allow", "ask", "deny", "additionalDirectories"})
DICT_UNION_KEYS = frozenset({"enabledPlugins", "env", "extraKnownMarketplaces"})


class SettingsError(Exception):
    """A settings file is missing or is not a JSON object."""


@dataclass(frozen=True)
class ScalarOverride:
    """A scalar the overlay replaced in the base."""

    key: str
    base: object
    overlay: object


@dataclass
class MergeResult:
    """Composed settings plus a record of how they were composed."""

    settings: dict = field(default_factory=dict)
    overrides: list[ScalarOverride] = field(default_factory=list)
    sources: list[Path] = field(default_factory=list)

    def render(self) -> str:
        """The settings as they should land on disk."""
        return json.dumps(self.settings, indent=2, ensure_ascii=False) + "\n"


@dataclass(frozen=True)
class KeptValue:
    """A live value that differs from the kit's and was left alone."""

    key: str
    kit: object
    live: object


@dataclass(frozen=True)
class SettingsDiff:
    """One difference between composed settings and a live file.

    ``kind`` is ``missing`` (kit entry absent from live) or ``kept`` (live value
    differs from the kit's and wins).
    """

    kind: str
    key: str
    expected: object | None = None
    actual: object | None = None


def overlay_for(platform: str) -> str:
    """Map ``sys.platform`` to an overlay name: ``windows``, ``macos`` or ``linux``."""
    if platform.startswith("win"):
        return "windows"
    if platform == "darwin":
        return "macos"
    return "linux"


def load_json_object(path: Path) -> dict:
    """Read a JSON file that must contain an object."""
    if not path.is_file():
        raise SettingsError(f"settings file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SettingsError(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise SettingsError(f"{path}: expected a JSON object, got {type(data).__name__}")
    return data


def _union_list(base: list, overlay: list) -> list:
    merged: list = []
    seen: set[str] = set()
    for item in list(base) + list(overlay):
        marker = json.dumps(item, sort_keys=True)
        if marker not in seen:
            seen.add(marker)
            merged.append(item)
    return merged


def _order_keys(data: dict, order: tuple[str, ...]) -> dict:
    ordered = {key: data[key] for key in order if key in data}
    for key in sorted(k for k in data if k not in order):
        ordered[key] = data[key]
    return ordered


def _take_scalar(
    merged: dict, key: str, base: dict, overlay: dict, dotted: str, overrides: list
) -> None:
    if key in overlay:
        if key in base and base[key] != overlay[key]:
            overrides.append(ScalarOverride(dotted, base[key], overlay[key]))
        merged[key] = overlay[key]
    else:
        merged[key] = base[key]


def _merge_permissions(base: dict, overlay: dict, overrides: list) -> dict:
    merged: dict = {}
    for key in sorted(set(base) | set(overlay)):
        if key in LIST_UNION_KEYS:
            merged[key] = _union_list(base.get(key, []), overlay.get(key, []))
        else:
            _take_scalar(merged, key, base, overlay, f"permissions.{key}", overrides)
    return _order_keys(merged, PERMISSIONS_ORDER)


def merge(base: dict, overlay: dict) -> MergeResult:
    """Compose base settings with an OS overlay.

    Lists union with base order first, dict-union keys merge key-wise with the
    overlay winning (including ``false``), and scalars take the overlay value and
    are reported as overrides.
    """
    overrides: list[ScalarOverride] = []
    merged: dict = {}
    for key in sorted(set(base) | set(overlay)):
        if key == "permissions":
            merged[key] = _merge_permissions(
                base.get(key, {}) or {}, overlay.get(key, {}) or {}, overrides
            )
        elif key in DICT_UNION_KEYS:
            combined = dict(base.get(key, {}) or {})
            for sub_key, value in (overlay.get(key, {}) or {}).items():
                if sub_key in combined and combined[sub_key] != value:
                    overrides.append(
                        ScalarOverride(f"{key}.{sub_key}", combined[sub_key], value)
                    )
                combined[sub_key] = value
            merged[key] = {k: combined[k] for k in sorted(combined)}
        else:
            _take_scalar(merged, key, base, overlay, key, overrides)
    return MergeResult(settings=_order_keys(merged, TOP_LEVEL_ORDER), overrides=overrides)


def compose(claude_dir: Path, platform: str) -> MergeResult:
    """Read and compose ``claude/settings.base.json`` with the platform overlay.

    A missing overlay is not an error; a missing base is.
    """
    base_path = claude_dir / BASE_NAME
    base = load_json_object(base_path)
    sources = [base_path]

    overlay: dict = {}
    overlay_path = claude_dir / OVERLAY_NAMES[overlay_for(platform)]
    if overlay_path.is_file():
        overlay = load_json_object(overlay_path)
        sources.append(overlay_path)

    result = merge(base, overlay)
    result.sources = sources
    return result


def _merge_scalar(
    container: dict, key: str, value: object, dotted: str, added: dict, kept: list
) -> None:
    if key not in container:
        container[key] = copy.deepcopy(value)
        added[dotted] = copy.deepcopy(value)
    elif container[key] != value:
        kept.append(KeptValue(dotted, value, container[key]))


def _merge_list(
    container: dict, key: str, items: list, dotted: str, added: dict, kept: list
) -> None:
    current = container.get(key)
    if current is None:
        container[key] = list(items)
        added[dotted] = list(items)
    elif isinstance(current, list):
        new = [item for item in items if item not in current]
        if new:
            current.extend(new)
            added[dotted] = new
    else:
        kept.append(KeptValue(dotted, items, current))


def _merge_dict(container: dict, key: str, items: dict, added: dict, kept: list) -> None:
    current = container.get(key)
    if current is None:
        container[key] = copy.deepcopy(items)
        added[key] = copy.deepcopy(items)
    elif isinstance(current, dict):
        new_items: dict = {}
        for sub, value in items.items():
            if sub not in current:
                current[sub] = copy.deepcopy(value)
                new_items[sub] = copy.deepcopy(value)
            elif current[sub] != value:
                kept.append(KeptValue(f"{key}.{sub}", value, current[sub]))
        if new_items:
            added[key] = new_items
    else:
        kept.append(KeptValue(key, items, current))


def apply_to_live(composed: dict, live: dict) -> tuple[dict, dict, list[KeptValue]]:
    """Merge composed settings into a live file without disturbing user content.

    Returns ``(new_live, added, kept)``. ``added`` records exactly what was
    inserted, keyed ``permissions.<list>`` for list entries, ``<key>`` for scalars
    and dict-union keys (the latter as ``{subkey: value}``).
    """
    new = copy.deepcopy(live)
    added: dict = {}
    kept: list[KeptValue] = []

    for key, value in composed.items():
        if key == "permissions" and isinstance(value, dict):
            existing = new.get("permissions")
            if existing is not None and not isinstance(existing, dict):
                kept.append(KeptValue(key, value, existing))
                continue
            perms: dict = existing if isinstance(existing, dict) else {}
            for pkey, pvalue in value.items():
                dotted = f"permissions.{pkey}"
                if pkey in LIST_UNION_KEYS and isinstance(pvalue, list):
                    _merge_list(perms, pkey, pvalue, dotted, added, kept)
                else:
                    _merge_scalar(perms, pkey, pvalue, dotted, added, kept)
            if existing is None and perms:
                new["permissions"] = perms
        elif key in DICT_UNION_KEYS and isinstance(value, dict):
            _merge_dict(new, key, value, added, kept)
        else:
            _merge_scalar(new, key, value, key, added, kept)
    return new, added, kept


def merge_added(previous: dict, new: dict) -> dict:
    """Combine two ``added`` records, so earlier additions stay reversible."""
    merged = copy.deepcopy(previous)
    for key, value in new.items():
        old = merged.get(key)
        if isinstance(value, list) and isinstance(old, list):
            merged[key] = old + [v for v in value if v not in old]
        elif isinstance(value, dict) and isinstance(old, dict):
            old.update(value)
        else:
            merged[key] = value
    return merged


def revert_from_live(live: dict, added: dict) -> tuple[dict, list[str], list[str]]:
    """Undo recorded additions that are still present and unchanged.

    Returns ``(new_live, reverted, left)``; each is a list of readable entries
    for ``reverted`` and ``left``. A container emptied by the removal is deleted.
    """
    new = copy.deepcopy(live)
    reverted: list[str] = []
    left: list[str] = []

    def revert(container: dict, key: str, recorded: object, dotted: str) -> None:
        if key not in container:
            return
        current = container[key]
        if isinstance(recorded, list) and isinstance(current, list):
            removed = [item for item in recorded if item in current]
            for item in removed:
                current.remove(item)
                reverted.append(f"{dotted}: {item}")
            if removed and not current:
                del container[key]
        elif isinstance(recorded, dict) and isinstance(current, dict):
            for sub, value in recorded.items():
                if sub not in current:
                    continue
                if current[sub] == value:
                    del current[sub]
                    reverted.append(f"{dotted}.{sub}")
                else:
                    left.append(f"{dotted}.{sub}")
            if not current:
                del container[key]
        elif current == recorded:
            del container[key]
            reverted.append(dotted)
        else:
            left.append(dotted)

    for dotted, recorded in added.items():
        if dotted.startswith("permissions."):
            perms = new.get("permissions")
            if isinstance(perms, dict):
                revert(perms, dotted.split(".", 1)[1], recorded, dotted)
                if not perms:
                    del new["permissions"]
        else:
            revert(new, dotted, recorded, dotted)
    return new, reverted, left


def diff_settings(composed: dict, live: dict) -> list[SettingsDiff]:
    """Kit entries missing from live, and live values that override the kit's."""
    _, added, kept = apply_to_live(composed, live)
    diffs: list[SettingsDiff] = []
    for key, value in added.items():
        if isinstance(value, dict) and key in DICT_UNION_KEYS:
            diffs.extend(SettingsDiff("missing", f"{key}.{sub}", v) for sub, v in value.items())
        else:
            diffs.append(SettingsDiff("missing", key, value))
    diffs.extend(SettingsDiff("kept", k.key, k.kit, k.live) for k in kept)
    return sorted(diffs, key=lambda d: (d.key, d.kind))
