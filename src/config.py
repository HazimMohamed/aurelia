"""Config loading and AgentConfig dataclass."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

GLOBAL_CONFIG_PATH = Path("/var/aurelia/config.json")
AGENT_HOME_BASE = Path("/home")

# Model IDs
MODEL_HAIKU = "claude-haiku-4-5-20251001"
MODEL_SONNET = "claude-sonnet-4-6"
MODEL_OPUS = "claude-opus-4-6"


@dataclass
class BardoConfig:
    model: str = MODEL_SONNET


@dataclass
class AgentConfig:
    name: str
    model: str = MODEL_SONNET
    description: str = ""
    bardo: BardoConfig = field(default_factory=BardoConfig)
    home: Path = field(init=False)

    def __post_init__(self) -> None:
        self.home = AGENT_HOME_BASE / self.name

    @property
    def identity_dir(self) -> Path:
        return self.home / "identity"

    @property
    def karma_dir(self) -> Path:
        return self.home / "karma"

    @property
    def akasha_dir(self) -> Path:
        return self.home / "akasha"

    @property
    def room_dir(self) -> Path:
        return self.home / "room"

    @property
    def dharma_dir(self) -> Path:
        return self.home / "dharma"

    @property
    def constitution_path(self) -> Path:
        return self.dharma_dir / "constitution.md"

    @property
    def current_symlink(self) -> Path:
        return self.karma_dir / "current"

    @property
    def episodic_extended_dir(self) -> Path:
        return self.karma_dir / "episodic" / "extended"


def load_global_config() -> dict:
    """Load /var/aurelia/config.json, return empty dict if missing."""
    if GLOBAL_CONFIG_PATH.exists():
        with GLOBAL_CONFIG_PATH.open() as f:
            return json.load(f)
    return {}


def load_agent_config(agent_name: str) -> AgentConfig:
    """Load per-agent config, falling back to global defaults."""
    global_cfg = load_global_config()
    defaults = global_cfg.get("defaults", {})

    agent_json_path = AGENT_HOME_BASE / agent_name / "agent.json"

    agent_data: dict = {}
    if agent_json_path.exists():
        with agent_json_path.open() as f:
            agent_data = json.load(f)

    # Resolve model: agent.json > global defaults > hardcoded default
    model = agent_data.get("model") or defaults.get("model") or MODEL_SONNET

    # Resolve bardo model
    bardo_data = agent_data.get("bardo") or defaults.get("bardo") or {}
    bardo_model = bardo_data.get("model") or MODEL_SONNET
    bardo_cfg = BardoConfig(model=bardo_model)

    return AgentConfig(
        name=agent_name,
        model=model,
        description=agent_data.get("description", ""),
        bardo=bardo_cfg,
    )


def list_known_agents() -> list[str]:
    """Return agent names that have a home dir and agent.json."""
    agents = []
    if not AGENT_HOME_BASE.exists():
        return agents
    for entry in sorted(AGENT_HOME_BASE.iterdir()):
        if entry.is_dir() and (entry / "agent.json").exists():
            agents.append(entry.name)
    return agents
