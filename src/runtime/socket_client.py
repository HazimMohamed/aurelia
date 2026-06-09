"""Thin client for the Aurelia runtime Unix socket.

Used by agent tool handlers that need to send requests to the runtime daemon
without going through HTTP.  The caller must already be running as an agent
Linux user — the daemon authenticates via SO_PEERCRED, no bearer token needed.
"""

from __future__ import annotations

import json
import socket
from pathlib import Path
from typing import Any

SOCKET_PATH = Path("/var/aurelia/runtime.sock")


def send_runtime_request(payload: dict[str, Any], timeout: float = 10.0) -> dict[str, Any]:
    """Send a JSON request to the runtime socket and return the parsed response.

    Raises RuntimeError if the daemon returns an error frame or the connection
    fails.  Never returns None — callers can always treat the result as a dict.
    """
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        try:
            s.connect(str(SOCKET_PATH))
        except (FileNotFoundError, ConnectionRefusedError) as exc:
            raise RuntimeError(f"Runtime socket unavailable ({SOCKET_PATH}): {exc}") from exc

        s.sendall(json.dumps(payload).encode("utf-8") + b"\n")

        buf = b""
        while b"\n" not in buf:
            chunk = s.recv(4096)
            if not chunk:
                break
            buf += chunk

        line = buf.split(b"\n", 1)[0]
        response = json.loads(line.decode("utf-8"))

    if response.get("status") == "error":
        raise RuntimeError(response.get("message", "Runtime returned error"))

    return response.get("data", response)
