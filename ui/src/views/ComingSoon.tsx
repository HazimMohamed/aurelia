type View = "Samsara" | "Logs";

const MAP: Record<View, { label: string; title: string; blurb: string; glyph: string }> = {
  Samsara: {
    label: "SAMSARA",
    title: "Runtime status",
    blurb: "Live view of agent incarnations: per-tick spend, queue depth, failure modes, restart cadence. The wheel keeps turning.",
    glyph: "◉",
  },
  Logs: {
    label: "LOGS",
    title: "Live tail",
    blurb: "Structured event stream across all agents and incarnations — filtered, searchable, replayable.",
    glyph: "≡",
  },
};

export function ComingSoon({ view }: { view: View }) {
  const m = MAP[view];
  return (
    <div className="coming-soon">
      <div className="coming-soon__inner">
        <div className="coming-soon__glyph-card">{m.glyph}</div>
        <div className="coming-soon__label">{m.label} · COMING SOON</div>
        <div className="coming-soon__title">{m.title}</div>
        <div className="coming-soon__blurb">{m.blurb}</div>
      </div>
    </div>
  );
}
