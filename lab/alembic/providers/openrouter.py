from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

import openai
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

_client: openai.AsyncOpenAI | None = None


def _get_client() -> openai.AsyncOpenAI:
    global _client
    if _client is None:
        import os
        _client = openai.AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ.get("OPENROUTER_API_KEY", ""),
        )
    return _client


async def stream(
    model: str,
    system_prompt: str,
    messages: list[dict[str, Any]],
    temperature: float = 0.7,
    max_tokens: int = 1024,
    on_token: Any = None,
) -> dict[str, Any]:
    client = _get_client()
    start_time = time.monotonic()
    full_text = ""
    input_tokens = 0
    output_tokens = 0

    all_messages: list[dict] = []
    if system_prompt:
        all_messages.append({"role": "system", "content": system_prompt})
    all_messages.extend(messages)

    response = await client.chat.completions.create(
        model=model,
        messages=all_messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
        stream_options={"include_usage": True},
    )

    async for chunk in response:
        if chunk.usage:
            input_tokens = chunk.usage.prompt_tokens or 0
            output_tokens = chunk.usage.completion_tokens or 0

        if not chunk.choices:
            continue

        delta = chunk.choices[0].delta.content
        if delta:
            for char in delta:
                if on_token:
                    on_token(char)
                else:
                    print(char, end="", flush=True)
                await asyncio.sleep(0.01)
            full_text += delta

    if not on_token:
        print()

    latency_ms = (time.monotonic() - start_time) * 1000

    return {
        "text": full_text,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency_ms": round(latency_ms, 2),
        # OpenRouter doesn't surface cost in the streaming response body
        "cost_usd": 0.0,
    }
