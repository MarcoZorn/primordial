#!/usr/bin/env bash
# Keeps the research run alive. Restarts the daemon if the process dies for any
# reason; the daemon itself reseeds the dish if the population hits zero, so
# extinction never ends the run either.
set -u
DIR="${PRIMORDIAL_DIR:-$HOME/Documents/PROJECTS/Neural_netowrks}"
RUN="${1:-runs/genesis}"
cd "$DIR" || exit 1
LOG="runs/watchdog.log"

running() {
    local f="$RUN/daemon.pid"
    [ -f "$f" ] && kill -0 "$(cat "$f" 2>/dev/null)" 2>/dev/null
}

echo "$(date '+%F %T') watchdog started for $RUN" >> "$LOG"
while true; do
    if ! running; then
        echo "$(date '+%F %T') daemon not running - starting it" >> "$LOG"
        setsid nohup python3 daemon.py --run "$RUN" --pop 500 \
            --save-every 10000 --log-every 1000 --report-every 50000 \
            >> runs/genesis.log 2>&1 < /dev/null &
        sleep 10
    fi
    sleep 60
done
