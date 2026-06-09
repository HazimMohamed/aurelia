"""
Agent provisioning — creation and teardown.

Single source of truth for standing up an Aurelia agent on disk:
    create_agent()            — permanent production agent
    create_ephemeral_agent()  — temporary experiment agent (exp-{base}-{hex})
    destroy_ephemeral_agent() — full teardown of an ephemeral agent

Constitutions are loaded from aurelia/constitution/{name}.md, not hardcoded here.

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

from ..config import (
    AGENT_HOME_BASE,
    AGENT_DATA_BASE,
    AGENT_RUN_BASE,
    GLOBAL_CONFIG_PATH,
    AgentConfig,
    MODEL_SONNET,
)
from ..agent.budget import _get_week_start

_CONSTITUTION_DIR = Path(__file__).parent.parent.parent / "constitution"
_REPO_ROOT = Path(__file__).parent.parent.parent


# ── Seed memory ────────────────────────────────────────────────────────────────


@dataclass
class SeedKarma:
    """Artificial memory to inject before an agent's first cycle."""

    memory_core: list[dict] = field(default_factory=list)
    episodes: list[dict] = field(default_factory=list)
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
    Load identity for agent_name from aurelia/constitution/{agent_name}.md.
    This is the agent's mission and character — not the plane mechanics.
    Falls back to a minimal default if the file doesn't exist.
    custom overrides everything.
    """
    if custom:
        return custom

    path = _CONSTITUTION_DIR / f"{agent_name}.md"
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
    data_dir: Path,
    agent_name: str,
    display_name: str,
    constitution: str,
    model: str,
    overwrite: bool = False,
) -> None:
    # Agent-owned workspace
    (home / "room").mkdir(parents=True, exist_ok=True)

    # Infra-managed data
    for d in ["memory/extended", "akasha", "constitution", "identity"]:
        (data_dir / d).mkdir(parents=True, exist_ok=True)

    memory_core = data_dir / "memory/core.jsonl"
    if not memory_core.exists():
        memory_core.touch()

    def write(path: Path, content: str) -> None:
        if overwrite or not path.exists():
            path.write_text(content, encoding="utf-8")

    write(data_dir / "constitution/identity.md", constitution)

    write(
        data_dir / "agent.json",
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
        data_dir / "identity/character.md",
        f"# Character\n\n"
        f"This is {display_name}'s character file. It will be populated over time "
        f"through interactions and bardo reflections.\n\n"
        f"Initial state: blank slate within the constraints of the constitution.",
    )
    write(
        data_dir / "identity/contract.md",
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
        data_dir / "identity/values.md",
        f"# Values\n\n"
        f"These values guide {display_name}'s behavior within its domain.\n\n"
        f"- Honesty over comfort\n"
        f"- Depth over performance\n"
        f"- Memory over repetition\n"
        f"- Presence over agenda",
    )


def _inject_seed_karma(home: Path, data_dir: Path, agent_name: str, seed: SeedKarma) -> None:
    ts = datetime.now(timezone.utc).isoformat()

    if seed.memory_core:
        core_path = data_dir / "memory/core.jsonl"
        with core_path.open("a", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                for entry in seed.memory_core:
                    entry.setdefault("ts", ts)
                    entry.setdefault("type", "memory_flag")
                    entry.setdefault("tier", "core")
                    f.write(json.dumps(entry) + "\n")
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    if seed.episodes:
        path = data_dir / "memory/extended" / f"{agent_name}-seed.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for entry in seed.episodes:
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


def _create_budget_file(data_dir: Path) -> None:
    from ..agent.budget import DEFAULT_HEARTBEAT_WEEKLY_BUDGET, save_budget
    path = data_dir / "budget.json"
    if not path.exists():
        save_budget(data_dir, {
            "week_start": _get_week_start(),
            "tokens_used": 0,
            "status": "active",
            "heartbeat_weekly_budget": DEFAULT_HEARTBEAT_WEEKLY_BUDGET,
            "heartbeat_cycles": {},
        })



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
    try:
        subprocess.run(["usermod", "-aG", "aurelia_agents", name], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        pass  # group may not exist in dev


def _destroy_linux_user(name: str) -> None:
    if not _user_exists(name):
        return
    subprocess.run(["userdel", name], check=True, capture_output=True)


def _chown(name: str, home: Path, data_dir: Path, run_dir: Path) -> None:
    def _run(cmd: list[str]) -> None:
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            print(f"[provisioning] WARNING: {' '.join(cmd)!r} failed: {result.stderr.decode().strip()}")

    # constitution/ and identity/ — owned by aurelia service, readable by aurelia_admin
    for d in ("constitution", "identity"):
        p = data_dir / d
        if p.exists():
            _run(["chown", "-R", "aurelia:aurelia_admin", str(p)])
            _run(["chmod", "-R", "640", str(p)])
            _run(["chmod", "750", str(p)])  # directory itself needs x

    # room/ and scratch/ — agent + aurelia_admin, 770 (bash_exec writes here)
    for d in ("room",):
        p = home / d
        if p.exists():
            _run(["chown", "-R", f"{name}:aurelia_admin", str(p)])
            _run(["chmod", "-R", "770", str(p)])

    # data_dir tree — blanket chown first so root-created files get corrected
    _run(["chown", "-R", f"{name}:aurelia_admin", str(data_dir)])

    # data_dir and memory/ — 750 (agent rw, aurelia_admin r, others none)
    for d in (data_dir, data_dir / "memory"):
        if d.exists():
            _run(["chmod", "750", str(d)])

    # core.jsonl and budget.json — 640 (agent rw, aurelia_admin r)
    for p in (data_dir / "memory" / "core.jsonl", data_dir / "budget.json"):
        if p.exists():
            _run(["chmod", "640", str(p)])

    # akasha/ and extended/ — 750 (Manas rw, aurelia_admin r, not in bash_exec ns)
    for d in (data_dir / "akasha", data_dir / "memory" / "extended"):
        if d.exists():
            _run(["chmod", "-R", "750", str(d)])

    # run_dir — agent:aurelia_admin, setgid so manas.sock inherits aurelia_admin group
    _run(["chown", "-R", f"{name}:aurelia_admin", str(run_dir)])
    _run(["chmod", "2750", str(run_dir)])  # setgid + 750


MANAS_LAUNCHER = "/opt/aurelia/bin/manas-launch"


def _sudoers_entry(name: str) -> str:
    return f"%aurelia_admin ALL = ({name}) NOPASSWD,SETENV: {MANAS_LAUNCHER} {name}"


def _add_to_sudoers(name: str) -> None:
    """Add agent to sudoers so aurelia_admin members can launch Manas as this user."""
    sudoers_path = Path("/etc/sudoers.d/aurelia")
    if not sudoers_path.exists():
        return
    content = sudoers_path.read_text()
    entry = _sudoers_entry(name)
    if entry in content:
        return
    # Remove any old broad entry for this agent (aurelia ALL = (name) NOPASSWD: /bin/bash)
    lines = [l for l in content.splitlines()
             if not (f"({name})" in l and "/bin/bash" in l)]
    new_content = "\n".join(lines).rstrip() + f"\n{entry}\n"
    sudoers_path.write_text(new_content)


def _remove_from_sudoers(name: str) -> None:
    """Remove agent from sudoers."""
    sudoers_path = Path("/etc/sudoers.d/aurelia")
    if not sudoers_path.exists():
        return
    content = sudoers_path.read_text()
    entry = _sudoers_entry(name)
    lines = [l for l in content.splitlines()
             if l != entry and not (f"({name})" in l and "/bin/bash" in l)]
    sudoers_path.write_text("\n".join(lines) + "\n")


# ── Shared provisioning core ───────────────────────────────────────────────────


def _provision(name: str) -> None:
    """
    Register an agent with the OS: Linux user, groups, directories, sudoers, permissions.
    OS-level primitives only — nothing about workspace content (that's standup's job).
    """
    home = AGENT_HOME_BASE / name
    data_dir = AGENT_DATA_BASE / name
    run_dir = AGENT_RUN_BASE / name

    _create_linux_user(name)
    home.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)
    _add_to_sudoers(name)
    _chown(name, home, data_dir, run_dir)


def _standup_agent(
    name: str,
    display_name: str,
    constitution: str,
    model: str,
    seed_karma: SeedKarma | None,
    overwrite: bool,
) -> str:
    """
    Initialize agent workspace: filesystem content, venv, budget, config token.
    Assumes the agent has already been provisioned (OS primitives exist).
    Returns token.
    """
    home = AGENT_HOME_BASE / name
    data_dir = AGENT_DATA_BASE / name
    token = secrets.token_hex(32)

    _setup_filesystem(home, data_dir, name, display_name, constitution, model, overwrite=overwrite)
    _setup_agent_venv(home, name)
    if seed_karma:
        _inject_seed_karma(home, data_dir, name, seed_karma)
    _create_budget_file(data_dir)
    _update_config(name, token)

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
                      constitution at constitution/{name}.md.
        constitution: Override the constitution. If None, loads from constitution/.
        seed_karma:   Artificial memory to inject before the first cycle.
        model:        LLM model for the agent.

    Returns:
        AgentConfig. Caller must trigger a runtime registry reload.
    """
    _provision(name)
    _standup_agent(
        name=name,
        display_name=name.capitalize(),
        constitution=load_constitution(name, constitution),
        model=model,
        seed_karma=seed_karma,
        overwrite=False,
    )
    # Re-run chown after standup — _setup_filesystem creates files as root
    _chown(name, AGENT_HOME_BASE / name, AGENT_DATA_BASE / name, AGENT_RUN_BASE / name)
    return AgentConfig(name=name, model=model)



