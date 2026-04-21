"""AgentDaemon: reads from FIFO queue, dispatches to FastAPI."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path


FIFO_BASE = Path("/var/aurelia/queue")
API_URL = "http://localhost:8000"


class AgentDaemon:
    """Reads work items from agent FIFO and dispatches them to the FastAPI server."""

    def __init__(self, agent_name: str, api_url: str = API_URL) -> None:
        self.agent_name = agent_name
        self.api_url = api_url
        self.fifo_path = FIFO_BASE / agent_name
        self._running = False

    def run(self) -> None:
        """Main daemon loop: blocking read from FIFO, dispatch each item."""
        import httpx

        self._running = True
        print(f"[daemon:{self.agent_name}] Started. Listening on {self.fifo_path}")

        if not self.fifo_path.exists():
            print(
                f"[daemon:{self.agent_name}] WARNING: FIFO {self.fifo_path} does not exist. "
                "Run setup_agent.sh with root to create it."
            )
            # In WSL dev mode, just sleep and retry
            while self._running:
                time.sleep(10)
                if self.fifo_path.exists():
                    break
            if not self.fifo_path.exists():
                return

        while self._running:
            try:
                with self.fifo_path.open("r", encoding="utf-8") as pipe:
                    for line in pipe:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            item = json.loads(line)
                            self._dispatch(item)
                        except json.JSONDecodeError as e:
                            print(f"[daemon:{self.agent_name}] Bad JSON: {e} — line: {line[:100]}")
            except OSError as e:
                print(f"[daemon:{self.agent_name}] FIFO read error: {e}. Retrying in 5s...")
                time.sleep(5)

    def _dispatch(self, item: dict) -> None:
        """POST work item to the internal process endpoint."""
        import httpx

        agent = item.get("agent", "")
        if agent and agent != self.agent_name:
            print(f"[daemon:{self.agent_name}] WARNING: item is for agent '{agent}', ignoring")
            return

        try:
            response = httpx.post(
                f"{self.api_url}/internal/process",
                json=item,
                timeout=300.0,
            )
            if response.status_code == 200:
                print(f"[daemon:{self.agent_name}] Dispatched {item.get('id', '?')} OK")
            else:
                print(
                    f"[daemon:{self.agent_name}] Dispatch failed: "
                    f"HTTP {response.status_code} — {response.text[:200]}"
                )
        except Exception as e:
            print(f"[daemon:{self.agent_name}] Dispatch error: {e}")

    def stop(self) -> None:
        self._running = False


def main() -> None:
    """Entry point for running an agent daemon from command line."""
    if len(sys.argv) < 2:
        print("Usage: python daemon.py <agent_name> [api_url]")
        sys.exit(1)

    agent_name = sys.argv[1]
    api_url = sys.argv[2] if len(sys.argv) > 2 else API_URL

    daemon = AgentDaemon(agent_name, api_url)
    try:
        daemon.run()
    except KeyboardInterrupt:
        daemon.stop()
        print(f"\n[daemon:{agent_name}] Stopped.")


if __name__ == "__main__":
    main()
