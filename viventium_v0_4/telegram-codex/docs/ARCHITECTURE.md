# Architecture

`telegram-codex` has five small parts:

## 1. Telegram bot

Handles commands, text, voice notes, Telegram attachments, live preview relaying, and per-chat project selection.

## 2. Access control

Maintains:

- paired Telegram user ids
- pending localhost pairing tokens
- the bootstrap rule that only the first local pairing is accepted

## 3. Codex bridge

Runs local `codex exec --json` and `codex exec resume --json`, parses JSONL events (including live message deltas when available), and forwards assistant messages back to Telegram.

## 4. Local transcription

Uses `pywhispercpp` for local voice-note transcription with lazy model loading and optional model download.

## 5. Session store

Keeps the active project alias and Codex thread id per chat.

## 6. Attachment staging

Stores Telegram photos/documents under `.telegram_codex/attachments` inside the active project so Codex can read them within the selected workspace.
