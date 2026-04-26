# Telegram Bridge - Requirements, Specs, and Learnings

## Overview

Telegram messages must route through the main LibreChat Agents pipeline by default. Responses
stream back to Telegram through the existing bridge.

## Core Requirements

- Telegram users receive complete responses or a clear error if the agent or voice stack disconnects.
- Connection loss mid-response must not leave users hanging on a partial holding message.
- Retry should be user-initiated to avoid duplicate tool actions.
- Telegram bot-token setup must stay truthful and reject malformed tokens.
- Telegram must differentiate voice-note input vs text input and forward that mode to LibreChat.
- Telegram media transcription failures must surface as explicit media errors, not as transcript text,
  and must not be forwarded into LibreChat as if the user said them.
- Telegram text responses should leverage MarkdownV2 formatting; voice-mode responses must be plain
  conversational text.
- Background follow-ups must preserve the same formatting rules as the main response.
- Telegram must mirror LibreChat UX for new features, including scheduled prompts and background
  follow-ups.
- Telegram must deliver LibreChat message attachments back to the Telegram user.
- Detached/local launches must not leave Telegram pointed at a dead LibreChat localhost origin after
  frontend dev-server exits or launcher-side supervision gaps.
- Detached/local launches must recover the LibreChat API when the real API child dies even if an
  npm/nodemon parent process is still alive.

## Public-Safe Implementation Notes

- Use the same product truth in Telegram and the web UI.
- Keep browser-facing URLs honest.
- Keep auth and token handling provider-specific and explicit.
- Do not embed private machine names, private paths, or owner-only debugging notes into the public
  contract.

## Telegram Voice and Call Behavior

- Voice-note transcription must use the configured runtime STT provider.
- Voice-note and video-note download/transcription failures must return one clean Telegram error and
  stop before chat submission.
- Telegram's hosted Bot API cannot download files above its platform limit, so oversized Telegram
  media must fail honestly unless the install is configured to use a local Telegram Bot API server.
- Voice replies must use a compatible TTS provider/key pair.
- `/call` should open the browser into the modern voice surface using a browser-facing URL.
- Raw LAN/IP browser-voice links should not be presented as a supported path unless they are
  explicitly known-good for the current deployment.

## Telegram Media Prerequisites

- Telegram voice notes and video notes are part of the supported bridge surface, so their media
  decoding requirements must be treated as first-class installer/runtime prerequisites.
- When Telegram is enabled, `ffmpeg` must be available and runnable on the host:
  - local `pywhispercpp` transcription needs it to decode Telegram's non-WAV voice-note media
  - Telegram video-note extraction already depends on it before transcription
- Presence alone is not enough. Startup/preflight must run a small ffmpeg media probe so broken
  Homebrew dynamic-library links fail honestly before Telegram is reported healthy.
- If the install needs Telegram media downloads beyond the hosted Bot API ceiling, the Telegram bot
  must be pointed at a local Telegram Bot API server instead of `https://api.telegram.org`.
- Canonical config owns that choice under `integrations.telegram`:
  - explicit external-server wiring with `bot_api_origin`, or
  - explicit `bot_api_base_url` and `bot_api_base_file_url`, or
  - Viventium-managed same-Mac server wiring under `local_bot_api`
- Path of least resistance applies here:
  - if an operator already has a supported local/external Telegram Bot API server, prefer wiring
    `bot_api_origin` (or the explicit base URLs) instead of making Viventium own another server
  - only use `integrations.telegram.local_bot_api` when Viventium must own the same-Mac server
    lifecycle itself
- Those canonical fields compile to:
  - `VIVENTIUM_TELEGRAM_BOT_API_ORIGIN`, or
  - explicit `VIVENTIUM_TELEGRAM_BOT_API_BASE_URL` and `VIVENTIUM_TELEGRAM_BOT_API_BASE_FILE_URL`
- When `integrations.telegram.local_bot_api.enabled` is true:
  - Viventium owns the local `telegram-bot-api` process lifecycle in the launcher
  - preflight must report the `telegram-bot-api` binary plus `api_id` / `api_hash` as prerequisites
  - the compiler derives `VIVENTIUM_TELEGRAM_BOT_API_ORIGIN` from the local host/port instead of
    requiring duplicate manual base-URL config
  - the Telegram bot must run in PTB local mode
  - Telegram media size policy must come from canonical config, not a hidden hardcoded default
- `integrations.telegram.max_file_size_bytes` is the canonical Telegram bridge media ceiling.
  Hosted Telegram defaults to 10 MB; managed local Bot API mode defaults to 100 MB unless the
  operator sets a different value explicitly.
- Public install flows must detect, install, and recheck `ffmpeg` automatically through preflight
  when Telegram is enabled.
- Telegram startup must fail honestly instead of reporting a healthy bridge when `ffmpeg` is
  unavailable or installed but not runnable.
- If a running bridge still encounters a non-runnable decoder, Telegram should return one clean
  media-decoder error and stop before chat submission.

## Telegram Attachments

Any file generated in LibreChat must be sent to the Telegram user as a Telegram photo/document,
not silently dropped.

Inbound Telegram message attachments must follow the same shared message-file contract as the web
UI. If the active model/provider supports a file through LibreChat's native "Upload to Provider"
path, the bridge must preserve the normal raw message attachment so downstream client code can send
it provider-natively. If the file is parseable but not valid for provider-native upload on that
surface, the runtime must promote it into the context-extraction pipeline instead of storing it as
an opaque upload the agent cannot read. If neither provider-native upload nor readable
context-extraction can handle the file on that surface, Telegram must fail the turn with a clear
attachment-processing error rather than silently dropping to caption-only behavior.

### Major file-type rule

- Text-like files must extract into readable context:
  - examples: `.txt`, `.md`, `.json`, `.csv`, `.xml`, `.yaml`, code/config text
- Provider-native raw attachments must stay raw when the current runtime can truly serialize them:
  - examples: images, PDFs, Google/OpenRouter audio/video, Bedrock document types
- Office/OpenDocument binaries that require OCR or a document parser must either:
  - use the configured OCR/document-parser path, or
  - fail honestly with a clear message when that extraction path is unavailable
- Unsupported binary/archive leftovers must not be accepted as inert message attachments.

### Fix pattern

- parse attachment events from the LibreChat stream
- download bytes through the gateway
- send images as albums when appropriate
- send non-image files as documents
- preserve provider-native message attachments and only auto-promote the non-provider-native
  parseable remainder into context extraction before the agent run
- reject files that are neither provider-native nor readable through context extraction

## Evidence to Capture

- helper logs
- Telegram bot logs
- Mongo proof of the exact user and assistant turns
- attachment delivery proof when files are involved
