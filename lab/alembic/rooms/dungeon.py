from __future__ import annotations

import asyncio
import json
import random
from dataclasses import dataclass, field
from pathlib import Path

from ..providers.anthropic import complete, stream
from .conference import _run_picker, _update_history
from .duo import Agent, _NAMES, _END_RE, _generate_name, _strip_end

# ── Campaign loading ──────────────────────────────────────────────────────────

_CAMPAIGNS_DIR = Path(__file__).parent.parent / "campaigns"


def _load_campaign(filename: str) -> str:
    return (_CAMPAIGNS_DIR / filename).read_text(encoding="utf-8")


try:
    DEFAULT_CAMPAIGN = _load_campaign("default.txt")
except FileNotFoundError:
    DEFAULT_CAMPAIGN = (
        "A classic dungeon delve. An ancient ruin, dangerous creatures, hidden treasure. "
        "Improvise a vivid adventure with memorable locations and NPCs."
    )

# ── Character data ────────────────────────────────────────────────────────────

RACES   = ["Human", "Elf", "Dwarf", "Halfling", "Gnome", "Half-Orc", "Tiefling"]
CLASSES = ["Fighter", "Wizard", "Rogue", "Cleric", "Ranger", "Paladin", "Bard", "Druid", "Barbarian"]
STATS   = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]

_BASE_HP: dict[str, int] = {
    "Barbarian": 12,
    "Fighter": 10, "Paladin": 10,
    "Ranger": 8, "Druid": 8, "Cleric": 8, "Rogue": 8, "Bard": 8, "Monk": 8,
    "Wizard": 6,
}

_WEAPON_DICE: dict[str, str] = {
    "Fighter": "1d8",  "Barbarian": "1d12", "Paladin": "1d8",
    "Rogue":   "1d6",  "Ranger":    "1d8",  "Monk":    "1d6",
    "Cleric":  "1d6",  "Druid":     "1d4",  "Bard":    "1d6",
    "Wizard":  "1d4",
}

_PRIMARY_STAT: dict[str, str] = {
    "Fighter": "STR", "Barbarian": "STR", "Paladin": "STR",
    "Rogue":   "DEX", "Ranger":    "DEX", "Monk":    "DEX",
    "Wizard":  "INT",
    "Cleric":  "WIS", "Druid":     "WIS",
    "Bard":    "CHA",
}

_COMBAT_KEYWORDS = {
    "attack", "strike", "hit", "stab", "shoot", "cast", "slash", "swing",
    "punch", "kick", "fire", "smite", "thrust", "charge", "lunge", "cleave",
}

# ── Character ─────────────────────────────────────────────────────────────────


@dataclass
class Character:
    name: str
    race: str
    cls: str         # "class" is reserved
    stats: dict[str, int]
    backstory: str = ""
    hp: int = 0

    def modifier(self, stat: str) -> int:
        return (self.stats[stat] - 10) // 2

    def primary_modifier(self) -> int:
        return self.modifier(_PRIMARY_STAT.get(self.cls, "STR"))

    def sheet(self) -> str:
        stats_str = "  ".join(f"{s} {v}" for s, v in self.stats.items())
        return (
            f"{self.name} ({self.race} {self.cls}) — HP {self.hp}\n"
            f"  {stats_str}\n"
            f"  {self.backstory}"
        )


# ── Dice ──────────────────────────────────────────────────────────────────────


def roll_4d6_drop_lowest() -> tuple[int, list[int]]:
    dice = [random.randint(1, 6) for _ in range(4)]
    return sum(sorted(dice)[1:]), dice


def _roll_dice(notation: str) -> int:
    n, x = notation.split("d")
    return sum(random.randint(1, int(x)) for _ in range(int(n)))


def _is_combat_action(text: str) -> bool:
    return any(w in text.lower() for w in _COMBAT_KEYWORDS)


def roll_action(character: Character, action_text: str) -> str:
    mod   = character.primary_modifier()
    roll  = random.randint(1, 20)
    total = roll + mod
    sign  = "+" if mod >= 0 else ""
    result = f"[Roll: d20{sign}{mod} = {total}"
    if _is_combat_action(action_text):
        dmg_dice = _WEAPON_DICE.get(character.cls, "1d6")
        dmg_mod  = max(0, mod)
        dmg      = _roll_dice(dmg_dice) + dmg_mod
        result  += f" | Damage if hit: {dmg_dice}+{dmg_mod} = {dmg}"
    return result + "]"


