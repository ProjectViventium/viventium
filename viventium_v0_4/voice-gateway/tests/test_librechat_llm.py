import os
import sys
import unittest
import asyncio
import json
import aiohttp
from unittest.mock import patch

from livekit.agents.llm.chat_context import ChatContext, ChatMessage

# Ensure voice-gateway root is on sys.path so `import librechat_llm` works
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from librechat_llm import (
    LibreChatAuth,
    LibreChatLLM,
    _extract_final_response_text,
    _extract_final_response_message_id,
    _extract_last_user_text,
    _extract_stream_error,
    _select_stream_error_message,
    _summarize_error_for_log,
    _payload_has_glasshive_tool_call,
    _extract_voice_task_event,
    _extract_voice_task_sync,
    _extract_resume_state_text,
    _NoResponseStreamGuard,
    _VoiceTtsDeltaBuffer,
    _VoiceTaskEventGate,
    is_no_response_only,
    format_insights_for_direct_speech,
)
from sse import sanitize_voice_tts_text
from speaker_segments import SpeakerSegmentTracker, attach_speaker_context_to_message
from voice_hop_trace import VoiceHopTrace


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

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def get(self, url, *args, **kwargs):
        self.get_calls.append((url, args, kwargs))
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
        self.get_calls.append((args, kwargs))
        return _FakeClosedSseResponse()


class _FakeSseContent:
    def __init__(self, events: list[dict]):
        self._events = events

    async def iter_any(self):
        for event in self._events:
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
                await stream._run()

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
                await stream._run()

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
                await stream._run()

        asyncio.run(run_stream())

        self.assertEqual(len(fake_session.post_calls), 1)
        post_json = fake_session.post_calls[0][1]["json"]
        self.assertEqual(post_json["streamId"], captured_stream_ids[0])
        self.assertTrue(post_json["streamId"].startswith("lc_"))
        self.assertEqual(post_json["viventiumTextDeltaMode"], "auto")

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


class TestLibreChatStreamingRun(unittest.TestCase):
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

        self.assertEqual("".join(asyncio.run(run_stream())), "Hello world.")

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
            llm.schedule_trace_terminal(trace, grace_s=60.0)
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
        self.assertEqual(llm.task_id_for_trace(audio_correlation), "task_1")
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
        self.assertNotIn(".", chunks)

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

        self.assertEqual(chunks, [expected])
        self.assertEqual("".join(chunks), expected)


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


class TestVoiceTtsDeltaBuffer(unittest.TestCase):
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
        self.assertEqual(buffer.feed("!"), ["Right. That landed!"])
        self.assertEqual(buffer.finalize(), [])

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


if __name__ == "__main__":
    unittest.main()
