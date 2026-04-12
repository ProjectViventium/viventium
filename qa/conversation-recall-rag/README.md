# Conversation Recall RAG QA

## Purpose

Verify that Viventium conversation recall remains correct across:

- explicit local-first embeddings/runtime selection
- honest recall health/freshness behavior
- degraded lexical fallback
- shared-model constraints with the current file-search sidecar contract
- historical OpenAI override compatibility when OpenAI is explicitly configured

## Acceptance Contract

- The config compiler emits the retrieval embeddings contract from
  `runtime.retrieval.embeddings` instead of relying on hidden sidecar defaults.
- When recall is configured to use Ollama embeddings, preflight, install summary, doctor, and the
  launcher surface the same prerequisite and fail closed honestly when the local runtime is down.
- When recall is configured to use Ollama embeddings, doctor and launcher also agree on model
  readiness:
  - doctor reports whether the configured model is already present or will be pulled on first start
  - launcher verifies/pulls the configured model before the RAG sidecar boots
  - untagged configured names remain valid if the Ollama host reports them back as `:latest`
- The current default shared local model is explicit:
  - provider `ollama`
  - model `qwen3-embedding:0.6b`
  - profile metadata `medium`
- `qwen3-embedding:4b` is experimental only, not a normal recommended install tier.
- `embeddinggemma` remains the low-footprint fallback.
- The current product uses one shared embeddings model/runtime across conversation recall and file
  search.
- Split recall/file-search embeddings are not silently enabled behind the same sidecar contract.
- If OpenAI is explicitly configured as the embeddings provider, the running isolated stack accepts
  a connected-account OpenAI token for embeddings through the normal LibreChat-to-RAG upload path.
- If OpenAI is explicitly configured, connected-account subscription tokens are routed to the
  platform embeddings endpoint, not the Codex chat/replies base URL.
- If OpenAI is explicitly configured and no user-scoped OpenAI key is available, LibreChat leaves
  the existing RAG env-key path unchanged.
- A modern-playground typed chat can still trigger conversation-recall indexing on the live stack.
- Any remaining assistant reply failure must be attributed separately from embeddings.
- Runtime must not attach vector-backed conversation-recall resources as trustworthy when the
  vector runtime is unhealthy or the corpus is stale.
- When conversation recall is enabled globally or per-agent, runtime must inject the
  YAML-configured recall instruction into the agent system prompt by default.
- Compile-time source-of-truth precedence must preserve that prompt block:
  - private curated source-of-truth YAML wins when present
  - otherwise tracked `local.librechat.yaml` wins
  - a previously generated runtime `librechat.yaml` must not become the next compile source
- The decision to use conversation recall must stay model-owned through `file_search`, not
  runtime-owned through prompt-text classifiers.
- When vector recall is unhealthy, stale, or missing, runtime may attach a source-only recall
  resource so the normal `file_search` path can degrade honestly.
- Degraded recall continuity is still required after the runtime-context cleanup:
  - proactive runtime recall snippet injection stays removed
  - continuity now comes from source-only recall attachment plus source-backed rescue inside
    `file_search`
- Assistant recall-echo replies to meta-recall prompts must not count as newer recall history than
  the original source turn.
- Assistant recall-echo replies must not be written back into the recall corpus or allowed to
  crowd out the original source turn in degraded lexical recall.
- The derivative-recall filter must be structural:
  - assistant recall-derived turns are identified from `file_search` attachment provenance that
    points at `conversation_recall:*`
  - the related user meta-recall prompt is identified by `parentMessageId`
  - runtime must not branch on one exact user prompt phrase or one exact QA marker string
- Runtime must not branch on broad catch-up phrases, named entities, medical vocabulary, or short
  query heuristics to decide recall intent.
- Model-facing file-search failure wording must remain inconclusive rather than implying absence.
- Scheduler list/search browsing must not leak prompt text or stale generated delivery prose.
- Local-first recall tiers must remain explicit:
  - the selected default and any alternate tier/model are config-selected vector spaces, not
    runtime guesses.
  - a tier/model switch must trigger a full re-embed before cutover.
- If the local embeddings runtime is unavailable, recall must degrade to lexical-only behavior
  rather than silently switching to a metered remote provider.
- The selected default local model must satisfy the public license gate for the open-source install
  story.
- Hybrid retrieval acceptance must prove that vector recall and lexical recall are fused through a
  generic strategy, not hardcoded named-entity or prompt-specific branches.
- Any model/provider switch that changes the vector space must trigger a rebuild rather than
  querying stale vectors from the old contract.
