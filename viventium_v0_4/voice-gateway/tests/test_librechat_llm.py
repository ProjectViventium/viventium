import os
import sys
import unittest
import asyncio
import json
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
    _NoResponseStreamGuard,
    _VoiceTtsDeltaBuffer,
    is_no_response_only,
    format_insights_for_direct_speech,
)
from sse import sanitize_voice_tts_text


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

    def test_aborts_librechat_stream_when_sse_closes_without_final_event(self) -> None:
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
        self.assertIn(
            "http://librechat.test/api/viventium/voice/stream/stream_voice_1/abort",
            post_urls,
        )

    def test_aborts_librechat_stream_when_livekit_cancels_task(self) -> None:
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
        self.assertIn(
            "http://librechat.test/api/viventium/voice/stream/stream_voice_cancel_1/abort",
            post_urls,
        )
        self.assertTrue(fake_session.abort_completed)


class TestLibreChatStreamingRun(unittest.TestCase):
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

        self.assertEqual(emitted, [" See brief and email email available."])
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
