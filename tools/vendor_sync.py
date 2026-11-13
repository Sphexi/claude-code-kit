"""Rebuild ``claude/vendor/`` from upstream marketplace clones and render its provenance files.

Every divergence from upstream is declared in :data:`MODIFICATIONS`. A re-sync
re-applies them deterministically and fails if upstream changed the text a
modification targets.

Usage::

    python tools/vendor_sync.py                      # dry run: report, change nothing
    python tools/vendor_sync.py --apply              # rebuild claude/vendor/
    python tools/vendor_sync.py --apply --only pr-review-toolkit
    python tools/vendor_sync.py --apply --marketplaces /path/to/clones
    python tools/vendor_sync.py --render-upstream    # rewrite UPSTREAM.md, licenses, notices, manifest

``--apply`` needs one clone per source key under ``~/.claude/plugins/marketplaces/``
(or ``--marketplaces DIR``) and never touches the network. ``--render-upstream``
needs no clones: it works from the vendored content and the pins already recorded.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VENDOR = REPO_ROOT / "claude" / "vendor"
MANIFEST = REPO_ROOT / "claude" / "plugins.manifest.json"
MARKETPLACES = Path.home() / ".claude" / "plugins" / "marketplaces"

sys.path.insert(0, str(REPO_ROOT / "build"))
from bundles import bundle_of  # noqa: E402

MANIFEST_SCHEMA = "plugins-manifest.v3"

#: Names never carried into ``claude/vendor/``, at any depth.
NOISE_DIRS = {".in_use", "__pycache__", "tests", "test", ".github", ".git",
              "node_modules", ".pytest_cache", ".ruff_cache", ".codex-plugin"}
NOISE_FILES = {".orphaned_at", ".DS_Store", "Thumbs.db", ".gcs-sha"}
NOISE_SUFFIXES = {".pyc", ".pyo"}

MIT_TEXT = """MIT License

Copyright (c) {year} {holder}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

MODIFIED_NOTICE = "<!-- Modified from the upstream version; changes are listed in UPSTREAM.md. -->"


# --------------------------------------------------------------------------- #
# upstream sources
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Source:
    """An upstream marketplace the vendored plugins are copied from.

    ``fallback_license`` is the text written into a plugin that ships no
    ``LICENSE`` when the clone's root ``LICENSE`` is not available.
    """

    key: str
    repo: str
    author: str
    commit_note: str
    fallback_license: str | None = None

    @property
    def root(self) -> Path:
        """Local clone of this marketplace."""
        return MARKETPLACES / self.key

    def commit(self) -> str:
        """Return the 40-character revision the local clone sits at, read as data."""
        head = self.root / ".git" / "refs" / "heads" / "main"
        if head.is_file():
            return head.read_text(encoding="utf-8").strip()
        packed = self.root / ".git" / "packed-refs"
        if packed.is_file():
            for line in packed.read_text(encoding="utf-8").splitlines():
                sha, _, ref = line.partition(" ")
                if ref == "refs/heads/main":
                    return sha
        gcs = self.root / ".gcs-sha"
        if gcs.is_file():
            return gcs.read_text(encoding="utf-8").strip()
        sys.exit(f"cannot determine a revision for marketplace {self.key!r} at {self.root}")

    def license_text(self) -> str | None:
        """Return the repository's root license text, from the clone or the fallback."""
        path = self.root / "LICENSE"
        if path.is_file():
            return path.read_text(encoding="utf-8").replace("\r\n", "\n")
        return self.fallback_license


SOURCES: dict[str, Source] = {
    "claude-code-workflows": Source(
        key="claude-code-workflows",
        repo="https://github.com/wshobson/agents",
        author="Seth Hobson",
        commit_note="git commit SHA (`.git/refs/heads/main` of the local marketplace clone)",
        fallback_license=MIT_TEXT.format(year=2024, holder="Seth Hobson"),
    ),
    "claude-plugins-official": Source(
        key="claude-plugins-official",
        repo="https://github.com/anthropics/claude-plugins-official",
        author="Anthropic",
        commit_note="content SHA (`.gcs-sha`; this marketplace is distributed as a GCS "
                    "snapshot, not a git clone)",
    ),
}

WSHOBSON = [
    "python-development", "backend-development", "cloud-infrastructure", "security-scanning",
    "comprehensive-review", "full-stack-orchestration", "code-documentation", "debugging-toolkit",
    "git-pr-workflows", "unit-testing", "performance-testing-review", "code-refactoring",
    "database-design", "database-migrations", "cicd-automation", "security-compliance",
    "backend-api-security", "frontend-mobile-security", "api-scaffolding", "accessibility-compliance",
    "tdd-workflows", "dependency-management", "shell-scripting", "systems-programming",
    "developer-essentials", "llm-application-dev",
]

OFFICIAL = ["pr-review-toolkit", "skill-creator", "security-guidance", "pyright-lsp",
            "feature-dev"]

#: Every vendored plugin, as (name, marketplace key).
PLUGINS: list[tuple[str, str]] = (
    [(n, "claude-code-workflows") for n in WSHOBSON]
    + [(n, "claude-plugins-official") for n in OFFICIAL]
)


# --------------------------------------------------------------------------- #
# declared modifications
# --------------------------------------------------------------------------- #

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)

#: Characters that would turn a plain YAML scalar into something else.
_UNSAFE_SCALAR = (": ", " #", "\n")


def frontmatter_field(text: str, key: str) -> str | None:
    """Return a top-level frontmatter value, or ``None`` when the key is absent."""
    match = FRONTMATTER.match(text)
    if match is None:
        return None
    for line in match.group(1).split("\n"):
        if line.startswith(f"{key}:"):
            return line[len(key) + 1:].strip()
    return None


def replace_field(text: str, key: str, value: str) -> str | None:
    """Replace a frontmatter field and any block-scalar continuation; ``None`` if absent."""
    match = FRONTMATTER.match(text)
    if match is None:
        return None
    lines = match.group(1).split("\n")
    for i, line in enumerate(lines):
        if line.startswith(f"{key}:"):
            end = i + 1
            while end < len(lines) and (lines[end].startswith((" ", "\t")) or not lines[end]):
                end += 1
            lines[i:end] = [f"{key}: {value}"]
            return text[:match.start(1)] + "\n".join(lines) + text[match.end(1):]
    return None


