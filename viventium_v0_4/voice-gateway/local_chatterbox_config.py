from __future__ import annotations

import os
import wave
from pathlib import Path
from typing import Optional

from mlx_chatterbox_tts import MlxChatterboxConfig


def _parse_bool_env(name: str, default: bool) -> bool:
    raw = (os.getenv(name, "") or "").strip().lower()
    if not raw:
        return default
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return default


def _parse_float_env(name: str, default: float) -> float:
    raw = (os.getenv(name, "") or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def validate_ref_audio_path(
    ref_audio_raw: str,
    *,
    min_duration_s: float = 5.0,
) -> tuple[Optional[str], Optional[str]]:
    """
    Validate optional local reference audio for Chatterbox voice cloning.

    Returns:
      (validated_path_or_none, warning_message_or_none)
    """
    ref_audio = (ref_audio_raw or "").strip()
    if not ref_audio:
        return None, None

    path = Path(ref_audio).expanduser()
    if not path.is_file():
        return None, f"VIVENTIUM_MLX_AUDIO_REF_AUDIO path does not exist or is not a file: {ref_audio}"

    try:
        size_bytes = path.stat().st_size
    except Exception as exc:
        return None, f"VIVENTIUM_MLX_AUDIO_REF_AUDIO stat failed for {ref_audio}: {exc}"

    if size_bytes < 1000:
        return None, (
            f"VIVENTIUM_MLX_AUDIO_REF_AUDIO file is suspiciously small ({size_bytes} bytes): {ref_audio}"
        )

    if path.suffix.lower() == ".wav":
        try:
            with wave.open(str(path), "rb") as wav_file:
                frames = int(wav_file.getnframes())
                sample_rate = int(wav_file.getframerate())
            duration_s = (frames / float(sample_rate)) if sample_rate > 0 else 0.0
            if duration_s < float(min_duration_s):
                return None, (
                    f"VIVENTIUM_MLX_AUDIO_REF_AUDIO WAV is too short ({duration_s:.2f}s); "
                    f"expected >= {min_duration_s:.1f}s for stable cloning: {ref_audio}"
                )
        except Exception as exc:
            return None, f"VIVENTIUM_MLX_AUDIO_REF_AUDIO WAV decode failed for {ref_audio}: {exc}"

    return str(path.resolve()), None


def build_local_chatterbox_config(
    model_id_override: Optional[str] = None,
) -> tuple[MlxChatterboxConfig, Optional[str]]:
    model_id = (
        (model_id_override or "").strip()
        or os.getenv("VIVENTIUM_MLX_AUDIO_MODEL_ID", "").strip()
        or "mlx-community/chatterbox-turbo-8bit"
    )
    stream = _parse_bool_env("VIVENTIUM_MLX_AUDIO_STREAM", True)
    streaming_interval_s = _parse_float_env("VIVENTIUM_MLX_AUDIO_STREAMING_INTERVAL_S", 1.0)
    sample_rate = max(8000, int(_parse_float_env("VIVENTIUM_MLX_AUDIO_SAMPLE_RATE", 24000.0)))
    prebuffer_ms = max(0.0, _parse_float_env("VIVENTIUM_MLX_AUDIO_PREBUFFER_MS", 500.0))
    temperature = _parse_float_env("VIVENTIUM_MLX_AUDIO_TEMPERATURE", 0.8)
    repetition_penalty = _parse_float_env("VIVENTIUM_MLX_AUDIO_REPETITION_PENALTY", 1.2)

    ref_audio, ref_audio_warning = validate_ref_audio_path(
        os.getenv("VIVENTIUM_MLX_AUDIO_REF_AUDIO", "")
    )
    return (
        MlxChatterboxConfig(
            model_id=model_id,
            sample_rate=sample_rate,
            stream=stream,
            streaming_interval_s=streaming_interval_s,
            prebuffer_ms=prebuffer_ms,
            ref_audio=ref_audio,
            temperature=temperature,
            repetition_penalty=repetition_penalty,
        ),
        ref_audio_warning,
    )
