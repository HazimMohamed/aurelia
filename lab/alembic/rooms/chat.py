from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..providers.openrouter import stream
from .conference import _run_picker

_DEFAULT_STORAGE = Path("chats")

_MODEL_OPTIONS: list[tuple[str, str]] = [
    ("anthropic/claude-sonnet-4-6",         "Claude Sonnet 4.6"),
    ("anthropic/claude-opus-4-5",           "Claude Opus 4.5"),
    ("anthropic/claude-haiku-4-5",          "Claude Haiku 4.5"),
    ("openai/gpt-4o",                       "GPT-4o"),
    ("openai/gpt-4o-mini",                  "GPT-4o Mini"),
    ("google/gemini-2.0-flash-001",         "Gemini 2.0 Flash"),
    ("google/gemini-2.5-pro-preview-03-25", "Gemini 2.5 Pro"),
    ("meta-llama/llama-4-maverick",         "Llama 4 Maverick"),
    ("x-ai/grok-3-beta",                    "Grok 3"),
    ("x-ai/grok-4.20-multi-agent",          "Grok 4.20 Multi-Agent"),
    ("x-ai/grok-4.20",                      "Grok 4.20"),
]

_MODEL_LABELS = [f"{label}  ({route})" for route, label in _MODEL_OPTIONS]
_MODEL_ROUTES = [route for route, _ in _MODEL_OPTIONS]
_MODEL_DISPLAY = {route: label for route, label in _MODEL_OPTIONS}


def _list_transcripts(storage: Path) -> list[Path]:
    if not storage.exists():
        return []
    return sorted(storage.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)


def _save_transcript(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _load_transcript(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _transcript_label(path: Path, data: dict) -> str:
    turns = len([m for m in data.get("messages", []) if m["role"] == "user"])
    model = data.get("model", "?")
    preview = ""
    for m in data.get("messages", []):
        if m["role"] == "user":
            preview = m["content"][:40].replace("\n", " ")
            break
    return f"{path.stem}  [{model} · {turns} turn{'s' if turns != 1 else ''}]  \"{preview}...\""


@dataclass
class ChatRoom:
    system_prompt: str
    model: str = "anthropic/claude-sonnet-4-6"
    turns: int | None = None
    temperature: float = 0.7
    max_tokens: int = 1024
    storage: Path = field(default_factory=lambda: _DEFAULT_STORAGE)
    transcript_name: str | None = None  # explicit filename stem; auto-generated if None

    async def run(self) -> None:
        loop = asyncio.get_event_loop()
        messages: list[dict[str, Any]] = []
        total_cost = 0.0
        turn = 0
        W = 60

        # ── Model picker ─────────────────────────────────────────────────────
        try:
            picked_label = await loop.run_in_executor(
                None, lambda: _run_picker(_MODEL_LABELS, "Choose a model:")
            )
            self.model = _MODEL_ROUTES[_MODEL_LABELS.index(picked_label)]
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        print()

        # ── Resume prompt ─────────────────────────────────────────────────────
        existing = _list_transcripts(self.storage)
        transcript_path: Path | None = None

        if existing:
            choices = ["Start fresh"] + [
                _transcript_label(p, d)
                for p in existing
                if (d := _load_transcript(p)) is not None
            ]
            valid_paths = [p for p in existing if _load_transcript(p) is not None]

            try:
                picked = await loop.run_in_executor(
                    None, lambda: _run_picker(choices, "Resume a conversation?")
                )
            except (KeyboardInterrupt, asyncio.CancelledError):
                picked = "Start fresh"
            print()

            if picked != "Start fresh":
                idx = choices.index(picked) - 1
                path = valid_paths[idx]
                saved = _load_transcript(path)
                if saved:
                    messages = saved.get("messages", [])
                    total_cost = saved.get("total_cost", 0.0)
                    turn = saved.get("turns", len([m for m in messages if m["role"] == "user"]))
                    transcript_path = path
                    print(f"  Resumed: {path.name}  ({turn} prior turn{'s' if turn != 1 else ''})\n")

        if transcript_path is None:
            stem = self.transcript_name or _auto_stem()
            transcript_path = self.storage / f"{stem}.json"

        # ── Header ────────────────────────────────────────────────────────────
        print(f"\n{'═' * W}")
        print(f"  Chat  ·  {self.model}  ·  {'unlimited' if self.turns is None else f'{self.turns} turns'}")
        print(f"  Ctrl+C mid-stream to interrupt · 'q' or blank to quit")
        print(f"{'═' * W}\n")

        model_display = _MODEL_DISPLAY.get(self.model, self.model.split("/")[-1])

        # ── Main loop ─────────────────────────────────────────────────────────
        while self.turns is None or turn < self.turns:
            try:
                user_input = await loop.run_in_executor(None, lambda: input("  you › "))
            except (EOFError, KeyboardInterrupt):
                print()
                break

            user_input = user_input.strip()
            if not user_input or user_input.lower() == "q":
                break

            messages.append({"role": "user", "content": user_input})
            print()

            print(f"┌─ {model_display}")
            print("│")
            print("│  ", end="")

            try:
                result = await stream(
                    model=self.model,
                    system_prompt=self.system_prompt,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
            except (KeyboardInterrupt, asyncio.CancelledError):
                messages.pop()
                print("\n│")
                try:
                    inject = await loop.run_in_executor(None, lambda: input("  ↳ retry ('q' to quit): "))
                except (EOFError, KeyboardInterrupt):
                    inject = "q"
                print()
                if not inject.strip() or inject.strip().lower() == "q":
                    break
                messages.append({"role": "user", "content": inject.strip()})
                print(f"┌─ {model_display}")
                print("│")
                print("│  ", end="")
                result = await stream(
                    model=self.model,
                    system_prompt=self.system_prompt,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )

            messages.append({"role": "assistant", "content": result["text"]})
            total_cost += result["cost_usd"]
            turn += 1

            print("│")
            print(f"└─ {result['latency_ms']:.0f}ms · {result['input_tokens']}→{result['output_tokens']} tok\n")

            _save_transcript(transcript_path, {
                "model": self.model,
                "system_prompt": self.system_prompt,
                "turns": turn,
                "total_cost": total_cost,
                "messages": messages,
            })

        print(f"{'═' * W}")
        print(f"  Turns: {turn}  ·  Transcript: {transcript_path}")
        print(f"{'═' * W}\n")


def _auto_stem() -> str:
    import datetime
    return datetime.datetime.now().strftime("chat_%Y%m%d_%H%M%S")
