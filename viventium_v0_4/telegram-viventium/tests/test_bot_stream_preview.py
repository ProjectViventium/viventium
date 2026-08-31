import asyncio
import base64
import hashlib
import html
import inspect
import os
import re
import stat
import subprocess
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
from utils.telegram_chunks import telegram_text_units  # noqa: E402
from utils.telegram_html import strip_html_tags  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_source_order_cache():
    tg_bot._LATEST_TELEGRAM_SOURCE_MESSAGES.clear()
    tg_bot._TELEGRAM_PRESENTATION_MUTEXES.clear()
    tg_bot._TELEGRAM_PRESENTATION_MUTEX_USERS.clear()
    tg_bot._TELEGRAM_HELD_PRESENTATION_FENCES.clear()
    yield
    tg_bot._LATEST_TELEGRAM_SOURCE_MESSAGES.clear()
    tg_bot._TELEGRAM_PRESENTATION_MUTEXES.clear()
    tg_bot._TELEGRAM_PRESENTATION_MUTEX_USERS.clear()
    tg_bot._TELEGRAM_HELD_PRESENTATION_FENCES.clear()


class _Msg:
    def __init__(self, mid: int) -> None:
        self.message_id = mid


def test_telegram_ready_marker_is_atomic_and_process_bound(tmp_path, monkeypatch):
    marker = tmp_path / "runtime" / "telegram_bot.ready"
    monkeypatch.setenv("VIVENTIUM_TELEGRAM_READY_FILE", str(marker))

    assert tg_bot._write_telegram_ready_marker() is True
    assert marker.read_text(encoding="utf-8") == f"{os.getpid()}\n"
    assert list(marker.parent.glob("telegram_bot.ready.*.tmp")) == []


@pytest.mark.asyncio
async def test_post_init_does_not_block_readiness_on_optional_bot_metadata(
    tmp_path, monkeypatch
):
    marker = tmp_path / "runtime" / "telegram_bot.ready"
    metadata_started = asyncio.Event()
    metadata_release = asyncio.Event()

    class _Bot:
        async def set_my_commands(self, _commands):
            metadata_started.set()
            await metadata_release.wait()

        async def set_my_description(self, _description):
            raise AssertionError("description must wait for commands")

    application = types.SimpleNamespace(bot=_Bot(), bot_data={})
    monkeypatch.setenv("VIVENTIUM_TELEGRAM_READY_FILE", str(marker))
    monkeypatch.setattr(tg_bot.config, "ChatGPTbot", None)

    await asyncio.wait_for(tg_bot.post_init(application), timeout=0.2)
    await asyncio.wait_for(metadata_started.wait(), timeout=0.2)

    assert marker.read_text(encoding="utf-8") == f"{os.getpid()}\n"
    assert not application.bot_data[tg_bot._BOT_METADATA_TASK_KEY].done()

    await tg_bot.post_shutdown(application)


def test_telegram_reply_context_is_typed_without_rewriting_user_text():
    replied = types.SimpleNamespace(
        message_id=91,
        text="Who signs first?",
        caption=None,
        date=datetime(2026, 8, 19, 21, 2, tzinfo=timezone.utc),
        from_user=types.SimpleNamespace(id=700, is_bot=True),
        document=None,
        audio=None,
        video=None,
        voice=None,
        animation=None,
        sticker=None,
        photo=[],
    )
    update_message = types.SimpleNamespace(reply_to_message=replied)

    assert tg_bot._telegram_reply_context_v1(update_message, bot_user_id=700) == {
        "version": 1,
        "repliedTelegramMessageId": "91",
        "quoteText": "Who signs first?",
        "senderKind": "assistant_candidate",
        "timestamp": "2026-08-19T21:02:00+00:00",
    }


def test_telegram_reply_context_marks_a_foreign_bot_as_third_party_candidate():
    replied = types.SimpleNamespace(
        message_id=92,
        text="Foreign bot text.",
        caption=None,
        date=None,
        from_user=types.SimpleNamespace(id=701, is_bot=True),
        document=None,
        audio=None,
        video=None,
        voice=None,
        animation=None,
        sticker=None,
        photo=[],
    )
    update_message = types.SimpleNamespace(
        reply_to_message=replied,
        chat=types.SimpleNamespace(type="supergroup"),
    )

    assert tg_bot._telegram_reply_context_v1(
        update_message,
        bot_user_id=700,
        current_sender_id=702,
    ) == {
        "version": 1,
        "repliedTelegramMessageId": "92",
        "quoteText": "Foreign bot text.",
        "senderKind": "external_candidate",
    }


@pytest.mark.parametrize(
    ("bot_user_id", "from_user", "sender_chat"),
    [
        (None, types.SimpleNamespace(id=701, is_bot=True), None),
        (700, None, None),
        (700, None, types.SimpleNamespace(id=-1008, type="channel")),
        (
            700,
            types.SimpleNamespace(id=1087968824, is_bot=True),
            types.SimpleNamespace(id=-1007, type="supergroup"),
        ),
    ],
    ids=[
        "missing-bot-identity",
        "missing-from-user",
        "sender-chat-only",
        "anonymous-admin-sender-chat",
    ],
)
def test_telegram_reply_context_keeps_unresolved_transport_identity_unknown(
    bot_user_id,
    from_user,
    sender_chat,
):
    replied = types.SimpleNamespace(
        message_id=95,
        text="Unresolved reply source.",
        caption=None,
        date=None,
        from_user=from_user,
        sender_chat=sender_chat,
        document=None,
        audio=None,
        video=None,
        voice=None,
        animation=None,
        sticker=None,
        photo=[],
    )
    update_message = types.SimpleNamespace(
        reply_to_message=replied,
        chat=types.SimpleNamespace(type="supergroup"),
    )

    context = tg_bot._telegram_reply_context_v1(
        update_message,
        bot_user_id=bot_user_id,
        current_sender_id=702,
    )

    assert context["senderKind"] == "unknown"


def test_telegram_reply_context_marks_the_current_sender_as_owner_candidate():
    replied = types.SimpleNamespace(
        message_id=94,
        text="My earlier note.",
        caption=None,
        date=None,
        from_user=types.SimpleNamespace(id=702, is_bot=False),
        document=None,
        audio=None,
        video=None,
        voice=None,
        animation=None,
        sticker=None,
        photo=[],
    )
    update_message = types.SimpleNamespace(reply_to_message=replied)

    assert tg_bot._telegram_reply_context_v1(
        update_message,
        bot_user_id=700,
        current_sender_id=702,
    ) == {
        "version": 1,
        "repliedTelegramMessageId": "94",
        "quoteText": "My earlier note.",
        "senderKind": "owner_candidate",
    }


def test_telegram_reply_context_carries_bounded_extracted_document_text():
    replied = types.SimpleNamespace(
        message_id=93,
        text=None,
        caption="Attached source",
        date=None,
        from_user=types.SimpleNamespace(id=700, is_bot=True),
        document=types.SimpleNamespace(file_id="doc-1", file_name="source.pdf"),
        audio=None,
        video=None,
        voice=None,
        animation=None,
        sticker=None,
        photo=[],
    )
    update_message = types.SimpleNamespace(reply_to_message=replied)

    context = tg_bot._telegram_reply_context_v1(
        update_message,
        bot_user_id=700,
        quoted_attachment_text="Document evidence",
    )

    assert context["attachments"] == [
        {
            "kind": "document",
            "fileId": "doc-1",
            "filename": "source.pdf",
            "extractedText": "Document evidence",
        }
    ]


def test_group_reply_caption_never_becomes_owner_authored_prompt_body():
    source = inspect.getsource(tg_bot.command_bot)

    assert "message = update_message.reply_to_message.caption" not in source


class _FakeTelegramBot:
    def __init__(self) -> None:
        self.messages = []
        self.edits = []
        self.audios = []
        self.deletes = []
        self.edit_error = None
        self.edit_errors = []
        self.send_errors = []
        self.sent_ids = []
        self.current_messages = {}
        self._messages_by_id = {}
        self.next_id = 1000

    async def send_chat_action(self, **_kwargs):
        return None

    async def send_message(self, **kwargs):
        if self.send_errors:
            error = self.send_errors.pop(0)
            if error:
                raise error
        self.messages.append(kwargs)
        self.next_id += 1
        self.sent_ids.append(self.next_id)
        self.current_messages[self.next_id] = kwargs
        self._messages_by_id[self.next_id] = kwargs
        return _Msg(self.next_id)

    async def edit_message_text(self, **kwargs):
        if self.edit_errors:
            error = self.edit_errors.pop(0)
            if error:
                raise error
        if self.edit_error:
            raise self.edit_error
        self.edits.append(kwargs)
        self.current_messages[kwargs["message_id"]] = kwargs
        return None

    async def delete_message(self, **_kwargs):
        self.deletes.append(_kwargs)
        sent = self._messages_by_id.pop(_kwargs.get("message_id"), None)
        self.current_messages.pop(_kwargs.get("message_id"), None)
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


def _final_delivered_texts(context):
    return [
        str(context.bot.current_messages[message_id].get("text", ""))
        for message_id in context.bot.sent_ids
        if message_id in context.bot.current_messages
    ]


def _visible_html(rendered):
    return html.unescape(re.sub(r"<[^>]+>", "", rendered))


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
    authorizations = []

    async def authorize_transport():
        authorizations.append("authorized")
        return True

    message_ids = asyncio.run(
        tg_bot.deliver_proactive_telegram_message(
            bot,
            chat_id=321,
            message_thread_id=77,
            text="**Bold** follow-up",
            parse_mode="MarkdownV2",
            voice_audio=b"voice-bytes",
            before_side_effect=authorize_transport,
        )
    )

    assert message_ids == ['1001']

    assert len(bot.messages) == 1
    assert bot.messages[0]["chat_id"] == 321
    assert bot.messages[0]["message_thread_id"] == 77
    assert bot.messages[0]["parse_mode"] == "HTML"
    assert "<b>Bold</b>" in bot.messages[0]["text"]

    assert len(bot.audios) == 1
    assert bot.audios[0]["chat_id"] == 321
    assert bot.audios[0]["message_thread_id"] == 77
    assert bot.audios[0]["title"] == "Voice"
    assert bot.audios[0]["audio"].getvalue() == b"voice-bytes"
    assert authorizations == ["authorized", "authorized"]


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


def test_resolve_voice_input_message_stops_caption_when_transcription_fails():
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

    assert message is None
    assert aborted is True
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
    async def observe_source_order(self, **kwargs):
        return {
            "latest_source_sequence": int(kwargs["source_sequence"]),
            "stale": False,
            "source_order_scope": "a" * 64,
            "source_event_id": "c" * 64,
        }

    async def source_order_is_current(self, **_kwargs):
        return True

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



@pytest.mark.parametrize(
    ("text", "delivery_event", "expected_audio_count"),
    [
        (
            "Structured skip keeps this text visible.",
            {
                "type": "delivery_disposition",
                "delivery_disposition": {
                    "version": 1,
                    "audio": "skip",
                    "required": True,
                    "valid": True,
                    "source": "model",
                },
                "required": True,
                "present": True,
            },
            0,
        ),
        (
            "Structured eligibility permits the saved voice preference.",
            {
                "type": "delivery_disposition",
                "delivery_disposition": {
                    "version": 1,
                    "audio": "eligible",
                    "required": True,
                    "valid": True,
                    "source": "model",
                },
                "required": True,
                "present": True,
            },
            1,
        ),
        (
            "Required metadata is missing, so this stays text-only.",
            {
                "type": "delivery_disposition",
                "delivery_disposition": None,
                "required": True,
                "present": False,
            },
            0,
        ),
        (
            "Legacy control still wins.\n{SKIP_VOICE}",
            {
                "type": "delivery_disposition",
                "delivery_disposition": {
                    "version": 1,
                    "audio": "eligible",
                    "required": True,
                    "valid": True,
                    "source": "model",
                },
                "required": True,
                "present": True,
            },
            0,
        ),
    ],
)
def test_get_viventium_response_applies_structured_delivery_disposition_precedence(
    monkeypatch,
    text,
    delivery_event,
    expected_audio_count,
):
    class _DispositionRobot:
        async def ask_stream_async(self, *args, **kwargs):
            _ = args, kwargs
            yield text
            yield delivery_event

        def get_cached_voice_route(self, _key):
            return None

        def reset(self, *args, **kwargs):
            _ = args, kwargs

    synthesized = []

    async def _fake_synthesize(tts_text, _convo_id, *, voice_route=None):
        synthesized.append((tts_text, voice_route))
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
        lambda *, voice_route=None: {
            "provider": "xai",
            "source": "test",
            "variant": "Eve",
        },
    )

    context = _FakeContext()
    asyncio.run(
        tg_bot.getViventiumResponse(
            update_message=_FakeUpdateMessage(),
            context=context,
            title="",
            robot=_DispositionRobot(),
            message="synthetic delivery contract check",
            chatid=111,
            messageid=222,
            convo_id="chat-1",
            message_thread_id=None,
            voice_note_detected=False,
            files=None,
            trace_id="test-structured-delivery-disposition",
            telegram_message_id=222,
            telegram_update_id=333,
        )
    )

    rendered = " ".join(
        str(item.get("text", ""))
        for item in context.bot.messages + context.bot.edits
    )
    assert "delivery_disposition" not in rendered
    assert "SKIP_VOICE" not in rendered
    assert len(synthesized) == expected_audio_count
    assert len(context.bot.audios) == expected_audio_count


