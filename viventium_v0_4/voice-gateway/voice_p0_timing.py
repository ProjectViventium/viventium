"""Optional content-free observations of the pinned provider boundaries.

These wrappers return the original objects and outcomes. They do not change endpointing,
provider requests, socket lifetime, or audio. Unsupported versions remain uninstrumented.
"""
from __future__ import annotations

import asyncio
from contextvars import ContextVar
from functools import wraps
import hashlib
from importlib.metadata import version
import inspect
import json
import math
import struct
import time
from weakref import WeakKeyDictionary, WeakMethod
from typing import Any
from speaker_segments import SPEAKER_CONTEXT_EXTRA_KEY

_tts_binding: ContextVar[dict | None] = ContextVar("voice_p0_tts_binding", default=None)


def _hash(kind: str, value: Any) -> str:
    return hashlib.sha256(f"viventium-p0-v1\0{kind}\0{value}".encode()).hexdigest()


def _number(value: Any) -> float | None:
    try:
        return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None
    except (OverflowError, ValueError):
        return None


def _first_active_pcm16le_index(data: bytes | memoryview) -> int | None:
    for index, (sample,) in enumerate(struct.iter_unpack("<h", data)):
        if abs(sample) / 32768 > .008:
            return index
    return None


class VoiceP0Timing:
    def __init__(self, logger: Any, call_id: str, *, enabled: bool = False):
        self.logger, self.enabled = logger, enabled
        self.call_hash = _hash("call", call_id)
        self._sequence = 0

    def _identity(self, kind: str) -> str:
        self._sequence += 1
        return _hash(kind, f"{self.call_hash}\0{self._sequence}")

    def emit(self, stage: str, **fields: Any) -> None:
        if not self.enabled:
            return
        try:
            self.logger.info("[VoiceP0] %s", json.dumps({
                "event": "voice_p0", "stage": stage, "callHash": self.call_hash,
                "observedAtMs": time.time_ns() / 1_000_000,
                "monotonicMs": time.monotonic_ns() / 1_000_000, **fields,
            }, separators=(",", ":")))
        except Exception:
            pass  # An observation must not change a delivered outcome.

    def _supported(self, package: str, target: Any, method: str, *args: Any) -> bool:
        try:
            supported = version("livekit-agents") == version(package) == "1.5.10"
            inspect.signature(getattr(target, method)).bind(*args)
            return supported
        except Exception:
            return False

    def bind_stt(self, stream: Any) -> None:
        if not self.enabled:
            return
        try:
            if version("livekit-agents") != "1.5.10":
                return
            stream._viventium_p0_stream_hash = self._identity("stt_stream")
            self.emit("stt_stream_bound", streamHash=stream._viventium_p0_stream_hash)
        except Exception:
            self.emit("stt_stream_support", status="unsupported")

    def attach_audio_recognition(self, recognition: Any) -> bool:
        if not self.enabled or getattr(recognition, "_viventium_p0_vad_bound", None) is self:
            return False
        if not type(recognition).__module__.startswith("livekit.agents.voice.audio_recognition") or not self._supported(
            "livekit-agents", recognition, "_on_vad_event", None
        ):
            self.emit("vad_receipt_support", status="unsupported")
            return False
        original = recognition._on_vad_event
        recognition_hash = self._identity("audio_recognition")

        @wraps(original)
        async def observed(event: Any) -> Any:
            if getattr(getattr(event, "type", None), "name", None) == "END_OF_SPEECH":
                self.emit("vad_end_observed", recognitionHash=recognition_hash,
                          samplesIndex=_number(getattr(event, "samples_index", None)),
                          speechDurationS=_number(getattr(event, "speech_duration", None)),
                          silenceDurationS=_number(getattr(event, "silence_duration", None)),
                          endClock="sdk_vad_sample_relative")
            return await original(event)

        try:
            recognition._on_vad_event = observed
            recognition._viventium_p0_vad_bound = self
        except Exception:
            recognition._on_vad_event = original
            self.emit("vad_receipt_support", status="unsupported")
            return False
        self.emit("vad_receipt_support", status="instrumented", recognitionHash=recognition_hash,
                  sdkVersion="1.5.10")
        return True

    def attach_assemblyai(self, stream: Any) -> bool:
        if not self.enabled:
            return False
        if not type(stream).__module__.startswith("livekit.plugins.assemblyai.") or not self._supported(
            "livekit-plugins-assemblyai", stream, "_process_stream_event", {}
        ):
            self.emit("stt_receipt_support", status="unsupported")
            return False
        original = stream._process_stream_event
        stream_hash = getattr(stream, "_viventium_p0_stream_hash", None) or self._identity("stt_stream")

        @wraps(original)
        def observed(data: dict) -> Any:
            if isinstance(data, dict) and data.get("type") == "Turn" and data.get("end_of_turn") is True:
                words = data.get("words")
                words = words if isinstance(words, list) else []
                last = words[-1] if words and isinstance(words[-1], dict) else {}
                self.emit("provider_eou_receipt", streamHash=stream_hash,
                          turnOrder=_number(data.get("turn_order")), wordCount=len(words),
                          confidence=_number(data.get("end_of_turn_confidence")),
                          formatted=data.get("turn_is_formatted") is True,
                          lastWordEndMs=_number(last.get("end")), endClock="provider_relative")
            return original(data)

        try:
            stream._process_stream_event = observed
            stream._viventium_p0_stream_hash = stream_hash
        except Exception:
            stream._process_stream_event = original
            self.emit("stt_receipt_support", status="unsupported")
            return False
        self.emit("stt_receipt_support", status="instrumented", streamHash=stream_hash, sdkVersion="1.5.10")
        return True

    def final_stt(self, event: Any, stream: Any) -> None:
        if getattr(getattr(event, "type", None), "name", None) != "FINAL_TRANSCRIPT":
            return
        self.emit("stt_final_observed", streamHash=getattr(stream, "_viventium_p0_stream_hash", None),
                  bindingStatus="bound" if getattr(stream, "_viventium_p0_stream_hash", None) else "missing")

    def attach_xai(self, tts: Any) -> bool:
        if not self.enabled:
            return False
        if not any(base.__module__.startswith("livekit.plugins.xai.") for base in type(tts).__mro__) or not self._supported(
            "livekit-plugins-xai", tts, "_connect_ws", 1.0
        ):
            self.emit("tts_transport_support", status="unsupported")
            return False
        original_connect, original_stream = tts._connect_ws, tts.stream
        sockets: WeakKeyDictionary = WeakKeyDictionary()
        original_acquire = getattr(tts, "_acquire_ws", None)

        def socket_state(ws: Any) -> tuple:
            previous = sockets.get(ws)
            state = previous or (self._identity("socket"), WeakMethod(ws.send_str), WeakMethod(ws.receive), None)
            sockets[ws] = state
            return state, previous is not None

        def bind_socket(ws: Any, binding: dict) -> None:
            try:
                state, _ = socket_state(ws)
                socket_hash, send_ref, receive_ref = state[:3]
                send, receive = send_ref(), receive_ref()
                if send is None or receive is None:
                    raise RuntimeError("socket methods unavailable")
            except Exception:
                self.emit("tts_socket_support", **binding, status="unsupported")
                return
            first_write = first_audio = first_done = True

            @wraps(send)
            async def write(data: Any, *args: Any, **kwargs: Any) -> Any:
                nonlocal first_write, first_done
                result = await send(data, *args, **kwargs)
                if not first_write and not first_done:
                    return result
                try:
                    packet = json.loads(data)
                    if first_write and packet.get("type") == "text.delta":
                        first_write = False
                        self.emit("tts_first_text_write", **binding, socketHash=socket_hash)
                    elif first_done and packet.get("type") == "text.done":
                        first_done = False
                        self.emit("tts_text_done_write", **binding, socketHash=socket_hash)
                except Exception:
                    pass
                return result

            @wraps(receive)
            async def read(*args: Any, **kwargs: Any) -> Any:
                nonlocal first_audio
                result = await receive(*args, **kwargs)
                if not first_audio:
                    return result
                try:
                    packet = json.loads(result.data)
                    if first_audio and packet.get("type") == "audio.delta":
                        first_audio = False
                        self.emit("tts_first_audio_receipt", **binding, socketHash=socket_hash)
                except Exception:
                    pass
                return result

            try:
                ws.send_str, ws.receive = write, read
            except Exception:
                ws.send_str, ws.receive = send, receive
                self.emit("tts_socket_support", **binding, status="unsupported")

        @wraps(original_connect)
        async def connect(*args: Any, **kwargs: Any) -> Any:
            binding = _tts_binding.get() or {}
            started = time.monotonic_ns()
            self.emit("tts_connect_start", **binding)
            try:
                ws = await original_connect(*args, **kwargs)
            except BaseException as exc:
                self.emit("tts_connect_end", **binding, status="cancelled" if isinstance(exc, asyncio.CancelledError) else "failed",
                          durationMs=(time.monotonic_ns() - started) / 1_000_000)
                raise
            try:
                state, reused = socket_state(ws)
                self.emit("tts_connect_end", **binding, socketHash=state[0], reused=reused,
                          status="completed", durationMs=(time.monotonic_ns() - started) / 1_000_000,
                          connectScope="combined_dns_tcp_tls_ws")
            except Exception:
                self.emit("tts_socket_support", **binding, status="unsupported")
            if not callable(original_acquire):
                bind_socket(ws, binding)
            return ws

        if callable(original_acquire):
            pool = getattr(tts, "_pool", None)
            if (type(pool).__module__ == "livekit.agents.utils.connection_pool"
                    and self._supported("livekit-agents", pool, "put", None)
                    and self._supported("livekit-agents", pool, "remove", None)):
                original_put, original_remove = pool.put, pool.remove

                def observe_disposition(method: Any, operation: str) -> Any:
                    @wraps(method)
                    def disposition(ws: Any, *args: Any, **kwargs: Any) -> Any:
                        result = method(ws, *args, **kwargs)
                        try:
                            state = sockets.get(ws)
                            lease = state[3] if state else None
                            if state:
                                sockets[ws] = (*state[:3], None)
                            self.emit("tts_pool_disposition", **(lease or {}),
                                      socketHash=state[0] if state else None,
                                      bindingStatus="active_lease" if lease else "unbound",
                                      operation=operation, trackedAfter=ws in pool._connections,
                                      availableAfter=ws in pool._available,
                                      closeQueuedAfter=ws in pool._to_close)
                        except Exception:
                            pass
                        return result
                    return disposition

                try:
                    pool.put = observe_disposition(original_put, "returned")
                    pool.remove = observe_disposition(original_remove, "evicted")
                except Exception:
                    pool.put, pool.remove = original_put, original_remove
                    self.emit("tts_pool_support", status="unsupported")
                else:
                    self.emit("tts_pool_support", status="instrumented", sdkVersion="1.5.10")
            else:
                self.emit("tts_pool_support", status="unsupported")

            @wraps(original_acquire)
            async def acquire(*args: Any, **kwargs: Any) -> Any:
                binding = _tts_binding.get() or {}
                started = time.monotonic_ns()
                self.emit("tts_acquire_start", **binding)
                try:
                    ws = await original_acquire(*args, **kwargs)
                except BaseException as exc:
                    self.emit("tts_acquire_end", **binding, status="cancelled" if isinstance(exc, asyncio.CancelledError) else "failed",
                              durationMs=(time.monotonic_ns() - started) / 1_000_000)
                    raise
                try:
                    state, _ = socket_state(ws)
                    binding["leaseHash"] = self._identity("tts_lease")
                    sockets[ws] = (*state[:3], dict(binding))
                    self.emit("tts_acquire_end", **binding, socketHash=state[0],
                              reused=bool(tts._pool.last_connection_reused), status="completed",
                              durationMs=(time.monotonic_ns() - started) / 1_000_000)
                    bind_socket(ws, binding)
                except Exception:
                    self.emit("tts_socket_support", **binding, status="unsupported")
                return ws

            tts._acquire_ws = acquire

        @wraps(original_stream)
        def stream(*args: Any, **kwargs: Any) -> Any:
            result = original_stream(*args, **kwargs)
            binding = {"streamHash": self._identity("tts_stream")}
            run, push = result._run, result.push_text
            first_text = True

            @wraps(push)
            def accept(text: str) -> Any:
                nonlocal first_text
                accepted = push(text)
                if first_text and text:
                    first_text = False
                    self.emit("tts_first_text_accepted", **binding)
                return accepted

            @wraps(run)
            async def observed_run(emitter: Any) -> Any:
                binding.pop("leaseHash", None)
                original_initialize = emitter.initialize
                original_push = getattr(emitter, "push", None)
                first_pcm = True
                first_active_pcm = True
                quiet_samples = 0
                pending_pcm_byte = b""
                sample_rate = None
                raw_pcm = False

                @wraps(original_initialize)
                def initialize(*args: Any, **kwargs: Any) -> Any:
                    nonlocal raw_pcm, sample_rate, first_active_pcm
                    initialized = original_initialize(*args, **kwargs)
                    mime_type = kwargs.get("mime_type")
                    raw_pcm = isinstance(mime_type, str) and mime_type.lower().strip().startswith(
                        ("audio/pcm", "audio/raw")
                    )
                    sample_rate = kwargs.get("sample_rate")
                    # The pinned xAI decoder declares this exact PCM16-LE MIME type.
                    if raw_pcm and not (mime_type.lower().strip() == "audio/pcm"
                                        and type(sample_rate) is int and sample_rate > 0
                                        and type(kwargs.get("num_channels")) is int
                                        and kwargs["num_channels"] == 1):
                        first_active_pcm = False
                        self.emit("tts_active_pcm_support", **binding, status="unsupported", reason="format")
                    request_id = kwargs.get("request_id")
                    if request_id:
                        binding["requestHash"] = _hash("tts_request", request_id)
                        self.emit("tts_request_bound", **binding)
                    return initialized

                def push_pcm(data: bytes) -> Any:
                    nonlocal first_pcm, first_active_pcm, quiet_samples, pending_pcm_byte
                    result = original_push(data)
                    if first_pcm and raw_pcm and isinstance(data, bytes) and data:
                        first_pcm = False
                        # xAI has decoded audio.delta before this SDK boundary.
                        # This is not proof of remote receipt or audible playout.
                        self.emit("tts_first_decoded_pcm", **binding, byteCount=len(data))
                    if first_active_pcm and raw_pcm and isinstance(data, bytes) and data:
                        try:
                            pcm = pending_pcm_byte + data
                            complete_length = len(pcm) & ~1
                            pending_pcm_byte = pcm[complete_length:]
                            index = _first_active_pcm16le_index(memoryview(pcm)[:complete_length])
                            if index is None:
                                quiet_samples += complete_length // 2
                            else:
                                first_active_pcm = False
                                self.emit("tts_first_active_produced_pcm", **binding,
                                          leadingQuietSamples=quiet_samples + index,
                                          sampleRate=sample_rate, thresholdNormalized=.008)
                        except Exception:
                            first_active_pcm = False
                            self.emit("tts_active_pcm_support", **binding, status="unsupported", reason="observation")
                    return result

                emitter.initialize = initialize
                if callable(original_push):
                    emitter.push = push_pcm
                token = _tts_binding.set(binding)
                status = "completed"
                try:
                    return await run(emitter)
                except BaseException as exc:
                    status = "cancelled" if isinstance(exc, asyncio.CancelledError) else "failed"
                    raise
                finally:
                    self.emit("tts_stream_end", **binding, status=status)
                    _tts_binding.reset(token)
                    emitter.initialize = original_initialize
                    if callable(original_push):
                        emitter.push = original_push

            result.push_text, result._run = accept, observed_run
            return result

        tts._connect_ws, tts.stream = connect, stream
        self.emit("tts_transport_support", status="instrumented", sdkVersion="1.5.10")
        return True


