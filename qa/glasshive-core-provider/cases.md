# GlassHive Core Provider QA Cases

## Case Catalog

| ID | Requirement / user outcome | Real surfaces | Last run |
| --- | --- | --- | --- |
| GCP-001 | GlassHive appears as a normal Agent Provider with exact friendly models and capability-filtered eligibility | Agent Builder | PASS (2026-07-30) |
| GCP-002 | `glasshive_options` and effort create/update/version/save/reload without provider coercion | Agent Builder, API, Mongo | PASS (2026-07-30) |
| GCP-003 | Canonical LIFE/full defaults and additive bootstrap preserve personalized content, exact quoted custom paths, and fail-loud absolute path boundaries | Installer/CLI, filesystem | PASS (2026-08-01 automated path-boundary coverage plus isolated clean install/configure preservation) |
| GCP-004 | Codex and Claude conversation mode answer naturally in the exact folder without mission scaffolding | Web chat, GlassHive | PASS (2026-07-30) |
| GCP-005 | Activity summaries/tool/file steps render, persist, and recover after refresh without hidden reasoning | Web chat, SSE, Mongo | PASS (2026-07-30) |
| GCP-006 | One native session/run per owner/conversation/agent/message; reconnect/retry does not duplicate | Web chat, GlassHive state | PASS (2026-07-30) |
| GCP-007 | Explicit Stop cancels; refresh/disconnect does not cancel; restart/reconnect resumes honestly | Web chat, logs/state | PASS (2026-07-30) |
| GCP-008 | GlassHive cortex executes with its own provider while Phase A stays direct and Phase B follows the main route/session | Web chat, cortex cards | PASS (2026-07-30) |
| GCP-009 | Feelings enters the main authored turn exactly once and never a specialist cortex/activity/LIFE file | Web, Telegram, logs/state | PASS (2026-07-30) |
| GCP-010 | Telegram text, voice note, and video note each produce one harness-authored response | Telegram UI, relay, Mongo | PARTIAL (2026-07-31 delivery regression automated pass; post-fix Desktop run pending) |
| GCP-011 | LiveKit uses the configured cascaded Voice Call LLM; GlassHive may be selected as that text-in/text-out pipeline model but is never mislabeled as native realtime audio | LiveKit UI/call, voice logs | PASS (2026-08-01 real GlassHive Voice LLM call/reconnect acceptance) |
| GCP-012 | Unknown provider/model/effort and stopped/missing/authless/busy/crashed harnesses fail visibly with no OpenAI substitution | Builder/chat, logs | PASS (2026-07-30) |
| GCP-013 | Custom path validation, workspace-only/full access, file work, native tools, and missing tool auth behave honestly | Builder/chat, filesystem/tools | PASS (2026-07-30) |
| GCP-014 | Ten-minute/concurrent mission load preserves the interactive lane and handles rate limit/interruption/restart | Web, GlassHive state | PASS (2026-07-30) |
| GCP-015 | Stream/activity output redacts split credentials and private paths before UI/persistence | API/SSE, Mongo/logs | PASS (2026-07-30) |
| GCP-016 | Direct, GlassHive Codex, and GlassHive Claude meet the combined Quality + Performance bar | Web evaluation matrix | BLOCKED (2026-07-31 current Codex repeat awaits provider quota) |
| GCP-017 | Generated/source/live config, nested commits, parent pins, builds, installed processes, and clean install agree | CLI/runtime/repo | PARTIAL (2026-08-01 exact pins, isolated clean install/upgrade, activation, and live runtime pass; hosted checks pending) |
| GCP-018 | A standard OpenAI Chat Completions client can call GlassHive with only bearer/model/messages/stream, while endpoint/MCP/runtime credentials, owner delegation, and full-access grants remain isolated | Direct SDK/API, generated config, GlassHive routes | PASS (2026-07-30) |
| GCP-019 | A standard OpenAI Responses client can use text/message input, instructions, streaming, and same-owner previous-response continuity through the same GlassHive execution core | Direct SDK/API, GlassHive request/session state | PASS (2026-07-30) |
| GCP-020 | Harness working preambles remain activity only; the authored reply is the final Codex agent message or Claude result | Web, direct SDK, native event logs | PASS (2026-07-30) |
| GCP-021 | A queued busy run does not hot-spin, survives restart, and clears active failure metadata after a successful retry while retaining retry audit fields | GlassHive API/state/logs | PASS (2026-07-30) |
| GCP-022 | Provider usage quota is an explicit OpenAI-compatible rate-limit failure with no fallback, retry storm, or duplicate authoring | Live Chat Completions/Responses API, DB, logs | PASS (2026-07-30) |
| GCP-023 | LibreChat honors the selected provider's declared transport capability at model construction, so SDK model-name heuristics or stale conversation options cannot switch a Chat-Completions provider to Responses | Web/Telegram, LibreChat API, GlassHive logs/state | PARTIAL (2026-08-01 installed web pass with one correlated Chat Completions request/run; Telegram rerun pending) |
| GCP-024 | Every first-turn GlassHive specialist and detached Emotional Reaction cortex binds to the canonical persisted conversation while retaining its own agent-scoped native session | Web chat, cortex cards, Mongo, GlassHive session state | PARTIAL (2026-08-01 regression fixed and automated tests pass; exact installed replay pending) |
| GCP-025 | Source-checkout Easy Install bootstraps GlassHive and compiles canonical Main to Codex, while immutable Native defaults remain GlassHive-off until that payload owns the runtime | Wizard/compiler, Native assembler | PASS (2026-08-01 focused source/native contract tests) |
| GCP-026 | Source Easy pins the Codex model/profile and requires authenticated Codex; a Claude-only host fails readiness without provider fallback or silent model remapping, while Custom may accept Claude | Wizard/preflight/readiness/compiler | PASS (2026-08-01 Codex-only and Claude-only regression tests) |
| GCP-027 | An alternate App Support runtime compiles and uses its own profiled GlassHive SQLite state without touching canonical user state | Compiler, clean install/upgrade, GlassHive API/state | PASS (2026-08-01 isolated clean install, direct API, web run, upgrade, and zero canonical-request evidence) |
| GCP-028 | Custom aligns an absent provider model to the resolved worker profile; an explicit mismatched model remains unchanged and fails its exact harness-auth gate | Defaults/preflight/compiler | PASS (2026-08-01 Custom Claude-only and explicit-model mismatch regression tests) |
| GCP-029 | An accepted host-native conversation survives API restart without truncating its instruction, double-launching the harness, or losing exact cancel/timeout/non-zero status | GlassHive API/supervisor/private state | PASS (2026-08-02 large-input Codex and Claude restart, active-child cancel, timeout, and non-zero-exit regressions) |
| GCP-030 | Independent interactive conversations do not suffer unbounded cross-chat head-of-line delay; any host-CLI concurrency limit is explicit and proven safe | Web, GlassHive state | FAIL (2026-08-03 one web turn queued about 75 seconds behind another conversation before completing correctly) |
| GCP-031 | A structured quota/rate admission failure before authoring uses the Agent Builder fallback exactly once; lifecycle reconciliation does not lock recovery and cancellation stops the active attempt | Agent Builder, web/Telegram chat, SSE, GlassHive state | PASS (2026-08-06 real native Telegram recovery plus automated quota/provider-unavailable coverage; see `reports/2026-08-06-telegram-reconciliation-fallback-recovery.md`) |
| GCP-032 | GlassHive's provider-internal serial fallback is a separate opt-in Agent setting, defaults disabled, persists model/effort, clears cleanly, and never starts after native authoring evidence | Agent Builder, API, Mongo, GlassHive state | PASS (2026-08-04 installed save/reload and degraded/race coverage; see `reports/2026-08-04-installed-agent-builder-glasshive-fallback.md`) |
| GCP-033 | A foreign reconciler preserves a host run only while its matching owner lease is valid; dead/stale/reused ownership and late CLI return cannot pin or overwrite durable interruption, while user Stop never falls back | Web/Telegram chat, GlassHive state, logs | PASS (2026-08-06 real reconciliation, Stop, dead-owner fallback, and focused regressions; see `reports/2026-08-06-telegram-reconciliation-fallback-recovery.md`) |
| GCP-034 | Conversation-provider host capabilities are projected only when policy authorizes them; an honest empty projection proceeds, while a declared capability whose signed bundle cannot be minted fails closed | Web chat, provider bootstrap, GlassHive state | PASS-LIVE/AUTOMATED (2026-08-08 empty-projection repair and 20 provider tests; see `../memory-continuity/reports/2026-08-08-cognitive-continuity-capability-repair.md`) |
| GCP-035 | Local-prod activation tolerates a legitimate persisted-state GlassHive cold start beyond three seconds, while candidate process exit fails immediately and the bounded deadline cleans only the candidate | Dev runtime activation, GlassHive runtime/MCP/UI, process/log evidence | PARTIAL (2026-08-12 focused regression passed; post-fix transactional local-prod activation pending; see `reports/2026-08-12-local-prod-cold-start-readiness.md`) |

