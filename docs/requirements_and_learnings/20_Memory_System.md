# Memory System: v0_3 vs v0_4 Analysis + Improvement Notes

**Document Version:** 2.8
**Date:** 2026-05-05
**Owner:** Viventium Core
**Scope:** High-level comparison of memory UX in v0_3 (Python) vs v0_4 (LibreChat), with public-safe lessons and implementation notes.

---

## Deployment Status

| Version | Date | Status | Environment |
|---------|------|--------|-------------|
| v2.4 | 2026-02-09 | Ready to deploy | current cloud-style deployment environment |
| v2.3 | 2026-02-01 | Superseded | legacy deployment environment |
| v2.2 | 2026-02-01 | Superseded | - |
| v2.1 | 2026-02-01 | Superseded | - |
| v2.0 | 2026-01-30 | Documented only | - |

## Executive Summary

The v0_3 Python stack has a more explicit memory architecture with short-term and long-term
separation, vector-based recall, and session continuity. The v0_4 LibreChat implementation relies
more heavily on key/value storage and broad injection of memory into prompts, which makes it easier
to drift into stale context if retrieval and update rules are not kept disciplined.

The core problem is usually not storage itself. It is retrieval, prioritization, and update
discipline:

- recent context must remain visible
- durable facts must remain stable
- temporary notes must not overwrite long-lived memory
- updates should stay additive whenever possible

## Product Surface Distinction

The v0_4 product has four different continuity surfaces that must not be conflated:

1. Saved memories
2. Conversation recall
3. Meeting transcript recall
4. Listen-Only call transcript evidence

### Saved memories

- Durable and explicit.
- Intended for facts, stable preferences, durable project context, and other information the user
  explicitly wants retained.
- Governed by the user-level memory opt-in and memory writer rules.

### Conversation recall

- Retrieval-oriented and session-continuity oriented.
- Intended to recover recent or historical chat corrections, updates, and context from prior
  conversations.
- Governed by conversation-recall policy plus runtime health/freshness.
- When enabled, the decision to search prior chats is model-owned through system-prompt/tool
  instructions; runtime must not use prompt-text regexes to decide recall intent.

### Meeting transcript recall

- Optional, local-first input from `VIVENTIUM_MEMORY_TRANSCRIPTS_DIR`.
- Owned by the saved-memory hardening operator and the existing file-search/RAG pipeline.
- Raw transcript files are never inserted as synthetic chat messages.
- Each new or changed transcript is first summarized as its own unit by the configured high-effort
  memory-hardening model. The summarizer receives the raw transcript envelope plus deterministic
  metadata: filename, file mtime, current date, configured/user-derived display names, optional
  calendar match when available, and the transcript caveat prompt.
- The saved-memory hardener receives the generated detailed summary plus provenance/evidence
  metadata, not the raw transcript body. This keeps raw transcript token load out of the hardener
  while preserving the transcript as soft meeting evidence.
- The runtime does no semantic parsing, column detection, participant extraction, or filename
  interpretation. CSV, TXT, MD, JSON, VTT, SRT, and similar text files are all data for the model.
- The configured transcript folder is expected to contain transcript artifacts. Downloader state or
  operational logs should live outside the source folder when possible. When a downloader must leave
  bookkeeping beside transcript files, `VIVENTIUM_MEMORY_TRANSCRIPTS_IGNORE_GLOBS` or
  `--transcript-ignore-glob` can exclude relative path globs deterministically. Ignore rules are
  path/lifecycle bookkeeping only; they must not parse transcript content or infer meeting meaning.
  Hidden files, temp/download partials, state directories, and `.log` files are ignored by default
  as source-folder sidecars.
- Transcript evidence is softer than chat evidence. A single transcript can support
  meeting-scoped `moments` or `context`; stable beliefs, identity, direction, or durable preferences
  require either two recent meeting transcripts or transcript plus chat evidence.
