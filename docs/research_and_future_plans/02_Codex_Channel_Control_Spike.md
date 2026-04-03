# Codex Channel Control Spike

**Purpose**: Research document for how Codex should fit into Viventium's existing multi-channel agent surface without breaking the core Viventium agent contract.

**Status**: Research Complete | Implementation: Pending Decision  
**Last Updated**: 2026-04-03

---

## Executive Summary

Viventium already has two relevant building blocks:

- a canonical multi-channel agent surface:
  - LibreChat web
  - Telegram bridge
  - voice calls through the voice gateway
- a separate owner/operator Codex surface:
  - `viventium_v0_4/telegram-codex/`

The best near-term architecture is a **hybrid**:

1. Keep Viventium as the canonical conversational front door across web, Telegram, and voice.
2. Keep `telegram-codex` as the direct owner/operator control channel for raw Codex work.
3. Design a medium-term **delegation path** where Viventium can explicitly hand coding and maintenance jobs to Codex as a durable worker and report status/results back.

The key architectural conclusion is:

**Codex fits Viventium better as a worker/delegation surface than as a background cortex.**

Background cortices in Viventium are built for fast detection plus asynchronous insight merge. Codex
work is workspace-bound, stateful, long-running, and owner-privileged. Those are different runtime
contracts.

---

## Current Repo Truth

### 1. Viventium already has a canonical multi-channel agent path

The main product contract is that Telegram and voice should reuse the same LibreChat agent pipeline
as the web UI.

Relevant files:

- `docs/requirements_and_learnings/03_Telegram_Bridge.md`
- `viventium_v0_4/telegram-viventium/README.md`
- `viventium_v0_4/LibreChat/api/server/routes/viventium/telegram.js`
- `docs/requirements_and_learnings/06_Voice_Calls.md`
- `viventium_v0_4/docs/VOICE_CALLS.md`
- `viventium_v0_4/voice-gateway/README.md`

### 2. Viventium already has background agents, but they are not durable coding workers

Background cortices are designed for:

- fast activation detection
- non-blocking execution
- asynchronous insight merge
- channel parity

Relevant files:

- `docs/requirements_and_learnings/02_Background_Agents.md`
- `viventium_v0_4/docs/ARCHITECTURE.md`
- `viventium_v0_4/docs/EXPECTED_BEHAVIOR.md`

### 3. A separate `telegram-codex` sidecar already exists and is wired into the product

`telegram-codex` is not a sketch or an external idea. It is already integrated into:

- config compilation
- installer/wizard flow
- launcher lifecycle

Relevant files:

- `viventium_v0_4/telegram-codex/README.md`
- `viventium_v0_4/telegram-codex/docs/ARCHITECTURE.md`
- `scripts/viventium/config_compiler.py`
- `viventium_v0_4/viventium-librechat-start.sh`
- `config.full.example.yaml`

### 4. `telegram-codex` is intentionally separate from LibreChat

This separation is part of the design:

- separate Telegram bot token
- localhost-only pairing page
- owner-only pairing lock
- per-chat workspace selection
- per-chat Codex thread continuity
- direct local Codex CLI execution against selected workspaces

That separation is currently an architectural advantage, not a bug.

### 5. Power Agents is the closest path to "Codex behind Viventium", but the live implementation is not there yet

The beta Power Agents docs describe both Claude Code and Codex support. The current runtime code
does not deliver that contract yet.

Current code reality:

- `viventium_v0_4/MCPs/power-agents-beta/mcp_server.py`
  - `power_agent_code(...)` documents `agent='codex'`
  - the tool currently ignores the `agent` parameter and always uses Claude Code
- `viventium_v0_4/MCPs/power-agents-beta/agent_server.py`
  - `/agent` and `/agent/stream` explicitly route all work to Claude Code
  - Codex paths exist in the file, but the live endpoint contract says Codex is disabled

This means Power Agents is strategically relevant, but it is not yet a reliable "Codex everywhere"
foundation.

---

## Problem Framing

The user goal is not just "run Codex somewhere." The goal is:

- talk to the Viventium agent through its current channels
- have Codex able to fix, extend, maintain, and configure the system
- achieve a smooth UX that feels like one coherent product

That creates tension between two different modes:

