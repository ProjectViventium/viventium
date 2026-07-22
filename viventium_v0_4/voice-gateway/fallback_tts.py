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
import os
import re
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
        serialized = json.dumps(value, ensure_ascii=False, default=str)
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


def _voice_controls_present(text: str) -> bool:
    """Detect provider-control markup through the owning shared sanitizer.

    Normalize whitespace on the source side because `strip_voice_control_tags` also collapses
    duplicate horizontal whitespace. This keeps the observation structural instead of treating
    ordinary formatting as an emotional rendering control.
    """

    value = text or ""
    normalized = re.sub(r"[ \t]{2,}", " ", value)
    return strip_voice_control_tags(value) != normalized


def _log_voice_rendering_observation(
    attempt: ProviderAttempt,
    *,
    event: str,
    mode: str,
    attempt_index: int,
    attempt_count: int,
    controls_present: Optional[bool],
) -> None:
    """Emit bounded route/rendering metadata without the synthesized text or credentials."""

    policy = "strip" if attempt.sanitize_voice_markup else "preserve"
    if controls_present is None:
        controls_state = "unknown"
        controls_action = "pending"
    elif not controls_present:
        controls_state = "false"
        controls_action = "none"
    else:
        controls_state = "true"
        controls_action = "stripped" if attempt.sanitize_voice_markup else "preserved"
    model = re.sub(r"\s+", "_", str(getattr(attempt.tts, "model", "") or "unknown").strip())[:120]

    logger.info(
        "[VoiceRendering][voice_gateway] event=%s mode=%s provider=%s model=%s role=%s "
        "attempt=%s attempt_count=%s accepts_inline_controls=%s markup_policy=%s "
        "controls_present=%s controls_action=%s",
        event,
        mode,
        attempt.label,
        model,
        "primary" if attempt_index == 0 else "fallback",
        attempt_index + 1,
        attempt_count,
        str(not attempt.sanitize_voice_markup).lower(),
        policy,
        controls_state,
        controls_action,
    )


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


class _StreamingVoiceControlObserver:
    """Observe only whether streamed text contains controls, with bounded retention."""

    def __init__(self, *, max_pending_chars: int = 512) -> None:
        self._max_pending_chars = max(16, int(max_pending_chars))
        self._pending = ""
        self.controls_present = False

    @property
    def pending_chars(self) -> int:
        return len(self._pending)

    def push_text(self, text: str) -> None:
        if self.controls_present or not text:
            return
        candidate = self._pending + text
        safe_end = _safe_markup_prefix_end(candidate)
        if safe_end > 0 and _voice_controls_present(candidate[:safe_end]):
            self.controls_present = True
            self._pending = ""
            return
        self._pending = candidate[safe_end:][-self._max_pending_chars :]

    def finish(self) -> bool:
        if not self.controls_present and self._pending:
            self.controls_present = _voice_controls_present(self._pending)
        self._pending = ""
        return self.controls_present


