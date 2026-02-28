#!/bin/bash
# Ensure LeadHunter server is running on port 8000
# Called by crontab every 5 minutes

WORKDIR="/Users/ishtelte/Documents/LeadHunter"
PIDFILE="$WORKDIR/.server.pid"
LOGFILE="$WORKDIR/server_watchdog.log"

# Check if server PROCESS is alive (not HTTP — avoids killing during heavy scans)
if pgrep -f "python3 server.py" > /dev/null 2>&1; then
    exit 0  # Process is running, don't touch it
fi

# Also check if anything is listening on port 8000
if lsof -i :8000 -sTCP:LISTEN > /dev/null 2>&1; then
    exit 0  # Port is bound, server is alive
fi

# Server is truly down — restart it
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ⚠️  Server down — restarting..." >> "$LOGFILE"
cd "$WORKDIR" || exit 1

# Kill any stale process
lsof -ti :8000 | xargs kill -9 2>/dev/null
sleep 1

# Start server in background
nohup /usr/bin/python3 server.py >> "$WORKDIR/server_output.log" 2>&1 &
echo $! > "$PIDFILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 🚀 Server started (PID: $!)" >> "$LOGFILE"
