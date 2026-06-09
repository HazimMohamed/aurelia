# Handoff: Aurelia — Chat Surface

## Overview
Three explorations of the main **Chat** surface for **Aurelia** (the local-first agent gateway, formerly "OpenClaw"). The variants progressively tighten information architecture around a single conviction: the **agent → incarnation** tree is the spine of the product, and the rest of the UI exists to serve a transcript view of that tree.

- **Variant A · Compact** — a density-first refinement of the existing UI. Same DNA, tighter rhythm. Sessions rail, compact tool strips, inline meta. Safest direction.
- **Variant B · Ledger** — an editorial reimagining. Left gutter for role/time/§index/model meta. Serif (Newsreader) for assistant prose with a terracotta highlighter for emphasis. Compiler-style tool blocks. Editorial masthead.
- **Variant C · Unified** *(canonical / recommended)* — same editorial transcript as B, but with **one unified left rail** that flips between a top-level menu (Chat / Samsara / Logs) and the agent → incarnation tree via breadcrumbs. The 3-item global nav lifts off the chrome entirely.

The user iterated heavily on Variant C; treat **C as the canonical direction**. A and B are kept on the canvas for context.

## About the Design Files
The files in this bundle are **design references created in HTML/React** — prototypes showing intended look and behavior, not production code to copy directly. The task is to **recreate these HTML designs in the target codebase's existing environment** (React + your component library, Vue, SwiftUI, etc.) using its established patterns. If no environment exists yet, choose the most appropriate framework for the project and implement the designs there.

The HTML uses inline JSX via `@babel/standalone` purely for prototyping speed; do not port that pattern to production.

## Fidelity
**High-fidelity.** Pixel-perfect mockups with final colors, typography, spacing, copy, and interaction patterns. Recreate the UI pixel-perfectly using the codebase's existing libraries.

## Files
- `index.html` — Babel/React harness, font loading, root mount
- `app.jsx` — Top-level: design canvas + tweaks panel wiring
- `chat-variants.jsx` — All three variants (`ChatA`, `ChatB`, `ChatC`) and their sub-components, plus the shared `transcript` data and the `Sidebar` / `Topbar` primitives
- `design-canvas.jsx` — Canvas shell (pan/zoom, artboards) — vendor; not part of the design
- `tweaks-panel.jsx` — Tweaks panel shell — vendor; not part of the design

The "design" the developer should implement is what's in `chat-variants.jsx` (specifically the `ChatC` subtree). `app.jsx`, `design-canvas.jsx`, and `tweaks-panel.jsx` exist only to present the designs side-by-side and are not meant to be ported.

---

## Design Tokens

### Colors (warm terracotta on cream)

```css
--bg:              #f7f2eb;   /* page background, cream */
--bg-accent:       #f1ebe1;   /* slightly warmer panel background */
--bg-elevated:     #ffffff;   /* inputs, raised surfaces */
--panel:           #fbf8f3;   /* main content panel */
--panel-strong:    #f4ede2;   /* gradient end for elevated rails */

--text:            #2a2520;   /* body text */
--text-strong:     #1a1612;   /* headlines, strong emphasis */
--muted:           #6b6259;   /* secondary text */
--muted-soft:      #9c9388;   /* tertiary text, captions */

--border:          #e6dfd3;   /* hairlines */
--border-strong:   #d4c9b8;   /* dividers, dashed placeholders */

--accent:          #c9673a;   /* terracotta — primary brand color */
--accent-soft:     #d99478;   /* lighter accent, borders on accent surfaces */
--accent-subtle:   #f5e3d6;   /* tinted background for active rows */
```

The dot in "cluster ok" is `#7a9d6a` (sage green).

The agent avatar gradient is `radial-gradient(circle at 30% 30%, #e08a5f, #b95c31 70%)` on the test-agent (active) avatar. The default-agent avatar (`main`) is outlined only — `var(--bg-elevated)` background with `inset 0 0 0 1px var(--border-strong)`.

The Aurelia wordmark badge is `linear-gradient(135deg, var(--accent), #9e4e2a)`.

