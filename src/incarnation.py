"""Incarnation lifecycle: spawn, load, naming."""

from __future__ import annotations

import os
import random
import re
import shutil
from pathlib import Path
from typing import Optional

import anthropic

from config import AgentConfig, MODEL_HAIKU
from transcript import (
    read_entries,
    write_incarnation_start,
    transcript_to_messages,
)


def _get_existing_incarnation_names(karma_dir: Path) -> list[str]:
    """Return all incarnation directory names under karma/."""
    names = []
    if not karma_dir.exists():
        return names
    for entry in karma_dir.iterdir():
        # Skip 'current' symlink, 'episodic', 'semantic' dirs
        if entry.name in ("current", "episodic", "semantic"):
            continue
        if entry.is_dir():
            names.append(entry.name)
    return names


def generate_incarnation_name(agent_name: str, karma_dir: Path) -> str:
    """Call Haiku to generate a unique adjective-noun pair, then build full name."""
    existing = _get_existing_incarnation_names(karma_dir)
    existing_str = ", ".join(existing) if existing else "none"

    client = anthropic.Anthropic()
    prompt = (
        f"Generate a unique two-word name for a new {agent_name} agent incarnation.\n"
        f"Format: adjective-noun (wandering-river, quiet-moon, bright-stone).\n"
        f"Already used: {existing_str}. Return only the hyphenated name, nothing else."
    )

    response = client.messages.create(
        model=MODEL_HAIKU,
        max_tokens=32,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip().lower()
    # Sanitize: keep only letters and hyphens
    raw = re.sub(r"[^a-z\-]", "", raw)
    # Ensure it's adjective-noun format
    parts = raw.split("-")
    if len(parts) >= 2:
        adjective = parts[0]
        noun = parts[1]
    else:
        adjective = raw or "silent"
        noun = "dawn"

    suffix = random.randint(10, 99)
    return f"{agent_name}-{adjective}-{noun}-{suffix}"


def get_active_incarnation(config: AgentConfig) -> Optional[str]:
    """Return the active incarnation name via current symlink, or None."""
    symlink = config.current_symlink
    if symlink.is_symlink():
        target = symlink.resolve()
        if target.exists():
            return target.name
        # Dangling symlink — remove it
        symlink.unlink()
    return None


def spawn_incarnation(config: AgentConfig) -> str:
    """Create a new incarnation directory, set current symlink, write start entry."""
    incarnation_name = generate_incarnation_name(config.name, config.karma_dir)
    incarnation_dir = config.karma_dir / incarnation_name
    scratch_dir = incarnation_dir / "scratch"

    incarnation_dir.mkdir(parents=True, exist_ok=True)
    scratch_dir.mkdir(parents=True, exist_ok=True)

    transcript_path = incarnation_dir / "transcript.jsonl"
    write_incarnation_start(transcript_path, incarnation_name, cycle=0)

    # Update current symlink
    symlink = config.current_symlink
    if symlink.is_symlink() or symlink.exists():
        symlink.unlink()
    symlink.symlink_to(incarnation_dir)

    return incarnation_name


def load_incarnation(config: AgentConfig, incarnation_name: str) -> dict:
    """Load incarnation state: transcript entries and current cycle count."""
    incarnation_dir = config.karma_dir / incarnation_name
    transcript_path = incarnation_dir / "transcript.jsonl"
    entries = read_entries(transcript_path)

    # Cycle = number of human_message entries
    cycle = sum(1 for e in entries if e.get("type") == "human_message")

    return {
        "name": incarnation_name,
        "dir": incarnation_dir,
        "transcript_path": transcript_path,
        "entries": entries,
        "cycle": cycle,
    }


def get_or_spawn_incarnation(config: AgentConfig) -> dict:
    """Get active incarnation or spawn a new one. Returns incarnation state dict."""
    active_name = get_active_incarnation(config)
    if active_name:
        return load_incarnation(config, active_name)
    incarnation_name = spawn_incarnation(config)
    return load_incarnation(config, incarnation_name)


def get_incarnation_by_id(config: AgentConfig, incarnation_id: str) -> dict:
    """Load a specific incarnation by name. Raises ValueError if not found."""
    incarnation_dir = config.karma_dir / incarnation_id
    if not incarnation_dir.exists():
        raise ValueError(f"Incarnation '{incarnation_id}' not found for agent '{config.name}'")
    return load_incarnation(config, incarnation_id)
