# === VIVENTIUM START ===
"""Execute a Listening selection without changing it or retrying consumed audio."""
import asyncio
import logging
import os
import threading
import time
from collections.abc import Mapping

import numpy as np

logger = logging.getLogger(__name__)


class TelegramSTTError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _report(callback, start, stage, **metadata):
    if callback is not None:
        try:
            callback(stage, (time.monotonic() - start) * 1000, metadata)
        except Exception:
            logger.debug('Listening timing callback failed', exc_info=True)


def _transcribe_local(pcm, variant, cancelled, start, callback):
    import config
    from pywhispercpp.model import Model
    try:
        from ..aient.aient.utils.scripts import (
            _LOCAL_STT_TRANSCRIBE_LOCK, _normalized_local_whisper_language, join_native_segments,
        )
    except ImportError:
        if __package__ != 'utils':
            raise
        from aient.aient.utils.scripts import (
            _LOCAL_STT_TRANSCRIBE_LOCK, _normalized_local_whisper_language, join_native_segments,
        )

    _report(callback, start, 'local_lock_wait_started', requested_variant=variant,
            effective_variant=variant)
    with _LOCAL_STT_TRANSCRIBE_LOCK:
        _report(callback, start, 'local_lock_acquired', requested_variant=variant,
                effective_variant=variant)
        if cancelled.is_set():
            raise TelegramSTTError('cancelled')
        try:
            model_path = config._local_whisper_model_path(variant)
        except (ValueError, RuntimeError) as error:
            raise TelegramSTTError('unsupported_configuration') from error
        if cancelled.is_set():
            raise TelegramSTTError('cancelled')
        # The existing native lock owns both residency and inference. Drop the old
        # model before loading its replacement; never keep a model tuple cache.
        if (getattr(config.local_whisper, 'model_path', None) is None
                or str(config.local_whisper.model_path) != str(model_path)):
            try:
                model_path = config._ensure_local_whisper_model_file(variant)
            except ValueError as error:
                raise TelegramSTTError('unsupported_configuration') from error
            except Exception as error:
                raise TelegramSTTError('provider_unavailable') from error
            if cancelled.is_set():
                raise TelegramSTTError('cancelled')
            config.local_whisper = None
            try:
                config.local_whisper = Model(str(model_path), n_threads=config.LOCAL_WHISPER_THREADS)
            except Exception as error:
                raise TelegramSTTError('provider_unavailable') from error
        _report(callback, start, 'local_model_ready', requested_variant=variant,
                effective_variant=variant)
        if cancelled.is_set():
            raise TelegramSTTError('cancelled')
        segments = config.local_whisper.transcribe(
            pcm, language=_normalized_local_whisper_language(config), translate=False,
            print_realtime=config.LOCAL_WHISPER_VERBOSE,
            n_threads=config.LOCAL_WHISPER_THREADS,
        )
        _report(callback, start, 'local_inference_completed', requested_variant=variant,
                effective_variant=variant)
        return join_native_segments(segments, pcm).strip()


def _transcribe_openai(file_bytes, variant, timeout_s, cancelled, start, callback):
    import requests
    try:
        from ..aient.aient.models.whisper import Whisper
    except ImportError:
        if __package__ != 'utils':
            raise
        from aient.aient.models.whisper import Whisper

    key = (os.environ.get('OPENAI_API_KEY') or '').strip()
    if not key or key == 'user_provided':
        raise TelegramSTTError('provider_auth_missing')
    if cancelled.is_set():
        raise TelegramSTTError('cancelled')
    # Generic API_KEY/BASE_URL may belong to the assistant's Grok provider.
    base_url = (os.environ.get('OPENAI_BASE_URL') or 'https://api.openai.com/v1/').strip()
    try:
        client = Whisper(api_key=key, api_url=base_url, timeout=timeout_s,
                         use_environment_url=False)
    except ValueError as error:
        raise TelegramSTTError('unsupported_configuration') from error
    try:
        _report(callback, start, 'openai_inference_started', requested_variant=variant,
                effective_variant=variant)
        result = client.generate(file_bytes, model=variant, timeout=timeout_s)
        _report(callback, start, 'openai_inference_completed', requested_variant=variant,
                effective_variant=variant)
        return result.strip()
    except requests.exceptions.RequestException as error:
        status = getattr(getattr(error, 'response', None), 'status_code', None)
        code = 'transcription_failed'
        if isinstance(error, requests.exceptions.Timeout):
            code = 'timeout'
        elif isinstance(error, (requests.exceptions.InvalidURL, requests.exceptions.InvalidSchema,
                                requests.exceptions.MissingSchema)):
            code = 'unsupported_configuration'
        elif isinstance(error, requests.exceptions.ConnectionError):
            code = 'provider_temporarily_unavailable'
        elif isinstance(error, requests.exceptions.HTTPError) and isinstance(status, int):
            if status == 401:
                code = 'provider_unauthorized'
            elif status == 403:
                code = 'provider_access_denied'
            elif status == 429:
                code = 'provider_rate_limited'
            elif status in {408, 504}:
                code = 'timeout'
            elif status >= 500:
                code = 'provider_temporarily_unavailable'
            elif status >= 400:
                code = 'provider_request_rejected'
        _report(callback, start, 'openai_inference_failed', requested_variant=variant,
                effective_variant=variant, error_code=code, http_status=status)
        raise TelegramSTTError(code) from error
    finally:
        client.session.close()


