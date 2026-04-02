import asyncio
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from TelegramVivBot.utils.librechat_bridge import (
    _strip_markdown,
    _stream_error_message,
    _is_file_attachment_payload,
    _empty_response_message,
    extract_completed_cortex_insights,
    extract_attachments,
    extract_cortex_followup,
    extract_cortex_parts,
    extract_final_error,
    extract_final_response_text,
    extract_response_message_id,
    extract_text_deltas,
    has_active_cortex,
    LibreChatBridge,
    LibreChatSession,
    render_telegram_markdown,
    sanitize_telegram_text,
)


def test_sanitize_telegram_text_removes_citations():
    text = "Hello \ue202turn0search0 world [12]  done"
    cleaned = sanitize_telegram_text(text)
    assert "\ue202turn0search0" not in cleaned
    assert "[12]" not in cleaned
    assert "Hello world done" in cleaned


def test_sanitize_telegram_text_removes_consecutive_citations():
    text = "Hello\ue202turn2search1\ue202turn1search3 world"
    cleaned = sanitize_telegram_text(text)
    assert "\ue202" not in cleaned
    assert "turn" not in cleaned
    assert "Hello world" in cleaned


def test_sanitize_telegram_text_removes_bare_citations():
    text = "ArriveCan.ue202turn1search2ue202turn1news1 Done"
    cleaned = sanitize_telegram_text(text)
    assert "ue202" not in cleaned.lower()
    assert "turn1search2" not in cleaned
    assert "turn1news1" not in cleaned
    assert "ArriveCan." in cleaned


def test_sanitize_telegram_text_removes_unknown_citation_type():
    text = "Hello ue202turn9custom7 world"
    cleaned = sanitize_telegram_text(text)
    assert "ue202" not in cleaned.lower()
    assert "turn9custom7" not in cleaned
    assert "Hello world" in cleaned


# === VIVENTIUM START ===
def test_sanitize_telegram_text_normalizes_em_dash_clause_breaks():
    text = "Hi—This is how it should read.\n\nHi — This is another example."
    cleaned = sanitize_telegram_text(text)
    assert "Hi, This is how it should read." in cleaned
    assert "Hi, This is another example." in cleaned


def test_sanitize_telegram_text_normalizes_inline_em_dash_to_space():
    text = "Or some other case could be—very different."
    cleaned = sanitize_telegram_text(text)
    assert cleaned == "Or some other case could be very different."


def test_sanitize_telegram_text_preserves_markdown_code_spans_when_cleaning_em_dashes():
    text = "Say Hi—There but keep `foo—bar` untouched."
    cleaned = sanitize_telegram_text(text)
    assert "Say Hi, There" in cleaned
    assert "`foo—bar`" in cleaned


def test_render_telegram_markdown_converts_basic_markdown():
    text = "Hello **bold**.\n- item"
    rendered = render_telegram_markdown(text)
    assert "<b>bold</b>" in rendered
    assert "\u2022 item" in rendered
# === VIVENTIUM END ===


def test_render_telegram_markdown_preserves_preescaped_text():
    text = "Already escaped\\. Still escaped\\! And list\\-item\\."
    rendered = render_telegram_markdown(text)
    assert rendered == text


def test_extract_text_deltas_from_text_payload():
    payload = {"text": "Hi there"}
    assert extract_text_deltas(payload) == ["Hi there"]


def test_extract_text_deltas_from_message_delta():
    payload = {
        "event": "on_message_delta",
        "data": {
            "delta": {
                "content": [
                    {"type": "text", "text": "Hello "},
                    {"type": "text", "text": "world"},
                ]
            }
        },
    }
    assert extract_text_deltas(payload) == ["Hello ", "world"]


def test_extract_attachments_from_attachment_event_wrapper():
    payload = {
        "event": "attachment",
        "data": {"file_id": "file-1", "filename": "x.png", "filepath": "/images/u/x.png"},
    }
    assert extract_attachments(payload) == [
        {"file_id": "file-1", "filename": "x.png", "filepath": "/images/u/x.png"}
    ]


def test_extract_attachments_from_direct_sse_attachment_event():
    payload = {"_sse_event": "attachment", "file_id": "file-2", "filename": "y.txt"}
    assert extract_attachments(payload) == [{"file_id": "file-2", "filename": "y.txt"}]


def test_extract_attachments_ignores_non_file_event_payload():
    payload = {"event": "attachment", "data": {"type": "memory", "key": "context"}}
    assert extract_attachments(payload) == []


def test_extract_attachments_ignores_non_file_direct_sse_payload():
    payload = {"_sse_event": "attachment", "type": "memory", "key": "context"}
    assert extract_attachments(payload) == []


def test_is_file_attachment_payload():
    assert _is_file_attachment_payload({"file_id": "abc"}) is True
    assert _is_file_attachment_payload({"filepath": "/images/u/a.png"}) is True
    assert _is_file_attachment_payload({"type": "memory"}) is False


def test_extract_attachments_from_final_payload():
    payload = {
        "final": True,
        "responseMessage": {
            "attachments": [{"file_id": "file-3", "filename": "z.pdf"}],
        },
    }
    assert extract_attachments(payload) == [{"file_id": "file-3", "filename": "z.pdf"}]


def test_extract_final_response_text():
    payload = {
        "final": True,
        "responseMessage": {
            "content": [
                {"type": "text", "text": "Final "},
                {"type": "text", "text": {"value": "answer"}},
            ]
        },
    }
    assert extract_final_response_text(payload) == "Final answer"


def test_extract_final_response_text_uses_response_text():
    payload = {
        "final": True,
        "responseMessage": {
            "text": "Hello",
            "content": [{"type": "text", "text": "Ignored"}],
        },
    }
    assert extract_final_response_text(payload) == "Hello"


