# Conversation Recall RAG

**Document Version:** 2.2
**Date:** 2026-04-09
**Owner:** Viventium Core
**Status:** Implemented in `viventium_v0_4`

## Purpose

Provide opt-in retrieval-augmented recall from a user’s own historical conversations, reusing the
existing file-search pipeline instead of introducing a new tool surface.

This feature adds two user-facing controls:

1. Global recall for the full user corpus.
2. Agent-level recall scoped to conversations where that agent was used.

## Product Requirements

1. User data isolation.
2. Explicit opt-in controls.
3. Path of least resistance.
4. Scope policy with agent toggle priority.
5. Proactive indexing.
6. Honest freshness semantics.

## Public-Safe Technical Design

- Build deterministic virtual files for conversation recall corpora.
- Embed them via the existing vector pipeline.
- Persist as file records with a recall context.
- Inject these files into runtime file-search resources when policy allows.
- When the configured embeddings provider is explicitly OpenAI, prefer a user-scoped OpenAI auth
  override when the current user has a connected OpenAI account or stored OpenAI user key
  available through LibreChat.
- When the configured embeddings provider is explicitly OpenAI, connected-account subscription
  tokens must target the platform embeddings endpoint rather than the Codex chat/replies base URL.
- When the configured embeddings provider is explicitly OpenAI, preserve the existing environment-
  key embeddings path as the fallback when no user-scoped OpenAI override exists or when the
  request-scoped override is rejected for auth/config reasons.
- Do not silently reroute conversation-recall embeddings to a different inference provider merely
  because another chat-capable API key exists in the runtime. Adding a new embeddings provider is a
  product change that requires explicit provider support, comparable quality evaluation, and
  cross-surface QA.

## 2026-04-08 Local-First Embeddings / Index Strategy

### Selection rules

- Default conversation-recall indexing must not require a metered remote embeddings provider when a
  supported local path exists.
- Model selection must be driven by explicit config or installer tier metadata, not by runtime
  guessing, provider-label remaps, or one-off user complaints turned into code branches.
- Default-eligible models must have a public-safe license posture for the public install story.
  Non-commercial, research-only, or otherwise restricted licenses are not valid defaults.
- Any change to embeddings provider, model, quantization family, output dimension, or normalization
  contract requires an index-version change and a full re-embed before cutover.
- If the local embedding runtime is unavailable, recall indexing must fail closed and retrieval must
  degrade to lexical recall. There must be no silent fallback to OpenAI or another remote provider.

### Recommended install tiers

#### Medium (default)

- Local runtime: Ollama
- Embedding model: `qwen3-embedding:0.6b`
- Why:
  - Apache-2.0 licensing
  - 32K context window
  - 1024-dimensional output
  - best current shared-model balance for conversation recall under the existing architecture
  - materially better recall quality than the ultra-light fallback while avoiding the severe
    runtime cost of the 4B variant
  - officially distributed through Ollama, which already exposes a simple local embeddings API

#### Experimental high-cost variant (not a recommended install tier today)

- Local runtime: Ollama
- Embedding model: `qwen3-embedding:4b`
- Why:
  - Apache-2.0 licensing
  - 32K context window
  - it can edge out the Medium model on some recall-heavy retrieval slices
  - but the observed gain is too small to justify its large latency and footprint penalty as a
    first-class install tier today
  - keep only as an explicit experimental override until larger-scale evals prove real user-value

#### Ultra-light fallback

- Local runtime: Ollama or Sentence Transformers
- Embedding model family: `embeddinggemma`
- Why:
  - excellent lightweight on-device behavior
  - strong enough to remain a practical fallback when footprint and steady-state latency dominate
  - still trails the default on recall-first quality, so it remains a fallback rather than the
    primary recommendation

#### Future split-model candidate (not valid as a shared default)

- Local runtime: Ollama
- Embedding model: `nomic-embed-text`
- Why:
  - strong file-search-specific retrieval results in local evaluation
  - but materially worse conversation-recall performance than the shared default
  - therefore only relevant if the architecture later grows explicit per-surface embedding-model
    support

#### Default-disqualified model classes