async def _transcribe_assemblyai(pcm, variant, start, callback, contextual_keyterms=None):
    import aiohttp
    from livekit import rtc
    from livekit.agents import APIConnectOptions, stt
    from livekit.plugins import assemblyai
    from .stt_env import build_assemblyai_stt_options

    key = (os.environ.get('ASSEMBLYAI_API_KEY') or '').strip()
    if not key:
        raise TelegramSTTError('provider_unavailable')
    try:
        options = build_assemblyai_stt_options(os.environ, contextual_keyterms)
    except ValueError as error:
        raise TelegramSTTError('unsupported_configuration') from error
    # The prerecorded adapter has no LiveKit JobContext; it owns its HTTP session.
    effective = variant
    trace = aiohttp.TraceConfig()

    async def connected(*_):
        _report(callback, start, 'assemblyai_connected', requested_variant=variant,
                effective_variant=effective)

    trace.on_request_end.append(connected)
    async with aiohttp.ClientSession(trace_configs=[trace]) as session:
        engine = assemblyai.STT(api_key=key, model=variant, sample_rate=16000,
                                http_session=session, **options)
        stream = engine.stream(conn_options=APIConnectOptions(max_retry=0))
        effective = engine.model
        _report(callback, start, 'assemblyai_stream_started', requested_variant=variant,
                effective_variant=effective)

        async def feed():
            clock = asyncio.get_running_loop()
            origin = clock.time()
            for offset in range(0, pcm.size, 1600):
                await asyncio.sleep(max(0, origin + offset / 16000 - clock.time()))
                samples = np.rint(np.clip(pcm[offset:offset + 1600], -1, 1) * 32767).astype('<i2')
                stream.push_frame(rtc.AudioFrame(data=samples.tobytes(), sample_rate=16000,
                                                num_channels=1, samples_per_channel=samples.size))
            await asyncio.sleep(max(0, origin + pcm.size / 16000 - clock.time()))
            stream.end_input()
            _report(callback, start, 'assemblyai_input_completed', requested_variant=variant,
                    effective_variant=effective)

        async def receive():
            final = []
            async for event in stream:
                if event.type == stt.SpeechEventType.FINAL_TRANSCRIPT and event.alternatives:
                    text = event.alternatives[0].text.strip()
                    if text:
                        final.append(text)
                    _report(callback, start, 'assemblyai_final_received',
                            requested_variant=variant, effective_variant=effective)
            return ' '.join(final)

        producer = asyncio.create_task(feed())
        consumer = asyncio.create_task(receive())
        try:
            _, text = await asyncio.gather(producer, consumer)
            return text
        finally:
            producer.cancel()
            consumer.cancel()
            await asyncio.gather(producer, consumer, return_exceptions=True)
            await stream.aclose()
            await engine.aclose()


async def transcribe_selected_audio(file_bytes, decoded_audio, selection, timeout_s,
                                    *, timing=None):
    """Use exactly the selected engine. Return a complete transcript or a typed error.

    Local native inference and synchronous HTTP cannot be killed inside a thread.
    Cancelled queued work checks cancellation before loading or running; an active
    local call retains its lock until it returns and cannot deliver a stale result.
    """
    if not isinstance(selection, Mapping):
        raise TelegramSTTError('unsupported_configuration')
    provider, variant = selection.get('provider'), selection.get('variant')
    if (not isinstance(provider, str) or not provider.strip()
            or not isinstance(variant, str) or not variant.strip()):
        raise TelegramSTTError('unsupported_configuration')
    provider, variant = provider.strip(), variant.strip()
    if decoded_audio.no_speech:
        raise TelegramSTTError('no_speech')
    pcm = decoded_audio.pcm
    if not isinstance(pcm, np.ndarray) or pcm.ndim != 1 or not pcm.size:
        raise TelegramSTTError('audio_empty')
    if not np.isfinite(pcm).all():
        raise TelegramSTTError('audio_nonfinite')
    if not file_bytes:
        raise TelegramSTTError('audio_empty')
    if not isinstance(timeout_s, (int, float)) or not np.isfinite(timeout_s) or timeout_s <= 0:
        raise TelegramSTTError('unsupported_configuration')
    start = time.monotonic()
    cancelled = threading.Event()
    # Only the streaming note adapter deliberately feeds at real-time speed.
    # Its recognition budget starts after the whole known-duration input.
    budget = timeout_s + pcm.size / 16000 if provider == 'assemblyai' else timeout_s
    try:
        async with asyncio.timeout(budget):
            if provider in {'local', 'whisper_local', 'pywhispercpp'}:
                text = await asyncio.to_thread(_transcribe_local, pcm, variant, cancelled,
                                               start, timing)
            elif provider == 'openai':
                text = await asyncio.to_thread(_transcribe_openai, file_bytes, variant,
                                               timeout_s, cancelled, start, timing)
            elif provider == 'assemblyai':
                text = await _transcribe_assemblyai(
                    pcm, variant, start, timing, selection.get('contextualKeyterms'),
                )
            else:
                raise TelegramSTTError('unsupported_configuration')
    except asyncio.CancelledError:
        cancelled.set()
        raise
    except TimeoutError as error:
        cancelled.set()
        raise TelegramSTTError('timeout') from error
    except TelegramSTTError:
        raise
    except ImportError as error:
        raise TelegramSTTError('provider_unavailable') from error
    except Exception as error:
        raise TelegramSTTError('transcription_failed') from error
    if not isinstance(text, str) or not text.strip():
        raise TelegramSTTError('no_speech')
    return text.strip()
# === VIVENTIUM END ===
