#!/usr/bin/env python3
"""
aurelia-admin.py — Administrative CLI for the Aurelia system.

Usage:
    python3 scripts/aurelia-admin.py promote-episodic --agent AGENT --incarnation INCARNATION --subtype SUBTYPE --note NOTE
    python3 scripts/aurelia-admin.py undissolve --agent AGENT --incarnation INCARNATION
    python3 scripts/aurelia-admin.py bardo --agent AGENT
    python3 scripts/aurelia-admin.py budget-override --agent AGENT --tokens N
    python3 scripts/aurelia-admin.py budget-status [--agent AGENT]
    python3 scripts/aurelia-admin.py bardo-check
    python3 scripts/aurelia-admin.py write-memory --agent AGENT --tier TIER --content CONTENT [--category CAT]
    python3 scripts/aurelia-admin.py mayor-queue
    python3 scripts/aurelia-admin.py list-incarnations --agent AGENT
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

AGENT_HOME = Path("/home")
VAR_AURELIA = Path("/var/aurelia")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _get_agent_config(agent_name: str):
    """Load agent config."""
    from src.config import load_agent_config
    return load_agent_config(agent_name)


def cmd_promote_episodic(args) -> None:
    """Promote an episodic entry to core (Traumatize/Enshrine)."""
    agent = args.agent
    incarnation = args.incarnation
    subtype = args.subtype
    note = args.note

    valid_subtypes = {"formative_success", "formative_error", "formative_moment"}
    if subtype not in valid_subtypes:
        print(f"ERROR: subtype must be one of: {', '.join(sorted(valid_subtypes))}")
        sys.exit(1)

    config = _get_agent_config(agent)
    core_dir = config.episodic_core_dir
    core_dir.mkdir(parents=True, exist_ok=True)

    ts = _now_iso()
    ts_safe = ts.replace(":", "-").replace("+", "")
    filename = f"formative-{subtype}-{ts_safe}.jsonl"
    path = core_dir / filename

    entry = {
        "ts": ts,
        "type": "episodic_core",
        "subtype": subtype,
        "agent": agent,
        "incarnation": incarnation,
        "note": note,
        "promoted_by": "god-lite",
    }

    with path.open("w", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    print(f"Promoted to episodic core:")
    print(f"  Agent:       {agent}")
    print(f"  Incarnation: {incarnation}")
    print(f"  Subtype:     {subtype}")
    print(f"  Note:        {note}")
    print(f"  File:        {path}")

    action = "Enshrined" if subtype == "formative_success" else "Traumatized"
    print(f"\n[{action}] All future {agent} incarnations will carry this memory.")


def cmd_undissolve(args) -> None:
    """Restore a dissolved incarnation via the API."""
    import urllib.request

    url = f"http://localhost:8000/admin/undissolve"
    data = json.dumps({"agent": args.agent, "incarnation": args.incarnation}).encode()

    try:
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
        print(f"Undissolve result: {json.dumps(result, indent=2)}")
    except Exception as e:
        # Try direct operation if API not available
        print(f"API unavailable ({e}), trying direct operation...")
        _undissolve_direct(args.agent, args.incarnation)


def _undissolve_direct(agent_name: str, incarnation_name: str) -> None:
    """Directly restore incarnation without API."""
    import shutil
    from src.config import load_agent_config
    from src.transcript import append_entry

    config = load_agent_config(agent_name)
    akasha_path = config.akasha_dir / incarnation_name
    karma_path = config.karma_dir / incarnation_name

    if not akasha_path.exists():
        print(f"ERROR: {akasha_path} not found in akasha")
        sys.exit(1)

    akasha_transcript = akasha_path / f"{incarnation_name}-transcript.jsonl"
    if not akasha_transcript.exists():
        print(f"ERROR: transcript not found at {akasha_transcript}")
        sys.exit(1)

    # Check active
    symlink = config.current_symlink
    if symlink.is_symlink() and symlink.resolve().exists():
        print(f"ERROR: Agent '{agent_name}' has an active incarnation. Bardo it first.")
        sys.exit(1)

    karma_path.mkdir(parents=True, exist_ok=True)
    transcript_path = karma_path / "transcript.jsonl"
    shutil.copy2(akasha_transcript, transcript_path)
    (karma_path / "scratch").mkdir(exist_ok=True)

    append_entry(transcript_path, {
        "ts": _now_iso(),
        "type": "undissolved",
        "incarnation": incarnation_name,
        "note": "Incarnation restored by God-lite",
    })

    if symlink.is_symlink():
        symlink.unlink()
    symlink.symlink_to(karma_path)

    print(f"Undissolved: {agent_name}/{incarnation_name}")
    print(f"  Karma path: {karma_path}")
    print(f"  Symlink: {symlink} -> {karma_path}")


def cmd_bardo(args) -> None:
    """Trigger bardo for an agent's active incarnation."""
    import urllib.request

    agent = args.agent
    url = f"http://localhost:8000/bardo/{agent}"
    data = b"{}"

    try:
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
        print(f"Bardo result: {json.dumps(result, indent=2)}")
    except Exception as e:
        print(f"API call failed: {e}")
        print("Try: curl -X POST http://localhost:8000/bardo/{agent}")
        sys.exit(1)


