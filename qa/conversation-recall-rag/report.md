# Conversation Recall RAG QA Report

## Date

- 2026-04-04
- 2026-04-08
- 2026-04-09

## 2026-04-09 Prompt-Owned Recall Trigger / Source-Only Fallback

### Scope

Remove the remaining runtime query-intent classifiers from conversation recall, move recall-use
decisions into a YAML-backed system-prompt instruction, and keep degraded continuity inside the
normal `file_search` tool path.

### Checks Executed

1. Read the owning product docs and traced the live ownership path:
   - source-of-truth YAML
   - agent system-prompt assembly
   - runtime recall attachment
   - `file_search` recall behavior
2. Review-only Claude second opinion against the exact architecture question.
   - Result:
     - confirmed that prompt-text/runtime recall classifiers were still misaligned with
       `01_Key_Principles.md`
     - agreed the deeper violation was proactive runtime snippet injection bypassing model tool
       choice
     - supported prompt-owned recall triggering plus tool-path degraded fallback
3. Removed executable prompt-text recall classifiers and proactive runtime recall injection.
4. Added a YAML-configured default recall prompt block under `viventium.conversation_recall.prompt`
   and injected it when recall is enabled globally or per-agent.
5. Changed runtime attachment behavior:
   - fresh/healthy vector state -> vector-backed recall resource
   - unhealthy/stale/missing vector state -> source-only recall resource
6. Kept degraded recall inside `file_search` by rescuing from source messages when recall is
   source-only or vector retrieval cannot provide usable evidence.
7. Verified compile-time source precedence with a stale generated-YAML simulation.
   - Result:
     - the compiler now prefers private curated source-of-truth YAML when present, otherwise the
       tracked `local.librechat.yaml`
     - a stale generated runtime YAML no longer strips the new
       `viventium.conversation_recall.prompt` field during compile
8. Verified live runtime propagation after a real `bin/viventium start --restart`.
   - Result:
     - `~/Library/Application Support/Viventium/runtime/librechat.yaml` contains the recall prompt
     - the active launcher `CONFIG_PATH`
       `~/Library/Application Support/Viventium/state/runtime/isolated/librechat.generated.yaml`
       also contains the recall prompt
     - restarted health checks passed:
       - `http://localhost:3180/api/health` -> `OK`
       - `http://localhost:8110/health` -> `{"status":"UP"}`

### Findings

1. `conversationRecallQuerySignals.js` was still illegal architecture.
   - Even after removing the explicit personal-facts ontology, the replacement still used runtime
     query-text logic to decide when recall should run.
2. `conversationRecallRuntimeContext.js` was the deeper problem.
   - It proactively injected retrieved snippets into shared run context before the model chose a
     tool, which put a model decision in runtime code.
3. The correct fix was structural, not lexical.
   - prompt/config owns recall-use behavior
   - runtime owns attachment policy and degradation truthfulness
   - `file_search` owns degraded source-backed fallback after the model chooses to search
4. Healthy vs degraded recall must still be explicit.
   - vector-backed recall remains health/freshness-gated
   - degraded source-only recall remains available without pretending the vector corpus is current
5. Deleting `conversationRecallRuntimeContext.js` did not delete degraded recall continuity.
   - The continuity layer moved to the supported ownership boundary:
     - runtime attaches source-only recall resources when vector recall is unavailable or stale
     - `file_search` performs bounded source-backed lexical rescue and reranking after the model
       chooses the tool
   - The removed behavior was proactive runtime snippet injection, not degraded recall itself.
6. There was an additional end-to-end compiler bug.
   - The code and tracked source-of-truth YAML were correct, but compile-time source precedence was
     still allowing the last generated runtime YAML to become the next compile input.
   - That caused new tracked fields like `viventium.conversation_recall.prompt` to disappear from
     live runtime until compile precedence was fixed.

## 2026-04-09 Structural Recall Filter / Upload Integrity Hardening

### Scope

Remove the remaining prompt-example overfit from recall filtering and prove that a live recall
rebuild no longer leaves the corpus in a reduced-window or duplicate-cohort state.

### Follow-up Alignment

- The original follow-up hardening still left one illegal prompt-text ontology branch in recall
  behavior:
  - a curated `PERSONAL_FACT_RECALL_REGEX` in degraded runtime recall
  - a second curated `PERSONAL_FACT_RECALL_REGEX` in recall-file prioritization inside
    `file_search`
