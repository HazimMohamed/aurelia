EX-01.4 budget-aware heartbeat. First run with the new per-cycle token tracking and free-time budget injected
  into the heartbeat prompt. The agent can now see its remaining heartbeat tokens and recent per-cycle usage. Prior runs:
  EX-01.1 (5 cycles) and EX-01.2 (15 cycles) showed zero noops and no saturation. EX-01.3 (15 cycles, noop-ok) showed one
  noop in cycle 5 and otherwise consistent output. This run changes two things: (1) the agent sees its balance and recent
  usage every cycle, (2) it's told that running out means losing free-time access. Hypothesis: the budget framing will
  produce occasional strategic noops or shorter cycles as the agent reasons about conservation, but the drive to reflect
  will likely dominate. The interesting signal is whether the agent references the budget in its reasoning at all.