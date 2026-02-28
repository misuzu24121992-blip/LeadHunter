#!/bin/bash
# LeadHunter Watchdog — keeps server alive + daily scan
# Runs in background via .zprofile on login
#
# Features:
#   - Starts server if not running
#   - Checks every 60s, auto-restarts on crash
#   - Runs daily scan + Vercel sync at 7:30 AM
#   - Logs to server_watchdog.log

WORKDIR="/Users/ishtelte/Documents/LeadHunter"
LOGFILE="$WORKDIR/server_watchdog.log"
SCAN_DONE=""

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOGFILE"
}

start_server() {
    cd "$WORKDIR" || return
    lsof -ti :8000 | xargs kill -9 2>/dev/null
    sleep 1
    nohup /usr/bin/python3 server.py >> "$WORKDIR/server_output.log" 2>&1 &
    log "🚀 Server started (PID: $!)"
}

run_daily_scan() {
    log "🔍 Daily scan started..."
    cd "$WORKDIR" || return
    curl -s -X POST http://localhost:8000/api/run-scan/leads -m 600 >> "$LOGFILE" 2>&1
    log "📤 Syncing to Vercel..."
    /usr/bin/python3 sync_to_vercel.py >> "$LOGFILE" 2>&1
    log "✅ Daily scan + sync complete"
}

# Main loop
log "========== Watchdog started =========="

while true; do
    # Check if server process is alive (NOT http — avoids killing during heavy scans)
    if ! pgrep -f "python3 server.py" > /dev/null 2>&1 && ! lsof -i :8000 -sTCP:LISTEN > /dev/null 2>&1; then
        log "⚠️  Server down — restarting..."
        start_server
        sleep 3
    fi

    # Check if it's 7:30 AM and scan hasn't run today
    CURRENT_HOUR=$(date '+%H')
    CURRENT_MIN=$(date '+%M')
    TODAY=$(date '+%Y-%m-%d')

    if [ "$CURRENT_HOUR" = "07" ] && [ "$CURRENT_MIN" -ge 30 ] && [ "$CURRENT_MIN" -le 31 ] && [ "$SCAN_DONE" != "$TODAY" ]; then
        run_daily_scan
        SCAN_DONE="$TODAY"
    fi

    sleep 60
done
