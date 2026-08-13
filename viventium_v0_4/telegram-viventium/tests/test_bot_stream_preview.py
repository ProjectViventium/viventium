import asyncio
import html
import re
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
from utils.telegram_chunks import telegram_text_units  # noqa: E402
from utils.telegram_html import strip_html_tags  # noqa: E402


class _Msg:
    def __init__(self, mid: int) -> None:
        self.message_id = mid


class _FakeTelegramBot:
    def __init__(self) -> None:
        self.messages = []
        self.edits = []
        self.audios = []
        self.deletes = []
        self.next_id = 1000
        self.edit_error = None
        self.edit_errors = []
        self.send_errors = []
        self.sent_ids = []
        self.current_messages = {}

    async def send_chat_action(self, **_kwargs):
        return None

    async def send_message(self, **kwargs):
        if self.send_errors:
            error = self.send_errors.pop(0)
            if error:
                raise error
        self.messages.append(kwargs)
        self.next_id += 1
        message_id = self.next_id
        self.sent_ids.append(message_id)
        self.current_messages[message_id] = kwargs
        return _Msg(message_id)

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
        self.current_messages.pop(_kwargs.get("message_id"), None)
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
    assert "First thought." in str(context.bot.edits[-1]["text"])
    assert "Second thought." in str(context.bot.messages[-1]["text"])
    assert synthesized == ["First thought. Second thought."]
    assert len(context.bot.audios) == 1


def test_message_break_transient_edit_failure_retries_without_duplicate_or_drop(monkeypatch):
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
    monkeypatch.setattr(
        tg_bot,
        "resolve_tts_selection",
        lambda *, voice_route=None: {"provider": "xai", "source": "test", "variant": "Eve"},
    )

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
    assert context.bot.current_messages[context.bot.sent_ids[0]]["parse_mode"] == "HTML"
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
    context.bot.edit_error = RuntimeError("synthetic persistent outage")

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

    assert len(context.bot.messages) == 2
    visible = [strip_html_tags(item) for item in _final_delivered_texts(context)]
    assert visible[0] == "First thought.\n\nSecond thought."
    assert visible[1] == tg_bot.TELEGRAM_DELIVERY_INTERRUPTED_NOTICE
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

    assert context.bot.deletes == []
    assert _final_delivered_texts(context) == [
        "Draft preview.",
        "Final continuation.",
    ]
    assert context.bot.edits[-1]["text"] == "Draft preview."
    assert context.bot.messages[-2]["reply_to_message_id"] == 222
    assert "reply_to_message_id" not in context.bot.messages[-1]
    assert robot.acks == [
        ("turn-1", 3, "committed", f"telegram:111:{context.bot.next_id}"),
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
    assert context.bot.deletes == []
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
    assert context.bot.current_messages == {}


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
