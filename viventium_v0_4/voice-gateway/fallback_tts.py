# === VIVENTIUM START ===
# Feature: TTS provider fallback wrapper (Cartesia primary, ElevenLabs fallback, etc.)
# Added: 2026-02-06
#
# Purpose:
# - When a primary TTS provider fails at runtime (for example Cartesia quota/auth/transient errors),
#   automatically try a secondary provider instead of ending the voice call.
# - Keep the AgentSession audio output sample rate stable by resampling fallback audio frames
#   to match the primary provider output settings.
# - Preserve native streaming whenever the selected provider supports it, instead of downgrading
#   the whole voice route back to sentence-buffered `StreamAdapter` behavior.
# - Emit a callback when a provider is selected so upstream can reflect the actual provider used
#   (for example LibreChat voice-mode prompt injection and route metadata).
#
# Notes:
# - `synthesize()` keeps the original full-buffer fallback semantics so a failed provider cannot
#   leak partial audio and then replay the same utterance from a fallback provider.
# - `stream()` is streaming-first. It uses a provider's native stream when available and falls back
#   to LiveKit `StreamAdapter` only for providers that do not support incremental input natively.
# === VIVENTIUM END ===

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass
from typing import Callable, Optional, Sequence, Union

from livekit import rtc
from livekit.agents import APIError
from livekit.agents._exceptions import APIStatusError
from livekit.agents.tts import (
    AudioEmitter,
    ChunkedStream,
    StreamAdapter,
    SynthesizeStream,
    TTS,
    TTSCapabilities,
)
from livekit.agents.types import APIConnectOptions, DEFAULT_API_CONNECT_OPTIONS, USERDATA_TIMED_TRANSCRIPT
from livekit.agents.utils import aio

# === VIVENTIUM START ===
# Feature: Strip voice control tags for non-expressive TTS providers during fallback.
from sse import strip_voice_control_tags
# === VIVENTIUM END ===

logger = logging.getLogger("voice-gateway.fallback_tts")

ProviderSelectedCallback = Callable[[str, TTS], None]


@dataclass(frozen=True)
class ProviderAttempt:
    label: str
    tts: TTS
    sanitize_voice_markup: bool = False


def _safe_json(value: object, *, max_len: int = 500) -> str:
    try:
        serialized = json.dumps(value, ensure_ascii=True, default=str)
    except Exception:
        serialized = str(value)
    if len(serialized) > max_len:
        return serialized[:max_len] + "..."
    return serialized


def _describe_attempt(attempt: ProviderAttempt, exc: BaseException) -> str:
    label = attempt.label

    voice_id = ""
    try:
        opts = getattr(attempt.tts, "_opts", None)
        raw_voice_id = getattr(opts, "voice_id", None)
        if isinstance(raw_voice_id, str) and raw_voice_id.strip():
            voice_id = raw_voice_id.strip()
    except Exception:
        voice_id = ""

    parts: list[str] = [label]
    if voice_id:
        parts.append(f"voice_id={voice_id}")

    if isinstance(exc, APIStatusError):
        if getattr(exc, "status_code", -1) != -1:
            parts.append(f"status_code={exc.status_code}")
        body = getattr(exc, "body", None)
        if body is not None:
            parts.append(f"body={_safe_json(body)}")

    return " ".join(parts)


def _safe_markup_prefix_end(text: str) -> int:
    """
    Return the prefix length that is safe to sanitize without cutting through a structural token.

    We buffer incomplete `<...` and `[...]` regions until they close so shared voice-control
    sanitization can run on complete text only.
    """

    tag_start: Optional[int] = None
    bracket_start: Optional[int] = None

    for index, ch in enumerate(text):
        if tag_start is None and bracket_start is None:
            if ch == "<":
                tag_start = index
            elif ch == "[":
                bracket_start = index
            continue

        if tag_start is not None:
            if ch == ">":
                tag_start = None
            continue

        if bracket_start is not None and ch == "]":
            bracket_start = None

    safe_end = len(text)
    if tag_start is not None:
        safe_end = min(safe_end, tag_start)
    if bracket_start is not None:
        safe_end = min(safe_end, bracket_start)
    return safe_end


