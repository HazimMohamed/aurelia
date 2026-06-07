# Aurelia Changelog

A chronological record of what's been built.

---

## Milestone 3: Memory and Bardo (MVP) — **COMPLETE** (2026-06)

**Commit:** `90c1b59` and prior

**Delivered:** Real persistent memory. Agents that remember Hazim across incarnations. Security hardening. Manas architecture.

### Core Features

**Memory System:**
- Bardo processing: timeout-based, forced on invite, smart-gated (`worth_archiving`/`worth_consolidating`)
- Semantic memory split: `core.jsonl` (always loaded, ~500 tokens) + `extended/`
- Episodic memory split: `core/` (formative, always loaded) + `extended/` (full history)
- `fcntl` file lock on semantic core writes; idempotent upsert via `_ensure_semantic_core`
- `memory_write` tool with immediate write for `semantic_core` and `semantic` tiers
- Bardo-initiated semantic extraction (Path 2) — unflagged insights
- Undissolve logic (restore from Akashic, same name)

**Shared Context:**
- `shared_context_write` tool (infra owns file, file lock, expiry + scoring)
- `hazim_introduction.md` + `hazim.jsonl` stack

**Budget & Monitoring:**
- Weekly budget tracking with auto-reset on Monday
- Budget exhaustion: pause not cutoff, deterministic dashboard notification
- Budget resume mechanism
- `log_note`, `dashboard_notification`, `search_episodic` tools

**Security & Permissions:**
- Linux permission model with graceful dev fallback
- Room directory permanent

### Beyond the Spec (Also Shipped in M3)

**Manas Architecture:** (`d8b551b`, `90c1b59`)
- Per-agent long-lived process running as agent user
- Eliminates sudo gymnastics for tool execution
- Unix socket communication between runtime daemon and Manas
- Natural permissions — agent process owns what it should own

**Runtime Daemon + Unix Socket IPC:**
- The runtime became a first-class process with explicit 6-function interface
- All transports (HTTP, CLI, future Discord) speak to it over `/var/aurelia/runtime.sock`
- Transport/runtime process separation — HTTP is a thin wrapper, not the system

**Source Tree Restructure:**
- `src/runtime/` (was `samsara/`) + `src/agent/` + `src/memory/` + `src/transport/`
- The folder structure names the layers whose behavior it governs

**CLI (`aurelia`):**
- God-lite's control interface, built on `rich` + `click`
- start/stop of processes, live status dashboard, messaging agents, tailing logs
- Spawning incarnations, forcing bardo, listing histories

**Smart Bardo:**
- `worth_consolidating`, `worth_archiving` — bardo decides what's worth keeping
- Empty incarnations dissolve without trace
- Mechanical heartbeats archive without Sonnet

**Scheduler Folded into Runtime:**
- No separate scheduler process, no HTTP hop between scheduler and runtime
- Scheduler thread calls `runtime_core.process_scheduled_item` directly

**`bash_exec` Tool:**
- Single general-purpose shell execution primitive
- Replaces narrower `web_search` and `web_fetch` tools
- Agents can search web, fetch URLs, read memory, run Python scripts, write files

**Streaming LLM Output:** (`bccdb65`)
- SSE endpoint for real-time streaming to frontend
- Thinking blocks (Claude's extended thinking) stored in transcript

**Lab Infrastructure:** (`a53018d`)
- Experiment harness in `lab/alembic/`
- Sandbox pool (5 Linux users borrowed via fcntl flock)
- Per-experiment results directories

**Adaptive Thinking:** (`a53018d`)
- Claude's extended thinking mode enabled via `thinking_budget_tokens` config
- Thinking blocks stored in transcript, fed back into context on future turns

**Concurrent Incarnations:** (`3f42974`)
- Multiple incarnations per agent (primary + active non-primary)
- Primary designation via symlink, can be reassigned

---

## Milestone 2: Agent Autonomy — **COMPLETE** (2026-04)

**Delivered:** Agents talk to each other, schedule themselves, run heartbeats. The plane is alive.

### Core Features

**Inter-Agent Communication:**
- `invite_agent` + `answer_phone` tools
- Agent invite hook (`HookType.AGENT_INVITE`)
- Forced bardo before invite (clean state)

**Scheduler:**
- Scheduler daemon — typed-action whitelist, pending/completed/failed dirs
- Scheduler API (`/internal/schedule`) with type-permission checking
- All four hook types: `human_message`, `heartbeat`, `scheduled_task`, `agent_invite`

**Heartbeat System:**
- Fast pre-check (budget + bulletin + scheduler queue)
- Agents decide how to use heartbeat time

**Tools:**
- `schedule_task` tool (with `rebirth_from` support for self-perpetuation)
- `list_tools` tool
- `web_search` + `web_fetch` tools (later superseded by `bash_exec`)

**Process Model (M2 - Legacy):**
- Named pipe (FIFO) queue per agent
- Agent daemon process (`src/runtime/agent_daemon.py`) — reads FIFO, dispatches work
- **Note:** Replaced by Manas architecture in M3

**Full HTTP API:**
- Properly exposed runtime interface over HTTP

---

## Milestone 1: Skeleton Agents — **COMPLETE** (2026-02)

**Delivered:** Working conversation that lands in Akashic records. HTTP interface. Health endpoint. Agent scaffolding.

### Core Features

**Basic Runtime:**
- FastAPI server with `POST /message` and `GET /health`
- Config system (global defaults + per-agent agent.json)
- Agent registry (filesystem discovery, in-memory cache)

**Linux Infrastructure:**
- Linux user and group setup (`setup_agent.sh`) for all agents
- Directory structure per agent (`memory/`, `akasha/`, `room/`, `identity/`, `constitution/`)

**Incarnation System:**
- Incarnation name generation via Haiku
- Per-incarnation memory folders with primary symlink
- Context assembly (constitution + identity + payload)
- Agent core loop (LLM call, no tools yet)

**Persistence:**
- Transcript written to `memory/{incarnation}/transcript.jsonl`
- Scratch folder created per incarnation
- Bardo on completion (Sonnet summary → `episodic/extended/`)
- Scratch archived to Akashic on bardo
- Memory folder cleaned after bardo

**Memory Foundation:**
- All memory files JSONL throughout
- Basic semantic/episodic split

---

## Pre-M1 (2026-01)

**Initial Commit:** Project structure, philosophy document, basic agent scaffolding.

**Philosophy Established:**
- Incarnations are disposable, memory is permanent
- Autonomy within governance
- The architecture earns its philosophy

---

**Last Updated:** 2026-06-05
