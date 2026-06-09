"""Aurelia runtime client — connects to the runtime daemon via Unix socket.

Used by HTTP transport, Discord bot, scheduler, or any process in transport_group.
Each call opens a fresh connection (no pooling needed at this scale).
"""

from __future__ import annotations

import json
import socket
import uuid
from pathlib import Path
from typing import Any, Iterator

from ..runtime.types import (
    AgentResponse,
    AgentSummary,
    HealthReport,
    IncarnationSummary,
    TranscriptEntry,
)
from ..agent.hooks import HookType

SOCKET_PATH = Path("/var/aurelia/runtime.sock")


class RuntimeClient:
    """Client for the Aurelia runtime daemon Unix socket protocol."""

    def __init__(self, socket_path: Path = SOCKET_PATH) -> None:
        self.socket_path = socket_path

    # ── Public API ─────────────────────────────────────────────────────────────

    def spawn(self, agent: str, goal: str | None = None, make_primary: bool | None = None) -> IncarnationSummary:
        """Spawn a fresh incarnation for an agent."""
        req: dict = {"type": "spawn", "agent": agent, "goal": goal}
        if make_primary is not None:
            req["make_primary"] = make_primary
        data = self._call(req)
        return IncarnationSummary(**data)

    def dispatch(
        self,
        agent: str,
        incarnation: str,
        hook: HookType,
        payload: dict[str, Any],
    ) -> AgentResponse:
        """Send a hook payload to a specific incarnation."""
        data = self._call({
            "type": "dispatch",
            "agent": agent,
            "incarnation": incarnation,
            "hook": hook if isinstance(hook, str) else hook.value,
            "payload": payload,
        })
        return AgentResponse(
            agent=data["agent"],
            incarnation=data["incarnation"],
            cycle=data["cycle"],
            content=data["content"],
        )

    def get_history(self, agent: str, incarnation: str) -> list[TranscriptEntry]:
        """Read transcript entries for a specific incarnation."""
        data = self._call({"type": "get_history", "agent": agent, "incarnation": incarnation})
        return [TranscriptEntry(**e) for e in data]

    def list_incarnations(self, agent: str) -> list[IncarnationSummary]:
        """List all incarnations for an agent."""
        data = self._call({"type": "list_incarnations", "agent": agent})
        return [IncarnationSummary(**i) for i in data]

    def list_agents(self) -> list[AgentSummary]:
        """List all registered agents and their status."""
        data = self._call({"type": "list_agents"})
        return [AgentSummary(**a) for a in data]

    def get_health(self) -> HealthReport:
        """Return system-wide health report."""
        data = self._call({"type": "get_health"})
        agents = [AgentSummary(**a) for a in data.get("agents", [])]
        return HealthReport(
            status=data["status"],
            agents=agents,
            pending_dashboard=data.get("pending_dashboard", 0),
        )

    def trigger_bardo(self, agent: str) -> dict[str, Any]:
        """Trigger bardo for an agent's active incarnation."""
        return self._call({"type": "trigger_bardo", "agent": agent})

    def get_primary(self, agent: str) -> str | None:
        """Return the primary incarnation name for an agent, or None."""
        data = self._call({"type": "get_primary", "agent": agent})
        return data.get("primary")

    def set_primary(self, agent: str, name: str) -> None:
        """Designate a specific incarnation as primary."""
        self._call({"type": "set_primary", "agent": agent, "name": name})

    def get_budget_info(self, agent: str) -> dict[str, Any]:
        """Return raw budget dict for an agent."""
        return self._call({"type": "get_budget_info", "agent": agent})

    def registry_reload(self) -> dict[str, Any]:
        """Force the agent registry to reload in the daemon."""
        return self._call({"type": "registry_reload"})

    def scheduler_tick(self) -> dict[str, Any]:
        """Wake the scheduler immediately — useful for tests and manual triggering."""
        return self._call({"type": "scheduler_tick"})

    def internal_process(
        self,
        agent: str,
        hook_type: str,
        goal: str = "",
        payload: dict[str, Any] | None = None,
        rebirth_from: str | None = None,
    ) -> dict[str, Any]:
        """Process an autonomous hook (heartbeat, scheduled_task, agent_invite)."""
        return self._call({
            "type": "internal_process",
            "agent": agent,
            "hook_type": hook_type,
            "goal": goal,
            "payload": payload or {},
            "rebirth_from": rebirth_from,
        })

    def dispatch_stream(
        self,
        agent: str,
        incarnation: str,
        hook: HookType,
        payload: dict[str, Any],
    ) -> Iterator[dict[str, Any]]:
        """Open a streaming dispatch connection, yielding frame dicts until 'done'.

        Keeps the socket open across multiple LLM calls (tool loop) — the caller
        receives frames as they are produced without any buffering on our side.
        """
        request = {
            "id": str(uuid.uuid4()),
            "type": "dispatch",
            "stream": True,
            "agent": agent,
            "incarnation": incarnation,
            "hook": hook if isinstance(hook, str) else hook.value,
            "payload": payload,
        }
        raw = json.dumps(request).encode("utf-8") + b"\n"

        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.connect(str(self.socket_path))
                sock.sendall(raw)
                sock.settimeout(None)  # blocking reads — no timeout during streaming

                buf = b""
                while True:
                    chunk = sock.recv(65536)
                    if not chunk:
                        break
                    buf += chunk
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        line = line.strip()
                        if not line:
                            continue
                        frame = json.loads(line.decode("utf-8"))
                        yield frame
                        if frame.get("type") == "done":
                            return

        except (FileNotFoundError, ConnectionRefusedError) as e:
            yield {
                "type": "done",
                "status": "error",
                "error": "ConnectionError",
                "message": (
                    f"Cannot connect to runtime daemon at {self.socket_path}: {e}. "
                    "Is the daemon running?"
                ),
            }
        except json.JSONDecodeError as e:
            yield {"type": "done", "status": "error", "error": "ParseError", "message": str(e)}

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _call(self, request: dict[str, Any]) -> Any:
        """
        Connect to the runtime socket, send a JSON+newline request,
        read a JSON+newline response, and return the parsed data.

        Raises RuntimeError if the daemon returns an error status.
        Raises ConnectionError if the socket cannot be reached.
        """
        if "id" not in request:
            request = {**request, "id": str(uuid.uuid4())}

        payload = json.dumps(request).encode("utf-8") + b"\n"

        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(300.0)  # agent cycles can be slow
                sock.connect(str(self.socket_path))
                sock.sendall(payload)

                # Read until newline
                buf = b""
                while b"\n" not in buf:
                    chunk = sock.recv(65536)
                    if not chunk:
                        raise ConnectionError("Runtime daemon closed connection unexpectedly")
                    buf += chunk

                line, _ = buf.split(b"\n", 1)
                response = json.loads(line.decode("utf-8"))

        except (FileNotFoundError, ConnectionRefusedError) as e:
            raise ConnectionError(
                f"Cannot connect to runtime daemon at {self.socket_path}: {e}. "
                "Is the daemon running? Start it with: python3 -m src.runtime_daemon"
            ) from e
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Malformed response from runtime daemon: {e}") from e

        if response.get("status") == "error":
            error_class = response.get("error", "RuntimeError")
            message = response.get("message", "Unknown error")
            raise RuntimeError(f"{error_class}: {message}")

        return response.get("data")


# ── Module-level default instance ──────────────────────────────────────────────

client = RuntimeClient()
