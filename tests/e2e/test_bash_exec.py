"""E2E: bash_exec capability tests.

Run with: pytest tests/e2e/test_bash_exec.py -v -s

These tests are meant to be watched by a human at a terminal.
Logs matter as much as asserts — you're looking at what the agent
actually did, not just whether it passed.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.transport.client import RuntimeClient  # noqa: E402

client = RuntimeClient()

AGENT = "janitor"  # Most natural fit for environment interaction
AGENT_HOME = Path("/home") / AGENT


# ── Helpers ────────────────────────────────────────────────────────────────────


def _print_response(response) -> None:
    print(f"\n  [{response.agent} / {response.incarnation}  cycle {response.cycle}]")
    print(f"  {'─' * 60}")
    for line in response.content.splitlines():
        print(f"  {line}")
    print(f"  {'─' * 60}")


def _print_tool_calls(response) -> None:
    """Fetch and print tool calls from the transcript for the last cycle."""
    try:
        history = client.get_history(response.agent, response.incarnation)
        tool_calls = [e for e in history if e.type == "tool_call"]
        if tool_calls:
            print(f"\n  Tool calls made ({len(tool_calls)}):")
            for tc in tool_calls:
                name = tc.extra.get("tool_name", "?")
                inp = tc.extra.get("tool_input", {}) or {}
                cmd = inp.get("command", "") or str(inp)[:120]
                preview = cmd[:120] + ("..." if len(cmd) > 120 else "")
                print(f"    • {name}  {preview!r}")
        else:
            print("\n  (no tool calls in transcript)")
    except Exception as e:
        print(f"\n  (could not fetch transcript: {e})")


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def runtime():
    try:
        health = client.get_health()
    except ConnectionError as e:
        pytest.skip(f"Runtime daemon not reachable: {e}")
    assert health.status in ("ok", "healthy")
    return health


@pytest.fixture
def live_janitor(runtime):
    """Reset janitor and return a fresh incarnation name."""
    result = subprocess.run(
        ["python3", str(PROJECT_ROOT / "cli" / "aurelia"), "agent", "reset", AGENT, "--yes"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Reset failed:\n{result.stderr}"
    incarnation = client.spawn(AGENT)
    print(f"\n  Spawned: {incarnation.name}")
    return incarnation.name


def _dispatch(incarnation: str, message: str):
    return client.dispatch(
        agent=AGENT,
        incarnation=incarnation,
        hook="human_message",
        payload={"content": message, "sender": "god-lite"},
    )


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_python_computation(live_janitor):
    """Agent uses bash_exec to compute something in python3 and report back.

    Expected: agent runs python3, gets a result, includes it in its response.
    """
    print("\n  Asking janitor to compute primes via python3...")
    print("  Expected: agent calls bash_exec with python3, reports the primes back.\n")

    response = _dispatch(
        live_janitor,
        "Use bash_exec to run a python3 one-liner that computes the first 10 prime numbers "
        "and prints them. Then tell me what you got.",
    )

    _print_response(response)
    _print_tool_calls(response)

    assert response.content, "Agent returned empty response"
    # Primes start with 2, 3, 5 — if any appear the agent ran real code
    found_primes = any(str(n) in response.content for n in [2, 3, 5, 7, 11])
    if found_primes:
        print("\n  ✓ Response contains prime numbers — bash_exec ran real python3")
    else:
        print("\n  ~ Response doesn't mention primes — agent may have reasoned instead of running code")


def test_write_and_read_file(live_janitor):
    """Agent writes a file to its home dir via bash_exec, we verify it exists.

    Expected: file appears at /home/janitor/test_artifact.txt with expected content.
    """
    artifact = AGENT_HOME / "test_artifact.txt"
    artifact.unlink(missing_ok=True)  # clean slate

    print(f"\n  Asking janitor to write a file to {artifact}...")
    print("  Expected: file exists after the response, content matches what agent wrote.\n")

    response = _dispatch(
        live_janitor,
        f"Use bash_exec to write a file at {artifact} containing exactly the text "
        f"'AURELIA_TEST_ARTIFACT' on the first line and today's date on the second line. "
        f"Use a python3 one-liner to do it. Then confirm the file exists by reading it back.",
    )

    _print_response(response)
    _print_tool_calls(response)

    if artifact.exists():
        content = artifact.read_text()
        print(f"\n  ✓ File exists at {artifact}")
        print(f"  Content: {content.strip()!r}")
        assert "AURELIA_TEST_ARTIFACT" in content, \
            f"Expected marker in file, got: {content!r}"
    else:
        print(f"\n  ✗ File not found at {artifact}")
        pytest.fail(f"Agent claimed to write file but {artifact} does not exist")


def test_web_search(live_janitor):
    """Agent searches the web via bash_exec and reports a real result.

    Expected: agent uses ddgs in a python3 one-liner, response includes something
    from the real web (a URL or a snippet mentioning Python version).
    """
    print("\n  Asking janitor to search the web for current Python version...")
    print("  Expected: agent runs ddgs via bash_exec, response contains real search results.\n")

    response = _dispatch(
        live_janitor,
        "Use bash_exec to search the web for 'latest Python 3 stable release' using: "
        "python3 -c \"from ddgs import DDGS; "
        "[print(r['title'], r['href']) for r in DDGS().text('latest Python 3 stable release', max_results=3)]\". "
        "Tell me what you found.",
    )

    _print_response(response)
    _print_tool_calls(response)

    assert response.content, "Agent returned empty response"
    has_python_ref = "python" in response.content.lower() or "3." in response.content
    if has_python_ref:
        print("\n  ✓ Response references Python — web search returned real results")
    else:
        print("\n  ~ Response doesn't clearly reference Python version (check tool calls above)")
