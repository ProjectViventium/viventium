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
_fake_aient_core_pkg = sys.modules.setdefault("aient.aient.core", types.ModuleType("aient.aient.core"))
_fake_aient_models_pkg = sys.modules.setdefault("aient.aient.models", types.ModuleType("aient.aient.models"))
_fake_aient_scripts = types.ModuleType("aient.aient.utils.scripts")
_fake_aient_core_utils = types.ModuleType("aient.aient.core.utils")
_fake_aient_whisper = types.ModuleType("aient.aient.models.whisper")
_fake_aient_assemblyai = types.ModuleType("aient.aient.models.assemblyai")


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


class _FakeBaseAPI:
    def __init__(self, api_url: str = "", **_kwargs):
        self.chat_url = api_url
        self.audio_speech = api_url


class _FakeAssemblyAI:
    def __init__(self, *_args, **_kwargs):
        pass


_fake_aient_core_utils.get_engine = lambda *_args, **_kwargs: None
_fake_aient_core_utils.BaseAPI = _FakeBaseAPI
_fake_aient_assemblyai.AssemblyAI = _FakeAssemblyAI

_fake_aient_pkg.aient = _fake_aient_inner_pkg
_fake_aient_inner_pkg.utils = _fake_aient_utils_pkg
_fake_aient_inner_pkg.core = _fake_aient_core_pkg
_fake_aient_inner_pkg.models = _fake_aient_models_pkg
_fake_aient_utils_pkg.scripts = _fake_aient_scripts
_fake_aient_core_pkg.utils = _fake_aient_core_utils
_fake_aient_models_pkg.whisper = _fake_aient_whisper
_fake_aient_models_pkg.assemblyai = _fake_aient_assemblyai
sys.modules["aient.aient.utils.scripts"] = _fake_aient_scripts
sys.modules["aient.aient.core.utils"] = _fake_aient_core_utils
sys.modules["aient.aient.models.whisper"] = _fake_aient_whisper
sys.modules["aient.aient.models.assemblyai"] = _fake_aient_assemblyai

from TelegramVivBot.utils.voice import (
    should_request_audio_reply,
    should_request_voice_mode,
    should_send_voice_reply,
)

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


def test_should_request_audio_reply_for_voice_note():
    assert (
        should_request_audio_reply(
            voice_note_detected=True,
            always_voice=False,
            voice_enabled=True,
        )
        is True
    )


def test_should_request_audio_reply_for_always_voice_text():
    assert (
        should_request_audio_reply(
            voice_note_detected=False,
            always_voice=True,
            voice_enabled=True,
        )
        is True
    )


def test_should_request_audio_reply_honors_string_disabled_value():
    assert (
        should_request_audio_reply(
            voice_note_detected=True,
            always_voice=True,
            voice_enabled="false",
        )
        is False
    )