class _BufferedVoiceMarkupSanitizer:
    """
    Apply shared voice-control sanitization to streaming text without hardcoded token vocabularies.

    The wrapper buffers unfinished structural tokens and only sanitizes complete text through the
    owning shared sanitizer from `sse.py`.
    """

    def __init__(self) -> None:
        self._buffer = ""

    def push_text(self, text: str) -> str:
        if text:
            self._buffer += text
        return self._drain(final=False)

    def flush(self) -> str:
        return self._drain(final=False)

    def end(self) -> str:
        return self._drain(final=True)

    def _drain(self, *, final: bool) -> str:
        if not self._buffer:
            return ""

        safe_end = len(self._buffer) if final else _safe_markup_prefix_end(self._buffer)
        if safe_end <= 0:
            return ""

        safe_text = self._buffer[:safe_end]
        self._buffer = self._buffer[safe_end:]
        return strip_voice_control_tags(safe_text)


def _build_streaming_tts(tts_impl: TTS) -> TTS:
    if tts_impl.capabilities.streaming:
        return tts_impl
    return StreamAdapter(tts=tts_impl)


class FallbackTTS(TTS):
    def __init__(
        self,
        *,
        attempts: Sequence[ProviderAttempt],
        on_provider_selected: Optional[ProviderSelectedCallback] = None,
    ) -> None:
        if not attempts:
            raise ValueError("FallbackTTS requires at least one ProviderAttempt")
        primary = attempts[0]
        super().__init__(
            capabilities=TTSCapabilities(streaming=True),
            sample_rate=int(primary.tts.sample_rate),
            num_channels=int(primary.tts.num_channels),
        )
        self._attempts = list(attempts)
        self._on_provider_selected = on_provider_selected

    @property
    def provider(self) -> str:
        return self._attempts[0].tts.provider

    @property
    def model(self) -> str:
        return self._attempts[0].tts.model

    def synthesize(
        self, text: str, *, conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS
    ) -> ChunkedStream:
        return _FallbackChunkedStream(
            tts=self,
            input_text=text,
            conn_options=conn_options,
            attempts=self._attempts,
            on_provider_selected=self._on_provider_selected,
        )

    def stream(
        self, *, conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS
    ) -> SynthesizeStream:
        return _FallbackSynthesizeStream(
            tts=self,
            conn_options=conn_options,
            attempts=self._attempts,
            on_provider_selected=self._on_provider_selected,
        )


