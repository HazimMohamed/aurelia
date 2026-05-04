#!/usr/bin/env python3
"""CLI chat with Claude via OpenRouter. Custom system prompt, infinite back and forth.

Usage:
    python examples/chat.py
    python examples/chat.py --system "You are a pirate" --model anthropic/claude-haiku-4-5
    python examples/chat.py --system @prompts/my_prompt.txt --model openai/gpt-4o
    python examples/chat.py --turns 10 --temperature 0.3 --name my_session
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path

_lab = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _lab)
sys.path.insert(0, os.path.dirname(_lab))

from alembic.rooms.chat import ChatRoom

_DEFAULT_MODEL = "anthropic/claude-sonnet-4-6"


def _load_system_prompt(value: str | None) -> str:
    if value is None:
        print("  Enter your system prompt (blank line to finish):")
        lines: list[str] = []
        try:
            while True:
                line = input()
                if line == "" and lines:
                    break
                lines.append(line)
        except (EOFError, KeyboardInterrupt):
            pass
        print()
        return "\n".join(lines).strip()

    if value.startswith("@"):
        path = Path(value[1:])
        if not path.exists():
            sys.exit(f"error: file not found: {path}")
        return path.read_text(encoding="utf-8").strip()

    return value.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="CLI chat via OpenRouter")
    parser.add_argument(
        "--system", "-s",
        metavar="PROMPT",
        help="System prompt text, or @path/to/file.txt. Interactive if omitted.",
    )
    parser.add_argument(
        "--model", "-m",
        default=_DEFAULT_MODEL,
        metavar="MODEL",
        help=f"OpenRouter model ID (default: {_DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--turns", "-t",
        type=int,
        default=None,
        metavar="N",
        help="Max turns (default: unlimited)",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.7,
        metavar="T",
        help="Temperature 0.0–1.0 (default: 0.7)",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=1024,
        metavar="N",
        help="Max output tokens per turn (default: 1024)",
    )
    parser.add_argument(
        "--storage",
        default="chats",
        metavar="DIR",
        help="Directory for transcript files (default: chats/)",
    )
    parser.add_argument(
        "--name",
        default=None,
        metavar="NAME",
        help="Transcript filename stem (default: auto timestamped)",
    )

    args = parser.parse_args()
    system_prompt = _load_system_prompt(args.system)

    room = ChatRoom(
        system_prompt=system_prompt,
        model=args.model,
        turns=args.turns,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        storage=Path(args.storage),
        transcript_name=args.name,
    )

    try:
        asyncio.run(room.run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
