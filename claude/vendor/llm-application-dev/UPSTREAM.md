# UPSTREAM — `llm-application-dev`

| Field | Value |
|---|---|
| Plugin | `llm-application-dev` |
| Upstream marketplace | `claude-code-workflows` |
| Source repo | https://github.com/wshobson/agents |
| Source path | `plugins/llm-application-dev` |
| Upstream commit | `9c61ab243def98f72da12abd41cfcf5bcd91af9d` |
| Commit provenance | git commit SHA (`.git/refs/heads/main` of the local marketplace clone) |
| Upstream version | `2.0.8` |
| Retrieval date | 2026-11-10 |
| Upstream author | Seth Hobson |
| License | MIT (`LICENSE` in this directory) |
| Deployed as | `sphexi-ai` plugin (`plugins/sphexi-ai/`) |

## Contents

- **agents** (3): `ai-engineer`, `prompt-engineer`, `vector-database-engineer`
- **commands** (3): `ai-assistant`, `langchain-agent`, `prompt-optimize`
- **skills** (8): `embedding-strategies`, `hybrid-search-implementation`, `langchain-architecture`, `llm-evaluation`, `prompt-engineering-patterns`, `rag-implementation`, `similarity-search-patterns`, `vector-index-tuning`

## Stripped on the way in

- `.codex-plugin/plugin.json`

## Not vendored

Nothing — every upstream component is carried.

## Collapsed into canonical copies

Nothing.

## Local modifications

Apart from the omissions above, the vendored copy diverges from upstream in exactly the
ways below. Everything else is byte-identical to the upstream repository's content.

- `agents/ai-engineer.md` — model set to `sonnet` per the tier table in `tools/vendor_sync.py` — judgement-heavy review, security and architecture on `opus`, implementers and routine analysis on `sonnet`. Upstream's value is overridden; nothing else in the file changed.

- `agents/prompt-engineer.md` — model set to `sonnet` per the tier table in `tools/vendor_sync.py` — judgement-heavy review, security and architecture on `opus`, implementers and routine analysis on `sonnet`. Upstream's value is overridden; nothing else in the file changed.

- `agents/vector-database-engineer.md` — model set to `sonnet` per the tier table in `tools/vendor_sync.py` — judgement-heavy review, security and architecture on `opus`, implementers and routine analysis on `sonnet`. Upstream's value is overridden; nothing else in the file changed.

- `agents/ai-engineer.md` — a note added under the frontmatter pointing at the built-in `claude-api` skill for current model IDs. Upstream hard-codes model names that date quickly.

- `agents/prompt-engineer.md` — a note added under the frontmatter pointing at the built-in `claude-api` skill for current model IDs. Upstream hard-codes model names that date quickly.

- `commands/langchain-agent.md` — a note added under the frontmatter pointing at the built-in `claude-api` skill for current model IDs. Upstream hard-codes model names that date quickly.

- `commands/prompt-optimize.md` — a note added under the frontmatter pointing at the built-in `claude-api` skill for current model IDs. Upstream hard-codes model names that date quickly.

- `skills/langchain-architecture/SKILL.md` — a note added under the frontmatter pointing at the built-in `claude-api` skill for current model IDs. Upstream hard-codes model names that date quickly.

- `skills/llm-evaluation/SKILL.md` — a note added under the frontmatter pointing at the built-in `claude-api` skill for current model IDs. Upstream hard-codes model names that date quickly.

- `skills/prompt-engineering-patterns/SKILL.md` — a note added under the frontmatter pointing at the built-in `claude-api` skill for current model IDs. Upstream hard-codes model names that date quickly.

- `skills/rag-implementation/SKILL.md` — a note added under the frontmatter pointing at the built-in `claude-api` skill for current model IDs. Upstream hard-codes model names that date quickly.

- `agents/ai-engineer.md` — the Anthropic model line names model families instead of pinned versions.

- `agents/prompt-engineer.md` — the Anthropic section heading names model families instead of pinned versions.

- `.claude-plugin/plugin.json` — description drops pinned model versions.

## Files added

None.

## Line endings

Text files are normalised to UTF-8 with LF line endings.

## Re-syncing

Run `python tools/vendor_sync.py --apply`. It re-copies from the local marketplace clone and
re-applies every modification listed above from its declared table. It fails rather than
skipping if upstream has changed the text a modification targets.
