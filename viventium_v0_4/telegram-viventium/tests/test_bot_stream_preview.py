import asyncio
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BOT_DIR = ROOT / "TelegramVivBot"

if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))
MD2TGMD_SRC_DIR = str(BOT_DIR / "md2tgmd" / "src")
sys.path[:] = [path for path in sys.path if path != MD2TGMD_SRC_DIR]

_fake_pil = types.ModuleType("PIL")
_fake_pil_image = types.ModuleType("PIL.Image")
_fake_pil.Image = _fake_pil_image
sys.modules.setdefault("PIL", _fake_pil)
sys.modules.setdefault("PIL.Image", _fake_pil_image)

# Some lightweight utility tests install a minimal `config` stub in sys.modules.
# This module imports the real bot, so clear that stub before bot import.
if "config" in sys.modules and not hasattr(sys.modules["config"], "__file__"):
    sys.modules.pop("config", None)
if "md2tgmd" in sys.modules and not hasattr(sys.modules["md2tgmd"], "__path__"):
    sys.modules.pop("md2tgmd", None)

import bot as tg_bot  # noqa: E402
from utils.librechat_bridge import TelegramLinkRequired  # noqa: E402
from utils import orchestration as orchestration_module  # noqa: E402


class _Msg:
    def __init__(self, mid: int) -> None:
        self.message_id = mid


class _FakeTelegramBot:
    def __init__(self) -> None:
        self.messages = []
        self.edits = []
        self.audios = []
        self.deletes = []
        self._messages_by_id = {}
        self.next_id = 1000

    async def send_chat_action(self, **_kwargs):
        return None

    async def send_message(self, **kwargs):
        self.messages.append(kwargs)
        self.next_id += 1
        self._messages_by_id[self.next_id] = kwargs
        return _Msg(self.next_id)

    async def edit_message_text(self, **kwargs):
        self.edits.append(kwargs)
        return None

    async def delete_message(self, **_kwargs):
        self.deletes.append(_kwargs)
        sent = self._messages_by_id.pop(_kwargs.get("message_id"), None)
        if sent in self.messages:
            self.messages.remove(sent)
        return None

    async def send_media_group(self, **_kwargs):
        return None

    async def send_audio(self, **_kwargs):
        self.audios.append(_kwargs)
        return None

    async def send_document(self, **_kwargs):
        return None


class _FailingGetMeBot(_FakeTelegramBot):
    async def get_me(self, **_kwargs):
        raise TimeoutError("synthetic get_me timeout")


class _FakeContext:
    def __init__(self) -> None:
        self.bot = _FakeTelegramBot()


class _FakeJobQueue:
    def __init__(self) -> None:
        self.jobs = []

    def run_once(self, *args, **kwargs):
        self.jobs.append((args, kwargs))


class _FakeCommandContext:
    def __init__(self) -> None:
        self.bot = _FailingGetMeBot()
        self.args = []
        self.job_queue = _FakeJobQueue()


def _make_message_info(*, voice_error_text=None):
    return (
        None,
        None,
        None,
        "chat-1",
        123,
        None,
        None,
        None,
        "chat-1:user-1",
        None,
        None,
        None,
        voice_error_text,
        [],
    )


def _telegram_update_for_filter(message):
    return types.SimpleNamespace(
        message=message,
        effective_message=message,
        edited_message=None,
        channel_post=None,
        edited_channel_post=None,
        callback_query=None,
    )


def test_telegram_attachment_filters_accept_broad_documents_and_audio():
    pptx_message = types.SimpleNamespace(
        text=None,
        caption="review this",
        document=types.SimpleNamespace(
            file_name="deck.pptx",
            mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ),
        photo=None,
        audio=None,
        video=None,
        voice=None,
        video_note=None,
        entities=None,
        caption_entities=None,
    )
    zip_message = types.SimpleNamespace(
        text=None,
        caption=None,
        document=types.SimpleNamespace(file_name="archive.zip", mime_type="application/zip"),
        photo=None,
        audio=None,
        video=None,
        voice=None,
        video_note=None,
        entities=None,
        caption_entities=None,
    )
    audio_message = types.SimpleNamespace(
        text=None,
        caption=None,
        document=None,
        photo=None,
        audio=types.SimpleNamespace(file_name="voiceover.mp3", mime_type="audio/mpeg"),
        video=None,
        voice=None,
        video_note=None,
        entities=None,
        caption_entities=None,
    )

    assert tg_bot._telegram_captioned_attachment_filter().check_update(
        _telegram_update_for_filter(pptx_message)
    )
    assert tg_bot._telegram_uncaptioned_attachment_filter().check_update(
        _telegram_update_for_filter(zip_message)
    )
    assert tg_bot._telegram_uncaptioned_attachment_filter().check_update(
        _telegram_update_for_filter(audio_message)
    )


def test_registered_telegram_ingress_and_control_handlers_are_nonblocking():
    class _RecordingApplication:
        def __init__(self):
            self.handlers = []
            self.error_handlers = []

        def add_handler(self, handler):
            self.handlers.append(handler)

        def add_error_handler(self, handler):
            self.error_handlers.append(handler)

    application = _RecordingApplication()

    tg_bot._register_application_handlers(application)

    assert application.handlers
    assert all(handler.block is False for handler in application.handlers)
    assert any(
        isinstance(handler, tg_bot.CallbackQueryHandler)
        and handler.callback is tg_bot.button_press
        for handler in application.handlers
    )
    assert any(
        isinstance(handler, tg_bot.MessageHandler)
        and handler.callback is tg_bot.handle_file
        for handler in application.handlers
    )

    captioned_message = types.SimpleNamespace(
        text=None,
        caption="review this",
        document=types.SimpleNamespace(file_name="deck.pptx", mime_type="application/octet-stream"),
        photo=None,
        audio=None,
        video=None,
        voice=None,
        video_note=None,
        entities=None,
        caption_entities=None,
    )
    uncaptioned_message = types.SimpleNamespace(
        text=None,
        caption=None,
        document=types.SimpleNamespace(file_name="archive.zip", mime_type="application/zip"),
        photo=None,
        audio=None,
        video=None,
        voice=None,
        video_note=None,
        entities=None,
        caption_entities=None,
    )
    captioned_matches = [
        handler
        for handler in application.handlers
        if isinstance(handler, tg_bot.MessageHandler)
        and handler.filters.check_update(_telegram_update_for_filter(captioned_message))
    ]
    uncaptioned_matches = [
        handler
        for handler in application.handlers
        if isinstance(handler, tg_bot.MessageHandler)
        and handler.filters.check_update(_telegram_update_for_filter(uncaptioned_message))
    ]

    assert len(captioned_matches) == 1
    assert captioned_matches[0].block is False
    assert uncaptioned_matches == [
        handler
        for handler in application.handlers
        if isinstance(handler, tg_bot.MessageHandler)
        and handler.callback is tg_bot.handle_file
    ]
    assert all(handler.block is False for handler in uncaptioned_matches)
    assert application.error_handlers == [tg_bot.error]


class _FakeEffectiveChat:
    id = "chat-1"


class _FakeEffectiveUser:
    id = "user-1"
    username = "sampleuser"


class _FakeCommandUpdate:
    effective_chat = _FakeEffectiveChat()
    effective_user = _FakeEffectiveUser()


def _make_command_message_info():
    return (
        None,
        None,
        None,
        "chat-1",
        777,
        None,
        None,
        None,
        "chat-1:user-1",
        None,
        None,
        None,
        None,
        [],
    )


def test_info_schedules_cleanup_without_blocking_or_deleting_menu(monkeypatch):
    tg_bot._PENDING_INFO_CALL_REFRESHES.clear()
    scheduled_deletes = []
    scheduled_background = []
    first_button_calls = []

    async def _fake_get_message_info(*_args, **_kwargs):
        return _make_command_message_info()

    def _fake_first_buttons(convo_id, **kwargs):
        first_button_calls.append((convo_id, kwargs))
        return [[tg_bot.InlineKeyboardButton("Preferences", callback_data="PREFERENCES")]]

    def _fake_delete(update, context, messageids, delay=60):
        scheduled_deletes.append((messageids, delay))
        return None

    def _fake_background(context, coroutine, update=None, name=None):
        scheduled_background.append(name)
        coroutine.close()
        return None

    monkeypatch.setattr(tg_bot, "GetMesageInfo", _fake_get_message_info)
    monkeypatch.setattr(tg_bot.config, "ADMIN_LIST", None)
    monkeypatch.setattr(tg_bot.config, "BLACK_LIST", None)
    monkeypatch.setattr(tg_bot.config, "GROUP_LIST", None)
    monkeypatch.setattr(tg_bot.config, "whitelist", None)
    monkeypatch.setattr(tg_bot, "update_info_message", lambda _convo_id: "Cognitive System: Viventium")
    monkeypatch.setattr(tg_bot, "update_first_buttons_message", _fake_first_buttons)
    monkeypatch.setattr(tg_bot, "schedule_delete_message", _fake_delete)
    monkeypatch.setattr(tg_bot, "schedule_background_task", _fake_background)

    try:
        asyncio.run(asyncio.wait_for(tg_bot.info(_FakeCommandUpdate(), _FakeContext()), timeout=0.25))

        assert scheduled_deletes == [([777], 60)]
        assert scheduled_background == ["telegram-refresh-info-call-button"]
        assert first_button_calls == [("chat-1:user-1", {"fetch_call_url": False})]
        assert ("chat-1", 1001) in tg_bot._PENDING_INFO_CALL_REFRESHES
    finally:
        tg_bot._PENDING_INFO_CALL_REFRESHES.clear()


def test_call_button_refresh_does_not_overwrite_after_preferences_navigation(monkeypatch):
    tg_bot._PENDING_INFO_CALL_REFRESHES.clear()
    context = _FakeContext()
    tg_bot._mark_info_call_refresh("chat-1", 1001)

    def _fake_call_link(_convo_id):
        tg_bot._PENDING_INFO_CALL_REFRESHES.discard(("chat-1", 1001))
        return {"url": "http://198.51.100.25:3300/?ok=1"}

    monkeypatch.setattr(tg_bot, "get_telegram_call_link_result", _fake_call_link)

    try:
        asyncio.run(
            tg_bot.refresh_call_button_message(
                context,
                "chat-1",
                1001,
                "chat-1:user-1",
                "Cognitive System: Viventium",
            )
        )

        assert context.bot.edits == []
    finally:
        tg_bot._PENDING_INFO_CALL_REFRESHES.clear()


