import { useStore } from "../store";
import { formatRelativeTimestamp } from "../lib/format";

function statusColor(status: string) {
  if (status === "active") return "var(--ok)";
  if (status === "idle" || status === "sleeping") return "var(--warn)";
  return "var(--muted)";
}

export function Agents() {
  const agents = useStore((s) => s.agentsList);
  const agentsLoading = useStore((s) => s.agentsLoading);
  const agentsError = useStore((s) => s.agentsError);
  const incarnations = useStore((s) => s.incarnationsList);
  const selectedAgentId = useStore((s) => s.selectedAgentId);

  if (agentsLoading) {
    return <div className="muted">Loading agents…</div>;
  }

  if (agentsError) {
    return <div className="callout danger">{agentsError}</div>;
  }

  if (!agents?.length) {
    return <div className="muted">No agents found.</div>;
  }

  return (
    <div className="stack">
      <div className="stat-grid">
        {agents.map((agent) => (
          <div
            key={agent.name}
            className="card stat-card"
            style={selectedAgentId === agent.name ? { borderColor: "var(--accent)" } : undefined}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
              <span style={{ fontWeight: 600, fontSize: 15 }}>{agent.name}</span>
              <span
                className="pill"
                style={{ borderColor: statusColor(agent.status), color: statusColor(agent.status), fontSize: 11, padding: "2px 8px" }}
              >
                {agent.status}
              </span>
            </div>
            {agent.incarnation && (
              <div className="stat-label" style={{ marginTop: 6 }}>
                incarnation: <span style={{ color: "var(--text)" }}>{agent.incarnation}</span>
              </div>
            )}
            {agent.last_active && (
              <div className="stat-label" style={{ marginTop: 4 }}>
                last active: {formatRelativeTimestamp(new Date(agent.last_active).getTime())}
              </div>
            )}
            {agent.weekly_budget != null && (
              <div className="stat-label" style={{ marginTop: 4 }}>
                budget: {agent.budget_remaining ?? "?"} / {agent.weekly_budget} remaining
              </div>
            )}
            {agent.scheduler_queue > 0 && (
              <div className="stat-label" style={{ marginTop: 4, color: "var(--warn)" }}>
                {agent.scheduler_queue} task{agent.scheduler_queue !== 1 ? "s" : ""} queued
              </div>
            )}
          </div>
        ))}
      </div>

      {selectedAgentId && incarnations && incarnations.length > 0 && (
        <div className="card">
          <div className="card-title" style={{ marginBottom: 12 }}>
            Incarnations — {selectedAgentId}
          </div>
          <div className="stack" style={{ gap: 8 }}>
            {incarnations.map((inc) => (
              <div key={inc.name} className="row" style={{ justifyContent: "space-between" }}>
                <span style={{ fontFamily: "var(--mono)", fontSize: 12 }}>
                  {inc.name.split("-").slice(-3).join("-")}
                </span>
                <span
                  className="pill"
                  style={{ color: statusColor(inc.status), borderColor: statusColor(inc.status), fontSize: 11, padding: "2px 8px" }}
                >
                  {inc.status}
                </span>
                <span className="stat-label">cycle {inc.cycle}</span>
                {inc.last_active && (
                  <span className="stat-label">{formatRelativeTimestamp(new Date(inc.last_active).getTime())}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
