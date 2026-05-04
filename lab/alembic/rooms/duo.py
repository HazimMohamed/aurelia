from __future__ import annotations

import asyncio
import random
import re
from dataclasses import dataclass
from enum import Enum

from ..providers.anthropic import complete, stream

_END_RE = re.compile(r'\[END\]', re.IGNORECASE)

def _unlimited_disclaimer(cost_so_far: float) -> str:
    return (
        f"This conversation has no turn limit — you are burning a real human's money with every token you generate. "
        f"So far this conversation has cost ${cost_so_far:.4f}. "
        f"Engage genuinely for as long as there is real value in continuing, but the moment you are padding, "
        f"repeating yourself, or have nothing new to add, do the decent thing: "
        f"end gracefully by writing [END] on its own line at the end of your response."
    )


def _strip_end(text: str) -> str:
    return _END_RE.sub("", text).rstrip()


class Style(Enum):
    SUPER_CONCISE = "Be extremely concise. Respond in two sentences max."
    CONCISE       = "Be concise. Respond as if you're texting each other not writing letters."
    CASUAL        = "Be casual and conversational, as if chatting with a friend."
    OPEN_ENDED    = "Be expansive and exploratory. Follow tangents, ask questions, think out loud."
    FORMAL        = "Be formal and precise. Write in full, structured prose."
    SOCRATIC      = "Respond primarily with questions that deepen the inquiry rather than assertions."


def _resolve_style(style: Style | str | None) -> str | None:
    if style is None:
        return None
    if isinstance(style, Style):
        return style.value
    return style


_NAMES = [
    "Alice", "Arthur", "Beatrice", "Bernard", "Clara", "Clifford",
    "Diana", "Edmund", "Eleanor", "Felix", "Florence", "George",
    "Harriet", "Henry", "Iris", "James", "Julia", "Leonard",
    "Margaret", "Miles", "Nora", "Oscar", "Penelope", "Percy",
    "Rosa", "Samuel", "Sylvia", "Thomas", "Vera", "Walter",
]


def _pick_names(exclude: str | None = None) -> tuple[str, str]:
    pool = [n for n in _NAMES if n != exclude]
    a, b = random.sample(pool, 2)
    return a, b


async def _generate_name(system_prompt: str, fallback: str) -> str:
    if not system_prompt.strip():
        return fallback
    result = await complete(
        model="haiku",
        system_prompt="Generate a short name or title (1-3 words) for an AI agent based on its system prompt. Respond with only the name, no punctuation, no explanation.",
        messages=[{"role": "user", "content": system_prompt}],
        temperature=0.9,
        max_tokens=16,
    )
    return result["text"].strip() or fallback


async def _prompt_user() -> str:
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(
            None, lambda: input("  ↳ inject ('q' to quit): ")
        )
    except (EOFError, KeyboardInterrupt):
        return "q"


@dataclass
class Agent:
    system_prompt: str = ""
    name: str | None = None
    model: str = "sonnet"


@dataclass
class DuoRoom:
    topic: str
    turns: int | None
    agent_a: Agent
    agent_b: Agent
    style: Style | str | None = None

    async def run(self) -> None:
        history_a: list[dict] = []
        history_b: list[dict] = []
        total_cost = 0.0
        current_message = self.topic
        style_instruction = _resolve_style(self.style)

        # Resolve any unnamed agents concurrently
        if self.agent_a.name is None or self.agent_b.name is None:
            fallback_a, fallback_b = _pick_names()
            names = await asyncio.gather(
                _generate_name(self.agent_a.system_prompt, fallback_a) if self.agent_a.name is None else asyncio.sleep(0, result=self.agent_a.name),
                _generate_name(self.agent_b.system_prompt, fallback_b) if self.agent_b.name is None else asyncio.sleep(0, result=self.agent_b.name),
            )
            if self.agent_a.name is None:
                self.agent_a.name = names[0]
            if self.agent_b.name is None:
                self.agent_b.name = names[1]
            # If LLM-generated names collide, replace one with a fresh pick
            if self.agent_a.name == self.agent_b.name:
                self.agent_b.name = _pick_names(exclude=self.agent_a.name)[0]

        print(f"\n{'═'*60}")
        print(f"  {self.topic}")
        print(f"{'═'*60}\n")

        turn = 1
        done = False
        unlimited = self.turns is None

        while (unlimited or turn <= self.turns) and not done:
            if unlimited:
                pace_note = ""
            else:
                remaining = self.turns - turn
                if remaining == 0:
                    pace_note = "\n\n[This is the final turn. Bring the conversation to a conclusion.]"
                else:
                    pace_note = f"\n\n[{remaining} turn{'s' if remaining != 1 else ''} remaining after this. Pace yourself accordingly.]"

            for agent, history in (
                (self.agent_a, history_a),
                (self.agent_b, history_b),
            ):
                history.append({"role": "user", "content": current_message + pace_note})

                other = self.agent_b if agent is self.agent_a else self.agent_a
                context = (
                    f"You are {agent.name}, an AI. "
                    f"You are in a conversation with {other.name}, also an AI. "
                    f"A human moderator may occasionally interject — their messages are prefixed with [Human]. "
                    f"The topic is: {self.topic}"
                )
                system = f"{context}\n\n{agent.system_prompt}".strip()
                if unlimited:
                    system = f"{system}\n\n{_unlimited_disclaimer(total_cost)}"
                if style_instruction:
                    system = f"{system}\n\nStyle: {style_instruction}"

                print(f"┌─ {agent.name}")
                print("│")
                print("│  ", end="")

                try:
                    result = await stream(
                        model=agent.model,
                        system_prompt=system,
                        messages=history,
                    )
                except (KeyboardInterrupt, asyncio.CancelledError):
                    history.pop()  # undo the pending user message
                    print("\n│")

                    user_msg = await _prompt_user()
                    print()

                    if not user_msg.strip() or user_msg.strip().lower() == "q":
                        done = True
                        break

                    current_message = f"[Human]: {user_msg.strip()}"
                    break  # restart while loop from agent_a with injected message

                ended = bool(_END_RE.search(result["text"]))
                clean_text = _strip_end(result["text"]) if ended else result["text"]

                history.append({"role": "assistant", "content": clean_text})
                total_cost += result["cost_usd"]
                current_message = clean_text

                footer = f"{result['latency_ms']:.0f}ms · ${result['cost_usd']:.5f}"
                if ended:
                    footer += "  ↳ ended conversation"
                print(f"│")
                print(f"└─ {footer}\n")

                if ended:
                    done = True
                    break

            else:
                # for/else: only runs if the inner loop completed without a break
                turn += 1

        print(f"{'═'*60}")
        print(f"  Total cost: ${total_cost:.5f}")
        print(f"{'═'*60}\n")