def test_deliver_proactive_telegram_message_keeps_text_canonical_and_voice_additive():
    bot = _FakeTelegramBot()

    asyncio.run(
        tg_bot.deliver_proactive_telegram_message(
            bot,
            chat_id=321,
            text="**Bold** follow-up",
            parse_mode="MarkdownV2",
            voice_audio=b"voice-bytes",
        )
    )

    assert len(bot.messages) == 1
    assert bot.messages[0]["chat_id"] == 321
    assert bot.messages[0]["parse_mode"] == "HTML"
    assert "<b>Bold</b>" in bot.messages[0]["text"]

    assert len(bot.audios) == 1
    assert bot.audios[0]["chat_id"] == 321
    assert bot.audios[0]["title"] == "Voice"
    assert bot.audios[0]["audio"].getvalue() == b"voice-bytes"


def test_deliver_proactive_telegram_message_falls_back_to_text_when_voice_send_fails():
    class _FailingVoiceBot(_FakeTelegramBot):
        async def send_audio(self, **_kwargs):
            raise RuntimeError("audio failed")

    bot = _FailingVoiceBot()

    asyncio.run(
        tg_bot.deliver_proactive_telegram_message(
            bot,
            chat_id=654,
            text="Plain follow-up",
            parse_mode=None,
            voice_audio=b"voice-bytes",
        )
    )

    assert len(bot.messages) == 1
    assert bot.messages[0]["chat_id"] == 654
    assert "Plain follow-up" in bot.messages[0]["text"]


def test_resolve_voice_input_message_aborts_without_transcription_preview():
    context = _FakeContext()

    message, aborted = asyncio.run(
        tg_bot._resolve_voice_input_message(
            context,
            chatid=321,
            messageid=654,
            message_thread_id=None,
            message=None,
            voice_text=None,
            voice_error_text="This video note is too large to transcribe in Telegram right now.",
        )
    )

    assert message is None
    assert aborted is True
    assert len(context.bot.messages) == 1
    assert context.bot.messages[0]["text"] == "This video note is too large to transcribe in Telegram right now."
    assert "🎤 Transcription" not in context.bot.messages[0]["text"]


def test_resolve_voice_input_message_passes_successful_transcription():
    context = _FakeContext()

    message, aborted = asyncio.run(
        tg_bot._resolve_voice_input_message(
            context,
            chatid=321,
            messageid=654,
            message_thread_id=None,
            message=None,
            voice_text="hello world",
            voice_error_text=None,
        )
    )

    assert message == "hello world"
    assert aborted is False
    assert len(context.bot.messages) == 1
    assert "🎤 Transcription" in context.bot.messages[0]["text"]


def test_resolve_voice_input_message_keeps_caption_when_media_fails():
    context = _FakeContext()

    message, aborted = asyncio.run(
        tg_bot._resolve_voice_input_message(
            context,
            chatid=321,
            messageid=654,
            message_thread_id=None,
            message="caption text",
            voice_text=None,
            voice_error_text="Temporarily unable to transcribe this video note. Please retry.",
        )
    )

    assert message == "caption text"
    assert aborted is False
    assert len(context.bot.messages) == 1
    assert context.bot.messages[0]["text"] == "Temporarily unable to transcribe this video note. Please retry."


class _FakeUser:
    id = 12345
    username = "sampleuser"


class _FakeChat:
    type = "private"


class _FakeUpdateMessage:
    def __init__(self) -> None:
        self.from_user = types.SimpleNamespace(
            id=_FakeUser.id,
            username=_FakeUser.username,
            first_name="Sample",
            is_bot=False,
        )
        self.chat = _FakeChat()
        self.date = datetime.now(timezone.utc)
        self.reply_text_calls = []
        self.reply_to_message = None
        self.voice = None
        self.video_note = None
        self.audio = None

    async def reply_text(self, *args, **kwargs):
        self.reply_text_calls.append((args, kwargs))


class _FakeRobot:
    async def ask_stream_async(self, *args, **kwargs):
        _ = args, kwargs
        yield "Yeah"
        yield "Yeah, what's the quick question?"

    def reset(self, *args, **kwargs):
        _ = args, kwargs


class _LinkRequiredRobot:
    async def ask_stream_async(self, *args, **kwargs):
        _ = args, kwargs
        raise TelegramLinkRequired(
            "http://localhost:3190/api/viventium/telegram/link/test-token",
            "Link your Viventium account to use Telegram.",
        )
        yield  # pragma: no cover

    def reset(self, *args, **kwargs):
        _ = args, kwargs


def test_get_viventium_response_always_voice_stays_text_mode_with_audio(monkeypatch):
    class _CaptureRobot:
        def __init__(self) -> None:
            self.kwargs = None

        async def ask_stream_async(self, *args, **kwargs):
            _ = args
            self.kwargs = kwargs
            yield "Hello [laughter]"

        def get_cached_voice_route(self, _key):
            return None

        def reset(self, *args, **kwargs):
            _ = args, kwargs

    async def _noop_send_librechat_attachments(**_kwargs):
        return None

    async def _fake_synthesize(_text, _convo_id, *, voice_route=None):
        _ = voice_route
        return b"voice-bytes"

    monkeypatch.setattr(
        tg_bot,
        "Users",
        types.SimpleNamespace(
            get_config=lambda _convo_id, key: (
                True if key in {"ALWAYS_VOICE_RESPONSE", "VOICE_RESPONSES_ENABLED"} else ""
            ),
        ),
    )
    monkeypatch.setattr(tg_bot, "send_librechat_attachments", _noop_send_librechat_attachments)
    monkeypatch.setattr(tg_bot, "synthesize_speech", _fake_synthesize)
    monkeypatch.setattr(
        tg_bot,
        "resolve_tts_selection",
        lambda *, voice_route=None: {"provider": "xai", "source": "test", "variant": "Eve"},
    )

    robot = _CaptureRobot()
    context = _FakeContext()

    asyncio.run(
        tg_bot.getViventiumResponse(
            update_message=_FakeUpdateMessage(),
            context=context,
            title="",
            robot=robot,
            message="reply with audio",
            chatid=111,
            messageid=222,
            convo_id="chat-1",
            message_thread_id=None,
            voice_note_detected=False,
            files=None,
            trace_id="test-always-voice-text-mode",
            telegram_message_id=222,
            telegram_update_id=333,
        )
    )

    assert robot.kwargs["voice_mode"] is False
    assert robot.kwargs["input_mode"] == "text"
    assert len(context.bot.audios) == 1
    rendered = " ".join(str(item.get("text", "")) for item in context.bot.messages + context.bot.edits)
    assert "[laughter]" not in rendered


# === VIVENTIUM START ===
# Regression: nested Telegram HTML formatting must never expose renderer placeholders.
def test_get_viventium_response_resolves_nested_blockquote_formatting(monkeypatch):
    class _NestedBlockquoteRobot:
        async def ask_stream_async(self, *args, **kwargs):
            _ = args, kwargs
            yield (
                "**Not the primary wedge.** **Build durable agency.**\n\n"
                "> **Agency compounds.**"
            )

        def get_cached_voice_route(self, _key):
            return None

        def reset(self, *args, **kwargs):
            _ = args, kwargs

    async def _noop_send_librechat_attachments(**_kwargs):
        return None

    monkeypatch.setattr(
        tg_bot,
        "Users",
        types.SimpleNamespace(get_config=lambda *_args, **_kwargs: False),
    )
    monkeypatch.setattr(tg_bot, "send_librechat_attachments", _noop_send_librechat_attachments)

    context = _FakeContext()
    asyncio.run(
        tg_bot.getViventiumResponse(
            update_message=_FakeUpdateMessage(),
            context=context,
            title="",
            robot=_NestedBlockquoteRobot(),
            message="give me the core recommendation",
            chatid=111,
            messageid=222,
            convo_id="chat-1",
            message_thread_id=None,
            voice_note_detected=False,
            files=None,
            trace_id="test-nested-blockquote-formatting",
            telegram_message_id=222,
            telegram_update_id=333,
        )
    )

    rendered = " ".join(
        str(item.get("text", ""))
        for item in context.bot.messages + context.bot.edits
    )
    assert "<blockquote><b>Agency compounds.</b></blockquote>" in rendered
    assert "\x00PH" not in rendered
# === VIVENTIUM END ===


def test_get_viventium_response_skip_voice_sends_full_text_without_tts(monkeypatch):
    class _SkipVoiceRobot:
        async def ask_stream_async(self, *args, **kwargs):
            _ = args, kwargs
            yield "Here is **the draft** for qa@example.com.\n{SKIP_VOICE}"

        def get_cached_voice_route(self, _key):
            return None

        def reset(self, *args, **kwargs):
            _ = args, kwargs

    synthesized = []

    async def _fake_synthesize(text, _convo_id, *, voice_route=None):
        synthesized.append((text, voice_route))
        return b"voice-bytes"

    async def _noop_send_librechat_attachments(**_kwargs):
        return None

    monkeypatch.setattr(
        tg_bot,
        "Users",
        types.SimpleNamespace(get_config=lambda *_a, **_k: True),
    )
    monkeypatch.setattr(tg_bot, "send_librechat_attachments", _noop_send_librechat_attachments)
    monkeypatch.setattr(tg_bot, "synthesize_speech", _fake_synthesize)

    context = _FakeContext()
    asyncio.run(
        tg_bot.getViventiumResponse(
            update_message=_FakeUpdateMessage(),
            context=context,
            title="",
            robot=_SkipVoiceRobot(),
            message="rewrite this email",
            chatid=111,
            messageid=222,
            convo_id="chat-1",
            message_thread_id=None,
            voice_note_detected=False,
            files=None,
            trace_id="test-skip-voice",
            telegram_message_id=222,
            telegram_update_id=333,
        )
    )

    rendered = " ".join(str(item.get("text", "")) for item in context.bot.messages + context.bot.edits)
    assert "the draft" in rendered
    assert "qa@example.com" in rendered
    assert "SKIP_VOICE" not in rendered
    assert synthesized == []
    assert context.bot.audios == []


