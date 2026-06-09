"""System-level administration: setup, reprovision, and uninstall.

These functions perform OS-level operations (groups, users, directories,
permissions, sudoers) and return structured results so callers can decide
how to present them. No console output happens here.

Requires root privileges for most operations.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import NamedTuple

from ..config import (
    AGENT_DATA_BASE,
    AGENT_HOME_BASE,
    AGENT_RUN_BASE,
)
from .provisioning import (
    _add_to_sudoers,
    _chown,
    _create_linux_user,
    _destroy_linux_user,
    _user_exists,
)

VAR_AURELIA = Path("/var/aurelia")
SUDOERS_PATH = Path("/etc/sudoers.d/aurelia")


class StepResult(NamedTuple):
    label: str
    ok: bool
    detail: str = ""


def _run(label: str, cmd: list[str]) -> StepResult:
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode == 0:
        return StepResult(label, True)
    err = result.stderr.decode().strip()
    if "already exists" in err or "already a member" in err:
        return StepResult(label, True, "already exists")
    return StepResult(label, False, err)


# ── Setup ──────────────────────────────────────────────────────────────────────


def setup(shell_user: str = "") -> list[StepResult]:
    """Create OS groups, service account, /var/aurelia dirs, and sudoers skeleton.

    Idempotent — safe to re-run. Returns one StepResult per operation.
    """
    results: list[StepResult] = []

    for group in ("aurelia_admin", "aurelia_agents", "transport_group"):
        results.append(_run(f"groupadd {group}", ["groupadd", "--system", group]))

    if subprocess.run(["id", "aurelia"], capture_output=True).returncode != 0:
        results.append(_run(
            "useradd aurelia",
            ["useradd", "-M", "-s", "/usr/sbin/nologin", "-g", "aurelia_admin", "aurelia"],
        ))
    else:
        results.append(StepResult("aurelia user", True, "already exists"))

    if shell_user:
        results.append(_run(
            f"add {shell_user} to aurelia_admin",
            ["usermod", "-aG", "aurelia_admin", shell_user],
        ))

    for d in (
        VAR_AURELIA / "logs",
        VAR_AURELIA / "scheduler" / "pending",
        VAR_AURELIA / "scheduler" / "completed",
        VAR_AURELIA / "scheduler" / "failed",
        VAR_AURELIA / "run",
        VAR_AURELIA / "dashboard" / "queue",
    ):
        try:
            d.mkdir(parents=True, exist_ok=True)
            results.append(StepResult(str(d), True))
        except OSError as e:
            results.append(StepResult(str(d), False, str(e)))

    results.append(_run(
        "chown /var/aurelia → aurelia:aurelia_admin",
        ["chown", "-R", "aurelia:aurelia_admin", str(VAR_AURELIA)],
    ))
    results.append(_run(
        "chmod /var/aurelia → 775",
        ["chmod", "-R", "775", str(VAR_AURELIA)],
    ))

    if not SUDOERS_PATH.exists():
        try:
            SUDOERS_PATH.write_text(
                "# Aurelia agent sudoers — managed by 'aurelia system setup' and 'aurelia agent create'\n"
                "# Each agent gets a line: %aurelia_admin ALL = ({agent}) NOPASSWD,SETENV: /opt/aurelia/bin/manas-launch {agent}\n"
            )
            os.chmod(str(SUDOERS_PATH), 0o440)
            results.append(StepResult(f"created {SUDOERS_PATH}", True))
        except OSError as e:
            results.append(StepResult(str(SUDOERS_PATH), False, str(e)))
    else:
        results.append(StepResult(str(SUDOERS_PATH), True, "already exists"))

    return results


# ── Reprovision ────────────────────────────────────────────────────────────────


def reprovision() -> list[StepResult]:
    """Re-apply group membership, sudoers entries, and per-resource permissions to all agents.

    Does not touch file content — only ownership and modes.
    """
    if not AGENT_DATA_BASE.exists():
        return []

    results: list[StepResult] = []
    for agent_dir in sorted(AGENT_DATA_BASE.iterdir()):
        if not agent_dir.is_dir():
            continue
        name = agent_dir.name
        home = AGENT_HOME_BASE / name
        data_dir = AGENT_DATA_BASE / name
        run_dir = AGENT_RUN_BASE / name
        run_dir.mkdir(parents=True, exist_ok=True)
        try:
            _create_linux_user(name)
            _add_to_sudoers(name)
            _chown(name, home, data_dir, run_dir)
            results.append(StepResult(name, True))
        except Exception as e:
            results.append(StepResult(name, False, str(e)))

    return results


# ── Uninstall ──────────────────────────────────────────────────────────────────


def uninstall(agents: list[str]) -> list[StepResult]:
    """Destroy all agents, /var/aurelia, sudoers, service account, and groups.

    Returns one StepResult per operation. Continues on failure.
    """
    results: list[StepResult] = []

    for name in agents:
        try:
            sudoers_lines = [
                line for line in SUDOERS_PATH.read_text().splitlines()
                if f"({name})" not in line
            ] if SUDOERS_PATH.exists() else []
            if SUDOERS_PATH.exists():
                SUDOERS_PATH.write_text("\n".join(sudoers_lines) + "\n")

            for d in (AGENT_HOME_BASE / name, AGENT_DATA_BASE / name, AGENT_RUN_BASE / name):
                if d.exists():
                    shutil.rmtree(d)

            if _user_exists(name):
                _destroy_linux_user(name)

            results.append(StepResult(name, True))
        except Exception as e:
            results.append(StepResult(name, False, str(e)))

    if VAR_AURELIA.exists():
        try:
            shutil.rmtree(VAR_AURELIA)
            results.append(StepResult("/var/aurelia", True))
        except OSError as e:
            results.append(StepResult("/var/aurelia", False, str(e)))
    else:
        results.append(StepResult("/var/aurelia", True, "not found"))

    if SUDOERS_PATH.exists():
        try:
            SUDOERS_PATH.unlink()
            results.append(StepResult(str(SUDOERS_PATH), True))
        except OSError as e:
            results.append(StepResult(str(SUDOERS_PATH), False, str(e)))

    if _user_exists("aurelia"):
        results.append(_run("userdel aurelia", ["userdel", "aurelia"]))
    else:
        results.append(StepResult("aurelia user", True, "not found"))

    for group in ("aurelia_agents", "aurelia_admin", "transport_group"):
        results.append(_run(f"groupdel {group}", ["groupdel", group]))

    return results
