from pathlib import Path
from io import BytesIO
import json
import sys
import types
import wave

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
TELEGRAM_ROOT = ROOT / "TelegramVivBot"
if str(TELEGRAM_ROOT) not in sys.path:
    sys.path.insert(0, str(TELEGRAM_ROOT))

from TelegramVivBot.utils import tts as tts_module


def _test_wav_bytes(frame_value: bytes = b"\x00\x00") -> bytes:
    output = BytesIO()
    with wave.open(output, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(44100)
        wav_file.writeframes(frame_value)
    return output.getvalue()


def _fake_config(**overrides):
    values = {
        "Users": types.SimpleNamespace(
            get_config=lambda _convo_id, key: None,
        ),
        "API_KEY": "openai-key",
        "BASE_URL": "https://api.openai.com/v1",
        "CARTESIA_API_KEY": "",
        "TTS_MODEL": "gpt-4o-mini-tts",
        "TTS_VOICE": "alloy",
        "TTS_RESPONSE_FORMAT": "mp3",
        "TTS_PROVIDER": "openai",
        "TTS_PROVIDER_PRIMARY": "openai",
        "TTS_PROVIDER_FALLBACK": "",
        "TTS_VOICE_ELEVENLABS": "voice-id",
        "ELEVENLABS_API_KEY": "",
        "ELEVENLABS_API_URL": "https://api.elevenlabs.io",
        "ELEVENLABS_MODEL": "eleven_turbo_v2_5",
        "ELEVENLABS_STABILITY": None,
        "ELEVENLABS_SIMILARITY": None,
        "ELEVENLABS_STYLE": None,
        "ELEVENLABS_USE_SPEAKER_BOOST": None,
        "ELEVENLABS_SPEED": None,
        "VIVENTIUM_CARTESIA_API_URL": "https://api.cartesia.ai/tts/bytes",
        "VIVENTIUM_CARTESIA_API_VERSION": "2026-03-01",
        "VIVENTIUM_CARTESIA_EMOTION": "neutral",
        "VIVENTIUM_CARTESIA_LANGUAGE": "en",
        "VIVENTIUM_CARTESIA_MODEL_ID": "sonic-3",
        "VIVENTIUM_CARTESIA_SAMPLE_RATE": 44100,
        "VIVENTIUM_CARTESIA_SPEED": 1.0,
        "VIVENTIUM_CARTESIA_VOICE_ID": "voice-id",
        "VIVENTIUM_CARTESIA_VOLUME": 1.0,
    }
    values.update(overrides)
    return types.SimpleNamespace(**values)


def test_resolve_tts_selection_prefers_supported_saved_chatterbox(monkeypatch):
    monkeypatch.setitem(
        sys.modules,
        "config",
        _fake_config(
            TTS_PROVIDER_PRIMARY="openai",
            TTS_PROVIDER_FALLBACK="",
        ),
    )
    monkeypatch.setattr(
        tts_module,
        "_is_local_chatterbox_supported",
        lambda: (True, None),
    )

    resolved = tts_module.resolve_tts_selection(
        voice_route={
            "tts": {
                "provider": "local_chatterbox_turbo_mlx_8bit",
                "variant": "mlx-community/chatterbox-turbo-8bit",
            }
        }
    )

    assert resolved["provider"] == "local_chatterbox_turbo_mlx_8bit"
    assert resolved["variant"] == "mlx-community/chatterbox-turbo-8bit"
    assert resolved["source"] == "saved"


def test_resolve_tts_selection_falls_back_when_saved_chatterbox_is_unavailable(monkeypatch):
    monkeypatch.setitem(
        sys.modules,
        "config",
        _fake_config(
            TTS_PROVIDER_PRIMARY="openai",
            TTS_PROVIDER_FALLBACK="",
        ),
    )
    monkeypatch.setattr(
        tts_module,
        "_is_local_chatterbox_supported",
        lambda: (False, "mlx_lm is not installed"),
    )

    resolved = tts_module.resolve_tts_selection(
        voice_route={
            "tts": {
                "provider": "local_chatterbox_turbo_mlx_8bit",
                "variant": "mlx-community/chatterbox-turbo-8bit",
            }
        }
    )

    assert resolved["provider"] == "openai"
    assert resolved["source"] == "default"


def test_resolve_tts_selection_treats_cartesia_variant_as_voice_id(monkeypatch):
    monkeypatch.setitem(
        sys.modules,
        "config",
        _fake_config(
            CARTESIA_API_KEY="cartesia-key",
            TTS_PROVIDER_PRIMARY="openai",
            TTS_PROVIDER_FALLBACK="",
        ),
    )

    resolved = tts_module.resolve_tts_selection(
        voice_route={
            "tts": {
                "provider": "cartesia",
                "variant": "6ccbfb76-1fc6-48f7-b71d-91ac6298247b",
            }
        }
    )

    assert resolved["provider"] == "cartesia"
    assert resolved["variant"] == "6ccbfb76-1fc6-48f7-b71d-91ac6298247b"
    assert resolved["source"] == "saved"


def test_is_local_chatterbox_supported_requires_full_import_chain(monkeypatch):
    monkeypatch.setattr(tts_module.sys, "platform", "darwin", raising=False)

    def _fake_find_spec(name):
        if name == "mlx_audio":
            return object()
        if name == "mlx_lm":
            return None
        return object()

    monkeypatch.setattr(tts_module.importlib.util, "find_spec", _fake_find_spec)

    supported, reason = tts_module._is_local_chatterbox_supported()

    assert supported is False
    assert reason == "mlx_lm is not installed"


@pytest.mark.asyncio
async def test_synthesize_speech_uses_local_chatterbox_branch_and_preserves_markers(monkeypatch):
    seen = {}

    monkeypatch.setitem(
        sys.modules,
        "config",
        _fake_config(
            TTS_PROVIDER_PRIMARY="openai",
            TTS_PROVIDER_FALLBACK="",
        ),
    )
    monkeypatch.setattr(
        tts_module,
        "_is_local_chatterbox_supported",
        lambda: (True, None),
    )

    def _fake_synthesize_wav_bytes(text, *, config):
        seen["text"] = text
        seen["model_id"] = getattr(config, "model_id", None)
        return b"wav-bytes"

    monkeypatch.setattr(
        tts_module,
        "_build_local_chatterbox_config",
        lambda model_id_override=None: (
            types.SimpleNamespace(model_id=model_id_override or "mlx-community/chatterbox-turbo-8bit"),
            _fake_synthesize_wav_bytes,
        ),
    )

    class _FailClient:
        def __init__(self, *args, **kwargs):
            raise AssertionError("HTTP client should not be used for local Chatterbox synthesis")

    monkeypatch.setattr(tts_module.httpx, "AsyncClient", _FailClient)

    voice_bytes = await tts_module.synthesize_speech(
        "Hello [laugh]",
        "conv-1",
        voice_route={
            "tts": {
                "provider": "local_chatterbox_turbo_mlx_8bit",
                "variant": "mlx-community/chatterbox-turbo-8bit",
            }
        },
    )

    assert voice_bytes == b"wav-bytes"
    assert seen["text"] == "Hello [laugh]"
    assert seen["model_id"] == "mlx-community/chatterbox-turbo-8bit"


@pytest.mark.asyncio
async def test_synthesize_speech_cartesia_uses_voice_variant_not_model_id(monkeypatch):
    seen = {}
    lyra_voice_id = "6ccbfb76-1fc6-48f7-b71d-91ac6298247b"

    monkeypatch.setitem(
        sys.modules,
        "config",
        _fake_config(
            CARTESIA_API_KEY="cartesia-key",
            TTS_PROVIDER_PRIMARY="openai",
            TTS_PROVIDER_FALLBACK="",
            VIVENTIUM_CARTESIA_MODEL_ID="sonic-2",
            VIVENTIUM_CARTESIA_VOICE_ID="default-voice-id",
        ),
    )

    class _Response:
        content = b"wav-bytes"

        def raise_for_status(self):
            return None

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, *, headers=None, content=None, **_kwargs):
            seen["url"] = url
            seen["headers"] = headers or {}
            seen["payload"] = json.loads(content)
            return _Response()

    monkeypatch.setattr(tts_module.httpx, "AsyncClient", _Client)

    voice_bytes = await tts_module.synthesize_speech(
        "Hello.",
        "conv-1",
        voice_route={
            "tts": {
                "provider": "cartesia",
                "variant": lyra_voice_id,
            }
        },
    )

    assert voice_bytes == b"wav-bytes"
    assert seen["headers"]["Cartesia-Version"] == "2026-03-01"
    assert seen["payload"]["model_id"] == "sonic-3"
    assert seen["payload"]["voice"] == {"mode": "id", "id": lyra_voice_id}


