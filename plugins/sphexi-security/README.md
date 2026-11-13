# sphexi-security

Security review: SAST, threat modelling, compliance checks, API and frontend hardening, dependency audits.

Part of [claude-code-kit](https://github.com/sphexi/claude-code-kit) 0.1.0. Licensed MIT.

## Install

```
/plugin marketplace add sphexi/claude-code-kit
/plugin install sphexi-security@sphexi
```

This plugin has no dependencies.

## What's in it

6 agents, 6 commands and 5 skills from 5 upstream plugins:

- **security-scanning** — agents: `security-scanning-security-auditor`, `threat-modeling-expert`; commands: `security-dependencies`, `security-hardening`, `security-sast`; skills: `attack-tree-construction`, `sast-configuration`, `security-requirement-extraction`, `stride-analysis-patterns`, `threat-mitigation-mapping`
- **security-compliance** — commands: `compliance-check`
- **backend-api-security** — agents: `backend-api-security-backend-security-coder`
- **frontend-mobile-security** — agents: `frontend-mobile-security-frontend-developer`, `frontend-security-coder`, `mobile-security-coder`; commands: `xss-scan`
- **dependency-management** — commands: `deps-audit`

Agents keep the names their upstream declares, so commands that call them by `subagent_type` resolve unchanged. Commands are invoked as `/sphexi-security:<command>`.

## Provenance

Each upstream plugin's source repository, pinned commit, local modifications and license are in `notices/<plugin>/UPSTREAM.md` and `notices/<plugin>/LICENSE`. This directory is generated from `claude/vendor/` in the source repository; edit there, not here.
