# Main-Agent Fallback Recovery QA Run - 2026-08-17

## Summary

- Result: **PASS** for the reported real Telegram fallback path; adjacent voice/background routing
  choices remain outside this incident.
- Build/source under test: current checkout after structured provider-failure, outer-fallback, and
  authored-content gating repairs.
- Runtime/artifact under test: installed local production rebound to the final source after the
  temporary synthetic fault seam was removed.
- Environment: local production with one public-safe synthetic fallback turn.
- Tester: Codex through Telegram Desktop plus supporting runtime, persistence, and GlassHive checks.
- Related change: preserve the recoverable GlassHive failure class, strip provider-internal nested
  fallback fields from outer fallback construction, and treat only content-bearing deltas as
  authorship.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `TR-005` | PASS for reported branch | One visible synthetic answer returned on the same Telegram turn through the configured Claude route | Other provider classes remain owned by their matrix |
| `TR-011` | PASS for reported branch | Primary error was not shown when the configured fallback succeeded | Honest terminal failure wording remains required when fallback also fails |
| Agent fallback class preservation | PASS | Structured `provider_response_failed` stayed retryable through the controller and send-completion path | The original incident was not proven to be quota exhaustion |
| Authorship gate | PASS | Contentless lifecycle/reasoning frames left recovery reachable | Content-bearing deltas still close the replay-safe boundary |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `TR-FALLBACK-UC-A` | Send a Telegram request whose primary fails before authoring | Telegram Desktop | PASS | The same turn returned one clean answer instead of the generic provider error | Primary failure preceded one Claude retry; no authored primary output existed | None for this incident branch |
| `TR-FALLBACK-UC-B` | Use the adjacent healthy primary path | Telegram Desktop | PASS | A neighboring healthy turn completed normally | Persistence and runtime logs showed the normal path | Broader provider-class matrix remains separate |
| `TR-FALLBACK-UC-C` | Restart from final source after removing the synthetic seam | Installed runtime and Telegram persistence | PASS | No QA fault remained active | API/Web health and the final persisted assistant row were healthy | Voice/background fallback design remains separate |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: Main Agent provider fallback continuity in Telegram.
- Requirement: before visible authorship, a recoverable primary failure switches once to the
  configured fallback; otherwise the user receives an honest provider-specific blocker.
- Use case: send one Telegram request during a recoverable provider failure and receive one answer
  without duplicate work or a leaked primary error.
- QA case: `TR-005`, `TR-011`, structured failure preservation, and content-bearing authorship gate.
- Expected result: exact failure class remains recoverable, outer fallback initializes without a
  false same-model rejection, and lifecycle frames do not suppress recovery.
- Actual evidence: one real Telegram reply, correlated primary-to-Claude runtime sequence, one
  completed GlassHive fallback run, and one complete non-error assistant row.
- Remaining gap or fix: voice and some background agents retain same-vendor or no-fallback authored
  configurations; changing them requires the normal live/source drift review, not this repair.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | Telegram bridge fallback contract and `TR-005`/`TR-011` |
| Code owning path | Which code path owns the behavior? | Agent callbacks, provider error classification, outer fallback construction, Agent endpoint initialization, and send-completion recovery |
| Docs and nested docs/repos | Which docs define expected behavior? | Key Principles, Telegram Bridge requirement, agent-config continuity and Telegram runtime QA cases |
| Scripts or harnesses | Which suites exercised it? | Controller, send-completion, fallback builder, callback/authorship, and provider-classification regressions |
| Local/external prerequisite state | Which dependency was healthy or degraded? | Primary was synthetically failed before authorship; configured Claude fallback and local Telegram/runtime path were healthy |
| Logs | Which sanitized logs confirm or contradict the result? | Primary structured failure was followed by exactly one Claude retry and no leaked primary answer |
| DB/state/persistence | Which persisted state confirms it? | Final assistant row was complete, non-error, and contained one fallback-recovery activity |
| Generated/shipped artifact | Which generated or shipped artifact was inspected? | Installed local runtime restarted from final source after removing the temporary seam; no release-pin claim |
| Real user path | Which real surface was used? | Telegram Desktop send/receive on the synthetic failure turn and an adjacent healthy turn |
| Visual/UX comparison | Did visible state match supporting evidence? | Yes: one clean visible answer matched one completed fallback run and one persisted assistant row |
| Not run / blocked | Which required surface was not run? | Unchanged Telegram Python sidecar suite lacked its Python test environment; voice/background route changes were out of scope |

Supporting evidence cannot replace required user-path evidence. The real Telegram send/receive path
was run; the unavailable unchanged sidecar suite and out-of-scope route designs are stated rather
than inferred as accepted.

## User-Grade Evidence

- Surface exercised: installed Telegram Desktop through the Viventium bot path.
- Real user path: sent one public-safe request under a temporary pre-authorship primary fault,
  observed the returned fallback answer, sent an adjacent healthy request, removed the seam, and
  validated/restarted local production from final source.
- Visible outcome: one clean answer appeared on the same Telegram turn; the generic primary error
  bubble did not appear on the successful recovery.
- Expanded/detail state: Telegram has no expandable fallback card; the complete visible reply bubble
  was inspected and contained one answer without duplicate or primary-error prose.
- Persistence/reload result: the final assistant row persisted as complete/non-error; after final
  restart API and Web health passed with the synthetic fault seam absent.
- Local/external prerequisite state: local Telegram/Core/GlassHive and configured fallback auth were
  healthy; the primary fault was controlled and removed after the run.
- Evidence retrieval classification, if applicable: recoverable `provider_response_failed` before
  authorship; not proven quota exhaustion.
- Fallback path, if applicable: outer Agent fallback switched once to the configured Claude route;
  provider-internal nested fallback metadata was not inherited.
- Backend/log/DB confirmation: runtime logs showed primary failure then one Claude retry; GlassHive
  recorded one completed fallback run and persistence recorded one recovery activity.
- Final model/runtime wording check: successful recovery showed only the useful answer; healthy
  adjacent behavior stayed normal and no misleading quota claim was made.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit
  tests are supporting evidence, not substitutes for any required visible-UI, detail-state,
  persistence, or wording step.

## Automated Evidence

- Affected automation: **286 tests across 5 suites passed**.
- Controller regression preserved the structured provider class.
- Send-completion regression routed the incident shape to the fallback.
- Fallback-builder regression removed only provider-internal nested fallback fields.
- Authorship regressions proved contentless message/reasoning frames leave fallback reachable.
- The unchanged Telegram Python sidecar suites were not rerun because their Python test environment
  was unavailable in this checkout; the report does not substitute other evidence for that gap.

## Findings

- Defects: the recoverable GlassHive class collapsed to `completion_error`; outer fallback inherited
  provider-internal fields and rejected itself as same-model; contentless lifecycle frames could
  falsely mark primary authorship. All three were repaired and regressed.
- Regressions: quota-exhaustion prose classification was also ordered before generic rate-limit
  classification so an empty balance cannot imply a short retry.
- Flakes: none observed in the final affected runs.
- Environment issues: unchanged sidecar suite environment was unavailable.
- Residual risks: same-vendor/no-fallback routes remain authored design choices outside this incident.
- Account hygiene: local private evidence was backed up before surgical QA cleanup; sanitized final
  audit recorded zero known QA-marker messages, zero bare-probe conversations, zero orphaned
  progress placeholders, and five intentionally preserved content-bearing orphan outputs.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, timestamps, and conclusions only.
