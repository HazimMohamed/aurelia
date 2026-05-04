from src.samsara.provisioning import destroy_agent

for agent in ["personal"]:
    print(f"Destroying {agent}...")
    destroy_agent(agent)
    print(f"  Done.")
