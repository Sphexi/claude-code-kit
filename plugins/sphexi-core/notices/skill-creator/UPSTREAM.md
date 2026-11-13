# UPSTREAM — `skill-creator`

| Field | Value |
|---|---|
| Plugin | `skill-creator` |
| Upstream marketplace | `claude-plugins-official` |
| Source repo | https://github.com/anthropics/claude-plugins-official |
| Source path | `plugins/skill-creator` |
| Upstream commit | `dceb15d50832e6adf380bedc26dde03d251324b9` |
| Commit provenance | content SHA (`.gcs-sha`; this marketplace is distributed as a GCS snapshot, not a git clone) |
| Upstream version | none declared — Claude Code resolves this plugin's version to the commit above |
| Retrieval date | 2026-11-10 |
| Upstream author | Anthropic |
| License | Apache-2.0 (`LICENSE` in this directory) |
| Deployed as | `sphexi-core` plugin (`plugins/sphexi-core/`) |

## Contents

- **skills** (1): `skill-creator`

## Stripped on the way in

Nothing — the upstream plugin contained no `.in_use/`, `__pycache__/`,
`.orphaned_at`, `tests/`, or `.github/` content.

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