def test_long_response_keeps_early_skip_voice_control(monkeypatch):
    long_prefix = ("A complete useful paragraph. " * 180).strip()

    class _LongSkipVoiceRobot:
        async def ask_stream_async(self, *args, **kwargs):
            _ = args, kwargs
            yield f"{{SKIP_VOICE}}\n{long_prefix}"
            yield "Final clean paragraph."

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
            robot=_LongSkipVoiceRobot(),
            message="prepare the long draft",
            chatid=111,
            messageid=222,
            convo_id="chat-1",
            message_thread_id=None,
            voice_note_detected=False,
            files=None,
            trace_id="test-long-skip-voice",
            telegram_message_id=222,
            telegram_update_id=333,
        )
    )

    final_texts = _final_delivered_texts(context)
    rendered = "".join(_visible_html(item) for item in final_texts)
    assert "Final clean paragraph." in rendered
    assert rendered.count("A complete useful paragraph.") == 180
    assert "SKIP_VOICE" not in rendered
    assert synthesized == []
    assert context.bot.audios == []
    assert all(telegram_text_units(item) <= 4000 for item in final_texts)


def test_message_break_transient_edit_failure_retries_without_duplicate_or_drop(monkeypatch):
    class _MessageBreakRobot:
        async def ask_stream_async(self, *args, **kwargs):
            _ = args, kwargs
            yield "First thought."
            await asyncio.sleep(0.12)
            yield "\n{MSG_BREAK}\nSecond thought."

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
        types.SimpleNamespace(get_config=lambda *_a, **_k: True),
    )
    monkeypatch.setattr(tg_bot, "send_librechat_attachments", _noop_send_librechat_attachments)
    monkeypatch.setattr(tg_bot, "synthesize_speech", _fake_synthesize)
    monkeypatch.setattr(
        tg_bot,
        "resolve_tts_selection",
        lambda *, voice_route=None: {"provider": "xai", "source": "test", "variant": "Eve"},
    )
    monkeypatch.setattr(tg_bot.config, "VIVENTIUM_TELEGRAM_STREAM_EDIT_INTERVAL_S", 0.1)

    context = _FakeContext()
    context.bot.edit_errors = [RuntimeError("synthetic flood-control")]

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
            trace_id="test-message-break-edit-failure",
            telegram_message_id=222,
            telegram_update_id=333,
        )
    )

    final_texts = _final_delivered_texts(context)
    visible = [strip_html_tags(item) for item in final_texts]
    assert visible == ["First thought.", "Second thought."]
    assert all(item.get("parse_mode") == "HTML" for item in context.bot.current_messages.values())
    assert len(context.bot.audios) == 1


def test_message_break_persistent_first_edit_failure_stops_later_delivery_and_audio(
    monkeypatch,
):
    class _MessageBreakRobot:
        async def ask_stream_async(self, *args, **kwargs):
            _ = args, kwargs
            yield "First thought.\n{MSG_BREAK}\nSecond thought."

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
        types.SimpleNamespace(get_config=lambda *_a, **_k: True),
    )
    monkeypatch.setattr(tg_bot, "send_librechat_attachments", _noop_send_librechat_attachments)
    monkeypatch.setattr(tg_bot, "synthesize_speech", _fake_synthesize)

    context = _FakeContext()
    context.bot.send_errors = [None, RuntimeError("synthetic persistent outage")]

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
            trace_id="test-message-break-persistent-edit-failure",
            telegram_message_id=222,
            telegram_update_id=333,
        )
    )

    assert len(context.bot.messages) == 1
    visible = [strip_html_tags(item) for item in _final_delivered_texts(context)]
    assert visible == [tg_bot.TELEGRAM_DELIVERY_INTERRUPTED_NOTICE]
    assert context.bot.audios == []


def test_long_response_keeps_early_message_break_and_safe_rendered_chunks(monkeypatch):
    first = ("First complete thought with `code`. " * 180).strip()

    class _LongMessageBreakRobot:
        async def ask_stream_async(self, *args, **kwargs):
            _ = args, kwargs
            yield f"{first}\n{{MSG_BREAK}}\nSecond complete thought."

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
            robot=_LongMessageBreakRobot(),
            message="give me a long two-part answer",
            chatid=111,
            messageid=222,
            convo_id="chat-1",
            message_thread_id=None,
            voice_note_detected=False,
            files=None,
            trace_id="test-long-message-break",
            telegram_message_id=222,
            telegram_update_id=333,
        )
    )

    final_texts = _final_delivered_texts(context)
    visible = "".join(_visible_html(item) for item in final_texts)
    assert visible.count("First complete thought with code.") == 180
    assert visible.endswith("Second complete thought.")
    assert "MSG_BREAK" not in visible
    assert all(telegram_text_units(item) <= 4000 for item in final_texts)
    assert len(context.bot.audios) == 1


def test_midstream_exception_delivers_partial_text_and_suppresses_audio(monkeypatch):
    class _InterruptedRobot:
        async def ask_stream_async(self, *args, **kwargs):
            _ = args, kwargs
            yield "Partial useful answer."
            raise TimeoutError("synthetic stream timeout")

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
            robot=_InterruptedRobot(),
            message="give me the answer",
            chatid=111,
            messageid=222,
            convo_id="chat-1",
            message_thread_id=None,
            voice_note_detected=False,
            files=None,
            trace_id="test-midstream-interruption",
            telegram_message_id=222,
            telegram_update_id=333,
        )
    )

    visible = " ".join(
        strip_html_tags(item)
        for item in _final_delivered_texts(context)
    )
    assert "Partial useful answer." in visible
    assert "Response interrupted before completion. Please try again." in visible
    assert "synthetic stream timeout" not in visible
    assert synthesized == []
    assert context.bot.audios == []


def test_midstream_exception_strips_an_incomplete_delivery_control_suffix(monkeypatch):
    class _InterruptedControlRobot:
        async def ask_stream_async(self, *args, **kwargs):
            _ = args, kwargs
            yield "Partial useful answer.\n{SKIP_"
            raise TimeoutError("synthetic stream timeout")

        def get_cached_voice_route(self, _key):
            return None

        def reset(self, *args, **kwargs):
            _ = args, kwargs

    async def _noop_send_librechat_attachments(**_kwargs):
        return None

    monkeypatch.setattr(
        tg_bot,
        "Users",
        types.SimpleNamespace(get_config=lambda *_a, **_k: False),
    )
    monkeypatch.setattr(tg_bot, "send_librechat_attachments", _noop_send_librechat_attachments)

    context = _FakeContext()
    asyncio.run(
        tg_bot.getViventiumResponse(
            update_message=_FakeUpdateMessage(),
            context=context,
            title="",
            robot=_InterruptedControlRobot(),
            message="give me the answer",
            chatid=111,
            messageid=222,
            convo_id="chat-1",
            message_thread_id=None,
            voice_note_detected=False,
            files=None,
            trace_id="test-midstream-control-interruption",
            telegram_message_id=222,
            telegram_update_id=333,
        )
    )

    visible = " ".join(strip_html_tags(item) for item in _final_delivered_texts(context))
    assert "Partial useful answer." in visible
    assert "Response interrupted before completion. Please try again." in visible
    assert "{SKIP_" not in visible


def test_plain_preview_fallback_is_replaced_by_final_html(monkeypatch):
    class _FormattedRobot:
        async def ask_stream_async(self, *args, **kwargs):
            _ = args, kwargs
            yield "**Bold final answer.**"

        def get_cached_voice_route(self, _key):
            return None

        def reset(self, *args, **kwargs):
            _ = args, kwargs

    async def _noop_send_librechat_attachments(**_kwargs):
        return None

    monkeypatch.setattr(
        tg_bot,
        "Users",
        types.SimpleNamespace(get_config=lambda *_a, **_k: False),
    )
    monkeypatch.setattr(tg_bot, "send_librechat_attachments", _noop_send_librechat_attachments)

    context = _FakeContext()
    context.bot.send_errors = [RuntimeError("can't parse entities"), None]
    asyncio.run(
        tg_bot.getViventiumResponse(
            update_message=_FakeUpdateMessage(),
            context=context,
            title="",
            robot=_FormattedRobot(),
            message="format this",
            chatid=111,
            messageid=222,
            convo_id="chat-1",
            message_thread_id=None,
            voice_note_detected=False,
            files=None,
            trace_id="test-preview-fallback-final-html",
            telegram_message_id=222,
            telegram_update_id=333,
        )
    )

    assert len(context.bot.sent_ids) == 1
    final = context.bot.current_messages[context.bot.sent_ids[0]]
    assert final["parse_mode"] == "HTML"
    assert "<b>Bold final answer.</b>" in final["text"]


def test_stream_preview_coalesces_before_expensive_rendering(monkeypatch):
    class _BurstRobot:
        async def ask_stream_async(self, *args, **kwargs):
            _ = args, kwargs
            for index in range(80):
                yield f" token-{index}"

        def get_cached_voice_route(self, _key):
            return None

        def reset(self, *args, **kwargs):
            _ = args, kwargs

    async def _noop_send_librechat_attachments(**_kwargs):
        return None

    original_render = tg_bot.render_telegram_markdown
    render_calls = 0

    def _counted_render(*args, **kwargs):
        nonlocal render_calls
        render_calls += 1
        return original_render(*args, **kwargs)

    monkeypatch.setattr(
        tg_bot,
        "Users",
        types.SimpleNamespace(get_config=lambda *_a, **_k: False),
    )
    monkeypatch.setattr(tg_bot, "should_send_voice_reply", lambda **_k: False)
    monkeypatch.setattr(tg_bot, "send_librechat_attachments", _noop_send_librechat_attachments)
    monkeypatch.setattr(tg_bot, "render_telegram_markdown", _counted_render)
    monkeypatch.setattr(tg_bot.config, "VIVENTIUM_TELEGRAM_STREAM_EDIT_INTERVAL_S", 0.1)

    context = _FakeContext()
    asyncio.run(
        tg_bot.getViventiumResponse(
            update_message=_FakeUpdateMessage(),
            context=context,
            title="",
            robot=_BurstRobot(),
            message="stream quickly",
            chatid=111,
            messageid=222,
            convo_id="chat-1",
            message_thread_id=None,
            voice_note_detected=False,
            files=None,
            trace_id="test-preview-render-coalescing",
            telegram_message_id=222,
            telegram_update_id=333,
        )
    )

    assert render_calls < 10
    assert "token-79" in " ".join(_final_delivered_texts(context))


def test_get_viventium_response_reconciles_preview_then_sends_ordered_final_segments(monkeypatch):
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
    assert _final_delivered_texts(context) == [
        "Draft preview.",
        "Final continuation.",
    ]
    assert context.bot.messages[-2]["reply_to_message_id"] == 222
    assert "reply_to_message_id" not in context.bot.messages[-1]
    assert robot.acks == [
        (
            "turn-1",
            3,
            "committed",
            f"telegram:111:{context.bot.next_id}",
            ["telegram:111:1002", "telegram:111:1003"],
        ),
    ]


def test_get_viventium_response_final_reconciliation_does_not_depend_on_preview_delete(monkeypatch):
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

    delivered = _final_delivered_texts(context)
    assert delivered[-2:] == ["First final.", "Second final."]
    assert len(context.bot.deletes) == 1
    assert not any("Connection error" in text for text in delivered)
    assert not any("stale preview delete failure" in text for text in delivered)


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


def test_get_viventium_response_supports_real_callback_context(monkeypatch):
    from telegram.ext import CallbackContext

    async def _noop_send_librechat_attachments(**_kwargs):
        return None

    monkeypatch.setattr(
        tg_bot,
        "Users",
        types.SimpleNamespace(get_config=lambda *_a, **_k: False),
    )
    monkeypatch.setattr(tg_bot, "should_send_voice_reply", lambda **_k: False)
    monkeypatch.setattr(tg_bot, "send_librechat_attachments", _noop_send_librechat_attachments)

    raw_bot = _FakeTelegramBot()
    context = CallbackContext(
        application=types.SimpleNamespace(bot=raw_bot),
        chat_id=111,
        user_id=700,
    )

    asyncio.run(
        tg_bot.getViventiumResponse(
            update_message=_FakeUpdateMessage(),
            context=context,
            title="",
            robot=_FakeRobot(),
            message="real context question",
            chatid=111,
            messageid=222,
            convo_id="chat-real-context",
            message_thread_id=None,
            voice_note_detected=False,
            files=None,
            trace_id="test-real-callback-context",
            telegram_message_id=222,
            telegram_update_id=333,
        )
    )

    assert context.bot is raw_bot
    assert len(raw_bot.messages) == 1


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
        (
            "turn-1",
            3,
            "committed",
            f"telegram:111:{context.bot.next_id}",
            ["telegram:111:1002", "telegram:111:1003"],
        ),
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