- That branch was removed and replaced with one shared generic short-specific-lookup signal.
- The shared signal does not enumerate “wife / birthday / lab / project / ...” as a product
  ontology. It detects short lookup queries from generic specificity and query shape instead.

### Checks Executed

1. Review-only Claude second opinion against the exact code/docs/runtime question.
   - Result:
     - confirmed the user-prompt regex path was still misaligned
     - recommended structural provenance through `file_search` attachments and parent linkage
     - agreed that the remaining curated personal-facts regex should be removed rather than
       renamed into another prompt-text branch
2. Targeted recall regression suites.
   - Command:
     `cd viventium_v0_4/LibreChat/api && npx jest --runInBand server/services/viventium/__tests__/conversationRecallService.spec.js server/services/viventium/__tests__/conversationRecallFilters.spec.js server/services/viventium/__tests__/conversationRecallRuntimeContext.spec.js test/app/clients/tools/util/fileSearch.test.js --no-cache`
   - Result: `77 passed`
3. Targeted follow-up regression for the shared short-specific-lookup signal.
   - Scope:
     - `conversationRecallFilters.spec.js`
     - `fileSearch.test.js`
     - existing runtime-context coverage for “what’s my name?” and partner/entity lookups
   - Result:
     - short specific lookup queries still trigger degraded recall behavior
     - mixed recall/non-recall file attachment no longer depends on a curated personal-facts regex
4. Agent controller smoke for runtime recall attachment.
   - Command:
     `cd viventium_v0_4/LibreChat/api && npx jest --runInBand server/controllers/agents/client.test.js --no-cache -t "conversation recall"`
   - Result: passed
5. Live isolated-stack rebuild on the running user corpus after restart.
   - Result before hardening:
     - 60-second client timeout caused repeated retries
     - RAG-side logs showed the server still completed the earlier uploads
     - the vector store accumulated duplicate cohorts for the same logical recall file
     - file metadata showed `conversationRecallSourceDigest != conversationRecallUploadedDigest`
   - Result after hardening:
     - live refresh detected the reduced prior upload and rebuilt it
     - the final metadata showed `conversationRecallSourceDigest == conversationRecallUploadedDigest`
     - `conversationRecallCharCount` returned to the full corpus window (`349905`)
     - the vector store returned to a single cohort (`339` rows for the file)
     - prompt-example meta-recall chatter remained absent from the rebuilt corpus (`0` matching rows)

### Findings

1. The previous “generic regex” patch was still not principled enough.
   - Even broad natural-language recall regexes are still prompt-text gating.
   - The correct signal is structured provenance:
     - assistant derivative recall turns via `file_search` attachment sources pointing to
       `conversation_recall:*`
     - related user prompt via `parentMessageId`
2. A curated ontology of “personal facts” was also misaligned.
   - `wife / husband / birthday / project / lab / blood / ...` is still runtime business logic
     keyed to human phrasing.
   - The correct replacement is a generic short-specific-lookup signal, not another vocabulary
     patch.
3. Live rebuild uncovered a second real bug in the ownership layer.
   - The old upload timeout was too short for the real local Ollama embedding workload.
   - Client retries were racing against server-side completions and creating duplicate vector
     cohorts for one logical recall file.
4. Digest handling was also too optimistic.
   - A reduced uploaded corpus was being stored with the full source digest, which let later runs
     skip rebuilds incorrectly.
5. The hardening now lives at the right layer.
   - adaptive upload timeout based on corpus size
   - unchanged short-circuit only when uploaded digest equals source digest
   - reduced uploads remain eligible for a later rebuild
6. Live state is now clean.
   - one full cohort in pgvector
   - full source/uploaded digest match
   - no prompt-example recall chatter in the rebuilt corpus
   - no prompt-text branch required for the derivative-recall filter

## 2026-04-09 Live Web Recall Recovery / Derivative Chatter Regression

### Scope

Close the remaining live web conversation-recall failure where an earlier recall answer could make
the corpus look stale even though the real source turn had already been indexed.

### Checks Executed

1. Targeted backend/runtime regression tests for corpus filtering, runtime degraded recall, newest
   recall-eligible timestamp selection, and file-search integration.
   - Command:
     `cd viventium_v0_4/LibreChat/api && npx jest --runInBand models/Message.spec.js server/services/viventium/__tests__/conversationRecallService.spec.js server/services/viventium/__tests__/conversationRecallRuntimeContext.spec.js test/app/clients/tools/util/fileSearch.test.js --no-cache`
   - Result: passed
