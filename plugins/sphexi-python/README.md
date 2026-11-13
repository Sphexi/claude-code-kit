# sphexi-python

Modern Python: python-pro, FastAPI and Django agents plus Python pattern skills.

Part of [claude-code-kit](https://github.com/sphexi/claude-code-kit) 0.1.0. Licensed MIT.

## Install

```
/plugin marketplace add sphexi/claude-code-kit
/plugin install sphexi-python@sphexi
```

This plugin has no dependencies.

## What's in it

3 agents, 1 commands and 16 skills from 1 upstream plugins:

- **python-development** — agents: `python-development-django-pro`, `python-development-fastapi-pro`, `python-pro`; commands: `python-scaffold`; skills: `async-python-patterns`, `python-anti-patterns`, `python-background-jobs`, `python-code-style`, `python-configuration`, `python-design-patterns`, `python-error-handling`, `python-observability`, `python-packaging`, `python-performance-optimization`, `python-project-structure`, `python-resilience`, `python-resource-management`, `python-testing-patterns`, `python-type-safety`, `uv-package-manager`

Agents keep the names their upstream declares, so commands that call them by `subagent_type` resolve unchanged. Commands are invoked as `/sphexi-python:<command>`.

## Provenance

Each upstream plugin's source repository, pinned commit, local modifications and license are in `notices/<plugin>/UPSTREAM.md` and `notices/<plugin>/LICENSE`. This directory is generated from `claude/vendor/` in the source repository; edit there, not here.
