import { useState, useEffect } from "react";
import { useStore } from "../store";
import { fetchIncarnations } from "../lib/api";
import type { AureliaIncarnation } from "../lib/api";

export type View = "Chat" | "Samsara" | "Logs";

type Props = {
  collapsed: boolean;
  onToggle: () => void;
  view: View;
  onView: (v: View) => void;
  onSelectIncarnation: (agentId: string, incId: string) => Promise<void>;
  onSpawnIncarnation: (agentId: string) => Promise<void>;
};

const MENU_ITEMS: [View, string, string][] = [
  ["Chat",    "💬", "transcript view"],
  ["Samsara", "◉",  "runtime status"],
  ["Logs",    "≡",  "live tail"],
];

const SAMSARA_STUBS: [string, string][] = [
  ["cluster", "0 nodes"],
  ["incarnations", "live count"],
  ["queues", "in/out"],
  ["restarts", "today"],
  ["spend", "per agent"],
];

const LOGS_STUBS: [string, string][] = [
  ["all streams", "tail"],
  ["errors", "filtered"],
  ["tool calls", "trace"],
  ["model i/o", "raw"],
  ["audit", "history"],
];

function agentInitial(name: string) {
  return name.charAt(0).toUpperCase();
}

export function UnifiedRail({
  collapsed,
  onToggle,
  view,
  onView,
  onSelectIncarnation,
  onSpawnIncarnation,
}: Props) {
  const [mode, setMode] = useState<"menu" | "tree">("tree");
  const [search, setSearch] = useState("");
  const [openAgents, setOpenAgents] = useState<Record<string, boolean>>({});
  const [agentIncs, setAgentIncs] = useState<Record<string, AureliaIncarnation[]>>({});

  const agentsList = useStore((s) => s.agentsList) ?? [];
  const storeIncs = useStore((s) => s.incarnationsList) ?? [];
  const selectedAgentId = useStore((s) => s.selectedAgentId);
  const selectedIncarnationId = useStore((s) => s.selectedIncarnationId);

  // Seed the selected agent's incarnations from store
  useEffect(() => {
    if (selectedAgentId && storeIncs.length > 0) {
      setAgentIncs((prev) => ({ ...prev, [selectedAgentId]: storeIncs }));
    }
  }, [selectedAgentId, storeIncs]);

  // Auto-open selected agent
  useEffect(() => {
    if (selectedAgentId) {
      setOpenAgents((prev) => ({ ...prev, [selectedAgentId]: true }));
    }
  }, [selectedAgentId]);

  const toggleAgent = async (agentId: string) => {
    const next = !openAgents[agentId];
    setOpenAgents((prev) => ({ ...prev, [agentId]: next }));
    if (next && !agentIncs[agentId]) {
      try {
        const incs = await fetchIncarnations(agentId);
        setAgentIncs((prev) => ({ ...prev, [agentId]: incs }));
      } catch { /* silent */ }
    }
  };

  const totalIncs = Object.values(agentIncs).reduce((s, a) => s + a.length, 0);

  // ── Collapsed ──────────────────────────────────────────────────────────────
  if (collapsed) {
    return (
      <aside className="rail rail--collapsed">
        <button className="rail__expand-btn" onClick={onToggle} title="Expand rail">›</button>
        <div className="rail__divider" />
        {agentsList.map((a) => {
          const isSelected = a.name === selectedAgentId;
          const isActive = a.status === "active";
          return (
            <button
              key={a.name}
              title={a.name}
              className={[
                "rail-collapsed-agent",
                isActive || isSelected ? "rail-collapsed-agent--gradient" : "rail-collapsed-agent--outlined",
                isSelected ? "rail-collapsed-agent--selected" : "",
              ].filter(Boolean).join(" ")}
              onClick={() => {
                const inc = agentIncs[a.name]?.[0];
                if (inc) void onSelectIncarnation(a.name, inc.name);
              }}
            >
              {agentInitial(a.name)}
            </button>
          );
        })}
        <button className="rail__new-agent-btn" title="New agent">＋</button>
      </aside>
    );
  }

  // ── Menu mode ──────────────────────────────────────────────────────────────
  if (mode === "menu") {
    return (
      <aside className="rail" style={{ width: 268, minWidth: 268 }}>
        <div className="rail__crumbs-row">
          <div className="rail__crumbs">
            <span className="rail__crumb-current">Aurelia</span>
          </div>
        </div>
        <div style={{ padding: "10px 8px", display: "flex", flexDirection: "column", gap: 2 }}>
          {MENU_ITEMS.map(([name, glyph, hint]) => (
            <button
              key={name}
              className={`rail-menu__row${view === name ? " rail-menu__row--active" : ""}`}
              onClick={() => { onView(name); setMode("tree"); }}
            >
              <span className="rail-menu__icon">{glyph}</span>
              <span>{name}</span>
              <span className="rail-menu__hint">{hint}</span>
            </button>
          ))}
        </div>
        <div className="rail__footer">
          <span>{agentsList.length} agents · {totalIncs} incarnations</span>
        </div>
      </aside>
    );
  }

  // ── Tree mode ──────────────────────────────────────────────────────────────
  const stubs = view === "Samsara" ? SAMSARA_STUBS : view === "Logs" ? LOGS_STUBS : null;

  const q = search.toLowerCase();

  return (
    <aside className="rail" style={{ width: 268, minWidth: 268 }}>
      <div className="rail__crumbs-row">
        <div className="rail__crumbs">
          <button className="rail__crumb-btn" onClick={() => setMode("menu")}>Aurelia</button>
          <span className="rail__crumb-sep">/</span>
          <span className="rail__crumb-current">{view}</span>
        </div>
        {view === "Chat" && (
          <div className="rail__search">
            <span style={{ opacity: 0.55, fontFamily: "var(--mono)", fontSize: 12 }}>⌕</span>
            <input
              className="rail__search-input"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Find agent or incarnation…"
            />
          </div>
        )}
      </div>

      <div className="rail__scroll">
        {stubs ? (
          <div style={{ padding: "6px 4px 12px", display: "flex", flexDirection: "column", gap: 1 }}>
            {stubs.map(([label, hint]) => (
              <div key={label} className="rail-stub">
                <span className="rail-stub__label">
                  <span className="rail-stub__dot" />
                  {label}
                </span>
                <span className="rail-stub__hint">{hint}</span>
              </div>
            ))}
            <div className="rail-stub__coming-soon">COMING SOON</div>
          </div>
        ) : (
          agentsList.map((a) => {
            const isOpen = openAgents[a.name] ?? false;
            const incs = agentIncs[a.name] ?? [];
            const filtered = q
              ? incs.filter((i) => (a.name + " " + i.name).toLowerCase().includes(q))
              : incs;
            const isActive = a.name === selectedAgentId;

            return (
              <div key={a.name} className="rail-agent">
                <button
                  className="rail-agent__header"
                  onClick={() => void toggleAgent(a.name)}
                >
                  <span className="rail-agent__chevron">{isOpen ? "▾" : "▸"}</span>
                  <span className={`rail-agent__avatar ${isActive ? "rail-agent__avatar--gradient" : "rail-agent__avatar--outlined"}`}>
                    {agentInitial(a.name)}
                  </span>
                  <span className="rail-agent__name">
                    {a.name}
                  </span>
                  <span className="rail-agent__count">{incs.length || "·"}</span>
                </button>

                {isOpen && (
                  <div className="rail-incs">
                    <div className="rail-incs__line" />
                    {filtered.map((inc) => {
                      const isSelectedInc = inc.name === selectedIncarnationId && isActive;
                      return (
                        <button
                          key={inc.name}
                          className={`rail-inc${isSelectedInc ? " rail-inc--active" : ""}`}
                          onClick={() => void onSelectIncarnation(a.name, inc.name)}
                        >
                          <span className="rail-inc__name">
                            {isSelectedInc && <span className="rail-inc__dot">●</span>}
                            {inc.name}
                          </span>
                          <span className="rail-inc__meta">{inc.cycle}</span>
                          <span className="rail-inc__meta">
                            {inc.status === "active" ? "live" : inc.status}
                          </span>
                        </button>
                      );
                    })}
                    <button
                      className="rail-inc__new"
                      onClick={() => void onSpawnIncarnation(a.name)}
                    >
                      ＋ new incarnation
                    </button>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      <div className="rail__footer">
        <span>
          {view === "Chat"
            ? `${agentsList.length} agents · ${totalIncs} incarnations`
            : `${view.toLowerCase()} · not yet wired`}
        </span>
      </div>
    </aside>
  );
}
