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
- the main answer does not claim background work has not started, cannot be shown, or needs to be
  spun up when runtime cards are already visible or requested
- activation detection cases with history must prove the latest user message is the decision
  subject. Older activation-worthy user turns may be included as context, but they must not produce
  fresh cards when the latest user turn is only a simple reply, test instruction, correction,
  provider clarification, or output-only command.
- browser QA must classify visible login, connected-account, and generation-environment blockers
  as blocked evidence with a sanitized reason. A provider/auth block must not be reported as an
  activation failure, and a blocked browser run does not satisfy outcome signoff.

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
| `BACKGROUND-UC-001` | Send a synthetic browser chat prompt that should activate background work and inspect the visible answer plus background cards. | `ACT-01`-`ACT-22` / background-card requirements | Real browser chat, expanded background cards, persisted message detail, and backend logs/DB | ACT prompt bank, coverage matrix, visible cards, stored message parts, logs, and dated QA report | The initial answer remains visible, background cards show status/result/error details, and the main answer does not contradict visible runtime cards. | NOT YET RUN for the full bank after catalog repair; required before next background-agent signoff |
| `BACKGROUND-UC-002` | Send synthetic negative-control prompts, auth/provider-blocked prompts, and latest-message-history prompts. | `ACT-01`-`ACT-22` / activation and blocker requirements | Real browser chat plus logs/DB state | ACT prompt bank, classifier/runtime assertions, visible blocker copy, stored message parts, and logs | Non-activation prompts do not create stale cards; provider/auth blocks are classified as blocked evidence, not feature failures or fake successes. | NOT YET RUN for the full bank after catalog repair; required before next background-agent signoff |
| `BACKGROUND-UC-003` | Refresh the conversation after completed background work and compare visible cards, answer text, and persisted message content. | `ACT-18`-`ACT-22` / persistence requirements | Browser refresh/reload, expanded cards, stored message state, and backend logs | Stored message content, visible card text, parent assistant message text, logs, and dated QA report | Completed terminal results persist, the parent message keeps visible answer text, and DB/log evidence agrees with the browser state. | NOT YET RUN for the full bank after catalog repair; required before next background-agent signoff |

## Release Test Traceability

- `tests/release/test_background_agent_browser_qa_harness.py`
- `tests/release/test_background_agent_governance_contract.py`
- `tests/release/test_scheduling_mcp_supervision.py`