def test_get_viventium_response_rechecks_newest_source_before_first_final_send(monkeypatch):
    tg_bot._LATEST_TELEGRAM_SOURCE_MESSAGES.clear()
    class _LateIngressRobot:
        def __init__(self):
            self.acks = []

        async def ask_stream_async(self, *args, **kwargs):
            _ = args, kwargs
            yield {"type": "logical_turn", "logical_turn_id": "turn-race", "revision": 1}
            tg_bot._note_telegram_source_message(111, None, 223)
            yield "Obsolete first reply."

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
    robot = _LateIngressRobot()

    asyncio.run(
        tg_bot.getViventiumResponse(
            update_message=_FakeUpdateMessage(),
            context=context,
            title="",
            robot=robot,
            message="first source",
            chatid=111,
            messageid=222,
            convo_id="chat-race",
            message_thread_id=None,
            trace_id="test-source-order-race",
            telegram_message_id=222,
            telegram_update_id=333,
        )
    )

    assert context.bot.messages == []
    assert robot.acks == [("turn-race", 1, "partial_removed", "telegram:111")]
    tg_bot._LATEST_TELEGRAM_SOURCE_MESSAGES.clear()


@pytest.mark.asyncio
async def test_polling_recalculates_offset_after_each_ordered_update_response(monkeypatch):
    import telegram.ext._updater as updater_module

    offsets = []
    responses = iter(
        [
            [22346, 22347],
            [22347, 22348],
            [22348, 22349],
        ]
    )

    class _PollingBot:
        async def get_updates(self, *, offset, timeout, allowed_updates):
            _ = timeout, allowed_updates
            offsets.append(offset)
            return tuple(
                types.SimpleNamespace(update_id=update_id)
                for update_id in next(responses)
                if update_id >= offset
            )

    async def _skip_bootstrap(self, *_args, **_kwargs):
        _ = self

    async def _poll_three_responses(*, action_cb, **_kwargs):
        for _ in range(3):
            await action_cb()

    monkeypatch.setattr(updater_module.Updater, "_bootstrap", _skip_bootstrap)
    monkeypatch.setattr(updater_module, "network_retry_loop", _poll_three_responses)
    queue = asyncio.Queue()
    updater = updater_module.Updater(_PollingBot(), queue)
    updater._running = True
    ready = asyncio.Event()

    await updater._start_polling(
        poll_interval=0,
        timeout=0,
        bootstrap_retries=0,
        drop_pending_updates=False,
        allowed_updates=None,
        ready=ready,
        error_callback=None,
    )
    await updater._Updater__polling_task

    assert ready.is_set()
    assert offsets == [0, 22348, 22349]
    assert updater._last_update_id == 22350
    assert [queue.get_nowait().update_id for _ in range(queue.qsize())] == [
        22346,
        22347,
        22348,
        22349,
    ]


@pytest.mark.asyncio
async def test_ingress_orders_chat_sources_not_update_arrival_time_and_fences_send(
    monkeypatch,
):
    observations = []
    update_arrivals = []
    source_watermarks = {}

    class _ScopedSourceRobot:
        @staticmethod
        def _identity(kwargs):
            return (
                str(kwargs["telegram_user_id"]),
                str(kwargs["telegram_chat_id"]),
                str(kwargs.get("telegram_message_thread_id") or ""),
            )

        async def observe_source_order(self, **kwargs):
            identity = self._identity(kwargs)
            sequence = int(kwargs["source_sequence"])
            latest = max(source_watermarks.get(identity, 0), sequence)
            source_watermarks[identity] = latest
            observations.append((*identity, sequence))
            source_scope = hashlib.sha256(":".join(identity).encode()).hexdigest()
            source_event = hashlib.sha256(f"{source_scope}:{sequence}".encode()).hexdigest()
            return {
                "latest_source_sequence": latest,
                "observed_at": 1,
                "stale": sequence < latest,
                "source_order_scope": source_scope,
                "source_event_id": source_event,
                "durability": "durable",
                "replica_safe": True,
            }

        async def source_order_is_current(self, **kwargs):
            return int(kwargs["source_sequence"]) >= source_watermarks.get(
                self._identity(kwargs), 0
            )

    def _update(update_id, *, chat_id, message_id, thread_id=77, user_id=12345):
        message = types.SimpleNamespace(
            message_id=message_id,
            chat_id=chat_id,
            message_thread_id=thread_id,
            from_user=types.SimpleNamespace(id=user_id),
        )
        return types.SimpleNamespace(
            update_id=update_id,
            effective_chat=types.SimpleNamespace(id=chat_id),
            effective_message=message,
        )

    async def _observe(update):
        update_arrivals.append(update.update_id)
        return await tg_bot._observe_telegram_update_ingress(update, context)

    robot = _ScopedSourceRobot()
    context = _FakeContext()
    monkeypatch.setattr(tg_bot, "get_robot", lambda _convo_id: (robot, None, None, None))

    newest = await _observe(_update(880002, chat_id=111, message_id=12347))
    assert newest is not None
    assert await _observe(_update(880001, chat_id=111, message_id=12346)) is None
    assert await _observe(_update(880003, chat_id=222, message_id=7)) is not None
    assert await _observe(_update(880004, chat_id=111, message_id=8, thread_id=88)) is not None
    assert await _observe(_update(880005, chat_id=111, message_id=9, user_id=54321)) is not None

    await newest.call("send_message", chat_id=111, text="Current source reply.")
    assert [message["text"] for message in context.bot.messages] == [
        "Current source reply."
    ]

    assert await _observe(_update(880006, chat_id=111, message_id=12348)) is not None
    with pytest.raises(tg_bot._StaleTelegramSourceOrder):
        await newest.call("send_message", chat_id=111, text="Stale replay.")

    assert update_arrivals == [880002, 880001, 880003, 880004, 880005, 880006]
    assert observations == [
        ("12345", "111", "77", 12347),
        ("12345", "111", "77", 12346),
        ("12345", "222", "77", 7),
        ("12345", "111", "88", 8),
        ("54321", "111", "77", 9),
        ("12345", "111", "77", 12348),
    ]
    assert context.bot.messages == []
    assert context.bot.deletes == [{"chat_id": 111, "message_id": 1001}]


def test_command_ingress_observes_n_plus_one_280ms_before_stale_presentation(
    monkeypatch, tmp_path
):
    from utils.tr014_local_qa import (
        arm_tr014_control,
        maybe_delay_tr014_core_ingestion,
        read_redacted_audit,
    )

    tg_bot._LATEST_TELEGRAM_SOURCE_MESSAGES.clear()
    case_token = base64.urlsafe_b64encode(b"t" * 32).decode().rstrip("=")
    session_ref = "qa_" + hashlib.sha256(case_token.encode()).hexdigest()[:24]
    monkeypatch.setenv("VIVENTIUM_TELEGRAM_LOCAL_QA_MODE", "tr-014")
    monkeypatch.setenv("VIVENTIUM_LOCAL_QA_CASE_ID", "TR-014")
    monkeypatch.setenv("VIVENTIUM_LOCAL_QA_CASE_TOKEN", case_token)
    monkeypatch.setenv("VIVENTIUM_LOCAL_QA_SESSION_REF", session_ref)
    monkeypatch.setenv("VIVENTIUM_TELEGRAM_STATE_DIR", str(tmp_path))
    control = arm_tr014_control(
        state_dir=tmp_path,
        case_id="TR-014",
        case_token=case_token,
        session_ref=session_ref,
        owner_user_id=12345,
        chat_id=111,
        thread_id=77,
        stale_source_sequence=12345,
        source_sequence=12346,
        update_id=22346,
        ttl_seconds=120,
    )
    latest_source_sequence = 12345
    source_n_send_started = asyncio.Event()
    release_source_n_send = asyncio.Event()
    source_n_plus_one_observed_at = None
    source_n_plus_one_core_started_at = None
    source_n_presented_at = None
    boundary_order = []
    requested_delays = []
    targeted_events = []

    async def _recording_boundary_delay(event):
        if event.update_id == 22346:
            boundary_order.append("delay")
            targeted_events.append(event)

        async def _recording_sleep(seconds):
            requested_delays.append(seconds)
            await asyncio.sleep(seconds)

        return await maybe_delay_tr014_core_ingestion(
            event,
            state_dir=tmp_path,
            sleeper=_recording_sleep,
        )

    async def _record_unrelated_await(_bot, _chat_id):
        boundary_order.append("unrelated_await")
        await asyncio.sleep(0)
        return False

    class _FaithfulRaceBot(_FakeTelegramBot):
        def __init__(self):
            super().__init__()
            self.next_id = 12346
            self.sent_history = []

        async def send_message(self, **kwargs):
            nonlocal source_n_presented_at
            if kwargs.get("text") == "Obsolete source N reply.":
                source_n_send_started.set()
                await release_source_n_send.wait()
            result = await super().send_message(**kwargs)
            self.sent_history.append((result.message_id, kwargs.get("text")))
            if kwargs.get("text") == "Obsolete source N reply.":
                source_n_presented_at = asyncio.get_running_loop().time()
            return result

        def reopened_visible_texts(self):
            return [message["text"] for message in self.messages]

    class _CoreOrderedRobot:
        def __init__(self):
            self.acks = []
            self.observations = []
            self.admissions = []

        async def ask_stream_async(self, *args, **kwargs):
            nonlocal source_n_plus_one_core_started_at
            _ = args
            sequence = int(kwargs["telegram_message_id"])
            if sequence == 12346:
                boundary_order.append("core_admission")
                self.admissions.append(kwargs)
                source_n_plus_one_core_started_at = asyncio.get_running_loop().time()
            yield {
                "type": "logical_turn",
                "logical_turn_id": "turn-source-order",
                "revision": 1 if sequence == 12345 else 2,
            }
            if sequence == 12345:
                yield "Obsolete source N reply."
            else:
                yield "Current source N+1 reply."

        async def observe_source_order(self, **kwargs):
            nonlocal latest_source_sequence, source_n_plus_one_observed_at
            sequence = int(kwargs["source_sequence"])
            latest_source_sequence = max(latest_source_sequence, sequence)
            self.observations.append(sequence)
            if sequence == 12346:
                source_n_plus_one_observed_at = asyncio.get_running_loop().time()
            return {
                "latest_source_sequence": latest_source_sequence,
                "observed_at": 1,
                "stale": sequence < latest_source_sequence,
                "source_order_scope": "a" * 64,
                "source_event_id": "c" * 64,
                "durability": "durable",
                "replica_safe": True,
            }

        async def source_order_is_current(self, **kwargs):
            return int(kwargs["source_sequence"]) >= latest_source_sequence

        async def ack_delivery(self, *args):
            self.acks.append(args)
            return True

        async def ack_delivery_status(self, *args):
            self.acks.append(args)
            return "recorded"

        def reset(self, *args, **kwargs):
            _ = args, kwargs

    def _update(sequence):
        message = _FakeUpdateMessage()
        message.message_id = sequence
        message.chat_id = 111
        message.message_thread_id = 77
        message.media_group_id = None
        return types.SimpleNamespace(
            update_id=sequence + 10_000,
            effective_user=message.from_user,
            effective_chat=types.SimpleNamespace(id=111),
            effective_message=message,
            message=message,
            edited_message=None,
            channel_post=None,
            edited_channel_post=None,
        )

    async def _fake_get_message_info(update, *_args, **_kwargs):
        sequence = update.effective_message.message_id
        message = update.effective_message
        text = "source N" if sequence == 12345 else "source N+1"
        return (
            text,
            text,
            None,
            111,
            sequence,
            None,
            message,
            77,
            "chat-source-order",
            None,
            None,
            None,
            None,
            [],
            [],
        )

    async def _noop_send_librechat_attachments(**_kwargs):
        return None

    async def run_exact_race():
        shared_bot = _FaithfulRaceBot()
        first_context = _FakeCommandContext()
        second_context = _FakeCommandContext()
        first_context.bot = shared_bot
        second_context.bot = shared_bot
        source_n_task = asyncio.create_task(
            tg_bot.command_bot(_update(12345), first_context, has_command=False)
        )
        await source_n_send_started.wait()
        boundary_order.clear()
        source_n_plus_one_task = asyncio.create_task(
            tg_bot.command_bot(_update(12346), second_context, has_command=False)
        )
        for _ in range(100):
            evidence = read_redacted_audit(
                state_dir=tmp_path,
                case_id="TR-014",
                case_token=case_token,
                session_ref=session_ref,
            )
            if any(item.get("outcome") == "claimed" for item in evidence):
                break
            await asyncio.sleep(0.005)
        else:
            raise AssertionError("TR-014 installed-QA delay was not claimed")
        release_source_n_send.set()
        await source_n_task
        await source_n_plus_one_task
        return shared_bot

    robot = _CoreOrderedRobot()
    monkeypatch.setattr(tg_bot, "GetMesageInfo", _fake_get_message_info)
    monkeypatch.setattr(tg_bot, "get_robot", lambda _convo_id: (robot, None, None, None))
    monkeypatch.setattr(tg_bot.config, "ChatGPTbot", robot, raising=False)
    monkeypatch.setattr(tg_bot.config, "BLACK_LIST", None, raising=False)
    monkeypatch.setattr(tg_bot.config, "whitelist", None, raising=False)
    monkeypatch.setattr(tg_bot.config, "GROUP_LIST", None, raising=False)
    monkeypatch.setattr(tg_bot.config, "ADMIN_LIST", None, raising=False)
    monkeypatch.setattr(tg_bot, "Users", types.SimpleNamespace(get_config=lambda *_a, **_k: False))
    monkeypatch.setattr(tg_bot, "remove_job_if_exists", lambda *_a, **_k: None)
    monkeypatch.setattr(tg_bot, "should_send_voice_reply", lambda **_k: False)
    monkeypatch.setattr(tg_bot, "send_librechat_attachments", _noop_send_librechat_attachments)
    monkeypatch.setattr(tg_bot, "is_bot_blocked", _record_unrelated_await)
    monkeypatch.setattr(
        tg_bot,
        "maybe_delay_tr014_core_ingestion",
        _recording_boundary_delay,
    )

    telegram = asyncio.run(run_exact_race())

    assert robot.observations == [12345, 12346]
    assert source_n_plus_one_observed_at is not None
    assert source_n_plus_one_core_started_at is not None
    assert source_n_presented_at is not None
    assert boundary_order == ["unrelated_await", "delay", "core_admission"]
    assert requested_delays == [0.280]
    assert [
        (
            event.update_id,
            event.chat_id,
            event.thread_id,
            event.source_sequence,
            event.owner_user_id,
            event.event_kind,
        )
        for event in targeted_events
    ] == [(22346, 111, 77, 12346, 12345, "telegram_source")]
    assert len(robot.admissions) == 1
    assert robot.admissions[0]["telegram_update_id"] == 22346
    assert robot.admissions[0]["telegram_message_id"] == 12346
    assert robot.admissions[0]["telegram_message_thread_id"] == 77
    assert robot.admissions[0]["source_event_id"] == "c" * 64
    assert robot.admissions[0]["source_order_scope"] == "a" * 64
    assert (
        source_n_plus_one_observed_at
        < source_n_presented_at
        < source_n_plus_one_core_started_at
    )
    assert telegram.sent_history == [
        (12347, "Obsolete source N reply."),
        (12348, "Current source N+1 reply."),
    ]
    assert {item["message_id"] for item in telegram.deletes} == {12347}
    assert telegram.reopened_visible_texts() == ["Current source N+1 reply."]
    assert robot.acks == [
        ("turn-source-order", 1, "partial_removed", "telegram:111"),
        (
            "turn-source-order",
            2,
            "committed",
            "telegram:111:12348",
            ["telegram:111:12348"],
        )
    ]


