# {{NAME}}

{{DESCRIPTION}}

Part of [claude-code-kit]({{REPOSITORY}}) {{VERSION}}. Licensed {{LICENSE}}.

## Install

```
/plugin marketplace add sphexi/claude-code-kit
/plugin install {{NAME}}@{{MARKETPLACE}}
```

## What's in it

**{{AGENT_COUNT}} specialist subagents**, each ending its report with a usage trailer and following the comment and test standards:

{{AGENT_LIST}}

**{{SKILL_COUNT}} skills.** Authored here:

{{OWN_SKILL_LIST}}

Vendored: {{VENDOR_SKILL_LIST}}.

**{{STYLE_COUNT}} output styles** — `terse-low`, `terse-medium`, `terse-full`. Select one with `/output-style`; the plugin never forces one. The levels vary how much supporting explanation survives, not grammar. The register rules (no agreement tokens, no graded findings, no teasers, no narration of conduct, no same-turn repetition) hold at every level.

**Code standards at session start.** A `SessionStart` hook prints {{HOOK_PARTS}} into the session: the comment and test standards that govern code written in it. Each part is at most 9,500 characters, under Claude Code's 10,000-character cap per hook string.

## What a plugin cannot deliver

A global `CLAUDE.md`, merged `settings.json` and the routing tables that name this kit's agents come only from the clone-and-deploy path described in the repository's `docs/deploy.md`.

## Companion plugins

{{BUNDLE_LIST}}

## Cowork

The Cowork zip adds a `terseness` skill that switches level mid-session and a second hook that applies `terse-full` at session start, because Cowork has no output-style mechanism.

## Attribution

`systematic-debugging` carries its attribution in its `SKILL.md`. `skill-creator` is vendored unmodified from Anthropic's `claude-plugins-official` under Apache-2.0; its license and provenance are in `notices/skill-creator/`. The repository's `THIRD_PARTY_NOTICES.md` lists every third-party source.
