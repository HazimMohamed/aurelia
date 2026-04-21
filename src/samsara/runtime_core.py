"""Aurelia runtime interface — pure logic, no HTTP concerns."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .config import AgentConfig
from ..agent.hooks import HookType
from .registry import AgentRegistry
from ..agent.incarnation import (
    get_active_incarnation,
    get_or_spawn_incarnation,
    spawn_incarnation,
    load_incarnation,
    get_incarnation_by_id,
)
from ..agent.core import run_agent_cycle_and_parse
from ..memory.bardo import run_bardo
from .scheduler import count_pending_for_agent
from ..agent.transcript import read_entries


# ── Runtime errors ─────────────────────────────────────────────────────────────

class IncarnationAlreadyActive(Exception):
    """Raised by spawn() when an active incarnation already exists for the agent."""


class IncarnationNotFound(Exception):
    """Raised by dispatch() or get_history() when the named incarnation doesn't exist."""


class IncarnationNotActive(Exception):
    """Raised by dispatch() when the named incarnation exists but is not active."""


class AgentNotFound(Exception):
    """Raised when the requested agent name is not registered."""


# ── Return types ───────────────────────────────────────────────────────────────

@dataclass
class IncarnationSummary:
    name: str
    agent: str
    status: str          # "active" | "dissolved"
    cycle: int
    last_active: Optional[str] = None


@dataclass
class AgentResponse:
    agent: str
    incarnation: str
    cycle: int
    content: str
    next_action: dict[str, Any] = field(default_factory=dict)


@dataclass
class TranscriptEntry:
    ts: str
    type: str
    content: Optional[str] = None
    cycle: Optional[int] = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentSummary:
    name: str
    status: str
    incarnation: Optional[str] = None
    cycle: Optional[int] = None
    last_active: Optional[str] = None
    budget_remaining: Optional[int] = None
    weekly_budget: Optional[int] = None
    scheduler_queue: int = 0


@dataclass
class HealthReport:
    status: str
    agents: list[AgentSummary]
    pending_dashboard: int = 0


# ── Global registry (shared with main.py) ─────────────────────────────────────

_registry = AgentRegistry()


def _require_config(agent: str) -> AgentConfig:
    config = _registry.get(agent)
    if not config:
        raise AgentNotFound(f"Agent '{agent}' not registered")
    return config


# ── Public runtime functions ───────────────────────────────────────────────────

def spawn(agent: str, goal: Optional[str] = None) -> IncarnationSummary:
    """Spawn a fresh incarnation. Raises IncarnationAlreadyActive if one is active."""
    config = _require_config(agent)
    active = get_active_incarnation(config)
    if active:
        raise IncarnationAlreadyActive(
            f"Agent '{agent}' already has active incarnation '{active}'"
        )
    name = spawn_incarnation(config)
    state = load_incarnation(config, name)
    return IncarnationSummary(
        name=name,
        agent=agent,
        status="active",
        cycle=state["cycle"],
    )


def dispatch(
    agent: str,
    incarnation: str,
    hook: HookType,
    payload: dict[str, Any],
) -> AgentResponse:
    """
    Send a hook payload to a specific incarnation.
    Raises IncarnationNotFound if incarnation doesn't exist.
    Raises IncarnationNotActive if incarnation is not the active one.
    """
    config = _require_config(agent)

    # Verify incarnation exists in karma
    karma_path = config.karma_dir / incarnation
    if not karma_path.exists():
        raise IncarnationNotFound(
            f"Incarnation '{incarnation}' not found for agent '{agent}'"
        )

    # Verify it is the active incarnation
    active = get_active_incarnation(config)
    if active != incarnation:
        raise IncarnationNotActive(
            f"Incarnation '{incarnation}' is not active for agent '{agent}' "
            f"(active: {active!r})"
        )

    incarnation_state = load_incarnation(config, incarnation)

    content = payload.get("content", "")
    sender = payload.get("sender", "god-lite")
    human_content = content

    from ..agent.tools.registry import build_tool_registry

    tool_registry = build_tool_registry(
        hook_type=hook,
        agent_name=agent,
        agent_config=config,
        incarnation_state=incarnation_state,
    )

    response_text, next_action = run_agent_cycle_and_parse(
        config=config,
        incarnation_state=incarnation_state,
        human_content=human_content,
        sender=sender,
        hook_type=hook,
        tool_registry=tool_registry,
    )

    # Trigger bardo if agent signalled done
    if next_action.get("type") == "done":
        active_name = get_active_incarnation(config)
        if active_name:
            try:
                run_bardo(config, active_name)
            except Exception as e:
                print(f"[runtime] Bardo after done failed: {e}")

    return AgentResponse(
        agent=agent,
        incarnation=incarnation_state["name"],
        cycle=incarnation_state["cycle"],
        content=response_text,
        next_action=next_action,
    )


