import { useState } from "react";

export type LedgerToolData = {
  key: string;
  name: string;
  args: unknown;
  output?: string;
  running: boolean;
};

type Props = { tool: LedgerToolData };

function formatArgs(name: string, args: unknown): string {
  if (!args) return `$ ${name}()`;
  const entries =
    typeof args === "object" && args !== null
      ? Object.entries(args as Record<string, unknown>)
      : null;
  if (!entries || entries.length === 0) return `$ ${name}()`;
  const inner = entries
    .map(([k, v]) => `${k}=${typeof v === "string" ? `"${v}"` : JSON.stringify(v)}`)
    .join(", ");
  return `$ ${name}(${inner})`;
}

export function LedgerTool({ tool }: Props) {
  const [open, setOpen] = useState(true);

  const statusClass =
    tool.running ? "ledger-tool__status--run"
    : tool.output != null ? "ledger-tool__status--ok"
    : "ledger-tool__status--ok";

  const statusLabel =
    tool.running ? "● RUNNING"
    : tool.output != null ? "● OK"
    : "● PENDING";

  return (
    <div className="ledger-tool">
      <div
        className={`ledger-tool__header${open ? " ledger-tool__header--open" : ""}`}
        onClick={() => setOpen((o) => !o)}
      >
        <span className={`ledger-tool__status ${statusClass}`}>{statusLabel}</span>
        <span className="ledger-tool__cmd">{formatArgs(tool.name, tool.args)}</span>
        <span className="ledger-tool__dur">
          <button
            className="ledger-tool__toggle"
            onClick={(e) => { e.stopPropagation(); setOpen((o) => !o); }}
          >
            {open ? "hide" : "show"}
          </button>
        </span>
      </div>
      {open && tool.output != null && (
        <div className="ledger-tool__output">
          <span className="ledger-tool__output-prompt">{">"} </span>
          {tool.output}
        </div>
      )}
      {open && tool.running && (
        <div className="ledger-tool__output" style={{ color: "var(--muted-soft)", fontStyle: "italic" }}>
          running…
        </div>
      )}
    </div>
  );
}
