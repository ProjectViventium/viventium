# Retired-Origin Callback QA — 2026-10-03

## Summary

- Result: PARTIAL for `PWK-UC-013`; the full journey keeps its existing open surface gates.
- Candidate: [`3dddc9dc`](https://github.com/ProjectViventium/viventium-librechat/commit/3dddc9dc7243cbd440e321e0476cee8b1149b622), the reviewed callback cleanup guard and empty-schedule adapter change merged in [component PR #126](https://github.com/ProjectViventium/viventium-librechat/pull/126).
- Artifact: the native LibreChat API package build completed from this change set. Component
  publication is merged, with the parent pin included in this change; this is not release certification.
- QA mode: critical-path. Synthetic expectations below describe the reusable case; private account
  data, recovery material and source hashes are omitted.

## Scope Run

| Contract | Result | Evidence |
| --- | --- | --- |
| Exact maintenance cleanup suppresses callback presentation before status persistence/synthesis and again inside the authored transaction. | PASS supporting evidence | 16 focused callback route, binding and adjudication cases. |
| Ordinary deleted-origin account continuation and foreign-owner isolation remain available. | PASS supporting evidence | Existing positive/negative callback cases and native transaction probes. |
| Empty schedule target sets skip the unused native bridge; nonempty verification stays strict. | PASS supporting evidence | 8 cleanup adapter tests, including a mock proving no spawn for an empty set; independent compiled native verification. |
| Native cleanup guard reads exact Mongo transaction state. | PASS supporting evidence | Four actual transaction probes: retired conversation, retired anchor, retained source and foreign owner. |
| Native delayed cleanup lifecycle and retained personal data. | PASS for this local maintenance branch | Real delayed verification completed through the source, search, recall, schedule, memory and nonce guards. Retained chat remained visible after browser reload. |
| Complete owning callback bank. | PASS | All 249 cases passed across the three existing callback banks. |
| Complete `PWK-UC-013` user journey. | PARTIAL | Archive/delete/restart/silence across installed Web/Telegram and audible Voice remains open. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: Parallel Work completion after its origin changes.
- Requirement: [`PW-109`](../../../docs/requirements_and_learnings/55_Parallel_Work_Orchestration.md).
- Use case and QA case: [`PWK-UC-013`](../cases.md), including reviewed maintenance cleanup.
- Expected result: retired owner-bound QA sources cannot create a status card or continuation;
  ordinary deletion retains useful Main-authored continuation without recreating the origin.
- Actual evidence: focused callback/adapter tests, native Mongo transaction checks, native package
  build, delayed lifecycle verification and retained-chat browser reload.
- Remaining gap: the complete installed surface journey; component publication is merged and this change records its parent pin.

## Full-View Evidence Checklist

| Evidence surface | Result |
| --- | --- |
| Code | Typed cleanup source guard; callback route; mission adjudication and binding; empty-schedule process adapter. |
| Docs and nested docs | Parallel Work `PW-109` owns behavior; `PWK-UC-013` owns the reusable case. |
| Logs, DB/state/persistence | Callback suppression, exact transaction probes and native delayed verification support the maintenance branch. Original failed verification evidence stays retained. |
| Generated/shipped artifact | Native API build passed; the reviewed component is merged and this change records its parent pin. Publication formatting preserves the reviewed source AST. |
| Real user path | A retained personal chat stayed visible after browser reload. The complete callback journey was not rerun through every channel. |
| Remaining gates | Full installed surface evidence remains PARTIAL; an unavailable required path must be reported BLOCKED. Supporting checks cannot replace required user-path evidence. |

## User-Grade Evidence

- Surface exercised: local browser retained-chat reload and native maintenance API lifecycle.
- Real user path: reload an existing retained chat after reviewed cleanup, then complete the delayed
  native verification without starting a new personal AI turn.
- Visible outcome: retained chat remained visible; no personal message or memory preservation claim
  depends on synthetic test data alone.
- Expanded/detail state: exact callback suppression and cleanup state were inspected through native
  receipts; the full Active Work and audible Voice detail journey was not run for this candidate.
- Persistence/reload result: retained personal data passed exact preservation checks and the chat
  remained visible after reload. Delayed source/search/recall/schedule/memory/nonce verification passed.
- Backend/log/DB confirmation: focused source tests, native transaction probes and the delayed native
  lifecycle agree with the structural guard. The original failed sweep was not rewritten.
- Final model/runtime wording check: no new personal AI turn or cross-channel callback wording was
  evaluated; ordinary continuation has supporting regression evidence.
- Substitution check: unit, native transaction, build and receipt evidence support this repair;
  they do not replace the remaining installed Web/Telegram/audible Voice journey.

## Automated Evidence

- Focused callback cases: 16 passed; the remaining cases in the 249-case owning bank were not run in
  that first focused selection; the later complete bank passed all 249 cases.
- Cleanup adapters: 8 passed. The empty-target case returns zero without spawning; all nonempty
  verification code is retained.
- Native Mongo transactions: all four guard cases passed against the compiled helper.
- Native API package build: passed. Hosted component build, lint and all automatic test checks passed.
- Parent manifest checks: all 14 passed; the new pin resolves to the component public main tip.
- Final owning callback bank: all 249 cases passed across the three existing suites. The cleanup adapter bank also passed all 8 cases.

Reusable synthetic inputs are a retired conversation, a retired anchor in a retained conversation,
an ordinary deleted origin and a foreign owner. Use the existing callback route, binding and mission
adjudication suites in `viventium_v0_4/LibreChat/api`, and
`packages/api/src/cleanup/__tests__/cleanupAdapters.test.ts` for the empty schedule case. Avoid real
account data in fixtures.

## Findings

Maintenance cleanup is exact structured provenance, not a model intent rule. The host suppresses
presentation before status persistence or synthesis and rechecks inside the authored transaction.
Ordinary deleted-origin continuation remains available. An empty schedule set now avoids unnecessary
native schema initialization. The broader journey remains PARTIAL.

For actual account maintenance, first let reviewed QA producer work and delivery settle. The source guard does not replace that quiescence check after a reply has already been authored and before it is delivered.

## Public-Safety Review

Only public-safe synthetic expectations and aggregate test results are included. No owner IDs,
personal target counts, emails, client data, private paths, recovery material, source hashes or raw
logs are published.