def get_history(agent: str, incarnation: str) -> list[TranscriptEntry]:
    """
    Read transcript entries for a specific incarnation (active or dissolved).
    Raises IncarnationNotFound if neither karma nor akasha has this incarnation.
    """
    config = _require_config(agent)

    # Check karma first (active), then akasha (dissolved)
    karma_transcript = config.karma_dir / incarnation / "transcript.jsonl"
    akasha_transcript = config.akasha_dir / incarnation / f"{incarnation}-transcript.jsonl"

    if karma_transcript.exists():
        transcript_path = karma_transcript
    elif akasha_transcript.exists():
        transcript_path = akasha_transcript
    else:
        raise IncarnationNotFound(
            f"Incarnation '{incarnation}' not found for agent '{agent}'"
        )

    raw_entries = read_entries(transcript_path)
    result = []
    for e in raw_entries:
        known_keys = {"ts", "type", "content", "cycle"}
        extra = {k: v for k, v in e.items() if k not in known_keys}
        result.append(TranscriptEntry(
            ts=e.get("ts", ""),
            type=e.get("type", ""),
            content=e.get("content"),
            cycle=e.get("cycle"),
            extra=extra,
        ))
    return result


def list_incarnations(agent: str) -> list[IncarnationSummary]:
    """
    List all incarnations for an agent — active (karma) and dissolved (akasha).
    Raises AgentNotFound if agent is not registered.
    """
    config = _require_config(agent)
    summaries: list[IncarnationSummary] = []

    active_name = get_active_incarnation(config)

    # Walk karma dir for active incarnations
    if config.karma_dir.exists():
        for entry in config.karma_dir.iterdir():
            if entry.name in ("current", "episodic", "semantic"):
                continue
            if not entry.is_dir():
                continue
            transcript_path = entry / "transcript.jsonl"
            entries = read_entries(transcript_path)
            cycle = sum(1 for e in entries if e.get("type") == "human_message")
            last_active = _last_ts(entries)
            status = "active" if entry.name == active_name else "sleeping"
            summaries.append(IncarnationSummary(
                name=entry.name,
                agent=agent,
                status=status,
                cycle=cycle,
                last_active=last_active,
            ))

    # Walk akasha dir for dissolved incarnations
    if config.akasha_dir.exists():
        for entry in config.akasha_dir.iterdir():
            if not entry.is_dir():
                continue
            transcript_path = entry / f"{entry.name}-transcript.jsonl"
            entries = read_entries(transcript_path)
            cycle = sum(1 for e in entries if e.get("type") == "human_message")
            last_active = _last_ts(entries)
            summaries.append(IncarnationSummary(
                name=entry.name,
                agent=agent,
                status="dissolved",
                cycle=cycle,
                last_active=last_active,
            ))

    summaries.sort(key=lambda s: s.last_active or "", reverse=True)
    return summaries


def list_agents() -> list[AgentSummary]:
    """List all registered agents and their current status."""
    from ..memory.budget import get_budget_remaining, load_budget

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
    """System-wide health: agents, budgets, scheduler queue."""
    agents = list_agents()

    dashboard_queue = Path("/var/aurelia/dashboard/queue")
    pending_dashboard = (
        len(list(dashboard_queue.glob("*.json")))
        if dashboard_queue.exists()
        else 0
    )

    return HealthReport(
        status="healthy",
        agents=agents,
        pending_dashboard=pending_dashboard,
    )


# ── Internal helpers ───────────────────────────────────────────────────────────

def _last_ts(entries: list[dict]) -> Optional[str]:
    """Return the last timestamp from a list of transcript entries."""
    for entry in reversed(entries):
        ts = entry.get("ts")
        if ts:
            return ts
    return None


def spawn_fresh_for_hook(agent: str, hook_type: str) -> dict:
    """
    For autonomous hooks (heartbeat, scheduled_task, agent_invite): spawn a fresh
    incarnation, removing any dangling active symlink first.
    Used by /internal/process — not part of the public runtime interface.
    """
    config = _require_config(agent)
    if hook_type == HookType.HUMAN_MESSAGE:
        return get_or_spawn_incarnation(config)

    # Autonomous hooks always get a fresh incarnation
    active = get_active_incarnation(config)
    if active:
        if config.current_symlink.is_symlink():
            config.current_symlink.unlink()

    name = spawn_incarnation(config)
    return load_incarnation(config, name)


