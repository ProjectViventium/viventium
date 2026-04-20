import asyncio
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

_fake_pil = types.ModuleType("PIL")
_fake_pil_image = types.ModuleType("PIL.Image")
_fake_pil.Image = _fake_pil_image
sys.modules.setdefault("PIL", _fake_pil)
sys.modules.setdefault("PIL.Image", _fake_pil_image)

_fake_aient_pkg = sys.modules.setdefault("aient", types.ModuleType("aient"))
_fake_aient_inner_pkg = sys.modules.setdefault("aient.aient", types.ModuleType("aient.aient"))
_fake_aient_utils_pkg = sys.modules.setdefault("aient.aient.utils", types.ModuleType("aient.aient.utils"))
_fake_aient_scripts = types.ModuleType("aient.aient.utils.scripts")


async def _fake_document_extract(*_args, **_kwargs):
    return None


def _fake_extract_audio_from_video(path):
    return path


def _fake_transcribe_audio_file(_path):
    return ""


def _fake_get_audio_message(_file_bytes):
    return ""


_fake_aient_scripts.Document_extract = _fake_document_extract
_fake_aient_scripts.extract_audio_from_video = _fake_extract_audio_from_video
_fake_aient_scripts.transcribe_audio_file = _fake_transcribe_audio_file
_fake_aient_scripts.get_audio_message = _fake_get_audio_message

_fake_aient_pkg.aient = _fake_aient_inner_pkg
_fake_aient_inner_pkg.utils = _fake_aient_utils_pkg
_fake_aient_utils_pkg.scripts = _fake_aient_scripts
sys.modules["aient.aient.utils.scripts"] = _fake_aient_scripts

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


def test_get_message_override_user_id_applies_to_convo_id():
    message = _DummyMessage(chat_id="chat-1", user_id="bot-1")
    _, _, _, _, _, _, _, convo_id, _, _, _, _, _ = asyncio.run(
        scripts.GetMesage(
            message,
            context=None,
            voice=False,
            override_user_id="user-42",
        )
    )
    assert convo_id == "chat-1:user-42"


def test_get_voice_surfaces_oversize_as_structured_error(monkeypatch):
    async def _fake_download(*_args, **_kwargs):
        return scripts.TelegramDownloadResult(error_code="file_too_large")

    monkeypatch.setattr(scripts, "download_telegram_file_result", _fake_download)

    result = asyncio.run(scripts.get_voice("voice-file", types.SimpleNamespace(bot=object())))

    assert result.text is None
    assert result.error_code == "file_too_large"
    assert result.error_text == "This voice note is too large to transcribe in Telegram right now."


@pytest.mark.parametrize(
    "error_message",
    [
        "File is too big",
        "Request Entity Too Large",
        "Bad Request: entity_content_too_large",
    ],
)
def test_download_telegram_file_result_classifies_oversize_exception(error_message):
    class _OversizeBot:
        async def get_file(self, *_args, **_kwargs):
            raise RuntimeError(error_message)

    result = asyncio.run(scripts.download_telegram_file_result(_OversizeBot(), "video-file"))

    assert result.file_bytes is None
    assert result.error_code == "file_too_large"


def test_transcribe_video_surfaces_download_failure_as_structured_error(monkeypatch):
    async def _fake_download(*_args, **_kwargs):
        return scripts.TelegramDownloadResult(error_code="download_failed")

    monkeypatch.setattr(scripts, "download_telegram_file_result", _fake_download)

    result = asyncio.run(
        scripts.transcribe_video(
            "video-file",
            types.SimpleNamespace(bot=object()),
            media_label="video note",
        )
    )

    assert result.text is None
    assert result.error_code == "download_failed"
    assert result.error_text == "Temporarily unable to download this video note from Telegram. Please retry."


def test_get_voice_surfaces_download_timeout_as_structured_error(monkeypatch):
    async def _fake_download(*_args, **_kwargs):
        return scripts.TelegramDownloadResult(error_code="download_timeout")

    monkeypatch.setattr(scripts, "download_telegram_file_result", _fake_download)

    result = asyncio.run(scripts.get_voice("voice-file", types.SimpleNamespace(bot=object())))

    assert result.text is None
    assert result.error_code == "download_timeout"
    assert result.error_text == "Timed out downloading this voice note from Telegram. Please retry."
