"""Tests for ``build/inline_shared.py``.

Every test that writes runs against a synthetic repository built in ``tmp_path``
by the ``fake_repo`` fixture, so the real payload under ``claude/`` is never
mutated. The tests that read the real repository do so read-only.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

START = "<!-- TERSENESS:START -->"
END = "<!-- TERSENESS:END -->"
CS_START = "<!-- CODE-STANDARDS:START -->"
CS_END = "<!-- CODE-STANDARDS:END -->"

MAIN_TEXT = "## Main Block\n\nAnswer first, no preamble."
SUBAGENT_TEXT = "## Subagent Block\n\nNo tool-call narration."
STANDARDS_TEXT = "## Comments\n\nA comment says why."


@pytest.fixture()
def inline_shared(repo_root: Path) -> ModuleType:
    """The ``build/inline_shared.py`` module, loaded by path."""
    path = repo_root / "build" / "inline_shared.py"
    spec = importlib.util.spec_from_file_location("inline_shared_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["inline_shared_under_test"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def fake_repo(tmp_path: Path) -> Path:
    """A synthetic repo with every shared source and an empty payload tree."""
    (tmp_path / "shared").mkdir()
    (tmp_path / "shared" / "terseness-main.md").write_text(
        MAIN_TEXT + "\n", encoding="utf-8"
    )
    (tmp_path / "shared" / "terseness-subagent.md").write_text(
        SUBAGENT_TEXT + "\n", encoding="utf-8"
    )
    (tmp_path / "shared" / "code-standards.md").write_text(
        STANDARDS_TEXT + "\n", encoding="utf-8"
    )
    (tmp_path / "claude" / "agents").mkdir(parents=True)
    (tmp_path / "claude" / "output-styles").mkdir(parents=True)
    return tmp_path


def run(module: ModuleType, repo: Path, *extra: str) -> int:
    """Invoke the script's ``main`` against `repo`, returning its exit code."""
    return module.main(["--repo-root", str(repo), *extra])


def marked(body: str) -> str:
    """A minimal target file with an empty terseness region."""
    return f"# Title\n\n{body}\n\n{START}\n{END}\n"


def marked_both(body: str) -> str:
    """A minimal target file carrying both block regions, empty."""
    return f"# Title\n\n{body}\n\n{START}\n{END}\n\n{CS_START}\n{CS_END}\n"


# --------------------------------------------------------------------------
# Marker detection
# --------------------------------------------------------------------------


def test_target_with_markers_is_populated(inline_shared, fake_repo):
    target = fake_repo / "claude" / "output-styles" / "terse-low.md"
    target.write_text(marked("Level rule."), encoding="utf-8")

    assert run(inline_shared, fake_repo) == 0
    assert MAIN_TEXT in target.read_text(encoding="utf-8")


def test_file_without_markers_is_untouched(inline_shared, fake_repo):
    plain = fake_repo / "claude" / "output-styles" / "plain.md"
    original = "# Plain\n\nNo markers anywhere in this file.\n"
    plain.write_text(original, encoding="utf-8")

    assert run(inline_shared, fake_repo) == 0
    assert plain.read_text(encoding="utf-8") == original


def test_no_targets_is_success(inline_shared, fake_repo, capsys):
    assert run(inline_shared, fake_repo) == 0
    assert "no targets found" in capsys.readouterr().out


def test_content_outside_markers_is_preserved(inline_shared, fake_repo):
    target = fake_repo / "claude" / "output-styles" / "terse-full.md"
    target.write_text(
        f"---\nname: X\n---\n\nBefore.\n\n{START}\n{END}\n\nAfter.\n",
        encoding="utf-8",
    )

    assert run(inline_shared, fake_repo) == 0
    text = target.read_text(encoding="utf-8")
    assert text.startswith("---\nname: X\n---\n\nBefore.\n")
    assert text.endswith("\n\nAfter.\n")


def test_stale_region_is_replaced_not_appended(inline_shared, fake_repo):
    target = fake_repo / "claude" / "output-styles" / "terse-medium.md"
    target.write_text(
        f"# T\n\n{START}\nold and wrong content\n{END}\n", encoding="utf-8"
    )

    assert run(inline_shared, fake_repo) == 0
    text = target.read_text(encoding="utf-8")
    assert "old and wrong content" not in text
    assert text.count(START) == 1
    assert text.count(END) == 1


# --------------------------------------------------------------------------
# Block selection by path
# --------------------------------------------------------------------------