class _ProviderTextBoundaryNormalizer:
    """
    Final guard for text chunks forwarded to streaming TTS providers.

    LiveKit/provider adapters can receive text in smaller pieces than the LLM-facing buffer emitted.
    Never forward punctuation-only chunks like "." to a provider, because some TTS APIs speak them
    literally as "dot". Keep decimal splits intact.
    """

    def __init__(self) -> None:
        self._last_sent_text = ""
        self._pending_punctuation = ""
        self.last_decision = ""

    @staticmethod
    def _is_orphan_punctuation(text: str) -> bool:
        stripped = (text or "").strip()
        punctuation = ".,!?;:…"
        closers = "\"'”’)]}"
        return (
            bool(stripped)
            and any(ch in punctuation for ch in stripped)
            and all(ch in punctuation or ch in closers for ch in stripped)
        )

    def push_text(self, text: str) -> str:
        self.last_decision = ""
        if not text:
            return ""

        if self._is_orphan_punctuation(text):
            self._pending_punctuation += text.strip()
            self.last_decision = "pending_punctuation_not_forwarded"
            return ""

        text = self._apply_pending_punctuation(text)
        cleaned = self._drop_leading_orphan_punctuation(text)
        if not cleaned or self._is_orphan_punctuation(cleaned):
            self.last_decision = self.last_decision or "orphan_punctuation_not_forwarded"
            return ""

        self._last_sent_text += cleaned
        return cleaned

    def _apply_pending_punctuation(self, text: str) -> str:
        if not self._pending_punctuation:
            return text

        pending = self._pending_punctuation
        self._pending_punctuation = ""
        previous = self._last_sent_text.rstrip()
        next_non_space = text.lstrip()[:1]

        if (
            previous[-1:].isdigit()
            and pending == "."
            and text[:1].isdigit()
        ):
            self.last_decision = "preserved_pending_decimal_point"
            return f"{pending}{text}"

        pending_core = pending.rstrip("\"'”’)]}")

        if pending and all(ch in ",;:" for ch in pending_core):
            self.last_decision = "preserved_pending_clause_punctuation"
            if text[:1].isspace():
                return f"{pending}{text}"
            return f"{pending} {text}" if previous and not previous[-1:].isspace() else f"{pending}{text}"

        if previous and pending and pending_core and all(ch in "?!" for ch in pending_core):
            self.last_decision = "preserved_pending_terminal_prosody"
            if text[:1].isspace():
                return f"{pending}{text}"
            return f"{pending} {text}" if not previous[-1:].isspace() else f"{pending}{text}"

        self.last_decision = "dropped_pending_terminal_punctuation"
        if previous and not previous[-1:].isspace() and next_non_space and not text[:1].isspace():
            return f" {text}"
        return text

    def _drop_leading_orphan_punctuation(self, text: str) -> str:
        if not text or not self._last_sent_text:
            return text

        match = re.match(r"^(\s*)([.,!?;:…]+[\"'”’)\]}]*)(\s*)", text)
        if not match:
            return text

        if not any(ch in ".!?…" for ch in match.group(2)):
            return text

        if self.last_decision == "preserved_pending_terminal_prosody":
            return text

        if any(ch in "?!" for ch in match.group(2)):
            return text

        remaining = text[match.end() :]
        if not remaining:
            return ""

        previous = self._last_sent_text.rstrip()
        if (
            previous[-1:].isdigit()
            and remaining[:1].isdigit()
            and "." in match.group(2)
        ):
            return text

        if not self._last_sent_text[-1:].isspace() and not remaining[:1].isspace():
            self.last_decision = self.last_decision or "dropped_leading_terminal_punctuation"
            return f" {remaining}"
        self.last_decision = self.last_decision or "dropped_leading_terminal_punctuation"
        return remaining


def _tts_payload_logging_enabled() -> bool:
    return (
        (os.getenv("VIVENTIUM_VOICE_DEBUG_TTS", "") or "").strip() == "1"
        or (os.getenv("VIVENTIUM_VOICE_LOG_TTS_INPUTS", "") or "").strip() == "1"
    )


def _tts_class_name(tts_impl: TTS) -> str:
    cls = tts_impl.__class__
    return f"{cls.__module__}.{cls.__name__}"


