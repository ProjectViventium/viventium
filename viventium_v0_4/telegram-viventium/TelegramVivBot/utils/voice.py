# === VIVENTIUM START ===
# Feature: Centralized voice reply gating for Telegram.
# Purpose: Allow per-chat disable/enable of voice replies without breaking defaults.
# === VIVENTIUM END ===

from __future__ import annotations

from typing import Any, Optional

try:
    from utils.env import coerce_bool
except ModuleNotFoundError:
    from TelegramVivBot.utils.env import coerce_bool

DELIVERY_DISPOSITION_VERSION = 1
DELIVERY_DISPOSITION_AUDIO_VALUES = frozenset({"skip", "eligible"})
DELIVERY_DISPOSITION_KEYS = frozenset(
    {"version", "audio", "required", "valid", "source"}
)
DELIVERY_DISPOSITION_VALID_SOURCES = frozenset({"model", "legacy_marker"})

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


def normalize_delivery_disposition(value: Any) -> Optional[dict[str, Any]]:
    """Return the validated LibreChat-to-adapter delivery contract."""

    if not isinstance(value, dict):
        return None
    audio = value.get("audio")
    source = value.get("source")
    valid = bool(
        set(value) == DELIVERY_DISPOSITION_KEYS
        and type(value.get("version")) is int
        and value.get("version") == DELIVERY_DISPOSITION_VERSION
        and isinstance(audio, str)
        and audio in DELIVERY_DISPOSITION_AUDIO_VALUES
        and type(value.get("required")) is bool
        and value.get("valid") is True
        and isinstance(source, str)
        and source in DELIVERY_DISPOSITION_VALID_SOURCES
    )
    if not valid:
        return None
    return {
        "version": value["version"],
        "audio": audio,
        "required": value["required"],
        "valid": True,
        "source": source,
    }


def resolve_delivery_audio_gate(
    *,
    legacy_skip_requested: bool,
    delivery_disposition: Any,
    disposition_required: bool,
) -> tuple[bool, str]:
    """Resolve structural audio eligibility before user preference gating.

    The standalone legacy control remains authoritative during rollout. A required
    structured contract fails closed when its final metadata is absent or invalid;
    an optional absent contract keeps the pre-existing behavior.
    """

    if legacy_skip_requested:
        return False, "legacy_skip"

    candidate_required = bool(
        isinstance(delivery_disposition, dict)
        and delivery_disposition.get("required") is True
    )
    required = bool(disposition_required or candidate_required)
    normalized = normalize_delivery_disposition(delivery_disposition)
    if required and normalized is not None and normalized["required"] is not True:
        normalized = None
    if normalized is not None:
        if normalized["audio"] == "skip":
            return False, "structured_skip"
        return True, "structured_eligible"
    if required:
        return False, "required_invalid"
    return True, "legacy"


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
