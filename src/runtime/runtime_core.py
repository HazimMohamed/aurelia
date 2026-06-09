"""Aurelia runtime core — registry, health, and system-level state.

Agent execution logic (spawn, dispatch, bardo, etc.) lives in src/manas/agent.py
and runs inside the per-agent Manas process.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from ..config import AgentConfig
from .registry import AgentRegistry
from .types import AgentSummary, HealthReport, IncarnationSummary


# ── Exception types (used by HTTP transport for status code mapping) ───────────

class IncarnationNotFound(Exception):
    pass


class AgentNotFound(Exception):
    pass


# ── Global registry ────────────────────────────────────────────────────────────

_registry = AgentRegistry()
_scheduler = None  # set by runtime_daemon.main() after scheduler thread starts


def get_registry() -> AgentRegistry:
    return _registry


# ── System-level queries ───────────────────────────────────────────────────────


def list_agents() -> list[AgentSummary]:
    from ..agent.budget import get_budget_remaining, load_budget
    from .scheduler import count_pending_for_agent

    summaries = []
    for agent_name in _registry.all_agents():
        config = _registry.get(agent_name)
        status_dict = _registry.agent_status(agent_name)

        budget_remaining = None
        weekly_budget = None
        if config:
            try:
                budget_remaining = get_budget_remaining(config)
                weekly_budget = config.weekly_budget_tokens
            except Exception:
                pass

        summaries.append(AgentSummary(
            name=agent_name,
            status=status_dict.get("status", "unknown"),
            incarnation=status_dict.get("incarnation"),
            cycle=status_dict.get("cycle"),
            last_active=status_dict.get("last_active"),
            budget_remaining=budget_remaining,
            weekly_budget=weekly_budget,
            scheduler_queue=count_pending_for_agent(agent_name),
        ))

    return summaries


def get_health() -> HealthReport:
    agents = list_agents()

    dashboard_queue = Path("/var/aurelia/dashboard/queue")
    pending_dashboard = (
        len(list(dashboard_queue.glob("*.json")))
        if dashboard_queue.exists()
        else 0
    )

    return HealthReport(status="healthy", agents=agents, pending_dashboard=pending_dashboard)


def get_budget_info(agent: str) -> dict:
    from ..agent.budget import load_budget
    config = _registry.get(agent)
    if not config:
        return {}
    return load_budget(config.data_dir)
