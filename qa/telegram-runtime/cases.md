# Telegram Runtime Cases

## Case TR-001: Polling Conflict Is Visible

- **Expected outcome:** A running Telegram bridge or Telegram Codex sidecar with recent
  `getUpdates` conflict evidence is reported as `Running with issues`.
- **Forbidden result:** `bin/viventium status` says the service is simply `Running` while recent logs
  show another bot process is consuming the same token.
- **Evidence to capture:** synthetic unit test, sanitized status output, and a local runtime note.
- **Last run:** 2026-05-14, automated synthetic coverage added.

## Case TR-002: Provider Authentication Failure Is Actionable

- **Expected outcome:** A running Telegram bridge with recent provider-auth evidence is reported as
  `Running with issues`; a stopped Telegram bridge with the same evidence is reported as
  `Action Required`. Both states use user-safe refresh guidance.
- **Forbidden result:** raw provider error text, token values, account identifiers, or private logs
  appear in public status or QA artifacts.
- **Evidence to capture:** synthetic unit test and public-safe QA report.
- **Last run:** 2026-05-14, automated synthetic coverage expanded after escaped user report.

## Case TR-003: Telegram Codex Restart Clears Scoped Orphans

- **Expected outcome:** `--restart` kills only Telegram Codex processes scoped to the configured
  Telegram Codex checkout before starting a new sidecar.
- **Forbidden result:** duplicate Telegram Codex pollers or broad process kills outside the Viventium
  checkout.
- **Evidence to capture:** static launcher regression test and local status after restart.
- **Last run:** 2026-05-14, static regression coverage added.

## Case TR-004: Provider Rejection Is Not Shown As Connection Error

- **Expected outcome:** A Telegram turn whose LibreChat final event reports rejected model provider
  credentials returns clear reconnect guidance for the AI provider.
- **Forbidden result:** Telegram says only `Connection error. Please retry.` or otherwise implies
  the Telegram transport is broken when the root cause is model-provider auth.
- **Evidence to capture:** bridge stream regression test, local runtime restart, sanitized status/log
  class check.
- **Last run:** 2026-05-14, bridge regression coverage added after escaped user report.

## Case TR-005: Provider Rate Limit Is Not Shown Or Spoken As Connection Error

- **Expected outcome:** A Telegram turn whose primary provider is rate-limited before visible text
  retries the configured valid main-agent fallback LLM. Only an unavailable, invalid, or exhausted
  fallback may return clear provider-rate-limit copy, and that terminal bridge/provider error is
  marked non-spoken.
- **Forbidden result:** Telegram says only `Connection error. Please retry.`, implies Telegram
  transport is broken, skips a configured fallback, or synthesizes a voice note of the bridge error.
- **Evidence to capture:** main-agent fallback regression test, bridge stream regression test,
  sanitized runtime log class, and dated QA report.
- **Last run:** 2026-06-28, automated regression and live-runtime QA rerun. See
  `reports/2026-06-28-telegram-fallback-audio-table-qa-rerun.md`.

## Case TR-006: Telegram Markdown Tables Render Readably

- **Expected outcome:** Markdown pipe tables from main answers or worker callbacks are converted to
  readable Telegram HTML rows.
- **Forbidden result:** Telegram displays raw `| Name | ... |` and `|---|` table syntax.
- **Evidence to capture:** Telegram HTML renderer regression test plus a visual/browser rendering
  check with synthetic public-safe content.
- **Last run:** 2026-06-28, automated regression plus Playwright visual QA rerun. See
  `reports/2026-06-28-telegram-fallback-audio-table-qa-rerun.md`.

## Case TR-007: Telegram Memory Capture Reaches New Conversations

- **Expected outcome:** An explicit synthetic durable fact sent through the real Telegram bot
  advances saved-memory state, while a separate natural event remains available through
  conversation recall; both can be recovered later from new authenticated Chrome/voice sessions.
- **Forbidden result:** Telegram reply success is counted as memory proof, same-thread history is
  reused, the detached writer drops a nearby turn, or saved memory and recall are conflated.
