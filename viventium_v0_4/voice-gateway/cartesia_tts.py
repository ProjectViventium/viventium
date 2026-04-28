# === VIVENTIUM START ===
# Feature: Cartesia Sonic-3 TTS provider for LiveKit Agents
# Added: 2026-01-10
#
# Design:
# - Keep `synthesize()` on Cartesia `/tts/bytes` for full-text, one-request surfaces.
# - Implement native LiveKit `stream()` on Cartesia WebSocket contexts so incremental LLM
#   text can begin speaking immediately without sentence-buffering in LiveKit's StreamAdapter.
# - Use a low explicit `max_buffer_delay_ms` for streaming voice calls to avoid Cartesia's
#   multi-second default token buffer while still allowing minor prosody smoothing.
# === VIVENTIUM END ===

from __future__ import annotations

import asyncio
import base64
import html
import io
import json
import logging
import os
import re
import time
import uuid
import wave
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse, urlunparse

import aiohttp

from livekit.agents import APIError
from livekit.agents.tts import AudioEmitter, ChunkedStream, SynthesizeStream, TTS, TTSCapabilities
from livekit.agents.types import APIConnectOptions, DEFAULT_API_CONNECT_OPTIONS

# === VIVENTIUM START ===
# Feature: Last-mile citation stripping before TTS.
from sse import sanitize_voice_text
# === VIVENTIUM END ===

logger = logging.getLogger("voice-gateway.cartesia_tts")


DEFAULT_URL = "https://api.cartesia.ai/tts/bytes"
DEFAULT_WS_URL = "wss://api.cartesia.ai/tts/websocket"
DEFAULT_VERSION = "2026-03-01"
DEFAULT_MODEL_ID = "sonic-3"
MEGAN_VOICE_ID = "e8e5fffb-252c-436d-b842-8879b84445b6"
LYRA_VOICE_ID = "6ccbfb76-1fc6-48f7-b71d-91ac6298247b"
DEFAULT_VOICE_ID = MEGAN_VOICE_ID
CARTESIA_VOICE_PRESETS: tuple[tuple[str, str], ...] = (
    (MEGAN_VOICE_ID, "Megan"),
    (LYRA_VOICE_ID, "Lyra"),
)
DEFAULT_SAMPLE_RATE = 44100
DEFAULT_NUM_CHANNELS = 1
# === VIVENTIUM START ===
# Feature: Low-latency Cartesia token buffering for live voice.
# Purpose: The docs note a default token buffer that can be multiple seconds for continuations.
# We keep a small explicit delay to start speech quickly while still smoothing micro-fragments.
DEFAULT_MAX_BUFFER_DELAY_MS = 120
# === VIVENTIUM END ===

# === VIVENTIUM START ===
# Feature: Cartesia emotion-tag segmentation + nonverbal normalization
DEFAULT_SEGMENT_SILENCE_MS = 80

_EMOTION_TAG_RE = re.compile(
    r"<emotion\s+value=[\"']?([^\"'>]+)[\"']?\s*>(.*?)</emotion>",
    re.IGNORECASE | re.DOTALL,
)
_EMOTION_SELF_CLOSING_RE = re.compile(r"<emotion\s+value=[\"']?([^\"'>]+)[\"']?\s*/>", re.IGNORECASE)
_SPEAK_TAG_RE = re.compile(r"</?speak[^>]*>", re.IGNORECASE)
# === VIVENTIUM NOTE ===
# Updated 2026-02-22: Exclude Cartesia-supported SSML tags (<break>, <speed>, <volume>, <spell>)
# from generic stripping. These are valid Cartesia Sonic 3 SSML tags that should be preserved
# in the transcript and passed through to the Cartesia API.
_CARTESIA_SSML_TAGS = {"emotion", "break", "speed", "volume", "spell", "speak"}
_GENERIC_TAG_RE = re.compile(r"</?([A-Za-z][A-Za-z0-9]*)\b[^>]*>")
# === VIVENTIUM NOTE ===
_BRACKET_TOKEN_RE = re.compile(r"\[([^\]]+)\]")
_STAGE_TOKEN_ALIASES = {
    # Cartesia docs currently document `[laughter]` as the supported nonverbal token.
    # Accept close laughter variants from model output, but do not synthesize unsupported
    # stage directions into invented speech.
    "laugh": "laughter",
    "laughter": "laughter",
    "giggle": "laughter",
    "chuckle": "laughter",
    "soft laugh": "laughter",
    "gentle laugh": "laughter",
    "quiet laugh": "laughter",
    "nervous laugh": "laughter",
    "awkward laugh": "laughter",
    "light laugh": "laughter",
}

