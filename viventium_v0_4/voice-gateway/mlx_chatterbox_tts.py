# === VIVENTIUM START ===
# Feature: Local Chatterbox Turbo (MLX-Audio) TTS provider for LiveKit Agents
# Added: 2026-02-10
#
# Purpose:
# - Enable a local (macOS/Apple Silicon) TTS provider that can reach "Cartesia-level" quality
#   while running fully offline/locally.
# - Use the upstream `mlx-audio` project and the MLX-converted Hugging Face model:
#     `mlx-community/chatterbox-turbo-8bit`
#
# Design constraints:
# - Voice-gateway runs on asyncio. MLX generation is CPU/GPU-bound and would block the event loop
#   if executed inline, which breaks "interruptions" and harms LiveKit responsiveness.
# - We therefore run synthesis in a background thread and forward PCM chunks back to the event loop
#   via `loop.call_soon_threadsafe(...)`.
#
# Notes:
# - This provider intentionally uses LiveKit's non-streaming TTS interface (`synthesize`), letting
#   LiveKit wrap it with `tts.StreamAdapter` to get low-latency sentence chunking from LLM deltas.
# - We keep the import of `mlx_audio` inside the model-loader so the rest of the stack can run
#   without MLX installed (e.g., Linux/Container Apps).
# === VIVENTIUM END ===

from __future__ import annotations

import asyncio
import io
import logging
import os
import re
import threading
import time
import uuid
import wave
from dataclasses import dataclass
from typing import Optional

import numpy as np

from livekit.agents import APIError
from livekit.agents.tts import AudioEmitter, ChunkedStream, TTS, TTSCapabilities
from livekit.agents.types import APIConnectOptions, DEFAULT_API_CONNECT_OPTIONS

from sse import sanitize_voice_text

logger = logging.getLogger("voice-gateway.mlx_chatterbox")


DEFAULT_MODEL_ID = "mlx-community/chatterbox-turbo-8bit"
# === VIVENTIUM START ===
# Feature: safe default sample rate for local Chatterbox.
# Purpose: Chatterbox Turbo emits 24kHz audio; matching that rate avoids slowed/chipmunk playback.
DEFAULT_SAMPLE_RATE = 24000
# === VIVENTIUM END ===
DEFAULT_NUM_CHANNELS = 1
DEFAULT_STREAM = True
# === VIVENTIUM START ===
# Feature: Tuned streaming defaults for audio quality.
# Purpose: The upstream mlx-audio default is 2.0s (50 tokens at 25Hz). At 0.18-0.25s we hit
# only 10 tokens per S3Gen vocoder chunk which causes audible boundary artifacts / periodic
# audio glitches. 1.0s (25 tokens) is the sweet spot: low TTFA while giving the vocoder
# enough context for clean, continuous audio per chunk.
DEFAULT_STREAMING_INTERVAL_S = 1.0
DEFAULT_PREBUFFER_MS = 500.0
# === VIVENTIUM END ===

_SPEAK_TAG_RE = re.compile(r"</?speak[^>]*>", re.IGNORECASE)
_EMOTION_SELF_CLOSING_RE = re.compile(r"<emotion\s+value=[\"']?([^\"'>]+)[\"']?\s*/>", re.IGNORECASE)
_EMOTION_WRAPPER_RE = re.compile(
    r"<emotion\s+value=[\"']?([^\"'>]+)[\"']?\s*>(.*?)</emotion>",
    re.IGNORECASE | re.DOTALL,
)

_MODEL_CACHE: dict[str, object] = {}
_MODEL_LOCK = threading.Lock()


def _should_log_latency() -> bool:
    return (os.getenv("VIVENTIUM_VOICE_LOG_LATENCY", "") or "").strip() == "1"


def _strip_cartesia_emotion_tags(text: str) -> str:
    """
    Chatterbox does not need Cartesia SSML. If the agent mistakenly emits <emotion> tags
    (e.g., carried over from Cartesia prompt rules), remove them while preserving inner text.
    """
    if not text:
        return ""
    cleaned = _SPEAK_TAG_RE.sub("", text)
    cleaned = _EMOTION_SELF_CLOSING_RE.sub("", cleaned)
    # Keep inner text for wrapper form.
    cleaned = _EMOTION_WRAPPER_RE.sub(lambda m: m.group(2) or "", cleaned)
    return cleaned


