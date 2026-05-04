from __future__ import annotations

import asyncio
import random
import re
import sys
import termios
import tty
from dataclasses import dataclass, field
from difflib import get_close_matches
from enum import Enum

from ..providers.anthropic import complete, stream
from .duo import Agent, Style, _NAMES, _generate_name, _resolve_style

_BATON_RE = re.compile(r'\[→\s*([^\]]+)\]', re.IGNORECASE)


def _parse_baton(text: str, participants: list[str]) -> str | None:
    match = _BATON_RE.search(text)
    if not match:
        return None
    name = match.group(1).strip()
    # Exact / substring match
    for p in participants:
        if p.lower() == name.lower() or name.lower() in p.lower():
            return p
    # Fuzzy match — handles typos and partial names
    fuzzy = get_close_matches(name, participants, n=1, cutoff=0.6)
    return fuzzy[0] if fuzzy else None


def _strip_baton(text: str) -> str:
    return _BATON_RE.sub("", text).rstrip()


class FloorControl(Enum):
    BATON_PASS  = "baton_pass"
    ROUND_ROBIN = "round_robin"
    RANDOM      = "random"


def _update_history(history: list[dict], speaker: str, agent_name: str, content: str) -> None:
    """Append a transcript entry to an agent's personal history, respecting strict alternation."""
    if speaker == agent_name:
        history.append({"role": "assistant", "content": content})
    else:
        formatted = f"[{speaker}]: {content}"
        if history and history[-1]["role"] == "user":
            history[-1]["content"] += f"\n\n{formatted}"
        else:
            history.append({"role": "user", "content": formatted})


async def _pick_next_baton(last_content: str, current_speaker: str, participants: list[str]) -> str:
    others = [p for p in participants if p != current_speaker]
    result = await complete(
        model="haiku",
        system_prompt=(
            "You manage speaking order in a group discussion. "
            "Based on the last message, decide who should speak next. "
            "Respond with only their name, nothing else."
        ),
        messages=[{"role": "user", "content": (
            f"Participants: {', '.join(others)}\n\n"
            f"Last message from {current_speaker}:\n{last_content}"
        )}],
        temperature=0.3,
        max_tokens=16,
    )
    name = result["text"].strip()
    for p in others:
        if p.lower() in name.lower() or name.lower() in p.lower():
            return p
    return random.choice(others)


def _run_picker(options: list[str], prompt: str) -> str:
    selected = 0
    n = len(options)

    def w(s: str) -> None:
        sys.stdout.write(s)
        sys.stdout.flush()

    def render(first: bool = False) -> None:
        if not first:
            w(f"\033[{n}A")
        for i, opt in enumerate(options):
            if i == selected:
                w(f"\r  \033[1;36m› {opt}\033[0m\033[K\r\n")
            else:
                w(f"\r  \033[90m  {opt}\033[0m\033[K\r\n")

    w(f"  {prompt}\r\n")
    render(first=True)

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        while True:
            ch = sys.stdin.read(1)
            if ch in ("\r", "\n"):
                break
            if ch == "\x03":
                raise KeyboardInterrupt
            if ch == "\x1b":
                rest = sys.stdin.read(2)
                if rest == "[A":
                    selected = (selected - 1) % n
                elif rest == "[B":
                    selected = (selected + 1) % n
                render()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

    # Collapse picker to a single summary line
    w(f"\033[{n + 1}A\r")
    w(f"  \033[90m→\033[0m \033[1;36m{options[selected]}\033[0m\033[K\r\n")
    for _ in range(n):
        w(f"\033[K\r\n")

    return options[selected]


async def _prompt_human(human_name: str) -> str:
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(
            None, lambda: input(f"  > ")
        )
    except (EOFError, KeyboardInterrupt):
        return "q"


async def _resolve_agent_names(agents: list[Agent], exclude: set[str]) -> None:
    """Resolve names for all unnamed agents, guaranteeing uniqueness."""
    pool = [n for n in _NAMES if n not in exclude]
    random.shuffle(pool)

    unnamed = [a for a in agents if a.name is None]
    fallbacks = pool[:len(unnamed)]

    resolved = await asyncio.gather(*[
        _generate_name(a.system_prompt, fallbacks[i])
        for i, a in enumerate(unnamed)
    ])

    seen: set[str] = set(a.name for a in agents if a.name is not None)
    remaining = [n for n in pool if n not in seen]

    for agent, name in zip(unnamed, resolved):
        if name in seen:
            name = remaining.pop(0) if remaining else name + "²"
        agent.name = name
        seen.add(name)