def test_extract_final_response_text_from_content_string():
    payload = {
        "final": True,
        "responseMessage": {"content": "Hello there"},
    }
    assert extract_final_response_text(payload) == "Hello there"


def test_extract_final_response_text_from_content_dict():
    payload = {
        "final": True,
        "responseMessage": {"content": {"type": "text", "text": "Hello"}},
    }
    assert extract_final_response_text(payload) == "Hello"


def test_extract_final_response_text_from_content_list_strings():
    payload = {
        "final": True,
        "responseMessage": {"content": ["Hello ", "world"]},
    }
    assert extract_final_response_text(payload) == "Hello world"


def test_extract_final_response_text_fallback_payload_text():
    payload = {"final": True, "text": "Fallback text"}
    assert extract_final_response_text(payload) == "Fallback text"


def test_extract_final_error_from_error_content_part():
    payload = {
        "final": True,
        "responseMessage": {"content": [{"type": "error", "error": "Access denied"}]},
    }
    assert extract_final_error(payload) == "Access denied"


def test_empty_response_message_default(monkeypatch):
    monkeypatch.delenv("VIVENTIUM_TELEGRAM_EMPTY_RESPONSE_MESSAGE", raising=False)
    assert _empty_response_message() == "No response received. Please retry."


def test_empty_response_message_env_override(monkeypatch):
    monkeypatch.setenv("VIVENTIUM_TELEGRAM_EMPTY_RESPONSE_MESSAGE", "Try again")
    assert _empty_response_message() == "Try again"


def test_stream_error_message_classifies_tool_errors():
    assert _stream_error_message("tool call failed") == "Tool connection error. Please retry."
    assert _stream_error_message("mcp auth required") == "Tool connection error. Please retry."
    assert (
        _stream_error_message("Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits.")
        == "Provider billing issue. Please check Plans & Billing."
    )
    assert (
        _stream_error_message("OpenAI connected account needs reconnect in Settings > Account > Connected Accounts.")
        == "OpenAI connected account needs reconnect in Settings > Account > Connected Accounts."
    )
    assert _stream_error_message("plain timeout") == "Connection error. Please retry."


# === VIVENTIUM START ===
# Tests: Follow-up event parsing and batching format.
def test_extract_cortex_followup_text():
    payload = {"event": "on_cortex_followup", "data": {"text": "Merged follow-up"}}
    assert extract_cortex_followup(payload) == "Merged follow-up"


def test_extract_cortex_followup_text_normalizes_em_dash_with_main_response_parity():
    payload = {"event": "on_cortex_followup", "data": {"text": "Hi—This landed from Phase B."}}
    assert extract_cortex_followup(payload) == "Hi, This landed from Phase B."


def test_format_pending_insights_batch():
    bridge = _make_bridge()
    insights = [
        {"cortex_name": "Online Tool Use", "insight": "Latest email found."},
        {"cortex_name": "Pattern Recognition", "insight": "Recurring request."},
    ]
    text = bridge._format_pending_insights(insights, voice_mode=False)
    assert "Latest email found." in text
    assert "Recurring request." in text
    assert "Online Tool Use" not in text
    assert "Pattern Recognition" not in text
    assert "Background insights" not in text
# === VIVENTIUM END ===


# === VIVENTIUM START ===
@pytest.mark.asyncio
async def test_followup_text_renders_html_for_telegram_display():
    bridge = _make_bridge()
    captured = {}

    async def _capture(chat_id, message, parse_mode=None):
        captured["chat_id"] = chat_id
        captured["message"] = message
        captured["parse_mode"] = parse_mode

    bridge.set_on_message_callback(_capture)
    await bridge._send_followup_text("123", "**Bold** and `code`")

    assert captured["chat_id"] == 123
    assert captured["parse_mode"] == "HTML"
    assert "<b>Bold</b>" in captured["message"]
    assert "<code>code</code>" in captured["message"]
# === VIVENTIUM END ===


# === VIVENTIUM START ===
def test_strip_markdown_preserves_paragraph_breaks():
    text = "**Title**\n\n- first\n- second\n\n`code`"
    cleaned = _strip_markdown(text)
    assert "Title" in cleaned
    assert "first" in cleaned
    assert "second" in cleaned
    assert "code" in cleaned
    assert "\n\n" in cleaned
# === VIVENTIUM END ===


# === VIVENTIUM START ===
# Feature: Proactive follow-up voice parity tests.
@pytest.mark.asyncio
async def test_deliver_callback_sends_voice_audio_when_preference_gate_passes(monkeypatch):
    bridge = _make_bridge()
    captured = {}

    async def _capture(chat_id, message, parse_mode=None, voice_audio=None):
        captured["chat_id"] = chat_id
        captured["message"] = message
        captured["parse_mode"] = parse_mode
        captured["voice_audio"] = voice_audio

    bridge.set_on_message_callback(_capture)

    fake_config = types.SimpleNamespace(
        Users=types.SimpleNamespace(
            get_config=lambda _convo_id, key: True if key == "ALWAYS_VOICE_RESPONSE" else True,
        )
    )
    monkeypatch.setitem(sys.modules, "config", fake_config)
    fake_utils_pkg = types.ModuleType("utils")
    fake_voice_mod = types.ModuleType("utils.voice")
    fake_tts_mod = types.ModuleType("utils.tts")
    fake_voice_mod.should_send_voice_reply = lambda **_kwargs: True

    async def _fake_tts(_text, _convo_id, *, voice_route=None):
        _ = voice_route
        return b"voice-bytes"

    fake_tts_mod.synthesize_speech = _fake_tts
    monkeypatch.setitem(sys.modules, "utils", fake_utils_pkg)
    monkeypatch.setitem(sys.modules, "utils.voice", fake_voice_mod)
    monkeypatch.setitem(sys.modules, "utils.tts", fake_tts_mod)

    await bridge._deliver_callback(
        123,
        "hello",
        parse_mode="MarkdownV2",
        preference_convo_id="123",
    )

    assert captured["chat_id"] == 123
    assert captured["message"] == "hello"
    assert captured["parse_mode"] == "MarkdownV2"
    assert captured["voice_audio"] == b"voice-bytes"


