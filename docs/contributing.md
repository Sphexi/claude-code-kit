# Contributing

## Development setup

Python 3.12 or newer. The shipped code uses only the standard library; `pytest` is the one development dependency.

```bash
git clone https://github.com/sphexi/claude-code-kit.git
cd claude-code-kit
python3 -m venv .venv
source .venv/bin/activate
python -m pip install pytest
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`.

Try deploy and refresh against a scratch configuration directory, never your own:

```bash
./deploy.sh --config-dir /tmp/claude-test
./deploy.sh --config-dir /tmp/claude-test --apply
./refresh.sh --config-dir /tmp/claude-test
```

## Running tests

```bash
python -m pytest tests/python -q              # fast suite; excludes tests marked slow
python -m pytest tests/python -q -m slow      # smoke: deploy, refresh, uninstall through the platform wrapper
python -m pytest tests/python/test_deploy_layout.py -q    # one file
```

The default run adds `-m "not slow"` from `pytest.ini`. A test that spawns a subprocess or deploys a tree is marked `slow`.

Run the full fast suite once before you start and once at the end. Between those, run only the tests that cover what you changed. Run the `slow` tests when you change deploy, refresh, the wrappers or settings composition.

## Generated files

Never edit these by hand: `plugins/`, `.claude-plugin/marketplace.json`, `THIRD_PARTY_NOTICES.md`, `docs/plugins.md`, regions between `TERSENESS` or `CODE-STANDARDS` markers, `claude/plugins.manifest.json`, and `claude/vendor/*/UPSTREAM.md`. Change the source, regenerate, and commit source and output together.

```bash
python build/inline_shared.py              # regenerate inlined shared blocks
python build/build_plugins.py              # regenerate every generated path
python build/inline_shared.py --check      # exit 1 if any target is stale
python build/build_plugins.py --check      # exit 1 on drift; writes nothing
```

When several sources change, run `python tools/vendor_sync.py`, then `inline_shared.py`, then `build_plugins.py`. See [customizing.md](customizing.md) and [vendored-upstreams.md](vendored-upstreams.md).

`docs/plugins.md` is generated from `build/templates/plugins-catalogue.md` and the plugin sources. To change it, change those.

## Code style

**Python** (`build/`, `tools/`, `tests/`): Python 3.12 or newer and the standard library only in shipped code. Type hints on every signature, `pathlib.Path` for paths, `argparse` for CLIs, explicit `encoding="utf-8"` and `newline="\n"` on every text write. Generated output is deterministic: sorted iteration, `json.dumps(indent=2, ensure_ascii=False)` with a trailing newline, no timestamps outside `UPSTREAM.md` and the manifest. Names that decide collisions use `str.casefold()`.

**Bash** (`*.sh`, `scripts/lib.sh`): `set -euo pipefail`, every expansion quoted, and compatible with Bash 3.2. That rules out associative arrays, `mapfile`, `${var,,}`, `&>>`, `|&`, `readlink -f`, `sed -i` without a suffix, and `grep -P`. Wrappers resolve an interpreter and `exec` the Python module; they contain no logic. ShellCheck-clean under `shellcheck -x --source-path=SCRIPTDIR`.

**PowerShell** (`*.ps1`, `scripts/lib.ps1`): Windows PowerShell 5.1, so no `?:`, `??`, `&&` or `||`. `$ErrorActionPreference = 'Stop'`, comment-based help on every function, approved verbs, ASCII only, and PSScriptAnalyzer-clean with no suppressions.

**Markdown payload**: YAML frontmatter first with no leading blank line. Agents carry `name`, `description`, `model` and optionally `tools`. Output styles carry `name`, `description` and `keep-coding-instructions`. Skills carry `name` and a `description` that names the triggers. Wording is neutral: no personal names, machine names or references to how the repository was built. `tests/python/test_sanitization.py` enforces a pattern list.

**Comments and tests** follow the standards in [terseness-and-standards.md](terseness-and-standards.md): no comment unless it states a constraint the code cannot, and tests sized to the project tier. The project tier is Light. Rationale and trade-offs belong in `docs/`, not in source comments.

## Deploy-affecting changes

Any code path that removes, overwrites or truncates a file under a live configuration directory must be reachable only with `--apply`, have a test proving it does nothing without `--apply`, and print the absolute path of every affected file before acting.

A change to deploy, refresh, the wrappers or settings composition states in the pull request which of Linux, macOS and Windows it was run on and which it was only reasoned about. Name all three, even when the answer is "not run".

## Continuous integration

`.github/workflows/ci.yml` runs on pushes to `main`, pull requests and manual dispatch with read-only permissions. Run the commands of a job locally before changing that job.

| Job | Runs on | Command to reproduce |
|---|---|---|
| `tests` | Linux, macOS, Windows; Python 3.12 | `python -m pytest tests/python -q` |
| `smoke` | Linux, macOS, Windows | `python -m pytest tests/python -q -m slow` |
| `generated` | Linux | `python build/inline_shared.py --check`, `python build/build_plugins.py --check`, and `python build/build_plugins.py --zip --output-dir <dir>` |
| `shellcheck` | Linux | `shellcheck -x --source-path=SCRIPTDIR deploy.sh refresh.sh scripts/lib.sh` |
| `psscriptanalyzer` | Windows | `Invoke-ScriptAnalyzer -Path deploy.ps1, refresh.ps1, scripts/lib.ps1` after `Install-Module PSScriptAnalyzer -Scope CurrentUser` |
| `plugin-validate` | Linux | `claude plugin validate . --strict`, then `claude plugin validate plugins/<name> --strict` for each directory under `plugins/` |

The smoke job runs the wrappers under `/bin/bash` on macOS and under PowerShell on Windows. A change that was run on one platform and reasoned about on the others is incomplete until the smoke job has passed on all three.

## Pull requests

- Describe the behaviour change and name the page under `docs/` that you updated. When behaviour changes, update the page that describes it in the same change.
- Include regenerated files with the source change that produced them. A change that leaves either `--check` command failing does not pass CI.
- Do not rewrite history, force-push, or create tags. Releases are tagged by a maintainer; see [releasing.md](releasing.md).
- Add a test for behaviour you change, sized to the Light tier: a test earns its place only if deleting it would make a realistic failure harder to catch.