class _FallbackChunkedStream(ChunkedStream):
    def __init__(
        self,
        *,
        tts: TTS,
        input_text: str,
        conn_options: APIConnectOptions,
        attempts: Sequence[ProviderAttempt],
        on_provider_selected: Optional[ProviderSelectedCallback],
    ) -> None:
        super().__init__(tts=tts, input_text=input_text, conn_options=conn_options)
        self._attempts = list(attempts)
        self._on_provider_selected = on_provider_selected

    async def _run(self, output_emitter: AudioEmitter) -> None:
        wrapper_tts: TTS = self._tts  # type: ignore[assignment]
        target_rate = int(wrapper_tts.sample_rate)
        target_channels = int(wrapper_tts.num_channels)

        request_id = f"tts_fallback_{uuid.uuid4().hex[:12]}"
        output_emitter.initialize(
            request_id=request_id,
            sample_rate=target_rate,
            num_channels=target_channels,
            mime_type="audio/pcm",
            frame_size_ms=200,
            stream=False,
        )

        errors: list[tuple[str, BaseException]] = []

        for attempt in self._attempts:
            try:
                frames = await self._collect_frames(
                    attempt,
                    target_rate=target_rate,
                    target_channels=target_channels,
                )
                if not frames:
                    raise APIError(f"{attempt.label} produced no audio frames")

                if self._on_provider_selected:
                    try:
                        self._on_provider_selected(attempt.label, attempt.tts)
                    except Exception:
                        logger.debug("on_provider_selected callback failed", exc_info=True)

                for frame in frames:
                    output_emitter.push(bytes(frame.data))
                return
            except APIError as exc:
                errors.append((attempt.label, exc))
                logger.warning(
                    "TTS provider attempt failed (%s); trying next fallback if available",
                    _describe_attempt(attempt, exc),
                    exc_info=exc,
                )
            except Exception as exc:
                errors.append((attempt.label, exc))
                logger.warning(
                    "TTS provider attempt failed (%s); trying next fallback if available",
                    _describe_attempt(attempt, exc),
                    exc_info=exc,
                )

        summary = "; ".join(f"{label}: {type(exc).__name__}" for label, exc in errors) or "unknown"
        any_retryable = any(getattr(exc, "retryable", True) for _, exc in errors)
        raise APIError(f"All TTS provider attempts failed ({summary})", retryable=any_retryable)

    async def _collect_frames(
        self,
        attempt: ProviderAttempt,
        *,
        target_rate: int,
        target_channels: int,
    ) -> list[rtc.AudioFrame]:
        tts_impl = attempt.tts
        conn_options = self._conn_options
        if getattr(conn_options, "max_retry", 0) != 0:
            conn_options = APIConnectOptions(
                max_retry=0,
                retry_interval=float(getattr(conn_options, "retry_interval", 2.0)),
                timeout=float(getattr(conn_options, "timeout", 10.0)),
            )

        synth_text = self._input_text or ""
        if attempt.sanitize_voice_markup:
            synth_text = strip_voice_control_tags(synth_text)

        stream = tts_impl.synthesize(synth_text, conn_options=conn_options)
        frames: list[rtc.AudioFrame] = []
        async with stream:
            async for ev in stream:
                if not hasattr(ev, "frame"):
                    continue
                frames.append(ev.frame)

        if not frames:
            return []

        src_rate = int(frames[0].sample_rate)
        src_channels = int(frames[0].num_channels)

        if src_channels != target_channels:
            raise APIError(
                f"TTS channel mismatch: got {src_channels}, expected {target_channels}",
                retryable=False,
            )

        if src_rate == target_rate and src_channels == target_channels:
            return frames

        resampler = rtc.AudioResampler(
            input_rate=src_rate,
            output_rate=target_rate,
            num_channels=src_channels,
        )
        out: list[rtc.AudioFrame] = []
        for frame in frames:
            out.extend(resampler.push(frame))
        out.extend(resampler.flush())
        return out


