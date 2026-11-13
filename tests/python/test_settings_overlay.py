"""The shipped settings files, and merging composed settings into a live file."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.reconcile import settings_merge

PLATFORMS = ["win32", "darwin", "linux"]
FILES = [
    "settings.base.json",
    "settings.linux.json",
    "settings.macos.json",
    "settings.windows.json",
]
FORBIDDEN_BASE_KEYS = (
    "model",
    "effortLevel",
    "switchModelsOnFlag",
    "env",
    "enabledPlugins",
    "extraKnownMarketplaces",
)
BLANKET_ALLOWS = ("Bash(*)", "Read(*)", "Write(*)", "Edit(*)", "MultiEdit(*)")
WINDOWS_RULES = (
    "runas",
    "diskpart",
    "bcdedit",
    "reg add",
    "regedit",
    "takeown",
    "net user",
    "C:/Windows/",
)
MACOS_RULES = ("diskutil erase", "csrutil", "nvram", "sysadminctl", "~/Library/Keychains/")
PLATFORM_PATH_MARKERS = ("C:", "/etc/", "/Library", "/System", "diskutil", "diskpart")
PROJECT_SCOPE_GIT = ("git commit", "git add", "git checkout", "git merge", "git rebase", "git reset")


@pytest.fixture()
def claude_dir(repo_root: Path) -> Path:
    return repo_root / "claude"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _deny(claude_dir: Path, platform: str) -> list[str]:
    return settings_merge.compose(claude_dir, platform).settings["permissions"]["deny"]


@pytest.mark.parametrize("name", FILES)
def test_every_settings_file_is_a_json_object(claude_dir: Path, name: str) -> None:
    assert isinstance(_load(claude_dir / name), dict)


def test_base_is_conservative_and_platform_neutral(claude_dir: Path) -> None:
    base = _load(claude_dir / "settings.base.json")
    text = json.dumps(base)

    assert not set(FORBIDDEN_BASE_KEYS) & set(base)
    assert "allow" not in base["permissions"] and "defaultMode" not in base["permissions"]
    assert not set(BLANKET_ALLOWS) & set(base["permissions"].get("allow", []))
    assert not [m for m in PLATFORM_PATH_MARKERS if m in text]
    assert base["$schema"].startswith("https://")
    assert base["outputStyle"] == "Terse (Full)"


@pytest.mark.parametrize("name", FILES[1:])
def test_overlays_carry_deny_rules_only(claude_dir: Path, name: str) -> None:
    overlay = _load(claude_dir / name)

    assert set(overlay) == {"permissions"}
    assert set(overlay["permissions"]) == {"deny"}


@pytest.mark.parametrize(
    ("platform", "expected"),
    [("win32", "windows"), ("cygwin", "linux"), ("darwin", "macos"), ("linux", "linux"), ("freebsd14", "linux")],
)
def test_overlay_for_platform(platform: str, expected: str) -> None:
    assert settings_merge.overlay_for(platform) == expected


@pytest.mark.parametrize("platform", PLATFORMS)
def test_deny_list_blocks_both_git_push_forms_and_nothing_else_in_git(
    claude_dir: Path, platform: str
) -> None:
    deny = _deny(claude_dir, platform)

    assert "Bash(git push)" in deny and "Bash(git push *)" in deny
    assert [r for r in deny if "git " in r and "git push" not in r] == []
    assert not [r for r in deny for fragment in PROJECT_SCOPE_GIT if fragment in r]


@pytest.mark.parametrize("platform", PLATFORMS)
def test_composition_is_deterministic_deduplicated_and_lossless(
    claude_dir: Path, platform: str
) -> None:
    first = settings_merge.compose(claude_dir, platform)
    second = settings_merge.compose(claude_dir, platform)
    deny = first.settings["permissions"]["deny"]
    sources = [_load(path) for path in first.sources]

    assert first.render() == second.render()
    assert len(deny) == len(set(deny))
    assert set(deny) == {rule for s in sources for rule in s["permissions"]["deny"]}
    assert "agentPushNotifEnabled" not in first.settings
    assert not [r for r in deny if r.startswith("Write(")]


def test_each_platform_composes_only_its_own_overlay(claude_dir: Path) -> None:
    linux, macos, windows = (_deny(claude_dir, p) for p in ("linux", "darwin", "win32"))

    assert not [r for r in linux if "C:" in r or "diskutil" in r]
    assert not [r for r in macos if "C:" in r or "/etc/shadow" in r or "mkswap" in r]
    assert not [r for r in windows if "diskutil" in r or "/etc/" in r]
    assert any("/etc/shadow" in r for r in linux)


@pytest.mark.parametrize("fragment", WINDOWS_RULES)
def test_windows_rules_survive(claude_dir: Path, fragment: str) -> None:
    assert any(fragment in rule for rule in _deny(claude_dir, "win32"))


@pytest.mark.parametrize("fragment", MACOS_RULES)
def test_macos_rules_present(claude_dir: Path, fragment: str) -> None:
    assert any(fragment in rule for rule in _deny(claude_dir, "darwin"))


def test_netsh_denies_mutating_subcommands_only(claude_dir: Path) -> None:
    netsh = [r for r in _deny(claude_dir, "win32") if "netsh" in r]

    assert "Bash(netsh *)" not in netsh
    assert any("advfirewall set" in r for r in netsh)


# --- merge into live --------------------------------------------------------


COMPOSED = {
    "$schema": "https://example.invalid/schema.json",
    "outputStyle": "Terse (Full)",
    "permissions": {"deny": ["a", "b"], "allow": ["x"]},
    "enabledPlugins": {"p@m": True, "off@m": False},
    "env": {"K": "1"},
}


@pytest.mark.parametrize(
    ("live", "expected_deny", "expected_added"),
    [
        ({}, ["a", "b"], {"a", "b"}),
        ({"permissions": {"deny": ["b", "z"]}}, ["b", "z", "a"], {"a"}),
        ({"permissions": {"deny": ["a", "b"]}}, ["a", "b"], set()),
    ],
)
def test_deny_entries_union_with_live_entries_first(
    live: dict, expected_deny: list[str], expected_added: set[str]
) -> None:
    new, added, _ = settings_merge.apply_to_live(COMPOSED, live)

    assert new["permissions"]["deny"] == expected_deny
    assert set(added.get("permissions.deny", [])) == expected_added


def test_scalars_are_set_only_when_absent_and_differences_are_reported() -> None:
    live = {"outputStyle": "Mine", "theme": "dark"}

    new, added, kept = settings_merge.apply_to_live(COMPOSED, live)

    assert new["outputStyle"] == "Mine" and new["theme"] == "dark"
    assert new["$schema"] == COMPOSED["$schema"] and added["$schema"] == COMPOSED["$schema"]
    assert "outputStyle" not in added
    assert [(k.key, k.kit, k.live) for k in kept] == [("outputStyle", "Terse (Full)", "Mine")]


def test_dict_keys_add_absent_entries_and_never_change_existing_ones() -> None:
    live = {"enabledPlugins": {"off@m": True}, "env": {"K": "other", "OWN": "1"}}

    new, added, kept = settings_merge.apply_to_live(COMPOSED, live)

    assert new["enabledPlugins"] == {"off@m": True, "p@m": True}
    assert new["env"] == {"K": "other", "OWN": "1"}
    assert added["enabledPlugins"] == {"p@m": True} and "env" not in added
    assert {k.key for k in kept} == {"enabledPlugins.off@m", "env.K"}


def test_unknown_live_keys_are_untouched_and_the_input_is_not_mutated() -> None:
    live = {"hooks": {"Stop": []}, "permissions": {"ask": ["q"]}}
    snapshot = json.loads(json.dumps(live))

    new, _, _ = settings_merge.apply_to_live(COMPOSED, live)

    assert new["hooks"] == {"Stop": []} and new["permissions"]["ask"] == ["q"]
    assert live == snapshot


def test_a_second_application_adds_nothing() -> None:
    once, _, _ = settings_merge.apply_to_live(COMPOSED, {})

    twice, added, kept = settings_merge.apply_to_live(COMPOSED, once)

    assert twice == once and added == {} and kept == []


def test_revert_removes_recorded_additions_and_keeps_user_changes() -> None:
    live = {"theme": "dark", "permissions": {"deny": ["mine"]}, "env": {"OWN": "1"}}
    merged, added, _ = settings_merge.apply_to_live(COMPOSED, live)
    merged["env"]["K"] = "changed"
    merged["permissions"]["deny"].append("later")

    reverted, done, left = settings_merge.revert_from_live(merged, added)

    assert reverted == {
        "theme": "dark",
        "permissions": {"deny": ["mine", "later"]},
        "env": {"OWN": "1", "K": "changed"},
    }
    assert "env.K" in left and "permissions.deny: a" in done


def test_revert_of_a_fresh_file_leaves_nothing() -> None:
    merged, added, _ = settings_merge.apply_to_live(COMPOSED, {})

    reverted, _, left = settings_merge.revert_from_live(merged, added)

    assert reverted == {} and left == []
