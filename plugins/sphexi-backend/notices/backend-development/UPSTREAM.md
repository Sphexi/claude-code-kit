# UPSTREAM — `backend-development`

| Field | Value |
|---|---|
| Plugin | `backend-development` |
| Upstream marketplace | `claude-code-workflows` |
| Source repo | https://github.com/wshobson/agents |
| Source path | `plugins/backend-development` |
| Upstream commit | `9c61ab243def98f72da12abd41cfcf5bcd91af9d` |
| Commit provenance | git commit SHA (`.git/refs/heads/main` of the local marketplace clone) |
| Upstream version | `1.3.3` |
| Retrieval date | 2026-11-10 |
| Upstream author | Seth Hobson |
| License | MIT (`LICENSE` in this directory) |
| Deployed as | `sphexi-backend` plugin (`plugins/sphexi-backend/`) |

## Contents

- **agents** (7): `backend-architect`, `event-sourcing-architect`, `graphql-architect`, `performance-engineer`, `security-auditor`, `temporal-python-pro`, `test-automator`
- **commands** (1): `feature-development`
- **skills** (9): `api-design-principles`, `architecture-patterns`, `cqrs-implementation`, `event-store-design`, `microservices-patterns`, `projection-patterns`, `saga-orchestration`, `temporal-python-testing`, `workflow-orchestration-patterns`

## Stripped on the way in

- `.codex-plugin/plugin.json`

## Not vendored

Nothing — every upstream component is carried.

## Collapsed into canonical copies

Dropped by the `COLLAPSE` table in `tools/vendor_sync.py`:

- `agents/tdd-orchestrator.md` — identical to `tdd-workflows`'s copy apart from its `name:` line; dropped, and 0 reference(s) to `backend-development-tdd-orchestrator` retargeted to `tdd-workflows-tdd-orchestrator`. Where a retargeted command told the model to use only local agents, that instruction now names the canonical agent as allowed.

## Local modifications

Apart from the omissions above, the vendored copy diverges from upstream in exactly the
ways below. Everything else is byte-identical to the upstream repository's content.

- `agents/backend-architect.md` — model set to `opus` per the tier table in `tools/vendor_sync.py` — judgement-heavy review, security and architecture on `opus`, implementers and routine analysis on `sonnet`. Upstream's value is overridden; nothing else in the file changed.

- `agents/event-sourcing-architect.md` — model set to `opus` per the tier table in `tools/vendor_sync.py` — judgement-heavy review, security and architecture on `opus`, implementers and routine analysis on `sonnet`. Upstream's value is overridden; nothing else in the file changed.

- `agents/temporal-python-pro.md` — model set to `sonnet` per the tier table in `tools/vendor_sync.py` — judgement-heavy review, security and architecture on `opus`, implementers and routine analysis on `sonnet`. Upstream's value is overridden; nothing else in the file changed.

## Files added

None.

## Line endings

Text files are normalised to UTF-8 with LF line endings.

## Re-syncing

Run `python tools/vendor_sync.py --apply`. It re-copies from the local marketplace clone and
re-applies every modification listed above from its declared table. It fails rather than
skipping if upstream has changed the text a modification targets.
