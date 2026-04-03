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
- Telegram text responses should leverage MarkdownV2 formatting; voice-mode responses must be plain
  conversational text.
- Background follow-ups must preserve the same formatting rules as the main response.
- Telegram must mirror LibreChat UX for new features, including scheduled prompts and background
  follow-ups.
- Telegram must deliver LibreChat message attachments back to the Telegram user.
- Detached/local launches must not leave Telegram pointed at a dead LibreChat localhost origin after
  frontend dev-server exits or launcher-side supervision gaps.

## Public-Safe Implementation Notes

- Use the same product truth in Telegram and the web UI.
- Keep browser-facing URLs honest.
- Keep auth and token handling provider-specific and explicit.
- Do not embed private machine names, private paths, or owner-only debugging notes into the public
  contract.

## Telegram Voice and Call Behavior
- Voice-note transcription must use the configured runtime STT provider.
- Voice replies must use a compatible TTS provider/key pair.
- `/call` should open the browser into the modern voice surface using a browser-facing URL.
- Raw LAN/IP browser-voice links should not be presented as a supported path unless they are
  explicitly known-good for the current deployment.

## Telegram Media Prerequisites
- Telegram voice notes and video notes are part of the supported bridge surface, so their media
  decoding requirements must be treated as first-class installer/runtime prerequisites.
- When Telegram is enabled, `ffmpeg` must be available on the host:
  - local `pywhispercpp` transcription needs it to decode Telegram's non-WAV voice-note media
  - Telegram video-note extraction already depends on it before transcription
- Public install flows must detect and install `ffmpeg` automatically through preflight when
  Telegram is enabled.
- Telegram startup must fail honestly instead of reporting a healthy bridge when `ffmpeg` is still
  unavailable.

## Telegram Attachments

Any file generated in LibreChat must be sent to the Telegram user as a Telegram photo/document,
not silently dropped.

### Fix pattern
- parse attachment events from the LibreChat stream
- download bytes through the gateway
- send images as albums when appropriate
- send non-image files as documents

## Evidence to Capture
- helper logs
- Telegram bot logs
- Mongo proof of the exact user and assistant turns
- attachment delivery proof when files are involved
