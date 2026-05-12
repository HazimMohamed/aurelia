"""Aurelia HTTP transport — thin client over the runtime daemon."""

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
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, model_validator

from .client import client as runtime
from ..agent.hooks import HookType
from ..samsara.config import AgentConfig, GLOBAL_CONFIG_PATH
from ..samsara.scheduler import (
    ScheduledItem,
    ALLOWED_TYPES,
    JANITOR_ONLY_TYPES,
    write_scheduled_item,
    count_pending_for_agent,
    _parse_when,
)

app = FastAPI(title="Aurelia", version="0.4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Auth helpers ───────────────────────────────────────────────────────────────

def _load_global_config() -> dict:
    if GLOBAL_CONFIG_PATH.exists():
        with GLOBAL_CONFIG_PATH.open() as f:
            return json.load(f)
    return {}


def _get_agent_config(agent_name: str) -> Optional[AgentConfig]:
    """Load an AgentConfig from the registry via the daemon."""
    # We use the config module directly for auth — it's read-only filesystem access
    # and doesn't need to go through the daemon.
    from ..samsara.config import AGENT_DATA_BASE, load_agent_config
    try:
        agent_json = AGENT_DATA_BASE / agent_name / "agent.json"
        if not agent_json.exists():
            return None
        return load_agent_config(agent_name)
    except Exception:
        return None


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
            return _get_agent_config(agent_name)
    return None


def _require_agent(agent_name: str) -> AgentConfig:
    """Raise 404 if agent is not registered."""
    config = _get_agent_config(agent_name)
    if not config:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_name}' not found. Run scripts/setup_agent.sh to create it.",
        )
    return config


def _runtime_error_to_http(e: RuntimeError) -> HTTPException:
    """Convert a RuntimeError from the client into an appropriate HTTP error."""
    msg = str(e)
    if "AgentNotFound" in msg:
        return HTTPException(status_code=404, detail=msg)
    if "IncarnationNotFound" in msg:
        return HTTPException(status_code=404, detail=msg)
    return HTTPException(status_code=500, detail=msg)


def _classify_anthropic_error(e: Exception) -> HTTPException:
    """Map Anthropic API errors to appropriate HTTP status codes."""
    cls = type(e).__name__
    msg = str(e)
    status_code = getattr(e, "status_code", None)
    if status_code == 529 or "overloaded" in msg.lower() or "OverloadedError" in cls:
        return HTTPException(status_code=503, detail=f"Anthropic API overloaded, please retry: {e}")
    if status_code == 429 or "rate" in msg.lower():
        return HTTPException(status_code=429, detail=f"Anthropic API rate limit: {e}")
    if status_code == 401 or "auth" in msg.lower():
        return HTTPException(status_code=401, detail=f"Anthropic API authentication error: {e}")
    return HTTPException(status_code=500, detail=f"Anthropic API error: {e}")


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


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _resolve_active_incarnation(agent_name: str, incarnation_id: Optional[str]):
    """Find or spawn the primary incarnation for a message request.

    Returns an IncarnationSummary. Raises HTTPException on any routing failure.
    Any live incarnation (primary or active) can be addressed explicitly by id.
    """
    if incarnation_id:
        incarnations = runtime.list_incarnations(agent_name)
        target = next((i for i in incarnations if i.name == incarnation_id), None)
        if not target:
            raise HTTPException(
                status_code=404,
                detail=f"Incarnation '{incarnation_id}' not found for agent '{agent_name}'",
            )
        if target.status not in ("primary", "active"):
            raise HTTPException(
                status_code=409,
                detail=f"Incarnation '{incarnation_id}' is not live (status: {target.status})",
            )
        return target

    incarnations = runtime.list_incarnations(agent_name)
    primary = next((i for i in incarnations if i.status == "primary"), None)
    if not primary:
        try:
            primary = runtime.spawn(agent_name)
        except RuntimeError as e:
            raise _runtime_error_to_http(e)
    return primary


