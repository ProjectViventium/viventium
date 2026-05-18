# QA System Feature Use-Case Checklist Repair - 2026-05-18

## Summary

- Result: PARTIAL for the product; PASS for the QA-contract repair. The escaped voice + web-search
  failure is now represented as a regression case, but the product search path still requires a
  full fix and rerun.
- Build/source under test: current local checkout on the active Viventium branch.
- Runtime/artifact under test: local LibreChat web UI on port 3190, modern playground on port 3300,
  local Mongo on port 27117, and generated local web-search config.
- Environment: local development runtime with public-safe synthetic writeups only.
- Tester: Codex.
- Related change: added product-wide natural user use-case checklist, per-feature checklist gates,
  and voice/web-search escaped-case coverage.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `QASYS-009` | PASS | `test_qa_operating_contract.py` passed with 21 tests | Enforces feature inventory, natural-use-case checklist, owner coverage, escaped-case promotion, generic-row rejection, and stale-backlog pressure. |
| `WEB-004` | FAIL | Live local UI/log/DB evidence summarized below | Regression case added; product behavior still needs a fix and rerun. |
| `MPV-006` | FAIL | Live local UI/log/DB evidence summarized below | Regression case added; product behavior still needs a fix and rerun. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `QASYS-UC-001` | Start QA from all features and obvious user actions. | Docs and QA contract plus unauthenticated Playwright browser smoke | PASS | `qa/feature-user-use-case-checklist.md` now exists and is linked from QA/agent docs; Playwright reached the local Viventium login page with no console errors. | Release test now verifies checklist terms, requirement docs, QA owner coverage, per-feature checklist headings, and rejection of generic placeholder rows. | None for the contract gate. |
| `WEB-UC-002` | Ask the agent to look something up while Web Search appears enabled. | Chrome/LibreChat local browser, linked voice/chat conversation | FAIL | Visible answer gave generic degraded search wording instead of a proven provider-state explanation. | Latest persisted matching assistant turn had three `web_search` tool-call parts; API log showed SearXNG request failures; local SearXNG and Firecrawl health probes failed. | Product fix and full browser/voice rerun required. |
| `MPV-UC-003` | Ask the voice-linked agent to look something up. | Chrome/LibreChat plus modern-playground session evidence | FAIL | The user-visible linked chat showed the same generic degraded wording after a voice-linked exchange. | Voice/chat persistence, web-search tool-call parts, API search failure class, and provider health were compared in sanitized form. | Product fix and full modern-playground rerun required. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: QA operating system, web search, modern playground voice.
- Requirement: `01_Key_Principles.md`, `10_Open_Source_Web_Search.md`, `06_Voice_Calls.md`,
  `45_Runtime_Feature_QA_Map.md`, and `qa/README.md`.
- Use case: a user asks Viventium to look up current information while Web Search appears enabled.
- QA case: `QASYS-009`, `WEB-004`, `MPV-006`.
- Expected result: either a grounded answer using fetched evidence or explicit degraded-provider
  wording tied to the configured search dependency.
- Actual evidence: visible local browser result returned generic degraded wording; persisted message
  contained `web_search` tool-call parts; API logs showed SearXNG failures; local SearXNG and
  Firecrawl probes failed.
- Remaining gap or fix: implement and rerun the product search/voice path so visible wording,
  provider health, persisted state, and logs agree.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | `QASYS-009`, `WEB-004`, and `MPV-006` now encode the missed feature-inventory and voice/web-search use cases. |
