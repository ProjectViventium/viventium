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
    # Voice replies require both audio-output routing and generated text.
    if not should_request_audio_reply(
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
# Feature: Shared Telegram audio-output routing.
# Purpose: Keep Telegram voice-note / always-voice audio delivery independent from
# LibreChat voice-call mode. Telegram is a text surface that can attach an audio reply.
def should_request_audio_reply(
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


def should_request_voice_mode(
    *,
    voice_note_detected: bool,
    always_voice: bool,
    voice_enabled: bool,
) -> bool:
    """Return whether Telegram should request LibreChat voice-call mode.

    Telegram voice notes and always-voice replies are text-mode turns with optional
    audio delivery, so they must not opt into the LiveKit/voice-call prompt,
    Phase-A, or LLM override path.
    """
    _ = voice_note_detected, always_voice, voice_enabled
    return False
# === VIVENTIUM END ===
