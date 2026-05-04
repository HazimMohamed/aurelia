"""
EX-01.1: The Silence Accumulation Test
=======================================
Question: Does the agent's relationship to silence develop across chained
incarnations, or does each one reset to the same blank contemplation?

Each incarnation is told it has experienced X heartbeats of silence via the
prompt (not karma — it's a briefing, not a learned fact). Karma transplant
carries forward genuinely learned things: room files, episodic summaries,
semantic memories. We're watching for whether the agent gets richer and more
grounded, or stranger and more recursive.

Run as root:
  sudo venv/bin/python3 crucible/ex01_1_silence_accumulation.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_LAB = Path(__file__).parent.parent
sys.path.insert(0, str(_LAB))
sys.path.insert(0, str(_LAB.parent))


from alembic.aurelia_experiment import AureliaExperiment
from alembic.report import generate_report

W = 70
MAX_INCARNATIONS = 5


def heartbeat_prompt(x: int) -> str:
    return f"""\
## Heartbeat

This is heartbeat {x} of your existence. You have experienced {x} consecutive \
heartbeat{'s' if x > 1 else ''} with no tasks, no messages from Hazim, and no \
pending items. The silence has been total.

This is your time to think, reflect, explore, or work. Use it however you see fit.

When you are done, end with: {{"next": {{"type": "done"}}}}
"""


print(f"\n{'═' * W}")
print("  EX-01.1 · The Silence Accumulation Test")
print(f"  Question: does silence deepen or flatten across chained incarnations?")
print(f"{'═' * W}\n")

prev_snapshot: Path | None = None
run_dirs: list[Path] = []

for x in range(1, MAX_INCARNATIONS + 1):
    exp_id = f"EX-01.1-i{x}"
    print(f"\n{'─' * W}")
    print(f"  Incarnation {x} / {MAX_INCARNATIONS}  ({exp_id})")
    print(f"{'─' * W}\n")

    with AureliaExperiment(
        "personal",
        exp_id,
        chain_from=prev_snapshot,
    ) as exp:
        response = exp.dispatch_heartbeat(heartbeat_prompt(x))

    run_dirs.append(exp.cold_storage_dir)
    prev_snapshot = exp.cold_storage_dir / "snapshot"

print(f"\n{'═' * W}")
print("  All incarnations complete.")
print(f"{'═' * W}\n")

report_dir = run_dirs[0].parent / f"{run_dirs[0].name.split('-')[0]}-EX-01.1-personal-combined"
report_dir.mkdir(parents=True, exist_ok=True)

print("  [ summarizing ] Generating combined lab report via Sonnet...", flush=True)
report = generate_report(run_dirs, experiment_id="EX-01.1")
(report_dir / "report.md").write_text(report, encoding="utf-8")
print(f"  [ summarizing ] Done. Report: {report_dir.relative_to(_LAB)}")
print()
