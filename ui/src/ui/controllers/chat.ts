import type { ChatAttachment } from "../ui-types.ts";
import { fetchHistory, fetchTranscript, sendMessage } from "../aurelia-client.ts";
import { generateUUID } from "../uuid.ts";

export type ChatState = {
  sessionKey: string;
  activeSessionId: string | null;
  chatLoading: boolean;
  chatMessages: unknown[];
  chatThinkingLevel: string | null;
  chatSending: boolean;
  chatMessage: string;
  chatAttachments: ChatAttachment[];
  chatRunId: string | null;
  chatStream: string | null;
  chatStreamStartedAt: number | null;
  lastError: string | null;
};

export type ChatEventPayload = {
  runId: string;
  sessionKey: string;
  sessionId?: string;
  state: "delta" | "final" | "aborted" | "error";
  message?: unknown;
  errorMessage?: string;
};

// Resolve agent name from sessionKey (e.g. "main" -> "main")
function resolveAgent(sessionKey: string): string {
  const parts = sessionKey.split(":");
  return parts[parts.length - 1] || "main";
}

export async function loadChatHistory(state: ChatState) {
  state.chatLoading = true;
  state.lastError = null;
  try {
    const agent = resolveAgent(state.sessionKey);
    // Fetch the most recent incarnation's transcript
    const incarnations = await fetchHistory(agent);
    if (!Array.isArray(incarnations) || incarnations.length === 0) {
      state.chatMessages = [];
      return;
    }
    const latest = incarnations[incarnations.length - 1] as { incarnation?: number } | number;
    const incarnationNum = typeof latest === "number" ? latest : (latest?.incarnation ?? 1);
    const transcript = await fetchTranscript(agent, incarnationNum);
    state.chatMessages = transcript.map((entry) => ({
      role: entry.role,
      content: [{ type: "text", text: entry.content }],
      timestamp: entry.timestamp ? new Date(entry.timestamp).getTime() : Date.now(),
    }));
  } catch (err) {
    state.lastError = String(err);
    state.chatMessages = [];
  } finally {
    state.chatLoading = false;
  }
}

export async function sendChatMessage(
  state: ChatState,
  message: string,
  _attachments?: ChatAttachment[],
): Promise<string | null> {
  const msg = message.trim();
  if (!msg) {
    return null;
  }

  const now = Date.now();
  const runId = generateUUID();

  // Optimistically add user message
  state.chatMessages = [
    ...state.chatMessages,
    {
      role: "user",
      content: [{ type: "text", text: msg }],
      timestamp: now,
    },
  ];

  state.chatSending = true;
  state.lastError = null;
  state.chatRunId = runId;
  state.chatStream = "";
  state.chatStreamStartedAt = now;

  try {
    const agent = resolveAgent(state.sessionKey);
    const result = await sendMessage(agent, msg);
    state.chatMessages = [
      ...state.chatMessages,
      {
        role: "assistant",
        content: [{ type: "text", text: result.content }],
        timestamp: Date.now(),
      },
    ];
    state.chatStream = null;
    state.chatRunId = null;
    state.chatStreamStartedAt = null;
    return runId;
  } catch (err) {
    const error = String(err);
    state.chatRunId = null;
    state.chatStream = null;
    state.chatStreamStartedAt = null;
    state.lastError = error;
    state.chatMessages = [
      ...state.chatMessages,
      {
        role: "assistant",
        content: [{ type: "text", text: "Error: " + error }],
        timestamp: Date.now(),
      },
    ];
    return null;
  } finally {
    state.chatSending = false;
  }
}

export async function abortChatRun(state: ChatState): Promise<boolean> {
  state.chatRunId = null;
  state.chatStream = null;
  state.chatStreamStartedAt = null;
  return true;
}

export function handleChatEvent(_state: ChatState, _payload?: ChatEventPayload) {
  // No WebSocket events in Aurelia — polling only
  return null;
}
