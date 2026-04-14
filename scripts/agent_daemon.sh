#!/usr/bin/env bash
# agent_daemon.sh — Reads from agent FIFO and dispatches to FastAPI.
# Usage: bash scripts/agent_daemon.sh <agent_name> [api_url]
#
# In production: run as the agent's Linux user (systemd handles this).
# In WSL dev: run via run_daemons.sh or manually.

set -euo pipefail

AGENT="${1:?Usage: $0 <agent_name> [api_url]}"
API_URL="${2:-http://localhost:8000}"
PIPE="/var/aurelia/queue/${AGENT}"

echo "[daemon:${AGENT}] Starting. FIFO: ${PIPE}, API: ${API_URL}"

# Wait for FIFO to exist (WSL: may need setup first)
if [[ ! -p "$PIPE" ]]; then
    echo "[daemon:${AGENT}] WARNING: ${PIPE} is not a named pipe. Waiting up to 30s..."
    for i in $(seq 1 30); do
        sleep 1
        if [[ -p "$PIPE" ]]; then
            echo "[daemon:${AGENT}] FIFO appeared."
            break
        fi
    done
    if [[ ! -p "$PIPE" ]]; then
        echo "[daemon:${AGENT}] ERROR: ${PIPE} still not a pipe. Run setup_agent.sh first."
        exit 1
    fi
fi

echo "[daemon:${AGENT}] Listening on ${PIPE}..."

while true; do
    # Blocking read from FIFO
    if read -r line < "$PIPE" 2>/dev/null; then
        if [[ -z "$line" ]]; then
            continue
        fi
        echo "[daemon:${AGENT}] Received item, dispatching..."
        response=$(curl -s -w "\n%{http_code}" -X POST "${API_URL}/internal/process" \
            -H "Content-Type: application/json" \
            -d "$line" \
            --max-time 300 2>&1)
        http_code=$(echo "$response" | tail -1)
        body=$(echo "$response" | head -n -1)
        if [[ "$http_code" == "200" ]]; then
            echo "[daemon:${AGENT}] OK: $body"
        else
            echo "[daemon:${AGENT}] ERROR HTTP ${http_code}: $body"
        fi
    fi
done
