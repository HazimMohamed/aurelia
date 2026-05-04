import type { NormalizedMessage, MessageContentItem } from "../types.ts";

const THOUGHT_ROLES = new Set(["thought", "thinking", "reasoning"]);

export function normalizeMessage(message: unknown): NormalizedMessage {
  const m = message as Record<string, unknown>;
  let role = typeof m.role === "string" ? m.role : "unknown";

  const hasToolId = typeof m.toolCallId === "string" || typeof m.tool_call_id === "string";
  const contentItems = Array.isArray(m.content) ? m.content : null;
  const hasToolContent =
    contentItems !== null &&
    contentItems.some((item) => {
      const x = item as Record<string, unknown>;
      const t = (typeof x.type === "string" ? x.type : "").toLowerCase();
      return t === "toolresult" || t === "tool_result";
    });
  const hasToolName = typeof m.toolName === "string" || typeof m.tool_name === "string";

  if (hasToolId || hasToolContent || hasToolName) role = "toolResult";

  let content: MessageContentItem[] = [];
  if (typeof m.content === "string") {
    content = [{ type: "text", text: m.content }];
  } else if (Array.isArray(m.content)) {
    content = m.content.map((item: Record<string, unknown>) => ({
      type: (item.type as MessageContentItem["type"]) || "text",
      text: item.text as string | undefined,
      name: item.name as string | undefined,
      args: item.args || item.arguments,
    }));
  } else if (typeof m.text === "string") {
    content = [{ type: "text", text: m.text }];
  }

  const timestamp = typeof m.timestamp === "number" ? m.timestamp : Date.now();
  const id = typeof m.id === "string" ? m.id : undefined;

  return { role, content, timestamp, id };
}

export function normalizeRoleForGrouping(role: string): string {
  if (role === "user" || role === "User") return role;
  if (role === "assistant") return "assistant";
  if (role === "system") return "system";
  const lower = role.toLowerCase();
  if (lower === "toolresult" || lower === "tool_result" || lower === "tool" || lower === "function") {
    return "tool";
  }
  if (THOUGHT_ROLES.has(lower)) return "thought";
  return role;
}

export function isThoughtRole(role: string): boolean {
  return THOUGHT_ROLES.has(role.toLowerCase());
}