def _bare_reference(stem: str) -> re.Pattern[str]:
    """Match ``stem`` as a standalone identifier — not prefixed, suffixed, or a filename."""
    return re.compile(rf"(?<![\w-]){re.escape(stem)}(?![\w-]|\.md)")


def text_files(root: Path) -> list[Path]:
    """Every UTF-8 text file in a vendored plugin, excluding ``UPSTREAM.md``."""
    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "UPSTREAM.md":
            continue
        try:
            path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        files.append(path)
    return files


@dataclass
class Modification:
    """One declared divergence from upstream; exactly one action field is set.

    ``reason`` is reproduced verbatim in the plugin's ``UPSTREAM.md``.
    """

    reason: str
    set_field: tuple[str, str, str] | None = None
    rename_agent: tuple[str, str] | None = None
    insert_note: tuple[str, str] | None = None
    drop_file: str | None = None
    replace: tuple[str, str, str] | None = None
    replace_line: tuple[str, str, str] | None = None
    write_file: tuple[str, str] | None = None

    def apply(self, root: Path) -> str:
        """Apply this modification to a freshly copied plugin and describe what changed.

        Exits rather than skipping when the target has moved upstream.
        """
        if self.set_field is not None:
            return self._set_field(root, *self.set_field)
        if self.rename_agent is not None:
            return self._rename_agent(root, *self.rename_agent)
        if self.insert_note is not None:
            return self._insert_note(root, *self.insert_note)

        if self.drop_file is not None:
            path = root / self.drop_file
            if not path.is_file():
                return f"already absent: {self.drop_file}"
            path.unlink()
            return f"dropped {self.drop_file}"

        if self.replace is not None:
            rel, old, new = self.replace
            path = root / rel
            if not path.is_file():
                sys.exit(f"{root.name}: cannot patch {rel} — file does not exist")
            text = path.read_text(encoding="utf-8")
            if new in text:
                return f"already patched: {rel}"
            if old not in text:
                sys.exit(f"{root.name}: text to replace not found in {rel}; "
                         f"upstream changed, revisit this modification")
            write(path, text.replace(old, new, 1))
            return f"patched {rel}"

        if self.replace_line is not None:
            rel, prefix, new = self.replace_line
            path = root / rel
            if not path.is_file():
                sys.exit(f"{root.name}: cannot patch {rel} — file does not exist")
            lines = path.read_text(encoding="utf-8").split("\n")
            matches = [i for i, line in enumerate(lines) if line.startswith(prefix)]
            if not matches:
                if any(line.startswith(new.split("\n")[0]) for line in lines):
                    return f"already patched: {rel}"
                sys.exit(f"{root.name}: no line starting {prefix!r} in {rel}; "
                         f"upstream changed, revisit this modification")
            if len(matches) > 1:
                sys.exit(f"{root.name}: {len(matches)} lines start {prefix!r} in {rel}; "
                         f"the modification is ambiguous")
            lines[matches[0]] = new
            write(path, "\n".join(lines))
            return f"patched {rel} (line)"

        if self.write_file is not None:
            rel, content = self.write_file
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            write(path, content)
            return f"wrote {rel}"

        sys.exit(f"{root.name}: modification declares no action: {self.reason}")

    @staticmethod
    def _set_field(root: Path, agent: str, key: str, value: str) -> str:
        """Set one frontmatter field of an agent, failing if upstream no longer declares it."""
        if any(token in value for token in _UNSAFE_SCALAR) or value[:1] in "'\"|>[{&*!%@`":
            sys.exit(f"{root.name}: {agent}.{key} value is not a safe plain YAML scalar")
        path = root / "agents" / f"{agent}.md"
        if not path.is_file():
            sys.exit(f"{root.name}: cannot set {key} on {agent} — {path} does not exist")
        text = path.read_text(encoding="utf-8")
        current = frontmatter_field(text, key)
        if current is None:
            sys.exit(f"{root.name}: {agent} no longer declares {key!r}; "
                     f"upstream changed, revisit this modification")
        if current == value:
            return f"already set: {agent}.{key}"
        updated = replace_field(text, key, value)
        assert updated is not None
        write(path, updated)
        shown = current if len(current) <= 20 else current[:17] + "..."
        return f"{agent}.{key}: {shown} -> {value if len(value) <= 20 else '(rewritten)'}"

    @staticmethod
    def _rename_agent(root: Path, stem: str, new_name: str) -> str:
        """Rename an agent's declared name and every bare reference to it inside the plugin."""
        path = root / "agents" / f"{stem}.md"
        if not path.is_file():
            sys.exit(f"{root.name}: cannot rename {stem} — {path} does not exist")
        text = path.read_text(encoding="utf-8")
        current = frontmatter_field(text, "name")
        if current not in (stem, new_name):
            sys.exit(f"{root.name}: {stem} declares name {current!r}, expected {stem!r}; "
                     f"upstream changed, revisit this modification")
        if current == stem:
            updated = replace_field(text, "name", new_name)
            assert updated is not None
            write(path, updated)
        pattern = _bare_reference(stem)
        refs = 0
        for file in text_files(root):
            body = file.read_text(encoding="utf-8")
            new_body, n = pattern.subn(new_name, body)
            if n:
                write(file, new_body)
                refs += n
        return f"renamed {stem} -> {new_name} ({refs} reference(s))"

    @staticmethod
    def _insert_note(root: Path, rel: str, note: str) -> str:
        """Insert a note directly after a file's frontmatter, or at the top if it has none."""
        path = root / rel
        if not path.is_file():
            sys.exit(f"{root.name}: cannot annotate {rel} — file does not exist")
        text = path.read_text(encoding="utf-8")
        if note in text:
            return f"already annotated: {rel}"
        match = FRONTMATTER.match(text)
        cut = match.end() if match else 0
        lead = "\n" if cut else ""
        write(path, f"{text[:cut]}{lead}{note}\n\n{text[cut:].lstrip(chr(10))}")
        return f"annotated {rel}"


# --------------------------------------------------------------------------- #
# selection: which upstream components are kept
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Selection:
    """Components of a plugin to keep; ``None`` keeps every component of that kind."""

    agents: tuple[str, ...] | None = None
    skills: tuple[str, ...] | None = None
    commands: tuple[str, ...] | None = None


