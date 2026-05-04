import { stripThinkingTags } from "../format.ts";

function stripEnvelope(text: string): string {
  return text.replace(/^<\|[^|]*\|>/g, "").trim();
}

const textCache = new WeakMap<object, string | null>();
const thinkingCache = new WeakMap<object, string | null>();

export function extractText(message: unknown): string | null {
  const m = message as Record<string, unknown>;
  const role = typeof m.role === "string" ? m.role : "";
  const content = m.content;
  if (typeof content === "string") {
    return role === "assistant" ? stripThinkingTags(content) : stripEnvelope(content);
  }
  if (Array.isArray(content)) {
    const parts = content
      .map((p) => {
        const item = p as Record<string, unknown>;
        return item.type === "text" && typeof item.text === "string" ? item.text : null;
      })
      .filter((v): v is string => typeof v === "string");
    if (parts.length > 0) {
      const joined = parts.join("\n");
      return role === "assistant" ? stripThinkingTags(joined) : stripEnvelope(joined);
    }
  }
  if (typeof m.text === "string") {
    return role === "assistant" ? stripThinkingTags(m.text) : stripEnvelope(m.text);
  }
  return null;
}

export function extractTextCached(message: unknown): string | null {
  if (!message || typeof message !== "object") return extractText(message);
  if (textCache.has(message)) return textCache.get(message) ?? null;
  const value = extractText(message);
  textCache.set(message, value);
  return value;
}

export function extractRawText(message: unknown): string | null {
  const m = message as Record<string, unknown>;
  const content = m.content;
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    const parts = content
      .map((p) => {
        const item = p as Record<string, unknown>;
        return item.type === "text" && typeof item.text === "string" ? item.text : null;
      })
      .filter((v): v is string => typeof v === "string");
    if (parts.length > 0) return parts.join("\n");
  }
  if (typeof m.text === "string") return m.text;
  return null;
}

export function extractThinking(message: unknown): string | null {
  const m = message as Record<string, unknown>;
  const content = m.content;
  const parts: string[] = [];
  if (Array.isArray(content)) {
    for (const p of content) {
      const item = p as Record<string, unknown>;
      if (item.type === "thinking" && typeof item.thinking === "string") {
        const cleaned = item.thinking.trim();
        if (cleaned) parts.push(cleaned);
      }
    }
  }
  if (parts.length > 0) return parts.join("\n");

  const rawText = extractRawText(message);
  if (!rawText) return null;
  const matches = [
    ...rawText.matchAll(/<\s*think(?:ing)?\s*>([\s\S]*?)<\s*\/\s*think(?:ing)?\s*>/gi),
  ];
  const extracted = matches.map((m) => (m[1] ?? "").trim()).filter(Boolean);
  return extracted.length > 0 ? extracted.join("\n") : null;
}

export function extractThinkingCached(message: unknown): string | null {
  if (!message || typeof message !== "object") return extractThinking(message);
  if (thinkingCache.has(message)) return thinkingCache.get(message) ?? null;
  const value = extractThinking(message);
  thinkingCache.set(message, value);
  return value;
}