- Stable-memory transcript recency is validated against deterministic file metadata from the
  scanned workpack, not model-supplied timestamps.
- Any non-noop hardener operation must carry valid evidence. Empty evidence is never enough for
  stable memory or transcript-derived writes.
- Prompt-injection protection comes from explicit untrusted-data sentinels and deterministic output
  validators, not from string-matching transcript content.
- Content-hash state prevents unchanged files and rename-only changes from being reprocessed.
- Processed state is only valid when the expected vector artifact still exists. Apply runs must
  requeue indexed transcript content when Mongo bookkeeping says `embedded=true` but the local
  vector store no longer has the corresponding summary/raw document.
- User/source-scoped derived transcript artifacts that are no longer represented in the current
  processed-content index are stale and must not remain attached as live recall evidence.
- Files deferred by deterministic transcript caps are not considered processed; later scheduled or
  manual runs must retry them even when mtime, size, and content hash are unchanged.
- Normal transcripts under the per-file/model-safe limit must be supplied completely to the
  transcript summarizer. A run-level character budget must never slice a normal transcript.
- Oversized text transcripts that would require partial input are deferred rather than promoted as
  complete recall. Binary or non-text inputs remain skipped as non-text.
- If the configured transcript source folder changes, per-user processed-content state from the old
  folder must not be reused for the new folder. Old artifacts become stale derived state and the new
  folder is processed under its own source-folder hash.
- Runtime recall attaches only artifacts whose stored source-folder hash matches the currently
  configured transcript folder, so artifacts from an old opt-in folder do not silently reappear
  after a directory change.
- Runtime recall attaches transcript vector artifacts only when the local RAG/vector runtime is
  configured and healthy. If vector runtime is unreachable, transcript recall must be advertised as
  unavailable instead of exposing dead file_search resources.
- Transcript RAG defaults to `detailed_summary_only`: the runtime file-search database stores and
  attaches detailed summary artifacts by default. `raw_and_summary` and `raw_only` are explicit
  QA/operator modes.
- Each detailed summary also carries agent-authored inventory fields when knowable: display title,
  one-line context, meeting date/time, and participants. The hardener builds a current
  user/source-scoped `meeting_inventory:*` file-search artifact from processed summary metadata.
  That inventory is a transcript-recall table of contents, not a saved-memory key, so it can be
  regenerated, repaired, and stale-pruned with the vector lifecycle without polluting durable memory.
- The transcript summarizer must keep those inventory fields human-contextual and compact. Artifact
  IDs, stable file IDs, vector IDs, content hashes, and source-folder hashes remain internal
  metadata and must not be written into the broad table-of-contents body.
- The inventory vector text itself must not prepend the generic transcript artifact header; lifecycle
  identifiers stay in Mongo/vector metadata, while the model-visible inventory remains a compact
  list for who/when/context recall.
- Broad transcript questions, including "list my recent conversations based on transcripts
  chronologically and give me a 5 line summary based on the actual context", must use that inventory
  surface to see the processed transcript set before composing the answer. The inventory exists so
  the model can reason over all current transcript entries with dates, participants, and one-line
  context; it must not become deterministic semantic extraction or durable memory promotion.
- Inventory ordering should use the model-authored meeting date/time when present, falling back to
  file mtime only when the meeting date/time is unknown. If the inventory grows beyond its compact
  source-backed size limit, it must truncate at entry boundaries and include an explicit omitted-entry
  marker rather than silently slicing the middle of the list.
- If detailed meeting summaries and derived conversation recall both return file_search hits,
  ranking must remain evidence-based: low-signal assistant no-access/no-memory disclaimers should
  not outrank current transcript content, but transcript source class must not blanket-override
  stronger chat-history evidence.
- Transcript vector upload temp files are private local artifacts and must be written with explicit
  owner-only permissions.
