"""Memory system: semantic core/extended and episodic core/extended writes."""

from __future__ import annotations

import fcntl
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..samsara.config import AgentConfig

SHARED_HAZIM_PATH = Path("/var/aurelia/shared/hazim.jsonl")
SHARED_INTRO_PATH = Path("/var/aurelia/shared/hazim_introduction.md")

# Approximate token cap for semantic core (~500 tokens → ~2000 chars)
SEMANTIC_CORE_CHAR_CAP = 2000

# Max entries from shared hazim.jsonl to load (by score)
SHARED_HAZIM_MAX_ENTRIES = 10
SHARED_HAZIM_MAX_CHARS = 2000

# How many days before shared context entries expire
SHARED_HAZIM_EXPIRY_DAYS = 30


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def write_with_lock(path: Path, entry: dict[str, Any]) -> None:
    """Append a JSONL entry to a file with exclusive file lock."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read all entries from a JSONL file. Returns empty list if missing."""
    if not path.exists():
        return []
    entries = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    except OSError:
        pass
    return entries


# ── Semantic memory ──────────────────────────────────────────────────────────────

def write_semantic_core(config: AgentConfig, entry: dict[str, Any]) -> None:
    """Write to semantic core with fcntl lock. Enforces size cap by pruning oldest."""
    path = config.semantic_core_path
    path.parent.mkdir(parents=True, exist_ok=True)

    # Read existing entries
    existing = read_jsonl(path)

    # Add new entry
    existing.append(entry)

    # Enforce approximate size cap
    while True:
        total_chars = sum(len(json.dumps(e)) for e in existing)
        if total_chars <= SEMANTIC_CORE_CHAR_CAP or len(existing) <= 1:
            break
        # Drop lowest importance or oldest entry
        # Sort by importance (low=0, medium=1, high=2) then ts — drop first
        importance_rank = {"low": 0, "medium": 1, "high": 2}
        existing.sort(key=lambda e: (
            importance_rank.get(e.get("importance", "medium"), 1),
            e.get("ts", ""),
        ))
        existing.pop(0)

    # Rewrite file atomically with lock
    with open(path, "w", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            for e in existing:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def write_semantic_extended(config: AgentConfig, category: str, entry: dict[str, Any]) -> None:
    """Write to semantic extended (domain-specific file)."""
    if not category:
        category = "general"
    path = config.semantic_extended_dir / f"{category}.jsonl"
    write_with_lock(path, entry)


def load_semantic_core(config: AgentConfig) -> str:
    """Load and format semantic core for context assembly."""
    entries = read_jsonl(config.semantic_core_path)
    if not entries:
        return ""

    lines = ["## Semantic Memory (Core — Always Loaded)\n"]
    for entry in entries:
        content = entry.get("content", "")
        importance = entry.get("importance", "")
        category = entry.get("category", "")
        ts = entry.get("ts", "")
        tier = entry.get("tier", "")

        meta = []
        if importance:
            meta.append(f"importance:{importance}")
        if category:
            meta.append(f"category:{category}")
        if tier:
            meta.append(f"tier:{tier}")

        meta_str = f" [{', '.join(meta)}]" if meta else ""
        lines.append(f"- {content}{meta_str}")

    return "\n".join(lines)


def load_semantic_extended_relevant(config: AgentConfig, query: str, max_chars: int = 1500) -> str:
    """Load relevant semantic extended entries based on keyword matching."""
    if not config.semantic_extended_dir.exists():
        return ""

    query_words = set(query.lower().split())
    matched_entries = []

    for ext_file in config.semantic_extended_dir.glob("*.jsonl"):
        entries = read_jsonl(ext_file)
        for entry in entries:
            content = entry.get("content", "").lower()
            if any(word in content for word in query_words):
                matched_entries.append(entry)

    if not matched_entries:
        return ""

    lines = ["## Semantic Memory (Extended — Relevant to current topic)\n"]
    total_chars = 0
    for entry in matched_entries:
        content = entry.get("content", "")
        line = f"- {content}"
        if total_chars + len(line) > max_chars:
            break
        lines.append(line)
        total_chars += len(line)

    return "\n".join(lines)


# ── Episodic memory ───────────────────────────────────────────────────────────

def load_episodic_core(config: AgentConfig) -> str:
    """Load and format all episodic core entries (formative experiences)."""
    core_dir = config.episodic_core_dir
    if not core_dir.exists():
        return ""

    entries = []
    for ep_file in sorted(core_dir.glob("*.jsonl")):
        entries.extend(read_jsonl(ep_file))

    if not entries:
        return ""

    lines = ["## Episodic Memory (Core — Formative Experiences)\n"]
    for entry in entries:
        subtype = entry.get("subtype", entry.get("type", ""))
        note = entry.get("note", entry.get("content", ""))
        incarnation = entry.get("incarnation", "")
        ts = entry.get("ts", "")

        label = {
            "formative_success": "Success",
            "formative_error": "Error",
            "formative_moment": "Moment",
        }.get(subtype, subtype or "Note")

        line = f"- [{label}]"
        if incarnation:
            line += f" (from {incarnation})"
        line += f": {note}"
        lines.append(line)

    return "\n".join(lines)


def load_episodic_extended_relevant(config: AgentConfig, query: str, limit: int = 3) -> str:
    """Load relevant episodic extended entries based on keyword matching."""
    extended_dir = config.episodic_extended_dir
    if not extended_dir.exists():
        return ""

    query_words = set(query.lower().split())
    results = []

    for ep_file in sorted(extended_dir.glob("*.jsonl"), reverse=True):
        entries = read_jsonl(ep_file)
        for entry in entries:
            summary_data = entry.get("summary", {})
            if isinstance(summary_data, dict):
                text = " ".join([
                    summary_data.get("summary", ""),
                    " ".join(summary_data.get("topics", [])),
                    " ".join(summary_data.get("insights", [])),
                ]).lower()
            else:
                text = str(summary_data).lower()

            if any(word in text for word in query_words):
                results.append(entry)
                if len(results) >= limit:
                    break

        if len(results) >= limit:
            break

    if not results:
        return ""

    lines = ["## Episodic Memory (Extended — Relevant to current topic)\n"]
    for entry in results:
        incarnation = entry.get("incarnation", "unknown")
        summary_data = entry.get("summary", {})
        if isinstance(summary_data, dict):
            summary = summary_data.get("summary", "")
        else:
            summary = str(summary_data)
        if summary:
            lines.append(f"**{incarnation}:** {summary}")

    return "\n".join(lines)


def search_episodic(config: AgentConfig, query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Keyword search across episodic/extended for matching entries."""
    extended_dir = config.episodic_extended_dir
    if not extended_dir.exists():
        return []

    query_words = set(query.lower().split())
    results = []

    for ep_file in sorted(extended_dir.glob("*.jsonl"), reverse=True):
        entries = read_jsonl(ep_file)
        for entry in entries:
            summary_data = entry.get("summary", {})
            if isinstance(summary_data, dict):
                text = " ".join([
                    summary_data.get("summary", ""),
                    " ".join(summary_data.get("topics", [])),
                    " ".join(summary_data.get("insights", [])),
                ]).lower()
            else:
                text = str(summary_data).lower()

            if any(word in text for word in query_words):
                results.append(entry)
                if len(results) >= limit:
                    return results

    return results


# ── Shared hazim context ──────────────────────────────────────────────────────

def load_shared_hazim_context() -> str:
    """Load top-scored shared hazim context entries, pruning expired ones."""
    from datetime import datetime, timedelta

    if not SHARED_HAZIM_PATH.exists():
        return ""

    now = datetime.now(timezone.utc)
    expiry_cutoff = now - timedelta(days=SHARED_HAZIM_EXPIRY_DAYS)
    entries = read_jsonl(SHARED_HAZIM_PATH)

    # Filter expired entries
    valid_entries = []
    for entry in entries:
        ts_str = entry.get("ts", "")
        if ts_str:
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if ts < expiry_cutoff:
                    continue
            except ValueError:
                pass
        valid_entries.append(entry)

    if not valid_entries:
        return ""

    # Sort by score descending, take top N
    valid_entries.sort(key=lambda e: float(e.get("score", 0.5)), reverse=True)
    top_entries = valid_entries[:SHARED_HAZIM_MAX_ENTRIES]

    # Build text, respect char budget
    lines = ["## Shared Context (About Hazim — Council-wide Knowledge)\n"]
    total_chars = 0
    for entry in top_entries:
        content = entry.get("content", "")
        entry_type = entry.get("type", "")
        author = entry.get("author", "")

        label = f"[{entry_type}]" if entry_type else ""
        attribution = f" (from {author})" if author else ""
        line = f"- {label}{attribution}: {content}"

        if total_chars + len(line) > SHARED_HAZIM_MAX_CHARS:
            break
        lines.append(line)
        total_chars += len(line)

    return "\n".join(lines)


def load_hazim_introduction() -> str:
    """Load the Hazim introduction file."""
    if not SHARED_INTRO_PATH.exists():
        return ""
    try:
        return SHARED_INTRO_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def write_shared_context(
    author: str,
    entry_type: str,
    content: str,
    score: float = 0.7,
) -> dict[str, Any]:
    """Write an entry to the shared hazim context with file lock."""
    entry = {
        "ts": _now_iso(),
        "type": entry_type,
        "author": author,
        "content": content,
        "score": score,
    }
    write_with_lock(SHARED_HAZIM_PATH, entry)
    return entry


# ── Permission setting (graceful fallback) ────────────────────────────────────

def set_permissions(path: Path, mode: int, uid: int = -1, gid: int = -1) -> None:
    """Set file permissions and ownership, with graceful fallback if non-root."""
    import os
    try:
        os.chmod(path, mode)
    except PermissionError:
        pass  # Non-root — log and continue

    if uid != -1 or gid != -1:
        try:
            os.chown(path, uid, gid)
        except (PermissionError, OSError):
            pass  # Non-root — acceptable in dev
