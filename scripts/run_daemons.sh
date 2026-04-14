#!/usr/bin/env bash
# run_daemons.sh — WSL-friendly: starts all daemons in the background.
# Usage: bash scripts/run_daemons.sh [api_url]
#
# This is the development replacement for systemd services.
# In production on real Linux, use the systemd service files instead.
#
# What this starts:
#   - Scheduler daemon (checks pending items every 60s)
#   - Agent daemon per agent (reads from FIFO, dispatches to API)
#
# Logs go to /var/aurelia/logs/{name}.log
# PIDs written to /var/aurelia/pids/{name}.pid
#
# To stop all: bash scripts/stop_daemons.sh
# To view logs: tail -f /var/aurelia/logs/scheduler.log

set -euo pipefail

API_URL="${1:-http://localhost:8000}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="/var/aurelia/logs"
PID_DIR="/var/aurelia/pids"
AGENTS=("personal" "cooking" "finance" "mayor" "janitor")

mkdir -p "$LOG_DIR" "$PID_DIR"

# ── Helper ──────────────────────────────────────────────────────────────────────

start_daemon() {
    local name="$1"
    local cmd="$2"
    local log="${LOG_DIR}/${name}.log"
    local pid_file="${PID_DIR}/${name}.pid"

    if [[ -f "$pid_file" ]]; then
        local old_pid
        old_pid=$(cat "$pid_file")
        if kill -0 "$old_pid" 2>/dev/null; then
            echo "[run_daemons] ${name} already running (PID ${old_pid}). Skipping."
            return
        else
            rm -f "$pid_file"
        fi
    fi

    echo "[run_daemons] Starting ${name}..."
    # shellcheck disable=SC2086
    bash -c "$cmd" >> "$log" 2>&1 &
    local pid=$!
    echo "$pid" > "$pid_file"
    echo "[run_daemons] ${name} started (PID ${pid}). Log: ${log}"
}

# ── Scheduler ──────────────────────────────────────────────────────────────────

start_daemon "scheduler" "bash '${SCRIPT_DIR}/scheduler_daemon.sh' '${API_URL}'"

# ── Agent daemons ──────────────────────────────────────────────────────────────

for agent in "${AGENTS[@]}"; do
    start_daemon "daemon-${agent}" "bash '${SCRIPT_DIR}/agent_daemon.sh' '${agent}' '${API_URL}'"
done

echo ""
echo "[run_daemons] All daemons started."
echo "[run_daemons] Logs: ${LOG_DIR}/"
echo "[run_daemons] PIDs: ${PID_DIR}/"
echo "[run_daemons] To stop: bash ${SCRIPT_DIR}/stop_daemons.sh"
echo "[run_daemons] To view scheduler log: tail -f ${LOG_DIR}/scheduler.log"
