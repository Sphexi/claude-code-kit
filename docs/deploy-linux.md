# Deploy on Linux

Read [deploy.md](deploy.md) first for the commands and behaviour common to every platform. This page covers what differs on Linux.

## Python

Deploy needs Python 3.12 or newer. Install it with your package manager:

```bash
# Debian, Ubuntu
sudo apt install python3

# Fedora, RHEL and derivatives
sudo dnf install python3

# Arch
sudo pacman -S python
```

Check the version:

```bash
python3 --version
```

If your distribution ships an older default, install a newer interpreter beside it. `deploy.sh` tries `python3.14`, `python3.13`, `python3.12`, `python3` and `python`, in that order, and uses the first that reports 3.12 or newer, so a versioned binary is found even when `python3` is older.

When none qualifies, the wrapper prints an error and exits with code 2.

## Run

```bash
./deploy.sh              # report only
./deploy.sh --apply      # write
./refresh.sh             # compare the machine with the clone
```

The scripts are Bash and need nothing beyond Bash and Python. If the executable bit was lost, run them as `bash deploy.sh`.

The default configuration directory is `~/.claude`, or `$CLAUDE_CONFIG_DIR` when set.

## Windows Subsystem for Linux

Deploy inside WSL uses the WSL home directory and the Linux overlay. It does not touch a Windows-side `~/.claude`. To deploy to Windows, run `deploy.ps1` from Windows; see [deploy-windows.md](deploy-windows.md).

## Linux settings overlay

Deploy composes `settings.json` from `claude/settings.base.json` and `claude/settings.linux.json`. The Linux overlay adds permission deny rules for:

- recursive deletion of `~`, `/etc`, `/usr`, `/var` and `/boot` contents
- disk and swap tools: `mkswap`, `fdisk`, `parted`
- `chmod -R 777 /*` and `chown -R * /`
- `shutdown`, `reboot`, `halt`, `init 0` and `init 6`
- reading `/etc/shadow`, `/etc/gshadow` and the sudoers files
- editing `/etc/shadow`, the sudoers files and `/boot`

The complete lists, the base rules and the merge behaviour are in [settings.md](settings.md).

## Managed settings

Deploy checks `/etc/claude-code/managed-settings.json` and `/etc/claude-code/managed-settings.d/*.json`. If an administrator's managed settings disable the `skills-dir` source, the deployed plugins load as nothing and deploy prints a warning. See [troubleshooting.md](troubleshooting.md).
