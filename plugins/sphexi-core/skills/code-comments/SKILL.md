---
name: code-comments
description: The minimal comment model — what a comment must say, what it must never contain, and how much of it is allowed. Use when writing or editing comments and docstrings, when reviewing a diff for comment quality, when a file's prose has outgrown its code, or when reducing an existing codebase's comments. Covers Python, Bash, PowerShell, Dockerfile, Rust, JavaScript, and Jinja2.
---

# Code Comments

The hard rules are in every agent definition and in `~/.claude/CLAUDE.md`, inlined from
`shared/code-standards.md`. This skill is the working reference: the reasoning behind
each rule, worked before-and-after examples, per-language mechanics, and the procedure
for reducing an existing codebase.

## The model in one paragraph

Source files are for code, and **the default is no comment at all**. A comment is a small,
expensive exception granted to a line that cannot speak for itself. It says **why** — the
constraint, the trap, the invariant. The code already says what and how, and the
repository's documentation already says what was decided and when. A comment that repeats
any of those is a second copy of something, and the copy is what goes stale. Most code
needs no justification anywhere and is finished as it stands.

## What a comment must never contain

This list is absolute. It holds in docstrings as much as in inline comments, in every
language, in test files as much as in source files.

| Category | Examples of the prohibited form |
|---|---|
| Process and provenance | `# Session 14 added this`, `# per TECHNICAL_PLAN.md § 4`, `# backlog #168`, `# added 2026-03-11` |
| Decision rationale | `# We went with Postgres because SQLite locks under concurrent writes` |
| The case for a choice, against its alternatives | `# Argon2id rather than bcrypt because…`, `# a plain SHA-256 is correct here, not a KDF, because…`, `# p=1 because each extra thread multiplies the memory pool` |
| Citations propping up a choice | a link to a standard, benchmark, or cheat sheet included to show a value was well-chosen |
| People | `# Sam wanted this configurable`, `# per our discussion`, `# requested by the platform team` |
| The assistant and its machinery | any mention of Claude, an agent, a subagent, a skill, a plugin, a prompt, `CLAUDE.md`, a technical plan, or a session |
| Changelog prose | `# Added in v2`, `# changed to fix the double-send bug`, `# used to call _legacy_parse` |
| Tours of other files | `# the login route catches this and converges on a 401`, `# imported by the CLI and by the admin route` |
| Commented-out code | any of it |

Four of these are worth their own note.

**Decision rationale versus a code constraint.** The distinction is which artefact would
have to change if the fact changed. If a different database would change the *decision*,
it is documentation. If a different database would change *this line*, it is a comment:

```python
# asyncpg rejects a bound parameter in an identifier position, so the table
# name is interpolated after validation against the allowlist above.
query = f"SELECT * FROM {table} WHERE workspace_id = $1"
```

That comment stops a future reader from "fixing" an apparent SQL injection. It names a
constraint the code is under. It does not mention which database was chosen or why.

**Why the assistant is prohibited.** A comment naming a session, a plan, or an agent
encodes the *authoring process* into a deliverable that outlives it. The file is read by
people who were not in that session, by other tools, and by whoever inherits the repo.
None of them can act on it, and all of them have to decide whether it is still true.

**The case for a choice is not a comment, however technical it sounds.** A constraint says
what happens to *this code* if you get it wrong. An argument says why the author preferred
one option over another, and it can always be recognised by the runner-up appearing in the
prose. The chosen value is already in the code; the reader editing that line does not need
the debate replayed, and a paragraph defending a number is the commonest way prose grows
back after a reduction pass. Two disguises to watch for. A comment that begins as a real
constraint and then keeps going has stopped qualifying partway through — keep the sentence
naming the constraint, delete the paragraph arguing for it. And an argument can be dressed
as an invariant: *"this must stay at 64 MiB because two concurrent jobs at peak load
would push the host into swap"* is a case for a value, not an invariant the code depends on.

A citation behaves the same way. A link to an upstream **defect** being worked around, or to
the **spec being implemented**, tells a reader something they cannot get from the code and
stays. A link to a cheat sheet or benchmark showing the value was well-chosen is the
argument above with a URL attached, and goes.

**Why a tour of other files is prohibited.** Prose in a callee describing what its callers
do with it — which route catches this error, which two modules import this schema — is
correct on the day it is written and silently wrong the first time any of them moves. It is
also unnecessary: those files are one grep away, and they hold the authoritative version of
their own behaviour. Name another module only where *this* code breaks without it.

## What a comment is for

