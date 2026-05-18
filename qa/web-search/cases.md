# Web Search QA Cases

## Case ID Convention

Use stable `WEB-NNN` IDs for web search cases.

## Case Catalog

| Case ID | Requirement | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- |
| `WEB-001` | Configured provider readiness | CLI/status, generated runtime config | test_local_web_search_compose.py and test_preflight.py | NOT YET RUN (cataloged 2026-05-17; run when feature changes) |
| `WEB-002` | Visible answer grounded in fetched evidence | Web chat, search/scrape logs summary, final answer | browser QA plus web-search tests | NOT YET RUN (cataloged 2026-05-17; run when feature changes) |
| `WEB-003` | Degraded search is explicit | Web/Telegram final answer, status output | test_local_web_search_compose.py | NOT YET RUN (cataloged 2026-05-17; run when feature changes) |
| `WEB-004` | Voice and chat current-data request uses real search or proves degraded provider state | Web chat, voice/LiveKit transcript, persisted tool-call parts, local search backend health, hosted search backend status | real browser/computer + DB/log/state inspection | FAIL (escaped 2026-05-18; synthetic regression added, fix run pending) |
| `WEB-005` | Web-search tool failures expose failure class and fallback policy | Web chat/model-facing tool output, browser/local-delegation fallback, logs/state | `modelFacingToolOutput.test.js` plus real browser QA | PARTIAL (2026-05-18 deterministic/runtime QA plus synthetic authenticated browser run; connected-model fallback run pending) |

## Natural User Use Case Checklist

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `WEB-UC-001` | Ask a current-data question in web chat with Web Search enabled. | `docs/requirements_and_learnings/10_Open_Source_Web_Search.md` / `WEB-002` | LibreChat browser conversation | Web-search tool-call parts, local search backend health, hosted search backend status, request logs, generated `webSearch` config | Answer is grounded in fetched evidence and cites only returned sources. | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
| `WEB-UC-002` | Ask the agent to look something up from a voice call or linked voice/chat transcript. | `docs/requirements_and_learnings/10_Open_Source_Web_Search.md`, `docs/requirements_and_learnings/06_Voice_Calls.md` / `WEB-004` | Modern Playground or linked LibreChat browser conversation | Visible transcript, persisted `web_search` tool-call parts, DB message state, API search errors or returned sources, local/hosted provider health | Search either succeeds with evidence or the answer names the degraded provider class without inventing facts. | FAIL (escaped 2026-05-18; fix run pending) |
| `WEB-UC-003` | Try search while SearXNG, Firecrawl, hosted keys, or required local services are unavailable. | `docs/requirements_and_learnings/10_Open_Source_Web_Search.md` / `WEB-003` | Browser/Telegram/voice surface that exposes search | Health/status command, logs, generated config, persisted answer and tool artifact | User sees honest degraded-service wording and retry/setup path; no fake current facts. | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
| `WEB-UC-004` | Ask for a named person/contact/date/current fact after the first web search attempt fails operationally. | `docs/requirements_and_learnings/10_Open_Source_Web_Search.md` / `WEB-005` | Browser chat with Web Search and local-delegation tool available | Tool output failure class, provider health, Docker/container state when local, delegation audit or browser fallback result, final wording | Assistant does not stop at generic search failure; it names the failure class and uses the available browser/local-delegation fallback or clearly states why fallback is unavailable. | PARTIAL (2026-05-18 deterministic/runtime QA plus synthetic authenticated browser run; connected-model fallback run pending) |

## `WEB-001` - Configured provider readiness

- Requirement: Configured provider readiness.
- Risk covered: Viventium claims the behavior works without proving the real user-visible surface and supporting state.
- Preconditions: local runtime or focused harness is available with synthetic public-safe data.
- Steps:
  1. Start local/hosted web-search configuration; verify status/preflight reports SearXNG/Firecrawl or API providers accurately.
  2. Compare visible result with source/config, logs or persisted state summary, and the owning requirement doc.
  3. Save a public-safe dated report under `reports/` using the standard run-report template.
- Expected result: visible behavior, supporting evidence, and documentation agree.
- Forbidden result: mocks, backend logs, source inspection, or model output are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, state/log summary, and public-safety review.
- Automation: test_local_web_search_compose.py and test_preflight.py.
- Last run: NOT YET RUN (cataloged 2026-05-17; not a substitute for the next real feature run).

## `WEB-002` - Visible answer grounded in fetched evidence

- Requirement: Visible answer grounded in fetched evidence.
- Risk covered: Viventium claims the behavior works without proving the real user-visible surface and supporting state.
- Preconditions: local runtime or focused harness is available with synthetic public-safe data.
- Steps:
  1. Ask a synthetic current web question; verify visible answer is grounded in retrieved evidence and does not cite source snippets not actually returned.
  2. Compare visible result with source/config, logs or persisted state summary, and the owning requirement doc.
  3. Save a public-safe dated report under `reports/` using the standard run-report template.
- Expected result: visible behavior, supporting evidence, and documentation agree.
- Forbidden result: mocks, backend logs, source inspection, or model output are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, state/log summary, and public-safety review.
- Automation: browser QA plus web-search tests.
- Last run: NOT YET RUN (cataloged 2026-05-17; not a substitute for the next real feature run).

