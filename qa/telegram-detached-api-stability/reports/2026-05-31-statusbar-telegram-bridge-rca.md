<!-- qa-evidence-exempt: Legacy or historical run note predates the V2 QA report template; retained as public-safe context, not a fresh completion claim. -->

# 2026-05-31 Status-Bar Telegram Bridge RCA

## Scope

- User symptom: the macOS V status-bar helper said the stack was running while Telegram did not respond.
- Case: `TGAPI-003` in `qa/telegram-detached-api-stability/cases.md`.
- Public-safety rule: this report uses only sanitized structural evidence. It omits bot tokens,
  Telegram user/chat identifiers, raw message text, local usernames, hostnames, private prompts, and
  absolute machine paths.

## Rules Applied

- Optimize for `Quality + Performance`, not apparent speed alone.
- Trace the real path: helper status -> CLI status -> launcher/watchdog -> Telegram bot handler ->
  logs -> database state -> user-visible status.
- Keep runtime behavior in runtime code and status code; do not patch user intent with keyword
  heuristics.
- Keep public/private boundaries: no raw Telegram updates or private runtime values in docs or QA.
- Verify owning artifacts: source, helper build, installed helper, running runtime, logs, DB shape,
  and status output.
- Use ClaudeViv only as review-only second opinion after a grounded RCA.

## Root Cause

1. The helper health model checked the core web surfaces, but not enabled Telegram sidecars or recent
   Telegram runtime failures. It could therefore present a simple running state while Telegram was
   unhealthy.
2. Telegram logs showed a Bot API polling conflict class: only one poller can own `getUpdates` for a
   BotFather token. The launcher had a stale-PID/orphan gap: outside a formal restart,
   `start_telegram_bot` trusted only the PID file and could start another same-checkout poller if the
   old process still existed without a current PID contract.
3. A transient Bot API `getMe` timeout exposed a separate handler bug: non-reply messages could crash
   while trying to read missing reply context.
4. Generic Telegram error logging included raw update objects, which can contain private Telegram
   content and identifiers.
5. A later real Telegram attempt reached the LibreChat stream path but returned a generic connection
   failure after a retry. Sanitized logs showed the retry/resume request hit a missing successful
   stream. The configured stream services were inheriting the manager default that deletes
   successful jobs immediately, so a reconnect at completion could lose the cached final event and
   turn a successful generation into a user-visible transport error.

## Fix Summary

- Helper status now models optional enabled sidecars:
  - Telegram Bridge PID must be live when Telegram is enabled.
  - Telegram Codex PID must be live when Telegram Codex is enabled.
  - recent Telegram polling/auth issue markers move the stack to a needs-attention state while core
    web surfaces can remain usable.
- CLI status ignores stale Telegram issue markers that occurred before the latest recovery marker.
- Launcher startup now reconciles same-checkout Telegram bot processes before launching:
  - one pidfile-free live bot is adopted back into `telegram_bot.pid`;
  - multiple same-checkout bot processes are collapsed by restart instead of starting another poller.
- Telegram `getMe` timeout fallback now tolerates missing reply context.
- Telegram error logs use structural update/message IDs instead of raw update objects.
- Configured LibreChat stream services now retain successful completed jobs for the store's short
  completion TTL instead of deleting them immediately. Late Telegram resume subscribers can receive
  the cached final event instead of a synthetic generic connection error.
- Exhausted transport-stream failures now emit a structured Telegram bridge error with clear
  expired-stream copy and `speak=false`, so always-voice output does not synthesize local transport
  plumbing failures.
- Requirements and QA case were updated to capture the new behavior.

## Verification Run

Automated checks:

- `bash -n viventium_v0_4/viventium-librechat-start.sh` - PASS.
- `swift build` in the macOS helper project - PASS.
- Telegram bot suite: `uv run python -m pytest ../tests -q` - PASS, 295 tests.
- Telegram bot suite after bridge-error residual fix: `uv run python -m pytest ../tests -q` - PASS,
  298 tests.
- Targeted bridge-error residual tests:
  `uv run python -m pytest ../tests/test_librechat_bridge.py::test_stream_error_message_classifies_tool_errors ../tests/test_librechat_bridge.py::test_stream_response_reports_expired_stream_as_non_spoken_bridge_error ../tests/test_bot_stream_preview.py::test_get_viventium_response_does_not_voice_transport_bridge_errors -q`
  - PASS, 3 tests.
- Release contracts:
  `uv run --with pytest --with pyyaml python -m pytest tests/release/test_detached_librechat_supervision.py tests/release/test_telegram_media_prereqs.py tests/release/test_install_summary.py -q`
  - PASS, 72 tests.
- Stream resume regression:
  `USE_REDIS=false npx jest src/stream/__tests__/GenerationJobManager.stream_integration.spec.ts --coverage=false --runInBand -t "should retain completed jobs for late resume by default"`
  - PASS, 1 targeted test.
