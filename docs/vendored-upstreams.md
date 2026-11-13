# Vendored upstreams

Most plugin content in the kit is copied from two upstream repositories at pinned commits. This page is for maintainers who re-sync that content. For what is vendored, which components are custom, and each component's source and license, see the generated catalogue: [plugins.md](plugins.md).

## Sources

| Source key | Repository | License |
|---|---|---|
| `claude-code-workflows` | https://github.com/wshobson/agents | MIT |
| `claude-plugins-official` | https://github.com/anthropics/claude-plugins-official | Apache-2.0 |

Thirty-one plugins are vendored into `claude/vendor/<plugin>/`, one directory per upstream plugin. Twenty-nine are assigned to a marketplace plugin by `build/bundles.py`; `pyright-lsp` and `security-guidance` are extras that ship only through `deploy --extra`.

## The rule

`claude/vendor/` is written only by `tools/vendor_sync.py`. A hand edit is overwritten on the next sync. Every divergence from upstream is an entry in one of the script's tables, and a sync reproduces them deterministically.

Nothing at run time depends on upstream clones. They are a maintainer convenience.

## Running a sync

The script needs one local clone per source key, in a directory named for the key. By default it looks under `~/.claude/plugins/marketplaces/`; use `--marketplaces DIR` for another location. It never uses the network. A pin is read from the clone: the `main` ref of a git clone, or a `.gcs-sha` file for a snapshot.

```bash
python tools/vendor_sync.py                          # dry run: report, change nothing
python tools/vendor_sync.py --apply                  # re-vendor every plugin
python tools/vendor_sync.py --apply --only pr-review-toolkit
python tools/vendor_sync.py --apply --marketplaces /path/to/clones
python tools/vendor_sync.py --render-upstream        # rewrite provenance files only
```

| Option | Effect |
|---|---|
| `--apply` | Write changes. Without it the script reports only |
| `--only PLUGIN` | Restrict to one plugin. Repeatable |
| `--date DATE` | Retrieval date recorded in `UPSTREAM.md`. Default: today |
| `--marketplaces DIR` | Directory holding one clone per source key |
| `--render-upstream` | Rewrite `LICENSE` files, modified-file notices, every `UPSTREAM.md` and the manifest from the vendored content. Needs no clones |

After an apply, regenerate the rest in order: `python build/inline_shared.py`, then `python build/build_plugins.py`. See [customizing.md](customizing.md).

## The tables

Each plugin is copied, noise is stripped (test directories, caches, editor files), and then the tables in `tools/vendor_sync.py` apply:

| Table | Purpose |
|---|---|
| `SELECTION` | Keep-lists of agents, skills and commands for plugins vendored in part. A plugin absent from the table is vendored whole |
| `COLLAPSE` | An agent that upstream ships identically under several plugins is kept in one owner plugin and dropped from the rest. References to the dropped name are retargeted to the owner's name |
| `TIERS` | Explicit model for each agent whose upstream value is `inherit` or differs from the kit's. Judgement-heavy review, security and architecture agents use `opus`; implementers and routine analysis use `sonnet` |
| `DESCRIPTIONS` | Shortened descriptions for agents whose upstream description is long or carries worked examples, because descriptions load into every session |
| `MODIFICATIONS` | Every other change: a frontmatter field, an agent rename, an inserted note, a dropped file, a text or line replacement, or a written file |

Each entry carries a reason that is reproduced in the plugin's `UPSTREAM.md`.

## Failing loudly

The sync exits with an error rather than guessing when:

- a `SELECTION` entry names a component upstream no longer ships
- a collapsed copy has diverged from its owner's copy apart from the `name:` line
- the text a modification targets has moved or is ambiguous
- an agent's frontmatter field that a modification sets is missing
- a plugin has no license and the source offers none to copy
- a license text is neither MIT nor Apache-2.0

When a modification fails, fix the entry. Do not loosen the check.

## License duties

- Every vendored plugin carries a `LICENSE`. If upstream ships none in the plugin, the source repository's root license is copied in. The SPDX id is read from the first lines of the text and recorded in the manifest.
- Every file changed in an Apache-2.0 plugin carries a notice directly after its frontmatter, or at the top: `<!-- Modified from the upstream version; changes are listed in UPSTREAM.md. -->`. Files the kit adds, such as a plugin manifest that upstream lacks, are listed in `UPSTREAM.md` as added; JSON has no comment syntax for an in-file notice.
- Every plugin directory carries an `UPSTREAM.md` recording the source repository, source path, pinned commit, upstream version, retrieval date, author, license, contents, what was stripped or not vendored, what was collapsed, and every local modification.
- `THIRD_PARTY_NOTICES.md` is generated from the manifest at `claude/plugins.manifest.json`: a section per source, a table per plugin, the Apache-2.0 statement and the list of adapted and external content.
- A generated marketplace plugin carries each member's `LICENSE` and `UPSTREAM.md` under `notices/<member>/`, and its `plugin.json` license is the SPDX `AND` of the members' licenses.

Do not vendor anything whose license forbids redistribution. Content that must track a live upstream stays an external entry in the `external` list of `build/kit.json`.

## Adding a plugin

1. Add its name and source key to `tools/vendor_sync.py`.
2. Assign it to a bundle, or to `EXTRAS`, in `build/bundles.py`.
3. Add any `SELECTION`, `COLLAPSE`, `TIERS`, `DESCRIPTIONS` or `MODIFICATIONS` entries it needs; every upstream `inherit` model needs a `TIERS` entry.
4. Run `python tools/vendor_sync.py --apply --only <plugin>`, then the regeneration commands above.
