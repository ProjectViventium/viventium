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
import time
from weakref import WeakKeyDictionary
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

    def attach_assemblyai(self, stream: Any) -> bool:
        if not self.enabled:
            return False
        if not type(stream).__module__.startswith("livekit.plugins.assemblyai.") or not self._supported(
            "livekit-plugins-assemblyai", stream, "_process_stream_event", {}
        ):
            self.emit("stt_receipt_support", status="unsupported")
            return False
        original = stream._process_stream_event
        stream_hash = self._identity("stt_stream")

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
        if not type(tts).__module__.startswith("livekit.plugins.xai.") or not self._supported(
            "livekit-plugins-xai", tts, "_connect_ws", 1.0
        ):
            self.emit("tts_transport_support", status="unsupported")
            return False
        original_connect, original_stream = tts._connect_ws, tts.stream
        sockets: WeakKeyDictionary = WeakKeyDictionary()

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
                previous = sockets.get(ws)
                reused = previous is not None
                socket_hash = previous[0] if previous else self._identity("socket")
                send, receive = previous[1:] if previous else (ws.send_str, ws.receive)
                sockets[ws] = (socket_hash, send, receive)
            except Exception:
                self.emit("tts_socket_support", **binding, status="unsupported")
                return ws
            self.emit("tts_connect_end", **binding, socketHash=socket_hash, reused=reused,
                      status="completed", durationMs=(time.monotonic_ns() - started) / 1_000_000,
                      connectScope="combined_dns_tcp_tls_ws")
            first_write = first_audio = True

            @wraps(send)
            async def write(data: Any, *args: Any, **kwargs: Any) -> Any:
                nonlocal first_write
                result = await send(data, *args, **kwargs)
                if not first_write:
                    return result
                try:
                    packet = json.loads(data)
                    if first_write and packet.get("type") == "text.delta":
                        first_write = False
                        self.emit("tts_first_text_write", **binding, socketHash=socket_hash)
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
            return ws

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
                original_initialize = emitter.initialize

                @wraps(original_initialize)
                def initialize(*args: Any, **kwargs: Any) -> Any:
                    initialized = original_initialize(*args, **kwargs)
                    request_id = kwargs.get("request_id")
                    if request_id:
                        binding["requestHash"] = _hash("tts_request", request_id)
                        self.emit("tts_request_bound", **binding)
                    return initialized

                emitter.initialize = initialize
                token = _tts_binding.set(binding)
                try:
                    return await run(emitter)
                finally:
                    _tts_binding.reset(token)
                    emitter.initialize = original_initialize

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
