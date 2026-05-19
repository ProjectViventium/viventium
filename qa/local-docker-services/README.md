# Local Docker Services QA

## Scope

This QA area covers local infrastructure services that support the installed and development
Viventium runtime:

- Meilisearch conversation search
- SearXNG local search
- Firecrawl local scraping
- adjacent Docker-backed singleton services when they affect resource pressure or port ownership

The folder is for public-safe service health, resource, ownership, and regression evidence. Raw
runtime state, secrets, private data, and machine-local paths stay out of the repo.

## Owning Docs

- [`docs/requirements_and_learnings/10_Open_Source_Web_Search.md`](../../docs/requirements_and_learnings/10_Open_Source_Web_Search.md)
- [`docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md`](../../docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md)
- [`docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md`](../../docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md)
- [`docs/requirements_and_learnings/50_Stable_Dev_Runtime.md`](../../docs/requirements_and_learnings/50_Stable_Dev_Runtime.md)
- [`docs/requirements_and_learnings/32_Conversation_Recall_RAG.md`](../../docs/requirements_and_learnings/32_Conversation_Recall_RAG.md)

## Quality Bar

- Status must distinguish "port answers" from functional readiness.
- Meilisearch readiness must include authenticated access and task/index health, not only `/health`.
- Docker-backed services must have intentional ownership, resource bounds, restart policy, and log
  behavior.
- Local web-search and scraping failures must be classified as provider unavailable, timeout,
  rejected request, unsupported configuration, missing prerequisite, or successful empty result.
- Evidence must include real service probes plus supporting source, docs, logs, and generated runtime
  config.

## Latest Status

- 2026-05-19: [`Meilisearch and Docker Resource Audit`](reports/2026-05-19-meilisearch-firecrawl-resource-audit.md) repaired Viventium-owned Meilisearch derived search state, added source-owned resource caps/readiness gates for Meilisearch, Firecrawl, and SearXNG, and left the foreign `chat-meilisearch` compat-port container untouched pending an explicit owner decision.
