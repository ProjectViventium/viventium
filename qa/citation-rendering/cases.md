# Citation Rendering QA Cases

## Case ID Convention

Use stable `CITE-NNN` IDs for citation rendering cases.

## Case Catalog

| Case ID | Requirement | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- |
| `CITE-001` | Tool citations render and expand | Web UI answer, citation expansion, persisted message | Prompt/rendering tests plus Playwright browser QA | NOT YET RUN (cataloged 2026-05-17; run when feature changes) |
| `CITE-002` | Unsupported or missing source data degrades honestly | Web UI answer and persisted message | Prompt/rendering tests | NOT YET RUN (cataloged 2026-05-17; run when feature changes) |
| `CITE-003` | Public-safe citation evidence | QA report and public-safety scan | test_qa_operating_contract.py | NOT YET RUN (cataloged 2026-05-17; run when feature changes) |
| `CITE-004` | Search citations appear only when web evidence was actually returned | Web UI answer, citation expansion, persisted `web_search` artifacts | browser QA plus persisted message inspection | FAIL (escaped 2026-05-18 by no-evidence search path; rerun pending) |

## `CITE-001` - Tool citations render and expand

- Requirement: Tool citations render and expand.
- Risk covered: Viventium claims the behavior works without proving the real user-visible surface and supporting state.
- Preconditions: local runtime or focused harness is available with synthetic public-safe data.
- Steps:
  1. Use a synthetic answer with supported source metadata in the web UI; verify visible citation chips/links, expanded source detail, persisted message reload, and no fabricated source labels.
  2. Compare visible result with source/config, logs or persisted state summary, and the owning requirement doc.
  3. Save a public-safe dated report under `reports/` using the standard run-report template.
- Expected result: visible behavior, supporting evidence, and documentation agree.
- Forbidden result: mocks, backend logs, source inspection, or model output are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, state/log summary, and public-safety review.
- Automation: Prompt/rendering tests plus Playwright browser QA.
- Last run: NOT YET RUN (cataloged 2026-05-17; not a substitute for the next real feature run).

## `CITE-002` - Unsupported or missing source data degrades honestly

- Requirement: Unsupported or missing source data degrades honestly.
- Risk covered: Viventium claims the behavior works without proving the real user-visible surface and supporting state.
- Preconditions: local runtime or focused harness is available with synthetic public-safe data.
- Steps:
  1. Render an answer with partial source metadata; verify the UI omits unsupported citation detail instead of inventing a source.
  2. Compare visible result with source/config, logs or persisted state summary, and the owning requirement doc.
  3. Save a public-safe dated report under `reports/` using the standard run-report template.
- Expected result: visible behavior, supporting evidence, and documentation agree.
- Forbidden result: mocks, backend logs, source inspection, or model output are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, state/log summary, and public-safety review.
- Automation: Prompt/rendering tests.
- Last run: NOT YET RUN (cataloged 2026-05-17; not a substitute for the next real feature run).

## `CITE-003` - Public-safe citation evidence

- Requirement: Public-safe citation evidence.
- Risk covered: Viventium claims the behavior works without proving the real user-visible surface and supporting state.
- Preconditions: local runtime or focused harness is available with synthetic public-safe data.
- Steps:
  1. Save a dated report with only synthetic source URLs/titles and no private source content.
  2. Compare visible result with source/config, logs or persisted state summary, and the owning requirement doc.
  3. Save a public-safe dated report under `reports/` using the standard run-report template.
- Expected result: visible behavior, supporting evidence, and documentation agree.
- Forbidden result: mocks, backend logs, source inspection, or model output are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, state/log summary, and public-safety review.
- Automation: test_qa_operating_contract.py.
- Last run: NOT YET RUN (cataloged 2026-05-17; not a substitute for the next real feature run).

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Citation Rendering. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `CITE-UC-001` | On Web UI answer, citation expansion, persisted message, verify that tool citations render and expand. | owning requirement for `CITE-001` / `CITE-001` | Web UI answer, citation expansion, persisted message | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to CITE-001. | The visible result for CITE-001 matches the documented requirement. | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
| `CITE-UC-002` | On Web UI answer and persisted message, try unsupported or missing source data degrades honestly with missing setup, missing auth/config, empty state, or a degraded dependency. | owning requirement for `CITE-002` / `CITE-002` | Web UI answer and persisted message | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to CITE-002. | The user sees an honest setup, retry, or degraded-state result for CITE-002; no fake success is accepted. | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
| `CITE-UC-003` | Ask a current-data prompt that triggers `web_search`, then verify citation UI appears only when sources were returned. | `docs/requirements_and_learnings/08_Citation_Rendering.md`, `docs/requirements_and_learnings/10_Open_Source_Web_Search.md` / `CITE-004` | LibreChat browser answer and citation expansion | Persisted `web_search` artifacts, returned-source counts, SearXNG/Firecrawl local search backend health, hosted search backend status, request logs, rendered citation chips/details | Source markers and expandable citations exist only for real returned web evidence; no source is fabricated when search fails. | FAIL (escaped 2026-05-18 by no-evidence search path; rerun pending) |

## `CITE-004` - Search Citations Must Prove Returned Evidence

- Requirement: `docs/requirements_and_learnings/08_Citation_Rendering.md` and
  `docs/requirements_and_learnings/10_Open_Source_Web_Search.md`.
- Risk covered: a user asks Viventium to look something up, the search request can fail or return no
  evidence, yet QA may not verify whether the citation UI correctly omits, degrades, or renders
  source detail based on actual returned artifacts.
- Preconditions: browser chat running with Web Search enabled; search provider health intentionally
  recorded; synthetic public current-data prompt available.
- Steps:
  1. Send a synthetic web-search prompt in the browser.
  2. Inspect visible answer for source markers, citation chips, and expanded source details.
  3. Inspect persisted `web_search` artifacts and source counts.
  4. Compare rendered citations with API logs and provider health.
- Expected result: citations render and expand only when returned web evidence exists; when search
  fails, the UI/answer degrades honestly without fabricated citation labels.
- Forbidden result: citation UI or source wording implies evidence exists when persisted
  `web_search` artifacts contain no returned sources or the provider failed.
- Evidence to capture: sanitized browser observation, citation expanded-state result, source count,
  local search backend health, hosted search backend status, request failure/source summary, persisted message
  artifact summary.
- Automation: Playwright/browser QA plus prompt/rendering tests.
- Last run: FAIL (escaped 2026-05-18 by no-evidence search path; rerun pending).
