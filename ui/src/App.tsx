import { useState, useEffect, useCallback } from "react";
import { useStore } from "./store";
import { fetchHealth, fetchAgents, fetchIncarnations, spawnIncarnation } from "./lib/api";
import { resolveTheme } from "./lib/theme";
import { UnifiedRail, type View } from "./components/UnifiedRail";
import { Chat } from "./views/Chat";
import { ComingSoon } from "./views/ComingSoon";
import { useChat } from "./hooks/useChat";

export default function App() {
  const [view, setView] = useState<View>("Chat");
  const [railCollapsed, setRailCollapsed] = useState(false);

  const connected  = useStore((s) => s.connected);
  const settings   = useStore((s) => s.settings);
  const applySettings = useStore((s) => s.applySettings);
  const { loadHistory } = useChat();

  // Apply theme on mount + system changes
  useEffect(() => {
    const theme = resolveTheme((settings.theme as "system" | "light" | "dark") ?? "system");
    document.documentElement.setAttribute("data-theme", theme);
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => {
      if (!settings.theme || settings.theme === "system") {
        document.documentElement.setAttribute("data-theme", mq.matches ? "dark" : "light");
      }
    };
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  // Health polling + initial agent/incarnation load
  useEffect(() => {
    async function poll() {
      try {
        const result = await fetchHealth();
        useStore.setState({ connected: result.status === "healthy", lastError: null });

        const { agentsList, agentsLoading } = useStore.getState();
        if (!agentsList && !agentsLoading) {
          useStore.setState({ agentsLoading: true });
          try {
            const agents = await fetchAgents();
            useStore.setState({ agentsList: agents, agentsLoading: false });

            const state = useStore.getState();
            const persisted = state.settings.selectedAgent;
            const valid = persisted && agents.some((a) => a.name === persisted);
            const agentId = valid ? persisted : agents[0]?.name ?? null;
            if (agentId) {
              if (!state.selectedAgentId) useStore.setState({ selectedAgentId: agentId });
              if (!useStore.getState().incarnationsList) {
                useStore.setState({ incarnationsLoading: true });
                try {
                  const list = await fetchIncarnations(agentId);
                  const persistedInc = state.settings.selectedIncarnation;
                  const validInc = persistedInc && list.some((i) => i.name === persistedInc);
                  const selectedInc = validInc
                    ? persistedInc
                    : list.find((i) => i.status === "active")?.name ?? list[0]?.name ?? null;
                  useStore.setState({
                    incarnationsList: list,
                    selectedIncarnationId: selectedInc,
                    incarnationsLoading: false,
                  });
                  await loadHistory();
                } catch (err) {
                  useStore.setState({ incarnationsError: String(err), incarnationsLoading: false });
                }
              }
            }
          } catch (err) {
            useStore.setState({ agentsError: String(err), agentsLoading: false });
          }
        }
      } catch {
        useStore.setState({ connected: false, lastError: "Cannot connect to backend at localhost:8000" });
      }
    }

    void poll();
    const id = setInterval(() => void poll(), 5000);
    return () => clearInterval(id);
  }, []);

  const selectIncarnation = useCallback(async (agentId: string, incId: string) => {
    try {
      useStore.setState({ selectedAgentId: agentId, selectedIncarnationId: incId });
      applySettings({ selectedAgent: agentId, selectedIncarnation: incId });
      await loadHistory();
    } catch (err) {
      console.error("selectIncarnation failed", err);
    }
  }, [loadHistory, applySettings]);

  const handleSpawnIncarnation = useCallback(async (agentId: string) => {
    try {
      const result = await spawnIncarnation(agentId);
      const list = await fetchIncarnations(agentId);
      useStore.setState({ incarnationsList: list });
      if (result.incarnation) {
        await selectIncarnation(agentId, result.incarnation);
      }
    } catch (err) {
      console.error("spawn failed", err);
    }
  }, [selectIncarnation]);

  return (
    <div className="shell-c">
      {/* ── Topbar ── */}
      <header className="topbar-c">
        <div className="topbar-c__left">
          <button
            className="topbar-c__hamburger"
            onClick={() => setRailCollapsed((c) => !c)}
            title={railCollapsed ? "Expand rail" : "Collapse rail"}
            aria-label={railCollapsed ? "Expand rail" : "Collapse rail"}
          >
            {railCollapsed ? "›≡" : "≡"}
          </button>
          <div className="topbar-c__brand-mark">A</div>
          <span className="topbar-c__wordmark">Aurelia</span>
          <span className="topbar-c__pill">local</span>
        </div>
        <div />
        <div className="topbar-c__right">
          <span className="topbar-c__cluster">
            <span style={{ color: connected ? "#7a9d6a" : "var(--muted-soft)" }}>●</span>
            {" "}{connected ? "cluster ok" : "offline"}
          </span>
          <div className="topbar-c__avatar">OC</div>
        </div>
      </header>

      {/* ── Body ── */}
      <div
        className="shell-c-body"
        style={{ gridTemplateColumns: `${railCollapsed ? 56 : 268}px 1fr` }}
      >
        <UnifiedRail
          collapsed={railCollapsed}
          onToggle={() => setRailCollapsed((c) => !c)}
          view={view}
          onView={setView}
          onSelectIncarnation={selectIncarnation}
          onSpawnIncarnation={handleSpawnIncarnation}
        />

        <main
          style={{
            display: "grid",
            gridTemplateRows: view === "Chat" ? "auto 1fr auto" : "1fr",
            minHeight: 0,
            background: "var(--panel)",
            overflow: "hidden",
          }}
        >
          {view === "Chat"    && <Chat />}
          {view === "Samsara" && <ComingSoon view="Samsara" />}
          {view === "Logs"    && <ComingSoon view="Logs" />}
        </main>
      </div>
    </div>
  );
}
