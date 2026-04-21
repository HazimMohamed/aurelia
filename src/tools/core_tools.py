"""Core tools: continue_task, memory_write, schedule_task, log_note, list_tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .registry import ToolRegistry


# ── Tool schemas ───────────────────────────────────────────────────────────────

CONTINUE_TASK_SCHEMA = {
    "name": "continue_task",
    "description": (
        "Continue to the next cycle of this incarnation. Use when you have more work "
        "to do in this same session. The infrastructure will loop and call you again "
        "with the same context."
    ),
    "input_schema": {"type": "object", "properties": {}, "required": []},
}

MEMORY_WRITE_SCHEMA = {
    "name": "memory_write",
    "description": (
        "Flag something for memory. Apply the six-month test: would this still matter "
        "in six months? Use tier: semantic_core for critical always-in-context facts. "
        "semantic_core writes are immediate (before bardo). "
        "semantic writes go to extended and are processed by bardo. "
        "Use shared_context_write instead if all agents would benefit."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "The memory content to store"},
            "importance": {
                "type": "string",
                "enum": ["low", "medium", "high"],
                "description": "Importance level of this memory",
            },
            "tier": {
                "type": "string",
                "enum": ["episodic", "semantic", "semantic_core"],
                "description": "Memory tier: episodic (this life), semantic (general), semantic_core (always loaded)",
            },
            "category": {
                "type": "string",
                "description": "Optional category tag for this memory (e.g. preferences, patterns, facts)",
            },
        },
        "required": ["content", "importance"],
    },
}

SCHEDULE_TASK_SCHEMA = {
    "name": "schedule_task",
    "description": (
        "Schedule a future fresh incarnation with a specific goal. Use when you want "
        "a genuine fresh start on a task — a new incarnation wakes up with this goal."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "goal": {"type": "string", "description": "What the future incarnation should work on"},
            "when": {
                "type": "string",
                "description": "ISO datetime or relative like '2h', '1d', '30m'",
            },
            "type": {
                "type": "string",
                "enum": ["heartbeat", "scheduled_task"],
                "description": "Hook type for the scheduled incarnation",
            },
            "recurring": {
                "type": "boolean",
                "description": "Whether to repeat this task on an interval",
                "default": False,
            },
            "interval_hours": {
                "type": "number",
                "description": "Interval in hours for recurring tasks",
            },
            "rebirth_from": {
                "type": "string",
                "description": "Incarnation name to load episodic context from (rebirth pattern)",
            },
        },
        "required": ["goal", "when"],
    },
}

LOG_NOTE_SCHEMA = {
    "name": "log_note",
    "description": "Write an explicit note to the transcript beyond automatic logging.",
    "input_schema": {
        "type": "object",
        "properties": {
            "note": {"type": "string", "description": "The note content to log"},
            "importance": {
                "type": "string",
                "enum": ["low", "medium", "high"],
                "description": "Importance level",
            },
            "category": {"type": "string", "description": "Optional category tag"},
        },
        "required": ["note"],
    },
}

LIST_TOOLS_SCHEMA = {
    "name": "list_tools",
    "description": "List all tools available in this incarnation.",
    "input_schema": {"type": "object", "properties": {}, "required": []},
}

DASHBOARD_NOTIFICATION_SCHEMA = {
    "name": "dashboard_notification",
    "description": (
        "Post to God-lite's dashboard queue. Use for non-urgent informational content: "
        "observations, briefings, findings, feedback. Not for urgent matters (use sos_alert for that)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "The notification content"},
            "category": {
                "type": "string",
                "enum": ["briefing", "alert", "observation", "find", "feedback", "curiosity"],
                "description": "Category of this notification",
            },
        },
        "required": ["content", "category"],
    },
}

SHARED_CONTEXT_WRITE_SCHEMA = {
    "name": "shared_context_write",
    "description": (
        "Share something about Hazim that ALL agents should know. "
        "Apply the council-wide test: would every agent benefit from knowing this? "
        "Examples: durable facts, current state, goals. "
        "Do NOT use for things only you need — use memory_write for those."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "type": {
                "type": "string",
                "enum": ["fact", "state", "context", "goal"],
                "description": "Type of shared context entry",
            },
            "content": {"type": "string", "description": "The shared context content"},
        },
        "required": ["type", "content"],
    },
}

SEARCH_EPISODIC_SCHEMA = {
    "name": "search_episodic",
    "description": (
        "Search your episodic memory for relevant past experiences. "
        "Keyword search across your episodic/extended/ history. "
        "Use when you want to recall specific past events or conversations."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Keywords to search for"},
            "limit": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 5)",
                "default": 5,
            },
        },
        "required": ["query"],
    },
}


# ── Handlers ───────────────────────────────────────────────────────────────────

def handle_continue_task(input_data: dict[str, Any], **ctx: Any) -> None:
    """continue_task returns None — infrastructure handles the loop."""
    return None


def handle_memory_write(input_data: dict[str, Any], **ctx: Any) -> dict[str, Any]:
    """Write a memory flag to transcript and immediately to semantic core if tier=semantic_core."""
    from datetime import datetime, timezone

    agent_config = ctx.get("agent_config")
    incarnation_state = ctx.get("incarnation_state")

    content = input_data.get("content", "")
    importance = input_data.get("importance", "medium")
    tier = input_data.get("tier", "episodic")
    category = input_data.get("category", "general") or "general"

    if not content:
        return {"error": "content is required"}

    ts = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    entry = {
        "ts": ts,
        "type": "memory_flag",
        "content": content,
        "importance": importance,
        "tier": tier,
        "category": category,
        "incarnation": incarnation_state["name"] if incarnation_state else "",
    }

    # Write memory flag to transcript
    if incarnation_state:
        from ..transcript import append_entry
        append_entry(incarnation_state["transcript_path"], entry)

    # Immediate write to semantic core if tier=semantic_core (Path 1)
    if tier == "semantic_core" and agent_config:
        try:
            from ..memory import write_semantic_core
            write_semantic_core(agent_config, entry)
            return {
                "status": "written",
                "tier": tier,
                "importance": importance,
                "message": "Written to semantic core immediately (always loaded).",
            }
        except Exception as e:
            return {
                "status": "flagged",
                "tier": tier,
                "importance": importance,
                "message": f"Flagged to transcript; semantic core write failed: {e}",
            }

    # For semantic extended — also write immediately
    if tier == "semantic" and agent_config:
        try:
            from ..memory import write_semantic_extended
            write_semantic_extended(agent_config, category, entry)
            return {
                "status": "written",
                "tier": tier,
                "importance": importance,
                "message": f"Written to semantic/extended/{category}.jsonl.",
            }
        except Exception as e:
            pass  # Bardo will catch it from transcript

    return {
        "status": "flagged",
        "tier": tier,
        "importance": importance,
        "message": f"Memory flagged for {tier} tier. Bardo will process it.",
    }


def handle_schedule_task(input_data: dict[str, Any], **ctx: Any) -> dict[str, Any]:
    """Schedule a future incarnation via the scheduler API."""
    import httpx

    agent_config = ctx.get("agent_config")
    incarnation_state = ctx.get("incarnation_state")
    api_url = ctx.get("api_url", "http://localhost:8000")

    goal = input_data.get("goal", "")
    when = input_data.get("when", "1h")
    task_type = input_data.get("type", "scheduled_task")
    recurring = input_data.get("recurring", False)
    interval_hours = input_data.get("interval_hours")
    rebirth_from = input_data.get("rebirth_from")

    if not goal:
        return {"error": "goal is required"}

    if not agent_config:
        return {"error": "no agent_config in context"}

    incarnation_name = incarnation_state["name"] if incarnation_state else "unknown"

    try:
        response = httpx.post(
            f"{api_url}/internal/schedule",
            json={
                "agent": agent_config.name,
                "goal": goal,
                "when": when,
                "type": task_type,
                "recurring": recurring,
                "interval_hours": interval_hours,
                "rebirth_from": rebirth_from,
                "created_by": incarnation_name,
            },
            headers={
                "Authorization": f"Bearer {_load_agent_token(agent_config.name)}",
            },
            timeout=30.0,
        )
        if response.status_code == 200:
            return response.json()
        return {"error": f"Scheduler returned HTTP {response.status_code}: {response.text[:200]}"}
    except Exception as e:
        return {"error": f"Failed to schedule task: {e}"}


def handle_log_note(input_data: dict[str, Any], **ctx: Any) -> dict[str, Any]:
    """Write an explicit note to the transcript."""
    from datetime import datetime, timezone
    from ..transcript import append_entry

    incarnation_state = ctx.get("incarnation_state")
    note = input_data.get("note", "")
    importance = input_data.get("importance", "medium")
    category = input_data.get("category", "")

    if not note:
        return {"error": "note is required"}

    if incarnation_state:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "type": "agent_note",
            "content": note,
            "importance": importance,
            "category": category,
        }
        append_entry(incarnation_state["transcript_path"], entry)
        return {"status": "logged", "importance": importance, "note": note[:100]}

    return {"status": "not_logged", "reason": "no incarnation state"}


def handle_list_tools(input_data: dict[str, Any], **ctx: Any) -> dict[str, Any]:
    """Return list of available tools in this incarnation."""
    tool_registry = ctx.get("tool_registry")
    if not tool_registry:
        return {"tools": [], "error": "tool_registry not in context"}

    tools = []
    for schema in tool_registry.get_schemas():
        tools.append({
            "name": schema["name"],
            "description": schema.get("description", ""),
        })
    return {"tools": tools, "count": len(tools)}


def handle_dashboard_notification(input_data: dict[str, Any], **ctx: Any) -> dict[str, Any]:
    """Write a notification to the dashboard queue."""
    import json
    from datetime import datetime, timezone
    from pathlib import Path

    agent_config = ctx.get("agent_config")
    incarnation_state = ctx.get("incarnation_state")

    content = input_data.get("content", "")
    category = input_data.get("category", "observation")

    if not content:
        return {"error": "content is required"}

    agent_name = agent_config.name if agent_config else "unknown"
    incarnation_name = incarnation_state["name"] if incarnation_state else ""

    ts = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    filename = f"{ts.replace(':', '-')}-{agent_name}-{category}.json"

    dashboard_dir = Path("/var/aurelia/dashboard/queue")
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    path = dashboard_dir / filename

    notification = {
        "ts": ts,
        "agent": agent_name,
        "incarnation": incarnation_name,
        "category": category,
        "content": content,
    }

    try:
        path.write_text(json.dumps(notification, indent=2))
        return {"status": "queued", "category": category, "file": filename}
    except OSError as e:
        return {"error": f"Failed to write notification: {e}"}


def handle_shared_context_write(input_data: dict[str, Any], **ctx: Any) -> dict[str, Any]:
    """Write to shared hazim context stack with file lock."""
    agent_config = ctx.get("agent_config")

    entry_type = input_data.get("type", "")
    content = input_data.get("content", "")

    if not entry_type:
        return {"error": "type is required"}
    if not content:
        return {"error": "content is required"}

    author = agent_config.name if agent_config else "unknown"

    try:
        from ..memory import write_shared_context
        entry = write_shared_context(
            author=author,
            entry_type=entry_type,
            content=content,
            score=0.75,  # default score for agent-written entries
        )
        return {
            "status": "written",
            "type": entry_type,
            "content": content[:100],
            "message": "Written to shared hazim context (all agents will see this).",
        }
    except Exception as e:
        return {"error": f"Failed to write shared context: {e}"}


def handle_search_episodic(input_data: dict[str, Any], **ctx: Any) -> dict[str, Any]:
    """Keyword search across episodic/extended memory."""
    agent_config = ctx.get("agent_config")

    query = input_data.get("query", "")
    limit = input_data.get("limit", 5)

    if not query:
        return {"error": "query is required"}

    if not agent_config:
        return {"error": "no agent_config in context"}

    try:
        from ..memory import search_episodic
        results = search_episodic(agent_config, query, limit=limit)

        formatted = []
        for entry in results:
            incarnation = entry.get("incarnation", "unknown")
            ts = entry.get("ts", "")
            summary_data = entry.get("summary", {})
            if isinstance(summary_data, dict):
                summary = summary_data.get("summary", "")
                topics = summary_data.get("topics", [])
            else:
                summary = str(summary_data)
                topics = []

            formatted.append({
                "incarnation": incarnation,
                "ts": ts,
                "summary": summary,
                "topics": topics,
            })

        return {
            "query": query,
            "results": formatted,
            "count": len(formatted),
        }
    except Exception as e:
        return {"error": f"Search failed: {e}"}


# ── Registration ───────────────────────────────────────────────────────────────

def register_core_tools(
    registry: ToolRegistry,
    agent_config: Any,
    incarnation_state: dict[str, Any],
    api_url: str,
) -> None:
    """Register all core tools into the registry."""
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

    registry.register(CONTINUE_TASK_SCHEMA, make_handler(handle_continue_task))
    registry.register(MEMORY_WRITE_SCHEMA, make_handler(handle_memory_write))
    registry.register(SCHEDULE_TASK_SCHEMA, make_handler(handle_schedule_task))
    registry.register(LOG_NOTE_SCHEMA, make_handler(handle_log_note))
    registry.register(LIST_TOOLS_SCHEMA, make_handler(handle_list_tools))
    registry.register(DASHBOARD_NOTIFICATION_SCHEMA, make_handler(handle_dashboard_notification))
    registry.register(SHARED_CONTEXT_WRITE_SCHEMA, make_handler(handle_shared_context_write))
    registry.register(SEARCH_EPISODIC_SCHEMA, make_handler(handle_search_episodic))


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
