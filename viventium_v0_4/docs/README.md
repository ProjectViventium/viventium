<!-- === VIVENTIUM START ===
Document: Viventium LC LiveKit Docs Index
Purpose: Canonical entry point for this repo's Viventium integration
Added: 2026-01-09
=== VIVENTIUM END === -->

# Viventium LC LiveKit Documentation

This folder is the canonical documentation for the Viventium integration inside LibreChat + LiveKit. It is designed to onboard a new engineer or AI without requiring tribal knowledge.

## Vision and Scope
- Provide a generic background-agent system on top of LibreChat (not neuroscience-specific).
- Keep background processing non-blocking with a 2s activation-detection budget.
- Preserve UX parity between text chat and LiveKit voice calls.
- Minimize upstream merge conflicts by isolating changes and marking edits.

## Non-Negotiable Rules
- UI must not expose internal neuroscience terms; use "Background Agent" language.
- All edits to upstream LibreChat files must be wrapped with `VIVENTIUM START/END` markers.
- Prefer new files or extension points over editing upstream files.
- Background agents must never block the main agent response.

## Quick Start
- Full stack (LibreChat + LiveKit + Playground + Voice Gateway): `./viventium-librechat-start.sh`
- LibreChat only (text UI): `./LibreChat/scripts/viventium-start.sh`

<!-- === VIVENTIUM START ===
Section: Recent runtime nuances
Added: 2026-01-11
=== VIVENTIUM END === -->
## Runtime Nuances (Do Not Skip)
- Voice STT defaults to local whisper.cpp (`VIVENTIUM_STT_PROVIDER=whisper_local`) with Silero VAD for streaming.
- Voice calls bypass LibreChat concurrency limits by default (`VIVENTIUM_VOICE_BYPASS_CONCURRENCY=true`).
- LiveKit startup is idempotent; the launcher reuses a running container on port 7880.
- `--modern-playground` uses the agent-starter-react UI under `agent-starter-react`.
- Code Interpreter runs via Docker on port 8001 (`LIBRECHAT_CODE_BASEURL`).

## Read in Order (High-Level to Deep)
1. `docs/VIVENTIUM_STATUS.md` (preferences, requirements, status, changes)
2. `docs/EXPECTED_BEHAVIOR.md` (rules, UX contract, timing, non-blocking flow)
3. `docs/ARCHITECTURE.md` (components, code paths, data model, SSE contract)
4. `docs/VOICE_CALLS.md` (LiveKit flow, voice gateway, parity rules)
5. `docs/DEVELOPMENT_GUIDE.md` (workflow, env, testing, merge strategy)
6. `docs/IMPLEMENTATION_INDEX.md` (where each change lives in the codebase)
7. `docs/feedback_1.md` (historical feedback for regression reference)

## Deep-Dive References (Historical / Evidence)
Note: Some legacy docs use internal \"cortex\" naming; UI language remains \"Background Agent\" per `docs/EXPECTED_BEHAVIOR.md`.
- `LibreChat/docs/BACKGROUND_CORTEX_IMPLEMENTATION.md`
- `LibreChat/docs/BACKGROUND_CORTEX_LEARNINGS.md`
- `VOICE_CALL_FULL_REPORT.md`
- `VOICE_CALL_GAP_ANALYSIS.md`
- `VOICE_CORTEX_INSIGHTS_IMPLEMENTATION.md`
- `VOICE_INSIGHT_GAP_ANALYSIS_2026-01-09.md`
- `VOICE_CALL_MEMORY_FIX_REPORT.md`
