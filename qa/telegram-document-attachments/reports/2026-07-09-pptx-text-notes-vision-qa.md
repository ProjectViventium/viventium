# 2026-07-09 PPTX Text, Notes, And Vision QA
<!-- qa-evidence-exempt: Historical local QA format retained without retroactively inventing evidence; current release acceptance is recorded separately. -->

## Status

PASS for Telegram PPTX handling in local runtime.

The local Telegram bridge now processes a mixed presentation as one file-backed user turn. Slide
text, speaker notes, and supported embedded image media reached the active agent; the user-visible
Telegram reply identified the expected slide/notes/image counts and recognized a known visual marker
from the first embedded photo-like image. The report stores counts and outcomes only; it does not
store the private deck, screenshots, raw chat content, account IDs, or local file paths.

## Requirement Trace

- Feature: Telegram document attachments and shared message-file parity.
- Owning docs: `docs/requirements_and_learnings/01_Key_Principles.md` and
  `docs/requirements_and_learnings/03_Telegram_Bridge.md`.
- QA case: `TGDOC-003` / `TGDOC-UC-004`.
- Expected result: PPTX uploads produce a content-aware answer grounded in slide text, speaker
  notes, and supported embedded images, or fail once with a truthful attachment-processing error.
- Forbidden result: no response, caption-only answer, one response per grouped item, bogus
  image-only/OCR error for a parser capability miss, or provider connection failure caused by an
  oversized extracted-image payload.

## Runtime Under Test

- Local prod runtime was activated from the current checkout after the code changes.
- API, LibreChat web, and modern playground health probes returned HTTP 200 after restart.
- Playwright opened the local LibreChat web surface and reached the Viventium login page with no
  console errors.
- The Telegram bot process used the same active checkout and sent the PPTX through the real
  Telegram-to-LibreChat bridge.

## Root Cause Confirmed

The original PPTX failure was upstream of model intelligence. The file bytes and visual assets were
not being delivered through a useful shared file contract:

1. PPTX was not included in the shared document-parser MIME matcher, so a valid Office presentation
   could fail before the model saw any slide content.
2. After text extraction was added, slide text and speaker notes reached the agent, but embedded
   images were still only described as unavailable visual content.
3. A first raw embedded-image injection path proved the vision route but exceeded practical provider
   payload size for a visual-heavy deck. The final fix resizes extracted document images before
   injecting them as ordinary image message parts.

## Implementation Truth

- Shared document parser now handles `.pptx` files and extracts slide text plus speaker notes.
- Supported embedded images under `ppt/media/` are extracted as image data URLs with bounded count
  and byte budgets.
- Telegram and the generic Viventium gateway preserve those extracted images and inject them through
  the same vision message-part contract used for normal image uploads.
- Extracted document images are resized before model injection so a visual deck does not create a
  multi-megabyte base64 prompt frame.
- Unsupported or non-extractable files still fail before caption-only submission with a clear
  attachment-processing error.

## Automated Checks

| Check | Result |
| --- | --- |
| `npm --workspace packages/api exec -- jest src/files/documents/crud.spec.ts --runInBand` | PASS, 17 tests |
| `npm --workspace packages/data-provider exec -- jest src/file-config.spec.ts --runInBand` | PASS, 95 tests |
| `npm --workspace api exec -- jest server/services/Files/process.spec.js --runInBand` | PASS, 33 tests |
| `npm --workspace api exec -- jest server/routes/viventium/__tests__/telegram.spec.js --runInBand` | PASS, 35 tests |
| `npm --workspace api exec -- jest server/routes/viventium/__tests__/gateway.spec.js --runInBand` | PASS, 14 tests |
| `npm --workspace packages/data-provider run build` | PASS |
| `npm --workspace packages/api run build` | PASS with existing non-fatal TypeScript resolution warnings |
| `uv run --project TelegramVivBot pytest tests/test_telegram_file_upload.py tests/test_bot_stream_preview.py::test_media_group_coalesces_files_into_one_viventium_call tests/test_voice_preferences.py::test_get_message_returns_attachment_capture_errors tests/test_voice_preferences.py::test_get_message_treats_regular_video_as_file_attachment -q` | PASS, 21 tests |
| `uv run --project TelegramVivBot pytest -q` | PASS, 323 tests |

## Direct Artifact Smoke

- A synthetic PPTX fixture with slide text and speaker notes extracted the expected text.
- A synthetic PPTX fixture with embedded PNG media returned extracted image data URLs.
- The private mixed QA presentation contained 26 slide text sections, 26 speaker-note sections, and
  15 supported embedded image files.
- Resizing those 15 extracted images reduced the approximate base64 image payload from about 7.9M
  characters to about 0.76M characters before model injection.

## Live Telegram QA

| Use Case | Visible Result | Supporting Evidence | Result |
| --- | --- | --- | --- |
| Synthetic PPTX with known text/notes marker | Telegram reply named the expected slide-text and speaker-note markers | Bot sent one file; backend completed one Telegram chat stream | PASS |
| Private mixed PPTX with text, speaker notes, and embedded images | Telegram reply reported 26 slide sections, 26 speaker-note sections, 15 embedded visual images, and recognized the expected first-image visual marker | Bot log showed one file sent to LibreChat; backend logs showed extracted document images prepared, images injected, and chat completion done | PASS |
| Same private mixed PPTX before image resizing | Telegram received a provider completion failure caused by oversized raw extracted-image payload | Backend prompt telemetry showed an oversized background context before the resize fix | FIXED |

## Not Run / Scope Boundary

- This pass did not store a public screenshot because the real Telegram chat contained private
  surrounding content.
- Browser drag-and-drop upload was not separately exercised with an authenticated user session in
  this pass. The browser surface was health-checked with Playwright; shared parser behavior and the
  generic gateway image-injection path were covered by automated route tests.
- This implementation extracts PPTX text, notes, and supported embedded image media. It does not
  claim full-fidelity slide rendering, animation, chart reconstruction, or non-image media analysis.

## Public-Safety Review

This report omits raw Telegram IDs, user IDs, private filenames, screenshots, private chat text,
tokens, local App Support paths, and local absolute file paths. Evidence is summarized as public-safe
counts, command names, and pass/fail outcomes.
