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

## Evidence
- [report.md](report.md)
