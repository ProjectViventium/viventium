# Participant Provider Fallback QA Run - 2026-08-18

## Summary

- Result: PARTIAL
- Build/source under test: active local source checkout with the participant-fallback change
- Runtime/artifact under test: rebuilt `@librechat/api` artifact in installed local production
- Environment: installed local production
- Tester: Codex automated and user-path QA
- Related change: effect-aware recovery for opaque pre-authoring graph-participant failures

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `TR-019` | PARTIAL | 265 fallback/controller, 26 graph, 51 Telegram route, and 152 bridge tests passed | Real post-restart Telegram provider recovery remains unrun. |
| `PWK-040` | PARTIAL | Compiled artifact, local restart, HTTP health, and Playwright Web checks passed | External delivery and persisted-message correlation remain unrun. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `TR-019-UC-01` | Ask Main for work that transfers to an in-process specialist whose primary provider fails before authorship. | Telegram | PARTIAL | No post-fix external Telegram turn was accepted as evidence. | Exact-boundary synthetic regression and rebuilt artifact passed. | Run one natural provider-failure recovery turn and correlate its persisted message. |
| `TR-019-UC-02` | Start an ordinary external-effect tool and confirm provider replay remains blocked. | API test harness | PASS | Not a visible user path. | Unmarked-tool and look-alike-metadata regressions passed. | Supporting evidence cannot replace required user-path evidence for the overall case. |
| `TR-019-UC-03` | Restart local Viventium and open the Web surface. | CLI and Playwright browser | PASS | The `Viventium` login page rendered with the expected controls and zero console errors. | API, Web, and Playground returned HTTP 200 from the active checkout. | None for runtime reachability. |
| `TR-019-UC-04` | Reach the Telegram gateway without starting a turn. | Read-only local API | PASS | A synthetic unmapped identity received the expected structured link-required response. | No model turn, external message, or persisted user prompt was created. | Does not prove provider recovery. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: Main-to-specialist provider fallback on Telegram agent graphs
- Requirement: Telegram Bridge and Parallel Work orchestration require Main to remain available while
  graph coordination stays distinct from externally effecting tools.
- Use case: A specialist provider fails before authorship and its configured fallback completes the
  same graph without replaying email, calendar, durable-work, or other effects.
- QA case: `TR-019` and `PWK-040`
- Expected result: Participant fallback runs first; unmarked effects and durable receipts remain
  replay fences.
- Actual evidence: Focused automation, real callback metadata propagation, compiled artifact,
  validated restart, HTTP health, Playwright Web render, and read-only gateway response passed.
- Remaining gap or fix: A natural post-fix Telegram recovery turn and persisted delivery correlation
  are still required for PASS.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | Telegram Bridge plus Parallel Work; `TR-019` and `PWK-040`. |
| Code owning path | Which code path owns the behavior? | Agent fallback classification, graph model invocation, graph-tool metadata, and AgentClient replay fencing. |
| Docs and nested docs/repos | Which docs define the expected behavior? | Telegram Bridge and Parallel Work requirements plus their living QA cases. |
| Scripts or harnesses | Which automated suites exercised it? | Fallback/controller, graph, Telegram route, and Telegram bridge suites. |
| Local/external prerequisite state | Which services or accounts were proven healthy or degraded? | Docker and the local core runtime were healthy; the independent Claude review session was unauthenticated. |
| Logs | Which sanitized logs confirm or contradict the result? | The escaped turn failed before any connected-account effect; current restart and health checks completed without a core-surface failure. |
| DB/state/persistence | Which sanitized state confirms it? | The read-only gateway check created no model turn or user prompt. Post-fix recovery persistence is unrun. |
| Generated/shipped artifact | Which built artifact was inspected? | Rebuilt `@librechat/api` contains the graph effect token and is served by the active checkout. |
| Real user path | Which real surface was used? | Playwright browser and the supported local runtime CLI; external Telegram recovery was not run. |
| Visual/UX comparison | Does visible UX match supporting evidence? | Web login and health agree that the core runtime is reachable. Provider-recovery copy is not yet visually proven. |
| Not run / blocked | Which required surface is missing? | External Telegram delivery, persisted-message correlation, and Claude review are BLOCKED or PARTIAL. |

Mocks, API responses, logs, DB rows, source inspection, and model review cannot replace required
user-path evidence. Logs, DB/state/persistence evidence remains explicitly partial for the natural
Telegram recovery path.

## User-Grade Evidence

- Surface exercised: Installed local production CLI, real Playwright browser, and read-only local Telegram API.
- Real user path: Restarted Viventium, opened the Web login page, and verified the gateway without starting a model turn.
- Visible outcome: The `Viventium` login surface rendered with email, password, and Continue controls.
- Expanded/detail state: Browser snapshot showed the complete login form; console inspection showed zero errors.
- Persistence/reload result: The validated restart completed and all three core ports remained HTTP 200 afterward.
- Local/external prerequisite state: Docker, API, Web, Playground, Telegram Bridge, GlassHive, search, and scraper were running; external provider recovery was not induced.
- Evidence retrieval classification, if applicable: successful structured request rejection for a synthetic unlinked identity; provider recovery not run.
- Fallback path, if applicable: Automated participant fallback passed; external Telegram proof remains PARTIAL.
- Backend/log/DB confirmation: Compiled token present, active process roots match the checkout, and the read-only check created no model turn.
- Final model/runtime wording check: The gateway returned structured link-required authority; no generic provider failure was generated in this non-model check.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit tests are supporting evidence, not substitutes for any required visible-UI, detail-state, persistence, or wording step.

## Automated Evidence

```bash
CI=true npm test -- server/services/viventium/__tests__/agentSchemaToolBindingPatch.spec.js server/services/viventium/__tests__/agentLlmFallback.spec.js server/controllers/agents/client.test.js --runInBand --watch=false
CI=true npx jest src/agents/run.spec.ts --runInBand --watch=false
CI=true npm test -- server/routes/viventium/__tests__/telegram.spec.js --runInBand --watch=false
TelegramVivBot/.venv/bin/python -m pytest tests/test_librechat_bridge.py -q
npm run build
bin/viventium dev-runtime activate-current --validate --restart --allow-protected-folder
```

## Findings

- Defects: The escaped failure combined an opaque participant provider error with an outer replay
  fence that treated server-owned graph transfer like an external tool effect.
- Regressions: None found in the focused adjacent suites.
- Flakes: None in the final runs.
- Environment issues: Docker was initially stopped and was started before the validated restart.
  Claude review was unavailable because its local OAuth session was not authenticated.
- Residual risks: Natural Telegram delivery and persistence remain unverified after the fix, so the
  cases stay PARTIAL.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
