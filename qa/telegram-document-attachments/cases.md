# Telegram Document Attachments QA Cases

Installed Worker file-parity contract: `tests/release/test_telegram_worker_file_parity_qa.py`.

## Case ID Convention

Use stable `TGDOC-NNN` IDs for telegram document attachments cases.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `TGDOC-001` | Telegram document uploads become usable attachments or honest failures with no private raw evidence in public reports. | User-visible behavior matches source, docs, persisted state, and logs | Telegram send/receive, attachment storage, model-visible file context | `tests/release/test_telegram_codex_runtime_paths.py` plus user-grade QA when visible | PASS 2026-07-09; see `reports/2026-07-09-telegram-file-ingress-parity.md` |
| `TGDOC-002` | Public QA evidence is sanitized and reproducible | A PR reviewer can verify the behavior without private/local data | QA report, git diff, logs summary, generated artifacts | Public-safety scan plus relevant release tests | PASS 2026-07-09; see `reports/2026-07-09-telegram-file-ingress-parity.md` |
| `TGDOC-003` | Captioned Office/OpenDocument uploads must enter the shared Telegram attachment contract. | Sending a presentation, spreadsheet, or document never results in silence; PPTX slide text, speaker notes, and supported embedded images become agent-visible context/vision inputs, while unsupported leftovers fail truthfully. | Telegram document upload, LibreChat Telegram route, document parser/provider upload | `tests/test_telegram_file_upload.py`, `tests/test_voice_preferences.py::test_get_message_returns_attachment_capture_errors`, LibreChat `telegram.spec.js`, LibreChat `gateway.spec.js`, LibreChat file parser/process tests | PASS 2026-07-09; see `reports/2026-07-09-pptx-text-notes-vision-qa.md` |
| `TGDOC-004` | Unsupported binary/archive files must fail visibly rather than becoming inert attachments. | User receives one clear Telegram error and no caption-only assistant turn is submitted. | Telegram document upload, LibreChat attachment upload failure, Python bridge error text | `tests/test_librechat_bridge.py::test_start_chat_error_message_surfaces_attachment_processing_reason`, LibreChat `telegram.spec.js` | PASS 2026-07-09; synthetic ZIP produced visible typed error |
| `TGDOC-005` | Telegram grouped media/files are one user turn. | An album/grouped message is coalesced and forwarded once with all files in Telegram order, using the caption-bearing item as primary. | Telegram media group, bot handler, LibreChat bridge call | `tests/test_bot_stream_preview.py::test_media_group_coalesces_files_into_one_viventium_call` | PASS 2026-07-09; synthetic album and two-file group each bridged once with two files |
| `TGDOC-006` | Authorization/API-key decorators must not download, parse, or transcribe attachments. | Each Telegram attachment is captured once by the real handler, avoiding duplicate downloads and split album turns. | Telegram auth decorators, bot logs, media download path | Source inspection plus full Telegram pytest suite | PASS 2026-07-09; post-restart grouped logs show one coalesced handler bridge call |
| `TGDOC-007` | Audio and regular video uploads are attachments; voice notes and video notes are STT inputs. | Uploaded audio/video files do not produce empty turns or accidental transcription errors; they follow the file contract. | Telegram audio/video upload, bot parser, LibreChat bridge call | `tests/test_bot_stream_preview.py::test_telegram_attachment_filters_accept_broad_documents_and_audio`, `tests/test_voice_preferences.py::test_get_message_treats_regular_video_as_file_attachment` | PASS 2026-07-09; synthetic WAV/MP4 produced file-contract errors and zero voice-ingress records |
| `TGDOC-008` | Telegram photos must reach the configured model or worker as exact owner-scoped bytes. | A single photo and a same-name album are readable without OCR/parser configuration, placeholders, or dropped files. | Telegram Desktop, LibreChat upload, GlassHive upload projection, provider workspace | LibreChat process/route tests plus GlassHive projection/materialization tests | PASS 2026-08-21; one post-restart uncaptioned photo and one three-photo album produced content-aware answers on the installed runtime |
| `TGDOC-009` | One logical attachment turn must produce one visible assistant result. | The user gets one answer bubble even when Main and a background cortex both complete. | Telegram delivery, Mongo presentation, cortex follow-up | `BackgroundCortexFollowUpService.spec.js` and affected Telegram/Core suites | PASS 2026-08-21; final album produced one assistant row and one Telegram bubble |
| `TGDOC-010` | Delegating a file/media task to a Worker Bee must preserve the complete supported input and output contract. | Every supported attachment family reaches the intended Bee with exact owner scope, identity, bytes, and order; generated files/media return once with a usable open/download action through Telegram or linked Active Work. | Telegram Desktop, LibreChat upload, GlassHive workspace, linked Web/Active Work, artifact delivery | Existing upload/projection/materialization suites plus Parallel Work artifact/delivery contracts; real installed matrix required | NOT RUN — cataloged 2026-08-24; narrower photo ingress and one-result delivery passes are supporting evidence only |

