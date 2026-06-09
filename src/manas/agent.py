"""Manas agent layer — all execution logic for a single agent.

Called by Manas socket handlers. Never imports from runtime_core.
Calls src/agent/* and src/memory/* directly.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

from ..config import AgentConfig
from ..runtime.types import AgentResponse, IncarnationSummary, TranscriptEntry
from ..agent.core import StreamCallback, run_agent_cycle
from ..agent.hooks import HookType
from ..agent.incarnation import (
    get_or_spawn_incarnation,
    get_primary_incarnation,
    load_incarnation,
    set_primary_incarnation,
    spawn_incarnation,
)
from ..agent.transcript import read_entries
from ..memory.bardo import run_bardo


# ── Core operations ────────────────────────────────────────────────────────────


def spawn(
    config: AgentConfig,
    goal: Optional[str] = None,
    make_primary: Optional[bool] = None,
) -> IncarnationSummary:
    if make_primary is None:
        make_primary = get_primary_incarnation(config) is None
    name = spawn_incarnation(config, make_primary=make_primary)
    state = load_incarnation(config, name)
    status = "primary" if make_primary else "active"
    return IncarnationSummary(name=name, agent=config.name, status=status, cycle=state["cycle"])


def dispatch(
    config: AgentConfig,
    incarnation: str,
    hook: HookType,
    payload: dict[str, Any],
    stream_callback: Optional[StreamCallback] = None,
) -> AgentResponse:
    from ..agent.tools.registry import build_tool_registry

    incarnation_path = config.memory_dir / incarnation
    if not incarnation_path.exists():
        raise ValueError(f"Incarnation '{incarnation}' not found for agent '{config.name}'")

    incarnation_state = load_incarnation(config, incarnation)
    tool_registry = build_tool_registry(
        hook_type=hook,
        agent_name=config.name,
        agent_config=config,
        incarnation_state=incarnation_state,
    )
    response_text = run_agent_cycle(
        config=config,
        incarnation_state=incarnation_state,
        human_content=payload.get("content", ""),
        sender=payload.get("sender", "god-lite"),
        hook_type=hook,
        tool_registry=tool_registry,
        stream_callback=stream_callback,
    )
    return AgentResponse(
        agent=config.name,
        incarnation=incarnation_state["name"],
        cycle=incarnation_state["cycle"],
        content=response_text,
    )


def get_history(config: AgentConfig, incarnation: str) -> list[TranscriptEntry]:
    active_transcript = config.memory_dir / incarnation / "transcript.jsonl"
    akasha_transcript = config.akasha_dir / incarnation / f"{incarnation}-transcript.jsonl"

    if active_transcript.exists():
        transcript_path = active_transcript
    elif akasha_transcript.exists():
        transcript_path = akasha_transcript
    else:
        raise ValueError(f"Incarnation '{incarnation}' not found for agent '{config.name}'")

    raw_entries = read_entries(transcript_path)
    result = []
    for e in raw_entries:
        known_keys = {"ts", "type", "content", "cycle"}
        extra = {k: v for k, v in e.items() if k not in known_keys}
        result.append(TranscriptEntry(
            ts=e.get("ts", ""),
            type=e.get("type", ""),
            content=e.get("content"),
            cycle=e.get("cycle"),
            extra=extra,
        ))
    return result


def list_incarnations(config: AgentConfig) -> list[IncarnationSummary]:
    summaries: list[IncarnationSummary] = []
    primary_name = get_primary_incarnation(config)

    if config.memory_dir.exists():
        for entry in config.memory_dir.iterdir():
            if entry.name in ("primary", "extended"):
                continue
            if not entry.is_dir():
                continue
            entries = read_entries(entry / "transcript.jsonl")
            cycle = sum(1 for e in entries if e.get("type") == "human_message")
            status = "primary" if entry.name == primary_name else "active"
            summaries.append(IncarnationSummary(
                name=entry.name, agent=config.name, status=status,
                cycle=cycle, last_active=_last_ts(entries),
            ))

    if config.akasha_dir.exists():
        for entry in config.akasha_dir.iterdir():
            if not entry.is_dir():
                continue
            entries = read_entries(entry / f"{entry.name}-transcript.jsonl")
            cycle = sum(1 for e in entries if e.get("type") == "human_message")
            summaries.append(IncarnationSummary(
                name=entry.name, agent=config.name, status="dissolved",
                cycle=cycle, last_active=_last_ts(entries),
            ))

    summaries.sort(key=lambda s: s.last_active or "", reverse=True)
    return summaries


def get_primary(config: AgentConfig) -> Optional[str]:
    return get_primary_incarnation(config)


def set_primary(config: AgentConfig, name: str) -> None:
    set_primary_incarnation(config, name)


def trigger_bardo(config: AgentConfig, incarnation: str) -> dict:
    return run_bardo(config, incarnation)


# ── Hook processing ────────────────────────────────────────────────────────────


def spawn_fresh_for_hook(config: AgentConfig, hook_type: str) -> dict:
    if hook_type == HookType.AGENT_INVITE:
        name = spawn_incarnation(config, make_primary=False)
        return load_incarnation(config, name)
    return get_or_spawn_incarnation(config)


def run_hook(
    config: AgentConfig,
    hook_type: str,
    hook_prompt: str,
    incarnation_state: dict,
) -> str:
    from ..agent.tools.registry import build_tool_registry

    tool_registry = build_tool_registry(
        hook_type=hook_type,
        agent_name=config.name,
        agent_config=config,
        incarnation_state=incarnation_state,
    )
    return run_agent_cycle(
        config=config,
        incarnation_state=incarnation_state,
        human_content=hook_prompt,
        sender="scheduler",
        hook_type=hook_type,
        tool_registry=tool_registry,
    )


def build_hook_prompt(
    config: AgentConfig,
    hook_type: str,
    goal: str,
    payload: dict,
    rebirth_from: Optional[str] = None,
) -> str:
    from ..agent.context import load_episodic_extended, load_recent_episodic_summary
    from ..agent.hooks import (
        HookType,
        format_agent_invite,
        format_heartbeat_prompt,
        format_task_goal,
    )

    if hook_type == HookType.HEARTBEAT:
        parts = []
        episodic_context = load_recent_episodic_summary(config)
        if episodic_context:
            parts.append(episodic_context)
        parts.append(format_heartbeat_prompt(config))
        return "\n\n".join(parts)

    if hook_type == HookType.SCHEDULED_TASK:
        parts = []
        if rebirth_from:
            rebirth_context = load_episodic_extended(config, rebirth_from)
            if rebirth_context:
                parts.append(rebirth_context)
        parts.append(format_task_goal({"goal": goal, "type": hook_type, **payload}))
        return "\n\n".join(parts)

    if hook_type == "agent_invite":
        return format_agent_invite(payload)

    return goal or "You have been woken up. Do your work."


def process_hook(
    config: AgentConfig,
    hook_type: str,
    goal: str,
    payload: dict,
    rebirth_from: Optional[str] = None,
) -> dict:
    from ..agent.hooks import HookType, heartbeat_precheck

    if hook_type == HookType.HEARTBEAT and not heartbeat_precheck(config):
        return {"status": "skipped", "reason": "heartbeat_precheck_false", "agent": config.name}

    hook_prompt = build_hook_prompt(config, hook_type, goal, payload, rebirth_from)
    incarnation_state = spawn_fresh_for_hook(config, hook_type)
    run_hook(config, hook_type, hook_prompt, incarnation_state)

    return {
        "status": "ok",
        "agent": config.name,
        "incarnation": incarnation_state["name"],
        "hook": hook_type,
    }


# ── Budget ─────────────────────────────────────────────────────────────────────


def reset_budget(config: AgentConfig) -> dict:
    from ..agent.budget import _fresh_budget, load_budget, save_budget

    existing = load_budget(config.data_dir)
    save_budget(config.data_dir, _fresh_budget(
        weekly_budget=existing.get("weekly_budget", 300_000),
        heartbeat_weekly_budget=existing.get("heartbeat_weekly_budget", 100_000),
    ))
    return {"status": "ok", "agent": config.name}


# ── Internal helpers ───────────────────────────────────────────────────────────


def _last_ts(entries: list[dict]) -> Optional[str]:
    for entry in reversed(entries):
        ts = entry.get("ts")
        if ts:
            return ts
    return None
