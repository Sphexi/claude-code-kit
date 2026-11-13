# UPSTREAM — `pyright-lsp`

| Field | Value |
|---|---|
| Plugin | `pyright-lsp` |
| Upstream marketplace | `claude-plugins-official` |
| Source repo | https://github.com/anthropics/claude-plugins-official |
| Source path | `plugins/pyright-lsp` |
| Upstream commit | `dceb15d50832e6adf380bedc26dde03d251324b9` |
| Commit provenance | content SHA (`.gcs-sha`; this marketplace is distributed as a GCS snapshot, not a git clone) |
| Upstream version | `1.0.0` |
| Retrieval date | 2026-11-10 |
| Upstream author | Anthropic |
| License | Apache-2.0 (`LICENSE` in this directory) |
| Deployed as | optional extra — installed only with `deploy --extra pyright-lsp` |

## Contents

- **lspServers** (1): `pyright`

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

- `.claude-plugin/plugin.json` — **authored here; upstream has none.** This plugin ships only a `LICENSE` and a `README`: its entire substance is the `lspServers` block in the marketplace catalogue entry, which a vendored copy cannot carry. The block was transcribed from that entry into an inline `lspServers` field; the author contact address is omitted. Without this file the directory is not a plugin. The language server itself is still a separate install (`pyright-langserver` must be on PATH).

Each modified Markdown file carries a notice that it was changed from the upstream version.

## Files added

- `.claude-plugin/plugin.json`

## Line endings

Text files are normalised to UTF-8 with LF line endings.

## Re-syncing

Run `python tools/vendor_sync.py --apply`. It re-copies from the local marketplace clone and
re-applies every modification listed above from its declared table. It fails rather than
skipping if upstream has changed the text a modification targets.
