"""
TranscriptStreamer — tail a JSONL transcript and pretty-print entries live.

Usage:
    with TranscriptStreamer(transcript_path) as streamer:
        # do blocking work — streamer polls in background
        pass
    # on exit: streamer flushes any remaining entries
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path


# ── ANSI colours (no external deps) ──────────────────────────────────────────

_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_DIM    = "\033[2m"
_CYAN   = "\033[36m"
_YELLOW = "\033[33m"
_GREEN  = "\033[32m"
_BLUE   = "\033[34m"
_MAGENTA = "\033[35m"
_RED    = "\033[31m"


def _c(text: str, *codes: str) -> str:
    return "".join(codes) + text + _RESET


# ── Entry rendering ───────────────────────────────────────────────────────────


def _trunc(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n] + "…"


def _render_tool_call(name: str, inp: dict) -> str:
    """Extract the human-meaningful part of a tool call input."""
    if name == "bash_exec":
        cmd = inp.get("command", "")
        return f"{_c('$', _YELLOW, _BOLD)} {_c(_trunc(cmd, 200), _YELLOW)}"

    if name in ("log_note", "memory_write"):
        text = inp.get("note") or inp.get("content", "")
        tier = inp.get("tier", "")
        suffix = f"  {_c(f'[{tier}]', _DIM)}" if tier else ""
        return f"{_c('✎', _MAGENTA, _BOLD)} {_c(name, _MAGENTA)}{suffix}\n  {_c(_trunc(text, 300), _DIM)}"

    if name == "dashboard_notification":
        content = inp.get("content", "")
        category = inp.get("category", "")
        return f"{_c('📋', _BLUE)} {_c(name, _BLUE)}  {_c(f'[{category}]', _DIM)}\n  {_c(_trunc(content, 200), _DIM)}"

    if name == "write_file":
        path = inp.get("path", "")
        content = inp.get("content", "")
        lines = content.count("\n") + 1
        return f"{_c('📝', _CYAN)} {_c(name, _CYAN)}  {_c(path, _BOLD)}  {_c(f'({lines} lines)', _DIM)}"

    if name == "read_file":
        path = inp.get("path", "")
        return f"{_c('📖', _DIM)} {_c(name, _DIM)}  {_c(path, _DIM)}"

    # Fallback: show tool name + compact input
    inp_str = json.dumps(inp, ensure_ascii=False)
    return f"{_c('⚙', _YELLOW)} {_c(name, _BOLD, _YELLOW)}  {_c(_trunc(inp_str, 160), _DIM)}"


def _render_tool_result(result: object) -> str | None:
    """Extract the human-meaningful part of a tool result."""
    if isinstance(result, dict):
        # bash_exec result
        if "stdout" in result or "stderr" in result:
            stdout = (result.get("stdout") or "").strip()
            stderr = (result.get("stderr") or "").strip()
            exit_code = result.get("exit_code", 0)
            parts = []
            if stdout:
                parts.append(_trunc(stdout, 400))
            if stderr:
                parts.append(_c(_trunc(stderr, 200), _RED))
            if exit_code != 0:
                parts.append(_c(f"exit {exit_code}", _RED))
            if not parts:
                return None
            indented = "\n    ".join("\n".join(parts).splitlines())
            return f"  {_c('└', _DIM)} {_c(indented, _DIM)}"

        # status/written style results — just show status
        status = result.get("status") or result.get("message", "")
        if status:
            return f"  {_c('└', _DIM)} {_c(_trunc(str(status), 120), _DIM)}"

    if isinstance(result, str) and result.strip():
        return f"  {_c('└', _DIM)} {_c(_trunc(result.strip(), 200), _DIM)}"

    return None


def _render_entry(entry: dict) -> str | None:
    t = entry.get("type")

    if t == "human_message":
        # Skip — not interesting to watch live (we control the input)
        return None

    if t == "tool_call":
        name = entry.get("tool_name", "?")
        inp = entry.get("tool_input", {})
        return "\n" + _render_tool_call(name, inp)

    if t == "tool_result":
        result = entry.get("result", "")
        rendered = _render_tool_result(result)
        return rendered + "\n" if rendered else None

    if t == "assistant_message":
        content = entry.get("content", "").strip()
        if not content:
            return None
        thinking_blocks = entry.get("thinking_blocks")
        parts = [f"\n{_c('─' * 60, _DIM)}"]
        if thinking_blocks:
            for tb in thinking_blocks:
                thinking = tb.get("thinking", "").strip()
                if thinking:
                    preview = _trunc(thinking, 500)
                    indented = "\n  ".join(preview.splitlines())
                    parts.append(f"{_c('💭', _MAGENTA, _DIM)}\n  {_c(indented, _DIM)}\n")
        parts.append(f"{_c('◀', _BOLD, _GREEN)} {content}")
        parts.append(f"{_c('─' * 60, _DIM)}\n")
        return "\n".join(parts)

    return None


# ── Streamer ──────────────────────────────────────────────────────────────────


class TranscriptStreamer:
    """
    Tails a JSONL transcript file and renders new entries to stdout in real time.
    Runs a poll loop in a background thread.
    """

    POLL_INTERVAL = 0.3  # seconds

    def __init__(self, transcript_path: Path) -> None:
        self._path = transcript_path
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._offset = 0  # byte offset — only read new data

    def __enter__(self) -> "TranscriptStreamer":
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()

    def start(self) -> None:
        # Capture current file size so we only stream new entries
        if self._path.exists():
            self._offset = self._path.stat().st_size
        self._stop.clear()
        self._thread = threading.Thread(target=self._poll, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        # Flush any remaining entries written between last poll and stop
        self._drain()

    def _poll(self) -> None:
        while not self._stop.is_set():
            self._drain()
            self._stop.wait(self.POLL_INTERVAL)

    def _drain(self) -> None:
        if not self._path.exists():
            return
        try:
            with self._path.open("rb") as f:
                f.seek(self._offset)
                chunk = f.read()
                if not chunk:
                    return
                self._offset += len(chunk)

            for raw_line in chunk.decode("utf-8", errors="replace").splitlines():
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    entry = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
                rendered = _render_entry(entry)
                if rendered is not None:
                    print(rendered, flush=True)
        except OSError:
            pass
