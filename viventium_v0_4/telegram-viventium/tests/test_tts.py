from pathlib import Path
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
TELEGRAM_ROOT = ROOT / "TelegramVivBot"
if str(TELEGRAM_ROOT) not in sys.path:
    sys.path.insert(0, str(TELEGRAM_ROOT))

from TelegramVivBot.utils import tts as tts_module


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
        "VIVENTIUM_CARTESIA_API_VERSION": "2025-04-16",
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
