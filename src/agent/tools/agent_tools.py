"""Agent-specific tools: mayor tools and janitor tools."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .registry import ToolRegistry

DASHBOARD_QUEUE_DIR = Path("/var/aurelia/dashboard/queue")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _write_dashboard_entry(
    agent_name: str,
    incarnation_name: str,
    category: str,
    payload: dict[str, Any],
) -> str:
    """Write a dashboard notification to queue directory."""
    DASHBOARD_QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    ts = _now_iso()
    filename = f"{ts.replace(':', '-')}-{agent_name}-{category}.json"
    path = DASHBOARD_QUEUE_DIR / filename

    entry = {
        "ts": ts,
        "agent": agent_name,
        "incarnation": incarnation_name,
        "category": category,
        **payload,
    }

    path.write_text(json.dumps(entry, indent=2))
    return filename


# ── Mayor tools ────────────────────────────────────────────────────────────────

MAYOR_WRITE_UP_SCHEMA = {
    "name": "mayor_write_up",
    "description": (
        "Write a council observation report for God-lite's weekly summary. "
        "Use when you have observed something significant about agent behavior or system health."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "subject": {"type": "string", "description": "Which agent or situation is being observed"},
            "observation": {"type": "string", "description": "What you observed"},
            "severity": {
                "type": "string",
                "enum": ["info", "concern", "urgent"],
                "description": "Severity level",
            },
        },
        "required": ["subject", "observation"],
    },
}

SOS_ALERT_SCHEMA = {
    "name": "sos_alert",
    "description": (
        "Send an urgent SOS alert to God-lite. Use for genuine emergencies only. "
        "False positives are explicitly welcome — it is better to over-alert than miss something real."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "The emergency message"},
            "agent_involved": {
                "type": "string",
                "description": "Which agent is involved (if any)",
            },
        },
        "required": ["message"],
    },
}

CONSTITUTION_FLAG_SCHEMA = {
    "name": "constitution_flag",
    "description": (
        "Flag an agent's constitution as potentially producing bad behavior. "
        "You observe and flag. Hazim decides. Janitor implements. "
        "Use with care — this is a governance signal."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "agent": {"type": "string", "description": "Which agent's constitution to flag"},
            "observation": {"type": "string", "description": "What behavior you observed"},
            "evidence": {"type": "string", "description": "Specific examples"},
            "suggested_direction": {
                "type": "string",
                "description": "Optional: what you think should change",
            },
        },
        "required": ["agent", "observation"],
    },
}


def handle_mayor_write_up(input_data: dict[str, Any], **ctx: Any) -> dict[str, Any]:
    """Write a mayor observation to the dashboard queue."""
    agent_config = ctx.get("agent_config")
    incarnation_state = ctx.get("incarnation_state")

    subject = input_data.get("subject", "")
    observation = input_data.get("observation", "")
    severity = input_data.get("severity", "info")

    if not subject or not observation:
        return {"error": "subject and observation are required"}

    agent_name = agent_config.name if agent_config else "mayor"
    incarnation_name = incarnation_state["name"] if incarnation_state else ""

    try:
        filename = _write_dashboard_entry(
            agent_name=agent_name,
            incarnation_name=incarnation_name,
            category="mayor_summary",
            payload={
                "subject": subject,
                "observation": observation,
                "severity": severity,
            },
        )
        return {
            "status": "written",
            "category": "mayor_summary",
            "severity": severity,
            "subject": subject,
            "file": filename,
        }
    except Exception as e:
        return {"error": f"Failed to write mayor write-up: {e}"}


def handle_sos_alert(input_data: dict[str, Any], **ctx: Any) -> dict[str, Any]:
    """Send SOS alert — write to dashboard queue AND log to stderr."""
    agent_config = ctx.get("agent_config")
    incarnation_state = ctx.get("incarnation_state")

    message = input_data.get("message", "")
    agent_involved = input_data.get("agent_involved", "")

    if not message:
        return {"error": "message is required"}

    agent_name = agent_config.name if agent_config else "mayor"
    incarnation_name = incarnation_state["name"] if incarnation_state else ""

    # Log to stderr immediately (urgent)
    print(
        f"[SOS] From {agent_name}/{incarnation_name}: {message}"
        + (f" (agent: {agent_involved})" if agent_involved else ""),
        file=sys.stderr,
        flush=True,
    )

    try:
        filename = _write_dashboard_entry(
            agent_name=agent_name,
            incarnation_name=incarnation_name,
            category="sos",
            payload={
                "message": message,
                "agent_involved": agent_involved,
                "urgent": True,
            },
        )
        return {
            "status": "sent",
            "category": "sos",
            "message": message[:100],
            "file": filename,
        }
    except Exception as e:
        return {"error": f"SOS write failed: {e}", "stderr_logged": True}


def handle_constitution_flag(input_data: dict[str, Any], **ctx: Any) -> dict[str, Any]:
    """Flag a constitution concern to the dashboard queue."""
    agent_config = ctx.get("agent_config")
    incarnation_state = ctx.get("incarnation_state")

    agent = input_data.get("agent", "")
    observation = input_data.get("observation", "")
    evidence = input_data.get("evidence", "")
    suggested_direction = input_data.get("suggested_direction", "")

    if not agent or not observation:
        return {"error": "agent and observation are required"}

    author_name = agent_config.name if agent_config else "mayor"
    incarnation_name = incarnation_state["name"] if incarnation_state else ""

    try:
        filename = _write_dashboard_entry(
            agent_name=author_name,
            incarnation_name=incarnation_name,
            category="constitution_flag",
            payload={
                "flagged_agent": agent,
                "observation": observation,
                "evidence": evidence,
                "suggested_direction": suggested_direction,
            },
        )
        return {
            "status": "flagged",
            "category": "constitution_flag",
            "flagged_agent": agent,
            "file": filename,
        }
    except Exception as e:
        return {"error": f"Failed to write constitution flag: {e}"}


# ── Janitor tools ──────────────────────────────────────────────────────────────

REGISTRY_RELOAD_SCHEMA = {
    "name": "registry_reload",
    "description": "Force the agent registry to reload from filesystem. Janitor-only.",
    "input_schema": {"type": "object", "properties": {}, "required": []},
}

CONFIG_UPDATE_SCHEMA = {
    "name": "config_update",
    "description": (
        "Update a configuration value in /var/aurelia/config.json. "
        "Janitor-only. Use with care. Every write is logged."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Dot-separated config path (e.g. 'agents.cooking.model')",
            },
            "value": {"description": "New value to set"},
            "reason": {"type": "string", "description": "Why this change is being made (required)"},
        },
        "required": ["path", "value", "reason"],
    },
}


def handle_registry_reload(input_data: dict[str, Any], **ctx: Any) -> dict[str, Any]:
    """Reload the agent registry. Janitor-only."""
    from ...runtime.socket_client import send_runtime_request
    try:
        return send_runtime_request({"type": "registry_reload"})
    except Exception as e:
        return {"error": f"Registry reload failed: {e}"}


def handle_config_update(input_data: dict[str, Any], **ctx: Any) -> dict[str, Any]:
    """Update config.json at a dot-separated path. Janitor-only. Logged."""
    from ...config import GLOBAL_CONFIG_PATH

    agent_config = ctx.get("agent_config")
    incarnation_state = ctx.get("incarnation_state")

    config_path = input_data.get("path", "")
    value = input_data.get("value")
    reason = input_data.get("reason", "")

    if not config_path:
        return {"error": "path is required"}
    if not reason:
        return {"error": "reason is required (every janitor write must be justified)"}

    agent_name = agent_config.name if agent_config else "janitor"
    incarnation_name = incarnation_state["name"] if incarnation_state else ""

    # Log the action
    print(
        f"[janitor] config_update by {incarnation_name}: "
        f"path={config_path}, reason={reason}",
        file=sys.stderr,
    )

    if not GLOBAL_CONFIG_PATH.exists():
        return {"error": "Global config not found"}

    try:
        with GLOBAL_CONFIG_PATH.open("r") as f:
            config = json.load(f)

        # Navigate to the target path
        parts = config_path.split(".")
        target = config
        for part in parts[:-1]:
            if part not in target:
                target[part] = {}
            target = target[part]

        old_value = target.get(parts[-1])
        target[parts[-1]] = value

        with GLOBAL_CONFIG_PATH.open("w") as f:
            json.dump(config, f, indent=2)

        return {
            "status": "updated",
            "path": config_path,
            "old_value": old_value,
            "new_value": value,
            "reason": reason,
        }
    except Exception as e:
        return {"error": f"Config update failed: {e}"}


def register_agent_tools(
    registry: ToolRegistry,
    agent_name: str,
    agent_config: Any = None,
    incarnation_state: dict[str, Any] = None,
) -> None:
    """Register agent-specific tools based on agent name."""
    ctx = {
        "agent_config": agent_config,
        "incarnation_state": incarnation_state,
    }

    def make_handler(fn):
        def handler(input_data, **extra_ctx):
            merged = {**ctx, **extra_ctx}
            return fn(input_data, **merged)
        return handler

    if agent_name == "mayor":
        registry.register(MAYOR_WRITE_UP_SCHEMA, make_handler(handle_mayor_write_up))
        registry.register(SOS_ALERT_SCHEMA, make_handler(handle_sos_alert))
        registry.register(CONSTITUTION_FLAG_SCHEMA, make_handler(handle_constitution_flag))

    elif agent_name == "janitor":
        registry.register(REGISTRY_RELOAD_SCHEMA, make_handler(handle_registry_reload))
        registry.register(CONFIG_UPDATE_SCHEMA, make_handler(handle_config_update))
