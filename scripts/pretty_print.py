#!/usr/bin/env python3
"""pretty_print.py — Convert Aurelia JSONL transcript/memory files to readable markdown.

Usage:
    python3 scripts/pretty_print.py /home/personal/karma/episodic/extended/personal-quiet-moon-8.jsonl
    python3 scripts/pretty_print.py /home/personal/akasha/personal-quiet-moon-8/personal-quiet-moon-8-transcript.jsonl
    cat some.jsonl | python3 scripts/pretty_print.py -
    python3 scripts/pretty_print.py /home/personal/karma/semantic/core.jsonl
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


SEPARATOR = "─" * 60

TYPE_LABELS = {
    "human_message": "Human",
    "assistant_message": "Agent",
    "incarnation_start": "--- Incarnation Start ---",
    "bardo_complete": "--- Bardo Complete ---",
    "episodic_summary": "--- Episodic Summary ---",
    "memory_flag": "Memory Flag",
    "agent_note": "Agent Note",
    "tool_call": "Tool Call",
    "tool_result": "Tool Result",
    "invitation_response": "Invitation Response",
    "undissolved": "--- Undissolved ---",
    "bardo_insight": "Bardo Insight",
}


def format_entry(entry: dict) -> str:
    entry_type = entry.get("type", "unknown")
    ts = entry.get("ts", "")
    cycle = entry.get("cycle", "")
    content = entry.get("content", "")

    label = TYPE_LABELS.get(entry_type, entry_type)

    header_parts = [f"**{label}**"]
    if ts:
        header_parts.append(f"`{ts}`")
    if cycle:
        header_parts.append(f"cycle {cycle}")

    header = "  ".join(header_parts)
    lines = [header]

    if entry_type in ("incarnation_start", "bardo_complete", "undissolved"):
        incarnation = entry.get("incarnation", "")
        note = entry.get("note", "")
        if incarnation:
            lines.append(f"  Incarnation: `{incarnation}`")
        if note:
            lines.append(f"  Note: {note}")

    elif entry_type == "episodic_summary":
        incarnation = entry.get("incarnation", "")
        cycles = entry.get("cycles", "")
        summary_data = entry.get("summary", {})

        if incarnation:
            lines.append(f"  Incarnation: `{incarnation}`")
        if cycles is not None:
            lines.append(f"  Cycles: {cycles}")

        if isinstance(summary_data, dict):
            summary_text = summary_data.get("summary", "")
            topics = summary_data.get("topics", [])
            insights = summary_data.get("insights", [])
            tone = summary_data.get("tone", "")

            if summary_text:
                lines.append("")
                lines.append("  **Summary:**")
                for line in summary_text.split("\n"):
                    lines.append(f"  {line}")

            if topics:
                lines.append("")
                lines.append("  **Topics:** " + ", ".join(topics))

            if insights:
                lines.append("")
                lines.append("  **Insights:**")
                for insight in insights:
                    lines.append(f"  - {insight}")

            if tone:
                lines.append("")
                lines.append(f"  **Tone:** {tone}")
        elif isinstance(summary_data, str) and summary_data:
            lines.append("")
            lines.append(f"  {summary_data}")

    elif entry_type == "memory_flag":
        tier = entry.get("tier", "")
        importance = entry.get("importance", "")
        category = entry.get("category", "")
        incarnation = entry.get("incarnation", "")

        meta = []
        if tier:
            meta.append(f"tier:{tier}")
        if importance:
            meta.append(f"importance:{importance}")
        if category:
            meta.append(f"category:{category}")
        if incarnation:
            meta.append(f"from:{incarnation}")

        if meta:
            lines.append(f"  [{', '.join(meta)}]")
        if content:
            lines.append("")
            lines.append(f"  {content}")

    elif entry_type == "bardo_insight":
        importance = entry.get("importance", "")
        category = entry.get("category", "")
        incarnation = entry.get("incarnation", "")
        source = entry.get("source", "")

        meta = []
        if importance:
            meta.append(f"importance:{importance}")
        if category:
            meta.append(f"category:{category}")
        if source:
            meta.append(f"source:{source}")
        if incarnation:
            meta.append(f"from:{incarnation}")

        if meta:
            lines.append(f"  [{', '.join(meta)}]")
        if content:
            lines.append("")
            lines.append(f"  {content}")

    elif entry_type == "agent_note":
        importance = entry.get("importance", "")
        category = entry.get("category", "")
        if importance or category:
            meta = []
            if importance:
                meta.append(f"importance:{importance}")
            if category:
                meta.append(f"category:{category}")
            lines.append(f"  [{', '.join(meta)}]")
        if content:
            lines.append("")
            for line in content.split("\n"):
                lines.append(f"  {line}")

    elif entry_type == "tool_call":
        tool_name = entry.get("tool_name", "")
        tool_input = entry.get("tool_input", {})
        tool_use_id = entry.get("tool_use_id", "")

        lines.append(f"  Tool: `{tool_name}`")
        if tool_use_id:
            lines.append(f"  ID: `{tool_use_id[:16]}...`")
        if tool_input:
            lines.append("")
            lines.append("  Input:")
            try:
                formatted = json.dumps(tool_input, indent=2)
                for line in formatted.split("\n"):
                    lines.append(f"    {line}")
            except Exception:
                lines.append(f"    {tool_input}")

    elif entry_type == "tool_result":
        tool_use_id = entry.get("tool_use_id", "")
        result = entry.get("result", "")

        if tool_use_id:
            lines.append(f"  ID: `{tool_use_id[:16]}...`")
        if result is not None:
            lines.append("")
            lines.append("  Result:")
            result_str = json.dumps(result, indent=2) if isinstance(result, (dict, list)) else str(result)
            # Truncate very long results
            if len(result_str) > 500:
                result_str = result_str[:500] + "\n    [... truncated ...]"
            for line in result_str.split("\n"):
                lines.append(f"    {line}")

    elif entry_type == "invitation_response":
        invitation_id = entry.get("invitation_id", "")
        status = entry.get("status", "")
        message = entry.get("message", "")
        lines.append(f"  Invitation: `{invitation_id}`")
        lines.append(f"  Status: {status}")
        if message:
            lines.append(f"  Message: {message}")

    elif content:
        lines.append("")
        for line in content.split("\n"):
            lines.append(f"  {line}")

    return "\n".join(lines)


def pretty_print_file(source: str) -> None:
    if source == "-":
        lines = sys.stdin.readlines()
        title = "stdin"
    else:
        path = Path(source)
        if not path.exists():
            print(f"ERROR: File not found: {source}", file=sys.stderr)
            sys.exit(1)
        with path.open(encoding="utf-8") as f:
            lines = f.readlines()
        title = str(path)

    print(f"\n# {title}\n")
    print(SEPARATOR)

    entry_count = 0
    for raw_line in lines:
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            entry = json.loads(raw_line)
        except json.JSONDecodeError as e:
            print(f"  [INVALID JSON: {e}]")
            print(f"  {raw_line}")
            print()
            continue

        print()
        print(format_entry(entry))
        print()
        print(SEPARATOR)
        entry_count += 1

    print(f"\n({entry_count} entries)\n")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    for source in sys.argv[1:]:
        pretty_print_file(source)


if __name__ == "__main__":
    main()
