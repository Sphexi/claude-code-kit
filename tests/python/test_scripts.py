"""Static checks on the wrapper scripts: portability and the no-logic rule."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SH_FILES = sorted([*ROOT.glob("*.sh"), *(ROOT / "scripts").glob("*.sh")])
PS_FILES = sorted([*ROOT.glob("*.ps1"), *(ROOT / "scripts").glob("*.ps1")])
SH_WRAPPERS = [ROOT / "deploy.sh", ROOT / "refresh.sh"]
PS_WRAPPERS = [ROOT / "deploy.ps1", ROOT / "refresh.ps1"]

BASH_32_VIOLATIONS = {
    "associative array": r"\b(declare|typeset)\s+-A\b",
    "mapfile/readarray": r"\b(mapfile|readarray)\b",
    "case-modifying expansion": r"\$\{[A-Za-z_][A-Za-z0-9_]*(,,|\^\^|,|\^)\}",
    "&>> redirect": r"&>>",
    "|& pipe": r"\|&",
    "readlink -f": r"\breadlink\s+-f\b",
    "realpath": r"\brealpath\b",
    "sed -i": r"\bsed\s+-[A-Za-z]*i",
    "grep -P": r"\bgrep\s+-[A-Za-z]*P",
    "date -d": r"\bdate\s+-d\b",
    "stat -c": r"\bstat\s+-c\b",
    "xargs -r": r"\bxargs\s+-r\b",
    "find -printf": r"\bfind\b[^\n]*-printf",
    "sort -V": r"\bsort\s+-[A-Za-z]*V",
    "local -n": r"\blocal\s+-n\b",
    "transform expansion": r"\$\{[^}]*@[QEPAa]\}",
    "globstar": r"\bshopt\s+-s\s+globstar\b",
    "coproc": r"\bcoproc\b",
}


def _code_lines(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [ln for ln in lines if ln.strip() and not ln.lstrip().startswith("#")]


def test_script_inventory_is_not_empty() -> None:
    assert len(SH_FILES) >= 3 and len(PS_FILES) >= 3


@pytest.mark.parametrize("path", PS_FILES, ids=lambda p: p.name)
def test_powershell_files_are_ascii_only(path: Path) -> None:
    data = path.read_bytes()

    assert data.isascii(), f"non-ASCII byte in {path.name}"
    assert b"\r\n" not in data


@pytest.mark.parametrize("path", SH_FILES, ids=lambda p: p.name)
def test_shell_files_avoid_bash_4_and_gnu_only_constructs(path: Path) -> None:
    code = "\n".join(_code_lines(path))

    found = [name for name, pattern in BASH_32_VIOLATIONS.items() if re.search(pattern, code)]

    assert found == []
    assert path.read_bytes().startswith(b"#!/usr/bin/env bash\n")
    assert b"\r\n" not in path.read_bytes()


@pytest.mark.parametrize("path", SH_WRAPPERS, ids=lambda p: p.name)
def test_shell_wrappers_resolve_python_and_exec_with_all_arguments(path: Path) -> None:
    code = _code_lines(path)

    assert "set -euo pipefail" in code
    assert code[-1].startswith('exec "$python_bin" -m tools.') and code[-1].endswith('"$@"')
    assert len(code) <= 8


def test_find_python_probes_versioned_interpreters_before_the_system_shim() -> None:
    text = (ROOT / "scripts" / "lib.sh").read_text(encoding="utf-8")
    order = re.search(r"for candidate in ([^;]+); do", text)

    assert order is not None
    names = order.group(1).split()
    assert names.index("python3.12") < names.index("python3") < names.index("python")


@pytest.mark.parametrize("path", PS_WRAPPERS, ids=lambda p: p.name)
def test_powershell_wrappers_only_dot_source_the_library_and_delegate(path: Path) -> None:
    code = _code_lines(path)

    assert "$ErrorActionPreference = 'Stop'" in code
    assert any(ln.startswith(". (Join-Path $PSScriptRoot 'scripts") for ln in code)
    assert code[-1].startswith("Invoke-KitModule -RepoRoot $PSScriptRoot -Module 'tools.")


@pytest.mark.parametrize("path", PS_FILES, ids=lambda p: p.name)
def test_powershell_files_use_only_5_1_syntax_and_document_functions(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    code = "\n".join(_code_lines(path))
    functions = re.findall(r"^function\s+([A-Za-z-]+)\s*\{\s*\n\s*<#", text, re.MULTILINE)
    declared = re.findall(r"^function\s+([A-Za-z-]+)", text, re.MULTILINE)

    assert functions == declared
    assert "Write-Host" not in code
    assert not re.search(r"\?\?|\?\.|&&|\|\||\?\s*\(", re.sub(r"'[^']*'|\"[^\"]*\"", "", code))
