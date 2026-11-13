# UPSTREAM — `api-scaffolding`

| Field | Value |
|---|---|
| Plugin | `api-scaffolding` |
| Upstream marketplace | `claude-code-workflows` |
| Source repo | https://github.com/wshobson/agents |
| Source path | `plugins/api-scaffolding` |
| Upstream commit | `9c61ab243def98f72da12abd41cfcf5bcd91af9d` |
| Commit provenance | git commit SHA (`.git/refs/heads/main` of the local marketplace clone) |
| Upstream version | `1.2.4` |
| Retrieval date | 2026-11-10 |
| Upstream author | Seth Hobson |
| License | MIT (`LICENSE` in this directory) |
| Deployed as | `sphexi-backend` plugin (`plugins/sphexi-backend/`) |

## Contents

- **skills** (1): `fastapi-templates`

## Stripped on the way in

- `.codex-plugin/plugin.json`

## Not vendored

Nothing — every upstream component is carried.

## Collapsed into canonical copies

Dropped by the `COLLAPSE` table in `tools/vendor_sync.py`:

- `agents/backend-architect.md` — identical to `backend-development`'s copy apart from its `name:` line; dropped, and 0 reference(s) to `api-scaffolding-backend-architect` retargeted to `backend-development-backend-architect`. Where a retargeted command told the model to use only local agents, that instruction now names the canonical agent as allowed.
- `agents/django-pro.md` — identical to `python-development`'s copy apart from its `name:` line; dropped, and 0 reference(s) to `api-scaffolding-django-pro` retargeted to `python-development-django-pro`. Where a retargeted command told the model to use only local agents, that instruction now names the canonical agent as allowed.
- `agents/fastapi-pro.md` — identical to `python-development`'s copy apart from its `name:` line; dropped, and 0 reference(s) to `api-scaffolding-fastapi-pro` retargeted to `python-development-fastapi-pro`. Where a retargeted command told the model to use only local agents, that instruction now names the canonical agent as allowed.
- `agents/graphql-architect.md` — identical to `backend-development`'s copy apart from its `name:` line; dropped, and 0 reference(s) to `api-scaffolding-graphql-architect` retargeted to `backend-development-graphql-architect`. Where a retargeted command told the model to use only local agents, that instruction now names the canonical agent as allowed.

## Local modifications

None. The vendored copy is byte-identical to the upstream repository's content.

## Files added

None.

## Line endings

Text files are normalised to UTF-8 with LF line endings.

## Re-syncing

Run `python tools/vendor_sync.py --apply`. It re-copies from the local marketplace clone and
re-applies every modification listed above from its declared table. It fails rather than
skipping if upstream has changed the text a modification targets.
