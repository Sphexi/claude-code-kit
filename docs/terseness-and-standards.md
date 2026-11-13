# Terseness and code standards

The kit ships two sets of working rules for Claude: how much a response says (terseness) and how code, comments and tests are written (code standards). Both are authored once and delivered to every place Claude reads instructions.

## Output styles

There are three output styles. They vary how much supporting explanation survives. They do not change grammar: every level is written in normal English, and a yes-or-no question gets a yes or a no at every level.

| Style | What survives |
|---|---|
| `Terse (Low)` | Answer first, no preamble, no recap. Full sentences. Reasoning is kept where it is load-bearing. |
| `Terse (Medium)` | The answer and the one thing needed to act on it. Background only when asked. |
| `Terse (Full)` | The answer. Fragments are acceptable. Explanation only where leaving it out would make the answer wrong. |

Use `Terse (Low)` for design discussion and debugging, where the reason matters as much as the result. Use `Terse (Full)` for lookups and fast iteration.

All three keep Claude Code's built-in coding instructions (`keep-coding-instructions: true`).

Select one with `/output-style`. An output style is part of the system prompt and is read at session start, so a change applies from the next session or after `/clear`.

Clone-and-deploy sets `outputStyle` to `Terse (Full)` when you have no value of your own. The marketplace plugin never sets or forces a style.

### Register

The levels change how much is said. A separate set of register rules governs how results are stated and holds at every level, including `Terse (Low)`:

- No agreement tokens such as "you're right" or "good catch".
- No adjectives that grade your own findings.
- No teasers that announce a finding before stating it.
- No narration of how or in what spirit a change was made.
- No restating a fact already given in the same turn.
- A sentence that only introduces, labels, justifies or counts other content is cut.

Working narration between tool calls, such as "Running the tests", is exempt.

Three kinds of content are never compressed at any level: safety-critical content such as security warnings and confirmations for irreversible actions; structured artefacts such as completion summaries, acceptance criteria, review findings and migration steps; and anything where shortening would leave order or dependency ambiguous.

### Subagents

An output style does not reach a subagent, which runs its own system prompt. The equivalent rules are written into each of the thirteen agent definitions in `sphexi-core`. They tell an agent to report outcome, then paths and deltas, then blockers and gaps, to end with a one-line `used` trailer naming the skills and plugins it invoked, and to follow the same register rules.

## Code standards

The standards govern comments and tests. They apply in every project, including projects with their own `CLAUDE.md`; a project may tighten them, and one that wants to loosen them says so explicitly in its own `CLAUDE.md`.

**Comments.** The default is no comment. The code says what and how; a comment says why. A comment never duplicates the code, its signature or documentation elsewhere in the repository. Comments never carry task identifiers, session numbers, dates, people, the history of a change, the case for one choice over another, or descriptions of other files. A comment earns its place only for code that looks wrong and is not, a constraint a signature cannot express, a workaround for an external defect, a source link, a deliberate omission, or an invariant the code depends on and does not enforce. Docstrings are one imperative line where the name and signature do not already say it.

**Tests.** A test earns its place only if deleting it would make a realistic failure materially harder to catch. Coverage is sized by project tier, as test lines against the code under test:

| Tier | Band | Covers |
|---|---|---|
| Light | about 0.85 to 1 | Happy path, error paths a caller can reach, config and boundary parsing |
| Standard | about 1.0 to 1.2 to 1 | The above plus edge cases, partial failure, retry and backoff |
| Heavy | about 1.5 to 1 | The above plus adversarial input, concurrency, recovery |

The ratio is a sanity check, not a target. Expensive tests, those touching a database, container, real filesystem or subprocess, are merged rather than parametrised, and pure tests are parametrised freely. During a session the suite is run in full once at the start, targeted runs follow each change, and one full run closes the work.

When the project's tier is not stated, Claude asks which it is before sizing tests or review.

The `code-comments` and `test-discipline` skills in `sphexi-core` hold the worked examples, per-language mechanics and the reduction procedure behind these rules. The rules themselves are in `shared/code-standards.md`.

## How the rules reach Claude

| Destination | Terseness | Code standards |
|---|---|---|
| Main session, clone and deploy | `outputStyle` in `settings.json`; the global `CLAUDE.md` describes the levels and the register rules | Inlined in the global `CLAUDE.md` |
| Main session, marketplace | A `SessionStart` hook in `sphexi-core` applies `Terse (Full)` by default; another output style selected with `/output-style` overrides it | The same hook prints the standards at session start |
| Subagents, both paths | Inlined in each agent definition | Inlined in each agent definition |
| Cowork | The same `SessionStart` hook as the marketplace, plus a `terseness` skill to switch level | The same `SessionStart` hook as the marketplace |

The hook splits its text at `##` headings into parts of at most 9,500 characters, one hook command per part, because Claude Code caps each hook output string at 10,000 characters and substitutes a file path and short preview above that. Deploy does not install the hook, since the global `CLAUDE.md` already carries the standards and `settings.json` sets `Terse (Full)`. See [cowork.md](cowork.md) for the Cowork additions.

A skill is not a delivery path. It loads only when its description matches the task, so the rules cannot rest on skills alone.

## Changing the rules

Edit the single source in `shared/`, then regenerate. See [customizing.md](customizing.md).
