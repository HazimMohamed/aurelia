#!/usr/bin/env python3
"""Aurelia runtime daemon — listens on Unix socket, routes to Manas or handles system ops.

Agent-specific operations (spawn, dispatch, bardo, etc.) are routed to the
relevant Manas process via its Unix socket. The daemon only handles system-level
concerns directly: scheduling, registry, health, and budget reads.

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

sys.path.insert(0, str(Path(__file__).parent.parent))

from . import runtime_core as runtime

# ── Manas routing ──────────────────────────────────────────────────────────────

# Requests that belong to a specific agent and must be handled by its Manas process.
_PER_AGENT_TYPES = frozenset({
    "spawn", "dispatch", "get_history", "list_incarnations",
    "get_primary", "get_active", "set_primary", "trigger_bardo", "internal_process",
})


def _is_manas_live(config: Any) -> bool:
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

SOCKET_PATH = Path("/var/aurelia/run/runtime.sock")
LOG_PATH = Path("/var/aurelia/logs/runtime.log")
SOCKET_GROUP = "transport_group"
SOCKET_MODE_PROD = 0o660
SOCKET_MODE_DEV = 0o666
MAX_WORKERS = 10

# ── Logging setup ──────────────────────────────────────────────────────────────


def _setup_logging() -> logging.Logger:
    logger = logging.getLogger("aurelia.runtime_daemon")
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(message)s")

    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

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
    try:
        cred = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
        pid, uid, gid = struct.unpack("3i", cred)
        return pid, uid, gid
    except (OSError, struct.error):
        return -1, -1, -1


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


# ── Request routing ────────────────────────────────────────────────────────────


def _require_admin_uid(uid: int) -> None:
    """Only root or members of aurelia_admin may perform admin operations."""
    import grp
    if uid == 0:
        return
    try:
        admin_gid = grp.getgrnam("aurelia_admin").gr_gid
        import pwd
        username = pwd.getpwuid(uid).pw_name
        # Check both the group's member list and the user's primary group
        in_admin = (
            username in grp.getgrnam("aurelia_admin").gr_mem
            or pwd.getpwuid(uid).pw_gid == admin_gid
        )
    except (KeyError, PermissionError):
        in_admin = False
    if not in_admin:
        raise PermissionError(f"UID {uid} is not a member of aurelia_admin")


def _require_agent_uid(uid: int, claimed_agent: str) -> None:
    import pwd
    own_uid = os.getuid()
    if uid == 0 or uid == own_uid:
        return
    try:
        expected_uid = pwd.getpwnam(claimed_agent).pw_uid
    except KeyError:
        raise PermissionError(f"No Linux user for agent '{claimed_agent}'")
    if uid != expected_uid:
        raise PermissionError(
            f"UID {uid} is not allowed to act as agent '{claimed_agent}' (expected uid {expected_uid})"
        )


def _dispatch(request: dict[str, Any], peer_uid: int = -1) -> Any:
    req_type = request.get("type")
    agent_name = request.get("agent")

    # Agent-specific operations must go to the agent's Manas process.
    if req_type in _PER_AGENT_TYPES:
        if not agent_name:
            raise ValueError(f"'{req_type}' requires 'agent' field")
        _require_agent_uid(peer_uid, agent_name)
        registry = runtime.get_registry()
        config = registry.get(agent_name)
        if config is None:
            raise ValueError(f"Agent '{agent_name}' not found")
        if not _is_manas_live(config):
            raise RuntimeError(
                f"Manas is not running for agent '{agent_name}'. "
                "Start it with: sudo aurelia agent start <name>"
            )
        return _route_to_manas(config, request)

    match req_type:
        case "list_agents":
            return runtime.list_agents()
        case "get_health":
            return runtime.get_health()
        case "get_budget_info":
            return runtime.get_budget_info(request["agent"])
        case "schedule":
            from .scheduler import AGENT_TYPES, ScheduledItem, write_scheduled_item
            agent = request.get("agent", "")
            if not agent:
                raise ValueError("schedule requires 'agent'")
            _require_agent_uid(peer_uid, agent)
            task_type = request.get("schedule_type", "scheduled_task")
            if task_type not in AGENT_TYPES:
                raise PermissionError(
                    f"Agents may only schedule {sorted(AGENT_TYPES)}, not '{task_type}'"
                )
            item = ScheduledItem(
                agent=agent,
                goal=request.get("goal", ""),
                type=task_type,
                trigger_time=request.get("trigger_time"),
                recurring=request.get("recurring", False),
                interval_hours=request.get("interval_hours"),
                rebirth_from=request.get("rebirth_from"),
                created_by=request.get("created_by", agent),
                payload=request.get("payload") or {},
            )
            write_scheduled_item(item)
            scheduler = getattr(runtime, "_scheduler", None)
            if scheduler:
                scheduler.tick_now()
            return {"status": "scheduled", "id": item.id}
        case "registry_reload":
            _require_admin_uid(peer_uid)
            registry = runtime.get_registry()
            registry._refresh()
            return {"status": "reloaded", "agents": registry.all_agents()}
        case "scheduler_tick":
            _require_admin_uid(peer_uid)
            scheduler = getattr(runtime, "_scheduler", None)
            if scheduler is None:
                raise RuntimeError("Scheduler not available")
            scheduler.tick_now()
            return {"status": "ticked"}
        case _:
            raise ValueError(f"Unknown request type: {req_type!r}")


def _serialize(obj: Any) -> Any:
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
                        raise RuntimeError(
                            f"Manas is not running for agent '{request.get('agent', 'unknown')}'. "
                            "Start it with: sudo aurelia agent start <name>"
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

            t_start = time.monotonic()
            try:
                result = _dispatch(request, peer_uid=uid)
                duration_ms = int((time.monotonic() - t_start) * 1000)
                response = {"id": req_id, "status": "ok", "data": _serialize(result)}
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
    if SOCKET_PATH.exists() or SOCKET_PATH.is_symlink():
        SOCKET_PATH.unlink()
    SOCKET_PATH.parent.mkdir(parents=True, exist_ok=True)

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(str(SOCKET_PATH))
    server.listen(64)

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
            os.chmod(str(SOCKET_PATH), SOCKET_MODE_DEV)
            log.info(
                f"[runtime_daemon] Dev mode — socket {SOCKET_PATH} mode=666 "
                f"(not root, skipping group ownership)"
            )
    except KeyError:
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
        server.settimeout(1.0)

        log.info(f"[runtime_daemon] Listening on {SOCKET_PATH} (max_workers={MAX_WORKERS})")

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            self._executor = executor
            while not self._shutdown.is_set():
                try:
                    conn, _ = server.accept()
                    executor.submit(_handle_connection, conn)
                except socket.timeout:
                    continue
                except OSError as e:
                    if not self._shutdown.is_set():
                        log.error(f"[runtime_daemon] Accept error: {e}")

        server.close()
        try:
            SOCKET_PATH.unlink(missing_ok=True)
        except OSError:
            pass
        log.info("[runtime_daemon] Shutdown complete.")


def main() -> None:
    log.info(f"[runtime_daemon] Starting (pid={os.getpid()}, uid={os.getuid()})")

    from .scheduler import SchedulerDaemon
    scheduler = SchedulerDaemon()
    runtime._scheduler = scheduler
    scheduler_thread = threading.Thread(target=scheduler.run, daemon=True, name="scheduler")
    scheduler_thread.start()
    log.info("[runtime_daemon] Scheduler thread started")

    daemon = RuntimeDaemon()
    daemon.run()


if __name__ == "__main__":
    main()
