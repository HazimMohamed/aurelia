"""Agent-specific tools: mayor and janitor stubs."""

from __future__ import annotations

from typing import Any

from tools.registry import ToolRegistry


# ── Mayor tools ────────────────────────────────────────────────────────────────

MAYOR_WRITE_UP_SCHEMA = {
    "name": "mayor_write_up",
    "description": (
        "Write a council observation report for God-lite's weekly summary. "
        "Use when you have observed something significant about agent behavior."
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
        "False positives are explicitly welcome."
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
        "Flag a constitution as potentially producing bad behavior. "
        "God-lite decides what to do. Janitor implements changes."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "agent": {"type": "string", "description": "Which agent's constitution to flag"},
            "reason": {"type": "string", "description": "Why you think it needs review"},
            "evidence": {"type": "string", "description": "Specific examples of problematic behavior"},
        },
        "required": ["agent", "reason"],
    },
}


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
        "Janitor-only. Use with care."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Dot-separated config path (e.g. 'agents.cooking.model')",
            },
            "value": {"description": "New value to set"},
        },
        "required": ["path", "value"],
    },
}


# ── Stub handlers ──────────────────────────────────────────────────────────────

def _stub_handler(tool_name: str):
    def handler(input_data: dict[str, Any], **ctx: Any) -> dict[str, Any]:
        return {
            "status": "not_implemented",
            "tool": tool_name,
            "message": f"Tool '{tool_name}' is a stub in M2. Full implementation in a future milestone.",
        }
    return handler


def handle_registry_reload(input_data: dict[str, Any], **ctx: Any) -> dict[str, Any]:
    """Reload the agent registry. Janitor-only."""
    api_url = ctx.get("api_url", "http://localhost:8000")
    try:
        import httpx
        response = httpx.post(f"{api_url}/internal/registry/reload", timeout=10.0)
        if response.status_code == 200:
            return {"status": "reloaded", "message": "Agent registry reloaded."}
        return {"error": f"Registry reload failed: HTTP {response.status_code}"}
    except Exception as e:
        return {"error": f"Registry reload failed: {e}"}


def register_agent_tools(registry: ToolRegistry, agent_name: str) -> None:
    """Register agent-specific tools based on agent name."""
    if agent_name == "mayor":
        registry.register(MAYOR_WRITE_UP_SCHEMA, _stub_handler("mayor_write_up"))
        registry.register(SOS_ALERT_SCHEMA, _stub_handler("sos_alert"))
        registry.register(CONSTITUTION_FLAG_SCHEMA, _stub_handler("constitution_flag"))

    elif agent_name == "janitor":
        registry.register(REGISTRY_RELOAD_SCHEMA, handle_registry_reload)
        registry.register(CONFIG_UPDATE_SCHEMA, _stub_handler("config_update"))
