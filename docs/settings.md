# Settings

Clone and deploy merges kit settings into `settings.json` in the configuration directory. The marketplace path never changes `settings.json`.

Skip the whole step with `--no-settings`.

## What the kit sets

Deploy composes one settings object from `claude/settings.base.json` and an overlay chosen by the operating system, then merges it into your live file.

`claude/settings.base.json`:

```json
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "outputStyle": "Terse (Full)",
  "permissions": {
    "deny": [
      "Bash(git push)",
      "Bash(git push *)",
      "Bash(sudo *)",
      "Bash(* --force)",
      "Bash(rm -rf /)",
      "Bash(rm -rf /*)",
      "Bash(dd *)",
      "Bash(mkfs *)",
      "Bash(mkfs.* *)"
    ]
  }
}
```

The overlay is selected from the platform deploy runs on: Windows uses `claude/settings.windows.json`, macOS uses `claude/settings.macos.json`, and everything else, including WSL, uses `claude/settings.linux.json`. Each overlay holds only `permissions.deny` entries for destructive or sensitive operations on that platform.

| Overlay | Adds deny rules for |
|---|---|
| Linux | Recursive deletion of system directories and `~`; `mkswap`, `fdisk`, `parted`; mass `chmod` and `chown` on `/`; `shutdown`, `reboot`, `halt`, `init 0`, `init 6`; reading `/etc/shadow`, `/etc/gshadow` and sudoers; editing `/etc/shadow`, sudoers and `/boot` |
| macOS | Recursive deletion of system and user directories; mass `chmod` and `chown` on `/`; destructive `diskutil`; `csrutil`, `nvram`, `spctl --master-disable`, `sysadminctl`, `dscl` create and delete; `shutdown`, `reboot`, `halt`; reading and editing sudoers and `~/Library/Keychains` |
| Windows | `runas`; recursive deletion of `C:\`; `format`, `diskpart`, `bcdedit`, `sfc`, `dism`; `takeown`, registry tools; `net user`, `net localgroup`, `sc` changes; firewall and interface changes with `netsh`; `shutdown`; reads and edits under system directories |

The exact entries are in the overlay files. [deploy-linux.md](deploy-linux.md), [deploy-macos.md](deploy-macos.md) and [deploy-windows.md](deploy-windows.md) summarise each.

Notable entries from the base list:

- `Bash(git push)` and `Bash(git push *)` block pushing from Claude Code in every project.
- `Bash(sudo *)` blocks `sudo`.
- `Bash(* --force)` matches any Bash command whose arguments end in `--force`, not only `git`.
- `Bash(dd *)` and the two `mkfs` rules block raw disk writes.

## What the kit does not set

The base file sets no model, no effort level, no default permission mode, no `allow` rules, no `env`, no `enabledPlugins` and no marketplace registrations. Your existing choices for those stay as they are. The only scalar it sets is `outputStyle`.

## Merge rules

Deploy merges into the live file rather than replacing it:

| Key | Rule |
|---|---|
| `permissions.deny`, `allow`, `ask`, `additionalDirectories` | Your entries stay in their order; kit entries you do not already have are appended |
| `env`, `enabledPlugins`, `extraKnownMarketplaces` | Kit keys you do not have are added; an existing key is never changed, including one set to `false` |
| Scalars (`outputStyle`, `$schema`) | Set only if absent. If you have a different value, yours is kept and deploy prints `kept user value` |
| Everything else | Untouched |

If the live file is not valid JSON or not a JSON object, deploy leaves it alone and prints a warning. Before writing an existing file, deploy copies it to `settings.json.bak-<timestamp>`.

Every entry deploy adds is recorded in `claude-code-kit-state.json`, so `./deploy.sh --uninstall` removes exactly those entries and nothing you added.

Refresh treats the kit entries as a subset check: entries missing from your file are drift, and a different value of yours is reported as `kept user value`, not drift.

## Why the deny list is the only global rule

Claude Code evaluates `deny` rules before `allow` rules, and a deny at user scope cannot be lifted by a project or local settings file. A conditional rule placed at user scope therefore could never be relaxed where it should be. So the kit's global settings contain only operations that should never run on any machine, and leave every conditional decision, such as which commands to allow or whether a project may commit, to project-level settings and `CLAUDE.md`.

The global `CLAUDE.md` follows the same split for git. By default Claude does not run git commands and asks you to review and commit; a project may opt in to staging and committing through its own `CLAUDE.md` or `.claude/settings.json`. `git push` is the one operation denied everywhere.

## Remove an entry

Delete the entry from `permissions.deny` in your `settings.json` and save. Claude Code reads it on the next session.

The next `./refresh.sh` then reports `settings.json` as behind, because a kit entry is missing. Refresh only merges it back if you answer yes to the prompt, so decline it. To stop the report, remove the entry from `claude/settings.base.json` (or the overlay) in your own clone; see [customizing.md](customizing.md). A deployment that was first made with `--no-settings` is not compared against settings at all.

## security-guidance variables

The `security-guidance` plugin, available with `--extra security-guidance` or from `claude-plugins-official`, reads environment variables. Set them in the `env` object of `settings.json` or in your shell. The kit sets none of them.

| Variable | Effect |
|---|---|
| `ENABLE_PATTERN_RULES=0` | Disable the regular-expression warnings on edits |
| `ENABLE_CODE_SECURITY_REVIEW=0` | Disable every model-based review |
| `ENABLE_STOP_REVIEW=0` | Disable only the review that runs when a turn ends |
| `ENABLE_COMMIT_REVIEW=0` | Disable the review on commit and push |
| `SECURITY_REVIEW_MODEL` | Model for the diff review; a model id your account or provider can invoke |
| `SG_AGENTIC_MODEL` | Model for the commit and push review, same syntax |

The model-based reviews send code to a model under your credentials and cost tokens, which is why the plugin is not part of any bundle. The plugin's own README documents credentials and behaviour.
