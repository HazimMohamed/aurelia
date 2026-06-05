import { useRef } from "react";
import TextareaAutosize from "react-textarea-autosize";
import { useStore } from "../store";
import { useChat } from "../hooks/useChat";
import { Masthead } from "../components/Masthead";
import { LedgerThread } from "../components/LedgerThread";

function formatTime(ts: number) {
  return new Date(ts).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

export function Chat() {
  const chatMessages    = useStore((s) => s.chatMessages);
  const chatStream      = useStore((s) => s.chatStream);
  const chatStreamStart = useStore((s) => s.chatStreamStartedAt);
  const chatSending     = useStore((s) => s.chatSending);
  const chatLoading     = useStore((s) => s.chatLoading);
  const chatDraft       = useStore((s) => s.chatDraft);
  const chatToolMsgs    = useStore((s) => s.chatToolMessages);
  const showThinking    = useStore((s) => s.showThinking);
  const connected       = useStore((s) => s.connected);
  const selectedAgent   = useStore((s) => s.selectedAgentId);
  const selectedInc     = useStore((s) => s.selectedIncarnationId);

  const { send, abort } = useChat();
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  function handleSend() {
    if (!chatDraft.trim() || !connected) return;
    void send(chatDraft);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key !== "Enter") return;
    if (e.isComposing || e.keyCode === 229) return;
    if (e.shiftKey) return;
    if (!connected) return;
    e.preventDefault();
    handleSend();
  }

  const userCount = chatMessages.filter((m) => m.role === "user").length;
  const nextCycle = userCount + 1;
  const now = Date.now();

  return (
    <>
      <Masthead
        agentId={selectedAgent}
        incarnationId={selectedInc}
        msgCount={chatMessages.length}
        cumCostUsd={null}
      />

      <LedgerThread
        messages={chatMessages}
        stream={chatStream}
        streamStartedAt={chatStreamStart}
        toolMessages={chatToolMsgs}
        showThinking={showThinking}
        loading={chatLoading}
      />

      <div className="composer-c">
        <div className="composer-c__inner">
          <div className="composer-c__gutter">
            <span className="composer-c__gutter-role">You</span>
            <span className="composer-c__gutter-time">{formatTime(now)}</span>
            <span className="composer-c__gutter-cycle">§ {String(nextCycle).padStart(2, "0")}</span>
          </div>
          <div className="composer-c__body">
            <div className="composer-c__box">
              <TextareaAutosize
                ref={textareaRef}
                className="composer-c__textarea"
                value={chatDraft}
                minRows={1}
                maxRows={8}
                disabled={!connected}
                placeholder={
                  connected
                    ? "↩ send · ⇧↩ newline · @ mention · / commands"
                    : "Connect to backend to start chatting…"
                }
                onChange={(e) => useStore.getState().setChatDraft(e.target.value)}
                onKeyDown={handleKeyDown}
              />
              <div className="composer-c__bar">
                <div className="composer-c__bar-left">
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                    <span style={{ width: 5, height: 5, borderRadius: 999, background: connected ? "#3f9f66" : "var(--muted-soft)", display: "inline-block" }} />
                    {connected ? "ready" : "offline"}
                  </span>
                </div>
                <div className="composer-c__bar-right">
                  {chatSending && (
                    <button className="composer-c__stop" onClick={abort}>
                      Stop
                    </button>
                  )}
                  <button
                    className="composer-c__send"
                    disabled={!connected}
                    onClick={handleSend}
                  >
                    SEND ↵
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
