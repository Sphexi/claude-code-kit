# Customizing and forking

To change what the kit ships, fork the repository, edit the sources, regenerate, and either deploy from your clone or point Claude Code at your fork as a marketplace. The generated plugin trees are committed, so a fork serves its own content with the same `/plugin marketplace add <you>/claude-code-kit` command.

Read [architecture.md](architecture.md) for how sources become generated files. For what the shipped plugins contain and where each component comes from, see the generated catalogue: [plugins.md](plugins.md).

Set up the tools first; see [contributing.md](contributing.md#development-setup).

## The rule that governs every change

Never edit a generated file. These are generated: `plugins/`, `.claude-plugin/marketplace.json`, `THIRD_PARTY_NOTICES.md`, `docs/plugins.md`, every region between `TERSENESS` or `CODE-STANDARDS` markers, `claude/plugins.manifest.json`, and every `claude/vendor/*/UPSTREAM.md`. Change the source, regenerate, and commit source and output together.

When several sources change, regenerate in this order:

```bash
python tools/vendor_sync.py        # only if vendored content changed
python build/inline_shared.py
python build/build_plugins.py
```

`python build/inline_shared.py --check` and `python build/build_plugins.py --check` exit 1 if anything is stale.

## Change the shared rules

The terseness rules and the code standards are single sources in `shared/`: `terseness-main.md`, `terseness-subagent.md` and `code-standards.md`. Edit one, then run `python build/inline_shared.py`.

The script copies each file into every payload file that contains its marker pair, such as `<!-- CODE-STANDARDS:START -->` and `<!-- CODE-STANDARDS:END -->`. Files under an `agents/` directory receive the subagent variant of the terseness block. Targets are found by markers, so a new agent or output style that carries the pair is picked up without further configuration. Content between markers is overwritten on every run.

Then run `python build/build_plugins.py` to carry the change into `plugins/`.

## Add or change an agent

1. Create or edit `claude/agents/<name>.md`. Frontmatter holds `name`, `description` and `model`, with an optional `tools` list.
2. Copy the `TERSENESS` and `CODE-STANDARDS` marker pairs from an existing agent so the shared rules are inlined into it.
3. Run `python build/inline_shared.py`, then `python build/build_plugins.py`.

Agents in `claude/agents/` ship in `sphexi-core`. The core plugin description says "Thirteen specialist subagents"; update the text in `build/bundles.py` if the count changes.

## Add a skill, output style or global instruction

- A skill: add `claude/skills/<name>/SKILL.md` with `name` and `description` frontmatter. The description names the triggers. It ships in `sphexi-core`.
- An output style: add `claude/output-styles/<name>.md` with `name`, `description` and `keep-coding-instructions` frontmatter.
- The global instructions: edit `claude/global-CLAUDE.md` outside the marked regions. Deploy installs it as `CLAUDE.md`.
- Settings: edit `claude/settings.base.json` or an OS overlay. See [settings.md](settings.md).

## Change bundle membership

`build/bundles.py` assigns every vendored plugin to exactly one marketplace plugin, or to `EXTRAS`, which ship only through `deploy --extra`. It also holds each plugin's description, dependencies, category and tags.

The build fails on:

- a vendored plugin assigned to no bundle and not listed in `EXTRAS`
- an agent, command or skill name that appears twice in one bundle
- a `subagent_type` reference that resolves to nothing in the bundle, its dependencies, `sphexi-core` or the built-in agents

If a command in one bundle calls an agent that moves to another, declare the dependency in `depends_on`.

## Release your changes to users

Users of a marketplace plugin receive an update only when the version changes. Bump `version` in `build/kit.json`; the build stamps it into every generated `plugin.json`. Steps: [releasing.md](releasing.md).

## Adopt live edits into your clone

If you edit an agent, output style, skill or `CLAUDE.md` directly under the configuration directory, refresh can copy the edit back into your clone's `claude/` directory so it stops showing as modified:

```bash
./refresh.sh --apply
```

Choose `adopt` for the unit when prompted. Adopt works on content authored under `claude/`. It refuses plugin directories, `settings.json` and vendored content, which are generated from other sources. Add `--adopt-unmanaged` to be offered files in the configuration directory that the kit does not manage.

After adopting, run the regeneration commands above and commit. See [deploy.md](deploy.md#refresh).

## Disable one plugin without removing it

In `settings.json`, set the plugin's id to `false` under `enabledPlugins`:

```json
{
  "enabledPlugins": {
    "sphexi-infra@sphexi": false
  }
}
```

Deploy never changes an existing `enabledPlugins` key, including one set to `false`.

## Change vendored plugins

Vendored plugin content is rewritten only by `tools/vendor_sync.py`. To change a vendored agent, declare a modification there rather than editing `claude/vendor/`. See [vendored-upstreams.md](vendored-upstreams.md), and the catalogue in [plugins.md](plugins.md) for which components are custom and which are vendored.
