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


def write_assistant_message(transcript_path: Path, content: str, cycle: int) -> None:
    append_entry(
        transcript_path,
        {
            "ts": _now_iso(),
            "type": "assistant_message",
            "content": content,
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


def transcript_to_messages(entries: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Convert transcript entries to Anthropic messages format (human/assistant pairs)."""
    messages = []
    for entry in entries:
        entry_type = entry.get("type")
        content = entry.get("content", "")
        if entry_type == "human_message" and content:
            messages.append({"role": "user", "content": content})
        elif entry_type == "assistant_message" and content:
            messages.append({"role": "assistant", "content": content})
    return messages
