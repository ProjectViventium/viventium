# === VIVENTIUM START ===
# Feature: TTS provider fallback wrapper (Cartesia primary, ElevenLabs fallback, etc.)
# Added: 2026-02-06
#
# Purpose:
# - When a primary TTS provider fails at runtime (e.g. Cartesia HTTP 402 / transient errors),
#   automatically try a secondary TTS provider instead of ending the voice call.
# - Keep the AgentSession audio output sample rate stable by resampling fallback audio frames
#   to match the primary provider output settings.
# - Emit a callback when a provider is selected so upstream can reflect the actual provider used
#   (e.g., for LibreChat voice-mode prompt injection / telemetry).
#
# Notes:
# - We implement fallback at the LiveKit `TTS` abstraction boundary to avoid coupling fallback
#   logic into provider-specific implementations.
# - This wrapper is `streaming=False` (ChunkedStream) by design; LiveKit will wrap it with
#   `tts.StreamAdapter` when streaming output is needed.
# === VIVENTIUM END ===

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from typing import Callable, Optional, Sequence

from livekit import rtc
from livekit.agents import APIError
from livekit.agents._exceptions import APIStatusError
from livekit.agents.tts import AudioEmitter, ChunkedStream, TTS, TTSCapabilities
from livekit.agents.types import APIConnectOptions, DEFAULT_API_CONNECT_OPTIONS

# === VIVENTIUM START ===
# Feature: Strip voice control tags for non-expressive TTS providers during fallback.
from sse import strip_voice_control_tags
# === VIVENTIUM END ===

logger = logging.getLogger("voice-gateway.fallback_tts")

ProviderSelectedCallback = Callable[[str, TTS], None]

# === VIVENTIUM START ===
# Feature: Providers whose TTS engines do not support Cartesia SSML/stage markers.
# Text routed to these providers is stripped of emotion tags and bracket markers
# so they are not spoken literally during same-turn fallback.
_NON_EXPRESSIVE_PROVIDERS: frozenset[str] = frozenset({"openai", "elevenlabs"})
# === VIVENTIUM END ===


@dataclass(frozen=True)
class ProviderAttempt:
    label: str
    tts: TTS


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
            capabilities=TTSCapabilities(streaming=False),
            sample_rate=int(primary.tts.sample_rate),
            num_channels=int(primary.tts.num_channels),
        )
        self._attempts = list(attempts)
        self._on_provider_selected = on_provider_selected

    @property
    def provider(self) -> str:
        # Expose the primary provider for default labeling. The actual provider used may
        # switch per request and is reported via `on_provider_selected`.
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

        # === VIVENTIUM START ===
        # Feature: Clear provider error logging (voice id + status/body when available).
        def _safe_json(value: object, *, max_len: int = 500) -> str:
            try:
                s = json.dumps(value, ensure_ascii=True, default=str)
            except Exception:
                s = str(value)
            if len(s) > max_len:
                return s[:max_len] + "..."
            return s

        def _describe_attempt(attempt: ProviderAttempt, exc: BaseException) -> str:
            label = attempt.label

            # Best-effort introspection: LiveKit ElevenLabs plugin stores voice_id in `_opts`.
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
        # === VIVENTIUM END ===

        for attempt in self._attempts:
            try:
                frames = await self._collect_frames(
                    attempt.tts,
                    provider_label=attempt.label,
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
                    # livekit.rtc.AudioFrame.data is a memoryview; AudioEmitter expects raw bytes.
                    output_emitter.push(bytes(frame.data))
                return
            except APIError as exc:
                errors.append((attempt.label, exc))
                # === VIVENTIUM START ===
                attempt_desc = _describe_attempt(attempt, exc)
                # === VIVENTIUM END ===
                logger.warning(
                    "TTS provider attempt failed (%s); trying next fallback if available",
                    attempt_desc,
                    exc_info=exc,
                )
            except Exception as exc:
                errors.append((attempt.label, exc))
                # === VIVENTIUM START ===
                attempt_desc = _describe_attempt(attempt, exc)
                # === VIVENTIUM END ===
                logger.warning(
                    "TTS provider attempt failed (%s); trying next fallback if available",
                    attempt_desc,
                    exc_info=exc,
                )

        summary = "; ".join(f"{label}: {type(exc).__name__}" for label, exc in errors) or "unknown"
        # === VIVENTIUM START ===
        # Feature: Reflect underlying retryability in final error.
        # If all underlying errors are non-retryable (e.g., 402 credits exhausted),
        # the final error should also be non-retryable to avoid unnecessary LiveKit
        # retry loops that waste latency on deterministic failures.
        # Updated: 2026-02-22
        any_retryable = any(
            getattr(exc, "retryable", True) for _, exc in errors
        )
        # === VIVENTIUM END ===
        raise APIError(f"All TTS provider attempts failed ({summary})", retryable=any_retryable)

    async def _collect_frames(
        self,
        tts_impl: TTS,
        *,
        provider_label: str,
        target_rate: int,
        target_channels: int,
    ) -> list[rtc.AudioFrame]:
        """Collect synthesized frames from a provider and resample if needed.

        We buffer provider output before emitting anything to the wrapper stream so that
        a mid-stream provider error cannot leak partial audio to the user.
        """
        # NOTE: The LiveKit SDK retries failed syntheses using conn_options.max_retry.
        # In our wrapper, retries inside a single provider attempt only add latency before we can
        # fall back to the next provider. Force single-shot synth per attempt; LiveKit can still
        # retry the wrapper itself if everything fails.
        conn_options = self._conn_options
        if getattr(conn_options, "max_retry", 0) != 0:
            conn_options = APIConnectOptions(
                max_retry=0,
                retry_interval=float(getattr(conn_options, "retry_interval", 2.0)),
                timeout=float(getattr(conn_options, "timeout", 10.0)),
            )

        # === VIVENTIUM START ===
        # Feature: Strip Cartesia SSML/stage markers before passing text to non-expressive
        # TTS providers. Prevents literal tag reading during same-turn fallback.
        synth_text = self._input_text or ""
        if provider_label in _NON_EXPRESSIVE_PROVIDERS:
            synth_text = strip_voice_control_tags(synth_text)
        # === VIVENTIUM END ===

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
