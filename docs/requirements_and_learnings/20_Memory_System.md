# Memory System: v0_3 vs v0_4 Analysis + Improvement Notes

**Document Version:** 2.4
**Date:** 2026-02-09
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

### 2.4 Example Memory Structure

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

---

## Part 3: Public-Safe QA Notes

### What to check

- the memory agent receives canonical time context
- the stored memory format is parseable and stable
- updates remain additive when possible
- placeholder text does not delete prior meaning
- the live runtime matches the source-of-truth config

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
