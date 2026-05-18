# 2026-05-17 Live Runtime Sanity QA

## Summary

- Cases: `NTA-004`, `MCPOAUTH-003`, `SDR-007`.
- Result: passed for the no-response/background-cortex recovery path, MCP endpoint containment, and truthful runtime status after a reopened log check caught and fixed a second MCP null-guard path.
- Residual: optional local services that were not running remained Action Required and are not counted as healthy.

## Scope Run

- Surfaces: local web chat, Agent Builder side panel, Mongo message state, runtime status CLI, backend logs, prompt bundle drift check.
- Data: synthetic QA prompts only. Raw screenshots, logs, DB IDs, account IDs, hostnames, LAN IPs, and local absolute paths are not included in this public-safe report.

Substitution check: user-visible browser QA, Mongo state summaries, backend log summaries, and CLI status were all checked; automated tests alone were not used as a substitute for user-grade evidence.

## User-Grade Evidence

- Browser QA:
  - Refreshing the previously stuck web conversation showed zero active `Analyzing with ...` rows.
  - A direct synthetic prompt produced a separate assistant text message with `unfinished=false`, `error=false`, and visible text in Mongo.
  - A synthetic original-shaped prompt activated a background cortex, completed with a `cortex_insight` part plus visible text, and did not produce the meta-instructions failure.
  - After rebuilding and restarting the runtime, a post-restart synthetic prompt produced the exact visible assistant text requested and the persisted assistant message had `unfinished=false`, `error=false`, and a text content part.
- CLI/runtime QA:
  - `bin/viventium status` reported core web surfaces Running and enabled optional broken surfaces Action Required.
  - macOS Status Bar Helper reported Running.
- Log QA:
  - A fresh log pass caught a second sibling MCP race, `Cannot read properties of null (reading 'has')`, after the first `get` guard. The user-connection path was patched, rebuilt, restarted, and rechecked.
  - Post-restart logs in the fresh window no longer showed `Cannot read properties of null (reading 'get')` or `Cannot read properties of null (reading 'has')`.
  - The unavailable local MS365 endpoint was skipped by persistent warmup instead of producing repeated connection failure loops.
  - Conversation Recall still logged upload/delete failures while its RAG endpoint was down; this matched the Action Required status and is not counted as healthy.

## Automated Evidence

- `tests/release/test_install_summary.py`: passed.
- `api/server/routes/__tests__/mcp.spec.js`: passed in targeted API run.
- `api/server/services/viventium/__tests__/staleCortexMessageRecovery.spec.js`: passed in targeted API run.
- `api/server/services/viventium/__tests__/BackgroundCortexFollowUpService.spec.js`: passed in targeted API run.
- `client/src/components/Chat/Messages/Content/__tests__/ProgressText.cortex.test.tsx`: passed.
- `packages/api/src/mcp/__tests__/MCPManager.test.ts`: passed as part of package API test run.
- Live prompt bundle drift check passed after recompilation; source and local runtime hashes matched.

## Findings Before Fix

- A refreshed conversation could show stale background cortex rows as active analysis even though the backing assistant message was marked finished.
- A background-style prompt exposed a forced Phase B follow-up that did not include the actual user request; the visible answer could say it only had meta-instructions.
- MCP warmup/status had two separate failure modes: a local OAuth endpoint down and a null `appConnections` path during reinitialization.
- A follow-up log pass found the same startup/reinitialize race one level deeper in the user-scoped MCP connection path: `appConnections` could be null while checking `.has`.
- Runtime status could say the stack was ready even when enabled optional surfaces were unreachable.
- The macOS status-bar helper was configured but not running until refreshed.

## Findings

- New behavior passed the live browser, DB, log, status, and prompt-bundle checks.
- Optional down services are now reported clearly instead of being hidden by a ready banner.
- Historical bad conversation content remains as a past local artifact; new turns after the fix passed.

## Fixes Verified

- Stale cortex recovery marks old active cortex rows as terminal errors and runs periodically after startup.
- Cortex UI treats old active rows as terminal instead of spinning forever after the UI safety timeout.
- Forced Phase B primary follow-up now passes the saved user request from the message tree into the follow-up prompt and source-of-truth prompt bundle.
- MCP warmup skips unreachable local OAuth endpoints and the MCP manager handles missing app-level connections without throwing.
- User-scoped MCP connection creation also treats a missing app-level connection repository as "no app connection" instead of throwing during startup/reinitialize races.
- Runtime status now reports "needs attention" when enabled optional surfaces are down and includes a macOS Status Bar Helper row.

## Residual Risk

- Optional services remained unavailable in this local run: Conversation Recall/RAG, SearXNG, Firecrawl, and the local MS365 MCP endpoint. The product now reports them honestly, but the services themselves still require their configured local dependencies.
- One legacy bad assistant message remains in the local conversation history as historical evidence. New turns after the fix passed.
- Conversation Recall still attempts syncs and enters cooldown while RAG is down; this is visible in logs and should be treated as a follow-up hardening opportunity, not a passed recall feature.

## Public-Safety Review

- This report intentionally omits raw conversation IDs, account IDs, local usernames, local absolute paths, hostnames, LAN IPs, private logs, and screenshots.
- Evidence is summarized with synthetic prompts and public-safe statuses only.