def _load_mlx_model(model_id: str) -> object:
    with _MODEL_LOCK:
        cached = _MODEL_CACHE.get(model_id)
        if cached is not None:
            return cached

        # Delayed import so non-mac deployments don't fail at import time.
        from mlx_audio.tts.utils import load_model  # type: ignore[import-not-found]

        model = load_model(model_id)
        _MODEL_CACHE[model_id] = model
        return model


def _audio_to_pcm_s16le(audio: object) -> bytes:
    if audio is None:
        return b""
    audio_np = np.asarray(audio, dtype=np.float32).reshape(-1)
    if audio_np.size == 0:
        return b""
    audio_np = np.clip(audio_np, -1.0, 1.0)
    audio_i16 = (audio_np * 32767.0).astype("<i2", copy=False)
    return audio_i16.tobytes()


def _pcm_to_wav_bytes(*, pcm: bytes, sample_rate: int, num_channels: int) -> bytes:
    if not pcm:
        return b""
    with io.BytesIO() as buffer:
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(max(1, int(num_channels)))
            wav_file.setsampwidth(2)
            wav_file.setframerate(max(8000, int(sample_rate)))
            wav_file.writeframes(pcm)
        return buffer.getvalue()


@dataclass(frozen=True)
class MlxChatterboxConfig:
    model_id: str = DEFAULT_MODEL_ID
    sample_rate: int = DEFAULT_SAMPLE_RATE
    num_channels: int = DEFAULT_NUM_CHANNELS
    stream: bool = DEFAULT_STREAM
    streaming_interval_s: float = DEFAULT_STREAMING_INTERVAL_S
    prebuffer_ms: float = DEFAULT_PREBUFFER_MS
    ref_audio: Optional[str] = None
    # === VIVENTIUM START ===
    # Feature: Expose upstream Chatterbox generation parameters for quality tuning.
    # Upstream defaults: temperature=0.8, repetition_penalty=1.2.
    temperature: float = 0.8
    repetition_penalty: float = 1.2
    # === VIVENTIUM END ===


class MlxChatterboxTTS(TTS):
    def __init__(self, *, config: MlxChatterboxConfig) -> None:
        super().__init__(
            capabilities=TTSCapabilities(streaming=False),
            sample_rate=int(config.sample_rate),
            num_channels=int(config.num_channels),
        )
        self._config = config

    @property
    def provider(self) -> str:
        return "mlx_audio"

    @property
    def model(self) -> str:
        return self._config.model_id

    def prewarm(self) -> None:
        """Best-effort preload. Downloads weights on first run and loads into MLX memory."""
        try:
            _load_mlx_model(self._config.model_id)
            logger.info("MLX Chatterbox model loaded (model=%s)", self._config.model_id)
        except Exception:
            logger.warning(
                "MLX Chatterbox prewarm failed (model=%s); first synthesis will be slow",
                self._config.model_id,
                exc_info=True,
            )

    def synthesize(
        self, text: str, *, conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS
    ) -> ChunkedStream:
        return _MlxChatterboxChunkedStream(tts=self, input_text=text, conn_options=conn_options)