def test_core_source_order_retracts_when_n_plus_one_arrives_during_final_send(monkeypatch):
    tg_bot._LATEST_TELEGRAM_SOURCE_MESSAGES.clear()
    latest_source_sequence = 12346
    final_send_started = asyncio.Event()
    release_final_send = asyncio.Event()

    class _RaceBot(_FakeTelegramBot):
        async def send_message(self, **kwargs):
            if len(self.messages) == 1:
                final_send_started.set()
                await release_final_send.wait()
            return await super().send_message(**kwargs)

    class _Robot:
        def __init__(self):
            self.acks = []

        async def ask_stream_async(self, *args, **kwargs):
            _ = args, kwargs
            yield {"type": "logical_turn", "logical_turn_id": "turn-send-race", "revision": 1}
            yield "First final.\n{MSG_BREAK}\nSecond final."

        async def source_order_is_current(self, **kwargs):
            return int(kwargs["source_sequence"]) >= latest_source_sequence

        async def ack_delivery(self, *args):
            self.acks.append(args)
            return True

        async def ack_delivery_status(self, *args):
            self.acks.append(args)
            return "recorded"

        def reset(self, *args, **kwargs):
            _ = args, kwargs

    async def run_race():
        nonlocal latest_source_sequence
        context = _FakeContext()
        context.bot = _RaceBot()
        robot = _Robot()
        task = asyncio.create_task(
            tg_bot.getViventiumResponse(
                update_message=_FakeUpdateMessage(),
                context=context,
                title="",
                robot=robot,
                message="source N",
                chatid=111,
                messageid=12346,
                convo_id="chat-send-race",
                message_thread_id=77,
                trace_id="test-source-order-during-send",
                telegram_message_id=12346,
                telegram_update_id=22346,
            )
        )
        await final_send_started.wait()
        latest_source_sequence = 12347
        release_final_send.set()
        await task
        return context, robot

    monkeypatch.setattr(tg_bot, "Users", types.SimpleNamespace(get_config=lambda *_a, **_k: False))
    monkeypatch.setattr(tg_bot, "should_send_voice_reply", lambda **_k: False)
    async def _noop_send_librechat_attachments(**_kwargs):
        return None

    monkeypatch.setattr(tg_bot, "send_librechat_attachments", _noop_send_librechat_attachments)

    context, robot = asyncio.run(run_race())

    assert context.bot.messages == []
    assert robot.acks == [("turn-send-race", 1, "partial_removed", "telegram:111")]
    tg_bot._LATEST_TELEGRAM_SOURCE_MESSAGES.clear()


def test_commit_ack_outage_retracts_final_and_shows_retryable_terminal(monkeypatch, tmp_path):
    store_path = tmp_path / "source-order-retractions.sqlite3"
    monkeypatch.setenv("VIVENTIUM_TELEGRAM_RETRACTION_STORE_PATH", str(store_path))

    class _Robot:
        async def ask_stream_async(self, *args, **kwargs):
            _ = args, kwargs
            yield {"type": "logical_turn", "logical_turn_id": "turn-ack-outage", "revision": 1}
            yield "Never leave this uncommitted."

        async def source_order_is_current(self, **_kwargs):
            return True

        async def ack_delivery_status(self, *_args):
            return "unavailable"

        def reset(self, *args, **kwargs):
            _ = args, kwargs

    async def _noop_send_librechat_attachments(**_kwargs):
        return None

    monkeypatch.setattr(tg_bot, "Users", types.SimpleNamespace(get_config=lambda *_a, **_k: False))
    monkeypatch.setattr(tg_bot, "should_send_voice_reply", lambda **_k: False)
    monkeypatch.setattr(tg_bot, "send_librechat_attachments", _noop_send_librechat_attachments)
    context = _FakeContext()

    asyncio.run(
        tg_bot.getViventiumResponse(
            update_message=_FakeUpdateMessage(),
            context=context,
            title="",
            robot=_Robot(),
            message="source",
            chatid=111,
            messageid=222,
            convo_id="chat-ack-outage",
            message_thread_id=None,
            telegram_message_id=222,
        )
    )

    assert len(context.bot.messages) == 1
    assert "Please retry your message" in context.bot.edits[-1]["text"]
    assert context.bot.deletes == []


def test_n_plus_one_during_retry_terminal_send_retracts_terminal(monkeypatch, tmp_path):
    latest_source_sequence = 222
    terminal_send_started = asyncio.Event()
    release_terminal_send = asyncio.Event()
    monkeypatch.setenv(
        "VIVENTIUM_TELEGRAM_RETRACTION_STORE_PATH",
        str(tmp_path / "source-order-retractions.sqlite3"),
    )

    class _TerminalRaceBot(_FakeTelegramBot):
        async def edit_message_text(self, **kwargs):
            if "Please retry your message" in str(kwargs.get("text", "")):
                terminal_send_started.set()
                await release_terminal_send.wait()
            return await super().edit_message_text(**kwargs)

    class _Robot:
        async def ask_stream_async(self, *args, **kwargs):
            _ = args, kwargs
            yield {"type": "logical_turn", "logical_turn_id": "turn-terminal-race", "revision": 1}
            yield "Unconfirmed source N answer."

        async def source_order_is_current(self, **kwargs):
            return int(kwargs["source_sequence"]) >= latest_source_sequence

        async def ack_delivery_status(self, *_args):
            return "unavailable"

        def reset(self, *args, **kwargs):
            _ = args, kwargs

    async def _noop_send_librechat_attachments(**_kwargs):
        return None

    async def run_race():
        nonlocal latest_source_sequence
        context = _FakeContext()
        context.bot = _TerminalRaceBot()
        task = asyncio.create_task(
            tg_bot.getViventiumResponse(
                update_message=_FakeUpdateMessage(),
                context=context,
                title="",
                robot=_Robot(),
                message="source N",
                chatid=111,
                messageid=222,
                convo_id="chat-terminal-race",
                message_thread_id=77,
                telegram_message_id=222,
            )
        )
        await terminal_send_started.wait()
        latest_source_sequence = 223
        release_terminal_send.set()
        await task
        return context

    monkeypatch.setattr(tg_bot, "Users", types.SimpleNamespace(get_config=lambda *_a, **_k: False))
    monkeypatch.setattr(tg_bot, "should_send_voice_reply", lambda **_k: False)
    monkeypatch.setattr(tg_bot, "send_librechat_attachments", _noop_send_librechat_attachments)

    context = asyncio.run(run_race())

    assert context.bot.messages == []
    assert {item["message_id"] for item in context.bot.deletes} == {1001}
    assert len(context.bot.deletes) == 1


def test_ack_and_watermark_outage_recovers_retry_terminal_after_restart(monkeypatch, tmp_path):
    store_path = tmp_path / "source-order-retractions.sqlite3"
    monkeypatch.setenv("VIVENTIUM_TELEGRAM_RETRACTION_STORE_PATH", str(store_path))

    class _OutageRobot:
        def __init__(self):
            self.ack_attempted = False

        async def ask_stream_async(self, *args, **kwargs):
            _ = args, kwargs
            yield {"type": "logical_turn", "logical_turn_id": "turn-full-outage", "revision": 1}
            yield "Current answer with an unavailable commit path."

        async def source_order_is_current(self, **_kwargs):
            if self.ack_attempted:
                raise ConnectionError("synthetic Core outage")
            return True

        async def ack_delivery_status(self, *_args):
            self.ack_attempted = True
            return "unavailable"

        def reset(self, *args, **kwargs):
            _ = args, kwargs

    class _RecoveredRobot:
        async def source_order_is_current(self, **_kwargs):
            return True

    async def _noop_send_librechat_attachments(**_kwargs):
        return None

    monkeypatch.setattr(tg_bot, "Users", types.SimpleNamespace(get_config=lambda *_a, **_k: False))
    monkeypatch.setattr(tg_bot, "should_send_voice_reply", lambda **_k: False)
    monkeypatch.setattr(tg_bot, "send_librechat_attachments", _noop_send_librechat_attachments)
    context = _FakeContext()

    asyncio.run(
        tg_bot.getViventiumResponse(
            update_message=_FakeUpdateMessage(),
            context=context,
            title="",
            robot=_OutageRobot(),
            message="source",
            chatid=111,
            messageid=222,
            convo_id="chat-full-outage",
            message_thread_id=77,
            telegram_message_id=222,
        )
    )

    restarted_store = tg_bot._TelegramRetractionStore(store_path, retry_delay_s=0)
    assert context.bot.messages == []
    assert restarted_store.pending_terminal_count() == 1
    recovery_now = tg_bot.time.time() + 31
    monkeypatch.setattr(tg_bot.time, "time", lambda: recovery_now)

    recovery_bot = _FakeTelegramBot()
    recovered = asyncio.run(
        tg_bot._retry_pending_source_order_terminals(
            recovery_bot,
            _RecoveredRobot(),
            restarted_store,
        )
    )

    assert recovered == 1
    assert recovery_bot.messages == []
    assert [item["text"] for item in recovery_bot.edits] == [
        "I could not safely confirm that reply. It was removed. Please retry your message."
    ]
    assert restarted_store.pending_terminal_count() == 0


def test_commit_ack_outage_terminal_is_cleaned_after_restart_before_one_retry_final(
    monkeypatch, tmp_path
):
    store_path = tmp_path / "source-order-retractions.sqlite3"
    monkeypatch.setenv("VIVENTIUM_TELEGRAM_RETRACTION_STORE_PATH", str(store_path))

    class _Robot:
        def __init__(self, text, ack_status):
            self.text = text
            self.ack_status = ack_status
            self.acks = []

        async def ask_stream_async(self, *args, **kwargs):
            _ = args, kwargs
            yield {"type": "logical_turn", "logical_turn_id": f"turn-{self.text}", "revision": 1}
            yield self.text

        async def source_order_is_current(self, **_kwargs):
            return True

        async def ack_delivery_status(self, *args):
            self.acks.append(args)
            return self.ack_status

        def reset(self, *args, **kwargs):
            _ = args, kwargs

    async def _noop_send_librechat_attachments(**_kwargs):
        return None

    monkeypatch.setattr(tg_bot, "Users", types.SimpleNamespace(get_config=lambda *_a, **_k: False))
    monkeypatch.setattr(tg_bot, "should_send_voice_reply", lambda **_k: False)
    monkeypatch.setattr(tg_bot, "send_librechat_attachments", _noop_send_librechat_attachments)
    telegram = _FakeTelegramBot()

    first_context = _FakeContext()
    first_context.bot = telegram
    asyncio.run(
        tg_bot.getViventiumResponse(
            update_message=_FakeUpdateMessage(),
            context=first_context,
            title="",
            robot=_Robot("Unconfirmed reply.", "unavailable"),
            message="source N",
            chatid=111,
            messageid=222,
            convo_id="chat-restart-recovery",
            message_thread_id=77,
            telegram_message_id=222,
        )
    )
    assert len(telegram.messages) == 1
    assert "Please retry" in telegram.edits[-1]["text"]

    restarted_context = _FakeContext()
    restarted_context.bot = telegram
    retry_robot = _Robot("Recovered reply.", "recorded")
    asyncio.run(
        tg_bot.getViventiumResponse(
            update_message=_FakeUpdateMessage(),
            context=restarted_context,
            title="",
            robot=retry_robot,
            message="source N+1 retry",
            chatid=111,
            messageid=223,
            convo_id="chat-restart-recovery",
            message_thread_id=77,
            telegram_message_id=223,
        )
    )

    assert [item["text"] for item in telegram.messages] == ["Recovered reply."]
    assert len(retry_robot.acks) == 1
    assert retry_robot.acks[0][2] == "committed"