2. Agent controller regression smoke for runtime recall attachment.
   - Command:
     `cd viventium_v0_4/LibreChat/api && npx jest --runInBand server/controllers/agents/client.test.js --no-cache -t "conversation recall"`
   - Result: passed
3. Live backend evidence check against the running local stack.
   - Result:
     - the newest recall-eligible timestamp now resolves to the original synthetic source turn
       rather than to a later assistant recall-echo answer
     - the global recall corpus remained fresh enough to attach on the next real run
4. Live authenticated browser QA through the normal web UI.
   - Result:
     - a fresh chat asked for a synthetic marker created in an earlier chat
     - the assistant used normal `file_search`
     - the attached recall source was `conversation-recall-all.txt`
     - the returned answer matched the exact synthetic marker from the original source turn

### Findings

1. The remaining live failure was not a generic freshness-policy bug.
   - The freshness gate was doing the right thing with the timestamp it was given.
   - The bug was that a derivative assistant recall answer had been allowed to masquerade as new
     recall history.
2. Assistant recall-echo answers are not source evidence.
   - When a user asks a meta-recall question such as "what exact marker did I say earlier?",
     the assistant's answer is derivative chatter about retrieval, not a new fact that should be
     embedded back into the corpus or used as the freshness owner.
3. The correct fix was exclusion, not weakening.
   - The product now excludes derivative assistant recall chatter from:
     - corpus writes
     - freshness eligibility
     - degraded lexical recall candidate selection
   - The real source turn remains eligible and recoverable.
4. Live web recovery is now proven on the normal user path.
   - The browser run attached recall through the existing file-search surface.
   - The tool output pointed back to the original source turn and returned the exact synthetic
     marker requested.

## 2026-04-09 Fresh-Install Ollama Model Readiness Follow-Up

### Scope

Close the remaining local-first fresh-install gap where the configured Ollama embeddings runtime
could be reachable while the configured embeddings model artifact was still missing.

### Checks Executed

1. Targeted release coverage for launcher/doctor/install-summary ownership.
   - Command:
     `python3 -m pytest tests/release/test_ollama_embeddings_prereqs.py tests/release/test_doctor_sh.py tests/release/test_install_summary.py -q`
   - Result: `20 passed`
2. Shell syntax validation for the owning start/doctor surfaces.
   - Command:
     `bash -n scripts/viventium/doctor.sh && bash -n viventium_v0_4/viventium-librechat-start.sh`
   - Result: passed
3. Live doctor check against the real local config/runtime.
   - Result:
     - doctor still honestly failed on the separate Docker-not-running requirement for Conversation
       Recall
     - doctor also reported the configured Ollama embeddings model was ready:
       `qwen3-embedding:0.6b`
4. Live launcher-function pull test against the real local Ollama host using a temporary official
   embeddings model that was not present in the pre-QA local model list.
   - Result before the final fix:
     - the model pulled successfully, but readiness misclassified it as missing because the host
       reported the model back as `all-minilm:latest`
   - Result after the final fix:
     - the same launcher function successfully pulled the missing model and reported readiness
   - Revert:
     - the temporary model was removed again and the post-QA local Ollama model list matched the
       pre-QA snapshot

### Findings

- The fresh-install gap was real:
  - launcher previously ensured only that Ollama was reachable
  - it did not ensure the configured embeddings model artifact existed before RAG startup
- The fix now lives at the owning start/doctor surfaces:
  - launcher verifies the configured model and pulls it if missing
  - doctor exports/uses the configured model/base-url metadata and reports readiness honestly
- Untagged Ollama model names need canonicalization:
  - a configured name such as `all-minilm` can be reported back by the host as
    `all-minilm:latest`
  - readiness checks must accept that host normalization instead of treating it as a false miss
- QA state was reverted:
  - no lasting Ollama-model-store drift remained from the live pull exercise

## Build Under Test

- Parent repo working tree on 2026-04-09
- Nested LibreChat working tree on 2026-04-09
- Runtime profile: `isolated`

## Checks Executed

1. Static validation of the connected-account OpenAI subscription path.
   - Result: the stored connected-account token succeeds against
     `https://api.openai.com/v1/embeddings`.
   - Result: the same token does not work against the Codex base URL embeddings path, so Codex
     base URLs must be omitted for embeddings.
