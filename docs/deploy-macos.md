# Deploy on macOS

Read [deploy.md](deploy.md) first for the commands and behaviour common to every platform. This page covers what differs on macOS. macOS uses the Bash wrappers, `deploy.sh` and `refresh.sh`; the PowerShell scripts are for Windows.

## Python

Deploy needs Python 3.12 or newer. Install it with Homebrew or from python.org:

```bash
brew install python@3.12
```

`/usr/bin/python3` is a shim from the Xcode Command Line Tools and is older than 3.12. When the tools are not installed, running it opens a GUI install dialog. The wrapper avoids it: it tries `python3.14`, `python3.13` and `python3.12` first, so a Homebrew or python.org interpreter is found before the shim, and it skips `/usr/bin/python3` when `xcode-select -p` reports no developer tools. It then uses the first candidate that reports 3.12 or newer.

When none qualifies, the wrapper prints an error naming `brew install python@3.12` and python.org, and exits with code 2.

## Run

```bash
./deploy.sh              # report only
./deploy.sh --apply      # write
./refresh.sh             # compare the machine with the clone
```

The wrappers are written for the Bash 3.2 that macOS ships at `/bin/bash`. No newer Bash is needed to deploy or refresh.

The default configuration directory is `~/.claude`, or `$CLAUDE_CONFIG_DIR` when set.

## macOS settings overlay

Deploy composes `settings.json` from `claude/settings.base.json` and `claude/settings.macos.json`. The macOS overlay adds permission deny rules for:

- recursive deletion of `~`, `/System`, `/Library`, `/Applications`, `/Users` and `/usr` contents
- `chmod -R 777 /*` and `chown -R * /`
- `diskutil erase`, `partitionDisk`, and APFS container and volume deletion
- `csrutil`, `nvram`, `spctl --master-disable`, `sysadminctl`, and `dscl . -create` and `-delete`
- `shutdown`, `reboot` and `halt`
- reading `/etc/sudoers`, its drop-in directory and `~/Library/Keychains`
- editing the same three locations

The complete lists, the base rules and the merge behaviour are in [settings.md](settings.md).

## The security-guidance extra needs a newer Bash

`./deploy.sh --extra security-guidance` installs a vendored plugin whose hook launcher, `sg-python.sh`, uses Bash 4 features. Its hooks invoke `bash`, which on macOS resolves to Bash 3.2 unless a newer one comes first on `PATH`. Install one and put it ahead of `/bin`:

```bash
brew install bash
```

Homebrew places it in `/opt/homebrew/bin` on Apple silicon and `/usr/local/bin` on Intel. Make sure that directory precedes `/bin` in the `PATH` that Claude Code starts with. The same applies if you install `security-guidance@claude-plugins-official` from the marketplace; see [install-marketplace.md](install-marketplace.md).

## Case-insensitive volumes

APFS is case-insensitive by default. Deploy compares target paths case-folded and exits with code 2 if two targets differ only by case, rather than letting one overwrite the other.

## Managed settings

Deploy checks `/Library/Application Support/ClaudeCode/managed-settings.json` and `managed-settings.d/*.json` in the same directory. If managed settings disable the `skills-dir` source, the deployed plugins load as nothing and deploy prints a warning. See [troubleshooting.md](troubleshooting.md).
