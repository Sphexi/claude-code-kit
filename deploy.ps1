<#
.SYNOPSIS
    Deploy claude-code-kit into a Claude Code config directory.
.DESCRIPTION
    Resolves a Python 3.12+ interpreter and runs python -m tools.deploy with every argument
    passed through unchanged. Exit code 2 means the run could not proceed.
.PARAMETER Arguments
    Forwarded verbatim to the Python module.
.EXAMPLE
    .\deploy.ps1 --config-dir C:\temp\claude-test
#>
[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Arguments
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'scripts\lib.ps1')
Invoke-KitModule -RepoRoot $PSScriptRoot -Module 'tools.deploy' -Arguments $Arguments
