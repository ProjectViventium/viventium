<!-- qa-evidence-exempt: Legacy or historical run note predates the V2 QA report template; retained as public-safe context, not a fresh completion claim. -->

# Meilisearch And Docker Resource Audit - 2026-05-19

## Problem Statement

Public-safe summary: the local operator reported that Meilisearch and other Docker-backed services,
especially Firecrawl, were consuming too many laptop resources. The requested audit was to inspect
source code, logs, runtime usage, docs, and current upstream guidance; identify configuration gaps;
validate fixes with tests; and get a review-only Claude second opinion before landing changes.

The original private wording is intentionally not reproduced in this public QA artifact.

## Summary

- Result: `PASS` for Viventium-owned Meilisearch functional readiness and rebuild; `PASS` for Firecrawl/SearXNG resource caps and live reachability; `PARTIAL` for Docker ownership because a foreign `chat-meilisearch` container still exists on the compat port and was intentionally left untouched.
- Build/source under test: current `/path/to/viventium` checkout.
- Runtime/artifact under test: installed local runtime state under `~/Library/Application Support/...`, Viventium Docker singleton services, and LibreChat nested source.
- Cloud scope: no cloud service was changed.
- Protected state: no Mongo conversations, users, sessions, agents, presets, assistants, or runtime config files were deleted. Meilisearch indexes/tasks are derived local search state; the incompatible old derived Meili data was archived before rebuilding.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `LDS-001` | `PASS` | Meilisearch v1.43.0 in Docker, `MEILI_ENV=production`, local bind, 768MiB/1 CPU/128 PID cap, log rotation, failed/processing/enqueued tasks all `0`, `messages` and `convos` primary key `_meiliId`. | Old incompatible derived Meili data archived, not deleted; indexes rebuilt from Mongo. |
| `LDS-002` | `PARTIAL` | Viventium-owned services are labeled and capped; foreign `chat-meilisearch` on `7701` remains clearly identified as non-Viventium-owned. | Not stopped or removed without user approval. |
| `LDS-003` | `PASS` | Firecrawl API/root probe returns 200; compose/live inspect show memory/CPU/PID/log caps for API, Playwright, Redis, RabbitMQ, and Postgres. | Idle API memory remains high by service design but is now bounded. |
| `LDS-004` | `PASS` | SearXNG root returns 200 and Playwright shows visible UI; compose/live inspect show SearXNG and Valkey memory/CPU/PID/log caps. | Settings/limiter/Wikidata warnings are classified as non-blocking for this local profile. |

## Implemented Remediation

- Meilisearch launcher defaults:
  - image pinned to `getmeili/meilisearch:v1.43.0`
  - `MEILI_ENV=production`
  - local bind only
  - Docker caps: 768MiB memory, 1.0 CPU, 128 PIDs
  - log rotation: json-file, 5MiB x 3
  - indexing caps: `MEILI_MAX_INDEXING_MEMORY=512MiB`, `MEILI_MAX_INDEXING_THREADS=1`
- Meilisearch readiness now requires authenticated access plus recent failed-task health. It fails closed on index-version/incompatibility failures instead of continuing to enqueue work.
- LibreChat Meili plugin now:
  - avoids repeated no-op settings-update churn
  - uses `_meiliId` as the Meili primary key so valid LibreChat IDs with disallowed Meili ID characters still index
  - preserves real `messageId` and `conversationId` for result lookup
  - waits for Meili task success before setting Mongo `_meiliIndex=true`
  - throws on failed waited Meili tasks
  - excludes listen-only transcript rows from search parity because they are intentionally not live-search documents
- Local search sync now validates `_meiliId` schemas, refuses legacy primary keys, checks recent failed tasks, and measures parity against search-eligible documents.
- Firecrawl and SearXNG compose files now include live-surviving memory, CPU, PID, and log controls.

## Live Repair Evidence

| Surface | Result |
| --- | --- |
| Meilisearch task cleanup | Removed 119 stale failed task records from the earlier invalid-ID attempt through Meili's task API; failed tasks after cleanup: `0`. |
| Meilisearch index parity | `messages`: 22,156 search-eligible Mongo docs, 22,156 Meili docs. `convos`: 2,108 Mongo docs, 2,108 Meili docs. |
| Mongo protected-state counts | Current sanitized counts: messages 22,163, conversations 2,108, users 7, agents 22, presets 0, assistants 0, sessions 17. |
| Listen-only exclusion | 1 listen-only transcript row remains in Mongo and is intentionally excluded from Meili search parity. |
| Runtime restart | Supported local path `bin/viventium dev-runtime activate-current --validate --restart ...` completed; LibreChat API, frontend, and Modern Playground ports listened afterward. |
| Browser QA | Playwright opened the LibreChat login page and captured [login screenshot](../artifacts/librechat-login-after-runtime-repair-2026-05-19.png). Console had 0 errors; network requests to `/api/config`, `/api/auth/refresh`, and `/api/banner` returned 200. |
| Firecrawl | Root banner returned 200; live inspect confirms caps and log rotation. `/health` is not the local health contract for this image and returns 404. |
| SearXNG | Root returned 200; Playwright evidence remains visible in [SearXNG screenshot](../artifacts/searxng-root-after-caps-2026-05-19.png). |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- |
| `LDS-UC-001` | Start or inspect local runtime and rely on conversation search | Meilisearch API, Mongo counts, sync script, launcher logs/source | `PASS` | Local runtime started and API/frontend became reachable. | Authenticated private chat search UI was not run to avoid using or exposing a real account/conversation. |
| `LDS-UC-002` | Check why local Docker services feel heavy | Docker inspect/stats, compose source | `PARTIAL` | Heavy services are now bounded and named. | Foreign `chat-meilisearch` remains a user decision; Firecrawl still has a high bounded idle footprint. |
| `LDS-UC-003` | Use local SearXNG as the browser-visible search prerequisite | Playwright browser and HTTP probe | `PASS` | SearXNG root UI visible; root HTTP 200. | Config maintenance warning should become a future update case. |
| `LDS-UC-004` | Use local Firecrawl as scraper prerequisite | HTTP probe, logs, Docker inspect/stats | `PASS` | Root banner 200 and live capped containers. | A real crawl was not run because this task was resource/startup remediation, not scraper correctness. |

