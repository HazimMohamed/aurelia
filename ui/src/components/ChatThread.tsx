import { useRef, useEffect } from "react";
import { ChatBubble } from "./ChatBubble";
import { ToolCard, type ToolCardData } from "./ToolCard";
import { normalizeMessage, normalizeRoleForGrouping } from "../lib/chat/message-normalizer";
import type { RawMessage, ToolMessage } from "../store";

type MessageGroup = {
  role: string;
  messages: RawMessage[];
  timestamp: number;
};

function groupMessages(messages: RawMessage[]): MessageGroup[] {
  const groups: MessageGroup[] = [];
  let current: MessageGroup | null = null;

  for (const msg of messages) {
    const normalized = normalizeMessage(msg);
    const role = normalizeRoleForGrouping(normalized.role);
    if (!current || current.role !== role) {
      if (current) groups.push(current);
      current = { role, messages: [msg], timestamp: normalized.timestamp ?? Date.now() };
    } else {
      current.messages.push(msg);
      current.timestamp = normalized.timestamp ?? current.timestamp;
    }
  }
  if (current) groups.push(current);
  return groups;
}

function formatTime(ts: number) {
  return new Date(ts).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

type AvatarProps = { role: string; assistantName: string };
function Avatar({ role, assistantName }: AvatarProps) {
  const normalized = normalizeRoleForGrouping(role);
  const initial =
    normalized === "user"
      ? "U"
      : normalized === "assistant"
        ? assistantName.charAt(0).toUpperCase() || "A"
        : "?";
  const cls = normalized === "user" ? "user" : normalized === "assistant" ? "assistant" : "other";
  return <div className={`chat-avatar ${cls}`}>{initial}</div>;
}

type GroupProps = {
  group: MessageGroup;
  showThinking: boolean;
  assistantName: string;
};

function ChatGroup({ group, showThinking, assistantName }: GroupProps) {
  const normalized = normalizeRoleForGrouping(group.role);
  const isUser = normalized === "user";
  const isThought = normalized === "thought";

  if (isThought) {
    return (
      <div className="chat-group thought" data-entity="ai">
        <div className="chat-group-messages">
          {group.messages.map((msg, i) => (
            <ChatBubble key={i} message={msg} showThinking={showThinking} />
          ))}
        </div>
      </div>
    );
  }

  const roleClass = isUser ? "user" : normalized === "assistant" ? "assistant" : "other";
  const entity = isUser ? "human" : "ai";

  return (
    <div className={`chat-group ${roleClass}`} data-entity={entity}>
      <Avatar role={group.role} assistantName={assistantName} />
      <div className="chat-group-messages">
        {group.messages.map((msg, i) => (
          <ChatBubble key={i} message={msg} showThinking={showThinking} />
        ))}
        <div className="chat-group-footer">
          <span className="chat-group-timestamp">{formatTime(group.timestamp)}</span>
        </div>
      </div>
    </div>
  );
}

type Props = {
  messages: RawMessage[];
  stream: string | null;
  streamStartedAt: number | null;
  toolMessages?: ToolMessage[];
  showThinking: boolean;
  loading: boolean;
  assistantName: string;
  onScroll?: (e: React.UIEvent<HTMLDivElement>) => void;
};

export function ChatThread({
  messages,
  stream,
  streamStartedAt,
  toolMessages = [],
  showThinking,
  loading,
  assistantName,
  onScroll,
}: Props) {
  const endRef = useRef<HTMLDivElement>(null);
  const threadRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when messages or stream changes
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, stream]);

  const groups = groupMessages(messages);

  return (
    <div
      ref={threadRef}
      className="chat-thread"
      role="log"
      aria-live="polite"
      onScroll={onScroll}
    >
      {loading && <div className="muted">Loading chat…</div>}

      {groups.map((group, i) => (
        <ChatGroup
          key={i}
          group={group}
          showThinking={showThinking}
          assistantName={assistantName}
        />
      ))}

      {/* Streaming indicator */}
      {(stream !== null || toolMessages.length > 0) && (
        <div className="chat-group assistant" data-entity="ai">
          <Avatar role="assistant" assistantName={assistantName} />
          <div className="chat-group-messages">
            {toolMessages.length > 0 && (
              <div className="chat-tool-list">
                {toolMessages.map((m) => {
                  const card: ToolCardData = {
                    key: m.tool_use_id,
                    name: String(m.name ?? "tool"),
                    args: m.input,
                    output: m.result != null
                      ? typeof m.result === "string" ? m.result : JSON.stringify(m.result, null, 2)
                      : undefined,
                    running: m.running,
                  };
                  return <ToolCard key={card.key} card={card} />;
                })}
              </div>
            )}
            {stream !== null && (stream.trim() ? (
              <ChatBubble
                message={{ role: "assistant", content: [{ type: "text", text: stream }], timestamp: streamStartedAt ?? Date.now() }}
                isStreaming
                showThinking={showThinking}
              />
            ) : (
              <div className="chat-bubble chat-reading-indicator" aria-hidden="true">
                <span className="chat-reading-indicator__dots">
                  <span /><span /><span />
                </span>
              </div>
            ))}
            {streamStartedAt && (
              <div className="chat-group-footer">
                <span className="chat-group-timestamp">{formatTime(streamStartedAt)}</span>
              </div>
            )}
          </div>
        </div>
      )}

      <div ref={endRef} />
    </div>
  );
}
