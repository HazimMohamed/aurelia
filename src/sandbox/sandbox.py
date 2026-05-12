"""
Sandbox pool for Alembic experiments.

Five fixed Linux users (sandbox-1 through sandbox-5) are provisioned once via
provision_sandbox_pool(). Experiments borrow a slot via acquire_sandbox_agent(),
which stands up a fresh agent for that experiment. When done, release_sandbox_agent()
tears it down and returns the slot to the pool.

This avoids the overhead of useradd/userdel per experiment and lets the slots
sit permanently in sudoers with correct permissions.

Usage:
    agent = acquire_sandbox_agent("personal", seed_karma=SEED)
    try:
        ...use agent...
    finally:
        release_sandbox_agent(agent)

One-time setup (run as root):
    sudo aurelia agent reset sandbox
"""

from __future__ import annotations

import fcntl
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from ..samsara.config import AGENT_HOME_BASE, AGENT_DATA_BASE, AGENT_RUN_BASE, AgentConfig, MODEL_SONNET
from ..samsara.provisioning import (
    SeedKarma,
    _provision,
    _standup_agent,
    load_constitution,
)

SANDBOX_POOL_SIZE = 5
SANDBOX_NAMES = [f"sandbox-{i}" for i in range(1, SANDBOX_POOL_SIZE + 1)]
SANDBOX_LOCK_DIR = Path("/var/aurelia/sandbox/locks")
SANDBOX_DIR = Path("/var/aurelia/sandbox")


@dataclass
class SandboxAgent:
    name: str        # e.g. "sandbox-3"
    base_agent: str  # e.g. "personal"
    config: AgentConfig
    token: str
    _lock_file: object = field(repr=False, default=None)
    _lock_path: Path = field(repr=False, default=None)


# ── Pool lock mechanics ────────────────────────────────────────────────────────


def _acquire_slot() -> tuple[str, object, Path]:
    """
    Try each sandbox slot in order. Returns (name, lock_file, lock_path) for the
    first free slot. Raises RuntimeError if all slots are busy.
    """
    SANDBOX_LOCK_DIR.mkdir(parents=True, exist_ok=True)
    for name in SANDBOX_NAMES:
        lock_path = SANDBOX_LOCK_DIR / f"{name}.lock"
        lock_file = open(lock_path, "w")
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return name, lock_file, lock_path
        except BlockingIOError:
            lock_file.close()
    raise RuntimeError("All sandbox slots are busy — try again shortly.")


def _release_slot(lock_file: object) -> None:
    fcntl.flock(lock_file, fcntl.LOCK_UN)
    lock_file.close()


# ── Stand up / tear down ───────────────────────────────────────────────────────


def _standup_sandbox(
    name: str,
    base_agent: str,
    constitution: str,
    model: str,
    seed_karma: SeedKarma | None,
) -> str:
    """Wipe the slot and stand up a fresh agent workspace for a new experiment. Returns token."""
    home = AGENT_HOME_BASE / name
    data_dir = AGENT_DATA_BASE / name
    for d in (home, data_dir):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True, exist_ok=True)
    return _standup_agent(
        name=name,
        display_name=base_agent.capitalize(),
        constitution=constitution,
        model=model,
        seed_karma=seed_karma,
        overwrite=True,
    )


def _teardown_sandbox(agent: SandboxAgent) -> None:
    """Tear down an agent and wipe its slot clean."""
    from ..samsara.provisioning import _remove_from_config

    _remove_from_config(agent.name)

    for d in (AGENT_HOME_BASE / agent.name, AGENT_DATA_BASE / agent.name, AGENT_RUN_BASE / agent.name):
        if d.exists():
            shutil.rmtree(d)


# ── Public API ─────────────────────────────────────────────────────────────────


def acquire_sandbox_agent(
    base_agent: str,
    constitution: str | None = None,
    seed_karma: SeedKarma | None = None,
    model: str = MODEL_SONNET,
) -> SandboxAgent:
    """
    Borrow a sandbox slot from the pool, standing up a fresh agent on it.

    Caller must call release_sandbox_agent() when done — use a try/finally.
    """
    name, lock_file, lock_path = _acquire_slot()

    resolved_constitution = load_constitution(base_agent, constitution)
    token = _standup_sandbox(name, base_agent, resolved_constitution, model, seed_karma)

    config = AgentConfig(name=name, model=model, description=f"Sandbox: {base_agent}")
    return SandboxAgent(
        name=name,
        base_agent=base_agent,
        config=config,
        token=token,
        _lock_file=lock_file,
        _lock_path=lock_path,
    )


def release_sandbox_agent(agent: SandboxAgent) -> None:
    """
    Tear down the agent and return the slot to the pool.

    Safe to call even if acquisition partially failed.
    """
    _teardown_sandbox(agent)

    if agent._lock_file is not None:
        _release_slot(agent._lock_file)


# ── One-time pool provisioning ─────────────────────────────────────────────────


def provision_sandbox_pool(
    base_agent: str = "personal",
    model: str = MODEL_SONNET,
) -> None:
    """
    Provision the sandbox pool: create sandbox-1..sandbox-N Linux users with
    correct permissions and sudoers entries. Safe to re-run.

    Normally invoked via: sudo aurelia agent reset sandbox
    """
    SANDBOX_DIR.mkdir(parents=True, exist_ok=True)
    SANDBOX_LOCK_DIR.mkdir(parents=True, exist_ok=True)
    for cmd in [
        ["chown", "aurelia:aurelia_admin", str(SANDBOX_DIR)],
        ["chmod", "770", str(SANDBOX_DIR)],
        ["chown", "aurelia:aurelia_admin", str(SANDBOX_LOCK_DIR)],
        ["chmod", "770", str(SANDBOX_LOCK_DIR)],
    ]:
        r = subprocess.run(cmd, capture_output=True)
        if r.returncode != 0:
            print(f"[sandbox] WARNING: {' '.join(cmd)}: {r.stderr.decode().strip()}")

    for name in SANDBOX_NAMES:
        print(f"  Provisioning {name}...")
        _provision(name)
        print(f"  {name} ready.")

    print(f"  Sandbox pool ({SANDBOX_POOL_SIZE} slots) provisioned.")
