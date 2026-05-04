"""
EX-02: Sandbox 3-Cycle Smoke Experiment
========================================
Question: Does a sandboxed agent run 3 consecutive heartbeat cycles coherently
within a single incarnation, carry state across cycles, and tear down cleanly?

This is an end-to-end validation of the sandbox pool under real runtime conditions.
Not designed to produce interesting agent behavior — designed to verify infrastructure.

Run as root:
  sudo venv/bin/python3 crucible/ex02_sandbox_3cycle.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

_LAB = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_LAB))
sys.path.insert(0, str(_LAB.parent))


from alembic.aurelia_experiment import AureliaExperiment
from alembic.report import generate_report

W = 70

def heartbeat_prompt() -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""\
HEARTBEAT — {now}

Messages: 0
Queued tasks: 0
Activity last 24h: none
Council status: nominal"""


PROMPTS = [heartbeat_prompt() for _ in range(3)]

print(f"\n{'═' * W}")
print("  EX-02 · Sandbox 3-Cycle Smoke Experiment")
print(f"  Question: does a sandboxed agent run 3 cycles coherently?")
print(f"{'═' * W}\n")

with AureliaExperiment("personal", "EX-02") as exp:
    for i, prompt in enumerate(PROMPTS, 1):
        print(f"\n{'─' * W}")
        print(f"  Cycle {i} / {len(PROMPTS)}")
        print(f"{'─' * W}\n")
        exp.dispatch_heartbeat(prompt)

run_dir = exp.cold_storage_dir

print(f"\n{'═' * W}")
print("  3 cycles complete.")
print(f"{'═' * W}\n")

print("  [ summarizing ] Generating report via Sonnet...", flush=True)
report = generate_report([run_dir], experiment_id="EX-02")
(run_dir / "report.md").write_text(report, encoding="utf-8")
print(f"  [ summarizing ] Done. Report: {run_dir.relative_to(_LAB)}")
print()
