"""Every reconcile verb: dry runs write nothing, applies touch only what they should."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from helpers import STAMP, compare_repo, deploy_repo, snapshot, unit

from tools import state
from tools.reconcile import actions, inventory

CORE = "sphexi-core"
REVIEW = "sphexi-review"
SILENT = lambda _line: None  # noqa: E731


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture()
def deployed(fake_repo: Path, tmp_claude_home: Path) -> Path:
    deploy_repo(fake_repo, tmp_claude_home, plugins=[CORE, REVIEW], settings=False)
    return tmp_claude_home


def _verdict(fake_repo: Path, home: Path, name: str):
    return unit(compare_repo(fake_repo, home), name)


def test_dry_runs_change_nothing_in_the_live_dir_or_the_repo(
    fake_repo: Path, deployed: Path
) -> None:
    _write(fake_repo / "plugins" / CORE / "agents" / "alpha.md", "alpha v2\n")
    (deployed / "agents" / "beta.md").write_text("user edit\n", encoding="utf-8")
    (deployed / "output-styles" / "terse.md").unlink()
    (fake_repo / "plugins" / CORE / "skills" / "own-skill" / "SKILL.md").unlink()
    _write(deployed / "agents" / "mine.md", "mine\n")
    result = compare_repo(fake_repo, deployed)
    live_before, repo_before = snapshot(deployed), snapshot(fake_repo)

    records = [
        actions.install(unit(result, "terse"), deployed, log=SILENT),
        actions.update(unit(result, "alpha"), deployed, log=SILENT),
        actions.update(unit(result, "beta"), deployed, log=SILENT),
        actions.remove(unit(result, "own-skill"), deployed, log=SILENT),
        actions.adopt(unit(result, "mine"), fake_repo, log=SILENT),
        actions.merge_settings({"theme": "dark"}, deployed, log=SILENT),
    ]

    assert snapshot(deployed) == live_before and snapshot(fake_repo) == repo_before
    assert [r.applied for r in records] == [False] * 6
    assert all(r.touched for r in records)


def test_install_writes_the_whole_unit_and_records_hashes(
    fake_repo: Path, deployed: Path
) -> None:
    for path in (deployed / "skills" / REVIEW).rglob("*"):
        if path.is_file():
            path.unlink()
    state_before = state.load(state.state_path(deployed))
    assert state_before is not None
    result = compare_repo(fake_repo, deployed)

    record = actions.install(unit(result, REVIEW), deployed, apply=True, log=SILENT)

    assert (deployed / "skills" / REVIEW / "agents" / "reviewer.md").is_file()
    assert record.applied and record.backups == []
    assert record.recorded == {
        k: v for k, v in state_before.files.items() if k.startswith(f"skills/{REVIEW}/")
    }


def test_updating_a_behind_unit_needs_no_backup_and_a_modified_one_gets_one(
    fake_repo: Path, deployed: Path
) -> None:
    _write(fake_repo / "plugins" / CORE / "agents" / "alpha.md", "alpha v2\n")
    (deployed / "agents" / "beta.md").write_text("user edit\n", encoding="utf-8")
    _write(fake_repo / "plugins" / CORE / "agents" / "beta.md", "beta v2\n")
    result = compare_repo(fake_repo, deployed)

    behind = actions.update(unit(result, "alpha"), deployed, apply=True, log=SILENT, timestamp=STAMP)
    modified = actions.update(unit(result, "beta"), deployed, apply=True, log=SILENT, timestamp=STAMP)

    assert (deployed / "agents" / "alpha.md").read_text(encoding="utf-8") == "alpha v2\n"
    assert behind.backups == [] and behind.recorded["agents/alpha.md"] == inventory.sha256_text("alpha v2\n")
    assert (deployed / "agents" / "beta.md").read_text(encoding="utf-8") == "beta v2\n"
    assert (deployed / "agents" / f"beta.md.bak-{STAMP}").read_text(encoding="utf-8") == "user edit\n"
    assert len(modified.backups) == 1


def test_update_removes_files_the_repo_dropped_only_when_unmodified(
    fake_repo: Path, deployed: Path
) -> None:
    helper = fake_repo / "plugins" / REVIEW / "skills" / "helper" / "SKILL.md"
    helper.unlink()
    _write(fake_repo / "plugins" / REVIEW / "agents" / "reviewer.md", "reviewer v2\n")

    result = compare_repo(fake_repo, deployed)
    record = actions.update(unit(result, REVIEW), deployed, apply=True, log=SILENT)

    assert not (deployed / "skills" / REVIEW / "skills").exists()
    assert record.forgotten == [f"skills/{REVIEW}/skills/helper/SKILL.md"]


def test_remove_deletes_retired_files_unless_they_were_modified(
    fake_repo: Path, deployed: Path
) -> None:
    (fake_repo / "plugins" / CORE / "agents" / "alpha.md").unlink()
    (fake_repo / "plugins" / CORE / "agents" / "beta.md").unlink()
    (deployed / "agents" / "beta.md").write_text("edited\n", encoding="utf-8")
    result = compare_repo(fake_repo, deployed)

    gone = actions.remove(unit(result, "alpha"), deployed, apply=True, log=SILENT)
    kept = actions.remove(unit(result, "beta"), deployed, apply=True, log=SILENT)

    assert not (deployed / "agents" / "alpha.md").exists() and gone.forgotten == ["agents/alpha.md"]
    assert (deployed / "agents" / "beta.md").read_text(encoding="utf-8") == "edited\n"
    assert kept.removed == [] and "left in place" in kept.reason


@pytest.mark.parametrize("name", ["terse", "mine", "skills/mystery"])
def test_remove_refuses_anything_that_is_not_retired(
    fake_repo: Path, deployed: Path, name: str
) -> None:
    (deployed / "output-styles" / "terse.md").unlink()
    _write(deployed / "agents" / "mine.md", "mine\n")
    _write(deployed / "skills" / "mystery" / "README.md", "x\n")
    before = snapshot(deployed)
    result = compare_repo(fake_repo, deployed)

    record = actions.remove(unit(result, name), deployed, apply=True, log=SILENT)

    assert record.refused and snapshot(deployed) == before


def test_adopt_copies_live_content_into_claude_and_records_it(
    fake_repo: Path, deployed: Path
) -> None:
    _write(fake_repo / "claude" / "agents" / "alpha.md", "authored\n")
    (deployed / "agents" / "alpha.md").write_text("improved\n", encoding="utf-8")
    _write(deployed / "agents" / "mine.md", "mine\n")
    _write(deployed / "skills" / "hand" / "SKILL.md", "hand\n")
    result = compare_repo(fake_repo, deployed)

    modified = actions.adopt(unit(result, "alpha"), fake_repo, apply=True, log=SILENT)
    unmanaged = actions.adopt(unit(result, "mine"), fake_repo, apply=True, log=SILENT)
    skill = actions.adopt(unit(result, "hand"), fake_repo, apply=True, log=SILENT)

    assert (fake_repo / "claude" / "agents" / "alpha.md").read_text(encoding="utf-8") == "improved\n"
    assert (fake_repo / "claude" / "agents" / "mine.md").read_text(encoding="utf-8") == "mine\n"
    assert (fake_repo / "claude" / "skills" / "hand" / "SKILL.md").is_file()
    assert modified.commit_hint == ["claude/agents/alpha.md"]
    assert unmanaged.recorded == {"agents/mine.md": inventory.sha256_text("mine\n")}
    assert skill.written and not skill.refused


def test_adopt_refusals(fake_repo: Path, deployed: Path) -> None:
    (deployed / "skills" / REVIEW / "agents" / "reviewer.md").write_text("e\n", encoding="utf-8")
    (deployed / "agents" / "beta.md").write_text("edited\n", encoding="utf-8")
    _write(deployed / "skills" / "mystery" / "README.md", "x\n")
    result = compare_repo(fake_repo, deployed)

    plugin = actions.adopt(unit(result, REVIEW), fake_repo, apply=True, log=SILENT)
    unclassified = actions.adopt(unit(result, "skills/mystery"), fake_repo, apply=True, log=SILENT)
    not_authored = actions.adopt(unit(result, "beta"), fake_repo, apply=True, log=SILENT)

    assert plugin.reason == actions.ADOPT_REFUSAL_PLUGIN
    assert unclassified.reason == actions.ADOPT_REFUSAL_UNCLASSIFIABLE
    assert not_authored.reason == actions.ADOPT_REFUSAL_NOT_AUTHORED
    assert not (fake_repo / "claude" / "agents").exists()


@pytest.mark.parametrize(
    ("rel", "expected"),
    [
        ("CLAUDE.md", "claude/global-CLAUDE.md"),
        ("agents/a.md", "claude/agents/a.md"),
        ("output-styles/s.md", "claude/output-styles/s.md"),
        ("skills/x/SKILL.md", "claude/skills/x/SKILL.md"),
    ],
)
def test_repo_destination_maps_live_paths_to_authored_sources(
    tmp_path: Path, rel: str, expected: str
) -> None:
    assert actions.repo_destination(rel, tmp_path) == (tmp_path / expected).resolve()


@pytest.mark.parametrize("rel", ["agents/../../escape.md", "plugins/x.json", "settings.json"])
def test_repo_destination_refuses_traversal_unknown_roots_and_settings(
    tmp_path: Path, rel: str
) -> None:
    with pytest.raises(actions.ActionError):
        actions.repo_destination(rel, tmp_path)


def test_merge_settings_adds_only_and_backs_up_an_existing_file(tmp_claude_home: Path) -> None:
    composed = {"outputStyle": "A", "permissions": {"deny": ["a"]}}
    (tmp_claude_home / "settings.json").write_text(
        json.dumps({"permissions": {"deny": ["own"]}}), encoding="utf-8"
    )

    record = actions.merge_settings(composed, tmp_claude_home, apply=True, log=SILENT, timestamp=STAMP)

    live = json.loads((tmp_claude_home / "settings.json").read_text(encoding="utf-8"))
    assert live == {"permissions": {"deny": ["own", "a"]}, "outputStyle": "A"}
    assert record.settings_added == {"outputStyle": "A", "permissions.deny": ["a"]}
    assert (tmp_claude_home / f"settings.json.bak-{STAMP}").is_file()
    assert not record.settings_created


def test_merge_settings_creates_a_missing_file_and_refuses_a_damaged_one(
    tmp_claude_home: Path, tmp_path: Path
) -> None:
    created = actions.merge_settings({"theme": "dark"}, tmp_claude_home, apply=True, log=SILENT)
    damaged_home = tmp_path / "damaged"
    _write(damaged_home / "settings.json", "{broken")
    refused = actions.merge_settings({"theme": "dark"}, damaged_home, apply=True, log=SILENT)

    assert created.settings_created and created.backups == []
    assert refused.refused and (damaged_home / "settings.json").read_text(encoding="utf-8") == "{broken"


@pytest.mark.parametrize("apply", [False, True])
def test_every_affected_absolute_path_is_printed(
    fake_repo: Path, deployed: Path, apply: bool
) -> None:
    (fake_repo / "plugins" / CORE / "agents" / "alpha.md").unlink()
    (deployed / "output-styles" / "terse.md").unlink()
    result = compare_repo(fake_repo, deployed)
    lines: list[str] = []

    actions.remove(unit(result, "alpha"), deployed, apply=apply, log=lines.append)
    actions.install(unit(result, "terse"), deployed, apply=apply, log=lines.append)

    assert lines == [
        f"    DELETE {(deployed / 'agents' / 'alpha.md').resolve()}",
        f"    write  {(deployed / 'output-styles' / 'terse.md').resolve()}",
    ]