2. Targeted LibreChat regression tests for `VectorDB/crud`.
   - Result: `5/5` tests passed, including the no-user-key fallback case.
3. Live isolated-stack validation through the modern playground.
   - Result: the browser connected to LiveKit, transcript chat submitted successfully, and the
     conversation-recall corpus upload completed on the running RAG service.

## Findings

- The new user-scoped embeddings override is working live.
- RAG container logs showed successful platform embeddings requests:
  - `POST https://api.openai.com/v1/embeddings "HTTP/1.1 200 OK"`
  - `Request POST http://localhost:8110/embed - 200`
- The running backend reported:
  - `[conversationRecall] Corpus upload completed`
- The old embeddings path remains preserved in code when no user-scoped OpenAI key exists.
  - Evidence: the targeted LibreChat regression test confirms no override headers are sent in the
    no-user-key path.

## Separate Remaining Blocker

- The modern playground typed transcript still returned:
  - `I'm having trouble reaching the service right now. Please try again.`
- That failure is no longer an embeddings failure.
- Launcher evidence for the same request window showed the assistant completion path failing with a
  different provider key problem:
  - `Incorrect API key provided: xa***bX`
- Conclusion: conversation recall embeddings are fixed for connected OpenAI accounts, while the
  final assistant reply is still blocked by a separate xAI completion credential issue.

## Limitations

- The current owner-machine env-key embeddings path could not be live-validated end to end because
  the environment OpenAI key in this runtime is invalid.
- The existing env-key path is therefore covered by regression tests in this pass, not by a second
  successful live env-key run.

## 2026-04-08 Runtime Regression Pass

### Scope

Production-hardening pass for stale-recall failures where recent conversation corrections were not
being surfaced reliably in catch-up style requests.

### Checks Executed

1. `packages/api` targeted recall attachment tests.
   - Command: `npx jest --runInBand src/agents/__tests__/initialize.test.ts -t "conversation recall resources"`
   - Result: passed
2. `api` targeted degraded-recall and tool-output tests.
   - Command: `npx jest --runInBand server/services/viventium/__tests__/conversationRecallRuntimeContext.spec.js test/app/clients/tools/util/modelFacingToolOutput.test.js test/app/clients/prompts/formatMessages.toolFailureNormalization.test.js`
   - Result: passed
3. Scheduling-cortex summary-safety regression test.
   - Command: `./.venv/bin/python -m unittest tests.test_bootstrap -v`
   - Result: passed
4. Agent-controller smoke coverage for init-path dependency propagation.
   - Command: `npx jest --runInBand server/controllers/agents/__tests__/openai.spec.js server/controllers/agents/__tests__/responses.unit.spec.js`
   - Result: passed

### Findings

- Conversation-recall resource attachment is now gated on real vector-runtime health, not merely on
  env-var presence.
- Global recall corpora are now rejected when newer recall-eligible messages exist than the corpus
  update timestamp.
- Broad catch-up prompts now activate degraded lexical recall without requiring explicit entity
  names.
- User-authored correction messages are no longer incorrectly down-ranked as meta recall residue
  simply because they contain phrases like “I said”.
- Default schedule list/search payloads can now stay useful without leaking prompt text or stale
  generated delivery payloads.

### Remaining Operational Requirement

- Code hardening does not by itself refresh a broken or outdated local recall corpus.
- A live incident still requires operational recovery when applicable:
  - restore the vector runtime
  - rebuild or resync the conversation-recall corpus
  - verify the new corpus timestamp catches up to recent recall-eligible messages

## 2026-04-08 Local-First Embeddings / Index Research Pass

### Verification Gate Claimed

- `Local development research-and-benchmark gate`
- Meaning:
  - current-source research completed against official model/runtime/backend docs
  - candidate defaults filtered through product-license, local-runtime, and integration-fit rules
  - at least one real local feasibility pass executed with synthetic inputs
- Not yet claimed:
  - `cross-surface landing gate`
  - `public release gate`

### Scope

Research and local smoke benchmarking for conversation-recall embeddings / index options that avoid
default reliance on metered OpenAI embeddings.

### Public-Safe Research Inputs

