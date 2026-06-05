import { useRef, useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { LedgerTool, type LedgerToolData } from "./LedgerTool";
import type { RawMessage, ToolMessage } from "../store";

function formatTime(ts: number) {
  return new Date(ts).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function extractText(msg: RawMessage): string {
  const content = Array.isArray(msg.content) ? msg.content : [];
  for (const item of content) {
    const it = item as Record<string, unknown>;
    if (it.type === "text" && typeof it.text === "string") return it.text;
  }
  return "";
}

function extractThinking(msg: RawMessage): string {
  const content = Array.isArray(msg.content) ? msg.content : [];
  for (const item of content) {
    const it = item as Record<string, unknown>;
    if (it.type === "thinking" && typeof it.thinking === "string") return it.thinking;
  }
  return "";
}

function extractTools(msg: RawMessage): LedgerToolData[] {
  const content = Array.isArray(msg.content) ? msg.content : [];
  const cards: LedgerToolData[] = [];
  const byKey = new Map<string, LedgerToolData>();

  for (const item of content) {
    const it = item as Record<string, unknown>;
    const kind = String(it.type ?? "").toLowerCase();
    if (["tool_use", "tooluse", "tool_call", "toolcall"].includes(kind)) {
      const name = String(it.name ?? "tool");
      const key = String(it.id ?? it.tool_call_id ?? it.toolCallId ?? `${name}:${cards.length}`);
      if (!byKey.has(key)) {
        const card: LedgerToolData = { key, name, args: it.arguments ?? it.args ?? it.input, running: false };
        cards.push(card);
        byKey.set(key, card);
      }
    }
  }

  for (const item of content) {
    const it = item as Record<string, unknown>;
    const kind = String(it.type ?? "").toLowerCase();
    if (!["tool_result", "toolresult"].includes(kind)) continue;
    const key = String(it.tool_use_id ?? it.toolCallId ?? it.tool_call_id ?? "");
    const output =
      typeof it.text === "string" ? it.text
      : typeof it.result === "string" ? it.result
      : it.result != null ? JSON.stringify(it.result, null, 2)
      : "";
    const existing = byKey.get(key);
    if (existing) existing.output = output;
  }

  return cards;
}

type TurnProps = {
  msg: RawMessage;
  userIndex: number;
  showThinking: boolean;
};

function LedgerTurn({ msg, userIndex, showThinking }: TurnProps) {
  const [thinkingOpen, setThinkingOpen] = useState(false);
  const isUser = msg.role === "user";
  const text = extractText(msg);
  const thinking = extractThinking(msg);
  const tools = extractTools(msg);
  const time = formatTime(msg.timestamp);

  return (
    <div className="ledger-turn">
      <div className="ledger-turn__gutter">
        <span className={`ledger-turn__role ledger-turn__role--${isUser ? "user" : "assistant"}`}>
          {isUser ? "You" : "Aurelia"}
        </span>
        <span>{time}</span>
        {isUser && (
          <span className="ledger-turn__cycle">§ {String(userIndex).padStart(2, "0")}</span>
        )}
        {!isUser && tools.length > 0 && (
          <span className="ledger-turn__model-meta">{tools.length} tool{tools.length !== 1 ? "s" : ""}</span>
        )}
      </div>
      <div className="ledger-turn__body">
        {thinking && showThinking && (
          <div>
            <button
              className="ledger-turn__thinking-toggle"
              onClick={() => setThinkingOpen((o) => !o)}
            >
              <span style={{ fontFamily: "var(--mono)", fontSize: 10 }}>{thinkingOpen ? "▾" : "▸"}</span>
              <span className="ledger-turn__thinking-label">THINKING</span>
            </button>
            {thinkingOpen && (
              <div className="ledger-turn__thinking">{thinking}</div>
            )}
          </div>
        )}
        {tools.length > 0 && (
          <div className="ledger-turn__tools">
            {tools.map((t) => <LedgerTool key={t.key} tool={t} />)}
          </div>
        )}
        {text && (
          <div className={`ledger-md ${isUser ? "ledger-turn__text--user" : "ledger-turn__text--assistant"}`}>
            <ReactMarkdown>{text}</ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}

type StreamingTurnProps = {
  stream: string | null;
  toolMessages: ToolMessage[];
  streamStartedAt: number | null;
  userCount: number;
  showThinking: boolean;
};

function StreamingTurn({ stream, toolMessages, streamStartedAt, showThinking }: StreamingTurnProps) {
  const time = streamStartedAt ? formatTime(streamStartedAt) : "";
  const hasContent = stream !== null || toolMessages.length > 0;
  if (!hasContent) return null;

  const tools: LedgerToolData[] = toolMessages.map((m) => ({
    key: m.tool_use_id,
    name: String(m.name ?? "tool"),
    args: m.input,
    output: m.result != null
      ? typeof m.result === "string" ? m.result : JSON.stringify(m.result, null, 2)
      : undefined,
    running: m.running,
  }));

  return (
    <div className="ledger-streaming">
      <div className="ledger-streaming__gutter">
        <span style={{ fontSize: "9.5px", letterSpacing: ".22em", textTransform: "uppercase", color: "var(--accent)", fontWeight: 600 }}>
          Aurelia
        </span>
        <span>{time}</span>
      </div>
      <div className="ledger-streaming__body" style={{ flexDirection: "column", alignItems: "flex-start", gap: 8, padding: "0 24px 0 22px" }}>
        {tools.length > 0 && (
          <div className="ledger-turn__tools" style={{ width: "100%" }}>
            {tools.map((t) => <LedgerTool key={t.key} tool={t} />)}
          </div>
        )}
        {stream !== null && (
          stream.trim() ? (
            <div className="ledger-md ledger-turn__text--assistant">
              <ReactMarkdown>{stream}</ReactMarkdown>
            </div>
          ) : (
            <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--muted)" }}>
              <span className="ledger-streaming__label">thinking</span>
              <span className="ledger-dots">
                <span /><span /><span />
              </span>
            </div>
          )
        )}
        {stream === null && tools.every((t) => t.running) && (
          <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--muted)" }}>
            <span className="ledger-streaming__label">working</span>
            <span className="ledger-dots">
              <span /><span /><span />
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

type Props = {
  messages: RawMessage[];
  stream: string | null;
  streamStartedAt: number | null;
  toolMessages: ToolMessage[];
  showThinking: boolean;
  loading: boolean;
};

export function LedgerThread({
  messages,
  stream,
  streamStartedAt,
  toolMessages,
  showThinking,
  loading,
}: Props) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, stream]);

  let userCount = 0;
  const isStreaming = stream !== null || toolMessages.length > 0;

  return (
    <div className="ledger">
      {loading && (
        <div style={{ padding: "24px 0", color: "var(--muted-soft)", fontFamily: "var(--mono)", fontSize: 11 }}>
          loading…
        </div>
      )}
      {messages.map((msg, i) => {
        if (msg.role === "user") userCount++;
        return (
          <LedgerTurn
            key={i}
            msg={msg}
            userIndex={userCount}
            showThinking={showThinking}
          />
        );
      })}
      {isStreaming && (
        <StreamingTurn
          stream={stream}
          toolMessages={toolMessages}
          streamStartedAt={streamStartedAt}
          userCount={userCount}
          showThinking={showThinking}
        />
      )}
      <div ref={endRef} />
    </div>
  );
}
