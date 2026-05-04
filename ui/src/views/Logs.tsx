import { useStore } from "../store";
import type { LogEntry, LogLevel } from "../lib/types";
import clsx from "clsx";

const LEVELS: LogLevel[] = ["trace", "debug", "info", "warn", "error", "fatal"];

const LEVEL_COLOR: Record<LogLevel, string> = {
  trace: "var(--muted)",
  debug: "var(--muted)",
  info: "var(--text)",
  warn: "var(--warn)",
  error: "var(--danger)",
  fatal: "var(--danger)",
};

function LogRow({ entry }: { entry: LogEntry }) {
  const color = entry.level ? LEVEL_COLOR[entry.level] : "var(--text)";
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "90px 50px 1fr",
        gap: 8,
        padding: "2px 0",
        borderBottom: "1px solid var(--border)",
        fontSize: 12,
        fontFamily: "var(--mono)",
        alignItems: "baseline",
      }}
    >
      <span style={{ color: "var(--muted)" }}>
        {entry.time ? new Date(entry.time).toLocaleTimeString() : ""}
      </span>
      <span style={{ color, fontWeight: 600, textTransform: "uppercase", fontSize: 10 }}>
        {entry.level ?? ""}
      </span>
      <span style={{ color: "var(--text)", wordBreak: "break-word" }}>
        {entry.subsystem ? <span style={{ color: "var(--muted)" }}>[{entry.subsystem}] </span> : null}
        {entry.message}
      </span>
    </div>
  );
}

export function Logs() {
  const entries = useStore((s) => s.logsEntries);
  const loading = useStore((s) => s.logsLoading);
  const error = useStore((s) => s.logsError);
  const filterText = useStore((s) => s.logsFilterText);
  const levelFilters = useStore((s) => s.logsLevelFilters);
  const autoFollow = useStore((s) => s.logsAutoFollow);
  const setLogsFilterText = useStore((s) => s.setLogsFilterText);
  const toggleLogsLevel = useStore((s) => s.toggleLogsLevel);
  const setLogsAutoFollow = useStore((s) => s.setLogsAutoFollow);

  const filtered = entries.filter((e) => {
    if (e.level && !levelFilters[e.level]) return false;
    if (filterText) {
      const q = filterText.toLowerCase();
      return e.message?.toLowerCase().includes(q) || e.raw?.toLowerCase().includes(q);
    }
    return true;
  });

  return (
    <div className="stack">
      <div className="card">
        <div className="filters" style={{ marginBottom: 12 }}>
          <input
            className="field"
            type="text"
            placeholder="Filter logs…"
            value={filterText}
            onChange={(e) => setLogsFilterText(e.target.value)}
            style={{ flex: 1, minWidth: 160 }}
          />
          {LEVELS.map((level) => (
            <button
              key={level}
              className={clsx("btn btn--sm", levelFilters[level] && "active")}
              onClick={() => toggleLogsLevel(level)}
              style={{ fontSize: 11, textTransform: "uppercase", padding: "4px 8px" }}
            >
              {level}
            </button>
          ))}
          <button
            className={clsx("btn btn--sm", autoFollow && "active")}
            onClick={() => setLogsAutoFollow(!autoFollow)}
          >
            Auto-follow
          </button>
        </div>

        {error && <div className="callout danger">{error}</div>}
        {loading && <div className="muted">Loading logs…</div>}

        {!loading && filtered.length === 0 && (
          <div className="muted" style={{ padding: "24px 0", textAlign: "center" }}>
            {entries.length === 0 ? "No logs yet — logs endpoint may not be available." : "No matching log entries."}
          </div>
        )}

        <div style={{ maxHeight: "calc(100vh - 300px)", overflowY: "auto" }}>
          {filtered.map((entry, i) => (
            <LogRow key={i} entry={entry} />
          ))}
        </div>
      </div>
    </div>
  );
}
