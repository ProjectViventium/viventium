# Telegram Document Attachments QA Report

## 2026-10-27 — selected local file recovery (blast-radius)

**Scoped local acceptance: PASS.** This is the outbound `TGDOC-011` consumer, not the full
`TGDOC-010` Worker/provider/channel matrix.

A native harness created a valid file and selected it from an ordinary OS temporary folder.
xPerfect rejected that folder before taking a file snapshot. Core and Telegram correctly kept
that typed unavailable result. Asking for OS access would not have corrected this publication rule.
The clear existing staging instruction had already failed on consecutive scheduled turns.

The shared publisher now snapshots an explicitly selected ordinary local file when the host harness
already has Full access and native tools. It reuses the immutable output, signed carrier and normal
Core/Telegram importer. No model call, format router, extra file cache or channel-specific fallback
was added. Restricted execution, implicit discovery and protected sources remain fenced. Hosts
explicitly declare their private support root. Review also closed external-upload and case-alias
bypasses, while allowing ordinary files beside a database.

Evidence retained privately:

- The exact original bytes fail on the preserved source and succeed on the candidate; the source
  file stays unchanged. Old/new image, PDF, CSV, custom and empty-file cases cover selection,
  distinct names, resend, immutable replay, private roots, links, non-regular files and races.
- 286 native checks, 85 Core file-consumer checks, 35 Telegram attachment checks and four host
  environment checks pass. Twelve existing artifact-preview HTML assertions fail identically on
  the preserved source; this repair does not claim that preview bank passes.
- The supported local compiler/start path loaded the frozen source and protected-root declaration.
  The verifier retained its signer isolation. Other separately owned native instances stayed alive.
- A real Telegram request recovered the original image and returned a checksum CSV. Core retained
  the original image hash; the photo opened in Telegram. The CSV downloaded through Telegram Web
  and matched Core byte for byte. One committed receipt covers the answer, photo and document;
  both attachments remain after reload.
- That live model used the existing managed temporary-folder path. The new outside-folder fallback
  has exact-file causal and canonical API/carrier proof; the live check proves the downstream real
  delivery path. These are distinct evidence claims.
- Opus reviewed the evidence and proposed contract. Independent source review found no remaining
  material issue after the isolation corrections. Models, prompts and user preferences were unchanged.

This result does not certify audio quality, latency, every provider or long-term endurance.


## 2026-10-26 scoped outbound recovery recheck

QA mode: **blast-radius**. This is a narrow `TGDOC-011` outbound consumer recheck, not a pass
for the full `TGDOC-010` worker/provider/restart matrix.

- The real local Telegram path accepted a request, continued the same durable worker after a
  correction, and sent three different generated images as three separate photos. Each opened in
  Telegram Web and the album survived reload. Stored files had distinct bytes and hashes; the
  outbound receipt contained one text message and three photos, with no retry.
- The investigation found a cold-session capacity refusal before Main admission and a separate
  long-response recovery defect: a stale-claim sweep could take a live Main claim, then retries
  changed native identity under the same idempotency key.
- The repair reuses the existing native queue, active claim, saved-result lookup and normal
  prepare/persist/file/delivery pipeline. It adds no model call or lookup to the first dispatch.
  Historical deadletters stay untouched. Queue and message continuations keep earlier results.
- Automated evidence: native capacity, exact result identity, owner/scope isolation, hold/Stop,
  lost-reply recovery, live-claim retention and the actual stream consumer. Replay preserves one
  file set, one speech-disposition range and usage without exposing reasoning.
- Final candidate activation and post-load Telegram checks: **PASS** for this scoped path.
  The reviewed native endpoint returned the original accepted result without execution. Core
  loaded the matching compiled candidate; a real Telegram follow-up received one saved reply.
  The delivered album remained available, and historical exhausted records were unchanged.
  Opus completed the causal reviews; its final reduced-delta run hit the account limit. A fresh
  independent reviewer closed the remaining file-binding finding; both owning Core banks and
  the native lookup bank passed.
- Raw conversations, IDs, hashes, screenshots and machine paths remain private. No Voice latency,
  endurance, all-provider or full cross-surface parity claim follows from this check.

## Historical report — 2026-04-16

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
