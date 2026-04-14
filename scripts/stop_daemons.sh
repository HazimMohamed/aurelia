#!/usr/bin/env bash
# stop_daemons.sh — Stop all Aurelia daemons started by run_daemons.sh.

set -euo pipefail

PID_DIR="/var/aurelia/pids"

if [[ ! -d "$PID_DIR" ]]; then
    echo "[stop_daemons] No PID directory found at ${PID_DIR}. Nothing to stop."
    exit 0
fi

stopped=0
for pid_file in "${PID_DIR}"/*.pid; do
    [[ -f "$pid_file" ]] || continue
    name=$(basename "$pid_file" .pid)
    pid=$(cat "$pid_file")
    if kill -0 "$pid" 2>/dev/null; then
        echo "[stop_daemons] Stopping ${name} (PID ${pid})..."
        kill "$pid"
        rm -f "$pid_file"
        ((stopped++))
    else
        echo "[stop_daemons] ${name} (PID ${pid}) not running, cleaning up."
        rm -f "$pid_file"
    fi
done

echo "[stop_daemons] Stopped ${stopped} daemon(s)."
