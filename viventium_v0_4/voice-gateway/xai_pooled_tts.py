# === VIVENTIUM START ===
# Reuse the installed LiveKit pool for xAI's multi-utterance socket protocol.
# This narrow 1.5.10 backport retains the upstream sender, receiver and wire format.
# === VIVENTIUM END ===
from __future__ import annotations

import asyncio
from importlib.metadata import version
import inspect
import logging
import time

from livekit.agents import APIConnectionError, APIConnectOptions, utils
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS
from livekit.plugins.xai import tts as xai

logger = logging.getLogger("voice-gateway.xai_pooled_tts")


def _supported() -> bool:
    try:
        return (
            version("livekit-agents") == version("livekit-plugins-xai") == "1.5.10"
            and len(inspect.signature(xai.TTS._connect_ws).parameters) == 2
        )
    except Exception:
        return False


def create_xai_tts(**kwargs):
    return PooledXaiTTS(**kwargs) if _supported() else xai.TTS(**kwargs)


class PooledXaiTTS(xai.TTS):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._pool = utils.ConnectionPool(
            connect_cb=self._connect_pooled_ws,
            close_cb=self._close_ws,
            max_session_duration=1800,
            mark_refreshed_on_get=False,
        )
        self._closed = False

    def _recipe(self):
        return self._opts.voice, self._opts.language

    async def _connect_pooled_ws(self, timeout):
        await self._pool._drain_to_close()
        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            recipe = self._recipe()
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise APIConnectionError("xAI connection settings changed during connection")
            ws = await self._connect_ws(remaining)
            if recipe == self._recipe():
                return ws
            await self._close_ws(ws)

    async def _acquire_ws(self, timeout):
        if self._closed:
            raise APIConnectionError("xAI renderer is closed")
        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise APIConnectionError("xAI socket acquisition timed out")
            ws = await self._pool.get(timeout=remaining)
            if not ws.closed:
                return ws
            self._pool.remove(ws)

    def update_options(self, *, voice=None, language=None):
        before = self._recipe()
        super().update_options(voice=voice, language=language)
        if before != self._recipe():
            # Keep an in-flight utterance intact. Its old lease is evicted on release.
            for ws in tuple(self._pool._available):
                self._pool.remove(ws)

    def prewarm(self):
        if self._closed:
            return
        # The installed pool's prewarm is one-shot. Reuse that task and lock while
        # allowing a later turn to replace an evicted, closed or expired idle socket.
        now = time.time()
        for ws in tuple(self._pool._available):
            if ws.closed or now - self._pool._connections[ws] > 1800:
                self._pool.remove(ws)
        task = self._pool._prewarm_task() if self._pool._prewarm_task else None
        if task is not None and not task.done():
            return
        self._pool._prewarm_task = None
        self._pool.prewarm()
        task = self._pool._prewarm_task() if self._pool._prewarm_task else None
        if task is not None:
            task.add_done_callback(self._consume_prewarm)

    @staticmethod
    def _consume_prewarm(task):
        if not task.cancelled() and (error := task.exception()) is not None:
            logger.warning("xAI TTS prewarm failed (%s); demand will retry", type(error).__name__)

    def stream(self, *, conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS):
        stream = _PooledSynthesizeStream(tts=self, conn_options=conn_options)
        self._streams.add(stream)
        return stream

    async def aclose(self):
        self._closed = True
        try:
            await super().aclose()
        finally:
            await self._pool.aclose()


class _PooledSynthesizeStream(xai.SynthesizeStream):
    async def _run_ws(self, input_stream, output_emitter):
        # The upstream method owns all wire processing. Its connect/close calls operate on
        # this stream's exact lease; only successful completion returns it to the pool.
        ws = await self._tts._acquire_ws(self._conn_options.timeout)
        self._acquire_time = self._tts._pool.last_acquire_time
        self._connection_reused = self._tts._pool.last_connection_reused
        original_tts = self._tts
        recipe = original_tts._recipe()
        text_sent = asyncio.Event()
        first_audio = False
        first_audio_deadline = None

        class _Socket:
            def __getattr__(self, name):
                return getattr(ws, name)

            async def send_str(self, data, **kwargs):
                nonlocal first_audio_deadline
                if not text_sent.is_set():
                    first_audio_deadline = asyncio.get_running_loop().time() + self_timeout
                    text_sent.set()
                return await ws.send_str(data, **kwargs)

            async def receive(self, **kwargs):
                await text_sent.wait()
                if first_audio:
                    return await ws.receive(**kwargs)
                # An idle TCP socket can appear open after its peer disappears.
                # Start the existing request budget at text, not during model inference.
                remaining = first_audio_deadline - asyncio.get_running_loop().time()
                return await asyncio.wait_for(ws.receive(**kwargs), max(0, remaining))

        class _Emitter:
            def __getattr__(self, name):
                return getattr(output_emitter, name)

            def push(self, data):
                nonlocal first_audio
                if data:
                    first_audio = True
                return output_emitter.push(data)

        self_timeout = self._conn_options.timeout
        socket = _Socket()

        class _Lease:
            def __getattr__(self, name):
                return getattr(original_tts, name)

            async def _connect_ws(self, timeout):
                return socket

            async def _close_ws(self, socket):
                pass

        self._tts = _Lease()
        try:
            await super()._run_ws(input_stream, _Emitter())
        except BaseException:
            original_tts._pool.remove(ws)
            raise
        else:
            if recipe == original_tts._recipe() and not ws.closed:
                original_tts._pool.put(ws)
            else:
                original_tts._pool.remove(ws)
        finally:
            self._tts = original_tts