def test_optional_text_audio_preference_has_smart_user_facing_label():
    assert tg_bot.config.PREFERENCE_DISPLAY_NAMES["ALWAYS_VOICE_RESPONSE"] == (
        "Smart voice for text"
    )


def test_get_viventium_response_message_break_sends_two_bubbles_and_one_audio(monkeypatch):
    class _MessageBreakRobot:
        async def ask_stream_async(self, *args, **kwargs):
            _ = args, kwargs
            yield "First thought.\n{MSG_"
            yield "BREAK}\nSecond thought."

        def get_cached_voice_route(self, _key):
            return None

        def reset(self, *args, **kwargs):
            _ = args, kwargs

    synthesized = []

    async def _fake_synthesize(text, _convo_id, *, voice_route=None):
        synthesized.append(text)
        return b"voice-bytes"

    async def _noop_send_librechat_attachments(**_kwargs):
        return None

    monkeypatch.setattr(
        tg_bot,
        "Users",
        types.SimpleNamespace(get_config=lambda *_a, **_k: True),
    )
    monkeypatch.setattr(tg_bot, "send_librechat_attachments", _noop_send_librechat_attachments)
    monkeypatch.setattr(tg_bot, "synthesize_speech", _fake_synthesize)
    monkeypatch.setattr(
        tg_bot,
        "resolve_tts_selection",
        lambda *, voice_route=None: {"provider": "xai", "source": "test", "variant": "Eve"},
    )

    context = _FakeContext()
    asyncio.run(
        tg_bot.getViventiumResponse(
            update_message=_FakeUpdateMessage(),
            context=context,
            title="",
            robot=_MessageBreakRobot(),
            message="give me a natural update",
            chatid=111,
            messageid=222,
            convo_id="chat-1",
            message_thread_id=None,
            voice_note_detected=False,
            files=None,
            trace_id="test-message-break",
            telegram_message_id=222,
            telegram_update_id=333,
        )
    )

    delivered = context.bot.messages + context.bot.edits
    assert len(context.bot.messages) == 2
    assert all("MSG_" not in str(item.get("text", "")) for item in delivered)
    assert "First thought." in str(context.bot.messages[0]["text"])
    assert "Second thought." in str(context.bot.messages[-1]["text"])
    assert context.bot.edits == []
    assert len(context.bot.deletes) == 1
    assert synthesized == ["First thought. Second thought."]
    assert len(context.bot.audios) == 1


def test_get_viventium_response_does_not_voice_transport_bridge_errors(monkeypatch):
    class _BridgeErrorRobot:
        async def ask_stream_async(self, *args, **kwargs):
            _ = args, kwargs
            yield {
                "type": "bridge_error",
                "text": "Response stream expired during reconnect. Please send the message again.",
                "speak": False,
            }

        def get_cached_voice_route(self, _key):
            return None

        def reset(self, *args, **kwargs):
            _ = args, kwargs

    async def _noop_send_librechat_attachments(**_kwargs):
        return None

    async def _fake_synthesize(_text, _convo_id, *, voice_route=None):
        _ = voice_route
        return b"voice-bytes"

    monkeypatch.setattr(
        tg_bot,
        "Users",
        types.SimpleNamespace(
            get_config=lambda _convo_id, key: (
                True if key in {"ALWAYS_VOICE_RESPONSE", "VOICE_RESPONSES_ENABLED"} else ""
            ),
        ),
    )
    monkeypatch.setattr(tg_bot, "send_librechat_attachments", _noop_send_librechat_attachments)
    monkeypatch.setattr(tg_bot, "synthesize_speech", _fake_synthesize)
    monkeypatch.setattr(
        tg_bot,
        "resolve_tts_selection",
        lambda *, voice_route=None: {"provider": "xai", "source": "test", "variant": "Eve"},
    )

    context = _FakeContext()

    asyncio.run(
        tg_bot.getViventiumResponse(
            update_message=_FakeUpdateMessage(),
            context=context,
            title="",
            robot=_BridgeErrorRobot(),
            message="reply with audio",
            chatid=111,
            messageid=222,
            convo_id="chat-1",
            message_thread_id=None,
            voice_note_detected=False,
            files=None,
            trace_id="test-bridge-error-no-voice",
            telegram_message_id=222,
            telegram_update_id=333,
        )
    )

    rendered = " ".join(str(item.get("text", "")) for item in context.bot.messages + context.bot.edits)
    assert "Response stream expired during reconnect" in rendered
    assert context.bot.audios == []


def test_get_viventium_response_voice_note_stays_text_mode_with_voice_note_input(monkeypatch):
    class _CaptureRobot:
        def __init__(self) -> None:
            self.kwargs = None

        async def ask_stream_async(self, *args, **kwargs):
            _ = args
            self.kwargs = kwargs
            yield "Voice note received."

        def get_cached_voice_route(self, _key):
            return None

        def reset(self, *args, **kwargs):
            _ = args, kwargs

    async def _noop_send_librechat_attachments(**_kwargs):
        return None

    async def _fake_synthesize(_text, _convo_id, *, voice_route=None):
        _ = voice_route
        return b"voice-bytes"

    monkeypatch.setattr(
        tg_bot,
        "Users",
        types.SimpleNamespace(
            get_config=lambda _convo_id, key: (
                False if key == "ALWAYS_VOICE_RESPONSE" else True
            ),
        ),
    )
    monkeypatch.setattr(tg_bot, "send_librechat_attachments", _noop_send_librechat_attachments)
    monkeypatch.setattr(tg_bot, "synthesize_speech", _fake_synthesize)
    monkeypatch.setattr(
        tg_bot,
        "resolve_tts_selection",
        lambda *, voice_route=None: {"provider": "xai", "source": "test", "variant": "Eve"},
    )

    robot = _CaptureRobot()
    context = _FakeContext()

    asyncio.run(
        tg_bot.getViventiumResponse(
            update_message=_FakeUpdateMessage(),
            context=context,
            title="",
            robot=robot,
            message="transcribed voice note",
            chatid=111,
            messageid=222,
            convo_id="chat-1",
            message_thread_id=None,
            voice_note_detected=True,
            files=None,
            trace_id="test-voice-note-text-mode",
            telegram_message_id=222,
            telegram_update_id=333,
        )
    )

    assert robot.kwargs["voice_mode"] is False
    assert robot.kwargs["input_mode"] == "voice_note"
    assert len(context.bot.audios) == 1


def test_get_viventium_response_stream_preview_flush_no_unbound(monkeypatch):
    async def _noop_send_librechat_attachments(**_kwargs):
        return None

    monkeypatch.setattr(
        tg_bot,
        "Users",
        types.SimpleNamespace(get_config=lambda *_a, **_k: False),
    )
    monkeypatch.setattr(tg_bot, "should_send_voice_reply", lambda **_k: False)
    monkeypatch.setattr(tg_bot, "send_librechat_attachments", _noop_send_librechat_attachments)

    update_message = _FakeUpdateMessage()
    context = _FakeContext()

    asyncio.run(
        tg_bot.getViventiumResponse(
            update_message=update_message,
            context=context,
            title="",
            robot=_FakeRobot(),
            message="quick question",
            chatid=111,
            messageid=222,
            convo_id="chat-1",
            message_thread_id=None,
            voice_note_detected=False,
            files=None,
            trace_id="test-stream-preview",
            telegram_message_id=222,
            telegram_update_id=333,
        )
    )

    delivered_texts = [str(item.get("text", "")) for item in context.bot.messages]
    delivered_texts.extend(str(item.get("text", "")) for item in context.bot.edits)

    assert len(context.bot.messages) == 1
    assert any("Yeah, what's the quick question?" in text for text in delivered_texts)
    assert all("stream_preview_task" not in text for text in delivered_texts)


def test_get_viventium_response_stream_preview_single_message_with_edits(monkeypatch):
    class _SlowRobot:
        async def ask_stream_async(self, *args, **kwargs):
            _ = args, kwargs
            yield "Yo"
            await asyncio.sleep(0.12)
            yield ". Late night"
            await asyncio.sleep(0.12)
            yield " grind?"

        def reset(self, *args, **kwargs):
            _ = args, kwargs

    async def _noop_send_librechat_attachments(**_kwargs):
        return None

    monkeypatch.setattr(
        tg_bot,
        "Users",
        types.SimpleNamespace(get_config=lambda *_a, **_k: False),
    )
    monkeypatch.setattr(tg_bot, "should_send_voice_reply", lambda **_k: False)
    monkeypatch.setattr(tg_bot, "send_librechat_attachments", _noop_send_librechat_attachments)
    monkeypatch.setattr(tg_bot.config, "VIVENTIUM_TELEGRAM_STREAM_EDIT_INTERVAL_S", 0.1)

    update_message = _FakeUpdateMessage()
    context = _FakeContext()

    asyncio.run(
        tg_bot.getViventiumResponse(
            update_message=update_message,
            context=context,
            title="",
            robot=_SlowRobot(),
            message="yo",
            chatid=111,
            messageid=222,
            convo_id="chat-1",
            message_thread_id=None,
            voice_note_detected=False,
            files=None,
            trace_id="test-stream-preview-edits",
            telegram_message_id=222,
            telegram_update_id=333,
        )
    )

    delivered_texts = [str(item.get("text", "")) for item in context.bot.messages]
    delivered_texts.extend(str(item.get("text", "")) for item in context.bot.edits)

    assert len(context.bot.messages) == 1
    assert len(context.bot.edits) >= 1
    assert any("Yo. Late night grind?" in text for text in delivered_texts)
    assert all("stream_preview_task" not in text for text in delivered_texts)


