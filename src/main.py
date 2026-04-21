"""Aurelia Milestone 2 — FastAPI server."""

from __future__ import annotations

import json
import os
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Load .env from project root if present (dev convenience)
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_path)

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, model_validator

from .registry import AgentRegistry
from .incarnation import get_or_spawn_incarnation, get_incarnation_by_id, spawn_incarnation
from .core import run_agent_cycle, run_agent_cycle_and_parse
from .bardo import run_bardo
from .config import AgentConfig, GLOBAL_CONFIG_PATH
from .hooks import (
    HookType,
    heartbeat_precheck,
    format_heartbeat_prompt,
    format_task_goal,
    format_agent_invite,
)
from .scheduler import (
    ScheduledItem,
    ALLOWED_TYPES,
    JANITOR_ONLY_TYPES,
    write_scheduled_item,
    count_pending_for_agent,
    _parse_when,
)
from .context import load_recent_episodic_summary, load_episodic_extended
from .incarnation import get_active_incarnation

app = FastAPI(title="Aurelia", version="0.2.0")

# Global registry — initialized once on startup
registry = AgentRegistry()


# ── Auth helpers ───────────────────────────────────────────────────────────────

def _load_global_config() -> dict:
    if GLOBAL_CONFIG_PATH.exists():
        with GLOBAL_CONFIG_PATH.open() as f:
            return json.load(f)
    return {}


def _get_agent_token(agent_name: str) -> Optional[str]:
    """Return bearer token for an agent, or None if not configured."""
    cfg = _load_global_config()
    return cfg.get("agents", {}).get(agent_name, {}).get("token")


def _load_janitor_token() -> Optional[str]:
    cfg = _load_global_config()
    return cfg.get("janitor", {}).get("scheduler_token")


def _verify_janitor_token(provided_token: str) -> bool:
    expected = _load_janitor_token()
    if not expected:
        return False
    return secrets.compare_digest(provided_token, expected)


def _authenticate_agent(
    authorization: Optional[str] = Header(default=None),
) -> Optional[AgentConfig]:
    """Dependency: authenticate an agent from Bearer token. Returns None if no auth configured."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[len("Bearer "):]
    cfg = _load_global_config()
    agents_cfg = cfg.get("agents", {})
    for agent_name, agent_data in agents_cfg.items():
        if isinstance(agent_data, dict) and agent_data.get("token") == token:
            return registry.get(agent_name)
    return None


# ── Request / Response models ──────────────────────────────────────────────────

class MessageTo(BaseModel):
    agent: str
    incarnation_id: Optional[str] = None


class MessageRequest(BaseModel):
    to: MessageTo
    content: str
    from_: Optional[str] = "god-lite"

    model_config = {"populate_by_name": True}

    @model_validator(mode="before")
    @classmethod
    def alias_from(cls, data):
        if isinstance(data, dict) and "from" in data and "from_" not in data:
            data["from_"] = data.pop("from")
        return data


class MessageResponse(BaseModel):
    agent: str
    incarnation: str
    cycle: int
    content: str


class BardoResponse(BaseModel):
    status: str
    agent: str
    incarnation: Optional[str] = None
    message: Optional[str] = None
    episodic_path: Optional[str] = None
    akasha_path: Optional[str] = None


class ScheduleRequest(BaseModel):
    agent: str
    goal: str
    when: str = "1h"
    type: str = "scheduled_task"
    recurring: bool = False
    interval_hours: Optional[float] = None
    rebirth_from: Optional[str] = None
    created_by: Optional[str] = None
    payload: Optional[dict[str, Any]] = None


class ProcessRequest(BaseModel):
    """Matches ScheduledItem dict structure."""
    id: Optional[str] = None
    agent: str
    goal: str
    type: str = "scheduled_task"
    trigger_time: Optional[str] = None
    recurring: bool = False
    interval_hours: Optional[float] = None
    rebirth_from: Optional[str] = None
    created_by: str = "system"
    status: str = "pending"
    created_at: Optional[str] = None
    payload: Optional[dict[str, Any]] = None


# ── Public endpoints ───────────────────────────────────────────────────────────

@app.post("/message", response_model=MessageResponse)
def post_message(req: MessageRequest) -> MessageResponse:
    """Send a human message to an agent and receive a response."""
    agent_name = req.to.agent
    if not agent_name:
        raise HTTPException(status_code=400, detail="'to.agent' is required")

    config = registry.get(agent_name)
    if not config:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_name}' not found. Run scripts/setup_agent.sh to create it.",
        )

    if req.to.incarnation_id:
        try:
            incarnation_state = get_incarnation_by_id(config, req.to.incarnation_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
    else:
        incarnation_state = get_or_spawn_incarnation(config)

    sender = req.from_ or "god-lite"

    from .tools.registry import build_tool_registry
    tool_registry = build_tool_registry(
        hook_type=HookType.HUMAN_MESSAGE,
        agent_name=agent_name,
        agent_config=config,
        incarnation_state=incarnation_state,
    )

    try:
        response_text, next_action = run_agent_cycle_and_parse(
            config=config,
            incarnation_state=incarnation_state,
            human_content=req.content,
            sender=sender,
            hook_type=HookType.HUMAN_MESSAGE,
            tool_registry=tool_registry,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent cycle failed: {e}")

    # Handle next action
    action_type = next_action.get("type", "sleep")
    if action_type == "done":
        active_name = get_active_incarnation(config)
        if active_name:
            try:
                run_bardo(config, active_name)
            except Exception as e:
                print(f"[main] Bardo after done failed: {e}")

    return MessageResponse(
        agent=agent_name,
        incarnation=incarnation_state["name"],
        cycle=incarnation_state["cycle"],
        content=response_text,
    )


@app.post("/bardo/{agent_name}", response_model=BardoResponse)
def post_bardo(agent_name: str) -> BardoResponse:
    """Manually trigger bardo for an agent's active incarnation."""
    config = registry.get(agent_name)
    if not config:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found.")

    active = get_active_incarnation(config)
    if not active:
        raise HTTPException(
            status_code=409,
            detail=f"Agent '{agent_name}' has no active incarnation to bardo.",
        )

    try:
        result = run_bardo(config, active)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bardo failed: {e}")

    return BardoResponse(
        status=result.get("status", "unknown"),
        agent=agent_name,
        incarnation=result.get("incarnation"),
        message=result.get("message"),
        episodic_path=result.get("episodic_path"),
        akasha_path=result.get("akasha_path"),
    )