### Mode A: Conversational Viventium

Optimized for:

- same main agent across channels
- parity across web, Telegram, and voice
- fast turn-taking
- background insights that do not block the main reply

### Mode B: Durable Codex work

Optimized for:

- workspace ownership
- persistent thread continuity
- file and repo operations
- potentially long-running tasks
- owner-only trust boundaries
- explicit progress, job status, and artifacts

Trying to force Mode B into Mode A's background-cortex plumbing creates a runtime mismatch.

---

## Options

## Option 1: Keep `telegram-codex` separate and use it as the direct operator channel

### What it means

- Viventium remains the main agent across web, Telegram bridge, and voice.
- `telegram-codex` remains a separate raw Codex bot for owner/operator work.
- Both can be started and managed through the same Viventium install and launcher.

### Pros

- already partially implemented
- safest permissions story
- clear workspace/thread continuity
- separate blast radius from the main agent
- no need to distort the background-cortex contract

### Cons

- two-bot UX seam on Telegram
- no automatic context bridge from Viventium conversations into Codex work
- can feel like two products if left disconnected too long

### Assessment

This is the best **near-term** path and the cleanest thing the repo already supports.

---

## Option 2: Add explicit Viventium-to-Codex delegation

### What it means

Viventium stays the front door, but gains a deliberate "hand this to Codex" capability.

The important detail is that this should behave like a **durable worker/job** flow, not like a
background cortex.

Expected behavior:

1. User asks Viventium to fix, extend, maintain, or configure something.
2. Viventium decides that this requires Codex.
3. Viventium creates a Codex job with explicit metadata:
   - workspace alias
   - requesting user/surface
   - source conversation id
   - task summary
   - owner-only permission gate
4. Codex runs as a durable worker.
5. Viventium reports status and final results back into the original channel.

### Pros

- preserves the "one agent everywhere" experience at the user-facing layer
- keeps Codex in the right runtime role
- works conceptually across web, Telegram, and voice
- provides a clear path for structured status, artifacts, and auditability

### Cons

- requires real product work:
  - job/status model
  - workspace selection logic
  - owner-auth gating
  - result reporting contract
- needs a bridge design, not just a tool call

### Assessment

This is the best **medium-term target**.

### Most likely implementation home

Power Agents is the most natural place for this structured delegation surface to evolve, because it
already models sandboxed coding work behind Viventium. But that path must first become genuinely
Codex-capable instead of documenting Codex while always running Claude Code.

---

## Option 3: Make Codex a background cortex

### What it means

Treat Codex like any other background agent attached to the main Viventium agent so every channel
implicitly gets Codex.

### Pros

- elegant on paper
- simple user story if it worked perfectly
- superficially aligns with "background agent" language

### Cons

- wrong contract for long-running repo work
- weak fit for workspace ownership and thread continuity
- awkward for owner-only permissions
- likely to create UX confusion around progress, waiting, and result delivery
- risks stretching the cortex abstraction until it stops being coherent

### Assessment

Not recommended as the first implementation path.

The only credible cortex-like use for Codex would be something much narrower, such as read-only repo
awareness or lightweight codebase insight generation. That is not the same as letting Codex fix and
maintain the system.

---

## Recommended Direction

### Recommendation

Use a **hybrid now, delegation next** plan:

1. Keep Viventium as the canonical conversational layer across web, Telegram, and voice.
2. Keep `telegram-codex` as the direct owner/operator Codex channel.
3. Build a deliberate Viventium-to-Codex delegation path later.
4. Do not implement Codex-first integration by turning Codex into a background cortex.

### Why this is the best fit

- It respects the current Viventium channel contract.
- It respects the current Codex work contract.
- It uses what the repo already has instead of inventing a fragile shortcut.
- It leaves room for a future "one agent everywhere" UX without lying about what is implemented now.

---

## Best User Experience

The strongest UX is not "hide Codex inside a cortex." It is:

- **one conversational front door**
  - Viventium on web
  - Viventium Telegram bridge
  - Viventium voice
- **one explicit coding/deep-maintenance worker**
  - Codex
- **one clear handoff**
  - Viventium says when it is delegating
  - Codex job status is visible
  - results come back as structured updates

