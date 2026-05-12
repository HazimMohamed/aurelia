#!/usr/bin/env python3
"""Aurelia runtime daemon — listens on Unix socket, dispatches to runtime.py.

Dev mode: run as 'zuzu' — socket is created at /var/aurelia/runtime.sock
  with permissions 666 (world-rw). No strict group ownership is set.

Production: run as 'aurelia' user — socket is owned aurelia:transport_group
  with permissions 660. HTTP server runs as a member of transport_group.
"""

from __future__ import annotations

import grp
import json
import logging
import os
import signal
import socket
import struct
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure the package root is importable when run as -m src.runtime_daemon
sys.path.insert(0, str(Path(__file__).parent.parent))

from . import runtime_core as runtime
from ..agent.hooks import HookType

# ── Manas routing ──────────────────────────────────────────────────────────────

_PER_AGENT_TYPES = frozenset({
    "spawn", "dispatch", "get_history", "list_incarnations",
    "get_active", "get_budget_info", "trigger_bardo", "internal_process",
})


def _is_manas_live(config: Any) -> bool:
    """Return True if this agent's Manas socket exists and responds to a ping."""
    if not config.manas_socket.exists():
        return False
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            s.connect(str(config.manas_socket))
            s.sendall(json.dumps({"type": "ping"}).encode() + b"\n")
            buf = b""
            while b"\n" not in buf:
                chunk = s.recv(256)
                if not chunk:
                    return False
                buf += chunk
        return True
    except (OSError, socket.timeout):
        return False


