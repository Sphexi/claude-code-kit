"""Structural tests for the 13 canonical agent definitions in ``claude/agents/``.

These are read-only assertions about the payload as committed. Nothing here
writes, so the suite is safe to run against a working tree at any point.

Frontmatter is parsed by hand rather than with PyYAML: the shipped tooling is
stdlib-only, and the agent frontmatter
is a fixed, flat set of keys with one optional block scalar. A real YAML parser
would buy nothing and add a dependency.
"""

from __future__ import annotations

from pathlib import Path

import pytest

START = "<!-- TERSENESS:START -->"
END = "<!-- TERSENESS:END -->"

#: The canonical fleet. Exactly these, no more and no fewer.
CANONICAL_AGENTS = {
    "bash-powershell-engineer": "sonnet",
    "docker-engineer": "sonnet",
    "docs-writer": "sonnet",
    "frontend-engineer": "sonnet",
    "integration-test-runner": "sonnet",
    "networking-engineer": "sonnet",
    "project-architect": "opus",
    "python-engineer": "sonnet",
    "rest-api-engineer": "sonnet",
    "rust-engineer": "sonnet",
    "rust-systems-engineer": "sonnet",
    "task-orchestrator": "opus",
    "test-engineer": "sonnet",
}

#: Byte sequences left behind when UTF-8 is decoded as cp1252 or latin-1.
MOJIBAKE_MARKERS = ("Ã", "â€", "ðŸ", "Â ")


def agent_paths(repo_root: Path) -> list[Path]:
    """Every markdown file in the payload's agents directory."""
    return sorted((repo_root / "claude" / "agents").glob("*.md"))


def split_frontmatter(text: str) -> tuple[list[str], str]:
    """Split a payload file into its frontmatter lines and its body.

    Args:
        text: Full file content.

    Returns:
        A ``(frontmatter_lines, body)`` pair. ``frontmatter_lines`` excludes
        both ``---`` fences.

    Raises:
        AssertionError: If the file does not open with a frontmatter fence or
            the fence is never closed.
    """
    lines = text.split("\n")
    assert lines[0] == "---", "file must start with '---' on line 1"
    try:
        closing = lines.index("---", 1)
    except ValueError:  # pragma: no cover - guarded by the assertion below
        raise AssertionError("frontmatter fence is never closed") from None
    return lines[1:closing], "\n".join(lines[closing + 1:])


def top_level_keys(frontmatter: list[str]) -> list[str]:
    """Frontmatter keys at indentation level zero, in file order."""
    return [
        line.split(":", 1)[0]
        for line in frontmatter
        if line and not line.startswith((" ", "\t", "-", "#"))
    ]


def scalar(frontmatter: list[str], key: str) -> str | None:
    """Value of a single-line top-level key, or None if absent."""
    prefix = f"{key}:"
    for line in frontmatter:
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return None


@pytest.fixture()
def agents(repo_root: Path) -> dict[str, str]:
    """Every agent file keyed by filename stem, read as UTF-8."""
    return {p.stem: p.read_text(encoding="utf-8") for p in agent_paths(repo_root)}


# --------------------------------------------------------------------------
# The fleet
# --------------------------------------------------------------------------


def test_exactly_thirteen_agents(agents):
    assert len(agents) == 13


def test_fleet_matches_the_canonical_roster(agents):
    assert set(agents) == set(CANONICAL_AGENTS)


# --------------------------------------------------------------------------
# Frontmatter
# --------------------------------------------------------------------------


@pytest.mark.parametrize("stem", sorted(CANONICAL_AGENTS))
def test_frontmatter_parses(agents, stem):
    frontmatter, body = split_frontmatter(agents[stem])
    assert frontmatter, f"{stem}: empty frontmatter"
    assert body.strip(), f"{stem}: empty body"


@pytest.mark.parametrize("stem", sorted(CANONICAL_AGENTS))
def test_name_matches_filename_stem(agents, stem):
    frontmatter, _ = split_frontmatter(agents[stem])
    assert scalar(frontmatter, "name") == stem


@pytest.mark.parametrize("stem", sorted(CANONICAL_AGENTS))
def test_model_is_pinned_not_inherited(agents, stem):
    frontmatter, _ = split_frontmatter(agents[stem])
    model = scalar(frontmatter, "model")
    assert model in {"opus", "sonnet"}, f"{stem}: model is {model!r}"
    assert model == CANONICAL_AGENTS[stem]


def test_no_agent_uses_inherit(agents):
    offenders = [
        stem
        for stem, text in agents.items()
        if scalar(split_frontmatter(text)[0], "model") == "inherit"
    ]
    assert offenders == []


@pytest.mark.parametrize("stem", sorted(CANONICAL_AGENTS))
def test_frontmatter_key_order(agents, stem):
    frontmatter, _ = split_frontmatter(agents[stem])
    keys = top_level_keys(frontmatter)
    assert keys[:3] == ["name", "description", "model"], f"{stem}: {keys}"
    assert set(keys) <= {"name", "description", "model", "tools"}, f"{stem}: {keys}"
    if "tools" in keys:
        assert keys.index("tools") == 3, f"{stem}: tools must follow model"


