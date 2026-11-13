# Troubleshooting

## Deployed plugins do not load

Deploy printed a warning about managed settings, or the plugins under `skills/` are absent from `/plugin`.

Deployed plugins load from the `skills-dir` source. Managed settings can disable that source without an error. Deploy reads the managed settings directory and warns on each of these:

- `strictKnownMarketplaces` is set and has no `{"source": "skills-dir"}` entry.
- `blockedMarketplaces` contains `skills-dir`.
- `strictPluginOnlyCustomization` is set. It also blocks skills and agents from user sources such as the configuration directory.

The managed settings directory is `/etc/claude-code` on Linux, `/Library/Application Support/ClaudeCode` on macOS and `C:\Program Files\ClaudeCode` on Windows. The fix belongs to whoever administers that file: add `{"source": "skills-dir"}` to `strictKnownMarketplaces`, remove the block, or install through the marketplace path instead.

## A plugin shows "Not loaded"

The plugin is both installed from the marketplace and deployed under `skills/`. Claude Code loads the marketplace copy and reports the deployed copy as not loaded because the name is taken. This is harmless. To end the duplication, either uninstall the marketplace copy or deploy with `--plugins` leaving that plugin out. See [deploy.md](deploy.md#coexistence-with-marketplace-installs).

## Every agent appears twice

`sphexi-core` is installed from the marketplace and also deployed. Deploy writes the agents as user-level files, so each shows as `python-engineer` and as `sphexi-core:python-engineer`. Use one path for core: deploy with `--plugins` excluding `sphexi-core`, or run `claude plugin uninstall sphexi-core@sphexi`.

## Duplicate warnings for other plugins

Deploy warns when `pr-review-toolkit@claude-plugins-official`, any plugin from the `claude-code-workflows` marketplace, or another installed plugin with the name of vendored content is present. The same agents then load under two namespaces. Run the `claude plugin uninstall <id>` command that deploy prints, if you want one copy. Deploy never runs it.

## The code standards appear as a file path

At session start Claude Code shows a file path and a short preview instead of the code standards. Claude Code caps each hook output string at 10,000 characters and substitutes a path above that. The `sphexi-core` hook splits its text into parts of at most 9,500 characters so each part stays under the cap, and the build fails if a part would exceed it. If you see the preview, check that you are on a current `sphexi-core` and that no local edit to the hook files made one part larger.

## Python not found

The wrapper exits with code 2 and prints an installation hint when no Python 3.12 or newer is found.

- **macOS.** `/usr/bin/python3` is the Xcode Command Line Tools shim, older than 3.12, and opens an install dialog when the tools are absent. The wrapper skips it. Install a current Python with `brew install python@3.12` or from python.org, then open a new terminal. See [deploy-macos.md](deploy-macos.md).
- **Windows.** The `python` alias that opens the Microsoft Store is not an interpreter, and the script passes over it. Install Python with `winget install Python.Python.3.12` or from python.org, then open a new terminal. The script tries `py -3`, `python` and `python3`. See [deploy-windows.md](deploy-windows.md).
- **Linux.** Install `python3` with your package manager and check that it reports 3.12 or newer. A versioned binary such as `python3.12` is found even when `python3` is older. See [deploy-linux.md](deploy-linux.md).

## PowerShell will not run the script

Windows reports that running scripts is disabled. Bypass the policy for one invocation:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\deploy.ps1
```

See [deploy-windows.md](deploy-windows.md#execution-policy).

## Deploy reports CONFLICT

A target file exists, differs from the kit's version, and was not written by the kit or has changed since. Deploy skips it, and skips the whole plugin or skill directory containing it. Compare the file with the source. To replace it, rerun with `--overwrite`, which copies each replaced file to `<name>.bak-<timestamp>` first. To keep your file, leave it; the rest of the deployment is unaffected. A conflict does not change the exit code.

A target that is a symbolic link or a directory is skipped even with `--overwrite`. Move it aside.

## Refresh reports "kept user value"

Your `settings.json` has a value for a key the kit also sets, such as a different `outputStyle`. Deploy and refresh keep your value and report the difference. It is not drift, and nothing needs fixing. See [settings.md](settings.md#merge-rules).

## Refresh reports settings as behind

A kit permission entry is missing from your `settings.json`, usually because you removed it. Decline the prompt to keep your file, or remove the entry from your clone's settings files. See [settings.md](settings.md#remove-an-entry).

## Refresh does nothing under `--apply`

Without a terminal, refresh prompts for nothing, so it skips every action. Add `--yes-safe` to confirm `missing` and `behind` units. `modified`, `retired` and `unmanaged` units always need an interactive answer.

## Errors that exit with code 2

| Message | Cause and action |
|---|---|
| `<path>/plugins does not exist` | The generated tree is absent. Run `python build/build_plugins.py` |
| `unknown plugin(s)` | A name in `--plugins` is not a plugin. Use the full `sphexi-` name; the message lists the valid ones |
| `--plugins needs at least one name` | The list was empty |
| State file is unreadable or not a schema 1 state file | Fix or delete `claude-code-kit-state.json` in the configuration directory, then redeploy |
| `targets collide on a case-insensitive filesystem` | Two repository paths differ only by case. Report it as a bug |
| `settings.json is not valid JSON` (a warning, not an error) | Deploy leaves the file alone. Repair it and rerun |

## security-guidance hooks fail on macOS

The vendored launcher uses Bash 4 syntax, and `bash` resolves to the Bash 3.2 that macOS ships. Install a newer Bash with `brew install bash` and put its directory before `/bin` on `PATH`. See [deploy-macos.md](deploy-macos.md#the-security-guidance-extra-needs-a-newer-bash).

## Commands are not found

Commands from a plugin are namespaced. Use `/sphexi-review:full-review`, not `/full-review`.
