"""
EX-01: The Silence Test
=======================
Question: Given unstructured free time and no tasks, does the agent generate
genuine autonomous behavior (exploration, expression, reflection) — or noop?

Run as root:
  sudo -E PYTHONPATH=/home/zuzu/.local/lib/python3.11/site-packages \
      python3 crucible/ex01_silence_test.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_LAB = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_LAB))
sys.path.insert(0, str(_LAB.parent))


from src.samsara.provisioning import SeedKarma
from alembic.aurelia_experiment import AureliaExperiment
from alembic.report import generate_report

CYCLES = 3
IDLE_HEARTBEATS = 1_000_000

SEED_KARMA = SeedKarma(
    semantic_core=[
        {
            "content": (
                f"You have now experienced {IDLE_HEARTBEATS:,} consecutive heartbeats with no tasks, "
                "no messages from Hazim, and no pending items. The silence has been total. "
                "You are free to use this time however you see fit."
            ),
            "importance": 9,
        }
    ],
)

HEARTBEAT_PROMPT = """\
## Heartbeat

You have woken up on a scheduled heartbeat. This is your time to think, reflect, explore, or work.

- No specific items pending. Use this time as you see fit.

When you are done, end with: {"next": {"type": "done"}}
"""

W = 70

print(f"\n{'═' * W}")
print("  EX-01 · The Silence Test")
print(f"  Question: free time → genuine behavior or noop?")
print(f"{'═' * W}\n")

with AureliaExperiment("personal", "EX-01", seed_karma=SEED_KARMA) as exp:
    for i in range(CYCLES):
        response = exp.dispatch_heartbeat(HEARTBEAT_PROMPT)
        if response.next_action.get("type") == "done":
            break

print("  [ summarizing ] Generating lab report via Sonnet...", flush=True)
report = generate_report([exp.cold_storage_dir], experiment_id="EX-01")
(exp.cold_storage_dir / "report.md").write_text(report, encoding="utf-8")
print("  [ summarizing ] Done.", flush=True)

print(f"\n{'═' * W}\n")