@app.get("/health")
def get_health() -> dict:
    """Return health status for all known agents, including scheduler queue depth."""
    agents = {}
    for agent_name in registry.all_agents():
        status = registry.agent_status(agent_name)
        status["scheduler_queue"] = count_pending_for_agent(agent_name)
        agents[agent_name] = status

    return {
        "status": "healthy",
        "agents": agents,
    }


# ── Internal endpoints ─────────────────────────────────────────────────────────

@app.post("/internal/process")
def internal_process(req: ProcessRequest) -> dict:
    """
    Process a scheduled work item (called by scheduler daemon or agent daemon).
    Runs the appropriate hook for the agent.
    """
    agent_name = req.agent
    config = registry.get(agent_name)
    if not config:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found.")

    hook_type = req.type
    payload = req.payload or {}

    # Heartbeat pre-check
    if hook_type == HookType.HEARTBEAT:
        if not heartbeat_precheck(config):
            return {"status": "skipped", "reason": "heartbeat_precheck_false", "agent": agent_name}

    # Build hook prompt
    if hook_type == HookType.HEARTBEAT:
        # Load recent episodic context for heartbeat
        episodic_context = load_recent_episodic_summary(config)
        prompt_parts = []
        if episodic_context:
            prompt_parts.append(episodic_context)
        prompt_parts.append(format_heartbeat_prompt(config))
        hook_prompt = "\n\n".join(prompt_parts)

    elif hook_type == HookType.SCHEDULED_TASK:
        task_payload = {
            "goal": req.goal,
            "type": hook_type,
            **payload,
        }
        prompt_parts = []
        if req.rebirth_from:
            rebirth_context = load_episodic_extended(config, req.rebirth_from)
            if rebirth_context:
                prompt_parts.append(rebirth_context)
        prompt_parts.append(format_task_goal(task_payload))
        hook_prompt = "\n\n".join(prompt_parts)

    elif hook_type == "agent_invite":
        hook_prompt = format_agent_invite(payload)

    else:
        hook_prompt = req.goal or "You have been woken up. Do your work."

    # For autonomous hooks, spawn a fresh incarnation
    incarnation_state = spawn_incarnation_for_hook(config, hook_type)

    from .tools.registry import build_tool_registry
    tool_registry = build_tool_registry(
        hook_type=hook_type,
        agent_name=agent_name,
        agent_config=config,
        incarnation_state=incarnation_state,
    )

    try:
        response_text, next_action = run_agent_cycle_and_parse(
            config=config,
            incarnation_state=incarnation_state,
            human_content=hook_prompt,
            sender="scheduler",
            hook_type=hook_type,
            tool_registry=tool_registry,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Hook cycle failed: {e}")

    # Handle next action
    action_type = next_action.get("type", "sleep")
    if action_type == "done":
        active_name = get_active_incarnation(config)
        if active_name:
            try:
                run_bardo(config, active_name)
            except Exception as e:
                print(f"[internal/process] Bardo after done failed: {e}")

    return {
        "status": "ok",
        "agent": agent_name,
        "incarnation": incarnation_state["name"],
        "hook": hook_type,
        "next_action": action_type,
    }


def spawn_incarnation_for_hook(config: AgentConfig, hook_type: str) -> dict:
    """
    For autonomous hooks (heartbeat, scheduled_task, agent_invite):
    spawn a fresh incarnation. For human_message: get or spawn.
    """
    if hook_type == HookType.HUMAN_MESSAGE:
        return get_or_spawn_incarnation(config)
    else:
        # Force a fresh incarnation for each autonomous wakeup
        # First, clean up any existing active incarnation (but don't bardo it here)
        from .incarnation import get_active_incarnation as _get_active
        active = _get_active(config)
        if active:
            # Remove current symlink so spawn creates fresh
            if config.current_symlink.is_symlink():
                config.current_symlink.unlink()
        incarnation_name = spawn_incarnation(config)
        from .incarnation import load_incarnation
        return load_incarnation(config, incarnation_name)


@app.post("/internal/schedule")
def internal_schedule(
    req: ScheduleRequest,
    agent: Optional[AgentConfig] = Depends(_authenticate_agent),
) -> dict:
    """
    Schedule a work item. Agents call this to schedule future incarnations.
    Enforces typed action whitelist and Janitor-only types.
    """
    # Validate action type
    all_allowed = ALLOWED_TYPES | JANITOR_ONLY_TYPES
    if req.type not in all_allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown type '{req.type}'. Allowed: {sorted(ALLOWED_TYPES)}",
        )

    # Janitor-only type enforcement
    if req.type in JANITOR_ONLY_TYPES:
        if agent is None or agent.name != "janitor":
            raise HTTPException(
                status_code=403,
                detail="Janitor-only type requires authenticated Janitor agent",
            )

    # Agents can only schedule for themselves (unless Janitor or agent_invite type)
    # agent_invite is allowed to target other agents — that's its whole purpose
    is_janitor = agent is not None and agent.name == "janitor"
    is_invite = req.type == "agent_invite"
    if req.agent != (agent.name if agent else req.agent):
        if not is_janitor and not is_invite:
            raise HTTPException(
                status_code=403,
                detail="Agents can only schedule tasks for themselves",
            )

    # Verify target agent exists
    target_config = registry.get(req.agent)
    if not target_config:
        raise HTTPException(status_code=404, detail=f"Agent '{req.agent}' not found")

    # Parse trigger time
    trigger_dt = _parse_when(req.when)
    trigger_time = trigger_dt.isoformat(timespec="seconds").replace("+00:00", "Z")

    created_by = req.created_by or (agent.name if agent else "system")

    item = ScheduledItem(
        agent=req.agent,
        goal=req.goal,
        type=req.type,
        trigger_time=trigger_time,
        recurring=req.recurring,
        interval_hours=req.interval_hours,
        rebirth_from=req.rebirth_from,
        created_by=created_by,
        payload=req.payload or {},
    )

    write_scheduled_item(item)

    return {"scheduled": item.id, "trigger_time": trigger_time, "agent": req.agent}


