"""Context assembly for agent LLM calls — supports all hook types."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..config import AgentConfig, CONSTITUTION_DIR
from .transcript import transcript_to_messages


def _read_file_safe(path: Path) -> str:
    """Read a file, returning empty string if missing."""
    if path.exists():
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError:
            return ""
    return ""


def _render_plane(config: AgentConfig) -> str:
    """Load plane.md and substitute agent-specific path variables."""
    template = _read_file_safe(CONSTITUTION_DIR / "plane.md")
    if not template:
        return ""
    scratch_dir = config.memory_dir / "current" / "scratch"
    replacements = {
        "{agent_name}": config.name.capitalize(),
        "{memory_dir}": str(config.memory_dir),
        "{room_dir}": str(config.room_dir),
        "{scratch_dir}": str(scratch_dir),
        "{akasha_dir}": str(config.akasha_dir),
    }
    for placeholder, value in replacements.items():
        template = template.replace(placeholder, value)
    return template


def build_system_prompt(config: AgentConfig, hook_content: str = "") -> str:
    """
    Build full system prompt:
    plane + identity + character files + semantic core + episodic core +
    hazim introduction + shared hazim context.
    """
    from ..memory.memory import (
        load_memory_core,
        load_shared_hazim_context,
    )

    parts = []

    # 1. The plane — universal mechanics, rendered with agent-specific paths
    plane = _render_plane(config)
    if plane:
        parts.append(plane)

    # 2. Identity — agent mission and character
    identity = _read_file_safe(config.identity_path)
    if identity:
        parts.append(identity)

    # 3. Character files (character.md, contract.md, values.md)
    if config.identity_dir.exists():
        for f in sorted(config.identity_dir.iterdir()):
            if f.suffix == ".md":
                content = _read_file_safe(f)
                if content:
                    parts.append(f"## {f.stem.capitalize()}\n{content}")

    # 4. Memory core — always loaded, size-capped
    memory_core = load_memory_core(config)
    if memory_core:
        parts.append(memory_core)

    # 5. Hazim introduction — from constitution/hazim_introduction.md
    hazim_intro = _read_file_safe(CONSTITUTION_DIR / "hazim_introduction.md")
    if hazim_intro:
        parts.append(f"## About Hazim (God-lite)\n{hazim_intro}")

    # 6. Shared hazim context — top scored entries
    shared_context = load_shared_hazim_context()
    if shared_context:
        parts.append(shared_context)

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
    from ..memory.memory import load_memory_extended_relevant

    if hook_type == HookType.HUMAN_MESSAGE:
        # Standard conversation: history + relevant extended memory + new message
        messages = transcript_to_messages(incarnation_entries)

        memory_context_parts = []

        extended_relevant = load_memory_extended_relevant(config, new_human_message)
        if extended_relevant:
            memory_context_parts.append(extended_relevant)

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


# ── Extended memory helpers ────────────────────────────────────────────────────

def load_recent_episodic_summary(config: AgentConfig, max_entries: int = 3) -> str:
    """Load recent episodic summaries for heartbeat context."""
    ext_dir = config.memory_extended_dir
    if not ext_dir.exists():
        return ""

    entries = []
    for ep_file in sorted(ext_dir.iterdir(), reverse=True):
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

    episodic = [e for e in entries if e.get("type") == "episodic_summary"]
    if not episodic:
        return ""

    parts = ["## Recent Episodic Memory\n"]
    for entry in episodic[:max_entries]:
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
    ep_file = config.memory_extended_dir / f"{incarnation_name}.jsonl"
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

    episodic = [e for e in entries if e.get("type") == "episodic_summary"]
    if not episodic:
        return ""

    entry = episodic[-1]
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
