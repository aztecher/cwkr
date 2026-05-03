#!/usr/bin/env bash
# Daily routine wrapper for cron / launchd.
# Activates the venv and runs daily_routine.py.
#
# Cron example (18:00 JST = 09:00 UTC):
#   0 9 * * * /path/to/cwkr/scripts/run_daily.sh >> /path/to/cwkr/logs/daily.log 2>&1

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$REPO_ROOT/.venv"
LOG_DIR="$REPO_ROOT/logs"

mkdir -p "$LOG_DIR"

echo "=== $(date '+%Y-%m-%d %H:%M:%S %Z') start ==="

# Activate virtualenv
if [[ -f "$VENV/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source "$VENV/bin/activate"
else
    echo "ERROR: virtualenv not found at $VENV. Run setup.sh first." >&2
    exit 1
fi

# Ensure claude CLI is available (it may live outside the venv)
if ! command -v claude &>/dev/null; then
    echo "ERROR: 'claude' CLI not found in PATH." >&2
    echo "       Install Claude Code: https://claude.ai/code" >&2
    exit 1
fi

cd "$REPO_ROOT"

python scripts/daily_routine.py "$@"

echo "=== $(date '+%Y-%m-%d %H:%M:%S %Z') done ==="