| Code owning path | Which code path owns the behavior? | `viventiumSearchTool.js` returns model-facing fallback output when search errors; `modelFacingToolOutput.js` normalizes web-search fallback text. |
| Docs and nested docs/repos | Which docs or nested repo docs define the expected behavior? | `01_Key_Principles.md`, `10_Open_Source_Web_Search.md`, `06_Voice_Calls.md`, `45_Runtime_Feature_QA_Map.md`, root `AGENTS.md`, root `CLAUDE.md`, and LibreChat `AGENTS.md`. |
| Scripts or harnesses | Which scripts, fixtures, QA harnesses, or automated suites exercised it? | `test_qa_operating_contract.py`; Playwright CLI browser smoke; health probes for local SearXNG and Firecrawl; sanitized Mongo query for persisted tool-call parts. |
| Logs | Which sanitized logs confirm or contradict the result? | API error log had SearXNG request failures during the same local runtime window. |
| DB/state/persistence | Which sanitized state, DB count/hash, persisted message, config, or artifact confirms it? | Mongo showed the latest matching assistant turn persisted with three `web_search` tool-call parts and text output. |
| Generated/shipped artifact | Which generated config, compiled bundle, prebuilt helper, or installed artifact was inspected when applicable? | Generated LibreChat YAML and local env reference the SearXNG and Firecrawl endpoints; no helper/prebuilt artifact changed in this repair. |
| Real user path | Which browser/computer, Telegram, voice, installer, CLI, MCP/tool, scheduler, or GlassHive path was used like a user? | Computer-use observation of the local Chrome/LibreChat UI plus local modern-playground context from the linked voice/chat flow. |
| Visual/UX comparison | Does the visible UI/UX or delivered result match the expected behavior and supporting evidence? | No. The UI exposed generic degraded wording; the supporting evidence points to provider unavailability/failure that QA had not required as a case. |
| Not run / blocked | Which required surface was not run, and why is the result partial or blocked? | A fresh synthetic modern-playground voice rerun after a product fix was not run because this change only repairs the QA contract and records the escaped product failure. |

## User-Grade Evidence

- Surface exercised: local Chrome/LibreChat browser with a voice-linked conversation; local
  modern-playground runtime was open and tied to the same failure class. Playwright CLI opened the
  local Viventium web surface and reached the login page without console errors; that Playwright run
  was an unauthenticated surface smoke, not the real-user-path proof for the search failure.
- Real user path: observe visible chat answer after the user asked the agent to look up information;
  compare with Web Search enabled state, persisted tool-call parts, provider health, and API logs.
- Visible outcome: the assistant produced generic degraded search wording instead of a clear
  provider-state explanation.
- Expanded/detail state: Agent Builder showed Web Search enabled; the linked conversation persisted
  the failed assistant turn.
- Persistence/reload result: Mongo persisted matching assistant turns; latest matching turn contained
  `web_search` tool-call parts.
- Backend/log/DB confirmation: SearXNG search errors were present in the API error log; local
  SearXNG and Firecrawl health probes returned connection failures; Mongo showed persisted
  `web_search` tool-call parts.
- Final model/runtime wording check: final wording did not prove the configured provider state and
  would have escaped the prior QA checklist.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit
  tests are supporting evidence, not substitutes for any required visible-UI, detail-state,
  persistence, or wording step.

## Automated Evidence

```bash
viventium_v0_4/voice-gateway/.venv/bin/python -m pytest tests/release/test_qa_operating_contract.py -q
viventium_v0_4/voice-gateway/.venv/bin/python -m pytest tests/release/ -q
CODEX_HOME="$HOME/.codex" PWCLI="$CODEX_HOME/skills/playwright/scripts/playwright_cli.sh" "$PWCLI" open http://localhost:3190 --headed
CODEX_HOME="$HOME/.codex" PWCLI="$CODEX_HOME/skills/playwright/scripts/playwright_cli.sh" "$PWCLI" snapshot
curl -fsS http://localhost:8082/
curl -fsS http://localhost:3003/
mongosh --quiet mongodb://127.0.0.1:27117/LibreChatViventium --eval "sanitized message/tool-call projection"
```

Result summary:

- `test_qa_operating_contract.py`: 21 passed.
- `tests/release/`: 607 passed, 4 skipped.
- Playwright CLI: local Viventium resolved to the login page with zero console errors; this was an
  unauthenticated smoke check, not a substitute for the signed-in Chrome/computer-use observation.
- SearXNG health probe: connection failed.
- Firecrawl health probe: connection failed.
- Mongo persistence probe: latest matching assistant turn persisted `web_search` tool-call parts.

## Findings

- Defects: prior QA allowed feature-map rows and config checks to exist without forcing natural
  cross-surface cases like voice + web-search.
- Regressions: the live search failure is not fixed by this report; it is now captured as `WEB-004`
  and `MPV-006`, plus adjacent affected-owner cases for Telegram web search, agent config
  continuity, config alignment, and citation rendering.
- Flakes: none identified in the QA-contract test run.
- Environment issues: local SearXNG and Firecrawl were unavailable during the evidence pass.
- Residual risks: the product fix still needs a full real-browser and modern-playground rerun with
  healthy and degraded provider states.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