### Near-term UX

- Use Viventium for conversation, planning, routing, and coordination.
- Use `telegram-codex` for raw repo work where the owner wants direct Codex control.

### Medium-term UX

Let Viventium say things like:

- "I'll hand that repo task to Codex in the `viventium_core` workspace."
- "Codex is working on it."
- "Codex finished. Here is the summary, changed files, and any follow-up needed."

### Voice-specific rule

Voice should support:

- task initiation
- status checks
- final summaries

Voice should **not** be the primary interactive surface for deep repo work. It is a poor medium for:

- file paths
- diffs
- project switching
- extended debugging loops

---

## Practical Path Today

The repo already supports enabling `telegram-codex` through canonical config.

Relevant public-safe config surface:

- `~/Library/Application Support/Viventium/config.yaml`
- `integrations.telegram_codex.enabled`
- `integrations.telegram_codex.secret_ref`
- `integrations.telegram_codex.bot_username`

The generated runtime files then land under:

- `~/Library/Application Support/Viventium/runtime/service-env/telegram-codex.env`
- `~/Library/Application Support/Viventium/runtime/telegram-codex/settings.yaml`
- `~/Library/Application Support/Viventium/runtime/telegram-codex/projects.yaml`

The generated projects file already includes a `viventium_core` workspace pointed at the repo root
through `scripts/viventium/config_compiler.py`.

That means the existing product can already support this operator loop:

1. chat with Viventium through the normal agent surfaces
2. switch to `telegram-codex` when raw Codex repo work is needed
3. keep Codex pinned to the Viventium workspace

---

## What Should Be Designed Next

Before implementation, specify a delegation contract with fields such as:

- job id
- workspace alias
- source conversation id
- requesting surface
- requesting user
- owner-only authorization result
- current status
- progress summary
- final summary
- changed files
- artifacts

The key product choice is that the handoff should feel explicit and trustworthy, not magical.

---

## Claude Second Opinion

A review-only Claude pass was run after the initial proposal was formed.

Main points Claude reinforced:

- the hybrid recommendation is the right near-term call
- Codex is better modeled as a durable worker than as a background cortex
- the main weakness in the initial reasoning was underselling the user's "one agent everywhere"
  aspiration
- the two surfaces should not remain disconnected for too long
- Power Agents should evolve into the structured Viventium-to-Codex delegation path instead of
  competing with `telegram-codex`

This review did not replace repo truth. It was used as a challenge pass on the proposal after the
repo analysis was already complete.

---

## Final Recommendation

### Rank 1

**Hybrid now**:

- Viventium is the main agent across existing channels
- `telegram-codex` is the raw owner/operator Codex channel

### Rank 2

**Structured delegation next**:

- Viventium can explicitly hand coding and maintenance jobs to a Codex worker
- Power Agents is the most natural place for that to mature, after its live Codex contract becomes
  real

### Rank 3

**Codex as background cortex**:

- not recommended as the primary path

---

## References

- `docs/requirements_and_learnings/02_Background_Agents.md`
- `docs/requirements_and_learnings/03_Telegram_Bridge.md`
- `docs/requirements_and_learnings/06_Voice_Calls.md`
- `docs/requirements_and_learnings/18_Power_Agents_Beta.md`
- `docs/requirements_and_learnings/40_Public_Private_Boundaries_and_License_Matrix.md`
- `docs/02_ARCHITECTURE_OVERVIEW.md`
- `docs/03_SYSTEMS_MAP.md`
- `viventium_v0_4/docs/ARCHITECTURE.md`
- `viventium_v0_4/docs/EXPECTED_BEHAVIOR.md`
- `viventium_v0_4/docs/VOICE_CALLS.md`
- `viventium_v0_4/voice-gateway/README.md`
- `viventium_v0_4/telegram-viventium/README.md`
- `viventium_v0_4/telegram-codex/README.md`
- `viventium_v0_4/telegram-codex/docs/ARCHITECTURE.md`
- `viventium_v0_4/MCPs/power-agents-beta/mcp_server.py`
- `viventium_v0_4/MCPs/power-agents-beta/agent_server.py`
- `scripts/viventium/config_compiler.py`
- `viventium_v0_4/viventium-librechat-start.sh`