def observe_sdk_commit(method: Any) -> Any:
    @wraps(method)
    async def observed(self: Any, *args: Any, **kwargs: Any) -> Any:
        observer = getattr(self, "_p0_timing", None)
        if observer is None or not observer.enabled:
            return await method(self, *args, **kwargs)
        started = time.monotonic_ns()
        message = args[1] if len(args) > 1 else kwargs.get("new_message")
        def turn_binding() -> dict:
            extra = getattr(message, "extra", None)
            context = extra.get(SPEAKER_CONTEXT_EXTRA_KEY, {}) if isinstance(extra, dict) else {}
            segments = context.get("speakerSegments") if isinstance(context, dict) else None
            first = segments[0] if isinstance(segments, list) and segments and isinstance(segments[0], dict) else {}
            turn_id = first.get("turnId")
            return {"turnHash": _hash("turn", turn_id)} if turn_id else {"bindingStatus": "missing"}
        observer.emit("sdk_commit_enter", **turn_binding())
        status = "completed"
        try:
            return await method(self, *args, **kwargs)
        except BaseException as exc:
            status = "cancelled" if isinstance(exc, asyncio.CancelledError) else "failed"
            raise
        finally:
            observer.emit("sdk_commit_exit", **turn_binding(), status=status, durationMs=(time.monotonic_ns() - started) / 1_000_000)
    return observed
