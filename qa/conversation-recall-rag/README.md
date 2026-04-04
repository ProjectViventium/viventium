# Conversation Recall RAG QA

## Purpose

Verify that Viventium conversation recall can reuse a user-scoped connected OpenAI account for
embeddings without breaking the existing environment-key embeddings path.

## Acceptance Contract

- The running isolated stack accepts a connected-account OpenAI token for embeddings through the
  normal LibreChat-to-RAG upload path.
- Connected-account subscription tokens are routed to the platform embeddings endpoint, not the
  Codex chat/replies base URL.
- When no user-scoped OpenAI key is available, LibreChat leaves the existing RAG env-key path
  unchanged.
- A modern-playground typed chat can still trigger conversation-recall indexing on the live stack.
- Any remaining assistant reply failure must be attributed separately from embeddings.

## Public-Safe Evidence

- LibreChat regression tests:
  - `viventium_v0_4/LibreChat/api/server/services/Files/VectorDB/__tests__/crud.spec.js`
- RAG container logs from the running isolated stack:
  - `docker logs librechat-rag_api-1`
- Modern playground browser artifacts:
  - `output/playwright/modern-playground-qa/.playwright-cli/`
  - Keep these local-only because they can include authenticated UI state.

## Verification Steps

1. Start the canonical isolated stack with `bin/viventium start --restart`.
2. Run the targeted LibreChat regression tests for `VectorDB/crud`.
3. Create an authenticated call session for the Viventium agent.
4. Open the returned modern-playground URL in a real browser.
5. Start chat, enable the transcript, and send a synthetic typed prompt.
6. Inspect RAG logs and launcher output for the exact prompt window.
7. Confirm embeddings succeed through OpenAI platform embeddings and separate any remaining
   completion failure by provider/runtime layer.
