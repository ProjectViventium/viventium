# Telegram Document Attachments QA Cases

## Case ID Convention

Use stable `TGDOC-NNN` IDs for telegram document attachments cases.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `TGDOC-001` | Telegram document uploads become usable attachments or honest failures with no private raw evidence in public reports. | User-visible behavior matches source, docs, persisted state, and logs | Telegram send/receive, attachment storage, model-visible file context | `tests/release/test_telegram_codex_runtime_paths.py` plus user-grade QA when visible | NOT YET RUN (cataloged 2026-05-17; next feature run required) |
| `TGDOC-002` | Public QA evidence is sanitized and reproducible | A PR reviewer can verify the behavior without private/local data | QA report, git diff, logs summary, generated artifacts | Public-safety scan plus relevant release tests | NOT YET RUN (cataloged 2026-05-17; next feature run required) |
| `TGDOC-003` | Captioned Office/OpenDocument uploads must enter the shared Telegram attachment contract. | Sending a presentation, spreadsheet, or document never results in silence; it becomes readable/provider-native context or an explicit attachment-processing error. | Telegram document upload, LibreChat Telegram route, document parser/provider upload | `tests/test_telegram_file_upload.py`, `tests/test_voice_preferences.py::test_get_message_returns_attachment_capture_errors`, LibreChat `telegram.spec.js` | AUTOMATED PASS 2026-07-09; real Telegram QA required for release signoff |
| `TGDOC-004` | Unsupported binary/archive files must fail visibly rather than becoming inert attachments. | User receives one clear Telegram error and no caption-only assistant turn is submitted. | Telegram document upload, LibreChat attachment upload failure, Python bridge error text | `tests/test_librechat_bridge.py::test_start_chat_error_message_surfaces_attachment_processing_reason`, LibreChat `telegram.spec.js` | AUTOMATED PASS 2026-07-09; real Telegram QA required for release signoff |
| `TGDOC-005` | Telegram grouped media/files are one user turn. | An album/grouped message is coalesced and forwarded once with all files in Telegram order, using the caption-bearing item as primary. | Telegram media group, bot handler, LibreChat bridge call | `tests/test_bot_stream_preview.py::test_media_group_coalesces_files_into_one_viventium_call` | AUTOMATED PASS 2026-07-09; real Telegram QA required for release signoff |
| `TGDOC-006` | Authorization/API-key decorators must not download, parse, or transcribe attachments. | Each Telegram attachment is captured once by the real handler, avoiding duplicate downloads and split album turns. | Telegram auth decorators, bot logs, media download path | Source inspection plus full Telegram pytest suite | AUTOMATED PASS 2026-07-09; real Telegram log correlation required for release signoff |
| `TGDOC-007` | Audio and regular video uploads are attachments; voice notes and video notes are STT inputs. | Uploaded audio/video files do not produce empty turns or accidental transcription errors; they follow the file contract. | Telegram audio/video upload, bot parser, LibreChat bridge call | `tests/test_bot_stream_preview.py::test_telegram_attachment_filters_accept_broad_documents_and_audio`, `tests/test_voice_preferences.py::test_get_message_treats_regular_video_as_file_attachment` | AUTOMATED PASS 2026-07-09; real Telegram QA required for release signoff |

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
- Last run: NOT YET RUN (cataloged 2026-05-17; not a substitute for the next real feature run).

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
- Last run: NOT YET RUN (cataloged 2026-05-17; run on each new public report).

## `TGDOC-003` - Captioned Office/OpenDocument Uploads

- Requirement: Office/OpenDocument files sent through Telegram must be handled by the same
  provider-native/context-extraction/fail-loud contract as web uploads.
- Risk covered: a captioned `.pptx`, `.docx`, `.xlsx`, `.odp`, `.odt`, or `.ods` update bypasses
  handlers and receives no response.
- Preconditions: local Telegram bridge is running against the changed checkout with a linked
  synthetic QA account.