## `WEB-003` - Degraded search is explicit

- Requirement: Degraded search is explicit.
- Risk covered: Viventium claims the behavior works without proving the real user-visible surface and supporting state.
- Preconditions: local runtime or focused harness is available with synthetic public-safe data.
- Steps:
  1. Stop or omit configured search/scrape provider; verify user-facing copy says search is unavailable or needs retry instead of inventing live facts.
  2. Compare visible result with source/config, logs or persisted state summary, and the owning requirement doc.
  3. Save a public-safe dated report under `reports/` using the standard run-report template.
- Expected result: visible behavior, supporting evidence, and documentation agree.
- Forbidden result: mocks, backend logs, source inspection, or model output are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, state/log summary, and public-safety review.
- Automation: test_local_web_search_compose.py.
- Last run: NOT YET RUN (cataloged 2026-05-17; not a substitute for the next real feature run).

## `WEB-004` - Voice And Chat Search Must Prove Real Retrieval Or Honest Degradation

- Requirement: `docs/requirements_and_learnings/10_Open_Source_Web_Search.md`,
  `docs/requirements_and_learnings/06_Voice_Calls.md`, and `qa/feature-user-use-case-checklist.md`.
- Risk covered: Web Search appears enabled in the agent UI, the user naturally asks Viventium to
  look something up, but QA only checked config/tests and missed that the real browser/voice surface
  returns generic degraded wording.
- Preconditions: local runtime running; Web Search capability enabled on the selected agent; synthetic
  public-safe current-data prompt; local SearXNG/Firecrawl or hosted providers intentionally either
  healthy or degraded for the scenario.
- Steps:
  1. Open an authenticated browser chat or voice-launched linked chat with a synthetic current-data
     prompt that asks the agent to look something up.
  2. Observe the visible answer and, for voice, the modern-playground transcript or linked LibreChat
     transcript.
  3. Inspect persisted assistant content for `web_search` tool-call parts or returned web-search
     artifacts.
  4. Probe configured search/scrape provider health and inspect API/tool logs for returned sources
     or failure class.
  5. Compare user-facing wording with the actual provider state and saved message/tool-call state.
- Expected result: if search providers are healthy, the answer uses fetched evidence and source
  markers. If providers are unavailable, the answer says the provider/search dependency is
  unavailable or retryable, without implying no information exists and without inventing facts.
- Forbidden result: generic "search is not pulling" copy is accepted without proving provider
  health/failure; Web Search UI checkbox is treated as proof of usable search; source inspection or
  unit tests replace the browser/voice result.
- Evidence to capture: sanitized browser/voice observation, health probe result, log failure class or
  returned-source count, persisted message/tool-call part counts, generated config state, and a
  public-safe report.
- Automation: real browser/computer QA plus `tests/release/test_local_web_search_compose.py`,
  `tests/release/test_config_compiler.py`, and narrower runtime tests as added.
- Last run: FAIL (escaped 2026-05-18 from a live local browser/voice-linked conversation; regression
  case added, product fix and rerun pending).

## `WEB-005` - Search Failure Classes And Escalation Fallback

- Requirement: `docs/requirements_and_learnings/10_Open_Source_Web_Search.md` and
  `docs/requirements_and_learnings/01_Key_Principles.md`.
- Risk covered: `web_search` fails because the provider, Docker-backed local service, auth, rate
  limit, or request shape is broken, but the assistant treats it as no results and stops instead of
  escalating.
- Preconditions: local runtime running; Web Search enabled; synthetic public-safe named-entity,
  contact, date, or current-fact prompt; browser/local-delegation fallback available for the
  fallback branch when configured.
- Steps:
  1. Force or observe each failure class with synthetic inputs: provider unavailable, timeout, rate
     limit, auth/config missing, request rejected, unsupported configuration, and successful-empty.
  2. For local providers, record Docker daemon and SearXNG/Firecrawl container state separately from
     search result content.
  3. Ask the same current-fact/named-entity prompt through the real browser/chat surface.
  4. Verify the visible answer names the failure class and, when fallback is available, uses the
     browser/local-delegation path before stopping.
  5. Compare persisted tool-call output, provider logs, health probes, generated config, and final
     wording.
- Expected result: final wording distinguishes operational failure from no-results, gives a retry or
  setup path, and uses fallback for factual lookup when available.
- Forbidden result: "search is not pulling" or equivalent generic text is accepted without proving
  provider health/failure class; Docker-off/provider-down state is missed; fallback is skipped for
  factual lookup with available local-delegation/browser capability.
- Evidence to capture: sanitized visible answer, model-facing tool output failure class, provider
  health/Docker state, persisted tool-call part count, fallback tool result or blocked reason, and
  public-safe report.
- Automation: `api/test/app/clients/tools/util/modelFacingToolOutput.test.js`,
  `api/test/app/clients/tools/util/viventiumSearchTool.test.js`, plus real browser/computer QA.
- Last run: PARTIAL (2026-05-18 deterministic/runtime QA plus synthetic authenticated browser run in
  `reports/2026-05-18-search-failure-classification-runtime-qa.md`; the synthetic chat reached the
  visible surface and web_search auth was enabled, but connected-model auth blocked tool execution;
  connected-model fallback and voice runs remain pending).