def test_agents_get_the_subagent_block(inline_shared, fake_repo):
    agent = fake_repo / "claude" / "agents" / "python-engineer.md"
    agent.write_text(marked("Role."), encoding="utf-8")

    assert run(inline_shared, fake_repo) == 0
    text = agent.read_text(encoding="utf-8")
    assert SUBAGENT_TEXT in text
    assert MAIN_TEXT not in text


def test_non_agents_get_the_main_block(inline_shared, fake_repo):
    style = fake_repo / "claude" / "output-styles" / "terse-low.md"
    style.write_text(marked("Level rule."), encoding="utf-8")

    assert run(inline_shared, fake_repo) == 0
    text = style.read_text(encoding="utf-8")
    assert MAIN_TEXT in text
    assert SUBAGENT_TEXT not in text


def test_generated_notice_names_the_source(inline_shared, fake_repo):
    agent = fake_repo / "claude" / "agents" / "docs-writer.md"
    style = fake_repo / "claude" / "output-styles" / "terse-full.md"
    agent.write_text(marked("Role."), encoding="utf-8")
    style.write_text(marked("Level."), encoding="utf-8")

    assert run(inline_shared, fake_repo) == 0
    assert "shared/terseness-subagent.md" in agent.read_text(encoding="utf-8")
    assert "shared/terseness-main.md" in style.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# The code-standards block
# --------------------------------------------------------------------------


def test_code_standards_block_is_populated(inline_shared, fake_repo):
    target = fake_repo / "claude" / "global-CLAUDE.md"
    target.write_text(f"# G\n\n{CS_START}\n{CS_END}\n", encoding="utf-8")

    assert run(inline_shared, fake_repo) == 0
    text = target.read_text(encoding="utf-8")
    assert STANDARDS_TEXT in text
    assert "shared/code-standards.md" in text


def test_code_standards_block_does_not_vary_by_path(inline_shared, fake_repo):
    agent = fake_repo / "claude" / "agents" / "test-engineer.md"
    style = fake_repo / "claude" / "output-styles" / "terse-low.md"
    for path in (agent, style):
        path.write_text(f"# T\n\n{CS_START}\n{CS_END}\n", encoding="utf-8")

    assert run(inline_shared, fake_repo) == 0
    for path in (agent, style):
        assert STANDARDS_TEXT in path.read_text(encoding="utf-8")


def test_both_blocks_in_one_file_are_both_filled(inline_shared, fake_repo):
    agent = fake_repo / "claude" / "agents" / "python-engineer.md"
    agent.write_text(marked_both("Role."), encoding="utf-8")

    assert run(inline_shared, fake_repo) == 0
    text = agent.read_text(encoding="utf-8")
    assert SUBAGENT_TEXT in text
    assert STANDARDS_TEXT in text
    assert text.index(SUBAGENT_TEXT) < text.index(STANDARDS_TEXT)


def test_one_block_missing_leaves_the_other_alone(inline_shared, fake_repo):
    agent = fake_repo / "claude" / "agents" / "docker-engineer.md"
    agent.write_text(marked("Role."), encoding="utf-8")

    assert run(inline_shared, fake_repo) == 0
    text = agent.read_text(encoding="utf-8")
    assert SUBAGENT_TEXT in text
    assert CS_START not in text


def test_code_standards_staleness_is_detected(inline_shared, fake_repo):
    target = fake_repo / "claude" / "agents" / "docs-writer.md"
    target.write_text(marked_both("Role."), encoding="utf-8")
    run(inline_shared, fake_repo)
    assert run(inline_shared, fake_repo, "--check") == 0

    (fake_repo / "shared" / "code-standards.md").write_text(
        STANDARDS_TEXT + "\n\nAnd a new rule.\n", encoding="utf-8"
    )
    assert run(inline_shared, fake_repo, "--check") == 1


# --------------------------------------------------------------------------
# Idempotency
# --------------------------------------------------------------------------


def test_two_runs_are_byte_identical(inline_shared, fake_repo):
    agent = fake_repo / "claude" / "agents" / "test-engineer.md"
    style = fake_repo / "claude" / "output-styles" / "terse-medium.md"
    agent.write_text(marked_both("Role."), encoding="utf-8")
    style.write_text(marked("Level."), encoding="utf-8")

    assert run(inline_shared, fake_repo) == 0
    first = (agent.read_bytes(), style.read_bytes())

    assert run(inline_shared, fake_repo) == 0
    second = (agent.read_bytes(), style.read_bytes())

    assert first == second


def test_second_run_reports_nothing_to_do(inline_shared, fake_repo, capsys):
    target = fake_repo / "claude" / "output-styles" / "terse-low.md"
    target.write_text(marked("Level."), encoding="utf-8")

    run(inline_shared, fake_repo)
    capsys.readouterr()
    assert run(inline_shared, fake_repo) == 0
    assert "already up to date" in capsys.readouterr().out