def test_stale_delete_failure_is_durable_and_retried_after_restart(monkeypatch, tmp_path):
    store_path = tmp_path / "source-order-retractions.sqlite3"
    monkeypatch.setenv("VIVENTIUM_TELEGRAM_RETRACTION_STORE_PATH", str(store_path))

    class _DeleteFailBot(_FakeTelegramBot):
        async def delete_message(self, **kwargs):
            self.deletes.append(kwargs)
            raise ConnectionError("synthetic delete outage")

    class _Robot:
        async def ask_stream_async(self, *args, **kwargs):
            _ = args, kwargs
            yield {"type": "logical_turn", "logical_turn_id": "turn-delete-retry", "revision": 1}
            yield "Stale at commit."

        async def source_order_is_current(self, **_kwargs):
            return True

        async def ack_delivery_status(self, *_args):
            return "stale_source_order"

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
            robot=_Robot(),
            message="source",
            chatid=111,
            messageid=222,
            convo_id="chat-delete-retry",
            message_thread_id=None,
            telegram_message_id=222,
        )
    )

    restarted_store = tg_bot._TelegramRetractionStore(store_path, ttl_s=60, retry_delay_s=0)
    assert restarted_store.pending_count() == 1
    recovery_bot = _FakeTelegramBot()
    asyncio.run(tg_bot._retry_source_order_retractions(recovery_bot, restarted_store))
    assert recovery_bot.deletes == [{"chat_id": "111", "message_id": 1001}]
    assert restarted_store.pending_count() == 0


def test_source_order_cache_ttl_keeps_active_turn_then_cleans_it(monkeypatch):
    now = 100.0
    monkeypatch.setenv("VIVENTIUM_TELEGRAM_SOURCE_CACHE_TTL_S", "1")
    monkeypatch.setattr(tg_bot.time, "monotonic", lambda: now)
    tg_bot._LATEST_TELEGRAM_SOURCE_MESSAGES.clear()
    key = tg_bot._activate_telegram_source_message(111, 77, 12346)
    now = 102.0
    tg_bot._cleanup_telegram_source_order_cache()
    assert key in tg_bot._LATEST_TELEGRAM_SOURCE_MESSAGES
    tg_bot._release_telegram_source_message(key)
    now = 104.0
    tg_bot._cleanup_telegram_source_order_cache()
    assert key not in tg_bot._LATEST_TELEGRAM_SOURCE_MESSAGES


def test_retry_terminal_ledger_expires_after_bounded_ttl(monkeypatch, tmp_path):
    now = 100.0
    monkeypatch.setattr(tg_bot.time, "time", lambda: now)
    store = tg_bot._TelegramRetractionStore(
        tmp_path / "source-order-retractions.sqlite3", ttl_s=60
    )
    store.remember_retry_terminal(
        telegram_user_id=9,
        chat_id=111,
        thread_id=77,
        source_sequence=12346,
        message_id=1001,
    )
    store.remember_pending_terminal(
        telegram_user_id=10,
        chat_id=111,
        thread_id=77,
        source_sequence=12346,
    )

    now = 159.0
    assert store.obsolete_retry_terminals(
        telegram_user_id=9,
        chat_id=111,
        thread_id=77,
        source_sequence=12347,
    ) == [("111", 1001, 12346)]
    assert store.pending_terminal_count() == 1

    now = 161.0
    assert store.obsolete_retry_terminals(
        telegram_user_id=9,
        chat_id=111,
        thread_id=77,
        source_sequence=12347,
    ) == []
    assert store.pending_terminal_count() == 0


def test_pending_terminal_claim_lease_token_fences_expired_process(monkeypatch, tmp_path):
    now = 100.0
    monkeypatch.setattr(tg_bot.time, "time", lambda: now)
    path = tmp_path / "source-order-retractions.sqlite3"
    first_process = tg_bot._TelegramRetractionStore(path, retry_delay_s=0)
    second_process = tg_bot._TelegramRetractionStore(path, retry_delay_s=0)
    first_process.remember_pending_terminal(
        telegram_user_id=9,
        chat_id=111,
        thread_id=77,
        source_sequence=12346,
        presentation_refs=["telegram:111:1001"],
    )

    first_claim = first_process.claim_pending_terminals(limit=1, lease_s=1)[0]
    now = 102.0
    second_claim = second_process.claim_pending_terminals(limit=1, lease_s=30)[0]

    assert first_claim["claim_token"] != second_claim["claim_token"]
    assert first_claim["claim_generation"] + 1 == second_claim["claim_generation"]
    assert first_process.complete_pending_terminal(first_claim) is False
    assert first_process.pending_terminal_count() == 1
    assert second_process.complete_pending_terminal(second_claim) is True
    assert second_process.pending_terminal_count() == 0


def test_live_process_fence_serializes_existing_message_past_every_logical_ttl(
    monkeypatch, tmp_path
):
    now = 100.0
    monkeypatch.setattr(tg_bot.time, "time", lambda: now)
    monkeypatch.setenv("VIVENTIUM_TELEGRAM_PRESENTATION_API_TIMEOUT_S", "35")
    monkeypatch.setenv("VIVENTIUM_TELEGRAM_PRESENTATION_OPERATION_LEASE_S", "40")
    path = tmp_path / "source-order-retractions.sqlite3"
    first_process = tg_bot._TelegramRetractionStore(path, ttl_s=60, retry_delay_s=0)
    second_process = tg_bot._TelegramRetractionStore(path, ttl_s=60, retry_delay_s=0)
    first_process.remember_pending_terminal(
        telegram_user_id=9,
        chat_id=111,
        thread_id=77,
        source_sequence=12346,
        presentation_refs=["telegram:111:1001"],
    )
    first_claim = first_process.claim_pending_terminals(limit=1, lease_s=1)[0]
    edit_started = asyncio.Event()
    release_edit = asyncio.Event()

    class _HeldEditBot(_FakeTelegramBot):
        def __init__(self):
            super().__init__()
            self.entered_texts = []
            self.visible_text = "original"

        async def edit_message_text(self, **kwargs):
            self.entered_texts.append(kwargs["text"])
            if kwargs["text"] == "generation-1":
                edit_started.set()
                await release_edit.wait()
            self.visible_text = kwargs["text"]
            return None

    class _Robot:
        async def source_order_is_current(self, **_kwargs):
            return True

    def guard(telegram, store, claim):
        candidate = tg_bot._TelegramSourceOrderGuard(
            bot=telegram,
            robot=_Robot(),
            telegram_user_id=9,
            chat_id=111,
            thread_id=77,
            source_sequence=12346,
        )
        candidate._store = store
        candidate._recovery_claim = claim
        return candidate

    async def exercise():
        nonlocal now
        telegram = _HeldEditBot()
        first_task = asyncio.create_task(
            guard(telegram, first_process, first_claim)._run_recovery_presentation_call(
                "edit_message_text",
                operation_key="message:111:1001",
                operation_kind="edit",
                chat_id=111,
                message_id=1001,
                text="generation-1",
            )
        )
        await asyncio.wait_for(edit_started.wait(), timeout=2)

        # Every wall-clock lease and ledger TTL is now stale. The live process fence remains.
        now = 10_000.0
        second_claim = second_process.claim_pending_terminals(limit=1, lease_s=30)[0]
        second_task = asyncio.create_task(
            guard(telegram, second_process, second_claim)._run_recovery_presentation_call(
                "edit_message_text",
                operation_key="message:111:1001",
                operation_kind="edit",
                chat_id=111,
                message_id=1001,
                text="generation-2",
            )
        )
        await asyncio.sleep(0.1)
        assert telegram.entered_texts == ["generation-1"]

        release_edit.set()
        first_result, first_completed = await asyncio.wait_for(first_task, timeout=2)
        second_result, second_completed = await asyncio.wait_for(second_task, timeout=2)
        assert first_result is None
        assert first_completed is False
        assert second_result is None
        assert second_completed is True
        assert second_process.complete_pending_terminal(second_claim) is True
        return telegram

    telegram = asyncio.run(exercise())

    assert telegram.entered_texts == ["generation-1", "generation-2"]
    assert telegram.visible_text == "generation-2"
    assert second_process.pending_terminal_count() == 0


