# UPSTREAM — `full-stack-orchestration`

| Field | Value |
|---|---|
| Plugin | `full-stack-orchestration` |
| Upstream marketplace | `claude-code-workflows` |
| Source repo | https://github.com/wshobson/agents |
| Source path | `plugins/full-stack-orchestration` |
| Upstream commit | `9c61ab243def98f72da12abd41cfcf5bcd91af9d` |
| Commit provenance | git commit SHA (`.git/refs/heads/main` of the local marketplace clone) |
| Upstream version | `1.3.2` |
| Retrieval date | 2026-11-10 |
| Upstream author | Seth Hobson |
| License | MIT (`LICENSE` in this directory) |
| Deployed as | `sphexi-backend` plugin (`plugins/sphexi-backend/`) |

## Contents

- **commands** (1): `full-stack-feature`

## Stripped on the way in

Nothing — the upstream plugin contained no `.in_use/`, `__pycache__/`,
`.orphaned_at`, `tests/`, or `.github/` content.

## Not vendored

Nothing — every upstream component is carried.

## Collapsed into canonical copies

Dropped by the `COLLAPSE` table in `tools/vendor_sync.py`:

- `agents/deployment-engineer.md` — identical to `cloud-infrastructure`'s copy apart from its `name:` line; dropped, and 1 reference(s) to `full-stack-orchestration-deployment-engineer` retargeted to `cloud-infrastructure-deployment-engineer`. Where a retargeted command told the model to use only local agents, that instruction now names the canonical agent as allowed.
- `agents/performance-engineer.md` — identical to `performance-testing-review`'s copy apart from its `name:` line; dropped, and 1 reference(s) to `full-stack-orchestration-performance-engineer` retargeted to `performance-testing-review-performance-engineer`. Where a retargeted command told the model to use only local agents, that instruction now names the canonical agent as allowed.
- `agents/security-auditor.md` — identical to `security-scanning`'s copy apart from its `name:` line; dropped, and 1 reference(s) to `full-stack-orchestration-security-auditor` retargeted to `security-scanning-security-auditor`. Where a retargeted command told the model to use only local agents, that instruction now names the canonical agent as allowed.
- `agents/test-automator.md` — identical to `unit-testing`'s copy apart from its `name:` line; dropped, and 1 reference(s) to `full-stack-orchestration-test-automator` retargeted to `unit-testing-test-automator`. Where a retargeted command told the model to use only local agents, that instruction now names the canonical agent as allowed.

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
