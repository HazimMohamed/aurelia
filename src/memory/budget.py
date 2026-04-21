"""Budget tracking: per-agent weekly token budgets with file locking."""

from __future__ import annotations

import fcntl
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from ..samsara.config import AgentConfig

BUDGET_DIR = Path("/var/aurelia/budgets")
DASHBOARD_QUEUE_DIR = Path("/var/aurelia/dashboard/queue")
MINIMUM_BUDGET_THRESHOLD = 1_000  # tokens — below this, heartbeat precheck fails


def _get_week_start() -> str:
    """Return ISO date string for Monday of the current week."""
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    return monday.isoformat()


def load_budget(agent_name: str) -> dict[str, Any]:
    """Load budget for agent, returning fresh budget if file missing or new week."""
    BUDGET_DIR.mkdir(parents=True, exist_ok=True)
    path = BUDGET_DIR / f"{agent_name}.json"
    if not path.exists():
        return {"week_start": _get_week_start(), "tokens_used": 0, "status": "active"}
    try:
        data = json.loads(path.read_text())
        # Reset if new week
        if data.get("week_start") != _get_week_start():
            return {"week_start": _get_week_start(), "tokens_used": 0, "status": "active"}
        return data
    except (json.JSONDecodeError, OSError):
        return {"week_start": _get_week_start(), "tokens_used": 0, "status": "active"}


def save_budget(agent_name: str, budget: dict[str, Any]) -> None:
    """Save budget with file lock."""
    BUDGET_DIR.mkdir(parents=True, exist_ok=True)
    path = BUDGET_DIR / f"{agent_name}.json"
    with open(path, "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            json.dump(budget, f, indent=2)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def deduct_budget(agent_name: str, tokens: int) -> dict[str, Any]:
    """Deduct tokens from budget. Resets weekly counter if new week."""
    budget = load_budget(agent_name)
    # If new week, reset was already handled in load_budget
    budget["tokens_used"] = budget.get("tokens_used", 0) + tokens
    save_budget(agent_name, budget)
    return budget


def get_budget_remaining(config: AgentConfig) -> int:
    """Return tokens remaining in current weekly budget."""
    budget = load_budget(config.name)
    if budget.get("status") == "budget_paused":
        return 0
    used = budget.get("tokens_used", 0)
    return max(0, config.weekly_budget_tokens - used)


def is_budget_ok(config: AgentConfig) -> bool:
    """Return True if the agent has budget remaining and is not paused."""
    budget = load_budget(config.name)
    if budget.get("status") == "budget_paused":
        return False
    used = budget.get("tokens_used", 0)
    return used < config.weekly_budget_tokens


def check_and_apply_budget(
    config: AgentConfig,
    tokens_used: int,
    incarnation_name: str = "",
    task_in_progress: str = "",
) -> bool:
    """
    Deduct tokens and check if budget is exhausted after this cycle.
    Sends dashboard notification if exhausted. Returns True if still ok.
    Current cycle always completes — this is called AFTER the cycle.
    """
    budget = deduct_budget(config.name, tokens_used)
    used = budget.get("tokens_used", 0)

    if used >= config.weekly_budget_tokens and budget.get("status") != "budget_paused":
        # Mark as paused
        budget["status"] = "budget_paused"
        save_budget(config.name, budget)

        # Write deterministic dashboard notification
        _write_budget_exhausted_notification(config.name, incarnation_name, task_in_progress)

        print(
            f"[budget] Agent '{config.name}' budget exhausted: "
            f"{used}/{config.weekly_budget_tokens} tokens used. Status: budget_paused",
            file=sys.stderr,
        )
        return False

    return True


def resume_budget(agent_name: str, additional_tokens: int = 0) -> dict[str, Any]:
    """Resume a budget-paused agent, optionally granting extra tokens."""
    budget = load_budget(agent_name)
    budget["status"] = "active"
    if additional_tokens > 0:
        # Reduce tokens_used by the override amount (effectively grants more headroom)
        budget["tokens_used"] = max(0, budget.get("tokens_used", 0) - additional_tokens)
    save_budget(agent_name, budget)
    return budget


def reset_weekly_budgets() -> list[str]:
    """Reset all agent budgets for the new week. Called by scheduler Monday task."""
    BUDGET_DIR.mkdir(parents=True, exist_ok=True)
    reset = []
    for budget_file in BUDGET_DIR.glob("*.json"):
        agent_name = budget_file.stem
        budget = {
            "week_start": _get_week_start(),
            "tokens_used": 0,
            "status": "active",
        }
        save_budget(agent_name, budget)
        reset.append(agent_name)
    return reset


# Keep old name as alias for any callers that used reset_all_budgets
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
