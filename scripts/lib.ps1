# Logging and Python discovery shared by the wrapper scripts. Dot-source it.

$script:MinPythonMinor = 12

function Write-KitLog {
    <#
    .SYNOPSIS
        Write one prefixed line: Info to standard output, Warn and Error to standard error.
    .PARAMETER Level
        Info, Warn or Error.
    .PARAMETER Message
        The text to write.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [ValidateSet('Info', 'Warn', 'Error')]
        [string]$Level,

        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    $line = '[{0}] {1}' -f $Level.ToUpper(), $Message
    if ($Level -eq 'Info') {
        [Console]::Out.WriteLine($line)
    }
    else {
        [Console]::Error.WriteLine($line)
    }
}

function Get-PythonCommand {
    <#
    .SYNOPSIS
        Find a Python 3.12 or newer interpreter.
    .OUTPUTS
        System.String[]. The executable followed by any fixed arguments (for the py
        launcher), or $null when no interpreter qualifies.
    #>
    [CmdletBinding()]
    param()

    $probe = 'import sys; sys.exit(0 if sys.version_info >= (3, {0}) else 1)' -f $script:MinPythonMinor
    $candidates = @(
        @('py', '-3'),
        @('python'),
        @('python3')
    )
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        foreach ($candidate in $candidates) {
            $exe = $candidate[0]
            $fixed = @($candidate | Select-Object -Skip 1)
            if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
            & $exe @fixed -c $probe 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) { return $candidate }
        }
    }
    finally {
        $ErrorActionPreference = $previous
    }
    return $null
}

function Invoke-KitModule {
    <#
    .SYNOPSIS
        Run a Python module from the repository root, then exit with its exit code.
    .DESCRIPTION
        Exits the calling script itself so the module's output streams to the
        console instead of being collected as a return value. Exit code 2 means no
        suitable Python was found.
    .PARAMETER RepoRoot
        Directory the module is resolved from.
    .PARAMETER Module
        Dotted module name, for example tools.deploy.
    .PARAMETER Arguments
        Arguments forwarded to the module unchanged.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot,

        [Parameter(Mandatory = $true)]
        [string]$Module,

        [string[]]$Arguments
    )

    $python = Get-PythonCommand
    if (-not $python) {
        Write-KitLog -Level Error -Message ('No Python 3.{0}+ interpreter found. Install one from https://www.python.org/downloads/ or with: winget install Python.Python.3.12' -f $script:MinPythonMinor)
        exit 2
    }
    $exe = $python[0]
    $fixed = @($python | Select-Object -Skip 1)

    Push-Location $RepoRoot
    try {
        & $exe @fixed -m $Module @Arguments
        $code = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
    exit $code
}