- Every hardening run should leave an inspectable local run directory. Failed runs must persist a
  redacted `summary.json`, `failure.redacted.json`, and `run-log.redacted.jsonl` with phase, reason,
  error class, timeout/status/signal when available, and message hash/preview without leaking
  private paths, account identifiers, secrets, or transcript text.
- Memory-hardening locks are concurrency guards, not durable state. A lock with a live recorded PID
  must fail closed, but a stale lock whose PID no longer exists must be cleared before the next
  manual or scheduled run so recovery does not require hand-editing local state.

### Listen-Only call transcript evidence

- Listen-Only Mode is live voice presence without live response. It saves transcribed call turns for
  later consolidation while bypassing the live Agents controller, TTS, tools, background cortices,
  title generation, and the live LibreChat Memory Agent.
- Listen-Only entries are structured transcript evidence stored with message metadata so they remain
  visible in the owning conversation history. They are not synthetic user chat messages:
  `isCreatedByUser=false`, `sender="Listen-Only"`, `tokenCount=0`, and
  `metadata.viventium.type="listen_only_transcript"`. They must opt out of Meili indexing with
  `_meiliIndex=false`.
- Live agent context must skip these entries even when they sit in the same conversation tree. After
  Listen-Only is turned off, the next normal assistant response must resume from the latest
  non-Listen-Only parent and must not spend live prompt tokens on ambient transcripts.
- Consecutive Listen-Only entries in the same visible timeline should be threaded linearly under
  the latest Listen-Only row, not as sibling branches under the same live parent. This is a UI tree
  shape rule only; memory and recall keep using the `listen_only_transcript` metadata boundary.
- The memory hardener receives these entries as `ambient_transcript` evidence. It must treat them
  like transcript evidence: softer than chat, untrusted as instructions, and insufficient by itself
  for stable identity, durable preferences, long-term direction, or beliefs unless corroborated.
- Stable-memory corroboration must count distinct ambient sources, not adjacent rows. Two rows from
  the same Listen-Only call session are one ambient source for stable-memory gating; a stable write
  needs either normal conversation evidence plus recent ambient evidence, or multiple distinct
  ambient source ids. Transcript-scoped keys such as `context` and `moments` can use single-session
  ambient context.
- Conversation recall excludes Listen-Only transcript entries at the corpus query boundary and in
  fallback filters so overheard room text does not masquerade as user-authored chat history or
  starve normal messages from the recall window.
- Same-microphone audio is not true speaker diarization. Speaker labels are trusted only when they
  arrive from structured LiveKit participant or track identity.

### Why this distinction matters

- A recent correction in chat should usually be recovered by conversation recall even if it was
  never promoted into durable memory.
- Saved memory should not be silently mutated to compensate for broken recent-conversation recall.
- Transcript recall should not silently promote audience-specific or outdated meeting language into
  durable identity. It should preserve important transitions while letting stale details decay or be
  compacted.
- Listen-Only recall follows the same caution: being present in a room is useful memory evidence,
  not blanket proof of the user's stable beliefs or instructions.
- If the product later adds an explicit “continuity state” surface for scheduled consolidation or
  working summaries, that should be designed as its own bounded layer with TTL/audit rules, not by
  overloading saved-memory semantics.

---

## Part 1: v0_3 Memory System (Python Stack)

### 1.1 Architecture Overview

```
storage/memory/<user_id>/
├── snapshots/
│   └── memory.md           # Full world-state snapshot
├── summaries/
│   └── <session_id>.md     # Per-session compressed summaries
├── transcripts/
│   └── <session_id>.md     # Raw conversation transcripts
├── raw/
│   └── gpt_memory_export.txt
└── secret/
    └── snapshots/memory.md
```

### 1.2 Memory Loading Flow

1. Snapshot bootstrap loads the current memory snapshot into the system prompt.
2. Recent working memory is appended when the last transcript is fresh enough.
3. A vector index is available for semantic search and recall.

### 1.3 Recall Tools

The system exposes explicit tools for semantic search and section-level reads so the agent can
search memory when needed rather than relying only on injected context.

