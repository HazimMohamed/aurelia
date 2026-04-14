"""Context assembly for agent LLM calls — supports all hook types."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from config import AgentConfig
from transcript import transcript_to_messages


def _read_file_safe(path: Path) -> str:
    """Read a file, returning empty string if missing."""
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return ""


def build_system_prompt(config: AgentConfig) -> str:
    """Build system prompt: constitution + all identity files concatenated."""
    parts = []

    # Constitution (dharma)
    constitution = _read_file_safe(config.constitution_path)
    if constitution:
        parts.append(constitution)

    # Identity files (character.md, contract.md, values.md)
    if config.identity_dir.exists():
        for identity_file in sorted(config.identity_dir.iterdir()):
            if identity_file.suffix == ".md":
                content = _read_file_safe(identity_file)
                if content:
                    parts.append(f"## {identity_file.stem.capitalize()}\n{content}")

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
    incarnation_entries: list[dict[str, Any]],
    new_human_message: str,
    hook_type: str,
) -> list[dict[str, Any]]:
    """Build messages array appropriate for the given hook type."""
    from hooks import HookType

    if hook_type == HookType.HUMAN_MESSAGE:
        # Standard conversation: history + new message
        messages = transcript_to_messages(incarnation_entries)
        messages.append({"role": "user", "content": new_human_message})
        return messages

    elif hook_type in (HookType.HEARTBEAT, HookType.SCHEDULED_TASK, HookType.AGENT_INVITE):
        # Autonomous hooks: fresh context (no prior conversation history for this incarnation)
        # new_human_message already contains the formatted hook prompt
        return [{"role": "user", "content": new_human_message}]

    else:
        # Fallback: treat as human message
        messages = transcript_to_messages(incarnation_entries)
        messages.append({"role": "user", "content": new_human_message})
        return messages


def load_recent_episodic_summary(config: AgentConfig, max_entries: int = 3) -> str:
    """Load recent episodic summaries for heartbeat context."""
    episodic_dir = config.episodic_extended_dir
    if not episodic_dir.exists():
        return ""

    entries = []
    import json
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

    import json
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

    entry = entries[-1]  # Most recent entry for this incarnation
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
