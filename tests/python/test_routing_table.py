"""Every agent, command and plugin named in a routing table exists in this repository."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ROUTED_FILES = ["claude/global-CLAUDE.md", "claude/agents/task-orchestrator.md",
                "claude/agents/project-architect.md"]
ROUTING_KINDS = {"agent", "task", "command"}
TOKEN = re.compile(r"`([^`]+)`")
OUTSIDE_THE_KIT = {"twingate-assistant", "security-guidance", "pyright-lsp"}


def marketplace_plugins() -> set[str]:
    data = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    return {entry["name"] for entry in data["plugins"]}


def custom_agents() -> set[str]:
    return {p.stem for p in (ROOT / "claude" / "agents").glob("*.md")}


def table_rows(rel: str) -> list[tuple[int, str, list[str]]]:
    """Return ``(line number, header kind, cells)`` for every table body row in a file."""
    rows = []
    kind = ""
    for number, line in enumerate((ROOT / rel).read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped.startswith("|"):
            kind = ""
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if not kind:
            kind = cells[0].lower()
            continue
        if set("".join(cells)) <= set("-: ") or kind not in ROUTING_KINDS:
            continue
        rows.append((number, kind, cells))
    return rows


def resolves(plugin: str, token: str) -> bool:
    base = ROOT / "plugins" / plugin
    return (base / "agents" / f"{token}.md").is_file() or (base / "skills" / token).is_dir()


def problems_in(rel: str) -> list[str]:
    plugins = marketplace_plugins()
    custom = custom_agents()
    problems = []
    for number, kind, cells in table_rows(rel):
        where = f"{rel}:{number}"
        if kind == "agent":
            problems += [f"{where}: custom agent {t!r} missing" for t in TOKEN.findall(cells[0])
                         if t not in custom]
            continue
        if kind == "command":
            targets = TOKEN.findall(cells[0])
        elif len(cells) >= 2:
            targets = TOKEN.findall(cells[1])
        else:
            continue
        row_plugins = [t for t in targets if t in plugins | OUTSIDE_THE_KIT]
        for token in targets:
            if token in row_plugins:
                continue
            if token.startswith("/"):
                plugin, _, command = token[1:].partition(":")
                if not (ROOT / "plugins" / plugin / "commands" / f"{command}.md").is_file():
                    problems.append(f"{where}: command {token} does not exist")
            elif token == "custom":
                continue
            elif "custom" in cells[1:] or cells[1].endswith("custom"):
                if token not in custom:
                    problems.append(f"{where}: custom agent {token!r} missing")
            elif token not in custom and not any(resolves(p, token) for p in row_plugins
                                                 if p in plugins):
                problems.append(f"{where}: {token!r} not found in {row_plugins}")
        problems += [f"{where}: plugin {p!r} is not a marketplace entry"
                     for p in re.findall(r"`(sphexi-[a-z]+)`", cells[1] if len(cells) > 1 else "")
                     if p not in plugins]
    return problems


@pytest.mark.parametrize("rel", ROUTED_FILES)
def test_routing_rows_name_only_things_that_exist(rel: str) -> None:
    assert problems_in(rel) == []


def test_the_parser_reads_the_rows_it_is_meant_to_check() -> None:
    rows = table_rows("claude/global-CLAUDE.md")
    kinds = {kind for _, kind, _ in rows}
    assert {"agent", "task", "command"} <= kinds
    assert sum(1 for _, kind, _ in rows if kind == "agent") == 13
    assert len(table_rows("claude/agents/task-orchestrator.md")) > 40