@dataclass
class ConferenceRoom:
    topic: str
    turns: int
    agents: list[Agent]
    floor_control: FloorControl = FloorControl.BATON_PASS
    human_name: str | None = None
    style: Style | str | None = None

    async def run(self) -> None:
        style_instruction = _resolve_style(self.style)

        # Resolve unnamed agents (exclude human_name from pool)
        await _resolve_agent_names(self.agents, exclude={self.human_name} if self.human_name else set())

        agent_by_name = {a.name: a for a in self.agents}
        ai_names = [a.name for a in self.agents]
        all_participants = ai_names + ([self.human_name] if self.human_name else [])

        # Per-agent conversation histories
        histories: dict[str, list[dict]] = {name: [] for name in ai_names}

        # Shared transcript
        transcript: list[dict] = []

        total_cost = 0.0
        done = False

        # Seed: topic goes to everyone's history as first user message
        for name in ai_names:
            histories[name].append({"role": "user", "content": self.topic})
        transcript.append({"speaker": "topic", "content": self.topic})

        # Starting speaker
        current_speaker = ai_names[0]
        rr_index = 0

        print(f"\n{'═'*60}")
        print(f"  {self.topic}")
        print(f"  {' · '.join(all_participants)}")
        print(f"{'═'*60}\n")

        for turn in range(1, self.turns + 1):
            if done:
                break

            passed_to: str | None = None

            # ── Human's turn ─────────────────────────────────────────
            if current_speaker == self.human_name:
                print(f"┌─ {self.human_name} (you)")
                print("│")

                try:
                    human_msg = await _prompt_human(self.human_name)
                except (KeyboardInterrupt, asyncio.CancelledError):
                    human_msg = "q"

                if not human_msg.strip() or human_msg.strip().lower() == "q":
                    print("│")
                    print("└─\n")
                    done = True
                    break

                content = human_msg.strip()

                # Ask who gets the baton
                others = [p for p in all_participants if p != self.human_name]
                loop = asyncio.get_event_loop()
                picked = await loop.run_in_executor(
                    None, lambda: _run_picker(others, "Pass to:")
                )
                passed_to = picked

                print("│")
                print("└─\n")

                transcript.append({"speaker": self.human_name, "content": content})
                for name in ai_names:
                    _update_history(histories[name], self.human_name, name, content)

            # ── AI's turn ─────────────────────────────────────────────
            else:
                agent = agent_by_name[current_speaker]
                history = histories[current_speaker]

                other_ai_names = [n for n in ai_names if n != current_speaker]
                others = [p for p in all_participants if p != current_speaker]
                context = (
                    f"You are {agent.name}, participating in a group discussion. "
                    f"Participants: {', '.join(all_participants)}. "
                    f"You are an AI. "
                    f"{'Other AIs: ' + ', '.join(other_ai_names) + '. ' if other_ai_names else ''}"
                    f"{self.human_name} is the human. "
                    f"Topic: {self.topic}"
                )
                baton_instruction = (
                    f"At the end of every response, pass the floor by writing [→ Name] "
                    f"on its own line, where Name is one of: {', '.join(others)}."
                )
                system = f"{context}\n\n{agent.system_prompt}\n\n{baton_instruction}".strip()
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
                    # Roll back the last user message we appended
                    if history and history[-1]["role"] == "user":
                        history.pop()
                    print("\n│")

                    loop = asyncio.get_event_loop()
                    try:
                        inject = await loop.run_in_executor(
                            None, lambda: input("  ↳ inject ('q' to quit): ")
                        )
                    except (EOFError, KeyboardInterrupt):
                        inject = "q"

                    print()
                    if not inject.strip() or inject.strip().lower() == "q":
                        done = True
                        break

                    content = f"[{self.human_name}]: {inject.strip()}"
                    transcript.append({"speaker": self.human_name, "content": inject.strip()})
                    for name in ai_names:
                        _update_history(histories[name], self.human_name, name, inject.strip())

                    # Re-prime the interrupted agent's history for their next turn
                    histories[current_speaker].append({"role": "user", "content": content})
                    continue

                raw = result["text"]
                passed_to = _parse_baton(raw, all_participants) if self.floor_control == FloorControl.BATON_PASS else None  # noqa: F841
                content = _strip_baton(raw) if self.floor_control == FloorControl.BATON_PASS else raw
                total_cost += result["cost_usd"]

                transcript.append({"speaker": current_speaker, "content": content})
                for name in ai_names:
                    _update_history(histories[name], current_speaker, name, content)

                footer = f"{result['latency_ms']:.0f}ms · ${result['cost_usd']:.5f}"
                if self.floor_control == FloorControl.BATON_PASS and passed_to is None:
                    footer += "  ↳ missed baton pass, falling back"
                print("│")
                print(f"└─ {footer}\n")

            # ── Pick next speaker ──────────────────────────────────────
            if not done and turn < self.turns:
                last_entry = transcript[-1]
                is_last_turn = (turn == self.turns - 1)
                eligible = [
                    p for p in all_participants
                    if not (is_last_turn and p == self.human_name)
                ]

                if self.floor_control == FloorControl.BATON_PASS:
                    # Discard human pick if it slipped through on the last turn
                    candidate = passed_to if passed_to in eligible else None
                    current_speaker = candidate or await _pick_next_baton(
                        last_entry["content"], last_entry["speaker"], eligible
                    )
                elif self.floor_control == FloorControl.ROUND_ROBIN:
                    rr_index = (rr_index + 1) % len(eligible)
                    current_speaker = eligible[rr_index % len(eligible)]
                elif self.floor_control == FloorControl.RANDOM:
                    others = [p for p in eligible if p != current_speaker]
                    current_speaker = random.choice(others)

        print(f"{'═'*60}")
        print(f"  Total cost: ${total_cost:.5f}")
        print(f"{'═'*60}\n")
