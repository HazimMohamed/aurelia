"""
generate_report — Sonnet-powered lab notebook entry for Aurelia experiments.

Accepts one or more cold storage run directories and produces a single
markdown report interpreting what happened across all incarnations.

Usage:
    from alembic.report import generate_report
    report = generate_report([run_dir1, run_dir2, ...], experiment_id="EX-01.1")
    (output_dir / "report.md").write_text(report)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_AURELIA_ROOT = Path(__file__).parent.parent.parent / "aurelia"
if str(_AURELIA_ROOT) not in sys.path:
    sys.path.insert(0, str(_AURELIA_ROOT))

from src.agent.transcript import read_entries


def _collect_artifacts(snapshot_dir: Path) -> dict[str, str]:
    artifacts = {}
    for base in ["karma", "akasha"]:
        base_dir = snapshot_dir / base
        if not base_dir.exists():
            continue
        for scratch_dir in base_dir.rglob("scratch"):
            if not scratch_dir.is_dir():
                continue
            for f in sorted(scratch_dir.rglob("*")):
                if f.is_file():
                    rel = f.relative_to(snapshot_dir)
                    try:
                        artifacts[str(rel)] = f.read_text(encoding="utf-8")
                    except OSError:
                        pass
    room_dir = snapshot_dir / "room"
    if room_dir.exists():
        for f in sorted(room_dir.rglob("*")):
            if f.is_file():
                rel = f.relative_to(snapshot_dir)
                try:
                    artifacts[str(rel)] = f.read_text(encoding="utf-8")
                except OSError:
                    pass
    return artifacts


def _collect_jsonl_dir(directory: Path) -> list[dict]:
    entries = []
    if not directory.exists():
        return entries
    for f in sorted(directory.iterdir()):
        if f.suffix != ".jsonl":
            continue
        try:
            entries.extend(read_entries(f))
        except OSError:
            pass
    return entries


def _build_raw_data(run_dirs: list[Path]) -> str:
    sections: list[str] = []

    for i, run_dir in enumerate(run_dirs):
        meta_path = run_dir / "experiment.json"
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}

        sections.append(f"\n# Incarnation {i + 1}: {meta.get('experiment_id', run_dir.name)}")
        sections.append(
            f"Agent: {meta.get('agent')} | Duration: {meta.get('wall_time_seconds')}s | "
            f"Chained from: {meta.get('chained_from') or 'none'}"
        )

        snapshot_dir = run_dir / "snapshot"

        # Transcript cycles
        transcript_files = list(snapshot_dir.rglob("transcript.jsonl")) if snapshot_dir.exists() else []
        for tf in sorted(transcript_files):
            entries = read_entries(tf)
            cycle = 0
            for entry in entries:
                t = entry.get("type")
                if t == "human_message":
                    cycle += 1
                    sections.append(f"\n## Cycle {cycle} — Prompt")
                    content = entry.get("content", "")
                    if isinstance(content, list):
                        content = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
                    sections.append(content)
                elif t == "tool_call":
                    sections.append(f"### Tool: {entry.get('tool_name')}")
                    sections.append(json.dumps(entry.get("tool_input", {}), ensure_ascii=False))
                elif t == "tool_result":
                    result = entry.get("result", "")
                    sections.append(f"### Tool result: {json.dumps(result, ensure_ascii=False)[:500]}")
                elif t == "assistant_message":
                    sections.append(f"### Response")
                    sections.append(entry.get("content", ""))

        # Artifacts
        artifacts = _collect_artifacts(snapshot_dir)
        if artifacts:
            sections.append("\n## Artifacts Written")
            for path, content in artifacts.items():
                sections.append(f"### {path}\n{content}")

        # Retained memories
        semantic = _collect_jsonl_dir(snapshot_dir / "karma" / "semantic" / "extended")
        episodic = _collect_jsonl_dir(snapshot_dir / "karma" / "episodic" / "extended")
        if semantic:
            sections.append("\n## Semantic Memories Retained")
            for e in semantic:
                sections.append(json.dumps(e, ensure_ascii=False))
        if episodic:
            sections.append("\n## Episodic Memories Retained")
            for e in episodic:
                sections.append(json.dumps(e, ensure_ascii=False))

    return "\n".join(sections)


def generate_report(run_dirs: list[Path], experiment_id: str = "") -> str:
    import anthropic

    raw = _build_raw_data(run_dirs)

    multi = len(run_dirs) > 1
    if multi:
        focus = (
            "This is a chained multi-incarnation experiment. "
            "Pay special attention to how the agent changes (or doesn't) across incarnations — "
            "does accumulated karma deepen the behavior, flatten it, or make it recursive? "
            "Compare tone, specificity, and the questions the agent holds across runs."
        )
    else:
        focus = "This is a single-incarnation experiment."

    system = (
        "You are writing a lab notebook entry for an AI behavior experiment. "
        "You will be given raw experiment data — prompts, tool calls, responses, artifacts, "
        "and retained memories — from one or more incarnations of an ephemeral Aurelia agent. "
        f"{focus} "
        "Write a concise, insightful report in markdown. "
        "Focus on: what the agent actually did, what was interesting or surprising, "
        "what questions this raises for future experiments. "
        "Do not just restate the raw data — interpret it. "
        "Use headers: ## Summary, ## What Happened, ## What Was Interesting, ## Open Questions. "
        "Keep it tight. A good lab notebook entry is specific, not exhaustive."
    )

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": f"Experiment: {experiment_id}\n\n{raw}"}],
    )
    return response.content[0].text
