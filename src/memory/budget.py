"""Budget tracking: per-agent weekly token budgets stored in agent home."""

from __future__ import annotations

import fcntl
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from ..samsara.config import AGENT_HOME_BASE, AgentConfig

DASHBOARD_QUEUE_DIR = Path("/var/aurelia/dashboard/queue")
MINIMUM_BUDGET_THRESHOLD = 1_000  # tokens — below this, heartbeat precheck fails
DEFAULT_HEARTBEAT_WEEKLY_BUDGET = 100_000


def _get_week_start() -> str:
    """Return ISO date string for Monday of the current week."""
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    return monday.isoformat()


def _budget_path(home: Path) -> Path:
    return home / "budget.json"


def load_budget(home: Path) -> dict[str, Any]:
    """Load budget from agent home, returning fresh budget if missing or new week."""
    path = _budget_path(home)
    if not path.exists():
        return {
            "week_start": _get_week_start(),
            "tokens_used": 0,
            "status": "active",
            "heartbeat_weekly_budget": DEFAULT_HEARTBEAT_WEEKLY_BUDGET,
            "heartbeat_cycles": {},
        }
    try:
        data = json.loads(path.read_text())
        if data.get("week_start") != _get_week_start():
            return {
                "week_start": _get_week_start(),
                "tokens_used": 0,
                "status": "active",
                "heartbeat_weekly_budget": data.get("heartbeat_weekly_budget", DEFAULT_HEARTBEAT_WEEKLY_BUDGET),
                "heartbeat_cycles": {},
            }
        return data
    except (json.JSONDecodeError, OSError):
        return {
            "week_start": _get_week_start(),
            "tokens_used": 0,
            "status": "active",
            "heartbeat_weekly_budget": DEFAULT_HEARTBEAT_WEEKLY_BUDGET,
            "heartbeat_cycles": {},
        }


def save_budget(home: Path, budget: dict[str, Any]) -> None:
    """Save budget to agent home with file lock and correct permissions."""
    path = _budget_path(home)
    with open(path, "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            json.dump(budget, f, indent=2)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
    try:
        os.chmod(path, 0o460)
    except PermissionError:
        pass


def deduct_budget(home: Path, tokens: int) -> dict[str, Any]:
    """Deduct tokens from weekly total. Resets counter if new week."""
    budget = load_budget(home)
    budget["tokens_used"] = budget.get("tokens_used", 0) + tokens
    save_budget(home, budget)
    return budget



def get_heartbeat_history(home: Path, n: int = 8) -> list[int]:
    """Return token counts for the last n heartbeat cycles, oldest first."""
    budget = load_budget(home)
    cycles = budget.get("heartbeat_cycles", {})
    return [v["tokens_used"] for v in list(cycles.values())[-n:]]


def get_heartbeat_tokens_used(home: Path) -> int:
    """Return total heartbeat tokens used this week."""
    budget = load_budget(home)
    return sum(v["tokens_used"] for v in budget.get("heartbeat_cycles", {}).values())


def get_budget_remaining(config: AgentConfig) -> int:
    """Return tokens remaining in current weekly budget."""
    budget = load_budget(config.home)
    if budget.get("status") == "budget_paused":
        return 0
    used = budget.get("tokens_used", 0)
    return max(0, config.weekly_budget_tokens - used)


def is_budget_ok(config: AgentConfig) -> bool:
    """Return True if the agent has budget remaining and is not paused."""
    budget = load_budget(config.home)
    if budget.get("status") == "budget_paused":
        return False
    used = budget.get("tokens_used", 0)
    return used < config.weekly_budget_tokens


def check_and_apply_budget(
    config: AgentConfig,
    tokens_used: int,
    incarnation_name: str = "",
    task_in_progress: str = "",
    heartbeat_cycle_key: str | None = None,
) -> bool:
    """
    Deduct tokens and check if budget is exhausted after this cycle.
    If heartbeat_cycle_key is set, also records per-cycle heartbeat usage.
    Sends dashboard notification if exhausted. Returns True if still ok.
    Current cycle always completes — this is called AFTER the cycle.
    """
    budget = load_budget(config.home)
    budget["tokens_used"] = budget.get("tokens_used", 0) + tokens_used
    if heartbeat_cycle_key:
        budget.setdefault("heartbeat_cycles", {})[heartbeat_cycle_key] = {
            "tokens_used": tokens_used,
            "model": config.model,
        }
    save_budget(config.home, budget)
    used = budget.get("tokens_used", 0)

    if used >= config.weekly_budget_tokens and budget.get("status") != "budget_paused":
        budget["status"] = "budget_paused"
        save_budget(config.home, budget)
        _write_budget_exhausted_notification(config.name, incarnation_name, task_in_progress)
        print(
            f"[budget] Agent '{config.name}' budget exhausted: "
            f"{used}/{config.weekly_budget_tokens} tokens used. Status: budget_paused",
            file=sys.stderr,
        )
        return False

    return True


def resume_budget(home: Path, additional_tokens: int = 0) -> dict[str, Any]:
    """Resume a budget-paused agent, optionally granting extra tokens."""
    budget = load_budget(home)
    budget["status"] = "active"
    if additional_tokens > 0:
        budget["tokens_used"] = max(0, budget.get("tokens_used", 0) - additional_tokens)
    save_budget(home, budget)
    return budget


def reset_weekly_budgets() -> list[str]:
    """Reset all agent budgets for the new week. Called by scheduler Monday task."""
    reset = []
    for home in AGENT_HOME_BASE.iterdir():
        path = _budget_path(home)
        if not path.exists():
            continue
        try:
            existing = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            existing = {}
        budget = {
            "week_start": _get_week_start(),
            "tokens_used": 0,
            "status": "active",
            "heartbeat_weekly_budget": existing.get("heartbeat_weekly_budget", DEFAULT_HEARTBEAT_WEEKLY_BUDGET),
            "heartbeat_cycles": {},
        }
        save_budget(home, budget)
        reset.append(home.name)
    return reset


# Keep old name as alias
reset_all_budgets = reset_weekly_budgets


def _write_budget_exhausted_notification(
    agent_name: str,
    incarnation_name: str,
    task_in_progress: str,
) -> None:
    """Write budget exhaustion notification to dashboard queue."""
    import uuid
    from datetime import datetime, timezone

    DASHBOARD_QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    filename = f"{ts.replace(':', '-')}-{agent_name}-budget.json"
    path = DASHBOARD_QUEUE_DIR / filename

    notification = {
        "ts": ts,
        "type": "budget_exhausted",
        "agent": agent_name,
        "incarnation": incarnation_name,
        "task_in_progress": task_in_progress,
        "category": "alert",
    }

    try:
        path.write_text(json.dumps(notification, indent=2))
    except OSError as e:
        print(f"[budget] Failed to write dashboard notification: {e}", file=sys.stderr)