@pytest.mark.asyncio
async def test_synthesize_speech_cartesia_ignores_legacy_model_variant(monkeypatch):
    seen = {}

    monkeypatch.setitem(
        sys.modules,
        "config",
        _fake_config(
            CARTESIA_API_KEY="cartesia-key",
            TTS_PROVIDER_PRIMARY="cartesia",
            TTS_PROVIDER_FALLBACK="",
            VIVENTIUM_CARTESIA_VOICE_ID="default-voice-id",
        ),
    )

    class _Response:
        content = b"wav-bytes"

        def raise_for_status(self):
            return None

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, _url, *, content=None, **_kwargs):
            seen["payload"] = json.loads(content)
            return _Response()

    monkeypatch.setattr(tts_module.httpx, "AsyncClient", _Client)

    voice_bytes = await tts_module.synthesize_speech(
        "Hello.",
        "conv-1",
        voice_route={
            "tts": {
                "provider": "cartesia",
                "variant": "sonic-2",
            }
        },
    )

    assert voice_bytes == b"wav-bytes"
    assert seen["payload"]["model_id"] == "sonic-3"
    assert seen["payload"]["voice"] == {"mode": "id", "id": "default-voice-id"}


@pytest.mark.asyncio
async def test_synthesize_speech_cartesia_preserves_voice_markup_and_sets_emotion(monkeypatch):
    seen = {}

    monkeypatch.setitem(
        sys.modules,
        "config",
        _fake_config(
            CARTESIA_API_KEY="cartesia-key",
            TTS_PROVIDER_PRIMARY="cartesia",
            TTS_PROVIDER_FALLBACK="",
            VIVENTIUM_CARTESIA_EMOTION="neutral",
            VIVENTIUM_CARTESIA_VOICE_ID="voice-id",
        ),
    )

    class _Response:
        content = b"wav-bytes"

        def raise_for_status(self):
            return None

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, _url, *, content=None, **_kwargs):
            seen["payload"] = json.loads(content)
            return _Response()

    monkeypatch.setattr(tts_module.httpx, "AsyncClient", _Client)
    raw = '<emotion value="frustrated"/>Hmm... okay. [laughter]'

    voice_bytes = await tts_module.synthesize_speech(raw, "conv-1")

    assert voice_bytes == b"wav-bytes"
    assert seen["payload"]["transcript"] == raw
    assert seen["payload"]["generation_config"]["emotion"] == "frustrated"


