import { fetchAgents, type AureliaAgent } from "../aurelia-client.ts";
import type { AgentsListResult } from "../types.ts";

export type AgentsState = {
  agentsLoading: boolean;
  agentsError: string | null;
  agentsList: AgentsListResult | null;
  agentsSelectedId: string | null;
};

function adaptAgents(agents: AureliaAgent[]): AgentsListResult {
  return {
    agents: agents.map((a) => ({
      id: a.name,
      name: a.name,
      identity: null,
    })),
    defaultId: agents[0]?.name ?? null,
  };
}

export async function loadAgents(state: AgentsState) {
  if (state.agentsLoading) {
    return;
  }
  state.agentsLoading = true;
  state.agentsError = null;
  try {
    const agents = await fetchAgents();
    state.agentsList = adaptAgents(agents);
    const selected = state.agentsSelectedId;
    const known = state.agentsList.agents.some((entry) => entry.id === selected);
    if (!selected || !known) {
      state.agentsSelectedId = state.agentsList.defaultId ?? state.agentsList.agents[0]?.id ?? null;
    }
  } catch (err) {
    state.agentsError = String(err);
  } finally {
    state.agentsLoading = false;
  }
}