The user avatar in the topbar is `linear-gradient(135deg, #d49b6a, #9e4e2a)`.

### Typography

```css
--serif:  "Newsreader", "Source Serif Pro", Georgia, serif;
--body:   "Inter", -apple-system, BlinkMacSystemFont, sans-serif;
--mono:   "JetBrains Mono", "SF Mono", Consolas, monospace;
```

Newsreader is used for the masthead agent/incarnation names AND for assistant prose in the transcript — that's the deliberate "editorial" voice. JetBrains Mono is used for all meta (timestamps, ids, latency, prices), tool call lines, and section labels. Inter (body) is used for the user's own messages and for nav/labels.

Size scale (in px):
- 9.5 / 10 / 10.5 / 11 — mono meta, captions, breadcrumbs
- 11.5 / 12 / 12.5 — body small (chips, rail labels)
- 13 / 13.5 / 14 — body, user messages
- 16 — assistant prose (serif, line-height 1.55)
- 22 / 26 / 28 — masthead headlines (serif)
- 32 — coming-soon page titles

Letter-spacing:
- Mono caps labels: `.14em` to `.24em` depending on emphasis
- Serif headlines: `-.025em` (tight)
- Body: `-.005em` (almost neutral)

### Spacing
- Rail widths: **268px** expanded / **56px** collapsed
- Topbar height: **~44px** (8px vertical padding + content)
- Editorial gutter (left column of every transcript row): **118px** with a 16px right-pad and 22px left-pad on the body column
- Masthead padding: **12px 24px**
- Transcript row padding: **14px 0** vertical, content insets via columns

### Radii & shadows
- Inputs / chips: **6–8px** radius
- Pills (status, INCARNATION badge, price chip): **999px**
- Avatars: **7px** (square-rounded, not circular — the OC user dot is the exception at 50%)
- Coming-soon glyph card: **18px**
- Send button shadow: `0 1px 0 rgba(255,255,255,.18) inset, 0 3px 10px rgba(201,103,58,.28)`

---

## Screens

### Variant C · Unified (canonical)

#### Layout
```
┌─────────────────────────────────────────────────────────┐
│ Topbar                                                  │ 44px
├──────────┬──────────────────────────────────────────────┤
│          │                                              │
│ Rail     │ Main                                         │
│ 268px    │                                              │
│          │                                              │
└──────────┴──────────────────────────────────────────────┘
```

When the rail is collapsed: rail = 56px, main = 1fr.

#### Topbar
Horizontal flex, three groups (left / center / right) on a `var(--panel)` background with a `var(--border)` hairline below.

**Left group** (gap 10):
- Hamburger button — `28×28`, 7px radius, `var(--bg-elevated)` background with `var(--border)` outline. Shows `≡` when expanded, `›≡` when collapsed. Toggles the rail.
- Brand mark `A` — `22×22`, 6px radius, `linear-gradient(135deg, var(--accent), #9e4e2a)`, mono 11/700 white.
- Wordmark "Aurelia" — Newsreader 16/500, `letter-spacing: -.01em`.
- "local" pill — mono 9.5, 1px solid border, 999px radius, `.08em` tracking, muted color.

**Center**: empty (the segmented control was deliberately removed — Chat/Samsara/Logs lives in the rail).

**Right group** (gap 8):
- "● cluster ok" pill — mono 10.5, muted, 1px border, 999px radius, `#7a9d6a` dot.
- User avatar "OC" — circle 26px, gradient `#d49b6a → #9e4e2a`, mono 10.5/700 white.

#### Rail — Menu mode
This is the rail's *root* view (breadcrumb = AURELIA, current).

