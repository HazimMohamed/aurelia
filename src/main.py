"""Aurelia HTTP transport — thin wrapper over src/runtime.py."""

from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Any, Optional

# Load .env from project root if present (dev convenience)
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_path)

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, model_validator

from . import runtime
from .runtime import (
    AgentNotFound,
    IncarnationAlreadyActive,
    IncarnationNotActive,
    IncarnationNotFound,
)
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

app = FastAPI(title="Aurelia", version="0.4.0")

# Registry exposed from runtime module (single instance)
registry = runtime.get_registry()


# ── Auth helpers ───────────────────────────────────────────────────────────────

def _load_global_config() -> dict:
    if GLOBAL_CONFIG_PATH.exists():
        with GLOBAL_CONFIG_PATH.open() as f:
            return json.load(f)
    return {}


def _get_agent_token(agent_name: str) -> Optional[str]:
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
    """Dependency: authenticate an agent from Bearer token."""
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
    """Send a human message to an agent. Finds active incarnation or spawns one."""
    agent_name = req.to.agent
    if not agent_name:
        raise HTTPException(status_code=400, detail="'to.agent' is required")

    # Validate agent exists
    config = registry.get(agent_name)
    if not config:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_name}' not found. Run scripts/setup_agent.sh to create it.",
        )

    # Transport-level policy: find active incarnation or spawn one
    if req.to.incarnation_id:
        # Explicit incarnation requested — validate it exists
        try:
            incarnations = runtime.list_incarnations(agent_name)
        except AgentNotFound as e:
            raise HTTPException(status_code=404, detail=str(e))

        target = next(
            (i for i in incarnations if i.name == req.to.incarnation_id),
            None,
        )
        if not target:
            raise HTTPException(
                status_code=404,
                detail=f"Incarnation '{req.to.incarnation_id}' not found for agent '{agent_name}'",
            )
        if target.status != "active":
            raise HTTPException(
                status_code=409,
                detail=f"Incarnation '{req.to.incarnation_id}' is not active (status: {target.status})",
            )
        active_inc = target
    else:
        # Find active or spawn
        incarnations = runtime.list_incarnations(agent_name)
        active_inc = next((i for i in incarnations if i.status == "active"), None)
        if not active_inc:
            try:
                active_inc = runtime.spawn(agent_name)
            except IncarnationAlreadyActive as e:
                # Race condition: someone spawned between list and spawn — re-query
                incarnations = runtime.list_incarnations(agent_name)
                active_inc = next((i for i in incarnations if i.status == "active"), None)
                if not active_inc:
                    raise HTTPException(status_code=500, detail=str(e))

    sender = req.from_ or "god-lite"

    try:
        response = runtime.dispatch(
            agent=agent_name,
            incarnation=active_inc.name,
            hook=HookType.HUMAN_MESSAGE,
            payload={"content": req.content, "sender": sender},
        )
    except (IncarnationNotFound, IncarnationNotActive) as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent cycle failed: {e}")

    return MessageResponse(
        agent=response.agent,
        incarnation=response.incarnation,
        cycle=response.cycle,
        content=response.content,
    )


@app.get("/health")
def get_health() -> dict:
    """Return health status for all known agents."""
    report = runtime.get_health()

    agents_out = {}
    for summary in report.agents:
        entry: dict[str, Any] = {"status": summary.status}
        if summary.incarnation:
            entry["incarnation"] = summary.incarnation
        if summary.cycle is not None:
            entry["cycle"] = summary.cycle
        if summary.last_active:
            entry["last_active"] = summary.last_active
        if summary.budget_remaining is not None:
            entry["budget_remaining"] = summary.budget_remaining
        if summary.weekly_budget is not None:
            entry["weekly_budget"] = summary.weekly_budget
        entry["scheduler_queue"] = summary.scheduler_queue

        if registry.get(summary.name):
            budget_info = runtime.get_budget_info(summary.name)
            entry["budget_status"] = budget_info.get("status", "active")
            entry["tokens_used_this_week"] = budget_info.get("tokens_used", 0)

        agents_out[summary.name] = entry

    return {
        "status": report.status,
        "agents": agents_out,
        "pending_dashboard": report.pending_dashboard,
    }


@app.get("/history/{agent_name}/{incarnation_id}")
def get_history(agent_name: str, incarnation_id: str) -> dict:
    """Return transcript for a specific incarnation."""
    try:
        entries = runtime.get_history(agent_name, incarnation_id)
    except AgentNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except IncarnationNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "agent": agent_name,
        "incarnation": incarnation_id,
        "entries": [
            {
                "ts": e.ts,
                "type": e.type,
                "content": e.content,
                "cycle": e.cycle,
                **e.extra,
            }
            for e in entries
        ],
    }