_STAGE_PROMPTS: dict[str, tuple[str, Optional[str]]] = {
    # Cartesia docs: insert `[laughter]` token to produce laughter.
    "laughter": ("[laughter]", "joking/comedic"),
}
# === VIVENTIUM END ===


@dataclass(frozen=True)
class CartesiaConfig:
    api_key: str
    model_id: str = DEFAULT_MODEL_ID
    voice_id: str = DEFAULT_VOICE_ID
    api_url: str = DEFAULT_URL
    ws_url: str = DEFAULT_WS_URL
    api_version: str = DEFAULT_VERSION
    sample_rate: int = DEFAULT_SAMPLE_RATE
    num_channels: int = DEFAULT_NUM_CHANNELS
    speed: float = 1.0
    volume: float = 1.0
    emotion: str = "neutral"
    segment_silence_ms: int = DEFAULT_SEGMENT_SILENCE_MS
    language: str = "en"
    max_buffer_delay_ms: int = DEFAULT_MAX_BUFFER_DELAY_MS


@dataclass(frozen=True)
class EmotionSegment:
    text: str
    emotion: Optional[str] = None
    stage: Optional[str] = None


@dataclass
class StreamingEmotionState:
    current_emotion: Optional[str] = None
    buffer: str = ""


class CartesiaTTS(TTS):
    def __init__(self, *, config: CartesiaConfig) -> None:
        if not config.api_key:
            raise ValueError("CartesiaTTS requires a non-empty api_key")
        ws_url = (config.ws_url or "").strip() or _default_ws_url(config.api_url)
        max_buffer_delay_ms = max(0, int(config.max_buffer_delay_ms))
        super().__init__(
            capabilities=TTSCapabilities(streaming=True),
            sample_rate=int(config.sample_rate),
            num_channels=int(config.num_channels),
        )
        self._config = CartesiaConfig(
            api_key=config.api_key,
            model_id=config.model_id,
            voice_id=config.voice_id,
            api_url=config.api_url,
            ws_url=ws_url,
            api_version=config.api_version,
            sample_rate=config.sample_rate,
            num_channels=config.num_channels,
            speed=config.speed,
            volume=config.volume,
            emotion=config.emotion,
            segment_silence_ms=config.segment_silence_ms,
            language=config.language,
            max_buffer_delay_ms=max_buffer_delay_ms,
        )

    @property
    def provider(self) -> str:
        return "cartesia"

    @property
    def model(self) -> str:
        return self._config.model_id

    def synthesize(
        self, text: str, *, conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS
    ) -> ChunkedStream:
        return _CartesiaChunkedStream(tts=self, input_text=text, conn_options=conn_options)

    def stream(
        self, *, conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS
    ) -> SynthesizeStream:
        return _CartesiaSynthesizeStream(tts=self, conn_options=conn_options)


# === VIVENTIUM START ===
# Feature: Cartesia text normalization helpers
def _should_debug() -> bool:
    return (os.getenv("VIVENTIUM_VOICE_DEBUG_TTS", "") or "").strip() == "1"


def _default_ws_url(api_url: str) -> str:
    raw = (api_url or "").strip()
    if not raw:
        return DEFAULT_WS_URL
    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        return DEFAULT_WS_URL
    ws_scheme = "wss" if parsed.scheme == "https" else "ws"
    return urlunparse((ws_scheme, parsed.netloc, "/tts/websocket", "", "", ""))


def _strip_non_cartesia_tags(text: str) -> str:
    """Strip HTML/XML tags that are NOT Cartesia-supported SSML tags."""
    def _replace_tag(m: re.Match[str]) -> str:
        tag_name = m.group(1).lower()
        if tag_name in _CARTESIA_SSML_TAGS:
            return m.group(0)  # preserve Cartesia SSML
        return ""
    return _GENERIC_TAG_RE.sub(_replace_tag, text)


