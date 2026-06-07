# Background Agents QA Cases

The durable case bank for background agents currently lives in:

- [`03_eval_prompt_bank.md`](03_eval_prompt_bank.md) - ACT case definitions and expected behavior
- [`05_coverage_matrix.md`](05_coverage_matrix.md) - agent-to-case coverage and interpretation
- dated reports in this folder - execution evidence and incident-specific RCA

Use this file as the QA catalog entrypoint so future agents do not miss the existing ACT cases.
When adding a new production-miss regression, add the case to `03_eval_prompt_bank.md`, update
`05_coverage_matrix.md`, and add the short metadata entry here.

## Current Case Families

| Case Range | Scope | Required Evidence |
| --- | --- | --- |
| `ACT-01` - `ACT-12` | Baseline activation, negative controls, and productivity-agent boundaries | Activation result plus affected runtime assertions |
| `ACT-13` - `ACT-17` | Promoted outcome regressions for classifier and Phase A/B behavior | User-visible result, persistence, and backend/log confirmation |
| `ACT-18` | Runtime background-card visibility must not be contradicted by the main answer | Full browser loop, named cards, persistence/DB confirmation, wording check |
| `ACT-19` | Main answer must not offer to start background work that is already requested/running | Full browser loop, named cards, persistence/DB confirmation, forbidden wording check |
| `ACT-20` | Background cards must never erase the original Phase A answer | Full browser loop, parent-message text survival, named cards, reload persistence, cortex-only parent failure |
| `ACT-21` | Activation detection must judge the latest user message, not stale history | Multi-turn browser/API loop, latest-message prompt evidence, no duplicate stale activation cards |
| `ACT-22` | Browser QA must classify visible environment/auth blocks instead of timing out vaguely | Visible UI error capture, sanitized block reason, no false activation verdict |
| `ACT-23` | Deferred tool-cortex hold/follow-up must not render a generic connection/provider error card | Real browser loop, parent/follow-up persistence, DB content check, backend log confirmation |
| `ACT-24` | Productivity cortices must retain provider-owned MCP tools | Source/live tool arrays, connected-account runtime evidence, provider tool-call completion, user-visible inbox synthesis |
| `ACT-25` | Generic plural inbox sweep activates both provider-owned productivity cortices | Activation prompt evidence, browser cards, DB parts, logs, single-provider negative controls |
| `ACT-26` | Phase B provider-stage failures preserve metadata and retry fallback | Runtime unit test, fallback log evidence, persisted cortex error metadata, non-retryable tool/auth controls |
| `ACT-27` | Broker-first local baseline disables Deep Research/MS365/Google main-agent background activation | Source/live activation flags, no retired specialist cards, direct-tool or GlassHive broker evidence, visible limitation wording; does not replace the GlassHive broker shadow-parity gate |
| `ACT-28` | Async-OFF detection early-exits when all results are in (text 1300ms / voice 690ms budget), never burning the full budget | Detection trace duration < budget when classifiers resolve fast; Phase A injected; per-mode budget evidence |
| `ACT-29` | Async-ON no-activation: speculative answer stands as Phase A; detection wait overlapped; single delivery, no double-bill, no redo | Timing trace (main started before detection done), exactly-once delivery/billing |
| `ACT-30` | Async-ON activation within budget: "nevermind" cancel + Phase A re-run with awareness; cards shown; Phase B follow-up; discarded speculative never delivered/billed | Trace showing abort+redo, named cards, follow-up persistence, exactly-once delivery |
| `ACT-31` | Mode independence + direct-action fail-closed: voice flag never changes text (and vice versa); a direct-action cortex forces the blocking path even with async ON | Per-mode config evidence, blocking-path taken for direct-action cortex, no cross-mode bleed |
| `ACT-32` | Phase B terminal decisions are durable and surface-visible even when no follow-up text should be sent | Browser/log/DB proof of `generated`, `suppressed`, `empty`, or `skipped` decision metadata; voice and Telegram pollers stop waiting on terminal silent decisions |
| `ACT-33` | Main-agent provider rate limits before visible text use a configured fallback or a classified blocker, not raw provider plumbing | Browser-visible answer/blocker, live agent fallback config, backend log class, persisted message content, and no raw `MODEL_RATE_LIMIT`/LangChain troubleshooting bubble |