def _route_to_manas(config: Any, request: dict) -> Any:
    """Forward a non-streaming request to Manas and return the result data."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(300.0)
        s.connect(str(config.manas_socket))
        s.sendall(json.dumps(request).encode() + b"\n")
        buf = b""
        while b"\n" not in buf:
            chunk = s.recv(65536)
            if not chunk:
                raise RuntimeError("Manas connection closed unexpectedly")
            buf += chunk
        line, _ = buf.split(b"\n", 1)
        resp = json.loads(line.decode())
        if resp.get("status") == "error":
            raise RuntimeError(resp.get("message", "Manas returned error"))
        return resp.get("data")


def _route_to_manas_stream(config: Any, request: dict, send_frame: Any) -> Any:
    """Forward a streaming dispatch to Manas.

    Calls send_frame for each intermediate frame. Returns the result dict from
    Manas's done frame — the caller is responsible for sending its own done frame
    with the correct request id.
    """
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(10.0)
        s.connect(str(config.manas_socket))
        s.sendall(json.dumps(request).encode() + b"\n")
        s.settimeout(None)
        buf = b""
        while True:
            chunk = s.recv(65536)
            if not chunk:
                raise RuntimeError("Manas stream ended without done frame")
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if not line:
                    continue
                frame = json.loads(line.decode())
                if frame.get("type") == "done":
                    if frame.get("status") == "error":
                        raise RuntimeError(frame.get("message", "Manas stream error"))
                    return frame.get("data")
                send_frame(frame)

# ── Configuration ──────────────────────────────────────────────────────────────

SOCKET_PATH = Path("/var/aurelia/runtime.sock")
LOG_PATH = Path("/var/aurelia/logs/runtime.log")
SOCKET_GROUP = "transport_group"
SOCKET_MODE_PROD = 0o660   # aurelia:transport_group — only group members can connect
SOCKET_MODE_DEV = 0o666    # world-rw for dev (both processes run as zuzu)
MAX_WORKERS = 10

# ── Logging setup ──────────────────────────────────────────────────────────────


def _setup_logging() -> logging.Logger:
    logger = logging.getLogger("aurelia.runtime_daemon")
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter("%(message)s")

    # stderr handler (always available)
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    # file handler (best-effort — may fail in dev if /var/aurelia doesn't exist yet)
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(LOG_PATH, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except OSError as e:
        logger.warning(f"[runtime_daemon] Cannot open log file {LOG_PATH}: {e}")

    return logger


log = _setup_logging()


# ── Socket helpers ─────────────────────────────────────────────────────────────


def _get_peer_cred(conn: socket.socket) -> tuple[int, int, int]:
    """Read SO_PEERCRED from a connected Unix socket. Returns (pid, uid, gid)."""
    # struct ucred: pid_t (4), uid_t (4), gid_t (4) — Linux only
    try:
        cred = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
        pid, uid, gid = struct.unpack("3i", cred)
        return pid, uid, gid
    except (OSError, struct.error):
        return -1, -1, -1


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


# ── Request routing ────────────────────────────────────────────────────────────


def _dispatch(request: dict[str, Any]) -> Any:
    """Route a parsed request dict to the correct runtime function and return result."""
    req_type = request.get("type")
    agent_name = request.get("agent")

    if req_type in _PER_AGENT_TYPES and agent_name:
        registry = runtime.get_registry()
        config = registry.get(agent_name)
        if config and _is_manas_live(config):
            return _route_to_manas(config, request)


    match req_type:
        case "spawn":
            return runtime.spawn(
                agent=request["agent"],
                goal=request.get("goal"),
            )
        case "dispatch":
            return runtime.dispatch(
                agent=request["agent"],
                incarnation=request["incarnation"],
                hook=HookType(request["hook"]),
                payload=request.get("payload", {}),
            )
        case "get_history":
            return runtime.get_history(
                agent=request["agent"],
                incarnation=request["incarnation"],
            )
        case "list_incarnations":
            return runtime.list_incarnations(agent=request["agent"])
        case "list_agents":
            return runtime.list_agents()
        case "get_health":
            return runtime.get_health()
        case "trigger_bardo":
            agent = request["agent"]
            active = runtime.get_active(agent)
            if not active:
                return {"status": "no_active", "agent": agent}
            return runtime.trigger_bardo(agent, active)
        case "internal_process":
            return _dispatch_internal_process(request)
        case "get_active":
            return {"active": runtime.get_active(request["agent"])}
        case "get_budget_info":
            return runtime.get_budget_info(request["agent"])
        case "registry_reload":
            registry = runtime.get_registry()
            registry._refresh()
            return {"status": "reloaded", "agents": registry.all_agents()}
        case "scheduler_tick":
            scheduler = getattr(runtime, "_scheduler", None)
            if scheduler is None:
                raise RuntimeError("Scheduler not available")
            scheduler.tick_now()
            return {"status": "ticked"}
        case _:
            raise ValueError(f"Unknown request type: {req_type!r}")


def _dispatch_internal_process(request: dict[str, Any]) -> dict[str, Any]:
    """Handle autonomous hook processing (heartbeat, scheduled_task, agent_invite)."""
    from ..agent.hooks import heartbeat_precheck

    agent_name = request["agent"]
    hook_type = request["hook_type"]
    goal = request.get("goal", "")
    payload = request.get("payload") or {}
    rebirth_from = request.get("rebirth_from")

    registry = runtime.get_registry()
    config = registry.get(agent_name)
    if not config:
        raise ValueError(f"Agent '{agent_name}' not found")

    if hook_type == HookType.HEARTBEAT:
        if not heartbeat_precheck(config):
            return {"status": "skipped", "reason": "heartbeat_precheck_false", "agent": agent_name}

    hook_prompt = runtime.build_hook_prompt(
        agent=agent_name,
        hook_type=hook_type,
        goal=goal,
        payload=payload,
        rebirth_from=rebirth_from,
    )

    incarnation_state = runtime.spawn_fresh_for_hook(agent_name, hook_type)

    response_text, next_action = runtime.run_hook(
        agent=agent_name,
        hook_type=hook_type,
        hook_prompt=hook_prompt,
        incarnation_state=incarnation_state,
    )

    return {
        "status": "ok",
        "agent": agent_name,
        "incarnation": incarnation_state["name"],
        "hook": hook_type,
        "next_action": next_action.get("type", "sleep"),
    }


def _serialize(obj: Any) -> Any:
    """Recursively convert dataclass instances to dicts for JSON serialization."""
    import dataclasses

    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _serialize(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, list):
        return [_serialize(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, Path):
        return str(obj)
    return obj


# ── Connection handler ─────────────────────────────────────────────────────────


def _handle_connection(conn: socket.socket) -> None:
    """Handle one client connection: read JSON request, dispatch, write JSON response.

    When the request includes "stream": true (only valid for "dispatch" type),
    the connection stays open and intermediate frames are written as newline-
    delimited JSON before a final {"type":"done"} frame closes the exchange.
    """
    pid, uid, gid = _get_peer_cred(conn)

    with conn:
        try:
            buf = b""
            conn.settimeout(30.0)
            while b"\n" not in buf:
                chunk = conn.recv(4096)
                if not chunk:
                    return
                buf += chunk

            line, _ = buf.split(b"\n", 1)
            request = json.loads(line.decode("utf-8"))

            req_id = request.get("id") or str(uuid.uuid4())
            req_type = request.get("type", "unknown")
            agent = request.get("agent", "")

            is_streaming = bool(request.get("stream")) and req_type == "dispatch"

            if is_streaming:
                # Remove timeout for the duration of the streamed response
                conn.settimeout(None)

                def send_frame(frame: dict[str, Any]) -> None:
                    conn.sendall(json.dumps(frame).encode("utf-8") + b"\n")

                t_start = time.monotonic()
                try:
                    registry = runtime.get_registry()
                    _config = registry.get(request["agent"])
                    if _config and _is_manas_live(_config):
                        result = _route_to_manas_stream(_config, request, send_frame)
                    else:
                        result = runtime.dispatch(
                            agent=request["agent"],
                            incarnation=request["incarnation"],
                            hook=HookType(request["hook"]),
                            payload=request.get("payload", {}),
                            stream_callback=send_frame,
                        )
                    duration_ms = int((time.monotonic() - t_start) * 1000)
                    send_frame({
                        "type": "done",
                        "id": req_id,
                        "status": "ok",
                        "data": _serialize(result),
                    })
                    log.info(
                        f"{_now_iso()} pid={pid} uid={uid} gid={gid} "
                        f"type={req_type} agent={agent} status=ok stream=true duration_ms={duration_ms}"
                    )
                except Exception as exc:
                    import traceback as _tb
                    duration_ms = int((time.monotonic() - t_start) * 1000)
                    send_frame({
                        "type": "done",
                        "id": req_id,
                        "status": "error",
                        "error": type(exc).__name__,
                        "message": str(exc),
                    })
                    log.error(
                        f"{_now_iso()} pid={pid} uid={uid} gid={gid} "
                        f"type={req_type} agent={agent} status=error stream=true "
                        f"duration_ms={duration_ms} error={type(exc).__name__}: {exc}\n"
                        + _tb.format_exc()
                    )
                return

            # ── Non-streaming path (unchanged) ──────────────────────────────────
            t_start = time.monotonic()

            try:
                result = _dispatch(request)
                duration_ms = int((time.monotonic() - t_start) * 1000)
                response = {
                    "id": req_id,
                    "status": "ok",
                    "data": _serialize(result),
                }
                log.info(
                    f"{_now_iso()} pid={pid} uid={uid} gid={gid} "
                    f"type={req_type} agent={agent} status=ok duration_ms={duration_ms}"
                )
            except Exception as exc:
                import traceback as _tb
                duration_ms = int((time.monotonic() - t_start) * 1000)
                response = {
                    "id": req_id,
                    "status": "error",
                    "error": type(exc).__name__,
                    "message": str(exc),
                }
                log.error(
                    f"{_now_iso()} pid={pid} uid={uid} gid={gid} "
                    f"type={req_type} agent={agent} status=error "
                    f"duration_ms={duration_ms} error={type(exc).__name__}: {exc}\n"
                    + _tb.format_exc()
                )

            conn.sendall(json.dumps(response).encode("utf-8") + b"\n")

        except json.JSONDecodeError as e:
            log.error(f"{_now_iso()} pid={pid} uid={uid} gid={gid} bad_json error={e}")
        except socket.timeout:
            log.warning(f"{_now_iso()} pid={pid} uid={uid} gid={gid} connection_timeout")
        except Exception as e:
            log.error(f"{_now_iso()} pid={pid} uid={uid} gid={gid} handler_error={e}")


# ── Socket setup ───────────────────────────────────────────────────────────────


def _setup_socket() -> socket.socket:
    """Create and bind the Unix socket, set ownership and permissions."""
    # Remove stale socket file from a previous (crashed) run
    if SOCKET_PATH.exists() or SOCKET_PATH.is_symlink():
        SOCKET_PATH.unlink()
    SOCKET_PATH.parent.mkdir(parents=True, exist_ok=True)

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(str(SOCKET_PATH))
    server.listen(64)

    # Attempt production-mode permission setup (requires root or correct group membership)
    is_root = os.geteuid() == 0
    try:
        gid = grp.getgrnam(SOCKET_GROUP).gr_gid
        if is_root:
            os.chown(str(SOCKET_PATH), os.geteuid(), gid)
            os.chmod(str(SOCKET_PATH), SOCKET_MODE_PROD)
            log.info(
                f"[runtime_daemon] Socket {SOCKET_PATH} "
                f"owned by aurelia:{SOCKET_GROUP} mode=660 (production)"
            )
        else:
            # Dev: can't chown, set 666 so both zuzu processes can connect
            os.chmod(str(SOCKET_PATH), SOCKET_MODE_DEV)
            log.info(
                f"[runtime_daemon] Dev mode — socket {SOCKET_PATH} mode=666 "
                f"(not root, skipping group ownership)"
            )
    except KeyError:
        # transport_group doesn't exist — dev environment
        os.chmod(str(SOCKET_PATH), SOCKET_MODE_DEV)
        log.info(
            f"[runtime_daemon] Dev mode — group '{SOCKET_GROUP}' not found, "
            f"socket {SOCKET_PATH} mode=666"
        )

    return server


# ── Main daemon ────────────────────────────────────────────────────────────────


class RuntimeDaemon:
    def __init__(self) -> None:
        self._shutdown = threading.Event()
        self._executor: ThreadPoolExecutor | None = None

    def _signal_handler(self, signum: int, frame: Any) -> None:
        log.info(f"[runtime_daemon] Received signal {signum}, shutting down...")
        self._shutdown.set()

    def run(self) -> None:
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        server = _setup_socket()
        server.settimeout(1.0)  # allow periodic shutdown checks

        log.info(f"[runtime_daemon] Listening on {SOCKET_PATH} (max_workers={MAX_WORKERS})")

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            self._executor = executor
            while not self._shutdown.is_set():
                try:
                    conn, _ = server.accept()
                    executor.submit(_handle_connection, conn)
                except socket.timeout:
                    continue  # check shutdown flag
                except OSError as e:
                    if not self._shutdown.is_set():
                        log.error(f"[runtime_daemon] Accept error: {e}")

        server.close()
        # Clean up socket file on graceful exit
        try:
            SOCKET_PATH.unlink(missing_ok=True)
        except OSError:
            pass
        log.info("[runtime_daemon] Shutdown complete.")


def main() -> None:
    log.info(f"[runtime_daemon] Starting (pid={os.getpid()}, uid={os.getuid()})")

    # Start scheduler as a background thread — same process, no IPC needed
    from .scheduler import SchedulerDaemon
    scheduler = SchedulerDaemon()
    runtime._scheduler = scheduler  # expose for socket command handler
    scheduler_thread = threading.Thread(target=scheduler.run, daemon=True, name="scheduler")
    scheduler_thread.start()
    log.info("[runtime_daemon] Scheduler thread started")

    daemon = RuntimeDaemon()
    daemon.run()


if __name__ == "__main__":
    main()