@pytest.mark.parametrize("stem", sorted(CANONICAL_AGENTS))
def test_description_is_present_and_substantial(agents, stem):
    frontmatter, _ = split_frontmatter(agents[stem])
    raw = scalar(frontmatter, "description")
    assert raw is not None, f"{stem}: no description"
    if raw == "|":
        block = [line for line in frontmatter if line.startswith("  ")]
        assert block, f"{stem}: block description is empty"
    else:
        assert len(raw) > 40, f"{stem}: description is too short to route on"


# --------------------------------------------------------------------------
# Encoding and whitespace
# --------------------------------------------------------------------------


@pytest.mark.parametrize("stem", sorted(CANONICAL_AGENTS))
def test_no_mojibake(agents, stem):
    text = agents[stem]
    found = [marker for marker in MOJIBAKE_MARKERS if marker in text]
    assert found == [], f"{stem}: mojibake sequences present: {found!r}"


def test_files_are_valid_utf8_without_bom(repo_root):
    for path in agent_paths(repo_root):
        raw = path.read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf"), f"{path.name}: has a UTF-8 BOM"
        raw.decode("utf-8")  # raises UnicodeDecodeError if invalid


def test_files_use_lf_line_endings(repo_root):
    for path in agent_paths(repo_root):
        assert b"\r\n" not in path.read_bytes(), f"{path.name}: has CRLF line endings"


@pytest.mark.parametrize("stem", sorted(CANONICAL_AGENTS))
def test_no_trailing_whitespace(agents, stem):
    offenders = [
        i + 1
        for i, line in enumerate(agents[stem].split("\n"))
        if line != line.rstrip()
    ]
    assert offenders == [], f"{stem}: trailing whitespace on lines {offenders}"


def test_files_end_with_exactly_one_newline(repo_root):
    for path in agent_paths(repo_root):
        raw = path.read_bytes()
        assert raw.endswith(b"\n"), f"{path.name}: no trailing newline"
        assert not raw.endswith(b"\n\n"), f"{path.name}: blank line at end of file"


# --------------------------------------------------------------------------
# Terseness markers
# --------------------------------------------------------------------------


@pytest.mark.parametrize("stem", sorted(CANONICAL_AGENTS))
def test_markers_present_and_balanced(agents, stem):
    text = agents[stem]
    assert text.count(START) == 1, f"{stem}: expected one start marker"
    assert text.count(END) == 1, f"{stem}: expected one end marker"
    assert text.index(START) < text.index(END), f"{stem}: markers are reversed"


@pytest.mark.parametrize("stem", sorted(CANONICAL_AGENTS))
def test_markers_sit_after_the_role_statement(agents, stem):
    _, body = split_frontmatter(agents[stem])
    before = body[: body.index(START)]
    assert "## " not in before, f"{stem}: markers appear after a section heading"
    assert before.strip(), f"{stem}: no role statement before the markers"


@pytest.mark.parametrize("stem", sorted(CANONICAL_AGENTS))
def test_subagent_block_is_inlined(agents, stem):
    text = agents[stem]
    region = text[text.index(START) : text.index(END)]
    assert "shared/terseness-subagent.md" in region, f"{stem}: wrong source block"
    assert "No tool-call narration" in region, f"{stem}: block content missing"


@pytest.mark.parametrize("stem", sorted(CANONICAL_AGENTS))
def test_main_block_is_not_inlined_into_agents(agents, stem):
    text = agents[stem]
    region = text[text.index(START) : text.index(END)]
    assert "shared/terseness-main.md" not in region, f"{stem}: got the main block"


# --------------------------------------------------------------------------
# Payload consistency
# --------------------------------------------------------------------------


def test_no_agent_references_a_merged_away_agent(agents):
    """The two Windows-only agents were merged into other agents and must not be cited."""
    retired = ("docker-orchestration-expert", "powershell-scripting-specialist")
    offenders = {
        stem: name for stem, text in agents.items() for name in retired if name in text
    }
    assert offenders == {}


def test_global_claude_md_has_no_mojibake(repo_root):
    text = (repo_root / "claude" / "global-CLAUDE.md").read_text(encoding="utf-8")
    found = [marker for marker in MOJIBAKE_MARKERS if marker in text]
    assert found == []


def test_global_claude_md_routes_to_docker_engineer(repo_root):
    text = (repo_root / "claude" / "global-CLAUDE.md").read_text(encoding="utf-8")
    assert "docker-orchestration-expert" not in text
    assert "`docker-engineer` custom" in text


def test_global_claude_md_states_the_git_policy(repo_root):
    text = (repo_root / "claude" / "global-CLAUDE.md").read_text(encoding="utf-8")
    assert "## Git Policy" in text
    assert "overridable per project" in text
    assert "`git push` is the one operation never permitted anywhere" in text


def test_global_claude_md_documents_the_output_styles(repo_root):
    text = (repo_root / "claude" / "global-CLAUDE.md").read_text(encoding="utf-8")
    for style in ("Terse (Low)", "Terse (Medium)", "Terse (Full)"):
        assert style in text, f"{style} not documented"
    assert "/output-style" in text


def test_powershell_scripting_skill_is_absent(repo_root):
    """The duplicate skill must not exist anywhere in the payload."""
    skills = repo_root / "claude" / "skills"
    if not skills.exists():
        return
    assert not (skills / "powershell-scripting").exists()