def _normalize_nonverbal_tokens(text: str, *, preserve_edge_whitespace: bool = False) -> str:
    text = _strip_non_cartesia_tags(text)

    def _replace(match: re.Match[str]) -> str:
        token = re.sub(r"\s+", " ", match.group(1).strip().lower())
        canonical = _STAGE_TOKEN_ALIASES.get(token)
        if not canonical:
            return ""
        return f"[{canonical}]"

    normalized = _BRACKET_TOKEN_RE.sub(_replace, text)
    normalized = re.sub(r"\s{2,}", " ", normalized).strip()
    if preserve_edge_whitespace and normalized:
        if text[:1].isspace() and not normalized[:1].isspace():
            normalized = " " + normalized
        if text[-1:].isspace() and not normalized[-1:].isspace():
            normalized = normalized + " "
    elif preserve_edge_whitespace and text and text.isspace():
        return " "
    return normalized


def _debug_text(text: str, *, max_len: int = 500) -> str:
    snippet = (text or "").replace("\n", "\\n").replace("\r", "\\r")
    if len(snippet) > max_len:
        return snippet[:max_len] + "..."
    return snippet


def _debug_text_json(text: str) -> str:
    return json.dumps(text or "", ensure_ascii=False)


def _with_emotion_ssml(text: str, emotion: Optional[str]) -> str:
    """
    Preserve LLM-selected Cartesia emotion control in the transcript sent to Cartesia.

    The model chooses the emotion tag in the assistant response. The adapter may split a
    streaming response into provider-safe chunks, so it reattaches that chosen emotion as
    Cartesia SSML while also passing the same value in generation_config.emotion.
    """
    cleaned = text or ""
    value = (emotion or "").strip()
    if not value:
        return cleaned
    if _EMOTION_SELF_CLOSING_RE.match(cleaned.lstrip()) or _EMOTION_WRAPPER_OPEN_RE.match(cleaned.lstrip()):
        return cleaned
    return f'<emotion value="{html.escape(value, quote=True)}"/>{cleaned}'


def _streaming_transcript_for_segment(
    segment: EmotionSegment,
    *,
    default_emotion: str,
) -> tuple[str, str]:
    emotion_from_llm = bool(segment.emotion) and not segment.stage
    if segment.stage:
        stage_prompt = _STAGE_PROMPTS.get(
            segment.stage,
            (f"[{segment.stage}]", None),
        )
        chunk = stage_prompt[0]
        emotion = (stage_prompt[1] or segment.emotion or default_emotion).strip() or "neutral"
    else:
        chunk = _normalize_nonverbal_tokens(
            segment.text,
            preserve_edge_whitespace=True,
        )
        emotion = (segment.emotion or default_emotion).strip() or "neutral"

    if not chunk:
        return "", emotion
    cartesia_transcript = (
        _with_emotion_ssml(chunk, segment.emotion)
        if emotion_from_llm
        else chunk
    )
    return cartesia_transcript, emotion


def _normalize_stage_token(raw: str) -> Optional[str]:
    token = re.sub(r"\s+", " ", raw.strip().lower())
    return _STAGE_TOKEN_ALIASES.get(token)


def _split_stage_segments(text: str, emotion: Optional[str]) -> list[EmotionSegment]:
    segments: list[EmotionSegment] = []
    last_idx = 0
    for match in _BRACKET_TOKEN_RE.finditer(text):
        before = text[last_idx:match.start()]
        if before.strip():
            segments.append(EmotionSegment(text=before, emotion=emotion))
        stage = _normalize_stage_token(match.group(1))
        if stage:
            segments.append(EmotionSegment(text="", emotion=emotion, stage=stage))
        last_idx = match.end()
    tail = text[last_idx:]
    if tail.strip():
        segments.append(EmotionSegment(text=tail, emotion=emotion))
    if not segments:
        segments.append(EmotionSegment(text=text, emotion=emotion))
    return segments