@pytest.mark.asyncio
async def test_deliver_callback_falls_back_to_text_when_voice_gate_fails(monkeypatch):
    bridge = _make_bridge()
    captured = {}

    async def _capture(chat_id, message, parse_mode=None, voice_audio=None):
        captured["chat_id"] = chat_id
        captured["message"] = message
        captured["parse_mode"] = parse_mode
        captured["voice_audio"] = voice_audio

    bridge.set_on_message_callback(_capture)

    fake_config = types.SimpleNamespace(
        Users=types.SimpleNamespace(
            get_config=lambda _convo_id, key: False if key == "ALWAYS_VOICE_RESPONSE" else True,
        )
    )
    monkeypatch.setitem(sys.modules, "config", fake_config)
    fake_utils_pkg = types.ModuleType("utils")
    fake_voice_mod = types.ModuleType("utils.voice")
    fake_tts_mod = types.ModuleType("utils.tts")
    fake_voice_mod.should_send_voice_reply = lambda **_kwargs: False

    async def _fake_tts(_text, _convo_id, *, voice_route=None):
        _ = voice_route
        return b"voice-bytes"

    fake_tts_mod.synthesize_speech = _fake_tts
    monkeypatch.setitem(sys.modules, "utils", fake_utils_pkg)
    monkeypatch.setitem(sys.modules, "utils.voice", fake_voice_mod)
    monkeypatch.setitem(sys.modules, "utils.tts", fake_tts_mod)

    await bridge._deliver_callback(
        456,
        "hello",
        parse_mode="MarkdownV2",
        preference_convo_id="456",
    )

    assert captured["chat_id"] == 456
    assert captured["voice_audio"] is None


@pytest.mark.asyncio
async def test_deliver_callback_splits_long_text_and_attaches_voice_only_to_last_chunk(monkeypatch):
    bridge = _make_bridge()
    messages = []

    async def _capture(chat_id, message, parse_mode=None, voice_audio=None):
        messages.append((chat_id, message, parse_mode, voice_audio))

    bridge.set_on_message_callback(_capture)

    fake_config = types.SimpleNamespace(
        Users=types.SimpleNamespace(
            get_config=lambda _convo_id, key: True if key == "ALWAYS_VOICE_RESPONSE" else True,
        )
    )
    monkeypatch.setitem(sys.modules, "config", fake_config)
    fake_utils_pkg = types.ModuleType("utils")
    fake_voice_mod = types.ModuleType("utils.voice")
    fake_tts_mod = types.ModuleType("utils.tts")
    fake_voice_mod.should_send_voice_reply = lambda **_kwargs: True

    async def _fake_tts(_text, _convo_id, *, voice_route=None):
        _ = voice_route
        return b"voice-bytes"

    fake_tts_mod.synthesize_speech = _fake_tts
    monkeypatch.setitem(sys.modules, "utils", fake_utils_pkg)
    monkeypatch.setitem(sys.modules, "utils.voice", fake_voice_mod)
    monkeypatch.setitem(sys.modules, "utils.tts", fake_tts_mod)

    long_text = "\n\n".join(
        [
            f"Section {index}: " + ("word " * 180)
            for index in range(1, 5)
        ]
    )

    await bridge._deliver_callback(
        789,
        render_telegram_markdown(long_text),
        parse_mode="HTML",
        preference_convo_id="789",
        raw_message=long_text,
    )

    assert len(messages) > 1
    assert all(message[0] == 789 for message in messages)
    assert all(message[2] == "HTML" for message in messages)
    assert all(message[3] is None for message in messages[:-1])
    assert messages[-1][3] == b"voice-bytes"
# === VIVENTIUM END ===


def test_extract_cortex_parts_and_active():
    content = [
        {"type": "text", "text": "Hello"},
        {"type": "cortex_brewing", "status": "brewing"},
        {"type": "cortex_insight", "status": "complete", "insight": "Done"},
    ]
    parts = extract_cortex_parts(content)
    assert len(parts) == 2
    assert has_active_cortex(parts) is True


def test_extract_completed_cortex_insights():
    parts = [
        {"type": "cortex_insight", "status": "complete", "insight": " Secret "},
        {"type": "cortex_insight", "status": "error", "insight": "Nope"},
    ]
    insights = extract_completed_cortex_insights(parts)
    assert insights == [
        {"cortex_id": "", "cortex_name": "Background Insight", "insight": "Secret"}
    ]


def test_extract_response_message_id():
    payload = {"final": True, "responseMessage": {"messageId": "msg-1"}}
    assert extract_response_message_id(payload) == "msg-1"


def _make_bridge():
    bridge = LibreChatBridge(
        get_conversation_id=lambda _chat_id: "new",
        set_conversation_id=lambda _chat_id, _convo_id: None,
    )
    bridge.secret = "test-secret"
    bridge.base_url = "http://example.com"
    return bridge


@pytest.mark.asyncio
async def test_ask_stream_async_listens_for_followup_events_even_when_raw_insights_disabled():
    bridge = _make_bridge()
    bridge.include_insights = False
    bridge.allow_insight_fallback = False
    seen = []

    async def _capture(chat_id, message, parse_mode=None):
        _ = chat_id, message, parse_mode

    async def fake_start_chat(**kwargs):
        _ = kwargs
        return LibreChatSession(stream_id="stream-followup", conversation_id="conv-followup")

    async def fake_listen_for_insights(*, stream_id, chat_id):
        seen.append((stream_id, chat_id))

    async def fake_stream_response(stream_id, chat_id, trace_id=None):
        _ = stream_id, chat_id, trace_id
        if False:
            yield ""

    bridge.set_on_message_callback(_capture)
    bridge._start_chat = fake_start_chat  # type: ignore[assignment]
    bridge._listen_for_insights = fake_listen_for_insights  # type: ignore[assignment]
    bridge._stream_response = fake_stream_response  # type: ignore[assignment]

    chunks = [chunk async for chunk in bridge.ask_stream_async("hi", "123")]
    await asyncio.sleep(0)

    assert chunks == []
    assert seen == [("stream-followup", "123")]


