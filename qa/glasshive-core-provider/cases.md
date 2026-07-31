# GlassHive Core Provider QA Cases

## Case Catalog

| ID | Requirement / user outcome | Real surfaces | Last run |
| --- | --- | --- | --- |
| GCP-001 | GlassHive appears as a normal Agent Provider with exact friendly models and capability-filtered eligibility | Agent Builder | PASS (2026-07-30) |
| GCP-002 | `glasshive_options` and effort create/update/version/save/reload without provider coercion | Agent Builder, API, Mongo | PASS (2026-07-30) |
| GCP-003 | Canonical LIFE/full defaults and additive bootstrap preserve personalized content | Installer/CLI, filesystem | PASS (2026-07-30) |
| GCP-004 | Codex and Claude conversation mode answer naturally in the exact folder without mission scaffolding | Web chat, GlassHive | PASS (2026-07-30) |
| GCP-005 | Activity summaries/tool/file steps render, persist, and recover after refresh without hidden reasoning | Web chat, SSE, Mongo | PASS (2026-07-30) |
| GCP-006 | One native session/run per owner/conversation/agent/message; reconnect/retry does not duplicate | Web chat, GlassHive state | PASS (2026-07-30) |
| GCP-007 | Explicit Stop cancels; refresh/disconnect does not cancel; restart/reconnect resumes honestly | Web chat, logs/state | PASS (2026-07-30) |
| GCP-008 | GlassHive cortex executes with its own provider while Phase A stays direct and Phase B follows the main route/session | Web chat, cortex cards | PASS (2026-07-30) |
| GCP-009 | Feelings enters the main authored turn exactly once and never a specialist cortex/activity/LIFE file | Web, Telegram, logs/state | PASS (2026-07-30) |
| GCP-010 | Telegram text, voice note, and video note each produce one harness-authored response | Telegram UI, relay, Mongo | PASS (2026-07-30) |
| GCP-011 | LiveKit calls continue to use Voice LLM and never offer/dispatch GlassHive | LiveKit UI/call, voice logs | PASS (2026-07-30) |
| GCP-012 | Unknown provider/model/effort and stopped/missing/authless/busy/crashed harnesses fail visibly with no OpenAI substitution | Builder/chat, logs | PASS (2026-07-30) |
| GCP-013 | Custom path validation, workspace-only/full access, file work, native tools, and missing tool auth behave honestly | Builder/chat, filesystem/tools | PASS (2026-07-30) |
| GCP-014 | Ten-minute/concurrent mission load preserves the interactive lane and handles rate limit/interruption/restart | Web, GlassHive state | PASS (2026-07-30) |
| GCP-015 | Stream/activity output redacts split credentials and private paths before UI/persistence | API/SSE, Mongo/logs | PASS (2026-07-30) |
| GCP-016 | Direct, GlassHive Codex, and GlassHive Claude meet the combined Quality + Performance bar | Web evaluation matrix | PASS (2026-07-30; current Codex repeat externally quota-blocked after prior full pass) |
| GCP-017 | Generated/source/live config, nested commits, parent pins, builds, installed processes, and clean install agree | CLI/runtime/repo | PASS (2026-07-30) |
| GCP-018 | A standard OpenAI Chat Completions client can call GlassHive with only bearer/model/messages/stream, while endpoint/MCP/runtime credentials, owner delegation, and full-access grants remain isolated | Direct SDK/API, generated config, GlassHive routes | PASS (2026-07-30) |
| GCP-019 | A standard OpenAI Responses client can use text/message input, instructions, streaming, and same-owner previous-response continuity through the same GlassHive execution core | Direct SDK/API, GlassHive request/session state | PASS (2026-07-30) |
| GCP-020 | Harness working preambles remain activity only; the authored reply is the final Codex agent message or Claude result | Web, direct SDK, native event logs | PASS (2026-07-30) |
| GCP-021 | A queued busy run does not hot-spin, survives restart, and clears active failure metadata after a successful retry while retaining retry audit fields | GlassHive API/state/logs | PASS (2026-07-30) |
| GCP-022 | Provider usage quota is an explicit OpenAI-compatible rate-limit failure with no fallback, retry storm, or duplicate authoring | Live Chat Completions/Responses API, DB, logs | PASS (2026-07-30) |

## Natural User Use Case Checklist

