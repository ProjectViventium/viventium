# Prompt Workbench PW-050 QA Run - 2026-08-28

## Summary

- Result: PARTIAL
- Build/source under test: source worktree for the nonterminal View / Steer receipt repair
- Runtime/artifact under test: source and automated harness only; not compiled or installed
- Environment: local source test environment
- Tester: automated harness with documentation reconciliation
- Related change: canonical nonterminal mission-control label and receipt-binding evidence

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `PW-050` | PARTIAL | 39 focused, 190 GlassHive MCP-server, and 77 exact-model/installed-journey harness checks passed | Required installed browser label, compiled artifact, and exact configured Main rerun were not run. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `PW-UC-050` | Launch durable work and open its nonterminal View / Steer link. | No real browser surface; source and automated harness only. | PARTIAL | No installed visible label was observed. | Typed launch metadata and sanitized URL/receipt binding hashes passed focused checks. | Compile, install, activate, run one configured Main launch, inspect the visible label, and verify refresh binding. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: Prompt Workbench nonterminal mission-control receipt truth
- Requirement: Visible View / Steer links must bind to the exact launch receipt without exposing raw private URLs.
- Use case: A user launches durable work and opens the correct nonterminal mission-control surface.
- QA case: `PW-050` / `PW-UC-050`
- Expected result: One canonical View / Steer label and a typed receipt-to-URL binding for that launch.
- Actual evidence: Source and automated suites passed; no installed visible-surface proof exists.
- Remaining gap or fix: Compile and activate the source, rerun one exact configured Main case, inspect the installed browser label, and verify reload persistence.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | `PW-050` / `PW-UC-050`; partial source proof only. |
| Code owning path | Which code path owns the behavior? | Typed GlassHive launch metadata, mission-control link projection, and exact-model evidence adapter. |
| Docs and nested docs/repos | Which docs or nested repo docs define the expected behavior? | Prompt architecture owner, Prompt Workbench cases, and nested GlassHive MCP contract. |
| Scripts or harnesses | Which scripts, fixtures, QA harnesses, or automated suites exercised it? | Focused launch/View/Steer/continue, MCP-server, and exact-model journey suites. |
| Local/external prerequisite state | Which required prerequisite was proven healthy or degraded? | Source test prerequisites passed; compiled and installed candidate state was not established. |
| Logs | Which sanitized logs confirm or contradict the result? | A read-only projection recorded two scoped receipts, two present URLs, and distinct binding hashes without raw URLs. |
| DB/state/persistence | Which persisted state confirms it? | Automated typed receipt state passed; installed reload persistence was not run. |
| Generated/shipped artifact | Which generated or installed artifact was inspected? | None; this is the reason the result is PARTIAL. |
| Real user path | Which browser or other user path was used? | None; the required installed LibreChat browser path was not run. |
| Visual/UX comparison | Does the visible label match the contract? | Not observed on an installed build. |
| Not run / blocked | Which required surface was not run? | Compile, activation, exact configured Main launch, browser label inspection, and reload. Supporting evidence cannot replace required user-path evidence. |

## User-Grade Evidence

- Surface exercised: Source and automated harness only; the required installed LibreChat browser was not exercised.
- Real user path: Not run; an installed Main launch and visible View / Steer link remain required.
- Visible outcome: Not observed on an installed surface.
- Expanded/detail state: Not inspected in a real browser.
- Persistence/reload result: Not run on an installed candidate.
- Local/external prerequisite state: Source test prerequisites were available; installed artifact identity was not established.
- Backend/log/DB confirmation: Sanitized automated evidence recorded two independent receipts, two URL-presence flags, distinct URL hashes, and distinct binding hashes.
- Final model/runtime wording check: Not run on the exact configured installed Main.
- Substitution check: Logs, DB rows, API responses, source inspection, model completions, and unit tests are supporting evidence, not substitutes for any required visible-UI, detail-state, persistence, or wording step.

## Automated Evidence

The original exact command strings were not retained in this report. The retained sanitized results
are: 39 focused launch/View/Steer/continue checks passed, 190 GlassHive MCP-server checks passed,
and 77 exact-model and installed-journey harness checks passed. This omission prevents treating the
report as reproducible release evidence.

## Findings

- Defects: The old generic labels and missing structured mission-control state were repaired in source.
- Regressions: None found in the retained automated results.
- Flakes: None recorded.
- Environment issues: Broad Ruff output contains 57 pre-existing findings across two touched Python files.
- Residual risks: Source is not compiled, installed, activated, or accepted through the real browser path; exact commands were not retained.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