def run_hook(
    agent: str,
    hook_type: str,
    hook_prompt: str,
    incarnation_state: dict,
) -> tuple[str, dict]:
    """
    Run a prepared hook prompt against a spawned incarnation state.
    Returns (response_text, next_action).
    Used by /internal/process so main.py doesn't need to import from core directly.
    """
    config = _require_config(agent)

    from ..agent.tools.registry import build_tool_registry

    tool_registry = build_tool_registry(
        hook_type=hook_type,
        agent_name=agent,
        agent_config=config,
        incarnation_state=incarnation_state,
    )

    response_text, next_action = run_agent_cycle_and_parse(
        config=config,
        incarnation_state=incarnation_state,
        human_content=hook_prompt,
        sender="scheduler",
        hook_type=hook_type,
        tool_registry=tool_registry,
    )

    if next_action.get("type") == "done":
        active_name = get_active_incarnation(config)
        if active_name:
            try:
                run_bardo(config, active_name)
            except Exception as e:
                print(f"[runtime] Bardo after done failed: {e}")

    return response_text, next_action


def get_active(agent: str) -> Optional[str]:
    """Return the active incarnation name for an agent, or None."""
    config = _require_config(agent)
    return get_active_incarnation(config)


def process_scheduled_item(item: dict) -> dict:
    """
    Process a scheduled item directly — called by the scheduler thread inside the runtime daemon.
    Routes to the correct hook handler based on item type.
    """
    from ..agent.hooks import HookType
    agent = item.get("agent")
    item_type = item.get("type", "scheduled_task")
    payload = item.get("payload") or {}
    payload["goal"] = item.get("goal", "")
    payload["rebirth_from"] = item.get("rebirth_from")

    if item_type == "bardo_check":
        from ..memory.bardo import check_bardo_timeouts
        _registry = get_registry()
        triggered = check_bardo_timeouts(_registry)
        return {"status": "ok", "triggered": triggered}

    if item_type == "budget_reset":
        from ..memory.budget import reset_all_budgets
        reset_all_budgets()
        return {"status": "ok", "action": "budget_reset"}

    if item_type == "heartbeat":
        hook = HookType.HEARTBEAT
    elif item_type == "agent_invite":
        hook = HookType.AGENT_INVITE
    else:
        hook = HookType.SCHEDULED_TASK

    config = _require_config(agent)
    from ..agent.hooks import heartbeat_precheck
    if hook == HookType.HEARTBEAT and not heartbeat_precheck(config):
        return {"status": "skipped", "reason": "precheck_false", "agent": agent}

    incarnations = list_incarnations(agent)
    active = next((i for i in incarnations if i.status == "active"), None)
    if not active:
        active = spawn(agent, goal=payload.get("goal"))

    # Build the hook prompt so dispatch gets non-empty content
    goal = payload.get("goal", "")
    rebirth_from = payload.get("rebirth_from")
    prompt = build_hook_prompt(agent, hook.value if hasattr(hook, "value") else hook, goal, payload, rebirth_from)
    payload["content"] = prompt

    return dispatch(agent, active.name, hook, payload).__dict__


def trigger_bardo(agent: str, incarnation: str) -> dict:
    """Trigger bardo for a specific incarnation. Returns bardo result dict."""
    config = _require_config(agent)
    return run_bardo(config, incarnation)


def build_hook_prompt(
    agent: str,
    hook_type: str,
    goal: str,
    payload: dict,
    rebirth_from: Optional[str] = None,
) -> str:
    """
    Build the full hook prompt string for an autonomous hook.
    Used by /internal/process so main.py doesn't import from context directly.
    """
    from ..agent.context import load_recent_episodic_summary, load_episodic_extended
    from ..agent.hooks import (
        format_heartbeat_prompt,
        format_task_goal,
        format_agent_invite,
        HookType,
    )

    config = _require_config(agent)

    if hook_type == HookType.HEARTBEAT:
        episodic_context = load_recent_episodic_summary(config)
        parts = []
        if episodic_context:
            parts.append(episodic_context)
        parts.append(format_heartbeat_prompt(config))
        return "\n\n".join(parts)

    elif hook_type == HookType.SCHEDULED_TASK:
        task_payload = {"goal": goal, "type": hook_type, **payload}
        parts = []
        if rebirth_from:
            rebirth_context = load_episodic_extended(config, rebirth_from)
            if rebirth_context:
                parts.append(rebirth_context)
        parts.append(format_task_goal(task_payload))
        return "\n\n".join(parts)

    elif hook_type == "agent_invite":
        return format_agent_invite(payload)

    else:
        return goal or "You have been woken up. Do your work."


def get_budget_info(agent: str) -> dict:
    """Return raw budget dict for an agent (status, tokens_used, etc.)."""
    from ..memory.budget import load_budget
    return load_budget(agent)


def get_registry() -> AgentRegistry:
    """Expose the shared registry for use in main.py."""
    return _registry
