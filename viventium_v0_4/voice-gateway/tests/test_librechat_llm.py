import os
import sys
import unittest
import asyncio
import json
import aiohttp
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from livekit.agents.llm.chat_context import ChatContext, ChatMessage

# Ensure voice-gateway root is on sys.path so `import librechat_llm` works
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from librechat_llm import (
    LibreChatAuth,
    LibreChatLLM,
    _VoicePresentationCoordinator,
    _abort_librechat_voice_stream,
    _extract_resume_state_text,
    _extract_final_response_text,
    _extract_final_response_message_id,
    _extract_last_user_text,
    _extract_stream_error,
    _select_stream_error_message,
    _summarize_error_for_log,
    _payload_has_glasshive_tool_call,
    _extract_voice_task_event,
    _extract_voice_task_sync,
    _NoResponseStreamGuard,
    _VoiceTtsDeltaBuffer,
    _VoiceTaskEventGate,
    is_no_response_only,
    format_insights_for_direct_speech,
)
from sse import sanitize_voice_tts_text
from speaker_segments import SpeakerSegmentTracker, attach_speaker_context_to_message
from voice_hop_trace import VoiceHopTrace


async def _project_tts_chunks(chunks):
    from worker import ViventiumVoiceAgent, Agent

    async def source():
        for value in chunks:
            yield value

    async def selected_node(agent, text, settings):
        async for value in text:
            yield value

    agent = ViventiumVoiceAgent(instructions="Synthetic")
    with patch.object(Agent.default, "tts_node", selected_node):
        return [value async for value in agent.tts_node(source(), None)]


def _voice_task_event(
    event_id: str,
    sequence: int,
    *,
    state: str = "running",
    phase: str = "tool",
    event_type: str = "progress",
    **extra,
):
    return {
        "version": 1,
        "eventId": event_id,
        "sequence": sequence,
        "emittedAt": f"2026-08-09T20:37:{sequence:02d}.000Z",
        "callSessionId": "call_1",
        "taskId": "task_1",
        "type": event_type,
        "state": state,
        "phase": phase,
        "cancellable": state
        not in {"completed", "failed", "cancelled_confirmed", "cancelled_unenforceable"},
        "retryable": False,
        "owner": {"kind": "generation_job", "id": "stream_1"},
        **extra,
    }


def _voice_task_sync(*, call_session_id: str = "call_1") -> dict:
    return {
        "version": 1,
        "callSessionId": call_session_id,
        "state": "synchronized",
        "emittedAt": "2026-08-09T20:37:59.000Z",
    }


class _FakeListenOnlyResponse:
    status = 200

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def json(self):
        return {"status": "listen_only", "listenOnly": True}

    async def text(self):
        return ""


class _FakeListenOnlySession:
    def __init__(self, *args, **kwargs):
        self.post_calls = []
        self.get_calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def post(self, *args, **kwargs):
        self.post_calls.append((args, kwargs))
        return _FakeListenOnlyResponse()

    def get(self, *args, **kwargs):
        self.get_calls.append((args, kwargs))
        raise AssertionError("Listen-Only responses must not open an SSE stream")


class _FakeJsonResponse:
    status = 200

    def __init__(self, payload: dict):
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def json(self):
        return self._payload

    async def text(self):
        return ""


class _FakeCallStateSession:
    def __init__(self, payload: dict, *, status: int = 200):
        self.payload = payload
        self.status = status
        self.get_calls = []
        self.post_calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def get(self, url, *args, **kwargs):
        self.get_calls.append((url, args, kwargs))
        response = _FakeJsonResponse(self.payload)
        response.status = self.status
        return response

    def post(self, url, *args, **kwargs):
        self.post_calls.append((url, args, kwargs))
        response = _FakeJsonResponse(self.payload)
        response.status = self.status
        return response


class _SequencedStatusResponse(_FakeJsonResponse):
    def __init__(self, status: int, payload: dict):
        super().__init__(payload)
        self.status = status

    async def text(self):
        return "synthetic transient failure"


class _RetryingSpeakerSession:
    def __init__(self, transient_tombstone_failures: int):
        self.remaining_failures = transient_tombstone_failures
        self.post_calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def post(self, url, *args, **kwargs):
        self.post_calls.append((url, args, kwargs))
        if str(url).endswith("/voice/speaker-session-state") and self.remaining_failures:
            self.remaining_failures -= 1
            return _SequencedStatusResponse(503, {"error": "temporary"})
        return _SequencedStatusResponse(
            200,
            {"version": 1, "accepted": ["segment_1"], "ignored": []},
        )


class _FakeClosedSseContent:
    async def iter_any(self):
        if False:
            yield b""


class _FakeClosedSseResponse:
    status = 200
    content = _FakeClosedSseContent()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def text(self):
        return ""


class _FakeClosedStreamSession:
    def __init__(self, *args, **kwargs):
        self.post_calls = []
        self.get_calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def post(self, url, *args, **kwargs):
        self.post_calls.append((url, args, kwargs))
        if str(url).endswith("/abort"):
            return _FakeJsonResponse({"success": True, "aborted": "stream_voice_1"})
        return _FakeJsonResponse({"streamId": "stream_voice_1", "conversationId": "conv_1"})

    def get(self, *args, **kwargs):
        if args and str(args[0]).endswith("/state"):
            return _FakeJsonResponse(None)
        self.get_calls.append((args, kwargs))
        return _FakeClosedSseResponse()


class _FakeSseContent:
    def __init__(self, events: list[dict], *, pause_before: int | None = None,
                 started: asyncio.Event | None = None, release: asyncio.Event | None = None):
        self._events = events
        self._pause_before = pause_before
        self._started = started
        self._release = release

    async def iter_any(self):
        for index, event in enumerate(self._events):
            if index == self._pause_before:
                self._started.set()
                await self._release.wait()
            payload = json.dumps(event)
            yield f"event: message\ndata: {payload}\n\n".encode("utf-8")


class _FakeStreamingSseResponse:
    status = 200

    def __init__(self, events: list[dict]):
        self.content = _FakeSseContent(events)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def text(self):
        return ""


class _FakeStreamingSseSession:
    def __init__(self, events: list[dict], *args, **kwargs):
        self._events = events
        self.post_calls = []
        self.get_calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def post(self, url, *args, **kwargs):
        self.post_calls.append((url, args, kwargs))
        return _FakeJsonResponse({"streamId": "stream_voice_1", "conversationId": "conv_1"})

    def get(self, url, *args, **kwargs):
        if str(url).endswith("/state"):
            return _FakeJsonResponse(None)
        self.get_calls.append((url, args, kwargs))
        return _FakeStreamingSseResponse(self._events)


class _FakeResumingSseSession(_FakeStreamingSseSession):
    def __init__(self, event_batches: list[list[dict]], *args, **kwargs):
        super().__init__([], *args, **kwargs)
        self._event_batches = list(event_batches)

    def get(self, url, *args, **kwargs):
        self.get_calls.append((url, args, kwargs))
        if not self._event_batches:
            raise AssertionError("Unexpected extra voice SSE reconnect")
        return _FakeStreamingSseResponse(self._event_batches.pop(0))


class _FakeLogicalStreamingSseSession(_FakeStreamingSseSession):
    def post(self, url, *args, **kwargs):
        self.post_calls.append((url, args, kwargs))
        return _FakeJsonResponse(
            {
                "streamId": "stream_voice_1",
                "conversationId": "conv_1",
                "logical_turn_id": "logical-1",
                "revision": 2,
            }
        )


class _CompletableSpeechHandle:
    def __init__(self, speech_id: str) -> None:
        self.id = speech_id
        self.interrupted = False
        self.chat_items = []
        self._done = False
        self._callbacks = []

    def done(self) -> bool:
        return self._done

    def add_done_callback(self, callback) -> None:
        self._callbacks.append(callback)

    def mark_audible_playout(self) -> None:
        message = ChatMessage(role="assistant", content=["Synthetic spoken response."])
        message.metrics["started_speaking_at"] = 1.0
        self.chat_items.append(message)

    def complete(self, *, interrupted: bool = False) -> None:
        self.interrupted = interrupted
        self._done = True
        for callback in list(self._callbacks):
            callback(self)


class _FakeDeliveryAckSession:
    def __init__(self, *args, **kwargs):
        self.post_calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def post(self, url, *args, **kwargs):
        self.post_calls.append((url, args, kwargs))
        return _FakeJsonResponse({"accepted": True})


class _CallTaskEventContent:
    def __init__(
        self,
        events: list[dict],
        delivered: asyncio.Event,
        *,
        marker_first: bool = False,
    ):
        self._events = events
        self._delivered = delivered
        self._marker_first = marker_first

    async def iter_any(self):
        marker = (
            "event: voice_task_sync\n"
            f"data: {json.dumps(_voice_task_sync())}\n\n"
        ).encode("utf-8")
        if self._marker_first:
            yield marker
        for task_event in self._events:
            payload = json.dumps({"voiceTaskEvent": task_event})
            yield f"event: voice_task_event\ndata: {payload}\n\n".encode("utf-8")
        if not self._marker_first:
            yield marker
        self._delivered.set()
        await asyncio.sleep(60)


class _CallTaskEventResponse:
    status = 200

    def __init__(
        self,
        events: list[dict],
        delivered: asyncio.Event,
        *,
        marker_first: bool = False,
    ):
        self.content = _CallTaskEventContent(
            events,
            delivered,
            marker_first=marker_first,
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def text(self):
        return ""


class _CallTaskEventSession:
    def __init__(self, events: list[dict], *args, marker_first: bool = False, **kwargs):
        self._events = events
        self._marker_first = marker_first
        self.delivered = asyncio.Event()
        self.get_calls = []
        self.closed = False

    def get(self, url, *args, **kwargs):
        self.get_calls.append((url, args, kwargs))
        return _CallTaskEventResponse(
            self._events,
            self.delivered,
            marker_first=self._marker_first,
        )

    async def close(self):
        self.closed = True


class _FailingCallTaskEventResponse:
    async def __aenter__(self):
        raise aiohttp.ClientConnectionError("synthetic disconnect")

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _ReconnectCallTaskEventSession(_CallTaskEventSession):
    def get(self, url, *args, **kwargs):
        self.get_calls.append((url, args, kwargs))
        if len(self.get_calls) == 1:
            return _FailingCallTaskEventResponse()
        return _CallTaskEventResponse(self._events, self.delivered)


class _CallTaskStatusResponse:
    def __init__(self, status: int):
        self.status = status
        self.content = _FakeClosedSseContent()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def text(self):
        return ""


class _CallTaskStatusSession:
    def __init__(self, status: int):
        self.status = status
        self.get_calls = []
        self.closed = False

    def get(self, url, *args, **kwargs):
        self.get_calls.append((url, args, kwargs))
        return _CallTaskStatusResponse(self.status)

    async def close(self):
        self.closed = True


class _CallTaskSyncOnlyContent:
    def __init__(self, payload: dict):
        self._payload = payload

    async def iter_any(self):
        yield (
            "event: voice_task_sync\n"
            f"data: {json.dumps(self._payload)}\n\n"
        ).encode("utf-8")
        await asyncio.sleep(60)


class _CallTaskSyncOnlyResponse:
    status = 200

    def __init__(self, payload: dict):
        self.content = _CallTaskSyncOnlyContent(payload)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _CallTaskSyncOnlySession(_CallTaskStatusSession):
    def __init__(self, payload: dict):
        super().__init__(200)
        self._payload = payload

    def get(self, url, *args, **kwargs):
        self.get_calls.append((url, args, kwargs))
        return _CallTaskSyncOnlyResponse(self._payload)


class _DisconnectingCallTaskEventContent:
    def __init__(self, events: list[dict]):
        self._events = events

    async def iter_any(self):
        for task_event in self._events:
            payload = json.dumps({"voiceTaskEvent": task_event})
            yield f"event: voice_task_event\ndata: {payload}\n\n".encode("utf-8")
        yield (
            "event: voice_task_sync\n"
            f"data: {json.dumps(_voice_task_sync())}\n\n"
        ).encode("utf-8")
        raise aiohttp.ClientConnectionError("synthetic mid-stream disconnect")


class _DisconnectingCallTaskEventResponse(_CallTaskEventResponse):
    def __init__(self, events: list[dict]):
        self.content = _DisconnectingCallTaskEventContent(events)


class _DisconnectThenReconnectCallTaskSession(_CallTaskEventSession):
    def __init__(self, first_events: list[dict], reconnect_events: list[dict]):
        super().__init__(reconnect_events)
        self._first_events = first_events

    def get(self, url, *args, **kwargs):
        self.get_calls.append((url, args, kwargs))
        if len(self.get_calls) == 1:
            return _DisconnectingCallTaskEventResponse(self._first_events)
        return _CallTaskEventResponse(self._events, self.delivered)


class _FakeBlockingSseContent:
    def __init__(self, started: asyncio.Event):
        self.started = started

    async def iter_any(self):
        self.started.set()
        await asyncio.sleep(60)
        if False:
            yield b""


class _FakeBlockingSseResponse:
    status = 200

    def __init__(self, started: asyncio.Event):
        self.content = _FakeBlockingSseContent(started)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def text(self):
        return ""


class _FakeSlowAbortResponse:
    status = 200

    def __init__(self, session: "_FakeBlockingStreamSession"):
        self.session = session

    async def __aenter__(self):
        await asyncio.sleep(0.01)
        self.session.abort_completed = True
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def json(self):
        return {"success": True, "aborted": "stream_voice_cancel_1"}

    async def text(self):
        return ""


class _FakeBlockingStreamSession:
    def __init__(self, *args, **kwargs):
        self.post_calls = []
        self.get_calls = []
        self.sse_started = asyncio.Event()
        self.abort_completed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def post(self, url, *args, **kwargs):
        self.post_calls.append((url, args, kwargs))
        if str(url).endswith("/abort"):
            return _FakeSlowAbortResponse(self)
        return _FakeJsonResponse({"streamId": "stream_voice_cancel_1", "conversationId": "conv_1"})

    def get(self, *args, **kwargs):
        self.get_calls.append((args, kwargs))
        return _FakeBlockingSseResponse(self.sse_started)


class _FakeInterruptedThenCompletedContent:
    def __init__(self, started: asyncio.Event, running_event: dict):
        self._started = started
        self._running_event = running_event

    async def iter_any(self):
        payload = json.dumps({"voiceTaskEvent": self._running_event})
        yield f"event: voice_task_event\ndata: {payload}\n\n".encode()
        self._started.set()
        await asyncio.sleep(60)


class _FakeInterruptedThenCompletedResponse:
    status = 200

    def __init__(self, content):
        self.content = content

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def text(self):
        return ""


class _FakeInterruptedThenCompletedSession:
    def __init__(self, running_event: dict, resumed_events: list[dict]):
        self.running_event = running_event
        self.resumed_events = resumed_events
        self.primary_started = asyncio.Event()
        self.post_calls = []
        self.get_calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def post(self, url, *args, **kwargs):
        self.post_calls.append((url, args, kwargs))
        return _FakeJsonResponse(
            {
                "streamId": "stream_resume_1",
                "taskId": self.running_event["taskId"],
                "conversationId": "conv_1",
            }
        )

    def get(self, url, *args, **kwargs):
        self.get_calls.append((url, args, kwargs))
        if len(self.get_calls) == 1:
            return _FakeInterruptedThenCompletedResponse(
                _FakeInterruptedThenCompletedContent(
                    self.primary_started,
                    self.running_event,
                )
            )
        return _FakeStreamingSseResponse(self.resumed_events)


class TestCallModeState(unittest.TestCase):
    def test_get_call_state_accepts_exact_frozen_status_enum_only(self) -> None:
        valid = (
            "created",
            "connecting",
            "listening",
            "speaking",
            "working",
            "needs_input",
            "degraded",
            "failed",
            "ended",
        )

        async def read(status):
            fake_session = _FakeCallStateSession(
                {
                    "version": 1,
                    "callSessionId": "call_1",
                    "mode": "call",
                    "status": status,
                    "revision": 1,
                    "updatedAt": "2026-08-09T20:37:04.000Z",
                }
            )
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                return await llm.get_call_state()

        for status in valid:
            with self.subTest(status=status):
                state = asyncio.run(read(status))
                self.assertEqual(state["status"], status)
        for status in ("active", "connected", "", None, True):
            with self.subTest(invalid=status):
                self.assertIsNone(asyncio.run(read(status)))

    def test_get_call_state_reuses_one_bounded_http_session(self) -> None:
        async def run():
            fake_session = _FakeCallStateSession(
                {
                    "version": 1,
                    "callSessionId": "call_1",
                    "mode": "call",
                    "status": "listening",
                    "revision": 1,
                    "updatedAt": "2026-08-09T20:37:04.000Z",
                }
            )
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            with patch(
                "librechat_llm.aiohttp.ClientSession", return_value=fake_session
            ) as session_cls:
                first = await llm.get_call_state()
                second = await llm.get_call_state()
            return first, second, fake_session, session_cls

        first, second, fake_session, session_cls = asyncio.run(run())
        self.assertEqual(first["mode"], "call")
        self.assertEqual(second["mode"], "call")
        self.assertEqual(len(fake_session.get_calls), 2)
        session_cls.assert_called_once()
        self.assertEqual(session_cls.call_args.kwargs["timeout"].total, 1.0)

    def test_get_turn_authority_reads_exact_persisted_call_turn_and_owner_revision(
        self,
    ) -> None:
        segment = {
            "version": 1,
            "callSessionId": "call_1",
            "segmentId": "segment_owner_1",
            "turnId": "turn_owner/1",
            "revision": 2,
            "isFinal": True,
            "speaker": {
                "attribution": "verified",
                "actorTrust": "owner_participant",
                "participantIdentity": "owner",
            },
        }
        valid = {
            "version": 1,
            "callSessionId": "call_1",
            "turnId": "turn_owner/1",
            "mode": "wing",
            "status": "listening",
            "revision": 8,
            "updatedAt": "2026-08-09T20:37:04.000Z",
            "speakerSegments": [segment],
        }

        async def read(payload):
            fake_session = _FakeCallStateSession(payload)
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                result = await llm.get_turn_authority("turn_owner/1")
            return result, fake_session

        authority, fake_session = asyncio.run(read(valid))
        self.assertEqual(authority["speakerSegments"], [segment])
        self.assertEqual(
            fake_session.get_calls[0][0],
            "http://librechat.test/api/viventium/voice/speaker-segments/authority/turn_owner%2F1",
        )

        for label, invalid in (
            ("different_call", {**valid, "callSessionId": "call_other"}),
            ("different_turn", {**valid, "turnId": "turn_other"}),
            ("terminal_session", {**valid, "status": "ended"}),
            (
                "different_segment_call",
                {
                    **valid,
                    "speakerSegments": [{**segment, "callSessionId": "call_other"}],
                },
            ),
            (
                "different_segment_turn",
                {**valid, "speakerSegments": [{**segment, "turnId": "turn_other"}]},
            ),
        ):
            with self.subTest(label=label):
                result, _ = asyncio.run(read(invalid))
                self.assertIsNone(result)

    def test_verify_voice_engagement_uses_bound_gateway_auth_and_exact_core_verdict(self) -> None:
        receipt = {
            "version": 1,
            "callSessionId": "call_1",
            "turnId": "turn_owner_1",
            "attestation": "A" * 43,
        }

        async def verify(payload, *, status=200):
            session = _FakeCallStateSession(payload, status=status)
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(
                    call_session_id="call_1",
                    call_secret="synthetic-gateway-secret",
                    job_id="job_1",
                    worker_id="worker_1",
                ),
            )
            with patch("librechat_llm.aiohttp.ClientSession", return_value=session):
                result = await llm.verify_voice_engagement(receipt)
            return result, session

        accepted, session = asyncio.run(
            verify(
                {
                    "version": 1,
                    "callSessionId": "call_1",
                    "turnId": "turn_owner_1",
                    "verified": True,
                }
            )
        )
        self.assertTrue(accepted)
        url, _args, kwargs = session.post_calls[0]
        self.assertEqual(url, "http://librechat.test/api/viventium/voice/engagement/verify")
        self.assertEqual(kwargs["json"], {"version": 1, "engagement": receipt})
        self.assertEqual(kwargs["headers"]["X-VIVENTIUM-JOB-ID"], "job_1")
        self.assertEqual(kwargs["headers"]["X-VIVENTIUM-WORKER-ID"], "worker_1")

        for rejected in (
            {"version": 1, "callSessionId": "another_call", "turnId": "turn_owner_1", "verified": True},
            {"version": 1, "callSessionId": "call_1", "turnId": "another_turn", "verified": True},
            {"version": 1, "callSessionId": "call_1", "turnId": "turn_owner_1", "verified": False},
        ):
            with self.subTest(verdict=rejected):
                result, _ = asyncio.run(verify(rejected))
                self.assertFalse(result)
        result, _ = asyncio.run(verify({"code": "voice_engagement_not_authorized"}, status=403))
        self.assertFalse(result)

    def test_get_call_mode_uses_authoritative_mode_and_shared_secret(self) -> None:
        async def run():
            fake_session = _FakeCallStateSession(
                {
                    "version": 1,
                    "callSessionId": "call/1",
                    "mode": "listen_only",
                    "status": "listening",
                    "revision": 7,
                    "updatedAt": "2026-08-09T20:37:04.000Z",
                }
            )
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call/1", call_secret="secret"),
            )
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                mode = await llm.get_call_mode()
            return mode, fake_session

        mode, fake_session = asyncio.run(run())

        self.assertEqual(mode, "listen_only")
        url, _args, kwargs = fake_session.get_calls[0]
        self.assertEqual(
            url,
            "http://librechat.test/api/viventium/voice/call-sessions/call%2F1/state",
        )
        self.assertEqual(kwargs["headers"]["X-VIVENTIUM-CALL-SECRET"], "secret")
        self.assertEqual(kwargs["headers"]["X-VIVENTIUM-CALL-SESSION"], "call/1")

    def test_get_call_mode_strictly_rejects_legacy_malformed_and_mismatched_state(self) -> None:
        async def run(payload, status=200):
            fake_session = _FakeCallStateSession(payload, status=status)
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                return await llm.get_call_mode()

        self.assertIsNone(asyncio.run(run({"wingMode": True})))
        self.assertIsNone(asyncio.run(run({"listenOnly": True})))
        self.assertIsNone(
            asyncio.run(
                run(
                    {
                        "version": 1,
                        "callSessionId": "call_1",
                        "mode": "call",
                        "status": "listening",
                        "revision": True,
                        "updatedAt": "not-a-time",
                    }
                )
            )
        )
        self.assertIsNone(asyncio.run(run({"error": "unavailable"}, status=503)))
        self.assertIsNone(
            asyncio.run(
                run(
                    {
                        "version": 1,
                        "callSessionId": "different_call",
                        "mode": "call",
                    }
                )
            )
        )


class TestExtractLastUserText(unittest.TestCase):
    def test_extracts_single_user_message(self) -> None:
        ctx = ChatContext(items=[ChatMessage(role="user", content=["hello"])])
        self.assertEqual(_extract_last_user_text(ctx), "hello")

    def test_extracts_last_user_message(self) -> None:
        ctx = ChatContext(
            items=[
                ChatMessage(role="user", content=["first"]),
                ChatMessage(role="assistant", content=["ignore"]),
                ChatMessage(role="user", content=["second"]),
            ]
        )
        self.assertEqual(_extract_last_user_text(ctx), "second")

    def test_joins_multiple_text_chunks(self) -> None:
        ctx = ChatContext(items=[ChatMessage(role="user", content=["hel", "lo"])])
        self.assertEqual(_extract_last_user_text(ctx), "hello")

    def test_ignores_empty_and_whitespace(self) -> None:
        ctx = ChatContext(items=[ChatMessage(role="user", content=[" ", "\n", "\t"])])
        self.assertEqual(_extract_last_user_text(ctx), "")


class TestListenOnlyStream(unittest.TestCase):
    def test_current_call_runtime_context_reaches_authenticated_post_without_user_text_change(self) -> None:
        fake_session = _FakeListenOnlySession()
        facts = {"version": 1, "callSessionId": "call_1", "readyRoute": {
            "stt": {"provider": "pywhispercpp", "variant": "large-v3-turbo"},
            "tts": {"provider": "local_chatterbox_turbo_mlx_8bit", "variant": "local-model"},
        }, "configuredTtsFallback": None}

        async def run_stream() -> None:
            llm = LibreChatLLM(origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"))
            self.assertIsNone(llm._voice_runtime_context)
            llm.set_voice_provider("local_chatterbox_turbo_mlx_8bit", runtime_context=facts)
            stream = llm.chat(chat_ctx=ChatContext(items=[ChatMessage(role="user", content=["Current settings?"])]))
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                async with stream:
                    async for _chunk in stream:
                        pass

        asyncio.run(run_stream())
        posted = fake_session.post_calls[0][1]["json"]
        self.assertEqual(posted["voiceRuntimeContext"], facts)
        self.assertEqual(posted["text"], "Current settings?")

    def test_listen_only_response_returns_without_stream_subscription(self) -> None:
        fake_session = _FakeListenOnlySession()

        async def run_stream() -> None:
            ctx = ChatContext(items=[ChatMessage(role="user", content=["ambient transcript"])])
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            stream = llm.chat(chat_ctx=ctx)
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                async with stream:
                    async for _chunk in stream:
                        pass

        asyncio.run(run_stream())

        self.assertEqual(len(fake_session.post_calls), 1)
        self.assertEqual(fake_session.get_calls, [])

    def test_provider_speaker_id_reaches_voice_chat_post_as_structured_segment(self) -> None:
        fake_session = _FakeListenOnlySession()
        tracker = SpeakerSegmentTracker(
            call_session_id="call_1",
            participant_identity="owner-participant",
            participant_name="Owner",
            track_sid="TR_owner_mic",
            owner_signed=True,
        )
        tracker.ingest(
            transcript="Synthetic owner request",
            is_final=True,
            provider_speaker_id="A",
            created_at=100.0,
            start_time=10.0,
            end_time=11.0,
        )
        message = ChatMessage(role="user", content=["Synthetic owner request"])
        attach_speaker_context_to_message(tracker, message)

        async def run_stream() -> None:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            stream = llm.chat(chat_ctx=ChatContext(items=[message]))
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                async with stream:
                    async for _chunk in stream:
                        pass

        asyncio.run(run_stream())

        posted = fake_session.post_calls[0][1]["json"]
        self.assertEqual(posted["speakerLabel"], "Owner")
        self.assertEqual(posted["speakerSegmentRevisions"], [])
        self.assertEqual(
            posted["speakerSegments"][0]["speaker"]["providerSpeakerId"],
            "A",
        )
        self.assertEqual(
            posted["speakerSegments"][0]["speaker"]["actorTrust"],
            "owner_participant",
        )

    def test_signed_owner_wing_engagement_reaches_core_without_browser_reinterpretation(self) -> None:
        fake_session = _FakeListenOnlySession()
        tracker = SpeakerSegmentTracker(
            call_session_id="call_1",
            participant_identity="owner-participant",
            participant_name="Owner",
            track_sid="TR_owner_mic",
            owner_signed=True,
        )
        tracker.ingest(
            transcript="Please launch my worker.",
            is_final=True,
            provider_speaker_id="A",
            created_at=100.0,
            start_time=10.0,
            end_time=11.0,
        )
        message = ChatMessage(role="user", content=["Please launch my worker."])
        context = attach_speaker_context_to_message(tracker, message)
        receipt = {
            "version": 1,
            "callSessionId": "call_1",
            "turnId": "turn_000001",
            "participantIdentity": "owner-participant",
            "segmentIds": ["segment_000001"],
            "directlyAddressed": True,
            "source": "semantic_model",
            "revision": 1,
            "issuedAtMs": 1787659200000,
            "expiresAtMs": 1787659230000,
            "attestation": "synthetic-signed-owner-engagement",
        }
        context["voiceEngagement"] = receipt

        async def run_stream() -> None:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            stream = llm.chat(chat_ctx=ChatContext(items=[message]))
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                async with stream:
                    async for _chunk in stream:
                        pass

        asyncio.run(run_stream())

        posted = fake_session.post_calls[0][1]["json"]
        self.assertEqual(posted["voiceEngagement"], receipt)

    def test_posts_per_turn_stream_id_to_librechat(self) -> None:
        fake_session = _FakeListenOnlySession()
        captured_stream_ids: list[str] = []

        async def run_stream() -> None:
            ctx = ChatContext(items=[ChatMessage(role="user", content=["ambient transcript"])])
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            stream = llm.chat(chat_ctx=ctx)
            captured_stream_ids.append(stream._request_id)
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                async with stream:
                    async for _chunk in stream:
                        pass

        asyncio.run(run_stream())

        self.assertEqual(len(fake_session.post_calls), 1)
        post_json = fake_session.post_calls[0][1]["json"]
        self.assertEqual(post_json["streamId"], captured_stream_ids[0])
        self.assertTrue(post_json["streamId"].startswith("lc_"))
        self.assertEqual(post_json["viventiumTextDeltaMode"], "auto")

    def test_posts_stable_opaque_source_event_id_without_capability_authority(self) -> None:
        message = ChatMessage(role="user", content=["stable utterance"])
        posted_source_ids: list[str] = []

        async def run_once() -> None:
            fake_session = _FakeListenOnlySession()
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            stream = llm.chat(chat_ctx=ChatContext(items=[message]))
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                async with stream:
                    async for _chunk in stream:
                        pass
            payload = fake_session.post_calls[0][1]["json"]
            posted_source_ids.append(payload["sourceEventId"])
            self.assertNotIn("segment_stability", payload)
            self.assertNotIn("supersede_scope", payload)
            self.assertNotIn("interactionAdapterCapabilities", payload)

        asyncio.run(run_once())
        asyncio.run(run_once())

        self.assertEqual(posted_source_ids[0], posted_source_ids[1])
        self.assertIn(message.id, posted_source_ids[0])
        self.assertNotIn("stable utterance", posted_source_ids[0])


class _PublicVoicePresentationCoordinatorTests(unittest.TestCase):
    __test__ = False

    def test_provisional_acoustic_interruption_does_not_supersede_presentation(self) -> None:
        coordinator = _VoicePresentationCoordinator()
        presentation = coordinator.begin_stable(
            source_event_id="voice:call:item:one",
            presentation_ref="speech-one",
        )

        coordinator.note_provisional_interruption(presentation)

        self.assertTrue(coordinator.is_current(presentation))

    def test_next_stable_utterance_permanently_supersedes_old_presentation(self) -> None:
        coordinator = _VoicePresentationCoordinator()
        first = coordinator.begin_stable(
            source_event_id="voice:call:item:one",
            presentation_ref="speech-one",
        )
        coordinator.bind_core_context(
            first,
            {"logical_turn_id": "logical-1", "revision": 1},
        )

        second = coordinator.begin_stable(
            source_event_id="voice:call:item:two",
            presentation_ref="speech-two",
        )
        coordinator.bind_core_context(
            second,
            {"logicalTurnId": "logical-1", "revision": 2},
        )

        self.assertFalse(coordinator.is_current(first))
        self.assertTrue(coordinator.is_current(second))
        self.assertEqual(second.logical_turn_id, "logical-1")
        self.assertEqual(second.revision, 2)

    def test_delivery_ack_is_optional_and_uses_voice_scoped_adapter_contract(self) -> None:
        async def run() -> tuple[bool, _FakeDeliveryAckSession]:
            fake_session = _FakeDeliveryAckSession()
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="voice-secret"),
            )
            with (
                patch.dict(
                    os.environ,
                    {
                        "VIVENTIUM_DELIVERY_ACK_ENDPOINT": "/api/viventium/interactions/delivery-ack",
                        "VIVENTIUM_VOICE_INTERACTION_ADAPTER_SECRET": "adapter-secret",
                    },
                    clear=True,
                ),
                patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session),
            ):
                accepted = await llm.ack_delivery(
                    logical_turn_id="logical-1",
                    revision=2,
                    state="committed",
                    presentation_ref="speech-one",
                )
            return accepted, fake_session

        accepted, fake_session = asyncio.run(run())

        self.assertTrue(accepted)
        url, _args, kwargs = fake_session.post_calls[0]
        self.assertEqual(
            url,
            "http://librechat.test/api/viventium/interactions/delivery-ack",
        )
        self.assertEqual(
            kwargs["json"],
            {
                "logical_turn_id": "logical-1",
                "revision": 2,
                "state": "committed",
                "presentation_ref": "speech-one",
            },
        )
        self.assertEqual(
            kwargs["headers"]["x-viventium-adapter-secret"],
            "adapter-secret",
        )

    def test_delivery_ack_never_falls_back_to_a_shared_adapter_secret(self) -> None:
        async def run() -> tuple[bool, _FakeDeliveryAckSession]:
            fake_session = _FakeDeliveryAckSession()
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="voice-secret"),
            )
            with (
                patch.dict(
                    os.environ,
                    {
                        "VIVENTIUM_DELIVERY_ACK_ENDPOINT": "/api/viventium/interactions/delivery-ack",
                        "VIVENTIUM_INTERACTION_ADAPTER_SECRET": "shared-secret",
                    },
                    clear=True,
                ),
                patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session),
            ):
                accepted = await llm.ack_delivery(
                    logical_turn_id="logical-1",
                    revision=1,
                    state="committed",
                )
            return accepted, fake_session

        accepted, fake_session = asyncio.run(run())

        self.assertFalse(accepted)
        self.assertEqual(fake_session.post_calls, [])

    def test_delivery_ack_missing_contract_is_unavailable_not_failed(self) -> None:
        async def run() -> bool:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="voice-secret"),
            )
            with patch.dict(os.environ, {}, clear=True):
                return await llm.ack_delivery(
                    logical_turn_id="logical-1",
                    revision=1,
                    state="committed",
                    presentation_ref="speech-one",
                )

        self.assertFalse(asyncio.run(run()))

    def test_delivery_ack_retries_one_transient_failure_idempotently(self) -> None:
        async def run() -> tuple[bool, list[tuple]]:
            statuses = [503, 200]
            calls: list[tuple] = []

            class _RetrySession:
                async def __aenter__(self):
                    return self

                async def __aexit__(self, exc_type, exc, tb):
                    return False

                def post(self, url, *args, **kwargs):
                    calls.append((url, args, kwargs))
                    return _SequencedStatusResponse(statuses.pop(0), {})

            async def _no_delay(_seconds: float) -> None:
                return None

            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="voice-secret"),
            )
            with (
                patch.dict(
                    os.environ,
                    {
                        "VIVENTIUM_DELIVERY_ACK_ENDPOINT": "/api/viventium/interactions/delivery-ack",
                        "VIVENTIUM_VOICE_INTERACTION_ADAPTER_SECRET": "adapter-secret",
                    },
                    clear=True,
                ),
                patch("librechat_llm.aiohttp.ClientSession", return_value=_RetrySession()),
                patch("librechat_llm.asyncio.sleep", side_effect=_no_delay),
            ):
                accepted = await llm.ack_delivery(
                    logical_turn_id="logical-1",
                    revision=2,
                    state="committed",
                    presentation_ref="speech-one",
                )
            return accepted, calls

        accepted, calls = asyncio.run(run())

        self.assertTrue(accepted)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][2]["json"], calls[1][2]["json"])

    def test_production_trace_posts_exact_lease_bound_content_free_contract(self) -> None:
        async def run() -> tuple[bool, _FakeDeliveryAckSession]:
            fake_session = _FakeDeliveryAckSession()
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(
                    call_session_id="call_1",
                    call_secret="voice-secret",
                    job_id="job_1",
                    worker_id="worker_1",
                ),
            )
            trace = VoiceHopTrace(correlation_id="request_1", call_session_id="call_1")
            llm.register_trace(trace)
            presentation = llm._presentation_coordinator.begin_stable(
                source_event_id="voice:call_1:item:one",
                presentation_ref="request_1",
            )
            llm._presentation_coordinator.bind_core_context(
                presentation,
                {"logical_turn_id": "logical-1", "revision": 2},
            )
            llm.bind_trace_core_context(
                "request_1",
                stream_id="stream_1",
                task_id="task_1",
                presentation=presentation,
            )
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                accepted = await llm._post_production_trace(
                    "request_1",
                    "tts.completed",
                )
            return accepted, fake_session

        accepted, fake_session = asyncio.run(run())

        self.assertTrue(accepted)
        self.assertEqual(len(fake_session.post_calls), 1)
        url, _args, kwargs = fake_session.post_calls[0]
        self.assertEqual(url, "http://librechat.test/api/viventium/voice/trace/stages")
        self.assertEqual(
            kwargs["headers"],
            {
                "Content-Type": "application/json",
                "X-VIVENTIUM-CALL-SESSION": "call_1",
                "X-VIVENTIUM-CALL-SECRET": "voice-secret",
                "X-VIVENTIUM-JOB-ID": "job_1",
                "X-VIVENTIUM-WORKER-ID": "worker_1",
            },
        )
        self.assertEqual(
            kwargs["json"],
            {
                "version": 1,
                "callSessionId": "call_1",
                "turnId": "logical-1",
                "streamId": "stream_1",
                "taskId": "task_1",
                "presentationRef": "request_1",
                "stage": "tts.completed",
            },
        )
        self.assertNotIn("text", json.dumps(kwargs["json"]).lower())

    def test_audio_trace_requires_current_audible_committed_playout(self) -> None:
        async def run(*, audible: bool, acked: bool) -> list:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="voice-secret"),
            )
            llm.ack_delivery = AsyncMock(return_value=acked)
            llm._post_production_trace = AsyncMock(return_value=True)
            handle = _CompletableSpeechHandle("speech-one")
            llm.register_speech_handle(handle)
            presentation = llm.chat(
                chat_ctx=ChatContext(items=[ChatMessage(role="user", content=["hello"])])
            )._presentation
            trace_id = presentation.trace_id
            llm.register_trace(VoiceHopTrace(correlation_id=trace_id, call_session_id="call_1"))
            llm._presentation_coordinator.bind_core_context(
                presentation,
                {"logical_turn_id": "logical-1", "revision": 1},
            )
            llm.bind_trace_core_context(
                trace_id,
                stream_id="stream_1",
                task_id="task_1",
                presentation=presentation,
            )
            if audible:
                handle.mark_audible_playout()
            handle.complete(interrupted=False)
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            return llm._post_production_trace.await_args_list

        completed = asyncio.run(run(audible=True, acked=True))
        self.assertEqual(len(completed), 1)
        self.assertTrue(completed[0].args[0].startswith("lc_"))
        self.assertEqual(completed[0].args[1], "audio.completed")
        failed = asyncio.run(run(audible=False, acked=True))
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0].args[1], 'audio.failed')
        self.assertEqual(asyncio.run(run(audible=True, acked=False)), [])

    def test_terminal_audio_failure_and_interruption_stages_reach_the_trace_producer(self) -> None:
        async def run() -> list:
            llm = LibreChatLLM(origin='http://librechat.test',
                auth=LibreChatAuth(call_session_id='call_1', call_secret='voice-secret'))
            llm._post_production_trace = AsyncMock(return_value=True)
            for stage in ['audio.failed', 'audio.interrupted', 'audio.superseded']:
                self.assertTrue(llm.record_completed_trace_stage('request_1', stage))
                self.assertFalse(llm.record_completed_trace_stage('request_1', stage))
            await asyncio.sleep(0)
            return llm._post_production_trace.await_args_list
        self.assertEqual([call.args[1] for call in asyncio.run(run())],
                         ['audio.failed', 'audio.interrupted', 'audio.superseded'])

    def test_core_turn_identity_is_bound_and_superseded_stream_emits_no_stale_chunks(self) -> None:
        events = [
            {
                "event": "voice_task_event",
                "voiceTaskEvent": _voice_task_event("event_1", 1),
            },
            {"text": "This stale answer must not be presented."},
            {
                "final": True,
                "responseMessage": {
                    "messageId": "msg-old",
                    "content": [{"type": "text", "text": "Stale final."}],
                },
            },
        ]

        async def run() -> tuple[list[str], list[dict], list, object]:
            fake_session = _FakeLogicalStreamingSseSession(events)
            relayed = []
            followups = []
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
                task_event_handler=relayed.append,
                followup_handler=lambda *args, **kwargs: followups.append((args, kwargs)),
            )
            old_stream = llm.chat(
                chat_ctx=ChatContext(items=[ChatMessage(role="user", content=["first"])])
            )
            second_presentation = llm._presentation_coordinator.begin_stable(
                source_event_id="voice:call_1:item:second",
                presentation_ref="speech-second",
            )
            self.assertTrue(
                llm._presentation_coordinator.is_current(second_presentation)
            )
            chunks = []
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                async with old_stream:
                    async for chunk in old_stream:
                        if chunk.delta and chunk.delta.content:
                            chunks.append(chunk.delta.content)
            return chunks, relayed, followups, old_stream._presentation

        chunks, relayed, followups, presentation = asyncio.run(run())

        self.assertEqual(chunks, [])
        self.assertEqual(len(relayed), 1)
        self.assertEqual(relayed[0]["taskId"], "task_1")
        self.assertEqual(followups, [])
        self.assertEqual(presentation.logical_turn_id, "logical-1")
        self.assertEqual(presentation.revision, 2)

    def test_playout_completion_acknowledges_current_or_retracts_superseded_presentation(self) -> None:
        async def run() -> list:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            llm.ack_delivery = AsyncMock(return_value=True)
            first_handle = _CompletableSpeechHandle("speech-first")
            llm.register_speech_handle(first_handle)
            first = llm.chat(
                chat_ctx=ChatContext(items=[ChatMessage(role="user", content=["first"])])
            )._presentation
            llm._presentation_coordinator.bind_core_context(
                first,
                {"logical_turn_id": "logical-1", "revision": 1},
            )

            second_handle = _CompletableSpeechHandle("speech-second")
            llm.register_speech_handle(second_handle)
            second = llm.chat(
                chat_ctx=ChatContext(items=[ChatMessage(role="user", content=["second"])])
            )._presentation
            llm._presentation_coordinator.bind_core_context(
                second,
                {"logical_turn_id": "logical-1", "revision": 2},
            )
            first_handle.mark_audible_playout()
            first_handle.complete(interrupted=False)
            second_handle.mark_audible_playout()
            second_handle.complete(interrupted=False)
            await asyncio.sleep(0)
            return llm.ack_delivery.await_args_list

        acknowledgements = asyncio.run(run())

        self.assertEqual(acknowledgements[0].kwargs["state"], "partial_removed")
        self.assertEqual(acknowledgements[0].kwargs["presentation_ref"], "speech-first")
        self.assertEqual(acknowledgements[1].kwargs["state"], "committed")
        self.assertEqual(acknowledgements[1].kwargs["revision"], 2)

    def test_interrupted_playback_without_a_stable_successor_retains_main(self) -> None:
        async def run(*, closing: bool, detached: bool):
            llm = LibreChatLLM(origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"))
            llm.ack_delivery = AsyncMock(return_value=True)
            llm.record_completed_trace_stage = Mock()
            handle = _CompletableSpeechHandle("ended-speech")
            llm.register_speech_handle(handle)
            presentation = llm.chat(chat_ctx=ChatContext(items=[
                ChatMessage(id="owned-source", role="user", content=["A useful answer."])
            ]))._presentation
            llm._presentation_coordinator.bind_core_context(presentation,
                {"logical_turn_id": "logical-1", "revision": 1})
            llm._speaker_delivery_closing = closing
            if detached:
                llm._presentation_coordinator._current = None
            handle.mark_audible_playout()
            handle.complete(interrupted=True)
            await asyncio.sleep(0)
            self.assertEqual(llm.ack_delivery.await_args.kwargs["state"], "failed")
            self.assertEqual(presentation.delivery_state, "failed")
            llm.record_completed_trace_stage.assert_called_once_with(
                presentation.trace_id, "audio.interrupted")
        for closing, detached in [(False, False), (True, False), (True, True)]:
            with self.subTest(closing=closing, detached=detached):
                asyncio.run(run(closing=closing, detached=detached))

    def test_interrupted_playback_removes_only_a_distinct_stable_source(self) -> None:
        async def run(*, same_source: bool):
            llm = LibreChatLLM(origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"))
            llm.ack_delivery = AsyncMock(return_value=True)
            first = llm._presentation_coordinator.begin_stable(
                source_event_id="source-one", presentation_ref="speech-one")
            llm._presentation_coordinator.bind_core_context(first,
                {"logical_turn_id": "logical-1", "revision": 1})
            llm._presentation_coordinator.begin_stable(
                source_event_id="source-one" if same_source else "source-two",
                presentation_ref="speech-two")
            handle = _CompletableSpeechHandle("speech-one")
            handle.mark_audible_playout()
            handle.complete(interrupted=True)
            self.assertTrue(await llm._ack_completed_presentation(first, handle))
            self.assertEqual(llm.ack_delivery.await_args.kwargs["state"],
                "failed" if same_source else "partial_removed")
        for same_source in [False, True]:
            with self.subTest(same_source=same_source):
                asyncio.run(run(same_source=same_source))

    def test_playout_completion_fails_current_presentation_without_audible_output(self) -> None:
        async def run(*, include_unplayed_assistant_item: bool) -> list:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            llm.ack_delivery = AsyncMock(return_value=True)
            handle = _CompletableSpeechHandle("speech-no-audio")
            if include_unplayed_assistant_item:
                handle.chat_items.append(
                    ChatMessage(role="assistant", content=["Generated but never played."])
                )
            llm.register_speech_handle(handle)
            presentation = llm.chat(
                chat_ctx=ChatContext(items=[ChatMessage(role="user", content=["hello"])])
            )._presentation
            llm._presentation_coordinator.bind_core_context(
                presentation,
                {"logical_turn_id": "logical-1", "revision": 1},
            )
            handle.complete(interrupted=False)
            await asyncio.sleep(0)
            return llm.ack_delivery.await_args_list

        for include_unplayed_assistant_item in (False, True):
            with self.subTest(
                outcome="terminal_tts_failure"
                if not include_unplayed_assistant_item
                else "zero_audio_playout"
            ):
                acknowledgements = asyncio.run(
                    run(include_unplayed_assistant_item=include_unplayed_assistant_item)
                )
                self.assertEqual(len(acknowledgements), 1)
                self.assertEqual(acknowledgements[0].kwargs["state"], "failed")

    def test_false_barge_in_resumes_and_commits_after_positive_playout(self) -> None:
        async def run() -> list:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            llm.ack_delivery = AsyncMock(return_value=True)
            handle = _CompletableSpeechHandle("speech-resumed")
            llm.register_speech_handle(handle)
            presentation = llm.chat(
                chat_ctx=ChatContext(items=[ChatMessage(role="user", content=["hello"])])
            )._presentation
            llm._presentation_coordinator.bind_core_context(
                presentation,
                {"logical_turn_id": "logical-1", "revision": 1},
            )
            llm.note_provisional_interruption()
            handle.mark_audible_playout()
            handle.complete(interrupted=False)
            await asyncio.sleep(0)
            return llm.ack_delivery.await_args_list

        acknowledgements = asyncio.run(run())

        self.assertEqual(len(acknowledgements), 1)
        self.assertEqual(acknowledgements[0].kwargs["state"], "committed")

    def test_sse_close_does_not_cancel_backend_task(self) -> None:
        fake_session = _FakeClosedStreamSession()
        os.environ["VIVENTIUM_VOICE_SSE_MAX_RETRIES"] = "0"
        os.environ["VIVENTIUM_VOICE_SSE_RETRY_DELAY_S"] = "0.01"
        try:
            async def run_stream() -> None:
                ctx = ChatContext(items=[ChatMessage(role="user", content=["hello"])])
                llm = LibreChatLLM(
                    origin="http://librechat.test",
                    auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
                )
                stream = llm.chat(chat_ctx=ctx)
                with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                    await stream._run()

            asyncio.run(run_stream())
        finally:
            os.environ.pop("VIVENTIUM_VOICE_SSE_MAX_RETRIES", None)
            os.environ.pop("VIVENTIUM_VOICE_SSE_RETRY_DELAY_S", None)

        self.assertGreaterEqual(len(fake_session.get_calls), 1)
        post_urls = [call[0] for call in fake_session.post_calls]
        self.assertIn("http://librechat.test/api/viventium/voice/chat", post_urls)
        self.assertNotIn(
            "http://librechat.test/api/viventium/voice/stream/stream_voice_1/abort",
            post_urls,
        )

    def test_livekit_stream_interruption_does_not_cancel_backend_task(self) -> None:
        async def run_stream() -> _FakeBlockingStreamSession:
            fake_session = _FakeBlockingStreamSession()
            ctx = ChatContext(items=[ChatMessage(role="user", content=["hello"])])
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            stream = llm.chat(chat_ctx=ctx)
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                task = asyncio.create_task(stream._run())
                await asyncio.wait_for(fake_session.sse_started.wait(), timeout=1.0)
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
            return fake_session

        fake_session = asyncio.run(run_stream())

        post_urls = [call[0] for call in fake_session.post_calls]
        self.assertNotIn(
            "http://librechat.test/api/viventium/voice/stream/stream_voice_cancel_1/abort",
            post_urls,
        )
        self.assertFalse(fake_session.abort_completed)

    def test_interruption_detaches_task_only_resume_through_completion(self) -> None:
        running = _voice_task_event("event_1", 1)
        source = _voice_task_event(
            "event_2",
            2,
            phase="source",
            event_type="source",
            source={"title": "Synthetic source", "url": "https://example.test/source"},
        )
        completed = _voice_task_event(
            "event_3",
            3,
            state="completed",
            phase="completed",
            event_type="result",
        )
        fake_session = _FakeInterruptedThenCompletedSession(
            running,
            [
                {"event": "voice_task_event", "voiceTaskEvent": running},
                {"event": "voice_task_event", "voiceTaskEvent": source},
                {
                    "event": "on_message_delta",
                    "data": {
                        "delta": {
                            "content": [
                                {
                                    "type": "tool_call",
                                    "tool_call": {
                                        "function": {
                                            "name": "delegate_mcp_glasshive-workers-projects"
                                        }
                                    },
                                }
                            ]
                        }
                    },
                },
                {"text": "Late result must never reach model or TTS output."},
                {"event": "voice_task_event", "voiceTaskEvent": completed},
                {
                    "final": True,
                    "responseMessage": {
                        "messageId": "msg_resume_1",
                        "content": [{"type": "text", "text": "Persisted result."}],
                    },
                },
            ],
        )
        relayed = []
        followups = []
        async def run_stream() -> None:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
                task_event_handler=relayed.append,
                followup_handler=lambda *args, **kwargs: followups.append((args, kwargs)),
            )
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                await llm._relay_task_event_once(running)
                # The interrupted foreground owned the first subscription. The detached,
                # task-only continuation starts at the resumable second subscription.
                fake_session.get_calls.append(("interrupted-primary", (), {}))
                llm._start_task_continuation(
                    stream_id="stream_resume_1",
                    task_id="task_1",
                    headers={
                        "X-VIVENTIUM-CALL-SESSION": "call_1",
                        "X-VIVENTIUM-CALL-SECRET": "secret",
                    },
                    request_id="request_1",
                    pending_insights=[],
                    saw_cortex_event=False,
                    saw_glasshive_tool_call=False,
                    cortex_message_id="",
                    hop_trace=VoiceHopTrace(
                        correlation_id="request_1",
                        call_session_id="call_1",
                    ),
                )
                await llm.wait_for_background_continuations(timeout_s=1.0)

        asyncio.run(run_stream())

        self.assertEqual(relayed, [running, source, completed])
        self.assertEqual(len(followups), 1)
        self.assertEqual(followups[0][0][0], "msg_resume_1")
        self.assertEqual(followups[0][0][2], "")
        self.assertTrue(followups[0][1]["glasshive_expected"])

    def test_call_lifetime_task_stream_relays_child_after_parent_stream_ended(self) -> None:
        parent_completed = _voice_task_event(
            "parent_completed",
            9,
            taskId="task_parent",
            state="completed",
            phase="completed",
            event_type="result",
        )
        child_queued = _voice_task_event(
            "child_queued",
            1,
            taskId="task_child_retry",
            state="queued",
            phase="queued",
            event_type="snapshot",
            parentTaskId="task_parent",
        )
        child_source = _voice_task_event(
            "child_source",
            2,
            taskId="task_child_retry",
            state="running",
            phase="source",
            event_type="source",
            parentTaskId="task_parent",
            source={"title": "Synthetic source", "url": "https://example.test/retry"},
        )
        child_completed = _voice_task_event(
            "child_completed",
            3,
            taskId="task_child_retry",
            state="completed",
            phase="completed",
            event_type="result",
            parentTaskId="task_parent",
        )
        fake_session = _CallTaskEventSession(
            [parent_completed, child_queued, child_source, child_completed]
        )
        relayed: list[dict] = []

        async def run() -> None:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(
                    call_session_id="call_1",
                    call_secret="secret",
                    job_id="job_1",
                    worker_id="worker_1",
                ),
                task_event_handler=relayed.append,
            )
            await llm._relay_task_event_once(parent_completed)
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                task = llm.start_call_task_event_stream(
                    reconnect_min_s=0.01,
                    reconnect_max_s=0.02,
                )
                self.assertIsNotNone(task)
                await asyncio.wait_for(fake_session.delivered.wait(), timeout=1.0)
                await llm.stop_call_task_event_stream()
            await llm.close_background_continuations()

        asyncio.run(run(), debug=True)

        self.assertEqual(
            [event["eventId"] for event in relayed],
            ["parent_completed", "child_queued", "child_source", "child_completed"],
        )
        self.assertEqual(len(fake_session.get_calls), 1)
        url, _args, kwargs = fake_session.get_calls[0]
        self.assertEqual(
            url,
            "http://librechat.test/api/viventium/voice/tasks/events",
        )
        self.assertEqual(kwargs["params"], {"callSessionId": "call_1"})
        self.assertEqual(
            kwargs["headers"],
            {
                "Accept": "text/event-stream",
                "X-VIVENTIUM-CALL-SESSION": "call_1",
                "X-VIVENTIUM-CALL-SECRET": "secret",
                "X-VIVENTIUM-JOB-ID": "job_1",
                "X-VIVENTIUM-WORKER-ID": "worker_1",
            },
        )
        self.assertTrue(fake_session.closed)

    def test_call_lifetime_stream_relays_later_completed_source_after_cancel_race(self) -> None:
        completed = _voice_task_event(
            "completed_after_cancel_race",
            7,
            taskId="task_raced",
            state="completed",
            phase="completed",
            event_type="result",
        )
        late_source = _voice_task_event(
            "late_completed_source",
            8,
            taskId="task_raced",
            state="completed",
            phase="source",
            event_type="source",
            source={"title": "Completed source", "url": "https://example.test/completed"},
        )
        late_result = _voice_task_event(
            "late_completed_result",
            9,
            taskId="task_raced",
            state="completed",
            phase="completed",
            event_type="result",
            resultMessageId="msg_completed",
        )
        fake_session = _CallTaskEventSession([completed, late_source, late_result])
        relayed: list[dict] = []

        async def run() -> bool:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(
                    call_session_id="call_1",
                    call_secret="secret",
                    job_id="job_1",
                    worker_id="worker_1",
                ),
                task_event_handler=relayed.append,
            )
            # LibreChat's exact GlassHive 409 already_completed means cancellation was
            # never accepted. The gateway deliberately keeps its local speech barrier,
            # while higher-sequence completed source/result events remain visible.
            llm._task_event_gate.mark_cancel_accepted("task_raced")
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                llm.start_call_task_event_stream(
                    reconnect_min_s=0.01,
                    reconnect_max_s=0.02,
                )
                await asyncio.wait_for(fake_session.delivered.wait(), timeout=1.0)
                await llm.stop_call_task_event_stream()
            suppressed = llm.is_task_output_suppressed("task_raced")
            await llm.close_background_continuations()
            return suppressed

        self.assertTrue(asyncio.run(run(), debug=True))
        self.assertEqual(
            [event["eventId"] for event in relayed],
            ["completed_after_cancel_race", "late_completed_source", "late_completed_result"],
        )

    def test_call_lifetime_task_stream_reconnects_with_full_job_auth_and_closes_cleanly(self) -> None:
        child_running = _voice_task_event(
            "child_after_reconnect",
            1,
            taskId="task_child",
            state="running",
            phase="tool",
            event_type="progress",
        )
        fake_session = _ReconnectCallTaskEventSession([child_running])
        relayed: list[dict] = []

        async def run() -> list[str]:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(
                    call_session_id="call_1",
                    call_secret="secret",
                    job_id="job_1",
                    worker_id="worker_1",
                ),
                task_event_handler=relayed.append,
            )
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                stream_task = llm.start_call_task_event_stream(
                    reconnect_min_s=0.01,
                    reconnect_max_s=0.02,
                )
                await asyncio.wait_for(fake_session.delivered.wait(), timeout=1.0)
                await llm.close_background_continuations()
            self.assertTrue(stream_task.done())
            return [task.get_name() for task in asyncio.all_tasks() if not task.done()]

        live_task_names = asyncio.run(run(), debug=True)

        self.assertEqual([event["eventId"] for event in relayed], ["child_after_reconnect"])
        self.assertEqual(len(fake_session.get_calls), 2)
        self.assertTrue(fake_session.closed)
        self.assertFalse(any(name.startswith("viventium-call-task-events:") for name in live_task_names))

    def test_call_lifetime_task_stream_requires_exact_job_and_worker_auth(self) -> None:
        async def run() -> None:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            self.assertIsNone(llm.start_call_task_event_stream())
            await llm.close_background_continuations()

        asyncio.run(run(), debug=True)

    def test_call_task_stream_startup_401_never_reports_ready(self) -> None:
        fake_session = _CallTaskStatusSession(401)
        health: list[dict] = []

        async def run() -> tuple[bool, dict, list[str]]:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(
                    call_session_id="call_1",
                    call_secret="secret",
                    job_id="job_1",
                    worker_id="worker_1",
                ),
            )
            llm.set_call_task_event_stream_health_handler(health.append)
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                llm.start_call_task_event_stream()
                ready = await llm.wait_call_task_event_stream_ready(timeout_s=0.5)
                snapshot = llm.call_task_event_stream_health
                await llm.close_background_continuations()
            live = [task.get_name() for task in asyncio.all_tasks() if not task.done()]
            return ready, snapshot, live

        ready, snapshot, live = asyncio.run(run(), debug=True)

        self.assertFalse(ready)
        self.assertEqual(snapshot["state"], "terminal")
        self.assertEqual(snapshot["status"], 401)
        self.assertEqual([item["state"] for item in health[:2]], ["connecting", "terminal"])
        self.assertTrue(fake_session.closed)
        self.assertFalse(any(name.startswith("viventium-call-task-events:") for name in live))

    def test_call_task_stream_2xx_without_sync_marker_never_reports_ready(self) -> None:
        fake_session = _CallTaskStatusSession(200)
        health: list[dict] = []

        async def run() -> bool:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(
                    call_session_id="call_1",
                    call_secret="secret",
                    job_id="job_1",
                    worker_id="worker_1",
                ),
            )
            llm.set_call_task_event_stream_health_handler(health.append)
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                llm.start_call_task_event_stream(
                    reconnect_min_s=0.01,
                    reconnect_max_s=0.01,
                )
                ready = await llm.wait_call_task_event_stream_ready(timeout_s=0.05)
                await llm.close_background_continuations()
            return ready

        self.assertFalse(asyncio.run(run(), debug=True))
        self.assertNotIn("connected", [item["state"] for item in health])

    def test_call_task_sync_marker_is_strictly_call_scoped(self) -> None:
        fake_session = _CallTaskSyncOnlySession(
            _voice_task_sync(call_session_id="call_other")
        )

        async def run() -> bool:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(
                    call_session_id="call_1",
                    call_secret="secret",
                    job_id="job_1",
                    worker_id="worker_1",
                ),
            )
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                llm.start_call_task_event_stream()
                ready = await llm.wait_call_task_event_stream_ready(timeout_s=0.05)
                await llm.close_background_continuations()
            return ready

        self.assertFalse(asyncio.run(run(), debug=True))

    def test_call_task_sync_marker_rejects_malformed_contracts(self) -> None:
        valid = {**_voice_task_sync(), "_sse_event": "voice_task_sync"}
        malformed = (
            {**valid, "version": True},
            {**valid, "state": "ready"},
            {**valid, "emittedAt": "not-a-time"},
            {**valid, "emittedAt": "2026-08-09T20:37:59"},
            {**valid, "extra": "field"},
        )

        self.assertEqual(
            _extract_voice_task_sync(
                valid,
                expected_call_session_id="call_1",
            ),
            _voice_task_sync(),
        )
        for payload in malformed:
            with self.subTest(payload=payload):
                self.assertIsNone(
                    _extract_voice_task_sync(
                        payload,
                        expected_call_session_id="call_1",
                    )
                )

    def test_call_task_sync_marker_follows_all_initial_snapshot_events(self) -> None:
        snapshot = _voice_task_event(
            "initial_snapshot",
            1,
            taskId="task_snapshot",
            event_type="snapshot",
        )
        fake_session = _CallTaskEventSession([snapshot])
        relayed: list[dict] = []
        relayed_count_when_connected: list[int] = []

        async def run() -> bool:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(
                    call_session_id="call_1",
                    call_secret="secret",
                    job_id="job_1",
                    worker_id="worker_1",
                ),
                task_event_handler=relayed.append,
            )

            def on_health(item: dict) -> None:
                if item["state"] == "connected":
                    relayed_count_when_connected.append(len(relayed))

            llm.set_call_task_event_stream_health_handler(on_health)
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                llm.start_call_task_event_stream()
                ready = await llm.wait_call_task_event_stream_ready(timeout_s=0.5)
                await llm.close_background_continuations()
            return ready

        self.assertTrue(asyncio.run(run(), debug=True))
        self.assertEqual([event["eventId"] for event in relayed], ["initial_snapshot"])
        self.assertEqual(relayed_count_when_connected, [1])

    def test_disconnect_cancel_barrier_blocks_stale_chunks_then_reconnects_health(self) -> None:
        running = _voice_task_event("before_disconnect", 1, taskId="task_disconnect")
        stale_after_cancel = _voice_task_event(
            "stale_after_cancel",
            2,
            taskId="task_disconnect",
            state="running",
            phase="tool",
            event_type="progress",
        )
        completed = _voice_task_event(
            "completed_after_reconnect",
            3,
            taskId="task_disconnect",
            state="completed",
            phase="completed",
            event_type="result",
        )
        fake_session = _DisconnectThenReconnectCallTaskSession(
            [running],
            [stale_after_cancel, completed],
        )
        relayed: list[dict] = []
        health_states: list[str] = []
        disconnected = asyncio.Event()

        async def run() -> bool:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(
                    call_session_id="call_1",
                    call_secret="secret",
                    job_id="job_1",
                    worker_id="worker_1",
                ),
                task_event_handler=relayed.append,
            )

            def on_health(item: dict) -> None:
                health_states.append(item["state"])
                if item["state"] == "disconnected":
                    disconnected.set()

            llm.set_call_task_event_stream_health_handler(on_health)
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                llm.start_call_task_event_stream(
                    reconnect_min_s=0.05,
                    reconnect_max_s=0.05,
                )
                self.assertTrue(await llm.wait_call_task_event_stream_ready(timeout_s=0.5))
                await asyncio.wait_for(disconnected.wait(), timeout=0.5)
                llm._task_event_gate.mark_cancel_accepted("task_disconnect")
                await asyncio.wait_for(fake_session.delivered.wait(), timeout=1.0)
                await llm.close_background_continuations()
            return llm.is_task_output_suppressed("task_disconnect")

        self.assertTrue(asyncio.run(run(), debug=True))
        self.assertEqual(
            [event["eventId"] for event in relayed],
            ["before_disconnect", "completed_after_reconnect"],
        )
        self.assertIn("disconnected", health_states)
        self.assertGreaterEqual(health_states.count("connected"), 2)

    def test_unexpected_call_task_stream_death_is_terminal_and_leak_free(self) -> None:
        fake_session = _CallTaskEventSession(
            [_voice_task_event("consumer_death", 1, taskId="task_death")],
            marker_first=True,
        )
        health: list[dict] = []

        async def run() -> tuple[dict, list[str]]:
            def fail_consumer(_event: dict) -> None:
                raise RuntimeError("synthetic consumer failure")

            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(
                    call_session_id="call_1",
                    call_secret="secret",
                    job_id="job_1",
                    worker_id="worker_1",
                ),
                task_event_handler=fail_consumer,
            )
            llm.set_call_task_event_stream_health_handler(health.append)
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                stream = llm.start_call_task_event_stream()
                self.assertTrue(await llm.wait_call_task_event_stream_ready(timeout_s=0.5))
                await asyncio.wait_for(stream, timeout=0.5)
                snapshot = llm.call_task_event_stream_health
                await llm.close_background_continuations()
            live = [task.get_name() for task in asyncio.all_tasks() if not task.done()]
            return snapshot, live

        snapshot, live = asyncio.run(run(), debug=True)

        self.assertEqual(snapshot["state"], "terminal")
        self.assertIsNone(snapshot["status"])
        self.assertEqual(
            [item["state"] for item in health[:3]],
            ["connecting", "syncing", "connected"],
        )
        self.assertIn("terminal", [item["state"] for item in health])
        self.assertTrue(fake_session.closed)
        self.assertFalse(any(name.startswith("viventium-call-task-events:") for name in live))

    def test_explicit_task_cancel_calls_task_endpoint_once(self) -> None:
        fake_session = _FakeClosedStreamSession()
        cancel_acceptances = []

        async def cancel_twice() -> tuple[dict, dict]:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
                task_cancel_handler=lambda task_id, result: cancel_acceptances.append(
                    (task_id, result.get("state"))
                ),
            )
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                first = await llm.cancel_task("task_1", reason="user_requested")
                second = await llm.cancel_task("task_1", reason="user_requested")
            return first, second

        first, second = asyncio.run(cancel_twice())

        cancel_urls = [
            call[0]
            for call in fake_session.post_calls
            if "/voice/tasks/" in str(call[0])
        ]
        self.assertEqual(
            cancel_urls,
            ["http://librechat.test/api/viventium/voice/tasks/task_1/cancel"],
        )
        self.assertEqual(first, second)
        self.assertEqual(cancel_acceptances, [("task_1", first.get("state"))])

    def test_terminal_task_tombstone_precedes_publish_and_rejects_stale_replay(self) -> None:
        running = _voice_task_event("event_5", 5)
        cancelling = {
            **running,
            "eventId": "event_6",
            "sequence": 6,
            "state": "cancelling",
        }
        replay = {**running, "eventId": "event_4", "sequence": 4}
        observed = []

        async def run() -> tuple[bool, bool, bool]:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
                task_event_handler=lambda event: observed.append(
                    (event["sequence"], llm.is_task_output_suppressed("task_1"))
                ),
            )
            accepted_running = await llm._relay_task_event_once(running)
            accepted_cancelling = await llm._relay_task_event_once(cancelling)
            accepted_replay = await llm._relay_task_event_once(replay)
            return accepted_running, accepted_cancelling, accepted_replay

        accepted = asyncio.run(run())
        self.assertEqual(accepted, (True, True, False))
        self.assertEqual(observed, [(5, False), (6, True)])

    def test_cancel_suppression_survives_a_full_120_minute_soak(self) -> None:
        now = [0.0]
        gate = _VoiceTaskEventGate(clock=lambda: now[0])
        gate.mark_cancel_accepted("task_1")

        now[0] = 7_201.0

        self.assertTrue(gate.is_suppressed("task_1"))
        self.assertFalse(gate.accept(_voice_task_event("stale", 1)))

    def test_cancel_suppression_survives_more_than_ten_thousand_ordinary_tasks(self) -> None:
        now = [0.0]
        gate = _VoiceTaskEventGate(max_tasks=128, clock=lambda: now[0])
        gate.mark_cancel_accepted("task_cancelled")

        for index in range(10_500):
            event = _voice_task_event(
                f"ordinary_{index}",
                1,
                taskId=f"task_ordinary_{index}",
            )
            self.assertTrue(gate.accept(event))

        self.assertTrue(gate.is_suppressed("task_cancelled"))
        self.assertFalse(
            gate.accept(
                _voice_task_event(
                    "cancelled_stale_under_pressure",
                    1,
                    taskId="task_cancelled",
                )
            )
        )

    def test_live_suppression_is_never_evicted_by_tombstone_count_pressure(self) -> None:
        now = [0.0]
        gate = _VoiceTaskEventGate(clock=lambda: now[0])
        gate.mark_cancel_accepted("task_cancelled")

        for index in range(65_537):
            gate.mark_cancel_accepted(f"other_cancelled_{index}")

        self.assertTrue(gate.is_suppressed("task_cancelled"))

    def test_suppression_tombstones_expire_only_after_the_full_24_hour_ttl(self) -> None:
        now = [0.0]
        gate = _VoiceTaskEventGate(clock=lambda: now[0])
        gate.mark_cancel_accepted("task_cancelled")

        now[0] = 86_400.0
        self.assertTrue(gate.is_suppressed("task_cancelled"))
        now[0] = 86_400.001
        self.assertFalse(gate.is_suppressed("task_cancelled"))

    def test_explicit_task_cancel_stops_detached_continuation(self) -> None:
        fake_session = _FakeClosedStreamSession()

        async def run() -> bool:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            continuation = asyncio.create_task(asyncio.sleep(60))
            llm._background_continuations.add(continuation)
            llm._continuations_by_task["task_1"] = {continuation}
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                await llm.cancel_task("task_1")
            await asyncio.sleep(0)
            cancelled = continuation.cancelled()
            await llm.close_background_continuations()
            return cancelled

        self.assertTrue(asyncio.run(run()))

    def test_late_speaker_revision_posts_to_dedicated_endpoint_once(self) -> None:
        fake_session = _FakeClosedStreamSession()
        revision = {
            "version": 1,
            "callSessionId": "call_1",
            "turnId": "turn_000001",
            "segmentId": "segment_000001",
            "sequence": 1,
            "revision": 2,
            "text": "Synthetic words",
            "isFinal": True,
            "speaker": {
                "key": "provider:A",
                "label": "Speaker 1",
                "source": "provider_diarization",
                "attribution": "unverified",
                "actorTrust": "shared_mic_unverified",
                "providerSpeakerId": "A",
            },
        }

        async def post_twice() -> None:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                await llm.post_speaker_segment_revisions([revision])
                await llm.post_speaker_segment_revisions([revision])

        asyncio.run(post_twice())

        revision_calls = [
            call
            for call in fake_session.post_calls
            if str(call[0]).endswith("/voice/speaker-segments/revisions")
        ]
        self.assertEqual(len(revision_calls), 1)
        self.assertEqual(
            revision_calls[0][2]["json"],
            {
                "speakerSegmentRevisions": [revision],
                "ownerParticipantIdentity": "",
                "ownerTrackSid": "",
            },
        )

    def test_shared_mic_tombstone_persists_before_bounded_revision_pages(self) -> None:
        fake_session = _FakeClosedStreamSession()
        revisions = []
        for index in range(130):
            revisions.append(
                {
                    "version": 1,
                    "callSessionId": "call_1",
                    "turnId": f"turn_{index:06d}",
                    "segmentId": f"segment_{index:06d}",
                    "sequence": index + 1,
                    "revision": 2,
                    "text": "Synthetic words",
                    "isFinal": True,
                    "speaker": {
                        "key": "provider:A",
                        "label": "Speaker 1",
                        "source": "provider_diarization",
                        "attribution": "unverified",
                        "actorTrust": "shared_mic_unverified",
                        "providerSpeakerId": "A",
                        "trackSid": "TR_owner",
                        "participantIdentity": "owner",
                    },
                }
            )
        state = {
            "version": 1,
            "callSessionId": "call_1",
            "revision": 1,
            "attributionState": "shared_mic_unverified",
            "detectedAt": "2026-08-09T20:37:04.000Z",
            "sourceTrackSid": "TR_owner",
        }

        async def post() -> None:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                await llm.post_speaker_segment_revisions(
                    revisions,
                    session_state=state,
                )

        asyncio.run(post())
        calls = [call for call in fake_session.post_calls if "/voice/speaker" in str(call[0])]
        self.assertTrue(str(calls[0][0]).endswith("/voice/speaker-session-state"))
        revision_calls = [
            call for call in calls if str(call[0]).endswith("/voice/speaker-segments/revisions")
        ]
        self.assertEqual(
            [len(call[2]["json"]["speakerSegmentRevisions"]) for call in revision_calls],
            [64, 64, 2],
        )
        self.assertTrue(
            all(len(json.dumps(call[2]["json"])) < 128_000 for call in revision_calls)
        )

    def test_supervised_revision_queue_retries_beyond_three_and_never_overtakes_tombstone(self) -> None:
        fake_session = _RetryingSpeakerSession(transient_tombstone_failures=4)
        revision = {
            "version": 1,
            "callSessionId": "call_1",
            "turnId": "turn_1",
            "segmentId": "segment_1",
            "sequence": 1,
            "revision": 2,
            "text": "Synthetic words",
            "isFinal": True,
            "speaker": {
                "key": "provider:A",
                "label": "Speaker 1",
                "source": "provider_diarization",
                "attribution": "unverified",
                "actorTrust": "shared_mic_unverified",
                "providerSpeakerId": "A",
                "trackSid": "TR_owner",
            },
        }
        state = {
            "version": 1,
            "callSessionId": "call_1",
            "revision": 1,
            "attributionState": "shared_mic_unverified",
            "detectedAt": "2026-08-09T20:37:04.000Z",
            "sourceTrackSid": "TR_owner",
        }

        async def no_sleep(_delay):
            return None

        async def run() -> None:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            with (
                patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session),
                patch("librechat_llm.asyncio.sleep", side_effect=no_sleep),
            ):
                await llm.queue_speaker_segment_revisions(
                    [revision],
                    session_state=state,
                )
            await llm.close_background_continuations()

        asyncio.run(run())
        urls = [str(call[0]) for call in fake_session.post_calls]
        first_revision_index = next(
            index
            for index, url in enumerate(urls)
            if url.endswith("/voice/speaker-segments/revisions")
        )
        self.assertGreaterEqual(first_revision_index, 5)
        self.assertTrue(
            all(url.endswith("/voice/speaker-session-state") for url in urls[:first_revision_index])
        )

    def test_ambient_ingress_is_structured_and_idempotent(self) -> None:
        fake_session = _FakeClosedStreamSession()
        segment = {
            "version": 1,
            "callSessionId": "call_1",
            "turnId": "turn_ambient_001_000001",
            "segmentId": "segment_ambient_001_000001",
            "sequence": 1,
            "revision": 1,
            "text": "Synthetic guest context",
            "isFinal": True,
            "speaker": {
                "key": "participant:guest",
                "label": "Guest",
                "source": "hybrid",
                "attribution": "unverified",
                "actorTrust": "authenticated_participant",
            },
        }
        payload = {
            "version": 1,
            "callSessionId": "call_1",
            "mode": "wing",
            "ingressKind": "ambient_participant",
            "turnId": segment["turnId"],
            "segments": [segment],
        }

        async def post_twice() -> None:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                await llm.post_ambient_transcript(payload)
                await llm.post_ambient_transcript(payload)

        asyncio.run(post_twice())

        calls = [
            call for call in fake_session.post_calls
            if str(call[0]).endswith("/voice/ambient-transcript")
        ]
        self.assertEqual(len(calls), 1)
        self.assertEqual(
            calls[0][2]["json"],
            {
                "version": 1,
                "callSessionId": "call_1",
                "mode": "wing",
                "ingressKind": "ambient_participant",
                "turnId": segment["turnId"],
                "segments": [segment],
            },
        )

    def test_listen_only_owner_ingress_uses_exact_zero_authority_contract(self) -> None:
        fake_session = _FakeClosedStreamSession()
        segment = {
            "version": 1,
            "callSessionId": "call_1",
            "turnId": "turn_owner_1",
            "segmentId": "segment_owner_1",
            "sequence": 1,
            "revision": 1,
            "text": "Synthetic owner transcript",
            "isFinal": True,
            "speaker": {
                "key": "participant:owner",
                "label": "Owner",
                "source": "hybrid",
                "attribution": "verified",
                "actorTrust": "owner_participant",
                "participantIdentity": "owner",
            },
        }

        async def post():
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                await llm.post_ambient_transcript(
                    {
                        "version": 1,
                        "callSessionId": "call_1",
                        "mode": "listen_only",
                        "ingressKind": "listen_only_owner",
                        "segments": [segment],
                    }
                )

        asyncio.run(post())
        call = next(
            call
            for call in fake_session.post_calls
            if str(call[0]).endswith("/voice/ambient-transcript")
        )
        self.assertEqual(
            call[2]["json"],
            {
                "version": 1,
                "callSessionId": "call_1",
                "ingressKind": "listen_only_owner",
                "segments": [segment],
            },
        )
class _PublicLibreChatStreamingRunTests(unittest.TestCase):
    __test__ = False

    def test_abort_http_error_never_reads_or_logs_private_provider_body(self) -> None:
        sensitive = "SYNTHETIC_PRIVATE_ABORT_PROVIDER_CREDENTIAL"

        class _PrivateAbortResponse(_FakeClosedSseResponse):
            status = 503

            def __init__(self):
                self.body_reads = 0

            async def text(self):
                self.body_reads += 1
                return sensitive

        class _PrivateAbortSession:
            def __init__(self):
                self.response = _PrivateAbortResponse()

            def post(self, *_args, **_kwargs):
                return self.response

        async def run():
            fake_session = _PrivateAbortSession()
            with patch("librechat_llm.logger.warning") as warning:
                await _abort_librechat_voice_stream(
                    session=fake_session,
                    origin="http://librechat.test",
                    stream_id="stream_synthetic",
                    headers={},
                    request_id="request_synthetic",
                    started_at=0.0,
                    reason="user_requested",
                    log_latency=False,
                )
            return fake_session, warning

        fake_session, warning = asyncio.run(run())

        self.assertEqual(fake_session.response.body_reads, 0)
        self.assertNotIn(sensitive, str(warning.call_args_list))

    def test_stream_http_error_never_reads_or_logs_private_provider_body(self) -> None:
        sensitive = "SYNTHETIC_PRIVATE_STREAM_PROVIDER_CREDENTIAL"

        class _PrivateSseResponse(_FakeClosedSseResponse):
            status = 503

            def __init__(self):
                self.body_reads = 0

            async def text(self):
                self.body_reads += 1
                return sensitive

        class _PrivateStreamSession(_FakeClosedStreamSession):
            def __init__(self):
                super().__init__()
                self.response = _PrivateSseResponse()

            def get(self, *args, **kwargs):
                self.get_calls.append((args, kwargs))
                return self.response

        async def run():
            fake_session = _PrivateStreamSession()
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            stream = llm.chat(
                chat_ctx=ChatContext(items=[ChatMessage(role="user", content=["hello"])])
            )
            with (
                patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session),
                patch("librechat_llm.logger.warning") as warning,
            ):
                await stream._run()
            return fake_session, warning

        fake_session, warning = asyncio.run(run())

        self.assertEqual(fake_session.response.body_reads, 0)
        self.assertNotIn(sensitive, str(warning.call_args_list))

    def test_trace_grace_finalizer_is_timer_owned_and_cancelled_on_close(self) -> None:
        async def run():
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            trace = VoiceHopTrace(
                correlation_id="request_timer_lifecycle",
                call_session_id="call_1",
            )
            llm.register_trace(trace)
            llm.schedule_trace_terminal(trace, grace_s=60.0, stream_terminal=True)
            await asyncio.sleep(0)
            self.assertEqual(len(llm._trace_finalizers), 1)
            self.assertFalse(
                any(
                    isinstance(finalizer, asyncio.Task)
                    for finalizer in llm._trace_finalizers.values()
                )
            )
            await llm.close_background_continuations()
            self.assertEqual(llm._trace_finalizers, {})
            leaked = [
                task
                for task in asyncio.all_tasks()
                if task is not asyncio.current_task()
                and "_finalize_after_grace" in repr(task.get_coro())
            ]
            self.assertEqual(leaked, [])

        asyncio.run(run(), debug=True)

    def test_terminal_trace_finalizes_failure_before_tts_or_before_audio_once(self) -> None:
        llm = LibreChatLLM(
            origin="http://librechat.test",
            auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
        )
        before_tts = VoiceHopTrace(
            correlation_id="request_before_tts",
            call_session_id="call_1",
        )
        for hop, timestamp in (
            ("utterance_end", 1_000),
            ("gateway_dispatch", 1_100),
            ("agent_start", 1_200),
            ("first_model_token", 1_300),
        ):
            before_tts.record(hop, timestamp)
        before_audio = VoiceHopTrace(
            correlation_id="request_before_audio",
            call_session_id="call_1",
        )
        for hop, timestamp in (
            ("utterance_end", 2_000),
            ("gateway_dispatch", 2_100),
            ("agent_start", 2_200),
            ("first_model_token", 2_300),
            ("tts_first_byte", 2_400),
        ):
            before_audio.record(hop, timestamp)

        tts_failure = llm.finalize_trace_terminal(before_tts)
        audio_failure = llm.finalize_trace_terminal(before_audio)

        self.assertIn("tts_first_byte", tts_failure["missingHops"])
        self.assertIn("audio_output", tts_failure["missingHops"])
        self.assertNotIn("tts_first_byte", audio_failure["missingHops"])
        self.assertIn("audio_output", audio_failure["missingHops"])
        self.assertIsNone(llm.finalize_trace_terminal(before_audio))

    def test_tts_and_playout_are_correlated_to_oldest_eligible_trace_not_latest_global(self) -> None:
        llm = LibreChatLLM(
            origin="http://librechat.test",
            auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
        )
        first = VoiceHopTrace(correlation_id="request_1", call_session_id="call_1")
        second = VoiceHopTrace(correlation_id="request_2", call_session_id="call_1")
        first.record("first_model_token", 1_000)
        second.record("first_model_token", 1_100)
        llm.register_trace(first)
        llm.bind_trace_task("request_1", "task_1")
        llm.register_trace(second)
        llm.bind_trace_task("request_2", "task_2")

        tts_correlation = llm.record_next_trace_hop("tts_first_byte", 1_200)
        audio_correlation = llm.record_next_trace_hop("audio_output", 1_300)

        self.assertEqual(tts_correlation, "request_1")
        self.assertEqual(audio_correlation, "request_1")
        self.assertFalse(second.has("tts_first_byte"))

    def test_structured_tool_start_and_completion_record_distinct_hops(self) -> None:
        trace = VoiceHopTrace(correlation_id="request_1", call_session_id="call_1")
        start = {
            "event": "voice_task_event",
            "voiceTaskEvent": _voice_task_event(
                "event_start",
                1,
                detail="arbitrary localized copy",
            ),
        }
        completed = {
            "event": "on_run_step_completed",
            "data": {"id": "step_1", "result": {"content": "{}"}},
        }

        LibreChatLLM._record_tool_hops_from_event(trace, start, timestamp_ms=1_000)
        LibreChatLLM._record_tool_hops_from_event(trace, completed, timestamp_ms=1_250)

        self.assertTrue(trace.has("tool_start"))
        self.assertTrue(trace.has("tool_end"))
        self.assertIsNone(trace.first_breach({"tool_start->tool_end": 300}))

    def test_native_clarification_task_event_retains_exact_keys_and_rejects_duplicate_questions(self) -> None:
        task = _voice_task_event("native_question", 3)
        question = {"key": "Which  size?", "label": "Which size?", "multiSelect": False,
                    "options": [{"value": "Small", "label": "Small"}, {"value": "Other", "label": "Other"}]}
        task["needsInput"] = {"prompt": "Choose a size.", "inputType": "native_question", "questionForm": {"questions": [question]}}
        payload = {"event": "voice_task_event", "voiceTaskEvent": task}
        self.assertIs(_extract_voice_task_event(payload), task)
        task["needsInput"]["questionForm"]["questions"] = [question, question]
        self.assertIsNone(_extract_voice_task_event(payload))

    def test_extracts_canonical_named_sse_task_event_without_rewriting(self) -> None:
        task_event = _voice_task_event("event_1", 3)
        payload = {"_sse_event": "voice_task_event", "voiceTaskEvent": task_event}

        self.assertIs(_extract_voice_task_event(payload), task_event)

    def test_recovering_task_error_retryable_relays_unmodified_to_ui_handler(self) -> None:
        recovering = _voice_task_event(
            "event_recovering",
            7,
            state="recovering",
            phase="cancel_barrier_recovering",
            event_type="error",
            error={
                "code": "cancel_barrier_unavailable",
                "message": "Cancellation could not be made durable. Output remains locally suppressed.",
                "retryable": True,
            },
        )
        observed = []

        async def run() -> bool:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
                task_event_handler=observed.append,
            )
            return await llm._relay_task_event_once(recovering)

        self.assertTrue(asyncio.run(run()))
        self.assertEqual(observed, [recovering])
        self.assertIs(observed[0], recovering)

    def test_task_error_retryable_boundary_rejects_nonboolean_and_extra_keys(self) -> None:
        canonical = _voice_task_event(
            "event_error",
            8,
            state="recovering",
            phase="cancel_barrier_recovering",
            event_type="error",
        )
        for error in (
            {
                "code": "cancel_barrier_unavailable",
                "message": "Retrying.",
                "retryable": "true",
            },
            {
                "code": "cancel_barrier_unavailable",
                "message": "Retrying.",
                "retryable": 1,
            },
            {
                "code": "cancel_barrier_unavailable",
                "message": "Retrying.",
                "retryable": True,
                "internal": "not allowed",
            },
        ):
            with self.subTest(error=error):
                self.assertIsNone(
                    _extract_voice_task_event(
                        {
                            "event": "voice_task_event",
                            "voiceTaskEvent": {**canonical, "error": error},
                        },
                        expected_call_session_id="call_1",
                    )
                )

    def test_strict_task_parser_rejects_cross_session_missing_id_and_bool_sequence(self) -> None:
        canonical = _voice_task_event("event_1", 1)
        for malformed in (
            {**canonical, "callSessionId": "other_call"},
            {key: value for key, value in canonical.items() if key != "eventId"},
            {**canonical, "sequence": True},
            {**canonical, "owner": {"kind": "generation_job", "secret": "no"}},
        ):
            self.assertIsNone(
                _extract_voice_task_event(
                    {"event": "voice_task_event", "voiceTaskEvent": malformed},
                    expected_call_session_id="call_1",
                )
            )
        unsafe_source = _voice_task_event(
            "event_unsafe_source",
            2,
            event_type="source",
            phase="source",
            source={"title": "Unsafe", "url": "javascript:alert(1)"},
        )
        self.assertIsNone(
            _extract_voice_task_event(
                {"event": "voice_task_event", "voiceTaskEvent": unsafe_source},
                expected_call_session_id="call_1",
            )
        )

    def test_invalid_task_progress_rejects_entire_event_without_rewriting(self) -> None:
        task_event = _voice_task_event(
            "event_1",
            3,
            progress={"current": 5, "total": 2},
        )

        extracted = _extract_voice_task_event(
            {"_sse_event": "voice_task_event", "voiceTaskEvent": task_event}
        )

        self.assertIsNone(extracted)
        self.assertIn("progress", task_event)

    def test_relays_authoritative_task_event_unmodified_and_suppresses_late_result(self) -> None:
        running = _voice_task_event("event_1", 1, phase="searching")
        cancelling = _voice_task_event(
            "event_2",
            2,
            state="cancelling",
            phase="stopping",
            event_type="state",
        )
        events = [
            {"event": "voice_task_event", "voiceTaskEvent": running},
            {"text": "Working now."},
            {"event": "voice_task_event", "voiceTaskEvent": cancelling},
            {"text": " This late result must not be spoken."},
            {
                "final": True,
                "responseMessage": {
                    "messageId": "msg_1",
                    "content": [{"type": "text", "text": "Working now. This late result must not be spoken."}],
                },
            },
        ]
        fake_session = _FakeStreamingSseSession(events)
        relayed = []

        async def run_stream() -> list[str]:
            ctx = ChatContext(items=[ChatMessage(role="user", content=["look it up"])])
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
                task_event_handler=relayed.append,
            )
            stream = llm.chat(chat_ctx=ctx)
            chunks = []
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                async with stream:
                    async for chunk in stream:
                        chunks.append(chunk.delta.content or "")
            return chunks

        spoken = "".join(asyncio.run(run_stream()))

        self.assertEqual(relayed, [running, cancelling])
        self.assertEqual(spoken, "Working now.")

    def test_streamed_sse_deltas_preserve_reported_word_boundaries(self) -> None:
        expected = (
            "Nice, invoice cleared is a real milestone. "
            "On the two stakeholders, what's your read, is this them getting protective, "
            "or trying to formalize something before it gets bigger?"
        )
        events = [
            {"text": "Nice, invoice cleared "},
            {"text": "is a real milestone. "},
            {"text": "On the two stakeholders, what's "},
            {"text": "your read, is this "},
            {"text": "them getting protective, or trying "},
            {"text": "to formalize something "},
            {"text": "before it gets bigger?"},
            {
                "final": True,
                "responseMessage": {
                    "content": [{"type": "text", "text": expected}],
                },
            },
        ]

        async def run_stream() -> list[str]:
            fake_session = _FakeStreamingSseSession(events)
            ctx = ChatContext(items=[ChatMessage(role="user", content=["hello"])])
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            chunks: list[str] = []
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                stream = llm.chat(chat_ctx=ctx)
                async with stream:
                    async for chunk in stream:
                        if chunk.delta and chunk.delta.content:
                            chunks.append(chunk.delta.content)
            return chunks

        chunks = asyncio.run(run_stream())
        spoken_text = "".join(chunks)

        self.assertEqual(spoken_text, expected)
        for bad_join in [
            "clearedis",
            "what'syour",
            "thisthem",
            "tryingto",
            "somethingbefore",
        ]:
            self.assertNotIn(bad_join, spoken_text)

    def test_call_lifetime_task_stream_relays_child_after_parent_stream_ended(self) -> None:
        parent_completed = _voice_task_event(
            "parent_completed",
            9,
            taskId="task_parent",
            state="completed",
            phase="completed",
            event_type="result",
        )
        child_queued = _voice_task_event(
            "child_queued",
            1,
            taskId="task_child_retry",
            state="queued",
            phase="queued",
            event_type="snapshot",
            parentTaskId="task_parent",
        )
        child_source = _voice_task_event(
            "child_source",
            2,
            taskId="task_child_retry",
            state="running",
            phase="source",
            event_type="source",
            parentTaskId="task_parent",
            source={"title": "Synthetic source", "url": "https://example.test/retry"},
        )
        child_completed = _voice_task_event(
            "child_completed",
            3,
            taskId="task_child_retry",
            state="completed",
            phase="completed",
            event_type="result",
            parentTaskId="task_parent",
        )
        fake_session = _CallTaskEventSession(
            [parent_completed, child_queued, child_source, child_completed]
        )
        relayed: list[dict] = []

        async def run() -> None:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(
                    call_session_id="call_1",
                    call_secret="secret",
                    job_id="job_1",
                    worker_id="worker_1",
                ),
                task_event_handler=relayed.append,
            )
            await llm._relay_task_event_once(parent_completed)
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                task = llm.start_call_task_event_stream(
                    reconnect_min_s=0.01,
                    reconnect_max_s=0.02,
                )
                self.assertIsNotNone(task)
                await asyncio.wait_for(fake_session.delivered.wait(), timeout=1.0)
                await llm.stop_call_task_event_stream()
            await llm.close_background_continuations()

        asyncio.run(run(), debug=True)

        self.assertEqual(
            [event["eventId"] for event in relayed],
            ["parent_completed", "child_queued", "child_source", "child_completed"],
        )
        self.assertEqual(len(fake_session.get_calls), 1)
        url, _args, kwargs = fake_session.get_calls[0]
        self.assertEqual(
            url,
            "http://librechat.test/api/viventium/voice/tasks/events",
        )
        self.assertEqual(kwargs["params"], {"callSessionId": "call_1"})
        self.assertEqual(
            kwargs["headers"],
            {
                "Accept": "text/event-stream",
                "X-VIVENTIUM-CALL-SESSION": "call_1",
                "X-VIVENTIUM-CALL-SECRET": "secret",
                "X-VIVENTIUM-JOB-ID": "job_1",
                "X-VIVENTIUM-WORKER-ID": "worker_1",
            },
        )
        self.assertTrue(fake_session.closed)

    def test_call_lifetime_stream_relays_later_completed_source_after_cancel_race(self) -> None:
        completed = _voice_task_event(
            "completed_after_cancel_race",
            7,
            taskId="task_raced",
            state="completed",
            phase="completed",
            event_type="result",
        )
        late_source = _voice_task_event(
            "late_completed_source",
            8,
            taskId="task_raced",
            state="completed",
            phase="source",
            event_type="source",
            source={"title": "Completed source", "url": "https://example.test/completed"},
        )
        late_result = _voice_task_event(
            "late_completed_result",
            9,
            taskId="task_raced",
            state="completed",
            phase="completed",
            event_type="result",
            resultMessageId="msg_completed",
        )
        fake_session = _CallTaskEventSession([completed, late_source, late_result])
        relayed: list[dict] = []

        async def run() -> bool:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(
                    call_session_id="call_1",
                    call_secret="secret",
                    job_id="job_1",
                    worker_id="worker_1",
                ),
                task_event_handler=relayed.append,
            )
            # LibreChat's exact GlassHive 409 already_completed means cancellation was
            # never accepted. The gateway deliberately keeps its local speech barrier,
            # while higher-sequence completed source/result events remain visible.
            llm._task_event_gate.mark_cancel_accepted("task_raced")
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                llm.start_call_task_event_stream(
                    reconnect_min_s=0.01,
                    reconnect_max_s=0.02,
                )
                await asyncio.wait_for(fake_session.delivered.wait(), timeout=1.0)
                await llm.stop_call_task_event_stream()
            suppressed = llm.is_task_output_suppressed("task_raced")
            await llm.close_background_continuations()
            return suppressed

        self.assertTrue(asyncio.run(run(), debug=True))
        self.assertEqual(
            [event["eventId"] for event in relayed],
            ["completed_after_cancel_race", "late_completed_source", "late_completed_result"],
        )

    def test_call_lifetime_task_stream_reconnects_with_full_job_auth_and_closes_cleanly(self) -> None:
        child_running = _voice_task_event(
            "child_after_reconnect",
            1,
            taskId="task_child",
            state="running",
            phase="tool",
            event_type="progress",
        )
        fake_session = _ReconnectCallTaskEventSession([child_running])
        relayed: list[dict] = []

        async def run() -> list[str]:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(
                    call_session_id="call_1",
                    call_secret="secret",
                    job_id="job_1",
                    worker_id="worker_1",
                ),
                task_event_handler=relayed.append,
            )
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                stream_task = llm.start_call_task_event_stream(
                    reconnect_min_s=0.01,
                    reconnect_max_s=0.02,
                )
                await asyncio.wait_for(fake_session.delivered.wait(), timeout=1.0)
                await llm.close_background_continuations()
            self.assertTrue(stream_task.done())
            return [task.get_name() for task in asyncio.all_tasks() if not task.done()]

        live_task_names = asyncio.run(run(), debug=True)

        self.assertEqual([event["eventId"] for event in relayed], ["child_after_reconnect"])
        self.assertEqual(len(fake_session.get_calls), 2)
        self.assertTrue(fake_session.closed)
        self.assertFalse(any(name.startswith("viventium-call-task-events:") for name in live_task_names))

    def test_call_lifetime_task_stream_requires_exact_job_and_worker_auth(self) -> None:
        async def run() -> None:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            self.assertIsNone(llm.start_call_task_event_stream())
            await llm.close_background_continuations()

        asyncio.run(run(), debug=True)

    def test_call_task_stream_startup_401_never_reports_ready(self) -> None:
        fake_session = _CallTaskStatusSession(401)
        health: list[dict] = []

        async def run() -> tuple[bool, dict, list[str]]:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(
                    call_session_id="call_1",
                    call_secret="secret",
                    job_id="job_1",
                    worker_id="worker_1",
                ),
            )
            llm.set_call_task_event_stream_health_handler(health.append)
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                llm.start_call_task_event_stream()
                ready = await llm.wait_call_task_event_stream_ready(timeout_s=0.5)
                snapshot = llm.call_task_event_stream_health
                await llm.close_background_continuations()
            live = [task.get_name() for task in asyncio.all_tasks() if not task.done()]
            return ready, snapshot, live

        ready, snapshot, live = asyncio.run(run(), debug=True)

        self.assertFalse(ready)
        self.assertEqual(snapshot["state"], "terminal")
        self.assertEqual(snapshot["status"], 401)
        self.assertEqual([item["state"] for item in health[:2]], ["connecting", "terminal"])
        self.assertTrue(fake_session.closed)
        self.assertFalse(any(name.startswith("viventium-call-task-events:") for name in live))

    def test_call_task_stream_2xx_without_sync_marker_never_reports_ready(self) -> None:
        fake_session = _CallTaskStatusSession(200)
        health: list[dict] = []

        async def run() -> bool:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(
                    call_session_id="call_1",
                    call_secret="secret",
                    job_id="job_1",
                    worker_id="worker_1",
                ),
            )
            llm.set_call_task_event_stream_health_handler(health.append)
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                llm.start_call_task_event_stream(
                    reconnect_min_s=0.01,
                    reconnect_max_s=0.01,
                )
                ready = await llm.wait_call_task_event_stream_ready(timeout_s=0.05)
                await llm.close_background_continuations()
            return ready

        self.assertFalse(asyncio.run(run(), debug=True))
        self.assertNotIn("connected", [item["state"] for item in health])

    def test_call_task_sync_marker_is_strictly_call_scoped(self) -> None:
        fake_session = _CallTaskSyncOnlySession(
            _voice_task_sync(call_session_id="call_other")
        )

        async def run() -> bool:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(
                    call_session_id="call_1",
                    call_secret="secret",
                    job_id="job_1",
                    worker_id="worker_1",
                ),
            )
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                llm.start_call_task_event_stream()
                ready = await llm.wait_call_task_event_stream_ready(timeout_s=0.05)
                await llm.close_background_continuations()
            return ready

        self.assertFalse(asyncio.run(run(), debug=True))

    def test_call_task_sync_marker_rejects_malformed_contracts(self) -> None:
        valid = {**_voice_task_sync(), "_sse_event": "voice_task_sync"}
        malformed = (
            {**valid, "version": True},
            {**valid, "state": "ready"},
            {**valid, "emittedAt": "not-a-time"},
            {**valid, "emittedAt": "2026-08-09T20:37:59"},
            {**valid, "extra": "field"},
        )

        self.assertEqual(
            _extract_voice_task_sync(
                valid,
                expected_call_session_id="call_1",
            ),
            _voice_task_sync(),
        )
        for payload in malformed:
            with self.subTest(payload=payload):
                self.assertIsNone(
                    _extract_voice_task_sync(
                        payload,
                        expected_call_session_id="call_1",
                    )
                )

    def test_call_task_sync_marker_follows_all_initial_snapshot_events(self) -> None:
        snapshot = _voice_task_event(
            "initial_snapshot",
            1,
            taskId="task_snapshot",
            event_type="snapshot",
        )
        fake_session = _CallTaskEventSession([snapshot])
        relayed: list[dict] = []
        relayed_count_when_connected: list[int] = []

        async def run() -> bool:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(
                    call_session_id="call_1",
                    call_secret="secret",
                    job_id="job_1",
                    worker_id="worker_1",
                ),
                task_event_handler=relayed.append,
            )

            def on_health(item: dict) -> None:
                if item["state"] == "connected":
                    relayed_count_when_connected.append(len(relayed))

            llm.set_call_task_event_stream_health_handler(on_health)
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                llm.start_call_task_event_stream()
                ready = await llm.wait_call_task_event_stream_ready(timeout_s=0.5)
                await llm.close_background_continuations()
            return ready

        self.assertTrue(asyncio.run(run(), debug=True))
        self.assertEqual([event["eventId"] for event in relayed], ["initial_snapshot"])
        self.assertEqual(relayed_count_when_connected, [1])

    def test_disconnect_cancel_barrier_blocks_stale_chunks_then_reconnects_health(self) -> None:
        running = _voice_task_event("before_disconnect", 1, taskId="task_disconnect")
        stale_after_cancel = _voice_task_event(
            "stale_after_cancel",
            2,
            taskId="task_disconnect",
            state="running",
            phase="tool",
            event_type="progress",
        )
        completed = _voice_task_event(
            "completed_after_reconnect",
            3,
            taskId="task_disconnect",
            state="completed",
            phase="completed",
            event_type="result",
        )
        fake_session = _DisconnectThenReconnectCallTaskSession(
            [running],
            [stale_after_cancel, completed],
        )
        relayed: list[dict] = []
        health_states: list[str] = []
        disconnected = asyncio.Event()

        async def run() -> bool:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(
                    call_session_id="call_1",
                    call_secret="secret",
                    job_id="job_1",
                    worker_id="worker_1",
                ),
                task_event_handler=relayed.append,
            )

            def on_health(item: dict) -> None:
                health_states.append(item["state"])
                if item["state"] == "disconnected":
                    disconnected.set()

            llm.set_call_task_event_stream_health_handler(on_health)
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                llm.start_call_task_event_stream(
                    reconnect_min_s=0.05,
                    reconnect_max_s=0.05,
                )
                self.assertTrue(await llm.wait_call_task_event_stream_ready(timeout_s=0.5))
                await asyncio.wait_for(disconnected.wait(), timeout=0.5)
                llm._task_event_gate.mark_cancel_accepted("task_disconnect")
                await asyncio.wait_for(fake_session.delivered.wait(), timeout=1.0)
                await llm.close_background_continuations()
            return llm.is_task_output_suppressed("task_disconnect")

        self.assertTrue(asyncio.run(run(), debug=True))
        self.assertEqual(
            [event["eventId"] for event in relayed],
            ["before_disconnect", "completed_after_reconnect"],
        )

    def test_unknown_error_summary_never_returns_raw_private_provider_content(self) -> None:
        sensitive = "SYNTHETIC_PRIVATE_UNKNOWN_PROVIDER_CREDENTIAL"

        summary = _summarize_error_for_log(
            f"Authorization: Bearer {sensitive}; private response body"
        )

        self.assertEqual(summary, "category=upstream_error")
        self.assertNotIn(sensitive, summary)

    def test_structured_error_summary_rejects_private_values_in_type_and_code(self) -> None:
        sensitive = "SYNTHETIC_PRIVATE_STRUCTURED_PROVIDER_CREDENTIAL"
        summary = _summarize_error_for_log(
            json.dumps(
                {
                    "type": f"credential {sensitive}",
                    "error": {
                        "type": f"private/{sensitive}",
                        "code": f"Bearer {sensitive}",
                    },
                }
            )
        )

        self.assertEqual(summary, "category=upstream_error")
        self.assertNotIn(sensitive, summary)

    def test_extracts_final_response_text_preserves_word_boundaries(self) -> None:
        final_event = {
            "final": True,
            "responseMessage": {
                "content": [
                    {"type": "text", "text": "Hello"},
                    {"type": "text", "text": " world"},
                ]
            },
        }
        self.assertEqual(_extract_final_response_text(final_event), "Hello world")

    def test_terminal_fallback_respects_core_audio_disposition(self) -> None:
        for source, valid in (("model", True), ("required_missing", False),
                              ("required_malformed", False), ("legacy_marker", True)):
            with self.subTest(source=source):
                response = {
                    "content": [{"type": "text", "text": "Text-only result"}],
                    "metadata": {"viventium": {"deliveryDisposition": {
                        "version": 1, "audio": "skip", "required": True,
                        "valid": valid, "source": source,
                    }}},
                }
                self.assertEqual(_extract_final_response_text({"responseMessage": response}), "")
        response["metadata"]["viventium"]["deliveryDisposition"].update(
            audio="eligible", valid=True, source="model")
        self.assertEqual(_extract_final_response_text({"responseMessage": response}), "Text-only result")

    def test_unexpected_call_task_stream_death_is_terminal_and_leak_free(self) -> None:
        fake_session = _CallTaskEventSession(
            [_voice_task_event("consumer_death", 1, taskId="task_death")],
            marker_first=True,
        )
        health: list[dict] = []

        async def run() -> tuple[dict, list[str]]:
            def fail_consumer(_event: dict) -> None:
                raise RuntimeError("synthetic consumer failure")

            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(
                    call_session_id="call_1",
                    call_secret="secret",
                    job_id="job_1",
                    worker_id="worker_1",
                ),
                task_event_handler=fail_consumer,
            )
            llm.set_call_task_event_stream_health_handler(health.append)
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                stream = llm.start_call_task_event_stream()
                self.assertTrue(await llm.wait_call_task_event_stream_ready(timeout_s=0.5))
                await asyncio.wait_for(stream, timeout=0.5)
                snapshot = llm.call_task_event_stream_health
                await llm.close_background_continuations()
            live = [task.get_name() for task in asyncio.all_tasks() if not task.done()]
            return snapshot, live

        snapshot, live = asyncio.run(run(), debug=True)

        self.assertEqual(snapshot["state"], "terminal")
        self.assertIsNone(snapshot["status"])
        self.assertEqual(
            [item["state"] for item in health[:3]],
            ["connecting", "syncing", "connected"],
        )
        self.assertIn("terminal", [item["state"] for item in health])
        self.assertTrue(fake_session.closed)
        self.assertFalse(any(name.startswith("viventium-call-task-events:") for name in live))

    def test_explicit_task_cancel_calls_task_endpoint_once(self) -> None:
        fake_session = _FakeClosedStreamSession()
        cancel_acceptances = []

        async def cancel_twice() -> tuple[dict, dict]:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
                task_cancel_handler=lambda task_id, result: cancel_acceptances.append(
                    (task_id, result.get("state"))
                ),
            )
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                first = await llm.cancel_task("task_1", reason="user_requested")
                second = await llm.cancel_task("task_1", reason="user_requested")
            return first, second

        first, second = asyncio.run(cancel_twice())

        cancel_urls = [
            call[0]
            for call in fake_session.post_calls
            if "/voice/tasks/" in str(call[0])
        ]
        self.assertEqual(
            cancel_urls,
            ["http://librechat.test/api/viventium/voice/tasks/task_1/cancel"],
        )
        self.assertEqual(first, second)
        self.assertEqual(cancel_acceptances, [("task_1", first.get("state"))])

    def test_terminal_task_tombstone_precedes_publish_and_rejects_stale_replay(self) -> None:
        running = _voice_task_event("event_5", 5)
        cancelling = {
            **running,
            "eventId": "event_6",
            "sequence": 6,
            "state": "cancelling",
        }
        replay = {**running, "eventId": "event_4", "sequence": 4}
        observed = []

        async def run() -> tuple[bool, bool, bool]:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
                task_event_handler=lambda event: observed.append(
                    (event["sequence"], llm.is_task_output_suppressed("task_1"))
                ),
            )
            accepted_running = await llm._relay_task_event_once(running)
            accepted_cancelling = await llm._relay_task_event_once(cancelling)
            accepted_replay = await llm._relay_task_event_once(replay)
            return accepted_running, accepted_cancelling, accepted_replay

        accepted = asyncio.run(run())
        self.assertEqual(accepted, (True, True, False))
        self.assertEqual(observed, [(5, False), (6, True)])

    def test_cancel_suppression_survives_a_full_120_minute_soak(self) -> None:
        now = [0.0]
        gate = _VoiceTaskEventGate(clock=lambda: now[0])
        gate.mark_cancel_accepted("task_1")

        now[0] = 7_201.0

        self.assertTrue(gate.is_suppressed("task_1"))
        self.assertFalse(gate.accept(_voice_task_event("stale", 1)))

    def test_cancel_suppression_survives_more_than_ten_thousand_ordinary_tasks(self) -> None:
        now = [0.0]
        gate = _VoiceTaskEventGate(max_tasks=128, clock=lambda: now[0])
        gate.mark_cancel_accepted("task_cancelled")

        for index in range(10_500):
            event = _voice_task_event(
                f"ordinary_{index}",
                1,
                taskId=f"task_ordinary_{index}",
            )
            self.assertTrue(gate.accept(event))

        self.assertTrue(gate.is_suppressed("task_cancelled"))
        self.assertFalse(
            gate.accept(
                _voice_task_event(
                    "cancelled_stale_under_pressure",
                    1,
                    taskId="task_cancelled",
                )
            )
        )

    def test_live_suppression_is_never_evicted_by_tombstone_count_pressure(self) -> None:
        now = [0.0]
        gate = _VoiceTaskEventGate(clock=lambda: now[0])
        gate.mark_cancel_accepted("task_cancelled")

        for index in range(65_537):
            gate.mark_cancel_accepted(f"other_cancelled_{index}")

        self.assertTrue(gate.is_suppressed("task_cancelled"))

    def test_suppression_tombstones_expire_only_after_the_full_24_hour_ttl(self) -> None:
        now = [0.0]
        gate = _VoiceTaskEventGate(clock=lambda: now[0])
        gate.mark_cancel_accepted("task_cancelled")

        now[0] = 86_400.0
        self.assertTrue(gate.is_suppressed("task_cancelled"))
        now[0] = 86_400.001
        self.assertFalse(gate.is_suppressed("task_cancelled"))

    def test_explicit_task_cancel_stops_detached_continuation(self) -> None:
        fake_session = _FakeClosedStreamSession()

        async def run() -> bool:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            continuation = asyncio.create_task(asyncio.sleep(60))
            llm._background_continuations.add(continuation)
            llm._continuations_by_task["task_1"] = {continuation}
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                await llm.cancel_task("task_1")
            await asyncio.sleep(0)
            cancelled = continuation.cancelled()
            await llm.close_background_continuations()
            return cancelled

        self.assertTrue(asyncio.run(run()))

class _PublicVoiceTtsDeltaBufferTests(unittest.TestCase):
    __test__ = False

    # === VIVENTIUM START ===
    # Preserve sentence numbers when an arbitrary streaming boundary makes them
    # look like a numbered-list prefix to the per-chunk speech sanitizer.
    def test_streaming_chunk_boundary_does_not_drop_active_count(self) -> None:
        expected = (
            "Checking the live parallel-work roster now. Active count is 7. "
            "Urgent attention: two missions need input because the connected model account "
            "is unavailable, and five failed launches are sitting there unread and can be "
            "dismissed."
        )
        deltas = [
            "Checkin",
            "g the l",
            "i",
            "ve pa",
            "rallel-wo",
            "rk roste",
            "r now. ",
            "Activ",
            "e count ",
            "is 7. ",
            "Urgent att",
            "enti",
            "on: two m",
            "iss",
            "ions ",
            "nee",
            "d ",
            "input beca",
            "use t",
            "he connec",
            "ted model ac",
            "count is u",
            "nav",
            "ailab",
            "le",
            ", and five f",
            "ai",
            "led launche",
            "s are ",
            "sitting ",
            "there unr",
            "ea",
            "d and ",
            "can be ",
            "dismis",
            "sed.",
        ]
        buffer = _VoiceTtsDeltaBuffer(
            sanitize_chunk=lambda text: sanitize_voice_tts_text(
                text,
                preserve_leading_space=text[:1].isspace(),
                preserve_trailing_space=text[-1:].isspace(),
                allow_voice_controls=False,
            )
        )

        emitted: list[str] = []
        for delta in deltas:
            emitted.extend(buffer.feed(delta))
        emitted.extend(buffer.finalize())

        self.assertEqual("".join(emitted), expected)

    # === VIVENTIUM END ===

    def test_buffers_tiny_initial_i_until_phrase_boundary(self) -> None:
        buffer = _VoiceTtsDeltaBuffer()

        emitted: list[str] = []
        emitted.extend(buffer.feed("I"))
        emitted.extend(buffer.feed(" hear"))
        self.assertEqual(emitted, [])

        emitted.extend(buffer.feed(" you."))
        self.assertEqual(emitted, ["I hear you."])
        self.assertEqual(buffer.finalize(), [])

    def test_shared_mic_tombstone_persists_before_bounded_revision_pages(self) -> None:
        fake_session = _FakeClosedStreamSession()
        revisions = []
        for index in range(130):
            revisions.append(
                {
                    "version": 1,
                    "callSessionId": "call_1",
                    "turnId": f"turn_{index:06d}",
                    "segmentId": f"segment_{index:06d}",
                    "sequence": index + 1,
                    "revision": 2,
                    "text": "Synthetic words",
                    "isFinal": True,
                    "speaker": {
                        "key": "provider:A",
                        "label": "Speaker 1",
                        "source": "provider_diarization",
                        "attribution": "unverified",
                        "actorTrust": "shared_mic_unverified",
                        "providerSpeakerId": "A",
                        "trackSid": "TR_owner",
                        "participantIdentity": "owner",
                    },
                }
            )
        state = {
            "version": 1,
            "callSessionId": "call_1",
            "revision": 1,
            "attributionState": "shared_mic_unverified",
            "detectedAt": "2026-08-09T20:37:04.000Z",
            "sourceTrackSid": "TR_owner",
        }

        async def post() -> None:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                await llm.post_speaker_segment_revisions(
                    revisions,
                    session_state=state,
                )

        asyncio.run(post())
        calls = [call for call in fake_session.post_calls if "/voice/speaker" in str(call[0])]
        self.assertTrue(str(calls[0][0]).endswith("/voice/speaker-session-state"))
        revision_calls = [
            call for call in calls if str(call[0]).endswith("/voice/speaker-segments/revisions")
        ]
        self.assertEqual(
            [len(call[2]["json"]["speakerSegmentRevisions"]) for call in revision_calls],
            [64, 64, 2],
        )
        self.assertTrue(
            all(len(json.dumps(call[2]["json"])) < 128_000 for call in revision_calls)
        )

    def test_same_revision_scoped_track_tombstones_are_each_delivered_once(self) -> None:
        fake_session = _FakeClosedStreamSession()

        def state(track_sid: str) -> dict[str, object]:
            return {
                "version": 1,
                "callSessionId": "call_1",
                "revision": 1,
                "attributionState": "shared_mic_unverified",
                "detectedAt": "2026-08-09T20:37:04.000Z",
                "sourceTrackSid": track_sid,
                "sharedTrackSids": [track_sid],
            }

        async def post() -> None:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                await llm.post_speaker_segment_revisions([], session_state=state("TR_guest_1"))
                await llm.post_speaker_segment_revisions([], session_state=state("TR_guest_2"))
                await llm.post_speaker_segment_revisions([], session_state=state("TR_guest_1"))

        asyncio.run(post())
        state_calls = [
            call
            for call in fake_session.post_calls
            if str(call[0]).endswith("/voice/speaker-session-state")
        ]
        self.assertEqual(len(state_calls), 2)
        self.assertEqual(
            [call[2]["json"]["sourceTrackSid"] for call in state_calls],
            ["TR_guest_1", "TR_guest_2"],
        )

    def test_supervised_revision_queue_retries_beyond_three_and_never_overtakes_tombstone(self) -> None:
        fake_session = _RetryingSpeakerSession(transient_tombstone_failures=4)
        revision = {
            "version": 1,
            "callSessionId": "call_1",
            "turnId": "turn_1",
            "segmentId": "segment_1",
            "sequence": 1,
            "revision": 2,
            "text": "Synthetic words",
            "isFinal": True,
            "speaker": {
                "key": "provider:A",
                "label": "Speaker 1",
                "source": "provider_diarization",
                "attribution": "unverified",
                "actorTrust": "shared_mic_unverified",
                "providerSpeakerId": "A",
                "trackSid": "TR_owner",
            },
        }
        state = {
            "version": 1,
            "callSessionId": "call_1",
            "revision": 1,
            "attributionState": "shared_mic_unverified",
            "detectedAt": "2026-08-09T20:37:04.000Z",
            "sourceTrackSid": "TR_owner",
        }

        async def no_sleep(_delay):
            return None

        async def run() -> None:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            with (
                patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session),
                patch("librechat_llm.asyncio.sleep", side_effect=no_sleep),
            ):
                await llm.queue_speaker_segment_revisions(
                    [revision],
                    session_state=state,
                )
            await llm.close_background_continuations()

        asyncio.run(run())
        urls = [str(call[0]) for call in fake_session.post_calls]
        first_revision_index = next(
            index
            for index, url in enumerate(urls)
            if url.endswith("/voice/speaker-segments/revisions")
        )
        self.assertGreaterEqual(first_revision_index, 5)
        self.assertTrue(
            all(url.endswith("/voice/speaker-session-state") for url in urls[:first_revision_index])
        )

    def test_ambient_ingress_is_structured_and_idempotent(self) -> None:
        fake_session = _FakeClosedStreamSession()
        segment = {
            "version": 1,
            "callSessionId": "call_1",
            "turnId": "turn_ambient_001_000001",
            "segmentId": "segment_ambient_001_000001",
            "sequence": 1,
            "revision": 1,
            "text": "Synthetic guest context",
            "isFinal": True,
            "speaker": {
                "key": "participant:guest",
                "label": "Guest",
                "source": "hybrid",
                "attribution": "unverified",
                "actorTrust": "authenticated_participant",
            },
        }
        payload = {
            "version": 1,
            "callSessionId": "call_1",
            "mode": "wing",
            "ingressKind": "ambient_participant",
            "turnId": segment["turnId"],
            "segments": [segment],
        }

        async def post_twice() -> None:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                await llm.post_ambient_transcript(payload)
                await llm.post_ambient_transcript(payload)

        asyncio.run(post_twice())

        calls = [
            call for call in fake_session.post_calls
            if str(call[0]).endswith("/voice/ambient-transcript")
        ]
        self.assertEqual(len(calls), 1)
        self.assertEqual(
            calls[0][2]["json"],
            {
                "version": 1,
                "callSessionId": "call_1",
                "mode": "wing",
                "ingressKind": "ambient_participant",
                "turnId": segment["turnId"],
                "segments": [segment],
            },
        )

    def test_listen_only_owner_ingress_uses_exact_zero_authority_contract(self) -> None:
        fake_session = _FakeClosedStreamSession()
        segment = {
            "version": 1,
            "callSessionId": "call_1",
            "turnId": "turn_owner_1",
            "segmentId": "segment_owner_1",
            "sequence": 1,
            "revision": 1,
            "text": "Synthetic owner transcript",
            "isFinal": True,
            "speaker": {
                "key": "participant:owner",
                "label": "Owner",
                "source": "hybrid",
                "attribution": "verified",
                "actorTrust": "owner_participant",
                "participantIdentity": "owner",
            },
        }

        async def post():
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                await llm.post_ambient_transcript(
                    {
                        "version": 1,
                        "callSessionId": "call_1",
                        "mode": "listen_only",
                        "ingressKind": "listen_only_owner",
                        "segments": [segment],
                    }
                )

        asyncio.run(post())
        call = next(
            call
            for call in fake_session.post_calls
            if str(call[0]).endswith("/voice/ambient-transcript")
        )
        self.assertEqual(
            call[2]["json"],
            {
                "version": 1,
                "callSessionId": "call_1",
                "ingressKind": "listen_only_owner",
                "segments": [segment],
            },
        )

    def test_posts_stable_opaque_source_event_id_without_capability_authority(self) -> None:
        message = ChatMessage(role="user", content=["stable utterance"])
        posted_source_ids: list[str] = []

        async def run_once() -> None:
            fake_session = _FakeListenOnlySession()
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            stream = llm.chat(chat_ctx=ChatContext(items=[message]))
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                await stream._run()
            payload = fake_session.post_calls[0][1]["json"]
            posted_source_ids.append(payload["sourceEventId"])
            self.assertNotIn("segment_stability", payload)
            self.assertNotIn("supersede_scope", payload)
            self.assertNotIn("interactionAdapterCapabilities", payload)

        asyncio.run(run_once())
        asyncio.run(run_once())

        self.assertEqual(posted_source_ids[0], posted_source_ids[1])
        self.assertIn(message.id, posted_source_ids[0])
        self.assertNotIn("stable utterance", posted_source_ids[0])


class TestLibreChatStreamingRun(_PublicLibreChatStreamingRunTests):
    __test__ = True

    def _file_failure_final(self, *, audio="eligible", content=None, attachments=None):
        return {"final": True, "responseMessage": {
            "messageId": "file-result",
            "content": [{"type": "text", "text": "Here is the file."}] if content is None else content,
            "metadata": {"viventium": {"deliveryDisposition": {
                "version": 1, "audio": audio, "source": "model", "valid": True, "required": True,
            }}},
            "attachments": [{"nativeOutputFile": {
                "version": 1, "status": "unavailable", "code": "native_output_file_unreadable",
            }}] if attachments is None else attachments,
        }}

    async def _run_file_failure_stream(self, events, *, reconnect=False, hook=None, connected=True):
        fake = _FakeResumingSseSession(events) if reconnect else _FakeStreamingSseSession(events)
        def post(url, *args, **kwargs):
            fake.post_calls.append((url, args, kwargs))
            return _FakeJsonResponse({"streamId": "stream_voice_1", "taskId": "task_1",
                "conversationId": "conv_1", "logical_turn_id": "logical-1", "revision": 2})
        fake.post = post
        relayed, followups, chunks = [], [], []
        connection = {"connected": connected}
        def relay(event):
            relayed.append(event)
            if hook:
                hook(llm, event)
        llm = LibreChatLLM(origin="http://librechat.test", auth=LibreChatAuth(
            call_session_id="call_1", call_secret="secret"), task_event_handler=relay,
            followup_handler=lambda *args, **kwargs: followups.append((args, kwargs)),
            is_participant_connected=lambda: connection["connected"])
        async def rejoin():
            connection["connected"] = True
            return True
        llm.wait_for_participant_reconnect = rejoin
        with patch("librechat_llm.aiohttp.ClientSession", return_value=fake), \
             patch("librechat_llm._get_voice_sse_retry_config", return_value=(1, 0.0)):
            async with llm.chat(chat_ctx=ChatContext(items=[ChatMessage(
                    role="user", content=["Synthetic file request"])])) as stream:
                async for chunk in stream:
                    if chunk.delta and chunk.delta.content:
                        chunks.append(chunk.delta.content)
        return {"text": "".join(chunks), "tts": "".join(await _project_tts_chunks(chunks)),
                "relayed": relayed, "followups": followups}

    def test_current_final_file_failure_reaches_tts_without_waiting_for_background_completion(self):
        for streamed in (False, True):
            for task_state in (None, "completed", "running"):
                with self.subTest(streamed=streamed, task_state=task_state):
                    events = [{"text": "Here is the file."}] if streamed else []
                    if task_state:
                        events.append({"event": "voice_task_event", "voiceTaskEvent": _voice_task_event(
                            "file-task-event", 3, state=task_state,
                            phase="completed" if task_state == "completed" else "delegated",
                            event_type="result" if task_state == "completed" else "progress",
                            streamId="stream_voice_1", resultMessageId="file-result" if task_state == "completed" else "",
                            error={"code": "native_output_file_unavailable", "message": "Private diagnostic"}
                                  if task_state == "completed" else None)})
                    final = self._file_failure_final()
                    events.append(final)
                    result = asyncio.run(self._run_file_failure_stream(events))
                    self.assertEqual(result["text"], "Here is the file.\nThe file could not be attached.")
                    self.assertIn("The file could not be attached.", result["tts"])
                    self.assertNotIn("Private diagnostic", result["text"])
                    self.assertEqual(result["followups"][0][0][0], "file-result")
                    self.assertEqual(result["followups"][0][0][2], "Here is the file.")
                    self.assertEqual(final["responseMessage"]["content"][0]["text"], "Here is the file.")

    def test_file_failure_notice_keeps_model_silence_and_no_response_controls(self):
        silent_range = {"type": "text", "text": "Silent result.", "deliveryDispositionRanges": [{
            "start": 0, "end": 14, "disposition": {
                "version": 1, "audio": "skip", "required": True, "valid": True, "source": "model",
            }}]}
        for final in (self._file_failure_final(audio="skip"),
                      self._file_failure_final(content=[silent_range]),
                      self._file_failure_final(content=[{"type": "text", "text": "{NTA}"}])):
            with self.subTest(final=final):
                self.assertEqual(asyncio.run(self._run_file_failure_stream([final]))["text"], "")
        result = asyncio.run(self._run_file_failure_stream([
            {"text": "Here is the file."}, self._file_failure_final(audio="skip")]))
        self.assertEqual(result["text"], "Here is the file.")

    def test_file_failure_notice_stops_with_current_task_and_current_presentation(self):
        completed = {"event": "voice_task_event", "voiceTaskEvent": _voice_task_event(
            "current-result", 3, state="completed", phase="completed", event_type="result")}
        stop = {"event": "voice_task_event", "voiceTaskEvent": _voice_task_event(
            "current-stop", 2, state="cancelling", phase="stopping", event_type="state")}
        stopped = asyncio.run(self._run_file_failure_stream([
            {"text": "Here is the file."}, stop, completed, self._file_failure_final()]))
        self.assertEqual(stopped["text"], "Here is the file.")
        def newer_turn(llm, _event):
            llm._presentation_coordinator.begin_stable(source_event_id="newer", presentation_ref="newer")
        superseded = asyncio.run(self._run_file_failure_stream([
            {"text": "Here is the file."}, completed, self._file_failure_final()], hook=newer_turn))
        self.assertEqual(superseded["text"], "Here is the file.")

    def test_file_failure_notice_preserves_primary_generation_error_precedence(self):
        final = self._file_failure_final(content=[{"type": "error", "error_class": "provider_response_failed",
                                                  "error": "Private diagnostic"}])
        result = asyncio.run(self._run_file_failure_stream([final]))
        self.assertEqual(result["text"], "The model returned no usable answer. Please retry this turn.")
        result = asyncio.run(self._run_file_failure_stream([
            {"text": "Here is the file."}, {"_sse_event": "error", "error": "service failure"},
            self._file_failure_final()]))
        self.assertNotIn("The file could not be attached.", result["text"])

    def test_file_failure_notice_requires_typed_unavailable_attachment_and_final(self):
        for info in ({"version": True, "status": "unavailable"}, {"version": 2, "status": "unavailable"},
                     {"version": 1, "status": "available"}, None):
            with self.subTest(info=info):
                final = self._file_failure_final(attachments=[{"nativeOutputFile": info}] if info else [])
                self.assertEqual(asyncio.run(self._run_file_failure_stream([final]))["text"], "Here is the file.")
        final = self._file_failure_final()
        final["final"] = "true"
        self.assertEqual(asyncio.run(self._run_file_failure_stream([final]))["text"], "Here is the file.")

    def test_file_failure_notice_reconnect_uses_one_final_and_keeps_authored_dedupe(self):
        final = self._file_failure_final()
        sync = {"sync": True, "resumeState": {
            "aggregatedContent": [{"type": "text", "text": "Here is the file."}], "finalEvent": final,
        }}
        result = asyncio.run(self._run_file_failure_stream([
            [{"text": "Here is the file."}], [sync, final, final]], reconnect=True))
        self.assertEqual(result["text"], "Here is the file.\nThe file could not be attached.")
        self.assertEqual(result["followups"][0][0][2], "Here is the file.")
        disconnected = asyncio.run(self._run_file_failure_stream([
            {"text": "Here is the file."}, final], connected=False))
        self.assertEqual(disconnected["text"], result["text"])

    def test_empty_authored_file_failure_has_one_factual_notice_without_cortex_rewrite(self):
        result = asyncio.run(self._run_file_failure_stream([self._file_failure_final(content=[])]))
        self.assertEqual(result["text"], "The file could not be attached.")
        self.assertEqual(result["followups"][0][0][2], "")

    def test_streamed_and_final_only_public_links_reach_sdk_unchanged(self) -> None:
        pieces = ["Read [the ", "report](https://example.invalid/report?revision=2&view=owner)",
                  " and https://example.invalid/source."]
        text = "".join(pieces)
        for streamed in (True, False):
            with self.subTest(streamed=streamed):
                events = [{"event": "on_message_delta", "data": {"delta": {
                    "content": [{"type": "text", "text": piece}],
                }}} for piece in pieces] if streamed else []
                events.append({"final": True, "responseMessage": {
                    "content": [{"type": "text", "text": {"value": text}}],
                }})

                async def run():
                    fake = _FakeStreamingSseSession(events)
                    llm = LibreChatLLM(origin="http://librechat.test", auth=LibreChatAuth(
                        call_session_id="call_1", call_secret="secret"))
                    with patch("librechat_llm.aiohttp.ClientSession", return_value=fake):
                        async with llm.chat(chat_ctx=ChatContext(items=[ChatMessage(
                            role="user", content=["Synthetic request"])])) as stream:
                            return "".join([chunk.delta.content async for chunk in stream
                                            if chunk.delta and chunk.delta.content])

                self.assertEqual(asyncio.run(run()), text)

    def test_first_public_text_measurement_is_once_and_only_after_eligible_output(self) -> None:
        for audio, flag, expected in (
            ("skip", "true", 0), ("eligible", "true", 1),
            ("eligible", "1", 1), ("eligible", "false", 0),
        ):
            with self.subTest(audio=audio, flag=flag):
                metadata = {"viventium": {"deliveryDisposition": {
                    "version": 1, "audio": audio, "source": "model", "valid": True,
                    "required": True,
                }}}
                text = "Synthetic first sentence. Synthetic second sentence."
                events = [{"event": "on_message_delta", "data": {"delta": {
                    "content": [{"type": "text", "text": part}], "metadata": metadata,
                }}} for part in ("Synthetic first sentence. ", "Synthetic second sentence.")]
                events.append({"final": True, "responseMessage": {
                    "content": [{"type": "text", "text": text}], "metadata": metadata,
                }})

                async def run() -> list:
                    fake = _FakeStreamingSseSession(events)
                    llm = LibreChatLLM(origin="http://librechat.test", auth=LibreChatAuth(
                        call_session_id="call_1", call_secret="secret"))
                    with patch("librechat_llm.aiohttp.ClientSession", return_value=fake), \
                         patch.dict(os.environ, {"VIVENTIUM_VOICE_LOG_LATENCY": flag}), \
                         patch("librechat_llm.logger.info") as info:
                        async with llm.chat(chat_ctx=ChatContext(items=[ChatMessage(
                            role="user", content=["Synthetic request"])])) as stream:
                            async for _ in stream:
                                pass
                        return [call for call in info.call_args_list
                                if "llm_first_text_ms=" in str(call.args[0])]

                measurements = asyncio.run(run())
                self.assertEqual(len(measurements), expected)
                for measurement in measurements:
                    self.assertNotIn("Synthetic", str(measurement))
                    self.assertIsInstance(measurement.args[-1], float)

    def test_same_delta_delivery_control_precedes_audio(self) -> None:
        for audio in ("skip", "eligible"):
            with self.subTest(audio=audio):
                metadata = {"viventium": {"deliveryDisposition": {
                    "version": 1, "audio": audio, "source": "model", "valid": True,
                    "required": True,
                }}}
                text = "The report is ready."
                events = [{
                    "event": "on_message_delta",
                    "data": {"delta": {"content": [{"type": "text", "text": text}],
                                       "metadata": metadata}},
                }, {"final": True, "responseMessage": {
                    "content": [{"type": "text", "text": text}], "metadata": metadata,
                }}]

                async def run() -> list[str]:
                    fake = _FakeStreamingSseSession(events)
                    llm = LibreChatLLM(origin="http://librechat.test", auth=LibreChatAuth(
                        call_session_id="call_1", call_secret="secret"))
                    chunks = []
                    with patch("librechat_llm.aiohttp.ClientSession", return_value=fake):
                        async with llm.chat(chat_ctx=ChatContext(items=[ChatMessage(
                            role="user", content=["Synthetic request"])])) as stream:
                            async for chunk in stream:
                                if chunk.delta and chunk.delta.content:
                                    chunks.append(chunk.delta.content)
                    return chunks

                self.assertEqual("".join(asyncio.run(run())), "" if audio == "skip" else text)

    def test_mixed_invocation_delivery_controls_apply_to_each_public_delta(self) -> None:
        for controls in (("eligible", "skip"), ("skip", "eligible")):
            with self.subTest(controls=controls):
                texts = ["Useful current update. ", "The final result is ready. "]
                events = []
                for text, audio in zip(texts, controls):
                    metadata = {"viventium": {"deliveryDisposition": {
                        "version": 1, "audio": audio, "source": "model", "valid": True,
                        "required": True,
                    }}}
                    events.append({"event": "on_message_delta", "data": {"delta": {
                        "content": [{"type": "text", "text": text}], "metadata": metadata,
                    }}})
                events.append({"final": True, "responseMessage": {
                    "content": [{"type": "text", "text": "".join(texts)}], "metadata": metadata,
                }})

                async def run() -> list[str]:
                    fake = _FakeStreamingSseSession(events)
                    llm = LibreChatLLM(origin="http://librechat.test", auth=LibreChatAuth(
                        call_session_id="call_1", call_secret="secret"))
                    chunks = []
                    with patch("librechat_llm.aiohttp.ClientSession", return_value=fake):
                        async with llm.chat(chat_ctx=ChatContext(items=[ChatMessage(
                            role="user", content=["Synthetic request"])])) as stream:
                            async for chunk in stream:
                                if chunk.delta and chunk.delta.content:
                                    chunks.append(chunk.delta.content)
                    return chunks

                spoken = "".join(asyncio.run(run()))
                for text, audio in zip(texts, controls):
                    self.assertEqual(text.strip() in spoken, audio == "eligible")
                self.assertEqual(spoken.count(next(text.strip() for text, audio in zip(texts, controls)
                                                  if audio == "eligible")), 1)

    def test_mixed_audio_reconnect_tracks_silent_raw_text_before_and_after_completion(self) -> None:
        # The native tool path can join two model envelopes at one content index.
        # Graph reentry can instead produce two parts owned by the same Main.
        texts = ["Useful update 🟢. ", "The final result is ready. "]
        for controls in (("eligible", "skip"), ("skip", "eligible")):
            for separate_parts in (False, True):
                for completed in (False, True):
                    for consumed in (0, 1, 2):
                        with self.subTest(controls=controls, separate_parts=separate_parts,
                                          completed=completed, consumed=consumed):
                            dispositions = [{"version": 1, "audio": audio, "source": "model",
                                             "valid": True, "required": True} for audio in controls]
                            deltas = [{"event": "on_message_delta", "data": {"delta": {
                                "content": [{"type": "text", "text": text}],
                                "metadata": {"viventium": {"deliveryDisposition": disposition}},
                            }}} for text, disposition in zip(texts, dispositions)]
                            offsets = [0, len(texts[0].encode("utf-16-le")) // 2,
                                       len("".join(texts).encode("utf-16-le")) // 2]
                            if separate_parts:
                                parts = [{"type": "text", "text": text, "agentId": "main",
                                          "deliveryDispositionRanges": [{"start": 0,
                                              "end": len(text.encode("utf-16-le")) // 2,
                                              "disposition": disposition}]}
                                         for text, disposition in zip(texts, dispositions)]
                            else:
                                parts = [{"type": "text", "text": "".join(texts), "agentId": "main",
                                          "deliveryDispositionRanges": [{"start": offsets[i],
                                              "end": offsets[i + 1], "disposition": disposition}
                                              for i, disposition in enumerate(dispositions)]}]
                            final = {"final": True, "responseMessage": {"content": parts,
                                     "metadata": {"viventium": {
                                         "deliveryDisposition": dispositions[-1]}}}}
                            resume = {"aggregatedContent": parts}
                            if completed:
                                resume["finalEvent"] = final
                            batches = [deltas[:consumed], [{"sync": True, "resumeState": resume}, final]]

                            async def run() -> str:
                                fake = _FakeResumingSseSession(batches)
                                llm = LibreChatLLM(origin="http://librechat.test", auth=LibreChatAuth(
                                    call_session_id="call_1", call_secret="secret"))
                                chunks = []
                                with patch("librechat_llm.aiohttp.ClientSession", return_value=fake), \
                                     patch("librechat_llm._get_voice_sse_retry_config", return_value=(1, 0.0)):
                                    async with llm.chat(chat_ctx=ChatContext(items=[ChatMessage(
                                        role="user", content=["Synthetic request"])])) as stream:
                                        async for chunk in stream:
                                            if chunk.delta and chunk.delta.content:
                                                chunks.append(chunk.delta.content)
                                self.assertEqual(len(fake.get_calls), 2)
                                return "".join(chunks)

                            self.assertEqual(asyncio.run(run()), next(
                                text for text, audio in zip(texts, controls) if audio == "eligible"))

    def test_mixed_final_only_audio_uses_each_retained_choice(self) -> None:
        for controls in (("eligible", "skip"), ("skip", "eligible")):
            with self.subTest(controls=controls):
                texts = ["Public update. ", "Public result."]
                dispositions = [{"version": 1, "audio": audio, "source": "model", "valid": True,
                                 "required": True} for audio in controls]
                part = {"type": "text", "text": "".join(texts), "deliveryDispositionRanges": [
                    {"start": 0, "end": len(texts[0]), "disposition": dispositions[0]},
                    {"start": len(texts[0]), "end": len("".join(texts)), "disposition": dispositions[1]},
                ]}
                final = {"final": True, "responseMessage": {"content": [part],
                    "metadata": {"viventium": {"deliveryDisposition": dispositions[-1]}}}}
                self.assertEqual(_extract_final_response_text(final), next(
                    text.strip() for text, audio in zip(texts, controls) if audio == "eligible"))

    def test_invalid_resume_ranges_fail_closed_when_the_field_is_present(self) -> None:
        from librechat_llm import _content_audio_segments
        eligible = {"version": 1, "audio": "eligible", "source": "model", "valid": True,
                    "required": True}
        invalid = [
            {"start": 0, "end": 8, "disposition": {**eligible, "source": "untrusted"}},
            {"start": 0, "end": 8, "disposition": {**eligible, "required": False}},
            {"start": 0, "end": 8, "disposition": {**eligible, "valid": False}},
            {"start": 0, "end": 8, "disposition": {**eligible, "extra": True}},
            {"start": False, "end": 8, "disposition": eligible},
            {"start": 0, "end": 99, "disposition": eligible},
            # Offset 3 divides the Unicode surrogate pair in this text.
            {"start": 0, "end": 3, "disposition": eligible},
        ]
        for item in invalid:
            for default in (False, True):
                with self.subTest(item=item, default=default):
                    part = {"type": "text", "text": "Hi🟢text", "deliveryDispositionRanges": [item]}
                    self.assertEqual(_content_audio_segments([part], default_skipped=default),
                                     [(part["text"], True)])

    def test_absent_resume_ranges_keep_legacy_default_but_invalid_present_field_stays_silent(self) -> None:
        from librechat_llm import _content_audio_segments
        part = {"type": "text", "text": "Legacy result."}
        for default in (False, True):
            with self.subTest(default=default):
                self.assertEqual(_content_audio_segments([part], default_skipped=default),
                                 [(part["text"], default)])
        for ranges in (None, [], {}, "unknown"):
            with self.subTest(ranges=ranges):
                malformed = {**part, "deliveryDispositionRanges": ranges}
                self.assertEqual(_content_audio_segments([malformed], default_skipped=False),
                                 [(part["text"], True)])

    def test_valid_skip_prefix_does_not_leak_when_a_later_resume_range_is_malformed(self) -> None:
        from librechat_llm import _content_audio_segments
        choice = {"version": 1, "audio": "skip", "source": "model", "valid": True,
                  "required": True}
        part = {"type": "text", "text": "Hi🟢text", "deliveryDispositionRanges": [
            {"start": 0, "end": 2, "disposition": choice},
            {"start": 2, "end": 3, "disposition": {**choice, "audio": "eligible"}},
        ]}
        self.assertEqual(_content_audio_segments([part], default_skipped=False), [(part["text"], True)])

    def test_malformed_running_resume_never_replays_known_silent_text_to_audio(self) -> None:
        skip = {"version": 1, "audio": "skip", "source": "model", "valid": True, "required": True}
        text = "Text-only detail. 🟢"
        part = {"type": "text", "text": text, "deliveryDispositionRanges": [
            {"start": 0, "end": 18, "disposition": skip},
            {"start": 18, "end": 19, "disposition": {**skip, "audio": "eligible"}},
        ]}
        final = {"final": True, "responseMessage": {"content": [part],
            "metadata": {"viventium": {"deliveryDisposition": {**skip, "audio": "eligible"}}}}}
        batches = [[{"event": "on_message_delta", "data": {"delta": {
            "content": [{"type": "text", "text": text}],
            "metadata": {"viventium": {"deliveryDisposition": skip}},
        }}}], [{"sync": True, "resumeState": {"aggregatedContent": [part]}}, final]]

        async def run() -> list[str]:
            fake = _FakeResumingSseSession(batches)
            llm = LibreChatLLM(origin="http://librechat.test", auth=LibreChatAuth(
                call_session_id="call_1", call_secret="secret"))
            chunks = []
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake), \
                 patch("librechat_llm._get_voice_sse_retry_config", return_value=(1, 0.0)):
                async with llm.chat(chat_ctx=ChatContext(items=[ChatMessage(
                    role="user", content=["Synthetic request"])])) as stream:
                    async for chunk in stream:
                        if chunk.delta and chunk.delta.content:
                            chunks.append(chunk.delta.content)
            return chunks

        self.assertEqual(asyncio.run(run()), [])

    def test_utterance_clock_survives_speaker_context_to_hop_trace(self) -> None:
        from speaker_segments import SPEAKER_CONTEXT_EXTRA_KEY
        for clock in ("utc", "call_audio_relative"):
            with self.subTest(clock=clock):
                message = ChatMessage(role="user", content=["Synthetic request"])
                message.extra[SPEAKER_CONTEXT_EXTRA_KEY] = {
                    "utteranceEndClock": clock, "utteranceEndAtMs": 1_790_000_001_234.0,
                    "utteranceEndOffsetMs": 1234.0,
                    "utteranceEndTimingSource": "stt_call_audio_timeline",
                }
                fake = _FakeStreamingSseSession([{"final": True, "responseMessage": {
                    "content": [{"type": "text", "text": "Done."}],
                }}])
                traces = []

                async def run() -> None:
                    llm = LibreChatLLM(origin="http://librechat.test", auth=LibreChatAuth(
                        call_session_id="call_1", call_secret="secret"))
                    llm.register_trace = traces.append
                    with patch("librechat_llm.aiohttp.ClientSession", return_value=fake):
                        await llm.chat(chat_ctx=ChatContext(items=[message]))._run()

                asyncio.run(run())
                observed = traces[0].terminal_summary({})["timestampsMs"]
                self.assertEqual(observed.get("utterance_end"),
                                 1_790_000_001_234.0 if clock == "utc" else None)

    def test_resume_sync_respects_stored_final_audio_disposition(self) -> None:
        raw = '<emotion value="happy"/>Text-only result.'
        for audio in ("skip", "eligible"):
            with self.subTest(audio=audio):
                final = {
                    "final": True,
                    "responseMessage": {
                        "content": [{"type": "text", "text": raw}],
                        "metadata": {"viventium": {"deliveryDisposition": {
                            "version": 1, "audio": audio, "source": "model", "valid": True,
                        }}},
                    },
                }
                event = {"sync": True, "resumeState": {
                    "aggregatedContent": [{"type": "text", "text": raw}],
                    "finalEvent": final,
                }}
                self.assertEqual(_extract_resume_state_text(event), "" if audio == "skip" else raw)

    def test_reconnected_text_only_completion_emits_no_speech(self) -> None:
        final = {
            "final": True,
            "responseMessage": {
                "content": [{"type": "text", "text": "The report is ready."}],
                "metadata": {"viventium": {"deliveryDisposition": {
                    "version": 1, "audio": "skip", "source": "model", "valid": True,
                }}},
            },
        }
        batches = [[], [{"sync": True, "resumeState": {
            "aggregatedContent": [{"type": "text", "text": "The report is ready."}],
            "finalEvent": final,
        }}, final]]

        async def run() -> list[str]:
            fake = _FakeResumingSseSession(batches)
            llm = LibreChatLLM(origin="http://librechat.test", auth=LibreChatAuth(
                call_session_id="call_1", call_secret="secret"))
            chunks = []
            with (
                patch("librechat_llm.aiohttp.ClientSession", return_value=fake),
                patch("librechat_llm._get_voice_sse_retry_config", return_value=(1, 0.0)),
            ):
                async with llm.chat(chat_ctx=ChatContext(items=[ChatMessage(
                    role="user", content=["Use text only."])])) as stream:
                    async for chunk in stream:
                        if chunk.delta and chunk.delta.content:
                            chunks.append(chunk.delta.content)
            self.assertEqual(len(fake.get_calls), 2)
            return chunks

        self.assertEqual(asyncio.run(run()), [])

    def test_resume_state_preserves_raw_text_for_chunk_boundary_deduplication(self) -> None:
        raw = '<emotion value="happy"/>See [the file](https://example.test) or a@example.test.'
        event = {
            "sync": True,
            "resumeState": {"aggregatedContent": [{"type": "text", "text": raw}]},
        }

        self.assertEqual(_extract_resume_state_text(event), raw)

    def test_resume_sync_is_stable_across_non_associative_whitespace_chunks(self) -> None:
        event_batches = [
            [{"text": "Hello "}],
            [
                {
                    "sync": True,
                    "resumeState": {
                        "aggregatedContent": [{"type": "text", "text": "Hello  world."}]
                    },
                },
                {
                    "final": True,
                    "responseMessage": {
                        "content": [{"type": "text", "text": "Hello  world."}]
                    },
                },
            ],
        ]

        async def run_stream() -> list[str]:
            fake_session = _FakeResumingSseSession(event_batches)
            chunks: list[str] = []
            ctx = ChatContext(items=[ChatMessage(role="user", content=["hello"])])
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            with (
                patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session),
                patch("librechat_llm._get_voice_sse_retry_config", return_value=(1, 0.0)),
            ):
                stream = llm.chat(chat_ctx=ctx)
                async with stream:
                    async for chunk in stream:
                        if chunk.delta and chunk.delta.content:
                            chunks.append(chunk.delta.content)
            return chunks

        chunks = asyncio.run(run_stream())
        self.assertEqual("".join(chunks), "Hello  world.")
        self.assertEqual("".join(asyncio.run(_project_tts_chunks(chunks))), "Hello world.")

    def test_resume_sync_recovers_only_missing_text_without_duplicate_speech(self) -> None:
        event_batches = [
            [{"text": "Hello "}],
            [
                {
                    "sync": True,
                    "resumeState": {
                        "aggregatedContent": [{"type": "text", "text": "Hello world."}]
                    },
                },
                {
                    "final": True,
                    "responseMessage": {
                        "content": [{"type": "text", "text": "Hello world."}]
                    },
                },
            ],
        ]

        async def run_stream() -> list[str]:
            fake_session = _FakeResumingSseSession(event_batches)
            chunks: list[str] = []
            ctx = ChatContext(items=[ChatMessage(role="user", content=["hello"])])
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            with (
                patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session),
                patch("librechat_llm._get_voice_sse_retry_config", return_value=(1, 0.0)),
            ):
                stream = llm.chat(chat_ctx=ctx)
                async with stream:
                    async for chunk in stream:
                        if chunk.delta and chunk.delta.content:
                            chunks.append(chunk.delta.content)
            return chunks

        self.assertEqual("".join(asyncio.run(run_stream())), "Hello world.")

    def test_buffers_completed_speech_until_same_claimed_owner_reconnects(self) -> None:
        events = [
            {"text": "Answer completed while the browser was reloading."},
            {
                "final": True,
                "responseMessage": {
                    "content": [
                        {"type": "text", "text": "Answer completed while the browser was reloading."}
                    ]
                },
            },
        ]

        async def run_stream() -> tuple[list[str], list[str]]:
            fake_session = _FakeStreamingSseSession(events)
            connected = False
            chunks: list[str] = []
            ctx = ChatContext(items=[ChatMessage(role="user", content=["hello"])])
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
                is_participant_connected=lambda: connected,
                participant_reconnect_grace_s=0.5,
            )

            async def consume() -> None:
                with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                    stream = llm.chat(chat_ctx=ctx)
                    async with stream:
                        async for chunk in stream:
                            if chunk.delta and chunk.delta.content:
                                chunks.append(chunk.delta.content)

            task = asyncio.create_task(consume())
            await asyncio.sleep(0.05)
            before_reconnect = list(chunks)
            connected = True
            await asyncio.wait_for(task, timeout=1.0)
            return before_reconnect, chunks

        before_reconnect, chunks = asyncio.run(run_stream())
        self.assertEqual(before_reconnect, [])
        self.assertEqual(
            "".join(chunks),
            "Answer completed while the browser was reloading.",
        )

    def test_drops_buffered_speech_after_grace_without_cancelling_persisted_work(self) -> None:
        events = [
            {"text": "Persisted answer with no listener."},
            {
                "final": True,
                "responseMessage": {
                    "content": [{"type": "text", "text": "Persisted answer with no listener."}]
                },
            },
        ]

        async def run_stream() -> tuple[list[str], _FakeStreamingSseSession]:
            fake_session = _FakeStreamingSseSession(events)
            chunks: list[str] = []
            ctx = ChatContext(items=[ChatMessage(role="user", content=["hello"])])
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
                is_participant_connected=lambda: False,
                participant_reconnect_grace_s=0.01,
            )
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                stream = llm.chat(chat_ctx=ctx)
                async with stream:
                    async for chunk in stream:
                        if chunk.delta and chunk.delta.content:
                            chunks.append(chunk.delta.content)
            return chunks, fake_session

        chunks, fake_session = asyncio.run(run_stream())
        self.assertEqual(chunks, [])
        abort_calls = [call for call in fake_session.post_calls if str(call[0]).endswith("/abort")]
        self.assertEqual(abort_calls, [])

    def test_trace_grace_finalizer_is_timer_owned_and_cancelled_on_close(self) -> None:
        async def run():
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            trace = VoiceHopTrace(
                correlation_id="request_timer_lifecycle",
                call_session_id="call_1",
            )
            llm.register_trace(trace)
            llm.schedule_trace_terminal(trace, grace_s=60.0, stream_terminal=True)
            await asyncio.sleep(0)
            self.assertEqual(len(llm._trace_finalizers), 1)
            self.assertFalse(
                any(
                    isinstance(finalizer, asyncio.Task)
                    for finalizer in llm._trace_finalizers.values()
                )
            )
            await llm.close_background_continuations()
            self.assertEqual(llm._trace_finalizers, {})
            leaked = [
                task
                for task in asyncio.all_tasks()
                if task is not asyncio.current_task()
                and "_finalize_after_grace" in repr(task.get_coro())
            ]
            self.assertEqual(leaked, [])

        asyncio.run(run(), debug=True)

    def test_terminal_trace_finalizes_failure_before_tts_or_before_audio_once(self) -> None:
        llm = LibreChatLLM(
            origin="http://librechat.test",
            auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
        )
        before_tts = VoiceHopTrace(
            correlation_id="request_before_tts",
            call_session_id="call_1",
        )
        for hop, timestamp in (
            ("utterance_end", 1_000),
            ("gateway_dispatch", 1_100),
            ("agent_start", 1_200),
            ("first_model_token", 1_300),
        ):
            before_tts.record(hop, timestamp)
        before_audio = VoiceHopTrace(
            correlation_id="request_before_audio",
            call_session_id="call_1",
        )
        for hop, timestamp in (
            ("utterance_end", 2_000),
            ("gateway_dispatch", 2_100),
            ("agent_start", 2_200),
            ("first_model_token", 2_300),
            ("tts_first_byte", 2_400),
        ):
            before_audio.record(hop, timestamp)

        tts_failure = llm.finalize_trace_terminal(before_tts)
        audio_failure = llm.finalize_trace_terminal(before_audio)

        self.assertIn("tts_first_byte", tts_failure["missingHops"])
        self.assertIn("audio_output", tts_failure["missingHops"])
        self.assertNotIn("tts_first_byte", audio_failure["missingHops"])
        self.assertIn("audio_output", audio_failure["missingHops"])
        self.assertIsNone(llm.finalize_trace_terminal(before_audio))

    def test_tts_and_playout_are_correlated_to_oldest_eligible_trace_not_latest_global(self) -> None:
        llm = LibreChatLLM(
            origin="http://librechat.test",
            auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
        )
        first = VoiceHopTrace(correlation_id="request_1", call_session_id="call_1")
        second = VoiceHopTrace(correlation_id="request_2", call_session_id="call_1")
        first.record("first_model_token", 1_000)
        second.record("first_model_token", 1_100)
        llm.register_trace(first)
        llm.bind_trace_task("request_1", "task_1")
        llm.register_trace(second)
        llm.bind_trace_task("request_2", "task_2")

        tts_correlation = llm.record_next_trace_hop("tts_first_byte", 1_200)
        audio_correlation = llm.record_next_trace_hop("audio_output", 1_300)

        self.assertEqual(tts_correlation, "request_1")
        self.assertEqual(audio_correlation, "request_1")
        self.assertFalse(second.has("tts_first_byte"))

    def test_structured_tool_start_and_completion_record_distinct_hops(self) -> None:
        trace = VoiceHopTrace(correlation_id="request_1", call_session_id="call_1")
        start = {
            "event": "voice_task_event",
            "voiceTaskEvent": _voice_task_event(
                "event_start",
                1,
                detail="arbitrary localized copy",
            ),
        }
        completed = {
            "event": "on_run_step_completed",
            "data": {"id": "step_1", "result": {"content": "{}"}},
        }

        LibreChatLLM._record_tool_hops_from_event(trace, start, timestamp_ms=1_000)
        LibreChatLLM._record_tool_hops_from_event(trace, completed, timestamp_ms=1_250)

        self.assertTrue(trace.has("tool_start"))
        self.assertTrue(trace.has("tool_end"))
        self.assertIsNone(trace.first_breach({"tool_start->tool_end": 300}))

    def test_extracts_canonical_named_sse_task_event_without_rewriting(self) -> None:
        task_event = _voice_task_event("event_1", 3)
        payload = {"_sse_event": "voice_task_event", "voiceTaskEvent": task_event}

        self.assertIs(_extract_voice_task_event(payload), task_event)

    def test_recovering_task_error_retryable_relays_unmodified_to_ui_handler(self) -> None:
        recovering = _voice_task_event(
            "event_recovering",
            7,
            state="recovering",
            phase="cancel_barrier_recovering",
            event_type="error",
            error={
                "code": "cancel_barrier_unavailable",
                "message": "Cancellation could not be made durable. Output remains locally suppressed.",
                "retryable": True,
            },
        )
        observed = []

        async def run() -> bool:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
                task_event_handler=observed.append,
            )
            return await llm._relay_task_event_once(recovering)

        self.assertTrue(asyncio.run(run()))
        self.assertEqual(observed, [recovering])
        self.assertIs(observed[0], recovering)

    def test_task_error_retryable_boundary_rejects_nonboolean_and_extra_keys(self) -> None:
        canonical = _voice_task_event(
            "event_error",
            8,
            state="recovering",
            phase="cancel_barrier_recovering",
            event_type="error",
        )
        for error in (
            {
                "code": "cancel_barrier_unavailable",
                "message": "Retrying.",
                "retryable": "true",
            },
            {
                "code": "cancel_barrier_unavailable",
                "message": "Retrying.",
                "retryable": 1,
            },
            {
                "code": "cancel_barrier_unavailable",
                "message": "Retrying.",
                "retryable": True,
                "internal": "not allowed",
            },
        ):
            with self.subTest(error=error):
                self.assertIsNone(
                    _extract_voice_task_event(
                        {
                            "event": "voice_task_event",
                            "voiceTaskEvent": {**canonical, "error": error},
                        },
                        expected_call_session_id="call_1",
                    )
                )

    def test_strict_task_parser_rejects_cross_session_missing_id_and_bool_sequence(self) -> None:
        canonical = _voice_task_event("event_1", 1)
        for malformed in (
            {**canonical, "callSessionId": "other_call"},
            {key: value for key, value in canonical.items() if key != "eventId"},
            {**canonical, "sequence": True},
            {**canonical, "owner": {"kind": "generation_job", "secret": "no"}},
        ):
            self.assertIsNone(
                _extract_voice_task_event(
                    {"event": "voice_task_event", "voiceTaskEvent": malformed},
                    expected_call_session_id="call_1",
                )
            )
        unsafe_source = _voice_task_event(
            "event_unsafe_source",
            2,
            event_type="source",
            phase="source",
            source={"title": "Unsafe", "url": "javascript:alert(1)"},
        )
        self.assertIsNone(
            _extract_voice_task_event(
                {"event": "voice_task_event", "voiceTaskEvent": unsafe_source},
                expected_call_session_id="call_1",
            )
        )

    def test_invalid_task_progress_rejects_entire_event_without_rewriting(self) -> None:
        task_event = _voice_task_event(
            "event_1",
            3,
            progress={"current": 5, "total": 2},
        )

        extracted = _extract_voice_task_event(
            {"_sse_event": "voice_task_event", "voiceTaskEvent": task_event}
        )

        self.assertIsNone(extracted)
        self.assertIn("progress", task_event)

    def test_relays_authoritative_task_event_unmodified_and_suppresses_late_result(self) -> None:
        running = _voice_task_event("event_1", 1, phase="searching")
        cancelling = _voice_task_event(
            "event_2",
            2,
            state="cancelling",
            phase="stopping",
            event_type="state",
        )
        events = [
            {"event": "voice_task_event", "voiceTaskEvent": running},
            {"text": "Working now."},
            {"event": "voice_task_event", "voiceTaskEvent": cancelling},
            {"text": " This late result must not be spoken."},
            {
                "final": True,
                "responseMessage": {
                    "messageId": "msg_1",
                    "content": [{"type": "text", "text": "Working now. This late result must not be spoken."}],
                },
            },
        ]
        fake_session = _FakeStreamingSseSession(events)
        relayed = []

        async def run_stream() -> list[str]:
            ctx = ChatContext(items=[ChatMessage(role="user", content=["look it up"])])
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
                task_event_handler=relayed.append,
            )
            stream = llm.chat(chat_ctx=ctx)
            chunks = []
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                async with stream:
                    async for chunk in stream:
                        chunks.append(chunk.delta.content or "")
            return chunks

        spoken = "".join(asyncio.run(run_stream()))

        self.assertEqual(relayed, [running, cancelling])
        self.assertEqual(spoken, "Working now.")

    def test_streamed_sse_deltas_preserve_reported_word_boundaries(self) -> None:
        expected = (
            "Nice, invoice cleared is a real milestone. "
            "On the two stakeholders, what's your read, is this them getting protective, "
            "or trying to formalize something before it gets bigger?"
        )
        events = [
            {"text": "Nice, invoice cleared "},
            {"text": "is a real milestone. "},
            {"text": "On the two stakeholders, what's "},
            {"text": "your read, is this "},
            {"text": "them getting protective, or trying "},
            {"text": "to formalize something "},
            {"text": "before it gets bigger?"},
            {
                "final": True,
                "responseMessage": {
                    "content": [{"type": "text", "text": expected}],
                },
            },
        ]

        async def run_stream() -> list[str]:
            fake_session = _FakeStreamingSseSession(events)
            ctx = ChatContext(items=[ChatMessage(role="user", content=["hello"])])
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            chunks: list[str] = []
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                stream = llm.chat(chat_ctx=ctx)
                async with stream:
                    async for chunk in stream:
                        if chunk.delta and chunk.delta.content:
                            chunks.append(chunk.delta.content)
            return chunks

        chunks = asyncio.run(run_stream())
        spoken_text = "".join(chunks)

        self.assertEqual(spoken_text, expected)
        for bad_join in [
            "clearedis",
            "what'syour",
            "thisthem",
            "tryingto",
            "somethingbefore",
        ]:
            self.assertNotIn(bad_join, spoken_text)

    def test_streamed_server_normalized_message_deltas_do_not_duplicate_speech(self) -> None:
        expected = "I'm here. Tell me what's going on."
        events = [
            {
                "event": "on_message_delta",
                "data": {"delta": {"content": [{"type": "text", "text": "I'm"}]}},
            },
            {
                "event": "on_message_delta",
                "data": {"delta": {"content": [{"type": "text", "text": " here"}]}},
            },
            {
                "event": "on_message_delta",
                "data": {
                    "delta": {"content": [{"type": "text", "text": ". Tell me"}]},
                },
            },
            {
                "event": "on_message_delta",
                "data": {"delta": {"content": [{"type": "text", "text": " what's going on."}]}},
            },
            {"final": True, "responseMessage": {"content": [{"type": "text", "text": expected}]}},
        ]

        async def run_stream() -> list[str]:
            fake_session = _FakeStreamingSseSession(events)
            ctx = ChatContext(items=[ChatMessage(role="user", content=["hello"])])
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            chunks: list[str] = []
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                stream = llm.chat(chat_ctx=ctx)
                async with stream:
                    async for chunk in stream:
                        if chunk.delta and chunk.delta.content:
                            chunks.append(chunk.delta.content)
            return chunks

        spoken_text = "".join(asyncio.run(run_stream()))

        self.assertEqual(spoken_text, expected)
        self.assertNotIn("I'mI'm", spoken_text)
        self.assertNotIn("here here", spoken_text)

    def test_streamed_server_normalized_no_response_marker_stays_silent(self) -> None:
        events = [
            {
                "event": "on_message_delta",
                "data": {"delta": {"content": [{"type": "text", "text": "{N"}]}},
            },
            {
                "event": "on_message_delta",
                "data": {"delta": {"content": [{"type": "text", "text": "TA"}]}},
            },
            {
                "event": "on_message_delta",
                "data": {"delta": {"content": [{"type": "text", "text": "}"}]}},
            },
            {"final": True, "responseMessage": {"content": [{"type": "text", "text": "{NTA}"}]}},
        ]

        async def run_stream() -> list[str]:
            fake_session = _FakeStreamingSseSession(events)
            ctx = ChatContext(items=[ChatMessage(role="user", content=["hello"])])
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            chunks: list[str] = []
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                stream = llm.chat(chat_ctx=ctx)
                async with stream:
                    async for chunk in stream:
                        if chunk.delta and chunk.delta.content:
                            chunks.append(chunk.delta.content)
            return chunks

        self.assertEqual(asyncio.run(run_stream()), [])

    def test_streamed_server_normalized_quoted_repetition_is_not_collapsed(self) -> None:
        expected = 'She said "no no no no no no" and waited.'
        events = [
            {
                "event": "on_message_delta",
                "data": {"delta": {"content": [{"type": "text", "text": 'She said "no'}]}},
            },
            {
                "event": "on_message_delta",
                "data": {
                    "delta": {"content": [{"type": "text", "text": " no no"}]},
                },
            },
            {
                "event": "on_message_delta",
                "data": {"delta": {"content": [{"type": "text", "text": ' no no no" and waited.'}]}},
            },
            {"final": True, "responseMessage": {"content": [{"type": "text", "text": expected}]}},
        ]

        async def run_stream() -> list[str]:
            fake_session = _FakeStreamingSseSession(events)
            ctx = ChatContext(items=[ChatMessage(role="user", content=["quote it"])])
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            chunks: list[str] = []
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                stream = llm.chat(chat_ctx=ctx)
                async with stream:
                    async for chunk in stream:
                        if chunk.delta and chunk.delta.content:
                            chunks.append(chunk.delta.content)
            return chunks

        self.assertEqual("".join(asyncio.run(run_stream())), expected)

    def test_streamed_sse_deltas_attach_delayed_period_after_max_split(self) -> None:
        first = "This phrase is long enough to cross the streaming TTS length threshold"
        expected = f"{first}. Next thought."
        events = [
            {"text": first},
            {"text": "."},
            {"text": " Next thought."},
            {
                "final": True,
                "responseMessage": {
                    "content": [{"type": "text", "text": f"{first}. Next thought."}],
                },
            },
        ]

        async def run_stream() -> list[str]:
            fake_session = _FakeStreamingSseSession(events)
            ctx = ChatContext(items=[ChatMessage(role="user", content=["hello"])])
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            chunks: list[str] = []
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                stream = llm.chat(chat_ctx=ctx)
                async with stream:
                    async for chunk in stream:
                        if chunk.delta and chunk.delta.content:
                            chunks.append(chunk.delta.content)
            return chunks

        chunks = asyncio.run(run_stream())

        self.assertEqual("".join(chunks), expected)
        speech = asyncio.run(_project_tts_chunks(chunks))
        self.assertEqual("".join(speech), expected)
        self.assertNotIn(".", speech)

    def test_streamed_sse_deltas_preserve_delayed_question_mark(self) -> None:
        expected = "Good morning. Sleep okay?"
        events = [
            {"text": "Good morning. Sleep okay "},
            {"text": "?"},
            {
                "final": True,
                "responseMessage": {
                    "content": [{"type": "text", "text": expected}],
                },
            },
        ]

        async def run_stream() -> list[str]:
            fake_session = _FakeStreamingSseSession(events)
            ctx = ChatContext(items=[ChatMessage(role="user", content=["hello"])])
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            chunks: list[str] = []
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                stream = llm.chat(chat_ctx=ctx)
                async with stream:
                    async for chunk in stream:
                        if chunk.delta and chunk.delta.content:
                            chunks.append(chunk.delta.content)
            return chunks

        chunks = asyncio.run(run_stream())

        self.assertEqual("".join(chunks), "Good morning. Sleep okay ?")
        speech = asyncio.run(_project_tts_chunks(chunks))
        self.assertEqual(speech, [expected])


    async def _native_worker_followup_case(self, task_event, *, continuation, reconnect=False):
        event = {"event": "voice_task_event", "voiceTaskEvent": task_event}
        final = {"final": True, "responseMessage": {
            "messageId": "msg_native_child", "content": [{"type": "text", "text": "Accepted."}],
        }}
        fake_session = (_FakeResumingSseSession([[event], [event, final]]) if reconnect
                        else _FakeStreamingSseSession([event, final]))
        followups, relayed, chunks = [], [], []
        llm = LibreChatLLM(
            origin="http://librechat.test",
            auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            task_event_handler=relayed.append,
            followup_handler=lambda *args, **kwargs: followups.append((args, kwargs)),
        )
        with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session), patch.dict(
            os.environ, {"VIVENTIUM_VOICE_SSE_RETRY_DELAY_S": "0"}
        ):
            if continuation:
                await llm._continue_task_stream(
                    stream_id="stream_voice_1", task_id="task_1", headers={},
                    request_id="request_1", pending_insights=[], saw_cortex_event=False,
                    saw_glasshive_tool_call=False, cortex_message_id="",
                    hop_trace=VoiceHopTrace(correlation_id="request_1", call_session_id="call_1"),
                )
            else:
                stream = llm.chat(chat_ctx=ChatContext(items=[ChatMessage(role="user", content=["Continue."])]))
                async with stream:
                    async for chunk in stream:
                        chunks.append(chunk.delta.content or "")
        self.assertEqual(len(followups), 1)
        self.assertEqual(followups[0][0][0], "msg_native_child")
        self.assertFalse(followups[0][1]["cortex_expected"])
        if continuation:
            self.assertEqual(chunks, [])
        self.assertEqual(len(fake_session.get_calls), 2 if reconnect else 1)
        return followups[0][1]["glasshive_expected"], relayed

    def _native_worker_followup_identity_cases(self, *, continuation):
        child = _voice_task_event(
            "native_child", 1, taskId="task_child", parentTaskId="task_1",
            owner={"kind": "glasshive_run", "id": "run_child"},
        )
        cases = [
            ("delegated_child", child, True),
            ("failed_child", {**child, "state": "failed", "phase": "failed", "cancellable": False}, True),
            ("completed_child", {**child, "state": "completed", "phase": "completed", "cancellable": False}, True),
            ("wrong_call", {**child, "callSessionId": "call_other"}, False),
            ("malformed_sequence", {**child, "sequence": "1"}, False),
            ("malformed_owner", {**child, "owner": {"kind": "glasshive_run", "extra": True}}, False),
            ("general_generation", {**child, "owner": {"kind": "generation_job", "id": "stream_other"}}, False),
            ("foreground_native_main", {**child, "taskId": "task_1", "parentTaskId": "",
                "owner": {"kind": "remote_generation", "id": "stream_voice_1"}}, False),
        ]
        for name, event, expected in cases:
            with self.subTest(case=name, continuation=continuation):
                armed, relayed = asyncio.run(self._native_worker_followup_case(event, continuation=continuation))
                self.assertEqual(armed, expected)
                valid = _extract_voice_task_event(
                    {"event": "voice_task_event", "voiceTaskEvent": event}, expected_call_session_id="call_1",
                )
                self.assertEqual(relayed, [] if valid is None else [event])

    def test_native_worker_task_arms_only_matching_child_in_foreground_stream(self):
        self._native_worker_followup_identity_cases(continuation=False)

    def test_native_worker_task_arms_only_matching_child_in_durable_stream(self):
        self._native_worker_followup_identity_cases(continuation=True)

    def test_native_worker_reconnect_arms_once_without_replaying_task_or_audio(self):
        child = _voice_task_event(
            "native_reconnect", 1, taskId="task_child", parentTaskId="task_1",
            owner={"kind": "glasshive_run", "id": "run_child"},
        )
        for continuation in [False, True]:
            with self.subTest(continuation=continuation):
                armed, relayed = asyncio.run(self._native_worker_followup_case(
                    child, continuation=continuation, reconnect=True,
                ))
                self.assertTrue(armed)
                self.assertEqual(relayed, [child])


class TestFinalEventHelpers(unittest.TestCase):
    def test_extracts_final_response_message_id(self) -> None:
        final_event = {"final": True, "responseMessage": {"messageId": "msg_123"}}
        self.assertEqual(_extract_final_response_message_id(final_event), "msg_123")

    def test_extracts_final_response_message_id_missing(self) -> None:
        self.assertEqual(_extract_final_response_message_id({"final": True}), "")

    def test_detects_glasshive_tool_call_in_nested_stream_event(self) -> None:
        event = {
            "event": "on_agent_update",
            "data": {
                "messages": [
                    {
                        "content": [
                            {
                                "type": "tool_call",
                                "tool_call": {"name": "worker_delegate_once_mcp_glasshive-workers-projects"},
                            }
                        ]
                    }
                ]
            },
        }
        self.assertTrue(_payload_has_glasshive_tool_call(event))

    def test_extracts_error_content_part_as_fallback_message(self) -> None:
        os.environ["VIVENTIUM_VOICE_STREAM_ERROR_MESSAGE"] = "Stream down."
        try:
            final_event = {
                "final": True,
                "responseMessage": {"content": [{"type": "error", "error": "Access denied"}]},
            }
            self.assertEqual(_extract_final_response_text(final_event), "Stream down.")
        finally:
            os.environ.pop("VIVENTIUM_VOICE_STREAM_ERROR_MESSAGE", None)

    def test_summarizes_error_content_without_raw_message(self) -> None:
        raw = (
            'An error occurred while processing the request: 401 '
            '{"type":"error","error":{"type":"authentication_error",'
            '"message":"Invalid authentication credentials"}}'
        )
        summary = _summarize_error_for_log(raw)
        self.assertIn("status=401", summary)
        self.assertIn("type=error", summary)
        self.assertIn("error_type=authentication_error", summary)
        self.assertNotIn("Invalid authentication credentials", summary)

    def test_extracts_final_response_text_preserves_word_boundaries(self) -> None:
        final_event = {
            "final": True,
            "responseMessage": {
                "content": [
                    {"type": "text", "text": "Hello"},
                    {"type": "text", "text": " world"},
                ]
            },
        }
        self.assertEqual(_extract_final_response_text(final_event), "Hello world")

    def test_formats_insights_for_direct_speech(self) -> None:
        speech = format_insights_for_direct_speech(
            [{"cortex_name": "Background Analysis", "insight": "Secret code: 27."}]
        )
        self.assertIn("Secret code: 27.", speech)
        self.assertEqual(speech.count("Secret code: 27."), 1)
        self.assertNotIn("Background insights update.", speech)

    # === VIVENTIUM START ===
    def test_formats_insights_for_direct_speech_strips_links(self) -> None:
        speech = format_insights_for_direct_speech(
            [
                {
                    "cortex_name": "Online Tool Use",
                    "insight": "Plan: 1) Check. Zoom: https://example.com",
                }
            ]
        )
        self.assertNotIn("Plan:", speech)
        self.assertNotIn("https://", speech)
        self.assertIn("Check.", speech)
    # === VIVENTIUM END ===

    def test_formats_insights_for_direct_speech_with_preamble(self) -> None:
        os.environ["VIVENTIUM_VOICE_INSIGHT_PREAMBLE"] = "Quick note."
        try:
            speech = format_insights_for_direct_speech(
                [{"cortex_name": "Background Analysis", "insight": "Secret code: 27."}]
            )
            self.assertTrue(speech.startswith("Quick note."))
        finally:
            os.environ.pop("VIVENTIUM_VOICE_INSIGHT_PREAMBLE", None)


class TestStreamErrorHelpers(unittest.TestCase):
    def test_extracts_stream_error(self) -> None:
        payload = {"_sse_event": "error", "error": "boom"}
        self.assertEqual(_extract_stream_error(payload), "boom")

    def test_selects_tool_error_message(self) -> None:
        os.environ["VIVENTIUM_VOICE_STREAM_ERROR_MESSAGE"] = "Stream down."
        os.environ["VIVENTIUM_VOICE_TOOL_ERROR_MESSAGE"] = "Tool down."
        os.environ["VIVENTIUM_VOICE_AUTH_ERROR_MESSAGE"] = "Auth down."
        os.environ["VIVENTIUM_VOICE_RATE_LIMIT_ERROR_MESSAGE"] = "Rate limited."
        try:
            self.assertEqual(_select_stream_error_message("MCP connection failed"), "Tool down.")
            self.assertEqual(
                _select_stream_error_message("401 authentication_error"),
                "Auth down.",
            )
            self.assertEqual(
                _select_stream_error_message("status 429 rate_limit_error"),
                "Rate limited.",
            )
            self.assertEqual(
                _select_stream_error_message(
                    "server_is_overloaded: servers are currently overloaded"
                ),
                "Rate limited.",
            )
            self.assertEqual(_select_stream_error_message("other error"), "Stream down.")
        finally:
            os.environ.pop("VIVENTIUM_VOICE_STREAM_ERROR_MESSAGE", None)
            os.environ.pop("VIVENTIUM_VOICE_TOOL_ERROR_MESSAGE", None)
            os.environ.pop("VIVENTIUM_VOICE_AUTH_ERROR_MESSAGE", None)
            os.environ.pop("VIVENTIUM_VOICE_RATE_LIMIT_ERROR_MESSAGE", None)

class TestNoResponseStreamingGuard(unittest.TestCase):
    def test_buffers_and_suppresses_braced_tag(self) -> None:
        guard = _NoResponseStreamGuard()
        emitted: list[str] = []
        for delta in ["{", "NTA", "}"]:
            emitted.extend(guard.feed(delta))

        self.assertEqual(emitted, [])
        suppressed, pending = guard.finalize("{NTA}")
        self.assertTrue(suppressed)
        self.assertEqual(pending, [])
        self.assertTrue(is_no_response_only("{NTA}"))

    def test_emits_normal_text_immediately(self) -> None:
        guard = _NoResponseStreamGuard()
        emitted = guard.feed("Hello")
        self.assertEqual(emitted, ["Hello"])
        suppressed, pending = guard.finalize("Hello")
        self.assertFalse(suppressed)
        self.assertEqual(pending, [])

    def test_preserves_leading_space_on_following_streamed_delta(self) -> None:
        guard = _NoResponseStreamGuard()
        emitted: list[str] = []
        emitted.extend(guard.feed("Hello"))
        emitted.extend(guard.feed(" world"))
        self.assertEqual(emitted, ["Hello", " world"])
        suppressed, pending = guard.finalize("Hello world")
        self.assertFalse(suppressed)
        self.assertEqual(pending, [])

    def test_suppresses_nothing_to_add_variants(self) -> None:
        guard = _NoResponseStreamGuard()
        emitted = guard.feed("Nothing new to add for now.")
        self.assertEqual(emitted, [])
        suppressed, pending = guard.finalize("Nothing new to add for now.")
        self.assertTrue(suppressed)
        self.assertEqual(pending, [])

    def test_does_not_suppress_meaningful_nothing_statement(self) -> None:
        guard = _NoResponseStreamGuard()
        emitted = guard.feed("Nothing beats a clean implementation.")
        self.assertEqual(emitted, ["Nothing beats a clean implementation."])
        suppressed, pending = guard.finalize("Nothing beats a clean implementation.")
        self.assertFalse(suppressed)
        self.assertEqual(pending, [])

    def test_flushes_when_nothing_to_add_becomes_meaningful(self) -> None:
        guard = _NoResponseStreamGuard()
        emitted: list[str] = []
        emitted.extend(guard.feed("Nothing"))
        self.assertEqual(emitted, [])
        emitted.extend(guard.feed(" to add except this: keep the space."))
        self.assertNotEqual(emitted, [])
        suppressed, pending = guard.finalize("".join(["Nothing", " to add except this: keep the space."]))
        self.assertFalse(suppressed)
        self.assertEqual(pending, [])

    def test_strips_inline_nta_when_meaningful_content_follows(self) -> None:
        guard = _NoResponseStreamGuard()
        emitted: list[str] = []
        emitted.extend(guard.feed("{"))
        emitted.extend(guard.feed("NTA"))
        emitted.extend(guard.feed("} Useful follow-up"))
        self.assertEqual("".join(emitted), "Useful follow-up")
        suppressed, pending = guard.finalize("{NTA} Useful follow-up")
        self.assertFalse(suppressed)
        self.assertEqual(pending, [])


class TestVoiceTtsDeltaBuffer(_PublicVoiceTtsDeltaBufferTests):
    __test__ = True

    def test_buffers_tiny_initial_i_until_phrase_boundary(self) -> None:
        buffer = _VoiceTtsDeltaBuffer()

        emitted: list[str] = []
        emitted.extend(buffer.feed("I"))
        emitted.extend(buffer.feed(" hear"))
        self.assertEqual(emitted, [])

        emitted.extend(buffer.feed(" you."))
        self.assertEqual(emitted, ["I hear you."])
        self.assertEqual(buffer.finalize(), [])

    def test_preserves_spaces_inside_buffered_phrase(self) -> None:
        buffer = _VoiceTtsDeltaBuffer()
        emitted: list[str] = []
        for delta in ["Yeah,", " that", " lands."]:
            emitted.extend(buffer.feed(delta))

        self.assertEqual(emitted, ["Yeah, that lands."])

    def test_flushes_short_complete_phrase_without_waiting_for_finalize(self) -> None:
        buffer = _VoiceTtsDeltaBuffer()
        self.assertEqual(buffer.feed("Okay."), ["Okay."])
        self.assertEqual(buffer.finalize(), [])

    def test_repairs_missing_space_after_sentence_boundary(self) -> None:
        buffer = _VoiceTtsDeltaBuffer()
        self.assertEqual(
            buffer.feed("That tracks with the rebound after stopping Strattera."),
            ["That tracks with the rebound after stopping Strattera."],
        )

        self.assertEqual(buffer.feed("What's hitting hardest right now?"), [" What's hitting hardest right now?"])
        self.assertEqual(buffer.finalize(), [])

    def test_does_not_insert_spaces_inside_split_word_tokens(self) -> None:
        buffer = _VoiceTtsDeltaBuffer()
        self.assertEqual(buffer.feed("Emotion"), [])
        self.assertEqual(buffer.feed("al"), [])
        self.assertEqual(buffer.feed(" pain."), ["Emotional pain."])
        self.assertEqual(buffer.finalize(), [])

    def test_buffers_later_phrase_until_punctuation_boundary(self) -> None:
        buffer = _VoiceTtsDeltaBuffer()
        self.assertEqual(buffer.feed("Hey there."), ["Hey there."])

        emitted: list[str] = []
        for delta in [" Good", " to", " hear", " you", "."]:
            emitted.extend(buffer.feed(delta))

        self.assertEqual(emitted, [" Good to hear you."])
        self.assertEqual(buffer.finalize(), [])

    def test_preserves_delayed_question_mark_after_whitespace_candidate(self) -> None:
        buffer = _VoiceTtsDeltaBuffer(
            sanitize_chunk=lambda text: sanitize_voice_tts_text(
                text,
                preserve_leading_space=text[:1].isspace(),
                preserve_trailing_space=text[-1:].isspace(),
                allow_voice_controls=False,
            )
        )

        self.assertEqual(buffer.feed("Good morning. Sleep okay "), [])
        self.assertEqual(buffer.feed("?"), ["Good morning. Sleep okay?"])
        self.assertEqual(buffer.finalize(), [])

    def test_preserves_delayed_exclamation_after_whitespace_candidate(self) -> None:
        buffer = _VoiceTtsDeltaBuffer(
            sanitize_chunk=lambda text: sanitize_voice_tts_text(
                text,
                preserve_leading_space=text[:1].isspace(),
                preserve_trailing_space=text[-1:].isspace(),
                allow_voice_controls=False,
            )
        )

        self.assertEqual(buffer.feed("Right. That landed "), [])
        # The next character can make this an image opener; input end resolves it.
        self.assertEqual(buffer.feed("!"), [])
        self.assertEqual(buffer.finalize(), ["Right. That landed!"])

    def test_delayed_exclamation_releases_after_whitespace_rules_out_image(self) -> None:
        buffer = _VoiceTtsDeltaBuffer(
            sanitize_chunk=lambda text: sanitize_voice_tts_text(
                text,
                preserve_leading_space=text[:1].isspace(),
                preserve_trailing_space=text[-1:].isspace(),
                allow_voice_controls=False,
            )
        )

        self.assertEqual(buffer.feed("Right. That landed "), [])
        self.assertEqual(buffer.feed("!"), [])
        self.assertEqual(buffer.feed(" "), ["Right. That landed! "])
        self.assertEqual(buffer.finalize(), [])

    def test_delayed_exclamation_keeps_character_split_inline_image(self) -> None:
        buffer = _VoiceTtsDeltaBuffer(
            sanitize_chunk=lambda text: sanitize_voice_tts_text(
                text,
                preserve_leading_space=text[:1].isspace(),
                preserve_trailing_space=text[-1:].isspace(),
                allow_voice_controls=False,
            )
        )

        self.assertEqual(buffer.feed("Right. That landed "), [])
        self.assertEqual(buffer.feed("!"), [])
        emitted = []
        for char in "[the diagram](relative/diagram.png) then continue.":
            emitted.extend(buffer.feed(char))
        emitted.extend(buffer.finalize())
        self.assertEqual("".join(emitted), "Right. That landed the diagram then continue.")

    def test_keeps_whitespace_latency_for_single_ongoing_sentence(self) -> None:
        buffer = _VoiceTtsDeltaBuffer()

        self.assertEqual(buffer.feed("Nice, invoice cleared "), ["Nice, invoice "])
        self.assertEqual(buffer.feed("is a real milestone."), ["cleared is a real milestone."])
        self.assertEqual(buffer.finalize(), [])

    def test_keeps_whitespace_latency_for_long_post_terminal_tail(self) -> None:
        buffer = _VoiceTtsDeltaBuffer()

        self.assertEqual(
            buffer.feed("Yeah. You've been threading "),
            ["Yeah. You've been "],
        )
        self.assertEqual(buffer.feed("that needle."), ["threading that needle."])

    def test_preserves_delayed_question_mark_after_long_single_sentence(self) -> None:
        buffer = _VoiceTtsDeltaBuffer(
            sanitize_chunk=lambda text: sanitize_voice_tts_text(
                text,
                preserve_leading_space=text[:1].isspace(),
                preserve_trailing_space=text[-1:].isspace(),
                allow_voice_controls=False,
            )
        )

        chunks = buffer.feed("Did you really mean the deployment should roll back tonight ")
        chunks.extend(buffer.feed("?"))
        chunks.extend(buffer.finalize())

        self.assertEqual("".join(chunks), "Did you really mean the deployment should roll back tonight?")
        self.assertNotIn("?", chunks)

    def test_max_length_flush_keeps_owner_word_for_delayed_period(self) -> None:
        buffer = _VoiceTtsDeltaBuffer(max_chars=12)
        self.assertEqual(buffer.feed("This phrase is long enough"), ["This phrase "])
        self.assertEqual(buffer.feed("."), ["is long enough."])
        self.assertEqual(buffer.finalize(), [])

    def test_drops_orphan_period_before_next_phrase(self) -> None:
        buffer = _VoiceTtsDeltaBuffer()
        self.assertEqual(buffer.feed("Done."), ["Done."])
        self.assertEqual(buffer.feed("."), [])
        self.assertEqual(buffer.feed(" Next thought."), [" Next thought."])
        self.assertEqual(buffer.finalize(), [])

    def test_preserves_decimal_split_after_prior_speech(self) -> None:
        buffer = _VoiceTtsDeltaBuffer(min_first_chars=1, max_chars=1)
        self.assertEqual(buffer.feed("3"), [])
        self.assertEqual(buffer.feed(".14 is pi."), ["3.14 is pi."])
        self.assertEqual(buffer.finalize(), [])

    def test_max_length_flush_keeps_trailing_word_in_buffer(self) -> None:
        buffer = _VoiceTtsDeltaBuffer(max_chars=24)

        self.assertEqual(
            buffer.feed("Nice, invoice cleared is a real"),
            ["Nice, invoice cleared "],
        )
        self.assertEqual(buffer.feed(" milestone."), ["is a real milestone."])
        self.assertEqual(buffer.finalize(), [])

    def test_max_length_flush_waits_when_no_safe_whitespace_boundary_exists(self) -> None:
        buffer = _VoiceTtsDeltaBuffer(max_chars=8)

        self.assertEqual(buffer.feed("Supercalifragilistic"), [])
        self.assertEqual(buffer.feed("."), ["Supercalifragilistic."])
        self.assertEqual(buffer.finalize(), [])

    def test_max_length_flush_uses_first_safe_boundary_after_target(self) -> None:
        buffer = _VoiceTtsDeltaBuffer(max_chars=8)

        self.assertEqual(buffer.feed("Supercalifragilistic word"), ["Supercalifragilistic "])
        self.assertEqual(buffer.feed(" lands."), ["word lands."])
        self.assertEqual(buffer.finalize(), [])

    def test_holds_short_open_quote_for_delayed_question_mark(self) -> None:
        buffer = _VoiceTtsDeltaBuffer(
            sanitize_chunk=lambda text: sanitize_voice_tts_text(
                text,
                preserve_leading_space=text[:1].isspace(),
                preserve_trailing_space=text[-1:].isspace(),
                allow_voice_controls=False,
            )
        )

        self.assertEqual(buffer.feed("She asked, “Sleep okay "), [])
        self.assertEqual(buffer.feed("?”"), ["She asked, “Sleep okay?”"])
        self.assertEqual(buffer.finalize(), [])

    def test_flushes_remainder_on_finalize(self) -> None:
        buffer = _VoiceTtsDeltaBuffer()
        self.assertEqual(buffer.feed("Short"), [])
        self.assertEqual(buffer.finalize(), ["Short"])

    def test_sanitizes_tts_chunk_before_emit(self) -> None:
        buffer = _VoiceTtsDeltaBuffer(
            sanitize_chunk=lambda text: sanitize_voice_tts_text(
                text,
                preserve_leading_space=text[:1].isspace(),
                preserve_trailing_space=text[-1:].isspace(),
                allow_voice_controls=False,
            )
        )
        emitted: list[str] = []
        for delta in [" See", " [brief](https://example.com)", " and email qa@example.com."]:
            emitted.extend(buffer.feed(delta))

        self.assertEqual(emitted, [" See brief and email address available."])
        self.assertEqual(buffer.finalize(), [])

    def test_waits_for_url_tail_before_sanitizing(self) -> None:
        buffer = _VoiceTtsDeltaBuffer(
            max_chars=18,
            sanitize_chunk=lambda text: sanitize_voice_tts_text(
                text,
                preserve_leading_space=text[:1].isspace(),
                preserve_trailing_space=text[-1:].isspace(),
                allow_voice_controls=False,
            ),
        )
        self.assertEqual(buffer.feed("Visit https://example."), [])
        self.assertEqual(buffer.feed("com now."), ["Visit link available now."])

    def test_strips_plain_tts_voice_controls_after_buffering(self) -> None:
        buffer = _VoiceTtsDeltaBuffer(
            sanitize_chunk=lambda text: sanitize_voice_tts_text(
                text,
                preserve_leading_space=text[:1].isspace(),
                preserve_trailing_space=text[-1:].isspace(),
                allow_voice_controls=False,
            )
        )
        emitted: list[str] = []
        for delta in ['<emotion value="calm"/>', "Hello ", '<break time="500ms"/>', "there."]:
            emitted.extend(buffer.feed(delta))

        self.assertEqual(emitted, ["Hello there."])
        self.assertEqual(buffer.finalize(), [])

    def test_preserves_supported_tts_voice_controls_when_allowed(self) -> None:
        buffer = _VoiceTtsDeltaBuffer(
            sanitize_chunk=lambda text: sanitize_voice_tts_text(
                text,
                preserve_leading_space=text[:1].isspace(),
                preserve_trailing_space=text[-1:].isspace(),
                allow_voice_controls=True,
            )
        )
        emitted: list[str] = []
        for delta in ['<emotion value="calm"/>', "Hello ", '<break time="500ms"/>', "there."]:
            emitted.extend(buffer.feed(delta))

        self.assertEqual(emitted, ['<emotion value="calm"/>Hello <break time="500ms"/>there.'])
        self.assertEqual(buffer.finalize(), [])

    def test_preserves_trailing_space_across_sanitized_length_flush(self) -> None:
        buffer = _VoiceTtsDeltaBuffer(
            max_chars=18,
            sanitize_chunk=lambda text: sanitize_voice_tts_text(
                text,
                preserve_leading_space=text[:1].isspace(),
                preserve_trailing_space=text[-1:].isspace(),
                allow_voice_controls=False,
            ),
        )
        emitted: list[str] = []
        emitted.extend(buffer.feed("Nice, invoice cleared "))
        emitted.extend(buffer.feed("is a real milestone."))

        self.assertEqual("".join(emitted), "Nice, invoice cleared is a real milestone.")
        self.assertEqual(buffer.finalize(), [])


class TestVoicePresentationCoordinator(_PublicVoicePresentationCoordinatorTests):
    __test__ = True

    async def _cancelled_then_stable(self, *, speech_handle=None, early_completion=False,
                                     offered_text=False, damage_binding="", ack_accepted=True,
                                     replay_ack=False, same_source=False, provisional=False):
        started = asyncio.Event()
        admitted = asyncio.Event()
        post_started = asyncio.Event()
        order = []
        if not early_completion:
            admitted.set()

        class Response(_FakeJsonResponse):
            async def json(self):
                if self._payload["revision"] == 1:
                    post_started.set()
                    await admitted.wait()
                return self._payload

        class Content:
            async def iter_any(self):
                if offered_text:
                    yield b'event: message\ndata: {"text":"Already offered to speech."}\n\n'
                started.set()
                await asyncio.Event().wait()

        class Session(_FakeStreamingSseSession):
            def post(self, url, *args, **kwargs):
                self.post_calls.append((url, args, kwargs))
                revision = len(self.post_calls)
                order.append(f"post-{revision}")
                return Response({"streamId": kwargs["json"]["streamId"],
                    "taskId": f"task_{revision}", "logical_turn_id": "logical-1", "revision": revision})

            def get(self, url, *args, **kwargs):
                if len(self.post_calls) == 1:
                    response = _FakeStreamingSseResponse([])
                    response.content = Content()
                    return response
                return _FakeStreamingSseResponse([{"final": True,
                    "responseMessage": {"messageId": "answer-2", "content": [{"type": "text", "text": "Next."}]}}])

        session = Session([])
        llm = LibreChatLLM(origin="http://librechat.test",
            auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"))

        async def acknowledge(**kwargs):
            order.append("ack")
            await asyncio.sleep(0)
            return ack_accepted

        llm.ack_delivery = AsyncMock(side_effect=acknowledge)
        llm._start_task_continuation = unittest.mock.Mock()
        with patch("librechat_llm.aiohttp.ClientSession", return_value=session):
            if speech_handle is not None:
                llm.register_speech_handle(speech_handle)
            first = llm.chat(chat_ctx=ChatContext(items=[ChatMessage(id="first-source", role="user", content=["First."])]))
            if early_completion:
                await asyncio.wait_for(post_started.wait(), 1)
                speech_handle.complete(interrupted=True)
                await asyncio.sleep(0)
                admitted.set()
            await asyncio.wait_for(started.wait(), 1)
            await first.aclose()
            if provisional:
                llm.note_provisional_interruption()
                await llm._ack_unpresented_superseded_presentation(first._presentation, first._presentation)
                llm.ack_delivery.assert_not_awaited()
            if damage_binding == "task":
                llm._task_id_by_trace_id.pop(first._request_id, None)
            elif damage_binding == "other_task":
                llm._task_id_by_trace_id[first._request_id] = "other-task"
            elif damage_binding == "stream":
                llm._stream_id_by_trace_id.pop(first._request_id, None)
            elif damage_binding == "other_stream":
                llm._stream_id_by_trace_id[first._request_id] = "other-stream"
            elif damage_binding == "presentation":
                llm._presentation_by_trace_id.pop(first._request_id, None)
            elif damage_binding == "context":
                first._presentation.logical_turn_id = ""
            elif damage_binding == "other_context":
                first._presentation.logical_turn_id = "other-logical-turn"
            elif damage_binding == "revision":
                first._presentation.revision = 2
            elif damage_binding == "reference":
                first._presentation.presentation_ref = "other-presentation"
            elif damage_binding == "call":
                llm._auth = LibreChatAuth(call_session_id="other-call", call_secret="secret")
            elif damage_binding == "interrupted":
                first._presentation.interrupted_binding = None
            elif damage_binding == "audio_started":
                first._presentation.audio_started_at_ms = 1
            elif damage_binding == "playout_active":
                first._presentation.playout_active = True
            elif damage_binding == "sequence":
                llm._presentation_coordinator.begin_stable(source_event_id="unadmitted-source", presentation_ref="unadmitted")
            elif damage_binding == "closing":
                llm._speaker_delivery_closing = True
            second = llm.chat(chat_ctx=ChatContext(items=[ChatMessage(id="first-source" if same_source else "second-source", role="user", content=["Second."])]))
            replays = []
            if replay_ack:
                replays = [asyncio.create_task(llm._ack_unpresented_superseded_presentation(
                    first._presentation, second._presentation)) for _ in range(2)]
            async with second:
                async for _chunk in second:
                    pass
            if replays:
                self.assertEqual(await asyncio.gather(*replays), [True, True])
                self.assertTrue(await llm._ack_unpresented_superseded_presentation(
                    first._presentation, second._presentation))
            await llm.close_background_continuations()
        return llm, first, second, order

    def test_zero_presented_supersession_ack_fences_successor_receipt(self) -> None:
        llm, first, _second, order = asyncio.run(self._cancelled_then_stable())
        self.assertEqual(order, ["post-1", "post-2", "ack"])
        self.assertEqual(llm.ack_delivery.await_args.kwargs, {
            "logical_turn_id": "logical-1", "revision": 1, "state": "partial_removed",
            "presentation_ref": first._request_id,
        })
        llm._start_task_continuation.assert_called_once()

    def test_zero_presented_terminal_before_core_context_ack_is_retried_at_supersession(self) -> None:
        handle = _CompletableSpeechHandle("speech-before-core")
        llm, _first, _second, order = asyncio.run(self._cancelled_then_stable(
            speech_handle=handle, early_completion=True))
        self.assertEqual(order, ["post-1", "post-2", "ack"])
        self.assertEqual(llm.ack_delivery.await_args.kwargs["presentation_ref"], handle.id)
        self.assertEqual(llm.ack_delivery.await_args.kwargs["state"], "partial_removed")

    def test_zero_presented_ack_never_covers_offered_or_live_or_audible_speech(self) -> None:
        audible = _CompletableSpeechHandle("audible")
        audible.mark_audible_playout()
        for options in ({"offered_text": True}, {"speech_handle": _CompletableSpeechHandle("live")},
                        {"speech_handle": audible}, {"speech_handle": SimpleNamespace(id="unknown-handle")}):
            with self.subTest(options=options):
                llm, _first, _second, order = asyncio.run(self._cancelled_then_stable(**options))
                llm.ack_delivery.assert_not_awaited()
                self.assertEqual(order, ["post-1", "post-2"])

    def test_zero_presented_ack_requires_exact_owned_bindings(self) -> None:
        for damaged in ("task", "other_task", "stream", "other_stream", "presentation", "context",
                        "other_context", "revision", "reference", "call", "interrupted",
                        "audio_started", "playout_active", "sequence", "closing"):
            with self.subTest(damaged=damaged):
                llm, _first, _second, order = asyncio.run(self._cancelled_then_stable(damage_binding=damaged))
                llm.ack_delivery.assert_not_awaited()
                self.assertEqual(order, ["post-1"] if damaged == "closing" else ["post-1", "post-2"])

    def test_zero_presented_ack_is_idempotent_across_concurrent_and_completed_replay(self) -> None:
        llm, _first, _second, order = asyncio.run(self._cancelled_then_stable(replay_ack=True))
        llm.ack_delivery.assert_awaited_once()
        self.assertEqual(order, ["post-1", "ack", "post-2"])

    def test_zero_presented_ack_requires_new_stable_source(self) -> None:
        llm, _first, _second, order = asyncio.run(self._cancelled_then_stable(same_source=True))
        llm.ack_delivery.assert_not_awaited()
        self.assertEqual(order, ["post-1", "post-2"])

    def test_zero_presented_provisional_interruption_waits_for_stable_successor(self) -> None:
        llm, first, _second, order = asyncio.run(self._cancelled_then_stable(provisional=True))
        self.assertEqual(first._presentation.provisional_interruptions, 1)
        llm.ack_delivery.assert_awaited_once()
        self.assertEqual(order, ["post-1", "post-2", "ack"])

    def test_zero_presented_failed_ack_is_not_recorded_as_accepted(self) -> None:
        llm, first, _second, order = asyncio.run(self._cancelled_then_stable(ack_accepted=False))
        self.assertEqual(order, ["post-1", "post-2", "ack"])
        self.assertNotEqual(first._presentation.delivery_state, "partial_removed")

    def test_completed_audible_ack_is_not_retracted_by_later_stable_turn_or_callback(self) -> None:
        async def run():
            llm = LibreChatLLM(origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"))
            llm.ack_delivery = AsyncMock(return_value=True)
            first = llm._presentation_coordinator.begin_stable(
                source_event_id="first-source", presentation_ref="first-speech")
            llm._presentation_coordinator.bind_core_context(first, {"logical_turn_id": "logical-1", "revision": 1})
            handle = _CompletableSpeechHandle("first-speech")
            handle.mark_audible_playout()
            handle.complete()
            self.assertTrue(await llm._ack_completed_presentation(first, handle))
            second = llm._presentation_coordinator.begin_stable(
                source_event_id="second-source", presentation_ref="second-speech")
            self.assertFalse(await llm._ack_unpresented_superseded_presentation(first, second))
            self.assertTrue(await llm._ack_completed_presentation(first, handle))
            return llm, first

        llm, first = asyncio.run(run())
        llm.ack_delivery.assert_awaited_once()
        self.assertEqual(llm.ack_delivery.await_args.kwargs["state"], "committed")
        self.assertEqual(first.delivery_state, "committed")

    def test_provisional_acoustic_interruption_does_not_supersede_presentation(self) -> None:
        coordinator = _VoicePresentationCoordinator()
        presentation = coordinator.begin_stable(
            source_event_id="voice:call:item:one",
            presentation_ref="speech-one",
        )

        coordinator.note_provisional_interruption(presentation)

        self.assertTrue(coordinator.is_current(presentation))

    def test_next_stable_utterance_permanently_supersedes_old_presentation(self) -> None:
        coordinator = _VoicePresentationCoordinator()
        first = coordinator.begin_stable(
            source_event_id="voice:call:item:one",
            presentation_ref="speech-one",
        )
        coordinator.bind_core_context(
            first,
            {"logical_turn_id": "logical-1", "revision": 1},
        )

        second = coordinator.begin_stable(
            source_event_id="voice:call:item:two",
            presentation_ref="speech-two",
        )
        coordinator.bind_core_context(
            second,
            {"logicalTurnId": "logical-1", "revision": 2},
        )

        self.assertFalse(coordinator.is_current(first))
        self.assertTrue(coordinator.is_current(second))
        self.assertEqual(second.logical_turn_id, "logical-1")
        self.assertEqual(second.revision, 2)

    def test_delivery_ack_is_optional_and_uses_voice_scoped_adapter_contract(self) -> None:
        async def run() -> tuple[bool, _FakeDeliveryAckSession]:
            fake_session = _FakeDeliveryAckSession()
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="voice-secret"),
            )
            with (
                patch.dict(
                    os.environ,
                    {
                        "VIVENTIUM_DELIVERY_ACK_ENDPOINT": "/api/viventium/interactions/delivery-ack",
                        "VIVENTIUM_VOICE_INTERACTION_ADAPTER_SECRET": "adapter-secret",
                    },
                    clear=True,
                ),
                patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session),
            ):
                accepted = await llm.ack_delivery(
                    logical_turn_id="logical-1",
                    revision=2,
                    state="committed",
                    presentation_ref="speech-one",
                )
            return accepted, fake_session

        accepted, fake_session = asyncio.run(run())

        self.assertTrue(accepted)
        url, _args, kwargs = fake_session.post_calls[0]
        self.assertEqual(
            url,
            "http://librechat.test/api/viventium/interactions/delivery-ack",
        )
        self.assertEqual(
            kwargs["json"],
            {
                "logical_turn_id": "logical-1",
                "revision": 2,
                "state": "committed",
                "presentation_ref": "speech-one",
            },
        )
        self.assertEqual(
            kwargs["headers"]["x-viventium-adapter-secret"],
            "adapter-secret",
        )

    def test_delivery_ack_never_falls_back_to_a_shared_adapter_secret(self) -> None:
        async def run() -> tuple[bool, _FakeDeliveryAckSession]:
            fake_session = _FakeDeliveryAckSession()
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="voice-secret"),
            )
            with (
                patch.dict(
                    os.environ,
                    {
                        "VIVENTIUM_DELIVERY_ACK_ENDPOINT": "/api/viventium/interactions/delivery-ack",
                        "VIVENTIUM_INTERACTION_ADAPTER_SECRET": "shared-secret",
                    },
                    clear=True,
                ),
                patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session),
            ):
                accepted = await llm.ack_delivery(
                    logical_turn_id="logical-1",
                    revision=1,
                    state="committed",
                )
            return accepted, fake_session

        accepted, fake_session = asyncio.run(run())

        self.assertFalse(accepted)
        self.assertEqual(fake_session.post_calls, [])

    def test_delivery_ack_missing_contract_is_unavailable_not_failed(self) -> None:
        async def run() -> bool:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="voice-secret"),
            )
            with patch.dict(os.environ, {}, clear=True):
                return await llm.ack_delivery(
                    logical_turn_id="logical-1",
                    revision=1,
                    state="committed",
                    presentation_ref="speech-one",
                )

        self.assertFalse(asyncio.run(run()))

    def test_delivery_ack_retries_one_transient_failure_idempotently(self) -> None:
        async def run() -> tuple[bool, list[tuple]]:
            statuses = [503, 200]
            calls: list[tuple] = []

            class _RetrySession:
                async def __aenter__(self):
                    return self

                async def __aexit__(self, exc_type, exc, tb):
                    return False

                def post(self, url, *args, **kwargs):
                    calls.append((url, args, kwargs))
                    return _SequencedStatusResponse(statuses.pop(0), {})

            async def _no_delay(_seconds: float) -> None:
                return None

            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="voice-secret"),
            )
            with (
                patch.dict(
                    os.environ,
                    {
                        "VIVENTIUM_DELIVERY_ACK_ENDPOINT": "/api/viventium/interactions/delivery-ack",
                        "VIVENTIUM_VOICE_INTERACTION_ADAPTER_SECRET": "adapter-secret",
                    },
                    clear=True,
                ),
                patch("librechat_llm.aiohttp.ClientSession", return_value=_RetrySession()),
                patch("librechat_llm.asyncio.sleep", side_effect=_no_delay),
            ):
                accepted = await llm.ack_delivery(
                    logical_turn_id="logical-1",
                    revision=2,
                    state="committed",
                    presentation_ref="speech-one",
                )
            return accepted, calls

        accepted, calls = asyncio.run(run())

        self.assertTrue(accepted)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][2]["json"], calls[1][2]["json"])

    def test_core_turn_identity_is_bound_and_superseded_stream_emits_no_stale_chunks(self) -> None:
        events = [
            {
                "event": "voice_task_event",
                "voiceTaskEvent": _voice_task_event("event_1", 1),
            },
            {"text": "This stale answer must not be presented."},
            {
                "final": True,
                "responseMessage": {
                    "messageId": "msg-old",
                    "content": [{"type": "text", "text": "Stale final."}],
                },
            },
        ]

        async def run() -> tuple[list[str], list[dict], list, object]:
            fake_session = _FakeLogicalStreamingSseSession(events)
            relayed = []
            followups = []
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
                task_event_handler=relayed.append,
                followup_handler=lambda *args, **kwargs: followups.append((args, kwargs)),
            )
            old_stream = llm.chat(
                chat_ctx=ChatContext(items=[ChatMessage(role="user", content=["first"])])
            )
            second_presentation = llm._presentation_coordinator.begin_stable(
                source_event_id="voice:call_1:item:second",
                presentation_ref="speech-second",
            )
            self.assertTrue(
                llm._presentation_coordinator.is_current(second_presentation)
            )
            chunks = []
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                async with old_stream:
                    async for chunk in old_stream:
                        if chunk.delta and chunk.delta.content:
                            chunks.append(chunk.delta.content)
            return chunks, relayed, followups, old_stream._presentation

        chunks, relayed, followups, presentation = asyncio.run(run())

        self.assertEqual(chunks, [])
        self.assertEqual(len(relayed), 1)
        self.assertEqual(relayed[0]["taskId"], "task_1")
        self.assertEqual(followups, [])
        self.assertEqual(presentation.logical_turn_id, "logical-1")
        self.assertEqual(presentation.revision, 2)

    def test_playout_completion_acknowledges_current_or_retracts_superseded_presentation(self) -> None:
        async def run() -> list:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            llm.ack_delivery = AsyncMock(return_value=True)
            first_handle = _CompletableSpeechHandle("speech-first")
            llm.register_speech_handle(first_handle)
            first = llm.chat(
                chat_ctx=ChatContext(items=[ChatMessage(role="user", content=["first"])])
            )._presentation
            llm._presentation_coordinator.bind_core_context(
                first,
                {"logical_turn_id": "logical-1", "revision": 1},
            )

            second_handle = _CompletableSpeechHandle("speech-second")
            llm.register_speech_handle(second_handle)
            second = llm.chat(
                chat_ctx=ChatContext(items=[ChatMessage(role="user", content=["second"])])
            )._presentation
            llm._presentation_coordinator.bind_core_context(
                second,
                {"logical_turn_id": "logical-1", "revision": 2},
            )
            first_handle.mark_audible_playout()
            first_handle.complete(interrupted=False)
            second_handle.mark_audible_playout()
            second_handle.complete(interrupted=False)
            await asyncio.sleep(0)
            return llm.ack_delivery.await_args_list

        acknowledgements = asyncio.run(run())

        self.assertEqual(acknowledgements[0].kwargs["state"], "partial_removed")
        self.assertEqual(acknowledgements[0].kwargs["presentation_ref"], "speech-first")
        self.assertEqual(acknowledgements[1].kwargs["state"], "committed")
        self.assertEqual(acknowledgements[1].kwargs["revision"], 2)

    def test_playout_completion_fails_current_presentation_without_audible_output(self) -> None:
        async def run(*, include_unplayed_assistant_item: bool) -> list:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            llm.ack_delivery = AsyncMock(return_value=True)
            handle = _CompletableSpeechHandle("speech-no-audio")
            if include_unplayed_assistant_item:
                handle.chat_items.append(
                    ChatMessage(role="assistant", content=["Generated but never played."])
                )
            llm.register_speech_handle(handle)
            presentation = llm.chat(
                chat_ctx=ChatContext(items=[ChatMessage(role="user", content=["hello"])])
            )._presentation
            llm._presentation_coordinator.bind_core_context(
                presentation,
                {"logical_turn_id": "logical-1", "revision": 1},
            )
            handle.complete(interrupted=False)
            await asyncio.sleep(0)
            return llm.ack_delivery.await_args_list

        for include_unplayed_assistant_item in (False, True):
            with self.subTest(
                outcome="terminal_tts_failure"
                if not include_unplayed_assistant_item
                else "zero_audio_playout"
            ):
                acknowledgements = asyncio.run(
                    run(include_unplayed_assistant_item=include_unplayed_assistant_item)
                )
                self.assertEqual(len(acknowledgements), 1)
                self.assertEqual(acknowledgements[0].kwargs["state"], "failed")

    def test_false_barge_in_resumes_and_commits_after_positive_playout(self) -> None:
        async def run() -> list:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            llm.ack_delivery = AsyncMock(return_value=True)
            handle = _CompletableSpeechHandle("speech-resumed")
            llm.register_speech_handle(handle)
            presentation = llm.chat(
                chat_ctx=ChatContext(items=[ChatMessage(role="user", content=["hello"])])
            )._presentation
            llm._presentation_coordinator.bind_core_context(
                presentation,
                {"logical_turn_id": "logical-1", "revision": 1},
            )
            llm.note_provisional_interruption()
            handle.mark_audible_playout()
            handle.complete(interrupted=False)
            await asyncio.sleep(0)
            return llm.ack_delivery.await_args_list

        acknowledgements = asyncio.run(run())

        self.assertEqual(len(acknowledgements), 1)
        self.assertEqual(acknowledgements[0].kwargs["state"], "committed")

    def test_sse_close_does_not_cancel_backend_task(self) -> None:
        fake_session = _FakeClosedStreamSession()
        os.environ["VIVENTIUM_VOICE_SSE_MAX_RETRIES"] = "0"
        os.environ["VIVENTIUM_VOICE_SSE_RETRY_DELAY_S"] = "0.01"
        try:
            async def run_stream() -> None:
                ctx = ChatContext(items=[ChatMessage(role="user", content=["hello"])])
                llm = LibreChatLLM(
                    origin="http://librechat.test",
                    auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
                )
                stream = llm.chat(chat_ctx=ctx)
                with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                    await stream._run()

            asyncio.run(run_stream())
        finally:
            os.environ.pop("VIVENTIUM_VOICE_SSE_MAX_RETRIES", None)
            os.environ.pop("VIVENTIUM_VOICE_SSE_RETRY_DELAY_S", None)

        self.assertGreaterEqual(len(fake_session.get_calls), 1)
        post_urls = [call[0] for call in fake_session.post_calls]
        self.assertIn("http://librechat.test/api/viventium/voice/chat", post_urls)
        self.assertNotIn(
            "http://librechat.test/api/viventium/voice/stream/stream_voice_1/abort",
            post_urls,
        )

    def test_livekit_stream_interruption_does_not_cancel_backend_task(self) -> None:
        async def run_stream() -> _FakeBlockingStreamSession:
            fake_session = _FakeBlockingStreamSession()
            ctx = ChatContext(items=[ChatMessage(role="user", content=["hello"])])
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            stream = llm.chat(chat_ctx=ctx)
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                task = asyncio.create_task(stream._run())
                await asyncio.wait_for(fake_session.sse_started.wait(), timeout=1.0)
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
            return fake_session

        fake_session = asyncio.run(run_stream())

        post_urls = [call[0] for call in fake_session.post_calls]
        self.assertNotIn(
            "http://librechat.test/api/viventium/voice/stream/stream_voice_cancel_1/abort",
            post_urls,
        )
        self.assertFalse(fake_session.abort_completed)

    def test_interruption_detaches_task_only_resume_through_completion(self) -> None:
        running = _voice_task_event("event_1", 1)
        source = _voice_task_event(
            "event_2",
            2,
            phase="source",
            event_type="source",
            source={"title": "Synthetic source", "url": "https://example.test/source"},
        )
        completed = _voice_task_event(
            "event_3",
            3,
            state="completed",
            phase="completed",
            event_type="result",
        )
        fake_session = _FakeInterruptedThenCompletedSession(
            running,
            [
                {"event": "voice_task_event", "voiceTaskEvent": running},
                {"event": "voice_task_event", "voiceTaskEvent": source},
                {
                    "event": "on_message_delta",
                    "data": {
                        "delta": {
                            "content": [
                                {
                                    "type": "tool_call",
                                    "tool_call": {
                                        "function": {
                                            "name": "delegate_mcp_glasshive-workers-projects"
                                        }
                                    },
                                }
                            ]
                        }
                    },
                },
                {"text": "Late result must never reach model or TTS output."},
                {"event": "voice_task_event", "voiceTaskEvent": completed},
                {
                    "final": True,
                    "responseMessage": {
                        "messageId": "msg_resume_1",
                        "content": [{"type": "text", "text": "Persisted result."}],
                    },
                },
            ],
        )
        relayed = []
        followups = []
        async def run_stream() -> None:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
                task_event_handler=relayed.append,
                followup_handler=lambda *args, **kwargs: followups.append((args, kwargs)),
            )
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                await llm._relay_task_event_once(running)
                # The interrupted foreground owned the first subscription. The detached,
                # task-only continuation starts at the resumable second subscription.
                fake_session.get_calls.append(("interrupted-primary", (), {}))
                llm._start_task_continuation(
                    stream_id="stream_resume_1",
                    task_id="task_1",
                    headers={
                        "X-VIVENTIUM-CALL-SESSION": "call_1",
                        "X-VIVENTIUM-CALL-SECRET": "secret",
                    },
                    request_id="request_1",
                    pending_insights=[],
                    saw_cortex_event=False,
                    saw_glasshive_tool_call=False,
                    cortex_message_id="",
                    hop_trace=VoiceHopTrace(
                        correlation_id="request_1",
                        call_session_id="call_1",
                    ),
                )
                await llm.wait_for_background_continuations(timeout_s=1.0)

        asyncio.run(run_stream())

        self.assertEqual(relayed, [running, source, completed])
        self.assertEqual(len(followups), 1)
        self.assertEqual(followups[0][0][0], "msg_resume_1")
        self.assertEqual(followups[0][0][2], "")
        self.assertTrue(followups[0][1]["glasshive_expected"])

    def test_call_lifetime_task_stream_relays_child_after_parent_stream_ended(self) -> None:
        parent_completed = _voice_task_event(
            "parent_completed",
            9,
            taskId="task_parent",
            state="completed",
            phase="completed",
            event_type="result",
        )
        child_queued = _voice_task_event(
            "child_queued",
            1,
            taskId="task_child_retry",
            state="queued",
            phase="queued",
            event_type="snapshot",
            parentTaskId="task_parent",
        )
        child_source = _voice_task_event(
            "child_source",
            2,
            taskId="task_child_retry",
            state="running",
            phase="source",
            event_type="source",
            parentTaskId="task_parent",
            source={"title": "Synthetic source", "url": "https://example.test/retry"},
        )
        child_completed = _voice_task_event(
            "child_completed",
            3,
            taskId="task_child_retry",
            state="completed",
            phase="completed",
            event_type="result",
            parentTaskId="task_parent",
        )
        fake_session = _CallTaskEventSession(
            [parent_completed, child_queued, child_source, child_completed]
        )
        relayed: list[dict] = []

        async def run() -> None:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(
                    call_session_id="call_1",
                    call_secret="secret",
                    job_id="job_1",
                    worker_id="worker_1",
                ),
                task_event_handler=relayed.append,
            )
            await llm._relay_task_event_once(parent_completed)
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                task = llm.start_call_task_event_stream(
                    reconnect_min_s=0.01,
                    reconnect_max_s=0.02,
                )
                self.assertIsNotNone(task)
                await asyncio.wait_for(fake_session.delivered.wait(), timeout=1.0)
                await llm.stop_call_task_event_stream()
            await llm.close_background_continuations()

        asyncio.run(run(), debug=True)

        self.assertEqual(
            [event["eventId"] for event in relayed],
            ["parent_completed", "child_queued", "child_source", "child_completed"],
        )
        self.assertEqual(len(fake_session.get_calls), 1)
        url, _args, kwargs = fake_session.get_calls[0]
        self.assertEqual(
            url,
            "http://librechat.test/api/viventium/voice/tasks/events",
        )
        self.assertEqual(kwargs["params"], {"callSessionId": "call_1"})
        self.assertEqual(
            kwargs["headers"],
            {
                "Accept": "text/event-stream",
                "X-VIVENTIUM-CALL-SESSION": "call_1",
                "X-VIVENTIUM-CALL-SECRET": "secret",
                "X-VIVENTIUM-JOB-ID": "job_1",
                "X-VIVENTIUM-WORKER-ID": "worker_1",
            },
        )
        self.assertTrue(fake_session.closed)

    def test_call_lifetime_stream_relays_later_completed_source_after_cancel_race(self) -> None:
        completed = _voice_task_event(
            "completed_after_cancel_race",
            7,
            taskId="task_raced",
            state="completed",
            phase="completed",
            event_type="result",
        )
        late_source = _voice_task_event(
            "late_completed_source",
            8,
            taskId="task_raced",
            state="completed",
            phase="source",
            event_type="source",
            source={"title": "Completed source", "url": "https://example.test/completed"},
        )
        late_result = _voice_task_event(
            "late_completed_result",
            9,
            taskId="task_raced",
            state="completed",
            phase="completed",
            event_type="result",
            resultMessageId="msg_completed",
        )
        fake_session = _CallTaskEventSession([completed, late_source, late_result])
        relayed: list[dict] = []

        async def run() -> bool:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(
                    call_session_id="call_1",
                    call_secret="secret",
                    job_id="job_1",
                    worker_id="worker_1",
                ),
                task_event_handler=relayed.append,
            )
            # LibreChat's exact GlassHive 409 already_completed means cancellation was
            # never accepted. The gateway deliberately keeps its local speech barrier,
            # while higher-sequence completed source/result events remain visible.
            llm._task_event_gate.mark_cancel_accepted("task_raced")
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                llm.start_call_task_event_stream(
                    reconnect_min_s=0.01,
                    reconnect_max_s=0.02,
                )
                await asyncio.wait_for(fake_session.delivered.wait(), timeout=1.0)
                await llm.stop_call_task_event_stream()
            suppressed = llm.is_task_output_suppressed("task_raced")
            await llm.close_background_continuations()
            return suppressed

        self.assertTrue(asyncio.run(run(), debug=True))
        self.assertEqual(
            [event["eventId"] for event in relayed],
            ["completed_after_cancel_race", "late_completed_source", "late_completed_result"],
        )

    def test_call_lifetime_task_stream_reconnects_with_full_job_auth_and_closes_cleanly(self) -> None:
        child_running = _voice_task_event(
            "child_after_reconnect",
            1,
            taskId="task_child",
            state="running",
            phase="tool",
            event_type="progress",
        )
        fake_session = _ReconnectCallTaskEventSession([child_running])
        relayed: list[dict] = []

        async def run() -> list[str]:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(
                    call_session_id="call_1",
                    call_secret="secret",
                    job_id="job_1",
                    worker_id="worker_1",
                ),
                task_event_handler=relayed.append,
            )
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                stream_task = llm.start_call_task_event_stream(
                    reconnect_min_s=0.01,
                    reconnect_max_s=0.02,
                )
                await asyncio.wait_for(fake_session.delivered.wait(), timeout=1.0)
                await llm.close_background_continuations()
            self.assertTrue(stream_task.done())
            return [task.get_name() for task in asyncio.all_tasks() if not task.done()]

        live_task_names = asyncio.run(run(), debug=True)

        self.assertEqual([event["eventId"] for event in relayed], ["child_after_reconnect"])
        self.assertEqual(len(fake_session.get_calls), 2)
        self.assertTrue(fake_session.closed)
        self.assertFalse(any(name.startswith("viventium-call-task-events:") for name in live_task_names))

    def test_call_lifetime_task_stream_requires_exact_job_and_worker_auth(self) -> None:
        async def run() -> None:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            self.assertIsNone(llm.start_call_task_event_stream())
            await llm.close_background_continuations()

        asyncio.run(run(), debug=True)

    def test_call_task_stream_startup_401_never_reports_ready(self) -> None:
        fake_session = _CallTaskStatusSession(401)
        health: list[dict] = []

        async def run() -> tuple[bool, dict, list[str]]:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(
                    call_session_id="call_1",
                    call_secret="secret",
                    job_id="job_1",
                    worker_id="worker_1",
                ),
            )
            llm.set_call_task_event_stream_health_handler(health.append)
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                llm.start_call_task_event_stream()
                ready = await llm.wait_call_task_event_stream_ready(timeout_s=0.5)
                snapshot = llm.call_task_event_stream_health
                await llm.close_background_continuations()
            live = [task.get_name() for task in asyncio.all_tasks() if not task.done()]
            return ready, snapshot, live

        ready, snapshot, live = asyncio.run(run(), debug=True)

        self.assertFalse(ready)
        self.assertEqual(snapshot["state"], "terminal")
        self.assertEqual(snapshot["status"], 401)
        self.assertEqual([item["state"] for item in health[:2]], ["connecting", "terminal"])
        self.assertTrue(fake_session.closed)
        self.assertFalse(any(name.startswith("viventium-call-task-events:") for name in live))

    def test_call_task_stream_2xx_without_sync_marker_never_reports_ready(self) -> None:
        fake_session = _CallTaskStatusSession(200)
        health: list[dict] = []

        async def run() -> bool:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(
                    call_session_id="call_1",
                    call_secret="secret",
                    job_id="job_1",
                    worker_id="worker_1",
                ),
            )
            llm.set_call_task_event_stream_health_handler(health.append)
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                llm.start_call_task_event_stream(
                    reconnect_min_s=0.01,
                    reconnect_max_s=0.01,
                )
                ready = await llm.wait_call_task_event_stream_ready(timeout_s=0.05)
                await llm.close_background_continuations()
            return ready

        self.assertFalse(asyncio.run(run(), debug=True))
        self.assertNotIn("connected", [item["state"] for item in health])

    def test_call_task_sync_marker_is_strictly_call_scoped(self) -> None:
        fake_session = _CallTaskSyncOnlySession(
            _voice_task_sync(call_session_id="call_other")
        )

        async def run() -> bool:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(
                    call_session_id="call_1",
                    call_secret="secret",
                    job_id="job_1",
                    worker_id="worker_1",
                ),
            )
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                llm.start_call_task_event_stream()
                ready = await llm.wait_call_task_event_stream_ready(timeout_s=0.05)
                await llm.close_background_continuations()
            return ready

        self.assertFalse(asyncio.run(run(), debug=True))

    def test_call_task_sync_marker_rejects_malformed_contracts(self) -> None:
        valid = {**_voice_task_sync(), "_sse_event": "voice_task_sync"}
        malformed = (
            {**valid, "version": True},
            {**valid, "state": "ready"},
            {**valid, "emittedAt": "not-a-time"},
            {**valid, "emittedAt": "2026-08-09T20:37:59"},
            {**valid, "extra": "field"},
        )

        self.assertEqual(
            _extract_voice_task_sync(
                valid,
                expected_call_session_id="call_1",
            ),
            _voice_task_sync(),
        )
        for payload in malformed:
            with self.subTest(payload=payload):
                self.assertIsNone(
                    _extract_voice_task_sync(
                        payload,
                        expected_call_session_id="call_1",
                    )
                )

    def test_call_task_sync_marker_follows_all_initial_snapshot_events(self) -> None:
        snapshot = _voice_task_event(
            "initial_snapshot",
            1,
            taskId="task_snapshot",
            event_type="snapshot",
        )
        fake_session = _CallTaskEventSession([snapshot])
        relayed: list[dict] = []
        relayed_count_when_connected: list[int] = []

        async def run() -> bool:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(
                    call_session_id="call_1",
                    call_secret="secret",
                    job_id="job_1",
                    worker_id="worker_1",
                ),
                task_event_handler=relayed.append,
            )

            def on_health(item: dict) -> None:
                if item["state"] == "connected":
                    relayed_count_when_connected.append(len(relayed))

            llm.set_call_task_event_stream_health_handler(on_health)
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                llm.start_call_task_event_stream()
                ready = await llm.wait_call_task_event_stream_ready(timeout_s=0.5)
                await llm.close_background_continuations()
            return ready

        self.assertTrue(asyncio.run(run(), debug=True))
        self.assertEqual([event["eventId"] for event in relayed], ["initial_snapshot"])
        self.assertEqual(relayed_count_when_connected, [1])

    def test_disconnect_cancel_barrier_blocks_stale_chunks_then_reconnects_health(self) -> None:
        running = _voice_task_event("before_disconnect", 1, taskId="task_disconnect")
        stale_after_cancel = _voice_task_event(
            "stale_after_cancel",
            2,
            taskId="task_disconnect",
            state="running",
            phase="tool",
            event_type="progress",
        )
        completed = _voice_task_event(
            "completed_after_reconnect",
            3,
            taskId="task_disconnect",
            state="completed",
            phase="completed",
            event_type="result",
        )
        fake_session = _DisconnectThenReconnectCallTaskSession(
            [running],
            [stale_after_cancel, completed],
        )
        relayed: list[dict] = []
        health_states: list[str] = []
        disconnected = asyncio.Event()

        async def run() -> bool:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(
                    call_session_id="call_1",
                    call_secret="secret",
                    job_id="job_1",
                    worker_id="worker_1",
                ),
                task_event_handler=relayed.append,
            )

            def on_health(item: dict) -> None:
                health_states.append(item["state"])
                if item["state"] == "disconnected":
                    disconnected.set()

            llm.set_call_task_event_stream_health_handler(on_health)
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                llm.start_call_task_event_stream(
                    reconnect_min_s=0.05,
                    reconnect_max_s=0.05,
                )
                self.assertTrue(await llm.wait_call_task_event_stream_ready(timeout_s=0.5))
                await asyncio.wait_for(disconnected.wait(), timeout=0.5)
                llm._task_event_gate.mark_cancel_accepted("task_disconnect")
                await asyncio.wait_for(fake_session.delivered.wait(), timeout=1.0)
                await llm.close_background_continuations()
            return llm.is_task_output_suppressed("task_disconnect")

        self.assertTrue(asyncio.run(run(), debug=True))
        self.assertEqual(
            [event["eventId"] for event in relayed],
            ["before_disconnect", "completed_after_reconnect"],
        )
        self.assertIn("disconnected", health_states)
        self.assertGreaterEqual(health_states.count("connected"), 2)

    def test_unexpected_call_task_stream_death_is_terminal_and_leak_free(self) -> None:
        fake_session = _CallTaskEventSession(
            [_voice_task_event("consumer_death", 1, taskId="task_death")],
            marker_first=True,
        )
        health: list[dict] = []

        async def run() -> tuple[dict, list[str]]:
            def fail_consumer(_event: dict) -> None:
                raise RuntimeError("synthetic consumer failure")

            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(
                    call_session_id="call_1",
                    call_secret="secret",
                    job_id="job_1",
                    worker_id="worker_1",
                ),
                task_event_handler=fail_consumer,
            )
            llm.set_call_task_event_stream_health_handler(health.append)
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                stream = llm.start_call_task_event_stream()
                self.assertTrue(await llm.wait_call_task_event_stream_ready(timeout_s=0.5))
                await asyncio.wait_for(stream, timeout=0.5)
                snapshot = llm.call_task_event_stream_health
                await llm.close_background_continuations()
            live = [task.get_name() for task in asyncio.all_tasks() if not task.done()]
            return snapshot, live

        snapshot, live = asyncio.run(run(), debug=True)

        self.assertEqual(snapshot["state"], "terminal")
        self.assertIsNone(snapshot["status"])
        self.assertEqual(
            [item["state"] for item in health[:3]],
            ["connecting", "syncing", "connected"],
        )
        self.assertIn("terminal", [item["state"] for item in health])
        self.assertTrue(fake_session.closed)
        self.assertFalse(any(name.startswith("viventium-call-task-events:") for name in live))

    def test_explicit_task_cancel_calls_task_endpoint_once(self) -> None:
        fake_session = _FakeClosedStreamSession()
        cancel_acceptances = []

        async def cancel_twice() -> tuple[dict, dict]:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
                task_cancel_handler=lambda task_id, result: cancel_acceptances.append(
                    (task_id, result.get("state"))
                ),
            )
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                first = await llm.cancel_task("task_1", reason="user_requested")
                second = await llm.cancel_task("task_1", reason="user_requested")
            return first, second

        first, second = asyncio.run(cancel_twice())

        cancel_urls = [
            call[0]
            for call in fake_session.post_calls
            if "/voice/tasks/" in str(call[0])
        ]
        self.assertEqual(
            cancel_urls,
            ["http://librechat.test/api/viventium/voice/tasks/task_1/cancel"],
        )
        self.assertEqual(first, second)
        self.assertEqual(cancel_acceptances, [("task_1", first.get("state"))])

    def test_terminal_task_tombstone_precedes_publish_and_rejects_stale_replay(self) -> None:
        running = _voice_task_event("event_5", 5)
        cancelling = {
            **running,
            "eventId": "event_6",
            "sequence": 6,
            "state": "cancelling",
        }
        replay = {**running, "eventId": "event_4", "sequence": 4}
        observed = []

        async def run() -> tuple[bool, bool, bool]:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
                task_event_handler=lambda event: observed.append(
                    (event["sequence"], llm.is_task_output_suppressed("task_1"))
                ),
            )
            accepted_running = await llm._relay_task_event_once(running)
            accepted_cancelling = await llm._relay_task_event_once(cancelling)
            accepted_replay = await llm._relay_task_event_once(replay)
            return accepted_running, accepted_cancelling, accepted_replay

        accepted = asyncio.run(run())
        self.assertEqual(accepted, (True, True, False))
        self.assertEqual(observed, [(5, False), (6, True)])

    def test_cancel_suppression_survives_a_full_120_minute_soak(self) -> None:
        now = [0.0]
        gate = _VoiceTaskEventGate(clock=lambda: now[0])
        gate.mark_cancel_accepted("task_1")

        now[0] = 7_201.0

        self.assertTrue(gate.is_suppressed("task_1"))
        self.assertFalse(gate.accept(_voice_task_event("stale", 1)))

    def test_cancel_suppression_survives_more_than_ten_thousand_ordinary_tasks(self) -> None:
        now = [0.0]
        gate = _VoiceTaskEventGate(max_tasks=128, clock=lambda: now[0])
        gate.mark_cancel_accepted("task_cancelled")

        for index in range(10_500):
            event = _voice_task_event(
                f"ordinary_{index}",
                1,
                taskId=f"task_ordinary_{index}",
            )
            self.assertTrue(gate.accept(event))

        self.assertTrue(gate.is_suppressed("task_cancelled"))
        self.assertFalse(
            gate.accept(
                _voice_task_event(
                    "cancelled_stale_under_pressure",
                    1,
                    taskId="task_cancelled",
                )
            )
        )

    def test_live_suppression_is_never_evicted_by_tombstone_count_pressure(self) -> None:
        now = [0.0]
        gate = _VoiceTaskEventGate(clock=lambda: now[0])
        gate.mark_cancel_accepted("task_cancelled")

        for index in range(65_537):
            gate.mark_cancel_accepted(f"other_cancelled_{index}")

        self.assertTrue(gate.is_suppressed("task_cancelled"))

    def test_suppression_tombstones_expire_only_after_the_full_24_hour_ttl(self) -> None:
        now = [0.0]
        gate = _VoiceTaskEventGate(clock=lambda: now[0])
        gate.mark_cancel_accepted("task_cancelled")

        now[0] = 86_400.0
        self.assertTrue(gate.is_suppressed("task_cancelled"))
        now[0] = 86_400.001
        self.assertFalse(gate.is_suppressed("task_cancelled"))

    def test_explicit_task_cancel_stops_detached_continuation(self) -> None:
        fake_session = _FakeClosedStreamSession()

        async def run() -> bool:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            continuation = asyncio.create_task(asyncio.sleep(60))
            llm._background_continuations.add(continuation)
            llm._continuations_by_task["task_1"] = {continuation}
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                await llm.cancel_task("task_1")
            await asyncio.sleep(0)
            cancelled = continuation.cancelled()
            await llm.close_background_continuations()
            return cancelled

        self.assertTrue(asyncio.run(run()))

    def test_late_speaker_revision_posts_to_dedicated_endpoint_once(self) -> None:
        fake_session = _FakeClosedStreamSession()
        revision = {
            "version": 1,
            "callSessionId": "call_1",
            "turnId": "turn_000001",
            "segmentId": "segment_000001",
            "sequence": 1,
            "revision": 2,
            "text": "Synthetic words",
            "isFinal": True,
            "speaker": {
                "key": "provider:A",
                "label": "Speaker 1",
                "source": "provider_diarization",
                "attribution": "unverified",
                "actorTrust": "shared_mic_unverified",
                "providerSpeakerId": "A",
            },
        }

        async def post_twice() -> None:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                await llm.post_speaker_segment_revisions([revision])
                await llm.post_speaker_segment_revisions([revision])

        asyncio.run(post_twice())

        revision_calls = [
            call
            for call in fake_session.post_calls
            if str(call[0]).endswith("/voice/speaker-segments/revisions")
        ]
        self.assertEqual(len(revision_calls), 1)
        self.assertEqual(
            revision_calls[0][2]["json"],
            {
                "speakerSegmentRevisions": [revision],
                "ownerParticipantIdentity": "",
                "ownerTrackSid": "",
            },
        )

    def test_shared_mic_tombstone_persists_before_bounded_revision_pages(self) -> None:
        fake_session = _FakeClosedStreamSession()
        revisions = []
        for index in range(130):
            revisions.append(
                {
                    "version": 1,
                    "callSessionId": "call_1",
                    "turnId": f"turn_{index:06d}",
                    "segmentId": f"segment_{index:06d}",
                    "sequence": index + 1,
                    "revision": 2,
                    "text": "Synthetic words",
                    "isFinal": True,
                    "speaker": {
                        "key": "provider:A",
                        "label": "Speaker 1",
                        "source": "provider_diarization",
                        "attribution": "unverified",
                        "actorTrust": "shared_mic_unverified",
                        "providerSpeakerId": "A",
                        "trackSid": "TR_owner",
                        "participantIdentity": "owner",
                    },
                }
            )
        state = {
            "version": 1,
            "callSessionId": "call_1",
            "revision": 1,
            "attributionState": "shared_mic_unverified",
            "detectedAt": "2026-08-09T20:37:04.000Z",
            "sourceTrackSid": "TR_owner",
        }

        async def post() -> None:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                await llm.post_speaker_segment_revisions(
                    revisions,
                    session_state=state,
                )

        asyncio.run(post())
        calls = [call for call in fake_session.post_calls if "/voice/speaker" in str(call[0])]
        self.assertTrue(str(calls[0][0]).endswith("/voice/speaker-session-state"))
        revision_calls = [
            call for call in calls if str(call[0]).endswith("/voice/speaker-segments/revisions")
        ]
        self.assertEqual(
            [len(call[2]["json"]["speakerSegmentRevisions"]) for call in revision_calls],
            [64, 64, 2],
        )
        self.assertTrue(
            all(len(json.dumps(call[2]["json"])) < 128_000 for call in revision_calls)
        )

    def test_ambient_ingress_is_structured_and_idempotent(self) -> None:
        fake_session = _FakeClosedStreamSession()
        segment = {
            "version": 1,
            "callSessionId": "call_1",
            "turnId": "turn_ambient_001_000001",
            "segmentId": "segment_ambient_001_000001",
            "sequence": 1,
            "revision": 1,
            "text": "Synthetic guest context",
            "isFinal": True,
            "speaker": {
                "key": "participant:guest",
                "label": "Guest",
                "source": "hybrid",
                "attribution": "unverified",
                "actorTrust": "authenticated_participant",
            },
        }
        payload = {
            "version": 1,
            "callSessionId": "call_1",
            "mode": "wing",
            "ingressKind": "ambient_participant",
            "turnId": segment["turnId"],
            "segments": [segment],
        }

        async def post_twice() -> None:
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                await llm.post_ambient_transcript(payload)
                await llm.post_ambient_transcript(payload)

        asyncio.run(post_twice())

        calls = [
            call for call in fake_session.post_calls
            if str(call[0]).endswith("/voice/ambient-transcript")
        ]
        self.assertEqual(len(calls), 1)
        self.assertEqual(
            calls[0][2]["json"],
            {
                "version": 1,
                "callSessionId": "call_1",
                "mode": "wing",
                "ingressKind": "ambient_participant",
                "turnId": segment["turnId"],
                "segments": [segment],
            },
        )

    def test_listen_only_owner_ingress_uses_exact_zero_authority_contract(self) -> None:
        fake_session = _FakeClosedStreamSession()
        segment = {
            "version": 1,
            "callSessionId": "call_1",
            "turnId": "turn_owner_1",
            "segmentId": "segment_owner_1",
            "sequence": 1,
            "revision": 1,
            "text": "Synthetic owner transcript",
            "isFinal": True,
            "speaker": {
                "key": "participant:owner",
                "label": "Owner",
                "source": "hybrid",
                "attribution": "verified",
                "actorTrust": "owner_participant",
                "participantIdentity": "owner",
            },
        }

        async def post():
            llm = LibreChatLLM(
                origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="secret"),
            )
            with patch("librechat_llm.aiohttp.ClientSession", return_value=fake_session):
                await llm.post_ambient_transcript(
                    {
                        "version": 1,
                        "callSessionId": "call_1",
                        "mode": "listen_only",
                        "ingressKind": "listen_only_owner",
                        "segments": [segment],
                    }
                )

        asyncio.run(post())
        call = next(
            call
            for call in fake_session.post_calls
            if str(call[0]).endswith("/voice/ambient-transcript")
        )
        self.assertEqual(
            call[2]["json"],
            {
                "version": 1,
                "callSessionId": "call_1",
                "ingressKind": "listen_only_owner",
                "segments": [segment],
            },
        )


class TestNativeInputChoices(unittest.TestCase):
    @staticmethod
    def permission_detail_event():
        task = _voice_task_event("native_detail", 1)
        task.update(type="needs_input", state="needs_input", needsInput={
            "prompt": "May I create the file? Allow once or Deny.", "inputType": "choice",
            "choices": [{"value": "allow-once", "label": "Allow once"}],
            "operationTitle": "Create synthetic.txt in the working folder.",
            "nativeInputRequest": {"version": 1, "kind": "permission", "requestId": "permission-detail",
                "requestFingerprint": "a" * 64, "runId": "run-detail", "attemptId": "attempt-detail",
                "expiresAt": "2099-01-01T00:00:00.000Z"}})
        return task

    def test_permission_detail_reaches_actual_relay_without_changing_speech_prompt(self):
        task = self.permission_detail_event()
        self.assertIs(_extract_voice_task_event({"event": "voice_task_event", "voiceTaskEvent": task}), task)
        observed = []
        async def run():
            llm = LibreChatLLM(origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="synthetic-secret"),
                task_event_handler=observed.append)
            return await llm._relay_task_event_once(task)
        self.assertTrue(asyncio.run(run()))
        self.assertEqual(observed, [task])
        self.assertEqual(observed[0]["needsInput"]["prompt"], "May I create the file? Allow once or Deny.")

    def test_permission_detail_rejects_unbound_nonpermission_malformed_or_oversized_values(self):
        for changes in ({"operationTitle": "x" * 8001}, {"operationTitle": 42}, {"operationTitle": ""},
                        {"inputType": "text"}, {"nativeInputRequest": None},
                        {"nativeInputRequest": {**self.permission_detail_event()["needsInput"]["nativeInputRequest"], "kind": "question"}}):
            with self.subTest(changes=list(changes)):
                task = self.permission_detail_event()
                task["needsInput"].update(changes)
                self.assertIsNone(_extract_voice_task_event({"event": "voice_task_event", "voiceTaskEvent": task}))

    def test_preserves_valid_choices_and_rejects_malformed_choices(self):
        task = _voice_task_event("native_choice", 1)
        task.update(type="needs_input", state="needs_input", needsInput={"prompt":"Write the requested file", "inputType":"choice", "choices":[{"value":"allow-a", "label":"Allow once"}]})
        envelope = {"event":"voice_task_event", "voiceTaskEvent":task}
        self.assertEqual(_extract_voice_task_event(envelope)["needsInput"]["choices"], task["needsInput"]["choices"])
        task["needsInput"]["choices"] = [{"value":"allow-a", "label":"Allow once", "secret":"not permitted"}]
        self.assertIsNone(_extract_voice_task_event(envelope))


class TestNativeInputStopPresentation(unittest.TestCase):
    def test_owner_input_outcomes_are_not_reported_as_provider_outages(self):
        expected = {
            "native_input_declined": "You declined that action. It was stopped.",
            "native_input_expired": "The approval request expired, so that action was stopped. Please retry.",
            "native_input_cancelled": "That action was cancelled.",
            "native_turn_cancelled": "That action was cancelled.",
            "source_context_unavailable": "The conversation context could not be preserved. Please retry this turn.",
            "provider_response_failed": "The model returned no usable answer. Please retry this turn.",
        }
        for code, message in expected.items():
            with self.subTest(code=code):
                final = {"final": True, "responseMessage": {"content": [{"type": "error", "error": "Synthetic private detail", "error_class": code}]}}
                self.assertEqual(_extract_final_response_text(final), message)

    def test_unknown_or_untyped_error_keeps_existing_failure_boundary(self):
        self.assertEqual(_select_stream_error_message("Synthetic", code={}), _select_stream_error_message("Synthetic"))

class VoiceLateMetricsRegressionTests(unittest.TestCase):
    def test_playout_before_synthesis_metrics_joins_the_same_trace(self):
        async def run(order):
            llm = LibreChatLLM(origin='http://librechat.test', auth=LibreChatAuth(call_session_id='call_1', call_secret='secret'))
            trace = VoiceHopTrace(correlation_id='late-metrics', call_session_id='call_1')
            trace.record('first_model_token', 1000)
            llm.register_trace(trace)
            timestamps = {'audio_output': 1300, 'tts_first_byte': 1200}
            for hop in order:
                self.assertEqual(llm.record_next_trace_hop(hop, timestamps[hop]), 'late-metrics')
            self.assertNotIn('late-metrics', llm._summarized_trace_ids)
            self.assertEqual(trace.terminal_summary({})['timestampsMs']['audio_output'], 1300)
            self.assertEqual(trace.terminal_summary({})['timestampsMs']['tts_first_byte'], 1200)
            llm.schedule_trace_terminal(trace, grace_s=0, stream_terminal=True)
            await asyncio.sleep(0.01)
            self.assertIn('late-metrics', llm._summarized_trace_ids)
            await llm.close_background_continuations()
        for order in [('audio_output', 'tts_first_byte'), ('tts_first_byte', 'audio_output')]:
            with self.subTest(order=order):
                asyncio.run(run(order))

    def test_stream_grace_waits_for_its_active_livekit_handle(self):
        async def run():
            llm = LibreChatLLM(origin='http://librechat.test', auth=LibreChatAuth(call_session_id='call_1', call_secret='secret'))
            trace = VoiceHopTrace(correlation_id='active-playout', call_session_id='call_1')
            llm.register_trace(trace)
            llm._speech_handles_by_trace_id[trace.correlation_id] = SimpleNamespace(done=lambda: False)
            llm.schedule_trace_terminal(trace, grace_s=0, stream_terminal=True)
            await asyncio.sleep(0)
            self.assertNotIn(trace.correlation_id, llm._summarized_trace_ids)
            self.assertNotIn(trace.correlation_id, llm._trace_finalizers)
            llm._speech_handles_by_trace_id.pop(trace.correlation_id)
            llm.schedule_trace_terminal(trace, grace_s=0, stream_terminal=True)
            await asyncio.sleep(0.01)
            self.assertIn(trace.correlation_id, llm._summarized_trace_ids)
            await llm.close_background_continuations()
        asyncio.run(run())

    def test_terminal_error_speech_tracks_audio_without_claiming_a_model_token(self):
        llm = LibreChatLLM(origin='http://librechat.test', auth=LibreChatAuth(call_session_id='call_1', call_secret='secret'))
        trace = VoiceHopTrace(correlation_id='error-speech', call_session_id='call_1')
        llm.register_trace(trace)
        llm._speech_output_trace_ids.add(trace.correlation_id)
        self.assertEqual(llm.record_next_trace_hop('audio_output', 1300), 'error-speech')
        self.assertEqual(llm.record_next_trace_hop('tts_first_byte', 1200), 'error-speech')
        self.assertFalse(trace.has('first_model_token'))

    def test_early_exact_handle_completion_cannot_finalize_an_open_stream(self):
        async def run():
            llm = LibreChatLLM(origin='http://librechat.test', auth=LibreChatAuth(call_session_id='call_1', call_secret='secret'))
            trace = VoiceHopTrace(correlation_id='early-handle', call_session_id='call_1')
            llm.register_trace(trace)
            presentation = llm._presentation_coordinator.begin_stable(source_event_id='source_1', presentation_ref=trace.correlation_id)
            handle = _CompletableSpeechHandle('handle_1')
            llm.register_speech_handle(handle)
            llm._bind_next_speech_handle(presentation)
            llm._ack_completed_presentation = AsyncMock(return_value=True)
            handle.complete()
            await asyncio.sleep(0)
            self.assertNotIn(trace.correlation_id, llm._trace_finalizers)
            self.assertNotIn(trace.correlation_id, llm._summarized_trace_ids)
            llm.schedule_trace_terminal(trace, grace_s=0, stream_terminal=True)
            await asyncio.sleep(0.01)
            self.assertIn(trace.correlation_id, llm._summarized_trace_ids)
            await llm.close_background_continuations()
        asyncio.run(run())

    async def _held_stream_trace_case(self, *, early_handle_done=False, detach=False, finish_detached=False):
        started, release = asyncio.Event(), asyncio.Event()
        events = [
            {'event': 'on_run_step', 'data': {'id': 'tool-start', 'type': 'tool_calls', 'status': 'running'}},
            {'text': 'A synthetic response can start speaking now.'},
            {'event': 'on_run_step_completed', 'data': {'id': 'tool-end', 'result': {'type': 'tool_call'}}},
            {'final': True, 'responseMessage': {'content': [{'type': 'text', 'text': 'A synthetic response can start speaking now.'}]}},
        ]
        session = _FakeStreamingSseSession(events)
        original_post, original_get = session.post, session.get
        def post(*args, **kwargs):
            response = original_post(*args, **kwargs)
            response._payload['taskId'] = 'task_1'
            return response
        def get(url, *args, **kwargs):
            response = original_get(url, *args, **kwargs)
            if not str(url).endswith('/state'):
                response.content = _FakeSseContent(events, pause_before=2, started=started, release=release)
            return response
        session.post, session.get = post, get
        llm = LibreChatLLM(origin='http://librechat.test', auth=LibreChatAuth(call_session_id='call_1', call_secret='secret'))
        handle = _CompletableSpeechHandle('handle_1')
        if not detach:
            llm.register_speech_handle(handle)
        llm._ack_completed_presentation = AsyncMock(return_value=True)
        logs, chunks = [], []
        loop = asyncio.get_running_loop()
        with patch('librechat_llm.aiohttp.ClientSession', return_value=session), \
             patch('librechat_llm.logger.info', side_effect=lambda fmt, *args: logs.append(fmt % args)), \
             patch.object(loop, 'call_later', return_value=unittest.mock.Mock()) as schedule:
            stream = llm.chat(chat_ctx=ChatContext(items=[ChatMessage(role='user', content=['Synthetic question.'])]))
            send = stream._event_ch.send_nowait
            def capture(chunk):
                chunks.append(chunk)
                return send(chunk)
            try:
                with patch.object(stream._event_ch, 'send_nowait', side_effect=capture):
                    await asyncio.wait_for(started.wait(), 1)
                    trace = llm._traces_by_id[stream._request_id]
                    self.assertTrue(any(chunk.delta and chunk.delta.content for chunk in chunks))
                    self.assertTrue(trace.has('first_model_token'))
                    self.assertTrue(trace.has('tool_start'))
                    self.assertFalse(trace.has('tool_end'))
                    self.assertFalse(stream._task.done())
                    self.assertEqual(len(session.post_calls), 1)
                    if detach:
                        await stream.aclose()
                        await asyncio.sleep(0)
                        self.assertTrue(llm._background_continuations)
                        self.assertNotIn(trace.correlation_id, llm._trace_finalizers)
                        if finish_detached:
                            release.set()
                            await llm.wait_for_background_continuations(timeout_s=1)
                            self.assertTrue(trace.has('tool_end'))
                            self.assertFalse(llm._background_continuations)
                            self.assertEqual(schedule.call_args.args[0], 5.0)
                            schedule.call_args.args[1]()
                    else:
                        llm.record_next_trace_hop('audio_output', 1300)
                        llm.record_next_trace_hop('tts_first_byte', 1200)
                        if early_handle_done:
                            handle.complete()
                            await asyncio.sleep(0)
                        self.assertNotIn(trace.correlation_id, llm._summarized_trace_ids)
                        self.assertNotIn(trace.correlation_id, llm._trace_finalizers)
                        release.set()
                        await stream._task
                        self.assertTrue(trace.has('tool_end'))
                        if not early_handle_done:
                            self.assertNotIn(trace.correlation_id, llm._trace_finalizers)
                            handle.complete()
                            await asyncio.sleep(0)
                        self.assertEqual(schedule.call_args.args[0], 5.0)
                        schedule.call_args.args[1]()
                    await llm.close_background_continuations()
                    summaries = [json.loads(line[len('[VoiceHop] '):]) for line in logs if line.startswith('[VoiceHop] ') and 'voice_hop_trace_terminal' in line]
                    self.assertEqual(len(summaries), 1)
                    self.assertIn('utterance_end', summaries[0]['missingHops'])
                    if not detach:
                        self.assertNotIn('tool_end', summaries[0]['missingHops'])
                        self.assertEqual(summaries[0]['timestampsMs']['audio_output'], 1300)
                        self.assertEqual(summaries[0]['timestampsMs']['tts_first_byte'], 1200)
            finally:
                await stream.aclose()
                await llm.close_background_continuations()

    def test_sdk_owned_stream_speaks_before_late_tool_end_and_waits_for_handle(self):
        for early in (False, True):
            with self.subTest(early_handle_done=early):
                asyncio.run(self._held_stream_trace_case(early_handle_done=early))

    def test_cancelled_sdk_consumer_keeps_detached_terminal_owner(self):
        for finish in (False, True):
            with self.subTest(finish_detached=finish):
                asyncio.run(self._held_stream_trace_case(detach=True, finish_detached=finish))

    def test_call_end_seals_incomplete_trace_once_without_invented_clocks(self):
        async def run():
            llm = LibreChatLLM(origin='http://librechat.test', auth=LibreChatAuth(call_session_id='call_1', call_secret='secret'))
            trace = VoiceHopTrace(correlation_id='call-end', call_session_id='call_1')
            llm.register_trace(trace)
            logs = []
            with patch('librechat_llm.logger.info', side_effect=lambda fmt, *args: logs.append(fmt % args)):
                await llm.close_background_continuations()
                await llm.close_background_continuations()
            summaries = [json.loads(line[len('[VoiceHop] '):]) for line in logs if 'voice_hop_trace_terminal' in line]
            self.assertEqual(len(summaries), 1)
            self.assertEqual(summaries[0]['status'], 'incomplete')
            self.assertIn('audio_output', summaries[0]['missingHops'])
            self.assertIn('utterance_end', summaries[0]['missingHops'])
        asyncio.run(run())

class TestPublicPartCompletionCarrier(unittest.TestCase):
    def _completion(self, *, part='run-a:1', **changes):
        completion = {'version': 1, 'complete': True, 'request_id': 'request-a', 'run_id': 'run-a',
                      'part_id': part, 'message_id': 'message-a', 'stream_id': 'stream_voice_1'}
        completion.update(changes)
        return {'event': 'on_public_content_part_complete', 'data': {
            'completion': completion, 'deliveryDisposition': {'version': 1, 'audio': 'eligible',
                                                             'source': 'model', 'required': True, 'valid': True}}}

    def _final(self, text='First part. Later part.'):
        return {'final': True, 'responseMessage': {'content': [{'type': 'text', 'text': text}]}}

    async def _run(self, events, *, fake=None, connected=True, reconnect=True, hook=None):
        fake = fake or _FakeStreamingSseSession(events)
        llm = LibreChatLLM(origin='http://librechat.test', auth=LibreChatAuth(call_session_id='call_1', call_secret='synthetic'), is_participant_connected=lambda: connected, task_event_handler=(lambda event: hook(llm, event)) if hook else None)
        chunks = []
        with patch('librechat_llm.aiohttp.ClientSession', return_value=fake), \
             patch('librechat_llm._get_voice_sse_retry_config', return_value=(1, 0.0)), \
             patch.object(llm, 'wait_for_participant_reconnect', return_value=reconnect):
            async with llm.chat(chat_ctx=ChatContext(items=[ChatMessage(role='user', content=['Synthetic'])])) as stream:
                async for chunk in stream:
                    chunks.append(chunk)
        return chunks

    def _markers(self, chunks):
        return [c.delta.extra['viventium_public_part_complete'] for c in chunks
                if c.delta and 'viventium_public_part_complete' in (c.delta.extra or {})]

    def test_completion_only_controls_follow_exact_tagged_text_and_do_not_end_cognition(self):
        text = '<emphasis>First part.</emphasis>'
        chunks = asyncio.run(self._run([{'text': text}, self._completion(), self._completion(),
                                       {'text': ' Later part.'}, self._completion(part='run-a:2'), self._final(text+' Later part.')]))
        self.assertEqual(''.join(c.delta.content or '' for c in chunks), text+' Later part.')
        self.assertEqual([m['part_id'] for m in self._markers(chunks)], ['run-a:1', 'run-a:2'])
        self.assertIsNone(chunks[1].delta.content)
        self.assertTrue(chunks[2].delta.content)
        self.assertTrue(all(c.id == chunks[0].id for c in chunks))

    def test_invalid_unbound_skip_and_noncompletion_events_never_flush(self):
        events = [{'text': 'Public.'}]
        for changed in [{'complete': False}, {'stream_id': 'foreign'}, {'version': True}, {'text': 'must not carry text'}, {'run_id': ''}]:
            events.append(self._completion(**changed))
        skipped = self._completion(); skipped['data']['deliveryDisposition']['audio'] = 'skip'; events.append(skipped)
        events += [{'event': 'on_run_step_completed', 'data': {'result': {'type': 'tool_call'}}}, self._final('Public.')]
        chunks = asyncio.run(self._run(events))
        self.assertEqual(self._markers(chunks), [])
        self.assertEqual(''.join(c.delta.content or '' for c in chunks), 'Public.')

    def test_control_without_public_text_or_only_no_response_has_no_speech(self):
        for text in ['', '{NTA}']:
            with self.subTest(text=text):
                chunks = asyncio.run(self._run([{'text': text}, self._completion(), self._final(text)]))
                self.assertEqual(self._markers(chunks), [])
                self.assertEqual(''.join(c.delta.content or '' for c in chunks), '')

    def test_stop_drops_late_control_and_text(self):
        stopped = _voice_task_event('stop', 2, state='cancelling', phase='stopping', event_type='state')
        events = [{'event': 'voice_task_event', 'voiceTaskEvent': _voice_task_event('running', 1)},
                  {'text': 'First part.'}, {'event': 'voice_task_event', 'voiceTaskEvent': stopped},
                  self._completion(), {'text': ' Forbidden late part.'}, self._final()]
        chunks = asyncio.run(self._run(events))
        self.assertEqual(self._markers(chunks), [])
        self.assertEqual(''.join(c.delta.content or '' for c in chunks), 'First part.')

    def test_reconnect_replay_preserves_one_boundary_and_exact_words(self):
        boundary = self._completion()
        fake = _FakeResumingSseSession([[{'text': 'First part.'}, boundary],
                                        [{'sync': True, 'resumeState': {'aggregatedContent': [{'type': 'text', 'text': 'First part.'}]}}, boundary, {'text': ' Later part.'}, self._final()]])
        chunks = asyncio.run(self._run([], fake=fake))
        self.assertEqual(len(self._markers(chunks)), 1)
        self.assertEqual(''.join(c.delta.content or '' for c in chunks), 'First part. Later part.')

    def test_disconnected_queue_drains_text_then_control_and_grace_drop_has_neither(self):
        events = [{'text': '<emphasis>First part.</emphasis>'}, self._completion(), self._final('<emphasis>First part.</emphasis>')]
        chunks = asyncio.run(self._run(events, connected=False))
        self.assertTrue(chunks[0].delta.content)
        self.assertEqual(len(self._markers(chunks)), 1)
        self.assertIsNone(chunks[1].delta.content)
        self.assertEqual(asyncio.run(self._run(events, connected=False, reconnect=False)), [])

    def test_artifact_failure_notice_survives_as_later_public_text_after_completion(self):
        final = self._final('Here is the file.')
        final['responseMessage'].update(metadata={'viventium': {'deliveryDisposition': {
            'version': 1, 'audio': 'eligible', 'source': 'model', 'valid': True, 'required': True}}},
            attachments=[{'nativeOutputFile': {'version': 1, 'status': 'unavailable', 'code': 'native_output_file_unreadable'}}])
        chunks = asyncio.run(self._run([{'text': 'Here is the file.'}, self._completion(), final]))
        self.assertEqual(len(self._markers(chunks)), 1)
        self.assertEqual(''.join(c.delta.content or '' for c in chunks), 'Here is the file.\nThe file could not be attached.')
        marker_index = next(i for i,c in enumerate(chunks) if c.delta.extra)
        self.assertIn('could not be attached', chunks[marker_index+1].delta.content)

    def test_completion_reaches_llm_consumer_while_final_is_still_pending(self):
        async def run():
            allow_final = asyncio.Event()
            owner = self
            class DeferredContent:
                async def iter_any(self):
                    for event in [{'text': '<emphasis>First part.</emphasis>'}, owner._completion()]:
                        yield ('data: '+json.dumps(event)+'\n\n').encode()
                    await allow_final.wait()
                    yield ('data: '+json.dumps(owner._final('<emphasis>First part.</emphasis>'))+'\n\n').encode()
            fake = _FakeStreamingSseSession([])
            response = _FakeStreamingSseResponse([]); response.content = DeferredContent()
            fake.get = lambda *args, **kwargs: response
            llm = LibreChatLLM(origin='http://librechat.test', auth=LibreChatAuth(call_session_id='call_1', call_secret='synthetic'))
            with patch('librechat_llm.aiohttp.ClientSession', return_value=fake):
                stream = llm.chat(chat_ctx=ChatContext(items=[ChatMessage(role='user', content=['Synthetic'])]))
                async with stream:
                    async for chunk in stream:
                        if chunk.delta.extra:
                            self.assertFalse(stream._task.done())
                            self.assertFalse(allow_final.is_set())
                            allow_final.set()
                self.assertTrue(allow_final.is_set())
        asyncio.run(asyncio.wait_for(run(), timeout=2.0))

    def test_supersession_drops_pending_control_without_suppressing_existing_words(self):
        def supersede(llm, event):
            if event['state'] == 'completed':
                llm._presentation_coordinator.begin_stable(source_event_id='newer', presentation_ref='newer')
        completed = _voice_task_event('finished', 2, state='completed', phase='completed', event_type='result')
        events = [{'text': 'First part.'}, {'event': 'voice_task_event', 'voiceTaskEvent': completed},
                  self._completion(), {'text': ' Forbidden later.'}, self._final()]
        chunks = asyncio.run(self._run(events, hook=supersede))
        self.assertEqual(self._markers(chunks), [])
        self.assertEqual(''.join(c.delta.content or '' for c in chunks), 'First part.')

    def test_skipped_model_delta_never_seals_an_eligible_control(self):
        skipped = {'event': 'on_message_delta', 'data': {'delta': {
            'content': [{'type': 'text', 'text': 'Unspoken tool handoff.'}], 'metadata': {'viventium': {
                'deliveryDisposition': {'version': 1, 'audio': 'skip', 'source': 'model', 'valid': True, 'required': True}}}}}}
        chunks = asyncio.run(self._run([skipped, self._completion(), self._final('')]))
        self.assertEqual(self._markers(chunks), [])
        self.assertEqual(''.join(c.delta.content or '' for c in chunks), '')


class TestErrorSpeechCallAuthority(unittest.TestCase):
    def _state(self, **changes):
        state = {"version": 1, "callSessionId": "call_1", "mode": "call",
                 "status": "listening", "revision": 7,
                 "updatedAt": "2026-08-09T20:37:04.000Z"}
        state.update(changes)
        return state

    def _error(self):
        return {"event": "error", "error": "Synthetic upstream failure"}

    def _final_error(self):
        return {"final": True, "responseMessage": {"messageId": "message_1",
                "content": [{"type": "error", "error": "Synthetic private failure",
                             "error_class": "provider_response_failed"}]}}

    async def _run(self, events, *, state=None, status=200, connected=True,
                   reconnect=True, during_read=None, unavailable=False, hook=None):
        class ErrorSseContent:
            async def iter_any(self):
                for event in events:
                    kind = "error" if event.get("event") == "error" else "message"
                    yield ("event: " + kind + "\ndata: " + json.dumps(event) + "\n\n").encode()

        class ErrorSseSession(_FakeStreamingSseSession):
            def get(self, url, *args, **kwargs):
                self.get_calls.append((url, args, kwargs))
                response = _FakeStreamingSseResponse([])
                response.content = ErrorSseContent()
                return response

        fake = ErrorSseSession(events)
        state_session = _FakeCallStateSession(state, status=status)
        llm = LibreChatLLM(
            origin="http://librechat.test",
            auth=LibreChatAuth(call_session_id="call_1", call_secret="synthetic",
                              job_id="job_1", worker_id="worker_1"),
            is_participant_connected=lambda: connected,
            task_event_handler=(lambda event: hook(llm, event)) if hook else None,
        )
        llm._call_state_session = state_session
        if during_read:
            base_get = state_session.get
            def get(url, *args, **kwargs):
                response = base_get(url, *args, **kwargs)
                base_json = response.json
                async def read():
                    await asyncio.sleep(0)
                    during_read(llm)
                    return await base_json()
                response.json = read
                return response
            state_session.get = get
        if unavailable:
            def get(url, *args, **kwargs):
                state_session.get_calls.append((url, args, kwargs))
                raise aiohttp.ClientConnectionError("Synthetic unavailable authority")
            state_session.get = get
        chunks = []
        with patch("librechat_llm.aiohttp.ClientSession", return_value=fake), \
             patch("librechat_llm._get_voice_sse_retry_config", return_value=(1, 0.0)), \
             patch.object(llm, "wait_for_participant_reconnect", return_value=reconnect), \
             patch.object(llm, "_followup_handler", None):
            async with llm.chat(chat_ctx=ChatContext(items=[ChatMessage(role="user", content=["Synthetic"])])) as stream:
                async for chunk in stream:
                    chunks.append(chunk)
        text = "".join(chunk.delta.content or "" for chunk in chunks)
        self.assertFalse(any(str(call[0]).endswith("/abort") for call in fake.post_calls))
        return text, state_session, llm

    def test_ended_or_failed_call_suppresses_both_error_fallback_producers(self):
        for status in ("ended", "failed"):
            for error in (self._error(), self._final_error()):
                with self.subTest(status=status, final="final" in error):
                    text, state, _ = asyncio.run(self._run([error], state=self._state(status=status)))
                    self.assertEqual(text, "")
                    self.assertEqual(len(state.get_calls), 1)

    def test_live_call_preserves_typed_and_stream_error_messages(self):
        for error, expected in (
            (self._error(), _select_stream_error_message("Synthetic upstream failure")),
            (self._final_error(), "The model returned no usable answer. Please retry this turn."),
        ):
            with self.subTest(final="final" in error):
                text, state, _ = asyncio.run(self._run([error], state=self._state()))
                self.assertEqual(text, expected)
                self.assertEqual(len(state.get_calls), 1)
                self.assertEqual(state.get_calls[0][0], "http://librechat.test/api/viventium/voice/call-sessions/call_1/state")
                self.assertEqual(state.get_calls[0][2]["headers"]["X-VIVENTIUM-WORKER-ID"], "worker_1")

    def test_access_denial_keeps_typed_meaning_in_stream_and_final_error_speech(self):
        for error in (
            {"event": "error", "error": "403 PRIVATE_WORKSPACE_CANARY", "error_class": "provider_access_denied"},
            {"final": True, "responseMessage": {"messageId": "message_1", "content": [
                {"type": "error", "error": "403 PRIVATE_WORKSPACE_CANARY", "error_class": "provider_access_denied"}]}},
        ):
            with self.subTest(final="final" in error):
                text, state, _ = asyncio.run(self._run([error], state=self._state()))
                self.assertEqual(text, "The model provider denied access to this request.")
                self.assertNotIn("PRIVATE_WORKSPACE_CANARY", text)
                self.assertEqual(len(state.get_calls), 1)

    def test_unknown_foreign_malformed_or_unavailable_authority_preserves_live_error(self):
        cases = [({}, {}), (None, {}), (self._state(callSessionId="foreign"), {}),
                 (self._state(revision=True), {}), (self._state(status="connected"), {}),
                 (self._state(updatedAt="invalid"), {}), (self._state(mode="invalid"), {}),
                 (self._state(status="ended"), {"status": 503}),
                 (self._state(status="ended"), {"unavailable": True})]
        for state, options in cases:
            with self.subTest(state=state, options=options):
                text, session, _ = asyncio.run(self._run([self._error()], state=state, **options))
                self.assertEqual(text, _select_stream_error_message("Synthetic upstream failure"))
                self.assertEqual(len(session.get_calls), 1)

    def test_healthy_text_and_final_do_not_read_call_state(self):
        final = {"final": True, "responseMessage": {"content": [{"type": "text", "text": "Useful reply."}]}}
        for events in ([{"text": "Useful reply."}, final], [final]):
            with self.subTest(streamed=len(events) == 2):
                text, state, _ = asyncio.run(self._run(events, state=self._state(status="ended")))
                self.assertEqual(text, "Useful reply.")
                self.assertEqual(state.get_calls, [])

    def test_already_stopped_stream_never_reads_or_emits_fallback(self):
        stopped = _voice_task_event("stop", 2, state="cancelling", phase="stopping", event_type="state")
        text, state, _ = asyncio.run(self._run(
            [{"event": "voice_task_event", "voiceTaskEvent": _voice_task_event("running", 1)}, {"event": "voice_task_event", "voiceTaskEvent": stopped}, self._error()],
            state=self._state()))
        self.assertEqual(text, "")
        self.assertEqual(state.get_calls, [])

    def test_stop_and_supersession_during_authority_read_drop_error_output(self):
        for transition in (
            lambda llm: llm._task_event_gate.accept(_voice_task_event("stop", 2, state="cancelling", phase="stopping", event_type="state")),
            lambda llm: llm._presentation_coordinator.begin_stable(source_event_id="newer", presentation_ref="newer"),
        ):
            with self.subTest(transition=transition):
                text, state, _ = asyncio.run(self._run(
                    [{"event": "voice_task_event", "voiceTaskEvent": _voice_task_event("running", 1)}, self._error()],
                    state=self._state(), during_read=transition))
                self.assertEqual(text, "")
                self.assertEqual(len(state.get_calls), 1)

    def test_end_discards_disconnected_speech_before_reconnect(self):
        text, state, _ = asyncio.run(self._run(
            [{"text": "Pending reply."}, self._error()],
            state=self._state(status="ended"), connected=False))
        self.assertEqual(text, "")
        self.assertEqual(len(state.get_calls), 1)

    def test_live_disconnected_error_survives_reconnect(self):
        text, state, _ = asyncio.run(self._run([self._error()], state=self._state(), connected=False))
        self.assertEqual(text, _select_stream_error_message("Synthetic upstream failure"))
        self.assertEqual(len(state.get_calls), 1)

    def test_existing_public_words_remain_and_only_late_apology_is_dropped(self):
        text, _, _ = asyncio.run(self._run([{"text": "Useful reply."}, self._error()], state=self._state(status="ended")))
        self.assertEqual(text, "Useful reply.")

    def test_current_listen_only_state_suppresses_error_speech(self):
        for error in (self._error(), self._final_error()):
            with self.subTest(final="final" in error):
                text, state, _ = asyncio.run(self._run([error], state=self._state(mode="listen_only")))
                self.assertEqual(text, "")
                self.assertEqual(len(state.get_calls), 1)

    def test_skipped_final_error_has_no_speech_or_authority_fetch(self):
        final = self._final_error()
        final["responseMessage"]["metadata"] = {"viventium": {"deliveryDisposition": {
            "version": 1, "audio": "skip", "source": "model", "valid": True, "required": True}}}
        text, state, _ = asyncio.run(self._run([final], state=self._state()))
        self.assertEqual(text, "")
        self.assertEqual(state.get_calls, [])


# === VIVENTIUM START === External task cancellation stops its already queued foreground speech.
# Purpose: Exercise strict Core task-event delivery through the actual pinned LiveKit interruption
# methods. No room, provider request, audio transform or client-auth shortcut is used.
class TestExternalTaskCancelPlayout(unittest.IsolatedAsyncioTestCase):
    def _fixture(self):
        from types import MethodType
        from unittest.mock import Mock
        from livekit.agents.voice.agent_activity import AgentActivity
        from livekit.agents.voice.agent_session import AgentSession
        from livekit.agents.voice.speech_handle import InputDetails, SpeechHandle
        import worker

        speech = SpeechHandle(speech_id="main_speech", allow_interruptions=False,
                              input_details=InputDetails(modality="text"))
        queued = SpeechHandle(speech_id="queued_speech", allow_interruptions=False,
                              input_details=InputDetails(modality="text"))
        activity = SimpleNamespace(
            _cancel_preemptive_generation=lambda: None,
            _interrupt_background_speeches=lambda **kwargs: [],
            _current_speech=speech, _speech_q=[(0, 0, queued)], _rt_session=None,
        )
        activity.interrupt = MethodType(AgentActivity.interrupt, activity)
        session = object.__new__(AgentSession)
        session._activity = activity
        scheduler = SimpleNamespace(cancel_pending=Mock(), set_mode=Mock())
        events = []
        callbacks = []
        llm = LibreChatLLM(origin="http://librechat.test",
                          auth=LibreChatAuth(call_session_id="call_1", call_secret="synthetic"))
        presentation = llm._presentation_coordinator.begin_stable(
            source_event_id="source_1", presentation_ref="trace_1")
        llm.register_trace(VoiceHopTrace(correlation_id="trace_1", call_session_id="call_1"))
        llm.bind_trace_core_context("trace_1", stream_id="stream_1", task_id="task_1",
                                    presentation=presentation)
        llm._speech_handles_by_trace_id["trace_1"] = speech

        def suppress(task_id, result):
            callbacks.append((task_id, llm.is_task_output_suppressed(task_id)))
            worker._apply_task_cancel_suppression(task_id, followup_scheduler=scheduler,
                                                session=session)

        llm.set_task_cancel_handler(suppress)
        llm.set_task_event_handler(lambda event: events.append(
            (event["state"], speech.interrupted, llm.is_task_output_suppressed(event["taskId"]))))
        self.addCleanup(speech._mark_done)
        self.addCleanup(queued._mark_done)
        return SimpleNamespace(llm=llm, speech=speech, queued=queued, session=session,
                               scheduler=scheduler, callbacks=callbacks, events=events)

    @staticmethod
    def _event(state="cancelling", sequence=2, **extra):
        return _voice_task_event(f"event_{sequence}", sequence, state=state,
                                 event_type="state", streamId="stream_1",
                                 conversationId="conversation_1",
                                 owner={"kind": "remote_generation", "id": "stream_1"}, **extra)

    async def test_external_cancelling_interrupts_only_bound_native_speech_before_publish(self):
        f = self._fixture()
        with patch("librechat_llm.aiohttp.ClientSession") as no_network:
            self.assertTrue(await f.llm._relay_task_event_once(self._event()))
        no_network.assert_not_called()
        self.assertTrue(f.speech.interrupted)
        self.assertFalse(f.queued.interrupted)
        self.assertEqual(f.callbacks, [])
        self.assertEqual(f.events, [("cancelling", True, True)])
        f.scheduler.cancel_pending.assert_not_called()

    async def test_first_cancelled_confirmed_snapshot_also_interrupts_native_playout(self):
        f = self._fixture()
        self.assertTrue(await f.llm._relay_task_event_once(self._event("cancelled_confirmed")))
        self.assertTrue(f.speech.interrupted)
        self.assertFalse(f.queued.interrupted)
        self.assertEqual(f.callbacks, [])

    async def test_first_unconfirmed_cancel_snapshot_still_suppresses_native_playout(self):
        f = self._fixture()
        self.assertTrue(await f.llm._relay_task_event_once(self._event("cancelled_unenforceable")))
        self.assertTrue(f.speech.interrupted)
        self.assertEqual(f.callbacks, [])

    async def test_exact_and_later_terminal_replays_do_not_interrupt_twice(self):
        f = self._fixture()
        event = self._event()
        self.assertTrue(await f.llm._relay_task_event_once(event))
        self.assertFalse(await f.llm._relay_task_event_once(event))
        self.assertTrue(await f.llm._relay_task_event_once(self._event("cancelled_confirmed", 3)))
        self.assertEqual(f.callbacks, [])
        f.scheduler.cancel_pending.assert_not_called()

    async def test_external_stop_does_not_invoke_callwide_cancel_callback(self):
        f = self._fixture()
        order = []

        async def interrupt(task_id, event):
            await asyncio.sleep(0)
            f.session.interrupt(force=True)
            order.append("interrupt")

        f.llm.set_task_cancel_handler(interrupt)
        f.llm.set_task_event_handler(lambda event: order.append("publish"))
        await f.llm._relay_task_event_once(self._event())
        self.assertEqual(order, ["publish"])
        self.assertTrue(f.speech.interrupted)

    async def test_direct_cancel_then_external_event_uses_existing_callback_once(self):
        f = self._fixture()
        transport = _FakeClosedStreamSession()
        with patch("librechat_llm.aiohttp.ClientSession", return_value=transport):
            await f.llm.cancel_task("task_1")
            await f.llm._relay_task_event_once(self._event())
        self.assertEqual(f.callbacks, [("task_1", True)])
        self.assertTrue(f.speech.interrupted)
        self.assertEqual(len(transport.post_calls), 1)

    async def test_external_event_then_direct_cancel_keeps_native_interrupt_idempotent(self):
        f = self._fixture()
        transport = _FakeClosedStreamSession()
        await f.llm._relay_task_event_once(self._event())
        self.assertTrue(f.speech.interrupted)
        interrupt_future = f.speech._interrupt_fut
        with patch("librechat_llm.aiohttp.ClientSession", return_value=transport):
            await f.llm.cancel_task("task_1")
            await f.llm.cancel_task("task_1")
        self.assertIs(f.speech._interrupt_fut, interrupt_future)
        self.assertTrue(f.speech.interrupted)
        self.assertTrue(f.queued.interrupted)
        self.assertEqual(len(transport.post_calls), 1)

    async def test_non_cancel_states_leave_current_native_speech_intact(self):
        for state in ["queued", "running", "needs_input", "recovering", "completed", "failed"]:
            with self.subTest(state=state):
                f = self._fixture()
                await f.llm._relay_task_event_once(self._event(state))
                self.assertFalse(f.speech.interrupted)
                self.assertEqual(f.callbacks, [])
                f.speech._mark_done(); f.queued._mark_done()

    async def test_background_worker_foreign_stream_owner_and_call_cannot_interrupt_main(self):
        variants = [
            {"taskId": "background_task", "streamId": "worker_stream", "owner": {"kind": "glasshive_run", "id": "worker_run"}},
            {"taskId": "another_task"},
            {"streamId": "another_stream"},
            {"owner": {"kind": "glasshive_run", "id": "stream_1"}},
            {"owner": {"kind": "remote_generation", "id": "another_stream"}},
            {"callSessionId": "another_call"},
            {"streamId": None},
            {"sequence": True},
        ]
        for changes in variants:
            with self.subTest(changes=changes):
                f = self._fixture()
                await f.llm._relay_task_event_once({**self._event(), **changes})
                self.assertFalse(f.speech.interrupted)
                self.assertFalse(f.queued.interrupted)
                self.assertEqual(f.callbacks, [])
                f.speech._mark_done(); f.queued._mark_done()

    async def test_valid_cancel_without_owner_id_or_nonempty_stream_still_publishes(self):
        variants = ["missing_owner_id", "missing_stream_and_binding", "missing_both", "blank_stream"]
        for variant in variants:
            with self.subTest(variant=variant):
                f = self._fixture()
                event = self._event()
                if variant in {"missing_owner_id", "missing_both"}:
                    event["owner"] = {"kind": "remote_generation"}
                if variant in {"missing_stream_and_binding", "missing_both"}:
                    event.pop("streamId")
                    f.llm._stream_id_by_trace_id.clear()
                if variant == "blank_stream":
                    event["streamId"] = " "
                    event["owner"]["id"] = " "
                    f.llm._stream_id_by_trace_id["trace_1"] = " "
                self.assertTrue(await f.llm._relay_task_event_once(event))
                self.assertFalse(f.speech.interrupted)
                self.assertFalse(f.queued.interrupted)
                self.assertEqual(f.events, [("cancelling", False, True)])
                self.assertTrue(f.llm.is_task_output_suppressed("task_1"))
                self.assertEqual(f.callbacks, [])
                f.speech._mark_done(); f.queued._mark_done()

    async def test_stale_cancel_event_does_not_interrupt_or_install_barrier(self):
        f = self._fixture()
        await f.llm._relay_task_event_once(self._event("running", 5))
        self.assertFalse(await f.llm._relay_task_event_once(self._event("cancelling", 4)))
        self.assertFalse(f.speech.interrupted)
        self.assertFalse(f.llm.is_task_output_suppressed("task_1"))

    async def test_superseded_presentation_cannot_interrupt_newly_queued_reply(self):
        f = self._fixture()
        f.llm._presentation_coordinator.begin_stable(source_event_id="new_source",
                                                    presentation_ref="new_trace")
        await f.llm._relay_task_event_once(self._event())
        self.assertFalse(f.speech.interrupted)
        self.assertTrue(f.llm.is_task_output_suppressed("task_1"))
        self.assertEqual(f.callbacks, [])

    async def test_missing_task_or_stream_binding_blocks_callback_but_retains_suppression(self):
        for binding in ["_task_id_by_trace_id", "_stream_id_by_trace_id"]:
            with self.subTest(binding=binding):
                f = self._fixture()
                getattr(f.llm, binding).clear()
                await f.llm._relay_task_event_once(self._event())
                self.assertFalse(f.speech.interrupted)
                self.assertTrue(f.llm.is_task_output_suppressed("task_1"))
                self.assertEqual(f.callbacks, [])
                f.speech._mark_done(); f.queued._mark_done()

    async def test_listen_only_already_interrupted_playout_is_not_interrupted_again(self):
        from unittest.mock import Mock
        import worker
        f = self._fixture()
        worker._apply_authoritative_call_mode_to_speech_planes(
            "listen_only", ambient_ingress=SimpleNamespace(set_mode=Mock()),
            followup_scheduler=f.scheduler, session=f.session)
        self.assertTrue(f.speech.interrupted)
        await f.llm._relay_task_event_once(self._event())
        self.assertEqual(f.callbacks, [])
        self.assertTrue(f.llm.is_task_output_suppressed("task_1"))
        f.scheduler.cancel_pending.assert_not_called()

    async def test_ended_or_completed_handle_does_not_touch_closed_native_session(self):
        f = self._fixture()
        f.speech._mark_done()
        f.session._activity = None
        with self.assertNoLogs("voice-gateway", level="WARNING"):
            await f.llm._relay_task_event_once(self._event())
        self.assertEqual(f.callbacks, [])
        self.assertTrue(f.llm.is_task_output_suppressed("task_1"))

    async def test_healthy_task_event_does_not_add_suppression_lookup_or_network(self):
        from unittest.mock import Mock
        f = self._fixture()
        f.llm.set_task_event_handler(None)
        f.llm.is_task_output_suppressed = Mock(side_effect=AssertionError("extra healthy lookup"))
        with patch("librechat_llm.aiohttp.ClientSession") as no_network:
            self.assertTrue(await f.llm._relay_task_event_once(self._event("running")))
        f.llm.is_task_output_suppressed.assert_not_called()
        no_network.assert_not_called()
        self.assertFalse(f.speech.interrupted)

    async def _captured_followup_gate(self, *, detached=False):
        event = _voice_task_event("followup_parent", 1, streamId="stream_voice_1",
                                  owner={"kind": "generation_job", "id": "stream_voice_1"})
        final = {"final": True, "responseMessage": {
            "messageId": "followup_anchor", "content": [{"type": "text", "text": "Ready."}],
        }}
        transport = _FakeStreamingSseSession([
            {"event": "voice_task_event", "voiceTaskEvent": event}, final])
        followups = []
        llm = LibreChatLLM(origin="http://librechat.test",
                          auth=LibreChatAuth(call_session_id="call_1", call_secret="synthetic"),
                          followup_handler=lambda *args, **kwargs: followups.append((args, kwargs)))
        with patch("librechat_llm.aiohttp.ClientSession", return_value=transport):
            if detached:
                await llm._continue_task_stream(
                    stream_id="stream_voice_1", task_id="task_1", headers={},
                    request_id="trace_followup", pending_insights=[], saw_cortex_event=True,
                    saw_glasshive_tool_call=False, cortex_message_id="",
                    hop_trace=VoiceHopTrace(correlation_id="trace_followup", call_session_id="call_1"))
            else:
                stream = llm.chat(chat_ctx=ChatContext(items=[
                    ChatMessage(role="user", content=["Continue."])]))
                async with stream:
                    async for _ in stream:
                        pass
        self.assertEqual(len(followups), 1)
        return llm, followups[0][1]["presentation_is_current"]

    async def test_scheduled_main_followup_predicate_tracks_later_task_stop(self):
        llm, current = await self._captured_followup_gate()
        self.assertTrue(current())
        await llm._relay_task_event_once({**self._event(), "streamId": "stream_voice_1",
                                        "owner": {"kind": "generation_job", "id": "stream_voice_1"}})
        self.assertFalse(current())

    async def test_detached_main_followup_predicate_tracks_later_task_stop(self):
        llm, current = await self._captured_followup_gate(detached=True)
        self.assertTrue(callable(current))
        self.assertTrue(current())
        await llm._relay_task_event_once({**self._event(), "streamId": "stream_voice_1",
                                        "owner": {"kind": "generation_job", "id": "stream_voice_1"}})
        self.assertFalse(current())

    async def test_unrelated_task_stop_keeps_existing_main_followup_predicate_true(self):
        llm, current = await self._captured_followup_gate()
        await llm._relay_task_event_once({**self._event(), "taskId": "another_task"})
        self.assertTrue(current())
# === VIVENTIUM END ===


class TestCompletedGenerationPlayoutStop(unittest.IsolatedAsyncioTestCase):
    _fixture = TestExternalTaskCancelPlayout._fixture
    _event = staticmethod(TestExternalTaskCancelPlayout._event)
    def _playing_fixture(self):
        f = self._fixture()
        presentation = f.llm._presentation_by_trace_id["trace_1"]
        presentation.presentation_ref = f.speech.id
        presentation.playout_active = True
        presentation.audio_started_at_ms = 1000
        return f

    def _completed_stop(self, sequence=2, **changes):
        return {**self._event("completed", sequence,
            presentation={"ref": "main_speech", "state": "stop_requested", "startedAtMs": 1000}),
            **changes}

    async def test_completed_stop_interrupts_only_exact_active_handle_and_preserves_job_state(self):
        f = self._playing_fixture()
        with patch("librechat_llm.aiohttp.ClientSession") as no_network:
            self.assertTrue(await f.llm._relay_task_event_once(self._completed_stop()))
        no_network.assert_not_called()
        self.assertTrue(f.speech.interrupted)
        self.assertFalse(f.queued.interrupted)
        self.assertFalse(f.llm.is_task_output_suppressed("task_1"))
        self.assertEqual(f.callbacks, [])
        self.assertEqual(f.events, [("completed", True, False)])
        f.scheduler.cancel_pending.assert_not_called()

    async def test_new_generation_does_not_hide_still_active_old_speech_from_its_exact_stop(self):
        f = self._playing_fixture()
        f.llm._current_trace_id = "new_generation"
        f.llm._presentation_coordinator.begin_stable(
            source_event_id="source_new", presentation_ref="new_generation")
        await f.llm._relay_task_event_once(self._completed_stop())
        self.assertTrue(f.speech.interrupted)
        self.assertFalse(f.queued.interrupted)

    async def test_stale_ref_inactive_or_other_owner_cannot_stop_completed_speech(self):
        changes = [
            {"presentation": {"ref": "old_speech", "state": "stop_requested", "startedAtMs": 1000}},
            {"presentation": {"ref": "main_speech", "state": "speaking", "startedAtMs": 1000}},
            {"presentation": {"ref": "main_speech", "state": "stop_requested", "startedAtMs": True}},
            {"owner": {"kind": "glasshive_run", "id": "stream_1"}},
            {"streamId": "other_stream"}, {"taskId": "other_task"},
            {"callSessionId": "other_call"},
        ]
        for change in changes:
            with self.subTest(change=change):
                f = self._playing_fixture()
                await f.llm._relay_task_event_once(self._completed_stop(**change))
                self.assertFalse(f.speech.interrupted)
                self.assertFalse(f.queued.interrupted)
        f = self._playing_fixture()
        f.llm._presentation_by_trace_id["trace_1"].playout_active = False
        await f.llm._relay_task_event_once(self._completed_stop())
        self.assertFalse(f.speech.interrupted)

    async def test_direct_completed_stop_bypasses_callwide_cancel_callback_and_task_barrier(self):
        f = self._playing_fixture()
        transport = _FakeClosedStreamSession()
        result = {"version": 1, "outcome": "playout_stop_requested", "event": self._completed_stop()}
        transport.post = lambda *args, **kwargs: _FakeJsonResponse(result)
        with patch("librechat_llm.aiohttp.ClientSession", return_value=transport):
            self.assertEqual(await f.llm.cancel_task("task_1"), result)
            self.assertEqual(await f.llm.cancel_task("task_1"), result)
        self.assertTrue(f.speech.interrupted)
        self.assertFalse(f.queued.interrupted)
        self.assertFalse(f.llm.is_task_output_suppressed("task_1"))
        self.assertEqual(f.callbacks, [])
        self.assertNotIn("task_1", f.llm._task_cancel_results)
        f.scheduler.cancel_pending.assert_not_called()

    async def test_stream_then_direct_completed_stop_remains_idempotent_without_global_cancel(self):
        f = self._playing_fixture()
        event = self._completed_stop()
        await f.llm._relay_task_event_once(event)
        interrupt_future = f.speech._interrupt_fut
        transport = _FakeClosedStreamSession()
        transport.post = lambda *args, **kwargs: _FakeJsonResponse(
            {"version": 1, "outcome": "playout_stop_requested", "event": event})
        with patch("librechat_llm.aiohttp.ClientSession", return_value=transport):
            await f.llm.cancel_task("task_1")
        self.assertIs(f.speech._interrupt_fut, interrupt_future)
        self.assertFalse(f.queued.interrupted)
        self.assertEqual(f.callbacks, [])

    async def test_malformed_completed_stop_response_is_not_cached_or_converted_to_generation_cancel(self):
        f = self._playing_fixture()
        transport = _FakeClosedStreamSession()
        transport.post = lambda *args, **kwargs: _FakeJsonResponse(
            {"version": 1, "outcome": "playout_stop_requested", "event": self._event("completed")})
        with patch("librechat_llm.aiohttp.ClientSession", return_value=transport):
            with self.assertRaises(RuntimeError):
                await f.llm.cancel_task("task_1")
        self.assertFalse(f.speech.interrupted)
        self.assertFalse(f.llm.is_task_output_suppressed("task_1"))
        self.assertEqual(f.callbacks, [])
        self.assertNotIn("task_1", f.llm._task_cancel_results)

    async def test_native_started_projection_uses_exact_handle_without_await_or_network(self):
        f = self._fixture()
        with patch.object(f.llm, "record_completed_trace_stage", return_value=True) as publish:
            with patch("librechat_llm.aiohttp.ClientSession") as no_network:
                self.assertTrue(f.llm.record_speech_started(f.speech, 1000.75))
                self.assertFalse(f.llm.record_speech_started(f.speech, 2000))
                self.assertFalse(f.llm.record_speech_started(f.queued, 3000))
        no_network.assert_not_called()
        publish.assert_called_once_with("trace_1", "audio.started")
        presentation = f.llm._presentation_by_trace_id["trace_1"]
        self.assertTrue(presentation.playout_active)
        self.assertEqual(presentation.audio_started_at_ms, 1000)

    async def test_started_trace_reuses_existing_exact_core_and_worker_binding(self):
        f = self._playing_fixture()
        f.llm._auth = LibreChatAuth(call_session_id="call_1", call_secret="synthetic",
                                   job_id="job_1", worker_id="worker_1")
        presentation = f.llm._presentation_by_trace_id["trace_1"]
        presentation.logical_turn_id = "logical_1"
        presentation.revision = 1
        transport = _FakeClosedStreamSession()
        with patch("librechat_llm.aiohttp.ClientSession", return_value=transport):
            self.assertTrue(await f.llm._post_production_trace("trace_1", "audio.started"))
        body = transport.post_calls[0][2]["json"]
        self.assertEqual(body, {"version": 1, "callSessionId": "call_1", "turnId": "logical_1",
            "streamId": "stream_1", "taskId": "task_1", "presentationRef": "main_speech",
            "stage": "audio.started", "startedAtMs": 1000})


class TestExactFollowupProductionTrace(unittest.IsolatedAsyncioTestCase):
    async def test_worker_trace_uses_canonical_worker_turn_and_parent_task_not_main_clock(self):
        llm = LibreChatLLM(origin="http://example.test", auth=LibreChatAuth(call_session_id="call_1",
            call_secret="synthetic", job_id="job_1", worker_id="worker_1"))
        delivery = {"deliveryId": "delivery_1", "claimId": "claim_1", "dispatchPermit": {"permitId": "permit_1"},
            "workerCompletionPresentation": {"callSessionId": "call_1", "presentationRef": "worker_ref",
                                              "turnId": "worker_turn"}}
        transport = _FakeDeliveryAckSession()
        with patch("librechat_llm.aiohttp.ClientSession", return_value=transport):
            self.assertTrue(await llm.record_followup_presentation("parent_stream", "worker_ref", "audio.started",
                started_at_ms=2000, task_ref={"taskId": "parent_task", "streamId": "parent_stream"},
                worker_delivery=delivery))
        self.assertEqual(transport.post_calls[0][2]["json"], {"version": 1, "callSessionId": "call_1",
            "turnId": "worker_turn", "streamId": "parent_stream", "taskId": "parent_task",
            "presentationRef": "worker_ref", "stage": "audio.started", "startedAtMs": 2000,
            "workerDelivery": {"deliveryId": "delivery_1", "claimId": "claim_1",
                               "dispatchPermit": {"permitId": "permit_1"}}})

    async def test_worker_trace_missing_or_foreign_identity_abstains_before_http(self):
        llm = LibreChatLLM(origin="http://example.test", auth=LibreChatAuth(call_session_id="call_1",
            call_secret="synthetic", job_id="job_1", worker_id="worker_1"))
        good = {"deliveryId": "delivery_1", "claimId": "claim_1", "dispatchPermit": {},
            "workerCompletionPresentation": {"callSessionId": "call_1", "presentationRef": "worker_ref",
                                              "turnId": "worker_turn"}}
        for proof in ([], {}, {**good, "deliveryId": None}, {**good, "claimId": None},
            {**good, "dispatchPermit": None}, {**good, "workerCompletionPresentation": {
                **good["workerCompletionPresentation"], "callSessionId": "foreign"}}):
            with self.subTest(proof=proof), patch("librechat_llm.aiohttp.ClientSession") as no_http:
                self.assertFalse(await llm.record_followup_presentation("parent", "worker_ref", "audio.started",
                    started_at_ms=2000, task_ref={"taskId": "parent_task", "streamId": "parent_stream"},
                    worker_delivery=proof))
                no_http.assert_not_called()

    async def test_cortex_trace_uses_its_own_native_start_clock(self):
        f = TestCompletedGenerationPlayoutStop()._playing_fixture()
        f.llm._auth = LibreChatAuth(call_session_id="call_1", call_secret="synthetic", job_id="job_1", worker_id="worker_1")
        p = f.llm._presentation_by_trace_id["trace_1"]
        p.logical_turn_id = "main_turn"; p.revision = 1
        transport = _FakeDeliveryAckSession()
        with patch("librechat_llm.aiohttp.ClientSession", return_value=transport):
            self.assertTrue(await f.llm.record_followup_presentation("trace_1", "cortex_ref", "audio.started",
                started_at_ms=3000, task_ref={"taskId": "task_1", "streamId": "stream_1"}))
        body = transport.post_calls[0][2]["json"]
        self.assertEqual(body["startedAtMs"], 3000)
        self.assertEqual(body["presentationRef"], "cortex_ref")
        self.assertEqual(body["turnId"], "main_turn")
        self.assertNotIn("workerDelivery", body)


class TestNeutralWorkerProductionTrace(unittest.IsolatedAsyncioTestCase):
    async def test_neutral_callback_uses_its_existing_delivery_reference_and_stored_request(self):
        llm = LibreChatLLM(origin="http://example.test", auth=LibreChatAuth(call_session_id="call_1",
            call_secret="synthetic", job_id="job_1", worker_id="worker_1"))
        delivery = {"deliveryId": "neutral_delivery", "claimId": "claim_1", "dispatchPermit": {"permitId": "permit_1"},
                    "voiceCallSessionId": "call_1", "voiceRequestId": "stored_request"}
        transport = _FakeDeliveryAckSession()
        with patch("librechat_llm.aiohttp.ClientSession", return_value=transport):
            self.assertTrue(await llm.record_followup_presentation("parent", "neutral_delivery", "audio.started",
                started_at_ms=2000, task_ref={"taskId": "parent_task", "streamId": "parent_stream"},
                worker_delivery=delivery))
        body = transport.post_calls[0][2]["json"]
        self.assertEqual(body["turnId"], "stored_request")
        self.assertEqual(body["presentationRef"], "neutral_delivery")
        self.assertNotIn("workerCompletionPresentation", body)

class TestPendingCoreAdmission(unittest.TestCase):
    """Exercise the actual HTTP cancellation race against a private Core fixture."""

    async def _pending_post(self, *, status=200, timeout=False, closing=False,
                            handle_done=True, audible=False, cancel_successor=False,
                            missing_identity=False, changed_call=False, closing_waiter=False,
                            malformed=False, ack_accepted=True, third_source=False,
                            metadata=False, middle_receipt_failure=False):
        from aiohttp import web
        started, release, second_started = asyncio.Event(), asyncio.Event(), asyncio.Event()
        order, requests, sessions = [], [], []
        previous_receipts = []

        async def chat(request):
            body = await request.json()
            requests.append(body)
            revision = len(requests)
            order.append(f"post-{revision}")
            self.assertEqual(body["sourceEventId"],
                all_streams[revision - 1]._presentation.source_event_id)
            if revision > 1:
                previous = all_streams[revision - 2]._presentation
                previous_receipts.append({
                    "sourceEventId": previous.source_event_id,
                    "logicalTurnId": previous.logical_turn_id,
                    "revision": previous.revision,
                    "done": previous.admission_task.done(),
                })
            if revision == 1:
                started.set()
                await release.wait()
            else:
                second_started.set()
            order.append(f"receipt-{revision}")
            if revision == 2 and middle_receipt_failure:
                # The original source reached Core, but no admitted identity is returned.
                return web.json_response({"code": "voice_turn_authority_unavailable"}, status=503)
            payload = {"streamId": body["streamId"], "taskId": f"task_{revision}",
                       "logical_turn_id": "logical-1", "revision": revision}
            if revision == 1 and missing_identity:
                payload.pop("logical_turn_id")
            if revision == 1 and malformed:
                return web.Response(text="{", content_type="application/json")
            return web.json_response(payload, status=status if revision == 1 else 200)

        async def stream(request):
            event = {"final": True, "responseMessage": {"messageId": "answer-2",
                "content": [{"type": "text", "text": "Next."}]}}
            return web.Response(text="data: " + json.dumps(event) + "\n\n",
                                content_type="text/event-stream")

        app = web.Application()
        app.router.add_post("/api/viventium/voice/chat", chat)
        app.router.add_get("/api/viventium/voice/stream/{stream_id}", stream)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        origin = "http://127.0.0.1:" + str(site._server.sockets[0].getsockname()[1])
        original_session = aiohttp.ClientSession

        def tracked_session(*args, **kwargs):
            session = original_session(*args, **kwargs)
            sessions.append(session)
            return session

        llm = LibreChatLLM(origin=origin,
            auth=LibreChatAuth(call_session_id="call_1", call_secret="synthetic"),
            timeout_s=0.075 if timeout else 1.0)
        admission_errors = []
        llm.on("error", admission_errors.append)
        handle = _CompletableSpeechHandle("first-speech")
        llm.register_speech_handle(handle)
        llm._start_task_continuation = unittest.mock.Mock()
        llm.schedule_trace_terminal = unittest.mock.Mock()
        llm.record_completed_trace_stage = unittest.mock.Mock(return_value=True)

        async def acknowledge(**kwargs):
            order.append("ack")
            return ack_accepted

        llm.ack_delivery = AsyncMock(side_effect=acknowledge)
        first, second = None, None
        chunks = []
        all_streams = []
        expected_courier = []

        def context(source_id, text):
            message = ChatMessage(id=source_id, role="user", content=[text])
            if metadata:
                tracker = SpeakerSegmentTracker(call_session_id="call_1",
                    participant_identity="owner-participant", participant_name="Owner",
                    track_sid="TR_owner_mic", owner_signed=True)
                tracker.ingest(transcript=text, is_final=True, provider_speaker_id="A",
                    created_at=100.0 + len(expected_courier), start_time=10.0, end_time=11.0)
                original = attach_speaker_context_to_message(tracker, message)
                expected_courier.append({"text": text,
                    "sourceEventId": f"voice:call_1:item:{source_id}",
                    **{key: original[key] for key in ("speakerSegments", "speakerSegmentRevisions",
                       "speakerLabel", "ownerParticipantIdentity", "ownerTrackSid")}})
            return ChatContext(items=[message])
        try:
            with patch("librechat_llm.aiohttp.ClientSession", side_effect=tracked_session):
                first = llm.chat(chat_ctx=context("first-source", "First."))
                all_streams.append(first)
                await asyncio.wait_for(started.wait(), 1)
                if audible:
                    handle.mark_audible_playout()
                if handle_done:
                    handle.complete(interrupted=True)
                    await asyncio.sleep(0)
                # Core has not returned any stream/task/logical-turn identity yet.
                self.assertEqual(first._presentation.logical_turn_id, "")
                self.assertIsNone(first._presentation.interrupted_binding)
                await asyncio.wait_for(first.aclose(), 0.25)
                if changed_call:
                    llm._auth = LibreChatAuth(call_session_id="call_2", call_secret="synthetic")
                if not closing:
                    if cancel_successor:
                        middle_handle = _CompletableSpeechHandle("second-speech")
                        llm.register_speech_handle(middle_handle)
                    second = llm.chat(chat_ctx=context("second-source", "Second: β\nline 2  \nnext." if metadata else "Second."))
                    all_streams.append(second)
                    await asyncio.sleep(0.02)
                    if cancel_successor:
                        middle_handle.complete(interrupted=True)
                        await asyncio.wait_for(second.aclose(), 0.25)
                        if third_source:
                            second = llm.chat(chat_ctx=context("third-source", "Third: correction." if metadata else "Third."))
                            all_streams.append(second)
                            await asyncio.sleep(0.02)
                    if closing_waiter:
                        await asyncio.wait_for(llm.close_background_continuations(), 0.25)
                else:
                    await asyncio.wait_for(llm.close_background_continuations(), 0.25)
                # No successor POST may start while the first real receipt is held.
                self.assertEqual([body["sourceEventId"] for body in requests],
                    ["voice:call_1:item:first-source"])
                if not timeout:
                    release.set()
                consumer_error = None
                if second is not None and (not cancel_successor or third_source):
                    try:
                        async with second:
                            async for chunk in second:
                                chunks.append(chunk)
                    except TimeoutError:
                        if not timeout:
                            raise
                        # Foreground failure is not an admission receipt. The
                        # retained task below must prove the actual outcome.
                        consumer_error = "timeout"
                if consumer_error is None and any(event.recoverable for event in admission_errors):
                    consumer_error = "deferred"
                tasks = [getattr(item._presentation, "admission_task", None) for item in all_streams]
                if not closing:
                    await asyncio.gather(*(item for item in tasks if item is not None), return_exceptions=True)
                # Timeout is exercised by the real aiohttp ClientTimeout.
                release.set()
                await llm.close_background_continuations()
                self.assertTrue(all(session.closed for session in sessions))
        finally:
            release.set()
            if first is not None:
                await first.aclose()
            if second is not None:
                await second.aclose()
            await llm.close_background_continuations()
            await runner.cleanup()
        llm._test_expected_courier = expected_courier
        llm._test_previous_admission_receipts = previous_receipts
        llm._test_admission_consumer_error = consumer_error
        return llm, first, second, order, requests, chunks

    def test_pending_post_interruption_retains_exact_receipt_before_successor(self):
        llm, first, _second, order, requests, chunks = asyncio.run(self._pending_post())
        self.assertEqual([item for item in order if item != "ack"],
            ["post-1", "receipt-1", "post-2", "receipt-2"])
        self.assertEqual(first._presentation.interrupted_binding,
            ("call_1", "logical-1", 1, "first-speech", first._request_id, "task_1"))
        self.assertEqual(llm.ack_delivery.await_args.kwargs,
            {"logical_turn_id": "logical-1", "revision": 1, "state": "partial_removed",
             "presentation_ref": "first-speech"})
        self.assertEqual(len(requests), 2)
        llm.ack_delivery.assert_awaited_once()
        self.assertEqual(llm._test_previous_admission_receipts, [{
            "sourceEventId": "voice:call_1:item:first-source",
            "logicalTurnId": "logical-1", "revision": 1, "done": True,
        }])
        self.assertTrue(chunks)
        llm._start_task_continuation.assert_called_once()

    def test_pending_post_403_creates_no_ack_or_interrupted_identity(self):
        llm, first, _second, _order, requests, _chunks = asyncio.run(self._pending_post(status=403))
        self.assertEqual(first._presentation.logical_turn_id, "")
        self.assertIsNone(first._presentation.interrupted_binding)
        llm.ack_delivery.assert_not_awaited()
        llm._start_task_continuation.assert_not_called()
        self.assertEqual(len(requests), 2)

    def test_pending_post_timeout_is_bounded_and_creates_no_ack(self):
        llm, first, second, _order, requests, _chunks = asyncio.run(self._pending_post(timeout=True))
        self.assertEqual(first._presentation.logical_turn_id, "")
        llm.ack_delivery.assert_not_awaited()
        self.assertEqual([item["text"] for item in requests], ["First.", "Second."])
        self.assertEqual(second._presentation.logical_turn_id, "logical-1")
        self.assertEqual(second._presentation.revision, 2)
        if llm._test_admission_consumer_error in {"timeout", "deferred"}:
            llm._start_task_continuation.assert_called_once()
            self.assertEqual(llm._start_task_continuation.call_args.kwargs["task_id"], "task_2")
        else:
            llm._start_task_continuation.assert_not_called()

    def test_pending_post_end_cancels_and_closes_its_owned_session(self):
        llm, first, _second, _order, requests, _chunks = asyncio.run(self._pending_post(closing=True))
        self.assertEqual(first._presentation.logical_turn_id, "")
        llm.ack_delivery.assert_not_awaited()
        llm._start_task_continuation.assert_not_called()
        self.assertEqual(len(requests), 1)

    def test_pending_post_end_drains_waiting_successor_without_dispatch_or_ack(self):
        llm, first, _second, _order, requests, chunks = asyncio.run(self._pending_post(closing_waiter=True))
        self.assertEqual(first._presentation.logical_turn_id, "")
        llm.ack_delivery.assert_not_awaited()
        llm._start_task_continuation.assert_not_called()
        self.assertEqual(len(requests), 1)
        self.assertEqual(chunks, [])

    def test_pending_post_successor_cancel_does_not_cancel_predecessor_receipt(self):
        llm, first, _second, order, requests, _chunks = asyncio.run(self._pending_post(cancel_successor=True))
        self.assertEqual(first._presentation.logical_turn_id, "logical-1")
        self.assertEqual([item for item in order if item != "ack"],
            ["post-1", "receipt-1", "post-2", "receipt-2"])
        self.assertEqual([item["text"] for item in requests], ["First.", "Second."])
        llm.ack_delivery.assert_awaited_once()

    def test_pending_post_third_source_couriers_each_input_after_prior_real_receipt(self):
        llm, first, _third, order, requests, chunks = asyncio.run(self._pending_post(
            cancel_successor=True, third_source=True))
        self.assertEqual([item for item in order if item != "ack"],
            ["post-1", "receipt-1", "post-2", "receipt-2", "post-3", "receipt-3"])
        self.assertEqual([item["text"] for item in requests], ["First.", "Second.", "Third."])
        self.assertEqual([item["sourceEventId"] for item in requests],
            ["voice:call_1:item:first-source", "voice:call_1:item:second-source", "voice:call_1:item:third-source"])
        self.assertEqual(llm.ack_delivery.await_count, 2)
        self.assertEqual(llm.ack_delivery.await_args_list[0].kwargs,
            {"logical_turn_id": "logical-1", "revision": 1, "state": "partial_removed", "presentation_ref": "first-speech"})
        self.assertEqual(llm.ack_delivery.await_args_list[1].kwargs,
            {"logical_turn_id": "logical-1", "revision": 2, "state": "partial_removed", "presentation_ref": "second-speech"})
        self.assertEqual(llm._test_previous_admission_receipts, [
            {"sourceEventId": "voice:call_1:item:first-source",
             "logicalTurnId": "logical-1", "revision": 1, "done": True},
            {"sourceEventId": "voice:call_1:item:second-source",
             "logicalTurnId": "logical-1", "revision": 2, "done": True},
        ])
        self.assertTrue(chunks)

    def test_pending_post_three_sources_preserve_exact_prose_and_speaker_metadata(self):
        llm, _first, _third, order, requests, chunks = asyncio.run(self._pending_post(
            cancel_successor=True, third_source=True, metadata=True))
        self.assertEqual([item for item in order if item.startswith("post-")],
            ["post-1", "post-2", "post-3"])
        self.assertLess(order.index("receipt-1"), order.index("post-2"))
        self.assertLess(order.index("receipt-2"), order.index("post-3"))
        self.assertEqual(len(requests), 3)
        for actual, expected in zip(requests, llm._test_expected_courier):
            self.assertEqual({key: actual[key] for key in expected}, expected)
        self.assertTrue(chunks)

    def test_pending_post_middle_receipt_failure_does_not_fabricate_its_removal(self):
        llm, _first, _third, order, requests, chunks = asyncio.run(self._pending_post(
            cancel_successor=True, third_source=True, middle_receipt_failure=True))
        self.assertEqual([item["text"] for item in requests], ["First.", "Second.", "Third."])
        self.assertEqual([item for item in order if item.startswith("post-")],
            ["post-1", "post-2", "post-3"])
        self.assertLess(order.index("receipt-1"), order.index("post-2"))
        self.assertLess(order.index("receipt-2"), order.index("post-3"))
        llm.ack_delivery.assert_awaited_once()
        self.assertEqual(llm.ack_delivery.await_args.kwargs["revision"], 1)
        self.assertTrue(chunks)

    def test_pending_post_live_handle_is_never_zero_presented_acknowledged(self):
        llm, first, _second, order, _requests, _chunks = asyncio.run(self._pending_post(handle_done=False))
        self.assertEqual(first._presentation.logical_turn_id, "logical-1")
        llm.ack_delivery.assert_not_awaited()
        self.assertEqual(order, ["post-1", "receipt-1", "post-2", "receipt-2"])

    def test_pending_post_audible_handle_is_never_zero_presented_acknowledged(self):
        llm, first, _second, order, _requests, _chunks = asyncio.run(self._pending_post(audible=True))
        self.assertEqual(first._presentation.logical_turn_id, "logical-1")
        llm.ack_delivery.assert_not_awaited()
        self.assertEqual(order, ["post-1", "receipt-1", "post-2", "receipt-2"])

    def test_pending_post_missing_core_identity_cannot_create_removal_ack(self):
        llm, first, _second, _order, _requests, _chunks = asyncio.run(self._pending_post(missing_identity=True))
        self.assertEqual(first._presentation.logical_turn_id, "")
        self.assertIsNone(first._presentation.interrupted_binding)
        llm.ack_delivery.assert_not_awaited()

    def test_pending_post_malformed_receipt_cannot_create_identity_or_ack(self):
        llm, first, _second, _order, _requests, _chunks = asyncio.run(self._pending_post(malformed=True))
        self.assertEqual(first._presentation.logical_turn_id, "")
        self.assertIsNone(first._presentation.interrupted_binding)
        llm.ack_delivery.assert_not_awaited()
        llm._start_task_continuation.assert_not_called()

    def test_pending_post_denied_removal_ack_is_not_recorded_as_accepted(self):
        llm, first, _second, order, _requests, _chunks = asyncio.run(self._pending_post(ack_accepted=False))
        self.assertEqual([item for item in order if item != "ack"],
            ["post-1", "receipt-1", "post-2", "receipt-2"])
        llm.ack_delivery.assert_awaited_once()
        self.assertNotEqual(first._presentation.delivery_state, "partial_removed")
        self.assertIsNone(first._presentation.delivery_ack_identity)

    def test_pending_post_receipt_does_not_cross_call_ownership(self):
        llm, first, _second, _order, _requests, _chunks = asyncio.run(self._pending_post(changed_call=True))
        # A late old-call receipt is not attached to the newly current owner.
        self.assertEqual(first._presentation.logical_turn_id, "")
        self.assertIsNone(first._presentation.interrupted_binding)
        llm.ack_delivery.assert_not_awaited()
        llm._start_task_continuation.assert_not_called()

    def test_delayed_prior_ack_rechecks_exact_binding_before_removal(self):
        async def run():
            llm = LibreChatLLM(origin="http://librechat.test",
                auth=LibreChatAuth(call_session_id="call_1", call_secret="synthetic"))
            llm.ack_delivery = AsyncMock(return_value=True)
            first = llm._presentation_coordinator.begin_stable(
                source_event_id="source-1", presentation_ref="speech-1")
            llm.register_trace(VoiceHopTrace(correlation_id=first.trace_id, call_session_id="call_1"))
            llm._presentation_coordinator.bind_core_context(first, {"logical_turn_id": "logical-1", "revision": 1})
            llm.bind_trace_core_context(first.trace_id, stream_id="stream-1", task_id="task-1", presentation=first)
            first.interrupted_binding = ("call_1", "logical-1", 1, "speech-1", "stream-1", "task-1")
            started, release = asyncio.Event(), asyncio.Event()

            async def prior_ack():
                started.set()
                await release.wait()
                return False

            first.delivery_ack_task = asyncio.create_task(prior_ack())
            second = llm._presentation_coordinator.begin_stable(
                source_event_id="source-2", presentation_ref="speech-2")
            removing = asyncio.create_task(llm._ack_unpresented_superseded_presentation(first, second))
            await started.wait()
            await asyncio.sleep(0)
            llm._task_id_by_trace_id[first.trace_id] = "foreign-task"
            release.set()
            self.assertFalse(await removing)
            llm.ack_delivery.assert_not_awaited()
            await llm.close_background_continuations()

        asyncio.run(run())



class TestOrderedAdmissionDeadlineRecovery(unittest.IsolatedAsyncioTestCase):
    """The consumer deadline must not erase an ordered source still waiting for Core."""

    async def _held_prior(self, *, end=False, changed_call=False, four_pending=False,
                          middle_failure=False):
        from aiohttp import web
        started, release = asyncio.Event(), asyncio.Event()
        requests, sessions, order, streams, expected = [], [], [], [], []

        async def chat(request):
            body = await request.json()
            requests.append(body)
            number = len(requests)
            order.append(f"post-{number}")
            if number == 1:
                started.set()
                await release.wait()
            order.append(f"receipt-{number}")
            if middle_failure and number == 2:
                return web.json_response({"code":"voice_turn_authority_unavailable"},status=503)
            return web.json_response({"streamId": body["streamId"], "taskId": f"task-{number}",
                "logical_turn_id": "logical-held", "revision": number})

        async def stream(request):
            return web.Response(text='data: {"final":true}\n\n', content_type="text/event-stream")

        app = web.Application()
        app.router.add_post('/api/viventium/voice/chat', chat)
        app.router.add_get('/api/viventium/voice/stream/{stream_id}', stream)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '127.0.0.1', 0)
        await site.start()
        origin = 'http://127.0.0.1:' + str(site._server.sockets[0].getsockname()[1])
        real_session = aiohttp.ClientSession

        def tracking_session(*args, **kwargs):
            result = real_session(*args, **kwargs)
            sessions.append(result)
            return result

        llm = LibreChatLLM(origin=origin, auth=LibreChatAuth(call_session_id='held-call',
            call_secret='synthetic'), timeout_s=0.06)
        from livekit.agents import AgentSession
        sdk_session = AgentSession()
        sdk_errors = []
        llm.on('error', sdk_errors.append)
        llm.on('error', sdk_session._on_error)
        llm._start_task_continuation = unittest.mock.Mock()
        llm.schedule_trace_terminal = unittest.mock.Mock()
        llm.record_completed_trace_stage = unittest.mock.Mock(return_value=True)

        async def acknowledge(**kwargs):
            order.append('ack-' + str(kwargs['revision']))
            return True

        llm.ack_delivery = AsyncMock(side_effect=acknowledge)

        def context(number, text):
            message = ChatMessage(id=f'held-{number}', role='user', content=[text])
            tracker = SpeakerSegmentTracker(call_session_id='held-call',
                participant_identity='held-owner', participant_name='Owner',
                track_sid='TR_held', owner_signed=True)
            tracker.ingest(transcript=text, is_final=True, provider_speaker_id='speaker-A',
                created_at=100.0+number, start_time=float(number), end_time=float(number)+0.5)
            original = attach_speaker_context_to_message(tracker, message)
            expected.append({'text': text, 'sourceEventId': f'voice:held-call:item:held-{number}',
                **{key: original[key] for key in ('speakerSegments', 'speakerSegmentRevisions',
                    'speakerLabel', 'ownerParticipantIdentity', 'ownerTrackSid')}})
            return ChatContext(items=[message])

        try:
            with patch('librechat_llm.aiohttp.ClientSession', side_effect=tracking_session):
                first = llm.chat(chat_ctx=context(1, 'Alpha: Ω\nline 2  \nkeep.'))
                # A held older attempt can have a longer remaining transport budget.
                # This is a local control, not a product configuration mutation.
                first._timeout_s = 0.75
                streams.append(first)
                await asyncio.wait_for(started.wait(), 0.5)
                await first.aclose()
                inputs = [(2, 'Beta: β\nsecond correction.'),
                          (3, 'Gamma: γ\nlast correction.')]
                if four_pending:
                    inputs.extend([(4, 'Delta: δ\nkeep source four.'),
                                   (5, 'Epsilon: ε\nkeep source five.')])
                for number, text in inputs:
                    current = llm.chat(chat_ctx=context(number, text))
                    streams.append(current)
                    async with current:
                        chunks = [item async for item in current]
                    self.assertEqual(chunks, [])
                self._test_deadline_trace = {"order": list(order), "requests": list(requests),
                    "foreground_pending_errors": len(sdk_errors),
                    "admission_done": [item._presentation.admission_task.done() for item in streams]}
                self.assertEqual(len(sdk_errors), len(inputs))
                self.assertTrue(all(event.recoverable for event in sdk_errors))
                self.assertTrue(all(isinstance(event.error, TimeoutError) for event in sdk_errors))
                self.assertEqual(sdk_session._llm_error_counts, 0)
                self.assertIsNone(sdk_session._closing_task)
                # A timeout is neither a receipt nor permission to overtake A.
                self.assertEqual(len(requests), 1)
                self.assertEqual(llm.ack_delivery.await_count, 0)
                self.assertTrue(all(item._presentation.logical_turn_id == '' for item in streams))
                if end:
                    await asyncio.wait_for(llm.close_background_continuations(), 0.3)
                elif changed_call:
                    llm._auth = LibreChatAuth(call_session_id='different-call', call_secret='synthetic')
                else:
                    self.assertTrue(all(not item._presentation.admission_task.done() for item in streams))
                release.set()
                await asyncio.wait_for(asyncio.gather(*(item._presentation.admission_task
                    for item in streams), return_exceptions=True), 0.5)
                if not end and not changed_call:
                    self.assertEqual(len(requests), len(streams))
                    for actual, original in zip(requests, expected):
                        self.assertEqual({key: actual[key] for key in original}, original)
                    self.assertEqual([entry for entry in order if not entry.startswith('ack-')],
                        [part for number in range(1,len(streams)+1)
                         for part in (f'post-{number}',f'receipt-{number}')])
                    for number, item in enumerate(streams, 1):
                        if middle_failure and number == 2:
                            self.assertEqual(item._presentation.logical_turn_id,'')
                            self.assertIsNone(item._presentation.interrupted_binding)
                            continue
                        self.assertEqual(item._presentation.logical_turn_id, 'logical-held')
                        self.assertEqual(item._presentation.revision, number)
                        self.assertEqual(item._presentation.interrupted_binding,
                            ('held-call', 'logical-held', number, item._presentation.presentation_ref,
                             item._request_id, f'task-{number}'))
                    missing = 1 if middle_failure else 0
                    self.assertEqual(llm._start_task_continuation.call_count, len(streams)-missing)
                    self.assertEqual(llm.ack_delivery.await_count, len(streams)-1-missing)
                    if middle_failure:
                        actual_errors=[event for event in sdk_errors if not event.recoverable]
                        self.assertEqual(len(actual_errors),1)
                        self.assertIsInstance(actual_errors[0].error,RuntimeError)
                        self.assertEqual(sdk_session._llm_error_counts,1)
                        self.assertIsNone(sdk_session._closing_task)
                else:
                    self.assertEqual(len(requests), 1)
                    llm.ack_delivery.assert_not_awaited()
                    llm._start_task_continuation.assert_not_called()
                await llm.close_background_continuations()
                self.assertTrue(all(session.closed for session in sessions))
                self.assertFalse(llm._background_continuations)
        finally:
            release.set()
            for item in streams:
                await item.aclose()
            await llm.close_background_continuations()
            await runner.cleanup()

    async def test_held_prior_ready_retains_timed_out_successors_and_real_receipts(self):
        await self._held_prior()

    async def test_end_drains_timed_out_successors_without_post_or_ack(self):
        await self._held_prior(end=True)

    async def test_call_change_does_not_dispatch_timed_out_successors_with_old_owner(self):
        await self._held_prior(changed_call=True)

    async def test_four_pending_deadlines_do_not_close_installed_sdk_or_cancel_sources(self):
        await self._held_prior(four_pending=True)

    async def test_deferred_source_actual_transport_failure_stays_nonrecoverable(self):
        await self._held_prior(middle_failure=True)


class TestReadyReceiptWhileRemovalStalls(unittest.IsolatedAsyncioTestCase):
    async def _ready_before_removal(self, *, removal_error=False):
        from aiohttp import web
        requests, sessions, order = [], [], []
        received, ack_started, ack_release = asyncio.Event(), asyncio.Event(), asyncio.Event()
        llm = None

        async def chat(request):
            body = await request.json()
            requests.append(body)
            number=len(requests)
            order.append(f'post-{number}')
            received.set()
            if number == 2:
                self.assertEqual(current._presentation.logical_turn_id,'real-successor')
                self.assertEqual(current._presentation.revision,2)
                self.assertTrue(current._presentation.admission_task.done())
                self.assertFalse(prior.delivery_ack_task.done())
            order.append(f'receipt-{number}')
            return web.json_response({'streamId': body['streamId'],
                'taskId': 'successor-task' if number == 1 else 'third-task',
                'logical_turn_id': 'real-successor' if number == 1 else 'real-third',
                'revision': number+1})

        async def stream(request):
            return web.Response(text='data: {"final":true,"responseMessage":{"content":[{"type":"text","text":"Ready."}]}}\n\n',
                content_type='text/event-stream')

        app = web.Application()
        app.router.add_post('/api/viventium/voice/chat', chat)
        app.router.add_get('/api/viventium/voice/stream/{stream_id}', stream)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '127.0.0.1', 0)
        await site.start()
        origin = 'http://127.0.0.1:' + str(site._server.sockets[0].getsockname()[1])
        real_session = aiohttp.ClientSession

        def track(*args, **kwargs):
            result = real_session(*args, **kwargs)
            sessions.append(result)
            return result

        llm = LibreChatLLM(origin=origin, auth=LibreChatAuth(call_session_id='ack-call',
            call_secret='synthetic'), timeout_s=0.2)
        llm._start_task_continuation = unittest.mock.Mock()
        llm.schedule_trace_terminal = unittest.mock.Mock()
        llm.record_completed_trace_stage = unittest.mock.Mock(return_value=True)
        prior = llm._presentation_coordinator.begin_stable(source_event_id='prior-source',
            presentation_ref='prior-presentation')
        llm.register_trace(VoiceHopTrace(correlation_id=prior.trace_id, call_session_id='ack-call'))
        llm._presentation_coordinator.bind_core_context(prior,
            {'logical_turn_id': 'real-prior', 'revision': 1})
        llm.bind_trace_core_context(prior.trace_id, stream_id='prior-stream', task_id='prior-task',
            presentation=prior)
        prior.interrupted_binding=('ack-call', 'real-prior', 1, 'prior-presentation',
            'prior-stream', 'prior-task')

        async def acknowledge(**kwargs):
            ack_started.set()
            await ack_release.wait()
            if removal_error:
                raise RuntimeError('Synthetic removal transport failure')
            return True

        llm.ack_delivery = AsyncMock(side_effect=acknowledge)
        current, third = None, None
        try:
            with patch('librechat_llm.aiohttp.ClientSession', side_effect=track):
                current = llm.chat(chat_ctx=ChatContext(items=[ChatMessage(id='successor-source',
                    role='user', content=['Original: Ω\nretain me.'])]))
                await asyncio.wait_for(asyncio.gather(received.wait(),ack_started.wait()),0.3)
                # Transport delivery must bind before this independent ACK resolves.
                for _ in range(15):
                    if current._presentation.logical_turn_id:
                        break
                    await asyncio.sleep(0.002)
                self.assertEqual(current._presentation.logical_turn_id,'real-successor')
                self.assertEqual(current._presentation.revision,2)
                self.assertEqual(llm._task_id_by_trace_id[current._request_id],'successor-task')
                self.assertEqual(llm._stream_id_by_trace_id[current._request_id],current._request_id)
                self.assertNotEqual(prior.delivery_state,'partial_removed')
                self.assertIsNone(prior.delivery_ack_identity)
                # B's own ready receipt admits C without waiting for A's ACK.
                async with current:
                    chunks=[item async for item in current]
                self.assertTrue(chunks)
                third=llm.chat(chat_ctx=ChatContext(items=[ChatMessage(id='third-source',
                    role='user',content=['Third: γ\noriginal correction.'])]))
                async with third:
                    third_chunks=[item async for item in third]
                self.assertTrue(third_chunks)
                self.assertEqual(third._presentation.logical_turn_id,'real-third')
                self.assertEqual(third._presentation.revision,3)
                self.assertEqual(order,['post-1','receipt-1','post-2','receipt-2'])
                if removal_error:
                    ack_release.set()
                await asyncio.wait_for(asyncio.gather(prior.delivery_ack_task,
                    return_exceptions=True),0.4)
                self.assertFalse(prior.delivery_ack_task.result())
                llm._start_task_continuation.assert_not_called()
                self.assertEqual(len(requests),2)
                self.assertEqual(requests[1]['text'],'Third: γ\noriginal correction.')
                self.assertEqual(requests[1]['sourceEventId'],'voice:ack-call:item:third-source')
                self.assertEqual(requests[0]['text'],'Original: Ω\nretain me.')
                self.assertEqual(requests[0]['sourceEventId'],'voice:ack-call:item:successor-source')
                self.assertNotEqual(prior.delivery_state,'partial_removed')
                self.assertIsNone(prior.delivery_ack_identity)
                await llm.close_background_continuations()
                self.assertTrue(all(session.closed for session in sessions))
                self.assertFalse(llm._background_continuations)
        finally:
            ack_release.set()
            if current is not None:
                await current.aclose()
            if third is not None:
                await third.aclose()
            await llm.close_background_continuations()
            await runner.cleanup()

    async def test_ready_receipt_survives_stalled_or_failed_prior_removal(self):
        for removal_error in (False,True):
            with self.subTest(removal_error=removal_error):
                await self._ready_before_removal(removal_error=removal_error)

class TestNativeQuestionSpeechOffer(unittest.TestCase):
    def event(self, sequence=1):
        return _voice_task_event('native-question-'+str(sequence), sequence, state='needs_input', phase='needs_input', event_type='needs_input',
            streamId='stream_voice_1', owner={'kind':'generation_job','id':'stream_voice_1'}, needsInput={'prompt':'Choose size', 'inputType':'text',
            'nativeInputRequest':{'version':1,'kind':'question','requestId':'q-1','requestFingerprint':'a'*64,'runId':'run-q','attemptId':'attempt-q','expiresAt':'2099-01-01T00:00:00Z'}})

    def transport(self, batches):
        class NativeSession(_FakeResumingSseSession):
            def __init__(self):
                super().__init__(batches); self.offered=False
            def post(inner,url,*args,**kwargs):
                if str(url).endswith('/native-input/speech-offer'):
                    inner.post_calls.append((url,args,kwargs))
                    if inner.offered: return _SequencedStatusResponse(409,{'error':'already-offered'})
                    inner.offered=True
                    return _FakeJsonResponse({'version':1,'outcome':'offered_unknown','requestKey':'b'*64,'nativeInputRequest':kwargs['json']['nativeInputRequest']})
                return super().post(url,*args,**kwargs)
        return NativeSession()

    def test_native_offer_excludes_provider_resume_text_and_does_not_replay_on_reconnect(self):
        event=self.event();snapshot=self.event(2)
        transport=self.transport([[{'text':'Before. '},{'event':'voice_task_event','voiceTaskEvent':event}],
            [{'sync':True,'resumeState':{'aggregatedContent':[{'type':'text','text':'Before. '}]}}, {'event':'voice_task_event','voiceTaskEvent':snapshot}, {'text':'After.'},
             {'final':True,'responseMessage':{'content':[{'type':'text','text':'Before. After.'}]}}]])
        chunks=asyncio.run(TestPublicPartCompletionCarrier()._run([],fake=transport))
        self.assertEqual(''.join(chunk.delta.content or '' for chunk in chunks),'Before. Choose sizeAfter.')
        markers=[chunk.delta.extra['viventium_native_input_offer'] for chunk in chunks if chunk.delta and 'viventium_native_input_offer' in (chunk.delta.extra or {})]
        self.assertEqual(len(markers),1)

    def test_native_offer_is_not_buffered_while_participant_disconnected(self):
        event=self.event();transport=self.transport([[{'event':'voice_task_event','voiceTaskEvent':event},{'final':True,'responseMessage':{'content':[]}}]])
        chunks=asyncio.run(TestPublicPartCompletionCarrier()._run([],fake=transport,connected=False,reconnect=False))
        self.assertFalse(any('viventium_native_input_offer' in (chunk.delta.extra or {}) for chunk in chunks if chunk.delta))
        self.assertFalse(any(str(url).endswith('/native-input/speech-offer') for url,_,_ in transport.post_calls))

    def test_claim_response_does_not_offer_after_replacement_stop_or_disconnect(self):
        async def run(change):
            event=self.event()
            connected=True
            llm=LibreChatLLM(origin='http://librechat.test',auth=LibreChatAuth(call_session_id='call_1',call_secret='synthetic'),is_participant_connected=lambda:connected)
            llm._task_event_gate.accept(event)
            class Response(_FakeJsonResponse):
                async def json(inner):
                    nonlocal connected
                    if change=='stop':
                        llm._task_event_gate.mark_cancel_accepted(event['taskId'])
                    elif change=='disconnect':
                        connected=False
                    else:
                        next_event=self.event(2)
                        next_event['needsInput']['nativeInputRequest']['requestFingerprint']='c'*64
                        llm._task_event_gate.accept(next_event)
                    return {'version':1,'outcome':'offered_unknown','requestKey':'b'*64,'nativeInputRequest':event['needsInput']['nativeInputRequest']}
            class Session:
                def post(inner,*args,**kwargs): return Response({})
            self.assertIsNone(await llm.claim_native_input_speech_offer(event,'stream_voice_1',Session()))
        for change in ['replacement','stop','disconnect']:
            with self.subTest(change=change): asyncio.run(run(change))

    def test_expired_wrong_generation_and_replaced_requests_do_not_offer(self):
        async def run():
            event=self.event(); transport=self.transport([])
            llm=LibreChatLLM(origin='http://librechat.test',auth=LibreChatAuth(call_session_id='call_1',call_secret='synthetic'),is_participant_connected=lambda:True)
            llm._task_event_gate.accept(event)
            self.assertIsNone(await llm.claim_native_input_speech_offer(event,'foreign-stream',transport))
            event['needsInput']['nativeInputRequest']['expiresAt']='2000-01-01T00:00:00Z';llm._task_event_gate.accept({**event,'sequence':2})
            self.assertIsNone(await llm.claim_native_input_speech_offer(event,'stream_voice_1',transport))
            self.assertFalse(transport.post_calls)
        asyncio.run(run())


class TestCallPreparationAdmission(unittest.IsolatedAsyncioTestCase):
    """Preparation shares ingress ownership and adds no provider/stream timeout change."""
    async def _server(self, handler):
        from aiohttp import web
        app = web.Application()
        app.router.add_post('/api/viventium/voice/chat', handler)
        async def stream(_):
            return web.Response(text='data: {"final":true}\n\n', content_type='text/event-stream')
        app.router.add_get('/api/viventium/voice/stream/{stream_id}', stream)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '127.0.0.1', 0)
        await site.start()
        return runner, 'http://127.0.0.1:' + str(site._server.sockets[0].getsockname()[1])

    async def test_typed_busy_retries_exact_retained_body_until_receipt(self):
        from aiohttp import web
        from librechat_llm import _post_voice_admission_receipt
        bodies = []
        async def handler(request):
            bodies.append(await request.json())
            if len(bodies) == 1:
                return web.json_response({'code': 'call_context_busy', 'retryable': True}, status=409)
            return web.json_response({'streamId': 'same-source-receipt'})
        runner, origin = await self._server(handler)
        body = {'text': 'Keep exact input.', 'sourceEventId': 'voice:synthetic:input', 'streamId': 'same-source'}
        try:
            async with aiohttp.ClientSession() as session:
                receipt = await _post_voice_admission_receipt(session, origin + '/api/viventium/voice/chat',
                    headers={}, body=body, is_call_current=lambda: True)
            self.assertEqual(receipt, {'streamId': 'same-source-receipt'})
            self.assertEqual(bodies, [body, body])
        finally:
            await runner.cleanup()

    async def test_unretryable_authority_error_never_reposts(self):
        from aiohttp import web
        from librechat_llm import _post_voice_admission_receipt
        requests = []
        async def handler(request):
            requests.append(await request.json())
            return web.json_response({'code': 'voice_turn_authority_unavailable', 'retryable': False}, status=409)
        runner, origin = await self._server(handler)
        try:
            async with aiohttp.ClientSession() as session:
                with self.assertRaisesRegex(RuntimeError, 'status 409'):
                    await _post_voice_admission_receipt(session, origin + '/api/viventium/voice/chat',
                        headers={}, body={'text': 'Retain.'}, is_call_current=lambda: True)
            self.assertEqual(len(requests), 1)
        finally:
            await runner.cleanup()

    async def test_call_owner_change_stops_preparation_retries(self):
        from aiohttp import web
        from librechat_llm import _post_voice_admission_receipt
        current, requests = [True], []
        async def handler(request):
            requests.append(await request.json())
            current[0] = False
            return web.json_response({'code': 'call_context_busy', 'retryable': True}, status=409)
        runner, origin = await self._server(handler)
        try:
            async with aiohttp.ClientSession() as session:
                receipt = await _post_voice_admission_receipt(session, origin + '/api/viventium/voice/chat',
                    headers={}, body={'text': 'Retain.'}, is_call_current=lambda: current[0])
            self.assertEqual(receipt, {})
            self.assertEqual(len(requests), 1)
        finally:
            await runner.cleanup()

    async def test_per_call_preparation_adds_only_admission_budget(self):
        from aiohttp import web
        requests, transport_budgets = [], []
        async def handler(request):
            requests.append(await request.json())
            await asyncio.sleep(0.08)  # Beyond the ordinary response deadline.
            return web.json_response({'streamId': requests[-1]['streamId'], 'taskId': 'prep-ready',
                'logical_turn_id': 'prep-ready', 'revision': 1})
        runner, origin = await self._server(handler)
        real_session = aiohttp.ClientSession
        def tracking(*args, **kwargs):
            transport_budgets.append(kwargs['timeout'].total)
            return real_session(*args, **kwargs)
        llm = LibreChatLLM(origin=origin, auth=LibreChatAuth(call_session_id='synthetic-call',
            call_secret='synthetic'), timeout_s=0.03, preparation_timeout_s=1)
        stream = None
        try:
            with patch('librechat_llm.aiohttp.ClientSession', side_effect=tracking):
                stream = llm.chat(chat_ctx=ChatContext(items=[ChatMessage(id='early', role='user', content=['Retain early input.'])]))
                async for _ in stream:
                    pass
            self.assertEqual(len(requests), 1)
            self.assertEqual(requests[0]['text'], 'Retain early input.')
            self.assertEqual(stream._presentation.logical_turn_id, 'prep-ready')
            self.assertEqual(llm._timeout_s, 0.03)
            self.assertIn(0.03, transport_budgets)  # Streaming retains its original budget.
            self.assertIn(11.03, transport_budgets)  # Prep + bounded stop allowance, admission only.
        finally:
            if stream is not None:
                await stream.aclose()
            await llm.close_background_continuations()
            await runner.cleanup()
