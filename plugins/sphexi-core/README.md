# sphexi-core

Thirteen specialist subagents; the systematic-debugging, code-comments, test-discipline and skill-creator skills; three terseness output styles; and a session-start hook that applies the comment and test standards and the Terse (Full) default.

Part of [claude-code-kit](https://github.com/sphexi/claude-code-kit) 0.1.0. Licensed MIT AND Apache-2.0.

## Install

```
/plugin marketplace add sphexi/claude-code-kit
/plugin install sphexi-core@sphexi
```

## What's in it

**13 specialist subagents**, each ending its report with a usage trailer and following the comment and test standards:

- `bash-powershell-engineer` (sonnet)
- `docker-engineer` (sonnet)
- `docs-writer` (sonnet)
- `frontend-engineer` (sonnet)
- `integration-test-runner` (sonnet)
- `networking-engineer` (sonnet)
- `project-architect` (opus)
- `python-engineer` (sonnet)
- `rest-api-engineer` (sonnet)
- `rust-engineer` (sonnet)
- `rust-systems-engineer` (sonnet)
- `task-orchestrator` (opus)
- `test-engineer` (sonnet)

**4 skills.** Authored here:

- `code-comments`
- `systematic-debugging`
- `test-discipline`

Vendored: `skill-creator`.

**3 output styles** — `terse-low`, `terse-medium`, `terse-full`. `terse-full` is applied by default through the session-start hook below; select another with `/output-style` to override it. The levels vary how much supporting explanation survives, not grammar. The register rules (no agreement tokens, no graded findings, no teasers, no narration of conduct, no same-turn repetition) hold at every level.

**Standards and terseness at session start.** A `SessionStart` hook prints 3 files into the session: the comment and test standards that govern code written in it, and the `terse-full` level as the default response style. Each part is at most 9,500 characters, under Claude Code's 10,000-character cap per hook string.

## What a plugin cannot deliver

A global `CLAUDE.md`, merged `settings.json` and the routing tables that name this kit's agents come only from the clone-and-deploy path described in the repository's `docs/deploy.md`.

## Companion plugins

- **sphexi-review** — Code review, refactoring, testing and debugging: multi-perspective review, PR review agents, feature-dev workflow, TDD cycle, unit testing and accessibility audits.
- **sphexi-security** — Security review: SAST, threat modelling, compliance checks, API and frontend hardening, dependency audits.
- **sphexi-python** — Modern Python: python-pro, FastAPI and Django agents plus Python pattern skills.
- **sphexi-languages** — Bash and POSIX shell, Go, and general developer skills (git, error handling, auth, SQL, e2e testing).
- **sphexi-backend** — Backend architecture, API scaffolding, database design and migrations, and full-stack feature orchestration.
- **sphexi-infra** — Cloud architecture, Kubernetes, Terraform, service mesh and CI/CD pipelines.
- **sphexi-ai** — LLM application development: RAG, embeddings, vector search, prompt engineering and LLM evaluation.

## Cowork

The Cowork zip adds a `terseness` skill that switches level mid-session, because Cowork has no output-style mechanism.

## Attribution

`systematic-debugging` carries its attribution in its `SKILL.md`. `skill-creator` is vendored unmodified from Anthropic's `claude-plugins-official` under Apache-2.0; its license and provenance are in `notices/skill-creator/`. The repository's `THIRD_PARTY_NOTICES.md` lists every third-party source.