#: Per-plugin keep-lists. A plugin absent here is vendored whole.
SELECTION: dict[str, Selection] = {
    "systems-programming": Selection(agents=("golang-pro",), commands=()),
    "developer-essentials": Selection(
        agents=(),
        skills=("auth-implementation-patterns", "code-review-excellence",
                "debugging-strategies", "e2e-testing-patterns", "error-handling-patterns",
                "git-advanced-workflows", "sql-optimization-patterns"),
    ),
}


def apply_selection(root: Path, selection: Selection) -> list[str]:
    """Remove every component not on the plugin's keep-lists and return what was removed."""
    removed: list[str] = []
    for kind in ("agents", "commands", "skills"):
        keep = getattr(selection, kind)
        if keep is None:
            continue
        folder = root / kind
        if kind == "skills":
            present = {p.name: p for p in folder.iterdir() if p.is_dir()} if folder.is_dir() else {}
        else:
            present = {p.stem: p for p in folder.glob("*.md")} if folder.is_dir() else {}
        missing = sorted(set(keep) - set(present))
        if missing:
            sys.exit(f"{root.name}: selected {kind} not present upstream: {missing}; "
                     f"revisit SELECTION")
        for name, path in sorted(present.items()):
            if name in keep:
                continue
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            removed.append(f"{kind}/{name}")
    return removed


# --------------------------------------------------------------------------- #
# duplicate collapse: one canonical copy per identical agent
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Collapse:
    """An agent kept in ``owner`` and dropped from plugins carrying an identical copy."""

    owner: str
    duplicates: tuple[str, ...]


#: The sync verifies each copy is identical to the owner's apart from the ``name:``
#: line before dropping it, and fails on a diverged copy.
COLLAPSE: dict[str, Collapse] = {
    "backend-architect": Collapse("backend-development", ("api-scaffolding", "backend-api-security")),
    "cloud-architect": Collapse("cloud-infrastructure", ("cicd-automation",)),
    "code-reviewer": Collapse("comprehensive-review", ("code-documentation", "code-refactoring",
                                                       "git-pr-workflows", "tdd-workflows")),
    "debugger": Collapse("debugging-toolkit", ("unit-testing",)),
    "deployment-engineer": Collapse("cloud-infrastructure", ("cicd-automation",
                                                             "full-stack-orchestration")),
    "django-pro": Collapse("python-development", ("api-scaffolding",)),
    "fastapi-pro": Collapse("python-development", ("api-scaffolding",)),
    "graphql-architect": Collapse("backend-development", ("api-scaffolding",)),
    "kubernetes-architect": Collapse("cloud-infrastructure", ("cicd-automation",)),
    "legacy-modernizer": Collapse("code-refactoring", ("dependency-management",)),
    "performance-engineer": Collapse("performance-testing-review", ("full-stack-orchestration",)),
    "security-auditor": Collapse("security-scanning", ("comprehensive-review", "security-compliance",
                                                       "full-stack-orchestration")),
    "tdd-orchestrator": Collapse("tdd-workflows", ("backend-development",)),
    "terraform-specialist": Collapse("cloud-infrastructure", ("cicd-automation",)),
    "test-automator": Collapse("unit-testing", ("full-stack-orchestration",
                                                "performance-testing-review")),
}


#: Rewritten in every file whose references were retargeted, because the claim is
#: false once an agent lives in another plugin.
LOCAL_AGENTS_CLAIM = (
    "**Use only local agents.** All `subagent_type` references use agents bundled with this "
    "plugin or `general-purpose`. No cross-plugin dependencies."
)
LOCAL_AGENTS_REWRITE = (
    "**Use only the named agents.** Every `subagent_type` reference names an agent bundled with "
    "this plugin, `general-purpose`, or a canonical agent from another vendored plugin that is "
    "always deployed alongside it (see this plugin's `UPSTREAM.md`). Do not substitute others."
)


def _without_name(text: str) -> str:
    """Return agent text with its ``name:`` line blanked, for identity comparison."""
    return re.sub(r"^name:.*$", "", text, count=1, flags=re.M)


def collapse_duplicates(name: str, root: Path) -> list[str]:
    """Drop this plugin's duplicate agents and retarget references to the canonical names."""
    notes: list[str] = []
    market = dict(PLUGINS)
    for stem, rule in sorted(COLLAPSE.items()):
        if name not in rule.duplicates:
            continue
        path = root / "agents" / f"{stem}.md"
        if not path.is_file():
            sys.exit(f"{name}: COLLAPSE expects agents/{stem}.md, which upstream no longer ships")
        canonical_path = SOURCES[market[rule.owner]].root / "plugins" / rule.owner / "agents" / f"{stem}.md"
        if not canonical_path.is_file():
            sys.exit(f"{name}: canonical {rule.owner}/agents/{stem}.md is missing upstream")
        duplicate = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        canonical = canonical_path.read_text(encoding="utf-8").replace("\r\n", "\n")
        if _without_name(duplicate) != _without_name(canonical):
            sys.exit(f"{name}: agents/{stem}.md has diverged from the {rule.owner} copy; "
                     f"it is no longer a duplicate — revisit COLLAPSE")
        dropped = frontmatter_field(duplicate, "name")
        target = frontmatter_field(canonical, "name")
        if not dropped or not target or dropped == stem:
            sys.exit(f"{name}: agents/{stem}.md declares no plugin-prefixed name; references "
                     f"to it cannot be retargeted safely")
        path.unlink()
        refs = 0
        for file in text_files(root):
            body = file.read_text(encoding="utf-8")
            if dropped in body:
                refs += body.count(dropped)
                body = body.replace(dropped, target).replace(LOCAL_AGENTS_CLAIM,
                                                             LOCAL_AGENTS_REWRITE)
                write(file, body)
        notes.append(f"`agents/{stem}.md` — identical to `{rule.owner}`'s copy apart from its "
                     f"`name:` line; dropped, and {refs} reference(s) to `{dropped}` retargeted "
                     f"to `{target}`. Where a retargeted command told the model to use only "
                     f"local agents, that instruction now names the canonical agent as allowed.")
    return notes


# --------------------------------------------------------------------------- #
# model tiers
# --------------------------------------------------------------------------- #

