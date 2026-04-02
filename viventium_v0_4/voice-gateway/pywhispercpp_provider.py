# === VIVENTIUM START ===
# Feature: Local whisper.cpp STT provider with VAD stream adapter (v1 parity)
# Added: 2026-01-11
# === VIVENTIUM END ===

"""PyWhisperCpp STT Provider - Fast, reliable C++ Whisper implementation."""

from __future__ import annotations

import audioop
import logging
import os
import platform
import tempfile
import wave
from pathlib import Path
from typing import List, Optional

import numpy as np
from livekit.agents.stt import (
    STT,
    STTCapabilities,
    SpeechData,
    SpeechEvent,
    SpeechEventType,
)
from livekit.agents.stt.stream_adapter import StreamAdapter
from livekit.agents.utils import AudioBuffer
from livekit.rtc.audio_frame import AudioFrame
from silero_vad_config import get_silero_vad_kwargs

try:
    from pywhispercpp.model import Model
except ImportError as exc:
    raise RuntimeError(
        "PyWhisperCpp STT selected but the 'pywhispercpp' package is not installed. "
        "Install it via 'pip install pywhispercpp'."
    ) from exc

_logger = logging.getLogger(__name__)
_MODEL_CACHE: dict[str, Model] = {}

# Common hallucination phrases Whisper outputs on silence/noise
# Based on research: https://github.com/ggml-org/whisper.cpp/issues/1724
HALLUCINATION_PHRASES = {
    "thank you",
    "thanks",
    "okay",
    "ok",
    "bye",
    "goodbye",
    "you",
    "thank you.",
    "thanks.",
    "okay.",
    "- thank you",
    "- thank you.",
    "- okay",
    "- okay.",
}


def _default_model_name(configured_model: Optional[str] = None) -> str:
    configured = (configured_model or os.getenv("VIVENTIUM_STT_MODEL", "")).strip()
    if configured:
        return configured
    if platform.machine().lower() == "x86_64":
        return "tiny.en"
    return "large-v3-turbo"


def _get_model(model_name_override: Optional[str] = None) -> Model:
    """Get or create the WhisperCpp model instance."""
    model_name = _default_model_name(model_name_override)
    cached_model = _MODEL_CACHE.get(model_name)
    if cached_model is None:
        model_path = os.getenv("VIVENTIUM_STT_MODEL_PATH")
        default_threads = "2" if platform.machine().lower() == "x86_64" else "8"
        n_threads = int(os.getenv("VIVENTIUM_STT_THREADS", default_threads))

        # If model_path not specified, download the model
        if not model_path:
            model_map = {
                "tiny": "ggml-tiny.bin",
                "tiny.en": "ggml-tiny.en.bin",
                "base": "ggml-base.bin",
                "base.en": "ggml-base.en.bin",
                "small": "ggml-small.bin",
                "medium": "ggml-medium.bin",
                "large": "ggml-large.bin",
                "large-v1": "ggml-large-v1.bin",
                "large-v2": "ggml-large-v2.bin",
                "large-v3": "ggml-large-v3.bin",
                "large-v3-turbo": "ggml-large-v3-turbo.bin",
            }

            filename = model_map.get(model_name, "ggml-large-v3-turbo.bin")
            model_dir = Path.home() / ".cache" / "whisper"
            model_dir.mkdir(parents=True, exist_ok=True)
            model_path = str(model_dir / filename)

            # Download if not exists
            if not Path(model_path).exists():
                _logger.info("Downloading Whisper model %s to %s", model_name, model_path)
                import urllib.request
                url = f"https://huggingface.co/ggerganov/whisper.cpp/resolve/main/{filename}"
                urllib.request.urlretrieve(url, model_path)
                _logger.info("Downloaded %s successfully", model_name)

        _logger.info("Loading PyWhisperCpp model from %s", model_path)
        cached_model = Model(model_path, n_threads=n_threads, print_realtime=False, print_progress=False)
        _MODEL_CACHE[model_name] = cached_model
        _logger.info("PyWhisperCpp model loaded successfully with %s threads", n_threads)

    return cached_model


def prewarm_model(model_name: Optional[str] = None) -> None:
    """Ensure the local whisper.cpp model is downloaded and loaded in-process."""
    _get_model(model_name)


