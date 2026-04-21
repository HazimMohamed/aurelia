import { html, nothing } from "lit";
import { unsafeHTML } from "lit/directives/unsafe-html.js";
import type { AssistantIdentity } from "../assistant-identity.ts";
import type { MessageGroup } from "../types/chat-types.ts";
import { toSanitizedMarkdownHtml } from "../markdown.ts";
import { detectTextDirection } from "../text-direction.ts";
import { renderCopyAsMarkdownButton } from "./copy-as-markdown.ts";
import {
  extractTextCached,
  extractThinkingCached,
  formatReasoningMarkdown,
} from "./message-extract.ts";
import { isThoughtRole, normalizeRoleForGrouping } from "./message-normalizer.ts";
import { extractToolCards, renderToolCardSidebar } from "./tool-cards.ts";

type ImageBlock = {
  url: string;
  alt?: string;
};

function extractImages(message: unknown): ImageBlock[] {
  const m = message as Record<string, unknown>;
  const content = m.content;
  const images: ImageBlock[] = [];

  if (Array.isArray(content)) {
    for (const block of content) {
      if (typeof block !== "object" || block === null) {
        continue;
      }
      const b = block as Record<string, unknown>;

      if (b.type === "image") {
        // Handle source object format (from sendChatMessage)
        const source = b.source as Record<string, unknown> | undefined;
        if (source?.type === "base64" && typeof source.data === "string") {
          const data = source.data;
          const mediaType = (source.media_type as string) || "image/png";
          // If data is already a data URL, use it directly
          const url = data.startsWith("data:") ? data : `data:${mediaType};base64,${data}`;
          images.push({ url });
        } else if (typeof b.url === "string") {
          images.push({ url: b.url });
        }
      } else if (b.type === "image_url") {
        // OpenAI format
        const imageUrl = b.image_url as Record<string, unknown> | undefined;
        if (typeof imageUrl?.url === "string") {
          images.push({ url: imageUrl.url });
        }
      }
    }
  }

  return images;
}

export function renderReadingIndicatorGroup(assistant?: AssistantIdentity) {
  return html`
    <div class="chat-group assistant" data-entity="ai">
      ${renderAvatar("assistant", assistant)}
      <div class="chat-group-messages">
        <div class="chat-bubble chat-reading-indicator" aria-hidden="true">
          <span class="chat-reading-indicator__dots">
            <span></span><span></span><span></span>
          </span>
        </div>
      </div>
    </div>
  `;
}

export function renderStreamingGroup(
  text: string,
  startedAt: number,
  opts?: {
    isToolExpanded?: (key: string) => boolean;
    onToolExpandedChange?: (key: string, expanded: boolean) => void;
  },
  assistant?: AssistantIdentity,
) {
  const timestamp = new Date(startedAt).toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
  });

  return html`
    <div class="chat-group assistant" data-entity="ai">
      ${renderAvatar("assistant", assistant)}
      <div class="chat-group-messages">
        ${renderGroupedMessage(
          {
            role: "assistant",
            content: [{ type: "text", text }],
            timestamp: startedAt,
          },
          { isStreaming: true, showReasoning: false },
          opts,
        )}
        <div class="chat-group-footer">
          <span class="chat-group-timestamp">${timestamp}</span>
        </div>
      </div>
    </div>
  `;
}

export function renderMessageGroup(
  group: MessageGroup,
  opts: {
    isToolExpanded?: (key: string) => boolean;
    onToolExpandedChange?: (key: string, expanded: boolean) => void;
    showReasoning: boolean;
    assistantName?: string;
    assistantAvatar?: string | null;
  },
) {
  const normalizedRole = normalizeRoleForGrouping(group.role);
  const isThought = normalizedRole === "thought";
  const assistantName = opts.assistantName ?? "Assistant";
  const entity = normalizedRole === "user" ? "human" : "ai";
  const toolOnlyGroup =
    !isThought &&
    group.messages.length > 0 &&
    group.messages.every((entry) => isToolOnlyMessage(entry.message));

  if (isThought) {
    return html`
      <div class="chat-group thought" data-entity="ai">
        <div class="chat-group-messages">
          ${group.messages.map((item) => renderThoughtMessage(item.message))}
        </div>
      </div>
    `;
  }

  if (toolOnlyGroup) {
    return html`
      <div class="chat-group tool-only" data-entity="ai">
        <div class="chat-group-messages">
          ${group.messages.map((item, index) =>
            renderGroupedMessage(
              item.message,
              {
                isStreaming: group.isStreaming && index === group.messages.length - 1,
                showReasoning: opts.showReasoning,
              },
              opts,
            ),
          )}
        </div>
      </div>
    `;
  }

  const roleClass =
    normalizedRole === "user" ? "user" : normalizedRole === "assistant" ? "assistant" : "other";
  const timestamp = new Date(group.timestamp).toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
  });

  return html`
    <div class="chat-group ${roleClass}" data-entity="${entity}">
      ${renderAvatar(group.role, {
        name: assistantName,
        avatar: opts.assistantAvatar ?? null,
      })}
      <div class="chat-group-messages">
        ${group.messages.map((item, index) =>
          renderGroupedMessage(
            item.message,
            {
              isStreaming: group.isStreaming && index === group.messages.length - 1,
              showReasoning: opts.showReasoning,
            },
            opts,
          ),
        )}
        <div class="chat-group-footer">
          <span class="chat-group-timestamp">${timestamp}</span>
        </div>
      </div>
    </div>
  `;
}