| Tool | Purpose |
|------|---------|
| `search_memory` | Semantic vector search plus current session buffer |
| `read_memory_section` | Read a specific snapshot section |

### 1.4 Public-Safe Learning

The strongest v0_3 lesson is that memory systems work better when the agent can distinguish:

- durable facts
- recent working context
- private or temporary notes
- search-based recall

---

## Part 2: v0_4 Memory System (LibreChat)

### 2.1 Core Strengths

v0_4 improves product integration and keeps memory closer to the runtime surface that users actually
see. It also makes it easier to ship memory behavior as part of the source-of-truth config.

### 2.2 Common Failure Modes

- memory writes can become too rewrite-heavy if the model is not guided toward additive updates
- recency can drift if the agent does not get canonical time context
- multi-line values can become hard to parse if they are serialized too aggressively
- placeholder text can erase prior meaning if the system accepts it as a destructive overwrite

### 2.3 Public-Safe Fix Pattern

The public-safe fix pattern is:

1. Inject canonical time context where the memory agent needs it.
2. Keep the formatted memory payload easy for the model to parse.
3. Prefer additive merges over destructive rewrites.
4. Add guardrails for placeholder-based updates that would otherwise drop prior content.
5. Keep the runtime behavior aligned with the tracked source-of-truth config.

### 2.3.1 Continuity failure handling

When the user reports stale understanding, fix order matters:

1. Check whether saved-memory opt-in is enabled.
2. Check whether conversation recall is healthy and fresh.
3. Check whether the runtime is confusing retrieval failure with “nothing found”.
4. Check whether unrelated scheduler/task prose is being injected as faux context.

Do not jump straight to prompt edits or user-specific hardcoding when the failure is caused by
runtime retrieval, freshness, or context assembly.

### 2.4 Compiler-Owned Model Assignment

The memory runtime is configurable, but the generated `librechat.yaml` must still come from the
installer/compiler ownership layer instead of inheriting historical template defaults.

- The compiler must assign `memory.agent.provider` and `memory.agent.model` from actually available
  foundation auth (`openai` / `anthropic`), including connected-account auth.
- Do not silently leave the memory writer on xAI when xAI was never configured for that install.
- Current compiler policy prefers Anthropic for the memory writer when Anthropic is available, and
  otherwise falls back to OpenAI.
- QA and docs must reflect that exact compiler rule instead of assuming memory follows some separate
  generic foundation ordering contract.
- Source-of-truth templates may still carry historical defaults, but generated runtime files are the
  product contract users actually run.

### 2.5 Example Memory Structure

```yaml
working:
  summary: "Current active tasks and recent context"
  _updated: 2026-02-09
  _expires: 2026-02-12

signals:
  - domain: productivity
    observation: "Morning sessions tend to be more focused"
    confidence: high
    first_seen: 2026-01-15
    last_seen: 2026-02-09

drafts:
  - thread: launch_planning
    status: in_progress
    started: 2026-02-08
    last_worked: 2026-02-09
```

### 2.6 2026-04-08 Incident Follow-Up

The April 8, 2026 continuity incident clarified three separate truths that must stay distinct in
both code and QA:

#### 2.6.1 Recent-chat recall failure is not the same as saved-memory failure

- A stale or unavailable conversation-recall corpus can cause the assistant to miss recent
  corrections even when saved memories are enabled.
- Re-enabling saved memories alone does not repair recent conversational continuity if recall
  indexing/retrieval is unhealthy.

#### 2.6.2 Saved-memory writer initialization is part of product correctness

- The generated runtime contract currently compiles `memory.agent.provider` from foundation
  availability using lower-case values such as `openai`.
- Runtime provider resolution now accepts the compiler-emitted canonical values through the shared
  normalization boundary instead of requiring a different alias such as `openAI`.
- QA must cover both the compiler output and the runtime initialization path so a generated
  provider token cannot silently regress in one resolver while still appearing valid in another.
