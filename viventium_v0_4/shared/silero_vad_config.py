# === VIVENTIUM START ===
# Feature: Shared Silero VAD env configuration for voice STT paths
# Added: 2026-03-10
#
# Purpose:
# - Keep Silero VAD env parsing as a single source of truth across the generic
#   voice gateway VAD path and the local whisper.cpp StreamAdapter path.
# - Expose max_buffered_speech so long continuous speech does not silently hit
#   LiveKit's 60-second default buffer ceiling.
# === VIVENTIUM END ===

from __future__ import annotations

import os
from typing import Any, Mapping

DEFAULT_SAMPLE_RATE = 16000
DEFAULT_MIN_SPEECH_DURATION = 0.1
DEFAULT_MIN_SILENCE_DURATION = 0.5
DEFAULT_ACTIVATION_THRESHOLD = 0.4
DEFAULT_MAX_BUFFERED_SPEECH = 600.0
DEFAULT_FORCE_CPU = False


def _read_env(env: Mapping[str, str | None], name: str) -> str:
    raw = env.get(name)
    return raw.strip() if isinstance(raw, str) else ""


def _parse_float_env(
    env: Mapping[str, str | None], name: str, fallback: float
) -> float:
    raw = _read_env(env, name)
    if not raw:
        return fallback

    try:
        value = float(raw)
    except ValueError:
        return fallback

    if value < 0 or value == float("inf"):
        return fallback

    return value


def _parse_bool_env(
    env: Mapping[str, str | None], name: str, fallback: bool
) -> bool:
    raw = _read_env(env, name).lower()
    if not raw:
        return fallback

    return raw in {"1", "true", "yes", "y", "on"}


def get_silero_vad_kwargs(
    env: Mapping[str, str | None] | None = None,
) -> dict[str, Any]:
    source = env if env is not None else os.environ

    return {
        "sample_rate": DEFAULT_SAMPLE_RATE,
        "min_speech_duration": _parse_float_env(
            source,
            "VIVENTIUM_STT_VAD_MIN_SPEECH",
            DEFAULT_MIN_SPEECH_DURATION,
        ),
        "min_silence_duration": _parse_float_env(
            source,
            "VIVENTIUM_STT_VAD_MIN_SILENCE",
            DEFAULT_MIN_SILENCE_DURATION,
        ),
        "max_buffered_speech": _parse_float_env(
            source,
            "VIVENTIUM_STT_VAD_MAX_BUFFERED_SPEECH",
            DEFAULT_MAX_BUFFERED_SPEECH,
        ),
        "activation_threshold": _parse_float_env(
            source,
            "VIVENTIUM_STT_VAD_ACTIVATION",
            DEFAULT_ACTIVATION_THRESHOLD,
        ),
        "force_cpu": _parse_bool_env(
            source,
            "VIVENTIUM_STT_VAD_FORCE_CPU",
            DEFAULT_FORCE_CPU,
        ),
    }


__all__ = [
    "DEFAULT_ACTIVATION_THRESHOLD",
    "DEFAULT_FORCE_CPU",
    "DEFAULT_MAX_BUFFERED_SPEECH",
    "DEFAULT_MIN_SILENCE_DURATION",
    "DEFAULT_MIN_SPEECH_DURATION",
    "DEFAULT_SAMPLE_RATE",
    "get_silero_vad_kwargs",
]