Adapted from [Stack Overflow's best practices for writing code
comments](https://stackoverflow.blog/2021/12/23/best-practices-for-writing-code-comments/),
which is the reference this model follows most closely.

1. **Do not duplicate the code.** `i += 1  # increment i` is pure cost.
2. **A good comment does not excuse unclear code.** Rename the variable, split the
   function, invert the condition. Reach for a comment only after the code is as clear
   as it can be made.
3. **If the comment is hard to write, the code is probably too clever.** Difficulty
   articulating what a block does is evidence about the block, not about your prose.
4. **A comment must dispel confusion, never create it.** A cryptic or half-true comment
   is worse than silence — delete it rather than leaving it ambiguous.
5. **Explain unidiomatic code.** Code that looks redundant, wrong, or pointlessly
   defensive gets a line saying why it is none of those. This is the single highest-value
   comment there is, because without it the code gets deleted by someone being helpful.
6. **Link the source of adapted code.** A URL to the answer, gist, or spec it came from.
7. **Link external references at the point of use.** The RFC section, the vendor's
   documented quirk, the standard being implemented. Not a reference that exists to show
   the value was well-chosen — see the note on citations above.
8. **Comment around a bug fix — as a constraint, not an incident.** `# the API returns
   200 with an empty body on a rate limit, so status alone is not sufficient`, never
   `# fixes the double-sync bug`.
9. **Mark incomplete work with `TODO`, naming the condition that resolves it.** No
   person, no session, no date: `# TODO: batch these once the API exposes a bulk endpoint`.

## Size limits

| Scope | Budget |
|---|---|
| Module / file header | 1–3 lines. What this file is. Nothing else. |
| Public class, function, method | One-line docstring where the name and signature do not already say it. Imperative mood. `hash_password(plaintext: str) -> str` needs no line reporting that it hashes a password. |
| Public constant, type alias, interface, field | None, unless the value or shape is genuinely not self-evident from the name |
| `Args:` / `Returns:` / `Raises:` and equivalents | Only where they add information the signature does not carry |
| Private helper | None, unless the logic is genuinely not self-evident |
| Inline | One line. A paragraph means the code needs restructuring. |

A 60-line module docstring is not a documentation success. It is documentation that has
been filed in the wrong place, where no reader looking for documentation will find it and
every reader looking for code has to scroll past it.

## Per-language mechanics

### Python

Every public symbol keeps a docstring; the first line is a short imperative sentence.
`Args:`/`Returns:`/`Raises:` sections are cut wherever they restate an annotated
signature — which, with modern type hints, is most of the time.

Before:

```python
def fetch_measurements(
    self, start: datetime, end: datetime, page_size: int = 100
) -> list[Measurement]:
    """Fetch measurements from the API.

    Retrieves all measurements within the given date range, handling
    pagination automatically. This was added in sprint 12 after Sam found
    that the single-page version silently dropped data; see
    docs/design.md § Pagination for the full design.

    Args:
        start: Start of the window as a datetime.
        end: End of the window as a datetime.
        page_size: Number of records per page, defaults to 100.

    Returns:
        A list of Measurement objects.

    Raises:
        AuthError: If authentication fails.
    """
```

After:

```python
def fetch_measurements(
    self, start: datetime, end: datetime, page_size: int = 100
) -> list[Measurement]:
    """Fetch every measurement in the window, following pagination to the end.

    Both bounds are inclusive; the API treats an exclusive end as an off-by-one
    and silently drops the final record.
    """
```

The second version is shorter *and* carries more: the inclusivity of the bounds is a
caller constraint that the signature cannot express. Everything deleted was either a
restatement of the annotations or history that belongs in `docs/` and git.

Module docstrings follow the same rule — one to three lines:

```python
"""asyncpg pool and workspace-scoped query helpers.

Scoped helpers bind `workspace_id` as `$1` and reject SQL that does not
reference it in a predicate position.
"""
```

`#:` attribute comments on constants say what the constant constrains, not what its
name already says.

### Bash and PowerShell

The header says what the script does and what it assumes. Not who wrote it, not when,
not what changed.

```bash
#!/usr/bin/env bash
# Provision Docker and the compose plugin on a fresh Ubuntu host.
# Idempotent; safe to re-run.
set -euo pipefail
```

A `# shellcheck disable=` line carries a comment saying why the finding is a false
positive — that is a constraint comment and is required, not optional.

PowerShell comment-based help (`.SYNOPSIS`, `.PARAMETER`) is the documented public
interface of a function and stays. `.PARAMETER` entries that restate a typed parameter
go; `.NOTES` holding history goes.

### Dockerfile

Comment the *intent* of a layer, and only where the instruction does not carry it —
typically a cache-ordering decision, a pinned version, or a workaround:

```dockerfile
# Dependencies before source so a code change does not invalidate the pip layer.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
```

Do **not** maintain a changelog in a Dockerfile, and do not reference commits or
versions of the repo in comments, despite how often that advice appears online. Git
already holds that, and a Dockerfile comment holding it goes stale silently.

### Rust

`///` on public items, one line unless a caller constraint needs stating. `//!` module
docs stay short. `// SAFETY:` on every `unsafe` block is mandatory and states the
invariant being upheld — this is a constraint comment and among the most valuable in the
language. Doctests are code, not comments, and are exempt.

### JavaScript, CSS, Jinja2

Same model. A Jinja2 `{# #}` comment explaining a block structure that the template
already shows is deleted. A comment explaining why a value is escaped a particular way,
or why a CSS rule needs a specific specificity to beat a framework default, stays.

## Reducing an existing codebase

When cutting comments across a repository rather than writing new ones:

1. **Work file by file, not with a regex.** Comment removal is a judgement call per
   comment; a pattern-based pass deletes the valuable ones alongside the rest.
2. **Never touch string literals.** UI copy, schema `description=` fields, SQL, log
   messages, and validation text are data the program depends on. This is the failure
   mode that costs real data in a comment-reduction pass, and it has happened.
3. **Verify structural equivalence.** For Python, compare the AST of each file before
   and after with docstrings stripped — a comment-only change must leave the parse tree
   otherwise identical. Any file that fails gets reviewed by hand.
4. **Delete, do not paraphrase.** Material that belongs in `docs/` is removed from the
   source; it is not compressed into a shorter version of itself. If it is not already
   in `docs/`, put it there in the same change.
5. **Re-wrap afterwards, mechanically.** Compression pushes lines over the line-length
   limit. Re-wrap with a tool that only rewrites lines proven to be prose, then re-verify.
6. **Report the delta.** Prose lines before and after, and the prose-to-code ratio.
   A healthy ratio after a pass is well under 0.2:1.
