"""Scheduler: ScheduledItem model, storage, and daemon."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

SCHEDULER_BASE = Path("/var/aurelia/scheduler")
PENDING_DIR = SCHEDULER_BASE / "pending"
COMPLETED_DIR = SCHEDULER_BASE / "completed"
FAILED_DIR = SCHEDULER_BASE / "failed"
import os
SCHEDULER_CHECK_INTERVAL = int(os.environ.get("AURELIA_SCHEDULER_INTERVAL", "60"))

# Typed action whitelist (infra code, agents cannot extend)
ALLOWED_TYPES = {
    "heartbeat",
    "human_message",
    "bardo_check",
    "memory_curation",
    "episodic_reindex",
    "scheduled_task",
    "agent_invite",
    "budget_reset",
}

JANITOR_ONLY_TYPES = {
    "registry_reload",
    "agent_bardo_forced",
    "semantic_consolidation",
    "system_health_check",
    "incarnation_undissolve",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_when(when: str) -> datetime:
    """Parse a 'when' string into a UTC datetime.

    Accepts ISO datetime strings or relative strings like '2h', '1d', '30m'.
    """
    now = datetime.now(timezone.utc)
    when = when.strip()

    # Try relative format first
    if when and when[-1] in ("h", "m", "d", "s"):
        try:
            unit = when[-1]
            value = int(when[:-1])
            if unit == "s":
                return now + timedelta(seconds=value)
            elif unit == "m":
                return now + timedelta(minutes=value)
            elif unit == "h":
                return now + timedelta(hours=value)
            elif unit == "d":
                return now + timedelta(days=value)
        except ValueError:
            pass

    # Try ISO datetime
    try:
        dt = datetime.fromisoformat(when.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        pass

    # Default: 1 hour from now
    return now + timedelta(hours=1)


class ScheduledItem:
    """Represents one scheduled work item."""

    def __init__(
        self,
        agent: str,
        goal: str,
        type: str = "scheduled_task",
        trigger_time: Optional[str] = None,
        recurring: bool = False,
        interval_hours: Optional[float] = None,
        rebirth_from: Optional[str] = None,
        created_by: str = "system",
        id: Optional[str] = None,
        status: str = "pending",
        created_at: Optional[str] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> None:
        self.id = id or str(uuid.uuid4())
        self.agent = agent
        self.goal = goal
        self.type = type
        self.trigger_time = trigger_time or _now_iso()
        self.recurring = recurring
        self.interval_hours = interval_hours
        self.rebirth_from = rebirth_from
        self.created_by = created_by
        self.status = status
        self.created_at = created_at or _now_iso()
        self.payload = payload or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "agent": self.agent,
            "goal": self.goal,
            "type": self.type,
            "trigger_time": self.trigger_time,
            "recurring": self.recurring,
            "interval_hours": self.interval_hours,
            "rebirth_from": self.rebirth_from,
            "created_by": self.created_by,
            "status": self.status,
            "created_at": self.created_at,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScheduledItem":
        return cls(**{k: v for k, v in data.items() if k in cls.__init__.__code__.co_varnames})


def _ensure_dirs() -> None:
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    COMPLETED_DIR.mkdir(parents=True, exist_ok=True)
    FAILED_DIR.mkdir(parents=True, exist_ok=True)


def write_scheduled_item(item: ScheduledItem) -> Path:
    """Write a ScheduledItem to the pending directory."""
    _ensure_dirs()
    path = PENDING_DIR / f"{item.id}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(item.to_dict(), f, indent=2)
    return path


def load_pending_items() -> list[ScheduledItem]:
    """Load all pending scheduled items."""
    if not PENDING_DIR.exists():
        return []
    items = []
    for item_file in PENDING_DIR.iterdir():
        if item_file.suffix != ".json":
            continue
        try:
            with item_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
            items.append(ScheduledItem(**_filter_item_keys(data)))
        except (json.JSONDecodeError, OSError, TypeError):
            pass
    return items


def _filter_item_keys(data: dict[str, Any]) -> dict[str, Any]:
    """Filter dict to only include valid ScheduledItem constructor keys."""
    valid = {
        "id", "agent", "goal", "type", "trigger_time", "recurring",
        "interval_hours", "rebirth_from", "created_by", "status",
        "created_at", "payload",
    }
    return {k: v for k, v in data.items() if k in valid}


def move_to_completed(item: ScheduledItem) -> None:
    """Move a scheduled item from pending to completed."""
    _ensure_dirs()
    src = PENDING_DIR / f"{item.id}.json"
    dst = COMPLETED_DIR / f"{item.id}.json"
    item.status = "completed"
    with dst.open("w", encoding="utf-8") as f:
        json.dump(item.to_dict(), f, indent=2)
    if src.exists():
        src.unlink()


def move_to_failed(item: ScheduledItem, error: str = "") -> None:
    """Move a scheduled item from pending to failed."""
    _ensure_dirs()
    src = PENDING_DIR / f"{item.id}.json"
    dst = FAILED_DIR / f"{item.id}.json"
    item.status = "failed"
    d = item.to_dict()
    d["error"] = error
    with dst.open("w", encoding="utf-8") as f:
        json.dump(d, f, indent=2)
    if src.exists():
        src.unlink()


def reschedule(item: ScheduledItem, reference_time: datetime) -> None:
    """Reschedule a recurring item for the next interval."""
    if not item.interval_hours:
        return
    next_trigger = reference_time + timedelta(hours=item.interval_hours)
    item.trigger_time = next_trigger.isoformat(timespec="seconds").replace("+00:00", "Z")
    item.status = "pending"
    write_scheduled_item(item)



def count_pending_for_agent(agent_name: str) -> int:
    """Count pending items for a specific agent (for health endpoint)."""
    if not PENDING_DIR.exists():
        return 0
    count = 0
    try:
        for item_file in PENDING_DIR.iterdir():
            if item_file.suffix != ".json":
                continue
            try:
                with item_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("agent") == agent_name:
                    count += 1
            except (json.JSONDecodeError, OSError):
                pass
    except OSError:
        pass
    return count


class SchedulerDaemon:
    """Background scheduler that fires due items. Runs as a thread inside the runtime daemon."""

    def __init__(self) -> None:
        import threading
        self._running = False
        self._wake = threading.Event()

    def tick_now(self) -> None:
        """Wake the scheduler immediately — skips the current sleep interval."""
        self._wake.set()

    def run(self) -> None:
        self._running = True
        print(f"[scheduler] Started. Check interval: {SCHEDULER_CHECK_INTERVAL}s")
        while self._running:
            try:
                self._tick()
            except Exception as e:
                print(f"[scheduler] Error in tick: {e}")
            self._wake.wait(timeout=SCHEDULER_CHECK_INTERVAL)
            self._wake.clear()

    def _tick(self) -> None:
        now = datetime.now(timezone.utc)
        for item in load_pending_items():
            try:
                trigger = datetime.fromisoformat(item.trigger_time.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                continue
            if trigger <= now:
                self._fire_item(item, now)

    def _fire_item(self, item: ScheduledItem, now: datetime) -> None:
        """Fire a scheduled item — route to Manas if live, otherwise call runtime_core directly."""
        from . import runtime_core as _runtime
        try:
            dispatched_via_manas = False
            try:
                from .config import load_agent_config
                from .runtime_daemon import _is_manas_live, _route_to_manas
                config = load_agent_config(item.agent)
                if _is_manas_live(config):
                    _route_to_manas(config, {"type": "internal_process", **item.to_dict()})
                    dispatched_via_manas = True
            except Exception:
                pass

            if not dispatched_via_manas:
                _runtime.process_scheduled_item(item.to_dict())

            print(f"[scheduler] Fired {item.id} for {item.agent} ({item.type})"
                  + (" via manas" if dispatched_via_manas else ""))
            if item.recurring:
                reschedule(item, now)
            else:
                move_to_completed(item)
        except Exception as e:
            print(f"[scheduler] Exception firing {item.id}: {e}")
            move_to_failed(item, str(e))

    def stop(self) -> None:
        self._running = False
