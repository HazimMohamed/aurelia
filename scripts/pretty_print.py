#!/usr/bin/env python3
"""pretty_print.py — Convert Aurelia JSONL transcript files to readable markdown.

Usage:
    python3 scripts/pretty_print.py /home/personal/karma/episodic/extended/personal-quiet-moon-8.jsonl
    python3 scripts/pretty_print.py /home/zuzu/akasha/personal-quiet-moon-8/personal-quiet-moon-8-transcript.jsonl
    cat some.jsonl | python3 scripts/pretty_print.py -
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
}

TYPE_EMOJIS = {
    "human_message": "👤",
    "assistant_message": "🤖",
    "incarnation_start": "🌅",
    "bardo_complete": "🌙",
    "episodic_summary": "📚",
}


def format_entry(entry: dict) -> str:
    entry_type = entry.get("type", "unknown")
    ts = entry.get("ts", "")
    cycle = entry.get("cycle", "")
    content = entry.get("content", "")

    label = TYPE_LABELS.get(entry_type, entry_type)
    emoji = TYPE_EMOJIS.get(entry_type, "  ")

    header_parts = [f"{emoji} **{label}**"]
    if ts:
        header_parts.append(f"`{ts}`")
    if cycle:
        header_parts.append(f"cycle {cycle}")

    header = "  ".join(header_parts)

    lines = [header]

    if entry_type in ("incarnation_start", "bardo_complete"):
        incarnation = entry.get("incarnation", "")
        if incarnation:
            lines.append(f"  Incarnation: `{incarnation}`")
    elif entry_type == "episodic_summary":
        incarnation = entry.get("incarnation", "")
        cycles = entry.get("cycles", "")
        summary_data = entry.get("summary", {})

        if incarnation:
            lines.append(f"  Incarnation: `{incarnation}`")
        if cycles:
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