## Required User-Grade Loop For Card Regressions

For any background-agent Web UI change, QA must prove:

- real browser prompt/action was used, not only an API call or model completion
- activated background agents are visible by name in cards or rows
- expanded cards show why/result/status/error details as applicable
- refresh/reload preserves completed terminal results when persistence is required
- stored `messages.content` cortex parts match the visible browser state
- the originating assistant parent message keeps visible Phase A answer text unless the turn
  intentionally produced a structured no-visible-answer marker such as `{NTA}`
- if provider fallback/exhaustion means no visible Phase A text ever materialized, a forced Phase B
  synthesis may be promoted onto the otherwise empty canonical parent; QA must still prove the
  parent has visible answer text plus structured cortex parts after reload
- a parent assistant message with only cortex parts and no text is a failure, even if a later Phase B
  follow-up message looks good
- logs or DB confirm completion, fallback, or terminal error state
- `{NTA}`, empty, skipped, and generated Phase B follow-up outcomes persist a structured terminal
  decision so web, voice, Telegram, and QA can distinguish "nothing useful to add" from "Phase B
  never finished"
- the main answer does not claim background work has not started, cannot be shown, or needs to be
  spun up when runtime cards are already visible or requested
- activation detection cases with history must prove the latest user message is the decision
  subject. Older activation-worthy user turns may be included as context, but they must not produce
  fresh cards when the latest user turn is only a simple reply, test instruction, correction,
  provider clarification, or output-only command such as an exact-marker response check.
- browser QA must classify visible login, connected-account, and generation-environment blockers
  as blocked evidence with a sanitized reason. A provider/auth block must not be reported as an
  activation failure, and a blocked browser run does not satisfy outcome signoff.
- deferred tool-cortex hold turns must not show a generic browser connection/provider error when a
  successful Phase B follow-up exists; stored parent content must not retain stale `completion_error`
  or `late_stream_termination` parts after recovery.
- productivity cortices must initialize with their owned Google Workspace or MS365 MCP tool arrays
  whenever those cortices activate for live inbox/status work; recall-only output is a degraded path,
  not a passing live-account result.

## Incident Promotion Checklist

