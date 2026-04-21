import { html, nothing } from "lit";
import type { ToolCard } from "../types/chat-types.ts";
import { icons } from "../icons.ts";
import { resolveToolDisplay } from "../tool-display.ts";
import { extractTextCached } from "./message-extract.ts";
import { isToolResultMessage } from "./message-normalizer.ts";
import { isTruncatedByPreview } from "./tool-helpers.ts";

export function extractToolCards(message: unknown): ToolCard[] {
  const m = message as Record<string, unknown>;
  const content = normalizeContent(m.content);
  const cards: ToolCard[] = [];
  const cardsByKey = new Map<string, ToolCard>();
  const pendingByName = new Map<string, ToolCard[]>();

  for (let index = 0; index < content.length; index++) {
    const item = content[index];
    const kind = (typeof item.type === "string" ? item.type : "").toLowerCase();
    const isToolCall =
      ["toolcall", "tool_call", "tooluse", "tool_use"].includes(kind) ||
      (typeof item.name === "string" && item.arguments != null);
    if (isToolCall) {
      const name = (item.name as string) ?? "tool";
      const key = resolveCardKey(m, item, name, index);
      const existing = cardsByKey.get(key);
      const args = coerceArgs(item.arguments ?? item.args);
      if (existing) {
        existing.args = args;
      } else {
        const card: ToolCard = { key, name, args };
        cards.push(card);
        cardsByKey.set(key, card);
        const pending = pendingByName.get(name) ?? [];
        pending.push(card);
        pendingByName.set(name, pending);
      }
    }
  }

  for (let index = 0; index < content.length; index++) {
    const item = content[index];
    const kind = (typeof item.type === "string" ? item.type : "").toLowerCase();
    if (kind !== "toolresult" && kind !== "tool_result") {
      continue;
    }
    const output = extractToolText(item);
    const name = typeof item.name === "string" ? item.name : "tool";
    const key = resolveCardKey(m, item, name, index);
    const existing = cardsByKey.get(key);
    if (existing) {
      existing.output = output;
      continue;
    }

    const pending = pendingByName.get(name) ?? [];
    const pendingCard = pending.find((card) => !card.output);
    if (pendingCard) {
      pendingCard.output = output;
      continue;
    }

    const card: ToolCard = {
      key,
      name,
      output,
    };
    cards.push(card);
    cardsByKey.set(key, card);
  }

  const hasToolMarkers =
    isToolResultMessage(message) ||
    typeof m.toolCallId === "string" ||
    typeof m.tool_call_id === "string" ||
    typeof m.toolName === "string" ||
    typeof m.tool_name === "string";

  if (hasToolMarkers && cards.length === 0) {
    const name =
      (typeof m.toolName === "string" && m.toolName) ||
      (typeof m.tool_name === "string" && m.tool_name) ||
      "tool";
    const output = extractTextCached(message) ?? undefined;
    cards.push({
      key: resolveCardKey(m, m, name, cards.length),
      name,
      output,
      args: coerceArgs(m.arguments ?? m.args),
    });
  }

  return cards;
}