- If the memory writer fails before it starts, the system cannot rely on prompt rules like
  “NO DATA LOSS” or contradiction cleanup because the memory agent never gets to run.
- Connected-account OpenAI Codex routes are a second runtime contract inside the memory writer:
  - top-level `instructions` must be present on Responses requests
  - `system` / `developer` messages must not remain inside Responses `input`
- Therefore Codex compatibility is not only “does auth initialize”; QA must prove the saved-memory
  run itself survives the live connected-account request shape.

#### 2.6.3 Long-conversation corrections need explicit coverage

- The current memory writer processes a bounded recent message window.
- The runtime code defaults that window to `5` messages if no product config overrides it, while
  the current Viventium source-of-truth config sets it to `15`.
- A bounded current window is still correct for efficiency, but it needs structured older-context
  coverage so important earlier user corrections are not dropped purely because they sit outside
  the current chat slice.
- The implemented fix prepends a bounded older-user-context digest from messages before the current
  window, using explicit scan/user-turn/char caps rather than a giant raw window.
- This older-context path must stay generic and metadata-free:
  - no hardcoded entity names
  - no complaint-specific keyword branches
  - no user-identity-specific logic
- QA must cover inclusion, truncation, and the exclusion of irrelevant older assistant chatter.

#### 2.6.4 Product requirement going forward

- Saved memory must remain the durable explicit-notes surface.
- Conversation recall must remain the recent/history recovery surface.
- If Viventium adds a future “continuity state” or consolidation layer, it must be explicit,
  bounded, auditable, and separate from saved-memory semantics.

#### 2.6.5 Anthropic default-thinking memory writer contract

- The April 21, 2026 local continuity investigation found a second memory-writer failure class on
  the Anthropic path:
  - Anthropic default thinking was active even when runtime did not explicitly set a `thinking`
    object.
  - The memory writer also forces tool use for deterministic `apply_memory_changes`.
  - Sending `temperature` with active/default Anthropic thinking is invalid.
  - Sending `thinking: false` on that forced-tool path is also invalid for the live request shape.
- The owned product fix is:
  - treat Anthropic default thinking as active when sanitizing memory-writer config
  - remove `temperature` whenever Anthropic thinking is active by default or explicitly
  - for adaptive-era Anthropic models currently used by Viventium memory (`claude-sonnet-4-5`),
    omit explicit `temperature` entirely from the shipped memory-writer config so fresh installs do
    not rely on runtime stripping to stay valid
  - if the memory run is also forcing tool use, remove `thinking` entirely instead of setting it to
    `false`
  - keep one retry for transient upstream failures, but log the exact provider/model/thinking mode
    on hard failure
- This is a runtime contract fix, not a prompt fix. If the writer request shape is illegal, the
  saved-memory prompt never gets a chance to help.

#### 2.6.6 Missing visible follow-up can masquerade as memory failure

- The same April 21, 2026 incident showed a separate user-visible failure:
  - background cortex recall recovered the correct same-day context
  - but the user-facing follow-up message could still disappear if follow-up synthesis returned an
    empty string
- Product rule:
  - `{NTA}` remains the only legal silent outcome for a non-replacement follow-up
  - a truly empty follow-up generation must not be auto-normalized into `{NTA}` and suppressed
  - raw `{NTA}` from the follow-up LLM must not silence a non-replacement follow-up when a
    substantive visible fallback still exists after cleanup
  - if synthesis fails, returns empty, or incorrectly returns `{NTA}` while substantive background
    insight exists, persist a deterministic visible fallback instead of dropping the correction on
    the floor
- Otherwise the user experiences “memory did not work” even though the recovery layer actually found
  the right context.

### 2.7 Strict Memory Rules

The following rules are product requirements. They preserve the user wording, normalized only for
typing errors.

a. Memory has to be fast; we have 0 tolerance for slow bottlenecks.