- [ ] Convert private/raw user text into a synthetic public-safe prompt.
- [ ] Add the expected activation/result behavior to `03_eval_prompt_bank.md`.
- [ ] Add positive and negative controls if the case depends on subtle intent or context.
- [ ] Update `05_coverage_matrix.md`.
- [ ] Add or update an automated test where deterministic checks are possible.
- [ ] Run impacted existing ACT cases and save a dated public-safe report.

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Background Agents. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `BACKGROUND-UC-001` | Send a synthetic browser chat prompt that should activate background work and inspect the visible answer plus background cards. | `ACT-01`-`ACT-23` / background-card requirements | Real browser chat, expanded background cards, persisted message detail, and backend logs/DB | ACT prompt bank, coverage matrix, visible cards, stored message parts, logs, and dated QA report | The initial answer remains visible, background cards show status/result/error details, and the main answer does not contradict visible runtime cards. | NOT YET RUN for the full bank after catalog repair; required before next background-agent signoff |
| `BACKGROUND-UC-002` | Send synthetic negative-control prompts, auth/provider-blocked prompts, and latest-message-history prompts. | `ACT-01`-`ACT-23` / activation and blocker requirements | Real browser chat plus logs/DB state | ACT prompt bank, classifier/runtime assertions, visible blocker copy, stored message parts, and logs | Non-activation prompts do not create stale cards; provider/auth blocks are classified as blocked evidence, not feature failures or fake successes. | NOT YET RUN for the full bank after catalog repair; required before next background-agent signoff |
| `BACKGROUND-UC-003` | Refresh the conversation after completed background work and compare visible cards, answer text, and persisted message content. | `ACT-18`-`ACT-23` / persistence requirements | Browser refresh/reload, expanded cards, stored message state, and backend logs | Stored message content, visible card text, parent assistant message text, logs, and dated QA report | Completed terminal results persist, the parent message keeps visible answer text, and DB/log evidence agrees with the browser state. | NOT YET RUN for the full bank after catalog repair; required before next background-agent signoff |
| `BACKGROUND-UC-004` | Trigger or fixture a deferred tool-cortex hold with a successful follow-up and verify no generic connection/provider error is visible. | `ACT-23` / deferred direct-action handoff | Real browser chat or synthetic browser fixture, refresh, DB parent/follow-up check, backend logs | Stored parent content, follow-up metadata, visible browser state, and dated QA report | Runtime hold and follow-up are visible as a continuing background workflow; stale parent `completion_error`/`late_stream_termination` content is removed or never persisted. | 2026-05-21 PASS for synthetic fixture and live Telegram; see `reports/2026-05-21-telegram-productivity-provider-routing.md` |
| `BACKGROUND-UC-005` | Ask for a live inbox/status rundown while productivity cortices are enabled and verify provider tools actually run. | `ACT-24`, `ACT-25`, `ACT-26` / productivity provider tools | Real Telegram or browser chat with connected accounts, backend logs, DB content parts, source/live agent tool arrays | Source bundle, live Mongo agent rows, prompt-frame telemetry, provider tool-call counts, fallback logs, visible result wording | When productivity cortices are intentionally enabled, MS365 and Google run with owned MCP tools and current-run evidence; final answer does not pretend recall-only evidence is a live inbox read; pre-tool provider failures preserve metadata and retry configured fallback. | 2026-05-27 PASS before broker-first retirement: generic browser inbox prompt activated both cortices; Google and MS365 each completed current-run live tool evidence after provider fallback. See `reports/2026-05-27-google-ms365-background-activation.md` |
| `BACKGROUND-UC-006` | Ask for combined web research, Google inbox, MS365 inbox, and confirmation-bias review after broker-first local soft-retirement. | `ACT-27` / GlassHive broker-first soft-retirement; full broker replacement parity remains tracked by `qa/glasshive-mcp-capability-broker/cases.md` `GH-MCP-BROKER-007` | Real browser, Telegram, and voice surfaces where available, plus live source/DB config and backend logs | Source bundle, live Mongo agent row, visible card names, stored message parts, GlassHive/direct-tool evidence, logs | `Deep Research`, `MS365`, and `Google` do not appear as background cards; `Confirmation Bias` may still appear for independent bias review; provider/research work is handled by main/direct tools or reported as a verified limitation. | 2026-05-27 PASS for browser, Telegram bridge, and LiveKit playground typed transcript: no retired background cards/parts; no background-cortex promise after prompt hardening; GlassHive/direct-tool or limitation evidence present. LiveKit evidence is typed-transcript scope, not audible-call QA, because ACT-27 changes activation/config routing rather than voice audio behavior. This proves the local no-retired-background-agent behavior, not permanent broker parity/removal readiness. See `reports/2026-05-27-act27-broker-retirement-browser.md`, `reports/2026-05-27-act27-broker-retirement-telegram.md`, and `reports/2026-05-27-act27-broker-retirement-livekit.md` |
| `BACKGROUND-UC-007` | Trigger or fixture a main-agent provider `429`/`MODEL_RATE_LIMIT` before any visible text. | `ACT-33` / user-facing provider-class error and main-agent fallback contract | Real browser chat or deterministic runtime fixture, live agent config, backend logs, stored message content | Agent primary/fallback route fields, fallback retry log or classified blocker log, persisted assistant content, browser-visible result | A valid configured fallback produces the answer; otherwise the assistant shows a concise provider-class blocker. The user must not see raw LangChain troubleshooting URLs, internal stack/plumbing, or an empty assistant message with only an error part. | PUBLIC-SAFE LOCAL RUN PENDING after 2026-06-04 incident promotion; private enterprise deployment evidence stored outside repo |

## Release Test Traceability

- `tests/release/test_background_agent_browser_qa_harness.py`
- `tests/release/test_background_agent_governance_contract.py`
- `tests/release/test_scheduling_mcp_supervision.py`