# ── LLM helpers ───────────────────────────────────────────────────────────────


async def _generate_backstory(name: str, race: str, cls: str, stats: dict[str, int]) -> str:
    top = sorted(stats.items(), key=lambda x: x[1], reverse=True)[:2]
    top_str = ", ".join(f"{s} {v}" for s, v in top)
    result = await complete(
        model="haiku",
        system_prompt="Write a 2-sentence backstory for a D&D character. Be evocative and specific. No clichés.",
        messages=[{"role": "user", "content": f"{name}, a {race} {cls}. Strongest stats: {top_str}."}],
        temperature=0.9,
        max_tokens=80,
    )
    return result["text"].strip()


async def _generate_companion_backstory(name: str, race: str, cls: str, personality: str) -> str:
    result = await complete(
        model="haiku",
        system_prompt="Write one vivid sentence of backstory for a D&D companion character.",
        messages=[{"role": "user", "content": f"{name}, a {race} {cls}. Personality: {personality or 'adventurous'}."}],
        temperature=0.9,
        max_tokens=60,
    )
    return result["text"].strip()


async def _suggest_actions(dm_narration: str, character: Character) -> list[str]:
    result = await complete(
        model="haiku",
        system_prompt=(
            "You are a helpful D&D assistant. "
            "Suggest 3 short, distinct actions (one sentence each) a player could take. "
            "Respond with exactly 3 lines. No numbering. No explanation."
        ),
        messages=[{"role": "user", "content": (
            f"Scene: {dm_narration[-600:]}\n\n"
            f"Player: {character.name}, a {character.race} {character.cls}."
        )}],
        temperature=0.8,
        max_tokens=120,
    )
    lines = [ln.strip() for ln in result["text"].strip().splitlines() if ln.strip()]
    return lines[:3]


# ── Character creation ────────────────────────────────────────────────────────


async def create_character() -> Character:
    W = 60
    loop = asyncio.get_event_loop()

    print(f"\n{'═'*W}")
    print("  Character Creation")
    print(f"{'═'*W}\n")

    # Roll stats
    print("  Rolling your stats (4d6, drop lowest)...\n")
    rolled: list[int] = []
    for i in range(6):
        val, dice = roll_4d6_drop_lowest()
        dice_sorted = sorted(dice, reverse=True)
        dropped = min(dice)
        print(f"  Roll {i+1}:  {val:2d}   [{' '.join(str(d) for d in dice_sorted)}  — drop {dropped}]")
        rolled.append(val)
    print()

    # Assign stats — build unique labels for the picker (handles duplicate values)
    remaining: list[tuple[int, int]] = list(enumerate(rolled, 1))  # (roll_idx, value)
    stats: dict[str, int] = {}
    for stat in STATS:
        options = [f"{v}  (roll {i})" for i, v in remaining]
        try:
            picked = await loop.run_in_executor(
                None, lambda opts=options, s=stat: _run_picker(opts, f"Assign to {s}:")
            )
        except (KeyboardInterrupt, asyncio.CancelledError):
            raise
        idx = options.index(picked)
        _, val = remaining.pop(idx)
        stats[stat] = val
    print()

    # Race
    race = await loop.run_in_executor(None, lambda: _run_picker(RACES, "Choose your race:"))
    print()

    # Class
    cls = await loop.run_in_executor(None, lambda: _run_picker(CLASSES, "Choose your class:"))
    print()

    # Name
    try:
        name = (await loop.run_in_executor(None, lambda: input("  Your name: "))).strip()
    except (EOFError, KeyboardInterrupt):
        name = ""
    name = name or random.choice(_NAMES)
    print()

    # Backstory
    print("  Generating backstory...", end="", flush=True)
    backstory = await _generate_backstory(name, race, cls, stats)
    print(f"\r  {backstory}\n")

    hp = _BASE_HP.get(cls, 8) + (stats["CON"] - 10) // 2
    char = Character(name=name, race=race, cls=cls, stats=stats, backstory=backstory, hp=hp)

    print(f"{'─'*W}")
    print(f"  {char.sheet()}")
    print(f"{'─'*W}\n")

    return char


# ── Companion auto-build ──────────────────────────────────────────────────────


