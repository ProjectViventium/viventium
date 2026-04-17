# Telegram Document Attachments QA

## Purpose

Validate that Telegram document/message attachments reach the agent as readable context instead of
being silently reduced to caption-only turns.

## Scope

- Telegram ingress for non-image message attachments
- shared LibreChat message-attachment upload behavior for parseable files and provider-native files
- agent-visible file context and persisted message attachment linkage
- generic gateway parity for the same attachment path

## Test Cases

1. A parseable message attachment without explicit `tool_resource=context` is auto-promoted into
   the context-extraction pipeline only when it is not a valid native "Upload to Provider" file for
   the active endpoint/provider.
2. Provider-native message attachments keep the raw message-attachment path so BaseClient can send
   them through the normal provider encoding flow.
3. Extracted message attachments are stored as `FileSources.text` instead of opaque raw local files.
4. Unsupported binary message attachments that the runtime cannot send provider-natively or parse
   into readable context fail closed with a clear attachment-processing error.
5. Generic gateway ingress remains compatible with the same shared upload behavior.
6. Live local Telegram bridge E2E on the current main-agent provider proves:
   markdown attachments become readable text context and provider-native PDFs remain raw while still
   being readable by the model.
7. OCR-gated Office/OpenDocument files auto-route into context extraction and either use the
   configured OCR/parser path or fail honestly if that runtime capability is unavailable.

## Evidence Rules

- Use public-safe logs and synthetic filenames only.
- Do not include private chat text, user IDs, or real uploaded document names.
- Redact or omit Mongo identifiers when summarizing the incident.