- Official Ollama embeddings docs and model library entries
- Official Qwen3 embedding model cards / blog references
- Official Google EmbeddingGemma announcement / model card
- Official pgvector docs
- Official Chroma full-text-search docs
- Official Qdrant local/hybrid docs
- Official BGE-M3 model card
- Official LlamaIndex BM25 / fusion retriever docs

### Local Feasibility Environment

- Anonymous hardware class: `Apple Silicon M5 / 32GB RAM`
- Ollama client: `0.20.2`
- Benchmark corpus: synthetic recall-like message batch only
- No private chat content or secret-bearing prompts used

### Local Benchmark Results

| Model | Tier role | Ollama artifact | Warm single | Cold single | Batch 100 | Batch / item | Output dims | Loaded footprint |
|------|------|------|------:|------:|------:|------:|------:|------:|
| `qwen3-embedding:0.6b` | Recommended `Medium` | `639MB` | `79.0 ms` | `1961.2 ms` | `1791.2 ms` | `17.9 ms` | `1024` | `5.7 GB` |
| `qwen3-embedding:4b` | Experimental candidate | `2.5GB` | `138.6 ms` | `2912.4 ms` | `9446.9 ms` | `94.5 ms` | `2560` | `9.9 GB` |
| `embeddinggemma` | Ultra-light fallback | `621MB` | `62.3 ms` | `7594.2 ms` | `967.9 ms` | `9.7 ms` | `768` | `1.1 GB` |

Loaded footprint comes from `ollama ps` on the same local run. It is a useful sizing signal, not a
portable universal guarantee.

### Findings

1. `qwen3-embedding:0.6b` is the best current default balance.
   - It kept warm latency comfortably low on the reference machine.
   - It preserves a 32K context contract and a modern 1024-dimensional vector space.
   - It is materially more suitable for recall-quality defaults than ultra-small legacy models.
2. `qwen3-embedding:4b` is a viable `High` tier, not a safe default.
   - Quality headroom is attractive.
   - Its loaded local footprint and much slower batch throughput make it inappropriate as the
     default for 16GB-class installs.
3. `embeddinggemma` is the speed / footprint fallback, not the default quality tier.
   - It was the fastest candidate in local batch throughput.
   - Its shorter context window makes it less attractive as the default episodic-recall model.
4. The index/backend decision is separate from the embeddings decision.
   - The lowest-change path is local embeddings first, while preserving the current recall corpus
     shape and vector-runtime contract.
   - Native PostgreSQL or a new embedded backend remains a second decision.
5. Hybrid retrieval is now mandatory.
   - Near-term hybrid on the current stack should fuse vector recall with the existing scoped
     lexical recall path instead of trying to invent entity-specific runtime hacks.
6. Tier changes require explicit re-embedding.
   - `Medium` and `High` are different vector spaces and must not share the same authoritative
     corpus/index without a full rebuild and cutover.

### Default Recommendation

- `Medium` default:
  - Ollama + `qwen3-embedding:0.6b`
  - keep the current vector-runtime contract first
- experimental override only:
  - Ollama + `qwen3-embedding:4b`
  - require explicit re-embed and fresh-corpus cutover
- ultra-light fallback:
  - `embeddinggemma`
  - use only when footprint and throughput dominate over recall-quality headroom

### Default Exclusions

- Non-commercial or research-only model licenses are not valid defaults for the public product
  path.
- API-only embedding services are not valid defaults for a local-first recall story.
- Remote OpenAI fallback may remain an explicit opt-in secondary mode, but it is not the default
  continuity contract.

### Second-Opinion Review

- A review-only Claude CLI pass completed successfully for this selection pass.
- The main critiques folded into the recommendation were:
  - define the near-term hybrid fusion strategy explicitly
  - define the re-embed contract on tier/model change explicitly
  - define the local-runtime outage fallback explicitly

## 2026-04-09 Private Local Corpus Eval Pass

### Verification Gate Claimed

- `Private local corpus research gate`
- Meaning:
  - real local corpora were evaluated outside the repo
  - only aggregate/public-safe metrics are recorded here
  - this informs model selection, but it is not a clean-install or public-release claim
- Not yet claimed:
  - `cross-surface landing gate`
  - `public release gate`

### Scope

Compare the leading local embedding candidates on real local conversation-recall and uploaded-file
corpora without storing raw private content in the public repo.

### Public-Safe Corpus Shape

