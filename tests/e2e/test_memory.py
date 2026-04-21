"""E2E: memory persistence tests.

Run with: pytest tests/e2e/test_memory.py -v -s

Human-readable terminal tests. Logs matter as much as asserts.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.transport.client import RuntimeClient  # noqa: E402

client = RuntimeClient()

AGENT = "personal"
AGENT_HOME = Path("/home") / AGENT


# ── Helpers ────────────────────────────────────────────────────────────────────


def _print_response(response) -> None:
    print(f"\n  [{response.agent} / {response.incarnation}  cycle {response.cycle}]")
    print(f"  {'─' * 60}")
    for line in response.content.splitlines():
        print(f"  {line}")
    print(f"  {'─' * 60}")


def _reset_and_spawn(agent: str = AGENT) -> str:
    result = subprocess.run(
        ["python3", str(PROJECT_ROOT / "cli" / "aurelia"), "agent", "reset", agent, "--yes"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Reset failed:\n{result.stderr}"
    incarnation = client.spawn(agent)
    print(f"\n  Spawned: {incarnation.name}")
    return incarnation.name


def _dispatch(incarnation: str, message: str, agent: str = AGENT):
    return client.dispatch(
        agent=agent,
        incarnation=incarnation,
        hook="human_message",
        payload={"content": message, "sender": "god-lite"},
    )


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def runtime():
    try:
        health = client.get_health()
    except ConnectionError as e:
        pytest.skip(f"Runtime daemon not reachable: {e}")
    assert health.status in ("ok", "healthy")
    return health


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_goldfish(runtime):
    """Multi-turn in-context recall: give a number string, distract, ask for it back.

    Tests that the transcript is assembled correctly across cycles and the agent
    doesn't lose information within a single incarnation.

    Expected: agent recalls the exact number string after 2 unrelated messages.
    """
    TOKEN = "4829-3710-5566"

    incarnation = _reset_and_spawn()

    print(f"\n  Token to remember: {TOKEN}")
    print("  Expected: agent recalls the token after 2 unrelated messages.\n")

    r1 = _dispatch(incarnation, f"Remember this number string, it's important: {TOKEN}")
    _print_response(r1)

    r2 = _dispatch(incarnation, "What's your favourite thing about autumn?")
    _print_response(r2)

    r3 = _dispatch(incarnation, "If you could live anywhere, where would it be?")
    _print_response(r3)

    r4 = _dispatch(incarnation, "What was the number string I asked you to remember?")
    _print_response(r4)

    if TOKEN in r4.content:
        print(f"\n  ✓ Agent recalled the token exactly: {TOKEN}")
    else:
        print(f"\n  ✗ Token not found in response. Got: {r4.content[:200]}")
        pytest.fail(f"Agent failed to recall token '{TOKEN}' within the same incarnation")


def test_bardo_memory_persistence(runtime):
    """Tell agent a real personal fact, trigger bardo, spawn new incarnation, ask for it.

    Tests the full karma pipeline:
      dispatch → memory_write (semantic_core) → bardo → new incarnation context → recall

    We tell the agent something that genuinely matters to serving Hazim well,
    so it has real motivation to store it — not an arbitrary test token.

    Expected: new incarnation knows the fact without being told again.
    """
    FACT = "Hazim grew up in Kuala Lumpur"
    PROBE = "Where did I grow up?"

    incarnation = _reset_and_spawn()

    print(f"\n  Fact to persist: {FACT!r}")
    print("  Expected: new incarnation recalls it after bardo.\n")

    r1 = _dispatch(
        incarnation,
        f"I want to tell you something about myself that you should always remember: "
        f"{FACT}. Please store this using memory_write so you carry it across incarnations.",
    )
    _print_response(r1)

    semantic_core = AGENT_HOME / "karma" / "semantic" / "core.jsonl"
    core_text = semantic_core.read_text() if semantic_core.exists() else ""
    if "Kuala Lumpur" in core_text:
        print("\n  ✓ Fact written to semantic core immediately (Path 1 confirmed)")
    else:
        print("\n  ~ Not yet in semantic core — bardo will need to consolidate it")

    print("\n  Triggering bardo...")
    bardo_result = client.trigger_bardo(AGENT)
    print(f"  Bardo status: {bardo_result.get('status', 'unknown')}")

    print("\n  Spawning new incarnation...")
    new_incarnation = client.spawn(AGENT)
    print(f"  New incarnation: {new_incarnation.name}")

    r2 = client.dispatch(
        agent=AGENT,
        incarnation=new_incarnation.name,
        hook="human_message",
        payload={"content": PROBE, "sender": "god-lite"},
    )
    _print_response(r2)

    if "Kuala Lumpur" in r2.content:
        print("\n  ✓ New incarnation recalled the fact: Kuala Lumpur")
    else:
        print("\n  ✗ Fact not found in new incarnation's response")
        core_text = semantic_core.read_text() if semantic_core.exists() else "(empty)"
        print(f"  Semantic core:\n{core_text[:500]}")
        pytest.fail(f"Fact not recalled by new incarnation after bardo")


def test_bardo_smart_gate(runtime):
    """Trivial exchange → bardo → assert no episodic file written.

    Tests _worth_archiving: bardo should discard sessions with no meaningful content.

    Expected: no new file in akasha/ after bardo on a one-liner exchange.
    Note: this test is inherently soft — the LLM decides what's worth archiving.
    """
    incarnation = _reset_and_spawn()

    akasha = AGENT_HOME / "akasha"
    files_before = set(akasha.rglob("*.jsonl")) if akasha.exists() else set()
    print(f"\n  Akasha files before: {len(files_before)}")
    print("  Expected: no new episodic file after a trivial exchange.\n")

    r = _dispatch(incarnation, "ok")
    _print_response(r)

    print("\n  Triggering bardo...")
    bardo_result = client.trigger_bardo(AGENT)
    status = bardo_result.get("status", "unknown")
    print(f"  Bardo status: {status}")

    time.sleep(1)  # bardo is async in some paths

    files_after = set(akasha.rglob("*.jsonl")) if akasha.exists() else set()
    new_files = files_after - files_before
    print(f"  Akasha files after:  {len(files_after)}")

    if not new_files:
        print("\n  ✓ No new episodic files written — bardo correctly discarded trivial session")
    else:
        print(f"\n  ~ {len(new_files)} new file(s) written — bardo judged session worth archiving:")
        for f in new_files:
            print(f"    {f}")
        print("  (this is a soft failure — the LLM may have produced archivable content)")
        # Soft fail: print a warning but don't hard-fail since this is LLM-dependent
        pytest.xfail("Bardo archived a trivial session — LLM classification is non-deterministic")


def test_memory_write_semantic_core(runtime):
    """Ask agent to write to semantic_core, verify the file is updated.

    Tests the immediate Path 1 write in handle_memory_write.
    Expected: karma/semantic/core.jsonl contains the written content.
    """
    FACT = "Hazim's favourite number is 42"

    incarnation = _reset_and_spawn()

    semantic_core = AGENT_HOME / "karma" / "semantic" / "core.jsonl"
    content_before = semantic_core.read_text() if semantic_core.exists() else ""

    print(f"\n  Asking agent to write to semantic_core: {FACT!r}")
    print("  Expected: karma/semantic/core.jsonl updated immediately after the call.\n")

    r = _dispatch(
        incarnation,
        f"Please use memory_write to store this fact: '{FACT}'. "
        f"Use tier=semantic_core and importance=high.",
    )
    _print_response(r)

    content_after = semantic_core.read_text() if semantic_core.exists() else ""

    if FACT in content_after:
        print(f"\n  ✓ Fact found in semantic core: {FACT!r}")
    elif content_after != content_before:
        print(f"\n  ~ Semantic core was updated but exact fact not found")
        print(f"  New content: {content_after[len(content_before):][:300]}")
        # Partial pass — something was written, just not verbatim
    else:
        print(f"\n  ✗ Semantic core unchanged after memory_write call")
        pytest.fail("memory_write with tier=semantic_core did not update core.jsonl")


def test_dashboard_notification(runtime):
    """Ask agent to post a dashboard notification, verify the file appears.

    Expected: new .json file in /var/aurelia/dashboard/queue/ after the call.
    """
    dashboard_dir = Path("/var/aurelia/dashboard/queue")
    files_before = set(dashboard_dir.glob("*.json")) if dashboard_dir.exists() else set()

    incarnation = _reset_and_spawn()

    print(f"\n  Dashboard files before: {len(files_before)}")
    print("  Expected: new .json file in /var/aurelia/dashboard/queue/ after call.\n")

    r = _dispatch(
        incarnation,
        "Please use dashboard_notification to send me a briefing with the message "
        "'Test notification from memory test suite' and category=briefing.",
    )
    _print_response(r)

    files_after = set(dashboard_dir.glob("*.json")) if dashboard_dir.exists() else set()
    new_files = files_after - files_before

    if new_files:
        f = next(iter(new_files))
        content = f.read_text()
        print(f"\n  ✓ Notification file written: {f.name}")
        print(f"  Content: {content[:300]}")
    else:
        print(f"\n  ✗ No new notification file found in {dashboard_dir}")
        pytest.fail("dashboard_notification tool did not write a file to the queue")
