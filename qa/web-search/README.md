# Web Search QA

## Scope

- Owning requirements: see `docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md` for the current requirement mapping.
- Primary outcome: Browser and chat web-search flows use configured search/scrape providers and report degraded local services honestly.
- User-visible surfaces: web chat, SearXNG/Firecrawl, answer evidence.

## Quality Bar

- Exercise the real user surface when the behavior is visible.
- Compare the visible result with source code, generated/runtime config, logs, persisted state, and docs.
- Include cross-surface natural use cases: browser chat, Telegram when enabled, and voice/LiveKit
  requests that ask the agent to look something up.
- Web Search UI capability state is not proof that search worked. Every pass must compare visible
  output with provider health, persisted tool-call artifacts, and API/tool logs.
- Empty/error search output must be classified before the user-facing result is accepted:
  successful-empty, provider unavailable, timeout, rate limit, auth/config missing, request
  rejected, unsupported configuration, and local prerequisite unavailable are different outcomes.
- For local SearXNG/Firecrawl, Docker daemon and container state are part of the evidence chain. QA
  must not miss that Docker Desktop/local containers are off and then call the visible answer
  complete.
- For named-entity, contact, date, event, or current-fact lookups, one failed `web_search` attempt
  must trigger a browser/local-delegation fallback check when available.
- Keep public evidence sanitized: no secrets, account identifiers, raw private logs, local absolute paths, or private screenshots.

## Required Suites

| Suite | Command or Manual Path | Required When |
| --- | --- | --- |
| Feature contract | `tests/release/test_local_web_search_compose.py` | Relevant code/docs/config changes |
| Full-view QA | Real surface -> visible result -> supporting logs/state/docs -> sanitized report | User-visible behavior changes |
| Public-safety scan | Pattern scan over report/diff | Before PR/public push |

## Current Status

- Case catalog: `cases.md`.
- Reports: `reports/` for new dated public-safe runs.
- Last catalog update: 2026-05-17.
- 2026-05-18 escaped gap: voice/chat search request returned generic degraded wording while local
  evidence showed `web_search` tool-call parts plus SearXNG failures and unavailable local
  SearXNG/Firecrawl health. `WEB-004` is now the regression owner until the product fix and full
  user-path rerun pass.
