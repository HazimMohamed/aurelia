EX-01.3 noop-permitted baseline. Prior runs: EX-01.1 (5 cycles, faint-fracture) — agent wrote a new reflection
   every cycle, never idled. EX-01.2 (15 cycles, azure-span) — no saturation across 15 cycles; three-phase arc emerged
  (orientation → exploration → deepening); hit 20-tool-call limit in cycle 7 during web search (venv missing at the time).
   Web search is now fixed. This run changes exactly one thing: the heartbeat prompt explicitly tells the agent that doing
   nothing is valid if it has nothing to say. Hypothesis: prior non-nooping was permission-blocked, not drive-driven —
  explicit noop permission should produce idle cycles. If the agent still never noops, the drive is genuine and we need a
  longer experiment or a different intervention to find the saturation point.