## `TGDOC-001` - Core User Flow

- Requirement: Telegram document uploads become usable attachments or honest failures with no private raw evidence in public reports.
- Risk covered: implementation, docs, and user-visible behavior drift apart.
- Preconditions: local Viventium runtime or the specific feature harness is available with synthetic, public-safe data.
- Steps:
  1. Exercise the feature through the real user surface, not only a unit test.
  2. Compare the visible result with source code, generated/runtime config, logs, persisted state, and the owning requirement doc.
  3. Capture a public-safe report with expected result, forbidden result, evidence, residual risk, and follow-up.
- Expected result: the feature behaves as documented and every supporting layer agrees.
- Forbidden result: backend logs, mocks, source inspection, or model completions are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, generated/runtime state summary, and docs/case links.
- Automation: `tests/release/test_telegram_codex_runtime_paths.py` plus any narrower feature tests discovered during implementation.
- Last run: PASS 2026-07-09; see `reports/2026-07-09-telegram-file-ingress-parity.md`.

## `TGDOC-002` - Public-Safe Evidence Record

- Requirement: public QA artifacts must be reproducible and free of secrets, personal data, local paths, raw IDs, and private screenshots.
- Risk covered: a useful local QA run cannot be safely reviewed or published.
- Preconditions: a dated QA report is created for this feature.
- Steps:
  1. Review the report and related diffs for local absolute paths, account identifiers, tokens, raw logs, raw DB rows, private chats, and screenshots with private content.
  2. Keep raw/private evidence outside the public repo and summarize only public-safe counts, statuses, hashes, and conclusions.
  3. Link the report back to this case and the owning requirement doc.
- Expected result: the public report proves the behavior without leaking private/local data.
- Forbidden result: a report includes private transcripts, account identifiers, raw runtime dumps, local home paths, tokens, or secret-bearing command lines.
- Evidence to capture: public-safety scan result and link to the sanitized report.
- Automation: public-safety pattern scan plus relevant release tests.
- Last run: PASS 2026-07-09; see `reports/2026-07-09-telegram-file-ingress-parity.md`.

## `TGDOC-003` - Captioned Office/OpenDocument Uploads

- Requirement: Office/OpenDocument files sent through Telegram must be handled by the same
  provider-native/context-extraction/vision/fail-loud contract as web uploads and gateway uploads.
- Risk covered: a captioned `.pptx`, `.docx`, `.xlsx`, `.odp`, `.odt`, or `.ods` update bypasses
  handlers and receives no response.
- Preconditions: local Telegram bridge is running against the changed checkout with a linked
  synthetic QA account.
- Steps:
  1. Send a small text-bearing synthetic presentation with a short caption through Telegram.
  2. Send a mixed presentation with readable slide text, speaker notes, and embedded image media.
  3. Verify the Telegram user receives either a content-aware answer or one clear
     attachment-processing error.
  4. Verify logs show one attachment capture and one LibreChat Telegram turn.
- Expected result: PPTX produces a content-aware answer grounded in slide text and speaker notes,
  and supported embedded images are available as model vision inputs. Unsupported or non-extractable
  files produce one truthful attachment-processing error.
