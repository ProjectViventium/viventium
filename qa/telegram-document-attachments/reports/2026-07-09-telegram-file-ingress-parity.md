# 2026-07-09 Telegram File Ingress Parity QA

## Status

PASS for the Telegram file-ingress contract tested in local runtime: grouped photos, grouped files,
captioned Office uploads, unsupported archives, audio uploads, and regular video uploads now produce
one aligned user-visible outcome instead of silence or split turns.

Important scope note: this pass proves routing/parity/fail-loud behavior. It does not claim every
file type is provider-native or extractable in this local stack. The tested PPTX, WAV, and MP4 paths
returned clear attachment-processing errors when extraction/provider upload was unavailable.

## Requirement Trace

- Feature: Telegram document and media attachments.
- Owning docs: `docs/requirements_and_learnings/01_Key_Principles.md` and
  `docs/requirements_and_learnings/03_Telegram_Bridge.md`.
- QA cases: `TGDOC-001` through `TGDOC-007`.
- Expected result: Telegram file messages either become one truthful file-backed user turn or fail
  visibly before an agent answers the caption alone.
- Forbidden result: no response, one response per album/file item, duplicate decorator downloads,
  caption-only answers for failed files, or voice/video-note STT handling for regular uploads.

## Runtime Under Test

- Local runtime checkout, helper checkout, and live stack owner were the current repo checkout.
- API, LibreChat web, and modern playground health probes returned HTTP 200 after restart.
- Telegram bot was restarted from the current checkout before live QA.
- Runtime logs and database checks were inspected with IDs, local paths, and private content omitted.

## Root Cause Confirmed

The original failure had two owning causes:

1. Telegram media groups arrived as multiple updates, but the bot did not buffer by `media_group_id`.
   Decorator-side heavy parsing also downloaded attachments before the owning handler, amplifying
   duplicate/split processing.
2. Telegram document handling used a narrow attachment filter, so captioned Office files could miss
   the file contract. Downstream upload/parser failures were not consistently returned as typed,
   user-visible attachment errors.

The aligned fix is structural: broad attachment ingress, lightweight auth identity extraction,
`media_group_id` coalescing, one LibreChat bridge turn per group, and typed 422 attachment-processing
errors from LibreChat back to Telegram. This matches the OpenClaw-style pattern of buffering grouped
Telegram media by `media_group_id` rather than deduping by filename/content or branching on prompt text.

## Automated Checks

| Check | Result |
| --- | --- |
| Telegram `py_compile` for bot/parser/decorator/bridge modules | PASS before and after cleanup |
| Focused Telegram attachment/media-group/bridge tests | PASS, 25 tests |
| Broader Telegram suite subset | PASS, 175 tests |
| Full Telegram suite | PASS, 323 tests after cleanup |
| LibreChat Telegram route Jest test | PASS, 34 tests after cleanup |
| Direct local Telegram route probe for unsupported archive | PASS, HTTP 422 with `attachmentProcessingError: true` |

## Live Telegram QA

All live UI tests used synthetic public-safe files through Telegram Desktop. No screenshots are stored
in this public report because the surrounding chat history is private.

| Use Case | Case | Visible Telegram Result | Supporting Evidence | Result |
| --- | --- | --- | --- | --- |
| Unsupported archive with caption | `TGDOC-004`, `TGDOC-UC-006` | One clear attachment-processing error; no caption-only answer | Bot sent one file to bridge; LibreChat logged typed 422 for unsupported archive | PASS |
| Two-image album with one caption | `TGDOC-005`, `TGDOC-UC-005` | One assistant reply described both images together | Bot log: coalesced media group with `messages=2 files=2`, then one `Bridge sending 2 file(s)` | PASS |
| Captioned synthetic PPTX | `TGDOC-003`, `TGDOC-UC-004` | One clear attachment-processing error that extraction was unavailable; no silence | Bot sent one PPTX to bridge; LibreChat logged typed 422 for extraction failure | PASS for ingress/fail-loud contract |
| Synthetic WAV upload | `TGDOC-007`, `TGDOC-UC-007` | One clear unsupported-file attachment error | Bot sent one file to bridge; voice gate logged `voice_note=0` and did not send TTS for the failed attachment | PASS |
| Synthetic MP4 regular video upload | `TGDOC-007`, `TGDOC-UC-007` | One clear unsupported-file attachment error | Bot sent one file to bridge; voice gate logged `voice_note=0` and did not treat it as video-note STT | PASS |
| Two grouped text/markdown files with one caption | `TGDOC-005`, `TGDOC-UC-005` | One assistant reply named both files in one turn | Bot log: coalesced media group with `messages=2 files=2`, then one `Bridge sending 2 file(s)` | PASS |

## State And Logs

- Before the restart, logs showed the reported failure shape: grouped photos were forwarded as
  separate `Bridge sending 1 file(s)` calls.
- After the restart, synthetic grouped photos and grouped files each produced one coalesced
  `messages=2 files=2` log entry and one `Bridge sending 2 file(s)` call.
- Unsupported ZIP, PPTX extraction failure, WAV, and MP4 each produced one Telegram-visible error
  after a typed 422 route response.
- Database summary after live QA showed recent conversation/message records and Telegram ingress
  records, with zero recent voice-ingress records for the regular audio/video file tests.
- After the final source cleanup, the local runtime was restarted from the current checkout and API,
  LibreChat web, and modern playground probes returned HTTP 200. The Telegram bot log showed polling
  restarted and the application started.

## ClaudeViv Review

- The first structured ClaudeViv JSON review attempt completed with a schema-output failure and was
  not used as evidence.
- A shorter review-only ClaudeViv fallback completed. It agreed the implementation is structurally
  aligned and surgical: media groups are keyed by `media_group_id`, auth uses lightweight identity
  extraction, regular audio/video remain file uploads, and typed 422 errors avoid silent/caption-only
  turns.
- Claude flagged a real cleanup issue: an older shadowed Telegram attachment-filter block could
  mislead future edits. That dead block was removed.
- Claude also suggested adding a media-group regression test. Codex verified the regression already
  exists as `tests/test_bot_stream_preview.py::test_media_group_coalesces_files_into_one_viventium_call`;
  that test and the full Telegram suite passed after cleanup.

## Residual Risks

- This local stack still returns clear errors for PPTX extraction, WAV, and MP4 when the configured
  upload/parser path cannot process them. That is acceptable for the Telegram parity contract, but
  it is not full provider-native support for every file type.
- The live grouped-file tests covered two photos and two document files. Larger albums, mixed media
  groups, and slow Telegram delivery are covered by the coalescing design and automated regression,
  but should be included in a future release-scale soak if file throughput becomes a release focus.
- Provider/auth issues outside this file-ingress layer can still affect the intelligence of an
  eventual answer. They do not invalidate the attachment routing/fail-loud result.

## Public-Safety Review

This report intentionally omits raw Telegram IDs, chat text, screenshots, tokens, local App Support
paths, Mongo IDs, and private filenames. Evidence is summarized as synthetic filenames, timestamps,
counts, and pass/fail outcomes.