#: Explicit model per agent wherever the kit differs from upstream. Every upstream
#: ``inherit`` needs an entry.
TIERS: dict[str, dict[str, str]] = {
    "backend-api-security": {"backend-security-coder": "opus"},
    "backend-development": {"backend-architect": "opus", "event-sourcing-architect": "opus",
                            "temporal-python-pro": "sonnet"},
    "database-design": {"sql-pro": "sonnet"},
    "database-migrations": {"database-optimizer": "sonnet"},
    "feature-dev": {"code-architect": "opus", "code-reviewer": "opus"},
    "frontend-mobile-security": {"frontend-developer": "sonnet", "frontend-security-coder": "opus"},
    "llm-application-dev": {"ai-engineer": "sonnet", "prompt-engineer": "sonnet",
                            "vector-database-engineer": "sonnet"},
    "performance-testing-review": {"performance-engineer": "sonnet"},
    "pr-review-toolkit": {"code-simplifier": "sonnet", "comment-analyzer": "sonnet",
                          "pr-test-analyzer": "sonnet", "silent-failure-hunter": "opus",
                          "type-design-analyzer": "opus"},
    "python-development": {"django-pro": "sonnet", "fastapi-pro": "sonnet", "python-pro": "sonnet"},
    "systems-programming": {"golang-pro": "sonnet"},
}

#: Plugins whose agents keep ``model: inherit``.
INHERIT_ALLOWED: frozenset[str] = frozenset()

_TIER_REASON = (
    "model set to `{model}` per the tier table in `tools/vendor_sync.py` — judgement-heavy "
    "review, security and architecture on `opus`, implementers and routine analysis on "
    "`sonnet`. Upstream's value is overridden; nothing else in the file changed."
)


def check_tiers(name: str, root: Path) -> None:
    """Fail when an agent has no model line or keeps ``inherit`` outside the allow-list."""
    for path in sorted((root / "agents").glob("*.md")):
        model = frontmatter_field(path.read_text(encoding="utf-8"), "model")
        if not model:
            sys.exit(f"{name}: agents/{path.name} declares no model; add it to TIERS")
        if model == "inherit" and name not in INHERIT_ALLOWED:
            sys.exit(f"{name}: agents/{path.name} still declares model: inherit; add it to TIERS")


# --------------------------------------------------------------------------- #
# modification table
# --------------------------------------------------------------------------- #

_CODE_SIMPLIFIER_OLD = """2. **Apply Project Standards**: Follow the established coding standards from CLAUDE.md including:

   - Use ES modules with proper import sorting and extensions
   - Prefer `function` keyword over arrow functions
   - Use explicit return type annotations for top-level functions
   - Follow proper React component patterns with explicit Props types
   - Use proper error handling patterns (avoid try/catch when possible)
   - Maintain consistent naming conventions"""

_CODE_SIMPLIFIER_NEW = """2. **Apply Project Standards**: The project's `CLAUDE.md` is the only authority on style. Read it
   before changing anything, and apply what it actually says:

   - Follow its stated language versions, formatting rules, and linting requirements
   - Follow its naming conventions; where it is silent, match the surrounding file
   - Follow its error-handling conventions rather than importing a preference from elsewhere
   - Follow its type-annotation and docstring requirements
   - Where `CLAUDE.md` is silent, prefer consistency with the existing code over any external
     house style. Never introduce a convention the project does not already use.

   You have no house style of your own. A simplification that makes code less like the rest of
   the codebase is not a simplification."""

_PYRIGHT_PLUGIN_JSON = """{
  "name": "pyright-lsp",
  "version": "1.0.0",
  "description": "Python language server (Pyright) for type checking and code intelligence",
  "author": {
    "name": "Anthropic"
  },
  "homepage": "https://github.com/anthropics/claude-plugins-official/tree/main/plugins/pyright-lsp",
  "lspServers": {
    "pyright": {
      "command": "pyright-langserver",
      "args": ["--stdio"],
      "extensionToLanguage": {
        ".py": "python",
        ".pyi": "python"
      }
    }
  }
}
"""

#: Replacement descriptions for agents whose upstream description is long or example-laden.
DESCRIPTIONS: dict[str, dict[str, str]] = {
    "pr-review-toolkit": {
        "code-reviewer": (
            "Review code for adherence to the project's CLAUDE.md, style guides and best "
            "practices, reporting only high-confidence issues. Use proactively after writing or "
            "modifying code and before committing or opening a pull request. Reviews the unstaged "
            "git diff unless told which files to focus on."
        ),
        "code-simplifier": (
            "Simplify recently written or modified code for clarity, consistency and "
            "maintainability while preserving behaviour. Use proactively after completing a "
            "feature, bug fix or refactor. Scoped to the code just changed unless told otherwise."
        ),
        "comment-analyzer": (
            "Check code comments and docstrings for accuracy against the code, completeness and "
            "comment rot. Use after writing large docstrings, before finalising a pull request "
            "that adds or changes comments, or when auditing existing comments."
        ),
        "pr-test-analyzer": (
            "Review a pull request's tests for coverage quality and missed edge cases. Use after "
            "a pull request is created or updated, and before marking it ready to merge."
        ),
        "silent-failure-hunter": (
            "Find silent failures in changed code — swallowed exceptions, empty catch or except "
            "blocks, unjustified fallbacks and error paths that hide problems. Use proactively "
            "after writing or refactoring error handling, retry or fallback logic, and before "
            "calling a diff done."
        ),
        "type-design-analyzer": (
            "Rate type design for encapsulation, invariant expression, usefulness and "
            "enforcement. Use when introducing a new type, when a pull request adds types, or "
            "when refactoring existing types."
        ),
    },
}

_DESCRIPTION_REASON = (
    "description shortened to its triggers. Upstream's {detail}; descriptions load into every "
    "session. The agent body is untouched."
)

_DESCRIPTION_DETAILS = {
    "code-simplifier": "is a block scalar carrying three worked `<example>` transcripts",
    "silent-failure-hunter": (
        "is a single-line scalar holding literal `\\n` escapes, so its worked examples rendered "
        "as one unbroken run of text, and all three use a named individual as the example user"
    ),
}

_MODEL_NOTE = (
    "> **Model identifiers in this file are illustrative and date quickly.** For current Claude "
    "model IDs, pricing and API parameters, load the `claude-api` skill rather than copying an "
    "ID from here."
)

