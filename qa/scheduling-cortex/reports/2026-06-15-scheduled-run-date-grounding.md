<!-- qa-evidence-exempt: legacy sanitized RCA/QA note retained for historical context; current acceptance must use cases plus a fresh v2 report. -->

# Scheduled Run Date Grounding QA

Date: 2026-06-15
Case: `SCHED-013` / `SCHED-UC-013`
Result: PASS for deterministic date grounding, date guard ledger, Telegram delivery, same-conversation prior-date contamination path, and stream-final completion. PARTIAL pending the next natural private daily run.

## Scope

This QA verifies the scheduled briefing bug class where a daily morning-style schedule can reuse or infer the wrong day label. The tested fix grounds scheduled runs with deterministic due-date context and an explicit ISO due-date tag, requires verified tool/cortex evidence for live calendar/email/task facts, records a narrow leading-date guard in the delivery ledger, and prevents final-only SSE streams from leaving successful scheduled runs stuck in `running`.

The full private morning briefing content was not copied into this report. The live user path was exercised with public-safe synthetic scheduled prompts delivered through the same scheduler, LibreChat, Telegram, Mongo, and same-conversation delivery path.

## Evidence

Automated checks:

- PASS: scheduling cortex dispatch suite, 58 tests.
- PASS: LibreChat API focused suites, 3 suites / 80 tests.
- PASS: config compiler timezone subset, 3 tests.
- PASS: Python compile for scheduler dispatch and config compiler.

Runtime health:

- Scheduler health returned OK on the isolated runtime after restart.
- The running scheduler process used the checked-out scheduling-cortex directory.
- Telegram bridge and LibreChat API were running.
- Final `bin/viventium status` showed Scheduler, Telegram Bridge, LibreChat API, Google Workspace
  MCP, and Microsoft 365 MCP running.
- Residual environment issue: the broader runtime still reported attention needed for primary
  connected-account setup/verification and Conversation Recall. These are not blockers for
  deterministic scheduled date grounding, but they remain relevant to live Office-backed facts.

Live scheduler QA:

- PASS: New-conversation synthetic schedule delivered to LibreChat and Telegram.
  - Generated text: `Monday, June 15, 2026 - synthetic fast completion date grounding check passed.`
  - Ledger: `last_status=success`, `last_delivery_outcome=sent`, both `librechat` and `telegram` channel outcomes `sent`.
  - Date guard: expected and claimed `Monday, June 15, 2026`; status `passed`.
  - Mongo persisted the same assistant text.
  - Computer Use confirmed the visible Telegram message.

- PASS: Same-conversation synthetic schedule reused the real daily morning briefing conversation.
  - Generated text: `Monday, June 15, 2026 - synthetic same-conversation date grounding check passed.`
  - Ledger: `last_status=success`, `last_delivery_outcome=sent`, both `librechat` and `telegram` channel outcomes `sent`.
  - Date guard: expected and claimed `Monday, June 15, 2026`; status `passed`.
  - LibreChat logs showed scheduler request, stream creation, final event, and job completion in the same real daily conversation.
  - Mongo persisted the same assistant text in that conversation.
  - Computer Use confirmed the visible Telegram message.

- PASS: Post-Claude simplification path.
  - ClaudeViv review found that mutating only persisted `message.text` would not reliably update
    agent history stored in message content parts, so the old-message correction route was removed.
  - The current design relies on deterministic `schedulerRunContext`, the explicit
    `scheduled_due_local_date_iso` tag, and current-delivery date-guard metadata rather than
    mutating prior conversation messages.
  - Focused scheduler dispatch regression verifies that a leading wrong opening date is corrected
    for the current delivery without calling any persisted-history correction endpoint.
  - Focused guard regression verifies that a first-line event date is not rewritten when it is not
    the leading opening date label.
  - A deliberately wrong-date live model prompt returned `{NTA}` under the scheduler no-response
    contract, so it did not exercise the live model correction branch.

- PASS: Post-simplification live date-tag run on 2026-06-16.
  - Generated text: `2026-06-15 simplified date tag grounding check passed.`
  - The run fired while the host date was 2026-06-16 in Europe/Amsterdam, but the schedule timezone
    was America/Los_Angeles, so the correct schedule-local ISO tag was `2026-06-15`.
  - Ledger: `last_status=success`, `last_delivery_outcome=sent`, both `librechat` and `telegram`
    channel outcomes `sent`.
  - Date guard: `no_opening_date_claim` with expected human label `Monday, June 15, 2026`, because
    this test intentionally used the ISO date tag instead of a human opening date label.
  - Mongo persisted both `text` and `content[]` with the delivered ISO-tag message for the new run.
  - Computer Use confirmed the Viventium Telegram chat list preview showed the delivered ISO-tag
    message. Telegram row-click accessibility returned an AX not-implemented error, so the message
    was not reopened in detail view during this rerun.

- PASS: Temporary synthetic QA rows were inactive after execution and did not remain scheduled.

Second-opinion review:

- PASS/PARTIAL: ClaudeViv review-only pass approved the RCA/fix direction after checking the
  due-date anchoring, scheduler request payload, system time-context path, and SSE
  stream-completion change.
- ClaudeViv identified two important simplification/fix points: do not mutate old messages via a
  text-only correction route, and do not let the guard rewrite arbitrary first-line event dates.
  The implementation was updated to remove old-message mutation and narrow the guard to leading
  opening date labels.

## Findings

The original failure mode is addressed structurally rather than with prompt keyword branching:

- Scheduler dispatch now builds a deterministic scheduled-run context from due time, schedule timezone, and run time.
- The context is injected into the scheduled prompt and also sent as structured `schedulerRunContext` to LibreChat, including `scheduled_due_local_date_iso`.
- LibreChat time-context instructions repeat the deterministic due date/window when present.
- Morning briefing bootstrap wording now requires verified tool/cortex evidence for calendar/email/task/current-day facts.
- A delivery date guard records whether the leading opening date claim matched the deterministic due date, and can correct that current delivery mismatch.
- The implementation does not mutate prior persisted conversation messages.
- Scheduler/Telegram stream readers stop on final events and rely on the existing follow-up poll path, avoiding successful final-only runs sitting open on SSE linger.

## Remaining Gaps

- The next natural daily private briefing after the change has not yet occurred. The same owning path was invoked live with public-safe content, including the real same conversation, but a natural full-content daily run should still be watched on its next scheduled occurrence.
- Existing live daily schedule timezone remains `America/Los_Angeles`. The code now anchors to the configured schedule timezone; it does not silently migrate live user-managed schedule state.
- Office-backed content quality still depends on Microsoft/Google MCP auth and connected-account
  health. The fix prevents unsupported live-fact claims, but it does not repair expired OAuth or
  degraded recall services.

## Public/Private Safety

No private briefing text, Telegram thread content, personal identifiers, local home-directory paths, OAuth URLs, tokens, or secret-bearing logs are included in this report.
