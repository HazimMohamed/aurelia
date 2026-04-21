"""Context assembly for agent LLM calls — supports all hook types."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import AgentConfig
from .transcript import transcript_to_messages


def _read_file_safe(path: Path) -> str:
    """Read a file, returning empty string if missing."""
    if path.exists():
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError:
            return ""
    return ""


def build_system_prompt(config: AgentConfig, hook_content: str = "") -> str:
    """
    Build full system prompt:
    constitution + identity + semantic core + episodic core +
    hazim introduction + shared hazim context + room mention.
    """
    from .memory import (
        load_semantic_core,
        load_episodic_core,
        load_hazim_introduction,
        load_shared_hazim_context,
    )

    parts = []

    # 1. Constitution (dharma)
    constitution = _read_file_safe(config.constitution_path)
    if constitution:
        parts.append(constitution)

    # 2. Identity files (character.md, contract.md, values.md)
    if config.identity_dir.exists():
        for identity_file in sorted(config.identity_dir.iterdir()):
            if identity_file.suffix == ".md":
                content = _read_file_safe(identity_file)
                if content:
                    parts.append(f"## {identity_file.stem.capitalize()}\n{content}")

    # 3. Semantic core — always loaded, size-capped ~500 tokens
    semantic_core = load_semantic_core(config)
    if semantic_core:
        parts.append(semantic_core)

    # 4. Episodic core — formative experiences, always loaded
    episodic_core = load_episodic_core(config)
    if episodic_core:
        parts.append(episodic_core)

    # 5. Hazim introduction
    hazim_intro = load_hazim_introduction()
    if hazim_intro:
        parts.append(f"## About Hazim (God-lite)\n{hazim_intro}")

    # 6. Shared hazim context — top scored entries
    shared_context = load_shared_hazim_context()
    if shared_context:
        parts.append(shared_context)

    # 7. Room mention — permanent space
    room_dir = config.room_dir
    parts.append(
        f"## Your Room\n"
        f"Your permanent space is at `{room_dir}/`. "
        f"Things you put there persist across all incarnations. "
        f"Your scratch folder is at `{config.karma_dir}/current/scratch/` — "
        f"private workspace for this incarnation, archived to Akashic after bardo."
    )

    return "\n\n---\n\n".join(parts) if parts else "You are a helpful AI agent."


def build_messages(
    incarnation_entries: list[dict[str, Any]],
    new_human_message: str,
) -> list[dict[str, str]]:
    """Build Anthropic messages array from transcript history + new message (human_message hook)."""
    messages = transcript_to_messages(incarnation_entries)
    messages.append({"role": "user", "content": new_human_message})
    return messages


def build_hook_messages(
    config: AgentConfig,
    incarnation_entries: list[dict[str, Any]],
    new_human_message: str,
    hook_type: str,
) -> list[dict[str, Any]]:
    """Build messages array appropriate for the given hook type."""
    from .hooks import HookType
    from .memory import load_episodic_extended_relevant, load_semantic_extended_relevant

    if hook_type == HookType.HUMAN_MESSAGE:
        # Standard conversation: history + relevant extended memory + new message
        messages = transcript_to_messages(incarnation_entries)

        # Inject relevant extended memory as a system-like user context block
        memory_context_parts = []

        episodic_relevant = load_episodic_extended_relevant(config, new_human_message)
        if episodic_relevant:
            memory_context_parts.append(episodic_relevant)

        semantic_relevant = load_semantic_extended_relevant(config, new_human_message)
        if semantic_relevant:
            memory_context_parts.append(semantic_relevant)

        if memory_context_parts and not messages:
            # Prepend memory context before the user message
            memory_block = "\n\n".join(memory_context_parts)
            full_message = f"{memory_block}\n\n---\n\n{new_human_message}"
            messages.append({"role": "user", "content": full_message})
        elif memory_context_parts and messages:
            # Inject memory context as a user message before conversation history
            memory_block = "\n\n".join(memory_context_parts)
            messages = [{"role": "user", "content": f"[Context from memory]\n{memory_block}"},
                        {"role": "assistant", "content": "I have reviewed the relevant memory context."}] + messages
            messages.append({"role": "user", "content": new_human_message})
        else:
            messages.append({"role": "user", "content": new_human_message})

        return messages

    elif hook_type in (HookType.HEARTBEAT, HookType.SCHEDULED_TASK, HookType.AGENT_INVITE):
        # Autonomous hooks: fresh context, hook prompt is the full message
        return [{"role": "user", "content": new_human_message}]

    else:
        # Fallback: treat as human message without memory injection
        messages = transcript_to_messages(incarnation_entries)
        messages.append({"role": "user", "content": new_human_message})
        return messages


# ── Episodic summary helpers (kept for backward compat) ─────────────────────

def load_recent_episodic_summary(config: AgentConfig, max_entries: int = 3) -> str:
    """Load recent episodic summaries for heartbeat context."""
    episodic_dir = config.episodic_extended_dir
    if not episodic_dir.exists():
        return ""

    entries = []
    for ep_file in sorted(episodic_dir.iterdir(), reverse=True):
        if ep_file.suffix != ".jsonl":
            continue
        with ep_file.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        if len(entries) >= max_entries:
            break

    if not entries:
        return ""

    parts = ["## Recent Episodic Memory\n"]
    for entry in entries[:max_entries]:
        incarnation = entry.get("incarnation", "unknown")
        summary_data = entry.get("summary", {})
        if isinstance(summary_data, dict):
            summary = summary_data.get("summary", "")
        else:
            summary = str(summary_data)
        if summary:
            parts.append(f"**{incarnation}:** {summary}")

    return "\n\n".join(parts)


def load_episodic_extended(config: AgentConfig, incarnation_name: str) -> str:
    """Load the episodic summary for a specific incarnation (for rebirth_from)."""
    ep_file = config.episodic_extended_dir / f"{incarnation_name}.jsonl"
    if not ep_file.exists():
        return ""

    entries = []
    with ep_file.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    if not entries:
        return ""

    entry = entries[-1]
    summary_data = entry.get("summary", {})
    if isinstance(summary_data, dict):
        summary = summary_data.get("summary", "")
        topics = summary_data.get("topics", [])
        insights = summary_data.get("insights", [])
    else:
        summary = str(summary_data)
        topics = []
        insights = []

    parts = [f"## Episodic Context from {incarnation_name}\n", summary]
    if topics:
        parts.append(f"\n**Topics:** {', '.join(topics)}")
    if insights:
        parts.append("\n**Insights:**")
        for insight in insights:
            parts.append(f"  - {insight}")

    return "\n".join(parts)