def test_output_uses_lf_line_endings(inline_shared, fake_repo):
    target = fake_repo / "claude" / "output-styles" / "terse-low.md"
    target.write_text(marked("Level."), encoding="utf-8")

    run(inline_shared, fake_repo)
    assert b"\r\n" not in target.read_bytes()


def test_crlf_input_is_normalised_and_then_stable(inline_shared, fake_repo):
    target = fake_repo / "claude" / "output-styles" / "terse-low.md"
    target.write_bytes(marked("Level.").replace("\n", "\r\n").encode("utf-8"))

    assert run(inline_shared, fake_repo) == 0
    first = target.read_bytes()
    assert b"\r\n" not in first
    assert run(inline_shared, fake_repo) == 0
    assert target.read_bytes() == first


# --------------------------------------------------------------------------
# --check mode
# --------------------------------------------------------------------------


def test_check_detects_staleness_and_writes_nothing(
    inline_shared, fake_repo, capsys
):
    target = fake_repo / "claude" / "output-styles" / "terse-low.md"
    original = marked("Level.")
    target.write_text(original, encoding="utf-8")

    assert run(inline_shared, fake_repo, "--check") == 1
    assert target.read_text(encoding="utf-8") == original
    assert "terse-low.md" in capsys.readouterr().err


def test_check_passes_when_current(inline_shared, fake_repo, capsys):
    target = fake_repo / "claude" / "output-styles" / "terse-low.md"
    target.write_text(marked("Level."), encoding="utf-8")
    run(inline_shared, fake_repo)
    capsys.readouterr()

    assert run(inline_shared, fake_repo, "--check") == 0
    assert "up to date" in capsys.readouterr().out


def test_check_detects_a_hand_edited_block(inline_shared, fake_repo):
    target = fake_repo / "claude" / "agents" / "docker-engineer.md"
    target.write_text(marked("Role."), encoding="utf-8")
    run(inline_shared, fake_repo)

    text = target.read_text(encoding="utf-8")
    target.write_text(
        text.replace("No tool-call narration.", "Narrate everything."),
        encoding="utf-8",
    )

    assert run(inline_shared, fake_repo, "--check") == 1


def test_check_detects_staleness_after_source_change(inline_shared, fake_repo):
    target = fake_repo / "claude" / "output-styles" / "terse-low.md"
    target.write_text(marked("Level."), encoding="utf-8")
    run(inline_shared, fake_repo)
    assert run(inline_shared, fake_repo, "--check") == 0

    (fake_repo / "shared" / "terseness-main.md").write_text(
        MAIN_TEXT + "\n\nA new rule.\n", encoding="utf-8"
    )
    assert run(inline_shared, fake_repo, "--check") == 1


# --------------------------------------------------------------------------
# Error handling
# --------------------------------------------------------------------------


def test_missing_end_marker_is_a_clear_error(inline_shared, fake_repo, capsys):
    target = fake_repo / "claude" / "output-styles" / "broken.md"
    target.write_text(f"# T\n\n{START}\nno end marker here\n", encoding="utf-8")

    assert run(inline_shared, fake_repo) == 2
    err = capsys.readouterr().err
    assert "broken.md" in err
    assert END in err


def test_missing_code_standards_end_marker_is_an_error(
    inline_shared, fake_repo, capsys
):
    target = fake_repo / "claude" / "agents" / "broken.md"
    target.write_text(f"# T\n\n{CS_START}\nno end marker\n", encoding="utf-8")

    assert run(inline_shared, fake_repo) == 2
    assert CS_END in capsys.readouterr().err


def test_missing_end_marker_writes_nothing(inline_shared, fake_repo):
    good = fake_repo / "claude" / "output-styles" / "aaa-good.md"
    broken = fake_repo / "claude" / "output-styles" / "zzz-broken.md"
    good.write_text(marked("Level."), encoding="utf-8")
    broken.write_text(f"# T\n\n{START}\n", encoding="utf-8")

    assert run(inline_shared, fake_repo) == 2
    # The good file sorts first and is written before the broken one is
    # reached; what must hold is that the broken file is never mangled.
    assert broken.read_text(encoding="utf-8") == f"# T\n\n{START}\n"


def test_end_before_start_is_an_error(inline_shared, fake_repo, capsys):
    target = fake_repo / "claude" / "output-styles" / "reversed.md"
    target.write_text(f"# T\n\n{END}\nbody\n{START}\n", encoding="utf-8")

    assert run(inline_shared, fake_repo) == 2
    assert "reversed.md" in capsys.readouterr().err