def _split_emotion_segments_with_state(
    text: str, *, initial_emotion: Optional[str] = None
) -> tuple[list[EmotionSegment], Optional[str]]:
    # === VIVENTIUM START ===
    # Feature: Support Cartesia SSML emotion tags (block + self-closing).
    #
    # Cartesia docs primarily show self-closing tags like:
    #   <emotion value="excited"/>Hello there.
    # These act as a state change applying to subsequent text until changed again.
    #
    # We keep backward-compat for our legacy wrapper form:
    #   <emotion value="excited">Hello there.</emotion>
    cleaned = _SPEAK_TAG_RE.sub("", text or "")

    segments: list[EmotionSegment] = []
    cursor = 0
    current_emotion: Optional[str] = initial_emotion

    while cursor < len(cleaned):
        block_match = _EMOTION_TAG_RE.search(cleaned, cursor)
        self_match = _EMOTION_SELF_CLOSING_RE.search(cleaned, cursor)

        next_match = None
        next_kind = ""
        if block_match and self_match:
            if block_match.start() <= self_match.start():
                next_match = block_match
                next_kind = "block"
            else:
                next_match = self_match
                next_kind = "self"
        elif block_match:
            next_match = block_match
            next_kind = "block"
        elif self_match:
            next_match = self_match
            next_kind = "self"
        else:
            break

        if next_match is None:
            break

        before = cleaned[cursor:next_match.start()]
        if before.strip():
            segments.extend(_split_stage_segments(before, current_emotion))

        if next_kind == "self":
            # Emotion state change: applies to subsequent text.
            value = next_match.group(1).strip() if next_match.group(1) else ""
            current_emotion = value or None
            cursor = next_match.end()
            continue

        # Wrapper emotion: applies only to its inner content; does not mutate state.
        emotion = next_match.group(1).strip() if next_match.group(1) else None
        inner = next_match.group(2)
        if inner and inner.strip():
            segments.extend(_split_stage_segments(inner, emotion))
        cursor = next_match.end()

    tail = cleaned[cursor:]
    if tail.strip():
        segments.extend(_split_stage_segments(tail, current_emotion))

    if not segments:
        segments.extend(_split_stage_segments(cleaned, current_emotion))

    return segments, current_emotion
    # === VIVENTIUM END ===


def _split_emotion_segments(text: str) -> list[EmotionSegment]:
    segments, _ = _split_emotion_segments_with_state(text, initial_emotion=None)
    return segments


_EMOTION_WRAPPER_OPEN_RE = re.compile(
    r"<emotion\s+value=[\"']?([^\"'>]+)[\"']?\s*>",
    re.IGNORECASE,
)


def _partition_streamable_emotion_text(text: str) -> tuple[str, str]:
    if not text:
        return "", ""

    safe_len = len(text)
    last_lt = text.rfind("<")
    last_gt = text.rfind(">")
    if last_lt > last_gt:
        safe_len = last_lt

    unmatched_wrapper_start: Optional[int] = None
    safe_text = text[:safe_len]
    for match in _EMOTION_WRAPPER_OPEN_RE.finditer(safe_text):
        if safe_text.find("</emotion>", match.end()) == -1:
            unmatched_wrapper_start = match.start()
            break

    if unmatched_wrapper_start is not None:
        safe_len = min(safe_len, unmatched_wrapper_start)

    return text[:safe_len], text[safe_len:]


def _normalize_streaming_emotion_tail(text: str) -> str:
    if not text:
        return ""

    tail = text
    last_lt = tail.rfind("<")
    last_gt = tail.rfind(">")
    if last_lt > last_gt:
        tail = tail[:last_lt]

    tail = re.sub(
        r"<emotion\s+value=[\"']?([^\"'>]+)[\"']?\s*>",
        lambda match: f'<emotion value="{match.group(1)}"/>',
        tail,
        flags=re.IGNORECASE,
    )
    tail = tail.replace("</emotion>", "")
    tail = _SPEAK_TAG_RE.sub("", tail)
    return tail


def _consume_streaming_emotion_chunk(
    state: StreamingEmotionState, chunk: str, *, final: bool = False
) -> list[EmotionSegment]:
    if chunk:
        state.buffer += chunk

    if final:
        streamable, pending = _partition_streamable_emotion_text(state.buffer)
        process_text = streamable + _normalize_streaming_emotion_tail(pending)
        state.buffer = ""
    else:
        process_text, state.buffer = _partition_streamable_emotion_text(state.buffer)

    if not process_text:
        return []

    segments, current_emotion = _split_emotion_segments_with_state(
        process_text,
        initial_emotion=state.current_emotion,
    )
    state.current_emotion = current_emotion
    return segments
# === VIVENTIUM END ===


