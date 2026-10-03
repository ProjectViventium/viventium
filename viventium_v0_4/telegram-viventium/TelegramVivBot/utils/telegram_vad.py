# === VIVENTIUM START ===
"""Reuse call VAD to detect speech presence; never crop a whole Telegram note."""
import asyncio
from functools import lru_cache

import numpy as np


class SpeechPresenceError(RuntimeError):
    code = 'speech_presence_unavailable'


@lru_cache(maxsize=1)
def _load_vad(configuration):
    from livekit.plugins import silero
    return silero.VAD.load(**dict(configuration))


async def preload_speech_detector():
    try:
        # The pinned plugin registers on the main thread; only ONNX loading
        # belongs in the worker thread. Each note reuses the resident detector.
        from livekit.plugins import silero  # noqa: F401
        from silero_vad_config import get_silero_vad_kwargs
        configuration = tuple(sorted(get_silero_vad_kwargs().items()))
        return await asyncio.to_thread(_load_vad, configuration)
    except Exception as error:
        raise SpeechPresenceError(SpeechPresenceError.code) from error


async def has_speech(pcm):
    try:
        return await _has_speech(pcm)
    except SpeechPresenceError:
        raise
    except Exception as error:
        raise SpeechPresenceError(SpeechPresenceError.code) from error


async def _has_speech(pcm):
    from livekit import rtc
    from livekit.agents.vad import VADEventType
    vad = await preload_speech_detector()
    stream = vad.stream()

    async def feed():
        for offset in range(0, pcm.size, 1600):
            samples = np.rint(np.clip(pcm[offset:offset + 1600], -1, 1) * 32767).astype('<i2')
            stream.push_frame(rtc.AudioFrame(data=samples.tobytes(), sample_rate=16000,
                                            num_channels=1, samples_per_channel=samples.size))
            await asyncio.sleep(0)
        stream.end_input()

    producer = asyncio.create_task(feed())
    try:
        async for event in stream:
            if event.type == VADEventType.START_OF_SPEECH:
                return True
        await producer
        return False
    finally:
        producer.cancel()
        await asyncio.gather(producer, return_exceptions=True)
        await stream.aclose()
# === VIVENTIUM END ===