def cmd_budget_override(args) -> None:
    """Grant additional tokens to an agent."""
    import urllib.request

    url = "http://localhost:8000/admin/budget-override"
    data = json.dumps({
        "agent": args.agent,
        "additional_tokens": args.tokens,
    }).encode()

    try:
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
        print(f"Budget override result: {json.dumps(result, indent=2)}")
    except Exception as e:
        print(f"API unavailable ({e}), trying direct...")
        from src.budget import resume_budget
        budget = resume_budget(args.agent, additional_tokens=args.tokens)
        print(f"Budget updated: {json.dumps(budget, indent=2)}")


def cmd_budget_status(args) -> None:
    """Show budget status for all or specific agents."""
    from src.budget import load_budget
    from src.config import load_agent_config, list_known_agents

    agents = [args.agent] if args.agent else list_known_agents()

    for agent_name in agents:
        try:
            config = load_agent_config(agent_name)
            budget = load_budget(agent_name)
            used = budget.get("tokens_used", 0)
            remaining = max(0, config.weekly_budget_tokens - used)
            status = budget.get("status", "active")
            week_start = budget.get("week_start", "unknown")

            print(f"\n{agent_name}:")
            print(f"  Status:         {status}")
            print(f"  Week start:     {week_start}")
            print(f"  Used:           {used:,} / {config.weekly_budget_tokens:,}")
            print(f"  Remaining:      {remaining:,}")
            print(f"  Used pct:       {100 * used / config.weekly_budget_tokens:.1f}%")
        except Exception as e:
            print(f"\n{agent_name}: ERROR - {e}")


def cmd_bardo_check(args) -> None:
    """Check for bardo timeouts across all agents."""
    import urllib.request

    url = "http://localhost:8000/admin/bardo-check"
    data = b"{}"

    try:
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
        print(f"Bardo check: {json.dumps(result, indent=2)}")
    except Exception as e:
        print(f"API unavailable ({e}), trying direct...")
        from src.config import list_known_agents, load_agent_config
        from src.registry import AgentRegistry
        registry = AgentRegistry()
        from src.bardo import check_bardo_timeouts
        triggered = check_bardo_timeouts(registry)
        print(f"Triggered bardo for: {triggered}")


def cmd_write_memory(args) -> None:
    """Write directly to an agent's memory (admin path)."""
    from src.config import load_agent_config
    from src.memory import write_semantic_core, write_semantic_extended

    config = load_agent_config(args.agent)
    tier = args.tier
    content = args.content
    category = getattr(args, "category", "general") or "general"

    entry = {
        "ts": _now_iso(),
        "type": "admin_memory",
        "content": content,
        "importance": getattr(args, "importance", "medium") or "medium",
        "tier": tier,
        "category": category,
        "source": "admin",
    }

    if tier == "semantic_core":
        write_semantic_core(config, entry)
        print(f"Written to semantic core: {config.semantic_core_path}")
    elif tier == "semantic":
        write_semantic_extended(config, category, entry)
        print(f"Written to semantic extended: {config.semantic_extended_dir}/{category}.jsonl")
    else:
        print(f"ERROR: use --tier semantic_core or semantic")
        sys.exit(1)

    print(f"Content: {content}")


