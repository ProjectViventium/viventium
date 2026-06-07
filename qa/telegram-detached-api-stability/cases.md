# Telegram Detached API Stability QA Cases

## Case ID Convention

Use stable `TGAPI-NNN` IDs for telegram detached api stability cases.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `TGAPI-001` | Detached Telegram API paths start, supervise, and fail without breaking the main runtime. | User-visible behavior matches source, docs, persisted state, and logs | Telegram bot/API process, status output, logs | `tests/release/test_telegram_lazy_startup_contract.py` plus user-grade QA when visible | NOT YET RUN (cataloged 2026-05-17; next feature run required) |
| `TGAPI-002` | Public QA evidence is sanitized and reproducible | A PR reviewer can verify the behavior without private/local data | QA report, git diff, logs summary, generated artifacts | Public-safety scan plus relevant release tests | NOT YET RUN (cataloged 2026-05-17; next feature run required) |
| `TGAPI-003` | Status-bar helper and Telegram handler failures are truthful and privacy-safe. | User does not see a simple "Running" helper state while enabled Telegram is unhealthy; transient Bot API metadata failures do not crash normal turns. | macOS helper status menu, Telegram bot process/logs, handler tests | Swift helper build, Telegram pytest slice, live status/menu QA | NOT YET RUN (cataloged 2026-05-31; next feature run required) |
| `TGAPI-004` | Telegram stream resume preserves completed responses across brief reconnect races. | User receives the completed answer instead of a generic connection error when the stream reconnects after successful completion. | Telegram bot, LibreChat stream manager, Telegram SSE endpoint, logs | packages/api stream regression plus real Telegram send/receive QA | NOT YET RUN (cataloged 2026-05-31; next feature run required) |
| `TGAPI-005` | Telegram pre-start LibreChat API outages surface as class-specific, text-only transport errors and recover quickly. | User sees an honest local-runtime-unavailable/restarting message instead of a generic assistant-style reply or spoken fallback when the API is unavailable before ingress. | Telegram bot, LibreChat API watchdog, runtime logs, Mongo ingress ledger, Computer/real Telegram QA | Telegram bridge transport regression, watchdog regression, status/health checks, real Telegram send/receive after live runtime proof | PARTIAL (RCA run 2026-06-06; live send blocked pending user confirmation) |

## `TGAPI-001` - Core User Flow

- Requirement: Detached Telegram API paths start, supervise, and fail without breaking the main runtime.
- Risk covered: implementation, docs, and user-visible behavior drift apart.
- Preconditions: local Viventium runtime or the specific feature harness is available with synthetic, public-safe data.
- Steps:
  1. Exercise the feature through the real user surface, not only a unit test.
  2. Compare the visible result with source code, generated/runtime config, logs, persisted state, and the owning requirement doc.
  3. Capture a public-safe report with expected result, forbidden result, evidence, residual risk, and follow-up.
- Expected result: the feature behaves as documented and every supporting layer agrees.
- Forbidden result: backend logs, mocks, source inspection, or model completions are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, generated/runtime state summary, and docs/case links.
- Automation: `tests/release/test_telegram_lazy_startup_contract.py` plus any narrower feature tests discovered during implementation.
- Last run: NOT YET RUN (cataloged 2026-05-17; not a substitute for the next real feature run).

## `TGAPI-002` - Public-Safe Evidence Record

- Requirement: public QA artifacts must be reproducible and free of secrets, personal data, local paths, raw IDs, and private screenshots.
- Risk covered: a useful local QA run cannot be safely reviewed or published.
- Preconditions: a dated QA report is created for this feature.
- Steps:
  1. Review the report and related diffs for local absolute paths, account identifiers, tokens, raw logs, raw DB rows, private chats, and screenshots with private content.
  2. Keep raw/private evidence outside the public repo and summarize only public-safe counts, statuses, hashes, and conclusions.
  3. Link the report back to this case and the owning requirement doc.
- Expected result: the public report proves the behavior without leaking private/local data.
- Forbidden result: a report includes private transcripts, account identifiers, raw runtime dumps, local home paths, tokens, or secret-bearing command lines.
- Evidence to capture: public-safety scan result and link to the sanitized report.
- Automation: public-safety pattern scan plus relevant release tests.
- Last run: NOT YET RUN (cataloged 2026-05-17; run on each new public report).

## `TGAPI-003` - Honest Helper State And Handler Resilience