class _FallbackSynthesizeStream(SynthesizeStream):
    def __init__(
        self,
        *,
        tts: TTS,
        conn_options: APIConnectOptions,
        attempts: Sequence[ProviderAttempt],
        on_provider_selected: Optional[ProviderSelectedCallback],
    ) -> None:
        super().__init__(tts=tts, conn_options=conn_options)
        self._attempts = list(attempts)
        self._on_provider_selected = on_provider_selected
        self._pushed_tokens: list[str] = []

    async def _try_synthesize(
        self,
        *,
        attempt: ProviderAttempt,
        input_ch: aio.ChanReceiver[Union[str, SynthesizeStream._FlushSentinel]],
        conn_options: APIConnectOptions,
    ):
        stream_tts = _build_streaming_tts(attempt.tts)
        stream = stream_tts.stream(conn_options=conn_options)
        text_transform = _BufferedVoiceMarkupSanitizer() if attempt.sanitize_voice_markup else None

        async def _forward_input_task() -> None:
            try:
                async for data in input_ch:
                    if isinstance(data, str):
                        text = data
                        if text_transform is not None:
                            text = text_transform.push_text(text)
                        if text:
                            stream.push_text(text)
                    elif isinstance(data, self._FlushSentinel):
                        if text_transform is not None:
                            flushed = text_transform.flush()
                            if flushed:
                                stream.push_text(flushed)
                        stream.flush()
            finally:
                if text_transform is not None:
                    tail = text_transform.end()
                    if tail:
                        stream.push_text(tail)
                stream.end_input()

        input_task = asyncio.create_task(_forward_input_task(), name="fallback_tts_forward_input")
        try:
            async with stream:
                async for audio in stream:
                    yield audio
        finally:
            await aio.cancel_and_wait(input_task)

    async def _run(self, output_emitter: AudioEmitter) -> None:
        wrapper_tts: TTS = self._tts  # type: ignore[assignment]
        target_rate = int(wrapper_tts.sample_rate)
        target_channels = int(wrapper_tts.num_channels)
        request_id = f"tts_fallback_stream_{uuid.uuid4().hex[:12]}"
        errors: list[tuple[str, BaseException]] = []
        new_input_ch: aio.Chan[Union[str, SynthesizeStream._FlushSentinel]] | None = None

        output_emitter.initialize(
            request_id=request_id,
            sample_rate=target_rate,
            num_channels=target_channels,
            mime_type="audio/pcm",
            frame_size_ms=200,
            stream=True,
        )
        output_emitter.start_segment(segment_id=request_id)

        async def _forward_input_task() -> None:
            nonlocal new_input_ch
            async for data in self._input_ch:
                if isinstance(data, str) and data:
                    self._pushed_tokens.append(data)
                if new_input_ch is not None:
                    new_input_ch.send_nowait(data)
            if new_input_ch is not None:
                new_input_ch.close()

        input_task = asyncio.create_task(_forward_input_task(), name="fallback_tts_capture_input")
        try:
            for attempt in self._attempts:
                try:
                    new_input_ch = aio.Chan[Union[str, SynthesizeStream._FlushSentinel]]()
                    for token in self._pushed_tokens:
                        new_input_ch.send_nowait(token)
                    if input_task.done():
                        new_input_ch.close()

                    conn_options = self._conn_options
                    if getattr(conn_options, "max_retry", 0) != 0:
                        conn_options = APIConnectOptions(
                            max_retry=0,
                            retry_interval=float(getattr(conn_options, "retry_interval", 2.0)),
                            timeout=float(getattr(conn_options, "timeout", 10.0)),
                        )

                    resampler: Optional[rtc.AudioResampler] = None
                    if attempt.tts.sample_rate != target_rate:
                        resampler = rtc.AudioResampler(
                            input_rate=int(attempt.tts.sample_rate),
                            output_rate=target_rate,
                            num_channels=int(attempt.tts.num_channels),
                        )

                    selected_reported = False
                    async for synthesized_audio in self._try_synthesize(
                        attempt=attempt,
                        input_ch=new_input_ch,
                        conn_options=conn_options,
                    ):
                        if not selected_reported and self._on_provider_selected is not None:
                            try:
                                self._on_provider_selected(attempt.label, attempt.tts)
                            except Exception:
                                logger.debug("on_provider_selected callback failed", exc_info=True)
                        selected_reported = True

                        if texts := synthesized_audio.frame.userdata.get(USERDATA_TIMED_TRANSCRIPT):
                            output_emitter.push_timed_transcript(texts)

                        if resampler is not None:
                            for resampled_frame in resampler.push(synthesized_audio.frame):
                                output_emitter.push(resampled_frame.data.tobytes())
                        else:
                            output_emitter.push(synthesized_audio.frame.data.tobytes())

                    if resampler is not None:
                        for resampled_frame in resampler.flush():
                            output_emitter.push(resampled_frame.data.tobytes())
                    return
                except APIError as exc:
                    errors.append((attempt.label, exc))
                    logger.warning(
                        "Streaming TTS provider attempt failed (%s); trying next fallback if available",
                        _describe_attempt(attempt, exc),
                        exc_info=exc,
                    )
                except Exception as exc:
                    errors.append((attempt.label, exc))
                    logger.warning(
                        "Streaming TTS provider attempt failed (%s); trying next fallback if available",
                        _describe_attempt(attempt, exc),
                        exc_info=exc,
                    )

                if output_emitter.pushed_duration() > 0.0:
                    logger.warning(
                        "%s already synthesized partial audio; refusing streaming fallback replay",
                        attempt.label,
                    )
                    return

            summary = "; ".join(f"{label}: {type(exc).__name__}" for label, exc in errors) or "unknown"
            any_retryable = any(getattr(exc, "retryable", True) for _, exc in errors)
            raise APIError(f"All TTS provider attempts failed ({summary})", retryable=any_retryable)
        finally:
            if new_input_ch is not None and not new_input_ch.closed:
                new_input_ch.close()
            await aio.cancel_and_wait(input_task)