class PyWhisperCppSTT(STT):
    """PyWhisperCpp-based Speech-to-Text implementation."""

    def __init__(
        self,
        *,
        language: str = "en",
        sample_rate: int = 16000,
        model_name: Optional[str] = None,
    ) -> None:
        super().__init__(
            capabilities=STTCapabilities(streaming=False, interim_results=False)
        )
        self._language = language
        self._sample_rate = sample_rate
        self._model_name = _default_model_name(model_name)
        self._model = _get_model(self._model_name)

    @property
    def model(self) -> str:
        return self._model_name

    @property
    def provider(self) -> str:
        return "PyWhisperCpp"

    async def _recognize_impl(
        self,
        buffer: AudioBuffer,
        *,
        language: str | None = None,
        conn_options: object = None,
    ) -> SpeechEvent:
        # Handle AudioBuffer which can be a frame or list of frames
        frames: List[AudioFrame] = []
        if isinstance(buffer, list):
            frames = buffer
        else:
            frames = [buffer]

        if not frames:
            return SpeechEvent(
                type=SpeechEventType.FINAL_TRANSCRIPT,
                alternatives=[SpeechData(text="", language=self._language)]
            )

        # Combine all audio frames into a single PCM buffer
        sample_rate = frames[0].sample_rate
        num_channels = frames[0].num_channels
        pcm_chunks: List[bytes] = []

        for frame in frames:
            if frame.sample_rate != sample_rate or frame.num_channels != num_channels:
                raise ValueError("Mismatched audio frame parameters")
            pcm_chunks.append(frame.data.tobytes())

        pcm_bytes = b"".join(pcm_chunks)

        # Convert to mono if needed
        if num_channels > 1:
            pcm_bytes = audioop.tomono(pcm_bytes, 2, 0.5, 0.5)
            num_channels = 1

        # Resample to 16kHz if needed
        if sample_rate != self._sample_rate:
            pcm_bytes, _ = audioop.ratecv(
                pcm_bytes,
                2,  # 16-bit audio (2 bytes per sample)
                num_channels,
                sample_rate,
                self._sample_rate,
                None,
            )

        # Convert to int16 numpy array (PyWhisperCpp expects int16)
        audio_data = np.frombuffer(pcm_bytes, dtype=np.int16)

        # Use memory-mapped temp file for faster I/O
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
            tmp_path = tmp_wav.name
            # Write WAV header and data directly
            with wave.open(tmp_path, "wb") as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(self._sample_rate)
                wav_file.writeframes(audio_data.tobytes())

        try:
            lang = language or self._language
            segments = self._model.transcribe(
                tmp_path,
                language=lang,
                no_speech_thold=0.7,
                logprob_thold=-0.8,
                suppress_blank=True,
                temperature=0.0,
                entropy_thold=2.2,
            )

            text = " ".join([segment.text for segment in segments]) if segments else ""

            text_clean = text.strip().lower()
            if text_clean in HALLUCINATION_PHRASES:
                _logger.debug("Filtered hallucination: '%s'", text)
                text = ""
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

        return SpeechEvent(
            type=SpeechEventType.FINAL_TRANSCRIPT,
            alternatives=[SpeechData(text=text, language=lang)]
        )


def get_stt(*, model_name: Optional[str] = None, language: Optional[str] = None) -> StreamAdapter:
    """Get PyWhisperCpp STT wrapped in StreamAdapter with VAD for streaming support."""
    from livekit.plugins.silero import VAD

    stt_kwargs = {
        "language": language or os.getenv("VIVENTIUM_STT_LANGUAGE", "en"),
    }
    if model_name is not None:
        stt_kwargs["model_name"] = model_name

    stt = PyWhisperCppSTT(**stt_kwargs)

    vad_kwargs = get_silero_vad_kwargs()
    _logger.info(
        "Loading PyWhisperCpp StreamAdapter VAD min_speech=%ss min_silence=%ss activation=%s max_buffered_speech=%ss force_cpu=%s",
        vad_kwargs["min_speech_duration"],
        vad_kwargs["min_silence_duration"],
        vad_kwargs["activation_threshold"],
        vad_kwargs["max_buffered_speech"],
        vad_kwargs["force_cpu"],
    )
    vad = VAD.load(**vad_kwargs)

    return StreamAdapter(stt=stt, vad=vad)


__all__ = ["get_stt", "PyWhisperCppSTT", "prewarm_model"]