def test_existing_message_process_fence_releases_only_after_child_process_death(tmp_path):
    path = tmp_path / "private-ledger" / "source-order-retractions.sqlite3"
    child_source = """
import asyncio
import sys
sys.path.insert(0, sys.argv[2])
import bot

async def hold():
    store = bot._TelegramRetractionStore(sys.argv[1])
    async with bot._telegram_existing_message_fence(store.path, 111, 1001):
        print("locked", flush=True)
        await asyncio.Event().wait()

asyncio.run(hold())
"""
    child = subprocess.Popen(
        [sys.executable, "-c", child_source, str(path), str(BOT_DIR)],
        cwd=str(ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        assert child.stdout is not None
        assert child.stdout.readline().strip() == "locked"

        async def exercise():
            entered = asyncio.Event()

            async def acquire_after_child():
                async with tg_bot._telegram_existing_message_fence(path, 111, 1001):
                    entered.set()

            contender = asyncio.create_task(acquire_after_child())
            await asyncio.sleep(0.1)
            assert not entered.is_set()

            child.terminate()
            await asyncio.to_thread(child.wait, 5)
            await asyncio.wait_for(entered.wait(), timeout=2)
            await asyncio.wait_for(contender, timeout=2)

        asyncio.run(exercise())
        lock_file = tg_bot._telegram_presentation_lock_file(path, 111, 1001)
        assert stat.S_IMODE(lock_file.parent.stat().st_mode) == 0o700
        assert stat.S_IMODE(lock_file.stat().st_mode) == 0o600
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)


def test_child_death_allows_new_generation_to_complete_one_current_external_edit(tmp_path):
    path = tmp_path / "private-ledger" / "source-order-retractions.sqlite3"
    first_process = tg_bot._TelegramRetractionStore(path, retry_delay_s=0)
    second_process = tg_bot._TelegramRetractionStore(path, retry_delay_s=0)
    first_process.remember_pending_terminal(
        telegram_user_id=9,
        chat_id=111,
        thread_id=77,
        source_sequence=12346,
        presentation_refs=["telegram:111:1001"],
    )
    first_claim = first_process.claim_pending_terminals(limit=1, lease_s=30)[0]
    child_source = """
import asyncio
import sys
sys.path.insert(0, sys.argv[2])
import bot

claim = {
    "telegram_user_id": "9",
    "chat_id": "111",
    "thread_id": "77",
    "source_sequence": 12346,
    "claim_token": sys.argv[3],
    "claim_generation": int(sys.argv[4]),
    "presentation_refs": ["telegram:111:1001"],
}

class HeldTelegramMutation:
    async def edit_message_text(self):
        print("mutation-entered", flush=True)
        await asyncio.Event().wait()
        print("stale-result", flush=True)

async def hold_generation_one_mutation():
    store = bot._TelegramRetractionStore(sys.argv[1], retry_delay_s=0)
    operation = store.begin_presentation_operation(
        claim,
        operation_key="message:111:1001",
        operation_kind="edit",
        lease_s=2,
    )
    assert operation is not None
    async with bot._telegram_existing_message_fence(store.path, 111, 1001):
        assert store.refresh_presentation_operation(operation, lease_s=2)
        await HeldTelegramMutation().edit_message_text()

asyncio.run(hold_generation_one_mutation())
"""
    child = subprocess.Popen(
        [
            sys.executable,
            "-c",
            child_source,
            str(path),
            str(BOT_DIR),
            first_claim["claim_token"],
            str(first_claim["claim_generation"]),
        ],
        cwd=str(ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    class _CurrentRobot:
        async def source_order_is_current(self, **_kwargs):
            return True

    class _VisibleTelegramBot(_FakeTelegramBot):
        def __init__(self):
            super().__init__()
            self.visible_replies = {1001: "unfinished prior reply"}

        async def edit_message_text(self, **kwargs):
            await super().edit_message_text(**kwargs)
            self.visible_replies[kwargs["message_id"]] = kwargs["text"]
            return None

    try:
        assert child.stdout is not None

        async def exercise():
            entered = await asyncio.wait_for(
                asyncio.to_thread(child.stdout.readline), timeout=5
            )
            assert entered.strip() == "mutation-entered"

            second_claim = None
            deadline = asyncio.get_running_loop().time() + 5
            while second_claim is None and asyncio.get_running_loop().time() < deadline:
                claims = second_process.claim_pending_terminals(limit=1, lease_s=30)
                second_claim = claims[0] if claims else None
                if second_claim is None:
                    await asyncio.sleep(0.05)
            assert second_claim is not None
            assert second_claim["claim_generation"] == first_claim["claim_generation"] + 1

            telegram = _VisibleTelegramBot()
            guard = tg_bot._TelegramSourceOrderGuard(
                bot=telegram,
                robot=_CurrentRobot(),
                telegram_user_id=9,
                chat_id=111,
                thread_id=77,
                source_sequence=12346,
            )
            guard._store = second_process
            guard._recovery_claim = second_claim
            guard.retain_presentation_refs(second_claim["presentation_refs"])
            current_task = asyncio.create_task(
                guard.send_retryable_terminal(
                    persist=False, pending_claim=second_claim
                )
            )
            await asyncio.sleep(0.1)
            assert telegram.edits == []
            assert child.poll() is None

            child.terminate()
            await asyncio.to_thread(child.wait, timeout=5)
            current_message_id = await asyncio.wait_for(current_task, timeout=3)
            return telegram, second_claim, current_message_id

        telegram, second_claim, current_message_id = asyncio.run(exercise())
        remaining_child_output = child.stdout.read()

        assert "stale-result" not in remaining_child_output
        assert current_message_id == 1001
        assert len(telegram.edits) == 1
        assert telegram.visible_replies == {
            1001: (
                "I could not safely confirm that reply. It was removed. "
                "Please retry your message."
            )
        }
        assert second_process.pending_terminal_count() == 0
        assert first_process.complete_pending_terminal(first_claim) is False
        assert second_claim["claim_token"] != first_claim["claim_token"]
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)


def test_existing_message_fence_uses_private_bounded_hash_slots(tmp_path):
    path = tmp_path / "private-ledger" / "source-order-retractions.sqlite3"
    lock_paths = {
        tg_bot._telegram_presentation_lock_file(path, -100123, message_id)
        for message_id in range(10_000, 15_000)
    }

    assert len(lock_paths) <= tg_bot._TELEGRAM_PRESENTATION_LOCK_SLOTS
    assert all(lock_path.parent == next(iter(lock_paths)).parent for lock_path in lock_paths)
    assert all(len(lock_path.stem) == 4 for lock_path in lock_paths)
    assert all("-100123" not in lock_path.name for lock_path in lock_paths)
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(next(iter(lock_paths)).parent.stat().st_mode) == 0o700


def test_late_new_send_is_creator_retracted_after_operation_generation_changes(
    monkeypatch, tmp_path
):
    now = 100.0
    monkeypatch.setattr(tg_bot.time, "time", lambda: now)
    monkeypatch.setenv("VIVENTIUM_TELEGRAM_PRESENTATION_API_TIMEOUT_S", "35")
    monkeypatch.setenv("VIVENTIUM_TELEGRAM_PRESENTATION_OPERATION_LEASE_S", "40")
    path = tmp_path / "source-order-retractions.sqlite3"
    first_process = tg_bot._TelegramRetractionStore(path, retry_delay_s=0)
    second_process = tg_bot._TelegramRetractionStore(path, retry_delay_s=0)
    first_process.remember_pending_terminal(
        telegram_user_id=9,
        chat_id=111,
        thread_id=77,
        source_sequence=12346,
    )
    first_claim = first_process.claim_pending_terminals(limit=1, lease_s=1)[0]
    send_started = asyncio.Event()
    release_send = asyncio.Event()

    class _HeldSendBot(_FakeTelegramBot):
        def __init__(self):
            super().__init__()
            self.hold_once = True

        async def send_message(self, **kwargs):
            if self.hold_once:
                self.hold_once = False
                send_started.set()
                await release_send.wait()
            result = await super().send_message(**kwargs)
            result.chat_id = kwargs.get("chat_id")
            return result

    class _Robot:
        async def source_order_is_current(self, **_kwargs):
            return True

    def _guard(telegram, store, claim):
        guard = tg_bot._TelegramSourceOrderGuard(
            bot=telegram,
            robot=_Robot(),
            telegram_user_id=9,
            chat_id=111,
            thread_id=77,
            source_sequence=12346,
        )
        guard._store = store
        guard._recovery_claim = claim
        return guard

    async def exercise():
        nonlocal now
        telegram = _HeldSendBot()
        first_task = asyncio.create_task(
            _guard(telegram, first_process, first_claim).send_retryable_terminal(
                persist=False, pending_claim=first_claim
            )
        )
        await send_started.wait()
        now = 141.0
        second_claim = second_process.claim_pending_terminals(limit=1, lease_s=30)[0]
        release_send.set()
        assert await first_task is None
        current_message_id = await _guard(
            telegram, second_process, second_claim
        ).send_retryable_terminal(persist=False, pending_claim=second_claim)
        return telegram, current_message_id

    telegram, current_message_id = asyncio.run(exercise())

    assert current_message_id == 1002
    assert {item["message_id"] for item in telegram.deletes} == {1001}
    assert len(telegram.messages) == 1
    assert second_process.pending_terminal_count() == 0


def test_retraction_store_creates_and_repairs_private_modes(tmp_path):
    private_parent = tmp_path / "private-ledger"
    private_parent.mkdir(mode=0o777)
    os.chmod(private_parent, 0o777)
    path = private_parent / "source-order-retractions.sqlite3"
    path.touch(mode=0o666)
    os.chmod(path, 0o666)

    store = tg_bot._TelegramRetractionStore(path)
    assert store.pending_count() == 0

    assert stat.S_IMODE(private_parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    for suffix in ("-wal", "-shm"):
        sidecar = Path(f"{path}{suffix}")
        if sidecar.exists():
            assert stat.S_IMODE(sidecar.stat().st_mode) == 0o600


def test_retraction_store_atomically_creates_private_parent_and_file(tmp_path):
    path = tmp_path / "new-private-ledger" / "source-order-retractions.sqlite3"

    assert tg_bot._TelegramRetractionStore(path).pending_count() == 0

    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_active_presentation_operation_extends_then_expires_bounded_ttl(
    monkeypatch, tmp_path
):
    now = 100.0
    monkeypatch.setattr(tg_bot.time, "time", lambda: now)
    path = tmp_path / "source-order-retractions.sqlite3"
    store = tg_bot._TelegramRetractionStore(path, ttl_s=60, retry_delay_s=0)
    store.remember_pending_terminal(
        telegram_user_id=9,
        chat_id=111,
        thread_id=77,
        source_sequence=12346,
    )
    claim = store.claim_pending_terminals(limit=1, lease_s=1)[0]
    operation = store.begin_presentation_operation(
        claim,
        operation_key="message:111:1001",
        operation_kind="edit",
        lease_s=90,
    )
    assert operation is not None

    now = 161.0
    reopened_while_active = tg_bot._TelegramRetractionStore(path, ttl_s=60)
    assert reopened_while_active.pending_terminal_count() == 1
    with reopened_while_active._connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM telegram_source_presentation_operations"
        ).fetchone()[0] == 1

    now = 251.0
    reopened_after_ttl = tg_bot._TelegramRetractionStore(path, ttl_s=60)
    assert reopened_after_ttl.pending_terminal_count() == 0
    with reopened_after_ttl._connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM telegram_source_presentation_operations"
        ).fetchone()[0] == 0


def test_late_send_compensation_delete_failure_is_durably_retried(tmp_path):
    path = tmp_path / "source-order-retractions.sqlite3"
    store = tg_bot._TelegramRetractionStore(path, retry_delay_s=0)

    class _DeleteFailsOnceBot(_FakeTelegramBot):
        def __init__(self):
            super().__init__()
            self.fail_once = True

        async def delete_message(self, **kwargs):
            if self.fail_once:
                self.fail_once = False
                raise RuntimeError("synthetic delete failure")
            return await super().delete_message(**kwargs)

    async def exercise():
        telegram = _DeleteFailsOnceBot()
        telegram._messages_by_id[1001] = {"text": "late stale output"}
        telegram.messages.append(telegram._messages_by_id[1001])
        guard = tg_bot._TelegramSourceOrderGuard(
            bot=telegram,
            robot=_FakeRobot(),
            telegram_user_id=9,
            chat_id=111,
            thread_id=77,
            source_sequence=12346,
        )
        guard._store = store
        guard._recovery_claim = {
            "claim_token": "expired",
            "claim_generation": 1,
        }
        guard._retain(111, 1001)
        assert await guard._compensate_new_message(111, 1001) is True
        assert store.due() == [("111", 1001)]
        assert await tg_bot._retry_source_order_retractions(telegram, store) == 1
        return telegram

    telegram = asyncio.run(exercise())

    assert telegram.messages == []
    assert store.pending_count() == 0


def test_retraction_store_persists_source_and_recovery_ledger_across_process_reopen(
    tmp_path,
):
    path = tmp_path / "private-ledger" / "source-order-retractions.sqlite3"
    store = tg_bot._TelegramRetractionStore(path, retry_delay_s=0)
    store.enqueue(111, 1000)
    store.remember_pending_terminal(
        telegram_user_id=9,
        chat_id=111,
        thread_id=77,
        source_sequence=12346,
        presentation_refs=["telegram:111:1001"],
    )
    child_source = """
import sys
sys.path.insert(0, sys.argv[2])
import bot
store = bot._TelegramRetractionStore(sys.argv[1], retry_delay_s=0)
claim = store.claim_pending_terminals(limit=1, lease_s=30)[0]
assert store.settle_pending_terminal(claim, 1001)
print(f\"{store.pending_count()}:{store.pending_terminal_count()}\")
"""

    completed = subprocess.run(
        [sys.executable, "-c", child_source, str(path), str(BOT_DIR)],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        timeout=20,
        check=True,
    )

    reopened_store = tg_bot._TelegramRetractionStore(path, retry_delay_s=0)
    assert completed.stdout.strip() == "1:0"
    assert reopened_store.due() == [("111", 1000)]
    assert reopened_store.obsolete_retry_terminals(
        telegram_user_id=9,
        chat_id=111,
        thread_id=77,
        source_sequence=12347,
    ) == [("111", 1001, 12346)]


def test_expired_recovery_worker_cannot_edit_or_delete_after_new_process_claims(
    monkeypatch, tmp_path
):
    now = 100.0
    monkeypatch.setattr(tg_bot.time, "time", lambda: now)
    path = tmp_path / "source-order-retractions.sqlite3"
    first_process = tg_bot._TelegramRetractionStore(path, retry_delay_s=0)
    second_process = tg_bot._TelegramRetractionStore(path, retry_delay_s=0)
    first_process.remember_pending_terminal(
        telegram_user_id=9,
        chat_id=111,
        thread_id=77,
        source_sequence=12346,
        presentation_refs=["telegram:111:1001"],
    )
    first_claim = first_process.claim_pending_terminals(limit=1, lease_s=1)[0]
    now = 102.0
    second_claim = second_process.claim_pending_terminals(limit=1, lease_s=30)[0]

    class _Robot:
        async def source_order_is_current(self, **_kwargs):
            return True

    async def exercise_stale_worker():
        bot = _FakeTelegramBot()
        guard = tg_bot._TelegramSourceOrderGuard(
            bot=bot,
            robot=_Robot(),
            telegram_user_id=9,
            chat_id=111,
            thread_id=77,
            source_sequence=12346,
        )
        guard._store = first_process
        guard._recovery_claim = first_claim
        guard.retain_presentation_refs(first_claim["presentation_refs"])
        assert await guard.send_retryable_terminal(
            persist=False, pending_claim=first_claim
        ) is None
        await guard.retract_all()
        return bot

    telegram = asyncio.run(exercise_stale_worker())

    assert telegram.edits == []
    assert telegram.deletes == []
    assert first_process.pending_terminal_count() == 1
    assert second_process.complete_pending_terminal(second_claim) is True


def test_ack_outage_persists_recovery_before_destructive_retraction(monkeypatch, tmp_path):
    store_path = tmp_path / "source-order-retractions.sqlite3"
    monkeypatch.setenv("VIVENTIUM_TELEGRAM_RETRACTION_STORE_PATH", str(store_path))

    class _Robot:
        def __init__(self):
            self.ack_attempted = False

        async def ask_stream_async(self, *_args, **_kwargs):
            yield {"type": "logical_turn", "logical_turn_id": "turn-crash", "revision": 1}
            yield "Current answer before crash."

        async def source_order_is_current(self, **_kwargs):
            return not self.ack_attempted

        async def ack_delivery_status(self, *_args):
            self.ack_attempted = True
            return "unavailable"

        def reset(self, *_args, **_kwargs):
            return None

    async def _noop_send_librechat_attachments(**_kwargs):
        return None

    async def _crash_before_retraction(_guard):
        raise SystemExit("synthetic process death before deletion")

    monkeypatch.setattr(tg_bot, "Users", types.SimpleNamespace(get_config=lambda *_a, **_k: False))
    monkeypatch.setattr(tg_bot, "should_send_voice_reply", lambda **_k: False)
    monkeypatch.setattr(tg_bot, "send_librechat_attachments", _noop_send_librechat_attachments)
    monkeypatch.setattr(tg_bot._TelegramSourceOrderGuard, "retract_all", _crash_before_retraction)
    context = _FakeContext()

    with pytest.raises(SystemExit, match="before deletion"):
        asyncio.run(
            tg_bot.getViventiumResponse(
                update_message=_FakeUpdateMessage(),
                context=context,
                title="",
                robot=_Robot(),
                message="source",
                chatid=111,
                messageid=222,
                convo_id="chat-crash-before-delete",
                message_thread_id=77,
                telegram_message_id=222,
            )
        )

    restarted_store = tg_bot._TelegramRetractionStore(store_path, retry_delay_s=0)
    assert restarted_store.pending_terminal_count() == 1


def test_ack_outage_persists_recovery_before_retry_notice_send(monkeypatch, tmp_path):
    store_path = tmp_path / "source-order-retractions.sqlite3"
    monkeypatch.setenv("VIVENTIUM_TELEGRAM_RETRACTION_STORE_PATH", str(store_path))
    pending_counts = []

    class _CrashBot(_FakeTelegramBot):
        async def edit_message_text(self, **kwargs):
            if "Please retry your message" in str(kwargs.get("text", "")):
                pending_counts.append(
                    tg_bot._TelegramRetractionStore(store_path).pending_terminal_count()
                )
                raise SystemExit("synthetic process death before retry notice")
            return await super().edit_message_text(**kwargs)

    class _Robot:
        async def ask_stream_async(self, *_args, **_kwargs):
            yield {"type": "logical_turn", "logical_turn_id": "turn-notice-crash", "revision": 1}
            yield "Current answer before retry notice crash."

        async def source_order_is_current(self, **_kwargs):
            return True

        async def ack_delivery_status(self, *_args):
            return "unavailable"

        def reset(self, *_args, **_kwargs):
            return None

    async def _noop_send_librechat_attachments(**_kwargs):
        return None

    monkeypatch.setattr(tg_bot, "Users", types.SimpleNamespace(get_config=lambda *_a, **_k: False))
    monkeypatch.setattr(tg_bot, "should_send_voice_reply", lambda **_k: False)
    monkeypatch.setattr(tg_bot, "send_librechat_attachments", _noop_send_librechat_attachments)
    context = _FakeContext()
    context.bot = _CrashBot()

    with pytest.raises(SystemExit, match="before retry notice"):
        asyncio.run(
            tg_bot.getViventiumResponse(
                update_message=_FakeUpdateMessage(),
                context=context,
                title="",
                robot=_Robot(),
                message="source",
                chatid=111,
                messageid=222,
                convo_id="chat-crash-before-notice",
                message_thread_id=77,
                telegram_message_id=222,
            )
        )

    assert pending_counts == [1]
    assert tg_bot._TelegramRetractionStore(store_path).pending_terminal_count() == 1


def test_restart_replays_same_retry_edit_after_process_death_during_await(monkeypatch, tmp_path):
    store_path = tmp_path / "source-order-retractions.sqlite3"
    monkeypatch.setenv("VIVENTIUM_TELEGRAM_RETRACTION_STORE_PATH", str(store_path))

    class _CrashAfterEditBot(_FakeTelegramBot):
        def __init__(self):
            super().__init__()
            self.crash_once = True

        async def edit_message_text(self, **kwargs):
            result = await super().edit_message_text(**kwargs)
            if self.crash_once and "Please retry your message" in str(kwargs.get("text", "")):
                self.crash_once = False
                raise SystemExit("synthetic process death after Telegram accepted edit")
            return result

    class _Robot:
        async def ask_stream_async(self, *_args, **_kwargs):
            yield {"type": "logical_turn", "logical_turn_id": "turn-edit-await", "revision": 1}
            yield "Current answer before edit-await crash."

        async def source_order_is_current(self, **_kwargs):
            return True

        async def ack_delivery_status(self, *_args):
            return "unavailable"

        def reset(self, *_args, **_kwargs):
            return None

    class _RecoveredRobot:
        async def source_order_is_current(self, **_kwargs):
            return True

    async def _noop_send_librechat_attachments(**_kwargs):
        return None

    monkeypatch.setattr(tg_bot, "Users", types.SimpleNamespace(get_config=lambda *_a, **_k: False))
    monkeypatch.setattr(tg_bot, "should_send_voice_reply", lambda **_k: False)
    monkeypatch.setattr(tg_bot, "send_librechat_attachments", _noop_send_librechat_attachments)
    telegram = _CrashAfterEditBot()
    context = _FakeContext()
    context.bot = telegram

    with pytest.raises(SystemExit, match="accepted edit"):
        asyncio.run(
            tg_bot.getViventiumResponse(
                update_message=_FakeUpdateMessage(),
                context=context,
                title="",
                robot=_Robot(),
                message="source",
                chatid=111,
                messageid=222,
                convo_id="chat-edit-await-crash",
                message_thread_id=77,
                telegram_message_id=222,
            )
        )

    recovery_now = tg_bot.time.time() + 31
    monkeypatch.setattr(tg_bot.time, "time", lambda: recovery_now)
    store = tg_bot._TelegramRetractionStore(store_path, retry_delay_s=0)
    assert asyncio.run(
        tg_bot._retry_pending_source_order_terminals(telegram, _RecoveredRobot(), store)
    ) == 1
    assert store.pending_terminal_count() == 0
    assert len(telegram.messages) == 1
    retry_edits = [
        item for item in telegram.edits if "Please retry your message" in str(item.get("text", ""))
    ]
    assert len(retry_edits) == 2
    assert {item["message_id"] for item in retry_edits} == {1001}


def test_restart_after_retry_notice_atomic_settle_does_not_duplicate(monkeypatch, tmp_path):
    store_path = tmp_path / "source-order-retractions.sqlite3"
    monkeypatch.setenv("VIVENTIUM_TELEGRAM_RETRACTION_STORE_PATH", str(store_path))

    class _Robot:
        async def ask_stream_async(self, *_args, **_kwargs):
            yield {"type": "logical_turn", "logical_turn_id": "turn-settled-crash", "revision": 1}
            yield "Current answer before settled crash."

        async def source_order_is_current(self, **_kwargs):
            return True

        async def ack_delivery_status(self, *_args):
            return "unavailable"

        def reset(self, *_args, **_kwargs):
            return None

    class _RecoveredRobot:
        async def source_order_is_current(self, **_kwargs):
            return True

    async def _noop_send_librechat_attachments(**_kwargs):
        return None

    original_settle = tg_bot._TelegramRetractionStore.settle_pending_terminal

    def _settle_then_crash(store, claim, message_id):
        assert original_settle(store, claim, message_id) is True
        raise SystemExit("synthetic process death after atomic settle")

    monkeypatch.setattr(tg_bot, "Users", types.SimpleNamespace(get_config=lambda *_a, **_k: False))
    monkeypatch.setattr(tg_bot, "should_send_voice_reply", lambda **_k: False)
    monkeypatch.setattr(tg_bot, "send_librechat_attachments", _noop_send_librechat_attachments)
    monkeypatch.setattr(
        tg_bot._TelegramRetractionStore,
        "settle_pending_terminal",
        _settle_then_crash,
    )
    context = _FakeContext()

    with pytest.raises(SystemExit, match="after atomic settle"):
        asyncio.run(
            tg_bot.getViventiumResponse(
                update_message=_FakeUpdateMessage(),
                context=context,
                title="",
                robot=_Robot(),
                message="source",
                chatid=111,
                messageid=222,
                convo_id="chat-crash-after-settle",
                message_thread_id=77,
                telegram_message_id=222,
            )
        )

    monkeypatch.setattr(
        tg_bot._TelegramRetractionStore,
        "settle_pending_terminal",
        original_settle,
    )
    restarted_store = tg_bot._TelegramRetractionStore(store_path, retry_delay_s=0)
    recovery_bot = _FakeTelegramBot()
    assert restarted_store.pending_terminal_count() == 0
    assert asyncio.run(
        tg_bot._retry_pending_source_order_terminals(
            recovery_bot, _RecoveredRobot(), restarted_store
        )
    ) == 0
    assert len(context.bot.messages) == 1
    assert "Please retry your message" in context.bot.edits[-1]["text"]
    assert recovery_bot.messages == []


def test_n_plus_one_during_tts_audio_send_retracts_text_and_audio(monkeypatch):
    latest_source_sequence = 12346
    audio_send_started = asyncio.Event()
    release_audio_send = asyncio.Event()

    class _AudioRaceBot(_FakeTelegramBot):
        async def send_audio(self, **kwargs):
            audio_send_started.set()
            await release_audio_send.wait()
            self.next_id += 1
            self.audios.append(kwargs)
            return _Msg(self.next_id)

    class _Robot:
        def __init__(self):
            self.acks = []

        async def ask_stream_async(self, *args, **kwargs):
            _ = args, kwargs
            yield {"type": "logical_turn", "logical_turn_id": "turn-audio-race", "revision": 1}
            yield "Text and voice."

        async def source_order_is_current(self, **kwargs):
            return int(kwargs["source_sequence"]) >= latest_source_sequence

        async def ack_delivery(self, *args):
            self.acks.append(args)
            return True

        async def ack_delivery_status(self, *args):
            self.acks.append(args)
            return "recorded"

        def get_cached_voice_route(self, _key):
            return None

        def reset(self, *args, **kwargs):
            _ = args, kwargs

    async def _fake_synthesize(*_args, **_kwargs):
        return b"voice-bytes"

    async def _noop_send_librechat_attachments(**_kwargs):
        return None

    async def run_race():
        nonlocal latest_source_sequence
        context = _FakeContext()
        context.bot = _AudioRaceBot()
        robot = _Robot()
        task = asyncio.create_task(
            tg_bot.getViventiumResponse(
                update_message=_FakeUpdateMessage(),
                context=context,
                title="",
                robot=robot,
                message="source",
                chatid=111,
                messageid=12346,
                convo_id="chat-audio-race",
                message_thread_id=None,
                telegram_message_id=12346,
            )
        )
        await audio_send_started.wait()
        latest_source_sequence = 12347
        release_audio_send.set()
        await task
        return context, robot

    monkeypatch.setattr(tg_bot, "Users", types.SimpleNamespace(get_config=lambda *_a, **_k: True))
    monkeypatch.setattr(tg_bot, "synthesize_speech", _fake_synthesize)
    monkeypatch.setattr(tg_bot, "send_librechat_attachments", _noop_send_librechat_attachments)
    monkeypatch.setattr(
        tg_bot,
        "resolve_tts_selection",
        lambda *, voice_route=None: {"provider": "xai", "source": "test", "variant": "Eve"},
    )

    context, robot = asyncio.run(run_race())

    assert context.bot.messages == []
    assert {item["message_id"] for item in context.bot.deletes} == {1001, 1002}
    assert robot.acks == [("turn-audio-race", 1, "partial_removed", "telegram:111")]


def test_n_plus_one_during_attachment_upload_retracts_every_message_id(monkeypatch):
    latest_source_sequence = 12346
    document_send_started = asyncio.Event()
    release_document_send = asyncio.Event()

    class _AttachmentBot(_FakeTelegramBot):
        async def send_document(self, **kwargs):
            document_send_started.set()
            await release_document_send.wait()
            self.next_id += 1
            return _Msg(self.next_id)

    class _Robot:
        def __init__(self):
            self.acks = []

        async def ask_stream_async(self, *args, **kwargs):
            _ = args, kwargs
            yield {"type": "logical_turn", "logical_turn_id": "turn-attachment-race", "revision": 1}
            yield {"type": "attachment", "attachment": {"file_id": "file-1"}}
            yield "Attachment follows."

        async def source_order_is_current(self, **kwargs):
            return int(kwargs["source_sequence"]) >= latest_source_sequence

        async def ack_delivery(self, *args):
            self.acks.append(args)
            return True

        def reset(self, *args, **kwargs):
            _ = args, kwargs

    async def _send_attachment(**kwargs):
        await kwargs["bot"].send_document(chat_id=111, document=b"file")

    async def run_race():
        nonlocal latest_source_sequence
        context = _FakeContext()
        context.bot = _AttachmentBot()
        robot = _Robot()
        task = asyncio.create_task(
            tg_bot.getViventiumResponse(
                update_message=_FakeUpdateMessage(),
                context=context,
                title="",
                robot=robot,
                message="source",
                chatid=111,
                messageid=12346,
                convo_id="chat-attachment-race",
                message_thread_id=None,
                telegram_message_id=12346,
            )
        )
        await document_send_started.wait()
        latest_source_sequence = 12347
        release_document_send.set()
        await task
        return context, robot

    monkeypatch.setattr(tg_bot, "Users", types.SimpleNamespace(get_config=lambda *_a, **_k: False))
    monkeypatch.setattr(tg_bot, "should_send_voice_reply", lambda **_k: False)
    monkeypatch.setattr(tg_bot, "send_librechat_attachments", _send_attachment)

    context, robot = asyncio.run(run_race())

    assert {item["message_id"] for item in context.bot.deletes} == {1001, 1002}
    assert robot.acks == [("turn-attachment-race", 1, "partial_removed", "telegram:111")]


def test_n_plus_one_during_media_group_send_retracts_every_album_message_id():
    latest_source_sequence = 12346
    send_started = asyncio.Event()
    release_send = asyncio.Event()

    class _AlbumBot(_FakeTelegramBot):
        async def send_media_group(self, **_kwargs):
            send_started.set()
            await release_send.wait()
            return [_Msg(2001), _Msg(2002)]

    class _Robot:
        async def source_order_is_current(self, **kwargs):
            return int(kwargs["source_sequence"]) >= latest_source_sequence

    async def run_race():
        nonlocal latest_source_sequence
        bot = _AlbumBot()
        guard = tg_bot._TelegramSourceOrderGuard(
            bot=bot,
            robot=_Robot(),
            telegram_user_id=700,
            chat_id=111,
            thread_id=77,
            source_sequence=12346,
        )
        proxy = tg_bot._SourceOrderedBotProxy(guard)
        task = asyncio.create_task(
            proxy.send_media_group(chat_id=111, media=["a", "b"])
        )
        await send_started.wait()
        latest_source_sequence = 12347
        release_send.set()
        with pytest.raises(tg_bot._StaleTelegramSourceOrder):
            await task
        return bot

    bot = asyncio.run(run_race())
    assert {item["message_id"] for item in bot.deletes} == {2001, 2002}


def test_source_ordered_context_bot_supports_real_callback_context():
    from telegram.ext import CallbackContext

    raw_bot = _FakeTelegramBot()

    class _Robot:
        async def source_order_is_current(self, **_kwargs):
            return True

    guard = tg_bot._TelegramSourceOrderGuard(
        bot=raw_bot,
        robot=_Robot(),
        telegram_user_id=700,
        chat_id=111,
        thread_id=None,
        source_sequence=12346,
    )
    context = CallbackContext(
        application=types.SimpleNamespace(bot=raw_bot),
        chat_id=111,
        user_id=700,
    )

    async def send(guarded_context):
        assert guarded_context is not context
        assert guarded_context.bot is not raw_bot
        await guarded_context.bot.send_message(chat_id=111, text="guarded")
        return "sent"

    result = asyncio.run(
        tg_bot._with_source_ordered_context_bot(context, guard, send)
    )

    assert result == "sent"
    assert context.bot is raw_bot
    assert raw_bot.messages == [{"chat_id": 111, "text": "guarded"}]


def test_n_plus_one_during_account_link_send_retracts_link_prompt(monkeypatch):
    latest_source_sequence = 12346
    link_send_started = asyncio.Event()
    release_link_send = asyncio.Event()

    class _LinkBot(_FakeTelegramBot):
        async def send_message(self, **kwargs):
            link_send_started.set()
            await release_link_send.wait()
            return await super().send_message(**kwargs)

    class _Robot:
        async def ask_stream_async(self, *args, **kwargs):
            _ = args, kwargs
            raise TelegramLinkRequired("https://example.test/link", "Link required")
            yield

        async def source_order_is_current(self, **kwargs):
            return int(kwargs["source_sequence"]) >= latest_source_sequence

        def reset(self, *args, **kwargs):
            _ = args, kwargs

    async def run_race():
        nonlocal latest_source_sequence
        context = _FakeContext()
        context.bot = _LinkBot()
        task = asyncio.create_task(
            tg_bot.getViventiumResponse(
                update_message=_FakeUpdateMessage(),
                context=context,
                title="",
                robot=_Robot(),
                message="source",
                chatid=111,
                messageid=12346,
                convo_id="chat-link-race",
                message_thread_id=None,
                telegram_message_id=12346,
            )
        )
        await link_send_started.wait()
        latest_source_sequence = 12347
        release_link_send.set()
        await task
        return context

    monkeypatch.setattr(tg_bot, "Users", types.SimpleNamespace(get_config=lambda *_a, **_k: False))
    monkeypatch.setattr(tg_bot, "should_send_voice_reply", lambda **_k: False)

    context = asyncio.run(run_race())

    assert context.bot.messages == []


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


@pytest.mark.parametrize("ack_status", ["stale_revision", "stale_source_order"])
def test_get_viventium_response_retracts_just_sent_final_when_commit_ack_is_stale(
    monkeypatch,
    ack_status,
):
    class _StaleAtCommitRobot:
        def __init__(self):
            self.acks = []

        async def ask_stream_async(self, *args, **kwargs):
            _ = args, kwargs
            yield {"type": "logical_turn", "logical_turn_id": "turn-1", "revision": 1}
            yield "Finished locally but obsolete before Telegram commit."

        async def ack_delivery_status(self, *args):
            self.acks.append(args)
            return ack_status

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
        (
            "turn-1",
            1,
            "committed",
            "telegram:111:1001",
            ["telegram:111:1001"],
        ),
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
    context = _FakeContext()
    source_guard = tg_bot._TelegramSourceOrderGuard(
        bot=context.bot,
        robot=robot,
        telegram_user_id=9,
        chat_id=111,
        thread_id=None,
        source_sequence=222,
    )
    source_guard.source_order_scope = "a" * 64
    source_guard.source_event_id = "c" * 64

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
            trace_id="test-source-event",
            telegram_message_id=222,
            telegram_update_id=333,
            _source_guard=source_guard,
        )
    )

    assert robot.kwargs["source_event_id"] == "c" * 64
    assert robot.kwargs["source_order_scope"] == "a" * 64
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
    monkeypatch.setattr(tg_bot, "get_robot", lambda _convo_id: (_FakeRobot(), None, None, None))
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
        effective_chat=types.SimpleNamespace(id="chat-1"),
        effective_message=types.SimpleNamespace(
            message_id=123,
            chat_id="chat-1",
            message_thread_id=None,
            from_user=types.SimpleNamespace(id="user-1"),
            media_group_id=None,
        ),
    )
    context = _FakeContext()

    asyncio.run(tg_bot.handle_file(update, context))

    assert forwarded_calls == []
    assert len(context.bot.messages) == 1
    assert context.bot.messages[0]["text"] == "Temporarily unable to transcribe this video note. Please retry."
    assert "🎤 Transcription" not in context.bot.messages[0]["text"]


