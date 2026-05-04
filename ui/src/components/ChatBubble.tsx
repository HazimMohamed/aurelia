import { useState } from "react";
import ReactMarkdown from "react-markdown";
import clsx from "clsx";
import { ToolCard, type ToolCardData } from "./ToolCard";
import { extractTextCached, extractThinkingCached } from "../lib/chat/message-extract";
import { detectTextDirection } from "../lib/text-direction";

function extractToolCards(message: unknown): ToolCardData[] {
  const m = message as Record<string, unknown>;
  const content = Array.isArray(m.content) ? m.content : [];
  const cards: ToolCardData[] = [];
  const cardsByKey = new Map<string, ToolCardData>();
  const pendingByName = new Map<string, ToolCardData[]>();

  for (let i = 0; i < content.length; i++) {
    const item = content[i] as Record<string, unknown>;
    const kind = String(item.type ?? "").toLowerCase();
    const isCall = ["toolcall", "tool_call", "tooluse", "tool_use"].includes(kind);
    if (isCall) {
      const name = String(item.name ?? "tool");
      const key = String(item.id ?? item.toolCallId ?? item.tool_call_id ?? `${name}:${i}`);
      if (!cardsByKey.has(key)) {
        const args = item.arguments ?? item.args ?? item.input;
        const card: ToolCardData = { key, name, args };
        cards.push(card);
        cardsByKey.set(key, card);
        pendingByName.set(name, [...(pendingByName.get(name) ?? []), card]);
      }
    }
  }

  for (let i = 0; i < content.length; i++) {
    const item = content[i] as Record<string, unknown>;
    const kind = String(item.type ?? "").toLowerCase();
    if (kind !== "toolresult" && kind !== "tool_result") continue;
    const name = String(item.name ?? item.tool_name ?? "tool");
    const key = String(item.toolCallId ?? item.tool_call_id ?? item.tool_use_id ?? `${name}:${i}`);
    const existing = cardsByKey.get(key);
    const output = typeof item.text === "string"
      ? item.text
      : typeof item.result === "string"
        ? item.result
        : item.result != null
          ? JSON.stringify(item.result, null, 2)
          : "";
    if (existing) {
      existing.output = output;
    } else {
      const pending = pendingByName.get(name)?.find((c) => c.output == null);
      if (pending) pending.output = output;
    }
  }

  return cards;
}

type Props = {
  message: unknown;
  isStreaming?: boolean;
  showThinking: boolean;
};

export function ChatBubble({ message, isStreaming, showThinking }: Props) {
  const [thinkingOpen, setThinkingOpen] = useState(false);
  const text = extractTextCached(message);
  const thinking = extractThinkingCached(message);
  const toolCards = extractToolCards(message);
  const hasToolCards = toolCards.length > 0;

  if (hasToolCards) {
    return (
      <div className="chat-tool-list">
        {toolCards.map((card) => (
          <ToolCard key={card.key} card={card} />
        ))}
      </div>
    );
  }

  if (!text && !thinking) return null;

  return (
    <div className={clsx("chat-bubble", "fade-in", isStreaming && "streaming")}>
      {thinking && showThinking && (
        <div>
          <button
            style={{ background: "none", border: "none", cursor: "pointer", padding: "0 0 4px", color: "var(--muted)", fontSize: 11 }}
            onClick={() => setThinkingOpen((o) => !o)}
          >
            {thinkingOpen ? "▾ thinking" : "▸ thinking"}
          </button>
          {thinkingOpen && (
            <div
              className="chat-text chat-text--thinking"
              dir={detectTextDirection(thinking)}
            >
              <ReactMarkdown>{thinking}</ReactMarkdown>
            </div>
          )}
        </div>
      )}
      {text && (
        <div className="chat-text" dir={detectTextDirection(text)}>
          <ReactMarkdown>{text}</ReactMarkdown>
        </div>
      )}
    </div>
  );
}