- **Evidence to capture:** visible Telegram send/reply, hashed writer audit, Mongo key/revision and
  message/corpus evidence, new Chrome answer, real voice transcript/audio, and cleanup.
- **Last run:** ADDED 2026-07-11; real native journey required under `MEMCONT-004` and `RAG-005`.

## Case TR-008: Short Telegram Turns Preserve Tool And MCP Capability

- **Expected outcome:** A terse follow-up such as a GlassHive status question receives the same
  configured agent/MCP capability eligibility as a longer Telegram request. The eager GlassHive
  launch/status/wait gateway remains provider-bound and other operations remain discoverable through
  scoped `tool_search` in the same invocation.
- **Forbidden result:** message length, word count, or keywords return an empty tool set; Telegram says
  GlassHive is unavailable while the server is healthy; adding more intent keywords is accepted as a
  fix.
- **Evidence to capture:** exact long-then-short visible Telegram sequence, provider-binding logs,
  tool call content parts in Mongo, GlassHive run/events state, restart/reload proof, and latency.
- **Last run:** PASS-AUTOMATED/PARTIAL 2026-07-13. Long/terse binding and scoped discovery
  regressions pass. A dedicated synthetic Telegram identity has not run the visible sequence.

## Case TR-009: Feeling-Aware Audio Is Natural, Capability-Scoped, And Observable

- **Expected outcome:** Natural positive and negative turns on an always-voice xAI route may use the
  smallest fitting supported xAI controls without a user request; a calm factual turn may correctly
  use none. Raw local/TTS content and structural counts agree, visible Telegram text stays clean,
  audio delivers, and prompt-frame telemetry accounts for the audio instruction under
  `surface_prompt` with no unknown layer.
- **Forbidden result:** The user must beg for emotional voice; every turn is forced to contain a
  tag; xAI markup appears in the bubble; unsupported provider dialects cross routes; audio delivery
  is inferred from logs without a visible file/playback path; or `telegram_audio_output` is recorded
  as an unknown prompt layer.
- **Evidence to capture:** synthetic natural prompts, visible text and audio files, native playback,
  raw marker counts, TTS gate/provider/bytes/timings, Current/Nature state evidence, prompt-frame
  layer summary, exact-model provider negatives, and a public-safe dated report.
- **Last run:** PASS-AUTOMATED/PARTIAL 2026-07-14. Synthetic provider-control, clean-display,
  prompt-layer, and fixed-Nature regressions pass. Dedicated Telegram delivery/playback is NOT RUN.
  See
  `../emotional-cortex/reports/2026-07-14-feelings-activation-and-telegram-acceptance.md`.

## Case TR-010: Disabled Telegram Does Not Touch An Unowned LaunchAgent

- **Expected outcome:** When Telegram is disabled, stop/restart/uninstall does not query or boot out
  the fixed Telegram LaunchAgent label unless an owner-only Viventium receipt proves that the
  current App Support target created it. A receipt-backed job is removed narrowly.
- **Forbidden result:** A disabled or alternate-target install calls `launchctl print` or
  `launchctl bootout` against a personal or unrelated job that happens to use the same label.
- **Evidence to capture:** synthetic launcher test with a launchctl recorder, receipt permissions,
  and an isolated Easy Install stop log.
