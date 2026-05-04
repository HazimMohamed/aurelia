"""
Sandbox pool for Alembic experiments.

Five fixed Linux users (sandbox-1 through sandbox-5) are pre-provisioned once
via provision_sandbox_pool(). Experiments borrow a slot via acquire_sandbox_agent(),
use it, then return it via release_sandbox_agent() which wipes and resets the home.

This avoids the overhead of useradd/userdel per experiment and lets the slots
sit permanently in sudoers with correct permissions.

Usage:
    agent = acquire_sandbox_agent("personal", seed_karma=SEED)
    try:
        ...use agent...
    finally:
        release_sandbox_agent(agent)

One-time setup (run as root):
    sudo python3 -c "from src.test.sandbox import provision_sandbox_pool; provision_sandbox_pool()"
"""

from __future__ import annotations

import fcntl
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from ..samsara.config import AGENT_HOME_BASE, AgentConfig, MODEL_SONNET
from ..samsara.provisioning import (
    SeedKarma,
    _add_to_sudoers,
    _chown,
    _create_budget_file,
    _create_fifo,
    _create_linux_user,
    _inject_seed_karma,
    _setup_filesystem,
    _update_config,
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


# ── Home reset ─────────────────────────────────────────────────────────────────


def _reset_sandbox_home(
    name: str,
    base_agent: str,
    constitution: str,
    model: str,
    seed_karma: SeedKarma | None,
) -> None:
    """Wipe existing home content and re-provision for the new experiment."""
    home = AGENT_HOME_BASE / name
    if home.exists():
        shutil.rmtree(home)
    home.mkdir(parents=True, exist_ok=True)
    _setup_filesystem(home, name, base_agent.capitalize(), constitution, model, overwrite=True)
    if seed_karma:
        _inject_seed_karma(home, name, seed_karma)
    _chown(name, home)


# ── Public API ─────────────────────────────────────────────────────────────────


def acquire_sandbox_agent(
    base_agent: str,
    constitution: str | None = None,
    seed_karma: SeedKarma | None = None,
    model: str = MODEL_SONNET,
) -> SandboxAgent:
    """
    Borrow a sandbox slot from the pool.

    Blocks until a slot is free, resets the home for the requested agent type,
    and returns a SandboxAgent. Caller must call release_sandbox_agent() when
    done — use a try/finally or context manager.
    """
    import secrets
    from ..samsara.provisioning import _update_config

    name, lock_file, lock_path = _acquire_slot()
    token = secrets.token_hex(32)

    resolved_constitution = load_constitution(base_agent, constitution)
    _reset_sandbox_home(name, base_agent, resolved_constitution, model, seed_karma)
    _create_budget_file(name)
    _create_fifo(name)
    _update_config(name, token)

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
    Return a sandbox slot to the pool.

    Wipes the home directory and releases the flock so another experiment can
    acquire this slot. Safe to call even if acquisition partially failed.
    """
    from ..samsara.provisioning import _remove_from_config

    _remove_from_config(agent.name)

    fifo = Path("/var/aurelia/queue") / agent.name
    if fifo.exists():
        fifo.unlink(missing_ok=True)

    budget = Path("/var/aurelia/budgets") / f"{agent.name}.json"
    if budget.exists():
        budget.unlink(missing_ok=True)

    home = AGENT_HOME_BASE / agent.name
    if home.exists():
        shutil.rmtree(home)

    if agent._lock_file is not None:
        _release_slot(agent._lock_file)


# ── One-time setup ─────────────────────────────────────────────────────────────


def provision_sandbox_pool(
    base_agent: str = "personal",
    model: str = MODEL_SONNET,
) -> None:
    """
    One-time setup: create sandbox-1..sandbox-N Linux users with correct
    permissions, sudoers entries, and a skeleton home. Safe to re-run.

    Run as root before first use:
        sudo python3 -c "from src.test.sandbox import provision_sandbox_pool; provision_sandbox_pool()"
    """
    SANDBOX_DIR.mkdir(parents=True, exist_ok=True)
    SANDBOX_LOCK_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(["chown", "aurelia:aurelia_admin", str(SANDBOX_DIR)], check=True, capture_output=True)
    subprocess.run(["chmod", "770", str(SANDBOX_DIR)], check=True, capture_output=True)
    subprocess.run(["chown", "aurelia:aurelia_admin", str(SANDBOX_LOCK_DIR)], check=True, capture_output=True)
    subprocess.run(["chmod", "770", str(SANDBOX_LOCK_DIR)], check=True, capture_output=True)

    constitution = load_constitution(base_agent)
    for name in SANDBOX_NAMES:
        print(f"  Provisioning {name}...")
        _create_linux_user(name)
        home = AGENT_HOME_BASE / name
        home.mkdir(parents=True, exist_ok=True)
        _setup_filesystem(home, name, base_agent.capitalize(), constitution, model, overwrite=False)
        _chown(name, home)
        _add_to_sudoers(name)
        print(f"  {name} ready.")

    print(f"  Sandbox pool ({SANDBOX_POOL_SIZE} slots) provisioned.")
