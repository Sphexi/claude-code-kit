# UPSTREAM — `systems-programming`

| Field | Value |
|---|---|
| Plugin | `systems-programming` |
| Upstream marketplace | `claude-code-workflows` |
| Source repo | https://github.com/wshobson/agents |
| Source path | `plugins/systems-programming` |
| Upstream commit | `9c61ab243def98f72da12abd41cfcf5bcd91af9d` |
| Commit provenance | git commit SHA (`.git/refs/heads/main` of the local marketplace clone) |
| Upstream version | `1.2.4` |
| Retrieval date | 2026-11-10 |
| Upstream author | Seth Hobson |
| License | MIT (`LICENSE` in this directory) |
| Deployed as | `sphexi-languages` plugin (`plugins/sphexi-languages/`) |

## Contents

- **agents** (1): `golang-pro`
- **skills** (3): `go-concurrency-patterns`, `memory-safety-patterns`, `rust-async-patterns`

## Stripped on the way in

- `.codex-plugin/plugin.json`

## Not vendored

Left upstream by the `SELECTION` table in `tools/vendor_sync.py`:

- `agents/c-pro`
- `agents/cpp-pro`
- `agents/rust-pro`
- `commands/rust-project`

## Collapsed into canonical copies

Nothing.

## Local modifications

Apart from the omissions above, the vendored copy diverges from upstream in exactly the
ways below. Everything else is byte-identical to the upstream repository's content.

- `agents/golang-pro.md` — model set to `sonnet` per the tier table in `tools/vendor_sync.py` — judgement-heavy review, security and architecture on `opus`, implementers and routine analysis on `sonnet`. Upstream's value is overridden; nothing else in the file changed.

## Files added

None.

## Line endings

Text files are normalised to UTF-8 with LF line endings.

## Re-syncing

Run `python tools/vendor_sync.py --apply`. It re-copies from the local marketplace clone and
re-applies every modification listed above from its declared table. It fails rather than
skipping if upstream has changed the text a modification targets.
