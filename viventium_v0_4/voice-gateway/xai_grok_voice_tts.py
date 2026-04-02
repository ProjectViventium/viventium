# === VIVENTIUM START ===
# Feature: xAI Grok Voice (Voice Agent API) - TTS provider for LiveKit Agents
# Added: 2026-01-09
#
# Why:
# - Users want a first-class voice option matching Grok's voice styles (e.g., "Eve").
# - We keep LibreChat as the "brain" (memories + background cortices), but allow swapping the
#   *spoken* voice output provider.
#
# Evidence (xAI docs):
# - WebSocket endpoint: `wss://api.x.ai/v1/realtime`
# - Voices: Ara, Rex, Sal, Eve, Leo
# - Session config uses `session.update` with `voice` and `audio.*.format` (pcm/pcmu/pcma)
#   See: https://docs.x.ai/docs/guides/voice/agent
#
# Design:
# - Implement LiveKit Agents `TTS.synthesize()` using xAI realtime voice WebSocket.
# - We use "manual text turn" by setting `turn_detection.type = null` and sending:
#     1) session.update
#     2) conversation.item.create (user text)
#     3) response.create
#   Then we stream `response.output_audio.delta` events (base64 PCM) into LiveKit AudioEmitter.
#
# NOTE:
# - The Grok Voice Agent API is a *conversational* voice model, NOT traditional TTS.
# - We give it "voice actor" instructions to perform text expressively.
# - Emotion markers like [laugh], [sigh], [whisper] are treated as stage directions.
# - The model naturally adds micro-pauses, breathy texture, and emotional inflections.
# === VIVENTIUM END ===

from __future__ import annotations

import base64
import json
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any, Optional

import aiohttp

from livekit.agents import APIError
from livekit.agents.tts import AudioEmitter, ChunkedStream, TTS, TTSCapabilities
from livekit.agents.types import APIConnectOptions, DEFAULT_API_CONNECT_OPTIONS

logger = logging.getLogger("voice-gateway.xai_voice")


DEFAULT_WSS_URL = "wss://api.x.ai/v1/realtime"
DEFAULT_VOICE = "Eve"
DEFAULT_SAMPLE_RATE = 24000
DEFAULT_NUM_CHANNELS = 1


def _default_instructions() -> str:
    # Instructions for natural, expressive voice performance.
    # Key insight: xAI Grok is a conversational voice model, NOT a traditional TTS.
    # We give it "voice actor" instructions to perform text expressively.
    return (
        "You are a skilled voice actor performing a script. Your job is to bring text to life "
        "with natural, expressive speech.\n\n"
        "CRITICAL RULES:\n"
        "1. When you receive text, SPEAK IT ALOUD exactly as written - this is your script.\n"
        "2. Emotion markers in [brackets] are STAGE DIRECTIONS - perform them, don't say them:\n"
        "   - [laugh] → actually laugh naturally\n"
        "   - [sigh] → actually sigh\n"
        "   - [whisper] → whisper the next part\n"
        "   - [gasp] → gasp audibly\n"
        "   - [chuckle] → chuckle warmly\n"
        "   - [giggle] → giggle playfully\n"
        "   - [hmm] → make a thinking sound\n"
        "   - [groan] → groan\n"
        "3. Add natural micro-pauses, breathy texture, and emotional inflections.\n"
        "4. Match the energy: playful text → playful voice, serious → serious, flirty → flirty.\n"
        "5. Do NOT add extra words, commentary, or ask questions - just perform the script.\n"
        "6. Do NOT say 'Here is the text' or similar - just speak the content directly.\n\n"
        "Now perform the following script:"
    )


@dataclass(frozen=True)
class XaiGrokVoiceConfig:
    api_key: str
    voice: str = DEFAULT_VOICE
    wss_url: str = DEFAULT_WSS_URL
    sample_rate: int = DEFAULT_SAMPLE_RATE
    num_channels: int = DEFAULT_NUM_CHANNELS
    instructions: str = ""


def build_session_update(cfg: XaiGrokVoiceConfig) -> dict[str, Any]:
    return {
        "type": "session.update",
        "session": {
            "instructions": cfg.instructions or _default_instructions(),
            "voice": cfg.voice or DEFAULT_VOICE,
            # Per xAI docs: null for manual text turns
            "turn_detection": {"type": None},
            "audio": {
                "input": {"format": {"type": "audio/pcm", "rate": int(cfg.sample_rate)}},
                "output": {"format": {"type": "audio/pcm", "rate": int(cfg.sample_rate)}},
            },
        },
    }