def test_get_viventium_response_supersedes_preview_then_sends_ordered_final_segments(monkeypatch):
    class _SegmentRobot:
        def __init__(self):
            self.acks = []

        async def ask_stream_async(self, *args, **kwargs):
            _ = args, kwargs
            yield {"type": "logical_turn", "logical_turn_id": "turn-1", "revision": 3}
            yield "Draft preview.\n{MSG_BREAK}\nFinal continuation."

        async def ack_delivery(self, *args):
            self.acks.append(args)
            return True

        def reset(self, *args, **kwargs):
            _ = args, kwargs

    async def _noop_send_librechat_attachments(**_kwargs):
        return None

    monkeypatch.setattr(tg_bot, "Users", types.SimpleNamespace(get_config=lambda *_a, **_k: False))
    monkeypatch.setattr(tg_bot, "should_send_voice_reply", lambda **_k: False)
    monkeypatch.setattr(tg_bot, "send_librechat_attachments", _noop_send_librechat_attachments)
    context = _FakeContext()
    robot = _SegmentRobot()

    asyncio.run(
        tg_bot.getViventiumResponse(
            update_message=_FakeUpdateMessage(),
            context=context,
            title="",
            robot=robot,
            message="synthetic request",
            chatid=111,
            messageid=222,
            convo_id="chat-1",
            message_thread_id=None,
            trace_id="test-preview-supersession",
            telegram_message_id=222,
            telegram_update_id=333,
        )
    )

    assert len(context.bot.deletes) == 1
    assert [item["text"] for item in context.bot.messages[-2:]] == [
        "Draft preview.",
        "Final continuation.",
    ]
    assert context.bot.messages[-2]["reply_to_message_id"] == 222
    assert "reply_to_message_id" not in context.bot.messages[-1]
    assert robot.acks == [
        ("turn-1", 3, "committed", f"telegram:111:{context.bot.next_id}"),
    ]


def test_get_viventium_response_delete_failure_does_not_replace_success_with_connection_error(monkeypatch):
    class _DeleteFailBot(_FakeTelegramBot):
        async def delete_message(self, **kwargs):
            self.deletes.append(kwargs)
            raise ConnectionError("synthetic stale preview delete failure")

    class _SegmentRobot:
        async def ask_stream_async(self, *args, **kwargs):
            _ = args, kwargs
            yield "First final.\n{MSG_BREAK}\nSecond final."

        def reset(self, *args, **kwargs):
            _ = args, kwargs

    async def _noop_send_librechat_attachments(**_kwargs):
        return None

    monkeypatch.setattr(tg_bot, "Users", types.SimpleNamespace(get_config=lambda *_a, **_k: False))
    monkeypatch.setattr(tg_bot, "should_send_voice_reply", lambda **_k: False)
    monkeypatch.setattr(tg_bot, "send_librechat_attachments", _noop_send_librechat_attachments)
    context = _FakeContext()
    context.bot = _DeleteFailBot()

    asyncio.run(
        tg_bot.getViventiumResponse(
            update_message=_FakeUpdateMessage(),
            context=context,
            title="",
            robot=_SegmentRobot(),
            message="synthetic request",
            chatid=111,
            messageid=222,
            convo_id="chat-1",
            message_thread_id=None,
            trace_id="test-preview-delete-failure",
            telegram_message_id=222,
            telegram_update_id=333,
        )
    )

    delivered = [str(item.get("text") or "") for item in context.bot.messages]
    assert delivered[-2:] == ["First final.", "Second final."]
    assert not any("Connection error" in text for text in delivered)
    assert not any("stale preview delete failure" in text for text in delivered)


def test_get_viventium_response_superseded_terminal_retracts_preview_without_error(monkeypatch):
    class _SupersededRobot:
        def __init__(self):
            self.acks = []

        async def ask_stream_async(self, *args, **kwargs):
            _ = args, kwargs
            yield {"type": "logical_turn", "logical_turn_id": "turn-1", "revision": 1}
            yield "Unfinished preview."
            await asyncio.sleep(0.02)
            yield {"type": "superseded", "logical_turn_id": "turn-1", "revision": 1}

        async def ack_delivery(self, *args):
            self.acks.append(args)
            return True

        def reset(self, *args, **kwargs):
            _ = args, kwargs

    async def _noop_send_librechat_attachments(**_kwargs):
        return None

    monkeypatch.setattr(tg_bot, "Users", types.SimpleNamespace(get_config=lambda *_a, **_k: False))
    monkeypatch.setattr(tg_bot, "should_send_voice_reply", lambda **_k: False)
    monkeypatch.setattr(tg_bot, "send_librechat_attachments", _noop_send_librechat_attachments)
    context = _FakeContext()
    robot = _SupersededRobot()

    asyncio.run(
        tg_bot.getViventiumResponse(
            update_message=_FakeUpdateMessage(),
            context=context,
            title="",
            robot=robot,
            message="synthetic first segment",
            chatid=111,
            messageid=222,
            convo_id="chat-1",
            message_thread_id=None,
            trace_id="test-core-superseded",
            telegram_message_id=222,
            telegram_update_id=333,
        )
    )

    assert context.bot.deletes
    assert not any("Connection error" in str(item.get("text") or "") for item in context.bot.messages)
    assert not any("No response received" in str(item.get("text") or "") for item in context.bot.messages)
    assert robot.acks == [("turn-1", 1, "partial_removed", "telegram:111")]


def test_get_viventium_response_recoverable_error_stays_pending_without_commit_ack(monkeypatch):
    class _RecoveringRobot:
        def __init__(self):
            self.acks = []

        async def ask_stream_async(self, *args, **kwargs):
            _ = args, kwargs
            yield {"type": "logical_turn", "logical_turn_id": "turn-1", "revision": 1}
            yield {
                "type": "bridge_error",
                "text": "The model provider could not complete this request.",
                "speak": False,
                "error_class": "completion_error",
                "recoverable": True,
            }

        async def ack_delivery(self, *args):
            self.acks.append(args)
            return True

        def reset(self, *args, **kwargs):
            _ = args, kwargs

    async def _noop_send_librechat_attachments(**_kwargs):
        return None

    monkeypatch.setattr(tg_bot, "Users", types.SimpleNamespace(get_config=lambda *_a, **_k: False))
    monkeypatch.setattr(tg_bot, "should_send_voice_reply", lambda **_k: False)
    monkeypatch.setattr(tg_bot, "send_librechat_attachments", _noop_send_librechat_attachments)
    context = _FakeContext()
    robot = _RecoveringRobot()

    asyncio.run(
        tg_bot.getViventiumResponse(
            update_message=_FakeUpdateMessage(),
            context=context,
            title="",
            robot=robot,
            message="synthetic request",
            chatid=111,
            messageid=222,
            convo_id="chat-1",
            message_thread_id=None,
            trace_id="test-recoverable-pending",
            telegram_message_id=222,
            telegram_update_id=333,
        )
    )

    assert context.bot.messages == []
    assert robot.acks == []


def test_get_viventium_response_superseded_delete_failure_reports_failed_not_removed(monkeypatch):
    class _DeleteFailBot(_FakeTelegramBot):
        async def delete_message(self, **kwargs):
            self.deletes.append(kwargs)
            raise ConnectionError("synthetic stale preview delete failure")

    class _SupersededRobot:
        def __init__(self):
            self.acks = []

        async def ask_stream_async(self, *args, **kwargs):
            _ = args, kwargs
            yield {"type": "logical_turn", "logical_turn_id": "turn-1", "revision": 1}
            yield "Unfinished preview."
            await asyncio.sleep(0.02)
            yield {"type": "superseded", "logical_turn_id": "turn-1", "revision": 1}

        async def ack_delivery(self, *args):
            self.acks.append(args)
            return True

        def reset(self, *args, **kwargs):
            _ = args, kwargs

    async def _noop_send_librechat_attachments(**_kwargs):
        return None

    monkeypatch.setattr(tg_bot, "Users", types.SimpleNamespace(get_config=lambda *_a, **_k: False))
    monkeypatch.setattr(tg_bot, "should_send_voice_reply", lambda **_k: False)
    monkeypatch.setattr(tg_bot, "send_librechat_attachments", _noop_send_librechat_attachments)
    context = _FakeContext()
    context.bot = _DeleteFailBot()
    robot = _SupersededRobot()

    asyncio.run(
        tg_bot.getViventiumResponse(
            update_message=_FakeUpdateMessage(),
            context=context,
            title="",
            robot=robot,
            message="synthetic first segment",
            chatid=111,
            messageid=222,
            convo_id="chat-1",
            message_thread_id=None,
            trace_id="test-core-superseded-delete-failure",
            telegram_message_id=222,
            telegram_update_id=333,
        )
    )

    assert robot.acks == [("turn-1", 1, "failed", "telegram:111")]
    assert not any("Connection error" in str(item.get("text") or "") for item in context.bot.messages)


def test_get_viventium_response_retracts_just_sent_final_when_commit_ack_is_stale(monkeypatch):
    class _StaleAtCommitRobot:
        def __init__(self):
            self.acks = []

        async def ask_stream_async(self, *args, **kwargs):
            _ = args, kwargs
            yield {"type": "logical_turn", "logical_turn_id": "turn-1", "revision": 1}
            yield "Finished locally but obsolete before Telegram commit."

        async def ack_delivery_status(self, *args):
            self.acks.append(args)
            return "stale_revision"

        def reset(self, *args, **kwargs):
            _ = args, kwargs

    async def _noop_send_librechat_attachments(**_kwargs):
        return None

    monkeypatch.setattr(tg_bot, "Users", types.SimpleNamespace(get_config=lambda *_a, **_k: False))
    monkeypatch.setattr(tg_bot, "should_send_voice_reply", lambda **_k: False)
    monkeypatch.setattr(tg_bot, "send_librechat_attachments", _noop_send_librechat_attachments)
    context = _FakeContext()
    robot = _StaleAtCommitRobot()

    asyncio.run(
        tg_bot.getViventiumResponse(
            update_message=_FakeUpdateMessage(),
            context=context,
            title="",
            robot=robot,
            message="synthetic first segment",
            chatid=111,
            messageid=222,
            convo_id="chat-1",
            message_thread_id=None,
            trace_id="test-stale-at-commit",
            telegram_message_id=222,
            telegram_update_id=333,
        )
    )

    assert robot.acks == [
        ("turn-1", 1, "committed", "telegram:111:1001"),
    ]
    assert context.bot.deletes[-1] == {"chat_id": 111, "message_id": 1001}
    assert context.bot.messages == []


