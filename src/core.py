"""Agent core loop: LLM call, tool execution, and response handling."""

from __future__ import annotations

import json
import re
from typing import Any

import anthropic

from config import AgentConfig
from context import build_system_prompt, build_messages, build_hook_messages
from transcript import (
    write_human_message,
    write_assistant_message,
    write_tool_call,
    write_tool_result,
)
from hooks import HookType

MAX_TOOL_CYCLES = 20  # safety limit to prevent infinite loops


def _extract_next_action(text: str) -> dict[str, Any]:
    """Parse the next action JSON from the agent's response text."""
    # Look for {"next": {...}} pattern
    pattern = r'\{"next"\s*:\s*\{[^}]*\}\}'
    matches = re.findall(pattern, text)
    for match in reversed(matches):
        try:
            parsed = json.loads(match)
            if "next" in parsed:
                return parsed["next"]
        except json.JSONDecodeError:
            pass
    return {"type": "sleep"}  # default: just sleep quietly


def _build_tool_result_message(
    tool_use_id: str,
    result: Any,
) -> dict[str, Any]:
    """Build the tool result message for the Anthropic API."""
    if result is None:
        content = "null"
    elif isinstance(result, (dict, list)):
        content = json.dumps(result)
    else:
        content = str(result)

    return {
        "type": "tool_result",
        "tool_use_id": tool_use_id,
        "content": content,
    }


def run_agent_cycle(
    config: AgentConfig,
    incarnation_state: dict[str, Any],
    human_content: str,
    sender: str = "god-lite",
    hook_type: str = HookType.HUMAN_MESSAGE,
    tool_registry: Any = None,
) -> str:
    """
    Execute one agent cycle with optional tool use:
    1. Build system prompt and messages
    2. Call LLM (with tools if registry provided)
    3. Handle tool calls in a loop until text response
    4. Write human + assistant messages to transcript
    5. Return assistant response text
    """
    transcript_path = incarnation_state["transcript_path"]
    entries = incarnation_state["entries"]
    cycle = incarnation_state["cycle"] + 1

    system_prompt = build_system_prompt(config)
    messages = build_hook_messages(entries, human_content, hook_type)

    # Write human message to transcript now
    write_human_message(transcript_path, human_content, cycle, sender=sender)
    incarnation_state["cycle"] = cycle

    client = anthropic.Anthropic()

    # Prepare tools for API call
    tools = tool_registry.get_schemas() if tool_registry else []

    # Inject tool_registry into ctx for handlers that need it (list_tools)
    if tool_registry:
        tool_registry._ctx_extras = {"tool_registry": tool_registry}

    response_text = _run_with_tools(
        client=client,
        config=config,
        messages=messages,
        system_prompt=system_prompt,
        tools=tools,
        tool_registry=tool_registry,
        transcript_path=transcript_path,
        cycle=cycle,
    )

    write_assistant_message(transcript_path, response_text, cycle)

    # Update entries for future cycles
    incarnation_state["entries"] = incarnation_state["entries"] + [
        {"type": "human_message", "content": human_content, "cycle": cycle},
        {"type": "assistant_message", "content": response_text, "cycle": cycle},
    ]

    return response_text


def _run_with_tools(
    client: anthropic.Anthropic,
    config: AgentConfig,
    messages: list[dict[str, Any]],
    system_prompt: str,
    tools: list[dict[str, Any]],
    tool_registry: Any,
    transcript_path: Any,
    cycle: int,
) -> str:
    """Inner loop: call LLM, handle tool use, repeat until text response."""
    tool_cycle = 0

    while tool_cycle < MAX_TOOL_CYCLES:
        create_kwargs: dict[str, Any] = {
            "model": config.model,
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": messages,
        }
        if tools:
            create_kwargs["tools"] = tools

        response = client.messages.create(**create_kwargs)

        if response.stop_reason == "tool_use":
            # Process tool calls
            assistant_content = response.content

            # Add assistant message with tool use to messages
            messages = messages + [
                {"role": "assistant", "content": assistant_content}
            ]

            # Execute all tool calls and collect results
            tool_results = []
            for block in assistant_content:
                if block.type != "tool_use":
                    continue

                tool_name = block.name
                tool_input = block.input
                tool_use_id = block.id

                # Log tool call to transcript
                write_tool_call(transcript_path, tool_name, tool_input, tool_use_id, cycle)

                # Execute the tool
                if tool_registry:
                    extra_ctx = getattr(tool_registry, "_ctx_extras", {})
                    result = tool_registry.execute(tool_name, tool_input, **extra_ctx)
                else:
                    result = {"error": f"No tool registry; cannot execute '{tool_name}'"}

                # Log tool result to transcript
                write_tool_result(transcript_path, tool_use_id, result, cycle)

                tool_results.append(_build_tool_result_message(tool_use_id, result))

                # Special: continue_task returns None — loop is handled by infrastructure
                # The LLM gets the null result and can decide what to do next

            # Add tool results to messages
            messages = messages + [
                {"role": "user", "content": tool_results}
            ]

            tool_cycle += 1
            continue

        # stop_reason == "end_turn" (or "max_tokens") — extract text
        text_blocks = [b.text for b in response.content if hasattr(b, "text")]
        return "\n".join(text_blocks) if text_blocks else ""

    # Safety: hit max tool cycles
    return f"[Error: exceeded {MAX_TOOL_CYCLES} tool cycles without a text response]"


def run_agent_cycle_and_parse(
    config: AgentConfig,
    incarnation_state: dict[str, Any],
    human_content: str,
    sender: str = "god-lite",
    hook_type: str = HookType.HUMAN_MESSAGE,
    tool_registry: Any = None,
) -> tuple[str, dict[str, Any]]:
    """
    Run agent cycle and also parse the next action from the response.
    Returns (response_text, next_action_dict).
    """
    response_text = run_agent_cycle(
        config=config,
        incarnation_state=incarnation_state,
        human_content=human_content,
        sender=sender,
        hook_type=hook_type,
        tool_registry=tool_registry,
    )
    next_action = _extract_next_action(response_text)
    return response_text, next_action
