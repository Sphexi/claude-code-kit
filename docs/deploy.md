# Clone and deploy

Deploy copies the kit's content into a Claude Code configuration directory. It reads the same generated `plugins/` tree that the marketplace serves, so a deployment installs the same bytes. It also installs two things a plugin cannot: a global `CLAUDE.md` and a merged `settings.json`.

Platform notes: [Linux](deploy-linux.md), [macOS](deploy-macos.md), [Windows](deploy-windows.md).

## Prerequisites

- Python 3.12 or newer. The wrappers search for it; see the platform pages.
- A clone of the repository. Deploy has no dependencies beyond the Python standard library.
- Claude Code, installed.

```bash
git clone https://github.com/sphexi/claude-code-kit.git
cd claude-code-kit
```

## Run it

`deploy.sh` (Linux, macOS) and `deploy.ps1` (Windows) find a suitable Python and run `python -m tools.deploy` with your arguments unchanged. All behaviour is in the Python module.

Without `--apply`, deploy only reports. It prints every path it would write, back up, skip or remove, then a summary.

```bash
./deploy.sh              # report only
./deploy.sh --apply      # write
```

```powershell
.\deploy.ps1             # report only
.\deploy.ps1 --apply     # write
```

Read the report before applying. Exit code 0 means the run completed, including runs that skipped conflicts. Exit code 2 means it could not proceed: no suitable Python, an unknown plugin name, an unreadable state file, or two targets that differ only by case.

## Where files go

The configuration directory is `--config-dir`, else `$CLAUDE_CONFIG_DIR`, else `~/.claude`.

| Source in the repository | Target in the configuration directory | Notes |
|---|---|---|
| `claude/global-CLAUDE.md` | `CLAUDE.md` | |
| `plugins/sphexi-core/agents/*.md` | `agents/<name>.md` | User-level agents, not namespaced |
| `plugins/sphexi-core/output-styles/*.md` | `output-styles/<name>.md` | |
| `plugins/sphexi-core/skills/<skill>/` | `skills/<skill>/` | One directory per skill |
| `plugins/sphexi-<name>/` for every other plugin | `skills/sphexi-<name>/` | Whole plugin tree; Claude Code loads it as `sphexi-<name>@skills-dir` |
| `claude/vendor/<extra>/` | `skills/<extra>/` | Only with `--extra` |
| `claude/settings.base.json` plus an OS overlay | `settings.json` | Merged, not replaced; see [settings.md](settings.md) |

Not deployed: the `sphexi-core` hooks, notices, README and plugin manifest. The global `CLAUDE.md` already carries the code standards that the hook prints, so deploying the hook would repeat them. Symbolic links in the source tree are skipped and reported.

`plugins/` is generated. Deploy refuses to run if it is missing and tells you to run `python build/build_plugins.py`.

## Options