@app.get("/history/{agent_name}")
def list_agent_incarnations(agent_name: str) -> dict:
    """List all incarnations for an agent."""
    try:
        incarnations = runtime.list_incarnations(agent_name)
    except AgentNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "agent": agent_name,
        "incarnations": [
            {
                "name": i.name,
                "status": i.status,
                "cycle": i.cycle,
                "last_active": i.last_active,
            }
            for i in incarnations
        ],
    }


@app.get("/agents")
def list_agents() -> dict:
    """List all registered agents and their status."""
    agents = runtime.list_agents()
    return {
        "agents": [
            {
                "name": a.name,
                "status": a.status,
                "incarnation": a.incarnation,
                "cycle": a.cycle,
                "last_active": a.last_active,
                "budget_remaining": a.budget_remaining,
                "weekly_budget": a.weekly_budget,
                "scheduler_queue": a.scheduler_queue,
            }
            for a in agents
        ]
    }


# ── Bardo (manual testing tool) ───────────────────────────────────────────────

@app.post("/bardo/{agent_name}", response_model=BardoResponse)
def post_bardo(agent_name: str) -> BardoResponse:
    """Manually trigger bardo for an agent's active incarnation."""
    if not registry.get(agent_name):
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found.")

    try:
        active = runtime.get_active(agent_name)
    except AgentNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))

    if not active:
        raise HTTPException(
            status_code=409,
            detail=f"Agent '{agent_name}' has no active incarnation to bardo.",
        )

    try:
        result = runtime.trigger_bardo(agent_name, active)
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


# ── Internal endpoints ─────────────────────────────────────────────────────────

@app.post("/internal/process")
def internal_process(req: ProcessRequest) -> dict:
    """Process a scheduled work item (called by scheduler daemon or agent daemon)."""
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

    # Build hook prompt via runtime (keeps context/hooks imports out of main)
    hook_prompt = runtime.build_hook_prompt(
        agent=agent_name,
        hook_type=hook_type,
        goal=req.goal or "",
        payload=payload,
        rebirth_from=req.rebirth_from,
    )

    # Spawn fresh incarnation for autonomous hooks
    incarnation_state = runtime.spawn_fresh_for_hook(agent_name, hook_type)

    try:
        response_text, next_action = runtime.run_hook(
            agent=agent_name,
            hook_type=hook_type,
            hook_prompt=hook_prompt,
            incarnation_state=incarnation_state,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Hook cycle failed: {e}")

    action_type = next_action.get("type", "sleep")

    return {
        "status": "ok",
        "agent": agent_name,
        "incarnation": incarnation_state["name"],
        "hook": hook_type,
        "next_action": action_type,
    }


@app.post("/internal/schedule")
def internal_schedule(
    req: ScheduleRequest,
    agent: Optional[AgentConfig] = Depends(_authenticate_agent),
) -> dict:
    """Schedule a work item. Agents call this to schedule future incarnations."""
    all_allowed = ALLOWED_TYPES | JANITOR_ONLY_TYPES
    if req.type not in all_allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown type '{req.type}'. Allowed: {sorted(ALLOWED_TYPES)}",
        )

    if req.type in JANITOR_ONLY_TYPES:
        if agent is None or agent.name != "janitor":
            raise HTTPException(
                status_code=403,
                detail="Janitor-only type requires authenticated Janitor agent",
            )

    is_janitor = agent is not None and agent.name == "janitor"
    is_invite = req.type == "agent_invite"
    if req.agent != (agent.name if agent else req.agent):
        if not is_janitor and not is_invite:
            raise HTTPException(
                status_code=403,
                detail="Agents can only schedule tasks for themselves",
            )

    target_config = registry.get(req.agent)
    if not target_config:
        raise HTTPException(status_code=404, detail=f"Agent '{req.agent}' not found")

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
    """Internal bardo trigger. Non-fatal if no active incarnation exists."""
    if not registry.get(agent_name):
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found.")

    try:
        active = runtime.get_active(agent_name)
    except AgentNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))

    if not active:
        return {"status": "no_active", "agent": agent_name}

    try:
        result = runtime.trigger_bardo(agent_name, active)
        return {"status": result.get("status", "unknown"), "agent": agent_name, "incarnation": active}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Forced bardo failed: {e}")


@app.post("/internal/registry/reload")
def internal_registry_reload() -> dict:
    """Force the agent registry to reload."""
    registry._refresh()
    return {"status": "reloaded", "agents": registry.all_agents()}


# ── Scheduler management ───────────────────────────────────────────────────────

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