_LLM_NOTE_TARGETS = (
    "agents/ai-engineer.md", "agents/prompt-engineer.md", "commands/langchain-agent.md",
    "commands/prompt-optimize.md", "skills/langchain-architecture/SKILL.md",
    "skills/llm-evaluation/SKILL.md", "skills/prompt-engineering-patterns/SKILL.md",
    "skills/rag-implementation/SKILL.md",
)

_FEATURE_DEV_TOOLS = "Glob, Grep, Read, WebFetch, WebSearch"


def _build_modifications() -> dict[str, list[Modification]]:
    """Assemble the full modification table."""
    mods: dict[str, list[Modification]] = {}

    def add(plugin: str, mod: Modification) -> None:
        mods.setdefault(plugin, []).append(mod)

    for plugin, agents in TIERS.items():
        for agent, model in agents.items():
            add(plugin, Modification(
                reason=f"`agents/{agent}.md` — {_TIER_REASON.format(model=model)}",
                set_field=(agent, "model", model),
            ))

    for plugin, agents in DESCRIPTIONS.items():
        for agent, text in agents.items():
            detail = _DESCRIPTION_DETAILS.get(agent, "description runs to several sentences")
            add(plugin, Modification(
                reason=f"`agents/{agent}.md` — {_DESCRIPTION_REASON.format(detail=detail)}",
                set_field=(agent, "description", text),
            ))

    add("pr-review-toolkit", Modification(
        reason=(
            "`agents/code-simplifier.md` — removed another project's hardcoded house style. It "
            "mandated ES modules, `function` over arrow functions, explicit return types, React "
            "`Props` types, and avoiding try/catch, *while claiming to follow CLAUDE.md* — wrong "
            "for any project that is not that JavaScript codebase. Now defers to the project's "
            "`CLAUDE.md` and states that the agent has no house style of its own."
        ),
        replace=("agents/code-simplifier.md", _CODE_SIMPLIFIER_OLD, _CODE_SIMPLIFIER_NEW),
    ))

    for agent in ("code-architect", "code-explorer", "code-reviewer"):
        add("feature-dev", Modification(
            reason=(
                f"`agents/{agent}.md` — declared name changed to `feature-dev-{agent}`, with every "
                f"bare reference in the plugin updated. Upstream's bare `{agent}` collides with "
                "`pr-review-toolkit`'s agent of the same name inside one bundle; the "
                "prefixed form matches the `<plugin>-<agent>` convention wshobson uses."
            ),
            rename_agent=(agent, f"feature-dev-{agent}"),
        ))
        add("feature-dev", Modification(
            reason=(
                f"`agents/{agent}.md` — `tools:` reduced to `{_FEATURE_DEV_TOOLS}`. Upstream "
                "lists LS, NotebookRead, TodoWrite, KillShell and BashOutput, which current Claude "
                "Code does not provide; the agent's job is read-only search either way."
            ),
            set_field=(agent, "tools", _FEATURE_DEV_TOOLS),
        ))

    for rel in _LLM_NOTE_TARGETS:
        add("llm-application-dev", Modification(
            reason=(
                f"`{rel}` — a note added under the frontmatter pointing at the built-in "
                "`claude-api` skill for current model IDs. Upstream hard-codes model names "
                "that date quickly."
            ),
            insert_note=(rel, _MODEL_NOTE),
        ))
    add("llm-application-dev", Modification(
        reason=("`agents/ai-engineer.md` — the Anthropic model line names model families instead "
                "of pinned versions."),
        replace_line=("agents/ai-engineer.md", "- Anthropic Claude Opus 4.8",
                      "- Anthropic Claude (Opus, Sonnet and Haiku tiers) with tool use and "
                      "computer use — current IDs via the `claude-api` skill"),
    ))
    add("llm-application-dev", Modification(
        reason=("`agents/prompt-engineer.md` — the Anthropic section heading names model families "
                "instead of pinned versions."),
        replace_line=("agents/prompt-engineer.md", "#### Anthropic Claude (",
                      "#### Anthropic Claude (Opus, Sonnet and Haiku tiers — current IDs via the "
                      "`claude-api` skill)"),
    ))
    add("llm-application-dev", Modification(
        reason="`.claude-plugin/plugin.json` — description drops pinned model versions.",
        replace=(".claude-plugin/plugin.json", "for Claude 4.6 and GPT-5.4",
                 "for Claude and GPT model families"),
    ))

    mods["pyright-lsp"] = [
        Modification(
            reason=(
                "`.claude-plugin/plugin.json` — **authored here; upstream has none.** This plugin "
                "ships only a `LICENSE` and a `README`: its entire substance is the `lspServers` "
                "block in the marketplace catalogue entry, which a vendored copy cannot carry. The "
                "block was transcribed from that entry into an inline `lspServers` field; the author "
                "contact address is omitted. "
                "Without this file the directory is not a plugin. The language server itself is "
                "still a separate install (`pyright-langserver` must be on PATH)."
            ),
            write_file=(".claude-plugin/plugin.json", _PYRIGHT_PLUGIN_JSON),
        ),
    ]

    return mods


MODIFICATIONS = _build_modifications()


# --------------------------------------------------------------------------- #
# copying
# --------------------------------------------------------------------------- #


def write(path: Path, text: str) -> None:
    """Write UTF-8 text with LF endings."""
    path.write_text(text.replace("\r\n", "\n"), encoding="utf-8", newline="\n")


def is_noise(rel: Path) -> bool:
    """True when a path is build or runtime debris rather than plugin content."""
    for part in rel.parts:
        if part in NOISE_DIRS or part in NOISE_FILES:
            return True
    return rel.suffix in NOISE_SUFFIXES


def copy_plugin(src: Path, dst: Path) -> tuple[int, list[str]]:
    """Copy ``src`` to ``dst`` minus noise, normalising text to UTF-8 + LF.

    The destination is removed first, so the result is the upstream tree exactly,
    not a merge with whatever was there before.

    Args:
        src: Upstream plugin directory inside a marketplace clone.
        dst: Target directory under ``claude/vendor/``.

    Returns:
        ``(files_copied, stripped_relative_paths)``.
    """
    if dst.exists():
        shutil.rmtree(dst)
    copied = 0
    stripped: list[str] = []
    for path in sorted(src.rglob("*")):
        rel = path.relative_to(src)
        if path.is_symlink():
            # A symlink in the upstream clone would otherwise have its target's
            # content read and written into the vendored (then deployed) tree,
            # smuggling out-of-tree content past review. Strip it like noise.
            stripped.append(rel.as_posix())
            continue
        if is_noise(rel):
            if path.is_file():
                stripped.append(rel.as_posix())
            continue
        target = dst / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            shutil.copy2(path, target)
        else:
            write(target, text)
        copied += 1
    return copied, stripped


