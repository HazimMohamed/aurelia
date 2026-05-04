import { useRef, useCallback } from "react";
import { useStore } from "../store";
import { streamMessage, fetchTranscript } from "../lib/api";

const CHARS_PER_FRAME = 1;

export function useChat() {
  const abortRef = useRef<AbortController | null>(null);
  const pendingBuffer = useRef("");
  const displayedStream = useRef("");
  const rafRef = useRef<number | null>(null);
  const onDrainComplete = useRef<(() => void) | null>(null);

  // Stable ref to the drain loop so it can recurse via the ref
  const drainRef = useRef<() => void>(null!);
  drainRef.current = function drain() {
    if (pendingBuffer.current.length > 0) {
      const take = Math.min(CHARS_PER_FRAME, pendingBuffer.current.length);
      const chunk = pendingBuffer.current.slice(0, take);
      pendingBuffer.current = pendingBuffer.current.slice(take);
      displayedStream.current += chunk;
      useStore.setState({ chatStream: displayedStream.current });
    }

    if (pendingBuffer.current.length === 0 && onDrainComplete.current) {
      onDrainComplete.current();
      onDrainComplete.current = null;
      rafRef.current = null;
      return;
    }

    rafRef.current = requestAnimationFrame(drainRef.current);
  };

  function resetDrain() {
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    pendingBuffer.current = "";
    displayedStream.current = "";
    onDrainComplete.current = null;
  }

  function pushChars(text: string) {
    pendingBuffer.current += text;
    if (rafRef.current === null) {
      rafRef.current = requestAnimationFrame(drainRef.current);
    }
  }

  const loadHistory = useCallback(async () => {
    const { selectedAgentId, selectedIncarnationId, setChatMessages, setChatLoading } =
      useStore.getState();
    if (!selectedAgentId || !selectedIncarnationId) {
      setChatMessages([]);
      return;
    }
    setChatLoading(true);
    try {
      const { entries } = await fetchTranscript(selectedAgentId, selectedIncarnationId);
      const messages: unknown[] = [];

      // Collect tool_call/tool_result entries keyed by cycle, emit them as a
      // single assistant message with tool_use + tool_result content items so
      // ChatBubble.extractToolCards can render them.
      const pendingTools = new Map<number, { uses: unknown[]; results: unknown[]; ts: number }>();

      function flushTools(cycle: number) {
        const bucket = pendingTools.get(cycle);
        if (!bucket) return;
        const content = [...bucket.uses, ...bucket.results];
        if (content.length) messages.push({ role: "assistant", content, timestamp: bucket.ts });
        pendingTools.delete(cycle);
      }

      for (const entry of entries) {
        const ts = entry.ts ? new Date(entry.ts as string).getTime() : Date.now();
        const cycle = (entry.cycle as number) ?? 0;

        if (entry.type === "tool_call") {
          if (!pendingTools.has(cycle)) pendingTools.set(cycle, { uses: [], results: [], ts });
          pendingTools.get(cycle)!.uses.push({
            type: "tool_use",
            id: entry.tool_use_id,
            name: entry.tool_name,
            input: entry.tool_input,
          });
        } else if (entry.type === "tool_result") {
          if (!pendingTools.has(cycle)) pendingTools.set(cycle, { uses: [], results: [], ts });
          pendingTools.get(cycle)!.results.push({
            type: "tool_result",
            tool_use_id: entry.tool_use_id,
            result: entry.result,
          });
        } else if (entry.type === "human_message" && entry.content) {
          flushTools(cycle);
          messages.push({
            role: "user",
            content: [{ type: "text", text: entry.content }],
            timestamp: ts,
          });
        } else if (entry.type === "assistant_message" && entry.content) {
          flushTools(cycle);
          const thinkingBlocks = (entry.thinking_blocks as Array<{ thinking: string }> | undefined) ?? [];
          const content: unknown[] = [];
          for (const tb of thinkingBlocks) content.push({ type: "thinking", thinking: tb.thinking });
          content.push({ type: "text", text: entry.content });
          messages.push({ role: "assistant", content, timestamp: ts });
        }
      }

      // Flush any trailing tool entries
      for (const cycle of pendingTools.keys()) flushTools(cycle);

      setChatMessages(messages as Parameters<typeof setChatMessages>[0]);
    } catch (err) {
      useStore.setState({ lastError: String(err), chatMessages: [] });
    } finally {
      setChatLoading(false);
    }
  }, []);

  const send = useCallback(async (message: string) => {
    const { selectedAgentId, selectedIncarnationId } = useStore.getState();
    if (!selectedAgentId || !message.trim()) return;

    resetDrain();

    const now = Date.now();
    useStore.setState((s) => ({
      chatMessages: [
        ...s.chatMessages,
        { role: "user", content: [{ type: "text", text: message }], timestamp: now },
      ],
      chatToolMessages: [],
      chatSending: true,
      chatStream: "",
      chatStreamStartedAt: now,
      chatDraft: "",
    }));

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    let textAcc = "";
    let thinkingAcc = "";
    let committed = false;

    try {
      for await (const { event, data } of streamMessage(
        selectedAgentId,
        message,
        selectedIncarnationId,
        controller.signal,
      )) {
        if (controller.signal.aborted) break;

        if (event === "content_block_delta") {
          const delta = data.delta as Record<string, unknown> | undefined;
          if (delta?.type === "text_delta" && typeof delta.text === "string") {
            textAcc += delta.text;
            pushChars(delta.text);
          } else if (delta?.type === "thinking_delta" && typeof delta.thinking === "string") {
            thinkingAcc += delta.thinking;
          }
        } else if (event === "tool_use") {
          const id = String(data.id ?? "");
          useStore.setState((s) => ({
            chatToolMessages: [
              ...s.chatToolMessages,
              { type: "tool_use", tool_use_id: id, name: data.name, input: data.input, running: true },
            ],
          }));
        } else if (event === "tool_result") {
          const id = String(data.tool_use_id ?? "");
          useStore.setState((s) => ({
            chatToolMessages: s.chatToolMessages.map((m) =>
              m.tool_use_id === id ? { ...m, result: data.result, running: false } : m,
            ),
          }));
        } else if (event === "message_stop") {
          committed = true;
          const content: unknown[] = [];
          if (thinkingAcc) content.push({ type: "thinking", thinking: thinkingAcc });
          content.push({ type: "text", text: textAcc });

          const doCommit = () => {
            useStore.setState((s) => ({
              chatMessages: [
                ...s.chatMessages,
                { role: "assistant", content, timestamp: Date.now() },
              ],
              chatStream: null,
              chatStreamStartedAt: null,
            }));
          };

          if (pendingBuffer.current.length === 0) {
            doCommit();
          } else {
            onDrainComplete.current = doCommit;
          }
          break;
        } else if (event === "error") {
          throw new Error(String(data.message ?? data.error ?? "Stream error"));
        }
      }

      // Stream ended without message_stop
      if (!committed && !controller.signal.aborted && textAcc) {
        const content: unknown[] = [];
        if (thinkingAcc) content.push({ type: "thinking", thinking: thinkingAcc });
        content.push({ type: "text", text: textAcc });
        onDrainComplete.current = () => {
          useStore.setState((s) => ({
            chatMessages: [
              ...s.chatMessages,
              { role: "assistant", content, timestamp: Date.now() },
            ],
          }));
        };
        if (pendingBuffer.current.length === 0) {
          onDrainComplete.current();
          onDrainComplete.current = null;
        }
      }
    } catch (err) {
      resetDrain();
      if (!controller.signal.aborted) {
        const raw = String(err);
        const friendly = raw.includes("503") || raw.includes("overloaded")
          ? "Anthropic API is overloaded — please retry in a moment."
          : raw.includes("429") || raw.includes("rate")
            ? "Rate limited by Anthropic API — please wait before retrying."
            : raw;
        useStore.setState((s) => ({
          chatMessages: [
            ...s.chatMessages,
            { role: "assistant", content: [{ type: "text", text: friendly }], timestamp: Date.now() },
          ],
          lastError: friendly,
        }));
      }
    } finally {
      useStore.setState({ chatSending: false });
    }
  }, []);

  const abort = useCallback(() => {
    abortRef.current?.abort();
    resetDrain();
    useStore.setState({ chatSending: false, chatStream: null, chatStreamStartedAt: null });
  }, []);

  return { send, abort, loadHistory };
}
