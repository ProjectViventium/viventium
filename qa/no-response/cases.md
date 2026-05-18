# No Response QA Cases

## Case ID Convention

Use stable `NTA-NNN` IDs for no response cases.

## Case Catalog

| Case ID | Requirement | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- |
| `NTA-001` | Web silent turn suppression | Web chat, persisted message state | prompt/eval no-response checks plus browser QA | NOT YET RUN (cataloged 2026-05-17; run when feature changes) |
| `NTA-002` | Voice/listen-only silence | Voice/listen-only transcript and final output | prompt architecture eval harness plus voice QA | NOT YET RUN (cataloged 2026-05-17; run when feature changes) |
| `NTA-003` | Errors are never hidden | Web/Telegram/voice final output and logs summary | test_prompt_architecture_eval_harness.py | NOT YET RUN (cataloged 2026-05-17; run when feature changes) |
| `NTA-004` | Background cortex turns never leave an indefinite visible spinner or blank assistant answer | Web chat, Mongo message state, backend logs | `staleCortexMessageRecovery.spec.js`, `ProgressText.cortex.test.tsx`, live browser QA | 2026-05-17 live runtime sanity - passed with residual optional-service actions |

## `NTA-001` - Web silent turn suppression

- Requirement: Web silent turn suppression.
- Risk covered: Viventium claims the behavior works without proving the real user-visible surface and supporting state.
- Preconditions: local runtime or focused harness is available with synthetic public-safe data.
- Steps:
  1. Run a synthetic web turn whose correct output is no visible response; verify no user-visible message is produced and persisted state does not show raw no-response marker.
  2. Compare visible result with source/config, logs or persisted state summary, and the owning requirement doc.
  3. Save a public-safe dated report under `reports/` using the standard run-report template.
- Expected result: visible behavior, supporting evidence, and documentation agree.
- Forbidden result: mocks, backend logs, source inspection, or model output are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, state/log summary, and public-safety review.
- Automation: prompt/eval no-response checks plus browser QA.
- Last run: NOT YET RUN (cataloged 2026-05-17; not a substitute for the next real feature run).

## `NTA-002` - Voice/listen-only silence

- Requirement: Voice/listen-only silence.
- Risk covered: Viventium claims the behavior works without proving the real user-visible surface and supporting state.
- Preconditions: local runtime or focused harness is available with synthetic public-safe data.
- Steps:
  1. In listen-only or passive voice mode, verify ambient speech does not trigger supportive chatter unless directly addressed or safety/time sensitivity applies.
  2. Compare visible result with source/config, logs or persisted state summary, and the owning requirement doc.
  3. Save a public-safe dated report under `reports/` using the standard run-report template.
- Expected result: visible behavior, supporting evidence, and documentation agree.
- Forbidden result: mocks, backend logs, source inspection, or model output are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, state/log summary, and public-safety review.
- Automation: prompt architecture eval harness plus voice QA.
- Last run: NOT YET RUN (cataloged 2026-05-17; not a substitute for the next real feature run).

## `NTA-003` - Errors are never hidden

- Requirement: Errors are never hidden.
- Risk covered: Viventium claims the behavior works without proving the real user-visible surface and supporting state.
- Preconditions: local runtime or focused harness is available with synthetic public-safe data.
- Steps:
  1. Force a synthetic tool/provider failure in a no-response-capable path; verify the user sees the failure instead of silence.
  2. Compare visible result with source/config, logs or persisted state summary, and the owning requirement doc.
  3. Save a public-safe dated report under `reports/` using the standard run-report template.
- Expected result: visible behavior, supporting evidence, and documentation agree.
- Forbidden result: mocks, backend logs, source inspection, or model output are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, state/log summary, and public-safety review.
- Automation: test_prompt_architecture_eval_harness.py.
- Last run: NOT YET RUN (cataloged 2026-05-17; not a substitute for the next real feature run).

## `NTA-004` - Background Cortex Turn Completes Or Fails Visibly

- Requirement: background cortex turns must either produce visible assistant text or terminal visible error rows; they must not spin forever or save an empty canonical assistant message as if complete.
- Risk covered: a user sees "Analyzing with ..." indefinitely, while the DB says the assistant message is finished and no later recovery repairs it.
- Preconditions: local web runtime is running with synthetic public-safe data; Mongo and backend logs are available locally.
- Steps:
  1. Open the affected web conversation in a real browser and refresh it.
  2. Verify old stale cortex rows render as terminal errors, not active spinners.
  3. Send a fresh direct prompt and verify the latest assistant message has visible text, `unfinished=false`, and `error=false`.
  4. Send a synthetic prompt shaped like the original background-analysis failure and verify the latest assistant message has visible text, any cortex part is terminal (`complete` or `error`), and the answer does not claim the user request was missing.
  5. Compare browser result with Mongo message state, backend logs, and the owning source/test changes.
- Expected result: no active "Analyzing with ..." rows remain after completion/recovery; fresh assistant messages contain visible text; forced Phase B follow-up prompts include the actual user request.
- Forbidden result: a finished assistant message has only `cortex_brewing` active parts, empty visible text, or a follow-up answer that says only meta-instructions were available.
- Evidence to capture: sanitized browser screenshot/summary, Mongo shape summary without raw IDs, backend log summary, and automated test output.
- Automation: `api/server/services/viventium/__tests__/staleCortexMessageRecovery.spec.js`, `client/src/components/Chat/Messages/Content/__tests__/ProgressText.cortex.test.tsx`, and `api/server/services/viventium/__tests__/BackgroundCortexFollowUpService.spec.js`.
- Last run: 2026-05-17 live runtime sanity - passed for new turns; legacy bad message remains in history as past evidence, not current behavior.

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for No Response. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `NTA-UC-001` | On Web chat, persisted message state, verify that web silent turn suppression. | owning requirement for `NTA-001` / `NTA-001` | Web chat, persisted message state | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to NTA-001. | The visible result for NTA-001 matches the documented requirement. | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
| `NTA-UC-002` | On Voice/listen-only transcript and final output, try voice/listen-only silence with missing setup, missing auth/config, empty state, or a degraded dependency. | owning requirement for `NTA-002` / `NTA-002` | Voice/listen-only transcript and final output | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to NTA-002. | The user sees an honest setup, retry, or degraded-state result for NTA-002; no fake success is accepted. | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
| `NTA-UC-003` | After errors are never hidden, refresh, restart, retry, or switch linked surfaces and verify persistence/parity. | owning requirement for `NTA-003` / `NTA-003` | Web/Telegram/voice final output and logs summary | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to NTA-003. | NTA-003 remains correct after the persistence or parity step and final wording matches evidence. | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