- approximately `250` conversation-recall chunks
- approximately `90` uploaded-file chunks
- approximately `100` conversation-recall queries
- approximately `50` file-search queries
- approximately `100` recent-message throughput samples
- query styles:
  - exact corpus-derived queries
  - semantic rewrites generated locally on-device

### Method

- Runtime:
  - Ollama local embeddings
  - anonymous hardware class: `Apple Silicon M5 / 32GB RAM`
- Candidates:
  - `qwen3-embedding:0.6b`
  - `qwen3-embedding:4b`
  - `embeddinggemma`
  - `nomic-embed-text`
  - `mxbai-embed-large`
- Retrieval scoring:
  - dense retrieval only
  - lexical retrieval only
  - hybrid retrieval via reciprocal rank fusion
- Privacy boundary:
  - raw corpora, raw queries, and raw outputs stayed in local temp storage only
  - this report records aggregate metrics only

### Aggregate Results

| Model | Recent-message throughput | Recall semantic hybrid hit@1 | File semantic hybrid hit@1 | Compatibility notes | Decision signal |
|------|------:|------:|------:|------|------|
| `qwen3-embedding:0.6b` | `44.75 ms/msg` | `0.59` | `0.70` | fully compatible | best current shared default |
| `qwen3-embedding:4b` | `339.71 ms/msg` | `0.60` | `0.72` | fully compatible | quality gain too small for cost |
| `embeddinggemma` | `19.46 ms/msg` | `0.56` | `0.66` | fully compatible | strong low-footprint fallback |
| `nomic-embed-text` | `12.81 ms/msg` | `0.39` | `0.74` | fully compatible | promising file-search-only future candidate |
| `mxbai-embed-large` | `36.63 ms/msg` | n/a | `0.54` | recall corpus rejected: context length exceeded | reject as shared recall model |

### Additional Findings

1. The provisional `High` recommendation from the synthetic pass does not hold up on the private
   local corpus.
   - `qwen3-embedding:4b` was only marginally better than `0.6b` on recall/file-search hybrid
     hit@1.
   - The per-message runtime cost was roughly `7.6x` higher.
2. `embeddinggemma` performed better than expected.
   - It remained close enough to the shared default on recall/file-search hybrid metrics to stay
     credible as the low-footprint fallback.
3. `nomic-embed-text` is not acceptable as the shared model.
   - Its file-search results were strong.
   - Its conversation-recall results were materially too weak for a shared recall-first decision.
4. `mxbai-embed-large` is operationally disqualified for shared recall.
   - The real recall corpus triggered a context-length failure during embedding.
5. Lexical retrieval was very strong on this corpus.
   - Hybrid remained valuable as a dense+lexical strategy.
   - But the benchmark suggests the lexical component is doing much of the work on this corpus
     shape, so embedding-quality gaps must be interpreted carefully.

### Revised Recommendation

- Shared model today:
  - keep one shared embeddings model/runtime across recall and file search
  - choose `qwen3-embedding:0.6b` as the current default
- Alternate tiering:
  - demote `qwen3-embedding:4b` from recommended `High` tier to experimental-only
  - keep `embeddinggemma` as the low-footprint fallback
- Future architecture:
  - if explicit split-model support is added later, re-evaluate `nomic-embed-text` as a
    file-search-only model
- Current non-choice:
  - do not split recall and file-search embedding models under the current sidecar/query contract

### Qualification

- The current evidence is strong enough to justify a default decision, but not strong enough to
  treat the ranking between `qwen3-embedding:0.6b` and `embeddinggemma` as permanently settled.
- Re-run this benchmark when one of the following changes materially:
  - corpus scale
  - query mix
  - Ollama/model release
  - hybrid implementation

### Second-Opinion Review

- A review-only Claude CLI pass completed successfully on the benchmark findings.
- The main critiques folded into the recommendation were:
  - keep the shared-model decision for now, because split models are architecture work
  - demote `qwen3-embedding:4b` strongly because the real-corpus gain is too small for its cost
  - treat `qwen3-embedding:0.6b` as a defensible but still tentative default over `embeddinggemma`
  - mark `nomic-embed-text` explicitly as future file-search-only, never as a shared model

## 2026-04-09 Implementation / QA Pass

### Verification Gate Claimed

- `Local development implementation gate`
- Meaning:
  - the local-first embeddings/runtime contract is implemented in product code
  - the provider-alias runtime bug is fixed at the shared boundary
  - the long-conversation saved-memory blind spot has bounded structural coverage
  - the relevant release, runtime, and launcher tests pass for the owned surfaces under review
