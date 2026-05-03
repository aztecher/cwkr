#!/usr/bin/env bash
# Initial setup for the cwkr daily routine.
# Run once after cloning the repository.
#
# Usage:
#   bash setup.sh [--cron]          # Linux: installs crontab entry
#   bash setup.sh [--launchd]       # macOS: installs launchd plist
#   bash setup.sh                   # setup only, no scheduler

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$REPO_ROOT/.venv"
SCHEDULE_HOUR_UTC=9   # 09:00 UTC = 18:00 JST

echo "=== cwkr setup ==="
echo "Repo: $REPO_ROOT"

# ── 1. Python virtualenv ──────────────────────────────────────────────
echo ""
echo "1. Creating virtualenv..."
python3 -m venv "$VENV"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
pip install --quiet --upgrade pip
pip install --quiet -r "$REPO_ROOT/scripts/requirements.txt"
echo "   Done: $VENV"

# ── 2. Check claude CLI ───────────────────────────────────────────────
echo ""
echo "2. Checking Claude Code CLI..."
if command -v claude &>/dev/null; then
    echo "   Found: $(which claude)"
else
    echo "   WARNING: 'claude' CLI not found."
    echo "   Install Claude Code from https://claude.ai/code and authenticate."
fi

# ── 3. Check git remote ───────────────────────────────────────────────
echo ""
echo "3. Git remote:"
git -C "$REPO_ROOT" remote -v

# ── 4. Make scripts executable ────────────────────────────────────────
chmod +x "$REPO_ROOT/scripts/run_daily.sh"

# ── 5. Optional scheduler setup ───────────────────────────────────────
INSTALL_CRON=false
INSTALL_LAUNCHD=false

for arg in "$@"; do
    case "$arg" in
        --cron)     INSTALL_CRON=true ;;
        --launchd)  INSTALL_LAUNCHD=true ;;
    esac
done

# ── Linux cron ────────────────────────────────────────────────────────
if $INSTALL_CRON; then
    echo ""
    echo "4. Installing crontab entry (09:00 UTC daily)..."
    CRON_LINE="0 $SCHEDULE_HOUR_UTC * * * $REPO_ROOT/scripts/run_daily.sh >> $REPO_ROOT/logs/daily.log 2>&1"
    # Add only if not already present
    ( crontab -l 2>/dev/null | grep -v "run_daily.sh"; echo "$CRON_LINE" ) | crontab -
    echo "   Installed:"
    echo "   $CRON_LINE"
fi

# ── macOS launchd ─────────────────────────────────────────────────────
if $INSTALL_LAUNCHD; then
    echo ""
    echo "4. Installing launchd plist (09:00 UTC daily)..."
    PLIST_DIR="$HOME/Library/LaunchAgents"
    PLIST_FILE="$PLIST_DIR/com.cwkr.daily.plist"
    mkdir -p "$PLIST_DIR"
    cat > "$PLIST_FILE" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.cwkr.daily</string>
    <key>ProgramArguments</key>
    <array>
        <string>$REPO_ROOT/scripts/run_daily.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>$SCHEDULE_HOUR_UTC</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>$REPO_ROOT/logs/daily.log</string>
    <key>StandardErrorPath</key>
    <string>$REPO_ROOT/logs/daily.log</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
PLIST
    launchctl load "$PLIST_FILE" 2>/dev/null || true
    echo "   Installed: $PLIST_FILE"
    echo "   To unload: launchctl unload $PLIST_FILE"
fi

# ── Summary ───────────────────────────────────────────────────────────
echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Authenticate Claude Code:  claude login"
echo "  2. (Optional) Set GitHub token: export GITHUB_TOKEN=ghp_..."
echo "  3. Test a manual run:         scripts/run_daily.sh --no-push"
echo "  4. Full run with push:        scripts/run_daily.sh"
echo ""
if ! $INSTALL_CRON && ! $INSTALL_LAUNCHD; then
    echo "To install scheduler:"
    echo "  macOS: bash setup.sh --launchd"
    echo "  Linux: bash setup.sh --cron"
fi