export function renderToolCardSidebar(
  card: ToolCard,
  opts?: {
    expanded?: boolean;
    onExpandedChange?: (key: string, expanded: boolean) => void;
  },
) {
  const display = resolveToolDisplay({ name: card.name, args: card.args });
  const hasOutput = Boolean(card.output?.trim());
  const output = card.output ?? "";
  const outputTruncated = hasOutput ? isTruncatedByPreview(output) : false;
  const canExpand = hasOutput && outputTruncated;
  const isExpanded = Boolean(canExpand && opts?.expanded);

  const compactInput = formatToolInputCompact(card.args);

  return html`
    <details
      class="chat-tool-card"
      ?open=${isExpanded}
      @toggle=${
        canExpand
          ? (event: Event) => {
              const target = event.currentTarget as HTMLDetailsElement | null;
              opts?.onExpandedChange?.(card.key, Boolean(target?.open));
            }
          : nothing
      }
    >
      <summary class="chat-tool-card__summary ${canExpand ? "" : "chat-tool-card__summary--static"}">
        <span class="chat-tool-card__icon">${icons[display.icon]}</span>
        <span class="chat-tool-card__name">${display.label}</span>
        <span class="chat-tool-card__status">${icons.check}</span>
        <code class="chat-tool-card__input mono">${compactInput}</code>
      </summary>
      ${
        canExpand
          ? html`
              <div class="chat-tool-card__expanded">
                <table class="chat-tool-card__table">
                  <tr>
                    <td class="chat-tool-card__label">Tool</td>
                    <td class="chat-tool-card__value">${card.name}</td>
                  </tr>
                  ${
                    card.args != null
                      ? html`
                    <tr>
                      <td class="chat-tool-card__label">Input</td>
                      <td class="chat-tool-card__value">
                        <div class="chat-tool-card__value-row">
                          <pre class="chat-tool-card__pre mono">${formatArgsForTable(card.args)}</pre>
                          <button class="chat-tool-card__copy" title="Copy" @click=${() => copyToClipboard(formatArgsForTable(card.args))}>${icons.copy}</button>
                        </div>
                      </td>
                    </tr>
                  `
                      : nothing
                  }
                  <tr>
                    <td class="chat-tool-card__label">Output</td>
                    <td class="chat-tool-card__value">
                      <div class="chat-tool-card__value-row">
                        <pre class="chat-tool-card__pre mono">${output}</pre>
                        <button class="chat-tool-card__copy" title="Copy" @click=${() => copyToClipboard(output)}>${icons.copy}</button>
                      </div>
                    </td>
                  </tr>
                </table>
              </div>
            `
          : nothing
      }
    </details>
  `;
}

function normalizeContent(content: unknown): Array<Record<string, unknown>> {
  if (!Array.isArray(content)) {
    return [];
  }
  return content.filter(Boolean) as Array<Record<string, unknown>>;
}

function coerceArgs(value: unknown): unknown {
  if (typeof value !== "string") {
    return value;
  }
  const trimmed = value.trim();
  if (!trimmed) {
    return value;
  }
  if (!trimmed.startsWith("{") && !trimmed.startsWith("[")) {
    return value;
  }
  try {
    return JSON.parse(trimmed);
  } catch {
    return value;
  }
}

function formatToolInputCompact(args: unknown): string {
  if (args === undefined) {
    return "{}";
  }
  if (typeof args === "string") {
    const trimmed = args.trim();
    return trimmed.length > 80 ? trimmed.slice(0, 77) + "…" : trimmed;
  }
  try {
    const json = JSON.stringify(args);
    return json.length > 80 ? json.slice(0, 77) + "…" : json;
  } catch {
    return "[args]";
  }
}

function formatArgsForTable(args: unknown): string {
  if (args === undefined || args === null) {
    return "—";
  }
  if (typeof args === "string") {
    return args.trim() || "—";
  }
  try {
    return JSON.stringify(args, null, 2);
  } catch {
    return "[args]";
  }
}

function copyToClipboard(text: string): void {
  navigator.clipboard.writeText(text).catch(() => {
    // Fallback for older browsers
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand("copy");
    document.body.removeChild(textarea);
  });
}

function resolveCardKey(
  message: Record<string, unknown>,
  item: Record<string, unknown>,
  name: string,
  index: number,
): string {
  const itemCallId = getCallId(item);
  if (itemCallId) {
    return itemCallId;
  }
  const messageCallId = getCallId(message);
  if (messageCallId) {
    return messageCallId;
  }
  const timestamp = typeof message.timestamp === "number" ? message.timestamp : "na";
  return `${name}:${timestamp}:${index}`;
}

function getCallId(value: Record<string, unknown>): string | null {
  const raw =
    value.toolCallId ?? value.tool_call_id ?? value.callId ?? value.call_id ?? value.id ?? null;
  return typeof raw === "string" && raw.trim() ? raw : null;
}

function extractToolText(item: Record<string, unknown>): string | undefined {
  if (typeof item.text === "string") {
    return item.text;
  }
  if (typeof item.content === "string") {
    return item.content;
  }
  if (Array.isArray(item.content)) {
    const parts = item.content
      .map((entry) => {
        if (!entry || typeof entry !== "object") {
          return null;
        }
        const block = entry as Record<string, unknown>;
        return typeof block.text === "string" ? block.text : null;
      })
      .filter((value): value is string => typeof value === "string");
    if (parts.length > 0) {
      return parts.join("\n");
    }
  }
  const details =
    item.details && typeof item.details === "object"
      ? (item.details as Record<string, unknown>)
      : null;
  if (details && typeof details.aggregated === "string") {
    return details.aggregated;
  }
  return undefined;
}
