import { describe, expect, it } from "vitest";
import { mountApp, registerAppMountHooks } from "./test-helpers/app-mount.ts";

registerAppMountHooks();

describe("chat markdown rendering", () => {
  it("renders folded tool output with expandable full text", async () => {
    const app = mountApp("/chat");
    await app.updateComplete;

    app.settings = { ...app.settings, chatShowThinking: true };

    const timestamp = Date.now();
    app.chatMessages = [
      {
        role: "assistant",
        content: [
          { type: "toolcall", name: "noop", arguments: {} },
          { type: "toolresult", name: "noop", text: "Hello **world**" },
        ],
        timestamp,
      },
    ];

    await app.updateComplete;

    const toolCard = app.querySelector<HTMLElement>(".chat-tool-card");
    expect(toolCard).not.toBeNull();

    // Output should be visible inline or in field
    const summary = toolCard?.querySelector<HTMLElement>(".chat-tool-card__summary");
    expect(summary?.textContent).toContain("Hello **world**");

    const details = toolCard as HTMLDetailsElement;
    details.open = true;
    details.dispatchEvent(new Event("toggle"));

    await app.updateComplete;

    const output = toolCard?.querySelector<HTMLElement>(".chat-tool-card__output");
    expect(output?.textContent).toContain("Hello **world**");
  });

  it("toggles tool output expansion on summary click", async () => {
    const app = mountApp("/chat");
    await app.updateComplete;

    const timestamp = Date.now();
    const longOutput = "x".repeat(360);
    app.chatMessages = [
      {
        role: "assistant",
        content: [
          { type: "toolcall", name: "noop", arguments: {} },
          { type: "toolresult", name: "noop", text: longOutput },
        ],
        timestamp,
      },
    ];

    await app.updateComplete;

    const details = app.querySelector<HTMLDetailsElement>(".chat-tool-card");
    const summary = details?.querySelector<HTMLElement>(".chat-tool-card__summary");
    expect(details).not.toBeNull();
    expect(summary).not.toBeNull();

    expect(details?.open).toBe(false);
    summary?.click();
    await app.updateComplete;
    expect(details?.open).toBe(true);

    summary?.click();
    await app.updateComplete;
    expect(details?.open).toBe(false);
  });

  it("hides tool result output from history when thinking is off", async () => {
    const app = mountApp("/chat");
    await app.updateComplete;

    app.settings = { ...app.settings, chatShowThinking: false };
    await app.updateComplete;

    const timestamp = Date.now();
    app.chatMessages = [
      {
        role: "assistant",
        content: [
          { type: "toolCall", id: "exec:1", name: "exec", arguments: { command: "echo hi" } },
        ],
        timestamp,
      },
      {
        role: "toolResult",
        toolCallId: "exec:1",
        toolName: "exec",
        content: [{ type: "text", text: "hi" }],
        timestamp: timestamp + 1,
      },
    ];

    await app.updateComplete;

    const cards = Array.from(app.querySelectorAll<HTMLElement>(".chat-tool-card"));
    expect(cards.length).toBe(0);
  });

  it("shows tool result output from history when thinking is on", async () => {
    const app = mountApp("/chat");
    await app.updateComplete;

    app.settings = { ...app.settings, chatShowThinking: true };
    await app.updateComplete;

    const timestamp = Date.now();
    app.chatMessages = [
      {
        role: "assistant",
        content: [
          { type: "toolCall", id: "exec:1", name: "exec", arguments: { command: "echo hi" } },
        ],
        timestamp,
      },
      {
        role: "toolResult",
        toolCallId: "exec:1",
        toolName: "exec",
        content: [{ type: "text", text: "hi" }],
        timestamp: timestamp + 1,
      },
    ];

    await app.updateComplete;

    const cards = Array.from(app.querySelectorAll<HTMLElement>(".chat-tool-card"));
    expect(cards.length).toBeGreaterThanOrEqual(1);
  });

  it("renders thought messages as free-floating text", async () => {
    const app = mountApp("/chat");
    await app.updateComplete;

    const timestamp = Date.now();
    app.chatMessages = [
      {
        role: "thought",
        content: [
          {
            type: "thinking",
            thinking: "This is a thought block.",
          },
        ],
        timestamp,
      },
    ];

    await app.updateComplete;

    const thoughtLine = app.querySelector<HTMLElement>(".chat-thought-line");
    expect(thoughtLine?.textContent).toContain("This is a thought block.");
    const thoughtBubble = thoughtLine?.closest(".chat-bubble");
    expect(thoughtBubble).toBeNull();
  });
});