- Conversation-recall rebuilds must not silently accept degraded uploads as fully current:
  - if the uploaded digest differs from the source digest, the file remains eligible for rebuild
  - unchanged short-circuiting is valid only when uploaded digest matches source digest
  - local Ollama reindex must not create duplicate vector cohorts after client-side timeouts

## Public-Safe Evidence

- LibreChat regression tests:
  - `viventium_v0_4/LibreChat/api/server/services/Files/VectorDB/__tests__/crud.spec.js`
- RAG container logs from the running isolated stack:
  - `docker logs librechat-rag_api-1`
- Modern playground browser artifacts:
  - `output/playwright/modern-playground-qa/.playwright-cli/`
  - Keep these local-only because they can include authenticated UI state.
- Public-safe local benchmark artifacts may include:
  - synthetic message batches
  - model size / context / dimension notes from public model cards
  - local latency measurements on anonymous hardware classes such as `Apple Silicon 16GB` or
    `Apple Silicon 32GB`
  - aggregate-only metrics from private local corpora, provided the raw corpus, raw queries,
    retrieved passages, and machine-local artifacts remain outside the repo
  - never include local usernames, home paths, or private conversation text

## Verification Steps

1. Start the canonical isolated stack with `bin/viventium start --restart`.
2. Run the targeted LibreChat regression tests for `VectorDB/crud`.
3. Create an authenticated call session for the Viventium agent.
4. Open the returned modern-playground URL in a real browser.
5. Start chat, enable the transcript, and send a synthetic typed prompt.
6. Inspect RAG logs and launcher output for the exact prompt window.
7. Confirm embeddings succeed through OpenAI platform embeddings and separate any remaining
   completion failure by provider/runtime layer.
8. Stop or block the local vector runtime and confirm vector-backed recall is not presented as
   healthy/current evidence.
9. Create a stale-corpus condition with a newer synthetic message and confirm runtime attaches the
   degraded source-only recall path instead of proactive runtime snippets.
10. Send a synthetic prior-chat question and confirm the model chooses normal `file_search`, with
    degraded recall returning recent corrections from prior conversations when vector recall is
    unavailable.
11. Verify `schedule_list` / `schedule_search` outputs remain summary-safe and omit generated
    delivery prose.
12. For local-first tier evaluation, benchmark the selected embeddings runtime on a synthetic recall
    corpus and record:
    - cold single-input latency
    - warm single-input latency
    - batch latency
    - loaded footprint
    - output dimension
13. Optionally run a private local-corpus research pass outside the repo and record only
    aggregate/public-safe outputs such as:
    - approximate corpus scale by surface
    - recent-message throughput
    - exact vs semantic query metrics
    - dense vs lexical vs hybrid retrieval metrics
    - per-surface compatibility failures such as context-length rejection
14. Switch between the default model and any alternate tier/model and verify the system rebuilds
    the recall corpus instead of querying stale vectors from the old dimension/model contract.
15. Compile the runtime with the default local embeddings contract and verify the generated
    retrieval env exposes the configured provider/model/profile metadata.
16. Verify that preflight, doctor, install summary, and launcher readiness all report the same
    Ollama dependency when recall uses the default local embeddings provider.
17. Verify that if the configured Ollama model is missing, launcher pulls it before RAG startup and
    doctor reports that first-start pull behavior honestly.
18. Create a synthetic cross-chat recall marker in one conversation, then in a new conversation ask
    for that exact prior marker through normal chat/file-search behavior.
19. Verify that the live web run attaches the global recall corpus as a file-search resource and
    answers from the original source turn rather than from an assistant echo of an earlier recall
    answer.
20. Verify that a follow-up recall answer generated during the test does not itself become the new
    freshness owner or a degraded lexical recall candidate in later runs.
21. Force a live recall rebuild on the running isolated stack and verify:
    - a degraded prior upload state triggers a rebuild
    - the final uploaded digest matches the source digest
    - the vector store contains a single cohort for the logical `conversation_recall:*` file
    - no prompt-example meta-recall chatter remains in the rebuilt corpus
22. With both recall and non-recall files attached, send a short specific lookup query such as
    “what’s my name?” and verify the runtime still queries the recall file without relying on a
    curated personal-facts regex.
23. Simulate compile phase with a stale generated `librechat.yaml` override and verify the newly
    generated runtime YAML still preserves `viventium.conversation_recall.prompt` from tracked or
    private source-of-truth YAML.
24. After a real `bin/viventium start --restart`, verify the live `CONFIG_PATH` artifact contains
    the recall prompt block and the restarted API/RAG health checks pass.