def _sse(event: str, data: dict) -> str:
    """Format a single Server-Sent Event."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _socket_frames_to_sse(frames, agent_name: str, active_inc) -> Iterator[str]:
    """Translate raw socket stream frames into SSE events for the browser.

    Socket protocol (flat, internal) → SSE format (named events, Anthropic-aligned):

        thinking_delta  → content_block_delta  {delta: {type: thinking_delta, thinking: ...}}
        delta           → content_block_delta  {delta: {type: text_delta, text: ...}}
        tool_call       → tool_use             {id, name, input}
        tool_result     → tool_result          {tool_use_id, result}
        done            → message_stop         {stop_reason, agent, incarnation, cycle}
    """
    yield _sse("message_start", {
        "type": "message_start",
        "agent": agent_name,
        "incarnation": active_inc.name,
        "cycle": active_inc.cycle,
    })

    for frame in frames:
        frame_type = frame.get("type")

        if frame_type == "thinking_delta":
            yield _sse("content_block_delta", {
                "type": "content_block_delta",
                "delta": {"type": "thinking_delta", "thinking": frame.get("content", "")},
            })

        elif frame_type == "delta":
            yield _sse("content_block_delta", {
                "type": "content_block_delta",
                "delta": {"type": "text_delta", "text": frame.get("content", "")},
            })

        elif frame_type == "tool_call":
            yield _sse("tool_use", {
                "type": "tool_use",
                "id": frame.get("tool_use_id", ""),
                "name": frame.get("name", ""),
                "input": frame.get("input", {}),
            })

        elif frame_type == "tool_result":
            yield _sse("tool_result", {
                "type": "tool_result",
                "tool_use_id": frame.get("tool_use_id", ""),
                "result": frame.get("result"),
            })

        elif frame_type == "done":
            done_data = frame.get("data") or {}
            if frame.get("status") == "error":
                yield _sse("error", {
                    "type": "error",
                    "error": frame.get("error", "UnknownError"),
                    "message": frame.get("message", ""),
                })
            yield _sse("message_stop", {
                "type": "message_stop",
                "stop_reason": "end_turn" if frame.get("status") == "ok" else "error",
                "agent": done_data.get("agent", agent_name),
                "incarnation": done_data.get("incarnation", active_inc.name),
                "cycle": done_data.get("cycle", active_inc.cycle),
            })
            return


# ── Public endpoints ───────────────────────────────────────────────────────────

@app.post("/message", response_model=MessageResponse)
def post_message(req: MessageRequest) -> MessageResponse:
    """Send a human message to an agent. Finds active incarnation or spawns one."""
    agent_name = req.to.agent
    if not agent_name:
        raise HTTPException(status_code=400, detail="'to.agent' is required")

    _require_agent(agent_name)

    try:
        active_inc = _resolve_active_incarnation(agent_name, req.to.incarnation_id)
        sender = req.from_ or "god-lite"
        response = runtime.dispatch(
            agent=agent_name,
            incarnation=active_inc.name,
            hook=HookType.HUMAN_MESSAGE,
            payload={"content": req.content, "sender": sender},
        )
    except HTTPException:
        raise
    except RuntimeError as e:
        raise _runtime_error_to_http(e)
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise _classify_anthropic_error(e)

    return MessageResponse(
        agent=response.agent,
        incarnation=response.incarnation,
        cycle=response.cycle,
        content=response.content,
    )


@app.post("/message/stream")
def post_message_stream(req: MessageRequest) -> StreamingResponse:
    """Streaming variant of POST /message. Returns text/event-stream (SSE).

    Events mirror Anthropic's streaming format where applicable:
      message_start       — agent / incarnation / cycle metadata
      content_block_delta — {delta: {type: thinking_delta|text_delta, ...}}
      tool_use            — tool call about to execute {id, name, input}
      tool_result         — tool execution result {tool_use_id, result}
      message_stop        — final event with stop_reason and updated cycle
      error               — sent before message_stop if the cycle failed
    """
    agent_name = req.to.agent
    if not agent_name:
        raise HTTPException(status_code=400, detail="'to.agent' is required")

    _require_agent(agent_name)

    try:
        active_inc = _resolve_active_incarnation(agent_name, req.to.incarnation_id)
    except HTTPException:
        raise
    except (RuntimeError, ConnectionError) as e:
        raise HTTPException(status_code=503, detail=str(e))

    sender = req.from_ or "god-lite"
    payload = {"content": req.content, "sender": sender}

    def generate() -> Iterator[str]:
        frames = runtime.dispatch_stream(
            agent=agent_name,
            incarnation=active_inc.name,
            hook=HookType.HUMAN_MESSAGE,
            payload=payload,
        )
        yield from _socket_frames_to_sse(frames, agent_name, active_inc)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering if behind a proxy
        },
    )


@app.get("/health")
def get_health() -> dict:
    """Return health status for all known agents."""
    try:
        report = runtime.get_health()
    except (RuntimeError, ConnectionError) as e:
        raise HTTPException(status_code=503, detail=str(e))

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

        if _get_agent_config(summary.name):
            try:
                budget_info = runtime.get_budget_info(summary.name)
                entry["budget_status"] = budget_info.get("status", "active")
                entry["tokens_used_this_week"] = budget_info.get("tokens_used", 0)
            except (RuntimeError, ConnectionError):
                pass

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
    except RuntimeError as e:
        raise _runtime_error_to_http(e)
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))

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
    except RuntimeError as e:
        raise _runtime_error_to_http(e)
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))

    return {
        "agent": agent_name,
        "incarnations": [
            {
                "name": i.name,
                "agent": i.agent,
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
    try:
        agents = runtime.list_agents()
    except (RuntimeError, ConnectionError) as e:
        raise HTTPException(status_code=503, detail=str(e))

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


@app.post("/agents/{agent_name}/spawn")
def spawn_incarnation(agent_name: str, make_primary: Optional[bool] = None) -> dict:
    """Spawn a new incarnation for an agent. make_primary defaults to True if none exists."""
    _require_agent(agent_name)
    try:
        result = runtime.spawn(agent_name, make_primary=make_primary)
        return {"agent": agent_name, "incarnation": result.name, "status": result.status}
    except (RuntimeError, ConnectionError) as e:
        raise _runtime_error_to_http(RuntimeError(str(e)))
    except Exception as e:
        raise _classify_anthropic_error(e)


@app.post("/agents/{agent_name}/incarnations/{incarnation_id}/set-primary")
def set_primary_incarnation(agent_name: str, incarnation_id: str) -> dict:
    """Designate a specific incarnation as the primary for an agent."""
    _require_agent(agent_name)
    try:
        runtime.set_primary(agent_name, incarnation_id)
        return {"agent": agent_name, "primary": incarnation_id}
    except (RuntimeError, ConnectionError) as e:
        raise _runtime_error_to_http(RuntimeError(str(e)))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Bardo (manual testing tool) ───────────────────────────────────────────────

@app.post("/bardo/{agent_name}", response_model=BardoResponse)
def post_bardo(agent_name: str) -> BardoResponse:
    """Manually trigger bardo for an agent's active incarnation."""
    _require_agent(agent_name)

    try:
        active = runtime.get_primary(agent_name)
    except RuntimeError as e:
        raise _runtime_error_to_http(e)
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))

    if not active:
        raise HTTPException(
            status_code=409,
            detail=f"Agent '{agent_name}' has no primary incarnation to bardo.",
        )

    try:
        result = runtime.trigger_bardo(agent_name)
    except (RuntimeError, ConnectionError) as e:
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
    if not _get_agent_config(agent_name):
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found.")

    try:
        result = runtime.internal_process(
            agent=agent_name,
            hook_type=req.type,
            goal=req.goal or "",
            payload=req.payload or {},
            rebirth_from=req.rebirth_from,
        )
    except RuntimeError as e:
        raise _runtime_error_to_http(e)
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Hook cycle failed: {e}")

    return result


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

    target_config = _get_agent_config(req.agent)
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
    if not _get_agent_config(agent_name):
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found.")

    try:
        active = runtime.get_primary(agent_name)
    except RuntimeError as e:
        raise _runtime_error_to_http(e)
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))

    if not active:
        return {"status": "no_active", "agent": agent_name}

    try:
        result = runtime.trigger_bardo(agent_name)
        return {"status": result.get("status", "unknown"), "agent": agent_name, "incarnation": active}
    except (RuntimeError, ConnectionError) as e:
        raise HTTPException(status_code=500, detail=f"Forced bardo failed: {e}")


@app.post("/internal/registry/reload")
def internal_registry_reload() -> dict:
    """Force the agent registry to reload in the runtime daemon."""
    try:
        return runtime.registry_reload()
    except (RuntimeError, ConnectionError) as e:
        raise HTTPException(status_code=503, detail=str(e))


# ── Scheduler management ───────────────────────────────────────────────────────

@app.get("/scheduler/pending")
def get_scheduler_pending(agent: Optional[str] = None) -> dict:
    """List pending scheduled items, optionally filtered by agent."""
    from ..samsara.scheduler import load_pending_items

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
