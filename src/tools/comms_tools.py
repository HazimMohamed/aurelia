"""Communication tools: invite_agent and answer_phone."""

from __future__ import annotations

import uuid
from typing import Any

from .registry import ToolRegistry


INVITE_AGENT_SCHEMA = {
    "name": "invite_agent",
    "description": (
        "Invite another agent to connect and work on a task with you. "
        "This triggers a forced bardo on their active incarnation first, then "
        "sends them an invitation as a scheduled task. The other agent will wake up "
        "and can accept or decline via answer_phone."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "agent": {"type": "string", "description": "Name of the agent to invite"},
            "task": {"type": "string", "description": "What you want help with"},
            "context": {
                "type": "string",
                "description": "Additional context to share with the invited agent",
            },
            "optional": {
                "type": "boolean",
                "description": "Whether the invitation is optional (default: true)",
                "default": True,
            },
        },
        "required": ["agent", "task"],
    },
}

ANSWER_PHONE_SCHEMA = {
    "name": "answer_phone",
    "description": (
        "Accept or decline an agent invitation. Use this when you have been woken up "
        "via an agent_invite hook."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "invitation_id": {
                "type": "string",
                "description": "The invitation ID from the agent_invite hook",
            },
            "accept": {"type": "boolean", "description": "Whether to accept the invitation"},
            "message": {
                "type": "string",
                "description": "Optional message to send back to the inviting agent",
            },
        },
        "required": ["invitation_id", "accept"],
    },
}


def handle_invite_agent(input_data: dict[str, Any], **ctx: Any) -> dict[str, Any]:
    """Invite another agent: trigger forced bardo, then write invitation to their queue."""
    import json
    import httpx
    from pathlib import Path
    from ..config import AGENT_HOME_BASE

    target_agent = input_data.get("agent", "")
    task = input_data.get("task", "")
    context = input_data.get("context", "")
    optional = input_data.get("optional", True)

    agent_config = ctx.get("agent_config")
    incarnation_state = ctx.get("incarnation_state")
    api_url = ctx.get("api_url", "http://localhost:8000")

    if not target_agent:
        return {"error": "agent is required"}
    if not task:
        return {"error": "task is required"}

    # Lazy FS read: verify agent exists
    agent_dir = AGENT_HOME_BASE / target_agent
    if not agent_dir.exists() or not (agent_dir / "agent.json").exists():
        return {"error": f"Agent '{target_agent}' not found in {AGENT_HOME_BASE}"}

    invitation_id = str(uuid.uuid4())
    from_agent = agent_config.name if agent_config else "unknown"
    incarnation_name = incarnation_state["name"] if incarnation_state else "unknown"

    # Step 1: Trigger forced bardo on target's active incarnation
    try:
        bardo_response = httpx.post(
            f"{api_url}/internal/bardo/{target_agent}",
            json={"reason": "agent_invite", "forced": True},
            timeout=60.0,
        )
        # Bardo failure is non-fatal — agent might not have an active incarnation
        if bardo_response.status_code not in (200, 404, 409):
            print(f"[invite_agent] Bardo warning for {target_agent}: {bardo_response.status_code}")
    except Exception as e:
        print(f"[invite_agent] Bardo attempt failed for {target_agent}: {e}")

    # Step 2: Schedule the invitation as an agent_invite task
    try:
        schedule_response = httpx.post(
            f"{api_url}/internal/schedule",
            json={
                "agent": target_agent,
                "goal": task,
                "when": "now",
                "type": "agent_invite",
                "recurring": False,
                "created_by": incarnation_name,
                "payload": {
                    "invitation_id": invitation_id,
                    "from_agent": from_agent,
                    "from_incarnation": incarnation_name,
                    "task": task,
                    "context": context,
                    "optional": optional,
                },
            },
            headers={
                "Authorization": f"Bearer {_load_agent_token(from_agent)}",
            },
            timeout=30.0,
        )

        if schedule_response.status_code == 200:
            return {
                "status": "invited",
                "invitation_id": invitation_id,
                "target_agent": target_agent,
                "message": f"Invitation sent to {target_agent}. They will respond via answer_phone.",
            }
        return {
            "error": f"Failed to schedule invitation: HTTP {schedule_response.status_code}",
            "invitation_id": invitation_id,
        }
    except Exception as e:
        return {"error": f"Failed to send invitation: {e}", "invitation_id": invitation_id}


def handle_answer_phone(input_data: dict[str, Any], **ctx: Any) -> dict[str, Any]:
    """Accept or decline an agent invitation."""
    from datetime import datetime, timezone

    invitation_id = input_data.get("invitation_id", "")
    accept = input_data.get("accept", False)
    message = input_data.get("message", "")

    agent_config = ctx.get("agent_config")
    incarnation_state = ctx.get("incarnation_state")
    api_url = ctx.get("api_url", "http://localhost:8000")

    if not invitation_id:
        return {"error": "invitation_id is required"}

    agent_name = agent_config.name if agent_config else "unknown"
    status = "accepted" if accept else "declined"

    # Log the response to transcript
    if incarnation_state:
        from ..transcript import append_entry
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "type": "invitation_response",
            "invitation_id": invitation_id,
            "status": status,
            "message": message,
        }
        append_entry(incarnation_state["transcript_path"], entry)

    return {
        "status": status,
        "invitation_id": invitation_id,
        "message": message or f"Invitation {status} by {agent_name}.",
    }


def register_comms_tools(
    registry: ToolRegistry,
    agent_config: Any,
    incarnation_state: dict[str, Any],
    api_url: str,
) -> None:
    """Register communication tools into the registry."""
    ctx = {
        "agent_config": agent_config,
        "incarnation_state": incarnation_state,
        "api_url": api_url,
    }

    def make_handler(fn):
        def handler(input_data, **extra_ctx):
            merged = {**ctx, **extra_ctx}
            return fn(input_data, **merged)
        return handler

    registry.register(INVITE_AGENT_SCHEMA, make_handler(handle_invite_agent))
    registry.register(ANSWER_PHONE_SCHEMA, make_handler(handle_answer_phone))


def _load_agent_token(agent_name: str) -> str:
    """Load the agent's bearer token for API auth."""
    import json
    from ..config import GLOBAL_CONFIG_PATH

    try:
        if GLOBAL_CONFIG_PATH.exists():
            with GLOBAL_CONFIG_PATH.open() as f:
                cfg = json.load(f)
            agents_cfg = cfg.get("agents", {})
            agent_cfg = agents_cfg.get(agent_name, {})
            return agent_cfg.get("token", "")
    except (json.JSONDecodeError, OSError):
        pass
    return ""
