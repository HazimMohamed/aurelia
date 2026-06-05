type Props = {
  agentId: string | null;
  incarnationId: string | null;
  msgCount: number;
  cumCostUsd?: number | null;
};

function agentInitial(name: string) {
  return name.charAt(0).toUpperCase();
}

function formatCost(usd: number | null | undefined): string {
  if (usd == null) return "—";
  if (usd >= 1) return `$${usd.toFixed(2)}`;
  return `$${usd.toFixed(4)}`;
}

export function Masthead({ agentId, incarnationId, msgCount, cumCostUsd }: Props) {
  if (!agentId) {
    return (
      <div className="masthead" style={{ justifyContent: "center" }}>
        <div style={{ fontFamily: "var(--mono)", fontSize: 11, color: "var(--muted-soft)" }}>
          Select an agent to start chatting
        </div>
      </div>
    );
  }

  return (
    <div className="masthead">
      <div className="masthead__left">
        <div className="masthead__title-row">
          <span className="masthead__agent-avatar">{agentInitial(agentId)}</span>
          <span className="masthead__agent-name">{agentId}</span>
          {incarnationId && (
            <>
              <span className="masthead__sep"> / </span>
              <span className="masthead__inc-name">{incarnationId}</span>
            </>
          )}
          <span className="masthead__inc-pill">
            INCARNATION · {msgCount} MSG
          </span>
        </div>
        <div className="masthead__meta-row">
          {incarnationId && (
            <>
              <span>
                <span className="masthead__meta-key">inc </span>
                {incarnationId}
              </span>
              <span className="masthead__meta-sep">·</span>
            </>
          )}
          <span className="masthead__spent-chip">
            <span className="masthead__spent-label">spent </span>
            {formatCost(cumCostUsd)}
          </span>
        </div>
      </div>
      <div className="masthead__right">
        <button className="masthead__chip masthead__chip--accent">memory</button>
        <button className="masthead__chip">fork</button>
      </div>
    </div>
  );
}