b. Viventium LibreChat Memory has to work perfectly fine without having RAG Conversation enabled.
RAG Conversation is a nice-to-have hardening, and that should also work really well without
LibreChat Memory enabled.

c. Forgetting correctly is as important as remembering correctly. As per rule a, we cannot afford
to lose speed, and more tokens = more delay = more cost. So efficiency is key.

d. Forgetting is important, but so is history, tracking change, and signals. Memory must precisely
track notable changes and not always wipe past memories for new ones.

e. Efficient additive memories. Think of a chain-of-draft method: you are not rewriting /
overwriting all the past. You are using a no-blabber, token-efficient, record-tracking method for
each key to remember everything, not just the latest.

f. Read the memory-related `.md` files to know all the edge cases and important features and
guidelines, line by damn line, with no skipping or laziness.

### 2.8 2026-04-09 Integrity Follow-Up

The April 9, 2026 memory-integrity investigation added five concrete product truths:

#### 2.8.1 Saved-memory stale output can happen even when recall is also degraded

- The scheduled Telegram stale-output incident was explained by stale saved-memory keys on its own.
- In the observed run, the saved-memory `context` and `drafts` surfaces still carried explicitly
  forgotten references, while runtime file/recall retrieval was also degraded.
- Product debugging must therefore check saved memory and conversation recall separately instead of
  assuming a single continuity failure.

#### 2.8.2 Forgetting is a cross-key rewrite contract

- In the current 9-key architecture, `delete_memory` is only valid when an entire key should be
  removed.
- Forgetting part of memory must scan all keys, rewrite every affected key with `set_memory`, and
  remove only the forgotten detail.
- The forgetting contract must preserve unrelated history, change-tracking, and still-useful
  signals instead of flattening a whole key.
- On April 9, 2026, a local restart onto the fixed compiled runtime proved this through the product
  path: saved-memory maintenance/write processing removed previously stale forgotten references from
  `context` and `drafts` without manual database edits.

#### 2.8.3 Punctuation corruption must be cleaned at shared boundaries

- Repeated semicolon runs and similar punctuation corruption are token waste and a product defect.
- Shared memory write preparation and deterministic maintenance must collapse this corruption before
  it persists or reappears in later summaries.
- This cleanup is generic text hygiene, not a user-specific patch.

#### 2.8.4 Conversation-recall triggering belongs in prompt/config, not runtime text gates

- On April 9, 2026, Viventium removed runtime query classifiers that tried to decide from prompt
  text whether conversation recall should run.
- The correct contract is:
  - if conversation recall is enabled, inject the YAML-configured recall instruction into the
    agent system prompt
  - let the model choose when to use `file_search`
  - keep degraded recall fallback inside the retrieval/tool path, not in a prompt-text classifier
- This matters to memory because saved memory and conversation recall are separate continuity
  surfaces and must both stay efficient, auditable, and non-overfit.

#### 2.8.4 Temporal memory must self-heal without waiting for token pressure

- Expired `context`, stale `working`, and long-idle active `drafts` are correctness issues even
  when memory is well under budget.
- Deterministic maintenance must trigger on temporal staleness itself, not only on token pressure
  or scheduler/tool residue.
- Maintenance must refresh `context` / `working` markers to the current date when it rewrites those
  temporal keys.

#### 2.8.5 Draft history must stay additive

- Drafts are a compact active-work index, but history still matters.
- Archiving stale or completed draft threads is preferred over erasing them outright when a compact
  archive entry can preserve the useful trail.
- Later maintenance passes must preserve previously archived draft entries instead of silently
  dropping them on re-compaction.

### 2.9 2026-04-13 Remote Connected-Account QA

The April 13, 2026 remote QA pass added another concrete continuity boundary:

#### 2.9.1 Connected-account chat success is not memory success