```
┌─────────────────────────────┐
│ AURELIA                     │  ← Crumbs, mono 10.5, .14em, current=accent
├─────────────────────────────┤
│ ┌──┐                        │
│ │💬│ Chat        transcript │  ← rows: 9px 10px, 8px radius
│ └──┘                  view  │     active: bg=accent-subtle, text-strong
│ ┌──┐                        │     icon box: 26×26, 7px radius, mono 13
│ │◉ │ Samsara      runtime   │     hint: mono 10, muted-soft, .04em
│ └──┘              status    │
│ ┌──┐                        │
│ │≡ │ Logs         live tail │
│ └──┘                        │
│                             │
├─────────────────────────────┤
│ 2 agents · 7 incarnations   │  ← footer, mono 10, muted-soft
└─────────────────────────────┘
```

#### Rail — Tree mode (view = Chat)
Breadcrumb shows `AURELIA / CHAT` with AURELIA clickable (returns to menu mode).

Below the breadcrumb: a search input (5px 9px pad, 7px radius, mono 11.5) with `⌕` glyph and "Find agent or incarnation…" placeholder.

Below search: the agent tree. Each agent is a row:
- 14px chevron column (`▾` / `▸`)
- 20×20 agent avatar (5px radius)
- name + optional `DEFAULT` badge (mono 8.5, .14em, 1px border, 4px radius, 1px 5px pad)
- right-aligned incarnation count (mono 10.5)
- font: mono 12/600, -.005em

When expanded: a vertical 1px hairline at `left: 17px` from the row's left edge, running from top:2 to bottom:8. Each incarnation row sits at `paddingLeft: 24px` and is a 3-column grid (name / msg-count / when):
- Active incarnation: `bg=accent-subtle`, text-strong, leading `●` in accent
- Inactive: transparent bg
- Name: body 12.5, -.005em
- msg count + when: mono 10, muted-soft
- 4px 8px pad, 5px radius, 1px row gap

Below each agent's expanded list: `＋ new incarnation` text-link, mono 10.5, accent color, .04em tracking. **This is the canonical "new incarnation" affordance — do not add additional new-incarnation buttons elsewhere.**

#### Rail — Tree mode (view = Samsara or Logs)
Same shell as Chat, but the body is `ComingSoonRail`:
- Row-style stubs with `6×6` muted dot + label + mono hint. Greyed (opacity .8, muted-soft).
- Samsara stubs: cluster / incarnations / queues / restarts / spend
- Logs stubs: all streams / errors / tool calls / model i/o / audit
- Below: a dashed 8px-radius "COMING SOON" plaque on `var(--bg-elevated)`, mono 10 / .18em / muted-soft / centered

Search input, `＋ new`, and the regular footer are hidden in these views. Footer text becomes `runtime · not yet wired` / `logs · not yet wired`.

#### Rail — Collapsed (56px)
Always shows the **Chat-default minimized view**, regardless of which top-level view is active:
- 30×30 chevron `›` at top to expand
- 1px 28px hairline divider
- Stack of 36×36 agent avatars (active = gradient, default = outlined)
- Bottom: 32×32 dashed `＋` for new-agent

#### Main — Chat view

**Masthead** (12px 24px, `var(--bg-accent)`, hairline below):
- Left column (flex column, gap 5):
  - Title row (wrap, gap 10):
    - 26×26 active-agent avatar (gradient)
    - `test-agent` — serif 26/500, -.025em, text-strong
    - `/` — serif italic 20, muted-soft
    - `rate-limit triage` — serif 22/500, -.02em, accent
    - `INCARNATION · 8 MSG` pill — mono 9.5, .14em, 1px border, 999px radius
  - Meta row (mono 10.5, muted, -.005em, gap 10):
    - `id sess_8af2…4c1d`
    - `model anthropic/claude-sonnet-4.5`
    - `ws /tmp/test-agent-workspace`
    - **Spent chip** — `spent $0.0427`, 2px 9px pad, 999px radius, 1px `var(--accent-soft)` border, `var(--accent-subtle)` bg, accent color, 600 weight. The "spent" word is muted-soft 500. (This replaces the old p95+sparkline+latency cluster — cumulative spend takes the prime real estate.)
- Right column (flex row, gap 6):
  - `memory` chip — mono 10.5, accent color, 1px border, 6px radius
  - `fork` chip — same shell, muted color

