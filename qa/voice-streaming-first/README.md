# Voice Streaming First QA

## Scope
- Voice-gateway TTS startup latency for live voice calls
- Cartesia native incremental streaming
- Streaming-aware fallback behavior
- Regression coverage for the voice-gateway provider wrapper stack

## Acceptance Criteria
- Live voice TTS starts from incremental LLM output instead of waiting for the full final answer.
- Cartesia uses its native WebSocket continuation path for live voice.
- Fallback routing does not downgrade a native-streaming provider back to a non-streaming wrapper.
- Same-turn fallback still strips Cartesia-only control tags for non-expressive providers.
- Voice-gateway regression tests pass after the change.
- Same-turn Main continuation speech requires the current native reservation and matching accepted
  family; it does not receive an invocation preview or an inherited request body hash.
- A newer admission, changed logical turn, Stop or cancelled request suppresses stale public speech.
- Stream loss after early public words leaves the saved response unfinished, reports an error and
  does not start a replacement author. Failure after a resolved stream preserves the complete answer.
- Accepted durable actions remain once-only when speech stops or fails. Real captured audio must
  prove early speech and interruption behavior; deterministic replay alone is supporting evidence.
- Authored words before a selected local file link stream early; the mutable link suffix waits for
  the canonical terminal content and exact file carrier. Public URLs, code and literal text retain
  their behavior. Missing or rejected files do not gain a carrier, and stale or cancelled turns do
  not gain speech or artifact authority.

## Evidence

- [Current scoped Voice and Telegram acceptance, 2026-10-03](../modern-playground-voice/reports/2026-10-03-voice-and-telegram-acceptance.md): actual Main speech began before the tool-bearing native turn ended; physical response under two seconds remains unmet. This bounded result does not execute the complete Cartesia/fallback matrix below.
- [Retained native-harness evidence, 2026-09-30](../modern-playground-voice/reports/2026-09-30-native-harness-parity-and-observability.md): incremental text-to-TTS and stage measurements for unchanged paths.
- [Original provider-wrapper report](report.md).
