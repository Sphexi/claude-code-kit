# Deploy on Windows

Read [deploy.md](deploy.md) first for the commands and behaviour common to every platform. This page covers what differs on Windows. Windows uses the PowerShell scripts, `deploy.ps1` and `refresh.ps1`.

## PowerShell

The scripts target Windows PowerShell 5.1 and run unchanged in PowerShell 7. They contain only ASCII characters, because 5.1 reads a script without a byte-order mark as ANSI.

Run them from the repository root:

```powershell
.\deploy.ps1             # report only
.\deploy.ps1 --apply     # write
.\refresh.ps1            # compare the machine with the clone
```

Arguments are forwarded to the Python module unchanged, so options keep their double-dash form: `.\deploy.ps1 --plugins sphexi-core,sphexi-review --apply`. The script exits with the module's exit code; 2 means the run could not proceed.

## Execution policy

If PowerShell refuses to run the scripts because of the execution policy, bypass it for one invocation instead of changing the machine policy:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\deploy.ps1 --apply
```

Use `pwsh` in place of `powershell` for PowerShell 7. Files extracted from a downloaded archive may carry a download mark that triggers the same prompt; `Unblock-File .\deploy.ps1, .\refresh.ps1, .\scripts\lib.ps1` clears it.

## Python

Deploy needs Python 3.12 or newer. Install it from python.org or with winget:

```powershell
winget install Python.Python.3.12
```

The script tries `py -3`, then `python`, then `python3`, and uses the first that exits successfully on a 3.12-or-newer check. A `python` alias that only opens the Microsoft Store does not pass that check and is passed over. When no candidate qualifies, the script prints an error and exits with code 2.

Open a new terminal after installing so that `PATH` updates apply.

## Configuration directory

The default is `.claude` under your user profile, or `%CLAUDE_CONFIG_DIR%` when set. Use `--config-dir` to point elsewhere, for example a scratch directory:

```powershell
.\deploy.ps1 --config-dir $env:TEMP\claude-test --apply
```

## Git Bash and hooks

Claude Code runs shell-form plugin hooks with Git Bash when it is installed, and with PowerShell otherwise. The `sphexi-core` hook runs `cat` on a file inside the plugin, which works in both: PowerShell aliases `cat` to `Get-Content`.

The vendored `security-guidance` plugin invokes `bash` explicitly, so installing it, either with `--extra security-guidance` or from `claude-plugins-official`, needs Git Bash or another `bash` on `PATH`. See [install-marketplace.md](install-marketplace.md).

## Windows settings overlay

Deploy composes `settings.json` from `claude/settings.base.json` and `claude/settings.windows.json`. The Windows overlay adds permission deny rules for:

- `runas`
- recursive deletion of `C:\`, by `rm -rf`, `rd /s /q` and `Remove-Item -Recurse -Force`
- disk and boot tools: `format`, `diskpart`, `bcdedit`, `sfc`, `dism`, `cipher /w:`
- ownership and registry changes: `takeown`, `icacls C:\Windows`, `reg add`, `reg delete`, `regedit`
- account, service and firewall changes: `net user`, `net localgroup`, `sc delete`, `sc stop`, `sc config`, `netsh advfirewall` and `netsh interface` changes
- `shutdown`
- changing into `C:\Windows`, `C:\Program Files`, `C:\ProgramData` and other system directories
- reading and editing system locations under `C:/Windows`, `C:/Program Files`, `C:/ProgramData`, `C:/System Volume Information`, `C:/Recovery` and `C:/$Recycle.Bin`

The complete lists, the base rules and the merge behaviour are in [settings.md](settings.md).

## Managed settings

Deploy checks `C:\Program Files\ClaudeCode\managed-settings.json` and `managed-settings.d\*.json`. If managed settings disable the `skills-dir` source, the deployed plugins load as nothing and deploy prints a warning. See [troubleshooting.md](troubleshooting.md).

## Read-only files

When uninstall or a retirement removes a file that is marked read-only, deploy clears the attribute and deletes it. It only removes files whose content still matches what it wrote.
