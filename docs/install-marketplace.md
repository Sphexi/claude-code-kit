# Install from the marketplace

The repository is a Claude Code plugin marketplace named `sphexi`. Plugin ids take the form `<plugin>@sphexi`.

## Add the marketplace

```
/plugin marketplace add sphexi/claude-code-kit
```

This registers the repository's default branch. The generated plugin trees under `plugins/` are committed there, so no build step is needed on your side.

## Install plugins

```
/plugin install sphexi-core@sphexi
/plugin install sphexi-review@sphexi
```

The available plugins are `sphexi-core`, `sphexi-review`, `sphexi-security`, `sphexi-python`, `sphexi-languages`, `sphexi-backend`, `sphexi-infra` and `sphexi-ai`, plus the external `twingate-assistant`. [plugins.md](plugins.md) lists every agent, command, skill, output style and hook in each, and where each comes from.

Run `/plugin` to see what is installed, enable or disable a plugin, or uninstall one. From a shell, `claude plugin uninstall <plugin>@sphexi` removes a plugin.

Commands from a plugin are namespaced by the plugin name, for example `/sphexi-review:full-review`. Agents from a plugin appear under the same namespace.

## Dependencies

Two marketplace entries declare dependencies on other entries:

| Plugin | Depends on |
|---|---|
| `sphexi-review` | `sphexi-security` |
| `sphexi-backend` | `sphexi-infra`, `sphexi-review`, `sphexi-security` |

Vendored upstream plugins often shipped the same agent under several names. The kit keeps one canonical copy of each, so a command in one plugin can call an agent that lives in another. If you install a plugin without its dependencies, those steps have no agent to call. After installing, check in `/plugin` that the dependencies are enabled and install any that are missing.

`sphexi-core` has no dependencies. Its commands and agents work alone.

## Updates

Each plugin's version is pinned to the kit version in `build/kit.json`. You receive an update only when that version changes in a release.

To pull the latest marketplace listing yourself:

```
/plugin marketplace update sphexi
```

To update automatically, enable auto-update for the `sphexi` marketplace from its entry in `/plugin`.

## Uninstall

```
/plugin uninstall sphexi-review@sphexi
/plugin marketplace remove sphexi
```

Remove plugins before removing the marketplace.

## Twingate

`twingate-assistant` is an external entry. Claude Code fetches it from its own repository, not from this one:

```
/plugin install twingate-assistant@sphexi
```

It is Apache-2.0 licensed, maintained separately, and not redistributed by this repository.

## pyright-lsp and security-guidance

The kit vendors two Anthropic plugins that are not marketplace entries, because both already exist in the `claude-plugins-official` marketplace and the same plugin name in two marketplaces conflicts. Install them from there:

```
/plugin install pyright-lsp@claude-plugins-official
/plugin install security-guidance@claude-plugins-official
```

`pyright-lsp` needs a `pyright-langserver` binary on the host. `security-guidance` runs hooks that call the Agent SDK and a host Python. On macOS its launcher needs bash 4 or newer on `PATH`; see [deploy-macos.md](deploy-macos.md). Clone-and-deploy can install the vendored copies instead with `--extra`; see [deploy.md](deploy.md).

## What the marketplace path cannot deliver

A plugin carries agents, skills, commands, hooks and output styles. It cannot carry:

- A global `CLAUDE.md`. This holds the git policy, the code standards, the terseness description, the activity callouts and the agent routing tables.
- Entries in `settings.json`: the permission deny list and the default output style.

The `sphexi-core` plugin compensates for the first gap with a `SessionStart` hook that prints the code standards into each session, and for the second by shipping output styles you select with `/output-style`; it never forces one. Everything else in the global `CLAUDE.md` and `settings.json` comes only from [clone and deploy](deploy.md).

## Combining with a deployment

A plugin that is both installed from the marketplace and deployed produces duplicates. See [deploy.md](deploy.md#coexistence-with-marketplace-installs).
