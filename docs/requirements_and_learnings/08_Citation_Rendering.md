# Citation Rendering & Sanitization

## Overview
LibreChat injects citation markers into model output (e.g., `\ue202turn0search0`) so the web UI can
render rich sources. Surfaces that do not run the LibreChat citation renderer (Telegram and
agents-playground) must **strip** these markers to avoid user-visible noise.

## Core Requirements
- Telegram and agents-playground must **never** show raw citation markers.
- Sanitization must handle both literal escape sequences (`\ue202`) and actual Unicode characters
  (U+E202) emitted by different models.
- Sanitization must also strip bare marker strings without a backslash (e.g., `ue202turn0search0`).
- Sanitization must not hardcode citation type tokens; strip any `ue202turn<digits><type><digits>`.
- Bracket citations like `[1]` must be stripped on non-LibreChat surfaces.
- The cleanup patterns must remain aligned with LibreChat’s citation regexes.

## Specifications
- **LibreChat UI** (full citation rendering):
  - `viventium_v0_4/LibreChat/client/src/utils/citations.ts`
- **Telegram sanitization**:
  - `viventium_v0_4/telegram-viventium/TelegramVivBot/utils/librechat_bridge.py`
  - Function: `sanitize_telegram_text(...)`
- **Telegram TTS sanitization**:
  - `viventium_v0_4/telegram-viventium/TelegramVivBot/utils/tts.py`
  - Function: `prepare_tts_text(...)` (strips citations before speech)
- **Agents playground sanitization**:
  - `viventium_v0_4/agents-playground/src/utils/citations.ts`
  - Function: `stripCitations(...)`
  - Applied in `viventium_v0_4/agents-playground/src/components/chat/ChatMessage.tsx`
- **Modern playground sanitization (agent-starter-react)**:
  - `viventium_v0_4/agent-starter-react/lib/citations.ts`
  - Function: `stripCitations(...)`
  - Applied in `viventium_v0_4/agent-starter-react/components/app/chat-transcript.tsx`
- **Voice gateway sanitization** (LiveKit voice + playground):
  - `viventium_v0_4/voice-gateway/sse.py`
  - Function: `sanitize_voice_text(...)`

### Sanitization Behavior
- Remove composite citation blocks (`\ue200...\ue201`).
- Remove standalone citation anchors (`\ue202turnXsearchY`).
- Remove remaining citation marker characters.
- Remove bracket-style citations (`[1]`, `[12]`) when they appear as standalone anchors.
- Replace stripped markers with spaces and collapse whitespace to preserve word boundaries.

## Use Cases
- Telegram responses during background cortex follow-ups.
- Agents-playground chat display (voice playground UI).
- Voice gateway TTS output (avoid speaking citations).
- Telegram voice responses (avoid speaking citations).

## Edge Cases
- Consecutive citation anchors without separators.
- Mixed literal escape sequences and actual Unicode markers.
- Highlight spans (`\ue203...\ue204`) adjacent to citations.

## Integration Points
- `viventium_v0_4/telegram-viventium/TelegramVivBot/utils/librechat_bridge.py`
- `viventium_v0_4/telegram-viventium/TelegramVivBot/utils/tts.py`
- `viventium_v0_4/voice-gateway/sse.py`
- `viventium_v0_4/agents-playground/src/utils/citations.ts`
- `viventium_v0_4/agents-playground/src/components/chat/ChatMessage.tsx`
- `viventium_v0_4/agent-starter-react/lib/citations.ts`
- `viventium_v0_4/agent-starter-react/components/app/chat-transcript.tsx`
- `viventium_v0_4/LibreChat/client/src/utils/citations.ts`

## Learnings
- The existing citation regexes already handle consecutive markers; the main issue was missing
  sanitization in agents-playground, not a regex defect.
- Literal backslash sequences (`\\ue202...`) must be handled; Unicode-only regexes miss them.
