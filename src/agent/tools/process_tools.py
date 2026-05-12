"""Process management tools — start/list/logs/stop background processes.

bash_exec blocks until the command finishes and cannot keep background processes
alive. Use these tools instead for anything that needs to run persistently:
HTTP servers, long computations, watchers, etc.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .registry import ToolRegistry


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _registry_path(agent_home: Path) -> Path:
    return agent_home / "processes" / "registry.json"


def _log_dir(agent_home: Path) -> Path:
    return agent_home / "processes" / "logs"


def _load_registry(agent_home: Path) -> list[dict[str, Any]]:
    path = _registry_path(agent_home)
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except Exception:
        return []


def _save_registry(agent_home: Path, entries: list[dict[str, Any]]) -> None:
    path = _registry_path(agent_home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=2))


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _next_id(entries: list[dict[str, Any]]) -> int:
    if not entries:
        return 1
    return max(e["id"] for e in entries) + 1


# ── Tool: process_start ────────────────────────────────────────────────────────

PROCESS_START_SCHEMA = {
    "name": "process_start",
    "description": (
        "Start a command as a detached background process that survives after the tool call returns. "
        "Use this for HTTP servers, long-running scripts, watchers, or anything bash_exec can't keep alive.\n\n"
        "Examples:\n"
        "  • HTTP server:    command='python3 -m http.server 8765', label='room-server'\n"
        "  • Python script:  command='python3 /home/personal/watcher.py', label='watcher'\n"
        "  • Any long job:   command='ffmpeg -i input.mp4 output.mp4', label='transcode'\n\n"
        "stdout/stderr are written to a log file — use process_logs to read them.\n"
        "Processes persist across tool calls but NOT across machine reboots. "
        "Stop them with process_stop before bardo if they shouldn't outlive this incarnation."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Shell command to run in the background",
            },
            "label": {
                "type": "string",
                "description": "Short human-readable name (e.g. 'room-server', 'watcher')",
            },
            "cwd": {
                "type": "string",
                "description": "Working directory (default: agent home)",
            },
        },
        "required": ["command", "label"],
    },
}


def handle_process_start(input_data: dict[str, Any], **ctx: Any) -> dict[str, Any]:
    command = input_data.get("command", "").strip()
    label = input_data.get("label", "").strip()
    cwd_override = input_data.get("cwd")

    if not command:
        return {"error": "command is required"}
    if not label:
        return {"error": "label is required"}

    agent_config = ctx.get("agent_config")
    incarnation = ctx.get("incarnation", "unknown")
    agent_home = agent_config.home if agent_config else Path.home()
    cwd = Path(cwd_override) if cwd_override else agent_home
    if not cwd.exists():
        cwd = agent_home

    log_dir = _log_dir(agent_home)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{label}.log"

    agent_name = agent_config.name if agent_config else None
    cmd = (
        ["sudo", "-u", agent_name, "/bin/bash", "-c", command]
        if agent_name else ["/bin/bash", "-c", command]
    )

    try:
        log_file = open(log_path, "a")
        proc = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=log_file,
            cwd=str(cwd),
            start_new_session=True,  # detach from parent session
        )
    except Exception as e:
        return {"error": f"Failed to start process: {e}"}

    entries = _load_registry(agent_home)
    process_id = _next_id(entries)
    entries.append({
        "id": process_id,
        "label": label,
        "pid": proc.pid,
        "command": command,
        "log_path": str(log_path),
        "started_at": _now_iso(),
        "incarnation": incarnation,
        "status": "running",
    })
    _save_registry(agent_home, entries)

    return {
        "process_id": process_id,
        "pid": proc.pid,
        "label": label,
        "log_path": str(log_path),
        "message": f"Started '{label}' (pid={proc.pid}). Use process_logs to see output.",
    }


# ── Tool: process_list ─────────────────────────────────────────────────────────

PROCESS_LIST_SCHEMA = {
    "name": "process_list",
    "description": "List all background processes you have started, with their current status (running/stopped).",
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}


def handle_process_list(input_data: dict[str, Any], **ctx: Any) -> dict[str, Any]:
    agent_config = ctx.get("agent_config")
    agent_home = agent_config.home if agent_config else Path.home()

    entries = _load_registry(agent_home)
    if not entries:
        return {"processes": [], "message": "No background processes recorded."}

    result = []
    for e in entries:
        alive = _pid_alive(e["pid"])
        result.append({
            "id": e["id"],
            "label": e["label"],
            "pid": e["pid"],
            "status": "running" if alive else "stopped",
            "command": e["command"],
            "started_at": e["started_at"],
            "log_path": e["log_path"],
        })

    return {"processes": result}


# ── Tool: process_logs ─────────────────────────────────────────────────────────

PROCESS_LOGS_SCHEMA = {
    "name": "process_logs",
    "description": "Read the last N lines of a background process's log (stdout + stderr).",
    "input_schema": {
        "type": "object",
        "properties": {
            "process_id": {
                "type": "integer",
                "description": "ID from process_list or process_start",
            },
            "lines": {
                "type": "integer",
                "description": "Number of lines to return from the end of the log (default: 50)",
                "default": 50,
            },
        },
        "required": ["process_id"],
    },
}


def handle_process_logs(input_data: dict[str, Any], **ctx: Any) -> dict[str, Any]:
    process_id = input_data.get("process_id")
    lines = int(input_data.get("lines", 50))

    agent_config = ctx.get("agent_config")
    agent_home = agent_config.home if agent_config else Path.home()

    entries = _load_registry(agent_home)
    entry = next((e for e in entries if e["id"] == process_id), None)
    if not entry:
        return {"error": f"No process with id={process_id}. Use process_list to see available processes."}

    log_path = Path(entry["log_path"])
    if not log_path.exists():
        return {"process_id": process_id, "label": entry["label"], "log": "", "message": "Log file not yet created."}

    try:
        all_lines = log_path.read_text(errors="replace").splitlines()
        tail = all_lines[-lines:] if len(all_lines) > lines else all_lines
        return {
            "process_id": process_id,
            "label": entry["label"],
            "pid": entry["pid"],
            "status": "running" if _pid_alive(entry["pid"]) else "stopped",
            "log": "\n".join(tail),
            "total_lines": len(all_lines),
        }
    except Exception as e:
        return {"error": f"Failed to read log: {e}"}


# ── Tool: process_stop ─────────────────────────────────────────────────────────

PROCESS_STOP_SCHEMA = {
    "name": "process_stop",
    "description": "Stop a background process by its ID. Sends SIGTERM, then SIGKILL if it doesn't exit within 3 seconds.",
    "input_schema": {
        "type": "object",
        "properties": {
            "process_id": {
                "type": "integer",
                "description": "ID from process_list",
            },
        },
        "required": ["process_id"],
    },
}


def handle_process_stop(input_data: dict[str, Any], **ctx: Any) -> dict[str, Any]:
    import time

    process_id = input_data.get("process_id")

    agent_config = ctx.get("agent_config")
    agent_home = agent_config.home if agent_config else Path.home()

    entries = _load_registry(agent_home)
    entry = next((e for e in entries if e["id"] == process_id), None)
    if not entry:
        return {"error": f"No process with id={process_id}."}

    pid = entry["pid"]
    if not _pid_alive(pid):
        return {"process_id": process_id, "label": entry["label"], "message": "Process was already stopped."}

    try:
        os.kill(pid, signal.SIGTERM)
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            if not _pid_alive(pid):
                break
            time.sleep(0.1)
        if _pid_alive(pid):
            os.kill(pid, signal.SIGKILL)
            msg = f"Sent SIGTERM then SIGKILL to pid={pid} (label={entry['label']})."
        else:
            msg = f"Stopped pid={pid} (label={entry['label']}) with SIGTERM."
    except Exception as e:
        return {"error": f"Failed to stop process: {e}"}

    return {"process_id": process_id, "label": entry["label"], "pid": pid, "message": msg}


# ── Bardo cleanup ─────────────────────────────────────────────────────────────

def cleanup_incarnation_processes(agent_home: Path, incarnation: str) -> list[dict[str, Any]]:
    """Kill all running processes registered to a specific incarnation.

    Called by bardo before archiving. Returns list of killed process records.
    """
    import time

    entries = _load_registry(agent_home)
    killed = []

    for entry in entries:
        if entry.get("incarnation") != incarnation:
            continue
        pid = entry["pid"]
        if not _pid_alive(pid):
            continue
        try:
            os.kill(pid, signal.SIGTERM)
            deadline = time.monotonic() + 3.0
            while time.monotonic() < deadline:
                if not _pid_alive(pid):
                    break
                time.sleep(0.1)
            if _pid_alive(pid):
                os.kill(pid, signal.SIGKILL)
        except Exception:
            pass
        killed.append(entry)

    return killed


# ── Registration ───────────────────────────────────────────────────────────────

def register_process_tools(
    registry: ToolRegistry,
    agent_config: Any = None,
    incarnation: str = "unknown",
) -> None:
    def _ctx(handler):
        def wrapped(input_data, **extra):
            return handler(input_data, agent_config=agent_config, incarnation=incarnation, **extra)
        return wrapped

    registry.register(PROCESS_START_SCHEMA, _ctx(handle_process_start))
    registry.register(PROCESS_LIST_SCHEMA, _ctx(handle_process_list))
    registry.register(PROCESS_LOGS_SCHEMA, _ctx(handle_process_logs))
    registry.register(PROCESS_STOP_SCHEMA, _ctx(handle_process_stop))