def test_get_viventium_response_passes_stable_opaque_source_event_id(monkeypatch):
    class _CaptureRobot:
        def __init__(self):
            self.kwargs = None

        async def ask_stream_async(self, *args, **kwargs):
            _ = args
            self.kwargs = kwargs
            yield "Done."

        def reset(self, *args, **kwargs):
            _ = args, kwargs

    async def _noop_send_librechat_attachments(**_kwargs):
        return None

    monkeypatch.setattr(tg_bot, "Users", types.SimpleNamespace(get_config=lambda *_a, **_k: False))
    monkeypatch.setattr(tg_bot, "should_send_voice_reply", lambda **_k: False)
    monkeypatch.setattr(tg_bot, "send_librechat_attachments", _noop_send_librechat_attachments)
    robot = _CaptureRobot()

    asyncio.run(
        tg_bot.getViventiumResponse(
            update_message=_FakeUpdateMessage(),
            context=_FakeContext(),
            title="",
            robot=robot,
            message="synthetic request",
            chatid=111,
            messageid=222,
            convo_id="chat-1",
            message_thread_id=None,
            trace_id="test-source-event",
            telegram_message_id=222,
            telegram_update_id=333,
        )
    )

    assert robot.kwargs["source_event_id"] == "telegram:chat:111:message:222"
    assert "actor_kind" not in robot.kwargs
    assert "origin" not in robot.kwargs
    assert "supersede_scope" not in robot.kwargs


def test_get_viventium_response_surfaces_link_prompt(monkeypatch):
    async def _noop_send_librechat_attachments(**_kwargs):
        return None

    monkeypatch.setattr(
        tg_bot,
        "Users",
        types.SimpleNamespace(get_config=lambda *_a, **_k: False),
    )
    monkeypatch.setattr(tg_bot, "should_send_voice_reply", lambda **_k: False)
    monkeypatch.setattr(tg_bot, "send_librechat_attachments", _noop_send_librechat_attachments)

    update_message = _FakeUpdateMessage()
    context = _FakeContext()

    asyncio.run(
        tg_bot.getViventiumResponse(
            update_message=update_message,
            context=context,
            title="",
            robot=_LinkRequiredRobot(),
            message="hi",
            chatid=111,
            messageid=222,
            convo_id="chat-1",
            message_thread_id=None,
            voice_note_detected=False,
            files=None,
            trace_id="test-link-required",
            telegram_message_id=222,
            telegram_update_id=333,
        )
    )

    assert len(context.bot.messages) == 1
    sent_text = str(context.bot.messages[0].get("text", ""))
    assert "Please link your Viventium account to continue" in sent_text
    assert "telegram/link/test\\-token" in sent_text


def test_get_viventium_response_final_tts_prefers_conversation_voice_route(monkeypatch):
    saved_route = {
        "tts": {
            "provider": "cartesia",
            "variant": "voice-id",
        }
    }
    seen = {}

    class _RouteRobot:
        async def ask_stream_async(self, *args, **kwargs):
            _ = args, kwargs
            yield "Hello [laughter]"

        def get_cached_voice_route(self, key):
            return saved_route if key == "chat-1:user-1" else None

        def reset(self, *args, **kwargs):
            _ = args, kwargs

    async def _noop_send_librechat_attachments(**_kwargs):
        return None

    async def _fake_synthesize(text, convo_id, *, voice_route=None):
        seen["tts_text"] = text
        seen["convo_id"] = convo_id
        seen["voice_route"] = voice_route
        return b"voice-bytes"

    def _fake_resolve_tts_selection(*, voice_route=None):
        seen["resolved_voice_route"] = voice_route
        return {"provider": "cartesia", "variant": "voice-id", "source": "saved"}

    monkeypatch.setattr(
        tg_bot,
        "Users",
        types.SimpleNamespace(get_config=lambda *_a, **_k: True),
    )
    monkeypatch.setattr(tg_bot, "should_send_voice_reply", lambda **_k: True)
    monkeypatch.setattr(tg_bot, "send_librechat_attachments", _noop_send_librechat_attachments)
    monkeypatch.setattr(tg_bot, "synthesize_speech", _fake_synthesize)
    monkeypatch.setattr(tg_bot, "resolve_tts_selection", _fake_resolve_tts_selection)

    update_message = _FakeUpdateMessage()
    context = _FakeContext()

    asyncio.run(
        tg_bot.getViventiumResponse(
            update_message=update_message,
            context=context,
            title="",
            robot=_RouteRobot(),
            message="voice please",
            chatid="raw-chat",
            messageid=222,
            convo_id="chat-1:user-1",
            message_thread_id=None,
            voice_note_detected=True,
            files=None,
            trace_id="test-final-tts-route-cache",
            telegram_message_id=222,
            telegram_update_id=333,
        )
    )

    assert seen["voice_route"] == saved_route
    assert seen["resolved_voice_route"] == saved_route
    assert seen["convo_id"] == "chat-1:user-1"
    assert seen["tts_text"] == "Hello [laughter]"
    assert len(context.bot.audios) == 1


def test_get_viventium_response_xai_tts_does_not_split_wrapped_text(monkeypatch):
    saved_route = {
        "tts": {
            "provider": "xai",
            "variant": "Eve",
        }
    }
    long_wrapped_text = "<whisper>" + ("this xAI line should stay together. " * 40) + "</whisper>"
    seen = {"chunks": []}

    class _RouteRobot:
        async def ask_stream_async(self, *args, **kwargs):
            _ = args, kwargs
            yield long_wrapped_text

        def get_cached_voice_route(self, key):
            return saved_route if key == "chat-1:user-1" else None

        def reset(self, *args, **kwargs):
            _ = args, kwargs

    async def _noop_send_librechat_attachments(**_kwargs):
        return None

    async def _fake_synthesize(text, convo_id, *, voice_route=None):
        seen["chunks"].append(text)
        seen["convo_id"] = convo_id
        seen["voice_route"] = voice_route
        return b"voice-bytes"

    def _fake_resolve_tts_selection(*, voice_route=None):
        seen["resolved_voice_route"] = voice_route
        return {"provider": "xai", "variant": "Eve", "source": "saved"}

    monkeypatch.setattr(
        tg_bot,
        "Users",
        types.SimpleNamespace(get_config=lambda *_a, **_k: True),
    )
    monkeypatch.setattr(tg_bot, "should_send_voice_reply", lambda **_k: True)
    monkeypatch.setattr(tg_bot, "send_librechat_attachments", _noop_send_librechat_attachments)
    monkeypatch.setattr(tg_bot, "synthesize_speech", _fake_synthesize)
    monkeypatch.setattr(tg_bot, "resolve_tts_selection", _fake_resolve_tts_selection)

    update_message = _FakeUpdateMessage()
    context = _FakeContext()

    asyncio.run(
        tg_bot.getViventiumResponse(
            update_message=update_message,
            context=context,
            title="",
            robot=_RouteRobot(),
            message="voice please",
            chatid="raw-chat",
            messageid=222,
            convo_id="chat-1:user-1",
            message_thread_id=None,
            voice_note_detected=True,
            files=None,
            trace_id="test-final-xai-tts-no-split",
            telegram_message_id=222,
            telegram_update_id=333,
        )
    )

    assert seen["voice_route"] == saved_route
    assert seen["resolved_voice_route"] == saved_route
    assert seen["convo_id"] == "chat-1:user-1"
    assert seen["chunks"] == [long_wrapped_text]
    assert len(context.bot.audios) == 1


def test_handle_file_does_not_forward_failed_transcription(monkeypatch):
    forwarded_calls = []

    async def _fake_handle_get_message_info(*_args, **_kwargs):
        return _make_message_info(
            voice_error_text="Temporarily unable to transcribe this video note. Please retry."
        )

    async def _fake_get_viventium_response(*args, **kwargs):
        forwarded_calls.append((args, kwargs))
        return None

    monkeypatch.setattr(tg_bot, "GetMesageInfo", _fake_handle_get_message_info)
    monkeypatch.setattr(tg_bot, "getViventiumResponse", _fake_get_viventium_response)
    monkeypatch.setattr(tg_bot.config, "BLACK_LIST", None, raising=False)
    monkeypatch.setattr(tg_bot.config, "whitelist", None, raising=False)
    monkeypatch.setattr(tg_bot.config, "GROUP_LIST", None, raising=False)
    monkeypatch.setattr(tg_bot.config, "ADMIN_LIST", None, raising=False)
    monkeypatch.setattr(
        tg_bot.config,
        "get_robot",
        lambda _convo_id: ("robot", None, "api-key", "http://localhost:3180"),
        raising=False,
    )

    update = types.SimpleNamespace(
        effective_user=types.SimpleNamespace(id="user-1", username="user"),
        effective_chat=None,
    )
    context = _FakeContext()

    asyncio.run(tg_bot.handle_file(update, context))

    assert forwarded_calls == []
    assert len(context.bot.messages) == 1
    assert context.bot.messages[0]["text"] == "Temporarily unable to transcribe this video note. Please retry."
    assert "🎤 Transcription" not in context.bot.messages[0]["text"]


def test_handle_file_reports_attachment_capture_error(monkeypatch):
    forwarded_calls = []

    async def _fake_get_message_info(*_args, **_kwargs):
        return (
            "review this",
            "review this",
            None,
            "chat-1",
            123,
            None,
            types.SimpleNamespace(chat=types.SimpleNamespace(type="private")),
            None,
            "chat-1:user-1",
            None,
            None,
            None,
            None,
            [],
            [
                {
                    "filename": "deck.pptx",
                    "mime_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    "error_code": "download_timeout",
                    "media_kind": "document",
                }
            ],
        )

    async def _fake_get_viventium_response(*args, **kwargs):
        forwarded_calls.append((args, kwargs))
        return None

    monkeypatch.setattr(tg_bot, "GetMesageInfo", _fake_get_message_info)
    monkeypatch.setattr(tg_bot, "getViventiumResponse", _fake_get_viventium_response)
    monkeypatch.setattr(tg_bot.config, "BLACK_LIST", None, raising=False)
    monkeypatch.setattr(tg_bot.config, "whitelist", None, raising=False)
    monkeypatch.setattr(tg_bot.config, "GROUP_LIST", None, raising=False)
    monkeypatch.setattr(tg_bot.config, "ADMIN_LIST", None, raising=False)

    update = types.SimpleNamespace(
        effective_user=types.SimpleNamespace(id="user-1", username="user"),
        effective_chat=None,
    )
    context = _FakeContext()

    asyncio.run(tg_bot.handle_file(update, context))

    assert forwarded_calls == []
    assert len(context.bot.messages) == 1
    assert "deck.pptx" in context.bot.messages[0]["text"]
    assert "timed out" in context.bot.messages[0]["text"]