def test_telegram_never_requests_librechat_voice_call_mode():
    assert (
        should_request_voice_mode(
            voice_note_detected=True,
            always_voice=True,
            voice_enabled=True,
        )
        is False
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
    monkeypatch.setattr(scripts, "ffmpeg_runtime_ready", lambda: True)

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


def test_get_voice_surfaces_broken_local_decoder_as_structured_error(monkeypatch):
    async def _fake_download(*_args, **_kwargs):
        return scripts.TelegramDownloadResult(file_bytes=b"voice-bytes")

    monkeypatch.setattr(scripts, "download_telegram_file_result", _fake_download)
    monkeypatch.setattr(scripts.config, "WHISPER_MODE", "pywhispercpp", raising=False)
    monkeypatch.setattr(scripts, "ffmpeg_runtime_ready", lambda: False)

    result = asyncio.run(scripts.get_voice("voice-file", types.SimpleNamespace(bot=object())))

    assert result.text is None
    assert result.error_code == "media_decoder_unavailable"
    assert (
        result.error_text
        == "Temporarily unable to transcribe this voice note because Telegram media decoding is not ready. Run bin/viventium upgrade, then retry."
    )


def test_get_voice_serializes_local_whisper_transcription(monkeypatch):
    async def _fake_download(*_args, **_kwargs):
        return scripts.TelegramDownloadResult(file_bytes=b"voice-bytes")

    active = {"count": 0, "max": 0}

    def _fake_transcribe(_file_bytes):
        active["count"] += 1
        active["max"] = max(active["max"], active["count"])
        import time

        time.sleep(0.03)
        active["count"] -= 1
        return "hello"

    monkeypatch.setattr(scripts, "download_telegram_file_result", _fake_download)
    monkeypatch.setattr(scripts.config, "WHISPER_MODE", "pywhispercpp", raising=False)
    monkeypatch.setattr(scripts, "ffmpeg_runtime_ready", lambda: True)
    monkeypatch.setattr(scripts, "_get_audio_message_sync", _fake_transcribe)

    async def _run_pair():
        context = types.SimpleNamespace(bot=object())
        return await asyncio.gather(
            scripts.get_voice("voice-file-a", context),
            scripts.get_voice("voice-file-b", context),
        )

    first, second = asyncio.run(_run_pair())

    assert first.text == "hello"
    assert second.text == "hello"
    assert active["max"] == 1


def test_transcribe_video_surfaces_broken_decoder_as_structured_error(monkeypatch):
    monkeypatch.setattr(scripts, "ffmpeg_runtime_ready", lambda: False)

    result = asyncio.run(
        scripts.transcribe_video(
            "video-file",
            types.SimpleNamespace(bot=object()),
            media_label="video note",
        )
    )

    assert result.text is None
    assert result.error_code == "media_decoder_unavailable"
    assert (
        result.error_text
        == "Temporarily unable to transcribe this video note because Telegram media decoding is not ready. Run bin/viventium upgrade, then retry."
    )


def test_transcribe_video_uses_serialized_transcription_path(monkeypatch, tmp_path):
    async def _fake_download(*_args, **_kwargs):
        return scripts.TelegramDownloadResult(file_bytes=b"video-bytes", filename="clip.mp4")

    def _fake_extract_audio(video_path):
        audio_path = tmp_path / f"{Path(video_path).name}.ogg"
        audio_path.write_bytes(b"audio-bytes")
        return str(audio_path)

    active = {"count": 0, "max": 0}

    def _fake_transcribe(_file_bytes):
        active["count"] += 1
        active["max"] = max(active["max"], active["count"])
        import time

        time.sleep(0.03)
        active["count"] -= 1
        return "video hello"

    monkeypatch.setattr(scripts, "download_telegram_file_result", _fake_download)
    monkeypatch.setattr(scripts, "ffmpeg_runtime_ready", lambda: True)
    monkeypatch.setattr(scripts.config, "WHISPER_MODE", "pywhispercpp", raising=False)
    monkeypatch.setattr(scripts, "_get_audio_message_sync", _fake_transcribe)
    monkeypatch.setattr(_fake_aient_scripts, "extract_audio_from_video", _fake_extract_audio)

    async def _run_pair():
        context = types.SimpleNamespace(bot=object())
        return await asyncio.gather(
            scripts.transcribe_video("video-a", context),
            scripts.transcribe_video("video-b", context),
        )

    first, second = asyncio.run(_run_pair())

    assert first.text == "video hello"
    assert second.text == "video hello"
    assert active["max"] == 1


def test_get_voice_surfaces_download_timeout_as_structured_error(monkeypatch):
    async def _fake_download(*_args, **_kwargs):
        return scripts.TelegramDownloadResult(error_code="download_timeout")

    monkeypatch.setattr(scripts, "download_telegram_file_result", _fake_download)

    result = asyncio.run(scripts.get_voice("voice-file", types.SimpleNamespace(bot=object())))

    assert result.text is None
    assert result.error_code == "download_timeout"
    assert result.error_text == "Timed out downloading this voice note from Telegram. Please retry."
