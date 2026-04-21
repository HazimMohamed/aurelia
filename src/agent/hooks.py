"""Hook types and processors for Aurelia agents."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from ..samsara.config import AgentConfig


class HookType(str, Enum):
    HUMAN_MESSAGE = "human_message"
    HEARTBEAT = "heartbeat"
    SCHEDULED_TASK = "scheduled_task"
    AGENT_INVITE = "agent_invite"


BULLETIN_PATH = Path("/var/aurelia/bulletin.jsonl")
SCHEDULER_PENDING_DIR = Path("/var/aurelia/scheduler/pending")


def count_bulletin_unread(agent: AgentConfig) -> int:
    """Count unread bulletin messages for this agent."""
    if not BULLETIN_PATH.exists():
        return 0
    count = 0
    try:
        import json
        with BULLETIN_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    # Entries addressed to this agent or broadcast
                    target = entry.get("to", "all")
                    read_by = entry.get("read_by", [])
                    if target in ("all", agent.name) and agent.name not in read_by:
                        count += 1
                except (json.JSONDecodeError, KeyError):
                    pass
    except OSError:
        pass
    return count


def count_scheduled_now(agent: AgentConfig) -> int:
    """Count scheduled items that are due now for this agent."""
    if not SCHEDULER_PENDING_DIR.exists():
        return 0
    import json
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    count = 0
    try:
        for item_file in SCHEDULER_PENDING_DIR.iterdir():
            if item_file.suffix != ".json":
                continue
            try:
                with item_file.open("r", encoding="utf-8") as f:
                    item = json.load(f)
                if item.get("agent") != agent.name:
                    continue
                trigger_str = item.get("trigger_time", "")
                if trigger_str:
                    trigger = datetime.fromisoformat(
                        trigger_str.replace("Z", "+00:00")
                    )
                    if trigger <= now:
                        count += 1
            except (json.JSONDecodeError, OSError, ValueError):
                pass
    except OSError:
        pass
    return count


def heartbeat_precheck(agent: AgentConfig) -> bool:
    """
    Fast pre-check before doing a full LLM call for heartbeat.
    Returns True if there is meaningful work to do and budget available.
    """
    # Budget check — skip heartbeat if paused or below minimum threshold
    try:
        from ..memory.budget import get_budget_remaining, is_budget_ok
        if not is_budget_ok(agent):
            return False
        remaining = get_budget_remaining(agent)
        if remaining < 1_000:  # Below minimum threshold
            return False
    except Exception:
        pass  # If budget check fails, allow heartbeat to proceed

    has_unread = count_bulletin_unread(agent) > 0
    has_scheduled = count_scheduled_now(agent) > 0
    has_budget = get_budget_remaining(agent) > 1_000
    return has_unread or has_scheduled or has_budget


def format_heartbeat_prompt(agent: AgentConfig) -> str:
    """Build the heartbeat prompt text for the agent."""
    unread = count_bulletin_unread(agent)
    scheduled = count_scheduled_now(agent)

    parts = [
        "## Heartbeat",
        "",
        "You have woken up on a scheduled heartbeat. This is your time to think, reflect, explore, or work.",
        "",
    ]
    if unread > 0:
        parts.append(f"- You have {unread} unread bulletin message(s) to review.")
    if scheduled > 0:
        parts.append(f"- You have {scheduled} scheduled item(s) that are now due.")
    if unread == 0 and scheduled == 0:
        parts.append("- No specific items pending. Use this time as you see fit.")

    parts += [
        "",
        'When you are done, end with: {"next": {"type": "done"}}',
    ]
    return "\n".join(parts)


def format_task_goal(payload: dict[str, Any]) -> str:
    """Build the task goal prompt for a scheduled_task hook."""
    goal = payload.get("goal", "No specific goal provided.")
    task_type = payload.get("type", "scheduled_task")
    parts = [
        "## Scheduled Task",
        "",
        f"You have been woken up to work on the following goal:",
        "",
        f"**Goal:** {goal}",
        "",
        f"**Task type:** {task_type}",
        "",
        'When you are done, end with: {"next": {"type": "done"}}',
    ]
    return "\n".join(parts)


def format_agent_invite(payload: dict[str, Any]) -> str:
    """Build the invitation prompt for an agent_invite hook."""
    from_agent = payload.get("from_agent", "unknown")
    task = payload.get("task", "No task specified.")
    context = payload.get("context", "")
    invitation_id = payload.get("invitation_id", "")

    parts = [
        "## Agent Invitation",
        "",
        f"You have received an invitation from agent **{from_agent}**.",
        "",
        f"**Task they want help with:** {task}",
    ]
    if context:
        parts += ["", f"**Context:** {context}"]
    parts += [
        "",
        f"**Invitation ID:** {invitation_id}",
        "",
        "Use the `answer_phone` tool to accept or decline this invitation.",
    ]
    return "\n".join(parts)