def _log_tts_input(
    attempt: ProviderAttempt,
    *,
    mode: str,
    stage: str,
    action: str,
    text: str,
    reason: str = "",
    tts_impl: Optional[TTS] = None,
) -> None:
    if not _tts_payload_logging_enabled():
        return

    value = text or ""
    stripped = value.strip()
    logger.info(
        "[VoiceTTSInput] action=%s mode=%s stage=%s provider=%s tts_class=%s chars=%s stripped_chars=%s punctuation_only=%s leading_space=%s trailing_space=%s reason=%s text_json=%s",
        action,
        mode,
        stage,
        attempt.label,
        _tts_class_name(tts_impl or attempt.tts),
        len(value),
        len(stripped),
        _ProviderTextBoundaryNormalizer._is_orphan_punctuation(value),
        bool(value[:1].isspace()),
        bool(value[-1:].isspace()),
        reason,
        _safe_json(value, max_len=2000),
    )


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

        for attempt_index, attempt in enumerate(self._attempts):
            try:
                frames = await self._collect_frames(
                    attempt,
                    target_rate=target_rate,
                    target_channels=target_channels,
                    attempt_index=attempt_index,
                    attempt_count=len(self._attempts),
                )
                if not frames:
                    raise APIError(f"{attempt.label} produced no audio frames")

                if self._on_provider_selected:
                    try:
                        self._on_provider_selected(attempt.label, attempt.tts)
                    except Exception:
                        logger.debug("on_provider_selected callback failed", exc_info=True)

                _log_voice_rendering_observation(
                    attempt,
                    event="selected",
                    mode="synthesize",
                    attempt_index=attempt_index,
                    attempt_count=len(self._attempts),
                    controls_present=_voice_controls_present(self._input_text or ""),
                )

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
        attempt_index: int,
        attempt_count: int,
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
        controls_present = _voice_controls_present(synth_text)
        _log_voice_rendering_observation(
            attempt,
            event="attempt",
            mode="synthesize",
            attempt_index=attempt_index,
            attempt_count=attempt_count,
            controls_present=controls_present,
        )
        if attempt.sanitize_voice_markup:
            synth_text = strip_voice_control_tags(synth_text)

        _log_tts_input(
            attempt,
            mode="synthesize",
            stage="synthesize",
            action="forwarded",
            text=synth_text,
            tts_impl=tts_impl,
        )
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
        attempt_index: int,
        attempt_count: int,
    ):
        stream_tts = _build_streaming_tts(attempt.tts)
        stream = stream_tts.stream(conn_options=conn_options)
        text_transform = _BufferedVoiceMarkupSanitizer() if attempt.sanitize_voice_markup else None
        text_boundary = _ProviderTextBoundaryNormalizer()
        control_observer = _StreamingVoiceControlObserver()
        input_complete = False

        async def _forward_input_task() -> None:
            nonlocal input_complete
            try:
                async for data in input_ch:
                    if isinstance(data, str):
                        raw_text = data
                        control_observer.push_text(raw_text)
                        text = raw_text
                        if text_transform is not None:
                            text = text_transform.push_text(text)
                            if raw_text and not text:
                                _log_tts_input(
                                    attempt,
                                    mode="stream",
                                    stage="markup",
                                    action="suppressed",
                                    text=raw_text,
                                    reason="voice_markup_pending_or_stripped",
                                    tts_impl=stream_tts,
                                )
                        boundary_input = text
                        text = text_boundary.push_text(boundary_input)
                        boundary_reason = text_boundary.last_decision
                        if text:
                            _log_tts_input(
                                attempt,
                                mode="stream",
                                stage="push_text",
                                action="forwarded",
                                text=text,
                                reason=boundary_reason,
                                tts_impl=stream_tts,
                            )
                            stream.push_text(text)
                        elif boundary_input:
                            _log_tts_input(
                                attempt,
                                mode="stream",
                                stage="push_text",
                                action="dropped",
                                text=boundary_input,
                                reason=boundary_reason
                                or "orphan_punctuation_or_empty_after_boundary_normalization",
                                tts_impl=stream_tts,
                            )
                    elif isinstance(data, self._FlushSentinel):
                        if text_transform is not None:
                            flushed = text_transform.flush()
                            boundary_input = flushed
                            flushed = text_boundary.push_text(boundary_input)
                            boundary_reason = text_boundary.last_decision
                            if flushed:
                                _log_tts_input(
                                    attempt,
                                    mode="stream",
                                    stage="flush",
                                    action="forwarded",
                                    text=flushed,
                                    reason=boundary_reason,
                                    tts_impl=stream_tts,
                                )
                                stream.push_text(flushed)
                            elif boundary_input:
                                _log_tts_input(
                                    attempt,
                                    mode="stream",
                                    stage="flush",
                                    action="dropped",
                                    text=boundary_input,
                                    reason=boundary_reason
                                    or "orphan_punctuation_or_empty_after_boundary_normalization",
                                    tts_impl=stream_tts,
                                )
                        stream.flush()
                input_complete = True
            finally:
                if text_transform is not None:
                    tail = text_transform.end()
                    boundary_input = tail
                    tail = text_boundary.push_text(boundary_input)
                    boundary_reason = text_boundary.last_decision
                    if tail:
                        _log_tts_input(
                            attempt,
                            mode="stream",
                            stage="tail",
                            action="forwarded",
                            text=tail,
                            reason=boundary_reason,
                            tts_impl=stream_tts,
                        )
                        stream.push_text(tail)
                    elif boundary_input:
                        _log_tts_input(
                            attempt,
                            mode="stream",
                            stage="tail",
                            action="dropped",
                            text=boundary_input,
                            reason=boundary_reason
                            or "orphan_punctuation_or_empty_after_boundary_normalization",
                            tts_impl=stream_tts,
                        )
                stream.end_input()

        input_task = asyncio.create_task(_forward_input_task(), name="fallback_tts_forward_input")
        try:
            async with stream:
                async for audio in stream:
                    yield audio
        finally:
            await aio.cancel_and_wait(input_task)
            observed_controls = control_observer.finish()
            _log_voice_rendering_observation(
                attempt,
                event="input_complete" if input_complete else "input_interrupted",
                mode="stream",
                attempt_index=attempt_index,
                attempt_count=attempt_count,
                controls_present=observed_controls if input_complete or observed_controls else None,
            )

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
            for attempt_index, attempt in enumerate(self._attempts):
                try:
                    _log_voice_rendering_observation(
                        attempt,
                        event="attempt",
                        mode="stream",
                        attempt_index=attempt_index,
                        attempt_count=len(self._attempts),
                        controls_present=None,
                    )
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
                        attempt_index=attempt_index,
                        attempt_count=len(self._attempts),
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
                    if selected_reported:
                        _log_voice_rendering_observation(
                            attempt,
                            event="selected",
                            mode="stream",
                            attempt_index=attempt_index,
                            attempt_count=len(self._attempts),
                            controls_present=_voice_controls_present("".join(self._pushed_tokens)),
                        )
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
