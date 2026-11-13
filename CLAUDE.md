# CLAUDE.md — claude-code-kit

Rules for working **on** this repository. Nothing here is deployed to users.

## What This Repo Is

`claude-code-kit` packages a set of Claude Code agents, skills, output styles and curated
third-party plugins, and installs them into an existing Claude Code setup. It has two
consumers, both fed from the same generated tree:

1. **Marketplace (primary).** `.claude-plugin/marketplace.json` lists eight plugins served
   from `plugins/` — `sphexi-core`, `sphexi-review`, `sphexi-security`, `sphexi-python`,
   `sphexi-languages`, `sphexi-backend`, `sphexi-infra`, `sphexi-ai` — plus one external
   entry, `twingate-assistant`, fetched from its own repository. Users run
   `/plugin marketplace add sphexi/claude-code-kit` and install what they want as
   `<plugin>@sphexi`, for example `sphexi-review@sphexi`.
2. **Clone and deploy.** `deploy.sh` / `deploy.ps1` write the same content into `~/.claude`,
   together with the global `CLAUDE.md` and merged `settings.json` that a plugin cannot carry.
   `refresh.sh` / `refresh.ps1` reconcile a machine against the clone afterwards.

Cowork zips are a third consumer, built from `plugins/` at release time.

Linux, macOS and Windows are all supported for clone-and-deploy. Bash covers Linux and macOS,
PowerShell covers Windows, and all behaviour lives in one Python 3.12+ engine.

## Layout

```
.claude-plugin/marketplace.json  GENERATED
plugins/sphexi-<name>/           GENERATED — marketplace plugin roots; deploy reads these too
THIRD_PARTY_NOTICES.md           GENERATED
docs/plugins.md                  GENERATED
build/
  kit.json                       identity, version, external marketplace entries
  bundles.py                     which vendored plugin goes in which bundle
  inline_shared.py               shared/ blocks → marked payload files
  build_plugins.py               claude/ + shared/ → every GENERATED path; Cowork zips
  templates/                     README and catalogue templates
claude/                          SOURCE payload
  global-CLAUDE.md               → ~/.claude/CLAUDE.md on deploy
  settings.base.json             + settings.{linux,macos,windows}.json → merged settings.json
  agents/ output-styles/ skills/ authored content
  vendor/<plugin>/               third-party plugins, one per upstream plugin; vendor_sync only
  plugins.manifest.json          written by tools/vendor_sync.py
cowork/                          overlay added to the core Cowork zip only
shared/                          canonical prose blocks inlined into the payload
tools/
  payload.py                     the only repo-path → live-path table
  state.py                       ~/.claude/claude-code-kit-state.json
  deploy.py                      deploy and uninstall engine
  reconcile/                     refresh engine (three-way diff against the state file)
  vendor_sync.py                 the only writer of claude/vendor/ and the manifest
scripts/lib.sh, scripts/lib.ps1  logging and Python discovery for the wrappers
deploy.sh deploy.ps1 refresh.sh refresh.ps1   thin wrappers, no logic
tests/python/                    pytest suite
docs/                            user and maintainer documentation
```

`claude/global-CLAUDE.md` is deliberately not named `CLAUDE.md`: under that name Claude Code
would load it as a nested memory file whenever a session touches `claude/`, injecting
user-scope rules into work on this repo.

## How Content Flows

```
shared/*.md ──inline_shared.py──▶ claude/{agents,output-styles,global-CLAUDE.md}
upstream clones ──vendor_sync.py──▶ claude/vendor/ + claude/plugins.manifest.json
claude/ + shared/ + build/kit.json ──build_plugins.py──▶ plugins/, marketplace.json,
                                                          THIRD_PARTY_NOTICES.md, docs/plugins.md
plugins/ ──marketplace──▶ users' plugin cache
plugins/ + claude/global-CLAUDE.md + claude/settings.* ──tools/payload.py──▶ deploy, refresh
plugins/ + cowork/ ──build_plugins.py --zip──▶ dist/*.zip
```

- **Bundles.** Every vendored plugin belongs to exactly one bundle in `build/bundles.py`, or
  to `EXTRAS` (`pyright-lsp`, `security-guidance`), which ship only through
  `deploy --extra NAME`. The build fails on an unassigned plugin, a name collision inside a
  bundle, or a `subagent_type` reference that resolves neither in the bundle, its declared
  dependencies, `sphexi-core`, nor the built-in agents.
- **Core.** `plugins/sphexi-core` holds the 13 agents, the authored skills plus vendored
  `skill-creator`, the three output styles, and a SessionStart hook that prints the code
  standards. Deploy installs core's agents, skills and output styles as user-level files and
  never installs the hook — the deployed global `CLAUDE.md` already carries those standards.
