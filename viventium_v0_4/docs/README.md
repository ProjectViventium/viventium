<!-- === VIVENTIUM START ===
Document: Viventium LC LiveKit Docs Index
Purpose: Canonical entry point for this repo's Viventium integration
Added: 2026-01-09
=== VIVENTIUM END === -->

# Viventium LC LiveKit Documentation

This folder is the canonical documentation for the Viventium integration inside LibreChat + LiveKit. It is designed to onboard a new engineer or AI without requiring tribal knowledge.

## Vision and Scope
- Provide a generic background-agent system on top of LibreChat (not neuroscience-specific).
- Keep Main non-blocking under the current two-mode Phase A contract: 1,300 ms for text and 690 ms
  for voice, with 2,000 ms only as the shared fallback when a mode-specific value is unset.
- Preserve UX parity between text chat and LiveKit voice calls.
- Minimize upstream merge conflicts by isolating changes and marking edits.

## Non-Negotiable Rules
- UI must not expose internal neuroscience terms; use "Background Agent" language.
- All edits to upstream LibreChat files must be wrapped with `VIVENTIUM START/END` markers.
- Prefer new files or extension points over editing upstream files.
- Background work does not block Main by default. Only the explicitly configured legacy fail-closed
  tool-hold path may wait when an activated scope has no matching direct Main action surface.

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
- The modern LiveKit playground (`agent-starter-react`) is the default enabled voice UI; the classic
  `agents-playground` UI is default-off and requires an explicit classic playground selection.
- Code Interpreter runs via Docker on port 8001 (`LIBRECHAT_CODE_BASEURL`).

## Read in Order (High-Level to Deep)
1. [Shared project rules](../../AGENTS.md) and relevant-owner read order
2. [Cross-product principles](../../docs/requirements_and_learnings/01_Key_Principles.md)
3. [Feature owner and QA map](../../docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md)
4. [Runtime rules and UX contract](EXPECTED_BEHAVIOR.md)
5. [Architecture](ARCHITECTURE.md)
6. [Voice calls](VOICE_CALLS.md)
7. [Development guide](DEVELOPMENT_GUIDE.md)
8. [Implementation index](IMPLEMENTATION_INDEX.md)

## Deep-Dive References

Use the owning row in the root QA map for current requirement, code, test, and evidence links. Some
legacy runtime prose uses internal “cortex” naming; user-facing UI language remains “Background
Agent” per [Expected Behavior](EXPECTED_BEHAVIOR.md).
