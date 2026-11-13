# sphexi-languages

Bash and POSIX shell, Go, and general developer skills (git, error handling, auth, SQL, e2e testing).

Part of [claude-code-kit](https://github.com/sphexi/claude-code-kit) 0.1.0. Licensed MIT.

## Install

```
/plugin marketplace add sphexi/claude-code-kit
/plugin install sphexi-languages@sphexi
```

This plugin has no dependencies.

## What's in it

3 agents, 0 commands and 13 skills from 3 upstream plugins:

- **shell-scripting** — agents: `bash-pro`, `posix-shell-pro`; skills: `bash-defensive-patterns`, `bats-testing-patterns`, `shellcheck-configuration`
- **systems-programming** — agents: `golang-pro`; skills: `go-concurrency-patterns`, `memory-safety-patterns`, `rust-async-patterns`
- **developer-essentials** — skills: `auth-implementation-patterns`, `code-review-excellence`, `debugging-strategies`, `e2e-testing-patterns`, `error-handling-patterns`, `git-advanced-workflows`, `sql-optimization-patterns`

Agents keep the names their upstream declares, so commands that call them by `subagent_type` resolve unchanged. Commands are invoked as `/sphexi-languages:<command>`.

## Provenance

Each upstream plugin's source repository, pinned commit, local modifications and license are in `notices/<plugin>/UPSTREAM.md` and `notices/<plugin>/LICENSE`. This directory is generated from `claude/vendor/` in the source repository; edit there, not here.