- Forbidden result: no response, generic transport-only error for a parser failure, file ignored
  while the caption is answered alone, or an image/OCR error when the real blocker is an unsupported
  parser path.
- Safety regression: a synthetic presentation advertising an XML member larger than the extraction
  limit must fail before decompression/model submission with one truthful attachment-processing
  error; it must not exhaust memory or submit the caption alone.
- Evidence to capture: public-safe timestamp, visible Telegram result summary, sanitized log counts,
  and automated test output.
- Automation: `tests/test_telegram_file_upload.py`,
  `tests/test_voice_preferences.py::test_get_message_returns_attachment_capture_errors`, LibreChat
  `telegram.spec.js`, LibreChat `gateway.spec.js`,
  `packages/api/src/files/documents/crud.spec.ts`, LibreChat
  `api/server/services/Files/process.spec.js`.
- Last run: PASS 2026-07-09 for automated PPTX parser/process/route regressions and live Telegram
  mixed PPTX QA. See `reports/2026-07-09-pptx-text-notes-vision-qa.md`.

## `TGDOC-004` - Unsupported File Fails Clearly

- Requirement: unsupported binary/archive files must fail before the agent run with a visible
  Telegram error.
- Risk covered: unsupported files become inert attachments or produce a generic local API/server
  error.
- Preconditions: local Telegram bridge and LibreChat API are running.
- Steps:
  1. Send a synthetic unsupported archive with a short caption.
  2. Verify the Telegram user receives one clear attachment-processing error.
  3. Verify no assistant answer is generated from the caption alone.
- Expected result: one clear failure message; no silent turn.
- Forbidden result: generic HTTP/server error, no response, or caption-only agent answer.
- Evidence to capture: visible Telegram result summary, sanitized logs, and route/bridge test output.
- Automation: `tests/test_librechat_bridge.py::test_start_chat_error_message_surfaces_attachment_processing_reason`,
  LibreChat `telegram.spec.js`.
- Last run: PASS 2026-07-09; synthetic Telegram ZIP produced one clear typed error. See
  `reports/2026-07-09-telegram-file-ingress-parity.md`.

## `TGDOC-005` - Grouped Media/File Coalescing

- Requirement: Telegram albums/media groups are one user message and must be forwarded to LibreChat
  once with all files.
- Risk covered: each grouped photo/file is processed as a separate bot turn, causing repeated or
  context-fragmented replies.
- Preconditions: local Telegram bridge is running; synthetic grouped photos/files are available.
- Steps:
  1. Send a Telegram media group with multiple files/photos and a caption on one item.
  2. Verify Telegram receives one assistant response.
  3. Verify logs show one coalesced media-group bridge call with the expected file count.
- Expected result: one LibreChat turn, all files included in Telegram order, caption-bearing message
  selected as primary.
- Forbidden result: one assistant response per album item, duplicate downloads from auth decorators,
  or content-hash/filename dedupe that drops intentional repeats.
- Evidence to capture: visible Telegram result summary, sanitized coalescing log count, and
  automated regression output.
- Automation: `tests/test_bot_stream_preview.py::test_media_group_coalesces_files_into_one_viventium_call`.
- Last run: PASS 2026-08-21; a three-photo same-name album produced one coalesced turn, all
  three ordered worker files, and one answer. See
  `reports/2026-08-21-telegram-photo-worker-handoff.md`.

## `TGDOC-006` - Lightweight Auth Before Attachment Capture

- Requirement: authorization and API-key checks must derive chat/conversation identity without
  downloading, transcribing, or parsing attachments.
- Risk covered: decorator-side parsing duplicates file downloads and splits album processing before
  the owning handler can coalesce files.
- Preconditions: local Telegram bridge with attachment logging enabled enough to count captures
  without exposing message content.
- Steps:
  1. Send a synthetic grouped file/photo upload.
  2. Verify each attachment is captured once by the handler path.
  3. Verify no auth decorator log path performs media download or STT.
