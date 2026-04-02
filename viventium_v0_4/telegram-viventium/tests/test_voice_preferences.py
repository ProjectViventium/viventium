import sys
from pathlib import Path

import pytest
import types

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
TELEGRAM_ROOT = ROOT / "TelegramVivBot"
if str(TELEGRAM_ROOT) not in sys.path:
    sys.path.insert(0, str(TELEGRAM_ROOT))

from TelegramVivBot.utils.voice import should_send_voice_reply

# === VIVENTIUM START ===
# Feature: Provide a minimal config stub so utils.scripts avoids full config import.
_fake_config = types.SimpleNamespace(VIVENTIUM_TELEGRAM_BACKEND="librechat")
sys.modules.setdefault("config", _fake_config)
# === VIVENTIUM END ===

from TelegramVivBot.utils import scripts

# === VIVENTIUM START ===
# Feature: Validate callback-query preference routing uses the requesting user.
class _DummyUser:
    def __init__(self, user_id):
        self.id = user_id


class _DummyMessage:
    def __init__(self, chat_id, user_id):
        self.chat_id = chat_id
        self.from_user = _DummyUser(user_id)
        self.is_topic_message = False
        self.message_thread_id = None
        self.message_id = 123
        self.text = None
        self.reply_to_message = None
        self.photo = None
        self.voice = None
        self.audio = None
        self.video_note = None
        self.video = None
        self.document = None
        self.caption = None
# === VIVENTIUM END ===



def test_should_send_voice_reply_requires_enabled():
    assert (
        should_send_voice_reply(
            voice_note_detected=True,
            always_voice=False,
            voice_enabled=False,
            text="hello",
        )
        is False
    )


def test_should_send_voice_reply_requires_text():
    assert (
        should_send_voice_reply(
            voice_note_detected=True,
            always_voice=False,
            voice_enabled=True,
            text="   ",
        )
        is False
    )


def test_should_send_voice_reply_voice_note():
    assert (
        should_send_voice_reply(
            voice_note_detected=True,
            always_voice=False,
            voice_enabled=True,
            text="hello",
        )
        is True
    )


def test_should_send_voice_reply_always_voice():
    assert (
        should_send_voice_reply(
            voice_note_detected=False,
            always_voice=True,
            voice_enabled=True,
            text="hello",
        )
        is True
    )


@pytest.mark.asyncio
async def test_get_message_override_user_id_applies_to_convo_id():
    message = _DummyMessage(chat_id="chat-1", user_id="bot-1")
    _, _, _, _, _, _, _, convo_id, _, _, _, _ = await scripts.GetMesage(
        message,
        context=None,
        voice=False,
        override_user_id="user-42",
    )
    assert convo_id == "chat-1:user-42"