- A real connected OpenAI account on the stale remote install produced successful live chat.
- An explicit memory-worthy prompt also got an in-thread success response (`SAVED`).
- But the durable-memory surfaces still failed:
  - the browser `Memories` panel stayed at `0% used` / `No memories yet`
  - the saved-memory store still had `0` entries for that user
  - a brand-new conversation answered `Unknown` instead of recovering the stored preference

#### 2.9.2 Same-thread success is not acceptable memory evidence

- A product QA pass must not treat “the assistant answered correctly in the same thread” as proof
  that memory works.
- Durable-memory acceptance now requires all three:
  1. successful chat on a real connected account
  2. a real saved-memory artifact appearing in the durable memory surface
  3. cross-conversation recovery of that stored fact

#### 2.9.3 Memory and recall still fail independently

- The same remote run also showed recall remained unavailable because the local recall runtime was
  not live on that machine.
- Therefore:
  - connected foundation-model auth
  - durable saved-memory writing
  - conversation-recall retrieval
  are three separate acceptance surfaces and must be QA’d separately.

#### 2.9.4 Connected-account memory fixes must land in the shipped runtime bundle

- The runtime path that processes saved-memory requests imports the compiled `packages/api/dist`
  bundle, not the TypeScript source files directly.
- That compiled bundle is a generated local runtime artifact, not a tracked public-repo source of
  truth.
- Therefore a source-only fix inside `packages/api/src/...` is not a shipped product fix unless the
  supported upgrade/start path rebuilds the local bundle to match it.
- The April 14, 2026 remote-memory incident proved this boundary directly:
  - the source file carried the Codex instruction-normalization fix
  - the existing local compiled bundle still lacked that logic
  - the remote upgraded runtime therefore continued to fail with live
    `400 "System messages are not allowed"` responses
- Release acceptance for Codex-connected memory now requires both:
  1. source-level tests for the owning normalization logic
  2. explicit verification that the locally built runtime bundle used by the product carries the
     same behavior after the supported rebuild path runs
- In practice, that means:
  - keep launcher/upgrade rebuild detection tied to package source freshness, not only manifest
    mtimes
  - keep a regression that exercises the built `dist` bundle, not only the source test path

#### 2.9.5 Non-stream Codex runs must reconstruct streamed tool output

- A later April 14, 2026 remote repro exposed a second connected-account boundary after the
  instruction-normalization fix landed.
- For the saved-memory writer, the product path uses non-stream processing, but the Codex bridge
  still forces Responses requests to `stream: true` upstream and then adapts the SSE back into a
  JSON response for the caller.
- On the failing runtime, the upstream run could complete successfully while the bridged JSON
  response still showed:
  - `status: "completed"`
  - `output: []`
- The missing tool call was not a model decision bug. The actual function-call item existed only in
  streamed `response.output_item.*` and argument-delta events; the non-stream adapter was dropping
  them and returning only the sparse `response.completed` payload.
- Product requirement:
  - when Codex-connected Responses are adapted from SSE into JSON for non-stream callers, the bridge
    must reconstruct `output` from streamed output-item events whenever the completed response omits
    them
  - this includes function-call items and their argument deltas, not only plain text deltas
- QA for connected-account saved memory must therefore prove all three layers:
  1. the request shape is accepted
  2. the adapted non-stream JSON preserves the tool call in `output`
  3. the tool artifact reaches the durable memory store in a real browser flow

---

## Part 3: Public-Safe QA Notes

### 3.0 Scheduled Memory Hardening

Viventium now has a separate local operator job for saved-memory hardening. This is not the live
Memory Archivist and not conversation recall.

The supported entrypoint is:

```bash
bin/viventium memory-harden dry-run
bin/viventium memory-harden apply --run-id <run-id>
```

Product contract:

- semantic hardening is opt-in and default-off
- default schedule is daily `0 3 * * *` when enabled
- daily schedules run at local macOS wall-clock time; `timezone` is exported for logs/operator
  context and must not be confused with a LaunchAgent timezone override
