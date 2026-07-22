# Synthetic OpenAI Experimental Account-Bridge Lifecycle QA - 2026-07-20

## Summary

- Result: **PARTIAL**. The loopback provider contract passed; the browser lifecycle was not run.
- Build/source under test: current local release worktree and its synthetic lifecycle harness.
- Runtime/artifact under test: none. The integrated LibreChat candidate was unavailable.
- Environment: local loopback Node process; the reserved disposable macOS VM remained stopped.
- Tester: Codex local QA.
- Related change: synthetic compatibility coverage for the explicit experimental account bridge.
- Browser lifecycle: **NOT RUN**.

No real provider, cloud account, credential, personal state, external message, or installed runtime
was used or mutated. This report makes no claim about a visible grant, rendered answer, persistence,
refresh, local disconnect, or regrant result.

This bridge is not the Easy Install default or an official OpenAI integration. The supported Easy
Install API-key lifecycle remains a separate, unrun browser gate.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `INST-010` | PARTIAL | Harness contract and loopback provider self-test passed | The real browser consent and connected-state surface was not run. |
| `INST-017` | PARTIAL | One authorization-code exchange, one refresh, and one normalized Responses SSE request passed | The integrated installed/runtime artifact and real Chromium lifecycle remain untested. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `INST-017-UC-01` | Deny consent, cancel the popup, and retry | None; browser run intentionally deferred | BLOCKED | No UI evidence collected | Harness source and fail-closed contract tests only | Run against the integrated candidate in headed Chromium. |
| `INST-017-UC-02` | Grant a synthetic account and receive two useful answers | None; browser run intentionally deferred | BLOCKED | No rendered answers collected | Loopback OAuth and normalized Responses SSE self-test passed | Prove the consent UI, connected state, and both rendered answers. |
| `INST-017-UC-03` | Refresh the browser and restart the runtime without losing the conversation or grant | None; browser run intentionally deferred | BLOCKED | No persistence evidence collected | Restart command contract exists; no runtime or persisted state was used | Run browser refresh, disposable runtime restart, and state inspection. |
| `INST-017-UC-04` | Recover from proactive expiry and an early unauthorized response | Loopback provider self-test only | PARTIAL | No UI evidence collected | Refresh-token exchange contract passed; failure-recovery branches were not run in a browser | Prove both refresh paths and a useful answer after recovery. |
| `INST-017-UC-05` | See reconnect guidance after refresh failure, reconnect, Disconnect locally, see chat refused, and regrant | Loopback provider self-test only | PARTIAL | No guidance or account-state UI evidence collected | Provider-side revocation is unsupported; no integrated account state was changed | Prove local credential deletion, visible Disconnected state, no provider contact after Disconnect, truthful provider-control guidance, and successful regrant. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: Easy Install OpenAI connected-account lifecycle.
- Requirement: the installer/config compiler connected-account contract and `INST-017` lifecycle.
- Use case: a synthetic user connects, chats twice, survives refresh/restart, repairs expiry,
  disconnects locally, sees chat refused, and regrants without provider or cloud traffic.
- QA case: `INST-010` and `INST-017`.
- Expected result: useful persistent answers and actionable failure states through a real browser,
  with all provider traffic confined to loopback.
- Actual evidence: the local provider self-test and fail-closed release contracts passed.
- Remaining gap or fix: run headed Chromium against the integrated LibreChat candidate and inspect
  the active generated, built, installed, logged, and persisted state.

## Full-View Evidence Checklist

| Evidence surface | Required question | Evidence / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | Docs 39, `INST-010`, and `INST-017`; lifecycle evidence remains partial. |
| Code owning path | Which code path owns the behavior? | Connected-account routes/UI, OpenAI OAuth subscription handling, Responses configuration, and the lifecycle harness were traced. |
| Docs and nested docs/repos | Which docs define the expected behavior? | Installer/config compiler requirement 39 and the installer-resilience case catalog were inspected. |
| Scripts or harnesses | Which scripts, fixtures, QA harnesses, or automated suites exercised it? | `openai-connected-account-lifecycle-qa.cjs` self-test and `test_openai_connected_account_lifecycle_qa.py`. |
| Local/external prerequisite state | Which provider, service, or runtime was proven healthy or degraded? | Loopback provider healthy; integrated LibreChat candidate unavailable; no external provider contacted. |
| Logs | Which sanitized logs confirm or contradict the result? | Self-test returned sanitized exchange/request counts; no runtime logs exist because no runtime was started. |
| DB/state/persistence | Which persisted state confirms it? | Not run. No database or connected-account state was created or mutated. |
| Generated/shipped artifact | Which generated, built, or installed artifact was inspected? | Not run. No integrated artifact was handed over for this phase. |
| Real user path | Which user-facing path was exercised? | Not run. The browser lifecycle was deliberately deferred. |
| Visual/UX comparison | Did the visible result match the expected behavior? | Not run; no screenshot or visible UI outcome was collected. |
| Not run / blocked | Which required surface was not run, and why? | Headed browser, runtime restart, UI persistence, logs, database state, and installed-artifact checks await the integrated candidate. |

## User-Grade Evidence

- Surface exercised: the loopback OAuth/token and Responses SSE provider contract only.
- Real user path: not run; no browser or installed runtime was started.
- Visible outcome: none collected; therefore the browser lifecycle remains blocked.
- Expanded/detail state: not run; no connected-account detail view was opened.
- Persistence/reload result: not run; neither browser refresh nor runtime restart was performed.
- Local/external prerequisite state: loopback provider self-test healthy; integrated LibreChat
  candidate unavailable; reserved disposable VM stopped; no external provider used.
- Evidence retrieval classification, if applicable: local prerequisite unavailable.
- Fallback path, if applicable: no fallback substituted for the required browser path.
- Backend/log/DB confirmation: sanitized self-test counts only; no backend runtime, logs, database, or
  user state existed for this phase.
- Final model/runtime wording check: not run; no model or runtime response was displayed.
- Substitution check: source inspection, provider self-test output, and unit contracts are supporting
  evidence only and do not replace the required visible UI, detail-state, persistence, or wording
  checks.

## Automated Evidence

```bash
node --check qa/installer-resilience/scripts/openai-connected-account-lifecycle-qa.cjs
uv run --with pytest pytest tests/release/test_openai_connected_account_lifecycle_qa.py -q
uv run --with pytest --with pyyaml pytest tests/release/test_openai_connected_account_lifecycle_qa.py tests/release/test_install_experience_labels.py tests/release/test_qa_operating_contract.py tests/release/test_qa_results_public_safety.py -q
```

- JavaScript syntax: PASS.
- Focused lifecycle contracts: 4 passed.
- Combined QA-contract run after correcting the report template and ownership linkage: 35 passed.
- Real-browser evidence: NOT RUN.

## Findings

- Defects: the first report draft did not satisfy the central report template; corrected here.
- Regressions: none identified by the local provider contract.
- Flakes: none observed.
- Environment issues: the integrated LibreChat candidate was not ready, so the reserved disposable
  VM was intentionally left stopped.
- Residual risks: every user-visible lifecycle branch, persistence/restart behavior, runtime logs and
  state, generated configuration, built artifact, installed artifact, and external-attempt ledger
  still require the real-browser acceptance run.

OpenAI provider-side revocation is unsupported because the official OpenAI developer documentation
does not publish a ChatGPT/Codex OAuth revocation endpoint. The acceptance target is therefore an
honest local Disconnect plus provider-account guidance, never a synthetic remote-revoke claim.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.

Until the browser run is complete, `INST-017` remains **PARTIAL** and no release-readiness claim is
made.
