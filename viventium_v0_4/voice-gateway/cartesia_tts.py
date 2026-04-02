# === VIVENTIUM START ===
# Feature: Cartesia Sonic-3 TTS provider for LiveKit Agents
# Added: 2026-01-10
#
# Design:
# - Call Cartesia /tts/bytes to synthesize audio.
# - Request WAV (PCM S16LE) and stream raw PCM frames into LiveKit AudioEmitter.
# === VIVENTIUM END ===

from __future__ import annotations

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

import aiohttp

from livekit.agents import APIError
from livekit.agents.tts import AudioEmitter, ChunkedStream, TTS, TTSCapabilities
from livekit.agents.types import APIConnectOptions, DEFAULT_API_CONNECT_OPTIONS

# === VIVENTIUM START ===
# Feature: Last-mile citation stripping before TTS.
from sse import sanitize_voice_text
# === VIVENTIUM END ===

logger = logging.getLogger("voice-gateway.cartesia_tts")


DEFAULT_URL = "https://api.cartesia.ai/tts/bytes"
DEFAULT_VERSION = "2025-04-16"
DEFAULT_MODEL_ID = "sonic-3"
DEFAULT_VOICE_ID = "e8e5fffb-252c-436d-b842-8879b84445b6"
DEFAULT_SAMPLE_RATE = 44100
DEFAULT_NUM_CHANNELS = 1

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
    # Laughter family
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
    # Sighs / breath
    "sigh": "sigh",
    "gentle sigh": "sigh",
    "soft sigh": "sigh",
    "breath": "breath",
    "breath in": "breath",
    "breath out": "breath",
    "inhale": "breath",
    "exhale": "breath",
    # Other nonverbal
    "gasp": "gasp",
    "hmm": "hmm",
    "hm": "hmm",
}

_STAGE_PROMPTS: dict[str, tuple[str, Optional[str]]] = {
    # Cartesia docs: insert `[laughter]` token to produce laughter.
    "laughter": ("[laughter]", "joking/comedic"),
    "sigh": ("haaah", "sad"),
    "breath": ("hmm", "calm"),
    "gasp": ("ah!", "surprised"),
    "hmm": ("hmm", "contemplative"),
}
# === VIVENTIUM END ===


@dataclass(frozen=True)
class CartesiaConfig:
    api_key: str
    model_id: str = DEFAULT_MODEL_ID
    voice_id: str = DEFAULT_VOICE_ID
    api_url: str = DEFAULT_URL
    api_version: str = DEFAULT_VERSION
    sample_rate: int = DEFAULT_SAMPLE_RATE
    num_channels: int = DEFAULT_NUM_CHANNELS
    speed: float = 1.0
    volume: float = 1.0
    emotion: str = "neutral"
    segment_silence_ms: int = DEFAULT_SEGMENT_SILENCE_MS
    language: str = "en"


@dataclass(frozen=True)
class EmotionSegment:
    text: str
    emotion: Optional[str] = None
    stage: Optional[str] = None


class CartesiaTTS(TTS):
    def __init__(self, *, config: CartesiaConfig) -> None:
        if not config.api_key:
            raise ValueError("CartesiaTTS requires a non-empty api_key")
        super().__init__(
            capabilities=TTSCapabilities(streaming=False),
            sample_rate=int(config.sample_rate),
            num_channels=int(config.num_channels),
        )
        self._config = config

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


# === VIVENTIUM START ===
# Feature: Cartesia text normalization helpers
def _should_debug() -> bool:
    return (os.getenv("VIVENTIUM_VOICE_DEBUG_TTS", "") or "").strip() == "1"


def _strip_non_cartesia_tags(text: str) -> str:
    """Strip HTML/XML tags that are NOT Cartesia-supported SSML tags."""
    def _replace_tag(m: re.Match[str]) -> str:
        tag_name = m.group(1).lower()
        if tag_name in _CARTESIA_SSML_TAGS:
            return m.group(0)  # preserve Cartesia SSML
        return ""
    return _GENERIC_TAG_RE.sub(_replace_tag, text)


def _normalize_nonverbal_tokens(text: str) -> str:
    text = _strip_non_cartesia_tags(text)

    def _replace(match: re.Match[str]) -> str:
        token = re.sub(r"\s+", " ", match.group(1).strip().lower())
        canonical = _STAGE_TOKEN_ALIASES.get(token)
        if not canonical:
            return ""
        return f"[{canonical}]"

    normalized = _BRACKET_TOKEN_RE.sub(_replace, text)
    normalized = re.sub(r"\s{2,}", " ", normalized).strip()
    return normalized


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


def _split_emotion_segments(text: str) -> list[EmotionSegment]:
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
    current_emotion: Optional[str] = None

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

    return segments
    # === VIVENTIUM END ===
# === VIVENTIUM END ===


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
                    if segment.stage:
                        stage_prompt = _STAGE_PROMPTS.get(segment.stage, (f"[{segment.stage}]", None))
                        segment_text = stage_prompt[0]
                        emotion = (stage_prompt[1] or segment.emotion or cfg.emotion).strip() or "neutral"
                    else:
                        segment_text = _normalize_nonverbal_tokens(segment.text)
                        emotion = (segment.emotion or cfg.emotion).strip() or "neutral"
                    if not segment_text:
                        continue
                    payload = {
                        "model_id": cfg.model_id,
                        "transcript": segment_text,
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
                            "Cartesia segment %s emotion=%s text=%s",
                            idx + 1,
                            emotion,
                            segment_text[:200],
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
