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


def _test_wav_bytes(frame_value: bytes = b"\x00\x00", *, framerate: int = 44100) -> bytes:
    output = BytesIO()
    with wave.open(output, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(framerate)
        wav_file.writeframes(frame_value)
    return output.getvalue()


def _placeholder_nframes_wav_bytes(frame_value: bytes) -> bytes:
    data = bytearray(_test_wav_bytes(frame_value))
    data[4:8] = (0xFFFFFFFF).to_bytes(4, "little")
    data[40:44] = (0xFFFFFFFF).to_bytes(4, "little")
    return bytes(data)


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
        "VIVENTIUM_XAI_TTS_API_KEY": "",
        "XAI_API_KEY": "",
        "VIVENTIUM_XAI_TTS_API_URL": "https://api.x.ai/v1/tts",
        "VIVENTIUM_XAI_VOICE": "Sal",
        "VIVENTIUM_XAI_LANGUAGE": "en",
        "VIVENTIUM_XAI_TTS_CODEC": "mp3",
        "VIVENTIUM_XAI_TTS_SAMPLE_RATE": 24000,
        "VIVENTIUM_XAI_TTS_BIT_RATE": 128000,
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


def test_cartesia_capability_contract_is_loaded_from_shared_file():
    assert tts_module._CARTESIA_SONIC3_CAPABILITIES_PATH.exists()
    assert len(tts_module._CARTESIA_SONIC3_EMOTION_VALUES) >= 50
    assert tts_module._CARTESIA_SONIC3_API_VERSION == "2026-03-01"


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


def test_resolve_tts_selection_supports_xai_alias_and_voice_variant(monkeypatch):
    monkeypatch.setitem(
        sys.modules,
        "config",
        _fake_config(
            XAI_API_KEY="x",
            TTS_PROVIDER_PRIMARY="openai",
            TTS_PROVIDER_FALLBACK="",
        ),
    )

    resolved = tts_module.resolve_tts_selection(
        voice_route={
            "tts": {
                "provider": "x_ai",
                "variant": "Eve",
            }
        }
    )

    assert resolved["provider"] == "xai"
    assert resolved["variant"] == "Eve"
    assert resolved["source"] == "saved"


def test_resolve_tts_selection_supports_xai_tts_specific_key(monkeypatch):
    monkeypatch.setitem(
        sys.modules,
        "config",
        _fake_config(
            VIVENTIUM_XAI_TTS_API_KEY="t",
            XAI_API_KEY="",
            TTS_PROVIDER_PRIMARY="openai",
            TTS_PROVIDER_FALLBACK="",
        ),
    )

    resolved = tts_module.resolve_tts_selection(
        voice_route={
            "tts": {
                "provider": "xai",
                "variant": "Rex",
            }
        }
    )

    assert resolved["provider"] == "xai"
    assert resolved["variant"] == "Rex"
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
    monkeypatch.delenv("VIVENTIUM_CARTESIA_API_VERSION", raising=False)

    monkeypatch.setitem(
        sys.modules,
        "config",
        _fake_config(
            CARTESIA_API_KEY="cartesia-key",
            TTS_PROVIDER_PRIMARY="openai",
            TTS_PROVIDER_FALLBACK="",
            VIVENTIUM_CARTESIA_API_VERSION="stale-config-default",
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
    assert seen["headers"]["Cartesia-Version"] == tts_module._CARTESIA_SONIC3_API_VERSION
    assert seen["payload"]["model_id"] == "sonic-3"
    assert seen["payload"]["voice"] == {"mode": "id", "id": lyra_voice_id}


@pytest.mark.asyncio
async def test_synthesize_speech_xai_uses_tts_endpoint_and_preserves_xai_tags(monkeypatch):
    seen = {}

    monkeypatch.setitem(
        sys.modules,
        "config",
        _fake_config(
            XAI_API_KEY="x",
            TTS_PROVIDER_PRIMARY="xai",
            TTS_PROVIDER_FALLBACK="",
            VIVENTIUM_XAI_VOICE="Sal",
            VIVENTIUM_XAI_LANGUAGE="en",
        ),
    )

    class _Response:
        content = b"mp3-bytes"

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
        '<emotion value="excited"/>Hi [laugh]. <whisper>secret</whisper> [laughter]',
        "conv-1",
        voice_route={"tts": {"provider": "xai", "variant": "Eve"}},
    )

    assert voice_bytes == b"mp3-bytes"
    assert seen["url"] == "https://api.x.ai/v1/tts"
    assert seen["headers"]["Authorization"] == "Bearer x"
    assert seen["payload"]["voice_id"] == "Eve"
    assert seen["payload"]["language"] == "en"
    assert seen["payload"]["output_format"] == {
        "codec": "mp3",
        "sample_rate": 24000,
        "bit_rate": 128000,
    }
    assert seen["payload"]["text"] == 'Hi [laugh]. <whisper>secret</whisper>'


@pytest.mark.asyncio
async def test_synthesize_speech_xai_prefers_tts_specific_key_and_saved_voice(monkeypatch):
    seen = {}

    monkeypatch.setitem(
        sys.modules,
        "config",
        _fake_config(
            VIVENTIUM_XAI_TTS_API_KEY="t",
            XAI_API_KEY="l",
            TTS_PROVIDER_PRIMARY="openai",
            TTS_PROVIDER_FALLBACK="",
            VIVENTIUM_XAI_VOICE="Sal",
        ),
    )

    class _Response:
        content = b"mp3-bytes"

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
        "Hello [laugh].",
        "conv-1",
        voice_route={"tts": {"provider": "xai", "variant": "Rex"}},
    )

    assert voice_bytes == b"mp3-bytes"
    assert seen["url"] == "https://api.x.ai/v1/tts"
    assert seen["headers"]["Authorization"] == "Bearer t"
    assert seen["payload"]["voice_id"] == "Rex"


@pytest.mark.asyncio
async def test_synthesize_speech_xai_strips_malformed_square_wrapper_tags(monkeypatch):
    seen = {}

    monkeypatch.setitem(
        sys.modules,
        "config",
        _fake_config(
            XAI_API_KEY="x",
            TTS_PROVIDER_PRIMARY="xai",
            TTS_PROVIDER_FALLBACK="openai",
            VIVENTIUM_XAI_VOICE="Sal",
        ),
    )

    class _Response:
        content = b"mp3-bytes"

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
        "<soft>Morning. You have warmth.[/soft] If needed.",
        "conv-1",
        voice_route={"tts": {"provider": "xai", "variant": "Eve"}},
    )

    assert voice_bytes == b"mp3-bytes"
    assert seen["payload"]["text"] == "Morning. You have warmth. If needed."
    assert "<soft>" not in seen["payload"]["text"]
    assert "[/soft]" not in seen["payload"]["text"]


