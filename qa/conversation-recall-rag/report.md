# Conversation Recall RAG QA Report

## Date

- 2026-04-04

## Build Under Test

- Repo branch: `codex/remote-modern-playground-access`
- Nested LibreChat branch: `codex/remote-modern-playground-access`
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
