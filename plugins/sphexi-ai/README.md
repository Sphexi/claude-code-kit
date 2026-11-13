# sphexi-ai

LLM application development: RAG, embeddings, vector search, prompt engineering and LLM evaluation.

Part of [claude-code-kit](https://github.com/sphexi/claude-code-kit) 0.1.0. Licensed MIT.

## Install

```
/plugin marketplace add sphexi/claude-code-kit
/plugin install sphexi-ai@sphexi
```

This plugin has no dependencies.

## What's in it

3 agents, 3 commands and 8 skills from 1 upstream plugins:

- **llm-application-dev** — agents: `ai-engineer`, `prompt-engineer`, `vector-database-engineer`; commands: `ai-assistant`, `langchain-agent`, `prompt-optimize`; skills: `embedding-strategies`, `hybrid-search-implementation`, `langchain-architecture`, `llm-evaluation`, `prompt-engineering-patterns`, `rag-implementation`, `similarity-search-patterns`, `vector-index-tuning`

Agents keep the names their upstream declares, so commands that call them by `subagent_type` resolve unchanged. Commands are invoked as `/sphexi-ai:<command>`.

## Provenance

Each upstream plugin's source repository, pinned commit, local modifications and license are in `notices/<plugin>/UPSTREAM.md` and `notices/<plugin>/LICENSE`. This directory is generated from `claude/vendor/` in the source repository; edit there, not here.