def destroy_agent(name: str) -> None:
    """Permanently destroy a named agent, removing their home dir and all config."""
    _remove_from_sudoers(name)
    _remove_from_config(name)
    _destroy_linux_user(name)
    for d in (AGENT_HOME_BASE / name, AGENT_DATA_BASE / name, AGENT_RUN_BASE / name):
        if d.exists():
            shutil.rmtree(d)


def reset_agent(
    name: str,
    model: str = MODEL_SONNET,
    constitution: str | None = None,
) -> AgentConfig:
    """Destroy and recreate an agent from scratch — all memory wiped, identity reseeded.

    Returns the new AgentConfig. Caller must trigger a runtime registry reload.
    """
    destroy_agent(name)
    _provision(name)
    _standup_agent(
        name=name,
        display_name=name.capitalize(),
        constitution=load_constitution(name, constitution),
        model=model,
        seed_karma=None,
        overwrite=True,
    )
    _chown(name, AGENT_HOME_BASE / name, AGENT_DATA_BASE / name, AGENT_RUN_BASE / name)
    return AgentConfig(name=name, model=model)


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
                      Used to load the constitution from constitution/.
        constitution: Override the constitution.
        seed_karma:   Artificial memory to inject before the first cycle.
        model:        LLM model for the agent.

    Returns:
        EphemeralAgent. Caller must trigger a runtime registry reload.
    """
    name = f"exp-{base_agent}-{secrets.token_hex(4)}"
    _provision(name)
    token = _standup_agent(
        name=name,
        display_name=base_agent.capitalize(),
        constitution=load_constitution(base_agent, constitution),
        model=model,
        seed_karma=seed_karma,
        overwrite=True,
    )
    _chown(name, AGENT_HOME_BASE / name, AGENT_DATA_BASE / name, AGENT_RUN_BASE / name)
    config = AgentConfig(name=name, model=model, description=f"Ephemeral: {base_agent}")
    return EphemeralAgent(name=name, base_agent=base_agent, config=config, token=token)


def destroy_ephemeral_agent(agent: EphemeralAgent) -> None:
    """
    Tear down an ephemeral agent completely.

    Removes Linux user, home directory, run dir, data dir, and config token.
    Caller should trigger a runtime registry reload afterwards.

    Requires root privileges.
    """
    _remove_from_config(agent.name)
    _remove_from_sudoers(agent.name)
    _destroy_linux_user(agent.name)

    for d in (AGENT_HOME_BASE / agent.name, AGENT_DATA_BASE / agent.name, AGENT_RUN_BASE / agent.name):
        if d.exists():
            shutil.rmtree(d)