- **Hook payload size.** SessionStart output is capped at 10,000 characters per hook string,
  so the build splits each payload at `## ` headings into chunks of at most 9,500 characters,
  one hook command per chunk, and fails if a single section exceeds that.
- **Versions.** `build/kit.json` `version` is stamped into every generated `plugin.json`.
  Users receive an update only when it changes. `docs/releasing.md` has the release steps.

## Commands

```bash
python build/inline_shared.py              # regenerate inlined shared blocks
python build/inline_shared.py --check      # exit 1 if any target is stale
python build/build_plugins.py              # regenerate every GENERATED path
python build/build_plugins.py --check      # exit 1 on drift; writes nothing
python build/build_plugins.py --zip        # Cowork zips → dist/
python -m pytest tests/python -q           # fast suite
python -m pytest tests/python -q -m slow   # smoke deploy through the platform wrapper
python tools/vendor_sync.py                # dry run against local upstream clones
python tools/vendor_sync.py --apply        # re-vendor and re-apply declared modifications
python tools/vendor_sync.py --render-upstream   # rewrite UPSTREAM.md + manifest only
./deploy.sh --config-dir /tmp/claude-test           # dry run into a scratch dir
./deploy.sh --config-dir /tmp/claude-test --apply
./refresh.sh --config-dir /tmp/claude-test
```

Exercise deploy and refresh against a scratch `--config-dir`, never your own `~/.claude`.

## Generated Files

`plugins/`, `.claude-plugin/marketplace.json`, `THIRD_PARTY_NOTICES.md`, `docs/plugins.md`,
every region between `<!-- TERSENESS:START/END -->` or `<!-- CODE-STANDARDS:START/END -->`
markers, `claude/plugins.manifest.json`, and every `claude/vendor/*/UPSTREAM.md` are
generated. Never edit them by hand: change the source, regenerate, and commit source and
output together. CI runs both `--check` commands, and a change that leaves either stale fails.

Order matters when several sources change: `vendor_sync.py` → `inline_shared.py` →
`build_plugins.py`.

## Vendored Content

- `claude/vendor/` is written only by `tools/vendor_sync.py`. A hand edit is overwritten on
  the next sync.
- Every divergence from upstream is an entry in one of its tables — `SELECTION`, `COLLAPSE`,
  `TIERS`, `DESCRIPTIONS`, `MODIFICATIONS`. A modification whose target text has moved
  upstream fails the sync; fix the entry, never weaken the check.
- Every vendored plugin carries a `LICENSE` (the upstream repository's root license is copied
  in when the plugin has none) and an `UPSTREAM.md` recording source repo, pinned commit,
  retrieval date, license, and every local modification and added file.
- Files changed in an Apache-2.0 plugin carry an in-file notice that they were modified, and
  are listed in `UPSTREAM.md` and `THIRD_PARTY_NOTICES.md`. Apache-2.0 requires both.
- Do not vendor anything whose license forbids redistribution. Content that must track a
  live upstream stays an external marketplace entry in `build/kit.json`.
- Upstream clones are a maintainer convenience, read from `~/.claude/plugins/marketplaces/`
  or `--marketplaces DIR`. Nothing at runtime depends on them.

## Shared Blocks

`shared/terseness-main.md`, `shared/terseness-subagent.md` and `shared/code-standards.md` are
the only sources of that prose. Targets are discovered by marker presence; files under an
`agents/` directory get the subagent variant. The code standards reach users three ways —
the global `CLAUDE.md`, every agent, and the core SessionStart hook (plus the Cowork zip) —
and all three must stay wired. A skill is not a path: it loads only when triggered.

The terseness levels vary how much explanation survives; the register rules (no agreement
tokens, no graded findings, no teasers, no narration of one's own conduct, no same-turn
repetition) hold at every level. Name behaviours, not vocabulary, and keep the carve-out for
working narration between tool calls wherever those rules appear.

## Deploy and Settings Rules

- **One layout table.** `tools/payload.py` is the only place a repo path maps to a live path.
  Deploy, refresh and the smoke test all call it.
- **Kit-owned only.** Deploy and refresh may modify or remove a live file only when the state
  file records it and its current hash matches the recorded hash. Everything else is a
  conflict (skipped unless `--overwrite`, which backs up first) or unmanaged (never removed).
- **Merge, never replace.** Settings are composed from base plus the OS overlay, then merged
  into the live file: list entries are unioned, existing user keys and scalars win, and every
  addition is recorded in the state file so `--uninstall` can reverse it.
- **Conservative defaults.** `claude/settings.base.json` sets no model, no permission mode
  and no allow rules. The deny list holds only operations that must never run anywhere:
  Claude Code evaluates deny before allow and no narrower scope can override a global deny,
  so a conditional rule placed there could never be lifted.