@pytest.mark.asyncio
async def test_synthesize_speech_cartesia_splits_model_authored_emotion_states(monkeypatch):
    payloads = []

    monkeypatch.setitem(
        sys.modules,
        "config",
        _fake_config(
            CARTESIA_API_KEY="cartesia-key",
            TTS_PROVIDER_PRIMARY="cartesia",
            TTS_PROVIDER_FALLBACK="",
            VIVENTIUM_CARTESIA_EMOTION="neutral",
            VIVENTIUM_CARTESIA_VOICE_ID="voice-id",
        ),
    )

    class _Response:
        def __init__(self, content):
            self.content = content

        def raise_for_status(self):
            return None

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, _url, *, content=None, **_kwargs):
            payloads.append(json.loads(content))
            return _Response(_test_wav_bytes(len(payloads).to_bytes(2, "little")))

    monkeypatch.setattr(tts_module.httpx, "AsyncClient", _Client)

    voice_bytes = await tts_module.synthesize_speech(
        '<emotion value="frustrated"/>Hmm. <emotion value="calm"/>Okay.',
        "conv-1",
    )

    assert [payload["generation_config"]["emotion"] for payload in payloads] == [
        "frustrated",
        "calm",
    ]
    assert payloads[0]["transcript"].startswith('<emotion value="frustrated"/>')
    assert payloads[1]["transcript"].startswith('<emotion value="calm"/>')
    with wave.open(BytesIO(voice_bytes), "rb") as wav_file:
        assert wav_file.getnframes() == 2


def test_strip_voice_control_tags_for_non_cartesia_fallback():
    assert (
        tts_module._strip_voice_control_tags(
            '<emotion value="excited"/>Hi [laughter] <break time="1s"/><spell>ABC</spell>'
        )
        == "Hi ABC"
    )
