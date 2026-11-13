#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=scripts/lib.sh
source "${REPO_ROOT}/scripts/lib.sh"

python_bin="$(require_python)" || exit 2
cd "$REPO_ROOT"
exec "$python_bin" -m tools.reconcile "$@"
