"""Execution tools: bash_exec — the agent's general-purpose compute primitive."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from .registry import ToolRegistry


BASH_EXEC_SCHEMA = {
    "name": "bash_exec",
    "description": (
        "Run a bash command and return stdout, stderr, and exit code. "
        "Working directory is your home (/home/{agent}). "
        "Use this for anything that isn't covered by a dedicated tool:\n"
        "  • Web search:  python3 -c \"from ddgs import DDGS; [print(r) for r in DDGS().text('QUERY', max_results=5)]\"\n"
        "  • Fetch a URL: curl -sL URL  (or add | python3 -m html2text for readable output)\n"
        "  • Run Python:  python3 -c 'print(1+1)'  or  python3 /home/{agent}/script.py\n"
        "  • Read files:  cat /path/to/file\n"
        "  • Write files: echo 'content' > /path/to/file  or use python3 -c \"Path(...).write_text(...)\"\n"
        "Output is truncated at 8000 chars stdout / 2000 chars stderr. "
        "Default timeout is 30s — pass timeout_seconds to override (max 120).\n\n"
        "WARNING: Background commands DO NOT work here. Running 'cmd &' or 'nohup cmd &' will "
        "appear to succeed but the process will die immediately when this tool call returns. "
        "Use process_start instead for anything that needs to keep running: HTTP servers, "
        "long scripts, watchers, etc."
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
                "description": "Working directory override (default: agent home)",
            },
        },
        "required": ["command"],
    },
}

_STDOUT_MAX = 8_000
_STDERR_MAX = 2_000
_TIMEOUT_MAX = 120


def handle_bash_exec(input_data: dict[str, Any], **ctx: Any) -> dict[str, Any]:
    command = input_data.get("command", "").strip()
    timeout = min(int(input_data.get("timeout_seconds", 30)), _TIMEOUT_MAX)
    cwd_override = input_data.get("cwd")

    if not command:
        return {"error": "command is required"}

    agent_config = ctx.get("agent_config")
    if cwd_override:
        cwd = Path(cwd_override)
    elif agent_config:
        cwd = agent_config.home
    else:
        cwd = Path.home()

    if not cwd.exists():
        cwd = Path.home()

    agent_name = agent_config.name if agent_config else None
    # Inside Manas the process already runs as the agent user — no sudo needed.
    in_manas = os.environ.get("AURELIA_MANAS_AGENT") == agent_name
    cmd = (
        ["/bin/bash", "-c", command]
        if (not agent_name or in_manas)
        else ["sudo", "-u", agent_name, "/bin/bash", "-c", command]
    )

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd),
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


def register_exec_tools(registry: ToolRegistry, agent_config: Any = None) -> None:
    def handler(input_data: dict[str, Any], **extra_ctx: Any) -> Any:
        return handle_bash_exec(input_data, agent_config=agent_config, **extra_ctx)

    registry.register(BASH_EXEC_SCHEMA, handler)
