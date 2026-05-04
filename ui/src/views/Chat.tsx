import { useStore } from "../store";
import { useChat } from "../hooks/useChat";
import { AgentSelector } from "../components/AgentSelector";
import { ChatThread } from "../components/ChatThread";
import { ChatInput } from "../components/ChatInput";

export function Chat() {
  const connected = useStore((s) => s.connected);
  const chatMessages = useStore((s) => s.chatMessages);
  const chatStream = useStore((s) => s.chatStream);
  const chatStreamStartedAt = useStore((s) => s.chatStreamStartedAt);
  const chatSending = useStore((s) => s.chatSending);
  const chatLoading = useStore((s) => s.chatLoading);
  const chatDraft = useStore((s) => s.chatDraft);
  const chatToolMessages = useStore((s) => s.chatToolMessages);
  const showThinking = useStore((s) => s.showThinking);
  const lastError = useStore((s) => s.lastError);
  const { send, abort } = useChat();

  function handleSend() {
    if (!chatDraft.trim()) return;
    void send(chatDraft);
  }

  return (
    <section className="card chat">
      {lastError && <div className="callout danger">{lastError}</div>}
      <ChatThread
        messages={chatMessages}
        stream={chatStream}
        streamStartedAt={chatStreamStartedAt}
        toolMessages={chatToolMessages}
        showThinking={showThinking}
        loading={chatLoading}
        assistantName="Aurelia"
      />
      <ChatInput
        value={chatDraft}
        onChange={(v) => useStore.getState().setChatDraft(v)}
        onSend={handleSend}
        onAbort={abort}
        disabled={!connected}
        sending={chatSending}
        canAbort={chatSending}
      />
    </section>
  );
}
