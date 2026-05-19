# Local Docker Services QA Cases

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `LDS-001` | `39_Installer_and_Config_Compiler.md` Meilisearch auth readiness; `50_Stable_Dev_Runtime.md` singleton runtime | Conversation search only reports ready when Meilisearch can accept indexing/settings tasks for the active runtime | CLI/API/logs | Service API probes plus release tests | 2026-05-19 `PASS` ([report](reports/2026-05-19-meilisearch-firecrawl-resource-audit.md)) |
| `LDS-002` | `50_Stable_Dev_Runtime.md` shared singleton services; public/private boundary | Local Docker services are Viventium-owned or clearly identified as foreign before resource or port remediation | Docker/CLI | `docker ps`, `docker inspect`, port probes | 2026-05-19 `PARTIAL` ([report](reports/2026-05-19-meilisearch-firecrawl-resource-audit.md)) |
| `LDS-003` | `10_Open_Source_Web_Search.md` bounded local Firecrawl profile | Local Firecrawl starts with laptop-appropriate limits and honest health checks | Docker/API/logs | Compose inspection, `docker stats`, HTTP probes | 2026-05-19 `PASS` ([report](reports/2026-05-19-meilisearch-firecrawl-resource-audit.md)) |
| `LDS-004` | `10_Open_Source_Web_Search.md` SearXNG readiness; `45_Runtime_Feature_QA_Map.md` web search prerequisites | SearXNG is visibly reachable and bounded enough for local runtime use | Browser/Docker/logs | Playwright snapshot, compose inspection, logs | 2026-05-19 `PASS` ([report](reports/2026-05-19-meilisearch-firecrawl-resource-audit.md)) |

## Natural User Use Case Checklist

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `LDS-UC-001` | Start or inspect local runtime and rely on conversation search | `39_Installer_and_Config_Compiler.md` / `LDS-001` | CLI/API/logs | Meilisearch `/version`, `/stats`, `/tasks`, native logs, launcher source | Search reports ready only when indexes and tasks are healthy | 2026-05-19 `PASS` |
| `LDS-UC-002` | Check why local Docker services feel heavy | `50_Stable_Dev_Runtime.md` / `LDS-002`, `LDS-003`, `LDS-004` | Docker/CLI | `docker ps`, `docker stats`, `docker inspect`, compose files | Heavy services are named, bounded, and ownership is unambiguous | 2026-05-19 `PARTIAL` |
| `LDS-UC-003` | Use local SearXNG as the browser-visible search prerequisite | `10_Open_Source_Web_Search.md` / `LDS-004` | Browser with Playwright CLI | Browser snapshot, SearXNG logs, compose config | SearXNG root UI is visible and supporting logs/config do not hide blocking failures | 2026-05-19 `PASS` |
| `LDS-UC-004` | Use local Firecrawl as the scraper prerequisite | `10_Open_Source_Web_Search.md` / `LDS-003` | API/CLI/logs | HTTP banner/health probes, Firecrawl logs, Docker stats, compose config | Health/status uses the same contract as runtime and resource use is bounded or honestly degraded | 2026-05-19 `PASS` |

## `LDS-001` - Meilisearch functional readiness

- Requirement: local Meilisearch readiness must authenticate with the configured key and prove the
  active indexes can accept settings and document tasks.
- Risk covered: `/health` is green while search/indexing tasks fail in the background.
- Preconditions: local runtime search enabled; no private conversation data recorded in evidence.
- Steps:
  1. Probe Meilisearch `/health`, `/version`, `/stats`, and recent `/tasks` with the configured key.
  2. Inspect native or container logs for task failure class.
  3. Compare the running Meilisearch version with task/index compatibility errors.
  4. Inspect launcher and sync code that decides readiness/backfill.
- Expected result: no recent index-version task failures; no growing failed task class; readiness
  fails closed if indexing cannot work.
- Forbidden result: authenticated `/health` passes while document or settings tasks fail repeatedly.
- Evidence to capture: sanitized counts, timestamps, failure class, source lines, and report link.
- Full-view evidence minimum: API probe, logs, source readiness path, generated runtime mode, and
  automated release checks.
- Automation: release tests plus service probes.
- Last run: 2026-05-19 `PASS`.

## `LDS-002` - Docker ownership and port conflict

- Requirement: local singleton services must be owned, labeled, bounded, and non-conflicting before
  remediation or status can be trusted.
- Risk covered: a foreign container on a Viventium port makes fixes ambiguous or steals the bind.
- Preconditions: Docker daemon running.
- Steps:
  1. List containers and port listeners.
  2. Inspect restart policies, labels, binds, and limits.
  3. Compare ports with Viventium runtime profiles.
- Expected result: active services on Viventium ports are Viventium-owned or reported as foreign
  blockers with a clear user decision required.
- Forbidden result: a foreign `restart=always` service silently occupies a Viventium profile port.
- Evidence to capture: sanitized inspect summary, port table, and resource sample.
- Last run: 2026-05-19 `PARTIAL`.

## `LDS-003` - Firecrawl local resource and readiness contract

- Requirement: Firecrawl local stack uses laptop-friendly resource limits and the runtime/status
  probes match the service's actual local health surface.
- Risk covered: self-hosted scraper uses excessive idle resources or status checks strand startup.
- Preconditions: Docker daemon running; local web search enabled.
- Steps:
  1. Inspect Firecrawl compose resource and concurrency defaults.
  2. Probe root banner and `/health`.
  3. Inspect logs for expected local warnings versus blocking failures.
  4. Sample live Docker resource usage.
- Expected result: source limits are present, root or supported health probe succeeds, and status
  reports any missing endpoint honestly.
- Forbidden result: only a stricter health endpoint is used when the runtime accepts the API banner
  or container readiness contract.
- Last run: 2026-05-19 `PASS`.

## `LDS-004` - SearXNG local visibility and bounds

- Requirement: local SearXNG must be reachable as the search prerequisite and have clear resource
  and config maintenance behavior.
- Risk covered: local search appears reachable but config drift, missing limiter config, or unbounded
  container behavior creates hidden resource or reliability issues.
- Preconditions: Docker daemon running; SearXNG enabled.
- Steps:
  1. Open SearXNG root in a real browser with Playwright CLI.
  2. Inspect compose limits/logging.
  3. Inspect logs for settings and limiter warnings.
  4. Probe root HTTP status.
- Expected result: visible UI loads; logs do not contain untriaged blocking errors; resource bounds
  are intentional.
- Last run: 2026-05-19 `PASS`.