def synthesize_wav_bytes(text: str, *, config: MlxChatterboxConfig) -> bytes:
    """
    Produce a complete WAV payload for non-LiveKit surfaces such as Telegram.

    This reuses the same model cache, sanitization, ref-audio, and generation knobs as the
    streaming LiveKit provider while returning a single self-contained audio file.
    """
    input_text = sanitize_voice_text(text or "")
    input_text = _strip_cartesia_emotion_tags(input_text).strip()
    if not input_text:
        return b""

    model = _load_mlx_model(config.model_id)
    effective_sample_rate = int(config.sample_rate)
    chunks: list[bytes] = []

    for result in model.generate(  # type: ignore[attr-defined]
        text=input_text,
        ref_audio=config.ref_audio,
        stream=bool(config.stream),
        streaming_interval=float(config.streaming_interval_s),
        temperature=float(config.temperature),
        repetition_penalty=float(config.repetition_penalty),
    ):
        result_sample_rate = getattr(result, "sample_rate", None)
        if isinstance(result_sample_rate, int) and result_sample_rate > 0:
            effective_sample_rate = int(result_sample_rate)
        pcm = _audio_to_pcm_s16le(getattr(result, "audio", None))
        if pcm:
            chunks.append(pcm)

    if not chunks:
        return b""

    return _pcm_to_wav_bytes(
        pcm=b"".join(chunks),
        sample_rate=effective_sample_rate,
        num_channels=int(config.num_channels),
    )