- NC / research-only / non-redistribution-safe licenses
- API-only embedding services when the product goal is local-first recall
- older short-context small models that save little runtime but materially regress retrieval quality
- models that cannot embed the real recall corpus shape without truncation or context failures

### Index / storage options

#### Near-term lowest-change path

- Keep the current recall corpus shape and vector-runtime contract.
- First swap embeddings to a supported local runtime.
- Keep `pgvector` as the baseline index backend for the existing stack.
- Replacing Docker with native PostgreSQL is a separate simplification step, not the only legal way
  to become local-first on embeddings.

#### Medium-term simplification candidate

- Evaluate LanceDB as an embedded local backend that can collapse vector storage and lexical search
  into a single local surface.
- This is promising, but it is not the first decision. Benchmark it first against:
  - the real Viventium episodic corpus shape,
  - Node.js integration stability,
  - hybrid retrieval quality,
  - re-index / migration behavior.

#### Not the default path today

- `sqlite-vec`, Qdrant Edge/local mode, Milvus Lite, Chroma, and similar local-first backends stay
  in the candidate pool, but they are not the default recommendation until they beat the current
  stack on fit, hybrid retrieval, migration risk, and operational simplicity for this product.

### Hybrid retrieval is now a requirement

- Dense-only recall is not enough for short chat messages, named entities, dates, or exact phrasing.
- Near-term hybrid on the current stack should use application-level fusion over:
  - vector hits from the recall corpus, and
  - scoped lexical hits from the existing recall-safe message retrieval path.
- Reciprocal rank fusion or another explicit generic fusion strategy should be used; do not invent
  entity-specific or prompt-specific runtime rules.
- Longer term, a single backend with first-class lexical + vector retrieval may simplify this.

### Tier switch / re-embed contract

- Medium and any alternate tier/model are different vector spaces and must not be queried
  interchangeably.
- Runtime metadata for a recall corpus must record at least:
  - embeddings provider
  - embeddings model id
  - embedding dimension
  - index backend
  - corpus / schema version
- A tier or model change must trigger a background rebuild of the recall corpus before that new
  index is treated as authoritative.
- Cutover must happen only after the replacement corpus is complete and fresh.

### Framework / orchestration note

- LlamaIndex is relevant as a retrieval orchestration layer and is worth evaluating later for
  retriever composition and fusion workflows.
- It is not the first decision.
- First choose the embedding runtime, index backend, versioning contract, and degraded-mode
  semantics. Only then evaluate whether an orchestration layer improves quality enough to justify
  added complexity.

### Shared vs split model note

- The current product cleanly supports one shared embeddings runtime/model for both conversation
  recall and regular file search, plus different retrieval-time knobs per surface.
- The current product does not cleanly support different embedding models for recall and file
  search within the same sidecar/query contract.
- A split-model design would require explicit per-surface embedding metadata, query-time routing,
  cache-key changes, and rebuild/cutover rules. Treat that as architecture work, not a config
  tweak.

### Runtime resilience fallback
- If vector recall is degraded, conversation recall must remain available through the normal
  `file_search` tool path rather than through proactive runtime snippet injection.
- The degraded fallback belongs inside the recall/tool layer after the model chooses to search.
- Exclude the current conversation messages to avoid echoing the current turn.
- The old proactive runtime context injector was intentionally removed.
- The supported degraded continuity path is now:
  - source-only conversation-recall resource attachment at runtime
  - source-backed lexical rescue and reranking inside `file_search`
  - no proactive recall snippet injection before the model chooses the tool

### Indexing timing contract

- Proactive indexing is near-real-time, not instantaneous.
- Debounce and upload-throttling are allowed as long as runtime does not pretend stale vector state
  is current.
- During short indexing lag or prolonged vector outage, degraded lexical recall is the continuity
  contract.

## Runtime Attachment Rules

Conversation recall is a runtime-owned attachment/plumbing feature, not a runtime-owned
query-intent classifier.

- Runtime may attach recall resources when policy allows.
- Runtime must not branch on user prompt text to decide whether recall should run.
- The model decides when to use conversation recall through its system prompt/tool instructions.
- If vector recall is healthy and fresh, runtime may attach a vector-backed recall resource.
- If vector recall is unavailable, stale, or missing, runtime may still attach a source-only recall
  resource so the normal `file_search` path can degrade honestly.