- **Platform-neutral payload.** Only `settings.{linux,macos,windows}.json` may name a
  platform path, drive letter or shell.
- **No marketplace writes.** Deploy reads `installed_plugins.json` and `enabledPlugins` to
  warn about duplicates; it never edits plugin state, caches or marketplace registrations.

### Destructive Operation Rule

Any code path that removes, overwrites or truncates a file under a live config directory must:

1. Be reachable only with `--apply`.
2. Have a test proving it does nothing without `--apply`.
3. Print the full absolute path of every affected file before acting.

### Platform Testing Rule

A change to deploy, refresh, the wrappers or settings composition states which of Linux, macOS
and Windows it was actually run on and which were only reasoned about. Name all three, even
when the answer is "not run". A change run on one platform and reasoned about on the others is
incomplete until CI's smoke job has run on all three.

## Code Style

### Python (`build/`, `tools/`, `tests/`)

- Python 3.12+, standard library only in shipped code. `pytest` is the only dev dependency.
- Modern type hints on every signature; `pathlib.Path`, never string path concatenation;
  `argparse`; explicit `encoding="utf-8"` and `newline="\n"` on every text write.
- Generated output is deterministic: sorted iteration, `json.dumps(indent=2,
  ensure_ascii=False)` plus a trailing newline, no timestamps outside `UPSTREAM.md` and the
  manifest.
- Name comparisons that decide collisions use `str.casefold()` — macOS and Windows
  filesystems are case-insensitive.

### Bash (`*.sh`, `scripts/lib.sh`)

- `set -euo pipefail`; quote every expansion; source `scripts/lib.sh` for logging and
  `find_python`.
- Must run on bash 3.2 (macOS `/bin/bash`): no associative arrays, `mapfile`, `${var,,}`,
  `&>>`, `|&`, `readlink -f`, GNU-only `sed -i`, or `grep -P`.
- ShellCheck-clean under `shellcheck -x --source-path=SCRIPTDIR`. A suppression is allowed
  only for a demonstrated false positive, on the line above the statement, with the reason.
- Wrappers resolve an interpreter and `exec` the Python module with `"$@"`. No logic.

### PowerShell (`*.ps1`, `scripts/lib.ps1`)

- Target Windows PowerShell 5.1: no `?:`, `??`, `&&` or `||`.
- `$ErrorActionPreference = 'Stop'`; comment-based help on every function; approved verbs.
- ASCII only — 5.1 reads a BOM-less file as ANSI and corrupts non-ASCII characters.
- PSScriptAnalyzer-clean with no suppressions.

### Markdown payload

- YAML frontmatter first, no leading blank line.
- Agents: `name`, `description`, `model`, optional `tools`. Output styles: `name`,
  `description`, `keep-coding-instructions`. Skills: `name`, `description`, where the
  description names the triggers.
- Neutral wording: no personal names, no machine names, no references to how this repo was
  built. `tests/python/test_sanitization.py` enforces the pattern list.

## Code Standards

Comment and test rules from `shared/code-standards.md` apply in full to this repo's own code.
Rationale, trade-offs and design decisions belong in `docs/architecture.md` or the relevant
`docs/` page — never in a source comment.

Tier: Light. Test:code LOC band: ~0.85:1 — a diagnostic, never a target. Destructive paths
under a live config directory carry mandatory tests regardless of tier.

**Test run budget:** one full fast-suite run before starting, targeted runs while working,
one full run at the end. Run the `slow` smoke tests when deploy, refresh, the wrappers or
settings changed. Mark anything that spawns a subprocess or deploys a tree `slow`; merge such
tests rather than parametrising them.

## CI

`.github/workflows/ci.yml` runs the fast suite and the smoke tests on Linux, macOS and
Windows; both `--check` commands and a zip assembly; ShellCheck; PSScriptAnalyzer; and
`claude plugin validate --strict` on the marketplace and on each `plugins/sphexi-<name>/`.
`.github/workflows/release.yml` runs on `v*` tags, refuses a tag that differs from
`build/kit.json` `version`, and attaches the Cowork zips to the release.

Run the exact commands of a job locally before changing that job. CI is never the first place
a failure is seen.

## Git

Claude Code may stage and commit in this repository; it never pushes.

Commit source changes together with the generated output they produce. Do not rewrite history,
force anything, or create tags — releases are tagged by a maintainer.

## Docs

`README.md` is a landing page and table of contents; depth lives under `docs/`. When behaviour
changes, update the page that describes it in the same change. `docs/plugins.md` is generated
— change `build/templates/plugins-catalogue.md` or the sources instead.
