"""Bardo process: summarize transcript, process memory flags, archive to Akasha."""

from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import anthropic

from ..config import AgentConfig
from ..agent.transcript import (
    read_entries,
    append_entry,
    write_bardo_complete,
    transcript_to_messages,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _summarize_transcript(
    agent_name: str,
    incarnation_name: str,
    entries: list[dict[str, Any]],
    bardo_model: str,
) -> str:
    """Call Sonnet to summarize the incarnation transcript."""
    lines = []
    for entry in entries:
        entry_type = entry.get("type", "")
        content = entry.get("content", "")
        ts = entry.get("ts", "")
        if entry_type == "human_message":
            lines.append(f"[{ts}] Human: {content}")
        elif entry_type == "assistant_message":
            lines.append(f"[{ts}] {agent_name.capitalize()}: {content}")
        elif entry_type == "incarnation_start":
            lines.append(f"[{ts}] --- Incarnation started: {incarnation_name} ---")
        elif entry_type == "memory_flag":
            lines.append(f"[{ts}] [MEMORY FLAG] tier={entry.get('tier')} importance={entry.get('importance')}: {content}")
        elif entry_type == "agent_note":
            lines.append(f"[{ts}] [NOTE] {content}")

    transcript_text = "\n".join(lines) if lines else "(empty incarnation)"

    prompt = (
        f"You are summarizing the completed incarnation '{incarnation_name}' of the agent '{agent_name}'.\n\n"
        f"Create a concise episodic memory record that captures:\n"
        f"1. Key topics discussed\n"
        f"2. Important decisions or insights\n"
        f"3. Emotional tone and quality of the interaction\n"
        f"4. Anything the agent should remember in future incarnations\n\n"
        f"Transcript:\n{transcript_text}\n\n"
        f"Write the summary as a structured JSON object with fields: "
        f"summary (string), topics (list of strings), insights (list of strings), tone (string)."
    )

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=bardo_model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()

    try:
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        parsed = json.loads(raw)
        return json.dumps(parsed)
    except (json.JSONDecodeError, IndexError):
        return json.dumps({"summary": raw, "topics": [], "insights": [], "tone": "unknown"})


def _extract_semantic_insights(
    agent_name: str,
    incarnation_name: str,
    entries: list[dict[str, Any]],
    bardo_model: str,
) -> list[dict[str, Any]]:
    """
    Use Sonnet to identify additional semantic insights from the transcript
    that the agent didn't explicitly flag but that pass the six-month test.
    Returns list of insight dicts.
    """
    lines = []
    for entry in entries:
        entry_type = entry.get("type", "")
        content = entry.get("content", "")
        ts = entry.get("ts", "")
        if entry_type in ("human_message", "assistant_message"):
            role = "Human" if entry_type == "human_message" else agent_name.capitalize()
            lines.append(f"[{ts}] {role}: {content}")

    transcript_text = "\n".join(lines) if lines else "(empty)"

    if len(transcript_text) < 100:
        return []

    prompt = (
        f"You are processing the bardo (memory consolidation) for agent '{agent_name}'.\n\n"
        f"Read this conversation transcript and identify any insights about Hazim (God-lite) "
        f"or the agent's domain that should be preserved as semantic memory.\n\n"
        f"Apply the six-month test: only include things that would still be true and useful "
        f"six months from now.\n\n"
        f"Transcript:\n{transcript_text}\n\n"
        f"Return a JSON array of objects, each with fields:\n"
        f"  - content: the insight (string)\n"
        f"  - importance: 'low', 'medium', or 'high'\n"
        f"  - category: a short tag like 'preferences', 'patterns', 'facts' (string)\n\n"
        f"Return an empty array [] if there are no insights worth preserving.\n"
        f"Return only the JSON array, no other text."
    )

    client = anthropic.Anthropic()
    try:
        response = client.messages.create(
            model=bardo_model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return parsed
    except Exception as e:
        print(f"[bardo] Semantic insight extraction failed: {e}", file=sys.stderr)

    return []


def _set_permissions_safe(path: Path, mode: int) -> None:
    """Set file permissions, gracefully failing if non-root."""
    try:
        os.chmod(path, mode)
    except (PermissionError, OSError):
        pass


def _worth_consolidating(entries: list[dict[str, Any]]) -> bool:
    """
    Conservative check: only run Sonnet summarization if there's something real to consolidate.
    Purely mechanical incarnations (heartbeats that did nothing) just get archived.
    Skip archiving entirely if the transcript has no meaningful content at all.
    """
    meaningful_types = {"human_message", "memory_flag"}
    tool_calls = [e for e in entries if e.get("type") == "tool_call"]
    has_meaningful = any(e.get("type") in meaningful_types for e in entries)
    # Also consolidate if agent did substantial tool work (>2 calls) even without human messages
    has_real_work = len(tool_calls) > 2
    return has_meaningful or has_real_work


def _worth_archiving(entries: list[dict[str, Any]]) -> bool:
    """
    Even lighter check: is there anything beyond the incarnation_start marker?
    Completely empty incarnations (precheck passed but agent did nothing) aren't worth keeping.
    """
    non_start = [e for e in entries if e.get("type") not in ("incarnation_start", "bardo_complete")]
    return len(non_start) > 0


def _handoff_primary_if_needed(agent_config: AgentConfig, incarnation_name: str) -> None:
    """If the incarnation being bardo'd is primary, promote another or spawn fresh."""
    from ..agent.incarnation import set_primary_incarnation, spawn_incarnation

    symlink = agent_config.primary_symlink
    if not (symlink.is_symlink() and symlink.resolve().name == incarnation_name):
        return

    others = [
        d for d in agent_config.memory_dir.iterdir()
        if d.is_dir()
        and d.name not in (incarnation_name, "extended")
        and (d / "transcript.jsonl").exists()
    ]
    if others:
        next_primary = max(others, key=lambda d: d.stat().st_mtime)
        set_primary_incarnation(agent_config, next_primary.name)
        print(
            f"[bardo] Primary '{incarnation_name}' archived; '{next_primary.name}' promoted to primary",
            file=sys.stderr,
        )
    else:
        new_name = spawn_incarnation(agent_config, make_primary=True)
        print(
            f"[bardo] Primary '{incarnation_name}' archived; spawned fresh primary '{new_name}'",
            file=sys.stderr,
        )


def run_bardo(agent_config: AgentConfig, incarnation_name: str) -> dict[str, Any]:
    """
    Execute full bardo for a completed incarnation:
    1. Read transcript
    2. Summarize with Sonnet → write episodic/extended
    3. Process memory_flag entries → write semantic (core or extended)
    4. Extract additional semantic insights (bardo-initiated)
    5. Copy transcript to ~/akasha/
    6. Copy scratch to ~/akasha/ if non-empty
    7. Write bardo_complete to transcript (before copy)
    8. Remove current symlink
    9. Clean incarnation folder
    """
    from .memory import write_memory_core, write_memory_extended

    incarnation_dir = agent_config.memory_dir / incarnation_name
    transcript_path = incarnation_dir / "transcript.jsonl"
    scratch_dir = incarnation_dir / "scratch"

    if not incarnation_dir.exists():
        return {"status": "error", "message": f"Incarnation dir not found: {incarnation_dir}"}

    entries = read_entries(transcript_path)
    cycle_count = sum(1 for e in entries if e.get("type") == "human_message")

    if not _worth_archiving(entries):
        # Completely empty — just clean up, nothing to keep
        _handoff_primary_if_needed(agent_config, incarnation_name)
        symlink = agent_config.primary_symlink
        if symlink.is_symlink() and symlink.resolve().name == incarnation_name:
            symlink.unlink()
        shutil.rmtree(incarnation_dir)
        return {"status": "skipped", "reason": "empty incarnation", "incarnation": incarnation_name}

    # Write bardo_complete to transcript before archiving
    write_bardo_complete(transcript_path, incarnation_name, cycle_count)
    entries = read_entries(transcript_path)

    consolidate = _worth_consolidating(entries)

    if not consolidate:
        # Archive to akasha but skip the Sonnet summarization
        akasha_dir = agent_config.akasha_dir / incarnation_name
        akasha_dir.mkdir(parents=True, exist_ok=True)
        akasha_transcript = akasha_dir / f"{incarnation_name}-transcript.jsonl"
        shutil.copy2(transcript_path, akasha_transcript)
        _set_permissions_safe(akasha_transcript, 0o640)
        from ..agent.tools.process_tools import cleanup_incarnation_processes
        cleanup_incarnation_processes(agent_config.home, incarnation_name)
        _handoff_primary_if_needed(agent_config, incarnation_name)
        symlink = agent_config.primary_symlink
        if symlink.is_symlink() and symlink.resolve().name == incarnation_name:
            symlink.unlink()
        shutil.rmtree(incarnation_dir)
        return {"status": "archived", "reason": "not worth consolidating", "incarnation": incarnation_name}

    # 1. Summarize → episodic/extended
    summary_json = _summarize_transcript(
        agent_config.name,
        incarnation_name,
        entries,
        agent_config.bardo.model,
    )

    episodic_dir = agent_config.memory_extended_dir
    episodic_dir.mkdir(parents=True, exist_ok=True)
    episodic_path = episodic_dir / f"{incarnation_name}.jsonl"

    episodic_entry = {
        "ts": _now_iso(),
        "type": "episodic_summary",
        "incarnation": incarnation_name,
        "cycles": cycle_count,
        "summary": json.loads(summary_json),
    }
    append_entry(episodic_path, episodic_entry)
    _set_permissions_safe(episodic_path, 0o640)

    # 2. Process memory_flag entries from transcript
    memory_flags = [e for e in entries if e.get("type") == "memory_flag"]
    for flag in memory_flags:
        flag_entry = {
            "ts": flag.get("ts", _now_iso()),
            "type": "memory_flag",
            "content": flag.get("content", ""),
            "importance": flag.get("importance", "medium"),
            "tier": flag.get("tier", "semantic"),
            "category": flag.get("category", "general"),
            "incarnation": incarnation_name,
            "bardo_processed": True,
        }
        tier = flag.get("tier", "extended")
        if tier == "core":
            # Idempotent — bardo re-confirms it's present after live cycle wrote it
            _ensure_memory_core(agent_config, flag_entry)
        elif tier == "extended":
            write_memory_extended(
                agent_config,
                flag.get("category", "general"),
                flag_entry,
            )
        # other tiers are ignored — no episodic/semantic split exists anymore

    # 3. Extract additional semantic insights (bardo-initiated, catches unflagged)
    if cycle_count > 0:
        insights = _extract_semantic_insights(
            agent_config.name,
            incarnation_name,
            entries,
            agent_config.bardo.model,
        )
        for insight in insights:
            insight_entry = {
                "ts": _now_iso(),
                "type": "bardo_insight",
                "content": insight.get("content", ""),
                "importance": insight.get("importance", "medium"),
                "category": insight.get("category", "general"),
                "incarnation": incarnation_name,
                "source": "bardo",
            }
            if insight_entry["content"]:
                write_memory_extended(
                    agent_config,
                    insight.get("category", "general"),
                    insight_entry,
                )

    # 4. Archive to Akasha
    akasha_dir = agent_config.akasha_dir / incarnation_name
    akasha_dir.mkdir(parents=True, exist_ok=True)

    akasha_transcript = akasha_dir / f"{incarnation_name}-transcript.jsonl"
    shutil.copy2(transcript_path, akasha_transcript)
    _set_permissions_safe(akasha_transcript, 0o640)

    # 5. Copy scratch if non-empty
    if scratch_dir.exists() and any(scratch_dir.iterdir()):
        akasha_scratch = akasha_dir / "scratch"
        if akasha_scratch.exists():
            shutil.rmtree(akasha_scratch)
        shutil.copytree(scratch_dir, akasha_scratch)

    # 6. Kill any background processes started by this incarnation
    from ..agent.tools.process_tools import cleanup_incarnation_processes
    cleanup_incarnation_processes(agent_config.home, incarnation_name)

    # 7. Hand off primary designation if needed, then remove primary symlink
    _handoff_primary_if_needed(agent_config, incarnation_name)
    symlink = agent_config.primary_symlink
    if symlink.is_symlink() and symlink.resolve().name == incarnation_name:
        symlink.unlink()

    # 8. Clean incarnation folder
    shutil.rmtree(incarnation_dir)

    return {
        "status": "complete",
        "incarnation": incarnation_name,
        "cycles": cycle_count,
        "memory_flags_processed": len(memory_flags),
        "episodic_path": str(episodic_path),
        "akasha_path": str(akasha_dir),
    }


def _ensure_memory_core(config: AgentConfig, entry: dict[str, Any]) -> None:
    """Ensure a core entry exists; avoids duplicating what the live cycle already wrote."""
    from .memory import read_jsonl, write_memory_core

    existing = read_jsonl(config.memory_core_path)
    content = entry.get("content", "")

    for e in existing:
        if e.get("content", "") == content:
            return  # Already present

    write_memory_core(config, entry)


def check_bardo_timeouts(registry: Any) -> list[str]:
    """
    Check all agents for bardo timeout. Run by scheduler bardo_check task.
    Returns list of agent names that had bardo triggered.
    """
    from ..agent.incarnation import get_primary_incarnation

    triggered = []
    now = datetime.now(timezone.utc)

    for agent_name in registry.all_agents():
        config = registry.get(agent_name)
        if not config:
            continue

        active_name = get_primary_incarnation(config)
        if not active_name:
            continue

        # Find incarnation start time from transcript
        incarnation_dir = config.memory_dir / active_name
        transcript_path = incarnation_dir / "transcript.jsonl"

        if not transcript_path.exists():
            continue

        entries = read_entries(transcript_path)
        start_entry = next(
            (e for e in entries if e.get("type") == "incarnation_start"),
            None,
        )
        if not start_entry:
            continue

        ts_str = start_entry.get("ts", "")
        if not ts_str:
            continue

        try:
            start_time = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except ValueError:
            continue

        age_hours = (now - start_time).total_seconds() / 3600
        timeout_hours = config.bardo.timeout_hours

        if age_hours >= timeout_hours:
            print(
                f"[bardo] Timeout for {agent_name}/{active_name}: "
                f"{age_hours:.1f}h >= {timeout_hours}h",
                file=sys.stderr,
            )
            try:
                run_bardo(config, active_name)
                triggered.append(agent_name)
            except Exception as e:
                print(f"[bardo] Timeout bardo failed for {agent_name}: {e}", file=sys.stderr)

    return triggered