## Explicit Forgetting Boundary

- Saved-memory forgetting and conversation recall are separate product surfaces.
- Removing or rewriting a saved-memory entry does not itself rewrite the historical conversation
  corpus.
- The April 9, 2026 scheduled stale-output investigation showed that stale saved-memory keys alone
  can explain a continuity failure even when recall/file retrieval is also degraded.
- The same day, restarting onto the fixed saved-memory runtime removed the stale saved-memory
  references while the local vector runtime at `localhost:8110` remained unavailable, further
  proving that the two surfaces fail and recover independently.
- Therefore:
  - do not treat conversation recall as the mechanism that makes saved-memory forgetting work
  - do not mutate saved-memory semantics to compensate for a recall outage
  - do not silently invent entity-specific recall filters as a one-off reaction to one forgotten
    name or company
- If the product later adds explicit recall-level forgetting or exclusion behavior, that must be:
  - explicit
  - auditable
  - policy-driven
  - QA-covered as a separate feature

### Health gate

- Do not attach vector-backed conversation-recall resources only because `RAG_API_URL` is set.
- The local/vector runtime must pass a real health check first.
- When the configured embeddings provider is Ollama, launcher readiness must also ensure the
  configured embedding model exists on the configured Ollama host before the RAG sidecar starts.
- If the vector runtime is unreachable, timed out, or otherwise unhealthy, runtime should not
  present vector recall as healthy/current evidence for that run.
- In that degraded state, the supported path is a source-only recall attachment plus tool-level
  fallback through `file_search`, not proactive runtime recall snippets.

### Freshness gate

- Global conversation-recall corpora must be compared against the newest recall-eligible user
  message timestamp.
- If newer recall-eligible messages exist than the latest corpus update, the corpus is stale and
  must not be attached as live evidence.
- Agent-scoped and global recall remain policy-driven, but freshness still determines whether the
  vector corpus is usable in a given run.

### Derivative recall-chatter filter

- Assistant replies that merely echo retrieved history back to the user in response to a
  meta-recall prompt are derivative recall chatter, not new source history.
- These derivative assistant turns must be excluded from:
  - recall-corpus content
  - newest recall-eligible freshness comparisons
  - degraded lexical recall candidate pools
- The April 9, 2026 live web regression showed that letting these derivative assistant turns count
  as recall history creates a self-poisoning loop:
  - the echoed answer becomes "newer" than the real source turn
  - freshness then rejects an otherwise good corpus as stale
  - degraded lexical recall can surface the echoed answer instead of the original source evidence
- The fix is structural:
  - identify derivative assistant recall turns from structured `file_search` attachment provenance
    whose sources point at `conversation_recall:*`
  - identify the related user meta-recall prompt through `parentMessageId`, not by matching one
    English prompt phrase or one QA marker wording
  - keep the real source turn eligible
  - do not loosen the freshness contract itself
- Do not treat this as a license to special-case specific entities, marker strings, or one exact
  complaint. The rule is about derivative retrieval chatter vs source history.

### Upload integrity gate

- Conversation-recall upload success must be judged against the digest of the corpus that actually
  reached the vector store, not just the digest of the source corpus produced in memory.
- If the uploaded digest differs from the source digest, the corpus is degraded and must remain
  eligible for a later rebuild; do not treat it as fully current just because the source digest is
  unchanged.
- The April 9, 2026 live isolated-stack rebuild proved a real failure mode on local Ollama
  embeddings:
  - the RAG API completed a 339-chunk embed in roughly 68 seconds
  - the previous client timeout was 60 seconds
  - LibreChat timed out, retried, and the server still completed the earlier request
  - those retries appended duplicate vector cohorts for the same logical `file_id`
- The hardening required at the owning boundary is:
  - adaptive upload timeout sized to the recall corpus being embedded
  - metadata that separately tracks source digest vs uploaded digest
  - unchanged-corpus short-circuiting only when the uploaded digest matches the source digest
- Live post-fix proof on April 9, 2026:
  - recall file rebuilt to a full uploaded digest match
  - the vector store returned to a single 339-chunk cohort
  - prompt-example chatter remained absent from the rebuilt corpus

### Degraded-mode behavior