- Not yet claimed:
  - `cross-surface landing gate`
  - `public release gate`

### Scope

Apply and verify the production-facing fixes needed to make the researched local-first recall
contract real in the product:

- compiler-owned retrieval embeddings env contract
- honest Ollama prerequisite/readiness reporting across install/start surfaces
- shared runtime provider normalization for the memory writer
- bounded older-user-context recovery in the saved-memory writer
- direct automated coverage for recall availability / freshness gating

### Checks Executed

1. Release / compiler / installer surface tests.
   - Command:
     `python3 -m pytest tests/release/test_config_compiler.py tests/release/test_wizard.py tests/release/test_preflight.py tests/release/test_doctor_sh.py tests/release/test_install_summary.py tests/release/test_librechat_client_defaults.py -q`
   - Result: `105 passed`
2. Shared data-provider utility tests plus package build.
   - Command:
     `cd viventium_v0_4/LibreChat/packages/data-provider && npx jest --runInBand specs/utils.spec.ts --no-cache`
   - Result: `21 passed, 1 skipped`
   - Command:
     `cd viventium_v0_4/LibreChat/packages/data-provider && npm run build`
   - Result: passed
3. `packages/api` targeted runtime tests.
   - Command:
     `cd viventium_v0_4/LibreChat/packages/api && npx jest --runInBand src/endpoints/config.spec.ts src/agents/__tests__/conversationRecallAvailability.test.ts src/agents/__tests__/memory.test.ts --no-cache`
   - Result: `33 passed`
4. Backend/runtime targeted tests.
   - Command:
     `cd viventium_v0_4/LibreChat/api && npx jest --runInBand server/controllers/agents/client.test.js server/services/viventium/__tests__/conversationRecallRuntimeContext.spec.js server/services/viventium/__tests__/conversationRecallService.spec.js test/app/clients/tools/util/modelFacingToolOutput.test.js --no-cache`
   - Result: `124 passed`
5. Launcher / doctor shell syntax validation.
   - Command:
     `bash -n scripts/viventium/doctor.sh && bash -n viventium_v0_4/viventium-librechat-start.sh`
   - Result: passed
6. Broader release-suite smoke.
   - Command:
     `python3 -m pytest tests/release/ -q`
   - Result: `216 passed, 6 failed`
   - Result detail: current failures are outside the conversation-recall/memory continuity surface
     changed in this pass.

### Findings

1. The local-first retrieval contract is now explicit in generated runtime output.
   - The compiler now emits retrieval provider/model/profile metadata from
     `runtime.retrieval.embeddings`.
   - The current default public install contract is:
     - provider `ollama`
     - model `qwen3-embedding:0.6b`
     - profile `medium`
2. Install/start surfaces now treat Ollama as a real prerequisite when recall depends on it.
   - Wizard defaults, preflight, install summary, doctor, and launcher now consume the same
     retrieval-config helper.
   - The launcher checks real Ollama readiness instead of assuming Docker health is sufficient.
3. The saved-memory writer now accepts the compiler-emitted provider contract.
   - Shared provider normalization was added at the runtime boundary so the compiler-emitted
     lower-case `openai` token is accepted without changing the compiler back to a different alias.
4. Long conversations now have bounded older-user-context coverage.
   - The memory writer still keeps a bounded current-chat window.
   - It now also prepends a bounded older-user-only context section from earlier messages instead
     of relying on brittle complaint-specific keyword logic or a giant raw window.
5. Recall availability/freshness now has direct automated coverage.
   - Health, timeout, unreachable, cache-TTL, freshness, and newest-corpus cases are now tested in
     a dedicated suite.

### Remaining Work Before Broader Readiness Claims

- Run the `cross-surface landing gate` for:
  - Telegram
  - LibreChat web UI
  - scheduler-triggered flows
  - voice smoke coverage where relevant
- Run the `public release gate` from a clean install/public entrypoint story after the current
  unrelated release blockers are cleared:
  - `tests/release/test_background_agent_governance_contract.py`
  - `tests/release/test_local_web_search_compose.py`
  - `tests/release/test_native_stack_helpers.py`
  - `tests/release/test_voice_playground_dispatch_contract.py`
- If the product later wants separate recall/file-search embeddings, treat that as explicit
  architecture work rather than a hidden config tweak.
