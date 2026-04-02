# VIVENTIUM START
# File: test_stt_telegram_assemblyai.py
# Purpose: Validate Telegram STT dispatch uses AssemblyAI path.
# VIVENTIUM END
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
TELEGRAM_ROOT = ROOT / "TelegramVivBot"
if str(TELEGRAM_ROOT) not in sys.path:
    sys.path.insert(0, str(TELEGRAM_ROOT))

from TelegramVivBot.aient.aient.utils.scripts import get_audio_message


class StubAssemblyAI:
    def __init__(self):
        self.last_bytes = None

    def transcribe_bytes(self, audio_bytes: bytes) -> str:
        self.last_bytes = audio_bytes
        return "hello assembly"


def test_get_audio_message_assemblyai_path(monkeypatch):
    stub = StubAssemblyAI()
    config_stub = types.SimpleNamespace(
        WHISPER_MODE="assemblyai",
        assemblyai_client=stub,
        local_whisper=None,
        whisperBot=None,
        LOCAL_WHISPER_LANG="en",
        LOCAL_WHISPER_VERBOSE=False,
    )
    monkeypatch.setitem(sys.modules, "config", config_stub)

    payload = b"test-audio"
    text = get_audio_message(payload)
    assert text == "hello assembly"
    assert stub.last_bytes == payload


def test_get_audio_message_assemblyai_lazy_init(monkeypatch):
    stub = StubAssemblyAI()
    calls = {"count": 0}

    def ensure_stt_engine():
        calls["count"] += 1
        config_stub.assemblyai_client = stub

    config_stub = types.SimpleNamespace(
        WHISPER_MODE="assemblyai",
        assemblyai_client=None,
        local_whisper=None,
        whisperBot=None,
        ensure_stt_engine=ensure_stt_engine,
        LOCAL_WHISPER_LANG="en",
        LOCAL_WHISPER_VERBOSE=False,
    )
    monkeypatch.setitem(sys.modules, "config", config_stub)

    payload = b"lazy-audio"
    text = get_audio_message(payload)
    assert text == "hello assembly"
    assert calls["count"] == 1
    assert stub.last_bytes == payload


class StubLocalWhisper:
    def __init__(self):
        self.calls = []

    def transcribe(self, file_path, language, translate, print_realtime):
        self.calls.append(
            {
                "file_path": file_path,
                "language": language,
                "translate": translate,
                "print_realtime": print_realtime,
            }
        )
        return [types.SimpleNamespace(text="hello"), types.SimpleNamespace(text="local")]


def test_get_audio_message_local_whisper_lazy_init(monkeypatch):
    stub = StubLocalWhisper()
    calls = {"count": 0}

    def ensure_stt_engine():
        calls["count"] += 1
        config_stub.local_whisper = stub

    config_stub = types.SimpleNamespace(
        WHISPER_MODE="pywhispercpp",
        assemblyai_client=None,
        local_whisper=None,
        whisperBot=None,
        ensure_stt_engine=ensure_stt_engine,
        LOCAL_WHISPER_LANG="en",
        LOCAL_WHISPER_VERBOSE=False,
    )
    monkeypatch.setitem(sys.modules, "config", config_stub)

    payload = b"local-audio"
    text = get_audio_message(payload)
    assert text == "hello local"
    assert calls["count"] == 1
    assert len(stub.calls) == 1
