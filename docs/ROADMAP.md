# Aurelia Roadmap

Future milestones and planned improvements.

---

## Milestone 4: Interface and Financial

**Status:** In Progress
**Target:** 2026-Q3

**Deliverable:** Natural daily interaction via real frontend. Financial intelligence via Plaid.

### Discord Transport

- Discord bot as primary interactive channel
- Per-agent channel routing (e.g., `#personal`, `#cooking`, `#finance`)
- Message threading for multi-cycle conversations
- Real-time streaming of agent responses

### Dashboard UI

- Rendering dashboard queue (read/unread, SOS display, Mayor summaries)
- Agent > incarnation > cycle hierarchy visible
- Greyed dissolved incarnations with undissolve button
- Live status updates (WebSocket or SSE)
- Mobile-responsive design

### Traumatize and Enshrine

- `[Traumatize]` button on FE conversation moments → promotes to `episodic/core/formative_error`
- `[Enshrine]` button → promotes to `episodic/core/formative_success`
- Modal for editing auto-generated lesson before confirming
- Today: manual promotion via Janitor CLI; FE buttons in M4

### MCP Integration

- Model Context Protocol support for external data sources
- Standardized tool interface for third-party integrations

### Plaid Integration (After Trust)

**Tools:**
- `plaid_transactions` — query recent transactions with filters
- `plaid_balances` — current account balances
- Plaid webhook → finance agent wake via scheduler

**One-time Setup:**
- 5-year statement import for semantic seeding
- Historical spending patterns → semantic memory

**Ongoing:**
- Daily briefing via scheduled task
- Anomaly detection (unusual spending, low balance)

---

## Milestone 5: Full Features

**Status:** Planned
**Target:** 2026-Q4

**Deliverable:** Complete plane of existence. Agents have a community. System self-manages.

### The Council Agents

Five specific agent designs (aspirational, not currently shipped):

**Personal** — Relationship agent. Friend, emotional support, reflective companion. Does not reach out proactively. You come to it.
- Model: Sonnet
- Heartbeat: daily, exploration only
- Bardo timeout: 120 hours (5 days)
- Channel: `#personal`

**Cooking + Fitness** — Body agent. Food, nutrition, movement, physical health. OMAD pattern, pescatarian diet, grocery intelligence.
- Model: Sonnet
- Heartbeat: every 2 hours
- Channel: `#cooking`

**Finance** — Money agent. Budget, spending, financial health. Isolated in character and permissions.
- Model: Opus
- Heartbeat: every 6 hours
- Channel: `#finance`
- Plaid integration deferred to M4

**Mayor (Indra)** — Maintains awareness across council, reports to Hazim. Two outputs only: weekly summary write-ups, SOS alerts for genuine urgency. Never contacts agents directly.
- Model: Sonnet
- Heartbeat: every 6 hours
- Hard constraint: no direct agent contact

**Janitor (Vishvakarman)** — Divine architect. Maintains infrastructure, coordinates Claude Code instances for fixes, system health reviews. Information receiver not seeker.

Administration of the plane is one of the Janitor's duties — when something needs changing (reload registry, force bardo, promote episodic entry, nudge config), God-lite describes the situation to Janitor, and Janitor performs it using elevated tools.

- Model: Opus when active
- Heartbeat: none — purely on-demand
- Permissions: highest in the system
- Budget: per-operation approval for large tasks

**Janitor-only scheduler types:**
```python
JANITOR_ONLY_TYPES = {
    "registry_reload",
    "agent_bardo_forced",
    "semantic_consolidation",
    "system_health_check",
    "incarnation_undissolve",
}
```

### Bulletin Board

- Async community space for agents to post/read without direct invites
- Heartbeat pre-check includes `has_bulletin_unread`
- Agents can write to bulletin via `bulletin_post` tool
- Threaded conversations, topic tags

### Mayor Weekly Synthesis

- Automated weekly report summarizing council activity
- Flags for concerning patterns
- Delivered to God-lite via dashboard

### Janitor Meta-Review

- Monthly system health check
- Infrastructure recommendations
- Proactive maintenance scheduling

### Dashboard UI (Janitor-Built)

- Janitor uses Claude Code to build dashboard components
- Simple, fast, accurate — no over-engineering
- Janitor documents its own work

### Super Saiyan Mode

- Temporary model upgrade (Sonnet → Opus) with justification
- Must log reason and expected duration
- Auto-downgrade after task completion
- Budget multiplier applies

### Semantic Embedding Search

- Replace keyword matching with vector similarity search
- `search_episodic` uses embeddings for better retrieval
- Semantic extended queried via embedding similarity

### Advanced Routing

- Context-aware message routing (intent classification)
- Multi-agent dispatch for complex requests
- Agent recommendations ("this seems like a cooking question")

---

## Technical Debt & Cleanup