@pytest.mark.asyncio
async def test_ask_stream_async_caches_voice_route_from_chat_start():
    bridge = _make_bridge()

    async def fake_start_chat(**kwargs):
        _ = kwargs
        return LibreChatSession(
            stream_id="stream-voice",
            conversation_id="conv-voice",
            voice_route={
                "tts": {"provider": "local_chatterbox_turbo_mlx_8bit", "variant": "mlx-community/chatterbox-turbo-8bit"},
            },
        )

    async def fake_stream_response(stream_id, chat_id, trace_id=None):
        _ = stream_id, chat_id, trace_id
        if False:
            yield ""

    bridge._start_chat = fake_start_chat  # type: ignore[assignment]
    bridge._stream_response = fake_stream_response  # type: ignore[assignment]

    chunks = [chunk async for chunk in bridge.ask_stream_async("hi", "voice-chat")]

    assert chunks == []
    assert bridge.get_cached_voice_route("voice-chat") == {
        "tts": {
            "provider": "local_chatterbox_turbo_mlx_8bit",
            "variant": "mlx-community/chatterbox-turbo-8bit",
        },
    }


@pytest.mark.asyncio
async def test_insight_listener_treats_missing_completed_stream_as_benign(monkeypatch):
    bridge = _make_bridge()
    warnings = []

    async def _capture(chat_id, message, parse_mode=None):
        _ = chat_id, message, parse_mode

    class _FakeResponse:
        def __init__(self):
            import TelegramVivBot.utils.librechat_bridge as bridge_module

            self.status_code = 404
            self.text = '{"error":"Stream not found"}'
            self.request = bridge_module.httpx.Request(
                "GET",
                "http://example.com/api/viventium/telegram/stream/stream-missing",
            )

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            _ = exc_type, exc, tb
            return False

        def raise_for_status(self):
            import TelegramVivBot.utils.librechat_bridge as bridge_module

            raise bridge_module.httpx.HTTPStatusError(
                "stream no longer available",
                request=self.request,
                response=self,
            )

        def aiter_bytes(self):
            async def _gen():
                if False:
                    yield b""

            return _gen()

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            _ = args, kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            _ = exc_type, exc, tb
            return False

        def stream(self, *args, **kwargs):
            _ = args, kwargs
            return _FakeResponse()

    import TelegramVivBot.utils.librechat_bridge as bridge_module

    monkeypatch.setattr(bridge_module.httpx, "AsyncClient", _FakeClient)
    monkeypatch.setattr(bridge_module.logger, "warning", lambda *args, **kwargs: warnings.append(args))

    bridge.set_on_message_callback(_capture)
    bridge._set_active_stream("123", "stream-missing")

    await bridge._listen_for_insights(stream_id="stream-missing", chat_id="123")

    assert warnings == []
    assert bridge._active_stream_by_chat == {}


@pytest.mark.asyncio
async def test_stream_response_final_attachments_only_skips_empty_fallback(monkeypatch):
    bridge = _make_bridge()

    payloads = [
        {
            "final": True,
            "responseMessage": {
                "attachments": [
                    {"file_id": "file-1", "filename": "x.png", "filepath": "/images/u/x.png"}
                ],
                "content": [],
            },
        }
    ]

    async def fake_iter_sse_json_events(*, chunk_iter):
        _ = chunk_iter
        for payload in payloads:
            yield payload

    class _FakeResponse:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            _ = exc_type, exc, tb
            return False

        def raise_for_status(self):
            return None

        def aiter_bytes(self):
            async def _gen():
                if False:
                    yield b""

            return _gen()

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            _ = args, kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            _ = exc_type, exc, tb
            return False

        def stream(self, *args, **kwargs):
            _ = args, kwargs
            return _FakeResponse()

    import TelegramVivBot.utils.librechat_bridge as bridge_module

    monkeypatch.setattr(bridge_module, "iter_sse_json_events", fake_iter_sse_json_events)
    monkeypatch.setattr(bridge_module.httpx, "AsyncClient", _FakeClient)

    chunks = [chunk async for chunk in bridge._stream_response("stream-attach-final", "111")]

    assert chunks == [
        {
            "type": "attachment",
            "attachment": {"file_id": "file-1", "filename": "x.png", "filepath": "/images/u/x.png"},
        }
    ]


@pytest.mark.asyncio
async def test_stream_response_streamed_attachment_then_empty_final_skips_empty_fallback(monkeypatch):
    bridge = _make_bridge()

    payloads = [
        {
            "event": "attachment",
            "data": {"file_id": "file-2", "filename": "y.pdf", "filepath": "/files/u/y.pdf"},
        },
        {"final": True, "responseMessage": {"content": []}},
    ]

    async def fake_iter_sse_json_events(*, chunk_iter):
        _ = chunk_iter
        for payload in payloads:
            yield payload

    class _FakeResponse:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            _ = exc_type, exc, tb
            return False

        def raise_for_status(self):
            return None

        def aiter_bytes(self):
            async def _gen():
                if False:
                    yield b""

            return _gen()

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            _ = args, kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            _ = exc_type, exc, tb
            return False

        def stream(self, *args, **kwargs):
            _ = args, kwargs
            return _FakeResponse()

    import TelegramVivBot.utils.librechat_bridge as bridge_module

    monkeypatch.setattr(bridge_module, "iter_sse_json_events", fake_iter_sse_json_events)
    monkeypatch.setattr(bridge_module.httpx, "AsyncClient", _FakeClient)

    chunks = [chunk async for chunk in bridge._stream_response("stream-attach-first", "222")]

    assert chunks == [
        {
            "type": "attachment",
            "attachment": {"file_id": "file-2", "filename": "y.pdf", "filepath": "/files/u/y.pdf"},
        }
    ]


