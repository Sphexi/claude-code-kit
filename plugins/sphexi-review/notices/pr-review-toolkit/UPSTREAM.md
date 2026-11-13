# UPSTREAM — `pr-review-toolkit`

| Field | Value |
|---|---|
| Plugin | `pr-review-toolkit` |
| Upstream marketplace | `claude-plugins-official` |
| Source repo | https://github.com/anthropics/claude-plugins-official |
| Source path | `plugins/pr-review-toolkit` |
| Upstream commit | `dceb15d50832e6adf380bedc26dde03d251324b9` |
| Commit provenance | content SHA (`.gcs-sha`; this marketplace is distributed as a GCS snapshot, not a git clone) |
| Upstream version | `1.0.1` |
| Retrieval date | 2026-11-10 |
| Upstream author | Anthropic |
| License | Apache-2.0 (`LICENSE` in this directory) |
| Deployed as | `sphexi-review` plugin (`plugins/sphexi-review/`) |

## Contents

- **agents** (6): `code-reviewer`, `code-simplifier`, `comment-analyzer`, `pr-test-analyzer`, `silent-failure-hunter`, `type-design-analyzer`
- **commands** (1): `review-pr`

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

- `agents/code-simplifier.md` — model set to `sonnet` per the tier table in `tools/vendor_sync.py` — judgement-heavy review, security and architecture on `opus`, implementers and routine analysis on `sonnet`. Upstream's value is overridden; nothing else in the file changed.

- `agents/comment-analyzer.md` — model set to `sonnet` per the tier table in `tools/vendor_sync.py` — judgement-heavy review, security and architecture on `opus`, implementers and routine analysis on `sonnet`. Upstream's value is overridden; nothing else in the file changed.

- `agents/pr-test-analyzer.md` — model set to `sonnet` per the tier table in `tools/vendor_sync.py` — judgement-heavy review, security and architecture on `opus`, implementers and routine analysis on `sonnet`. Upstream's value is overridden; nothing else in the file changed.

- `agents/silent-failure-hunter.md` — model set to `opus` per the tier table in `tools/vendor_sync.py` — judgement-heavy review, security and architecture on `opus`, implementers and routine analysis on `sonnet`. Upstream's value is overridden; nothing else in the file changed.

- `agents/type-design-analyzer.md` — model set to `opus` per the tier table in `tools/vendor_sync.py` — judgement-heavy review, security and architecture on `opus`, implementers and routine analysis on `sonnet`. Upstream's value is overridden; nothing else in the file changed.

- `agents/code-reviewer.md` — description shortened to its triggers. Upstream's description runs to several sentences; descriptions load into every session. The agent body is untouched.

- `agents/code-simplifier.md` — description shortened to its triggers. Upstream's is a block scalar carrying three worked `<example>` transcripts; descriptions load into every session. The agent body is untouched.

- `agents/comment-analyzer.md` — description shortened to its triggers. Upstream's description runs to several sentences; descriptions load into every session. The agent body is untouched.

- `agents/pr-test-analyzer.md` — description shortened to its triggers. Upstream's description runs to several sentences; descriptions load into every session. The agent body is untouched.

- `agents/silent-failure-hunter.md` — description shortened to its triggers. Upstream's is a single-line scalar holding literal `\n` escapes, so its worked examples rendered as one unbroken run of text, and all three use a named individual as the example user; descriptions load into every session. The agent body is untouched.

- `agents/type-design-analyzer.md` — description shortened to its triggers. Upstream's description runs to several sentences; descriptions load into every session. The agent body is untouched.

- `agents/code-simplifier.md` — removed another project's hardcoded house style. It mandated ES modules, `function` over arrow functions, explicit return types, React `Props` types, and avoiding try/catch, *while claiming to follow CLAUDE.md* — wrong for any project that is not that JavaScript codebase. Now defers to the project's `CLAUDE.md` and states that the agent has no house style of its own.

Each modified Markdown file carries a notice that it was changed from the upstream version.

## Files added

None.

## Line endings

Text files are normalised to UTF-8 with LF line endings.

## Re-syncing

Run `python tools/vendor_sync.py --apply`. It re-copies from the local marketplace clone and
re-applies every modification listed above from its declared table. It fails rather than
skipping if upstream has changed the text a modification targets.