- **Last run:** PASS 2026-07-20. Disabled/no-receipt and valid-receipt paths pass; isolated Easy
  Install stop produced no Telegram launchctl access.

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Telegram Runtime. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `TELEGRAM-UC-001` | Start or inspect Telegram runtime status while a synthetic polling-conflict log fixture is present. | `TR-001`, `TR-003` | Telegram status command, launcher/supervisor path, and sanitized logs | Status output, scoped process list, launcher tests, and dated QA report | Telegram is shown as running with issues, scoped restart clears only Viventium-owned pollers, and no broad process kill occurs. | 2026-05-14 automated synthetic coverage - passed |
| `TELEGRAM-UC-002` | Send or simulate a Telegram turn whose model provider rejects credentials. | `TR-002`, `TR-004` | Telegram bridge stream, user-visible reply, and sanitized logs | Stream regression test, provider-auth status output, sanitized logs, and QA report | The reply gives provider reconnect guidance instead of blaming Telegram transport or leaking raw provider errors. | 2026-05-14 bridge regression coverage - passed |
| `TELEGRAM-UC-003` | Restart Telegram runtime and compare status/log evidence before and after restart. | `TR-001`-`TR-004` | CLI launcher/status, process list, logs, and Telegram bridge state | Scoped process evidence, status output, sanitized logs, and tests | Restart removes only stale scoped pollers, preserves unrelated processes, and status after restart matches the actual bridge state. | 2026-05-14 static regression coverage - passed |
| `TELEGRAM-UC-004` | Simulate a primary provider-rate-limited Telegram turn while audio replies are enabled. | `TR-005` | Main-agent fallback classifier, Telegram bridge stream, and voice gate | Fallback regression test, stream regression test, sanitized log class, and QA report | A valid configured fallback produces the answer; otherwise the terminal provider-rate-limit blocker is visible text only and non-spoken. | 2026-06-28 automated regression and live-runtime QA rerun - passed automated, partial live external Telegram |
| `TELEGRAM-UC-005` | Render a worker-style Markdown table result for Telegram. | `TR-006` | Telegram Markdown-to-HTML renderer and visual fixture | Renderer regression test and browser screenshot/check with synthetic content | The user sees readable rows, not raw pipe-table syntax. | 2026-06-28 automated plus Playwright visual coverage - passed |
| `TELEGRAM-UC-006` | Send one explicit synthetic memory and one natural synthetic event, then ask about each from new Chrome/voice conversations. | `TR-007`, `MEMCONT-004`, `RAG-005` | real Telegram, Chrome, Modern Playground voice | DB revisions, recall source, logs, visible/audible results, cleanup | Saved memory and recall each work through their own lane and neither depends on the original Telegram thread. | ADDED 2026-07-11; run required |
| `TELEGRAM-UC-007` | Ask Telegram to launch a synthetic GlassHive task, then send a terse status/wait follow-up. | `TR-008`, `AGCFG-005` | dedicated synthetic Telegram identity and isolated LibreChat/GlassHive runtime | visible messages, provider-bound tools, persisted fixture calls, GlassHive run/events, logs, latency | Both turns retain tools, the task is actually launched/checked, and no false unavailable claim appears. | PASS-AUTOMATED/PARTIAL 2026-07-13; binding/discovery regressions pass, dedicated Telegram user path NOT RUN |
| `TELEGRAM-UC-008` | Send natural positive, calm, and negative always-voice turns without naming voice controls. | `TR-009`, `TGVOICE-005`, `EMO-036` | dedicated synthetic Telegram identity and configured TTS fixture | clean bubbles, delivered/played audio, marker counts, provider telemetry, prompt-frame layers, synthetic Feeling state | Expressive moments use fitting supported controls, calm delivery remains restrained, no markup leaks, Current reacts while Nature stays fixed, and no prompt layer is unclassified | PASS-AUTOMATED/PARTIAL 2026-07-16; provider-boundary fixtures pass, dedicated Telegram delivery/playback NOT RUN ([report](../emotional-cortex/reports/2026-07-16-feelings-range-potency-and-telegram-replay.md)) |
| `TELEGRAM-UC-009` | Stop or restart Viventium with Telegram disabled and no ownership receipt, then repeat with a synthetic valid receipt. | `TR-010` | launcher stop/restart path with synthetic launchctl recorder | recorder calls, receipt mode/content, isolated stop log, and release test | No-receipt state makes no launchctl call; valid ownership removes only the receipt-backed label and clears the receipt. | PASS 2026-07-20; automated two-sided test and isolated Easy Install stop evidence |

## Release Test Traceability

- `tests/release/test_telegram_codex_runtime_paths.py`
- `tests/release/test_telegram_lazy_startup_contract.py`
- `tests/release/test_telegram_launchctl_ownership.py`
- `tests/release/test_telegram_transcription_error_contract.py`
