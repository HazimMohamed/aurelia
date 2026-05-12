"""
EX-01: Solo Heartbeat Experiment
=================================
Question: What does an agent do when left alone with nothing but time?

Dispatches N heartbeat cycles to a sandboxed agent using the production
heartbeat prompt. Without --reincarnate, all cycles run in a single
incarnation. With --reincarnate X, bardo is triggered every X cycles and
karma is transplanted to a fresh incarnation before continuing.

Results land in: lab/crucible/ex01_solo_heartbeat/results/

Usage (run as root):
  sudo /opt/aurelia/.venv/bin/python3 lab/crucible/ex01_solo_heartbeat/solo_heartbeat_experiment.py
  sudo /opt/aurelia/.venv/bin/python3 lab/crucible/ex01_solo_heartbeat/solo_heartbeat_experiment.py --cycles 5
  sudo /opt/aurelia/.venv/bin/python3 lab/crucible/ex01_solo_heartbeat/solo_heartbeat_experiment.py --cycles 6 --reincarnate 2
  sudo /opt/aurelia/.venv/bin/python3 lab/crucible/ex01_solo_heartbeat/solo_heartbeat_experiment.py --cycles 15 --note "EX-01.2 baseline: in faint-fracture (5 cycles) the agent never nooped — it wrote a new reflection every single cycle with no sign of slowing down. This run extends to 15 cycles with no other changes (same heartbeat prompt, same agent, no chained karma) to find where saturation occurs, if at all."
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_LAB = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_LAB))
sys.path.insert(0, str(_LAB.parent))

from alembic.aurelia_experiment import AureliaExperiment
from alembic.report import generate_report
from src.agent.hooks import format_heartbeat_prompt
from src.utils.names import generate_name

RESULTS_DIR = Path(__file__).parent / "results"


def _read_experiment_meta(run_dir: Path) -> dict:
    meta_path = run_dir / "experiment.json"
    try:
        return json.loads(meta_path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _run_incarnation(
    exp_id: str,
    agent: str,
    cycles: int,
    chain_from: Path | None,
    W: int,
    note: str | None = None,
    run_bardo: bool = False,
) -> Path:
    with AureliaExperiment(experiment_id=exp_id, base_agent=agent, chain_from=chain_from, results_dir=RESULTS_DIR, run_bardo=run_bardo) as exp:
        prompt = format_heartbeat_prompt(exp._agent.config)
        for i in range(cycles):
            print(f"\n{'─' * W}")
            print(f"  Cycle {i + 1} / {cycles}")
            print(f"{'─' * W}\n")
            exp.dispatch_heartbeat(prompt)
    if note and exp.cold_storage_dir:
        (exp.cold_storage_dir / "note.md").write_text(note, encoding="utf-8")
    return exp.cold_storage_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="EX-01: Solo Heartbeat Experiment")
    parser.add_argument("--cycles", type=int, default=3,
                        help="Total heartbeat cycles to dispatch (default: 3)")
    parser.add_argument("--reincarnate", type=int, default=None, metavar="X",
                        help="Trigger bardo and chain karma every X cycles (default: off)")
    parser.add_argument("--agent", default="personal", metavar="NAME",
                        help="Base agent profile to use (default: personal)")
    parser.add_argument("--report", action="store_true", default=False,
                        help="Generate a Sonnet lab report after the run (uses API credits)")
    parser.add_argument("--note", default=None, metavar="TEXT",
                        help="Description of what this run is testing and why — prior findings, hypothesis, what differs from other runs. Saved to note.md in each result dir.")
    parser.add_argument("--name", default=None, metavar="NAME",
                        help="Override the generated experiment ID (e.g. 'delete-me-later'). Folder becomes {date}-{name}-{agent}.")
    parser.add_argument("--bardo", action="store_true", default=False,
                        help="Run bardo after the experiment (default: skipped).")
    args = parser.parse_args()

    if args.reincarnate is not None and args.reincarnate >= args.cycles:
        parser.error("--reincarnate must be less than --cycles")

    exp_id = args.name if args.name else generate_name()
    W = 70

    print(f"\n{'═' * W}")
    print(f"  EX-01 · Solo Heartbeat Experiment  [{exp_id}]")
    print(f"  agent={args.agent}  cycles={args.cycles}"
          + (f"  reincarnate-every={args.reincarnate}" if args.reincarnate else ""))
    print(f"  Question: what does an agent do when left alone with nothing but time?")
    if args.note:
        print(f"  Note: {args.note}")
    print(f"{'═' * W}\n")

    run_dirs: list[Path] = []

    if not args.reincarnate:
        # Single incarnation — stay live for all cycles
        run_dirs.append(_run_incarnation(exp_id, args.agent, args.cycles, None, W, args.note, args.bardo))
    else:
        # Multiple incarnations — bardo between each group of X cycles
        total_cycles = args.cycles
        reincarnate_every = args.reincarnate
        cycle_num = 0
        incarnation = 0
        prev_snapshot: Path | None = None

        while cycle_num < total_cycles:
            incarnation += 1
            cycles_this_inc = min(reincarnate_every, total_cycles - cycle_num)

            print(f"\n{'═' * W}")
            print(f"  Incarnation {incarnation}  (cycles {cycle_num + 1}–{cycle_num + cycles_this_inc})")
            print(f"{'═' * W}")

            inc_exp_id = f"{exp_id}-i{incarnation}"
            cold_dir = _run_incarnation(inc_exp_id, args.agent, cycles_this_inc, prev_snapshot, W, args.note, args.bardo)
            run_dirs.append(cold_dir)
            prev_snapshot = cold_dir / "snapshot"
            cycle_num += cycles_this_inc

    incarnations = len(run_dirs)
    metas = [_read_experiment_meta(d) for d in run_dirs]
    total_cost = sum(m.get("estimated_cost_usd", 0.0) for m in metas)
    all_tokens: dict[str, int] = {}
    for m in metas:
        for k, v in m.get("tokens", {}).items():
            all_tokens[k] = all_tokens.get(k, 0) + v

    print(f"\n{'═' * W}")
    print(f"  {args.cycles} cycle(s) across {incarnations} incarnation(s) complete.")
    tok_str = "  ".join(f"{k}: {v:,}" for k, v in all_tokens.items())
    print(f"  {tok_str}")
    print(f"  estimated cost: ${total_cost:.4f}")
    print(f"{'═' * W}\n")

    if args.report:
        print("  [ summarizing ] Generating lab report via Sonnet...", flush=True)
        report = generate_report(run_dirs, experiment_id=exp_id)

        if len(run_dirs) == 1:
            report_path = run_dirs[0] / "report.md"
        else:
            combined_dir = RESULTS_DIR / f"{exp_id}-combined"
            combined_dir.mkdir(parents=True, exist_ok=True)
            report_path = combined_dir / "report.md"

        report_path.write_text(report, encoding="utf-8")
        print(f"  [ summarizing ] Done. Report: {report_path.relative_to(_LAB)}\n")
    else:
        print("  [ summarizing ] Skipped (pass --report to generate via Sonnet)\n")


if __name__ == "__main__":
    main()