- Requirement: status-bar helper and Telegram handler failures are truthful and privacy-safe.
- Risk covered: the menu-bar V reports "Running" while the Telegram bridge cannot respond, or the
  bot logs private Telegram update text while handling an otherwise recoverable failure. Also covers
  watchdog/startup creating a second same-checkout Telegram poller when the PID file is stale or
  missing.
- Preconditions: Telegram is enabled in the compiled local runtime; helper app and Telegram bridge
  are available locally.
- Steps:
  1. Produce or detect a Telegram sidecar issue through sanitized logs/state and verify CLI status
     reports the issue.
  2. Open the macOS helper menu and verify the status row is not simply "Running" while the enabled
     Telegram sidecar has a current issue.
  3. Run a synthetic non-reply Telegram text turn where `get_me` fails and verify the turn continues
     to the LibreChat bridge instead of crashing.
  4. Trigger the generic Telegram error handler and verify logs include only structural IDs, not raw
     update text.
  5. Verify launcher startup reconciles pidfile-free same-checkout bot processes before launching a
     new Telegram poller.
  6. Rebuild/reinstall any changed helper artifact before claiming the status-bar behavior is live.
- Expected result: enabled Telegram sidecar failures surface as needs-attention state, stale PID
  state does not create a duplicate local poller, transient Bot API metadata failures do not crash
  normal messages, and logs remain public-safe.
- Forbidden result: helper says simply "Running" while Telegram is enabled but unhealthy; a non-reply
  message crashes on missing reply context; logs include raw Telegram update/message content.
- Evidence to capture: sanitized CLI/helper status summary, handler test output, helper build/install
  proof, live Telegram or blocked-user-path note, and public-safety scan.
- Automation: Telegram pytest slice, launcher release contract, and Swift helper build; live helper
  menu and Telegram send/receive remain required user-grade evidence when available.
- Last run: NOT YET RUN (cataloged 2026-05-31; not a substitute for the next real feature run).

## `TGAPI-004` - Completed Stream Resume

- Requirement: Telegram stream resume preserves completed responses across brief reconnect races.
- Risk covered: generation succeeds, but the first SSE connection drops at completion and the retry
  receives a 404 because the successful job was deleted immediately; a real expired stream is then
  mislabeled and spoken as a generic connection failure.
- Preconditions: LibreChat API is running with the configured stream services; Telegram bridge is
  enabled or the stream manager can be exercised with a synthetic public-safe stream.
- Steps:
  1. Create a synthetic stream job through the configured stream services.
  2. Emit a final event and complete the job before the late subscriber connects.
  3. Subscribe to the same stream afterward, as a Telegram resume would.
  4. Verify the cached final event is delivered and the job remains only for the short completion
     TTL.
  5. Verify genuinely expired/missing-stream failures use clear text and are not synthesized as
     always-voice audio.
  6. Run a real Telegram synthetic send/receive after the active runtime has the changed package
     artifact loaded.
- Expected result: the late subscriber receives the completed final event; the user does not receive
  a synthetic generic connection error for a successful turn, and real expired-stream diagnostics
  remain text-only.
- Forbidden result: successful completion deletes the stream immediately and a normal Telegram retry
  receives a 404/missing stream instead of the final response; transport/plumbing errors are voiced
  as if they were assistant answers.
- Evidence to capture: packages/api targeted regression output, package build proof, active runtime
  artifact proof, bridge-error tests, sanitized Telegram log markers, and real Telegram visible
  result when available.
- Automation: `USE_REDIS=false npx jest src/stream/__tests__/GenerationJobManager.stream_integration.spec.ts --coverage=false --runInBand -t "should retain completed jobs for late resume by default"`.
- Last run: NOT YET RUN (cataloged 2026-05-31; not a substitute for the next real feature run).

## `TGAPI-005` - Pre-Start API Outage Error Contract

- Requirement: Telegram pre-start LibreChat API outages surface as class-specific, text-only
  transport errors and recover quickly.
- Risk covered: the bot receives a user turn while the local LibreChat API is down or restarting,
  fails before the Telegram ingress route writes a ledger row, and returns a generic assistant-style
  fallback that may be synthesized as always-voice audio.
- Preconditions: local Viventium runtime is enabled with Telegram bridge configured; LibreChat API
  can be made unavailable or a synthetic bridge harness can simulate a pre-ingress connect failure.
