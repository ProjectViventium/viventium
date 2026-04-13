# Self-Hosted Firecrawl (LibreChat v0.4)

## Goal
Run Firecrawl locally for LibreChat web scraping to avoid paid API usage while preserving
the standard web search pipeline.

## Configuration
Environment variables (in `.env.local`):
- `START_SEARXNG` (set `true` to launch SearxNG with the stack)
- `SEARXNG_PORT` (host port for local SearxNG, e.g., `8082`)
- `SEARXNG_INSTANCE_URL` (base URL for LibreChat, e.g., `http://localhost:8082`)
- `SEARXNG_API_KEY` (optional, if your SearxNG instance requires auth)
- `FIRECRAWL_API_KEY` (shared with the Firecrawl container)
- `FIRECRAWL_PORT` (host port for local Firecrawl)
- `FIRECRAWL_BASE_URL` (base URL for LibreChat, e.g., `http://localhost:3003`)
- `FIRECRAWL_VERSION` (API version for LibreChat, e.g., `v2`)
- `FIRECRAWL_API_URL` (legacy v0.3 stack expects a versioned URL, e.g., `http://localhost:3003/v2`)

LibreChat config (`viventium_v0_4/LibreChat/librechat.yaml`):
- `searxngInstanceUrl: "${SEARXNG_INSTANCE_URL}"`
- `searchProvider: "searxng"`
- `firecrawlApiUrl: "${FIRECRAWL_BASE_URL}"`
- `firecrawlVersion: "${FIRECRAWL_VERSION}"`

## Runtime wiring
- Docker Compose: `viventium_v0_4/docker/firecrawl/docker-compose.yml`
- SearxNG Compose: `viventium_v0_4/docker/searxng/docker-compose.yml` (if present)
- Launcher: `viventium_v0_4/viventium-librechat-start.sh`
  - Uses `START_FIRECRAWL=true` by default.
  - Uses `START_SEARXNG=true` by default.
  - `--skip-firecrawl` disables it for a run.
  - SearXNG readiness must probe the local root page, not a live search query, because cold search requests can be slow enough to create false installer/startup failures on clean Macs.
  - Firecrawl readiness in the launcher, install wait loop, and status must share the same local-health contract (`/health`, API banner, or the expected local API container) so first-run startup does not strand on a stricter probe than the runtime itself.

## Notes
- Installer UX contract:
  - if Docker Desktop is already available, Easy Install should enable local SearXNG + Firecrawl without extra friction
  - if Docker Desktop is not available, the wizard must still treat web search as first-class:
    - explain that choosing local search/scraping will make preflight install Docker Desktop automatically
    - offer the hosted Serper + Firecrawl API path with direct key URLs
    - explain that Firecrawl is what gives Viventium the full page content behind search results
- Firecrawl expects a valid `fc-` API key format (or UUID). LibreChat sends `FIRECRAWL_API_KEY`.
- If Firecrawl expects a different API version, update `FIRECRAWL_VERSION` and
  `FIRECRAWL_API_URL` together to keep v0.4 and v0.3 aligned.
- The canonical config under `~/Library/Application Support/Viventium/config.yaml` owns whether
  web search is actually enabled on a machine. The tracked `local.librechat.yaml` snapshot is not
  the live switch. If `integrations.web_search.enabled` is false or missing, the compiler will emit
  `interface.webSearch: false`, remove the top-level `webSearch` block, and the built-in agent tool
  surface will drift accordingly on restart.
- Runtime auth must accept both `${ENV_VAR}` references in tracked YAML and the
  already-interpolated literal values returned by LibreChat's loaded AppConfig.
- `rerankerType` is optional. If source-of-truth config does not declare a reranker,
  the runtime must not auto-enable one from unrelated ambient shell env.
- The compose stack includes Redis, RabbitMQ, Postgres (nuq), and the Playwright
  microservice. Defaults are `postgres`/`postgres` for Postgres and
  `firecrawl`/`firecrawl` for RabbitMQ; update the compose file if you need
  different values.
- The local single-user defaults should stay lightweight enough for a clean MacBook install:
  - prefer `rabbitmq:3-alpine` over the management image unless the local admin UI is explicitly
    needed
  - keep Playwright shared memory conservative (`256m`) for single-user local scraping
  - keep the Firecrawl API container on a bounded but sane default budget
    (`FIRECRAWL_API_MEM_LIMIT`, default `1536m`) so local scraping stays reliable
  - keep the Playwright helper on a lower bounded budget
    (`FIRECRAWL_PLAYWRIGHT_MEM_LIMIT`, default `768m`)
  - tune Firecrawl worker/concurrency knobs for a single-user laptop profile instead of shipping
    upstream multi-worker defaults
  - default Firecrawl logging should be `warn`, not `info`, for local installs
  - if Docker Desktop is configured below roughly `4 GB`, the installer and post-install summary
    must warn honestly that local Firecrawl may still restart and that Firecrawl API is the
    supported fallback

## Tests
- `./viventium_v0_4/viventium-librechat-start.sh`
- `curl -fs "${FIRECRAWL_BASE_URL%/}/health"` (if the service exposes a health endpoint)
- `curl -fs "${FIRECRAWL_BASE_URL%/}/"` (base API response)
- `curl -fs "${SEARXNG_INSTANCE_URL%/}/"`
