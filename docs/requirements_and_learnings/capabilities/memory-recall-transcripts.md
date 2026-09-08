# Memory, recall, and transcripts

## User promise

Viventium can retain explicit saved facts, retrieve authorized prior conversations, and ingest
optional transcript evidence without mixing those surfaces or turning stale or unavailable data
into confident truth.

## Separate continuity surfaces

1. **Saved memory:** explicit durable keys for stable facts, preferences, project context, and other
   user-approved information.
2. **Conversation recall:** opt-in retrieval from the owner's prior eligible chats.
3. **Meeting transcripts:** optional local-first transcript summaries and retrieval artifacts.
4. **Listen-Only transcripts:** visible ambient evidence, excluded from ordinary chat recall and
   treated as soft evidence for later memory processing.

Failure or deletion in one surface does not silently mutate or certify another.

## Saved memory

- Read and write only within the authenticated owner and configured policy.
- Valid keys, entry limits, token budget, revision, and conflict behavior are typed and visible to
  the user surface.
- Persist before acknowledging a write. Edit, refresh, restart, and explicit forgetting must show
  the same authoritative state.
- A writer uses actual evidence and cannot turn a transient note, tool result, transcript ambiguity,
  or unsupported inference into a stable fact.

## Conversation recall

- Recall requires explicit owner opt-in, user isolation, current scope policy, and a healthy or
  truthfully degraded retrieval path.
- Main decides semantically when ordinary recall is useful; runtime never activates recall from
  prompt keywords.
- Deep Memory Search uses the same typed semantic boundary: it may search older authorized evidence
  only when that evidence could materially change the current result. It does not run for every
  self-contained capability or status turn.
- Vector resources require health, freshness, source/upload integrity, and owner-scope checks.
- If vector recall is unavailable, any supported source-only fallback remains inside the recall tool
  path and reports the degraded state.
- `no relevant evidence found` means retrieval ran successfully; `no evidence retrieved in this
  run` is inconclusive. Provider failure is never flattened into absence.
- Retrieved assistant chatter does not become new source evidence and cannot poison freshness.

## Transcript ingestion

### Ingestion

- **DATA-005:** New or changed files from the configured transcript folder are ingested and digested
  automatically, with an explicit manual trigger.

### Recovery

- **DATA-006:** A blocked transcript run is diagnosable and resumable without duplicate ingestion or
  silent loss.
- Transcript content is untrusted data for the configured model. Runtime may own deterministic file
  lifecycle and metadata but cannot infer meeting meaning with keyword or column heuristics.
- Transcript summaries preserve provenance, speaker uncertainty, and source scope. Raw transcript
  files are not fabricated as chat messages.

## Owners and QA

- Saved memory: nested LibreChat memory policy, routes, and data-schema methods
- Recall: nested LibreChat file-search/recall services and RAG sidecars
- Transcript operator: memory-hardening scripts and configured transcript source
- QA: `qa/memory-continuity/`, `qa/memory-hardening/`, `qa/conversation-recall-rag/`, and
  `qa/meeting-transcript-memory/`

Acceptance requires create/read/edit/forget, refresh and restart, healthy recall, successful-empty,
degraded and recovery states, owner isolation, transcript deduplication, and exact installed
candidate evidence. A matching answer without a same-run retrieval receipt does not prove recall.

## Detailed contracts

- [Memory System](../20_Memory_System.md)
- [Conversation Recall RAG](../32_Conversation_Recall_RAG.md)
- [Viventium Periphery Nightly Insights](../53_Viventium_Periphery_Nightly_Insights.md)

### Governed creation and recall defaults

An ordinary authorized user can create, read, update and delete only their own saved memories.
The memory API exposes configured non-secret `validKeys`; the Create dialog displays and enforces
those keys before submission. Server authorization and key validation remain authoritative.
Without a governed key list the existing free-form behavior remains available.

An account with no stored recall preference follows the compiled installer default. A stored
`false` stays false even without an explicit-choice marker: older opt-outs cannot safely be
reclassified as defaults. Explicit edits record the chosen state. This supersedes the saved
proposal to rewrite all legacy false values.

Recall ingestion uses bounded embedding batches (`EMBEDDING_BATCH_SIZE`). A recall probe must
search text that exists in the indexed corpus; conversation titles and Worker status cards do not
prove corpus retrieval. Source owners are LibreChat's memory route/Create dialog,
`viventium-reconcile-user-defaults.js`, and RAG document ingestion. Installed create/reload/cleanup
and grounded recall remain separate evidence gates; source preservation adds no new live pass.
