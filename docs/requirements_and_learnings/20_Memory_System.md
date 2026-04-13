# Memory System: v0_3 vs v0_4 Analysis + Improvement Notes

**Document Version:** 2.6
**Date:** 2026-04-09
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

The v0_4 product has two different continuity surfaces that must not be conflated:

1. Saved memories
2. Conversation recall

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

### Why this distinction matters

- A recent correction in chat should usually be recovered by conversation recall even if it was
  never promoted into durable memory.
- Saved memory should not be silently mutated to compensate for broken recent-conversation recall.
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

---

## Part 3: Public-Safe QA Notes

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
