#!/bin/bash
# OPTIONAL 9:31 ET re-render: fetch → render with --postopen (adds the real
# gap/BIG_GAP once the open exists) → publish. NOT loaded automatically —
# quick-260915-va7 built this but left activation to the user:
#
#   launchctl load ~/Library/LaunchAgents/com.johnsontrades.session-conditions-postopen.plist
#
# Safe to run even if the open genuinely isn't in the data yet — today.py
# --postopen falls back to the same pre-open forward render in that case.
# Log: logs/daily.log (shared with run_daily.sh, lines prefixed [postopen]).

set -u
DIR="$(cd "$(dirname "$0")" && pwd)"
PY="$DIR/venv/bin/python"
LOG="$DIR/logs/daily.log"
mkdir -p "$DIR/logs"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') [postopen] $*" >> "$LOG"; }

cd "$DIR" || exit 1
log "=== run start ==="

if ! "$PY" fetch_data.py >> "$LOG" 2>&1; then
    log "FATAL: fetch_data.py failed — page not updated"
    exit 1
fi

if ! "$PY" today.py --postopen >> "$LOG" 2>&1; then
    log "FATAL: today.py --postopen failed — page not updated"
    exit 1
fi

if [ -n "$(git status --porcelain docs/)" ]; then
    git add docs/ >> "$LOG" 2>&1
    AS_OF=$("$PY" -c "import json; print(json.load(open('docs/today.json'))['as_of'])" 2>/dev/null || date +%F)
    git commit -m "chore: postopen page $AS_OF" -- docs/ >> "$LOG" 2>&1
    if git push origin main >> "$LOG" 2>&1; then
        log "published docs/ for $(date +%F)"
    else
        log "FATAL: git push failed — page rendered locally but not published"
        exit 1
    fi
else
    log "docs/ unchanged — nothing to publish"
fi

log "=== run ok ==="
