#!/usr/bin/env bash
# Logging and Python discovery shared by the wrapper scripts. Source it; do not run it.

MIN_PYTHON_MINOR=12

_log() {
    local fd="$1" color="$2" label="$3" message="$4"
    if [ -t "$fd" ]; then
        printf '%b[%s]%b %s\n' "$color" "$label" '\033[0m' "$message" >&"$fd"
    else
        printf '[%s] %s\n' "$label" "$message" >&"$fd"
    fi
}

log_info()  { _log 1 '\033[0;32m' INFO  "$*"; }
log_warn()  { _log 2 '\033[1;33m' WARN  "$*"; }
log_error() { _log 2 '\033[0;31m' ERROR "$*"; }

is_installed() { command -v "$1" >/dev/null 2>&1; }

# The Xcode Command Line Tools shim at /usr/bin/python3 opens a GUI installer
# when the tools are absent, even for `python3 -c`.
_is_clt_shim() {
    [ "$(uname -s)" = "Darwin" ] || return 1
    [ "$(command -v "$1")" = "/usr/bin/python3" ] || return 1
    ! xcode-select -p >/dev/null 2>&1
}

# Print the first interpreter that is Python 3.MIN_PYTHON_MINOR or newer.
find_python() {
    local candidate
    for candidate in python3.14 python3.13 python3.12 python3 python; do
        is_installed "$candidate" || continue
        if _is_clt_shim "$candidate"; then
            continue
        fi
        if "$candidate" -c "import sys; sys.exit(0 if sys.version_info >= (3, ${MIN_PYTHON_MINOR}) else 1)" >/dev/null 2>&1; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    return 1
}

require_python() {
    local found
    if ! found="$(find_python)"; then
        log_error "No Python 3.${MIN_PYTHON_MINOR}+ interpreter found on PATH."
        log_error "Install one: 'brew install python@3.12' (macOS), your package manager (Linux), or https://www.python.org/downloads/"
        return 1
    fi
    printf '%s\n' "$found"
}