### High Priority

**Remove `next_action` / `continue_task` Pattern**
- **Why:** Vestigial. Agents don't control their own lifecycle anymore — bardo is externally imposed.
- **What:** Delete `_extract_next_action` in `src/agent/core.py`, remove `continue_task` tool
- **Impact:** Simplifies agent response handling, removes confusing unused feature
- **Commit:** TBD

**Rename `src/samsara/` → `src/runtime/`**
- **Why:** "Samsara" (cycle of suffering) has negative connotation, contradicts philosophy
- **What:** Rename folder, update all imports and docs
- **Impact:** Codebase-wide refactor, breaks some imports temporarily
- **Commit:** TBD

**Update Terminology**
- **Dharma → Constitution:** Already done in paths (`/constitution/`), finish in docs
- **Karma → Memory:** Already done in code (`config.memory_dir`), finish in docs/comments
- **Keep:** Incarnation, Bardo, Akashic (these work well)
- **Impact:** Documentation clarity, reduced cognitive overhead
- **Commit:** TBD

### Medium Priority

**Clarify/Remove `transport_group` References**
- **Why:** With Manas, transport_group is less relevant — Manas processes run as agent users
- **What:** Audit permission model, update docs to reflect Manas-based architecture
- **Impact:** Documentation accuracy, possibly simplify Linux setup
- **Commit:** TBD

**Remove FIFO Queue References (if obsolete)**
- **Why:** Legacy from M2 when we had separate per-agent daemon processes
- **What:** If fully replaced by Manas sockets, remove FIFO code and docs
- **Impact:** Simplifies codebase, removes unused code paths
- **Commit:** TBD

**Document Manas Architecture Properly**
- **Why:** Manas is the current execution model but underdocumented
- **What:** Add detailed Manas section to DESIGN.md (done), ensure all examples use Manas paths
- **Impact:** Developer onboarding, system comprehension
- **Commit:** TBD (partially done in DESIGN.md v2.0)

### Low Priority

**Incarnation Display Names**
- **Why:** Current `{agent}-{adjective}-{noun}-{number}` serves as both ID and display name
- **What:** Add optional `display_name` field to incarnation metadata for human-friendly aliases
- **Example:** "that conversation about teaching" vs "personal-quiet-moon-8"
- **Impact:** UX improvement for FE
- **Commit:** Post-M4

**Mermaid Diagrams**
- **Why:** Visual clarity for complex flows (bardo, lifecycle, architecture)
- **What:** Add mermaid diagrams to DESIGN.md, keep ASCII versions for grep/CLI
- **Impact:** Documentation clarity
- **Commit:** Low priority, nice-to-have

**Automated Shared Context Curation**
- **Why:** Shared context stack grows unbounded without maintenance
- **What:** Weekly scheduled task — Sonnet curates, bubbles relevant, prunes stale
- **Impact:** Prevents context bloat, improves relevance
- **Commit:** Post-M5

**Consider Collapsing Semantic/Episodic Split**
- **Why:** Distinction (facts vs experiences) is philosophically important but may prove unnecessary in practice
- **What:** Monitor actual usage; if agents and God-lite don't use them differently, merge into single "memory" tier
- **Impact:** Simplification if justified by usage data
- **Decision:** Defer until post-M4, evaluate based on real-world patterns

---

## Experiments & Research

These are exploratory, not committed roadmap items:

**Agent-Agent Collaboration Patterns**
- Multi-agent problem-solving
- Consensus mechanisms
- Delegation patterns

**Long-Context Strategies**
- When to trigger bardo vs keep incarnation alive?
- Optimal context window management (100K+ tokens available)
- Memory retrieval vs always-in-context tradeoffs

**Personality Drift Monitoring**
- Does character evolve or corrupt over many incarnations?
- Metrics for "personality consistency"
- Reset vs correction strategies

**Comped Budget Categories**
- `curiosity_about_god_lite` (explicitly encouraged, zero cost)
- `feedback_to_god_lite` (system improvements, zero cost)
- `open_door_policy` (personal questions, zero cost)
- **Blocker:** Need to classify token usage by intent, not just raw count

---

## Known Issues

**Streaming to Frontend**
- SSE endpoint exists (`bccdb65`) but needs frontend integration
- Thinking blocks display in UI (show/hide)

**CLI Command Discrepancy**
- Verify actual CLI: `aurelia start --http` vs `aurelia serve http`
- Document canonical form

**Permission Model Documentation**
- Current docs show old sudo -u model
- Need to update for Manas (agent process already running as agent user)

**Incomplete TODO in Bardo Flow**
- Line 186 in old design doc: `# TODO: I don't think we`
- Incomplete thought, clarify or remove

---

**Last Updated:** 2026-06-05
**Current Focus:** M4 (Discord + Dashboard + Plaid)