function renderThoughtMessage(message: unknown) {
  const extractedText = extractTextCached(message);
  const extractedThinking = extractThinkingCached(message);
  const markdown = extractedText?.trim() ? extractedText : null;
  const thinkingMarkdown = extractedThinking ? formatReasoningMarkdown(extractedThinking) : null;
  const content = thinkingMarkdown ?? markdown;

  if (!content) {
    return nothing;
  }

  return html`<div class="chat-text chat-text--thinking chat-thought-line" dir="${detectTextDirection(content)}">${unsafeHTML(
    toSanitizedMarkdownHtml(content),
  )}</div>`;
}

function renderAvatar(role: string, assistant?: Pick<AssistantIdentity, "name" | "avatar">) {
  const normalized = normalizeRoleForGrouping(role);
  const assistantName = assistant?.name?.trim() || "Assistant";
  const assistantAvatar = assistant?.avatar?.trim() || "";
  const initial =
    normalized === "user"
      ? "U"
      : normalized === "assistant"
        ? assistantName.charAt(0).toUpperCase() || "A"
        : normalized === "tool"
          ? "⚙"
          : "?";
  const className =
    normalized === "user"
      ? "user"
      : normalized === "assistant"
        ? "assistant"
        : normalized === "tool"
          ? "tool"
          : "other";

  if (assistantAvatar && normalized === "assistant") {
    if (isAvatarUrl(assistantAvatar)) {
      return html`<img
        class="chat-avatar ${className}"
        src="${assistantAvatar}"
        alt="${assistantName}"
      />`;
    }
    return html`<div class="chat-avatar ${className}">${assistantAvatar}</div>`;
  }

  return html`<div class="chat-avatar ${className}">${initial}</div>`;
}

function isAvatarUrl(value: string): boolean {
  return (
    /^https?:\/\//i.test(value) || /^data:image\//i.test(value) || value.startsWith("/") // Relative paths from avatar endpoint
  );
}

function renderMessageImages(images: ImageBlock[]) {
  if (images.length === 0) {
    return nothing;
  }

  return html`
    <div class="chat-message-images">
      ${images.map(
        (img) => html`
          <img
            src=${img.url}
            alt=${img.alt ?? "Attached image"}
            class="chat-message-image"
            @click=${() => window.open(img.url, "_blank")}
          />
        `,
      )}
    </div>
  `;
}

function renderGroupedMessage(
  message: unknown,
  opts: { isStreaming: boolean; showReasoning: boolean },
  toolState?: {
    isToolExpanded?: (key: string) => boolean;
    onToolExpandedChange?: (key: string, expanded: boolean) => void;
  },
) {
  const m = message as Record<string, unknown>;
  const role = typeof m.role === "string" ? m.role : "unknown";
  const thoughtRole = isThoughtRole(role);

  const toolCards = extractToolCards(message);
  const hasToolCards = toolCards.length > 0;
  const images = extractImages(message);
  const hasImages = images.length > 0;

  const extractedText = extractTextCached(message);
  const extractedThinking =
    thoughtRole || role === "assistant" ? extractThinkingCached(message) : null;
  const markdown = extractedText?.trim() ? extractedText : null;
  const thinkingMarkdown = extractedThinking ? formatReasoningMarkdown(extractedThinking) : null;
  const canCopyMarkdown = role === "assistant" && Boolean(markdown?.trim());

  const bubbleClasses = [
    "chat-bubble",
    canCopyMarkdown ? "has-copy" : "",
    opts.isStreaming ? "streaming" : "",
    "fade-in",
  ]
    .filter(Boolean)
    .join(" ");

  if (hasToolCards) {
    return html`
      <div class="chat-tool-list">
        ${toolCards.map((card) =>
          renderToolCardSidebar(card, {
            expanded: toolState?.isToolExpanded?.(card.key),
            onExpandedChange: toolState?.onToolExpandedChange,
          }),
        )}
      </div>
    `;
  }

  if (!markdown && !thinkingMarkdown && !hasImages) {
    return nothing;
  }

  return html`
    <div class="${bubbleClasses}">
      ${canCopyMarkdown ? renderCopyAsMarkdownButton(markdown!) : nothing}
      ${renderMessageImages(images)}
      ${
        thinkingMarkdown
          ? html`<div class="chat-text chat-text--thinking" dir="${detectTextDirection(thinkingMarkdown)}">${unsafeHTML(
              toSanitizedMarkdownHtml(thinkingMarkdown),
            )}</div>`
          : nothing
      }
      ${
        markdown
          ? html`<div class="chat-text" dir="${detectTextDirection(markdown)}">${unsafeHTML(toSanitizedMarkdownHtml(markdown))}</div>`
          : nothing
      }
    </div>
  `;
}

function isToolOnlyMessage(message: unknown): boolean {
  const m = message as Record<string, unknown>;
  const role = typeof m.role === "string" ? m.role.toLowerCase() : "";
  if (role === "toolresult" || role === "tool_result" || role === "tool") {
    return true;
  }
  if (typeof m.toolCallId === "string" || typeof m.tool_call_id === "string") {
    return true;
  }

  const content = m.content;
  if (!Array.isArray(content)) {
    return false;
  }

  let hasToolBlock = false;
  let hasPlainTextBlock = false;
  for (const item of content) {
    if (!item || typeof item !== "object") {
      continue;
    }
    const block = item as Record<string, unknown>;
    const type = (typeof block.type === "string" ? block.type : "").toLowerCase();
    if (
      type === "toolcall" ||
      type === "tool_call" ||
      type === "tooluse" ||
      type === "tool_use" ||
      type === "toolresult" ||
      type === "tool_result"
    ) {
      hasToolBlock = true;
      continue;
    }
    if (type === "text" && typeof block.text === "string" && block.text.trim()) {
      hasPlainTextBlock = true;
    }
  }

  return hasToolBlock && !hasPlainTextBlock;
}
