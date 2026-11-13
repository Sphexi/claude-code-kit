# sphexi-backend

Backend architecture, API scaffolding, database design and migrations, and full-stack feature orchestration.

Part of [claude-code-kit](https://github.com/sphexi/claude-code-kit) 0.1.0. Licensed MIT.

## Install

```
/plugin marketplace add sphexi/claude-code-kit
/plugin install sphexi-backend@sphexi
```

**Depends on:** `sphexi-infra`, `sphexi-review`, `sphexi-security`. Some commands call an agent that lives in another plugin because upstream duplicates were collapsed to one canonical copy; without those plugins installed, those steps have no agent to call.

## What's in it

11 agents, 4 commands and 11 skills from 5 upstream plugins:

- **backend-development** — agents: `backend-development-backend-architect`, `backend-development-graphql-architect`, `backend-development-performance-engineer`, `backend-development-security-auditor`, `backend-development-test-automator`, `event-sourcing-architect`, `temporal-python-pro`; commands: `feature-development`; skills: `api-design-principles`, `architecture-patterns`, `cqrs-implementation`, `event-store-design`, `microservices-patterns`, `projection-patterns`, `saga-orchestration`, `temporal-python-testing`, `workflow-orchestration-patterns`
- **api-scaffolding** — skills: `fastapi-templates`
- **database-design** — agents: `database-design-database-architect`, `sql-pro`; skills: `postgresql-table-design`
- **database-migrations** — agents: `database-admin`, `database-migrations-database-optimizer`; commands: `migration-observability`, `sql-migrations`
- **full-stack-orchestration** — commands: `full-stack-feature`

Agents keep the names their upstream declares, so commands that call them by `subagent_type` resolve unchanged. Commands are invoked as `/sphexi-backend:<command>`.

## Provenance

Each upstream plugin's source repository, pinned commit, local modifications and license are in `notices/<plugin>/UPSTREAM.md` and `notices/<plugin>/LICENSE`. This directory is generated from `claude/vendor/` in the source repository; edit there, not here.
