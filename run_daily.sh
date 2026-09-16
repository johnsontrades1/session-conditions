#!/bin/bash
# Daily pre-open pipeline: fetch → render → publish (GitHub Pages via docs/ on main).
# Run by LaunchAgent com.johnsontrades.session-conditions weekdays 7:40 AM CT.
# Log: logs/daily.log. A stale date on the published page means this failed — check the log.

set -u
DIR="$(cd "$(dirname "$0")" && pwd)"
PY="$DIR/venv/bin/python"
LOG="$DIR/logs/daily.log"
mkdir -p "$DIR/logs"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG"; }

cd "$DIR" || exit 1
log "=== run start ==="

if ! "$PY" fetch_data.py >> "$LOG" 2>&1; then
    log "FATAL: fetch_data.py failed — page not updated"
    exit 1
fi

if ! "$PY" today.py >> "$LOG" 2>&1; then
    log "FATAL: today.py failed — page not updated"
    exit 1
fi

if [ -n "$(git status --porcelain docs/)" ]; then
    git add docs/ >> "$LOG" 2>&1
    AS_OF=$("$PY" -c "import json; print(json.load(open('docs/today.json'))['as_of'])" 2>/dev/null || date +%F)
    git commit -m "chore: daily page $AS_OF" -- docs/ >> "$LOG" 2>&1
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