def build_conversation_item_create(text: str) -> dict[str, Any]:
    # Frame the text as a script for the voice actor to perform.
    # No <speak> wrapper - the instructions already establish context.
    return {
        "type": "conversation.item.create",
        "previous_item_id": "",
        "item": {
            "type": "message",
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": text,
                }
            ],
        },
    }


def build_response_create() -> dict[str, Any]:
    return {"type": "response.create"}


def extract_output_audio_delta(event: dict[str, Any]) -> Optional[bytes]:
    """
    Return raw PCM bytes for a `response.output_audio.delta` event, or None.
    """
    if not isinstance(event, dict):
        return None
    if event.get("type") != "response.output_audio.delta":
        return None
    delta = event.get("delta")
    if not isinstance(delta, str) or not delta:
        return None
    try:
        return base64.b64decode(delta, validate=False)
    except Exception:
        return None


def is_response_done(event: dict[str, Any]) -> bool:
    if not isinstance(event, dict):
        return False
    t = event.get("type")
    return t in {"response.done", "response.output_audio.done"}


class XaiGrokVoiceTTS(TTS):
    """
    xAI Grok Voice Agent API-backed TTS for LiveKit Agents.
    """

    def __init__(self, *, config: XaiGrokVoiceConfig) -> None:
        if not config.api_key:
            raise ValueError("XaiGrokVoiceTTS requires a non-empty api_key")
        super().__init__(
            capabilities=TTSCapabilities(streaming=False),
            sample_rate=int(config.sample_rate),
            num_channels=int(config.num_channels),
        )
        self._config = config

    @property
    def provider(self) -> str:
        return "xai"

    @property
    def model(self) -> str:
        return "grok-voice-agent"

    def synthesize(
        self, text: str, *, conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS
    ) -> ChunkedStream:
        return _XaiGrokVoiceChunkedStream(tts=self, input_text=text, conn_options=conn_options)


class _XaiGrokVoiceChunkedStream(ChunkedStream):
    async def _run(self, output_emitter: AudioEmitter) -> None:
        tts: XaiGrokVoiceTTS = self._tts  # type: ignore[assignment]
        cfg = tts._config

        input_text = (self._input_text or "").strip()
        if not input_text:
            return

        request_id = f"xai_{uuid.uuid4().hex[:12]}"
        output_emitter.initialize(
            request_id=request_id,
            sample_rate=tts.sample_rate,
            num_channels=tts.num_channels,
            mime_type="audio/pcm",
            frame_size_ms=200,
            stream=False,
        )

        headers = {
            "Authorization": f"Bearer {cfg.api_key}",
        }

        # LiveKit's default APIConnectOptions.timeout is conservative (10s).
        # Voice synthesis can legitimately take longer for multi-sentence responses,
        # so we enforce a higher minimum to avoid premature aborts.
        total_timeout_s = max(120.0, float(self._conn_options.timeout))
        timeout = aiohttp.ClientTimeout(total=total_timeout_s)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.ws_connect(cfg.wss_url, headers=headers, heartbeat=20) as ws:
                    # 1) Configure session (voice + audio formats)
                    await ws.send_str(json.dumps(build_session_update(cfg)))

                    # 2) Add user text as a conversation item
                    await ws.send_str(json.dumps(build_conversation_item_create(input_text)))

                    # 3) Request response (audio will stream as deltas)
                    await ws.send_str(json.dumps(build_response_create()))

                    saw_audio = False
                    started_at = time.time()

                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                event = json.loads(msg.data)
                            except Exception:
                                continue

                            # Error events (shape may vary; keep defensive)
                            if isinstance(event, dict) and event.get("type") == "error":
                                raise APIError("xAI realtime error", body=event, retryable=True)

                            audio = extract_output_audio_delta(event) if isinstance(event, dict) else None
                            if audio:
                                saw_audio = True
                                output_emitter.push(audio)
                                continue

                            if isinstance(event, dict) and is_response_done(event):
                                break

                            # Safety: avoid hanging forever if server stops responding
                            if time.time() - started_at > total_timeout_s:
                                raise APIError("xAI realtime TTS timed out", retryable=True)

                        elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                            break

                    if not saw_audio:
                        raise APIError("xAI realtime produced no audio", retryable=True)

        except APIError:
            raise
        except Exception as e:
            raise APIError(f"xAI realtime TTS failed: {e}", retryable=True) from e

