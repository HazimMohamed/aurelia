import { useEffect } from "react";
import { useStore } from "./store";
import { fetchHealth, fetchAgents, fetchIncarnations } from "./lib/api";
import { resolveTheme } from "./lib/theme";
import { Nav } from "./components/Nav";
import { ThemeToggle } from "./components/ThemeToggle";
import { AgentSelector } from "./components/AgentSelector";
import { Chat } from "./views/Chat";
import { Agents } from "./views/Agents";
import { Logs } from "./views/Logs";
import { useChat } from "./hooks/useChat";

const PAGE_TITLES: Record<string, { title: string; sub: string }> = {
  chat: { title: "Chat", sub: "Talk to an agent" },
  agents: { title: "Agents", sub: "View and manage agents" },
  logs: { title: "Logs", sub: "Live log stream" },
};

export default function App() {
  const tab = useStore((s) => s.tab);
  const connected = useStore((s) => s.connected);
  const lastError = useStore((s) => s.lastError);
  const settings = useStore((s) => s.settings);
  const applySettings = useStore((s) => s.applySettings);
  const { loadHistory } = useChat();

  // Apply persisted theme on mount
  useEffect(() => {
    const theme = resolveTheme((settings.theme as "system" | "light" | "dark") ?? "system");
    document.documentElement.setAttribute("data-theme", theme);

    // Watch system theme changes
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => {
      if (!settings.theme || settings.theme === "system") {
        document.documentElement.setAttribute("data-theme", mq.matches ? "dark" : "light");
      }
    };
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  // Health polling + initial agent load
  useEffect(() => {
    async function poll() {
      try {
        const result = await fetchHealth();
        useStore.setState({ connected: result.status === "healthy", lastError: null });

        // Load agents on first connect
        const { agentsList, agentsLoading } = useStore.getState();
        if (!agentsList && !agentsLoading) {
          useStore.setState({ agentsLoading: true });
          try {
            const agents = await fetchAgents();
            useStore.setState({ agentsList: agents, agentsLoading: false });

            // Restore or auto-select first agent
            const state = useStore.getState();
            const persisted = state.settings.selectedAgent;
            const valid = persisted && agents.some((a) => a.name === persisted);
            const agentId = valid ? persisted : agents[0]?.name ?? null;
            if (agentId && !state.selectedAgentId) {
              useStore.setState({ selectedAgentId: agentId });

              // Load incarnations
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

  const isChat = tab === "chat";
  const { title, sub } = PAGE_TITLES[tab] ?? PAGE_TITLES["chat"];
  const navCollapsed = settings.navCollapsed ?? false;
  const chatFocus = isChat && (settings.chatFocusMode ?? false);

  return (
    <div
      className={[
        "shell",
        isChat ? "shell--chat" : "",
        navCollapsed ? "shell--nav-collapsed" : "",
        chatFocus ? "shell--chat-focus" : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {/* Topbar */}
      <header className="topbar">
        <div className="topbar-left">
          <button
            className="nav-collapse-toggle"
            onClick={() => applySettings({ navCollapsed: !navCollapsed })}
            title={navCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-label={navCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            <span className="nav-collapse-toggle__icon">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <line x1="3" y1="6" x2="21" y2="6" />
                <line x1="3" y1="12" x2="21" y2="12" />
                <line x1="3" y1="18" x2="21" y2="18" />
              </svg>
            </span>
          </button>
          <div className="brand">
            <div className="brand-logo">
              <img src="/favicon.svg" alt="Aurelia" />
            </div>
            <div className="brand-text">
              <div className="brand-title">AURELIA</div>
              <div className="brand-sub">Agent Dashboard</div>
            </div>
          </div>
        </div>
        <div className="topbar-status">
          <div className="pill">
            <span className={`statusDot ${connected ? "ok" : ""}`} />
            <span>Backend</span>
            <span className="mono">{connected ? "OK" : "Offline"}</span>
          </div>
          <ThemeToggle />
        </div>
      </header>

      {/* Sidebar nav */}
      <Nav />

      {/* Main content */}
      <main className={`content ${isChat ? "content--chat" : ""}`}>
        <section className="content-header">
          <div>
            <div className="page-title">{title}</div>
            <div className="page-sub">{sub}</div>
          </div>
          <div className="page-meta">
            {lastError && !isChat && <div className="pill danger">{lastError}</div>}
            {isChat && <AgentSelector />}
          </div>
        </section>

        {tab === "chat" && <Chat />}
        {tab === "agents" && <Agents />}
        {tab === "logs" && <Logs />}
      </main>
    </div>
  );
}