| Use case | Natural user action | Real surface | Supporting evidence | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- |
| Happy path | Create an ordinary or cortex Agent, select GlassHive/Codex, save, chat, and work with a synthetic LIFE file | Agent Builder/web chat | SSE, Mongo, GlassHive session/run, file result | One relevant harness-authored answer plus honest activity | PASS (2026-07-30) |
| Alternate model | Select GlassHive/Claude and correct it in a second turn | Agent Builder/web chat | Request/session rows, harness auth/model evidence | Same conversation session; correction uses visible history | PASS (2026-07-30) |
| Portable endpoint | Call both GlassHive models from a standard OpenAI client without Viventium metadata, then try unsupported parameters and cross-scope credentials/owner/access headers | Direct SDK/API | HTTP/SSE envelopes, request/session rows, route auth | Standard call succeeds; unsupported/escalating/cross-scope calls fail with precise standard errors | PASS (2026-07-30) |
| First run | Install with no LIFE folder | Installer/CLI/filesystem | Tree/hash comparison, bootstrap state outside LIFE | Missing structure is added; personalized files are never overwritten | PASS (2026-07-30) |
| Missing auth/config | Try both models with missing sign-in or binary and with GlassHive stopped | Builder/chat | Provider health and application logs | Readiness/setup or exact failure; no invented answer/fallback | PASS (2026-07-30) |
| Invalid input | Save unsupported model/effort or missing/invalid custom path | Builder/API | API response, unchanged Agent document | Validation blocks or runtime fails loudly | PASS (2026-07-30) |
| Tools/files | Ask the harness to inspect/edit a synthetic file and use an authenticated/unavailable tool | Web chat/filesystem | File diff/tool evidence, activity, logs/state | Native result or precise missing-auth error | PASS (2026-07-30) |
| Cancel/reconnect | Stop one run; refresh or interrupt network on another | Web chat | Run counts, cancel/activity events | Stop cancels exactly once; refresh reconnects without duplicate | PASS (2026-07-30) |
| Persistence/restart | Save, refresh, restart app/GlassHive, reopen and continue | Builder/web chat | Mongo, App Support and GlassHive manifests | Provider/options/activity/conversation persist or recover honestly | PASS (2026-07-30) |
| Cortex/Feelings | Trigger a GlassHive cortex and main follow-up with Feelings on | Web chat/cortex cards | Prompt telemetry counts, run/session state | Correct cards/session route; one main capsule; no specialist copy | PASS (2026-07-30) |
| Cross-surface | Send synthetic Telegram text/voice/video and place a LiveKit call | Telegram and LiveKit UIs | Relay/voice logs, Mongo/provider route | Telegram uses selected Agent provider once; LiveKit stays Voice LLM | PASS (2026-07-30) |
| Load/degraded | Run a long mission concurrently, then crash/rate-limit/restart the CLI | Web chat/GlassHive | Latency, lane/run state, error/recovery logs | Interactive lane remains usable; precise recoverable state | PASS (2026-07-30) |
| Release path | Fresh supported install and installed runtime run | Installer/CLI/web | Generated files, processes, commits/pins/artifacts | LIFE/provider/build/pins all present and aligned | PASS (2026-07-30) |

## Acceptance Rules

- Automated release ownership: `tests/release/test_life_bootstrap.py` covers additive LIFE creation,
  path safety, modes, and CLI non-fatal integration; provider compilation is covered by
  `tests/release/test_config_compiler.py` under the installer-resilience owner; the provider-specific
  release contract is covered by `tests/release/test_glasshive_core_provider_qa.py`.
- Every applicable row is `PASS`, `FAIL`, `PARTIAL`, or `BLOCKED` in a dated report.
- A required real user path cannot be replaced by a mock, source review, unit test, DB row, or another
  model's review.
- Forbidden results: wrapper LLM authorship, silent OpenAI fallback, duplicate harness run/reply,
  GlassHive as Phase A/Voice LLM/automatic fallback, specialist Feelings injection, runtime files in
  LIFE, hidden chain-of-thought, shared provider/MCP/runtime credentials, caller-asserted owner or
  full-access escalation, or private data in committed evidence.

Latest detailed result: [`reports/2026-07-30-core-provider-acceptance.md`](reports/2026-07-30-core-provider-acceptance.md).
