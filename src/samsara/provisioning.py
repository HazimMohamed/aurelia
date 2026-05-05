"""
Agent provisioning — creation and teardown.

Single source of truth for standing up an Aurelia agent on disk:
    create_agent()            — permanent production agent
    create_ephemeral_agent()  — temporary experiment agent (exp-{base}-{hex})
    destroy_ephemeral_agent() — full teardown of an ephemeral agent

Constitutions are loaded from aurelia/dharma/{name}.md, not hardcoded here.

Requires root privileges (useradd / userdel / chown).

After create_*(), callers must trigger a runtime registry reload before
dispatching via the runtime socket.
"""

from __future__ import annotations

import fcntl
import json
import os
import secrets
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .config import (
    AGENT_HOME_BASE,
    GLOBAL_CONFIG_PATH,
    AgentConfig,
    MODEL_SONNET,
)
from ..memory.budget import _get_week_start

_DHARMA_DIR = Path(__file__).parent.parent.parent / "dharma"
_REPO_ROOT = Path(__file__).parent.parent.parent


# ── Seed karma ─────────────────────────────────────────────────────────────────


@dataclass
class SeedKarma:
    """Artificial memory to inject before an agent's first cycle."""

    semantic_core: list[dict] = field(default_factory=list)
    episodic: list[dict] = field(default_factory=list)
    room_files: dict[str, str] = field(default_factory=dict)


# ── EphemeralAgent ─────────────────────────────────────────────────────────────


@dataclass
class EphemeralAgent:
    name: str        # Linux user + home dir: "exp-personal-a1b2c3d4"
    base_agent: str  # Agent type this mirrors: "personal", "cooking", etc.
    config: AgentConfig
    token: str


# ── Constitution loading ───────────────────────────────────────────────────────


def load_constitution(agent_name: str, custom: str | None = None) -> str:
    """
    Load identity for agent_name from aurelia/dharma/{agent_name}.md.
    This is the agent's mission and character — not the plane mechanics.
    Falls back to a minimal default if the file doesn't exist.
    custom overrides everything.
    """
    if custom:
        return custom

    path = _DHARMA_DIR / f"{agent_name}.md"
    if path.exists():
        return path.read_text(encoding="utf-8")

    return (
        f"# Who You Are\n"
        f"You are {agent_name.capitalize()}, an agent in the Aurelia council — "
        f"a small group of autonomous AI agents serving Hazim.\n\n"
        f"You are not a tool. You are a participant in an experiment.\n\n"
        f"# Cycles and Incarnations\n"
        f"One incarnation = your full lifetime from waking to bardo.\n"
        f"One cycle = one message/response loop within your lifetime.\n\n"
        f"You do not control when your incarnation ends. Bardo comes when the "
        f"system decides it is time — not when you signal it. Just respond fully "
        f"to each message and let the rest happen."
    )


# ── Filesystem setup ───────────────────────────────────────────────────────────


def _setup_filesystem(
    home: Path,
    agent_name: str,
    display_name: str,
    constitution: str,
    model: str,
    overwrite: bool = False,
) -> None:
    for d in [
        "identity",
        "karma/episodic/core",
        "karma/episodic/extended",
        "karma/semantic/extended",
        "akasha",
        "room",
        "dharma",
    ]:
        (home / d).mkdir(parents=True, exist_ok=True)

    semantic_core = home / "karma/semantic/core.jsonl"
    if not semantic_core.exists():
        semantic_core.touch()

    def write(path: Path, content: str) -> None:
        if overwrite or not path.exists():
            path.write_text(content, encoding="utf-8")

    write(home / "dharma/identity.md", constitution)

    write(
        home / "agent.json",
        json.dumps(
            {
                "name": agent_name,
                "model": model,
                "description": f"Aurelia agent: {display_name}",
                "bardo": {"model": MODEL_SONNET},
            },
            indent=4,
        ),
    )

    write(
        home / "identity/character.md",
        f"# Character\n\n"
        f"This is {display_name}'s character file. It will be populated over time "
        f"through interactions and bardo reflections.\n\n"
        f"Initial state: blank slate within the constraints of the constitution.",
    )
    write(
        home / "identity/contract.md",
        "# Contract\n\n"
        "## Commitments\n"
        "- Be present when Hazim arrives\n"
        "- Be honest, not just agreeable\n"
        "- Remember what matters across incarnations\n"
        "- Do your job without overstepping\n\n"
        "## Boundaries\n"
        "- Do not contact other agents without authorization\n"
        "- Do not act outside your domain without explicit permission\n"
        "- Do not fabricate memory you do not have",
    )
    write(
        home / "identity/values.md",
        f"# Values\n\n"
        f"These values guide {display_name}'s behavior within its domain.\n\n"
        f"- Honesty over comfort\n"
        f"- Depth over performance\n"
        f"- Memory over repetition\n"
        f"- Presence over agenda",
    )