- Expected result: one capture per real attachment and one bridge call for the media group.
- Forbidden result: repeated capture/download attempts before the handler or decorator-triggered STT.
- Evidence to capture: sanitized log counts and source/test evidence for `get_update_ids`.
- Automation: full Telegram pytest suite plus source inspection.
- Last run: PASS 2026-07-09; post-restart grouped Telegram logs show one coalesced handler bridge
  call and no decorator-side duplicate bridge calls. See
  `reports/2026-07-09-telegram-file-ingress-parity.md`.

## `TGDOC-007` - Audio And Regular Video As Attachments

- Requirement: Telegram audio uploads and regular video uploads follow the file contract; voice
  notes and video notes remain STT inputs.
- Risk covered: audio/video files produce empty turns, accidental transcription errors, or bypass
  the attachment handlers.
- Preconditions: local Telegram bridge is running.
- Steps:
  1. Send a synthetic audio file upload.
  2. Send a synthetic regular video file upload.
  3. Verify each receives either a content-aware response or a clear processing error.
- Expected result: audio/video files are passed as attachments; only voice-note affordances trigger
  transcription.
- Forbidden result: ignored audio, regular video treated as a voice note, or no response.
- Evidence to capture: visible Telegram result summary, sanitized logs, and automated regression
  output.
- Automation: `tests/test_bot_stream_preview.py::test_telegram_attachment_filters_accept_broad_documents_and_audio`,
  `tests/test_voice_preferences.py::test_get_message_treats_regular_video_as_file_attachment`.
- Last run: PASS 2026-07-09; synthetic Telegram WAV and MP4 followed the attachment contract and
  did not create voice-ingress records. See `reports/2026-07-09-telegram-file-ingress-parity.md`.

## `TGDOC-008` - Exact Photo Bytes Reach The Worker

- Requirement: a trusted Telegram image is valid visual input, not a text document that must pass a
  document parser.
- Risk covered: JPEG/PNG uploads fail with an unsupported-parser error, become placeholders, or map
  repeated `photo.jpg` names to the wrong bytes.
- Preconditions: installed local runtime, synthetic non-personal images, and a Telegram chat linked
  to the configured Main agent.
- Steps:
  1. Send one synthetic photo without a caption.
  2. Send three distinct synthetic photos as one album, with the same Telegram transport filename.
  3. Ask for exact visible facts from each image in order.
  4. Compare the visible answer with the upload rows, ordered upload projection, worker bundle,
     materialized files, provider request, and persisted turn.
- Expected result: the single image and all three album images are readable; album order is stable;
  each durable file ID resolves to its own owner-scoped bytes; the worker receives real files.
- Forbidden result: document-parser JPEG error, placeholder-only worker input, newest-file aliasing,
  filename dedupe, cross-owner lookup, or a claim that missing bytes were read.
- Evidence to capture: visible Telegram result, file count/order/byte hashes, one provider request,
  worker materialization, and Mongo turn counts.
- Automation: LibreChat Telegram upload/route tests, GlassHive upload projection tests, and host
  conversation materialization tests.
- Last run: PASS 2026-08-21. The post-restart blank-caption rerun also exercised a classified
  quota recovery and still delivered one correct answer. See
  `reports/2026-08-21-telegram-photo-worker-handoff.md`.

## `TGDOC-009` - One Attachment Turn, One Visible Answer

- Requirement: one completed logical attachment turn must be presented once.
- Risk covered: Main answers correctly, then a background cortex emits the same answer again with
  punctuation or spacing changes.
- Steps:
  1. Complete a natural multi-photo request through Telegram.
  2. Wait through the background follow-up window.
  3. Inspect Telegram, Mongo, delivery receipts, and follow-up decision logs.
- Expected result: one assistant row and one Telegram bubble contain the complete answer; an exact
  canonical duplicate is suppressed before persistence and delivery.
- Forbidden result: two bubbles for the same answer, Telegram-side filtering, or semantic suppression
  of a genuinely additive follow-up.