def inventory(root: Path) -> list[str]:
    """Human-readable component counts for ``UPSTREAM.md``."""
    lines = []
    for kind in ("agents", "commands"):
        d = root / kind
        if d.exists():
            items = sorted(p.stem for p in d.glob("*.md"))
            if items:
                lines.append(f"- **{kind}** ({len(items)}): "
                             + ", ".join(f"`{i}`" for i in items))
    d = root / "skills"
    if d.exists():
        items = sorted(p.name for p in d.iterdir() if p.is_dir())
        if items:
            lines.append(f"- **skills** ({len(items)}): " + ", ".join(f"`{i}`" for i in items))
    d = root / "hooks"
    if d.exists():
        items = sorted(p.name for p in d.iterdir() if p.is_file())
        if items:
            lines.append(f"- **hooks** ({len(items)}): " + ", ".join(f"`{i}`" for i in items))
    if (root / ".claude-plugin" / "plugin.json").is_file():
        data = json.loads((root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        if "lspServers" in data:
            lines.append(f"- **lspServers** ({len(data['lspServers'])}): "
                         + ", ".join(f"`{k}`" for k in sorted(data["lspServers"])))
    return lines


# --------------------------------------------------------------------------- #
# licensing
# --------------------------------------------------------------------------- #


def detect_license(text: str) -> str:
    """Return the SPDX id of a license text, judged from its first non-blank lines.

    Raises ``ValueError`` for anything other than MIT or Apache-2.0.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()][:5]
    if lines and lines[0].lower() == "mit license":
        return "MIT"
    head = "\n".join(lines).lower()
    if "apache license" in head and "version 2.0" in head:
        return "Apache-2.0"
    raise ValueError(f"unrecognised license text starting {lines[:1]!r}")


def plugin_license(root: Path) -> str:
    """Return the SPDX id of a vendored plugin's ``LICENSE``, exiting when it is absent or unknown."""
    path = root / "LICENSE"
    if not path.is_file():
        sys.exit(f"{root.name}: no LICENSE")
    try:
        return detect_license(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        sys.exit(f"{root.name}: {exc}")


def ensure_license(name: str, root: Path, source: Source) -> str:
    """Give a plugin a ``LICENSE``, copying the source repository's when it has none."""
    path = root / "LICENSE"
    if not path.is_file():
        text = source.license_text()
        if text is None:
            sys.exit(f"{name}: ships no LICENSE and {source.key} offers no root license to copy")
        write(path, text)
    return plugin_license(root)


def touched_files(name: str, root: Path) -> tuple[list[str], list[str]]:
    """Return ``(modified, added)`` plugin-relative paths, derived from the declared tables.

    Files holding a retargeted or renamed reference count as modified; ``LICENSE`` and
    ``UPSTREAM.md`` are never listed.
    """
    modified: set[str] = set()
    added: set[str] = set()

    def containing(name_: str) -> None:
        pattern = re.compile(rf"(?<![\w-]){re.escape(name_)}(?![\w-])")
        for path in text_files(root):
            if pattern.search(path.read_text(encoding="utf-8")):
                modified.add(path.relative_to(root).as_posix())

    for mod in MODIFICATIONS.get(name, []):
        if mod.set_field is not None:
            modified.add(f"agents/{mod.set_field[0]}.md")
        elif mod.rename_agent is not None:
            modified.add(f"agents/{mod.rename_agent[0]}.md")
            containing(mod.rename_agent[1])
        elif mod.insert_note is not None:
            modified.add(mod.insert_note[0])
        elif mod.replace is not None:
            modified.add(mod.replace[0])
        elif mod.replace_line is not None:
            modified.add(mod.replace_line[0])
        elif mod.write_file is not None:
            added.add(mod.write_file[0])

    for stem, rule in sorted(COLLAPSE.items()):
        if name not in rule.duplicates:
            continue
        owner = root.parent / rule.owner / "agents" / f"{stem}.md"
        if owner.is_file():
            target = frontmatter_field(owner.read_text(encoding="utf-8"), "name")
            if target:
                containing(target)

    present = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    modified = {m for m in modified if m in present and m not in ("LICENSE", "UPSTREAM.md")}
    return sorted(modified), sorted(added & present)


def apply_notices(name: str, root: Path, spdx: str) -> list[str]:
    """Insert the modified-file notice into every changed Markdown file of an Apache-2.0 plugin."""
    if spdx != "Apache-2.0":
        return []
    modified, _ = touched_files(name, root)
    return [Modification._insert_note(root, rel, MODIFIED_NOTICE)
            for rel in modified if rel.endswith(".md")]


# --------------------------------------------------------------------------- #
# UPSTREAM.md
# --------------------------------------------------------------------------- #


@dataclass
class Provenance:
    """Facts about a sync that only the sync itself can observe."""

    commit: str
    retrieved: str
    stripped: list[str]
    not_vendored: list[str]
    collapsed: list[str]


def _section(text: str, heading: str) -> list[str]:
    """Return the lines of one ``## `` section of an ``UPSTREAM.md``."""
    marker = f"## {heading}\n"
    if marker not in text:
        return []
    body = text.split(marker, 1)[1]
    return body.split("\n## ", 1)[0].split("\n")


def parse_upstream(text: str) -> Provenance:
    """Read back the facts :func:`upstream_md` renders, so a re-render needs no clone."""
    commit = re.search(r"^\| Upstream commit \| `([0-9a-f]+)` \|$", text, re.M)
    retrieved = re.search(r"^\| Retrieval date \| (.+?) \|$", text, re.M)
    if commit is None or retrieved is None:
        sys.exit("UPSTREAM.md records no upstream commit or retrieval date")
    return Provenance(
        commit=commit.group(1),
        retrieved=retrieved.group(1),
        stripped=[ln[2:].strip("`") for ln in _section(text, "Stripped on the way in")
                  if ln.startswith("- `")],
        not_vendored=[ln[2:].strip("`") for ln in _section(text, "Not vendored")
                      if ln.startswith("- `")],
        collapsed=[ln[2:] for ln in _section(text, "Collapsed into canonical copies")
                   if ln.startswith("- ")],
    )


def upstream_md(name: str, source: Source, prov: Provenance, root: Path,
                mods: list[Modification], spdx: str, added: list[str]) -> str:
    """Render a plugin's ``UPSTREAM.md``."""
    pj = root / ".claude-plugin" / "plugin.json"
    version = "none declared — Claude Code resolves this plugin's version to the commit above"
    if pj.is_file():
        declared = json.loads(pj.read_text(encoding="utf-8")).get("version")
        if declared:
            version = f"`{declared}`"
    bundle = bundle_of(name)
    deployed = (f"`{bundle}` plugin (`plugins/{bundle}/`)" if bundle
                else f"optional extra — installed only with `deploy --extra {name}`")

    out = [
        f"# UPSTREAM — `{name}`",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Plugin | `{name}` |",
        f"| Upstream marketplace | `{source.key}` |",
        f"| Source repo | {source.repo} |",
        f"| Source path | `plugins/{name}` |",
        f"| Upstream commit | `{prov.commit}` |",
        f"| Commit provenance | {source.commit_note} |",
        f"| Upstream version | {version} |",
        f"| Retrieval date | {prov.retrieved} |",
        f"| Upstream author | {source.author} |",
        f"| License | {spdx} (`LICENSE` in this directory) |",
        f"| Deployed as | {deployed} |",
        "",
        "## Contents",
        "",
    ]
    out += inventory(root) or ["- (no agents, skills, commands, hooks, or LSP servers)"]

    out += ["", "## Stripped on the way in", ""]
    if prov.stripped:
        out += [f"- `{s}`" for s in prov.stripped]
    else:
        out += ["Nothing — the upstream plugin contained no `.in_use/`, `__pycache__/`,",
                "`.orphaned_at`, `tests/`, or `.github/` content."]

    out += ["", "## Not vendored", ""]
    if prov.not_vendored:
        out += ["Left upstream by the `SELECTION` table in `tools/vendor_sync.py`:", ""]
        out += [f"- `{o}`" for o in prov.not_vendored]
    else:
        out += ["Nothing — every upstream component is carried."]

    out += ["", "## Collapsed into canonical copies", ""]
    if prov.collapsed:
        out += ["Dropped by the `COLLAPSE` table in `tools/vendor_sync.py`:", ""]
        out += [f"- {c}" for c in prov.collapsed]
    else:
        out += ["Nothing."]

    out += ["", "## Local modifications", ""]
    if mods:
        out += ["Apart from the omissions above, the vendored copy diverges from upstream in "
                "exactly the",
                "ways below. Everything else is byte-identical to the upstream repository's "
                "content.", ""]
        for m in mods:
            out += [f"- {m.reason}", ""]
        if spdx == "Apache-2.0":
            out += ["Each modified Markdown file carries a notice that it was changed from the "
                    "upstream version.", ""]
    else:
        out += ["None. The vendored copy is byte-identical to the upstream repository's content.", ""]

    out += ["## Files added", ""]
    out += [f"- `{a}`" for a in added] if added else ["None."]

    out += [
        "",
        "## Line endings",
        "",
        "Text files are normalised to UTF-8 with LF line endings.",
        "",
        "## Re-syncing",
        "",
        "Run `python tools/vendor_sync.py --apply`. It re-copies from the local marketplace clone and",
        "re-applies every modification listed above from its declared table. It fails rather than",
        "skipping if upstream has changed the text a modification targets.",
        "",
    ]
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# manifest
# --------------------------------------------------------------------------- #


def build_manifest(vendor: Path, commits: dict[str, str], generated: str) -> dict:
    """Assemble the v3 plugin manifest from the vendored tree and the declared tables."""
    plugins: list[dict] = []
    agent_owners: dict[str, list[str]] = {}

    for name, mk in PLUGINS:
        root = vendor / name
        source = SOURCES[mk]
        comps: dict[str, list[str]] = {}
        for kind in ("agents", "commands"):
            d = root / kind
            if d.exists():
                comps[kind] = sorted(p.stem for p in d.glob("*.md"))
        d = root / "skills"
        if d.exists():
            comps["skills"] = sorted(p.name for p in d.iterdir() if p.is_dir())
        for agent in comps.get("agents", []):
            agent_owners.setdefault(agent, []).append(name)

        version = "commit-sha"
        pj = root / ".claude-plugin" / "plugin.json"
        if pj.is_file():
            version = json.loads(pj.read_text(encoding="utf-8")).get("version", "commit-sha")
        modified, added = touched_files(name, root)
        plugins.append({
            "name": name,
            "upstream_marketplace": mk,
            "source_repo": source.repo,
            "source_path": f"plugins/{name}",
            "upstream_commit": commits[mk],
            "upstream_version": version,
            "license": plugin_license(root),
            "bundle": bundle_of(name),
            "local_modifications": bool(MODIFICATIONS.get(name) or modified or added),
            "files_modified": modified,
            "files_added": added,
            "components": comps,
        })

    duplicates = {a: sorted(ps) for a, ps in sorted(agent_owners.items()) if len(ps) > 1}

    return {
        "schema": MANIFEST_SCHEMA,
        "generated": generated,
        "generated_by": "tools/vendor_sync.py",
        "upstream_sources": {
            key: {"repo": src.repo, "author": src.author, "vendored_at": commits[key]}
            for key, src in SOURCES.items()
        },
        "canonical_agents": {
            "note": (
                "Agents upstream ships byte-identically (apart from the name line) under several "
                "plugins. One copy is kept in `owner`; the copies in `collapsed_from` are dropped "
                "by tools/vendor_sync.py and every reference to them is retargeted to the owner's "
                "declared name. The sync fails if a listed copy has diverged."
            ),
            "agents": {
                stem: {"owner": rule.owner, "collapsed_from": sorted(rule.duplicates)}
                for stem, rule in sorted(COLLAPSE.items())
            },
        },
        "accepted_duplicate_agents": {
            "note": (
                "Agent file stems still defined by more than one vendored plugin after the "
                "canonical collapse — copies whose content genuinely differs. Each declares a "
                "unique `<plugin>-<agent>` name, so addressing is unambiguous. "
                "tests/python/test_plugin_manifest.py fails on any duplicate not listed here."
            ),
            "agents": duplicates,
        },
        "plugins": plugins,
    }


def write_manifest(manifest: dict, path: Path) -> None:
    """Write the manifest with a trailing newline."""
    write(path, json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")


def rendered_upstream(name: str, mk: str, vendor: Path) -> str:
    """Return the ``UPSTREAM.md`` a vendored plugin should carry, from what is on disk."""
    root = vendor / name
    prov = parse_upstream((root / "UPSTREAM.md").read_text(encoding="utf-8"))
    _, added = touched_files(name, root)
    return upstream_md(name, SOURCES[mk], prov, root, MODIFICATIONS.get(name, []),
                       plugin_license(root), added)


def render_upstream(repo: Path, today: str, only: list[str] | None = None) -> int:
    """Re-render licenses, notices, ``UPSTREAM.md`` and the manifest from what is vendored.

    The pins, retrieval dates and sync-time lists are read back from the existing
    ``UPSTREAM.md`` files and manifest, so no clone is needed and no pin can move.
    """
    vendor = repo / "claude" / "vendor"
    manifest_path = repo / "claude" / "plugins.manifest.json"
    if not manifest_path.is_file():
        sys.exit(f"no existing manifest to read pins from: {manifest_path}")
    existing = json.loads(manifest_path.read_text(encoding="utf-8"))
    commits = {key: entry["vendored_at"]
               for key, entry in existing.get("upstream_sources", {}).items()}
    missing = set(SOURCES) - set(commits)
    if missing:
        sys.exit(f"existing manifest records no pin for {sorted(missing)}; "
                 "run 'python tools/vendor_sync.py --apply' instead")

    for name, mk in PLUGINS:
        if only and name not in only:
            continue
        root = vendor / name
        if not root.is_dir():
            sys.exit(f"{name}: not vendored at {root}")
        upstream = root / "UPSTREAM.md"
        if not upstream.is_file():
            sys.exit(f"{name}: no UPSTREAM.md to read provenance from")
        spdx = ensure_license(name, root, SOURCES[mk])
        apply_notices(name, root, spdx)
        write(upstream, rendered_upstream(name, mk, vendor))

    write_manifest(build_manifest(vendor, commits, existing.get("generated", today)),
                   manifest_path)
    print(f"rendered {len(PLUGINS)} UPSTREAM.md file(s) and "
          f"{manifest_path.relative_to(repo).as_posix()}")
    return 0


def vendor_one(name: str, mk: str, today: str, vendor: Path, commits: dict[str, str]) -> str:
    """Re-vendor one plugin from its clone and return a one-line summary."""
    source = SOURCES[mk]
    src = source.root / "plugins" / name
    if not src.is_dir():
        sys.exit(f"upstream missing: {src}")
    dst = vendor / name
    copied, stripped = copy_plugin(src, dst)
    omitted = apply_selection(dst, SELECTION[name]) if name in SELECTION else []
    collapsed = collapse_duplicates(name, dst)
    mods = MODIFICATIONS.get(name, [])
    applied = [m.apply(dst) for m in mods]
    check_tiers(name, dst)
    spdx = ensure_license(name, dst, source)
    applied += apply_notices(name, dst, spdx)
    _, added = touched_files(name, dst)
    prov = Provenance(commits[mk], today, stripped, omitted, collapsed)
    write(dst / "UPSTREAM.md", upstream_md(name, source, prov, dst, mods, spdx, added))

    extra = [f"-{len(omitted)} selected out"] if omitted else []
    extra += [f"-{len(collapsed)} collapsed"] if collapsed else []
    note = f"  [{'; '.join(extra + applied)}]" if extra or applied else ""
    return f"  {name:28s} {copied:3d} files  {spdx}{note}"


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    global MARKETPLACES
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--apply", action="store_true",
                        help="write changes; without it the script only reports")
    parser.add_argument("--only", metavar="PLUGIN", action="append",
                        help="restrict to one plugin (repeatable)")
    parser.add_argument("--date", default=date.today().isoformat(),
                        help="retrieval date recorded in UPSTREAM.md (default: today)")
    parser.add_argument("--marketplaces", type=Path, default=None, metavar="DIR",
                        help="directory holding one clone per upstream source key "
                             f"(default: {MARKETPLACES})")
    parser.add_argument("--render-upstream", action="store_true",
                        help="rewrite LICENSE files, modified-file notices, every UPSTREAM.md and "
                             "the manifest from the vendored content; needs no clones")
    args = parser.parse_args(argv)
    if args.marketplaces is not None:
        MARKETPLACES = args.marketplaces.resolve()

    known = {n for n, _ in PLUGINS}
    if args.only and set(args.only) - known:
        sys.exit(f"unknown plugin(s): {sorted(set(args.only) - known)}")
    selected = [(n, m) for n, m in PLUGINS if not args.only or n in args.only]

    if args.render_upstream:
        return render_upstream(REPO_ROOT, args.date, args.only)

    commits = {key: src.commit() for key, src in SOURCES.items()}
    for key, commit in commits.items():
        print(f"{key}: {commit}")
    print()

    if not args.apply:
        print("DRY RUN — nothing written. Re-run with --apply.\n")
        for name, mk in selected:
            src = SOURCES[mk].root / "plugins" / name
            status = "ok" if src.is_dir() else "MISSING UPSTREAM"
            mods = MODIFICATIONS.get(name, [])
            collapses = sum(1 for rule in COLLAPSE.values() if name in rule.duplicates)
            selection = "selected" if name in SELECTION else "whole"
            print(f"  {name:28s} {status:16s} {selection:8s} {collapses} collapse(s), "
                  f"{len(mods)} declared modification(s)")
        return 0

    VENDOR.mkdir(parents=True, exist_ok=True)
    for name, mk in selected:
        print(vendor_one(name, mk, args.date, VENDOR, commits))
    print(f"\n{len(selected)} plugin(s) vendored into {VENDOR}")

    # The manifest is derived from the whole tree, so it is rewritten in full even under --only.
    write_manifest(build_manifest(VENDOR, commits, args.date), MANIFEST)
    print(f"wrote {MANIFEST.relative_to(REPO_ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