def test_media_group_coalesces_files_into_one_viventium_call(monkeypatch):
    forwarded_calls = []

    def _message(mid, *, caption=None):
        return types.SimpleNamespace(
            message_id=mid,
            chat_id="chat-1",
            chat=types.SimpleNamespace(type="private"),
            from_user=types.SimpleNamespace(id="user-1", first_name="User", username="user"),
            media_group_id="album-1",
            is_topic_message=False,
            message_thread_id=None,
            caption=caption,
            text=None,
            voice=None,
            video_note=None,
            audio=None,
            document=types.SimpleNamespace(file_name=f"file-{mid}.jpg", mime_type="image/jpeg"),
            photo=None,
            video=None,
            date=datetime.now(timezone.utc),
        )

    update1 = types.SimpleNamespace(
        update_id=1001,
        effective_user=types.SimpleNamespace(id="user-1", username="user"),
        effective_chat=types.SimpleNamespace(id="chat-1"),
        effective_message=_message(1),
    )
    update2 = types.SimpleNamespace(
        update_id=1002,
        effective_user=types.SimpleNamespace(id="user-1", username="user"),
        effective_chat=types.SimpleNamespace(id="chat-1"),
        effective_message=_message(2, caption="review album"),
    )

    async def _fake_get_message_info(update, *_args, **_kwargs):
        msg = update.effective_message
        text = msg.caption
        return (
            text,
            text,
            None,
            "chat-1",
            msg.message_id,
            None,
            msg,
            None,
            "chat-1:user-1",
            None,
            None,
            None,
            None,
            [{"filename": f"file-{msg.message_id}.jpg", "mime_type": "image/jpeg", "data": "ZmFrZQ=="}],
            [],
        )

    async def _fake_get_viventium_response(*args, **kwargs):
        forwarded_calls.append((args, kwargs))
        return None

    monkeypatch.setattr(tg_bot.config, "VIVENTIUM_TELEGRAM_MEDIA_GROUP_WAIT_S", 0.01, raising=False)
    monkeypatch.setattr(tg_bot, "GetMesageInfo", _fake_get_message_info)
    monkeypatch.setattr(tg_bot, "getViventiumResponse", _fake_get_viventium_response)
    monkeypatch.setattr(tg_bot, "get_robot", lambda _convo_id: (_FakeRobot(), None, None, None))
    monkeypatch.setattr(tg_bot.config, "BLACK_LIST", None, raising=False)
    monkeypatch.setattr(tg_bot.config, "whitelist", None, raising=False)
    monkeypatch.setattr(tg_bot.config, "GROUP_LIST", None, raising=False)
    monkeypatch.setattr(tg_bot.config, "ADMIN_LIST", None, raising=False)
    monkeypatch.setattr(tg_bot.config, "get_robot", lambda _convo_id: (_FakeRobot(), None, None, None), raising=False)

    async def _run():
        tg_bot._MEDIA_GROUP_BUFFERS.clear()
        for task in list(tg_bot._MEDIA_GROUP_TASKS.values()):
            task.cancel()
        tg_bot._MEDIA_GROUP_TASKS.clear()
        await tg_bot.command_bot(update1, _FakeCommandContext(), has_command=False)
        await tg_bot.command_bot(update2, _FakeCommandContext(), has_command=False)
        tasks = list(tg_bot._MEDIA_GROUP_TASKS.values())
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            failures = [result for result in results if isinstance(result, Exception)]
            assert failures == []

    asyncio.run(_run())

    assert len(forwarded_calls) == 1
    args, kwargs = forwarded_calls[0]
    assert args[4] == "review album"
    assert kwargs["telegram_message_id"] == 2
    assert [file["filename"] for file in kwargs["files"]] == ["file-1.jpg", "file-2.jpg"]


def test_command_bot_get_me_timeout_without_reply_does_not_crash(monkeypatch):
    update_message = _FakeUpdateMessage()
    message_info = (
        "hello",
        "hello",
        None,
        "chat-1",
        42,
        None,
        update_message,
        None,
        "chat-1:user-1",
        None,
        None,
        None,
        None,
        [],
    )
    forwarded = []

    async def _fake_get_message_info(*_args, **_kwargs):
        return message_info

    async def _fake_get_viventium_response(*args, **kwargs):
        forwarded.append((args, kwargs))
        return None

    monkeypatch.setattr(tg_bot, "GetMesageInfo", _fake_get_message_info)
    monkeypatch.setattr(tg_bot, "getViventiumResponse", _fake_get_viventium_response)
    monkeypatch.setattr(tg_bot.config, "BLACK_LIST", None, raising=False)
    monkeypatch.setattr(tg_bot.config, "whitelist", None, raising=False)
    monkeypatch.setattr(tg_bot.config, "GROUP_LIST", None, raising=False)
    monkeypatch.setattr(tg_bot.config, "ADMIN_LIST", None, raising=False)
    monkeypatch.setattr(
        tg_bot,
        "Users",
        types.SimpleNamespace(get_config=lambda *_args, **_kwargs: False),
    )
    monkeypatch.setattr(
        tg_bot.config,
        "Users",
        types.SimpleNamespace(get_config=lambda *_args, **_kwargs: False),
        raising=False,
    )
    monkeypatch.setattr(tg_bot, "get_robot", lambda _convo_id: (_FakeRobot(), None, None, None))
    monkeypatch.setattr(tg_bot.config, "get_robot", lambda _convo_id: (_FakeRobot(), None, None, None), raising=False)
    monkeypatch.setattr(tg_bot, "remove_job_if_exists", lambda *_args, **_kwargs: None)

    update = types.SimpleNamespace(
        update_id=99,
        effective_user=types.SimpleNamespace(id="user-1", username="sampleuser"),
        effective_chat=types.SimpleNamespace(id="chat-1"),
    )
    context = _FakeCommandContext()

    asyncio.run(tg_bot.command_bot(update, context, has_command=False))

    assert len(forwarded) == 1
    assert context.job_queue.jobs


def test_error_handler_does_not_log_raw_update_text(caplog):
    class _PrivateUpdate:
        update_id = 123
        effective_message = types.SimpleNamespace(message_id=456)

        def __str__(self):
            return "PRIVATE MESSAGE TEXT SHOULD NOT BE LOGGED"

    context = types.SimpleNamespace(error=RuntimeError("synthetic failure"))

    with caplog.at_level("WARNING"):
        asyncio.run(tg_bot.error(_PrivateUpdate(), context))

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "PRIVATE MESSAGE TEXT" not in log_text
    assert "update_id=123" in log_text
    assert "message_id=456" in log_text


# === VIVENTIUM START ===
# Tests: Telegram Parallel Work account preference, cards, and capability-scoped controls.
def _parallel_snapshot(*, enabled=False, state="fresh", actions=None, items=True, has_more=False):
    preference = {
        "available": True,
        "mode": "parallel" if enabled else "focused",
    }
    work = {
        "snapshot": state,
        "work": None if state == "unavailable" else [],
        "overflowCount": None if state == "unavailable" else (2 if has_more else 0),
    }
    if items:
        work["work"] = [
            {
                "workRef": "ghw_private-ref:1",
                "title": "Research durable workers",
                "state": "running",
                "statusSummary": "Checking restart safety.",
                "updatedAt": "2026-08-12T14:59:00Z",
                "actions": actions or ["message", "pause"],
            }
        ]
    return orchestration_module.parse_snapshot(preference, work)


class _ParallelClient:
    def __init__(self, snapshot=None, error=None):
        self.snapshot = snapshot or _parallel_snapshot()
        self.error = error
        self.get_calls = []
        self.set_calls = []
        self.action_calls = []

    async def get_snapshot(self, user_id, *, cursor=""):
        self.get_calls.append((user_id, cursor) if cursor else user_id)
        if self.error:
            raise self.error
        return self.snapshot

    async def get_preference(self, user_id):
        self.get_calls.append(user_id)
        if self.error:
            raise self.error
        return self.snapshot

    async def set_parallel_work(self, user_id, enabled):
        self.set_calls.append((user_id, enabled))
        if self.error:
            raise self.error
        return self.snapshot

    async def act(self, user_id, work_ref, action, *, instruction=None, operation_id):
        self.action_calls.append(
            (user_id, work_ref, action, instruction, operation_id)
        )
        if self.error:
            raise self.error
        return self.snapshot


class _ParallelCallbackQuery:
    def __init__(self, data, *, user_id="user-1", chat_id="chat-1", message_id=901):
        self.data = data
        self.from_user = types.SimpleNamespace(id=user_id)
        self.message = types.SimpleNamespace(
            chat_id=chat_id,
            message_id=message_id,
            message_thread_id=None,
            is_topic_message=False,
        )
        self.answers = 0
        self.text_edits = []
        self.markup_edits = []

    async def answer(self):
        self.answers += 1

    async def edit_message_text(self, **kwargs):
        self.text_edits.append(kwargs)

    async def edit_message_reply_markup(self, **kwargs):
        self.markup_edits.append(kwargs)


def _parallel_callback_update(data, *, user_id="user-1", chat_id="chat-1"):
    query = _ParallelCallbackQuery(data, user_id=user_id, chat_id=chat_id)
    update = types.SimpleNamespace(
        callback_query=query,
        effective_user=query.from_user,
        effective_chat=types.SimpleNamespace(id=chat_id),
    )
    return update, query


def _flatten_keyboard(markup):
    return [button for row in markup.inline_keyboard for button in row]


def test_parallel_work_menu_buttons_are_hidden_when_unavailable_and_need_no_model_call():
    hidden_main = tg_bot._main_menu_buttons(
        "chat-1:user-1", fetch_call_url=False, parallel_available=False
    )
    hidden_preferences = tg_bot._preferences_menu_buttons(
        "chat-1:user-1", parallel_available=False
    )
    main_buttons = tg_bot._main_menu_buttons(
        "chat-1:user-1", fetch_call_url=False, parallel_available=True
    )
    preference_buttons = tg_bot._preferences_menu_buttons(
        "chat-1:user-1", parallel_available=True
    )

    assert not any(
        str(getattr(button, "callback_data", "") or "").startswith("PW:")
        for row in hidden_main + hidden_preferences
        for button in row
    )

    assert any(
        button.text == "Active work" and button.callback_data == "PW:L"
        for row in main_buttons
        for button in row
    )
    assert any(
        button.text == "Parallel work" and button.callback_data == "PW:S"
        for row in preference_buttons
        for button in row
    )