@pytest.mark.asyncio
async def test_synthesize_speech_cartesia_api_version_env_override_wins(monkeypatch):
    seen = {}

    monkeypatch.setenv("VIVENTIUM_CARTESIA_API_VERSION", "override-version")
    monkeypatch.setitem(
        sys.modules,
        "config",
        _fake_config(
            CARTESIA_API_KEY="cartesia-key",
            TTS_PROVIDER_PRIMARY="cartesia",
            TTS_PROVIDER_FALLBACK="",
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

        async def post(self, _url, *, headers=None, content=None, **_kwargs):
            seen["headers"] = headers or {}
            return _Response()

    monkeypatch.setattr(tts_module.httpx, "AsyncClient", _Client)

    voice_bytes = await tts_module.synthesize_speech("Hello.", "conv-1")

    assert voice_bytes == b"wav-bytes"
    assert seen["headers"]["Cartesia-Version"] == "override-version"


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
async def test_synthesize_speech_cartesia_clamps_speed_volume_from_contract(monkeypatch):
    seen = {}

    monkeypatch.setitem(
        sys.modules,
        "config",
        _fake_config(
            CARTESIA_API_KEY="cartesia-key",
            TTS_PROVIDER_PRIMARY="cartesia",
            TTS_PROVIDER_FALLBACK="",
            VIVENTIUM_CARTESIA_SPEED=9.0,
            VIVENTIUM_CARTESIA_VOLUME=0.1,
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

    voice_bytes = await tts_module.synthesize_speech("Hello.", "conv-1")

    assert voice_bytes == b"wav-bytes"
    assert seen["payload"]["generation_config"]["speed"] == 1.5
    assert seen["payload"]["generation_config"]["volume"] == 0.5


@pytest.mark.asyncio
async def test_synthesize_speech_cartesia_skips_empty_after_marker_normalization(monkeypatch):
    called = False

    monkeypatch.setitem(
        sys.modules,
        "config",
        _fake_config(
            CARTESIA_API_KEY="cartesia-key",
            TTS_PROVIDER_PRIMARY="cartesia",
            TTS_PROVIDER_FALLBACK="",
            VIVENTIUM_CARTESIA_VOICE_ID="voice-id",
        ),
    )

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *_args, **_kwargs):
            nonlocal called
            called = True
            raise AssertionError("empty Cartesia transcript should not be posted")

    monkeypatch.setattr(tts_module.httpx, "AsyncClient", _Client)

    voice_bytes = await tts_module.synthesize_speech("[sigh]", "conv-1")

    assert voice_bytes is None
    assert called is False


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


def test_merge_wav_chunks_rewrites_placeholder_nframes_header():
    merged = tts_module._merge_wav_chunks(
        [
            _placeholder_nframes_wav_bytes(b"\x01\x00"),
            _placeholder_nframes_wav_bytes(b"\x02\x00"),
        ]
    )

    assert merged.count(b"RIFF") == 1
    with wave.open(BytesIO(merged), "rb") as wav_file:
        assert wav_file.getnframes() == 2
        assert wav_file.readframes(2) == b"\x01\x00\x02\x00"


def test_merge_wav_chunks_rejects_mismatched_params_without_raw_concat():
    with pytest.raises(tts_module.WavMergeError):
        tts_module._merge_wav_chunks(
            [
                _test_wav_bytes(b"\x01\x00", framerate=44100),
                _test_wav_bytes(b"\x02\x00", framerate=48000),
            ]
        )


def test_summarize_voice_markup_counts_structural_markers():
    assert tts_module.summarize_voice_markup(
        '<emotion value="excited"/>Hi [laughter]. <break time="1s"/>'
        '<speed ratio="1.1"/>Fast. <volume ratio="0.9"/>Soft. <spell>ABC</spell>'
    ) == {
        "laughter": 1,
        "emotion": 1,
        "break": 1,
        "speed": 1,
        "volume": 1,
        "spell": 1,
    }


def test_cartesia_emotion_normalization_uses_shared_sonic3_list():
    assert tts_module._normalize_cartesia_emotion("joking/comedic", "neutral") == "joking/comedic"
    assert tts_module._normalize_cartesia_emotion("made up mood", "calm") == "calm"


def test_cartesia_nonverbal_normalization_keeps_contract_markers_and_strips_stage_noise():
    for marker in tts_module._CARTESIA_SONIC3_CAPABILITIES["nonverbal_markers"]:
        assert tts_module._normalize_cartesia_nonverbal_tokens(marker) == marker
        assert tts_module._strip_voice_control_tags(marker) == ""
    assert (
        tts_module._normalize_cartesia_nonverbal_tokens("Hi [Section 3] [sigh] [laugh] there")
        == "Hi   [laughter] there"
    )


def test_strip_voice_control_tags_for_non_cartesia_fallback():
    assert (
        tts_module._strip_voice_control_tags(
            '<emotion value="excited"/>Hi [laughter] <break time="1s"/><spell>ABC</spell>'
        )
        == "Hi ABC"
    )


def test_strip_voice_control_tags_removes_xai_wrapping_for_non_xai_fallback():
    assert (
        tts_module._strip_voice_control_tags(
            "Hi <whisper>quiet</whisper> and <slow><soft>gentle</soft></slow> [laugh]"
        )
        == "Hi quiet and gentle"
    )


def test_strip_voice_control_tags_removes_malformed_xai_wrappers_for_fallback():
    assert (
        tts_module._strip_voice_control_tags(
            "<soft>Morning. You have warmth.[/soft] If needed."
        )
        == "Morning. You have warmth. If needed."
    )


def test_strip_cartesia_markup_for_xai_preserves_documented_xai_tags():
    inline = " ".join(f"[{tag}]" for tag in tts_module._XAI_TTS_INLINE_TAGS)
    wrapping = " ".join(
        f"<{tag}>text-{index}</{tag}>"
        for index, tag in enumerate(tts_module._XAI_TTS_WRAPPING_TAGS)
    )

    cleaned = tts_module._strip_cartesia_markup_for_xai(f"{inline} {wrapping}")

    for tag in tts_module._XAI_TTS_INLINE_TAGS:
        assert f"[{tag}]" in cleaned
    for tag in tts_module._XAI_TTS_WRAPPING_TAGS:
        assert f"<{tag}>" in cleaned
        assert f"</{tag}>" in cleaned


def test_strip_cartesia_markup_for_xai_strips_cartesia_only_bracket_aliases():
    cleaned = tts_module._strip_cartesia_markup_for_xai(
        "Hi [soft laugh] [gentle sigh] [breath out] [laugh] [sigh] [Section 3]."
    )

    assert cleaned == "Hi [laugh] [sigh] [Section 3]."
    assert "[soft laugh]" not in cleaned
    assert "[gentle sigh]" not in cleaned
    assert "[breath out]" not in cleaned


def test_strip_cartesia_markup_for_xai_strips_every_malformed_wrapping_tag():
    for tag in tts_module._XAI_TTS_WRAPPING_TAGS:
        cleaned = tts_module._strip_cartesia_markup_for_xai(
            f"<{tag}>Keep this.</{tag}> [{tag}] tail [/{tag}] done."
        )
        assert cleaned == f"<{tag}>Keep this.</{tag}> tail done."
        assert f"[{tag}]" not in cleaned
        assert f"[/{tag}]" not in cleaned


def test_xai_fallback_wrapping_vocabulary_covers_documented_tags():
    assert set(tts_module._XAI_TTS_FALLBACK_WRAPPING_TAGS) == set(tts_module._XAI_TTS_WRAPPING_TAGS)
