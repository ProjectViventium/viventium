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

_fake_pil = types.ModuleType("PIL")
_fake_pil_image = types.ModuleType("PIL.Image")
_fake_pil.Image = _fake_pil_image
sys.modules.setdefault("PIL", _fake_pil)
sys.modules.setdefault("PIL.Image", _fake_pil_image)

import bot as tg_bot  # noqa: E402
from utils.librechat_bridge import TelegramLinkRequired  # noqa: E402


class _Msg:
    def __init__(self, mid: int) -> None:
        self.message_id = mid


class _FakeTelegramBot:
    def __init__(self) -> None:
        self.messages = []
        self.edits = []
        self.audios = []
        self.next_id = 1000

    async def send_chat_action(self, **_kwargs):
        return None

    async def send_message(self, **kwargs):
        self.messages.append(kwargs)
        self.next_id += 1
        return _Msg(self.next_id)

    async def edit_message_text(self, **kwargs):
        self.edits.append(kwargs)
        return None

    async def delete_message(self, **_kwargs):
        return None

    async def send_media_group(self, **_kwargs):
        return None

    async def send_audio(self, **_kwargs):
        self.audios.append(_kwargs)
        return None

    async def send_document(self, **_kwargs):
        return None


class _FakeContext:
    def __init__(self) -> None:
        self.bot = _FakeTelegramBot()


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
    username = "adri"


class _FakeChat:
    type = "private"


class _FakeUpdateMessage:
    def __init__(self) -> None:
        self.from_user = _FakeUser()
        self.chat = _FakeChat()
        self.date = datetime.now(timezone.utc)
        self.reply_text_calls = []

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


def test_handle_file_does_not_forward_failed_transcription(monkeypatch):
    forwarded_calls = []

    async def _fake_wrapper_get_message_info(*_args, **_kwargs):
        return _make_message_info(voice_error_text=None)

    async def _fake_handle_get_message_info(*_args, **_kwargs):
        return _make_message_info(
            voice_error_text="Temporarily unable to transcribe this video note. Please retry."
        )

    async def _fake_get_viventium_response(*args, **kwargs):
        forwarded_calls.append((args, kwargs))
        return None

    monkeypatch.setattr(tg_bot.decorators, "GetMesageInfo", _fake_wrapper_get_message_info)
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
