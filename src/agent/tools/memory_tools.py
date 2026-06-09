"""Curated tools for reading runtime-managed memory (akasha and memory/extended)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...config import AgentConfig


def _list_incarnations(config: AgentConfig) -> dict[str, Any]:
    """List past dissolved incarnation IDs from akasha."""
    akasha = config.akasha_dir
    if not akasha.exists():
        return {"incarnations": []}
    ids = sorted(
        p.name for p in akasha.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    )
    return {"incarnations": ids, "count": len(ids)}


def _read_incarnation(config: AgentConfig, incarnation_id: str) -> dict[str, Any]:
    """Read a past incarnation transcript from akasha."""
    if not incarnation_id or "/" in incarnation_id or incarnation_id.startswith("."):
        return {"error": "invalid incarnation_id"}
    inc_dir = config.akasha_dir / incarnation_id
    if not inc_dir.exists():
        return {"error": f"incarnation '{incarnation_id}' not found"}
    transcript_file = inc_dir / f"{incarnation_id}-transcript.jsonl"
    if not transcript_file.exists():
        # fallback: find any .jsonl in the dir
        candidates = list(inc_dir.glob("*.jsonl"))
        if not candidates:
            return {"error": "no transcript found"}
        transcript_file = candidates[0]
    try:
        lines = transcript_file.read_text(encoding="utf-8").strip().splitlines()
        entries = []
        for line in lines:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        return {"incarnation_id": incarnation_id, "entries": entries, "count": len(entries)}
    except OSError as e:
        return {"error": str(e)}


def _search_memory_extended(config: AgentConfig, query: str) -> dict[str, Any]:
    """Search memory/extended/ files for entries matching query."""
    ext_dir = config.memory_extended_dir
    if not ext_dir.exists():
        return {"matches": [], "searched_files": 0}

    query_lower = query.lower()
    matches = []
    files_searched = 0

    for f in sorted(ext_dir.glob("*.jsonl")):
        files_searched += 1
        try:
            for line in f.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    text = json.dumps(entry).lower()
                    if query_lower in text:
                        matches.append(entry)
                except json.JSONDecodeError:
                    pass
        except OSError:
            pass

    return {"matches": matches, "count": len(matches), "searched_files": files_searched}


def _read_memory_extended(config: AgentConfig, filename: str | None) -> dict[str, Any]:
    """Read memory/extended/ files. filename=None lists available files."""
    ext_dir = config.memory_extended_dir
    if not ext_dir.exists():
        return {"files": []} if filename is None else {"error": "no extended memory"}

    if filename is None:
        files = sorted(p.name for p in ext_dir.iterdir() if p.is_file())
        return {"files": files, "count": len(files)}

    if "/" in filename or filename.startswith("."):
        return {"error": "invalid filename"}

    path = ext_dir / filename
    if not path.exists():
        # try with .jsonl extension
        path = ext_dir / (filename + ".jsonl")
    if not path.exists():
        return {"error": f"file '{filename}' not found"}

    try:
        content = path.read_text(encoding="utf-8")
        if path.suffix == ".jsonl":
            entries = []
            for line in content.splitlines():
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        entries.append({"raw": line})
            return {"filename": path.name, "entries": entries}
        return {"filename": path.name, "content": content}
    except OSError as e:
        return {"error": str(e)}


# ── Tool schemas ───────────────────────────────────────────────────────────────

_LIST_INCARNATIONS_SCHEMA = {
    "name": "list_incarnations",
    "description": "List all past dissolved incarnation IDs in akasha. The current incarnation is already in your context — not listed here.",
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

_READ_INCARNATION_SCHEMA = {
    "name": "read_incarnation",
    "description": "Read the full transcript of a past dissolved incarnation from akasha.",
    "input_schema": {
        "type": "object",
        "properties": {
            "incarnation_id": {
                "type": "string",
                "description": "The incarnation ID to read (from list_incarnations).",
            }
        },
        "required": ["incarnation_id"],
    },
}

_SEARCH_MEMORY_SCHEMA = {
    "name": "search_memory",
    "description": "Search memory/extended/ for entries matching a query string. Covers past incarnation summaries and stored memory flags.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Text to search for across extended memory files.",
            }
        },
        "required": ["query"],
    },
}

_READ_MEMORY_EXTENDED_SCHEMA = {
    "name": "read_memory_extended",
    "description": "Read memory/extended/ files. Pass filename=null to list available files, or a filename to read that file.",
    "input_schema": {
        "type": "object",
        "properties": {
            "filename": {
                "type": ["string", "null"],
                "description": "File to read, or null to list available files.",
            }
        },
        "required": [],
    },
}


# ── Registration ───────────────────────────────────────────────────────────────


def register_memory_tools(registry: Any, agent_config: AgentConfig) -> None:
    registry.register(
        _LIST_INCARNATIONS_SCHEMA,
        lambda inp, **ctx: _list_incarnations(agent_config),
    )
    registry.register(
        _READ_INCARNATION_SCHEMA,
        lambda inp, **ctx: _read_incarnation(agent_config, inp.get("incarnation_id", "")),
    )
    registry.register(
        _SEARCH_MEMORY_SCHEMA,
        lambda inp, **ctx: _search_memory_extended(agent_config, inp.get("query", "")),
    )
    registry.register(
        _READ_MEMORY_EXTENDED_SCHEMA,
        lambda inp, **ctx: _read_memory_extended(agent_config, inp.get("filename")),
    )
