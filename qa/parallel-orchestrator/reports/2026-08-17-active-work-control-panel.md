# Active Work Control Panel Placement QA Run - 2026-08-17

## Summary

- Result: **PARTIAL** for the broader Active Work feature; **PASS** for the source-level placement,
  real empty state, visual state matrix, narrow layout, keyboard behavior, polling lifecycle, and
  reload persistence exercised in this run.
- Build/source under test: current source checkout in an isolated local development environment.
- Runtime/artifact under test: local Web client and real local API for the empty-state branch;
  public-safe intercepted read data for the visual state matrix.
- Environment: isolated local development with a synthetic non-admin QA account.
- Tester: Codex through a real headed browser.
- Related change: move live Active Work status and controls from Settings into a first-class section
  in the right Control Panel while retaining the account-wide Parallel Work preference in Settings.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `PWK-004` | PARTIAL | Visible hierarchy and real empty state passed | Real stale/unavailable and rollback branches were not run |
| `PWK-016` | PASS for placement scope | Closed-section request count stayed unchanged for six seconds | Broader latency budgets remain owned by later runs |
| `PWK-018` | PARTIAL | Current source rendered and persisted the section state | Shipped artifact, clean install, and rollback were not run |
| `PWK-UC-002` | PARTIAL | Real empty state plus synthetic full state matrix in light/dark themes | Telegram, Voice, stale/unavailable, and rollback parity remain |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `PWK-UC-002-A` | Open Active Work with no current work | Headed Web browser and real local API | PASS | `Live status` and `No active work.` were visible | Real API returned the empty roster | None for this branch |
| `PWK-UC-002-B` | Inspect representative running, attention, paused, queued, terminal, and overflow states | Headed Web browser with intercepted public-safe read data | PASS for visual rendering | Every supplied state rendered distinctly in light and dark themes | The interception affected only the roster read; no action endpoint ran | Repeat with real stale/unavailable and active records |
| `PWK-UC-002-C` | Use the section at narrow width and by keyboard | Headed Web browser | PASS | No horizontal overflow at a 351 px panel; Enter opened and closed the section | Content and scroll width both measured 327 px; browser console had zero errors | None for this branch |
| `PWK-UC-002-D` | Close the section and reload the page | Headed Web browser | PASS | Closed state stopped polling; open state survived reload and returned to the real empty roster | Request count stayed unchanged during the closed interval | None for this branch |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: Parallel Work Active Work roster and controls.
- Requirement: live work belongs in the right Control Panel; Settings retains only the account-wide
  preference and Connected Accounts.
- Use case: inspect work without leaving the conversation, including empty, varied status, narrow,
  keyboard, closed, and reload states.
- QA case: `PWK-004`, `PWK-016`, `PWK-018`, and `PWK-UC-002`.
- Expected result: Control Panel hierarchy and state remain legible, keyboard operable, free of
  horizontal overflow, and persistent without background polling while closed.
- Actual evidence: real headed-browser empty-state, navigation, keyboard, narrow-width, polling, and
  reload checks passed; a public-safe intercepted read rendered the complete visual state matrix.
- Remaining gap or fix: run real stale/unavailable records, rollback with existing work, and
  Telegram/Voice parity before calling the full feature accepted.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | Control Panel placement and `PWK-UC-002` branches linked above |
| Code owning path | Which code path owns the behavior? | Control Panel navigation, roster query gating, settings separation, and roster rendering in the Web client |
| Docs and nested docs/repos | Which docs define expected behavior? | Parallel Work requirement and `qa/parallel-orchestrator/cases.md` |
| Scripts or harnesses | Which suites exercised it? | Focused navigation/query/settings/roster/action tests, full client regression, production build, lint, and formatting checks |
| Local/external prerequisite state | Which dependency was healthy or degraded? | Local Web and API were available; external providers were not required for this placement run |
| Logs | Which sanitized logs confirm or contradict the result? | Browser console recorded zero errors and one unrelated future-flag warning |
| DB/state/persistence | Which persisted state confirms it? | Open-section preference survived page reload; no roster action mutation was invoked |
| Generated/shipped artifact | Which generated or shipped artifact was inspected? | Source-built development client only; no installed/prebuilt artifact claim |
| Real user path | Which real surface was used? | Headed browser opened Control Panel, Settings, Active Work, keyboard states, and a page reload |
| Visual/UX comparison | Did visible state match supporting evidence? | Yes for placement, empty state, supplied state matrix, narrow layout, themes, keyboard, and polling lifecycle |
| Not run / blocked | Which required surface was not run? | Real stale/unavailable, rollback, Telegram, Voice, and shipped-artifact parity |

Supporting evidence cannot replace required user-path evidence. Unrun real-state and cross-surface
branches remain `PARTIAL` even though source automation and the intercepted visual matrix passed.

## User-Grade Evidence

- Surface exercised: real headed Web browser against the local development client and API.
- Real user path: opened the Control Panel and Active Work, inspected the real empty state, opened
  Settings to confirm separation, exercised public-safe visual states, used Enter, closed the
  section, waited six seconds, reopened it, and reloaded the page.
- Visible outcome: hierarchy was Agent Builder, Active Work, Prompts, Feelings, Memories; Settings
  contained the preference and Connected Accounts without live cards; all supplied work states were
  distinct and the narrow panel did not overflow.
- Expanded/detail state: Active Work expanded correctly, showed the state matrix, and exposed the
  expected expanded state to keyboard focus.
- Persistence/reload result: the open section remained open after reload and returned to the real
  empty state after read interception was removed.
- Local/external prerequisite state: local Web and API were healthy; no connected account or model
  provider was needed.
- Evidence retrieval classification, if applicable: not applicable; this was a local UI/state run.
- Fallback path, if applicable: not applicable.
- Backend/log/DB confirmation: the real API supplied the empty roster, request counting proved no
  polling while closed, and the browser console showed zero errors.
- Final model/runtime wording check: visible labels accurately distinguished `Live status` from the
  empty roster and did not claim that synthetic states were real work.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit
  tests are supporting evidence, not substitutes for any required visible-UI, detail-state,
  persistence, or wording step.

## Automated Evidence

- Focused navigation, query-gating, settings, roster, action-idempotency, and long-label tests:
  **26 passed**.
- Full client regression: **142 suites / 1,458 tests passed**.
- Production bundle build, touched-file lint, and formatting checks passed.
- Repository-wide type checking still reported unrelated existing diagnostics; none referenced the
  files changed for this placement.

## Findings

- Defects: no placement-specific defect remained in the final run.
- Regressions: no affected automated regression remained.
- Flakes: none observed.
- Environment issues: none for the local placement branch.
- Residual risks: real stale/unavailable network states, rollback with existing work, installed
  artifact parity, and Telegram/Voice parity remain unaccepted.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, timestamps, and conclusions only.