def cmd_mayor_queue(args) -> None:
    """Show the dashboard queue for mayor write-ups and alerts."""
    queue_dir = VAR_AURELIA / "dashboard" / "queue"
    if not queue_dir.exists():
        print("Dashboard queue is empty (directory not found)")
        return

    files = sorted(queue_dir.glob("*.json"))
    if not files:
        print("Dashboard queue is empty")
        return

    print(f"\nDashboard queue ({len(files)} items):\n")
    for f in files:
        try:
            entry = json.loads(f.read_text())
            category = entry.get("category", "unknown")
            agent = entry.get("agent", "unknown")
            ts = entry.get("ts", "")
            print(f"  [{category}] {agent} @ {ts}")

            if category == "sos":
                print(f"    SOS: {entry.get('message', '')}")
            elif category == "mayor_summary":
                print(f"    Subject: {entry.get('subject', '')}")
                print(f"    Observation: {entry.get('observation', '')[:100]}")
            elif category == "constitution_flag":
                print(f"    Agent: {entry.get('flagged_agent', '')}")
                print(f"    Observation: {entry.get('observation', '')[:100]}")
            else:
                content = entry.get("content", "")
                if content:
                    print(f"    {content[:100]}")
            print()
        except Exception as e:
            print(f"  {f.name}: ERROR - {e}")


def cmd_list_incarnations(args) -> None:
    """List all incarnations for an agent (active + akasha)."""
    from src.config import load_agent_config

    config = load_agent_config(args.agent)

    # Active
    symlink = config.current_symlink
    active_name = None
    if symlink.is_symlink():
        target = symlink.resolve()
        if target.exists():
            active_name = target.name
            print(f"ACTIVE: {active_name}")

    # Karma (non-bardo'd)
    print("\nIn karma (not yet bardo'd):")
    if config.karma_dir.exists():
        for d in sorted(config.karma_dir.iterdir()):
            if d.is_dir() and d.name not in ("current", "episodic", "semantic"):
                marker = " [ACTIVE]" if d.name == active_name else ""
                print(f"  {d.name}{marker}")

    # Akasha
    print("\nIn akasha (dissolved):")
    if config.akasha_dir.exists():
        for d in sorted(config.akasha_dir.iterdir(), reverse=True):
            if d.is_dir():
                transcript = d / f"{d.name}-transcript.jsonl"
                has_transcript = " (has transcript)" if transcript.exists() else " (no transcript)"
                print(f"  {d.name}{has_transcript}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Aurelia administrative CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # promote-episodic
    p = subparsers.add_parser("promote-episodic", help="Traumatize or Enshrine an episodic entry")
    p.add_argument("--agent", required=True, help="Agent name")
    p.add_argument("--incarnation", required=True, help="Source incarnation name")
    p.add_argument("--subtype", required=True,
                   choices=["formative_success", "formative_error", "formative_moment"],
                   help="Subtype of the promotion")
    p.add_argument("--note", required=True, help="The note/lesson to record")

    # undissolve
    p = subparsers.add_parser("undissolve", help="Restore a dissolved incarnation")
    p.add_argument("--agent", required=True)
    p.add_argument("--incarnation", required=True)

    # bardo
    p = subparsers.add_parser("bardo", help="Trigger bardo for an agent")
    p.add_argument("--agent", required=True)

    # budget-override
    p = subparsers.add_parser("budget-override", help="Grant additional tokens to an agent")
    p.add_argument("--agent", required=True)
    p.add_argument("--tokens", type=int, default=100_000, help="Additional tokens to grant")

    # budget-status
    p = subparsers.add_parser("budget-status", help="Show budget status")
    p.add_argument("--agent", default=None, help="Specific agent (default: all)")

    # bardo-check
    p = subparsers.add_parser("bardo-check", help="Check bardo timeouts across all agents")

    # write-memory
    p = subparsers.add_parser("write-memory", help="Write directly to agent memory")
    p.add_argument("--agent", required=True)
    p.add_argument("--tier", required=True, choices=["semantic_core", "semantic"])
    p.add_argument("--content", required=True)
    p.add_argument("--category", default="general")
    p.add_argument("--importance", default="medium", choices=["low", "medium", "high"])

    # mayor-queue
    p = subparsers.add_parser("mayor-queue", help="Show dashboard queue")

    # list-incarnations
    p = subparsers.add_parser("list-incarnations", help="List incarnations for an agent")
    p.add_argument("--agent", required=True)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "promote-episodic": cmd_promote_episodic,
        "undissolve": cmd_undissolve,
        "bardo": cmd_bardo,
        "budget-override": cmd_budget_override,
        "budget-status": cmd_budget_status,
        "bardo-check": cmd_bardo_check,
        "write-memory": cmd_write_memory,
        "mayor-queue": cmd_mayor_queue,
        "list-incarnations": cmd_list_incarnations,
    }

    handler = commands.get(args.command)
    if handler:
        handler(args)
    else:
        print(f"Unknown command: {args.command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
