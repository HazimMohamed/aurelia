"""E2E: heartbeat test — pick a live agent, say hi, expect a coherent response."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.transport.client import RuntimeClient  # noqa: E402

client = RuntimeClient()


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def runtime():
    """Assert the runtime daemon is reachable before running any test."""
    try:
        health = client.get_health()
    except ConnectionError as e:
        pytest.skip(f"Runtime daemon not reachable: {e}")
    assert health.status in ("ok", "healthy"), f"Runtime unhealthy: {health.status}"
    return health


@pytest.fixture
def live_agent(runtime):
    """Return the name and active incarnation of any agent, resetting it first."""
    agents = client.list_agents()
    if not agents:
        pytest.skip("No agents registered")

    agent = agents[0]
    name = agent.name

    # Reset to clean state — mirrors what integration tests should always do
    result = subprocess.run(
        ["python3", str(PROJECT_ROOT / "cli" / "aurelia"), "agent", "reset", name, "--yes"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Reset failed:\n{result.stderr}"

    # Spawn a fresh incarnation
    incarnation = client.spawn(name)
    return name, incarnation.name


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_list_agents(runtime):
    """Runtime returns at least one agent."""
    agents = client.list_agents()
    assert len(agents) > 0, "Expected at least one registered agent"
    names = [a.name for a in agents]
    print(f"\n  Registered agents: {names}")


def test_heartbeat_response(live_agent):
    """Agent responds coherently to a simple 'are you doing okay?' message."""
    name, incarnation = live_agent

    response = client.dispatch(
        agent=name,
        incarnation=incarnation,
        hook="human_message",
        payload={"content": "Hey, are you doing okay?", "sender": "god-lite"},
    )

    print(f"\n  Agent: {name} / {incarnation}")
    print(f"  Response: {response.content[:300]}")

    assert response.content, "Agent returned an empty response"
    assert len(response.content) > 10, "Response suspiciously short"
    assert response.agent == name
    assert response.incarnation == incarnation
    assert response.cycle >= 1
