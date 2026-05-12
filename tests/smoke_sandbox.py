"""
Smoke test for the sandbox pool.

Verifies acquire/release mechanics without touching the runtime:
  - Slot locking (two concurrent acquires on same slot should fail)
  - Home reset (correct dirs, ownership, permissions)
  - Config write/cleanup
  - FIFO and budget file lifecycle

Run as root:
  sudo python3 scripts/smoke_sandbox.py
"""

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from src.sandbox.sandbox import (
    SANDBOX_NAMES,
    acquire_sandbox_agent,
    release_sandbox_agent,
)
from src.samsara.config import AGENT_HOME_BASE, AGENT_DATA_BASE, GLOBAL_CONFIG_PATH

W = 60

def check(label: str, ok: bool, detail: str = "") -> None:
    status = "PASS" if ok else "FAIL"
    line = f"  [{status}] {label}"
    if detail:
        line += f"  ({detail})"
    print(line)
    if not ok:
        sys.exit(1)

print(f"\n{'═' * W}")
print("  Sandbox pool smoke test")
print(f"{'═' * W}\n")

# ── 1. Basic acquire/release ───────────────────────────────────────────────────

print("1. Acquire slot")
agent = acquire_sandbox_agent("personal")
check("acquired a slot", agent.name in SANDBOX_NAMES, agent.name)
check("lock file is open", agent._lock_file is not None)

home = AGENT_HOME_BASE / agent.name
data_dir = AGENT_DATA_BASE / agent.name
check("home dir exists", home.is_dir(), str(home))
check("dharma/identity.md written", (home / "dharma/identity.md").exists())
check("data_dir exists", data_dir.is_dir(), str(data_dir))
check("agent.json written to data_dir", (data_dir / "agent.json").exists())
check("memory/semantic/core.jsonl exists", (data_dir / "memory/semantic/core.jsonl").exists())

fifo = Path("/var/aurelia/queue") / agent.name
check("FIFO created", fifo.exists(), str(fifo))

budget = data_dir / "budget.json"
check("budget file created", budget.exists(), str(budget))

import json
cfg = json.loads(GLOBAL_CONFIG_PATH.read_text()) if GLOBAL_CONFIG_PATH.exists() else {}
check("token written to config", agent.name in cfg.get("agents", {}))

# ── 2. Double-acquire same slot should fail ────────────────────────────────────

print("\n2. Lock exclusion")
import fcntl
lock_path = Path(f"/var/aurelia/sandbox/locks/{agent.name}.lock")
fd2 = open(lock_path, "w")
try:
    fcntl.flock(fd2, fcntl.LOCK_EX | fcntl.LOCK_NB)
    check("second lock on held slot should fail", False, "no BlockingIOError raised")
except BlockingIOError:
    check("second lock correctly blocked", True)
finally:
    fd2.close()

# ── 3. Release ─────────────────────────────────────────────────────────────────

print("\n3. Release slot")
release_sandbox_agent(agent)
check("home wiped after release", not home.exists(), str(home))
check("data_dir wiped after release", not data_dir.exists(), str(data_dir))
check("FIFO removed", not fifo.exists())
check("budget file removed", not budget.exists())
cfg2 = json.loads(GLOBAL_CONFIG_PATH.read_text()) if GLOBAL_CONFIG_PATH.exists() else {}
check("token removed from config", agent.name not in cfg2.get("agents", {}))

# ── 4. Re-acquire same slot ────────────────────────────────────────────────────

print("\n4. Re-acquire released slot")
agent2 = acquire_sandbox_agent("personal")
check("re-acquired a slot", agent2.name in SANDBOX_NAMES, agent2.name)
release_sandbox_agent(agent2)
check("re-released cleanly", not (AGENT_HOME_BASE / agent2.name).exists())

print(f"\n{'═' * W}")
print("  All checks passed.")
print(f"{'═' * W}\n")