def test_captioned_transcription_failure_makes_zero_core_calls_and_one_telegram_error(
    monkeypatch,
):
    forwarded_calls = []
    core_calls = []
    robot_resolution_calls = []

    class _CoreCallRecorder:
        async def observe_source_order(self, **_kwargs):
            core_calls.append("source-order")
            return {
                "latest_source_sequence": 123,
                "stale": False,
                "source_order_scope": "a" * 64,
                "source_event_id": "c" * 64,
            }

        async def source_order_is_current(self, **_kwargs):
            core_calls.append("source-order-current")
            return True

        async def ask_stream_async(self, *_args, **_kwargs):
            core_calls.append("chat")
            yield "must not run"

    robot = _CoreCallRecorder()
    update_message = _FakeUpdateMessage()
    update_message.message_id = 123
    update_message.chat_id = "chat-1"
    update_message.message_thread_id = None
    update_message.media_group_id = None
    update_message.caption = "caption text"
    update_message.voice = types.SimpleNamespace(file_id="voice-1")

    async def _fake_get_message_info(*_args, **_kwargs):
        return (
            "caption text",
            "caption text",
            None,
            "chat-1",
            123,
            None,
            update_message,
            None,
            "chat-1:user-1",
            None,
            None,
            None,
            "Temporarily unable to transcribe this voice note. Please retry.",
            [],
            [],
        )

    async def _fake_get_viventium_response(*args, **kwargs):
        forwarded_calls.append((args, kwargs))

    def _fake_get_robot(convo_id):
        robot_resolution_calls.append(convo_id)
        return robot, None, None, None

    monkeypatch.setattr(tg_bot, "GetMesageInfo", _fake_get_message_info)
    monkeypatch.setattr(tg_bot, "getViventiumResponse", _fake_get_viventium_response)
    monkeypatch.setattr(tg_bot, "get_robot", _fake_get_robot)
    monkeypatch.setattr(tg_bot.config, "BLACK_LIST", None, raising=False)
    monkeypatch.setattr(tg_bot.config, "whitelist", None, raising=False)
    monkeypatch.setattr(tg_bot.config, "GROUP_LIST", None, raising=False)
    monkeypatch.setattr(tg_bot.config, "ADMIN_LIST", None, raising=False)
    monkeypatch.setattr(tg_bot, "Users", types.SimpleNamespace(get_config=lambda *_a, **_k: False))
    monkeypatch.setattr(tg_bot, "remove_job_if_exists", lambda *_a, **_k: None)
    context = _FakeCommandContext()
    context.bot = _FakeTelegramBot()
    update = types.SimpleNamespace(
        update_id=456,
        effective_user=update_message.from_user,
        effective_chat=types.SimpleNamespace(id="chat-1"),
        effective_message=update_message,
        message=update_message,
        edited_message=None,
        channel_post=None,
        edited_channel_post=None,
    )

    asyncio.run(tg_bot.command_bot(update, context, has_command=False))

    assert core_calls == []
    assert robot_resolution_calls == []
    assert forwarded_calls == []
    assert len(context.bot.messages) == 1
    assert context.bot.messages[0]["text"] == (
        "Temporarily unable to transcribe this voice note. Please retry."
    )


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
    monkeypatch.setattr(tg_bot, "get_robot", lambda _convo_id: (_FakeRobot(), None, None, None))
    monkeypatch.setattr(tg_bot.config, "BLACK_LIST", None, raising=False)
    monkeypatch.setattr(tg_bot.config, "whitelist", None, raising=False)
    monkeypatch.setattr(tg_bot.config, "GROUP_LIST", None, raising=False)
    monkeypatch.setattr(tg_bot.config, "ADMIN_LIST", None, raising=False)

    update = types.SimpleNamespace(
        effective_user=types.SimpleNamespace(id="user-1", username="user"),
        effective_chat=types.SimpleNamespace(id="chat-1"),
        effective_message=types.SimpleNamespace(
            message_id=123,
            chat_id="chat-1",
            message_thread_id=None,
            from_user=types.SimpleNamespace(id="user-1"),
            media_group_id=None,
        ),
    )
    context = _FakeContext()

    asyncio.run(tg_bot.handle_file(update, context))

    assert forwarded_calls == []
    assert len(context.bot.messages) == 1
    assert "deck.pptx" in context.bot.messages[0]["text"]
    assert "timed out" in context.bot.messages[0]["text"]


