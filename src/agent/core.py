"""Agent core loop: LLM call, tool execution, and response handling."""

from __future__ import annotations

import json
import re
from typing import Any, Callable

import anthropic

from ..samsara.config import AgentConfig
from .context import build_system_prompt, build_messages, build_hook_messages
from .transcript import (
    write_human_message,
    write_assistant_message,
    write_tool_call,
    write_tool_result,
)
from .hooks import HookType

MAX_TOOL_CYCLES = 30  # safety limit to prevent infinite loops

StreamCallback = Callable[[dict[str, Any]], None]


def _extract_next_action(text: str) -> dict[str, Any]:
    """Parse the next action JSON from the agent's response text."""
    pattern = r'\{"next"\s*:\s*\{[^}]*\}\}'
    matches = re.findall(pattern, text)
    for match in reversed(matches):
        try:
            parsed = json.loads(match)
            if "next" in parsed:
                return parsed["next"]
        except json.JSONDecodeError:
            pass
    return {"type": "sleep"}


def _block_to_dict(block: Any) -> dict[str, Any]:
    """Convert an Anthropic content block object to a plain dict."""
    t = block.type
    if t == "thinking":
        return {"type": "thinking", "thinking": block.thinking, "signature": block.signature}
    if t == "text":
        return {"type": "text", "text": block.text}
    if t == "tool_use":
        return {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
    return {}


def _build_tool_result_message(tool_use_id: str, result: Any) -> dict[str, Any]:
    """Build the tool result message for the Anthropic API."""
    if result is None:
        content = "null"
    elif isinstance(result, (dict, list)):
        content = json.dumps(result)
    else:
        content = str(result)
    return {"type": "tool_result", "tool_use_id": tool_use_id, "content": content}


def run_agent_cycle(
    config: AgentConfig,
    incarnation_state: dict[str, Any],
    human_content: str,
    sender: str = "god-lite",
    hook_type: str = HookType.HUMAN_MESSAGE,
    tool_registry: Any = None,
    stream_callback: StreamCallback | None = None,
) -> str:
    """
    Execute one agent cycle:
    1. Build system prompt and messages
    2. Stream LLM response (buffered if no stream_callback)
    3. Handle tool calls in a loop until text response
    4. Write human + assistant messages to transcript
    5. Return assistant response text
    """
    transcript_path = incarnation_state["transcript_path"]
    entries = incarnation_state["entries"]
    cycle = incarnation_state["cycle"] + 1

    system_prompt = build_system_prompt(config, hook_content=human_content)
    messages = build_hook_messages(config, entries, human_content, hook_type)

    write_human_message(transcript_path, human_content, cycle, sender=sender)
    incarnation_state["cycle"] = cycle

    client = anthropic.Anthropic()

    tools = tool_registry.get_schemas() if tool_registry else []

    if tool_registry:
        tool_registry._ctx_extras = {"tool_registry": tool_registry}

    response_text, usage, thinking_blocks = _run_with_tools(
        client=client,
        config=config,
        messages=messages,
        system_prompt=system_prompt,
        tools=tools,
        tool_registry=tool_registry,
        transcript_path=transcript_path,
        cycle=cycle,
        stream_callback=stream_callback,
    )

    write_assistant_message(
        transcript_path,
        response_text,
        cycle,
        thinking_blocks=thinking_blocks if thinking_blocks else None,
        usage=usage if any(usage.values()) else None,
    )

    if any(usage.values()):
        try:
            from .budget import check_and_apply_budget
            incarnation_name = incarnation_state.get("name", "unknown")
            check_and_apply_budget(
                config=config,
                usage=usage,
                incarnation_name=incarnation_name,
                task_in_progress=human_content[:100],
                is_heartbeat=hook_type == HookType.HEARTBEAT,
            )
        except Exception as e:
            print(f"[core] Budget tracking error: {e}")

    incarnation_state["entries"] = incarnation_state["entries"] + [
        {"type": "human_message", "content": human_content, "cycle": cycle},
        {"type": "assistant_message", "content": response_text, "cycle": cycle},
    ]

    return response_text


def _with_cache_breakpoint(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mark the last message before the final user turn with a cache_control breakpoint.

    This caches the accumulated message history so subsequent cycles don't re-process
    it as raw input. No-op if there's only one message (nothing to cache yet).
    """
    if len(messages) < 2:
        return messages
    messages = list(messages)
    target = dict(messages[-2])
    content = target.get("content", "")
    if isinstance(content, str):
        target["content"] = [{"type": "text", "text": content, "cache_control": {"type": "ephemeral"}}]
    elif isinstance(content, list) and content:
        content = list(content)
        content[-1] = {**content[-1], "cache_control": {"type": "ephemeral"}}
        target["content"] = content
    messages[-2] = target
    return messages


def _run_with_tools(
    client: anthropic.Anthropic,
    config: AgentConfig,
    messages: list[dict[str, Any]],
    system_prompt: str,
    tools: list[dict[str, Any]],
    tool_registry: Any,
    transcript_path: Any,
    cycle: int,
    stream_callback: StreamCallback | None = None,
) -> tuple[str, int, list[dict[str, Any]]]:
    """
    Stream the LLM, handle tool use, repeat until text response.

    Always uses the streaming API internally. If stream_callback is None the
    deltas are silently accumulated and the final assembled response is returned —
    callers that don't want streaming get identical behaviour to before.

    Returns (response_text, usage, thinking_blocks).
    usage is {input, cache_write, cache_read, output} token counts.
    thinking_blocks contains {thinking, signature} dicts for transcript storage
    and must be fed back into the message history on future turns.
    """
    tool_cycle = 0
    usage: dict[str, int] = {"input": 0, "cache_write": 0, "cache_read": 0, "output": 0}

    # Build create kwargs once; updated per tool round if needed
    max_tokens = 8192
    create_kwargs: dict[str, Any] = {
        "model": config.model,
        "max_tokens": max_tokens,
        "system": [{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
        "messages": _with_cache_breakpoint(messages),
    }
    if tools:
        create_kwargs["tools"] = tools
    use_thinking = bool(config.thinking_budget_tokens)
    if use_thinking:
        create_kwargs["thinking"] = {"type": "adaptive"}
        create_kwargs["temperature"] = 1
        create_kwargs["max_tokens"] = 16000

    extra_ctx = getattr(tool_registry, "_ctx_extras", {}) if tool_registry else {}

    while tool_cycle < MAX_TOOL_CYCLES:
        create_kwargs["messages"] = messages

        with client.messages.stream(**create_kwargs) as stream:
            for event in stream:
                if event.type == "content_block_delta" and stream_callback:
                    delta = event.delta
                    if delta.type == "text_delta":
                        stream_callback({"type": "delta", "content": delta.text})
                    elif delta.type == "thinking_delta":
                        stream_callback({"type": "thinking_delta", "content": delta.thinking})
            final = stream.get_final_message()

        if hasattr(final, "usage") and final.usage:
            usage["input"] += getattr(final.usage, "input_tokens", 0)
            usage["cache_write"] += getattr(final.usage, "cache_creation_input_tokens", 0)
            usage["cache_read"] += getattr(final.usage, "cache_read_input_tokens", 0)
            usage["output"] += getattr(final.usage, "output_tokens", 0)

        # Partition content blocks
        thinking_blocks: list[dict[str, Any]] = []
        text_parts: list[str] = []
        tool_use_blocks: list[Any] = []

        for block in final.content:
            if block.type == "thinking":
                thinking_blocks.append({"thinking": block.thinking, "signature": block.signature})
            elif block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_use_blocks.append(block)

        if final.stop_reason == "tool_use":
            # Include all content blocks (thinking + tool_use) in the assistant turn
            assistant_content = [_block_to_dict(b) for b in final.content]
            messages = messages + [{"role": "assistant", "content": assistant_content}]

            tool_results = []
            for tc in tool_use_blocks:
                write_tool_call(transcript_path, tc.name, tc.input, tc.id, cycle)

                if stream_callback:
                    stream_callback({
                        "type": "tool_call",
                        "name": tc.name,
                        "input": tc.input,
                        "tool_use_id": tc.id,
                    })

                result = (
                    tool_registry.execute(tc.name, tc.input, **extra_ctx)
                    if tool_registry
                    else {"error": f"No tool registry; cannot execute '{tc.name}'"}
                )

                write_tool_result(transcript_path, tc.id, result, cycle)

                if stream_callback:
                    stream_callback({
                        "type": "tool_result",
                        "tool_use_id": tc.id,
                        "result": result,
                    })

                tool_results.append(_build_tool_result_message(tc.id, result))

            messages = messages + [{"role": "user", "content": tool_results}]
            tool_cycle += 1
            continue

        # end_turn — final text response
        response_text = "\n".join(text_parts) if text_parts else ""
        return response_text, usage, thinking_blocks

    return f"[Error: exceeded {MAX_TOOL_CYCLES} tool cycles without a text response]", usage, []


def run_agent_cycle_and_parse(
    config: AgentConfig,
    incarnation_state: dict[str, Any],
    human_content: str,
    sender: str = "god-lite",
    hook_type: str = HookType.HUMAN_MESSAGE,
    tool_registry: Any = None,
    stream_callback: StreamCallback | None = None,
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
        stream_callback=stream_callback,
    )
    next_action = _extract_next_action(response_text)
    return response_text, next_action
