<!-- qa-evidence-exempt: Legacy or historical run note predates the V2 QA report template; retained as public-safe context, not a fresh completion claim. -->

# Conversation Recall RAG Runtime Guardrails And QA

## Scope

- Feature: Conversation Recall RAG.
- Requirement: `docs/requirements_and_learnings/32_Conversation_Recall_RAG.md`.
- Cases: `RAG-001`, `RAG-002`, `RAG-UC-001`, `RAG-UC-002`, `RAG-UC-003`.
- Trigger: verify Conversation Recall still works after local Docker service remediation, without
  touching cloud services or private conversations/configs.

## Change Under Test

- Added local Docker guardrails to the Conversation Recall RAG sidecars:
  - RAG API: loopback publish, memory/CPU/PID caps, Docker log rotation.
  - PGVector: loopback publish, memory/CPU/PID caps, Docker log rotation.
- Preserved the existing host-mounted PGVector data path; no volume deletion was used.
- Did not change Conversation Recall semantics:
  - no prompt or runtime recall-intent heuristics changed
  - no corpus selection, health/freshness gates, or vector attachment rules changed
  - no Mongo conversation rows, saved memories, user configs, or cloud settings were modified

## Online Alignment

- Docker Compose service docs define service-level `logging`, `mem_limit`, and related service
  resource attributes.
- Docker JSON-file logging docs document `max-size` and `max-file` log rotation.
- Docker port-publishing docs warn that publishing without a host IP exposes ports broadly, and
  document loopback publishing for host-only access.

Conclusion: the RAG sidecar guardrails follow current Docker-documented service controls and align
with the local-only Conversation Recall design.

## Evidence

### Runtime

- RAG health returned `{"status":"UP"}` after applying the compose change.
- LibreChat API health returned `OK`.
- LibreChat frontend returned the login page.
- Ollama was reachable and had `qwen3-embedding:0.6b` available.
- After synthetic QA, the Ollama embedding runner was explicitly unloaded:
  - before cleanup, the Recall embedding model was temporarily resident because the synthetic RAG
    query had just used it
  - after cleanup, `ollama ps` reported no loaded models
  - RAG health still returned `{"status":"UP"}` and the model remained installed for on-demand use
- Root cause for the temporary runner residency:
  - the RAG image's LangChain `OllamaEmbeddings` client did not set `keep_alive`
  - Ollama's default keeps models loaded for 5 minutes after requests
  - the RAG sidecar now sets an explicit Viventium default keep-alive of 300 seconds for local Ollama
    embeddings, matching Ollama's default while rejecting indefinite residency
- Decision record for the keep-alive lever:
  - this laptop/local-prod environment keeps the 300-second default because active chat speed matters
    and the model should stay warm during normal conversational pauses
  - lower values are reserved for battery/low-resource profiles where cold Recall loads are acceptable
  - future workstation, appliance, or server-style cognitive runtimes should raise the same positive
    seconds lever to keep embeddings hot, with resource monitoring sized for that environment
  - the lever changes only residency/performance policy, not recall eligibility, health/freshness,
    corpus content, prompts, or tool behavior
- Automatic unload regression:
  - a second synthetic Recall upload/query loaded the embedding model temporarily
  - with a 30-second test override, `ollama ps` reported no loaded models after the configured
    keep-alive window without manual cleanup
  - the synthetic vector rows were deleted and the post-cleanup count for the QA prefixes was `0`
- Live RAG API container after apply:
  - published only on loopback host port `8110`
  - memory cap `1536 MiB`
  - CPU cap `1.00`
  - PID cap `160`
  - Docker JSON log rotation `5m x 3`
- Live PGVector container after apply:
  - published only on loopback host port `5433`
  - memory cap `512 MiB`
  - CPU cap `0.50`
  - PID cap `96`
  - Docker JSON log rotation `5m x 3`
- Runtime resource sample after synthetic QA:
  - RAG API: about `513 MiB / 1.5 GiB`, low CPU, 6 PIDs
  - PGVector: about `42 MiB / 512 MiB`, low CPU, 17 PIDs

### Synthetic RAG Path

Used public-safe throwaway data with a synthetic marker.

- Authenticated `/embed`: passed.
- `/documents/exists` after upload: passed.
- `/query`: returned the exact synthetic marker.
- `DELETE /documents`: passed.
- `/documents/exists` after delete: absent as expected.
- PGVector synthetic-row cleanup check: `0` rows remained for the synthetic prefix.
- Temporary local QA text files: none remained.

### Logs

- RAG API logs after the successful synthetic run showed no errors, exceptions, tracebacks, OOMs, or
  killed-process lines.
- PGVector logs showed no errors, fatals, panics, corruption, OOMs, or killed-process lines.
- One earlier unauthenticated `/embed` 401 was caused by the first QA probe before switching to the
  same short-lived JWT pattern LibreChat uses; it did not write data.

### Browser

- Opened the local Viventium login page with Playwright CLI.
- Page title: `Viventium`.
- Visible state: login form with credential fields and Continue button.
- Console: 0 errors.
- Authenticated browser chat recall was not run because that would require either private user
  session access or provider/cloud interaction, both outside this task's safety constraints.

### Automated Tests

- Release/contracts:
  - `uv run --with pytest --with pyyaml python -m pytest tests/release/test_rag_api_override_contract.py tests/release/test_ollama_embeddings_prereqs.py tests/release/test_rag_compose_resource_guardrails.py tests/release/test_config_compiler.py -q`
  - Result: `97 passed`.
- LibreChat backend:
  - `npm run test:api -- models/Message.spec.js test/app/clients/tools/util/fileSearch.test.js`
  - Result: `77 passed`.
- LibreChat packages/data-provider:
  - `npm run test:packages:data-provider -- specs/conversationRecall.spec.ts`
  - Result: `8 passed`.
- LibreChat packages/api:
  - `npm run test:packages:api -- src/agents/conversationRecall.test.ts src/agents/__tests__/conversationRecallAvailability.test.ts src/files/rag.spec.ts`
  - The package script ran the full package suite.
  - Result: `109` suites passed, `2777` tests passed, `1` skipped.

## Case Results

| Case | Result | Evidence |
| --- | --- | --- |
| `RAG-001` | `PARTIAL` | RAG API, vector lifecycle, health, logs, docs, source, and automated tests passed. Authenticated browser chat recall was intentionally not run to avoid private conversation access or cloud use. |
| `RAG-002` | `PASS` | This report uses synthetic data only, sanitized counts/statuses, no credential material, no raw private logs, no screenshots, no raw conversation content, and no local absolute paths. |
| `RAG-UC-001` | `PARTIAL` | Same as `RAG-001`; backend/sidecar/user-visible login surface passed, authenticated chat recall not run. |
| `RAG-UC-002` | `PASS` | Public-safe report and supporting tests created. |
| `RAG-UC-003` | `PASS` | Report rechecked after cleanup and test reruns. |

## Claude Review

- Review-only local Claude pass used sanitized diffs and evidence only.
- Verdict: aligned with the documented Conversation Recall design.
- Must-fix before final: none.
- Non-blocking notes:
  - default caps can make RAG fail closed if a very large local corpus exceeds the budget
  - the env-var override path should be used for those larger local corpora
  - no restart policy change is required for this fix because restart loops can hide persistent
    resource pressure

## Residual Risk

- The authenticated browser chat path remains unrun in this pass. Running it safely requires either a
  disposable local QA account with a local/offline chat provider or explicit approval to use a real
  authenticated session. This pass therefore proves the local Recall/RAG service path and guards
  against resource runaway, but does not claim full private-account chat UX acceptance.
