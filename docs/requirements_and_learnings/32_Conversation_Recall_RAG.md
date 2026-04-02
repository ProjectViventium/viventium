# Conversation Recall RAG

**Document Version:** 1.8
**Date:** 2026-02-19
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

## Public-Safe Technical Design

- Build deterministic virtual files for conversation recall corpora.
- Embed them via the existing vector pipeline.
- Persist as file records with a recall context.
- Inject these files into runtime file-search resources when policy allows.

### Runtime resilience fallback
- If vector uploads are degraded, perform a scoped lexical retrieval over the user’s past messages.
- Inject retrieved snippets into shared run context for participating agents.
- Exclude the current conversation messages to avoid echoing the current turn.

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
