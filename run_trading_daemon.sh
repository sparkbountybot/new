#!/bin/bash
# Alpaca Trading Engine - Persistent Background Runner
# Runs every 5 minutes during market hours (9:30-16:00 ET Mon-Fri)

RUN_DIR="/sandbox/new"
LOG_FILE="/sandbox/new/data/engine_daemon.log"
PID_FILE="/sandbox/new/data/engine_daemon.pid"

mkdir -p "$RUN_DIR/data"

while true; do
    NOW=$(date +%H)
    NOW_WD=$(date +%u)
    
    # Only run during market hours (14:00-20:00 UTC = 9:30-15:30 ET)
    if [ "$NOW_WD" -ge 1 ] && [ "$NOW_WD" -le 5 ] && [ "$NOW" -ge 14 ] && [ "$NOW" -lt 21 ]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') - Running trading cycle..." >> "$LOG_FILE"
        cd "$RUN_DIR" && python3 trading_engine.py run >> "$LOG_FILE" 2>&1
        echo "$(date '+%Y-%m-%d %H:%M:%S') - Cycle complete" >> "$LOG_FILE"
    fi
    
    sleep 300  # 5 minutes
done
