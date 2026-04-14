#!/usr/bin/env bash
# scheduler_daemon.sh — Runs the Python scheduler daemon.
# Usage: bash scripts/scheduler_daemon.sh [api_url]
#
# In production: run as 'aurelia' system user (systemd handles this).
# In WSL dev: run via run_daemons.sh or manually.

set -euo pipefail

API_URL="${1:-http://localhost:8000}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="${SCRIPT_DIR}/../src"

echo "[scheduler] Starting scheduler daemon. API: ${API_URL}"

cd "$SRC_DIR"
exec python3 -c "
import sys
sys.path.insert(0, '.')
from scheduler import SchedulerDaemon
daemon = SchedulerDaemon(api_url='${API_URL}')
try:
    daemon.run()
except KeyboardInterrupt:
    daemon.stop()
    print('[scheduler] Stopped.')
"