# === VIVENTIUM START ===
# Regression: internal-only deferred finals should wait for follow-up delivery instead of
# emitting a false Telegram empty-response error.
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {
            "final": True,
            "responseMessage": {
                "messageId": "msg-deferred-1",
                "unfinished": True,
                "content": [
                    {"type": "think", "think": "Still working"},
                    {"type": "cortex_brewing", "status": "brewing"},
                    {"type": "cortex_brewing", "status": "brewing"},
                ],
            },
        },
        {
            "final": True,
            "responseMessageId": "msg-deferred-2",
            "responseMessage": {
                "content": [
                    {"type": "think", "think": "Searching"},
                    {"type": "tool_call", "tool_call": {"name": "web_search"}},
                    {"type": "cortex_brewing", "status": "brewing"},
                ],
            },
        },
    ],
)
async def test_stream_response_deferred_internal_final_skips_false_empty_fallback(
    monkeypatch,
    payload,
):
    bridge = _make_bridge()
    scheduled = []

    async def fake_iter_sse_json_events(*, chunk_iter):
        _ = chunk_iter
        yield payload

    class _FakeResponse:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            _ = exc_type, exc, tb
            return False

        def raise_for_status(self):
            return None

        def aiter_bytes(self):
            async def _gen():
                if False:
                    yield b""

            return _gen()

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            _ = args, kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            _ = exc_type, exc, tb
            return False

        def stream(self, *args, **kwargs):
            _ = args, kwargs
            return _FakeResponse()

    import TelegramVivBot.utils.librechat_bridge as bridge_module

    monkeypatch.setattr(bridge_module, "iter_sse_json_events", fake_iter_sse_json_events)
    monkeypatch.setattr(bridge_module.httpx, "AsyncClient", _FakeClient)
    monkeypatch.setattr(
        bridge,
        "_schedule_followup_poll",
        lambda stream_id, chat_id: scheduled.append((stream_id, chat_id)),
    )

    chunks = [chunk async for chunk in bridge._stream_response("stream-deferred", "555")]

    assert chunks == []
    assert scheduled == [("stream-deferred", "555")]
    assert bridge._response_message_ids["stream-deferred"].startswith("msg-deferred-")
    assert bridge._has_cortex_seen("stream-deferred") is True
# === VIVENTIUM END ===


@pytest.mark.asyncio
async def test_stream_response_text_and_final_attachments(monkeypatch):
    bridge = _make_bridge()

    payloads = [
        {
            "event": "on_message_delta",
            "data": {"delta": {"content": [{"type": "text", "text": "Hello"}]}},
        },
        {
            "final": True,
            "responseMessage": {
                "content": [],
                "attachments": [{"file_id": "file-3", "filename": "z.txt", "filepath": "/files/u/z.txt"}],
            },
        },
    ]

    async def fake_iter_sse_json_events(*, chunk_iter):
        _ = chunk_iter
        for payload in payloads:
            yield payload

    class _FakeResponse:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            _ = exc_type, exc, tb
            return False

        def raise_for_status(self):
            return None

        def aiter_bytes(self):
            async def _gen():
                if False:
                    yield b""

            return _gen()

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            _ = args, kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            _ = exc_type, exc, tb
            return False

        def stream(self, *args, **kwargs):
            _ = args, kwargs
            return _FakeResponse()

    import TelegramVivBot.utils.librechat_bridge as bridge_module

    monkeypatch.setattr(bridge_module, "iter_sse_json_events", fake_iter_sse_json_events)
    monkeypatch.setattr(bridge_module.httpx, "AsyncClient", _FakeClient)

    chunks = [chunk async for chunk in bridge._stream_response("stream-text-attach", "333")]

    assert chunks == [
        "Hello",
        {
            "type": "attachment",
            "attachment": {"file_id": "file-3", "filename": "z.txt", "filepath": "/files/u/z.txt"},
        },
    ]


@pytest.mark.asyncio
async def test_stream_response_ignores_non_file_attachment_events(monkeypatch):
    bridge = _make_bridge()

    payloads = [
        {"event": "attachment", "data": {"type": "memory", "key": "context"}},
        {"final": True, "responseMessage": {"content": [{"type": "text", "text": "Recovered"}]}},
    ]

    async def fake_iter_sse_json_events(*, chunk_iter):
        _ = chunk_iter
        for payload in payloads:
            yield payload

    class _FakeResponse:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            _ = exc_type, exc, tb
            return False

        def raise_for_status(self):
            return None

        def aiter_bytes(self):
            async def _gen():
                if False:
                    yield b""

            return _gen()

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            _ = args, kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            _ = exc_type, exc, tb
            return False

        def stream(self, *args, **kwargs):
            _ = args, kwargs
            return _FakeResponse()

    import TelegramVivBot.utils.librechat_bridge as bridge_module

    monkeypatch.setattr(bridge_module, "iter_sse_json_events", fake_iter_sse_json_events)
    monkeypatch.setattr(bridge_module.httpx, "AsyncClient", _FakeClient)

    chunks = [chunk async for chunk in bridge._stream_response("stream-no-file-attach", "444")]

    assert chunks == ["Recovered"]


