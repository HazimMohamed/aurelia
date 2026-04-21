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

# Budget defaults per agent (weekly tokens)
WEEKLY_BUDGET_DEFAULTS = {
    "personal": 500_000,
    "cooking": 300_000,
    "finance": 200_000,
    "mayor": 150_000,
    "janitor": 1_000_000,
}
DEFAULT_WEEKLY_BUDGET = 300_000

# Bardo timeout defaults (hours)
BARDO_TIMEOUT_DEFAULTS = {
    "personal": 120,  # 5 days
}
DEFAULT_BARDO_TIMEOUT_HOURS = 48

# Heartbeat defaults (hours)
HEARTBEAT_INTERVAL_DEFAULTS = {
    "personal": 24,
    "cooking": 2,
    "finance": 6,
    "mayor": 6,
    "janitor": None,  # on-demand only
}
DEFAULT_HEARTBEAT_INTERVAL_HOURS = 2


@dataclass
class BardoConfig:
    model: str = MODEL_SONNET
    timeout_hours: int = DEFAULT_BARDO_TIMEOUT_HOURS


@dataclass
class AgentConfig:
    name: str
    model: str = MODEL_SONNET
    description: str = ""
    bardo: BardoConfig = field(default_factory=BardoConfig)
    weekly_budget_tokens: int = DEFAULT_WEEKLY_BUDGET
    heartbeat_interval_hours: Optional[float] = None
    discord_channel: str = ""
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

    @property
    def episodic_core_dir(self) -> Path:
        return self.karma_dir / "episodic" / "core"

    @property
    def semantic_core_path(self) -> Path:
        return self.karma_dir / "semantic" / "core.jsonl"

    @property
    def semantic_extended_dir(self) -> Path:
        return self.karma_dir / "semantic" / "extended"


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

    # Resolve bardo model and timeout
    bardo_data = agent_data.get("bardo") or defaults.get("bardo") or {}
    bardo_model = bardo_data.get("model") or MODEL_SONNET
    bardo_timeout = (
        bardo_data.get("timeout_hours")
        or BARDO_TIMEOUT_DEFAULTS.get(agent_name)
        or DEFAULT_BARDO_TIMEOUT_HOURS
    )
    bardo_cfg = BardoConfig(model=bardo_model, timeout_hours=int(bardo_timeout))

    # Resolve weekly budget
    weekly_budget = (
        agent_data.get("weekly_budget_tokens")
        or defaults.get("weekly_budget_tokens")
        or WEEKLY_BUDGET_DEFAULTS.get(agent_name)
        or DEFAULT_WEEKLY_BUDGET
    )

    # Resolve heartbeat interval
    heartbeat_hours = (
        agent_data.get("heartbeat_interval_hours")
        or HEARTBEAT_INTERVAL_DEFAULTS.get(agent_name)
        or DEFAULT_HEARTBEAT_INTERVAL_HOURS
    )

    discord_channel = agent_data.get("discord_channel", agent_name)

    return AgentConfig(
        name=agent_name,
        model=model,
        description=agent_data.get("description", ""),
        bardo=bardo_cfg,
        weekly_budget_tokens=int(weekly_budget),
        heartbeat_interval_hours=heartbeat_hours,
        discord_channel=discord_channel,
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
