# Telegram Document Attachments QA

## Purpose

Validate that Telegram documents, photos, and albums reach the active model or delegated worker as
readable context instead of being silently reduced to captions or attachment placeholders.

## Scope

- Telegram ingress for documents, single photos, and same-name photo albums
- shared LibreChat message-attachment upload behavior for parseable files and provider-native files
- owner-scoped raw-byte projection into provider and GlassHive conversation workspaces
- ordered attachment identity, agent-visible file context, and persisted linkage
- complete Worker Bee file/media input plus generated-file output parity through control, provider
  fallback, restart, Telegram delivery, and linked Active Work
- one logical Telegram turn produces one visible assistant result
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
8. PPTX uploads extract slide text, speaker notes, and supported embedded image media; embedded
   images enter the same vision path as ordinary image uploads when the ingress surface supports it.
9. Trusted Telegram JPEG/PNG uploads bypass text-only document parsing, retain exact owner-scoped
   bytes, and materialize into the worker workspace without filename-based aliasing.
10. Multiple Telegram photos with the same transport filename stay distinct by durable file ID and
    preserve album order.
11. A completed Main answer is presented once; a later cortex result that only reformats that exact
    answer is suppressed.
12. Delegation preserves every supported attachment family's exact owner scope, identity, bytes,
    order, and grouping. The Bee's generated file/media returns once and opens from Telegram or
    linked Active Work after control, fallback, and restart; unavailable inputs or delivery fail
    truthfully.

## Evidence Rules

- Use public-safe logs and synthetic filenames only.
- Do not include private chat text, user IDs, or real uploaded document names.
- Redact or omit Mongo identifiers when summarizing the incident.