- Steps:
  1. Send a small synthetic presentation with a short caption through Telegram.
  2. Verify the Telegram user receives either a content-aware answer or one clear
     attachment-processing error.
  3. Verify logs show one attachment capture and one LibreChat Telegram turn.
- Expected result: no silent turn and no caption-only answer when the file cannot be processed.
- Forbidden result: no response, generic transport-only error for a parser failure, or file ignored
  while the caption is answered alone.
- Evidence to capture: public-safe timestamp, visible Telegram result summary, sanitized log counts,
  and automated test output.
- Automation: `tests/test_telegram_file_upload.py`,
  `tests/test_voice_preferences.py::test_get_message_returns_attachment_capture_errors`, LibreChat
  `telegram.spec.js`.
- Last run: AUTOMATED PASS 2026-07-09; real Telegram QA pending in this run.

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
- Last run: AUTOMATED PASS 2026-07-09; real Telegram QA pending in this run.

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
- Last run: AUTOMATED PASS 2026-07-09; real Telegram QA pending in this run.

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
- Last run: AUTOMATED PASS 2026-07-09; real Telegram log correlation pending in this run.

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
- Last run: AUTOMATED PASS 2026-07-09; real Telegram QA pending in this run.

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Telegram Document Attachments. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `TGDOC-UC-001` | On Telegram send/receive, attachment storage, model-visible file context, verify that telegram document uploads become usable attachments or honest failures with no private raw evidence in public reports. | owning requirement for `TGDOC-001` / `TGDOC-001` | Telegram send/receive, attachment storage, model-visible file context | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to TGDOC-001. | User-visible behavior matches source, docs, persisted state, and logs | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
| `TGDOC-UC-002` | On QA report, git diff, logs summary, generated artifacts, create or review the public QA evidence record with setup/auth/config, empty-state, degraded-dependency, and privacy checks. | owning requirement for `TGDOC-002` / `TGDOC-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to TGDOC-002. | The user sees an honest setup, retry, or degraded-state result for TGDOC-002; no fake success is accepted. | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
| `TGDOC-UC-003` | After creating the public QA evidence record, rerun the scan after any retry, report update, or linked artifact change. | owning requirement for `TGDOC-002` / `TGDOC-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to TGDOC-002. | TGDOC-002 remains correct after the persistence or parity step and final wording matches evidence. | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
| `TGDOC-UC-004` | Send a captioned synthetic Office presentation in Telegram. | `03_Telegram_Bridge.md` Telegram Attachments / `TGDOC-003` | Telegram desktop/mobile bot chat | Source, bot logs, LibreChat route logs, DB/state, and automated tests. | Content-aware answer or one clear attachment-processing error; never no response. | AUTOMATED PASS 2026-07-09; real Telegram QA pending |
| `TGDOC-UC-005` | Send a grouped Telegram album/file set with one caption. | `03_Telegram_Bridge.md` Telegram Attachments / `TGDOC-005` | Telegram desktop/mobile bot chat | Coalescing log count, one LibreChat bridge call, stored assistant turn, automated test. | One assistant response for the group with all files forwarded in order. | AUTOMATED PASS 2026-07-09; real Telegram QA pending |
| `TGDOC-UC-006` | Send an unsupported synthetic archive with a caption. | `03_Telegram_Bridge.md` Telegram Attachments / `TGDOC-004` | Telegram desktop/mobile bot chat | LibreChat 422 route response, Python bridge error text, no generated caption-only answer. | One clear failure message and no silent turn. | AUTOMATED PASS 2026-07-09; real Telegram QA pending |
| `TGDOC-UC-007` | Send synthetic audio and regular video file uploads. | `03_Telegram_Bridge.md` Telegram Attachments / `TGDOC-007` | Telegram desktop/mobile bot chat | Bot handler selection, file capture logs, automated parser/filter tests. | Files follow attachment contract; only voice-note/video-note inputs use STT. | AUTOMATED PASS 2026-07-09; real Telegram QA pending |