def test_handle_file_preserves_reply_provenance_and_quoted_document_text(monkeypatch):
    forwarded_calls = []
    replied = types.SimpleNamespace(
        message_id=91,
        text=None,
        caption="Source document",
        date=None,
        from_user=types.SimpleNamespace(id=700, is_bot=True),
        document=types.SimpleNamespace(file_id="quoted-doc", file_name="source.pdf"),
        audio=None,
        video=None,
        voice=None,
        animation=None,
        sticker=None,
        photo=[],
    )
    update_message = types.SimpleNamespace(
        message_id=123,
        chat_id="chat-1",
        message_thread_id=None,
        from_user=types.SimpleNamespace(id="user-1"),
        media_group_id=None,
        chat=types.SimpleNamespace(type="private"),
        reply_to_message=replied,
    )

    async def _fake_get_message_info(*_args, **_kwargs):
        return (
            "review the attached file",
            "review the attached file",
            None,
            "chat-1",
            123,
            None,
            update_message,
            None,
            "chat-1:user-1",
            "/tmp/current.pdf",
            "Quoted document evidence",
            None,
            None,
            [{"filename": "current.pdf", "data": "synthetic"}],
            [],
        )

    async def _fake_get_viventium_response(*args, **kwargs):
        forwarded_calls.append((args, kwargs))

    monkeypatch.setattr(tg_bot, "GetMesageInfo", _fake_get_message_info)
    monkeypatch.setattr(tg_bot, "getViventiumResponse", _fake_get_viventium_response)
    monkeypatch.setattr(tg_bot, "get_robot", lambda _convo_id: (_FakeRobot(), None, None, None))
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
        update_id=321,
        effective_user=types.SimpleNamespace(id="user-1", username="user"),
        effective_chat=types.SimpleNamespace(id="chat-1"),
        effective_message=update_message,
    )
    context = _FakeContext()
    context.bot.id = 700

    asyncio.run(tg_bot.handle_file(update, context))

    assert len(forwarded_calls) == 1
    reply_context = forwarded_calls[0][1]["reply_context"]
    assert reply_context["repliedTelegramMessageId"] == "91"
    assert reply_context["attachments"][0]["extractedText"] == "Quoted document evidence"


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
    update_message.message_id = 42
    update_message.chat_id = "chat-1"
    update_message.message_thread_id = None
    update_message.media_group_id = None
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
        effective_message=update_message,
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