async def _auto_build_companion(agent: Agent, exclude_names: set[str]) -> tuple[Agent, Character]:
    race = random.choice(RACES)
    cls  = random.choice(CLASSES)

    # Roll stats and slot the best value into the primary stat
    rolled = sorted([roll_4d6_drop_lowest()[0] for _ in range(6)], reverse=True)
    primary = _PRIMARY_STAT.get(cls, "STR")
    secondary = [s for s in STATS if s != primary]
    random.shuffle(secondary)
    stat_order = [primary] + secondary
    stats = dict(zip(stat_order, rolled))

    # Name
    if agent.name is None:
        pool = [n for n in _NAMES if n not in exclude_names]
        fallback = random.choice(pool) if pool else "Adventurer"
        agent.name = await _generate_name(agent.system_prompt, fallback)

    backstory = await _generate_companion_backstory(agent.name, race, cls, agent.system_prompt)
    hp = _BASE_HP.get(cls, 8) + (stats["CON"] - 10) // 2
    char = Character(name=agent.name, race=race, cls=cls, stats=stats, backstory=backstory, hp=hp)
    return agent, char


# ── Tutorial ──────────────────────────────────────────────────────────────────


def _print_tutorial() -> None:
    W = 60
    print(f"\n{'═'*W}")
    print("  How to Play")
    print(f"{'═'*W}\n")
    print("  The Dungeon Master narrates scenes and resolves outcomes.")
    print("  Your AI companions act autonomously — treat them as party members.\n")
    print("  On your turn, pick a suggested action or type your own.")
    print("  A d20 roll happens automatically; the DM interprets the result.")
    print("  Combat actions also roll damage.\n")
    print("  Ctrl+C at any time to inject a message mid-stream.")
    print("  Type 'q' or leave blank to quit.")
    print(f"\n{'═'*W}")
    try:
        input("  Press Enter to begin character creation...")
    except (EOFError, KeyboardInterrupt):
        pass
    print()


# ── Human action prompt ───────────────────────────────────────────────────────


async def _prompt_human_action(character: Character, dm_narration: str) -> str:
    """Returns chosen action text, or 'q' to quit."""
    loop = asyncio.get_event_loop()

    suggestions: list[str] = []
    try:
        suggestions = await _suggest_actions(dm_narration, character)
    except Exception:
        pass

    if len(suggestions) >= 3:
        options = suggestions[:3] + ["Enter your own..."]
        try:
            picked = await loop.run_in_executor(
                None, lambda: _run_picker(options, "What do you do?")
            )
        except (KeyboardInterrupt, asyncio.CancelledError):
            return "q"
        if picked != "Enter your own...":
            return picked

    # Text input fallback
    try:
        action = await loop.run_in_executor(None, lambda: input("│  > "))
    except (EOFError, KeyboardInterrupt):
        return "q"
    return action.strip() or "q"


# ── Save / Load ───────────────────────────────────────────────────────────────


def _write_save(
    path: str,
    scene: int,
    total_cost: float,
    player: Character,
    companion_chars: list[Character],
    companion_agents: list[Agent],
    dm_history: list[dict],
    party_histories: dict[str, list[dict]],
    transcript: list[dict],
) -> None:
    data = {
        "version": 1,
        "scene": scene,
        "total_cost": total_cost,
        "player": {
            "name": player.name, "race": player.race, "cls": player.cls,
            "stats": player.stats, "backstory": player.backstory, "hp": player.hp,
        },
        "companions": [
            {
                "name": char.name, "race": char.race, "cls": char.cls,
                "stats": char.stats, "backstory": char.backstory, "hp": char.hp,
                "system_prompt": agent.system_prompt, "model": agent.model,
            }
            for char, agent in zip(companion_chars, companion_agents)
        ],
        "dm_history": dm_history,
        "party_histories": party_histories,
        "transcript": transcript,
    }
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")


def _load_save(path: str) -> dict | None:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return None


# ── DungeonRoom ───────────────────────────────────────────────────────────────


