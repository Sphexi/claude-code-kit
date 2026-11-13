"""Layout table, deploy classification, ownership and uninstall."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from helpers import STAMP, deploy_repo, snapshot

from tools import deploy, payload
from tools import state as kit_state
from tools.reconcile import inventory

CORE = "sphexi-core"
REVIEW = "sphexi-review"
ALL_PLUGINS = [CORE, REVIEW, "sphexi-python"]


def _targets(placements: list[payload.Placement]) -> dict[str, tuple[str, str]]:
    return {p.target: (p.category, p.unit) for p in placements}


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# --- layout -----------------------------------------------------------------


def test_layout_maps_the_payload_table(fake_repo: Path) -> None:
    placements = payload.layout(fake_repo, [CORE, REVIEW], ["pyright-lsp"], True)
    mapped = _targets(placements)

    assert mapped["CLAUDE.md"] == ("memory", "CLAUDE.md")
    assert mapped["agents/alpha.md"] == ("agent", "alpha")
    assert mapped["output-styles/terse.md"] == ("output-style", "terse")
    assert mapped["skills/own-skill/SKILL.md"] == ("skill", "own-skill")
    assert mapped["skills/sphexi-review/agents/reviewer.md"] == ("plugin", REVIEW)
    assert mapped["skills/sphexi-review/.claude-plugin/plugin.json"] == ("plugin", REVIEW)
    assert mapped["skills/sphexi-review/notices/demo-member/LICENSE"] == ("plugin", REVIEW)
    assert mapped["skills/pyright-lsp/skills/lsp/SKILL.md"] == ("plugin", "pyright-lsp")
    assert not [t for t in mapped if "sphexi-core" in t or "hooks" in t or "skill-creator" in t]
    assert "README.md" not in mapped and ".claude-plugin/plugin.json" not in mapped


def test_layout_options_and_errors(fake_repo: Path) -> None:
    without_memory = payload.layout(fake_repo, [CORE], [], include_claude_md=False)
    assert "CLAUDE.md" not in _targets(without_memory)

    without_core = payload.layout(fake_repo, [REVIEW], [], include_claude_md=False)
    assert not any(t.startswith(("agents/", "output-styles/")) for t in _targets(without_core))

    with pytest.raises(payload.PayloadError, match="not found"):
        payload.layout(fake_repo, ["sphexi-missing"])
    with pytest.raises(payload.PayloadError, match="not an extra"):
        payload.layout(fake_repo, [CORE], ["sphexi-review"])


def test_find_collisions_compares_case_insensitively(fake_repo: Path) -> None:
    clash = [
        payload.Placement(fake_repo / "a", "agents/Alpha.md", "agent", "Alpha"),
        payload.Placement(fake_repo / "b", "agents/alpha.md", "agent", "alpha"),
        payload.Placement(fake_repo / "c", "agents/beta.md", "agent", "beta"),
    ]

    assert payload.find_collisions(clash) == ["agents/Alpha.md", "agents/alpha.md"]


# --- fresh deploy ----------------------------------------------------------


def test_dry_run_changes_nothing_on_any_destructive_path(
    fake_repo: Path, tmp_claude_home: Path
) -> None:
    deploy_repo(fake_repo, tmp_claude_home, plugins=ALL_PLUGINS)
    _write(fake_repo / "plugins" / CORE / "agents" / "alpha.md", "changed\n")
    (tmp_claude_home / "agents" / "beta.md").write_text("edited\n", encoding="utf-8")
    _write(fake_repo / "plugins" / CORE / "agents" / "beta.md", "newer\n")
    before = snapshot(tmp_claude_home)

    overwrite = deploy_repo(
        fake_repo, tmp_claude_home, apply=False, overwrite=True, plugins=[CORE]
    )
    uninstall = deploy.run_uninstall(tmp_claude_home, apply=False, log=lambda _l: None)

    assert snapshot(tmp_claude_home) == before
    assert overwrite.applied is False and overwrite.backups and overwrite.removed
    assert uninstall.removed


def test_fresh_deploy_installs_exact_bytes_and_records_ownership(
    fake_repo: Path, tmp_claude_home: Path
) -> None:
    personal = tmp_claude_home / "skills" / "my-own-skill" / "SKILL.md"
    _write(personal, "mine\n")
    expected = payload.layout(fake_repo, ALL_PLUGINS, [], True)

    dry = deploy_repo(fake_repo, tmp_claude_home, apply=False, plugins=ALL_PLUGINS)
    assert not (tmp_claude_home / "agents").exists()
    assert len(dry.written) == len(expected) + 1

    plan = deploy_repo(fake_repo, tmp_claude_home, plugins=ALL_PLUGINS)

    assert {p.target: (tmp_claude_home / p.target).read_bytes() for p in expected} == {
        p.target: p.source.read_bytes() for p in expected
    }
    assert personal.read_text(encoding="utf-8") == "mine\n"
    recorded = kit_state.load(kit_state.state_path(tmp_claude_home))
    assert recorded is not None
    assert set(recorded.files) == {p.target for p in expected}
    assert recorded.plugins == ALL_PLUGINS and recorded.kit_version == "0.1.0"
    assert recorded.settings_created is True
    assert plan.conflicts == [] and plan.warnings == []


def test_deploy_options_select_content(fake_repo: Path, tmp_claude_home: Path) -> None:
    with pytest.raises(deploy.DeployError, match="unknown plugin"):
        deploy_repo(fake_repo, tmp_claude_home, plugins=["sphexi-nope"])
    assert snapshot(tmp_claude_home) == {}

    deploy_repo(
        fake_repo,
        tmp_claude_home,
        plugins=[REVIEW],
        extras=["pyright-lsp"],
        settings=False,
        claude_md=False,
    )

    files = snapshot(tmp_claude_home)
    assert "skills/sphexi-review/agents/reviewer.md" in files
    assert "skills/pyright-lsp/skills/lsp/SKILL.md" in files
    assert "CLAUDE.md" not in files and "settings.json" not in files
    assert not any(f.startswith(("agents/", "skills/sphexi-python")) for f in files)


def test_case_insensitive_target_collision_is_an_error(
    fake_repo: Path, tmp_claude_home: Path
) -> None:
    _write(fake_repo / "plugins" / CORE / "agents" / "Alpha.md", "dup\n")

    with pytest.raises(deploy.DeployError, match="collide"):
        deploy_repo(fake_repo, tmp_claude_home, plugins=[CORE])


# --- ownership --------------------------------------------------------------


def test_conflicts_are_skipped_whole_then_overwritten_with_a_backup(
    fake_repo: Path, tmp_claude_home: Path
) -> None:
    _write(tmp_claude_home / "agents" / "alpha.md", "user alpha\n")
    _write(tmp_claude_home / "CLAUDE.md", "user memory\n")
    _write(tmp_claude_home / "skills" / REVIEW / "agents" / "reviewer.md", "user reviewer\n")

    first = deploy_repo(fake_repo, tmp_claude_home, plugins=[CORE, REVIEW])

    assert {p.name for p in first.conflicts} == {"alpha.md", "CLAUDE.md", "reviewer.md"}
    assert (tmp_claude_home / "agents" / "alpha.md").read_text(encoding="utf-8") == "user alpha\n"
    assert (tmp_claude_home / "agents" / "beta.md").is_file()
    assert not (tmp_claude_home / "skills" / REVIEW / "skills").exists()
    recorded = kit_state.load(kit_state.state_path(tmp_claude_home))
    assert recorded is not None and "agents/alpha.md" not in recorded.files

    second = deploy_repo(fake_repo, tmp_claude_home, plugins=[CORE, REVIEW], overwrite=True)

    backup = tmp_claude_home / "agents" / f"alpha.md.bak-{STAMP}"
    assert backup.read_text(encoding="utf-8") == "user alpha\n"
    assert (tmp_claude_home / "agents" / "alpha.md").read_bytes() == (
        fake_repo / "plugins" / CORE / "agents" / "alpha.md"
    ).read_bytes()
    assert (tmp_claude_home / "skills" / REVIEW / "skills" / "helper" / "SKILL.md").is_file()
    assert len(second.backups) == 3 and second.conflicts == []


def test_redeploy_updates_unmodified_files_and_protects_edited_ones(
    fake_repo: Path, tmp_claude_home: Path
) -> None:
    deploy_repo(fake_repo, tmp_claude_home, plugins=[CORE])
    _write(fake_repo / "plugins" / CORE / "agents" / "alpha.md", "alpha v2\n")
    (tmp_claude_home / "agents" / "beta.md").write_text("user edit\n", encoding="utf-8")
    _write(fake_repo / "plugins" / CORE / "agents" / "beta.md", "beta v2\n")

    plan = deploy_repo(fake_repo, tmp_claude_home, plugins=[CORE])

    assert (tmp_claude_home / "agents" / "alpha.md").read_text(encoding="utf-8") == "alpha v2\n"
    assert (tmp_claude_home / "agents" / "beta.md").read_text(encoding="utf-8") == "user edit\n"
    assert [p.name for p in plan.conflicts] == ["beta.md"]
    recorded = kit_state.load(kit_state.state_path(tmp_claude_home))
    assert recorded is not None
    assert recorded.files["agents/alpha.md"] == inventory.sha256_text("alpha v2\n")


def test_dropping_a_plugin_removes_only_unmodified_kit_files(
    fake_repo: Path, tmp_claude_home: Path
) -> None:
    deploy_repo(fake_repo, tmp_claude_home, plugins=[CORE, REVIEW])
    unit_dir = tmp_claude_home / "skills" / REVIEW
    edited = unit_dir / "agents" / "reviewer.md"
    edited.write_text("my reviewer\n", encoding="utf-8")
    personal = tmp_claude_home / "skills" / "personal" / "SKILL.md"
    _write(personal, "personal\n")

    plan = deploy_repo(fake_repo, tmp_claude_home, plugins=[CORE])

    assert edited.read_text(encoding="utf-8") == "my reviewer\n"
    assert not (unit_dir / "skills").exists()
    assert personal.is_file()
    assert any("no longer shipped but was modified" in w for w in plan.warnings)
    recorded = kit_state.load(kit_state.state_path(tmp_claude_home))
    assert recorded is not None and recorded.plugins == [CORE]


def test_symlinked_target_is_never_written_through(
    fake_repo: Path, tmp_claude_home: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "outside.md"
    outside.write_text("outside\n", encoding="utf-8")
    (tmp_claude_home / "agents").mkdir()
    try:
        os.symlink(outside, tmp_claude_home / "agents" / "alpha.md")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")

    plan = deploy_repo(fake_repo, tmp_claude_home, plugins=[CORE], overwrite=True)

    assert outside.read_text(encoding="utf-8") == "outside\n"
    assert (tmp_claude_home / "agents" / "alpha.md").is_symlink()
    assert [p.name for p in plan.conflicts] == ["alpha.md"]


# --- settings ---------------------------------------------------------------


def test_settings_merge_keeps_user_content_and_backs_up_once(
    fake_repo: Path, tmp_claude_home: Path
) -> None:
    live = {"outputStyle": "Mine", "theme": "dark", "permissions": {"deny": ["Bash(x)"]}}
    (tmp_claude_home / "settings.json").write_text(json.dumps(live), encoding="utf-8")

    first = deploy_repo(fake_repo, tmp_claude_home, plugins=[CORE])
    second = deploy_repo(fake_repo, tmp_claude_home, plugins=[CORE])

    merged = json.loads((tmp_claude_home / "settings.json").read_text(encoding="utf-8"))
    assert merged["outputStyle"] == "Mine" and merged["theme"] == "dark"
    assert merged["permissions"]["deny"] == ["Bash(x)", "Bash(git push *)", "Bash(rm -rf /*)"]
    assert [k.key for k in first.kept_values] == ["outputStyle"]
    assert len(first.backups) == 1 and second.backups == []
    recorded = kit_state.load(kit_state.state_path(tmp_claude_home))
    assert recorded is not None
    assert recorded.settings_added == {
        "permissions.deny": ["Bash(git push *)", "Bash(rm -rf /*)"]
    }
    assert recorded.settings_created is False


def test_invalid_live_settings_are_left_untouched(
    fake_repo: Path, tmp_claude_home: Path
) -> None:
    (tmp_claude_home / "settings.json").write_text("{not json", encoding="utf-8")

    plan = deploy_repo(fake_repo, tmp_claude_home, plugins=[CORE])

    assert (tmp_claude_home / "settings.json").read_text(encoding="utf-8") == "{not json"
    assert any("not valid JSON" in w for w in plan.warnings)


# --- uninstall --------------------------------------------------------------


def test_uninstall_keeps_a_pruned_state_file_for_modified_files_left_behind(
    fake_repo: Path, tmp_claude_home: Path
) -> None:
    (tmp_claude_home / "settings.json").write_text(
        json.dumps({"theme": "dark"}), encoding="utf-8"
    )
    _write(tmp_claude_home / "agents" / "mine.md", "mine\n")
    deploy_repo(fake_repo, tmp_claude_home, plugins=[CORE, REVIEW])
    (tmp_claude_home / "agents" / "beta.md").write_text("edited\n", encoding="utf-8")

    plan = deploy.run_uninstall(
        tmp_claude_home, apply=True, log=lambda _l: None, timestamp=STAMP
    )

    remaining = set(snapshot(tmp_claude_home))
    assert remaining == {
        "agents/mine.md",
        "agents/beta.md",
        "settings.json",
        kit_state.STATE_FILENAME,
        f"settings.json.bak-{STAMP}",
        f"settings.json.bak-{STAMP}-1",
    }
    live = json.loads((tmp_claude_home / "settings.json").read_text(encoding="utf-8"))
    assert live == {"theme": "dark"}
    assert any("beta.md" in w for w in plan.warnings)
    assert not (tmp_claude_home / "skills").exists()
    kept = kit_state.load(kit_state.state_path(tmp_claude_home))
    assert kept is not None
    assert list(kept.files) == ["agents/beta.md"]
    assert kept.settings_added == {} and not kept.settings_created
    assert kept.plugins == [] and kept.extras == [] and not kept.claude_md


def test_uninstall_deletes_a_settings_file_the_kit_created(
    fake_repo: Path, tmp_claude_home: Path
) -> None:
    deploy_repo(fake_repo, tmp_claude_home, plugins=[CORE])

    deploy.run_uninstall(tmp_claude_home, apply=True, log=lambda _l: None)

    assert snapshot(tmp_claude_home) == {}


def test_uninstall_without_state_is_a_noop(tmp_claude_home: Path) -> None:
    plan = deploy.run_uninstall(tmp_claude_home, apply=True, log=lambda _l: None)

    assert plan.removed == [] and any("no state file" in n for n in plan.notes)


def test_state_paths_that_escape_the_config_dir_are_refused(
    tmp_claude_home: Path, state
) -> None:
    state.write(files={"../outside.txt": "0" * 64})

    with pytest.raises(deploy.DeployError, match="outside"):
        deploy.run_uninstall(tmp_claude_home, apply=True, log=lambda _l: None)


# --- warnings ---------------------------------------------------------------


def test_duplicate_warnings_never_touch_marketplace_state(
    fake_repo: Path, tmp_claude_home: Path
) -> None:
    installed = tmp_claude_home / "plugins" / "installed_plugins.json"
    ids = [
        "sphexi-core@sphexi",
        "sphexi-review@sphexi",
        "demo-member@claude-plugins-official",
        "anything@claude-code-workflows",
        "unrelated@elsewhere",
    ]
    _write(installed, json.dumps({"version": 2, "plugins": {i: [{}] for i in ids}}))
    before = installed.read_bytes()

    plan = deploy_repo(fake_repo, tmp_claude_home, plugins=[CORE, REVIEW])

    text = "\n".join(plan.warnings)
    assert "python-engineer and sphexi-core:python-engineer" in text
    assert "sphexi-review@sphexi is installed from the marketplace" in text
    assert "claude plugin uninstall demo-member@claude-plugins-official" in text
    assert "claude plugin uninstall anything@claude-code-workflows" in text
    assert "unrelated@elsewhere" not in text
    assert installed.read_bytes() == before


@pytest.mark.parametrize(
    ("managed", "expected"),
    [
        ({"strictKnownMarketplaces": [{"source": "github", "repo": "a/b"}]}, "strictKnownMarketplaces"),
        ({"strictKnownMarketplaces": []}, "strictKnownMarketplaces"),
        ({"strictKnownMarketplaces": [{"source": "skills-dir"}]}, None),
        ({"blockedMarketplaces": [{"source": "skills-dir"}]}, "block the skills-dir"),
        ({"strictPluginOnlyCustomization": True}, "strictPluginOnlyCustomization"),
        ({"strictPluginOnlyCustomization": False}, None),
        ({"permissions": {}}, None),
    ],
)
def test_managed_settings_warnings(tmp_path: Path, managed: dict, expected: str | None) -> None:
    _write(tmp_path / "managed-settings.json", json.dumps(managed))

    warnings = deploy.check_managed_settings(deploy.managed_settings_files(tmp_path))

    if expected is None:
        assert warnings == []
    else:
        assert len(warnings) == 1 and expected in warnings[0]


def test_managed_settings_drop_ins_and_damage(tmp_path: Path) -> None:
    _write(tmp_path / "managed-settings.d" / "10-a.json", json.dumps({"blockedMarketplaces": ["skills-dir"]}))
    _write(tmp_path / "managed-settings.d" / "20-bad.json", "{broken")
    _write(tmp_path / "managed-settings.d" / ".hidden.json", "{}")

    files = deploy.managed_settings_files(tmp_path)
    warnings = deploy.check_managed_settings(files)

    assert [f.name for f in files] == ["10-a.json", "20-bad.json"]
    assert any("block the skills-dir" in w for w in warnings)
    assert any("could not be read" in w for w in warnings)


# --- CLI --------------------------------------------------------------------


def test_cli_defaults_to_dry_run_and_exits_two_on_unusable_input(
    fake_repo: Path, tmp_claude_home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    args = ["--config-dir", str(tmp_claude_home), "--plugins", f"{CORE},{REVIEW}"]

    assert deploy.run(args, repo_root=fake_repo) == 0
    assert "DRY RUN" in capsys.readouterr().out
    assert snapshot(tmp_claude_home) == {}

    assert deploy.run([*args[:2], "--plugins", "nope"], repo_root=fake_repo) == 2
    assert deploy.run([*args[:2], "--plugins", " , "], repo_root=fake_repo) == 2
    assert deploy.run(args, repo_root=fake_repo.parent / "missing") == 2
    _write(tmp_claude_home / kit_state.STATE_FILENAME, "{bad")
    assert deploy.run(args, repo_root=fake_repo) == 2
    assert "error:" in capsys.readouterr().err