@pytest.mark.asyncio
async def test_stream_response_retries_after_transient_stream_error(monkeypatch):
    bridge = _make_bridge()
    bridge.max_retries = 1
    attempts = {"n": 0}

    payloads = [
        {
            "final": True,
            "responseMessage": {"content": [{"type": "text", "text": "Recovered after retry"}]},
        }
    ]

    async def fake_iter_sse_json_events(*, chunk_iter):
        _ = chunk_iter
        for payload in payloads:
            yield payload

    class _FailingResponse:
        async def __aenter__(self):
            raise RuntimeError("temporary timeout")

        async def __aexit__(self, exc_type, exc, tb):
            _ = exc_type, exc, tb
            return False

    class _SuccessResponse:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            _ = exc_type, exc, tb
            return False

        def raise_for_status(self):
            return None

        def aiter_bytes(self):
            async def _gen():
                if False:
                    yield b""

            return _gen()

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            _ = args, kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            _ = exc_type, exc, tb
            return False

        def stream(self, *args, **kwargs):
            _ = args, kwargs
            attempts["n"] += 1
            if attempts["n"] == 1:
                return _FailingResponse()
            return _SuccessResponse()

    import TelegramVivBot.utils.librechat_bridge as bridge_module

    monkeypatch.setattr(bridge_module, "iter_sse_json_events", fake_iter_sse_json_events)
    monkeypatch.setattr(bridge_module.httpx, "AsyncClient", _FakeClient)

    chunks = [chunk async for chunk in bridge._stream_response("stream-retry", "555")]

    assert attempts["n"] == 2
    assert chunks == ["Recovered after retry"]


def test_should_emit_insight_dedupes_identical():
    bridge = _make_bridge()
    bridge._retain_insight_seen("stream-1")
    insight = {"cortex_id": "pattern", "insight": "Same message"}
    assert bridge._should_emit_insight("stream-1", insight) is True
    assert bridge._should_emit_insight("stream-1", insight) is False
    bridge._release_insight_seen("stream-1")


def test_should_emit_insight_allows_distinct_cortex():
    bridge = _make_bridge()
    bridge._retain_insight_seen("stream-2")
    first = {"cortex_id": "pattern", "insight": "Same message"}
    second = {"cortex_id": "online_tool", "insight": "Same message"}
    assert bridge._should_emit_insight("stream-2", first) is True
    assert bridge._should_emit_insight("stream-2", second) is True
    bridge._release_insight_seen("stream-2")


@pytest.mark.asyncio
async def test_ask_stream_async_serializes_per_chat(monkeypatch):
    monkeypatch.setenv("VIVENTIUM_TELEGRAM_SERIALIZE_PER_CHAT", "1")
    bridge = _make_bridge()
    start_times = []

    async def fake_start_chat(
        *,
        text,
        conversation_id,
        agent_id,
        telegram_chat_id,
        telegram_user_id,
        telegram_username,
        telegram_message_id,
        telegram_update_id,
        preference_convo_id=None,
        voice_mode=None,
        input_mode="",
        files=None,
        # === VIVENTIUM START ===
        # Feature: Timezone propagation to LibreChat time context.
        client_timezone=None,
        # === VIVENTIUM END ===
        message_timestamp=None,
        # === VIVENTIUM START ===
        # Feature: Trace id passthrough from Telegram bridge.
        trace_id=None,
        # === VIVENTIUM END ===
    ):
        _ = (
            text,
            conversation_id,
            agent_id,
            telegram_chat_id,
            telegram_user_id,
            telegram_username,
            telegram_message_id,
            telegram_update_id,
        )
        _ = voice_mode, input_mode, files, message_timestamp, trace_id
        _ = preference_convo_id
        # === VIVENTIUM START ===
        # Feature: Ensure Telegram bridge forwards clientTimezone to LibreChat.
        assert client_timezone == "America/Toronto"
        # === VIVENTIUM END ===
        start_times.append(asyncio.get_running_loop().time())
        return LibreChatSession(stream_id=f"stream-{len(start_times)}", conversation_id="conv")

    async def fake_stream_response(_stream_id, _chat_id, *, trace_id=None):
        _ = trace_id
        yield "ok"
        await asyncio.sleep(0.05)

    bridge._start_chat = fake_start_chat  # type: ignore[assignment]
    bridge._stream_response = fake_stream_response  # type: ignore[assignment]

    async def consume():
        # === VIVENTIUM START ===
        # Feature: Pass clientTimezone through Telegram bridge.
        return [
            chunk
            async for chunk in bridge.ask_stream_async(
                "hi",
                "chat-1",
                client_timezone="America/Toronto",
            )
        ]
        # === VIVENTIUM END ===

    await asyncio.gather(consume(), consume())
    assert len(start_times) == 2
    assert (start_times[1] - start_times[0]) >= 0.04


@pytest.mark.asyncio
async def test_ask_stream_async_parallel_by_default(monkeypatch):
    monkeypatch.delenv("VIVENTIUM_TELEGRAM_SERIALIZE_PER_CHAT", raising=False)
    bridge = _make_bridge()
    start_times = []

    async def fake_start_chat(
        *,
        text,
        conversation_id,
        agent_id,
        telegram_chat_id,
        telegram_user_id,
        telegram_username,
        telegram_message_id,
        telegram_update_id,
        preference_convo_id=None,
        voice_mode=None,
        input_mode="",
        files=None,
        client_timezone=None,
        message_timestamp=None,
        trace_id=None,
    ):
        _ = (
            text,
            conversation_id,
            agent_id,
            telegram_chat_id,
            telegram_user_id,
            telegram_username,
            telegram_message_id,
            telegram_update_id,
            preference_convo_id,
            voice_mode,
            input_mode,
            files,
            client_timezone,
            message_timestamp,
            trace_id,
        )
        start_times.append(asyncio.get_running_loop().time())
        return LibreChatSession(stream_id=f"stream-{len(start_times)}", conversation_id="conv")

    async def fake_stream_response(_stream_id, _chat_id, *, trace_id=None):
        _ = trace_id
        yield "ok"
        await asyncio.sleep(0.05)

    bridge._start_chat = fake_start_chat  # type: ignore[assignment]
    bridge._stream_response = fake_stream_response  # type: ignore[assignment]

    async def consume():
        return [chunk async for chunk in bridge.ask_stream_async("hi", "chat-1")]

    await asyncio.gather(consume(), consume())
    assert len(start_times) == 2
    assert abs(start_times[1] - start_times[0]) < 0.04


