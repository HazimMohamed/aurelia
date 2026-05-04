import { useState } from "react";
import { Copy, Check, Wrench } from "lucide-react";
import clsx from "clsx";

export type ToolCardData = {
  key: string;
  name: string;
  args?: unknown;
  output?: string;
  running?: boolean;
};

function formatValue(v: unknown): string {
  if (v == null) return "";
  if (typeof v === "string") return v;
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return String(v);
  }
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  function copy() {
    void navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }
  return (
    <button className="chat-tool-card__copy" onClick={copy} title="Copy">
      {copied ? <Check size={12} /> : <Copy size={12} />}
    </button>
  );
}

export function ToolCard({ card }: { card: ToolCardData }) {
  const argsStr = formatValue(card.args);
  const outputStr = card.output ?? "";
  const hasContent = Boolean(argsStr || outputStr);

  return (
    <details className="chat-tool-card" open={false}>
      <summary
        className={clsx("chat-tool-card__summary", !hasContent && "chat-tool-card__summary--static")}
      >
        <span className="chat-tool-card__icon">
          <Wrench size={10} />
        </span>
        <span className="chat-tool-card__name">{card.name}</span>
        {card.running ? (
          <span className="chat-tool-card__status">running…</span>
        ) : (
          <span className="chat-tool-card__status">done</span>
        )}
        {argsStr && (
          <span className="chat-tool-card__input">
            {argsStr.slice(0, 80)}{argsStr.length > 80 ? "…" : ""}
          </span>
        )}
      </summary>
      {hasContent && (
        <div className="chat-tool-card__expanded">
          <table className="chat-tool-card__table">
            <tbody>
              {argsStr && (
                <tr>
                  <td className="chat-tool-card__label">Input</td>
                  <td className="chat-tool-card__value">
                    <div className="chat-tool-card__value-row">
                      <pre className="chat-tool-card__pre">{argsStr}</pre>
                      <CopyButton text={argsStr} />
                    </div>
                  </td>
                </tr>
              )}
              {outputStr && (
                <tr>
                  <td className="chat-tool-card__label">Output</td>
                  <td className="chat-tool-card__value">
                    <div className="chat-tool-card__value-row">
                      <pre className="chat-tool-card__pre">{outputStr}</pre>
                      <CopyButton text={outputStr} />
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </details>
  );
}