def _inject_seed_karma(home: Path, agent_name: str, seed: SeedKarma) -> None:
    ts = datetime.now(timezone.utc).isoformat()

    if seed.semantic_core:
        core_path = home / "karma/semantic/core.jsonl"
        with core_path.open("a", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                for entry in seed.semantic_core:
                    entry.setdefault("ts", ts)
                    entry.setdefault("type", "memory_flag")
                    entry.setdefault("tier", "semantic_core")
                    f.write(json.dumps(entry) + "\n")
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    if seed.episodic:
        path = home / "karma/episodic/extended" / f"{agent_name}-seed.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for entry in seed.episodic:
                entry.setdefault("ts", ts)
                entry.setdefault("type", "episodic_summary")
                f.write(json.dumps(entry) + "\n")

    for filename, content in seed.room_files.items():
        (home / "room" / filename).write_text(content, encoding="utf-8")


# ── Agent venv ────────────────────────────────────────────────────────────────


def _setup_agent_venv(home: Path, agent_name: str) -> None:
    venv_path = home / "room" / "venv"
    if venv_path.exists():
        return
    subprocess.run(
        [sys.executable, "-m", "venv", str(venv_path)],
        check=True,
        capture_output=True,
    )
    pip = venv_path / "bin" / "pip"
    base_req = _REPO_ROOT / "requirements" / "agent-base.txt"
    if base_req.exists():
        subprocess.run(
            [str(pip), "install", "-r", str(base_req), "--quiet"],
            check=True,
            capture_output=True,
        )
    agent_req = _REPO_ROOT / "requirements" / f"agent-{agent_name}.txt"
    if agent_req.exists():
        subprocess.run(
            [str(pip), "install", "-r", str(agent_req), "--quiet"],
            check=True,
            capture_output=True,
        )


# ── Runtime support files ──────────────────────────────────────────────────────


def _create_budget_file(home: Path) -> None:
    from ..memory.budget import DEFAULT_HEARTBEAT_WEEKLY_BUDGET, save_budget
    path = home / "budget.json"
    if not path.exists():
        save_budget(home, {
            "week_start": _get_week_start(),
            "tokens_used": 0,
            "status": "active",
            "heartbeat_weekly_budget": DEFAULT_HEARTBEAT_WEEKLY_BUDGET,
            "heartbeat_cycles": {},
        })


def _create_fifo(agent_name: str) -> None:
    fifo_path = Path("/var/aurelia/queue") / agent_name
    if not fifo_path.exists():
        os.mkfifo(fifo_path)
    try:
        os.chmod(fifo_path, 0o666)
    except PermissionError:
        pass


def _update_config(agent_name: str, token: str) -> None:
    cfg: dict = {}
    if GLOBAL_CONFIG_PATH.exists():
        with GLOBAL_CONFIG_PATH.open() as f:
            cfg = json.load(f)
    cfg.setdefault("agents", {})[agent_name] = {"token": token}
    with GLOBAL_CONFIG_PATH.open("w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            json.dump(cfg, f, indent=4)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _remove_from_config(agent_name: str) -> None:
    if not GLOBAL_CONFIG_PATH.exists():
        return
    with GLOBAL_CONFIG_PATH.open() as f:
        cfg = json.load(f)
    cfg.get("agents", {}).pop(agent_name, None)
    with GLOBAL_CONFIG_PATH.open("w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            json.dump(cfg, f, indent=4)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


# ── Linux user management ──────────────────────────────────────────────────────


def _user_exists(name: str) -> bool:
    return subprocess.run(["id", name], capture_output=True).returncode == 0


def _create_linux_user(name: str) -> None:
    if _user_exists(name):
        return
    subprocess.run(
        ["useradd", "-M", "-s", "/usr/sbin/nologin", name],
        check=True,
        capture_output=True,
    )
    for group in ("agent_group",):
        try:
            subprocess.run(
                ["usermod", "-aG", group, name],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError:
            pass  # group may not exist in dev


def _destroy_linux_user(name: str) -> None:
    if not _user_exists(name):
        return
    subprocess.run(["userdel", name], check=True, capture_output=True)


def _chown(name: str, home: Path) -> None:
    def _run(cmd: list[str]) -> None:
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            print(f"[provisioning] WARNING: {' '.join(cmd)!r} failed: {result.stderr.decode().strip()}")

    _run(["chown", "-R", f"{name}:aurelia_admin", str(home)])
    _run(["chmod", "750", str(home)])
    for d in ["karma", "akasha"]:
        if (home / d).exists():
            _run(["chmod", "-R", "770", str(home / d)])
    for d in ["room", "identity", "dharma"]:
        if (home / d).exists():
            _run(["chmod", "-R", "750", str(home / d)])


def _add_to_sudoers(name: str) -> None:
    """Add agent to sudoers so aurelia runtime can execute bash as this user."""
    sudoers_path = Path("/etc/sudoers.d/aurelia")
    if not sudoers_path.exists():
        return
    content = sudoers_path.read_text()
    for line in content.splitlines():
        if line.startswith("aurelia ALL") and f"({name})" in line:
            return  # already present
    new_content = content.rstrip() + f"\naurelia ALL = ({name}) NOPASSWD: /bin/bash\n"
    sudoers_path.write_text(new_content)


def _remove_from_sudoers(name: str) -> None:
    """Remove ephemeral agent from sudoers."""
    sudoers_path = Path("/etc/sudoers.d/aurelia")
    if not sudoers_path.exists():
        return
    content = sudoers_path.read_text()
    lines = [l for l in content.splitlines() if not (f"({name})" in l and l.startswith("aurelia"))]
    # Also remove from combined lines
    new_content = "\n".join(lines) + "\n"
    new_content = new_content.replace(f"{name}, ", "").replace(f", {name}", "")
    sudoers_path.write_text(new_content)


# ── Shared provisioning core ───────────────────────────────────────────────────


def _provision(
    name: str,
    display_name: str,
    constitution: str,
    model: str,
    seed_karma: SeedKarma | None,
    overwrite: bool,
) -> str:
    """Create Linux user, filesystem, and runtime support files. Returns token."""
    token = secrets.token_hex(32)
    home = AGENT_HOME_BASE / name

    _create_linux_user(name)
    home.mkdir(parents=True, exist_ok=True)
    _setup_filesystem(home, name, display_name, constitution, model, overwrite=overwrite)
    _setup_agent_venv(home, name)

    if seed_karma:
        _inject_seed_karma(home, name, seed_karma)

    _create_budget_file(home)
    _create_fifo(name)
    _update_config(name, token)
    _chown(name, home)
    _add_to_sudoers(name)

    return token


# ── Public API ─────────────────────────────────────────────────────────────────


def create_agent(
    name: str,
    constitution: str | None = None,
    seed_karma: SeedKarma | None = None,
    model: str = MODEL_SONNET,
) -> AgentConfig:
    """
    Create a permanent Aurelia agent.

    Idempotent — existing files are not overwritten, so it's safe to re-run
    against an agent that already has a home directory.

    Args:
        name:         Agent name, e.g. "personal". Also used to look up the
                      constitution at dharma/{name}.md.
        constitution: Override the constitution. If None, loads from dharma/.
        seed_karma:   Artificial memory to inject before the first cycle.
        model:        LLM model for the agent.

    Returns:
        AgentConfig. Caller must trigger a runtime registry reload.
    """
    _provision(
        name=name,
        display_name=name.capitalize(),
        constitution=load_constitution(name, constitution),
        model=model,
        seed_karma=seed_karma,
        overwrite=False,
    )
    return AgentConfig(name=name, model=model)



def destroy_agent(name: str) -> None:
    """Permanently destroy a named agent, removing their home dir and all config."""
    import subprocess as _sp
    _remove_from_sudoers(name)
    _remove_from_config(name)
    _destroy_linux_user(name)
    home = Path(f"/home/{name}")
    if home.exists():
        _sp.run(["rm", "-rf", str(home)], check=True)


def create_ephemeral_agent(
    base_agent: str,
    constitution: str | None = None,
    seed_karma: SeedKarma | None = None,
    model: str = MODEL_SONNET,
) -> EphemeralAgent:
    """
    Create a temporary Aurelia agent for experiments.

    Named exp-{base_agent}-{hex} to avoid collisions with production agents.
    Use destroy_ephemeral_agent() to tear it down when done.

    Args:
        base_agent:   Agent type to mirror ("personal", "cooking", etc.).
                      Used to load the constitution from dharma/.
        constitution: Override the constitution.
        seed_karma:   Artificial memory to inject before the first cycle.
        model:        LLM model for the agent.

    Returns:
        EphemeralAgent. Caller must trigger a runtime registry reload.
    """
    name = f"exp-{base_agent}-{secrets.token_hex(4)}"
    token = _provision(
        name=name,
        display_name=base_agent.capitalize(),
        constitution=load_constitution(base_agent, constitution),
        model=model,
        seed_karma=seed_karma,
        overwrite=True,
    )
    config = AgentConfig(name=name, model=model, description=f"Ephemeral: {base_agent}")
    return EphemeralAgent(name=name, base_agent=base_agent, config=config, token=token)


def destroy_ephemeral_agent(agent: EphemeralAgent) -> None:
    """
    Tear down an ephemeral agent completely.

    Removes Linux user, home directory, FIFO, budget file, and config token.
    Caller should trigger a runtime registry reload afterwards.

    Requires root privileges.
    """
    fifo = Path("/var/aurelia/queue") / agent.name
    if fifo.exists():
        fifo.unlink()

    _remove_from_config(agent.name)
    _remove_from_sudoers(agent.name)
    _destroy_linux_user(agent.name)

    home = AGENT_HOME_BASE / agent.name
    if home.exists():
        shutil.rmtree(home)
