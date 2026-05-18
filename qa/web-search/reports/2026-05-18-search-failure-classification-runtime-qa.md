# Web Search Failure Classification QA Run - 2026-05-18

## Summary

- Result: PARTIAL pass for deterministic runtime, prompt, QA-contract, provider-health, synthetic
  authenticated browser, and local browser-surface evidence; voice fallback and a connected-model
  web-search invocation remain required before closing the escaped user-path cases.
- Build/source under test: current local checkout, parent repo plus nested LibreChat.
- Runtime/artifact under test: local LibreChat runtime, local SearXNG, local Firecrawl, source-of-truth
  prompts, and model-facing web-search tool output helpers.
- Environment: local development runtime with synthetic public-safe checks.
- Tester: Codex.
- Related change: web-search failure classification, fallback policy, and QA contract hardening.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `WEB-005` | PARTIAL PASS | API unit tests, release tests, provider health, Playwright synthetic authenticated chat run | The synthetic account reached chat and web_search auth was enabled; model-provider connected account auth blocked the turn before web_search execution. |
| `WEB-UC-004` | PARTIAL PASS | Deterministic failure-class artifact test, prompt/release contract, synthetic authenticated browser evidence | Real fallback behavior still needs a connected-model browser run and linked voice path run. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `WEB-UC-004` | Ask for a named person/contact/date/current fact after the first web search attempt fails operationally. | Playwright logged into local LibreChat with a disposable synthetic account and submitted a public lookup prompt; deterministic tool harness exercised model-facing failure output. | PARTIAL | Chat UI showed a specific connected-account auth error instead of a silent empty result. | Tool artifact carries `failureClass=provider_unavailable`; safe error text contains no raw local endpoint; Docker, SearXNG, and Firecrawl health checks returned healthy; `/api/agents/tools/web_search/auth` returned authenticated system-defined providers/scrapers/rerankers; DB inspection found the synthetic auth-blocked turn did not persist a conversation or message; disposable local user/session were deleted after evidence capture. | Connected-model browser chat fallback and linked voice path still need a run. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: Web Search failure classification and factual-lookup fallback.
- Requirement: `docs/requirements_and_learnings/10_Open_Source_Web_Search.md` and
  `docs/requirements_and_learnings/01_Key_Principles.md`.
- Use case: `WEB-UC-004`.
- QA case: `WEB-005`.
- Expected result: operational failures are classified, Docker/provider state is recorded, raw local
  endpoints are not exposed, and current-fact fallback is used when available.
- Actual evidence: deterministic tool tests and release contract passed; local provider prerequisites
  were healthy; a synthetic account reached the real chat UI; web_search auth was enabled; the turn
  was blocked by model connected-account auth before tool execution.
- Remaining gap or fix: connected-model chat and voice fallback behavior still need a synthetic
  account run before the escaped cases can move from partial to pass.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | `10_Open_Source_Web_Search.md`, `WEB-UC-004`, `WEB-005`. |
| Code owning path | Which code path owns the behavior? | `modelFacingToolOutput.js` and `viventiumSearchTool.js`. |
| Docs and nested docs/repos | Which docs or nested repo docs define the expected behavior? | Root AGENTS/CLAUDE, Web Search requirements, QA README/templates, nested LibreChat AGENTS. |
| Scripts or harnesses | Which scripts, fixtures, QA harnesses, or automated suites exercised it? | Jest API tests, parent release tests, Playwright CLI smoke, Docker and curl health probes. |
| Local/external prerequisite state | Which required local service, provider, Docker-backed sidecar, OAuth grant, API key, model, or hosted dependency was proven healthy or degraded? | Docker daemon responsive; local SearXNG and Firecrawl endpoints returned HTTP 200. |
| Logs | Which sanitized logs confirm or contradict the result? | Test runner output showed all targeted suites passed; browser network evidence showed the chat stream returned a specific model connected-account auth error. Raw bearer-bearing network details were not stored. |
| DB/state/persistence | Which sanitized state, DB count/hash, persisted message, config, or artifact confirms it? | Disposable synthetic user existed and was verified/approved during the run; DB inspection found zero persisted conversations/messages for the auth-blocked turn; the disposable local user/session were deleted after evidence capture; deterministic tool artifact contained safe error and failure class. |
| Generated/shipped artifact | Which generated config, compiled bundle, prebuilt helper, or installed artifact was inspected when applicable? | Source-of-truth prompts and parent release prompt registry checks passed. |
| Real user path | Which browser/computer, Telegram, voice, installer, CLI, MCP/tool, scheduler, or GlassHive path was used like a user? | Playwright opened local LibreChat and voice surfaces, logged into LibreChat with a disposable synthetic account, and submitted a public lookup prompt. |
| Visual/UX comparison | Does the visible UI/UX or delivered result match the expected behavior and supporting evidence? | The visible chat error named the provider-auth blocker; fallback wording itself remains to be observed in a connected-model synthetic chat. |
| Not run / blocked | Which required surface was not run, and why is the result partial or blocked? | The synthetic browser chat was blocked before web_search execution because the synthetic account had no connected Anthropic account; linked voice fallback was not run. |

## User-Grade Evidence

- Surface exercised: Playwright CLI against local LibreChat and voice surfaces.
- Real user path: browser opened local Viventium login and voice assistant pages, logged in with a
  disposable synthetic account, and sent a public lookup prompt through the real chat UI.
- Visible outcome: LibreChat rendered the chat UI and then showed a specific model connected-account
  auth error rather than a silent empty web-search result.
- Expanded/detail state: not applicable to login smoke; voice settings listed local listening and
  speaking choices.
- Persistence/reload result: DB inspection found no conversation/message persisted for the
  auth-blocked synthetic turn; disposable local user/session were deleted after evidence capture.
- Local/external prerequisite state: Docker daemon responsive; SearXNG and Firecrawl endpoints
  returned HTTP 200.
- Evidence retrieval classification, if applicable: provider unavailable, timeout, rate limit,
  auth/config missing, request rejected, successful-empty, and local prerequisite paths are now
  documented and tested; the artifact test exercised `provider_unavailable`.
- Fallback path, if applicable: browser/computer/local-delegation fallback is required by prompt and
  QA contract; live connected-model fallback remains not run in this record.
- Backend/log/DB confirmation: Jest and release tests passed; web_search tool auth endpoint reported
  enabled; browser stream returned a specific model connected-account auth error; DB inspection found
  zero persisted conversations/messages for the auth-blocked synthetic turn.
- Final model/runtime wording check: deterministic model-facing output says provider unavailable is
  inconclusive and not proof that no results exist.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit
  tests are supporting evidence, not substitutes for any required visible-UI, detail-state,
  persistence, or wording step.

## Automated Evidence

```bash
npm test -- test/app/clients/tools/util/viventiumSearchTool.test.js test/app/clients/tools/util/modelFacingToolOutput.test.js --runInBand
npm run test:ci -- test/app/clients/prompts/formatMessages.toolFailureNormalization.test.js --runInBand
uv run --with pytest --with pyyaml python -m pytest tests/release -q
```

## Findings

- Defects: the original generic empty-output behavior is covered by a safer failure-class contract.
- Regressions: none found in targeted and parent release suites.
- Flakes: none observed.
- Environment issues: Docker was explicitly verified rather than assumed; the synthetic user path
  exposed a separate connected-model auth blocker.
- Residual risks: connected-model browser and voice fallback runs remain required.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
