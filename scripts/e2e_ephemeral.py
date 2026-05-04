"""
End-to-end test: create ephemeral agent → spawn → dispatch → destroy.
Must be run as root.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.samsara.provisioning import create_ephemeral_agent, destroy_ephemeral_agent
from src.transport.client import RuntimeClient

W = 60
client = RuntimeClient()

print(f"\n{'═'*W}")
print("  Ephemeral Agent E2E Test")
print(f"{'═'*W}\n")

agent = None
try:
    # ── 1. Create ──────────────────────────────────────────────────────────────
    print("[ 1/6 ] Creating ephemeral agent (personal)...")
    agent = create_ephemeral_agent("personal")
    print(f"        name:  {agent.name}")
    print(f"        home:  /home/{agent.name}")
    print(f"        token: {agent.token[:8]}...")

    # ── 2. Registry reload ─────────────────────────────────────────────────────
    print("\n[ 2/6 ] Reloading runtime registry...")
    client.registry_reload()
    print("        done")

    # ── 3. Verify agent is known ───────────────────────────────────────────────
    print("\n[ 3/6 ] Verifying agent is registered...")
    agents = client.list_agents()
    names = [a.name for a in agents]
    assert agent.name in names, f"Agent {agent.name} not found in registry: {names}"
    print(f"        found in registry ({len(agents)} agents total)")

    # ── 4. Spawn incarnation ───────────────────────────────────────────────────
    print("\n[ 4/6 ] Spawning incarnation...")
    inc = client.spawn(agent.name)
    print(f"        incarnation: {inc.name}")

    # ── 5. Dispatch a message ──────────────────────────────────────────────────
    print("\n[ 5/6 ] Dispatching human_message...")
    print(f"{'─'*W}")
    response = client.dispatch(
        agent=agent.name,
        incarnation=inc.name,
        hook="human_message",
        payload={"content": "Hello — quick test. Who are you and what is this place?", "sender": "test"},
    )
    print(response.content)
    print(f"{'─'*W}")
    print(f"        cycle: {response.cycle}  next: {response.next_action}")

finally:
    # ── 6. Destroy (always runs) ───────────────────────────────────────────────
    if agent:
        print("\n[ 6/6 ] Destroying ephemeral agent...")
        destroy_ephemeral_agent(agent)
        client.registry_reload()
        print(f"        {agent.name} torn down")

        # Confirm gone
        agents = client.list_agents()
        assert agent.name not in [a.name for a in agents], "Agent still in registry after destroy"
        print("        confirmed removed from registry")

print(f"\n{'═'*W}")
print("  E2E test passed.")
print(f"{'═'*W}\n")