- Steps:
  1. Prove the active Telegram bot is pointed at the intended local API origin.
  2. Trigger or simulate a pre-ingress LibreChat API transport failure before `/api/viventium/telegram/chat`
     can write a Telegram ingress event.
  3. Send a synthetic public-safe Telegram message, or run the equivalent bridge harness when live
     Telegram action is blocked.
  4. Verify the visible error names the local runtime/API outage or restart class and is actionable.
  5. Verify the error is delivered as text-only, even when always-voice replies are enabled.
  6. Verify Mongo has no fake successful ingress row for the failed pre-start turn.
  7. Verify the detached API watchdog detects and restores the API within the documented recovery
     envelope, or reports a truthful degraded state while recovery is still in progress.
- Expected result: user receives an honest local-runtime-unavailable/restarting message, no audio
  attachment is synthesized for the transport failure, the ingress ledger remains truthful, and the
  watchdog/status surfaces converge after recovery.
- Forbidden result: `Failed to reach Viventium. Please retry.` is emitted as a generic plain string;
  a transport failure is spoken as an assistant reply; status claims Telegram is ready while the API
  route cannot be reached; recovery takes minutes without a truthful degraded state.
- Evidence to capture: sanitized Telegram bot log markers, helper/watchdog recovery timing, API
  health status, Mongo ingress counts around the failed turn, visible Telegram result, Computer or
  Playwright/user-path proof, and public-safety scan.
- Automation: add a Telegram bridge regression that raises a pre-start connect error and asserts a
  non-spoken class-specific event; add a watchdog regression for mid-outage restarted watchdogs.
- Last run: PARTIAL (implementation QA run 2026-06-07; bridge/release/runtime/browser/Computer
  evidence captured, live Telegram send/receive not transmitted under Computer Use confirmation
  policy).

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Telegram Detached Api Stability. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `TGAPI-UC-001` | On Telegram bot/API process, status output, logs, verify that detached Telegram API paths start, supervise, and fail without breaking the main runtime. | owning requirement for `TGAPI-001` / `TGAPI-001` | Telegram bot/API process, status output, logs | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to TGAPI-001. | User-visible behavior matches source, docs, persisted state, and logs | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
| `TGAPI-UC-002` | On QA report, git diff, logs summary, generated artifacts, create or review the public QA evidence record with setup/auth/config, empty-state, degraded-dependency, and privacy checks. | owning requirement for `TGAPI-002` / `TGAPI-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to TGAPI-002. | The user sees an honest setup, retry, or degraded-state result for TGAPI-002; no fake success is accepted. | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
| `TGAPI-UC-003` | After creating the public QA evidence record, rerun the scan after any retry, report update, or linked artifact change. | owning requirement for `TGAPI-002` / `TGAPI-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to TGAPI-002. | TGAPI-002 remains correct after the persistence or parity step and final wording matches evidence. | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
| `TGAPI-UC-004` | With Telegram enabled and unhealthy, inspect the status-bar helper and Telegram handler behavior. | owning requirement for `TGAPI-003` / `TGAPI-003` | macOS helper menu, Telegram bot process/logs, handler tests | CLI status, helper build/install proof, sanitized logs, source, pytest output, and runtime process state. | Helper surfaces needs-attention instead of simple running; handler failures are recoverable and privacy-safe. | NOT YET RUN (cataloged 2026-05-31; next feature run required) |
| `TGAPI-UC-005` | Send or simulate a Telegram turn whose stream completes before a retry/resume attaches. | owning requirement for `TGAPI-004` / `TGAPI-004` | Telegram bot, LibreChat stream manager, Telegram SSE endpoint, logs | Stream regression, active package build, sanitized logs, DB/state when available. | User receives the completed answer, not a generic connection error caused by immediate stream deletion. | NOT YET RUN (cataloged 2026-05-31; next feature run required) |
| `TGAPI-UC-006` | Send or simulate a Telegram turn while the local LibreChat API is unavailable before ingress. | owning requirement for `TGAPI-005` / `TGAPI-005` | Telegram bot, LibreChat API watchdog, runtime logs, Mongo ingress ledger, Computer/real Telegram QA | Sanitized bridge logs, helper/watchdog timing, API health, Mongo ingress counts, bridge regression output, visible Telegram result. | User sees a class-specific text-only local-runtime/restart error, not a generic spoken fallback. | PARTIAL (RCA run 2026-06-06; live send blocked pending user confirmation) |