@pytest.mark.asyncio
async def test_start_chat_duplicate_ack_returns_none(monkeypatch):
    bridge = _make_bridge()

    class _FakeResponse:
        status_code = 200
        text = '{"duplicate":true}'

        @staticmethod
        def json():
            return {"duplicate": True, "conversationId": "conv-1"}

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            _ = args, kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            _ = exc_type, exc, tb
            return False

        async def post(self, _url, json=None, headers=None):
            assert json["telegramMessageId"] == "123"
            assert json["telegramUpdateId"] == "456"
            assert headers["X-VIVENTIUM-TELEGRAM-SECRET"] == "test-secret"
            return _FakeResponse()

    import TelegramVivBot.utils.librechat_bridge as bridge_module

    monkeypatch.setattr(bridge_module.httpx, "AsyncClient", _FakeClient)

    session = await bridge._start_chat(
        text="hello",
        conversation_id="new",
        agent_id="agent-1",
        telegram_chat_id="chat-1",
        telegram_user_id="user-1",
        telegram_username="name",
        telegram_message_id="123",
        telegram_update_id="456",
        preference_convo_id="chat-1",
        voice_mode=False,
        input_mode="text",
    )

    assert session is None


@pytest.mark.asyncio
async def test_start_chat_parses_voice_route_from_response(monkeypatch):
    bridge = _make_bridge()

    class _FakeResponse:
        status_code = 200
        text = '{"streamId":"stream-voice","conversationId":"conv-voice"}'

        @staticmethod
        def json():
            return {
                "streamId": "stream-voice",
                "conversationId": "conv-voice",
                "voiceRoute": {
                    "tts": {"provider": "cartesia", "variant": "sonic-3"},
                },
            }

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            _ = args, kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            _ = exc_type, exc, tb
            return False

        async def post(self, _url, json=None, headers=None):
            assert json["voiceMode"] is True
            assert headers["X-VIVENTIUM-TELEGRAM-SECRET"] == "test-secret"
            return _FakeResponse()

    import TelegramVivBot.utils.librechat_bridge as bridge_module

    monkeypatch.setattr(bridge_module.httpx, "AsyncClient", _FakeClient)

    session = await bridge._start_chat(
        text="hello",
        conversation_id="new",
        agent_id="agent-1",
        telegram_chat_id="chat-1",
        telegram_user_id="user-1",
        telegram_username="name",
        telegram_message_id="123",
        telegram_update_id="456",
        preference_convo_id="chat-1",
        voice_mode=True,
        input_mode="voice_note",
    )

    assert session is not None
    assert session.voice_route == {
      "tts": {"provider": "cartesia", "variant": "sonic-3"},
    }


@pytest.mark.asyncio
async def test_poll_for_followup_sends_followup():
    bridge = _make_bridge()
    messages = []

    async def on_message(chat_id, text):
        messages.append((chat_id, text))

    bridge.set_on_message_callback(on_message)
    stream_id = "stream-1"
    chat_id = "101"
    bridge._set_active_stream(chat_id, stream_id)
    bridge._response_message_ids[stream_id] = "msg-1"
    bridge._conversation_by_stream[stream_id] = "conv-1"
    bridge.followup_interval_s = 0.01
    bridge.followup_timeout_s = 0.2
    bridge.followup_grace_s = 0.05

    states = [
        {"cortexParts": [{"type": "cortex_brewing", "status": "brewing"}], "followUp": None},
        {"cortexParts": [{"type": "cortex_insight", "status": "complete", "insight": "Done"}], "followUp": {"text": "Follow up text"}},
    ]

    async def fake_fetch_followup_state(*, message_id, conversation_id, stream_id):
        _ = message_id, conversation_id, stream_id
        if states:
            return states.pop(0)
        return None

    bridge._fetch_followup_state = fake_fetch_followup_state  # type: ignore[assignment]

    await bridge._poll_for_followup(stream_id=stream_id, chat_id=chat_id)
    # NOTE: _send_followup_text now passes raw markdown; Telegram bot renders to MarkdownV2.
    assert len(messages) == 1
    assert messages[0][0] == 101
    assert "Follow up text" in messages[0][1] or "Follow" in messages[0][1]


# === VIVENTIUM START ===
@pytest.mark.asyncio
async def test_send_followup_text_once_dedupes_concurrent_paths():
    bridge = _make_bridge()
    messages = []

    async def on_message(chat_id, text):
        messages.append((chat_id, text))
        await asyncio.sleep(0.02)

    bridge.set_on_message_callback(on_message)
    stream_id = "stream-race"

    await asyncio.gather(
        bridge._send_followup_text_once("909", "Path A follow-up", stream_id=stream_id),
        bridge._send_followup_text_once("909", "Path B follow-up", stream_id=stream_id),
    )

    assert len(messages) == 1
    assert messages[0][0] == 909
# === VIVENTIUM END ===


