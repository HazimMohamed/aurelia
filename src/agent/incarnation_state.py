"""Per-incarnation state machine: inactive → active ↔ exploring.

All incarnation states for an agent are stored in a single
data_dir/states.json dict, keyed by incarnation name.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from ..config import AgentConfig

INACTIVE_THRESHOLD_MINUTES = 60

_write_lock = threading.Lock()


class IncarnationStatus(str, Enum):
    INACTIVE = "inactive"
    ACTIVE = "active"
    EXPLORING = "exploring"


def _states_path(config: AgentConfig):
    return config.data_dir / "states.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _read_all(config: AgentConfig) -> dict[str, Any]:
    path = _states_path(config)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _write_all(config: AgentConfig, states: dict[str, Any]) -> None:
    _states_path(config).write_text(json.dumps(states, indent=2))


def read_state(config: AgentConfig, incarnation_name: str) -> dict[str, Any]:
    return _read_all(config).get(incarnation_name, {"status": IncarnationStatus.INACTIVE, "last_active": None})


def write_state(
    config: AgentConfig,
    incarnation_name: str,
    status: IncarnationStatus,
    last_active: str | None = None,
) -> None:
    entry: dict[str, Any] = {"status": status.value}
    if last_active is not None:
        entry["last_active"] = last_active
    elif status == IncarnationStatus.ACTIVE:
        entry["last_active"] = _now_iso()

    with _write_lock:
        states = _read_all(config)
        states[incarnation_name] = entry
        _write_all(config, states)


def remove_state(config: AgentConfig, incarnation_name: str) -> None:
    """Called by bardo when an incarnation is archived."""
    with _write_lock:
        states = _read_all(config)
        states.pop(incarnation_name, None)
        _write_all(config, states)


def effective_status(config: AgentConfig, incarnation_name: str) -> IncarnationStatus:
    """Return effective status, treating stale active as inactive."""
    state = read_state(config, incarnation_name)
    try:
        status = IncarnationStatus(state.get("status", IncarnationStatus.INACTIVE))
    except ValueError:
        return IncarnationStatus.INACTIVE

    if status == IncarnationStatus.ACTIVE:
        last_active = state.get("last_active")
        if last_active:
            try:
                dt = datetime.fromisoformat(last_active.replace("Z", "+00:00"))
                age_minutes = (datetime.now(timezone.utc) - dt).total_seconds() / 60
                if age_minutes > INACTIVE_THRESHOLD_MINUTES:
                    return IncarnationStatus.INACTIVE
            except ValueError:
                return IncarnationStatus.INACTIVE
        else:
            return IncarnationStatus.INACTIVE

    return status