**Transcript** (overflow-y auto, padding `0 24px`):
- Each turn is a 2-column grid: `118px | 1fr`, top hairline (except first turn), 14px vertical padding.
- **Gutter** (right-aligned mono):
  - Role label — 9.5/.22em uppercase. `YOU` in muted, `AURELIA` in accent. 600 weight.
  - Time — mono 11
  - **For user turns only**: `§ 02` cycle marker, mono 9.5, opacity .7. Increments strictly by user turn count (1, 2, 3…), NOT by total transcript index. Assistant turns do NOT show §.
  - For assistant turns: `sonnet-4.5\n2 tools · 170ms` — mono 9.5, opacity .7, max-width 100px, right-aligned
  - For assistant turns: per-message price `$0.00xx` — mono 10/600, accent color
- **Body** (`0 24px 0 22px`):
  - Optional `THINKING` label (mono 10, .15em, accent) + italic serif 14 paragraph (muted, line-height 1.5)
  - Optional tool blocks (see `LedgerTool` in source) — `●` status dot + `$ tool(args)` mono header + `> output` lines
  - Text content:
    - User: body sans 14, -.005em
    - Assistant: serif 16, line-height 1.55, with `<mark>` emphasis in terracotta
- After the last turn, a "typing" row in the same gutter format: gutter shows `AURELIA / 10:44`, body has italic serif "reloading test-agent" + three bouncing dots.

**Composer** (`ComposerB`, hairline above):
- Textarea/input area (rendered as a styled div in the mock — replace with a real textarea)
- Inline placeholder ghost: `↩ send · ⇧↩ newline · @ mention · / commands`
- Bottom row (flex space-between):
  - Left chips: `@agent`, `/skill`, autocomplete preview of `/run`, `/diff`, `/memory`
  - Right chips:
    - `⌘K` — command palette shortcut hint. Implement a fuzzy command palette (agent/incarnation jump, action search) bound to ⌘K. If not implementing the palette, drop this chip.
    - `📎 attach` — file attachment trigger. Opens a file picker; attached files appear as chips above the composer.
    - **Send button** — `4px 14px` pad, 7px radius, `var(--accent)` background, `#fff8f2` text, mono 12.5/600 caps, .02em tracking. Label: `SEND ↵`. Shadow: `0 1px 0 rgba(255,255,255,.18) inset, 0 3px 10px rgba(201,103,58,.28)`.

#### Main — Samsara / Logs views
Hide masthead and composer entirely. Render a centered `ComingSoon` card:
- 88×88 glyph card, 18px radius, `var(--bg-accent)` bg, 1px border, accent-colored glyph (mono 38). Samsara glyph: `◉`. Logs glyph: `≡`.
- Mono 10.5, .24em uppercase muted-soft label: `SAMSARA · COMING SOON` (or `LOGS · COMING SOON`)
- Serif 32/500/-.025em text-strong title: "Runtime status" / "Live tail"
- Serif italic 15 muted blurb, max-width 460, text-wrap pretty, line-height 1.55

---

## Interactions & Behavior

### Rail navigation
- Click `AURELIA` breadcrumb → switch rail to menu mode.
- Click `Chat` / `Samsara` / `Logs` in menu mode → switch rail to tree mode (or coming-soon stub) for that view AND swap the main pane content. Selection updates the breadcrumb to `AURELIA / <view>`.
- Click hamburger in topbar → collapse rail to 56px (chat-minimized view) OR expand back. This is the **only** way to minimize the rail.
- Click chevron `›` in collapsed rail → expand. (Same effect as hamburger.)

### Agent tree
- Click agent row → toggle expanded/collapsed state for that agent.
- Click incarnation row → make it the active incarnation (updates masthead, loads transcript). Active row gets `accent-subtle` bg + leading `●`.
- Click `＋ new incarnation` → create a new incarnation under that agent (open a small inline form or modal — design decision).
- Search input → live-filters incarnations across all agents by substring match on `agent.name + " " + incarnation.name`.

### Topbar
- Hamburger toggles rail collapse.
- `● cluster ok` pill is a live status indicator — color reflects cluster health (sage / amber / terracotta).
- User avatar is the account/settings dropdown trigger (out of scope here).