@pytest.mark.asyncio
async def test_poll_for_followup_waits_when_cortex_seen_but_no_parts():
    bridge = _make_bridge()
    messages = []

    async def on_message(chat_id, text):
        messages.append((chat_id, text))

    bridge.set_on_message_callback(on_message)
    stream_id = "stream-2"
    chat_id = "202:999"
    bridge._set_active_stream(chat_id, stream_id)
    bridge._set_stream_identity(
        stream_id=stream_id,
        telegram_chat_id="202",
        telegram_user_id="user-1",
        telegram_username="tester",
    )
    bridge._response_message_ids[stream_id] = "msg-2"
    bridge._conversation_by_stream[stream_id] = "conv-2"
    bridge._mark_cortex_seen(stream_id)
    bridge.followup_interval_s = 0.01
    bridge.followup_timeout_s = 0.2
    bridge.followup_grace_s = 0.05

    states = [
        {"cortexParts": [], "followUp": None},
        {"cortexParts": [], "followUp": {"text": "Late follow up"}},
    ]

    async def fake_fetch_followup_state(*, message_id, conversation_id, stream_id):
        _ = message_id, conversation_id, stream_id
        if states:
            return states.pop(0)
        return None

    bridge._fetch_followup_state = fake_fetch_followup_state  # type: ignore[assignment]

    await bridge._poll_for_followup(stream_id=stream_id, chat_id=chat_id)
    # NOTE: _send_followup_text now converts to MarkdownV2 via render_telegram_markdown
    assert len(messages) == 1
    assert messages[0][0] == 202
    assert "Late follow up" in messages[0][1] or "Late" in messages[0][1]


@pytest.mark.asyncio
async def test_poll_for_followup_sends_canonical_text_when_hold_was_replaced():
    bridge = _make_bridge()
    messages = []

    async def on_message(chat_id, text):
        messages.append((chat_id, text))

    bridge.set_on_message_callback(on_message)
    stream_id = "stream-canonical"
    chat_id = "606"
    bridge._set_active_stream(chat_id, stream_id)
    bridge._response_message_ids[stream_id] = "msg-canonical"
    bridge._conversation_by_stream[stream_id] = "conv-canonical"
    bridge._stream_text_by_stream[stream_id] = "Checking now."
    bridge._brief_main_reply_by_stream[stream_id] = True
    bridge.followup_interval_s = 0.01
    bridge.followup_timeout_s = 0.2
    bridge.followup_grace_s = 0.05

    async def fake_fetch_followup_state(*, message_id, conversation_id, stream_id):
        _ = message_id, conversation_id, stream_id
        return {"cortexParts": [], "followUp": None, "canonicalText": "Real final answer"}

    bridge._fetch_followup_state = fake_fetch_followup_state  # type: ignore[assignment]

    await bridge._poll_for_followup(stream_id=stream_id, chat_id=chat_id)

    assert len(messages) == 1
    assert messages[0][0] == 606
    assert "Real final answer" in messages[0][1]


@pytest.mark.asyncio
async def test_poll_for_followup_skips_canonical_text_when_already_streamed():
    bridge = _make_bridge()
    messages = []

    async def on_message(chat_id, text):
        messages.append((chat_id, text))

    bridge.set_on_message_callback(on_message)
    stream_id = "stream-canonical-same"
    chat_id = "707"
    bridge._set_active_stream(chat_id, stream_id)
    bridge._response_message_ids[stream_id] = "msg-canonical-same"
    bridge._conversation_by_stream[stream_id] = "conv-canonical-same"
    bridge._stream_text_by_stream[stream_id] = "Already delivered reply"
    bridge._brief_main_reply_by_stream[stream_id] = True
    bridge.followup_interval_s = 0.01
    bridge.followup_timeout_s = 0.05
    bridge.followup_grace_s = 0.02

    async def fake_fetch_followup_state(*, message_id, conversation_id, stream_id):
        _ = message_id, conversation_id, stream_id
        return {
            "cortexParts": [],
            "followUp": None,
            "canonicalText": "Already delivered reply",
        }

    bridge._fetch_followup_state = fake_fetch_followup_state  # type: ignore[assignment]

    await bridge._poll_for_followup(stream_id=stream_id, chat_id=chat_id)

    assert messages == []


@pytest.mark.asyncio
async def test_send_followup_text_prefers_stream_identity_chat_id():
    bridge = _make_bridge()
    messages = []

    async def on_message(chat_id, text):
        messages.append((chat_id, text))

    bridge.set_on_message_callback(on_message)
    stream_id = "stream-3"
    bridge._set_stream_identity(
        stream_id=stream_id,
        telegram_chat_id="303",
        telegram_user_id="user-2",
        telegram_username="tester",
    )

    await bridge._send_followup_text("303:777", "Hello", stream_id=stream_id)
    # NOTE: _send_followup_text now converts to MarkdownV2 via render_telegram_markdown
    assert len(messages) == 1
    assert messages[0][0] == 303
    assert "Hello" in messages[0][1]


@pytest.mark.asyncio
async def test_send_followup_text_parses_composite_chat_id():
    bridge = _make_bridge()
    messages = []

    async def on_message(chat_id, text):
        messages.append((chat_id, text))

    bridge.set_on_message_callback(on_message)
    await bridge._send_followup_text("404:555", "Hello", stream_id="stream-4")
    # NOTE: _send_followup_text now converts to MarkdownV2 via render_telegram_markdown
    assert len(messages) == 1
    assert messages[0][0] == 404
    assert "Hello" in messages[0][1]


@pytest.mark.asyncio
async def test_send_followup_text_splits_long_proactive_messages():
    bridge = _make_bridge()
    messages = []

    async def on_message(chat_id, text, parse_mode=None, voice_audio=None):
        messages.append((chat_id, text, parse_mode, voice_audio))

    bridge.set_on_message_callback(on_message)
    long_text = "\n\n".join(
        [
            f"Section {index}: " + ("word " * 180)
            for index in range(1, 5)
        ]
    )

    await bridge._send_followup_text("505:666", long_text, stream_id="stream-5")

    assert len(messages) > 1
    assert all(message[0] == 505 for message in messages)
    assert all(message[2] == "HTML" for message in messages)
    assert all(message[3] is None for message in messages)
    assert all(len(message[1]) < 4096 for message in messages)
