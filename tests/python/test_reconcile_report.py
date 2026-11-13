"""Report rendering and the reconcile command line."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from helpers import compare_repo, deploy_repo, snapshot

from tools import state
from tools.reconcile import __main__ as cli
from tools.reconcile import actions, diff, inventory, report

CORE = "sphexi-core"
REVIEW = "sphexi-review"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _render(result: diff.DiffResult, home: Path, **kwargs) -> str:
    return report.render(
        result, apply=kwargs.pop("apply", False), config_dir=str(home), repo_root="repo", **kwargs
    )


def _run(repo: Path, home: Path, *args: str) -> int:
    return cli.run(["--config-dir", str(home), *args], repo_root=repo)


@pytest.fixture()
def deployed(fake_repo: Path, tmp_claude_home: Path) -> Path:
    deploy_repo(fake_repo, tmp_claude_home, plugins=[CORE, REVIEW, "sphexi-python"])
    return tmp_claude_home


def test_banner_marks_dry_runs_and_applies_at_top_and_bottom(
    fake_repo: Path, tmp_claude_home: Path
) -> None:
    result = compare_repo(fake_repo, tmp_claude_home)

    dry = _render(result, tmp_claude_home).splitlines()
    live = _render(result, tmp_claude_home, apply=True).splitlines()

    assert dry[1] == dry[-2] == report.BANNER_DRY
    assert live[1] == live[-2] == report.BANNER_APPLY


def test_plugin_is_one_line_unless_verbose_and_unmanaged_is_counted_not_listed(
    fake_repo: Path, deployed: Path
) -> None:
    (deployed / "skills" / REVIEW / "agents" / "reviewer.md").write_text("e\n", encoding="utf-8", newline="\n")
    _write(deployed / "agents" / "mine.md", "mine\n")
    result = compare_repo(fake_repo, deployed, plugins=(CORE, REVIEW))

    plain = _render(result, deployed)
    verbose = _render(result, deployed, verbose=True)
    listed = _render(result, deployed, show_unmanaged=True)

    unit_lines = [ln for ln in plain.splitlines() if ln.startswith("  [") and REVIEW in ln]
    assert len(unit_lines) == 1
    assert not [ln for ln in plain.splitlines() if ln.startswith("        [")]
    assert "        [ MOD] skills/sphexi-review/agents/reviewer.md" in verbose
    assert "1 unmanaged" in plain and "mine" not in plain.replace("unmanaged", "")
    assert "[  UNM] mine" in listed


def test_settings_section_shows_missing_entries_and_kept_user_values(tmp_path: Path) -> None:
    empty = inventory.Inventory(side="x", root=tmp_path)
    result = diff.compare(
        empty, empty, {}, {"outputStyle": "A", "theme": "dark"}, {"outputStyle": "B"}
    )

    text = _render(result, tmp_path)

    assert "+ theme: 'dark'" in text
    assert "kept user value 'B' (kit sets 'A')" in text


def test_collisions_and_refusals_are_reported(tmp_path: Path) -> None:
    result = diff.DiffResult(collisions=["agents/Alpha.md", "agents/alpha.md"])
    record = actions.ActionRecord(verb="adopt", unit="x", refused=True, reason="because")

    assert "!! agents/Alpha.md" in _render(result, tmp_path)
    summary = report.render_actions([record], apply=True)
    assert "Refused" in summary and "because" in summary


def test_default_run_and_dry_run_flag_change_nothing(fake_repo: Path, tmp_claude_home: Path) -> None:
    before = snapshot(tmp_claude_home)

    assert _run(fake_repo, tmp_claude_home) == 0
    assert _run(fake_repo, tmp_claude_home, "--dry-run") == 0

    assert snapshot(tmp_claude_home) == before


def test_apply_without_a_tty_changes_only_what_yes_safe_covers(
    fake_repo: Path, deployed: Path
) -> None:
    _write(fake_repo / "plugins" / CORE / "agents" / "alpha.md", "alpha v2\n")
    (deployed / "output-styles" / "terse.md").unlink()
    (deployed / "agents" / "beta.md").write_text("user edit\n", encoding="utf-8", newline="\n")
    _write(fake_repo / "plugins" / CORE / "agents" / "beta.md", "beta v2\n")
    (fake_repo / "plugins" / CORE / "skills" / "own-skill" / "SKILL.md").unlink()
    _write(deployed / "agents" / "mine.md", "mine\n")

    assert _run(fake_repo, deployed, "--apply") == 0
    assert (deployed / "agents" / "alpha.md").read_text(encoding="utf-8") == "---\nname: alpha\n---\nAlpha.\n"

    assert _run(fake_repo, deployed, "--apply", "--yes-safe") == 0

    assert (deployed / "agents" / "alpha.md").read_text(encoding="utf-8") == "alpha v2\n"
    assert (deployed / "output-styles" / "terse.md").is_file()
    assert (deployed / "agents" / "beta.md").read_text(encoding="utf-8") == "user edit\n"
    assert (deployed / "skills" / "own-skill" / "SKILL.md").is_file()
    assert (deployed / "agents" / "mine.md").is_file()
    recorded = state.load(state.state_path(deployed))
    assert recorded is not None
    assert recorded.files["agents/alpha.md"] == inventory.sha256_text("alpha v2\n")


def test_selection_and_settings_tracking_come_from_the_state_file(
    fake_repo: Path, tmp_claude_home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    deploy_repo(fake_repo, tmp_claude_home, plugins=[CORE], settings=False)

    assert _run(fake_repo, tmp_claude_home) == 0

    out = capsys.readouterr().out
    assert "missing=0" in out and "behind=0" in out and "modified=0" in out
    assert REVIEW not in out and "[  ok] settings.json" in out


def test_yes_safe_creates_missing_settings_but_never_merges_into_an_existing_file(
    fake_repo: Path, tmp_claude_home: Path
) -> None:
    deploy_repo(fake_repo, tmp_claude_home, plugins=[CORE])
    settings = tmp_claude_home / "settings.json"
    settings.write_text("{}", encoding="utf-8", newline="\n")

    assert _run(fake_repo, tmp_claude_home, "--apply", "--yes-safe") == 0
    assert settings.read_text(encoding="utf-8") == "{}"

    settings.unlink()
    assert _run(fake_repo, tmp_claude_home, "--apply", "--yes-safe") == 0
    assert "Bash(git push *)" in json.loads(settings.read_text(encoding="utf-8"))["permissions"]["deny"]


def test_report_file_is_written(fake_repo: Path, tmp_claude_home: Path, tmp_path: Path) -> None:
    target = tmp_path / "out" / "drift.txt"

    assert _run(fake_repo, tmp_claude_home, "--report", str(target)) == 0

    assert report.BANNER_DRY in target.read_text(encoding="utf-8")


def test_unusable_inputs_exit_two(
    fake_repo: Path, tmp_claude_home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(fake_repo.parent / "missing", tmp_claude_home) == 2
    _write(tmp_claude_home / state.STATE_FILENAME, "{bad")
    assert _run(fake_repo, tmp_claude_home) == 2
    assert "error:" in capsys.readouterr().err


def test_a_case_insensitive_collision_in_the_payload_exits_two(
    fake_repo: Path, tmp_claude_home: Path, case_sensitive_fs: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write(fake_repo / "plugins" / CORE / "agents" / "Alpha.md", "dup\n")

    assert _run(fake_repo, tmp_claude_home, "--apply") == 2
    assert "error:" in capsys.readouterr().err


def test_load_live_settings_tolerates_absence_and_damage(tmp_claude_home: Path) -> None:
    assert cli.load_live_settings(tmp_claude_home) is None

    (tmp_claude_home / "settings.json").write_text("{nope", encoding="utf-8", newline="\n")
    assert cli.load_live_settings(tmp_claude_home) is None

    (tmp_claude_home / "settings.json").write_text(json.dumps([1]), encoding="utf-8", newline="\n")
    assert cli.load_live_settings(tmp_claude_home) is None