- Full stream integration attempt:
  `npm run test:cache-integration:stream -- --testPathPatterns="src/stream/__tests__/GenerationJobManager.stream_integration.spec.ts$"`
  - BLOCKED by missing local Redis on `127.0.0.1:6379`; Redis-dependent cases failed with closed
    connection errors. This is recorded as a prerequisite failure, not a product pass or code
    regression.
- `npm run build` in `viventium_v0_4/LibreChat/packages/api` - PASS; package `dist` contains the
  new configured stream-service retention default.
- Helper fallback build and install were run before this report; the prebuilt helper artifact and
  installed helper were refreshed.
- ClaudeViv review-only pass for the stream-resume patch confirmed the shared-layer RCA and
  recommended fixing the residual expired-stream copy / transport-TTS behavior; that follow-up was
  completed before final QA.

Runtime checks:

- Supported restart path loaded the updated launcher; the normal detached launch was restored
  afterward.
- `bin/viventium status` after warmup reported:
  - LibreChat Frontend: Running.
  - LibreChat API: Running.
  - Modern Playground: Running.
  - Telegram Bridge: Running.
  - Telegram Codex: Running.
  - macOS Status Bar Helper: Running.
- Overall status still reported needs-attention because of an unrelated Scheduler row; Telegram
  itself was running.
- Telegram PID files were present and live:
  - Telegram bot PID: alive.
  - Telegram watchdog PID: alive.
  - Telegram Codex PID: alive.
- Same-checkout Telegram bot process count: `1`.
- Telegram log tail after the latest recovery marker contained:
  - polling start marker,
  - proactive callback registration,
  - scheduler started,
  - application started.
- Telegram log text after the latest recovery marker contained no polling conflict,
  `AttributeError`, auth rejection, or `getMe` failure markers.
- After the bridge-error residual fix, the stack was restarted again via the public CLI path.
  Post-restart status reported LibreChat API and Telegram Bridge running. The latest Telegram
  process was a single scoped bot process and the log showed polling registration and application
  start after the restart marker.
- MongoDB structural inspection showed Telegram collections present and latest ingress projection
  contained only structural keys after excluding raw/private fields.
- Sanitized Telegram logs for the later failed user attempt showed:
  - initial LibreChat stream attempt failed;
  - retry/resume returned `404 Not Found` for the stream endpoint;
  - the bot then produced the generic connection-failure fallback. This evidence triggered
    `TGAPI-004`.

Browser/user-surface checks:

- Playwright CLI was attempted per local QA expectations, but the CLI wrapper/session did not attach
  successfully in this environment and the package-backed screenshot command hung during browser
  bootstrap. The in-app Browser plugin also blocked the localhost navigation under its URL policy.
- Because browser automation was blocked, browser evidence is marked `PARTIAL` for this report.
  CLI status, helper build/install, process state, logs, and DB inspection are supporting evidence,
  not a replacement for real Telegram delivery.

ClaudeViv Review

- ClaudeViv review-only pass agreed with the helper truthfulness, handler null-safety, and logging
  privacy fixes.
- ClaudeViv highlighted that a real Telegram send/receive test is still required before claiming the
  end-user Telegram response path is fully proven.
- ClaudeViv also highlighted the duplicate-poller class; the launcher process reconciliation was added
  after that review and verified by release contract and live restart evidence.

## Result

- `TGAPI-003`: PARTIAL PASS.
- `TGAPI-004`: PARTIAL PASS.
- Passing:
  - status no longer has to collapse enabled Telegram sidecar failures into a simple running state;
  - stale Telegram issue markers no longer keep status unhealthy after a later clean recovery;
  - same-checkout stale-PID/orphan startup no longer creates another local poller;
  - transient `getMe` timeout without reply context no longer crashes the synthetic turn;
  - Telegram error logs no longer log raw update object text.
  - configured stream services retain completed jobs and replay a cached final event to a late
    subscriber in the targeted regression test;
  - the packages/api build succeeded after the stream-service change.
  - genuinely expired/missing stream failures now use specific text and are not eligible for
    always-voice synthesis in the tested bot path.
- Not fully proven:
  - A fresh user-grade inbound Telegram message sent from the real Telegram client and answered by
    Viventium after these changes. This requires the actual user Telegram surface or equivalent
    authenticated client path.
  - Redis-backed stream retention with a live Redis service. The local Redis prerequisite was not
    available during this run.

## Follow-Up Gate

Before marking the Telegram user path fully complete, run one synthetic, public-safe Telegram message
from the real user Telegram account after the post-fix runtime is active, then capture:

- visible Telegram request and Viventium reply,
- Telegram bot log markers for that turn without private text,
- LibreChat/API trace or DB ingress structural record,
- refresh/restart persistence if the flow is meant to survive restart.
