"""Manas — the per-agent long-lived process. The Ālayavijñāna.

One Manas process per agent, running as the agent's Linux user. Samsara routes
dispatches here via Unix socket; Manas spawns incarnation threads and returns
results. Bash_exec runs without sudo because the process already is the agent.

Entry point: python -m src.samsara.manas <agent_name>
Socket:      /var/aurelia/run/<agent>/manas.sock  (agent:aurelia_admin 660)
PID file:    /var/aurelia/run/<agent>/manas.pid
"""

from __future__ import annotations

import json
import os
import signal
import socket
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from .config import AGENT_RUN_BASE, load_agent_config
from . import runtime_core as runtime
from ..agent.hooks import HookType


def _serialize(obj: Any) -> Any:
    import dataclasses
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _serialize(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, list):
        return [_serialize(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, Path):
        return str(obj)
    return obj


class Manas:
    def __init__(self, agent_name: str) -> None:
        self.name = agent_name
        self.config = load_agent_config(agent_name)
        self._shutting_down = threading.Event()
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix=f"manas-{agent_name}")

    def run(self) -> None:
        run_dir = AGENT_RUN_BASE / self.name
        run_dir.mkdir(parents=True, exist_ok=True)

        socket_path = self.config.manas_socket
        pid_path = self.config.manas_pid

        if socket_path.exists():
            socket_path.unlink()

        pid_path.write_text(str(os.getpid()))

        # Signal bash_exec to skip sudo — we're already running as the agent user
        os.environ["AURELIA_MANAS_AGENT"] = self.name

        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(socket_path))
        # 660: agent user + aurelia_admin group (samsara) can connect; others cannot
        os.chmod(str(socket_path), 0o660)
        server.listen(16)
        server.settimeout(1.0)

        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        print(f"[manas:{self.name}] Started (pid={os.getpid()})", flush=True)

        try:
            while not self._shutting_down.is_set():
                try:
                    conn, _ = server.accept()
                    self._executor.submit(self._handle_connection, conn)
                except socket.timeout:
                    continue
                except OSError as e:
                    if not self._shutting_down.is_set():
                        print(f"[manas:{self.name}] Accept error: {e}", flush=True)
        finally:
            server.close()
            socket_path.unlink(missing_ok=True)
            pid_path.unlink(missing_ok=True)
            print(f"[manas:{self.name}] Shutdown complete.", flush=True)

    def _signal_handler(self, signum: int, frame: Any) -> None:
        print(f"[manas:{self.name}] Signal {signum} — shutting down.", flush=True)
        self._shutting_down.set()

    def _handle_connection(self, conn: socket.socket) -> None:
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
                req_type = request.get("type")

                if req_type == "ping":
                    conn.sendall(json.dumps({"status": "ok"}).encode() + b"\n")
                    return

                if req_type == "terminate":
                    conn.sendall(json.dumps({"status": "ok", "message": "shutting_down"}).encode() + b"\n")
                    self._shutting_down.set()
                    return

                is_streaming = bool(request.get("stream")) and req_type == "dispatch"

                if is_streaming:
                    conn.settimeout(None)

                    def send_frame(frame: dict) -> None:
                        conn.sendall(json.dumps(frame).encode() + b"\n")

                    try:
                        result = runtime.dispatch(
                            agent=request["agent"],
                            incarnation=request["incarnation"],
                            hook=HookType(request["hook"]),
                            payload=request.get("payload", {}),
                            stream_callback=send_frame,
                        )
                        send_frame({"type": "done", "status": "ok", "data": _serialize(result)})
                    except Exception as exc:
                        send_frame({"type": "done", "status": "error",
                                    "error": type(exc).__name__, "message": str(exc)})
                    return

                try:
                    result = self._dispatch(request)
                    response = {"status": "ok", "data": _serialize(result)}
                except Exception as exc:
                    response = {"status": "error", "error": type(exc).__name__, "message": str(exc)}

                conn.sendall(json.dumps(response).encode() + b"\n")

            except json.JSONDecodeError:
                pass
            except socket.timeout:
                pass
            except Exception as e:
                print(f"[manas:{self.name}] Connection error: {e}", flush=True)

    def _dispatch(self, request: dict) -> Any:
        req_type = request.get("type")

        match req_type:
            case "spawn":
                return runtime.spawn(agent=request["agent"], goal=request.get("goal"))
            case "dispatch":
                return runtime.dispatch(
                    agent=request["agent"],
                    incarnation=request["incarnation"],
                    hook=HookType(request["hook"]),
                    payload=request.get("payload", {}),
                )
            case "get_history":
                return runtime.get_history(agent=request["agent"], incarnation=request["incarnation"])
            case "list_incarnations":
                return runtime.list_incarnations(agent=request["agent"])
            case "get_primary" | "get_active":
                return {"primary": runtime.get_primary(request["agent"])}
            case "set_primary":
                runtime.set_primary(request["agent"], request["name"])
                return {"status": "ok"}
            case "get_budget_info":
                return runtime.get_budget_info(request["agent"])
            case "trigger_bardo":
                agent = request["agent"]
                primary = runtime.get_primary(agent)
                if not primary:
                    return {"status": "no_active", "agent": agent}
                return runtime.trigger_bardo(agent, primary)
            case "internal_process":
                from .runtime_daemon import _dispatch_internal_process
                return _dispatch_internal_process(request)
            case _:
                raise ValueError(f"Unknown request type: {req_type!r}")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m src.samsara.manas <agent_name>")
        sys.exit(1)
    Manas(sys.argv[1]).run()


if __name__ == "__main__":
    main()
