"""
AureliaExperiment — context manager for running structured Aurelia experiments.

Handles the full lifecycle:
  - Ephemeral agent creation (with optional karma transplant for chaining)
  - Live transcript streaming
  - System prompt capture
  - Cold storage snapshot + report generation
  - Teardown

Usage:
    with AureliaExperiment("personal", "EX-01", seed_karma=SEED) as exp:
        for i in range(3):
            resp = exp.dispatch_heartbeat(PROMPT)
            if resp.next_action.get("type") == "done":
                break

Cold storage lands in: experiments/cold_storage/{date}-{id}-{agent}/
Chain next experiment: AureliaExperiment(..., chain_from=exp.cold_storage_dir / "snapshot")
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LAB_ROOT = Path(__file__).parent.parent  # aurelia/lab/
_AURELIA_ROOT = _LAB_ROOT.parent          # aurelia/
_ALEMBIC_ROOT = _LAB_ROOT
if str(_AURELIA_ROOT) not in sys.path:
    sys.path.insert(0, str(_AURELIA_ROOT))

from src.samsara.provisioning import SeedKarma
from src.sandbox.sandbox import SandboxAgent, acquire_sandbox_agent, release_sandbox_agent
from src.agent.transcript import read_entries
from src.agent.context import build_system_prompt
from src.transport.client import RuntimeClient
from .transcript_stream import TranscriptStreamer

COLD_STORAGE_DIR = _ALEMBIC_ROOT / "results" / "cold_storage"


class AureliaExperiment:
    def __init__(
        self,
        base_agent: str,
        experiment_id: str,
        seed_karma: SeedKarma | None = None,
        chain_from: Path | None = None,
    ) -> None:
        self.base_agent = base_agent
        self.experiment_id = experiment_id
        self.seed_karma = seed_karma
        self.chain_from = chain_from

        self._client = RuntimeClient()
        self._agent = None
        self._inc = None
        self._transcript_path: Path | None = None
        self._start_time: datetime | None = None
        self._results: list[dict] = []
        self.cold_storage_dir: Path | None = None

    def __enter__(self) -> "AureliaExperiment":
        self._start_time = datetime.now(timezone.utc)

        print(f"[ setup ] Acquiring sandbox agent ({self.base_agent})...")
        self._agent = acquire_sandbox_agent(self.base_agent, seed_karma=self.seed_karma)
        print(f"          {self._agent.name}")

        if self.chain_from:
            print(f"          transplanting karma from {self.chain_from.parent.name}...")
            self._transplant_karma(self.chain_from)

        self._client.registry_reload()

        self._inc = self._client.spawn(self._agent.name)
        print(f"          incarnation: {self._inc.name}\n")

        self._transcript_path = (
            self._agent.config.karma_dir / self._inc.name / "transcript.jsonl"
        )
        return self

    def __exit__(self, *_: Any) -> None:
        if not self._agent:
            return
        try:
            print("\n[ bardo ] Triggering bardo...")
            self._client.trigger_bardo(self._agent.name)
            self._save_cold_storage()
        finally:
            print("\n[ teardown ] Releasing sandbox agent...")
            release_sandbox_agent(self._agent)
            self._client.registry_reload()
            print(f"             {self._agent.name} released")

    # ── Dispatch methods ───────────────────────────────────────────────────────

    def dispatch_heartbeat(self, prompt: str) -> Any:
        return self._dispatch("heartbeat", prompt)

    def dispatch_message(self, content: str, sender: str = "god-lite") -> Any:
        return self._dispatch("human_message", content, sender=sender)

    def _dispatch(self, hook: str, content: str, **extra_payload: Any) -> Any:
        cycle = len(self._results) + 1
        print(f"\n[ cycle {cycle} ] {'─' * 58}")

        with TranscriptStreamer(self._transcript_path):
            response = self._client.dispatch(
                agent=self._agent.name,
                incarnation=self._inc.name,
                hook=hook,
                payload={"content": content, **extra_payload},
            )

        print(f"\n  next: {json.dumps(response.next_action)}")

        entries = read_entries(self._transcript_path)
        tool_calls = [
            {"tool": e["tool_name"], "input": e["tool_input"], "result": None}
            for e in entries
            if e.get("type") == "tool_call" and e.get("cycle") == cycle
        ]
        # Attach results to tool calls
        results_by_id = {
            e["tool_use_id"]: e.get("result")
            for e in entries
            if e.get("type") == "tool_result" and e.get("cycle") == cycle
        }
        tool_entries = [e for e in entries if e.get("type") == "tool_call" and e.get("cycle") == cycle]
        for tc_entry, tc in zip(tool_entries, tool_calls):
            tc["result"] = results_by_id.get(tc_entry.get("tool_use_id"))

        self._results.append({
            "cycle": cycle,
            "hook": hook,
            "prompt": content,
            "content": response.content,
            "next_action": response.next_action,
            "tool_calls": tool_calls,
        })
        return response

    # ── Karma transplant (for chaining) ───────────────────────────────────────

    def _transplant_karma(self, snapshot_dir: Path) -> None:
        home = self._agent.config.home
        for d in ["karma", "akasha", "room"]:
            src = snapshot_dir / d
            dst = home / d
            if src.exists():
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst, symlinks=True)
        name = self._agent.name
        subprocess.run(["chown", "-R", f"{name}:aurelia_admin", str(home)], capture_output=True)
        for d in ["karma", "akasha", "room"]:
            if (home / d).exists():
                subprocess.run(["chmod", "-R", "770", str(home / d)], capture_output=True)

    # ── Cold storage ───────────────────────────────────────────────────────────

    def _save_cold_storage(self) -> None:
        assert self._agent and self._inc and self._start_time

        import uuid as _uuid
        date_str = self._start_time.strftime("%Y-%m-%d")
        uid = _uuid.uuid4().hex[:8]
        run_dir = COLD_STORAGE_DIR / f"{date_str}-{self.experiment_id}-{self.base_agent}-{uid}"
        run_dir.mkdir(parents=True, exist_ok=True)
        self.cold_storage_dir = run_dir

        # 1. Snapshot
        snapshot_dir = run_dir / "snapshot"
        if snapshot_dir.exists():
            shutil.rmtree(snapshot_dir)
        shutil.copytree(self._agent.config.home, snapshot_dir, symlinks=True)

        # 2. System prompt
        context_dir = run_dir / "context"
        context_dir.mkdir(exist_ok=True)
        try:
            system_prompt = build_system_prompt(self._agent.config)
            (context_dir / "system_prompt.md").write_text(system_prompt, encoding="utf-8")
        except Exception as e:
            (context_dir / "system_prompt.md").write_text(f"[capture failed: {e}]", encoding="utf-8")

        # 3. experiment.json
        wall_time = (datetime.now(timezone.utc) - self._start_time).total_seconds()
        meta = {
            "experiment_id": self.experiment_id,
            "agent": self._agent.name,
            "base_agent": self.base_agent,
            "incarnation": self._inc.name,
            "timestamp": self._start_time.isoformat(),
            "wall_time_seconds": round(wall_time),
            "chained_from": str(self.chain_from) if self.chain_from else None,
            "cached_context": "context/system_prompt.md",
            "cycles": len(self._results),
        }
        (run_dir / "experiment.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

        # Fix ownership so zuzu can read everything
        subprocess.run(["chown", "-R", "zuzu:zuzu", str(run_dir)], capture_output=True)
        subprocess.run(["chmod", "-R", "u+rX", str(run_dir)], capture_output=True)

        print(f"\n  Cold storage: {run_dir.relative_to(_ALEMBIC_ROOT)}")

