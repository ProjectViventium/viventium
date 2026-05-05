# Telegram Settings Latency QA

## Scope

Acceptance source for the Telegram `/info` -> Preferences path and adjacent bridge reliability
surfaces.

## Acceptance

- Pressing Preferences after `/info` must not wait behind delayed cleanup.
- `/info` must keep the interactive menu message available; delayed cleanup may remove only the
  user's command echo.
- Preferences and Back rendering must not perform synchronous call-link HTTP fetches on the
  callback hot path.
- Telegram voice-preference sync must not block the event loop while a toggle is being handled.
- When global voice STT is local Whisper and Telegram STT is omitted, the compiler must keep
  Telegram on the inherited local Whisper/whisper.cpp route. Hosted OpenAI or AssemblyAI STT must
  be explicit Telegram overrides, never silent defaults.
- Generated secret-bearing service env files must not be group/world readable.