def test_preferences_menu_fetches_core_availability_and_hides_unavailable_feature(monkeypatch):
    unavailable = orchestration_module.parse_snapshot(
        {"available": False, "mode": "focused"}
    )
    client = _ParallelClient(snapshot=unavailable)
    monkeypatch.setattr(tg_bot, "_PARALLEL_WORK_CLIENT", client)
    update, query = _parallel_callback_update("PREFERENCES")

    asyncio.run(tg_bot.button_press(update, _FakeContext()))

    assert client.get_calls == ["user-1"]
    buttons = _flatten_keyboard(query.markup_edits[-1]["reply_markup"])
    assert not any(
        str(getattr(button, "callback_data", "") or "").startswith("PW:")
        for button in buttons
    )


def test_stale_parallel_control_reports_unavailable_then_hides_feature_controls(monkeypatch):
    unavailable = orchestration_module.parse_snapshot(
        {"available": False, "mode": "focused"}
    )
    monkeypatch.setattr(tg_bot, "_PARALLEL_WORK_CLIENT", _ParallelClient(snapshot=unavailable))
    update, query = _parallel_callback_update("PW:S")

    asyncio.run(tg_bot.button_press(update, _FakeContext()))

    assert "unavailable" in query.text_edits[-1]["text"].lower()
    buttons = _flatten_keyboard(query.text_edits[-1]["reply_markup"])
    assert not any(
        str(getattr(button, "callback_data", "") or "").startswith("PW:")
        for button in buttons
    )


def test_active_work_cards_use_only_server_action_mask_and_opaque_callback_tokens(monkeypatch, tmp_path):
    store = orchestration_module.CallbackCapabilityStore(tmp_path / "callbacks.sqlite3")
    monkeypatch.setattr(tg_bot, "_PARALLEL_WORK_CALLBACK_STORE", store)
    snapshot = _parallel_snapshot(
        enabled=False,
        actions=["message", "pause"],
        has_more=True,
    )

    text, markup = tg_bot._active_work_view(snapshot, telegram_user_id="user-1", chat_id="chat-1")
    buttons = _flatten_keyboard(markup)
    action_buttons = [button for button in buttons if button.callback_data.startswith("PW:A:")]

    assert "Parallel work: Off" in text
    assert "Research durable workers" in text
    assert "2 more active items are not shown" in text
    assert [button.text for button in action_buttons] == ["1 · Message", "1 · Pause"]
    assert all(len(button.callback_data.encode("utf-8")) <= 64 for button in buttons)
    assert all("ghw_private-ref" not in button.callback_data for button in buttons)


def test_parallel_load_more_retries_same_saved_cursor_after_lost_response(monkeypatch, tmp_path):
    store = orchestration_module.CallbackCapabilityStore(tmp_path / "callbacks.sqlite3")
    token = store.issue_page(
        telegram_user_id="user-1",
        chat_id="chat-1",
        cursor="signed.next-page",
    )
    client = _ParallelClient(
        error=orchestration_module.OrchestrationError(
            "The page response was lost.", indeterminate=True
        )
    )
    monkeypatch.setattr(tg_bot, "_PARALLEL_WORK_CALLBACK_STORE", store)
    monkeypatch.setattr(tg_bot, "_PARALLEL_WORK_CLIENT", client)
    callback_data = orchestration_module.page_callback_data(token)
    update, query = _parallel_callback_update(callback_data)

    asyncio.run(tg_bot.button_press(update, _FakeContext()))

    retry = next(
        button
        for button in _flatten_keyboard(query.text_edits[-1]["reply_markup"])
        if button.text == "Retry Load more"
    )
    assert retry.callback_data == callback_data
    client.error = None
    retry_update, _retry_query = _parallel_callback_update(retry.callback_data)
    asyncio.run(tg_bot.button_press(retry_update, _FakeContext()))

    assert client.get_calls == [
        ("user-1", "signed.next-page"),
        ("user-1", "signed.next-page"),
    ]


def test_parallel_settings_toggle_calls_core_not_model_and_renders_account_state(monkeypatch, tmp_path):
    snapshot = _parallel_snapshot(enabled=True, items=False)
    client = _ParallelClient(snapshot=snapshot)
    monkeypatch.setattr(tg_bot, "_PARALLEL_WORK_CLIENT", client)
    monkeypatch.setattr(
        tg_bot,
        "_PARALLEL_WORK_CALLBACK_STORE",
        orchestration_module.CallbackCapabilityStore(tmp_path / "callbacks.sqlite3"),
    )
    update, query = _parallel_callback_update("PW:T:1")
    context = _FakeContext()

    asyncio.run(tg_bot.button_press(update, context))

    assert client.set_calls == [("user-1", True)]
    assert client.get_calls == []
    assert query.answers == 1
    assert "Account-wide" in query.text_edits[-1]["text"]
    assert "Status: On" in query.text_edits[-1]["text"]


def test_parallel_settings_preserves_link_required_truth_and_safe_link_action(monkeypatch, tmp_path):
    client = _ParallelClient(
        error=orchestration_module.OrchestrationLinkRequired(
            "This Telegram account is not linked to Viventium. Send /start to link it before managing Parallel work.",
        )
    )
    monkeypatch.setattr(tg_bot, "_PARALLEL_WORK_CLIENT", client)
    monkeypatch.setattr(
        tg_bot,
        "_PARALLEL_WORK_CALLBACK_STORE",
        orchestration_module.CallbackCapabilityStore(tmp_path / "callbacks.sqlite3"),
    )
    update, query = _parallel_callback_update("PW:S")

    asyncio.run(tg_bot.button_press(update, _FakeContext()))

    assert "not linked" in query.text_edits[-1]["text"]
    assert "/start" in query.text_edits[-1]["text"]
    buttons = _flatten_keyboard(query.text_edits[-1]["reply_markup"])
    assert not any(button.url for button in buttons)


def test_parallel_direct_action_uses_scoped_mapping_and_exact_work_ref(monkeypatch, tmp_path):
    store = orchestration_module.CallbackCapabilityStore(tmp_path / "callbacks.sqlite3")
    target = store.issue_actions(
        telegram_user_id="user-1",
        chat_id="chat-1",
        targets=[("ghw_private-ref:1", "pause")],
    )[0]
    client = _ParallelClient(snapshot=_parallel_snapshot(actions=["resume"]))
    monkeypatch.setattr(tg_bot, "_PARALLEL_WORK_CALLBACK_STORE", store)
    monkeypatch.setattr(tg_bot, "_PARALLEL_WORK_CLIENT", client)
    update, query = _parallel_callback_update(
        orchestration_module.action_callback_data(target.token)
    )

    asyncio.run(tg_bot.button_press(update, _FakeContext()))

    assert client.action_calls == [
        ("user-1", "ghw_private-ref:1", "pause", None, target.token)
    ]
    assert "Active work" in query.text_edits[-1]["text"]


def test_parallel_direct_action_retries_same_operation_after_lost_response(monkeypatch, tmp_path):
    store = orchestration_module.CallbackCapabilityStore(tmp_path / "callbacks.sqlite3")
    target = store.issue_actions(
        telegram_user_id="user-1",
        chat_id="chat-1",
        targets=[("private-work", "pause")],
    )[0]
    client = _ParallelClient(
        snapshot=_parallel_snapshot(actions=["resume"]),
        error=orchestration_module.OrchestrationError(
            "The response was lost.", indeterminate=True
        ),
    )
    monkeypatch.setattr(tg_bot, "_PARALLEL_WORK_CALLBACK_STORE", store)
    monkeypatch.setattr(tg_bot, "_PARALLEL_WORK_CLIENT", client)
    callback_data = orchestration_module.action_callback_data(target.token)
    update, query = _parallel_callback_update(callback_data)

    asyncio.run(tg_bot.button_press(update, _FakeContext()))

    retry = next(
        button
        for button in _flatten_keyboard(query.text_edits[-1]["reply_markup"])
        if button.text == "Retry same action"
    )
    assert retry.callback_data == callback_data
    assert "may already have accepted" in query.text_edits[-1]["text"]

    client.error = None
    retry_update, _retry_query = _parallel_callback_update(retry.callback_data)
    asyncio.run(tg_bot.button_press(retry_update, _FakeContext()))

    assert [call[4] for call in client.action_calls] == [target.token, target.token]


def test_parallel_direct_action_definitive_rejection_requires_refresh(monkeypatch, tmp_path):
    store = orchestration_module.CallbackCapabilityStore(tmp_path / "callbacks.sqlite3")
    target = store.issue_actions(
        telegram_user_id="user-1",
        chat_id="chat-1",
        targets=[("private-work", "pause")],
    )[0]
    client = _ParallelClient(
        snapshot=_parallel_snapshot(actions=["resume"]),
        error=orchestration_module.OrchestrationError(
            "The exact worker lifecycle changed. Refresh Active work."
        ),
    )
    monkeypatch.setattr(tg_bot, "_PARALLEL_WORK_CALLBACK_STORE", store)
    monkeypatch.setattr(tg_bot, "_PARALLEL_WORK_CLIENT", client)
    callback_data = orchestration_module.action_callback_data(target.token)
    update, query = _parallel_callback_update(callback_data)

    asyncio.run(tg_bot.button_press(update, _FakeContext()))

    buttons = _flatten_keyboard(query.text_edits[-1]["reply_markup"])
    assert [button.text for button in buttons] == ["Refresh Active work", "⬅️ Back"]
    assert "Retry same action" not in query.text_edits[-1]["text"]
    assert store.reserve_action(
        target.token,
        telegram_user_id="user-1",
        chat_id="chat-1",
    ) is None
    assert len(client.action_calls) == 1