- When conversation recall is enabled globally or for the selected agent, the agent system prompt
  must include a configurable YAML-backed instruction telling the model to use `file_search` for
  prior-chat / earlier-context questions.
- That prompt block must compile from tracked or private source-of-truth YAML, not from a
  previously generated runtime `librechat.yaml`.
- The decision to search prior chats is model-owned, not runtime-owned.
- Runtime code must not branch on prompt text, curated personal-fact vocabularies, catch-up
  phrases, or short-query heuristics to decide whether conversation recall should run.
- When vector recall is unavailable or stale, degraded lexical/source-backed recall must happen
  inside the recall tool path after the model chooses `file_search`.
- Degraded recall must still favor recent high-signal messages and corrections, but that ranking
  must come from retrieval/reranking evidence, not prompt-text activation gates.

### Tool-output semantics

- Model-facing tool output must preserve evidence semantics:
  - `no relevant evidence found` means the retrieval path ran and found nothing useful.
  - `no evidence retrieved in the current run` means the result is inconclusive and must not be
    treated as proof that the fact is absent.
- Do not flatten retrieval failures into authoritative-looking “nothing exists” language.

## UX Contract

- Saved memories and conversation recall are different surfaces.
- Saved memories are explicit durable notes/facts the user opted to store.
- Conversation recall is recent and historical chat continuity retrieved from prior messages.
- A failure in one surface must not be papered over by stale or unrelated content from another
  surface.

## 2026-04-08 Learning

A production incident showed that re-enabling saved memories alone does not repair recent recall if
the vector sidecar is down or the corpus is stale. The correct fix is:

1. restore durable memory when intended,
2. gate vector recall on health and freshness,
3. keep the recall-use decision in the model/system prompt instead of runtime query regexes,
4. keep degraded lexical recall inside the `file_search` path,
5. keep tool failure wording explicitly inconclusive,
6. prevent scheduler payloads from masquerading as conversation recall.

## 2026-04-09 Learning

Another follow-up bug showed the next ownership boundary:

- source-of-truth prompt changes can still fail to reach live runtime if compile-time source
  precedence seeds from the last generated runtime YAML instead of tracked/private source YAML
- that failure mode is subtle because code, docs, and even direct compiler rendering can look
  correct while the active generated runtime file silently drops the new field
- the fix belongs at the config/compiler boundary:
  - compile phase prefers private curated source-of-truth when present
  - otherwise compile phase prefers tracked `local.librechat.yaml`
  - previously generated runtime YAML is runtime input for launch, not source input for compile

The same incident also clarified a non-bug-but-important behavior:

- Proactive indexing can legitimately lag a fresh message by debounce/throttle windows.
- That short lag is acceptable only if freshness gating refuses stale corpora and degraded lexical
  recall covers the gap.
- Repeated transient upload failures must be visible in logs and QA because they can pause proactive
  sync entirely until the vector runtime recovers.

### 2026-04-09 Prompt-Owned Recall Triggering

- The April 9, 2026 follow-up removed a still-illegal architecture pattern:
  - runtime prompt-text classifiers deciding whether conversation recall should run
  - proactive runtime snippet injection that bypassed model tool choice
- Product truth after that fix:
  - when conversation recall is enabled globally or for an agent, the runtime injects a
    configurable YAML-backed recall instruction into the agent system prompt
  - the model chooses when to use `file_search`
  - runtime only owns attachment policy, corpus hygiene, freshness/health truthfulness, and
    degraded tool-path fallback
- This is required by `01_Key_Principles.md` and is not optional stylistic cleanup.

## 2026-04-09 Learning

A private local benchmark pass over a real local corpus refined the local-first recommendation.

### Public-safe benchmark shape

- corpus class:
  - approximately `250` conversation-recall chunks
  - approximately `90` uploaded-file chunks
  - approximately `100` recall queries
  - approximately `50` file-search queries
  - approximately `100` recent-message throughput samples
- query types:
  - exact user/file-derived queries
  - local semantic rewrites generated on-device
- all raw corpus content remained outside the repo; only aggregate metrics are recorded publicly

### What changed

1. `qwen3-embedding:0.6b` remains the best current shared default, but only narrowly.
   - It won the overall recall-first shared-model trade-off under the current architecture.
   - That recommendation is grounded, but it should remain open to re-validation on larger or more
     diverse corpora.
