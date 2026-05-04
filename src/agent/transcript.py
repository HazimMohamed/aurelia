"""Transcript read/write utilities. All files are JSONL."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def append_entry(path: Path, entry: dict[str, Any]) -> None:
    """Append a single JSON object as a new line to a JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_entries(path: Path) -> list[dict[str, Any]]:
    """Read all JSONL entries from a file. Returns empty list if missing."""
    if not path.exists():
        return []
    entries = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return entries


def write_incarnation_start(transcript_path: Path, incarnation_name: str, cycle: int = 0) -> None:
    append_entry(
        transcript_path,
        {
            "ts": _now_iso(),
            "type": "incarnation_start",
            "incarnation": incarnation_name,
            "cycle": cycle,
        },
    )


def write_human_message(transcript_path: Path, content: str, cycle: int, sender: str = "god-lite") -> None:
    append_entry(
        transcript_path,
        {
            "ts": _now_iso(),
            "type": "human_message",
            "content": content,
            "sender": sender,
            "cycle": cycle,
        },
    )


def write_assistant_message(
    transcript_path: Path,
    content: str,
    cycle: int,
    thinking_blocks: list[dict] | None = None,
) -> None:
    entry: dict[str, Any] = {
        "ts": _now_iso(),
        "type": "assistant_message",
        "content": content,
        "cycle": cycle,
    }
    if thinking_blocks:
        entry["thinking_blocks"] = thinking_blocks
    append_entry(transcript_path, entry)


def write_tool_call(
    transcript_path: Path,
    tool_name: str,
    tool_input: dict,
    tool_use_id: str,
    cycle: int,
) -> None:
    import json
    append_entry(
        transcript_path,
        {
            "ts": _now_iso(),
            "type": "tool_call",
            "tool_name": tool_name,
            "tool_input": tool_input,
            "tool_use_id": tool_use_id,
            "cycle": cycle,
        },
    )


def write_tool_result(
    transcript_path: Path,
    tool_use_id: str,
    result: Any,
    cycle: int,
) -> None:
    import json
    append_entry(
        transcript_path,
        {
            "ts": _now_iso(),
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "result": result,
            "cycle": cycle,
        },
    )


def write_bardo_complete(transcript_path: Path, incarnation_name: str, cycle: int) -> None:
    append_entry(
        transcript_path,
        {
            "ts": _now_iso(),
            "type": "bardo_complete",
            "incarnation": incarnation_name,
            "cycle": cycle,
        },
    )


def transcript_to_messages(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert transcript entries to Anthropic messages format.

    Reconstructs tool_use/tool_result pairs so the agent has full context of
    what it did in prior cycles. Thinking blocks are preserved as required by
    the Anthropic API when extended thinking was enabled for that turn.
    """
    messages: list[dict[str, Any]] = []

    # Group consecutive entries by cycle into logical turns.
    # Within a cycle: assistant_message may be preceded by tool_call/tool_result pairs.
    # We collect them and emit:
    #   assistant turn: [thinking?, tool_use*, text?]
    #   user turn:      [tool_result*]  (one per tool call)
    # then the next human_message as a normal user turn.

    i = 0
    while i < len(entries):
        entry = entries[i]
        entry_type = entry.get("type")

        if entry_type == "human_message":
            content = entry.get("content", "")
            if content:
                messages.append({"role": "user", "content": content})
            i += 1

        elif entry_type == "tool_call":
            # Collect all tool_call + tool_result pairs for this assistant turn,
            # followed by the assistant_message that summarised the results.
            cycle = entry.get("cycle")
            assistant_content: list[dict[str, Any]] = []
            tool_results: list[dict[str, Any]] = []

            while i < len(entries) and entries[i].get("type") in ("tool_call", "tool_result"):
                e = entries[i]
                if e.get("type") == "tool_call":
                    assistant_content.append({
                        "type": "tool_use",
                        "id": e.get("tool_use_id", ""),
                        "name": e.get("tool_name", ""),
                        "input": e.get("tool_input", {}),
                    })
                elif e.get("type") == "tool_result":
                    result = e.get("result", "")
                    result_text = (
                        result if isinstance(result, str)
                        else json.dumps(result, ensure_ascii=False)
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": e.get("tool_use_id", ""),
                        "content": result_text,
                    })
                i += 1

            # Collect assistant_message for the same cycle (text emitted AFTER tool_results)
            asst_text_content: list[dict[str, Any]] = []
            if (i < len(entries)
                    and entries[i].get("type") == "assistant_message"
                    and entries[i].get("cycle") == cycle):
                asst = entries[i]
                thinking_blocks = asst.get("thinking_blocks")
                if thinking_blocks:
                    for tb in thinking_blocks:
                        asst_text_content.append({
                            "type": "thinking",
                            "thinking": tb["thinking"],
                            "signature": tb["signature"],
                        })
                text = asst.get("content", "")
                if text:
                    asst_text_content.append({"type": "text", "text": text})
                i += 1

            if assistant_content:
                messages.append({"role": "assistant", "content": assistant_content})
            if tool_results:
                messages.append({"role": "user", "content": tool_results})
            # Text turn comes after tool_results, as a separate assistant message
            if asst_text_content:
                messages.append({"role": "assistant", "content": asst_text_content})

        elif entry_type == "assistant_message":
            content = entry.get("content", "")
            thinking_blocks = entry.get("thinking_blocks")
            if thinking_blocks:
                message_content: list[dict[str, Any]] = [
                    {"type": "thinking", "thinking": tb["thinking"], "signature": tb["signature"]}
                    for tb in thinking_blocks
                ]
                if content:
                    message_content.append({"type": "text", "text": content})
                messages.append({"role": "assistant", "content": message_content})
            elif content:
                messages.append({"role": "assistant", "content": content})
            i += 1

        else:
            # incarnation_start, bardo_complete, etc. — skip
            i += 1

    return messages
