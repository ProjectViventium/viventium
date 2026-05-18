# Web Search Telegram QA Cases

## Case ID Convention

Use stable `WEBTG-NNN` IDs for web search telegram cases.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `WEBTG-001` | Web search answers in Telegram/browser are grounded in fetched evidence and degrade honestly when local services are unavailable. | User-visible behavior matches source, docs, persisted state, and logs | Telegram/browser prompt, SearXNG/Firecrawl health, answer citations | `tests/release/test_local_web_search_compose.py` plus user-grade QA when visible | NOT YET RUN (cataloged 2026-05-17; next feature run required) |
| `WEBTG-002` | Public QA evidence is sanitized and reproducible | A PR reviewer can verify the behavior without private/local data | QA report, git diff, logs summary, generated artifacts | Public-safety scan plus relevant release tests | NOT YET RUN (cataloged 2026-05-17; next feature run required) |
| `WEBTG-003` | Telegram current-data request proves search or honest provider degradation | Telegram send/receive, stored message parts, local search backend health, hosted search backend status | Telegram user-grade QA plus web-search tests | FAIL (escaped 2026-05-18 by analogous browser/voice path; Telegram rerun pending) |

## `WEBTG-001` - Core User Flow

- Requirement: Web search answers in Telegram/browser are grounded in fetched evidence and degrade honestly when local services are unavailable.
- Risk covered: implementation, docs, and user-visible behavior drift apart.
- Preconditions: local Viventium runtime or the specific feature harness is available with synthetic, public-safe data.
- Steps:
  1. Exercise the feature through the real user surface, not only a unit test.
  2. Compare the visible result with source code, generated/runtime config, logs, persisted state, and the owning requirement doc.
  3. Capture a public-safe report with expected result, forbidden result, evidence, residual risk, and follow-up.
- Expected result: the feature behaves as documented and every supporting layer agrees.
- Forbidden result: backend logs, mocks, source inspection, or model completions are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, generated/runtime state summary, and docs/case links.
- Automation: `tests/release/test_local_web_search_compose.py` plus any narrower feature tests discovered during implementation.
- Last run: NOT YET RUN (cataloged 2026-05-17; not a substitute for the next real feature run).

## `WEBTG-002` - Public-Safe Evidence Record

- Requirement: public QA artifacts must be reproducible and free of secrets, personal data, local paths, raw IDs, and private screenshots.
- Risk covered: a useful local QA run cannot be safely reviewed or published.
- Preconditions: a dated QA report is created for this feature.
- Steps:
  1. Review the report and related diffs for local absolute paths, account identifiers, tokens, raw logs, raw DB rows, private chats, and screenshots with private content.
  2. Keep raw/private evidence outside the public repo and summarize only public-safe counts, statuses, hashes, and conclusions.
  3. Link the report back to this case and the owning requirement doc.
- Expected result: the public report proves the behavior without leaking private/local data.
- Forbidden result: a report includes private transcripts, account identifiers, raw runtime dumps, local home paths, tokens, or secret-bearing command lines.
- Evidence to capture: public-safety scan result and link to the sanitized report.
- Automation: public-safety pattern scan plus relevant release tests.
- Last run: NOT YET RUN (cataloged 2026-05-17; run on each new public report).

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Web Search Telegram. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `WEBTG-UC-001` | On Telegram/browser prompt, SearXNG/Firecrawl health, answer citations, verify that web search answers in Telegram/browser are grounded in fetched evidence and degrade honestly when local services are unavailable. | owning requirement for `WEBTG-001` / `WEBTG-001` | Telegram/browser prompt, SearXNG/Firecrawl health, answer citations | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to WEBTG-001. | User-visible behavior matches source, docs, persisted state, and logs | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
| `WEBTG-UC-002` | On QA report, git diff, logs summary, generated artifacts, create or review the public QA evidence record with setup/auth/config, empty-state, degraded-dependency, and privacy checks. | owning requirement for `WEBTG-002` / `WEBTG-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to WEBTG-002. | The user sees an honest setup, retry, or degraded-state result for WEBTG-002; no fake success is accepted. | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
| `WEBTG-UC-003` | Send a synthetic Telegram prompt asking Viventium to look something up with current public information while Web Search is enabled. | `docs/requirements_and_learnings/10_Open_Source_Web_Search.md` / `WEBTG-003` | Real Telegram bot send/receive path plus linked LibreChat persistence | Telegram delivery ledger, stored message/tool-call parts, local search backend health, hosted search backend status, request logs, generated `webSearch` config | Telegram answer either uses fetched evidence or states the configured provider is unavailable/retryable without inventing facts. | FAIL (escaped 2026-05-18 by analogous browser/voice path; Telegram rerun pending) |

## `WEBTG-003` - Telegram Search Must Prove Retrieval Or Honest Provider Degradation

- Requirement: `docs/requirements_and_learnings/10_Open_Source_Web_Search.md` and
  `docs/requirements_and_learnings/03_Telegram_Bridge.md`.
- Risk covered: the same Web Search provider failure observed in browser/voice can escape Telegram
  QA if only the web surface gets a regression case.
- Preconditions: Telegram bridge running with a synthetic QA chat; Web Search capability enabled;
  provider health intentionally recorded before the prompt.
- Steps:
  1. Send a synthetic current-data Telegram prompt that explicitly asks Viventium to look something
     up using public information.
  2. Inspect the visible Telegram reply and linked LibreChat/stored message state.
  3. Compare stored `web_search` tool-call parts or returned web artifacts with API logs and
     local search backend health and hosted search backend status.
  4. Save a public-safe report with no chat IDs, message IDs, account identifiers, or private prompt
     text.
- Expected result: Telegram reply is grounded in fetched evidence when providers are healthy, or
  names the search-provider degraded class when unavailable.
- Forbidden result: generic search failure copy is accepted without provider health/log/DB evidence;
  Telegram delivery is treated as proof that search worked.
- Evidence to capture: sanitized Telegram visible result, delivery status, stored message/tool-call
  counts, provider health result, API log failure class or source count, generated config state.
- Automation: Telegram user-grade QA plus `tests/release/test_local_web_search_compose.py`.
- Last run: FAIL (escaped 2026-05-18 by analogous browser/voice path; Telegram-specific rerun
  pending).
