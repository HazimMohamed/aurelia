"""Context assembly for agent LLM calls."""

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
    """Build Anthropic messages array from transcript history + new message."""
    messages = transcript_to_messages(incarnation_entries)
    messages.append({"role": "user", "content": new_human_message})
    return messages