| Option | Effect |
|---|---|
| `--apply` | Required for any write, backup or removal |
| `--config-dir PATH` | Target a directory other than the default. Use a scratch directory to try the kit first |
| `--plugins LIST` | Comma-separated plugin names to deploy. Default: all eight. Needs at least one name. `sphexi-core` controls the agents, core skills and output styles |
| `--extra NAME` | Also deploy a vendored plugin that ships in no bundle. Repeatable. Known extras: `pyright-lsp`, `security-guidance` |
| `--overwrite` | Replace conflicting files, copying each to `<name>.bak-<YYYYmmdd-HHMMSS>` first |
| `--no-settings` | Leave `settings.json` alone |
| `--no-claude-md` | Leave `CLAUDE.md` alone |
| `--uninstall` | Remove what the state file records; see [Uninstall](#uninstall) |
| `--quiet` | Print a summary instead of every path. Ignored under `--apply` |

Examples:

```bash
./deploy.sh --plugins sphexi-core,sphexi-python,sphexi-review,sphexi-security --apply
./deploy.sh --extra security-guidance --apply
./deploy.sh --no-settings --apply
./deploy.sh --config-dir /tmp/claude-test --apply
```

Choose plugins that match each other. `sphexi-review` calls agents in `sphexi-security`, and `sphexi-backend` calls agents in `sphexi-infra`, `sphexi-review` and `sphexi-security`. The deployed global `CLAUDE.md` routing tables name agents from every plugin, so a partial deployment leaves some rows pointing at agents that are not installed.

## What deploy checks first

Before classifying files, deploy reads two things and prints warnings. It never edits either.

- Managed settings. It looks in `/etc/claude-code` on Linux, `/Library/Application Support/ClaudeCode` on macOS and `C:\Program Files\ClaudeCode` on Windows, including `managed-settings.d/*.json`. It warns when `strictKnownMarketplaces` has no `{"source": "skills-dir"}` entry, when `blockedMarketplaces` contains `skills-dir`, or when `strictPluginOnlyCustomization` is set. Each of these disables the deployed plugins without an error.
- Existing plugin installs. It reads `plugins/installed_plugins.json` and `enabledPlugins` and warns about duplicates; see [Coexistence](#coexistence-with-marketplace-installs).

## Conflicts and backups

For each target file deploy compares the live file with the source and with the hash it recorded last time.

| Live file | Result |
|---|---|
| Absent | `write` |
| Identical to the source | `unchanged` |
| Differs, and matches the hash deploy recorded | `update`: the kit wrote it and you have not edited it |
| Differs and was never recorded, or differs from the recorded hash | `CONFLICT`: skipped and reported |
| Not a regular file, or a symbolic link | `CONFLICT`: skipped, even with `--overwrite` |

A plugin or skill directory is handled as a unit. If any file in it conflicts, the whole unit is skipped, so a plugin is never partly written.

`--overwrite` replaces conflicting files after copying each to a sibling named `<file>.bak-<YYYYmmdd-HHMMSS>`. Before changing an existing `settings.json`, deploy copies it to `settings.json.bak-<timestamp>` once per run. Backups are never removed by deploy or uninstall.

Files in the configuration directory that the kit did not write are never touched. A skill or agent of your own sits beside the kit's without interference.

When a plugin or file drops out of the selection or out of the kit, deploy removes it only if its live hash still matches the recorded hash. A modified file is reported and left.

## The state file

On `--apply`, deploy writes `claude-code-kit-state.json` in the configuration directory, atomically. It records:

- the kit version and the clone path
- the selected plugins and extras, and whether `CLAUDE.md` and `settings.json` were managed
- the SHA-256 of every file written
- each `settings.json` entry deploy added, and whether deploy created the file

Deploy, refresh and uninstall use it to tell a file the kit owns from one you wrote, and a changed source from a file you edited. Do not edit it by hand. If it is corrupt, deploy exits with code 2 and asks you to fix or delete it.

## Refresh

After pulling a newer clone, or after editing files in the configuration directory, run refresh to compare the machine with the clone.

```bash
git pull
./refresh.sh              # report only
./refresh.sh --apply      # act, prompting per unit
```

```powershell
.\refresh.ps1
.\refresh.ps1 --apply
```

Refresh classifies each unit (an agent, an output style, a skill, a plugin directory, `CLAUDE.md`):

| Class | Meaning | Offered actions |
|---|---|---|
| matched | Live equals the clone | none |
| missing | In the clone, absent live | install |
| behind | Live equals what deploy wrote; the clone has changed | update |
| modified | Live differs from both the clone and the recorded hash | update (backs up first), adopt, skip |
| retired | Recorded, no longer in the clone | remove (only if unmodified), skip |
| unmanaged | Live, in neither the state file nor the clone | adopt, skip. Never removed |

Settings are compared as a subset check: kit entries missing from `settings.json` are drift. A value you set that differs from the kit's, such as a different `outputStyle`, is reported as `kept user value` and is not drift.

| Option | Effect |
|---|---|
| `--dry-run` | Report only. The default |
| `--apply` | Act on the diff. Prompts per unit on a terminal |
| `--yes-safe` | With `--apply`, confirm `missing` and `behind` units without prompting |
| `--plugins LIST`, `--extra NAME` | Select plugins and extras. Default: the ones last deployed |
| `--adopt-unmanaged` | With `--apply`, prompt to adopt each unmanaged unit |
| `--report PATH` | Also write the report to a file |
| `--verbose` | Expand units to per-file detail |
| `--show-matched`, `--show-unmanaged` | List those units |
| `--version` | Print the refresh version |

Without a terminal, refresh prompts for nothing: `--apply` then acts only on what `--yes-safe` confirms, so an unattended run never overwrites or removes anything else. Refresh writes the state file after any applied action.

`adopt` copies a live agent, output style, skill or `CLAUDE.md` into the clone's `claude/` directory and records it as kit-owned. It refuses plugin directories, `settings.json` and vendored content. See [customizing.md](customizing.md).

## Uninstall

```bash
./deploy.sh --uninstall           # report
./deploy.sh --uninstall --apply   # remove
```

Uninstall deletes each file in the state file whose hash still matches, then the directories it emptied. It reverses each `settings.json` addition that is still present and unchanged, backing the file up first when it rewrites it, and deletes `settings.json` if deploy created it and nothing else remains. It deletes the state file last. Files you modified, settings values you changed, and every `.bak-*` file stay.

## Coexistence with marketplace installs

Use one path per plugin where you can. If both are present:

- `sphexi-<name>@sphexi` installed from the marketplace and `sphexi-<name>` deployed: Claude Code loads the marketplace copy and shows the deployed copy as `Not loaded`.
- `sphexi-core` installed from the marketplace and deployed: the deployed agents are user-level, so each agent appears twice, as `python-engineer` and as `sphexi-core:python-engineer`. Deploy with `--plugins` leaving out `sphexi-core`, or uninstall the marketplace copy.
- A plugin from another marketplace that duplicates vendored content, for example `pr-review-toolkit@claude-plugins-official` or anything from `claude-code-workflows`: deploy warns and prints the `claude plugin uninstall <id>` command. Deploy does not run it.

Deploy never edits `installed_plugins.json`, `enabledPlugins`, plugin caches or marketplace registrations.
