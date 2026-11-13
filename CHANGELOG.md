# Changelog

All notable changes to claude-code-kit are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.1.0] - Unreleased

### Added

- Plugin marketplace `sphexi`, installed with `/plugin marketplace add sphexi/claude-code-kit`. It lists eight plugins generated under `plugins/` (`sphexi-core`, `sphexi-review`, `sphexi-security`, `sphexi-python`, `sphexi-languages`, `sphexi-backend`, `sphexi-infra`, `sphexi-ai`) and one external entry fetched from its own repository.
- `sphexi-core`: thirteen specialist subagents, the `code-comments`, `systematic-debugging` and `test-discipline` skills, the vendored `skill-creator` skill, three terseness output styles (`Terse (Low)`, `Terse (Medium)`, `Terse (Full)`), and a `SessionStart` hook that prints the code standards in parts of at most 9,500 characters.
- Seven topic plugins assembled from third-party plugins vendored at pinned commits, with agents deduplicated to one canonical copy, explicit model tiers and shortened agent descriptions. Each carries its upstream licenses and provenance under `notices/`. Declared dependencies: `sphexi-review` on `sphexi-security`; `sphexi-backend` on `sphexi-infra`, `sphexi-review` and `sphexi-security`.
- Clone-and-deploy through `deploy.sh` and `deploy.ps1`, on Linux, macOS and Windows. Deploy reports by default and writes only with `--apply`. It installs core agents, skills and output styles as user-level files, the other plugins under `skills/`, a global `CLAUDE.md`, and a merged `settings.json`.
- Deploy options `--config-dir`, `--plugins`, `--extra`, `--overwrite`, `--no-settings`, `--no-claude-md`, `--uninstall` and `--quiet`; opt-in extras `pyright-lsp` and `security-guidance`.
- A state file, `claude-code-kit-state.json`, recording every file and settings entry the kit wrote with hashes, so deploy, refresh and uninstall change only kit-owned content. Modified or unrecorded files are reported as conflicts, and `--overwrite` backs each up first.
- Settings composed from a base file and a Linux, macOS or Windows overlay, merged into the live `settings.json` without replacing user values. The base sets a permission deny list, including `git push`, and a default output style; it sets no model, permission mode or allow rules.
- Pre-flight warnings for managed settings that disable `skills-dir` plugins and for marketplace installs that duplicate a deployment.
- `refresh.sh` and `refresh.ps1`: a three-way comparison of the clone, the state file and the live directory, with `matched`, `missing`, `behind`, `modified`, `retired` and `unmanaged` classes, per-unit prompts, `--yes-safe`, and `adopt` for copying live edits back into the clone.
- Cowork zips, one per plugin, with a core zip that adds a `terseness` skill and a session-start hook for the default level.
- Global `CLAUDE.md` covering git policy, code standards, terseness levels, activity callouts and agent routing tables.
- Generators: `build/build_plugins.py` (plugins, marketplace listing, notices, catalogue, zips; `--check`, `--zip`), `build/inline_shared.py` (shared prose blocks; `--check`), and `tools/vendor_sync.py` (vendored content and provenance; `--apply`, `--only`, `--marketplaces`, `--render-upstream`).
- `THIRD_PARTY_NOTICES.md`, generated per-plugin `LICENSE` and `UPSTREAM.md` files, and in-file notices on modified Apache-2.0 files.
- Documentation under `docs/`, including a generated plugin catalogue.
- Continuous integration: tests and smoke tests on Linux, macOS and Windows, generated-file checks, ShellCheck, PSScriptAnalyzer and `claude plugin validate --strict`; a release workflow that attaches the Cowork zips to a tagged release.
