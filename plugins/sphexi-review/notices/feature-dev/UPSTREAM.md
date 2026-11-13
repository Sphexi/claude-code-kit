# UPSTREAM — `feature-dev`

| Field | Value |
|---|---|
| Plugin | `feature-dev` |
| Upstream marketplace | `claude-plugins-official` |
| Source repo | https://github.com/anthropics/claude-plugins-official |
| Source path | `plugins/feature-dev` |
| Upstream commit | `dceb15d50832e6adf380bedc26dde03d251324b9` |
| Commit provenance | content SHA (`.gcs-sha`; this marketplace is distributed as a GCS snapshot, not a git clone) |
| Upstream version | `1.0.1` |
| Retrieval date | 2026-11-10 |
| Upstream author | Anthropic |
| License | Apache-2.0 (`LICENSE` in this directory) |
| Deployed as | `sphexi-review` plugin (`plugins/sphexi-review/`) |

## Contents

- **agents** (3): `code-architect`, `code-explorer`, `code-reviewer`
- **commands** (1): `feature-dev`

## Stripped on the way in

Nothing — the upstream plugin contained no `.in_use/`, `__pycache__/`,
`.orphaned_at`, `tests/`, or `.github/` content.

## Not vendored

Nothing — every upstream component is carried.

## Collapsed into canonical copies

Nothing.

## Local modifications

Apart from the omissions above, the vendored copy diverges from upstream in exactly the
ways below. Everything else is byte-identical to the upstream repository's content.

- `agents/code-architect.md` — model set to `opus` per the tier table in `tools/vendor_sync.py` — judgement-heavy review, security and architecture on `opus`, implementers and routine analysis on `sonnet`. Upstream's value is overridden; nothing else in the file changed.

- `agents/code-reviewer.md` — model set to `opus` per the tier table in `tools/vendor_sync.py` — judgement-heavy review, security and architecture on `opus`, implementers and routine analysis on `sonnet`. Upstream's value is overridden; nothing else in the file changed.

- `agents/code-architect.md` — declared name changed to `feature-dev-code-architect`, with every bare reference in the plugin updated. Upstream's bare `code-architect` collides with `pr-review-toolkit`'s agent of the same name inside one bundle; the prefixed form matches the `<plugin>-<agent>` convention wshobson uses.

- `agents/code-architect.md` — `tools:` reduced to `Glob, Grep, Read, WebFetch, WebSearch`. Upstream lists LS, NotebookRead, TodoWrite, KillShell and BashOutput, which current Claude Code does not provide; the agent's job is read-only search either way.

- `agents/code-explorer.md` — declared name changed to `feature-dev-code-explorer`, with every bare reference in the plugin updated. Upstream's bare `code-explorer` collides with `pr-review-toolkit`'s agent of the same name inside one bundle; the prefixed form matches the `<plugin>-<agent>` convention wshobson uses.

- `agents/code-explorer.md` — `tools:` reduced to `Glob, Grep, Read, WebFetch, WebSearch`. Upstream lists LS, NotebookRead, TodoWrite, KillShell and BashOutput, which current Claude Code does not provide; the agent's job is read-only search either way.

- `agents/code-reviewer.md` — declared name changed to `feature-dev-code-reviewer`, with every bare reference in the plugin updated. Upstream's bare `code-reviewer` collides with `pr-review-toolkit`'s agent of the same name inside one bundle; the prefixed form matches the `<plugin>-<agent>` convention wshobson uses.

- `agents/code-reviewer.md` — `tools:` reduced to `Glob, Grep, Read, WebFetch, WebSearch`. Upstream lists LS, NotebookRead, TodoWrite, KillShell and BashOutput, which current Claude Code does not provide; the agent's job is read-only search either way.

Each modified Markdown file carries a notice that it was changed from the upstream version.

## Files added

None.

## Line endings

Text files are normalised to UTF-8 with LF line endings.

## Re-syncing

Run `python tools/vendor_sync.py --apply`. It re-copies from the local marketplace clone and
re-applies every modification listed above from its declared table. It fails rather than
skipping if upstream has changed the text a modification targets.
