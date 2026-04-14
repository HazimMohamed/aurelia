"""Aurelia Milestone 1 — FastAPI server."""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Optional

# Load .env from project root if present (dev convenience)
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_path)

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, model_validator

from registry import AgentRegistry
from incarnation import get_or_spawn_incarnation, get_incarnation_by_id
from core import run_agent_cycle
from bardo import run_bardo

app = FastAPI(title="Aurelia", version="0.1.0")

# Global registry — initialized once on startup
registry = AgentRegistry()


# ── Request/Response models ────────────────────────────────────────────────────

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
        # Allow "from" key (Python reserved word) mapped to from_
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


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.post("/message", response_model=MessageResponse)
def post_message(req: MessageRequest) -> MessageResponse:
    """Send a message to an agent and receive a response."""
    agent_name = req.to.agent
    if not agent_name:
        raise HTTPException(status_code=400, detail="'to.agent' is required")

    config = registry.get(agent_name)
    if not config:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_name}' not found. Run scripts/setup_agent.sh to create it.",
        )

    # Route to specific incarnation or active/new one
    if req.to.incarnation_id:
        try:
            incarnation_state = get_incarnation_by_id(config, req.to.incarnation_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
    else:
        incarnation_state = get_or_spawn_incarnation(config)

    sender = req.from_ or "god-lite"

    try:
        response_text = run_agent_cycle(config, incarnation_state, req.content, sender=sender)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent cycle failed: {e}")

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
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_name}' not found.",
        )

    from incarnation import get_active_incarnation
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
    """Return health status for all known agents."""
    agents = {}
    for agent_name in registry.all_agents():
        agents[agent_name] = registry.agent_status(agent_name)

    return {
        "status": "healthy",
        "agents": agents,
    }


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
