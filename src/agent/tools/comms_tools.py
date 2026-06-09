"""Communication tools: invite_agent and answer_phone."""

from __future__ import annotations

import uuid
from typing import Any

from .registry import ToolRegistry


INVITE_AGENT_SCHEMA = {
    "name": "invite_agent",
    "description": (
        "Invite another agent to connect and work on a task with you. "
        "A fresh incarnation of the target agent is spawned — their primary conversation "
        "is left undisturbed. The invited agent can accept or decline via answer_phone."
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
    """Invite another agent: schedule an agent_invite hook on a fresh non-primary incarnation."""
    from ...config import AGENT_DATA_BASE
    from ...runtime.socket_client import send_runtime_request

    target_agent = input_data.get("agent", "")
    task = input_data.get("task", "")
    context = input_data.get("context", "")
    optional = input_data.get("optional", True)

    agent_config = ctx.get("agent_config")
    incarnation_state = ctx.get("incarnation_state")

    if not target_agent:
        return {"error": "agent is required"}
    if not task:
        return {"error": "task is required"}

    agent_dir = AGENT_DATA_BASE / target_agent
    if not agent_dir.exists():
        return {"error": f"Agent '{target_agent}' not found"}

    invitation_id = str(uuid.uuid4())
    from_agent = agent_config.name if agent_config else "unknown"
    incarnation_name = incarnation_state["name"] if incarnation_state else "unknown"

    try:
        send_runtime_request({
            "type": "schedule",
            "agent": target_agent,
            "goal": task,
            "schedule_type": "agent_invite",
            "trigger_time": None,
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
        })
        return {
            "status": "invited",
            "invitation_id": invitation_id,
            "target_agent": target_agent,
            "message": f"Invitation sent to {target_agent}. They will respond via answer_phone.",
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
) -> None:
    """Register communication tools into the registry."""
    ctx = {
        "agent_config": agent_config,
        "incarnation_state": incarnation_state,
    }

    def make_handler(fn):
        def handler(input_data, **extra_ctx):
            merged = {**ctx, **extra_ctx}
            return fn(input_data, **merged)
        return handler

    registry.register(INVITE_AGENT_SCHEMA, make_handler(handle_invite_agent))
    registry.register(ANSWER_PHONE_SCHEMA, make_handler(handle_answer_phone))

