# UPSTREAM — `python-development`

| Field | Value |
|---|---|
| Plugin | `python-development` |
| Upstream marketplace | `claude-code-workflows` |
| Source repo | https://github.com/wshobson/agents |
| Source path | `plugins/python-development` |
| Upstream commit | `9c61ab243def98f72da12abd41cfcf5bcd91af9d` |
| Commit provenance | git commit SHA (`.git/refs/heads/main` of the local marketplace clone) |
| Upstream version | `1.2.4` |
| Retrieval date | 2026-11-10 |
| Upstream author | Seth Hobson |
| License | MIT (`LICENSE` in this directory) |
| Deployed as | `sphexi-python` plugin (`plugins/sphexi-python/`) |

## Contents

- **agents** (3): `django-pro`, `fastapi-pro`, `python-pro`
- **commands** (1): `python-scaffold`
- **skills** (16): `async-python-patterns`, `python-anti-patterns`, `python-background-jobs`, `python-code-style`, `python-configuration`, `python-design-patterns`, `python-error-handling`, `python-observability`, `python-packaging`, `python-performance-optimization`, `python-project-structure`, `python-resilience`, `python-resource-management`, `python-testing-patterns`, `python-type-safety`, `uv-package-manager`

## Stripped on the way in

- `.codex-plugin/plugin.json`

## Not vendored

Nothing — every upstream component is carried.

## Collapsed into canonical copies

Nothing.

## Local modifications

Apart from the omissions above, the vendored copy diverges from upstream in exactly the
ways below. Everything else is byte-identical to the upstream repository's content.

- `agents/django-pro.md` — model set to `sonnet` per the tier table in `tools/vendor_sync.py` — judgement-heavy review, security and architecture on `opus`, implementers and routine analysis on `sonnet`. Upstream's value is overridden; nothing else in the file changed.

- `agents/fastapi-pro.md` — model set to `sonnet` per the tier table in `tools/vendor_sync.py` — judgement-heavy review, security and architecture on `opus`, implementers and routine analysis on `sonnet`. Upstream's value is overridden; nothing else in the file changed.

- `agents/python-pro.md` — model set to `sonnet` per the tier table in `tools/vendor_sync.py` — judgement-heavy review, security and architecture on `opus`, implementers and routine analysis on `sonnet`. Upstream's value is overridden; nothing else in the file changed.

## Files added

None.

## Line endings

Text files are normalised to UTF-8 with LF line endings.

## Re-syncing

Run `python tools/vendor_sync.py --apply`. It re-copies from the local marketplace clone and
re-applies every modification listed above from its declared table. It fails rather than
skipping if upstream has changed the text a modification targets.
