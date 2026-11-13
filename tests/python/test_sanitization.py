"""The repository's text carries no owner, machine or build-history references."""

from __future__ import annotations

import fnmatch
import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PRUNED_DIRS = {".git", ".venv", "dist", "__pycache__", ".pytest_cache", ".design", "node_modules",
               "plugins"}
SELF = "tests/python/test_sanitization.py"

ATTRIBUTION = ["**/UPSTREAM.md", "THIRD_PARTY_NOTICES.md", "README.md", "CHANGELOG.md",
               "CLAUDE.md", "docs/*.md", "build/templates/*", "tools/vendor_sync.py",
               "claude/skills/systematic-debugging/SKILL.md", "claude/agents/project-architect.md",
               "claude/agents/frontend-engineer.md",
               "tests/python/test_vendor_sync.py", "tests/python/test_plugin_manifest.py",
               "claude/plugins.manifest.json", "build/build_plugins.py"]
GENERATED_FOR_OTHERS = ["claude/agents/project-architect.md", "claude/agents/task-orchestrator.md",
                        "claude/agents/docs-writer.md", "claude/global-CLAUDE.md",
                        "claude/skills/code-comments/SKILL.md",
                        "claude/skills/systematic-debugging/SKILL.md"]

#: ``(id, regex, flags, allowed path globs)``; a file matching an allowed glob is not scanned.
PATTERNS: list[tuple[str, str, int, list[str]]] = [
    ("owner-name", r"\bBen\b", 0, []),
    ("personal-paths", r"/home/|C:\\Users\\|D:\\", re.I, []),
    ("old-names", r"claude-code-env|sphexi-env", re.I, []),
    ("capital-sphexi", r"Sphexi", 0, []),
    ("claude-security", r"claude-security", re.I, []),
    ("build-history", r"Session [0-9]+|Phase [0-9]|Decision [0-9]+|Open Question|Key Design Rule"
                      r"|TECHNICAL_PLAN|SESSIONS\.md|docs/sessions|docs/archive",
     0, GENERATED_FOR_OTHERS),
    ("usage-tooling", r"usage_probe|usage_merge|usage-report|exports/|recorded_usage", re.I, []),
    ("old-entry-points", r"install\.sh|install\.ps1|profiles/|scripts/0[1-9]|scripts/1[0-3]"
                         r"|99-deploy|deploy/deploy", re.I, [".github/workflows/ci.yml"]),
    ("machine-descriptions", r"Windows desktop|remote-dev|primary machine|daily use|daily work"
                             r"|w11-work|windows-primary|Windows 11", re.I, []),
    ("ghcr", r"GHCR", re.I, []),
    ("superpowers", r"superpowers", re.I,
     ["claude/skills/systematic-debugging/SKILL.md", "THIRD_PARTY_NOTICES.md",
      "build/build_plugins.py"]),
    ("caveman", r"caveman", re.I, []),
    ("twingate", r"Twingate", re.I,
     ["build/kit.json", ".claude-plugin/marketplace.json", "claude/global-CLAUDE.md",
      "docs/plugins.md", "THIRD_PARTY_NOTICES.md", "CLAUDE.md", "README.md",
      "docs/install-marketplace.md", "tests/python/test_routing_table.py"]),
    ("pinned-models", r"claude-opus-[0-9]|\[1m\]|SECURITY_REVIEW_MODEL|SG_AGENTIC_MODEL", re.I,
     ["docs/settings.md"]),
    ("email", r"[\w.+-]+@[\w-]+\.[\w.-]*[A-Za-z]", 0, []),
    ("attribution-names", r"Seth Hobson|Anthropic|Prime Radiant|Jesse Vincent", 0, ATTRIBUTION),
    ("dates-in-prose", r"^20[0-9]{2}-[01][0-9]-[0-3][0-9]", re.M, ["CHANGELOG.md", "**/UPSTREAM.md"]),
]


def tracked_text_files() -> dict[str, str]:
    """Every text file outside generated and vendored content, keyed by POSIX path."""
    files: dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(ROOT):
        rel_dir = Path(dirpath).relative_to(ROOT).as_posix()
        dirnames[:] = sorted(d for d in dirnames if d not in PRUNED_DIRS)
        in_vendor = rel_dir == "claude/vendor" or rel_dir.startswith("claude/vendor/")
        for name in sorted(filenames):
            rel = f"{rel_dir}/{name}" if rel_dir != "." else name
            if rel == SELF or rel == "OLD-CLAUDE.md":
                continue
            if in_vendor and name != "UPSTREAM.md":
                continue
            try:
                files[rel] = (ROOT / rel).read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
    return files


@pytest.fixture(scope="module")
def corpus() -> dict[str, str]:
    return tracked_text_files()


def allowed(rel: str, globs: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(rel, glob) or rel == glob for glob in globs)


@pytest.mark.parametrize(("pattern_id", "regex", "flags", "allow"), PATTERNS,
                         ids=[p[0] for p in PATTERNS])
def test_pattern_is_absent_outside_its_allowlist(
    corpus: dict[str, str], pattern_id: str, regex: str, flags: int, allow: list[str]
) -> None:
    compiled = re.compile(regex, flags)
    offenders = []
    for rel, text in corpus.items():
        if allowed(rel, allow):
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            match = compiled.search(line)
            if match:
                offenders.append(f"{rel}:{number}: {match.group(0)!r}")
    assert not offenders, f"{pattern_id}:\n  " + "\n  ".join(offenders[:25])