def test_parallel_action_token_cannot_be_replayed_by_another_user(monkeypatch, tmp_path):
    store = orchestration_module.CallbackCapabilityStore(tmp_path / "callbacks.sqlite3")
    target = store.issue_actions(
        telegram_user_id="user-1",
        chat_id="chat-1",
        targets=[("private-work", "pause")],
    )[0]
    client = _ParallelClient()
    monkeypatch.setattr(tg_bot, "_PARALLEL_WORK_CALLBACK_STORE", store)
    monkeypatch.setattr(tg_bot, "_PARALLEL_WORK_CLIENT", client)
    update, query = _parallel_callback_update(
        orchestration_module.action_callback_data(target.token),
        user_id="user-2",
    )

    asyncio.run(tg_bot.button_press(update, _FakeContext()))

    assert client.action_calls == []
    assert "expired" in query.text_edits[-1]["text"].lower()


def test_parallel_stop_requires_confirmation_before_core_action(monkeypatch, tmp_path):
    store = orchestration_module.CallbackCapabilityStore(tmp_path / "callbacks.sqlite3")
    target = store.issue_actions(
        telegram_user_id="user-1",
        chat_id="chat-1",
        targets=[("private-work", "stop")],
    )[0]
    client = _ParallelClient(snapshot=_parallel_snapshot(items=False))
    monkeypatch.setattr(tg_bot, "_PARALLEL_WORK_CALLBACK_STORE", store)
    monkeypatch.setattr(tg_bot, "_PARALLEL_WORK_CLIENT", client)
    update, query = _parallel_callback_update(
        orchestration_module.action_callback_data(target.token)
    )

    asyncio.run(tg_bot.button_press(update, _FakeContext()))

    assert client.action_calls == []
    assert "Stop / cancel this work?" in query.text_edits[-1]["text"]
    confirm_button = next(
        button
        for button in _flatten_keyboard(query.text_edits[-1]["reply_markup"])
        if button.text == "Stop / cancel work"
    )
    confirm_update, _ = _parallel_callback_update(confirm_button.callback_data)

    asyncio.run(tg_bot.button_press(confirm_update, _FakeContext()))

    assert len(client.action_calls) == 1
    assert client.action_calls[0][2] == "stop"


def test_parallel_message_requires_force_reply_then_submits_instruction_without_model(monkeypatch, tmp_path):
    store = orchestration_module.CallbackCapabilityStore(tmp_path / "callbacks.sqlite3")
    target = store.issue_actions(
        telegram_user_id="user-1",
        chat_id="chat-1",
        targets=[("private-work", "message")],
    )[0]
    client = _ParallelClient(snapshot=_parallel_snapshot())
    monkeypatch.setattr(tg_bot, "_PARALLEL_WORK_CALLBACK_STORE", store)
    monkeypatch.setattr(tg_bot, "_PARALLEL_WORK_CLIENT", client)
    update, query = _parallel_callback_update(
        orchestration_module.action_callback_data(target.token)
    )
    context = _FakeContext()

    asyncio.run(tg_bot.button_press(update, context))

    assert client.action_calls == []
    prompt = context.bot.messages[-1]
    assert prompt["text"].startswith(tg_bot.PARALLEL_WORK_PROMPT_PREFIX)
    assert prompt["reply_markup"].force_reply is True
    prompt_message_id = context.bot.next_id
    instruction_message = types.SimpleNamespace(
        text="Check the restart race first.",
        chat_id="chat-1",
        message_id=1002,
        message_thread_id=None,
        reply_to_message=types.SimpleNamespace(
            message_id=prompt_message_id,
            text=prompt["text"],
        ),
    )
    instruction_update = types.SimpleNamespace(
        effective_user=types.SimpleNamespace(id="user-1"),
        effective_chat=types.SimpleNamespace(id="chat-1"),
        effective_message=instruction_message,
        message=instruction_message,
    )

    asyncio.run(tg_bot.parallel_work_instruction_reply(instruction_update, context))

    assert len(client.action_calls) == 1
    assert client.action_calls[0][0:4] == (
        "user-1",
        "private-work",
        "message",
        "Check the restart race first.",
    )
    assert "Active work" in context.bot.messages[-1]["text"]


def test_parallel_instruction_action_retries_saved_instruction_after_lost_response(monkeypatch, tmp_path):
    store = orchestration_module.CallbackCapabilityStore(tmp_path / "callbacks.sqlite3")
    target = store.issue_actions(
        telegram_user_id="user-1",
        chat_id="chat-1",
        targets=[("private-work", "steer")],
    )[0]
    client = _ParallelClient(
        snapshot=_parallel_snapshot(),
        error=orchestration_module.OrchestrationError(
            "The response was lost.", indeterminate=True
        ),
    )
    monkeypatch.setattr(tg_bot, "_PARALLEL_WORK_CALLBACK_STORE", store)
    monkeypatch.setattr(tg_bot, "_PARALLEL_WORK_CLIENT", client)
    context = _FakeContext()
    update, _query = _parallel_callback_update(
        orchestration_module.action_callback_data(target.token)
    )
    asyncio.run(tg_bot.button_press(update, context))
    prompt = context.bot.messages[-1]
    instruction_message = types.SimpleNamespace(
        text="Preserve this exact instruction.",
        chat_id="chat-1",
        message_id=1003,
        message_thread_id=None,
        reply_to_message=types.SimpleNamespace(text=prompt["text"]),
    )
    instruction_update = types.SimpleNamespace(
        effective_user=types.SimpleNamespace(id="user-1"),
        effective_chat=types.SimpleNamespace(id="chat-1"),
        effective_message=instruction_message,
        message=instruction_message,
    )

    asyncio.run(tg_bot.parallel_work_instruction_reply(instruction_update, context))

    retry = next(
        button
        for button in _flatten_keyboard(context.bot.messages[-1]["reply_markup"])
        if button.text == "Retry same action"
    )
    assert retry.callback_data.startswith("PW:R:")
    client.error = None
    retry_update, _retry_query = _parallel_callback_update(retry.callback_data)
    asyncio.run(tg_bot.button_press(retry_update, context))

    assert len(client.action_calls) == 2
    assert client.action_calls[0][3:] == (
        "Preserve this exact instruction.",
        client.action_calls[1][4],
    )
    assert client.action_calls[1][3] == "Preserve this exact instruction."


def test_parallel_instruction_definitive_rejection_requires_refresh(monkeypatch, tmp_path):
    store = orchestration_module.CallbackCapabilityStore(tmp_path / "callbacks.sqlite3")
    target = store.issue_actions(
        telegram_user_id="user-1",
        chat_id="chat-1",
        targets=[("private-work", "steer")],
    )[0]
    client = _ParallelClient(
        snapshot=_parallel_snapshot(),
        error=orchestration_module.OrchestrationError(
            "The exact worker lifecycle changed. Refresh Active work."
        ),
    )
    monkeypatch.setattr(tg_bot, "_PARALLEL_WORK_CALLBACK_STORE", store)
    monkeypatch.setattr(tg_bot, "_PARALLEL_WORK_CLIENT", client)
    context = _FakeContext()
    update, _query = _parallel_callback_update(
        orchestration_module.action_callback_data(target.token)
    )
    asyncio.run(tg_bot.button_press(update, context))
    prompt = context.bot.messages[-1]
    instruction_message = types.SimpleNamespace(
        text="Preserve this exact definitive instruction.",
        chat_id="chat-1",
        message_id=1004,
        message_thread_id=None,
        reply_to_message=types.SimpleNamespace(text=prompt["text"]),
    )
    instruction_update = types.SimpleNamespace(
        effective_user=types.SimpleNamespace(id="user-1"),
        effective_chat=types.SimpleNamespace(id="chat-1"),
        effective_message=instruction_message,
        message=instruction_message,
    )

    asyncio.run(tg_bot.parallel_work_instruction_reply(instruction_update, context))

    buttons = _flatten_keyboard(context.bot.messages[-1]["reply_markup"])
    assert [button.text for button in buttons] == ["Refresh Active work", "⬅️ Back"]
    assert not any(button.text == "Retry same action" for button in buttons)
    assert store.reserve_prompt_action(
        target.token,
        telegram_user_id="user-1",
        chat_id="chat-1",
    ) is None
    assert len(client.action_calls) == 1


def test_parallel_unavailable_view_is_truthful_and_actionable():
    text, markup = tg_bot._parallel_work_unavailable_view("Core is unavailable.")
    assert text == "Core is unavailable."
    assert [button.text for button in _flatten_keyboard(markup)] == [
        "Refresh Active work",
        "⬅️ Back",
    ]


def test_parallel_all_server_returned_actions_have_product_controls(monkeypatch, tmp_path):
    store = orchestration_module.CallbackCapabilityStore(tmp_path / "callbacks.sqlite3")
    monkeypatch.setattr(tg_bot, "_PARALLEL_WORK_CALLBACK_STORE", store)
    snapshot = _parallel_snapshot(
        actions=["queue", "message", "steer", "pause", "resume", "stop", "retry", "dismiss"]
    )

    _text, markup = tg_bot._active_work_view(
        snapshot,
        telegram_user_id="user-1",
        chat_id="chat-1",
    )
    action_buttons = [
        button
        for button in _flatten_keyboard(markup)
        if str(button.callback_data or "").startswith("PW:A:")
    ]

    assert [button.text for button in action_buttons] == [
        "1 · Queue",
        "1 · Message",
        "1 · Steer",
        "1 · Pause",
        "1 · Resume",
        "1 · Stop / Cancel",
        "1 · Retry",
        "1 · Dismiss",
    ]
    assert all(len(button.callback_data.encode("utf-8")) <= 64 for button in action_buttons)


def test_parallel_instruction_handler_is_nonblocking_and_precedes_normal_text_handler():
    class _RecordingApplication:
        def __init__(self):
            self.handlers = []
            self.error_handlers = []

        def add_handler(self, handler, *args, **kwargs):
            self.handlers.append(handler)

        def add_error_handler(self, handler):
            self.error_handlers.append(handler)

    application = _RecordingApplication()

    tg_bot._register_application_handlers(application)

    instruction_index = next(
        index
        for index, handler in enumerate(application.handlers)
        if isinstance(handler, tg_bot.MessageHandler)
        and handler.callback is tg_bot.parallel_work_instruction_reply
    )
    normal_index = next(
        index
        for index, handler in enumerate(application.handlers)
        if isinstance(handler, tg_bot.MessageHandler)
        and handler.callback is not tg_bot.parallel_work_instruction_reply
        and handler.callback is not tg_bot.handle_file
    )
    assert instruction_index < normal_index
    assert application.handlers[instruction_index].block is False
# === VIVENTIUM END ===
