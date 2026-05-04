from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

MODEL_ALIASES: dict[str, str] = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-6",
}

MODEL_COSTS: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5-20251001": (0.80, 4.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-opus-4-6": (15.00, 75.00),
}

_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic()
    return _client


def resolve_model(model: str) -> str:
    return MODEL_ALIASES.get(model, model)


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    resolved = resolve_model(model)
    input_rate, output_rate = MODEL_COSTS.get(resolved, (3.00, 15.00))
    return (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000


async def complete(
    model: str,
    system_prompt: str,
    messages: list[dict[str, Any]],
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> dict[str, Any]:
    resolved_model = resolve_model(model)
    client = _get_client()
    start_time = time.monotonic()

    response = await client.messages.create(
        model=resolved_model,
        system=system_prompt,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    latency_ms = (time.monotonic() - start_time) * 1000
    text = response.content[0].text if response.content else ""

    return {
        "text": text,
        "model": resolved_model,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "latency_ms": round(latency_ms, 2),
        "cost_usd": calculate_cost(resolved_model, response.usage.input_tokens, response.usage.output_tokens),
    }


async def stream(
    model: str,
    system_prompt: str,
    messages: list[dict[str, Any]],
    temperature: float = 0.7,
    max_tokens: int = 1024,
    char_delay: float = 0.02,
    on_token: Any = None,
) -> dict[str, Any]:
    resolved_model = resolve_model(model)
    client = _get_client()
    start_time = time.monotonic()
    full_text = ""

    async with client.messages.stream(
        model=resolved_model,
        system=system_prompt,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    ) as s:
        async for chunk in s.text_stream:
            for char in chunk:
                if on_token:
                    on_token(char)
                else:
                    print(char, end="", flush=True)
                await asyncio.sleep(char_delay)
            full_text += chunk

    if not on_token:
        print()
    message = await s.get_final_message()
    latency_ms = (time.monotonic() - start_time) * 1000

    return {
        "text": full_text,
        "model": resolved_model,
        "input_tokens": message.usage.input_tokens,
        "output_tokens": message.usage.output_tokens,
        "latency_ms": round(latency_ms, 2),
        "cost_usd": calculate_cost(resolved_model, message.usage.input_tokens, message.usage.output_tokens),
    }
