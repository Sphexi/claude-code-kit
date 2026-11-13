# UPSTREAM — `cicd-automation`

| Field | Value |
|---|---|
| Plugin | `cicd-automation` |
| Upstream marketplace | `claude-code-workflows` |
| Source repo | https://github.com/wshobson/agents |
| Source path | `plugins/cicd-automation` |
| Upstream commit | `9c61ab243def98f72da12abd41cfcf5bcd91af9d` |
| Commit provenance | git commit SHA (`.git/refs/heads/main` of the local marketplace clone) |
| Upstream version | `1.2.4` |
| Retrieval date | 2026-11-10 |
| Upstream author | Seth Hobson |
| License | MIT (`LICENSE` in this directory) |
| Deployed as | `sphexi-infra` plugin (`plugins/sphexi-infra/`) |

## Contents

- **agents** (1): `devops-troubleshooter`
- **commands** (1): `workflow-automate`
- **skills** (4): `deployment-pipeline-design`, `github-actions-templates`, `gitlab-ci-patterns`, `secrets-management`

## Stripped on the way in

- `.codex-plugin/plugin.json`

## Not vendored

Nothing — every upstream component is carried.

## Collapsed into canonical copies

Dropped by the `COLLAPSE` table in `tools/vendor_sync.py`:

- `agents/cloud-architect.md` — identical to `cloud-infrastructure`'s copy apart from its `name:` line; dropped, and 0 reference(s) to `cicd-automation-cloud-architect` retargeted to `cloud-infrastructure-cloud-architect`. Where a retargeted command told the model to use only local agents, that instruction now names the canonical agent as allowed.
- `agents/deployment-engineer.md` — identical to `cloud-infrastructure`'s copy apart from its `name:` line; dropped, and 0 reference(s) to `cicd-automation-deployment-engineer` retargeted to `cloud-infrastructure-deployment-engineer`. Where a retargeted command told the model to use only local agents, that instruction now names the canonical agent as allowed.
- `agents/kubernetes-architect.md` — identical to `cloud-infrastructure`'s copy apart from its `name:` line; dropped, and 0 reference(s) to `cicd-automation-kubernetes-architect` retargeted to `cloud-infrastructure-kubernetes-architect`. Where a retargeted command told the model to use only local agents, that instruction now names the canonical agent as allowed.
- `agents/terraform-specialist.md` — identical to `cloud-infrastructure`'s copy apart from its `name:` line; dropped, and 0 reference(s) to `cicd-automation-terraform-specialist` retargeted to `cloud-infrastructure-terraform-specialist`. Where a retargeted command told the model to use only local agents, that instruction now names the canonical agent as allowed.

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
