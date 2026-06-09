"""Per-agent budget tracking: weekly token totals stored in agent home."""

from __future__ import annotations

import fcntl
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from ..config import AGENT_HOME_BASE, AGENT_DATA_BASE, AgentConfig

DASHBOARD_QUEUE_DIR = Path("/var/aurelia/dashboard/queue")
MINIMUM_BUDGET_THRESHOLD = 1_000
DEFAULT_HEARTBEAT_WEEKLY_BUDGET = 100_000

# Sonnet 4.6 prices per million tokens
_PRICES = {
    "input":       3.00,
    "cache_write": 3.75,
    "cache_read":  0.30,
    "output":     15.00,
}


def _get_week_start() -> str:
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    return monday.isoformat()


def _budget_path(home: Path) -> Path:
    return home / "budget.json"


def _empty_tokens() -> dict[str, int]:
    return {"input": 0, "cache_write": 0, "cache_read": 0, "output": 0}


def _add_usage(totals: dict[str, int], usage: dict[str, int]) -> dict[str, int]:
    return {k: totals.get(k, 0) + usage.get(k, 0) for k in _empty_tokens()}


def compute_cost(tokens: dict[str, int]) -> float:
    return round(sum(tokens.get(k, 0) * p / 1_000_000 for k, p in _PRICES.items()), 6)


def load_budget(home: Path) -> dict[str, Any]:
    path = _budget_path(home)
    if not path.exists():
        return _fresh_budget()
    try:
        data = json.loads(path.read_text())
        if data.get("week_start") != _get_week_start():
            return _fresh_budget(
                weekly_budget=data.get("weekly_budget", 300_000),
                heartbeat_weekly_budget=data.get("heartbeat_weekly_budget", DEFAULT_HEARTBEAT_WEEKLY_BUDGET),
            )
        return data
    except (json.JSONDecodeError, OSError):
        return _fresh_budget()


def _fresh_budget(
    weekly_budget: int = 300_000,
    heartbeat_weekly_budget: int = DEFAULT_HEARTBEAT_WEEKLY_BUDGET,
) -> dict[str, Any]:
    return {
        "week_start": _get_week_start(),
        "status": "active",
        "weekly_budget": weekly_budget,
        "heartbeat_weekly_budget": heartbeat_weekly_budget,
        "tokens": _empty_tokens(),
        "heartbeat_tokens": _empty_tokens(),
    }


def save_budget(home: Path, budget: dict[str, Any]) -> None:
    path = _budget_path(home)
    with open(path, "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            json.dump(budget, f, indent=2)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
    try:
        os.chmod(path, 0o660)
    except PermissionError:
        pass


def get_budget_remaining(config: AgentConfig) -> int:
    budget = load_budget(config.data_dir)
    if budget.get("status") == "budget_paused":
        return 0
    total = sum(budget.get("tokens", {}).values())
    return max(0, budget.get("weekly_budget", 300_000) - total)


def get_heartbeat_remaining(data_dir: Path) -> int:
    budget = load_budget(data_dir)
    limit = budget.get("heartbeat_weekly_budget", DEFAULT_HEARTBEAT_WEEKLY_BUDGET)
    used = sum(budget.get("heartbeat_tokens", {}).values())
    return max(0, limit - used)


def is_budget_ok(config: AgentConfig) -> bool:
    budget = load_budget(config.data_dir)
    if budget.get("status") == "budget_paused":
        return False
    total = sum(budget.get("tokens", {}).values())
    return total < budget.get("weekly_budget", 300_000)


def check_and_apply_budget(
    config: AgentConfig,
    usage: dict[str, int],
    incarnation_name: str = "",
    task_in_progress: str = "",
    is_heartbeat: bool = False,
) -> bool:
    """
    Apply usage to weekly totals and optionally heartbeat totals.
    Sends dashboard notification if weekly budget exhausted.
    Returns True if budget still ok.
    """
    budget = load_budget(config.data_dir)
    budget["tokens"] = _add_usage(budget.get("tokens", _empty_tokens()), usage)
    if is_heartbeat:
        budget["heartbeat_tokens"] = _add_usage(budget.get("heartbeat_tokens", _empty_tokens()), usage)
    save_budget(config.data_dir, budget)

    total = sum(budget["tokens"].values())
    weekly_budget = budget.get("weekly_budget", 300_000)

    if total >= weekly_budget and budget.get("status") != "budget_paused":
        budget["status"] = "budget_paused"
        save_budget(config.data_dir, budget)
        _write_budget_exhausted_notification(config.name, incarnation_name, task_in_progress)
        print(
            f"[budget] Agent '{config.name}' budget exhausted: "
            f"{total}/{weekly_budget} tokens. Status: budget_paused",
            file=sys.stderr,
        )
        return False

    return True


def resume_budget(home: Path, additional_tokens: int = 0) -> dict[str, Any]:
    budget = load_budget(home)
    budget["status"] = "active"
    if additional_tokens > 0:
        budget["tokens"]["output"] = max(0, budget["tokens"].get("output", 0) - additional_tokens)
    save_budget(home, budget)
    return budget


def reset_weekly_budgets() -> list[str]:
    reset = []
    if not AGENT_DATA_BASE.exists():
        return reset
    for data_dir in AGENT_DATA_BASE.iterdir():
        path = _budget_path(data_dir)
        if not path.exists():
            continue
        try:
            existing = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            existing = {}
        save_budget(data_dir, _fresh_budget(
            weekly_budget=existing.get("weekly_budget", 300_000),
            heartbeat_weekly_budget=existing.get("heartbeat_weekly_budget", DEFAULT_HEARTBEAT_WEEKLY_BUDGET),
        ))
        reset.append(data_dir.name)
    return reset


reset_all_budgets = reset_weekly_budgets


def _write_budget_exhausted_notification(
    agent_name: str,
    incarnation_name: str,
    task_in_progress: str,
) -> None:
    from datetime import datetime, timezone
    DASHBOARD_QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    path = DASHBOARD_QUEUE_DIR / f"{ts.replace(':', '-')}-{agent_name}-budget.json"
    try:
        path.write_text(json.dumps({
            "ts": ts,
            "type": "budget_exhausted",
            "agent": agent_name,
            "incarnation": incarnation_name,
            "task_in_progress": task_in_progress,
            "category": "alert",
        }, indent=2))
    except OSError as e:
        print(f"[budget] Failed to write dashboard notification: {e}", file=sys.stderr)
