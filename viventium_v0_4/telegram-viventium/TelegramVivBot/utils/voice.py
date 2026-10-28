# === VIVENTIUM START ===
# Feature: Centralized voice reply gating for Telegram.
# Purpose: Allow per-chat disable/enable of voice replies without breaking defaults.
# === VIVENTIUM END ===

from __future__ import annotations

import hashlib
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
VOICE_INPUT_MODES = ("voice_note", "voice", "voice_call")

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
    reply_voice_with_voice: bool = True,
) -> bool:
    # === VIVENTIUM START ===
    # Voice replies require both audio-output routing and generated text.
    if not should_request_audio_reply(
        voice_note_detected=voice_note_detected,
        always_voice=always_voice,
        voice_enabled=voice_enabled,
        reply_voice_with_voice=reply_voice_with_voice,
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


def extract_ranged_audio_text(content: Any) -> tuple[bool, bool, str]:
    """Read canonical model-owned UTF-16 ranges without changing displayed text.

    Return presence, validity and eligible text. Once ranges are present, every
    text part needs complete, ordered coverage. Missing coverage stays silent.
    """
    if not isinstance(content, list):
        return False, False, ""
    parts = [part for part in content if isinstance(part, dict) and part.get("type") == "text"]
    present = any("deliveryDispositionRanges" in part for part in parts)
    if not present:
        return False, False, ""
    eligible = []
    try:
        for part in parts:
            text = part.get("text")
            if isinstance(text, dict):
                text = text.get("value")
            if not isinstance(text, str):
                raise ValueError("invalid ranged text")
            if not text:
                continue
            ranges = part.get("deliveryDispositionRanges")
            if not isinstance(ranges, list) or (text and not ranges):
                raise ValueError("missing delivery ranges")
            encoded = text.encode("utf-16-le")
            cursor = 0
            for item in ranges:
                if not isinstance(item, dict) or set(item) != {"start", "end", "disposition"}:
                    raise ValueError("invalid delivery range")
                start, end = item.get("start"), item.get("end")
                disposition = normalize_delivery_disposition(item.get("disposition"))
                if (type(start) is not int or type(end) is not int or start != cursor
                        or end <= start or end * 2 > len(encoded)
                        or disposition is None or disposition["required"] is not True
                        or disposition["source"] != "model"):
                    raise ValueError("invalid delivery choice")
                segment = encoded[start * 2:end * 2].decode("utf-16-le")
                if disposition["audio"] == "eligible":
                    eligible.append(segment)
                cursor = end
            if cursor * 2 != len(encoded):
                raise ValueError("incomplete delivery range coverage")
    except (ValueError, UnicodeError):
        return True, False, ""
    return True, True, "".join(eligible)


def extract_followup_audio_text(text: str, controls: Any) -> Optional[str]:
    """Bind retained native ranges to this exact persisted callback text."""
    if controls is None:
        return None
    if not isinstance(controls, dict):
        return ""
    if "audioContent" not in controls:
        return "" if "sourceTextSha256" in controls else None
    source_hash = controls.get("sourceTextSha256")
    if (not isinstance(source_hash, str)
            or hashlib.sha256(text.encode("utf-8")).hexdigest() != source_hash):
        return ""
    content = controls["audioContent"]
    if not isinstance(content, list):
        return ""
    source = []
    for part in content:
        if not isinstance(part, dict) or part.get("type") != "text":
            return ""
        value = part.get("text")
        if isinstance(value, dict):
            value = value.get("value")
        if not isinstance(value, str):
            return ""
        source.append(value)
    if "".join(source) != text:
        return ""
    present, valid, eligible = extract_ranged_audio_text(content)
    return eligible if present and valid else ""


# === VIVENTIUM START ===
# Feature: Shared Telegram audio-output routing.
# Purpose: Keep Telegram voice-note / always-voice audio delivery independent from
# LibreChat voice-call mode. Telegram is a text surface that can attach an audio reply.
def should_request_audio_reply(
    *,
    voice_note_detected: bool,
    always_voice: bool,
    voice_enabled: bool,
    reply_voice_with_voice: bool = True,
) -> bool:
    voice_enabled = _coerce_bool(voice_enabled, True)
    always_voice = _coerce_bool(always_voice, True)
    reply_voice_with_voice = _coerce_bool(reply_voice_with_voice, True)
    if not voice_enabled:
        return False
    return bool(always_voice or (voice_note_detected and reply_voice_with_voice))


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