## Residual Risks And Follow-Ups

- Foreign `chat-meilisearch` on `7701` is still present, not Viventium-owned, and not modified. It should be presented as an explicit owner decision before Viventium uses or frees that compat port.
- Firecrawl API still idles around the high hundreds of MiB inside its new 1.5GiB cap. This is bounded now, but true laptop comfort would require on-demand startup or a stronger disable-by-default UX.
- SearXNG logs still report an upstream settings file update, missing `limiter.toml`, and a Wikidata 403. `limiter: false` makes the limiter warning non-blocking for this local private profile, but config refresh should be tracked separately.
- Ollama embeddings were unreachable during runtime logs. That is outside this Docker/Meili repair and does not affect Meilisearch/Firecrawl/SearXNG caps, but recall/embedding QA should not claim green while Ollama is down.
- A logged-in private conversation search was not exercised because doing so would touch private account/conversation state. Meili API search was validated instead, with no private content recorded.

## Claude Review-Only Check

Claude review-only completed after a shorter sanitized prompt. It challenged:

1. Prove Mongo-to-Meili parity, not just zero failed tasks.
2. Distinguish source-owned durability from live-only container edits.
3. Avoid overclaiming user-visible search because browser login/search with private data was not run.
4. Keep the foreign `chat-meilisearch` decision separate.
5. Treat Firecrawl/SearXNG warnings as classified residual risks.

Follow-up actions taken after Claude review:

- Added sanitized Mongo counts and explicit eligible-document parity.
- Verified live caps and source-owned launcher/compose changes after restart.
- Marked the private authenticated chat-search UI path as not run instead of claiming it.
- Kept `LDS-002` as `PARTIAL` because the foreign container remains.

## Test Evidence

```bash
bash -n viventium_v0_4/viventium-librechat-start.sh

uv run --with pytest --with pyyaml python -m pytest \
  tests/release/test_detached_librechat_supervision.py \
  tests/release/test_local_web_search_compose.py \
  tests/release/test_meilisearch_resource_guardrails.py -q
# 19 passed

cd viventium_v0_4/LibreChat
npm run build:data-schemas
npm run test:packages:data-schemas -- src/models/plugins/mongoMeili.spec.ts
# 48 passed

node -c api/db/indexSync.js
node -c scripts/viventium-sync-local-search.js

docker compose -f viventium_v0_4/docker/firecrawl/docker-compose.yml config
docker compose -f viventium_v0_4/docker/searxng/docker-compose.yml config

SEARCH=true MEILI_SYNC_BATCH_SIZE=100 MEILI_SYNC_DELAY_MS=100 \
  node scripts/viventium-sync-local-search.js
# Local search index already current
```

Additional live probes:

- Meilisearch v1.43.0 JS SDK compatibility probe: health, index create, settings update, document add, search, filter, and task polling succeeded.
- Firecrawl root: 200 with API banner.
- SearXNG root: 200.
- LibreChat API config: 200.
- LibreChat frontend root: 200 and browser-visible login page.
- Modern Playground root: 200.

## Official Documentation Cross-Check

- [Meilisearch configuration reference](https://www.meilisearch.com/docs/resources/self_hosting/configuration/reference): `MEILI_ENV`, master-key behavior, max indexing memory, and max indexing threads.
- [Meilisearch releases](https://github.com/meilisearch/meilisearch/releases): v1.43.0 is the current stable release used for the local pin at the time of this audit.
- [Meilisearch task API](https://www.meilisearch.com/docs/reference/api/tasks): failed task inspection and task deletion are first-class API operations.
- [Meilisearch backup overview](https://www.meilisearch.com/docs/resources/self_hosting/data_backup/overview): dumps are the portable migration path; local derived indexes can also be archived and rebuilt from Mongo when source data is protected.
- [Docker resource constraints](https://docs.docker.com/engine/containers/resource_constraints/): memory, CPU, and PID controls are supported container guardrails.
- [Docker logging drivers](https://docs.docker.com/engine/logging/configure/): json-file rotation prevents unbounded local log growth.
- [Firecrawl self-host configuration](https://firecrawl-firecrawl.mintlify.app/self-hosting/configuration): self-hosted Firecrawl uses Docker services and env-configured worker/runtime controls.
- [SearXNG Docker installation](https://github.com/searxng/searxng/blob/master/docs/admin/installation-docker.rst): compose is the expected container deployment shape.
- [SearXNG limiter docs](https://dalf.github.io/searxng/admin/searx.limiter.html): limiter config is relevant when limiter protection is enabled.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts and conclusions only.
