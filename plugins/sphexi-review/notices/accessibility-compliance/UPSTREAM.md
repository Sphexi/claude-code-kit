# UPSTREAM — `accessibility-compliance`

| Field | Value |
|---|---|
| Plugin | `accessibility-compliance` |
| Upstream marketplace | `claude-code-workflows` |
| Source repo | https://github.com/wshobson/agents |
| Source path | `plugins/accessibility-compliance` |
| Upstream commit | `9c61ab243def98f72da12abd41cfcf5bcd91af9d` |
| Commit provenance | git commit SHA (`.git/refs/heads/main` of the local marketplace clone) |
| Upstream version | `1.2.4` |
| Retrieval date | 2026-11-10 |
| Upstream author | Seth Hobson |
| License | MIT (`LICENSE` in this directory) |
| Deployed as | `sphexi-review` plugin (`plugins/sphexi-review/`) |

## Contents

- **agents** (1): `ui-visual-validator`
- **commands** (1): `accessibility-audit`
- **skills** (2): `screen-reader-testing`, `wcag-audit-patterns`

## Stripped on the way in

- `.codex-plugin/plugin.json`

## Not vendored

Nothing — every upstream component is carried.

## Collapsed into canonical copies

Nothing.

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