def _build_ws_generation_request(
    *,
    cfg: CartesiaConfig,
    context_id: str,
    transcript: str,
    continue_generation: bool,
    emotion: Optional[str] = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "model_id": cfg.model_id,
        "transcript": transcript,
        "voice": {"mode": "id", "id": cfg.voice_id},
        "output_format": {
            "container": "raw",
            "encoding": "pcm_s16le",
            "sample_rate": int(cfg.sample_rate),
        },
        "language": cfg.language or "en",
        "generation_config": {
            "speed": float(cfg.speed),
            "volume": float(cfg.volume),
            "emotion": ((emotion or cfg.emotion or "neutral").strip() or "neutral"),
        },
        "context_id": context_id,
        "continue": bool(continue_generation),
    }
    if int(cfg.max_buffer_delay_ms) > 0:
        payload["max_buffer_delay_ms"] = int(cfg.max_buffer_delay_ms)
    return payload


def _extract_ws_audio_chunk(event: dict[str, object]) -> Optional[bytes]:
    if not isinstance(event, dict):
        return None
    if event.get("type") != "chunk":
        return None
    raw = event.get("data")
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return base64.b64decode(raw, validate=False)
    except Exception:
        return None


def _is_ws_done(event: dict[str, object], *, context_id: str) -> bool:
    if not isinstance(event, dict):
        return False
    if event.get("type") != "done":
        return False
    event_context_id = event.get("context_id")
    if isinstance(event_context_id, str) and event_context_id and event_context_id != context_id:
        return False
    return True


def _ws_api_error(event: dict[str, object]) -> APIError:
    status_code = -1
    raw_status = event.get("status_code")
    if isinstance(raw_status, int):
        status_code = raw_status
    elif isinstance(raw_status, str):
        try:
            status_code = int(raw_status)
        except ValueError:
            status_code = -1
    retryable = status_code < 0 or status_code >= 500 or status_code == 429
    return APIError(
        f"Cartesia WebSocket TTS failed ({status_code if status_code >= 0 else 'unknown'})",
        body=event,
        retryable=retryable,
    )


class _CartesiaChunkedStream(ChunkedStream):
    async def _run(self, output_emitter: AudioEmitter) -> None:
        tts: CartesiaTTS = self._tts  # type: ignore[assignment]
        cfg = tts._config

        # === VIVENTIUM START ===
        # Feature: Last-mile citation stripping before TTS synthesis.
        input_text = sanitize_voice_text(self._input_text or "")
        input_text = input_text.strip()
        # === VIVENTIUM END ===
        if not input_text:
            return

        # === VIVENTIUM START ===
        # Feature: Split <emotion> segments + normalize nonverbal tokens before synthesis.
        segments = _split_emotion_segments(input_text)
        if _should_debug():
            logger.info(
                "Cartesia normalize: segments=%s",
                [
                    (seg.emotion or "default", seg.stage or "speech", seg.text.strip()[:120])
                    for seg in segments
                ],
            )
        # === VIVENTIUM END ===

        request_id = f"cartesia_{uuid.uuid4().hex[:12]}"
        output_emitter.initialize(
            request_id=request_id,
            sample_rate=tts.sample_rate,
            num_channels=tts.num_channels,
            mime_type="audio/pcm",
            frame_size_ms=200,
            stream=False,
        )

        total_timeout_s = max(120.0, float(self._conn_options.timeout))
        timeout = aiohttp.ClientTimeout(total=total_timeout_s)
        started_at = time.time()

        try:
            headers = {
                "Cartesia-Version": cfg.api_version,
                "X-API-Key": cfg.api_key,
                "Content-Type": "application/json",
            }
            bytes_per_sample = 2
            frame_samples = int(tts.sample_rate * 0.02)
            frame_bytes = frame_samples * bytes_per_sample * tts.num_channels
            silence_frames = int((tts.sample_rate * cfg.segment_silence_ms) / 1000.0)
            silence_bytes = b"\x00" * (silence_frames * bytes_per_sample * tts.num_channels)

            # === VIVENTIUM START ===
            # Feature: Per-segment emotion synthesis + laughter normalization.
            async with aiohttp.ClientSession(timeout=timeout) as session:
                for idx, segment in enumerate(segments):
                    emotion_from_llm = bool(segment.emotion) and not segment.stage
                    if segment.stage:
                        stage_prompt = _STAGE_PROMPTS.get(segment.stage, (f"[{segment.stage}]", None))
                        segment_text = stage_prompt[0]
                        emotion = (stage_prompt[1] or segment.emotion or cfg.emotion).strip() or "neutral"
                    else:
                        segment_text = _normalize_nonverbal_tokens(segment.text)
                        emotion = (segment.emotion or cfg.emotion).strip() or "neutral"
                    if not segment_text:
                        continue
                    cartesia_transcript = (
                        _with_emotion_ssml(segment_text, segment.emotion)
                        if emotion_from_llm
                        else segment_text
                    )
                    payload = {
                        "model_id": cfg.model_id,
                        "transcript": cartesia_transcript,
                        "voice": {"mode": "id", "id": cfg.voice_id},
                        "output_format": {
                            "container": "wav",
                            "encoding": "pcm_s16le",
                            "sample_rate": int(cfg.sample_rate),
                        },
                        "language": cfg.language or "en",
                        "generation_config": {
                            "speed": float(cfg.speed),
                            "volume": float(cfg.volume),
                            "emotion": emotion,
                        },
                    }

                    if _should_debug():
                        logger.info(
                            "[VoiceMarkup] cartesia_bytes_request segment=%s model=%s voice=%s version=%s emotion=%s transcript_json=%s",
                            idx + 1,
                            cfg.model_id,
                            cfg.voice_id,
                            cfg.api_version,
                            emotion,
                            _debug_text_json(cartesia_transcript),
                        )

                    async with session.post(cfg.api_url, headers=headers, data=json.dumps(payload)) as resp:
                        if resp.status != 200:
                            body = await resp.text()
                            # 402 = credits exhausted, 401/403 = auth errors — retrying won't help.
                            # Only transient errors (5xx, timeouts) are worth retrying.
                            retryable = resp.status >= 500
                            raise APIError(
                                f"Cartesia TTS failed ({resp.status})",
                                body={"status": resp.status, "body": body},
                                retryable=retryable,
                            )
                        wav_bytes = await resp.read()

                    pcm_bytes = _wav_to_pcm(
                        wav_bytes,
                        expected_rate=tts.sample_rate,
                        expected_channels=tts.num_channels,
                    )
                    if not pcm_bytes:
                        raise APIError("Cartesia TTS produced no audio", retryable=True)

                    if idx > 0 and silence_bytes:
                        output_emitter.push(silence_bytes)

                    for frame_idx in range(0, len(pcm_bytes), frame_bytes):
                        output_emitter.push(pcm_bytes[frame_idx: frame_idx + frame_bytes])
            # === VIVENTIUM END ===

            if time.time() - started_at > total_timeout_s:
                raise APIError("Cartesia TTS timed out", retryable=True)

        except APIError:
            raise
        except Exception as exc:
            raise APIError(f"Cartesia TTS failed: {exc}", retryable=True) from exc


