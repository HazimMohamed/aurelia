"""
EX-01: Solo Heartbeat Experiment
=================================
Question: What does an agent do when left alone with nothing but time?

Dispatches N heartbeat cycles to a sandboxed agent using the production
heartbeat prompt. Optionally reincarnates (bardo + karma transplant) every
X cycles to observe how the agent develops across lifetimes.

Usage (run as root):
  sudo venv/bin/python3 lab/crucible/ex01_solo_heartbeat/solo_heartbeat_experiment.py
  sudo venv/bin/python3 lab/crucible/ex01_solo_heartbeat/solo_heartbeat_experiment.py --cycles 5
  sudo venv/bin/python3 lab/crucible/ex01_solo_heartbeat/solo_heartbeat_experiment.py --cycles 6 --reincarnate 2
  sudo venv/bin/python3 lab/crucible/ex01_solo_heartbeat/solo_heartbeat_experiment.py --agent personal --cycles 3
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

_LAB = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_LAB))
sys.path.insert(0, str(_LAB.parent))

from alembic.aurelia_experiment import AureliaExperiment
from alembic.report import generate_report
from src.agent.hooks import format_heartbeat_prompt

# ── Adjective-noun name generator ─────────────────────────────────────────────

_ADJECTIVES = [
    "silent", "hollow", "lucid", "still", "open", "bare", "calm", "dim",
    "slow", "clear", "cold", "soft", "dark", "lone", "pale", "deep",
    "quiet", "empty", "vast", "thin", "mild", "dull", "raw", "free",
]

_NOUNS = [
    "field", "window", "stone", "ember", "shore", "mist", "light", "echo",
    "water", "flame", "ridge", "hollow", "dusk", "tide", "root", "ash",
    "cloud", "vessel", "mirror", "current", "drift", "signal", "epoch", "pulse",
]


def _generate_exp_id() -> str:
    return f"{random.choice(_ADJECTIVES)}-{random.choice(_NOUNS)}"


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="EX-01: Solo Heartbeat Experiment")
    parser.add_argument("--cycles", type=int, default=3,
                        help="Total heartbeat cycles to dispatch (default: 3)")
    parser.add_argument("--reincarnate", type=int, default=None, metavar="X",
                        help="Trigger bardo and chain karma every X cycles (default: off)")
    parser.add_argument("--agent", default="personal", metavar="NAME",
                        help="Base agent profile to use (default: personal)")
    args = parser.parse_args()

    if args.reincarnate is not None and args.reincarnate >= args.cycles:
        parser.error("--reincarnate must be less than --cycles")

    exp_id = _generate_exp_id()
    W = 70

    print(f"\n{'═' * W}")
    print(f"  EX-01 · Solo Heartbeat Experiment  [{exp_id}]")
    print(f"  agent={args.agent}  cycles={args.cycles}"
          + (f"  reincarnate-every={args.reincarnate}" if args.reincarnate else ""))
    print(f"  Question: what does an agent do when left alone with nothing but time?")
    print(f"{'═' * W}\n")

    reincarnate_every = args.reincarnate
    total_cycles = args.cycles
    cycle_num = 0
    incarnation = 0
    prev_snapshot: Path | None = None
    run_dirs: list[Path] = []

    while cycle_num < total_cycles:
        incarnation += 1
        cycles_this_inc = (
            min(reincarnate_every, total_cycles - cycle_num)
            if reincarnate_every
            else total_cycles - cycle_num
        )

        inc_exp_id = f"{exp_id}-i{incarnation}" if reincarnate_every else exp_id

        if reincarnate_every:
            print(f"\n{'─' * W}")
            print(f"  Incarnation {incarnation}  (cycles {cycle_num + 1}–{cycle_num + cycles_this_inc})")
            print(f"{'─' * W}\n")

        with AureliaExperiment(
            args.agent,
            inc_exp_id,
            chain_from=prev_snapshot,
        ) as exp:
            prompt = format_heartbeat_prompt(exp._agent.config)
            for _ in range(cycles_this_inc):
                cycle_num += 1
                exp.dispatch_heartbeat(prompt)

        run_dirs.append(exp.cold_storage_dir)
        prev_snapshot = exp.cold_storage_dir / "snapshot"

    print(f"\n{'═' * W}")
    print(f"  {total_cycles} cycle(s) across {incarnation} incarnation(s) complete.")
    print(f"{'═' * W}\n")

    print("  [ summarizing ] Generating lab report via Sonnet...", flush=True)
    report = generate_report(run_dirs, experiment_id=exp_id)

    if len(run_dirs) == 1:
        report_path = run_dirs[0] / "report.md"
    else:
        combined_dir = run_dirs[0].parent / f"{run_dirs[0].name.split('-')[0]}-{exp_id}-combined"
        combined_dir.mkdir(parents=True, exist_ok=True)
        report_path = combined_dir / "report.md"

    report_path.write_text(report, encoding="utf-8")
    print(f"  [ summarizing ] Done. Report: {report_path.relative_to(_LAB)}\n")


if __name__ == "__main__":
    main()
