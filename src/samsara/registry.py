"""AgentRegistry: filesystem discovery with in-memory cache."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .config import AgentConfig, load_agent_config, list_known_agents
from ..agent.incarnation import get_active_incarnation
from ..agent.transcript import read_entries


class AgentRegistry:
    """Discovers agents from filesystem and caches their configs in memory."""

    def __init__(self) -> None:
        self._configs: dict[str, AgentConfig] = {}
        self._lock = threading.Lock()
        self._refresh()

    def _refresh(self) -> None:
        """Scan filesystem and reconcile — adds new agents, removes deleted ones."""
        known = set(list_known_agents())
        with self._lock:
            # Remove agents whose home dirs are gone
            stale = [name for name in self._configs if name not in known]
            for name in stale:
                del self._configs[name]
            # Add newly discovered agents
            for agent_name in known:
                if agent_name not in self._configs:
                    try:
                        self._configs[agent_name] = load_agent_config(agent_name)
                    except Exception:
                        pass

    def get(self, agent_name: str) -> Optional[AgentConfig]:
        """Return AgentConfig for the given agent, or None if not found."""
        with self._lock:
            if agent_name in self._configs:
                return self._configs[agent_name]
        # Try loading fresh from filesystem
        agent_json = Path("/home") / agent_name / "agent.json"
        if agent_json.exists():
            config = load_agent_config(agent_name)
            with self._lock:
                self._configs[agent_name] = config
            return config
        return None

    def all_agents(self) -> list[str]:
        """Return list of all known agent names."""
        self._refresh()
        with self._lock:
            return list(self._configs.keys())

    def agent_status(self, agent_name: str) -> dict:
        """Return status dict for health endpoint."""
        config = self.get(agent_name)
        if not config:
            return {"status": "unknown"}

        # Check budget status first
        try:
            from ..memory.budget import load_budget
            budget_data = load_budget(config.home)
            if budget_data.get("status") == "budget_paused":
                last_active = _get_last_active_from_akasha(config)
                return {
                    "status": "budget_paused",
                    "last_active": last_active,
                }
        except Exception:
            pass

        active_incarnation = get_active_incarnation(config)
        if not active_incarnation:
            # Check last activity from akasha
            last_active = _get_last_active_from_akasha(config)
            return {
                "status": "sleeping",
                "last_active": last_active,
            }

        # Load current incarnation state
        incarnation_dir = config.karma_dir / active_incarnation
        transcript_path = incarnation_dir / "transcript.jsonl"
        entries = read_entries(transcript_path)
        cycle = sum(1 for e in entries if e.get("type") == "human_message")

        last_active = _get_last_ts_from_entries(entries)

        return {
            "status": "active",
            "incarnation": active_incarnation,
            "cycle": cycle,
            "last_active": last_active,
        }


def _get_last_ts_from_entries(entries: list[dict]) -> str:
    """Get last timestamp from transcript entries as a human-readable relative time."""
    if not entries:
        return "never"
    # Find last entry with a timestamp
    for entry in reversed(entries):
        ts_str = entry.get("ts")
        if ts_str:
            return _relative_time(ts_str)
    return "unknown"


def _get_last_active_from_akasha(config: AgentConfig) -> str:
    """Check akasha for last incarnation activity."""
    if not config.akasha_dir.exists():
        return "never"

    latest_ts = None
    for incarnation_dir in config.akasha_dir.iterdir():
        if not incarnation_dir.is_dir():
            continue
        transcript_path = incarnation_dir / f"{incarnation_dir.name}-transcript.jsonl"
        if transcript_path.exists():
            entries = read_entries(transcript_path)
            for entry in reversed(entries):
                ts_str = entry.get("ts")
                if ts_str:
                    try:
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        if latest_ts is None or ts > latest_ts:
                            latest_ts = ts
                    except ValueError:
                        pass
                    break

    if latest_ts is None:
        return "never"
    return _relative_time(latest_ts.isoformat())


def _relative_time(ts_str: str) -> str:
    """Convert ISO timestamp to human-readable relative time."""
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = now - ts
        seconds = int(delta.total_seconds())

        if seconds < 60:
            return f"{seconds}s ago"
        elif seconds < 3600:
            return f"{seconds // 60}m ago"
        elif seconds < 86400:
            return f"{seconds // 3600}h ago"
        else:
            return f"{seconds // 86400}d ago"
    except (ValueError, TypeError):
        return ts_str