@dataclass
class DungeonRoom:
    player_character: Character
    companions: list[Agent]
    campaign_guide: str = field(default_factory=lambda: DEFAULT_CAMPAIGN)
    dm_model: str = "sonnet"
    save_path: str | None = None
    tutorial: bool = True

    async def run(self) -> None:
        loop = asyncio.get_event_loop()

        # ── Tutorial ──────────────────────────────────────────────────────────
        if self.tutorial:
            _print_tutorial()

        # ── State: restore from save or initialise fresh ──────────────────────
        companion_agents = list(self.companions)
        companion_chars: list[Character] = []
        dm_history: list[dict] = []
        party_histories: dict[str, list[dict]] = {}
        transcript: list[dict] = []
        scene = 1
        total_cost = 0.0
        restored = False

        if self.save_path and Path(self.save_path).exists():
            saved = _load_save(self.save_path)
            if saved:
                try:
                    choice = await loop.run_in_executor(
                        None, lambda: _run_picker(["Resume saved game", "Start fresh"], "Save file found:")
                    )
                except (KeyboardInterrupt, asyncio.CancelledError):
                    choice = "Start fresh"
                print()

                if choice == "Resume saved game":
                    scene         = saved["scene"]
                    total_cost    = saved["total_cost"]
                    self.player_character = Character(**saved["player"])
                    companion_chars  = [Character(**{k: v for k, v in c.items() if k not in ("system_prompt", "model")}) for c in saved["companions"]]
                    companion_agents = [Agent(system_prompt=c["system_prompt"], model=c["model"], name=c["name"]) for c in saved["companions"]]
                    dm_history       = saved["dm_history"]
                    party_histories  = saved["party_histories"]
                    transcript       = saved["transcript"]
                    restored = True

        if not restored:
            names_so_far: set[str] = {self.player_character.name}
            built: list[tuple[Agent, Character]] = []
            for agent in self.companions:
                a, c = await _auto_build_companion(agent, exclude_names=names_so_far)
                names_so_far.add(c.name)
                built.append((a, c))
            companion_agents = [a for a, _ in built]
            companion_chars  = [c for _, c in built]
            party_histories  = {c.name: [] for c in companion_chars}
            dm_history       = [{"role": "user", "content": "Begin the adventure. Set the scene and draw the party in."}]

        player    = self.player_character
        all_names = [player.name] + [c.name for c in companion_chars]

        # ── System prompts ────────────────────────────────────────────────────
        party_sheets = "\n\n".join(c.sheet() for c in [player] + companion_chars)

        dm_system = (
            "You are an AI agent running inside Alembic, a Python library for AI-driven interactive "
            "experiences. You are the Dungeon Master in a terminal D&D session. "
            "The human player types actions via their keyboard; the other party members are AI agents.\n\n"
            "Narrate the world vividly, control NPCs and monsters, and resolve party actions based on dice rolls.\n\n"
            "Dice guide: 1–5 = failure with consequence, 6–10 = partial success, "
            "11–15 = success, 16–20 = strong success. Adjust for difficulty. "
            "On combat rolls use the attack number to judge hit/miss; apply the damage value if it lands. "
            "Do not track HP — describe injury and death narratively.\n\n"
            f"Campaign:\n{self.campaign_guide}\n\n"
            f"Party:\n{party_sheets}\n\n"
            "When the adventure concludes, write [END] on its own line."
        )

        def _companion_system(agent: Agent, char: Character) -> str:
            other_companions = [n for n in all_names if n != char.name and n != player.name]
            stats_line = "  ".join(f"{s} {char.stats[s]}" for s in STATS)
            return (
                "You are an AI agent running inside Alembic, a Python library for AI-driven interactive "
                "experiences. You are playing a character in a terminal D&D session alongside a human "
                "player and other AI companions. The Dungeon Master is also an AI.\n\n"
                f"You are {char.name}, a {char.race} {char.cls}. {char.backstory}\n"
                f"Stats: {stats_line} | HP: {char.hp}\n\n"
                f"Your party: {', '.join(other_companions)} and {player.name} (human).\n"
                "Stay in character. Describe your actions in 1–3 vivid sentences. "
                "Do NOT narrate outcomes — the Dungeon Master does that.\n\n"
                f"{agent.system_prompt}".strip()
            )

        # ── Header ────────────────────────────────────────────────────────────
        party_line = " · ".join(f"{c.name} ({c.cls})" for c in companion_chars) + f" · {player.name} ({player.cls})"
        campaign_title = self.campaign_guide.lstrip("# ").splitlines()[0][:50].strip()

        print(f"\n{'═'*60}")
        print(f"  {campaign_title}")
        print(f"  {party_line}")
        print(f"{'═'*60}\n")

        # ── Scene loop ────────────────────────────────────────────────────────
        done = False

        while not done:

            # ── DM narrates ───────────────────────────────────────────────────
            print(f"┌─ Dungeon Master  (Scene {scene})")
            print("│")
            print("│  ", end="")

            try:
                dm_result = await stream(
                    model=self.dm_model,
                    system_prompt=dm_system,
                    messages=dm_history,
                )
            except (KeyboardInterrupt, asyncio.CancelledError):
                print("\n│")
                try:
                    inject = await loop.run_in_executor(None, lambda: input("  ↳ inject ('q' to quit): "))
                except (EOFError, KeyboardInterrupt):
                    inject = "q"
                print()
                if not inject.strip() or inject.strip().lower() == "q":
                    done = True
                    break
                _update_history(dm_history, player.name, "Dungeon Master", inject.strip())
                continue

            dm_text_raw = dm_result["text"]
            dm_ended    = bool(_END_RE.search(dm_text_raw))
            dm_text     = _strip_end(dm_text_raw) if dm_ended else dm_text_raw
            total_cost += dm_result["cost_usd"]

            dm_footer = f"{dm_result['latency_ms']:.0f}ms · ${dm_result['cost_usd']:.5f}"
            if dm_ended:
                dm_footer += "  ↳ ended adventure"
            print("│")
            print(f"└─ {dm_footer}\n")

            dm_history.append({"role": "assistant", "content": dm_text})
            for char in companion_chars:
                _update_history(party_histories[char.name], "Dungeon Master", char.name, dm_text)
            transcript.append({"speaker": "Dungeon Master", "content": dm_text, "scene": scene})

            if dm_ended:
                done = True
                break

            # ── Companions act ────────────────────────────────────────────────
            party_actions: list[tuple[str, str]] = []

            for agent, char in zip(companion_agents, companion_chars):
                comp_system = _companion_system(agent, char)
                history     = party_histories[char.name]

                print(f"┌─ {char.name}  ({char.race} {char.cls})")
                print("│")
                print("│  ", end="")

                try:
                    comp_result = await stream(
                        model=agent.model,
                        system_prompt=comp_system,
                        messages=history,
                    )
                except (KeyboardInterrupt, asyncio.CancelledError):
                    print("\n│")
                    try:
                        inject = await loop.run_in_executor(None, lambda: input("  ↳ inject ('q' to quit): "))
                    except (EOFError, KeyboardInterrupt):
                        inject = "q"
                    print()
                    if not inject.strip() or inject.strip().lower() == "q":
                        done = True
                        break
                    for c in companion_chars:
                        _update_history(party_histories[c.name], player.name, c.name, inject.strip())
                    _update_history(dm_history, player.name, "Dungeon Master", inject.strip())
                    continue

                comp_text       = comp_result["text"]
                roll_str        = roll_action(char, comp_text)
                action_with_roll = f"{comp_text}\n{roll_str}"
                total_cost     += comp_result["cost_usd"]

                print("│")
                print(f"└─ {comp_result['latency_ms']:.0f}ms · ${comp_result['cost_usd']:.5f}  ·  {roll_str}\n")

                _update_history(party_histories[char.name], char.name, char.name, action_with_roll)
                for other in companion_chars:
                    if other.name != char.name:
                        _update_history(party_histories[other.name], char.name, other.name, action_with_roll)

                party_actions.append((char.name, action_with_roll))
                transcript.append({"speaker": char.name, "content": action_with_roll, "scene": scene})

            if done:
                break

            # ── Human acts ────────────────────────────────────────────────────
            print(f"┌─ {player.name} (you)  ({player.race} {player.cls})")
            print("│")

            human_action = await _prompt_human_action(player, dm_text)

            if not human_action or human_action.lower() == "q":
                print("│")
                print("└─\n")
                done = True
                break

            human_roll          = roll_action(player, human_action)
            action_with_roll    = f"{human_action}\n{human_roll}"

            print("│")
            print(f"└─  {human_roll}\n")

            for char in companion_chars:
                _update_history(party_histories[char.name], player.name, char.name, action_with_roll)

            party_actions.append((player.name, action_with_roll))
            transcript.append({"speaker": player.name, "content": action_with_roll, "scene": scene})

            # Batch all party actions into DM's next user message
            for name, action in party_actions:
                _update_history(dm_history, name, "Dungeon Master", action)

            # Save after each completed scene
            if self.save_path:
                _write_save(
                    self.save_path, scene, total_cost, player,
                    companion_chars, companion_agents,
                    dm_history, party_histories, transcript,
                )

            scene += 1

        print(f"{'═'*60}")
        print(f"  Total cost: ${total_cost:.5f}  ·  Scenes: {scene - 1}")
        print(f"{'═'*60}\n")
