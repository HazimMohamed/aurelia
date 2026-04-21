"""Bardo process: summarize transcript, archive to Akasha, clean karma."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import anthropic

from .config import AgentConfig
from .transcript import (
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
    # Build a readable version of the transcript for summarization
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

    # Try to extract JSON from the response
    try:
        # Handle markdown code blocks
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        parsed = json.loads(raw)
        return json.dumps(parsed)
    except (json.JSONDecodeError, IndexError):
        # Return as plain text wrapped in JSON
        return json.dumps({"summary": raw, "topics": [], "insights": [], "tone": "unknown"})


def run_bardo(agent_config: AgentConfig, incarnation_name: str) -> dict[str, Any]:
    """
    Execute bardo for a completed incarnation:
    1. Read transcript
    2. Summarize with Sonnet
    3. Write episodic record to ~/karma/episodic/extended/{incarnation_name}.jsonl
    4. Copy transcript to ~/akasha/{incarnation_name}/{incarnation_name}-transcript.jsonl
    5. Copy scratch to ~/akasha/{incarnation_name}/scratch/ if non-empty
    6. Write bardo_complete to transcript
    7. Clean karma incarnation folder
    8. Remove current symlink
    """
    incarnation_dir = agent_config.karma_dir / incarnation_name
    transcript_path = incarnation_dir / "transcript.jsonl"
    scratch_dir = incarnation_dir / "scratch"

    if not incarnation_dir.exists():
        return {"status": "error", "message": f"Incarnation dir not found: {incarnation_dir}"}

    entries = read_entries(transcript_path)
    cycle_count = sum(1 for e in entries if e.get("type") == "human_message")

    # Write bardo_complete to transcript before archiving
    write_bardo_complete(transcript_path, incarnation_name, cycle_count)
    # Re-read with the bardo_complete entry
    entries = read_entries(transcript_path)

    # 1. Summarize
    summary_json = _summarize_transcript(
        agent_config.name,
        incarnation_name,
        entries,
        agent_config.bardo.model,
    )

    # 2. Write episodic record
    episodic_dir = agent_config.episodic_extended_dir
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

    # 3. Archive to Akasha
    akasha_dir = agent_config.akasha_dir / incarnation_name
    akasha_dir.mkdir(parents=True, exist_ok=True)

    akasha_transcript = akasha_dir / f"{incarnation_name}-transcript.jsonl"
    shutil.copy2(transcript_path, akasha_transcript)

    # 4. Copy scratch if non-empty
    if scratch_dir.exists() and any(scratch_dir.iterdir()):
        akasha_scratch = akasha_dir / "scratch"
        if akasha_scratch.exists():
            shutil.rmtree(akasha_scratch)
        shutil.copytree(scratch_dir, akasha_scratch)

    # 5. Remove current symlink
    symlink = agent_config.current_symlink
    if symlink.is_symlink():
        symlink.unlink()

    # 6. Clean karma incarnation folder
    shutil.rmtree(incarnation_dir)

    return {
        "status": "complete",
        "incarnation": incarnation_name,
        "cycles": cycle_count,
        "episodic_path": str(episodic_path),
        "akasha_path": str(akasha_dir),
    }
