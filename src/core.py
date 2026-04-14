"""Agent core loop: LLM call and response."""

from __future__ import annotations

import anthropic

from config import AgentConfig
from context import build_system_prompt, build_messages
from transcript import (
    write_human_message,
    write_assistant_message,
)
from typing import Any


def run_agent_cycle(
    config: AgentConfig,
    incarnation_state: dict[str, Any],
    human_content: str,
    sender: str = "god-lite",
) -> str:
    """
    Execute one agent cycle:
    1. Build system prompt and messages
    2. Call LLM
    3. Write human + assistant messages to transcript
    4. Return assistant response text
    """
    transcript_path = incarnation_state["transcript_path"]
    entries = incarnation_state["entries"]
    cycle = incarnation_state["cycle"] + 1

    system_prompt = build_system_prompt(config)
    messages = build_messages(entries, human_content)

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=config.model,
        max_tokens=4096,
        system=system_prompt,
        messages=messages,
    )

    assistant_text = response.content[0].text

    # Write to transcript
    write_human_message(transcript_path, human_content, cycle, sender=sender)
    write_assistant_message(transcript_path, assistant_text, cycle)

    # Update incarnation state for callers who need current cycle
    incarnation_state["cycle"] = cycle

    return assistant_text