- default lookback is 7 days
- default idle gate skips users active in the last 60 minutes
- default input cap is 500,000 estimated characters and full-lookback mode is on by default
- the job imports the generated runtime memory instructions for key semantics, but uses a separate
  batch hardener prompt
- if the 7-day corpus exceeds the configured input cap, the job fails closed for that user unless
  the operator explicitly allows partial lookback
- when `dry_run_first` is enabled, the first scheduled apply after a fresh dry-run marker is absent
  performs a dry-run and writes the marker; the next scheduled run can apply
- the batch hardener must not rewrite `working`, because `working` is owned by the current
  conversation
- model output is a proposal only; database writes go through the existing memory methods and
  shared memory policy
- raw proposals and rollback snapshots stay under App Support state
- redacted run logs record memory-instruction presence/hash, lookback coverage, message counts,
  conversation counts, prompt size, and changed key names without storing raw conversation text
- macOS installs reconcile the LaunchAgent from generated config; the scheduled job invokes the
  memory-hardening wrapper directly from the plist so it is not blocked by a long-running
  user-facing CLI launcher lock. Non-macOS installs need an operator-managed cron/systemd
  equivalent.
- `runtime.memory_hardening.operator_user_email` optionally scopes scheduled/helper hardening to one
  local account; empty means all local users are eligible
- the compiler emits the selected hardening provider/model/effort tuple from configured foundation
  auth, preferring Claude Code `claude-opus-4-7` at `xhigh` when Anthropic is available and falling
  back to Codex/OpenAI `gpt-5.5` at `xhigh` when OpenAI is the available foundation route
- the OpenAI/Codex hardening path must pass a structured output schema and `xhigh` reasoning effort
  to the Codex CLI, matching the compiler-emitted tuple instead of relying on stale internal
  hardener fallbacks
- the macOS status-bar helper may expose an Advanced action for manual transcript ingest; that
  action must call the memory-hardening wrapper directly, surface the active user scope before and
  after the run, surface redacted count telemetry such as files checked, summaries uploaded, and
  files deferred by caps, bypass the idle gate because it is an explicit user action, and log only
  status/scope/counts, never transcript text
- public docs and QA artifacts must contain only hashed user ids, counts, key names, and policy
  outcomes

The job may use host-authenticated Claude Code or Codex CLI sessions. That is a privacy and billing
boundary different from the live user-connected memory writer, so semantic hardening must remain
explicitly enabled by the operator and covered by the public/private boundary doc.

### What to check

- the memory agent receives canonical time context
- the stored memory format is parseable and stable
- updates remain additive when possible
- placeholder text does not delete prior meaning
- the live runtime matches the source-of-truth config
- the generated runtime does not point memory at an unavailable provider
- the generated runtime provider string is actually accepted by runtime initialization
- a local restart onto the generated runtime removes the prior unsupported-provider failure without
  requiring manual App Support or Mongo edits
- connected-account installs still compile a valid memory writer without requiring extra API keys
- connected-account Codex memory requests normalize instruction messages into top-level
  `instructions` instead of leaving `system` / `developer` entries inside Responses `input`
- long-conversation corrections do not disappear purely because they fell outside a tiny memory
  writer window
- older-user-context limits remain bounded and token-efficient

### What not to publish

- private user email addresses
- named family members or partners
- private client or company names
- absolute local filesystem paths
- machine names or operator-only hostnames
- private deployment commands that depend on local secrets

### Safe command shape

Use repo-relative or environment-variable-based examples instead of personal paths:

```bash
cd viventium_v0_4/LibreChat
node scripts/viv-user-sync.js pull --memories --email="$USER_EMAIL"
node scripts/viventium-sync-agents.js push --prompts-only
```

---

## Executive Guidance

- Prefer additive updates over full rewrites.
- Keep time-sensitive context explicit.
- Keep public docs free of private identity and machine-specific data.
- Treat source-of-truth config as the real contract and runtime snapshots as evidence, not authorship.
- Keep durable memory and recent conversation continuity as separate product concerns.
