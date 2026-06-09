"""Execution tools: bash_exec — the agent's general-purpose compute primitive."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from .registry import ToolRegistry

_BWRAP = shutil.which("bwrap")

BASH_EXEC_SCHEMA = {
    "name": "bash_exec",
    "description": (
        "Run a bash command and return stdout, stderr, and exit code. "
        "Working directory defaults to ~/room. "
        "You have read-write access to ~/room (permanent) and ~/scratch (this incarnation only).\n"
        "Use this for anything that isn't covered by a dedicated tool:\n"
        "  • Web search:  python3 -c \"from ddgs import DDGS; [print(r) for r in DDGS().text('QUERY', max_results=5)]\"\n"
        "  • Fetch a URL: curl -sL URL  (or add | python3 -m html2text for readable output)\n"
        "  • Run Python:  python3 -c 'print(1+1)'  or  python3 ~/room/script.py\n"
        "  • Read files:  cat ~/room/notes.md\n"
        "  • Write files: use python3 or redirect output\n"
        "Output is truncated at 8000 chars stdout / 2000 chars stderr. "
        "Default timeout is 30s — pass timeout_seconds to override (max 120).\n\n"
        "WARNING: Background commands DO NOT work here. Running 'cmd &' or 'nohup cmd &' will "
        "appear to succeed but the process will die immediately when this tool call returns. "
        "Use process_start instead for anything that needs to keep running."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Bash command to execute",
            },
            "timeout_seconds": {
                "type": "integer",
                "description": "Timeout in seconds (default: 30, max: 120)",
                "default": 30,
            },
            "cwd": {
                "type": "string",
                "description": "Working directory override (must be within ~/room or ~/scratch)",
            },
        },
        "required": ["command"],
    },
}

_STDOUT_MAX = 8_000
_STDERR_MAX = 2_000
_TIMEOUT_MAX = 120


def _bwrap_cmd(
    command: str,
    agent_config: Any,
    incarnation_name: str,
    cwd: Path,
) -> list[str]:
    room = agent_config.room_dir
    scratch_src = agent_config.scratch_dir / incarnation_name
    scratch_dst = agent_config.home / "scratch"

    scratch_src.mkdir(parents=True, exist_ok=True)
    room.mkdir(parents=True, exist_ok=True)

    return [
        _BWRAP,
        "--unshare-all",
        "--share-net",        # agents need network for web search etc.
        "--die-with-parent",  # bwrap dies if Manas dies
        "--new-session",

        # Standard system paths
        "--ro-bind", "/usr", "/usr",
        "--ro-bind", "/bin", "/bin",
        "--ro-bind", "/lib", "/lib",
        "--ro-bind-try", "/lib64", "/lib64",
        "--ro-bind-try", "/lib32", "/lib32",
        "--ro-bind", "/etc", "/etc",

        # Project venv so agents can use installed packages
        "--ro-bind", "/opt/aurelia/.venv", "/opt/aurelia/.venv",

        # Agent home: room (rw, permanent) + incarnation scratch (rw, scoped)
        "--dir", str(agent_config.home),
        "--bind", str(room), str(room),
        "--bind", str(scratch_src), str(scratch_dst),

        # Minimal devices, /proc, fresh /tmp
        "--dev", "/dev",
        "--proc", "/proc",
        "--tmpfs", "/tmp",

        "--setenv", "HOME", str(agent_config.home),
        "--chdir", str(cwd),
        "--",
        "/bin/bash", "-c", command,
    ]


def handle_bash_exec(input_data: dict[str, Any], **ctx: Any) -> dict[str, Any]:
    command = input_data.get("command", "").strip()
    timeout = min(int(input_data.get("timeout_seconds", 30)), _TIMEOUT_MAX)
    cwd_override = input_data.get("cwd")

    if not command:
        return {"error": "command is required"}

    agent_config = ctx.get("agent_config")
    incarnation_name = ctx.get("incarnation_name", "unknown")

    # Resolve working directory
    if cwd_override:
        cwd = Path(cwd_override)
        # When bwrap is active only home subtree is mounted; fall back to room if outside it
        if _BWRAP and agent_config and not str(cwd).startswith(str(agent_config.home)):
            cwd = agent_config.room_dir
    elif agent_config:
        cwd = agent_config.room_dir if _BWRAP else agent_config.home
    else:
        cwd = Path.home()

    if not cwd.exists():
        cwd = agent_config.room_dir if agent_config else Path.home()

    if _BWRAP and agent_config:
        cmd = _bwrap_cmd(command, agent_config, incarnation_name, cwd)
    else:
        if not _BWRAP:
            import logging
            logging.warning("bwrap not found — bash_exec running without namespace isolation")
        cmd = ["/bin/bash", "-c", command]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd) if not _BWRAP else None,  # bwrap handles cwd via --chdir
        )
    except subprocess.TimeoutExpired:
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Command timed out after {timeout}s",
            "truncated": False,
            "timed_out": True,
        }
    except Exception as e:
        return {"error": f"Failed to run command: {e}"}

    stdout = result.stdout
    stderr = result.stderr
    truncated = False

    if len(stdout) > _STDOUT_MAX:
        stdout = stdout[:_STDOUT_MAX] + "\n[... stdout truncated ...]"
        truncated = True
    if len(stderr) > _STDERR_MAX:
        stderr = stderr[:_STDERR_MAX] + "\n[... stderr truncated ...]"

    return {
        "exit_code": result.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "truncated": truncated,
        "timed_out": False,
    }


def register_exec_tools(
    registry: ToolRegistry,
    agent_config: Any = None,
    incarnation_name: str = "unknown",
) -> None:
    def handler(input_data: dict[str, Any], **extra_ctx: Any) -> Any:
        return handle_bash_exec(
            input_data,
            agent_config=agent_config,
            incarnation_name=incarnation_name,
            **extra_ctx,
        )

    registry.register(BASH_EXEC_SCHEMA, handler)