def test_duplicate_marker_pair_is_an_error(inline_shared, fake_repo, capsys):
    target = fake_repo / "claude" / "output-styles" / "double.md"
    target.write_text(
        f"# T\n\n{START}\n{END}\n\nmiddle\n\n{START}\n{END}\n", encoding="utf-8"
    )

    assert run(inline_shared, fake_repo) == 2
    assert "exactly one TERSENESS block" in capsys.readouterr().err


def test_missing_shared_source_is_an_error(inline_shared, fake_repo, capsys):
    (fake_repo / "shared" / "terseness-subagent.md").unlink()

    assert run(inline_shared, fake_repo) == 2
    assert "missing shared source" in capsys.readouterr().err


def test_missing_code_standards_source_is_an_error(
    inline_shared, fake_repo, capsys
):
    (fake_repo / "shared" / "code-standards.md").unlink()

    assert run(inline_shared, fake_repo) == 2
    assert "code-standards.md" in capsys.readouterr().err


def test_empty_shared_source_is_an_error(inline_shared, fake_repo, capsys):
    (fake_repo / "shared" / "terseness-main.md").write_text("\n", encoding="utf-8")

    assert run(inline_shared, fake_repo) == 2
    assert "empty" in capsys.readouterr().err


def test_source_containing_markers_is_an_error(inline_shared, fake_repo, capsys):
    (fake_repo / "shared" / "terseness-main.md").write_text(
        f"{START}\nrecursive\n{END}\n", encoding="utf-8"
    )

    assert run(inline_shared, fake_repo) == 2
    assert "must not contain markers" in capsys.readouterr().err


def test_source_containing_another_blocks_markers_is_an_error(
    inline_shared, fake_repo, capsys
):
    (fake_repo / "shared" / "terseness-main.md").write_text(
        f"{CS_START}\nnested\n{CS_END}\n", encoding="utf-8"
    )

    assert run(inline_shared, fake_repo) == 2
    assert "must not contain markers" in capsys.readouterr().err


def test_nonexistent_root_is_an_error(inline_shared, fake_repo, capsys):
    assert run(inline_shared, fake_repo, "--root", "nope") == 2
    assert "root does not exist" in capsys.readouterr().err


# --------------------------------------------------------------------------
# The real repository
# --------------------------------------------------------------------------


def test_real_payload_is_up_to_date(inline_shared, repo_root, capsys):
    """`--check` must be clean against the committed payload."""
    exit_code = inline_shared.main(["--repo-root", str(repo_root), "--check"])
    captured = capsys.readouterr()
    assert exit_code == 0, captured.err


def test_real_shared_blocks_are_materially_different(repo_root):
    main = (repo_root / "shared" / "terseness-main.md").read_text(encoding="utf-8")
    subagent = (repo_root / "shared" / "terseness-subagent.md").read_text(
        encoding="utf-8"
    )

    assert main != subagent
    assert "yes/no" in main.lower()
    assert "tool-call narration" in subagent.lower()
    assert "tool-call narration" not in main.lower()


def test_every_agent_carries_the_code_standards_block(repo_root):
    agents = sorted((repo_root / "claude" / "agents").glob("*.md"))
    assert len(agents) == 13

    for agent in agents:
        text = agent.read_text(encoding="utf-8")
        assert text.count(CS_START) == 1, agent
        assert text.count(CS_END) == 1, agent


def test_global_claude_md_carries_the_code_standards_block(repo_root):
    text = (repo_root / "claude" / "global-CLAUDE.md").read_text(encoding="utf-8")
    assert CS_START in text
    assert "applies in every project" in text


def test_real_code_standards_source_covers_both_topics(repo_root):
    text = (repo_root / "shared" / "code-standards.md").read_text(encoding="utf-8")
    assert "## Comments" in text
    assert "## Tests" in text
    assert "Never appears in a comment" in text


def test_real_output_styles_have_valid_frontmatter(repo_root):
    styles = sorted((repo_root / "claude" / "output-styles").glob("terse-*.md"))
    assert {p.stem for p in styles} == {"terse-low", "terse-medium", "terse-full"}

    for style in styles:
        text = style.read_text(encoding="utf-8")
        assert text.startswith("---\n"), style
        _, frontmatter, _ = text.split("---\n", 2)
        keys = [
            line.split(":", 1)[0]
            for line in frontmatter.splitlines()
            if line and not line.startswith((" ", "-"))
        ]
        assert keys[:3] == ["name", "description", "keep-coding-instructions"], style
        assert "keep-coding-instructions: true" in frontmatter, style