### Composer
- Enter → send. Shift+Enter → newline.
- `@` → opens agent/incarnation mention picker.
- `/` → opens slash-command picker (run, diff, memory, …).
- `📎` → file picker, attached files become chips.
- `⌘K` → opens command palette.

### Transcript behaviors
- Tool blocks should be expandable/collapsible for verbose output (show first ~6 lines then "+ N more").
- Assistant prose `<mark>` highlights should be **content-driven** (the model produces them, not auto-applied) — they're a way for the model to emphasize a phrase.
- Streaming: the bouncing-dots row at the bottom appears while a response is in flight; replace with the streaming response as tokens arrive.

### Cycle counter (§)
- Only render on user turns.
- Increment is over **user turns only**, NOT total transcript index. The Nth user turn shows `§ N` (zero-padded to 2 digits). Assistant turns between them do not advance the counter and do not display it.

### Price display
- **Per-message** (assistant gutter): show the cost of generating that single assistant response. Mono 10/600, accent color.
- **Masthead chip** (`spent $0.0427`): cumulative cost of the current incarnation (sum of all assistant turns). Updates live as new turns complete.
- Format: 4 decimal places for small values; if cumulative exceeds $1.00, drop to 2 decimals.

---

## State Management

```ts
// Rail
type View = "Chat" | "Samsara" | "Logs";
type Mode = "menu" | "tree";

interface RailState {
  view: View;            // which top-level view is active
  mode: Mode;            // menu picker vs. tree
  collapsed: boolean;    // 268px vs. 56px
  search: string;        // filter query for tree mode
  openAgents: Record<string, boolean>;  // which agents are expanded
}

// Chat
interface ChatState {
  activeAgent: string;        // e.g. "test-agent"
  activeIncarnation: string;  // e.g. "rate-limit triage"
  transcript: Turn[];
  streaming: boolean;
}

interface Turn {
  role: "user" | "assistant";
  time: string;          // "10:42" — displayed; store as ISO
  thinking?: string;     // optional pre-text reasoning
  tools?: ToolCall[];
  text?: string;         // markdown-ish — supports <mark>...</mark> emphasis
  // assistant-only:
  model?: string;        // "claude-sonnet-4.5"
  toolCount?: number;
  latencyMs?: number;
  costUsd?: number;
}

interface ToolCall {
  status: "ok" | "err" | "running";
  name: string;
  args: string;          // single-line, mono
  output?: string;       // multi-line, mono, truncatable
}
```

Cumulative spend = `transcript.filter(t => t.role === "assistant").reduce((s, t) => s + (t.costUsd ?? 0), 0)`.

`§` counter for the Nth user turn = `transcript.slice(0, N).filter(t => t.role === "user").length`.

---

## Assets
- No bitmap or vector assets ship with this design. Agent avatars are letter glyphs on gradient/outlined backgrounds (see Colors). The Samsara `◉` and Logs `≡` glyphs are Unicode characters set in mono.
- Fonts: load Newsreader (400/500/600/italic), Inter (400/500/600), JetBrains Mono (400/500/700) from Google Fonts or self-host.

---

## Things to confirm with the designer / PM before building
1. **Command palette (`⌘K`)** — wire a real palette (fuzzy search across agents/incarnations + global actions), or drop the chip entirely. Currently it's just a discoverability hint.
2. **Variant A & B** — kept on the canvas for context, but the canonical direction is Variant C. Confirm before spending cycles on A/B.
3. **Samsara & Logs content** — the placeholders define the shape (rail stubs + center coming-soon card). Real designs for those views are still to come.
4. **Collapsed rail behavior when in Samsara/Logs** — currently expanding from collapsed restores the current view's rail (Samsara stub if view=Samsara). Open question whether expanding should always restore the Chat tree (treating Chat as the implicit default).

---

## A note on naming
The project began as "OpenClaw" — that name is gone. The product is **Aurelia** throughout. The legacy name does not appear in this design.
