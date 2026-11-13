# sphexi-review

Code review, refactoring, testing and debugging: multi-perspective review, PR review agents, feature-dev workflow, TDD cycle, unit testing and accessibility audits.

Part of [claude-code-kit](https://github.com/sphexi/claude-code-kit) 0.1.0. Licensed MIT AND Apache-2.0.

## Install

```
/plugin marketplace add sphexi/claude-code-kit
/plugin install sphexi-review@sphexi
```

**Depends on:** `sphexi-security`. Some commands call an agent that lives in another plugin because upstream duplicates were collapsed to one canonical copy; without those plugins installed, those steps have no agent to call.

## What's in it

20 agents, 20 commands and 2 skills from 11 upstream plugins:

- **comprehensive-review** — agents: `comprehensive-review-architect-review`, `comprehensive-review-code-reviewer`; commands: `full-review`, `pr-enhance`
- **pr-review-toolkit** — agents: `code-reviewer`, `code-simplifier`, `comment-analyzer`, `pr-test-analyzer`, `silent-failure-hunter`, `type-design-analyzer`; commands: `review-pr`
- **feature-dev** — agents: `feature-dev-code-architect`, `feature-dev-code-explorer`, `feature-dev-code-reviewer`; commands: `feature-dev`
- **tdd-workflows** — agents: `tdd-workflows-tdd-orchestrator`; commands: `tdd-cycle`, `tdd-green`, `tdd-red`, `tdd-refactor`
- **unit-testing** — agents: `unit-testing-test-automator`; commands: `test-generate`
- **code-refactoring** — agents: `code-refactoring-legacy-modernizer`; commands: `context-restore`, `refactor-clean`, `tech-debt`
- **code-documentation** — agents: `code-documentation-docs-architect`, `code-documentation-tutorial-engineer`; commands: `code-explain`, `doc-generate`
- **git-pr-workflows** — commands: `git-workflow`, `onboard`
- **performance-testing-review** — agents: `performance-testing-review-performance-engineer`; commands: `ai-review`, `multi-agent-review`
- **debugging-toolkit** — agents: `debugging-toolkit-debugger`, `debugging-toolkit-dx-optimizer`; commands: `smart-debug`
- **accessibility-compliance** — agents: `ui-visual-validator`; commands: `accessibility-audit`; skills: `screen-reader-testing`, `wcag-audit-patterns`

Agents keep the names their upstream declares, so commands that call them by `subagent_type` resolve unchanged. Commands are invoked as `/sphexi-review:<command>`.

## Provenance

Each upstream plugin's source repository, pinned commit, local modifications and license are in `notices/<plugin>/UPSTREAM.md` and `notices/<plugin>/LICENSE`. This directory is generated from `claude/vendor/` in the source repository; edit there, not here.