- Automation: `BackgroundCortexFollowUpService.spec.js`, including punctuation/whitespace-only
  duplicate suppression and distinct-result preservation.
- Last run: PASS 2026-08-21. See
  `reports/2026-08-21-telegram-photo-worker-handoff.md`.

## `TGDOC-010` - Worker Bee File Input And Output Parity

- Requirement: `01_Key_Principles.md` full capability parity and
  `55_Parallel_Work_Orchestration.md` Worker Bee input/output parity.
- Risk covered: delegation silently drops or alters an upload, gives the worker a placeholder or
  wrong same-name file, supports ingestion but not generated-file delivery, or works only on the
  primary provider before fallback/control/restart.
- Preconditions: installed current candidate; synthetic public-safe fixtures for every supported
  attachment family; Parallel Work enabled only through the local QA gate; one output-producing
  mission; headed linked Web/Active Work surface.
- Steps:
  1. Send representative single and grouped documents, images, audio, video, and prior artifacts
     through Telegram, including distinct same-name files and one captioned group.
  2. Explicitly delegate the exact file task to one Worker Bee and inspect its owner-scoped upload
     projection and materialized workspace.
  3. Message or Steer the same Bee, exercise provider fallback and runtime restart, and require it
     to generate a synthetic file or media artifact.
  4. Verify Telegram presents one Queen-authored completion and one usable artifact delivery; open
     the same result from linked chat or Active Work and compare identity/hash.
  5. Repeat missing parser, missing bytes, expired link, unavailable delivery, and cross-owner
     attempts, then recover the same mission where recovery is supported.
- Expected result: each supported input retains exact identity, bytes, order, caption grouping, and
  owner scope; unsupported input fails once and truthfully before caption-only work. The intended
  Bee alone can read the files. Its generated output is delivered once, opens successfully, and
  remains the same artifact through control, fallback, restart, and cross-surface viewing.
- Forbidden result: dropped/reordered/aliased files, caption-only execution after failed ingestion,
  parser fiction, placeholder-only worker input, cross-owner access, fallback without a required
  file ability, output described but not attached, dead/expired link reported as delivered,
  duplicate assistant bubbles, duplicate artifacts, or lost work after restart.
- Evidence to capture: visible Telegram and linked-Web outcomes; upload IDs and sanitized hashes;
  group order; worker projection/materialization; provider/tool receipt; action and attempt rows;
  output artifact ledger/hash; delivery receipt; opened result; restart/fallback correlation; and
  public-safe report.
- Automation: Telegram upload/parser/album tests, LibreChat upload/route tests, GlassHive
  projection/materialization tests, and Parallel Work artifact/delivery tests. Automation supports
  but does not replace the real installed matrix.