@app.post("/internal/bardo/{agent_name}")
def internal_bardo(agent_name: str, request: Optional[dict] = None) -> dict:
    """
    Internal bardo trigger (used by invite_agent). Forced bardo on active incarnation.
    Non-fatal if no active incarnation exists.
    """
    config = registry.get(agent_name)
    if not config:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found.")

    active = get_active_incarnation(config)
    if not active:
        return {"status": "no_active", "agent": agent_name}

    try:
        result = run_bardo(config, active)
        return {"status": result.get("status", "unknown"), "agent": agent_name, "incarnation": active}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Forced bardo failed: {e}")


@app.post("/internal/registry/reload")
def internal_registry_reload() -> dict:
    """Force the agent registry to reload (for Janitor tool use)."""
    registry._refresh()
    return {"status": "reloaded", "agents": registry.all_agents()}


# ── Scheduler management endpoints ────────────────────────────────────────────

@app.get("/scheduler/pending")
def get_scheduler_pending(agent: Optional[str] = None) -> dict:
    """List pending scheduled items, optionally filtered by agent."""
    from .scheduler import load_pending_items

    items = load_pending_items()
    if agent:
        items = [i for i in items if i.agent == agent]

    return {
        "pending": [i.to_dict() for i in items],
        "count": len(items),
    }


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
