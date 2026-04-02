# === VIVENTIUM START ===
# Feature: Centralized voice reply gating for Telegram.
# Purpose: Allow per-chat disable/enable of voice replies without breaking defaults.
# === VIVENTIUM END ===

from __future__ import annotations

from typing import Optional

# === VIVENTIUM START ===
# Feature: Robust boolean coercion for preference values.
def _coerce_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ("1", "true", "yes", "on"):
            return True
        if normalized in ("0", "false", "no", "off", ""):
            return False
        return default
    return bool(value)
# === VIVENTIUM END ===


def should_send_voice_reply(
    *,
    voice_note_detected: bool,
    always_voice: bool,
    voice_enabled: bool,
    text: Optional[str],
) -> bool:
    # === VIVENTIUM START ===
    # Coerce preference values (e.g., "false") into real booleans.
    voice_enabled = _coerce_bool(voice_enabled, True)
    always_voice = _coerce_bool(always_voice, False)
    # === VIVENTIUM END ===
    if not voice_enabled:
        return False
    if not text or not str(text).strip():
        return False
    return bool(voice_note_detected or always_voice)