class _CartesiaSynthesizeStream(SynthesizeStream):
    async def _run(self, output_emitter: AudioEmitter) -> None:
        tts: CartesiaTTS = self._tts  # type: ignore[assignment]
        cfg = tts._config

        request_id = f"cartesia_{uuid.uuid4().hex[:12]}"
        context_id = request_id
        output_emitter.initialize(
            request_id=request_id,
            sample_rate=tts.sample_rate,
            num_channels=tts.num_channels,
            mime_type="audio/pcm",
            frame_size_ms=200,
            stream=True,
        )
        output_emitter.start_segment(segment_id=context_id)

        total_timeout_s = max(120.0, float(self._conn_options.timeout))
        timeout = aiohttp.ClientTimeout(total=total_timeout_s)
        input_ready = asyncio.Event()
        sent_any_input = False
        context_done = False

        headers = {
            "Cartesia-Version": cfg.api_version,
            "X-API-Key": cfg.api_key,
        }

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.ws_connect(cfg.ws_url, headers=headers, heartbeat=20) as ws:
                emotion_state = StreamingEmotionState()
                sent_transcripts: list[str] = []
                sent_input_count = 0

                async def _emit_segment(segment: EmotionSegment) -> None:
                    nonlocal sent_any_input, sent_input_count

                    cartesia_transcript, emotion = _streaming_transcript_for_segment(
                        segment,
                        default_emotion=cfg.emotion,
                    )
                    if not cartesia_transcript:
                        return

                    sent_input_count += 1
                    sent_transcripts.append(cartesia_transcript)
                    if _should_debug():
                        logger.info(
                            "[VoiceMarkup] cartesia_ws_request index=%s model=%s voice=%s version=%s continue=true emotion=%s buffer_ms=%s transcript_json=%s joined_transcript_json=%s",
                            sent_input_count,
                            cfg.model_id,
                            cfg.voice_id,
                            cfg.api_version,
                            emotion,
                            cfg.max_buffer_delay_ms,
                            _debug_text_json(cartesia_transcript),
                            _debug_text_json("".join(sent_transcripts)),
                        )

                    await ws.send_str(
                        json.dumps(
                            _build_ws_generation_request(
                                cfg=cfg,
                                context_id=context_id,
                                transcript=cartesia_transcript,
                                continue_generation=True,
                                emotion=emotion,
                            )
                        )
                    )
                    sent_any_input = True
                    self._mark_started()
                    input_ready.set()

                async def _input_task() -> None:
                    async for data in self._input_ch:
                        if isinstance(data, self._FlushSentinel):
                            continue
                        chunk = sanitize_voice_text(data or "")
                        if not chunk:
                            continue

                        for segment in _consume_streaming_emotion_chunk(
                            emotion_state,
                            chunk,
                            final=False,
                        ):
                            await _emit_segment(segment)

                    for segment in _consume_streaming_emotion_chunk(
                        emotion_state,
                        "",
                        final=True,
                    ):
                        await _emit_segment(segment)

                    input_ready.set()
                    if not sent_any_input:
                        return

                    if _should_debug():
                        logger.info(
                            "[VoiceMarkup] cartesia_ws_finalize model=%s voice=%s version=%s continue=false transcript_json=%s joined_transcript_json=%s",
                            cfg.model_id,
                            cfg.voice_id,
                            cfg.api_version,
                            _debug_text_json(""),
                            _debug_text_json("".join(sent_transcripts)),
                        )

                    await ws.send_str(
                        json.dumps(
                            _build_ws_generation_request(
                                cfg=cfg,
                                context_id=context_id,
                                transcript="",
                                continue_generation=False,
                            )
                        )
                    )

                async def _recv_task() -> None:
                    nonlocal context_done
                    await input_ready.wait()
                    if not sent_any_input:
                        return

                    while True:
                        msg = await ws.receive(timeout=total_timeout_s)
                        if msg.type in (
                            aiohttp.WSMsgType.CLOSED,
                            aiohttp.WSMsgType.CLOSE,
                            aiohttp.WSMsgType.CLOSING,
                        ):
                            raise APIError("Cartesia WebSocket closed unexpectedly", retryable=True)
                        if msg.type == aiohttp.WSMsgType.ERROR:
                            raise APIError("Cartesia WebSocket errored unexpectedly", retryable=True)
                        if msg.type != aiohttp.WSMsgType.TEXT:
                            continue

                        try:
                            event = json.loads(msg.data)
                        except Exception as exc:
                            raise APIError(
                                f"Cartesia WebSocket returned invalid JSON: {exc}",
                                retryable=True,
                            ) from exc

                        if isinstance(event, dict) and event.get("type") == "error":
                            raise _ws_api_error(event)

                        audio = _extract_ws_audio_chunk(event) if isinstance(event, dict) else None
                        if audio:
                            output_emitter.push(audio)
                            continue

                        if isinstance(event, dict) and _is_ws_done(event, context_id=context_id):
                            context_done = True
                            return

                tasks = [
                    asyncio.create_task(_input_task(), name="cartesia_tts_input"),
                    asyncio.create_task(_recv_task(), name="cartesia_tts_recv"),
                ]
                try:
                    await asyncio.gather(*tasks)
                except asyncio.CancelledError:
                    if sent_any_input and not context_done:
                        try:
                            await ws.send_str(json.dumps({"context_id": context_id, "cancel": True}))
                        except Exception:
                            logger.debug("Cartesia WebSocket cancel failed", exc_info=True)
                    raise
                finally:
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)


def _wav_to_pcm(wav_bytes: bytes, *, expected_rate: int, expected_channels: int) -> Optional[bytes]:
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as reader:
            sample_rate = reader.getframerate()
            channels = reader.getnchannels()
            sample_width = reader.getsampwidth()
            if sample_width != 2:
                raise ValueError(f"Unsupported sample width: {sample_width} bytes")
            if sample_rate != expected_rate or channels != expected_channels:
                logger.warning(
                    "Cartesia WAV format mismatch (rate=%s, channels=%s), expected rate=%s channels=%s",
                    sample_rate,
                    channels,
                    expected_rate,
                    expected_channels,
                )
            return reader.readframes(reader.getnframes())
    except Exception as exc:
        logger.warning("Failed to decode Cartesia WAV: %s", exc)
        return None