class _MlxChatterboxChunkedStream(ChunkedStream):
    async def _run(self, output_emitter: AudioEmitter) -> None:
        tts: MlxChatterboxTTS = self._tts  # type: ignore[assignment]
        cfg = tts._config
        log_latency = _should_log_latency()
        started_at = time.monotonic()
        request_id = f"mlx_{uuid.uuid4().hex[:12]}"

        # Last-mile cleanup (citations, accidental Cartesia SSML).
        input_text = sanitize_voice_text(self._input_text or "")
        input_text = _strip_cartesia_emotion_tags(input_text)
        input_text = input_text.strip()
        if not input_text:
            # LiveKit's ChunkedStream main task always finalizes the emitter. If we return
            # without initialization here, it can raise "AudioEmitter isn't started".
            output_emitter.initialize(
                request_id=request_id,
                sample_rate=int(cfg.sample_rate),
                num_channels=tts.num_channels,
                mime_type="audio/pcm",
                frame_size_ms=200,
                stream=False,
            )
            return

        total_timeout_s = max(120.0, float(self._conn_options.timeout))
        deadline = time.monotonic() + total_timeout_s

        loop = asyncio.get_running_loop()
        q: asyncio.Queue[Optional[tuple[int, bytes]]] = asyncio.Queue()
        done_fut: asyncio.Future[None] = loop.create_future()
        stop_event = threading.Event()
        bytes_per_second = 0
        prebuffer_ms = max(0.0, float(cfg.prebuffer_ms))
        prebuffer_bytes = 0
        buffered = bytearray()
        generated_bytes = 0
        emitted_bytes = 0
        first_audio_at: Optional[float] = None
        effective_sample_rate: Optional[int] = None
        emitter_initialized = False

        def _set_done_ok() -> None:
            if done_fut.done():
                return
            done_fut.set_result(None)

        def _set_done_err(exc: BaseException) -> None:
            if done_fut.done():
                return
            done_fut.set_exception(exc)

        def _emit_pcm(sample_rate: int, pcm: bytes) -> None:
            if not pcm:
                return
            try:
                q.put_nowait((sample_rate, pcm))
            except Exception:
                # Should never happen with an unbounded queue; keep defensive.
                logger.debug("mlx chatterbox queue put failed", exc_info=True)

        def _emit_end() -> None:
            try:
                q.put_nowait(None)
            except Exception:
                logger.debug("mlx chatterbox end put failed", exc_info=True)

        def _worker() -> None:
            try:
                model = _load_mlx_model(cfg.model_id)
                # `mlx-audio` TTS models yield GenerationResult objects.
                # NOTE: upstream `sample_rate` param is the *input* ref_audio rate (not output).
                # Output rate is always model.sample_rate (S3GEN_SR = 24kHz for Chatterbox Turbo).
                # We read the actual output rate from result.sample_rate below.
                for result in model.generate(  # type: ignore[attr-defined]
                    text=input_text,
                    ref_audio=cfg.ref_audio,
                    stream=bool(cfg.stream),
                    streaming_interval=float(cfg.streaming_interval_s),
                    temperature=float(cfg.temperature),
                    repetition_penalty=float(cfg.repetition_penalty),
                ):
                    if stop_event.is_set():
                        break
                    result_sample_rate = getattr(result, "sample_rate", None)
                    if isinstance(result_sample_rate, int) and result_sample_rate > 0:
                        sample_rate = int(result_sample_rate)
                    else:
                        sample_rate = int(cfg.sample_rate)
                    pcm = _audio_to_pcm_s16le(getattr(result, "audio", None))
                    if not pcm:
                        continue
                    loop.call_soon_threadsafe(_emit_pcm, sample_rate, pcm)

                loop.call_soon_threadsafe(_set_done_ok)
            except BaseException as exc:
                loop.call_soon_threadsafe(_set_done_err, exc)
            finally:
                loop.call_soon_threadsafe(_emit_end)

        thread = threading.Thread(target=_worker, name="mlx-chatterbox-tts", daemon=True)
        thread.start()

        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    stop_event.set()
                    raise APIError("Local Chatterbox (MLX) TTS timed out", retryable=True)

                item = await asyncio.wait_for(q.get(), timeout=remaining)
                if item is None:
                    break
                chunk_sample_rate, chunk = item
                if not emitter_initialized:
                    effective_sample_rate = max(8000, int(chunk_sample_rate))
                    bytes_per_second = max(1, int(effective_sample_rate * tts.num_channels * 2))
                    prebuffer_bytes = int((prebuffer_ms / 1000.0) * bytes_per_second)
                    output_emitter.initialize(
                        request_id=request_id,
                        sample_rate=effective_sample_rate,
                        num_channels=tts.num_channels,
                        mime_type="audio/pcm",
                        frame_size_ms=200,
                        stream=False,
                    )
                    emitter_initialized = True
                    requested_sample_rate = int(cfg.sample_rate)
                    if effective_sample_rate != requested_sample_rate:
                        logger.warning(
                            "[voice-gateway][mlx-chatterbox] Using model output sample_rate=%s (requested=%s) to prevent distorted playback",
                            effective_sample_rate,
                            requested_sample_rate,
                        )
                generated_bytes += len(chunk)
                buffered.extend(chunk)

                should_emit = first_audio_at is not None or prebuffer_bytes <= 0
                if first_audio_at is None and prebuffer_bytes > 0 and len(buffered) >= prebuffer_bytes:
                    should_emit = True

                if should_emit and buffered:
                    output_emitter.push(bytes(buffered))
                    emitted_bytes += len(buffered)
                    buffered.clear()
                    if first_audio_at is None:
                        first_audio_at = time.monotonic()
                        if log_latency:
                            logger.info(
                                "[VoiceLatency] mlx_tts_first_audio_ms=%s request_id=%s prebuffer_ms=%s generated_bytes=%s",
                                int((first_audio_at - started_at) * 1000),
                                request_id,
                                int(prebuffer_ms),
                                generated_bytes,
                            )

            # Propagate worker thread exceptions.
            await done_fut

            if buffered:
                output_emitter.push(bytes(buffered))
                emitted_bytes += len(buffered)
                buffered.clear()
                if first_audio_at is None:
                    first_audio_at = time.monotonic()

            if log_latency:
                completed_at = time.monotonic()
                sample_rate_for_metrics = int(effective_sample_rate or cfg.sample_rate)
                bytes_per_second_for_metrics = max(1, int(sample_rate_for_metrics * tts.num_channels * 2))
                audio_s = emitted_bytes / float(bytes_per_second_for_metrics)
                wall_s = max(0.001, completed_at - started_at)
                rtf = (wall_s / audio_s) if audio_s > 0 else 0.0
                logger.info(
                    "[VoiceLatency] mlx_tts_done_ms=%s request_id=%s audio_ms=%s rtf=%.2f sample_rate=%s interval_s=%.2f",
                    int((completed_at - started_at) * 1000),
                    request_id,
                    int(audio_s * 1000),
                    rtf,
                    sample_rate_for_metrics,
                    float(cfg.streaming_interval_s),
                )

        except asyncio.CancelledError:
            stop_event.set()
            raise
        except APIError:
            stop_event.set()
            raise
        except Exception as exc:
            stop_event.set()
            raise APIError(f"Local Chatterbox (MLX) TTS failed: {exc}", retryable=True) from exc
