# {{NAME}}

{{DESCRIPTION}}

Part of [claude-code-kit]({{REPOSITORY}}) {{VERSION}}. Licensed {{LICENSE}}.

## Install

```
/plugin marketplace add sphexi/claude-code-kit
/plugin install {{NAME}}@{{MARKETPLACE}}
```

{{DEPENDS}}

## What's in it

{{AGENT_COUNT}} agents, {{COMMAND_COUNT}} commands and {{SKILL_COUNT}} skills from {{PLUGIN_COUNT}} upstream plugins:

{{PLUGIN_LIST}}

Agents keep the names their upstream declares, so commands that call them by `subagent_type` resolve unchanged. Commands are invoked as `/{{NAME}}:<command>`.

## Provenance

Each upstream plugin's source repository, pinned commit, local modifications and license are in `notices/<plugin>/UPSTREAM.md` and `notices/<plugin>/LICENSE`. This directory is generated from `claude/vendor/` in the source repository; edit there, not here.
