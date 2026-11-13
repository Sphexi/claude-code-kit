"""Composition semantics of :mod:`tools.reconcile.settings_merge` over synthetic input."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.reconcile import settings_merge


def test_overlay_deny_appends_to_base_deny() -> None:
    """Overlay deny rules add to the base list; they never replace it."""
    result = settings_merge.merge(
        {"permissions": {"deny": ["Bash(git push *)"]}},
        {"permissions": {"deny": ["Bash(diskpart *)"]}},
    )

    assert result.settings["permissions"]["deny"] == [
        "Bash(git push *)",
        "Bash(diskpart *)",
    ]


def test_duplicate_deny_rules_are_collapsed() -> None:
    """A rule in both files appears once, so composed output stays readable."""
    result = settings_merge.merge(
        {"permissions": {"deny": ["Bash(sudo *)", "Bash(dd *)"]}},
        {"permissions": {"deny": ["Bash(dd *)", "Bash(mkfs *)"]}},
    )

    assert result.settings["permissions"]["deny"] == [
        "Bash(sudo *)",
        "Bash(dd *)",
        "Bash(mkfs *)",
    ]


def test_allow_list_is_a_union() -> None:
    """Allow entries union rather than one side winning."""
    result = settings_merge.merge(
        {"permissions": {"allow": ["Bash(*)", "Read(*)"]}},
        {"permissions": {"allow": ["Read(*)", "WebFetch"]}},
    )

    assert result.settings["permissions"]["allow"] == ["Bash(*)", "Read(*)", "WebFetch"]


def test_enabled_plugins_union_never_drops_an_explicit_false() -> None:
    """A ``false`` entry is a value, not an absence.

    ``security-guidance@skills-dir: false`` is the whole reason an entry exists
    under skills-dir loading. Dropping it would silently re-enable a plugin that
    was deliberately turned off — and the plugin in question makes billed model
    calls per turn, so the failure would be expensive as well as invisible.
    """
    result = settings_merge.merge(
        {
            "enabledPlugins": {
                "tool@market": True,
                "security-guidance@skills-dir": False,
            }
        },
        {"enabledPlugins": {"other@skills-dir": True}},
    )

    plugins = result.settings["enabledPlugins"]
    assert plugins["security-guidance@skills-dir"] is False
    assert plugins["tool@market"] is True
    assert plugins["other@skills-dir"] is True


def test_overlay_may_disable_a_base_enabled_plugin() -> None:
    """An overlay turning a plugin off wins, and the override is reported."""
    result = settings_merge.merge(
        {"enabledPlugins": {"noisy@skills-dir": True}},
        {"enabledPlugins": {"noisy@skills-dir": False}},
    )

    assert result.settings["enabledPlugins"]["noisy@skills-dir"] is False
    assert [o.key for o in result.overrides] == ["enabledPlugins.noisy@skills-dir"]


def test_scalar_conflict_prefers_overlay_and_reports_it() -> None:
    """The overlay wins on scalars, and composition never happens silently."""
    result = settings_merge.merge(
        {"outputStyle": "A", "theme": "dark"},
        {"outputStyle": "B"},
    )

    assert result.settings["outputStyle"] == "B"
    assert result.settings["theme"] == "dark"
    override = next(o for o in result.overrides if o.key == "outputStyle")
    assert (override.base, override.overlay) == ("A", "B")


def test_identical_scalar_is_not_reported_as_an_override() -> None:
    """Repeating a value in the overlay is not an override worth reporting."""
    result = settings_merge.merge({"theme": "dark"}, {"theme": "dark"})

    assert result.overrides == []


def test_output_key_order_is_stable_and_canonical() -> None:
    """Composition is deterministic, so a re-run produces no diff."""
    base = {
        "extraKnownMarketplaces": {"m": {}},
        "permissions": {"defaultMode": "acceptEdits", "deny": ["x"], "allow": ["y"]},
        "outputStyle": "A",
    }
    first = settings_merge.merge(base, {})
    second = settings_merge.merge(dict(reversed(list(base.items()))), {})

    assert list(first.settings) == ["outputStyle", "permissions", "extraKnownMarketplaces"]
    assert list(first.settings["permissions"]) == ["allow", "deny", "defaultMode"]
    assert first.render() == second.render(), (
        "key order in the source files must not change the composed output"
    )


def test_render_is_json_with_a_trailing_newline() -> None:
    """The rendered text is exactly what should land on disk."""
    text = settings_merge.merge({"theme": "x"}, {}).render()

    assert text.endswith("\n")
    assert json.loads(text) == {"theme": "x"}


def test_overlay_for_platform() -> None:
    assert settings_merge.overlay_for("win32") == "windows"
    assert settings_merge.overlay_for("linux") == "linux"
    assert settings_merge.overlay_for("darwin") == "macos"


def test_compose_reads_base_and_the_matching_overlay(fake_repo: Path) -> None:
    """Composition picks the overlay for the platform it was asked about."""
    windows = settings_merge.compose(fake_repo / "claude", "win32")
    linux = settings_merge.compose(fake_repo / "claude", "linux")

    macos = settings_merge.compose(fake_repo / "claude", "darwin")

    assert "Bash(diskpart *)" in windows.settings["permissions"]["deny"]
    assert "Bash(diskpart *)" not in linux.settings["permissions"]["deny"]
    assert "Bash(rm -rf /*)" in linux.settings["permissions"]["deny"]
    assert "Bash(csrutil *)" in macos.settings["permissions"]["deny"]
    assert [p.name for p in windows.sources] == [
        "settings.base.json",
        "settings.windows.json",
    ]


def test_compose_missing_overlay_is_not_an_error(fake_repo: Path) -> None:
    """The base composes on its own; only a missing base is fatal."""
    (fake_repo / "claude" / "settings.linux.json").unlink()

    result = settings_merge.compose(fake_repo / "claude", "linux")

    assert result.settings["permissions"]["deny"] == ["Bash(git push *)"]
    assert len(result.sources) == 1


def test_compose_missing_base_raises(tmp_path: Path) -> None:
    """A missing base file is a hard error, not a silent empty composition."""
    with pytest.raises(settings_merge.SettingsError, match="not found"):
        settings_merge.compose(tmp_path, "linux")


def test_compose_invalid_json_raises(fake_repo: Path) -> None:
    """A damaged settings file fails loudly rather than composing garbage."""
    (fake_repo / "claude" / "settings.base.json").write_text("{not json", encoding="utf-8")

    with pytest.raises(settings_merge.SettingsError, match="invalid JSON"):
        settings_merge.compose(fake_repo / "claude", "linux")


def test_diff_settings_reports_missing_entries_and_kept_user_values() -> None:
    diffs = settings_merge.diff_settings(
        {"theme": "dark", "outputStyle": "A", "permissions": {"deny": ["a", "b"]}},
        {"outputStyle": "B", "effortLevel": "high", "permissions": {"deny": ["a"]}},
    )
    by_key = {d.key: d for d in diffs}

    assert by_key["theme"].kind == "missing"
    assert by_key["permissions.deny"].kind == "missing"
    assert by_key["permissions.deny"].expected == ["b"]
    assert by_key["outputStyle"].kind == "kept"
    assert (by_key["outputStyle"].expected, by_key["outputStyle"].actual) == ("A", "B")
    assert "effortLevel" not in by_key


def test_diff_settings_ignores_list_order_and_live_extras() -> None:
    diffs = settings_merge.diff_settings(
        {"permissions": {"deny": ["a", "b", "c"]}},
        {"permissions": {"deny": ["c", "a", "b", "extra"]}},
    )

    assert diffs == []


def test_diff_settings_against_nothing_reports_every_key() -> None:
    diffs = settings_merge.diff_settings({"theme": "dark", "outputStyle": "A"}, {})

    assert {d.key for d in diffs} == {"theme", "outputStyle"}
    assert all(d.kind == "missing" for d in diffs)
