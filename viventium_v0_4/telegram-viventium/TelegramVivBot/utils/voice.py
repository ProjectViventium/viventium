# === VIVENTIUM START ===
# Feature: Centralized voice reply gating for Telegram.
# Purpose: Allow per-chat disable/enable of voice replies without breaking defaults.
# === VIVENTIUM END ===

from __future__ import annotations

from typing import Optional

try:
    from utils.env import coerce_bool
except ModuleNotFoundError:
    from TelegramVivBot.utils.env import coerce_bool

# === VIVENTIUM START ===
# Feature: Robust boolean coercion for preference values.
def _coerce_bool(value: object, default: bool) -> bool:
    return coerce_bool(value, default)
# === VIVENTIUM END ===


# === VIVENTIUM START ===
# Feature: Public helper for honest preference logging.
def normalize_voice_preference(value: object, default: bool) -> bool:
    return _coerce_bool(value, default)
# === VIVENTIUM END ===


def should_send_voice_reply(
    *,
    voice_note_detected: bool,
    always_voice: bool,
    voice_enabled: bool,
    text: Optional[str],
) -> bool:
    # === VIVENTIUM START ===
    # Voice replies require both output routing and generated text.
    if not should_request_voice_mode(
        voice_note_detected=voice_note_detected,
        always_voice=always_voice,
        voice_enabled=voice_enabled,
    ):
        return False
    # === VIVENTIUM END ===
    if not text or not str(text).strip():
        return False
    return True


# === VIVENTIUM START ===
# Feature: Shared pre-generation voice-mode routing.
# Purpose: The same user preference that causes Telegram to send audio must also
# request voice-mode prompt instructions before the LLM response is generated.
def should_request_voice_mode(
    *,
    voice_note_detected: bool,
    always_voice: bool,
    voice_enabled: bool,
) -> bool:
    voice_enabled = _coerce_bool(voice_enabled, True)
    always_voice = _coerce_bool(always_voice, False)
    if not voice_enabled:
        return False
    return bool(voice_note_detected or always_voice)
# === VIVENTIUM END ===