2. `qwen3-embedding:4b` no longer merits a recommended `High` tier.
   - Its quality gain over `0.6b` was too small on the real corpus to justify its much higher
     per-message and corpus-embed cost.
   - Keep it experimental only.
3. `embeddinggemma` is a real fallback, not just a theoretical one.
   - Its quality remained competitive enough to keep as the low-footprint option.
4. `nomic-embed-text` is promising only for future split-model file search.
   - It was strong on file-search retrieval.
   - It was materially too weak on conversation recall to use as the shared model.
5. `mxbai-embed-large` is not acceptable as the shared recall model.
   - It failed on the real recall corpus shape with a context-length error.

### Current decision standard

- If one shared model must serve both conversation recall and file search today, prefer
  `qwen3-embedding:0.6b`.
- If the local machine is constrained enough that steady-state latency/footprint dominate over the
  small quality edge of the default, allow `embeddinggemma` as the fallback.
- Do not present `qwen3-embedding:4b` as a normal `High` tier again unless a larger benchmark pass
  proves a materially better user outcome.
- If future architecture adds true split-model support, re-evaluate `nomic-embed-text` as a
  file-search-only candidate rather than as a shared model.

### Implementation status in the current product

- The config compiler now owns the retrieval embeddings contract from
  `runtime.retrieval.embeddings` into generated runtime env:
  - `EMBEDDINGS_PROVIDER`
  - `EMBEDDINGS_MODEL`
  - `OLLAMA_BASE_URL` when applicable
  - `VIVENTIUM_RAG_EMBEDDINGS_PROVIDER`
  - `VIVENTIUM_RAG_EMBEDDINGS_MODEL`
  - `VIVENTIUM_RAG_EMBEDDINGS_PROFILE`
- The current default local-first contract is:
  - provider: `ollama`
  - model: `qwen3-embedding:0.6b`
  - profile metadata: `medium`
- Installer-facing runtime surfaces now consume the same retrieval config helper so they stay in
  lockstep:
  - wizard defaults
  - preflight prerequisite reporting
  - install summary
  - doctor
  - LibreChat launcher readiness/startup
- When recall is configured to use `ollama`, runtime must honestly surface that prerequisite and
  fail closed if the local embeddings runtime is unavailable.
- When recall is configured to use `ollama`, runtime must also verify the configured model artifact:
  - doctor reports whether the configured model is already ready or will be pulled on first start
  - the launcher pulls the configured model before RAG startup if it is missing
  - untagged configured names must still match host-reported `:latest` variants
- The current startup contract still treats the RAG sidecar as conversation-recall-owned:
  - enabling file search alone does not yet independently force RAG startup
  - that broader split-ownership/startup decision remains future architecture work
- The current product still uses one shared embeddings runtime/model for both recall and file
  search.
- Split-model recall-vs-file-search embeddings are still not implemented.

## Public-Safe Data Model Notes

- Keep user personalization separate from agent-scoped recall.
- Keep file context explicit and deterministic.
- Avoid publishing private email addresses, personal names, or machine-specific examples in the docs.

## Public-Safe Evidence Notes

- Record the exact user turn.
- Record the expected activation/suppression.
- Record the visible answer.
- Record the persisted truth or runtime log.
- Keep result folders and samples free of private identity data.
- 2026-04-04 live validation confirmed that a connected-account OpenAI override can drive the RAG
  embed path against the platform embeddings API while leaving the no-user-key env fallback path
  unchanged in request shape.
- 2026-04-08 regression coverage must also include:
  - vector runtime unhealthy
  - stale corpus newer-than-last-message mismatch
  - short post-message indexing lag while lexical fallback still succeeds
  - repeated transient upload failures causing proactive sync pause
  - broad catch-up prompt without explicit entity terms
  - scheduler list/search available in the same run without leaking delivery prose
- 2026-04-09 implementation coverage must also include:
  - compiler output for local embeddings provider/model metadata
  - honest Ollama prerequisite detection in preflight/doctor/launcher when recall uses Ollama
  - bounded older-user-context recovery for long-chat memory writes
  - no silent remote-provider fallback when the configured local embeddings runtime is unavailable
