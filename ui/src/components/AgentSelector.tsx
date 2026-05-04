import { Brain, RefreshCw, Plus } from "lucide-react";
import { useStore } from "../store";
import { fetchIncarnations, spawnIncarnation } from "../lib/api";
import { useChat } from "../hooks/useChat";

export function AgentSelector() {
  const agents = useStore((s) => s.agentsList);
  const agentsLoading = useStore((s) => s.agentsLoading);
  const selectedAgentId = useStore((s) => s.selectedAgentId);
  const incarnations = useStore((s) => s.incarnationsList);
  const incarnationsLoading = useStore((s) => s.incarnationsLoading);
  const incarnationsError = useStore((s) => s.incarnationsError);
  const selectedIncarnationId = useStore((s) => s.selectedIncarnationId);
  const showThinking = useStore((s) => s.showThinking);
  const toggleShowThinking = useStore((s) => s.toggleShowThinking);
  const settings = useStore((s) => s.settings);
  const { loadHistory } = useChat();

  async function loadIncarnations(agentId: string) {
    useStore.setState({ incarnationsLoading: true, incarnationsError: null });
    try {
      const list = await fetchIncarnations(agentId);
      const persisted = useStore.getState().settings.selectedIncarnation;
      const valid = persisted && list.some((i) => i.name === persisted) ? persisted : null;
      const active = list.find((i) => i.status === "active")?.name ?? list[0]?.name ?? null;
      const selected = valid ?? active;
      useStore.setState({ incarnationsList: list, selectedIncarnationId: selected });
      useStore.getState().persistSelection();
      await loadHistory();
    } catch (err) {
      useStore.setState({ incarnationsError: String(err) });
    } finally {
      useStore.setState({ incarnationsLoading: false });
    }
  }

  async function handleAgentChange(agentId: string) {
    useStore.setState({
      selectedAgentId: agentId || null,
      incarnationsList: null,
      selectedIncarnationId: null,
      chatMessages: [],
    });
    if (agentId) await loadIncarnations(agentId);
  }

  async function handleIncarnationChange(incId: string) {
    useStore.setState({ selectedIncarnationId: incId || null });
    useStore.getState().persistSelection();
    useStore.setState({ chatMessages: [] });
    await loadHistory();
  }

  async function handleSpawn() {
    if (!selectedAgentId) return;
    useStore.setState({ incarnationsLoading: true });
    try {
      const res = await spawnIncarnation(selectedAgentId);
      await loadIncarnations(selectedAgentId);
      useStore.setState({ selectedIncarnationId: res.incarnation });
      useStore.getState().persistSelection();
    } catch (err) {
      useStore.setState({ incarnationsError: String(err), incarnationsLoading: false });
    }
  }

  return (
    <div className="chat-controls">
      <div className="chat-controls__session-agent">
        <label className="field chat-controls__combined">
          <div className="session-agent-input">
            <select
              className="session-agent-input__agent"
              value={selectedAgentId ?? ""}
              disabled={agentsLoading}
              onChange={(e) => void handleAgentChange(e.target.value)}
              title="Select agent"
            >
              {agents?.length
                ? agents.map((a) => (
                    <option key={a.name} value={a.name}>
                      {a.name}
                    </option>
                  ))
                : <option value="">—</option>}
            </select>
            <select
              className="session-agent-input__agent"
              value={selectedIncarnationId ?? ""}
              disabled={incarnationsLoading || !selectedAgentId}
              onChange={(e) => void handleIncarnationChange(e.target.value)}
              title="Select incarnation"
              style={{ maxWidth: "14ch", fontSize: "0.78em", opacity: 0.85 }}
            >
              {incarnations?.length
                ? incarnations.map((inc) => (
                    <option key={inc.name} value={inc.name}>
                      {inc.status === "active" ? "● " : "○ "}
                      {inc.name.split("-").slice(-2).join("-")}
                    </option>
                  ))
                : <option value="">—</option>}
            </select>
          </div>
        </label>
        <button
          className="btn btn--sm btn--icon"
          disabled={incarnationsLoading || !selectedAgentId}
          onClick={() => void handleSpawn()}
          title="Spawn new incarnation"
        >
          <Plus size={14} />
        </button>
      </div>

      <button
        className="btn btn--sm btn--icon"
        onClick={() => void loadHistory()}
        title="Refresh chat"
      >
        <RefreshCw size={18} />
      </button>

      <button
        className={`btn btn--sm btn--icon ${showThinking ? "active" : ""}`}
        onClick={toggleShowThinking}
        aria-pressed={showThinking}
        title="Toggle thinking output"
      >
        <Brain size={18} />
      </button>

      {incarnationsError && (
        <span style={{ color: "var(--danger)", fontSize: 12 }}>{incarnationsError}</span>
      )}
    </div>
  );
}
