"""Classification of repository layout against live content and recorded state."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from helpers import compare_repo, deploy_repo, unit

from tools.reconcile import diff, inventory

CORE = "sphexi-core"
REVIEW = "sphexi-review"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


@pytest.fixture()
def deployed(fake_repo: Path, tmp_claude_home: Path) -> Path:
    deploy_repo(fake_repo, tmp_claude_home, plugins=[CORE, REVIEW], settings=False)
    return tmp_claude_home


def test_a_fully_deployed_repo_is_all_matched(fake_repo: Path, deployed: Path) -> None:
    result = compare_repo(fake_repo, deployed)

    assert {u.klass for u in result.units} == {"matched"}
    assert not result.has_actionable()


def test_fresh_machine_reports_everything_missing(
    fake_repo: Path, tmp_claude_home: Path
) -> None:
    result = compare_repo(fake_repo, tmp_claude_home)

    assert {u.klass for u in result.units} == {"missing"}
    assert result.has_actionable()


def test_each_class_is_assigned_from_live_state_and_recorded_hashes(
    fake_repo: Path, deployed: Path
) -> None:
    _write(fake_repo / "plugins" / CORE / "agents" / "alpha.md", "alpha v2\n")
    (deployed / "agents" / "beta.md").write_text("user edit\n", encoding="utf-8", newline="\n")
    (deployed / "output-styles" / "terse.md").unlink()
    (fake_repo / "plugins" / CORE / "skills" / "own-skill" / "SKILL.md").unlink()
    _write(deployed / "agents" / "mine.md", "mine\n")

    result = compare_repo(fake_repo, deployed)

    assert unit(result, "alpha").klass == "behind"
    assert unit(result, "beta").klass == "modified"
    assert unit(result, "terse").klass == "missing"
    assert unit(result, "own-skill").klass == "retired"
    assert unit(result, "mine").klass == "unmanaged"
    assert unit(result, REVIEW).klass == "matched"


def test_identical_content_without_a_record_is_matched_and_differing_is_modified(
    fake_repo: Path, tmp_claude_home: Path
) -> None:
    source = fake_repo / "plugins" / CORE / "agents"
    _write(tmp_claude_home / "agents" / "alpha.md", (source / "alpha.md").read_text("utf-8"))
    _write(tmp_claude_home / "agents" / "beta.md", "someone else's\n")

    result = compare_repo(fake_repo, tmp_claude_home, plugins=(CORE,))

    assert unit(result, "alpha").klass == "matched"
    assert unit(result, "beta").klass == "modified"


def test_plugin_units_roll_up_with_modified_dominating_and_foreign_files_counted_apart(
    fake_repo: Path, deployed: Path
) -> None:
    bundle = deployed / "skills" / REVIEW
    (bundle / "agents" / "reviewer.md").write_text("edit\n", encoding="utf-8", newline="\n")
    _write(fake_repo / "plugins" / REVIEW / "skills" / "helper" / "SKILL.md", "helper v2\n")
    _write(bundle / "my-notes.md", "foreign\n")

    result = compare_repo(fake_repo, deployed)
    verdict = unit(result, REVIEW)

    assert verdict.klass == "modified" and verdict.rolled_up
    assert "1 modified" in verdict.detail and "1 behind" in verdict.detail
    assert [f.klass for f in verdict.files if f.rel.endswith("my-notes.md")] == ["unmanaged"]


def test_a_matched_plugin_with_only_a_foreign_file_stays_matched_in_the_actionable_sense(
    fake_repo: Path, deployed: Path
) -> None:
    _write(deployed / "skills" / REVIEW / "my-notes.md", "foreign\n")

    result = compare_repo(fake_repo, deployed)

    assert unit(result, REVIEW).klass == "matched"
    assert not result.has_actionable()


def test_unclassifiable_skill_directory_is_its_own_unit(
    fake_repo: Path, tmp_claude_home: Path
) -> None:
    _write(tmp_claude_home / "skills" / "mystery" / "README.md", "no markers\n")

    result = compare_repo(fake_repo, tmp_claude_home)

    assert unit(result, "skills/mystery").klass == "unclassifiable"
    assert not [u for u in result.units if u.klass != "unclassifiable" and "mystery" in u.unit]


def test_settings_are_a_subset_check_that_keeps_user_values(fake_repo: Path) -> None:
    composed = {"outputStyle": "A", "permissions": {"deny": ["a", "b"]}}
    empty = inventory.Inventory(side="x", root=fake_repo)

    kept = diff.compare(empty, empty, {}, composed, {"outputStyle": "B", "permissions": {"deny": ["a", "b", "own"]}})
    behind = diff.compare(empty, empty, {}, composed, {"outputStyle": "A", "permissions": {"deny": ["a"]}})
    absent = diff.compare(empty, empty, {}, composed, None)
    skipped = diff.compare(empty, empty, {}, None, None)

    assert kept.settings_class == "matched" and [d.kind for d in kept.settings_diffs] == ["kept"]
    assert behind.settings_class == "behind" and behind.settings_diffs[0].expected == ["b"]
    assert absent.settings_class == "missing"
    assert skipped.settings_class == "matched"


def test_symlinks_are_skipped_and_reported(fake_repo: Path, tmp_claude_home: Path, tmp_path: Path) -> None:
    target = tmp_path / "elsewhere.md"
    target.write_text("x", encoding="utf-8", newline="\n")
    (tmp_claude_home / "agents").mkdir()
    try:
        os.symlink(target, tmp_claude_home / "agents" / "linked.md")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")

    result = compare_repo(fake_repo, tmp_claude_home)

    assert ("live:agents/linked.md", "symlink") in result.skipped
    assert not [u for u in result.units if u.unit == "linked"]


def test_counts_cover_every_class(fake_repo: Path, tmp_claude_home: Path) -> None:
    counts = compare_repo(fake_repo, tmp_claude_home).counts()

    assert set(counts) == set(diff.CLASSES)
    assert counts["missing"] > 0 and counts["matched"] == 0