## Natural User Use Case Checklist

| Use case | Natural user action | Real surface | Supporting evidence | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- |
| Happy path | Create an ordinary or cortex Agent, select GlassHive/Codex, save, chat, and work with a synthetic LIFE file | Agent Builder/web chat | SSE, Mongo, GlassHive session/run, file result | One relevant harness-authored answer plus honest activity | PASS (2026-07-30) |
| Alternate model | Select GlassHive/Claude and correct it in a second turn | Agent Builder/web chat | Request/session rows, harness auth/model evidence | Same conversation session; correction uses visible history | PASS (2026-07-30) |
| Portable endpoint | Call both GlassHive models from a standard OpenAI client without Viventium metadata, then try unsupported parameters and cross-scope credentials/owner/access headers | Direct SDK/API | HTTP/SSE envelopes, request/session rows, route auth | Standard call succeeds; unsupported/escalating/cross-scope calls fail with precise standard errors | PASS (2026-07-30) |
| First run | Install with no LIFE folder | Installer/CLI/filesystem | Tree/hash comparison, bootstrap state outside LIFE | Missing structure is added; personalized files are never overwritten | PASS (2026-08-01 isolated clean install plus configure/upgrade preservation) |
| Missing auth/config | Try both models with missing sign-in or binary and with GlassHive stopped | Builder/chat | Provider health and application logs | Readiness/setup or exact failure; no invented answer/fallback | PASS (2026-07-30) |
| Invalid input | Save unsupported model/effort, relative custom/root path, malformed compiled path, symlink loop, or missing custom path | Builder/API/CLI | API response, CLI stderr, unchanged Agent document/filesystem | Validation blocks or runtime fails loudly without a traceback or alternate directory | PARTIAL (2026-07-31 compiler/bootstrap automated pass; final Builder path rerun pending) |
| Tools/files | Ask the harness to inspect/edit a synthetic file and use an authenticated/unavailable tool | Web chat/filesystem | File diff/tool evidence, activity, logs/state | Native result or precise missing-auth error | PASS (2026-07-30) |
| Cancel/reconnect | Stop one run; refresh or interrupt network on another | Web chat | Run counts, cancel/activity events | Stop cancels exactly once; refresh reconnects without duplicate | PASS (2026-07-30) |
| Persistence/restart | Save, refresh, restart app/GlassHive, reopen and continue | Builder/web chat | Mongo, App Support and GlassHive manifests | Provider/options/activity/conversation persist or recover honestly | PASS (2026-07-30) |
| Cortex/Feelings | Trigger a GlassHive cortex and main follow-up with Feelings on | Web chat/cortex cards | Prompt telemetry counts, run/session state | Correct cards/session route; one main capsule; no specialist copy | PASS (2026-07-30) |
| Cross-surface | Send synthetic Telegram text/voice/video and place a LiveKit call | Telegram and LiveKit UIs | Relay/voice logs, Mongo/provider route | Telegram uses selected Agent provider once; LiveKit stays Voice LLM | PARTIAL (2026-07-31 post-fix user run pending) |
| Load/degraded | Run a long mission concurrently, then crash/rate-limit/restart the CLI | Web chat/GlassHive | Latency, lane/run state, error/recovery logs | Interactive lane remains usable; precise recoverable state | PASS (2026-07-30) |
| Fallback/recovery | Configure Agent-level and provider-internal fallbacks, then trigger pre-authoring rate limit, dead ownership, and explicit Stop | Agent Builder, web/Telegram, GlassHive state | Persisted settings, attempt/run ledger, visible result, cancellation state | At most one authorized fallback starts before authoring; Stop cancels without fallback; recovery remains visible and idempotent | PASS/PARTIAL (2026-08-04 through 2026-08-06; concurrency latency remains open in GCP-030) |
| Capability projection | Run once with no authorized host capabilities and once with a declared capability whose signed bundle cannot be minted | Web chat, broker/provider bootstrap | Visible answer/error, signed-bundle audit, provider state | Empty projection is a valid capability-free turn; an unmintable declared capability fails closed | PASS-LIVE/AUTOMATED (2026-08-08) |
| Cold-start recovery | Activate a reviewed checkout against an existing production-sized GlassHive state whose runtime is not ready at the old three-second boundary | Dev runtime activation, GlassHive runtime/MCP/UI | PID lifecycle, per-surface readiness timing, activation receipt, logs | The live predecessor remains safe until the candidate becomes fully ready; a live but slow candidate is not destroyed; failures remain bounded and candidate-scoped | PARTIAL (2026-08-12 focused regression passed; post-fix activation pending) |
| Release path | Fresh supported install and installed runtime run | Installer/CLI/web | Generated files, processes, commits/pins/artifacts | LIFE/provider/build/pins all present and aligned | PARTIAL (2026-08-01 isolated clean install/upgrade/live web proof passed; hosted checks pending) |

## Acceptance Rules

- Automated release ownership: `tests/release/test_life_bootstrap.py` covers additive LIFE creation,
  compiler-shell-quote round trips, absolute/symlink-loop path safety, modes, and CLI integration; provider compilation is covered by
  `tests/release/test_config_compiler.py` under the installer-resilience owner; the provider-specific
  release contract is covered by `tests/release/test_glasshive_core_provider_qa.py`.
- Every applicable row is `PASS`, `FAIL`, `PARTIAL`, or `BLOCKED` in a dated report.
- A required real user path cannot be replaced by a mock, source review, unit test, DB row, or another
  model's review.
- Forbidden results: wrapper LLM authorship, silent OpenAI fallback, duplicate harness run/reply,
  GlassHive as Phase A/native realtime audio, unconfigured or post-authoring fallback, specialist Feelings injection, runtime files in
  LIFE, hidden chain-of-thought, shared provider/MCP/runtime credentials, caller-asserted owner or
  full-access escalation, or private data in committed evidence.

Latest detailed recovery result:
[`reports/2026-08-06-telegram-reconciliation-fallback-recovery.md`](reports/2026-08-06-telegram-reconciliation-fallback-recovery.md).
The original cross-surface release matrix remains partial.