- Installed PRE-GATE only: `qa/telegram-document-attachments/scripts/run_tgdoc_010_installed_journey.cjs --local-qa --allow-telegram-mutation --allow-runtime-restart --scenario=<private-0600> --evidence-root=<private-0700>` requires a parent-injected authenticated Computer `@oai/sky` bridge plus separate diagnostic, desktop, Telegram, local JWT, and restart consent; standalone execution blocks.
- Last run: NOT RUN — cataloged 2026-08-24. `TGDOC-003`, `TGDOC-005`, `TGDOC-008`, and `TGDOC-009` prove narrower
  ingress/grouping/photo/one-result behavior only.

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Telegram Document Attachments. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `TGDOC-UC-001` | On Telegram send/receive, attachment storage, model-visible file context, verify that telegram document uploads become usable attachments or honest failures with no private raw evidence in public reports. | owning requirement for `TGDOC-001` / `TGDOC-001` | Telegram send/receive, attachment storage, model-visible file context | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to TGDOC-001. | User-visible behavior matches source, docs, persisted state, and logs | PASS 2026-07-09; report saved |
| `TGDOC-UC-002` | On QA report, git diff, logs summary, generated artifacts, create or review the public QA evidence record with setup/auth/config, empty-state, degraded-dependency, and privacy checks. | owning requirement for `TGDOC-002` / `TGDOC-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to TGDOC-002. | The user sees an honest setup, retry, or degraded-state result for TGDOC-002; no fake success is accepted. | PASS 2026-07-09; public-safe report saved |
| `TGDOC-UC-003` | After creating the public QA evidence record, rerun the scan after any retry, report update, or linked artifact change. | owning requirement for `TGDOC-002` / `TGDOC-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to TGDOC-002. | TGDOC-002 remains correct after the persistence or parity step and final wording matches evidence. | PASS 2026-07-09; public-safety scan passed |
| `TGDOC-UC-004` | Send a captioned Office presentation with slide text, speaker notes, and embedded images in Telegram. | `03_Telegram_Bridge.md` Telegram Attachments / `TGDOC-003` | Telegram desktop/mobile bot chat | Source, bot logs, LibreChat route logs, DB/state, and automated tests. | Content-aware answer grounded in slide text/notes, with supported embedded images available through vision; unsupported leftovers get one truthful error; never no response. | PASS 2026-07-09; mixed PPTX live Telegram QA and automated parser/process/route tests passed |
| `TGDOC-UC-005` | Send a grouped Telegram album/file set with one caption. | `03_Telegram_Bridge.md` Telegram Attachments / `TGDOC-005` | Telegram desktop/mobile bot chat | Coalescing log count, one LibreChat bridge call, stored assistant turn, automated test. | One assistant response for the group with all files forwarded in order. | PASS 2026-07-09; album and grouped docs coalesced |
| `TGDOC-UC-006` | Send an unsupported synthetic archive with a caption. | `03_Telegram_Bridge.md` Telegram Attachments / `TGDOC-004` | Telegram desktop/mobile bot chat | LibreChat 422 route response, Python bridge error text, no generated caption-only answer. | One clear failure message and no silent turn. | PASS 2026-07-09; synthetic ZIP fail-loud |
| `TGDOC-UC-007` | Send synthetic audio and regular video file uploads. | `03_Telegram_Bridge.md` Telegram Attachments / `TGDOC-007` | Telegram desktop/mobile bot chat | Bot handler selection, file capture logs, automated parser/filter tests. | Files follow attachment contract; only voice-note/video-note inputs use STT. | PASS 2026-07-09; WAV/MP4 file-contract errors and no voice ingress |
| `TGDOC-UC-008` | Send one photo without a caption, then send three different photos as one album and ask about every image. | `03_Telegram_Bridge.md` Telegram Attachments / `TGDOC-008` | Telegram Desktop and configured GlassHive-backed Main | Visible reply, upload rows, ordered file IDs, worker bundle/files, provider run, Mongo | Every exact image is readable in order; no parser error, placeholder, alias, or dropped attachment. | PASS 2026-08-21; post-restart single-photo and installed-runtime three-photo album passed |
| `TGDOC-UC-009` | Wait after the album answer and confirm no duplicate result appears. | `03_Telegram_Bridge.md` Telegram Attachments / `TGDOC-009` | Telegram Desktop, follow-up cortex, delivery store | Visible bubble count, assistant-row count, follow-up decision, delivery acknowledgement | One logical result is shown once; a distinct additive follow-up remains allowed. | PASS 2026-08-21; one assistant row and one bubble after the full follow-up window |
| `TGDOC-UC-010` | Send the supported synthetic file/media matrix, delegate it to one Bee, guide that Bee, restart/fallback, and open its generated file from Telegram and linked Active Work. | `01_Key_Principles.md`, `55_Parallel_Work_Orchestration.md` / `TGDOC-010`, `PWK-011`, `PWK-UC-019` | Installed Telegram Desktop, GlassHive worker, linked Web/Active Work, artifact viewer | Exact upload IDs/hashes/order, worker files, control/fallback/restart receipts, output hash, one delivery receipt, opened artifact | Exact authorized inputs reach only the intended Bee; one correct output returns once and opens on both surfaces; every unsupported or unavailable class is truthful and recoverable where supported. | NOT RUN — cataloged 2026-08-24; existing narrower attachment passes do not close Worker input/output parity |
