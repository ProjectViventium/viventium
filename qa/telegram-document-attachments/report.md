# Telegram Document Attachments QA Report

Date: 2026-04-16

## Summary

The Telegram attachment incident was caused by parseable message attachments entering LibreChat as
raw `message_attachment` uploads without the context-extraction path. That left the agent with only
the caption text and no readable file context, which explains the low-context reply. The fix now
preserves provider-native message attachments first, auto-promotes only the remaining readable
non-provider-native files into context extraction when the ingress adapter omits
`tool_resource=context`, and fails closed when a file would otherwise become an inert opaque
attachment.

## Forensic Evidence

- Live Mongo evidence for the failing turn showed:
  - the user message stored caption text only
  - `files: []` on the persisted user message
  - a separate file record created at the same time as a raw local `message_attachment`
- Shared agent-upload code showed the gap:
  - only `tool_resource=context` uploads were converted into `FileSources.text`
  - raw message attachments without that field stayed opaque and never produced file context
- Native LibreChat upload behavior showed an important parity rule:
  - some message attachments are supposed to stay raw because the downstream client encodes them for
    provider-native upload (`Upload to Provider`)
  - bridge defaults therefore must distinguish provider-native uploads from context extraction, not
    flatten them into one path
- Shared file-processing analysis uncovered a second issue:
  - the default text-parser MIME matcher is intentionally broad for the RAG text endpoint
  - without an extra guard, binary Office/OpenDocument files could fall into naive native text reads
    instead of using OCR/document parsing or failing clearly

## Automated Checks

- Passed: `cd viventium_v0_4/LibreChat/api && npm run test:ci -- --runInBand server/services/Files/process.spec.js`
- Passed: `cd viventium_v0_4/LibreChat/api && npm run test:ci -- --runInBand server/routes/files/files.agents.test.js`
- Passed: `cd viventium_v0_4/LibreChat/api && npm run test:ci -- --runInBand server/routes/viventium/__tests__/gateway.spec.js`
- Passed: `cd viventium_v0_4/LibreChat/api && npm run test:ci -- --runInBand server/routes/viventium/__tests__/telegram.spec.js -t "fails closed when a Telegram attachment cannot be processed"`

## Live Local E2E Validation

Current runtime surface during validation:

- local LibreChat API running on `http://localhost:3180`
- Telegram bridge enabled and bot process running
- main agent configured for the current local surface
- live main-agent provider: `anthropic`
- live main-agent model: `claude-opus-4-6`

Observed live cases through the real `/api/viventium/telegram/chat` route using a linked Telegram
user and the same payload contract the Python Telegram bot sends:

1. Baseline chat path
   - prompt: reply with a unique sentinel only
   - result: bridge returned the exact sentinel, confirming the live Telegram route and stream path
     were healthy before attachment validation

2. Markdown attachment, non-provider-native on the Anthropic main agent
   - prompt: reply with only the codename from the attached markdown file
   - result: assistant returned the exact codename from the file
   - persisted file record:
     - `source: text`
     - `context: message_attachment`
     - `type: text/markdown`
     - extracted text contained the expected sentinel
   - persisted user message contained exactly one linked file entry

3. PDF attachment, provider-native on the Anthropic main agent
   - prompt: reply with only the token inside the attached PDF
   - result: assistant returned the exact token from the PDF
   - persisted file record:
     - `source: local`
     - `context: message_attachment`
     - `type: application/pdf`
     - no extracted text blob was stored on the file record
   - persisted user message contained exactly one linked file entry

These live results confirm both branches of the shared decision:

- parseable non-provider-native message files are promoted into readable context
- provider-native message files stay on the raw attachment path and remain readable by the model

## Known Unrelated Red Test

- `server/routes/viventium/__tests__/telegram.spec.js`
  - existing failure: `POST existing convo resolves parentMessageId from the latest leaf, not the latest createdAt row`
  - failure is in Telegram conversation parent selection, not attachment ingestion
  - full-suite rerun still shows only that same parent-message mismatch after the attachment fix

## Product Truth

- Telegram and other bridges must preserve the same default message-file semantics as LibreChat web.
- Valid provider-native files must stay on the normal raw message-attachment path.
- Parseable files that are not valid provider-native uploads for the active endpoint/provider must
  auto-promote into the context-extraction path even when the bridge omits `tool_resource=context`.
- OCR-gated Office/OpenDocument binaries must use the configured OCR/document-parser path or fail
  honestly instead of falling back to fake text parsing.
- Files that are neither provider-native nor readable through context extraction must fail closed
  instead of being stored as inert message attachments.
- The same hardening now applies to any ingress that uses the shared `processAgentFileUpload`
  message-attachment path.
