from pathlib import Path
from io import BytesIO
import importlib.util
import json
import logging
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


def test_tts_capability_contract_fails_loudly_when_required_artifact_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    missing_contract = tmp_path / "missing-tts-provider-capabilities.json"
    monkeypatch.setattr(tts_module, "_TTS_PROVIDER_CAPABILITIES_PATH", missing_contract)

    with pytest.raises(RuntimeError, match="TTS provider capability contract"):
        tts_module._load_tts_provider_capabilities()


def _load_voice_gateway_sse_module():
    module_name = "viventium_voice_gateway_sse_for_telegram_tts_tests"
    if module_name in sys.modules:
        return sys.modules[module_name]
    path = ROOT.parent / "voice-gateway" / "sse.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


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


def test_prepare_tts_text_strips_shared_artifacts_without_breaking_word_boundaries():
    cleaned = tts_module.prepare_tts_text(
        "Sources: https://example.com/report\n"
        "Persian. turn0search4 If you mean coolest, read [brief](https://example.com/brief). "
        "Email qa@example.com, visit example.com, and say Good to hear you . Next."
    )

    assert "Sources:" not in cleaned
    assert "turn0search4" not in cleaned
    assert "https://" not in cleaned
    assert "qa@example.com" not in cleaned
    assert "visit example.com" in cleaned
    assert "Good to hear you. Next." in cleaned
    assert "Persian. If you mean coolest, read brief." in cleaned
    assert "address available" in cleaned
    assert "email email" not in cleaned


def test_prepare_tts_text_matches_livekit_common_artifact_cleanup():
    sse = _load_voice_gateway_sse_module()
    raw = (
        "Sources: https://example.com/report\n"
        "Persian. { NTA } turn0search4 If you mean coolest, read [brief](https://example.com/brief). "
        "Email qa@example.com, visit example.com, and say Good to hear you . Next."
    )

    assert tts_module.prepare_tts_text(raw) == sse.sanitize_voice_tts_text(
        raw,
        allow_voice_controls=True,
    )


def test_prepare_tts_text_preserves_dot_heavy_technical_tokens_like_livekit():
    sse = _load_voice_gateway_sse_module()
    raw = "Use .NET, asp.net, v1.2A, U.S.A., and node.js. Done.Next."

    assert tts_module.prepare_tts_text(raw) == sse.sanitize_voice_tts_text(
        raw,
        allow_voice_controls=True,
    )
    assert tts_module.prepare_tts_text(raw) == (
        "Use .NET, asp.net, v1.2A, U.S.A., and node.js. Done. Next."
    )


def test_prepare_tts_text_strips_unknown_tags_but_preserves_provider_voice_controls():
    raw = (
        '<emotion value="excited"/>Hello <custom data="x">there</custom>. '
        '<whisper>secret</whisper> <break time="500ms"/><spell>ABC</spell> [laughter]'
    )

    cleaned = tts_module.prepare_tts_text(raw)

    assert '<emotion value="excited"/>' in cleaned
    assert "<whisper>secret</whisper>" in cleaned
    assert '<break time="500ms"/>' in cleaned
    assert "<spell>ABC</spell>" in cleaned
    assert "[laughter]" in cleaned
    assert "<custom" not in cleaned
    assert "</custom>" not in cleaned
    assert "Hello there." in cleaned


@pytest.mark.parametrize(
    ("provider", "text", "expected"),
    [
        (
            "xai",
            "<whisper>Keep this close.</whisper> [sigh]",
            {
                "capability": "xai_speech_tags",
                "capability_supported": True,
                "compatible_control_count": 2,
                "incompatible_control_count": 0,
                "expressive_rendering": "provider_controls_present",
            },
        ),
        (
            "cartesia",
            '<emotion value="sad"/><break time="DURATION"/>Stay here.',
            {
                "capability": "cartesia_sonic3_ssml",
                "capability_supported": True,
                "compatible_control_count": 2,
                "incompatible_control_count": 0,
                "expressive_rendering": "provider_controls_present",
            },
        ),
        (
            "local_chatterbox_turbo_mlx_8bit",
            "[gasp] That changed fast.",
            {
                "capability": "chatterbox_nonverbal_markers",
                "capability_supported": True,
                "compatible_control_count": 1,
                "incompatible_control_count": 0,
                "expressive_rendering": "provider_controls_present",
            },
        ),
        (
            "openai",
            "<whisper>Do not forward this tag.</whisper>",
            {
                "capability": "plain_text_only",
                "capability_supported": False,
                "compatible_control_count": 0,
                "incompatible_control_count": 1,
                "expressive_rendering": "unsupported_controls_present",
            },
        ),
        (
            "elevenlabs",
            "[curious] This Eleven v3 tag is not valid on the configured v2.5 route.",
            {
                "capability": "plain_text_only",
                "capability_supported": False,
                "compatible_control_count": 0,
                "incompatible_control_count": 1,
                "expressive_rendering": "unsupported_controls_present",
            },
        ),
        (
            "unsupported-provider",
            "[laugh] Unknown route.",
            {
                "capability": "unknown",
                "capability_supported": False,
                "compatible_control_count": 0,
                "incompatible_control_count": 1,
                "expressive_rendering": "unsupported_controls_present",
            },
        ),
    ],
)
def test_voice_rendering_observation_is_provider_capability_driven(provider, text, expected):
    observation = tts_module._voice_rendering_observation(
        provider,
        text,
        route_role="fallback" if provider == "openai" else "primary",
    )

    assert {key: observation[key] for key in expected} == expected
    assert observation["route_role"] == ("fallback" if provider == "openai" else "primary")


def test_voice_rendering_observability_logs_only_structural_metadata(caplog):
    private_text = "Private sentence <whisper>spoken quietly</whisper> [sigh]"

    with caplog.at_level(logging.INFO, logger=tts_module.__name__):
        tts_module._log_voice_rendering_observation(
            "xai",
            private_text,
            route_role="primary",
        )

    line = next(message for message in caplog.messages if "[VoiceRendering][telegram]" in message)
    assert "provider=xai" in line
    assert "model=xai-tts" in line
    assert "role=primary" in line
    assert "capability=xai_speech_tags" in line
    assert "expressive_rendering=provider_controls_present" in line
    assert private_text not in line
    assert "Private sentence" not in line


def test_voice_rendering_observability_distinguishes_normalization_from_stripping(caplog):
    private_text = "[laugh-speak]Private playful sentence.[/laugh-speak]"
    forwarded_text = "<laugh-speak>Private playful sentence.</laugh-speak>"

    with caplog.at_level(logging.INFO, logger=tts_module.__name__):
        tts_module._log_voice_rendering_observation(
            "xai",
            private_text,
            route_role="primary",
            forwarded_text=forwarded_text,
        )

    line = next(message for message in caplog.messages if "[VoiceRendering][telegram]" in message)
    assert "compatible_controls=1" in line
    assert "normalized_controls=1" in line
    assert "stripped_controls=0" in line
    assert private_text not in line
    assert "Private playful sentence" not in line


def test_prepare_tts_text_strips_bare_turn_citation_shells():
    assert (
        tts_module.prepare_tts_text("Answer \u3010turn0search4\u2020source\u3011 continues")
        == "Answer continues"
    )
    assert (
        tts_module.prepare_tts_text("Answer turn0search1turn0news2turn0file3 done")
        == "Answer done"
    )


def test_prepare_tts_text_is_idempotent_for_shared_artifact_cleanup():
    raw = (
        "Sources: https://example.com/report\n"
        '<emotion value="excited"/>Hello <custom>there</custom> turn0search4 .'
    )
    once = tts_module.prepare_tts_text(raw)
    twice = tts_module.prepare_tts_text(once)

    assert twice == once


def test_prepare_tts_text_strips_livekit_matching_tool_directives_and_backticks():
    cleaned = tts_module.prepare_tts_text(
        "Use calendar view to check the start of day. "
        "Fetch inbox messages. "
        "Here is `paired` and stray` backtick."
    )

    assert "calendar view" not in cleaned
    assert "Fetch inbox messages" not in cleaned
    assert "`" not in cleaned
    assert "Here is paired and stray backtick." in cleaned


def test_prepare_tts_text_strips_inline_nta_like_livekit():
    assert tts_module.prepare_tts_text("{NTA}") == ""
    assert tts_module.prepare_tts_text("Useful context { NTA } keep going.") == (
        "Useful context keep going."
    )


def test_prepare_tts_text_strips_malformed_internal_nta_artifacts_like_livekit():
    sse = _load_voice_gateway_sse_module()
    raw = "Useful context {N{NTATA}} and {N{NTA} keep going."

    assert tts_module.prepare_tts_text(raw) == sse.sanitize_voice_tts_text(
        raw,
        allow_voice_controls=True,
    )
    assert "{N" not in tts_module.prepare_tts_text(raw)


def test_plain_fallback_stage_direction_cleanup_matches_livekit():
    sse = _load_voice_gateway_sse_module()
    raw = '<emotion value="excited"/>Hi [clears throat] <whisper>low</whisper> [Section 3].'

    assert tts_module._strip_voice_control_tags(raw) == sse.strip_voice_control_tags(raw)


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
async def test_synthesize_speech_chatterbox_strips_unsupported_voice_controls(monkeypatch):
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
        _ = config
        seen["text"] = text
        return b"wav-bytes"

    monkeypatch.setattr(
        tts_module,
        "_build_local_chatterbox_config",
        lambda model_id_override=None: (
            types.SimpleNamespace(model_id=model_id_override or "mlx-community/chatterbox-turbo-8bit"),
            _fake_synthesize_wav_bytes,
        ),
    )

    voice_bytes = await tts_module.synthesize_speech(
        '<emotion value="excited"/>Hi [laughter] [laugh] [sigh] [gasp] [clears throat] '
        '<whisper>secret</whisper> <break time="500ms"/>',
        "conv-1",
        voice_route={
            "tts": {
                "provider": "local_chatterbox_turbo_mlx_8bit",
                "variant": "mlx-community/chatterbox-turbo-8bit",
            }
        },
    )

    assert voice_bytes == b"wav-bytes"
    assert seen["text"] == "Hi [laugh] [sigh] [gasp] secret"
    assert "[laughter]" not in seen["text"]
    assert "[clears throat]" not in seen["text"]
    assert "<emotion" not in seen["text"]
    assert "<break" not in seen["text"]


@pytest.mark.asyncio
async def test_synthesize_speech_openai_direct_path_applies_common_speech_safety(monkeypatch):
    seen = {}
    monkeypatch.delenv("VIVENTIUM_OPENAI_TTS_INSTRUCTIONS", raising=False)
    monkeypatch.setitem(
        sys.modules,
        "config",
        _fake_config(
            API_KEY="openai-key",
            BASE_URL="https://api.openai.com/v1",
            TTS_PROVIDER_PRIMARY="openai",
            TTS_PROVIDER_FALLBACK="",
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

        async def post(self, url, *, headers=None, json=None, **_kwargs):
            seen["url"] = url
            seen["headers"] = headers or {}
            seen["payload"] = json
            return _Response()

    monkeypatch.setattr(tts_module.httpx, "AsyncClient", _Client)

    voice_bytes = await tts_module.synthesize_speech(
        "Sources: https://example.com/report\n"
        "Nice, invoice cleared is a real milestone. turn0search4 Good to hear you .",
        "conv-1",
    )

    assert voice_bytes == b"mp3-bytes"
    assert seen["payload"]["input"] == (
        "Nice, invoice cleared is a real milestone. Good to hear you."
    )
    assert "turn0search4" not in seen["payload"]["input"]
    assert "Sources:" not in seen["payload"]["input"]
    assert seen["payload"]["instructions"] == (
        tts_module._TTS_PROVIDER_CONTRACTS["openai"]["default_renderer_instruction"]
    )


@pytest.mark.asyncio
async def test_synthesize_speech_openai_legacy_model_omits_unsupported_instructions(monkeypatch):
    seen = {}
    monkeypatch.setenv("VIVENTIUM_OPENAI_TTS_INSTRUCTIONS", "Use a deliberately visible override.")
    monkeypatch.setitem(
        sys.modules,
        "config",
        _fake_config(
            API_KEY="openai-key",
            BASE_URL="https://api.openai.com/v1",
            TTS_MODEL="tts-1",
            TTS_PROVIDER_PRIMARY="openai",
            TTS_PROVIDER_FALLBACK="",
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

        async def post(self, url, *, headers=None, json=None, **_kwargs):
            seen["payload"] = json
            return _Response()

    monkeypatch.setattr(tts_module.httpx, "AsyncClient", _Client)

    voice_bytes = await tts_module.synthesize_speech("Hello.", "conv-1")

    assert voice_bytes == b"mp3-bytes"
    assert seen["payload"]["model"] == "tts-1"
    assert "instructions" not in seen["payload"]


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
async def test_synthesize_speech_xai_repairs_paired_square_wrapper_tags(monkeypatch):
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
        "[laugh-speak]Morning. You have warmth.[/laugh-speak] If needed.",
        "conv-1",
        voice_route={"tts": {"provider": "xai", "variant": "Eve"}},
    )

    assert voice_bytes == b"mp3-bytes"
    assert seen["payload"]["text"] == (
        "<laugh-speak>Morning. You have warmth.</laugh-speak> If needed."
    )
    assert "[laugh-speak]" not in seen["payload"]["text"]
    assert "[/laugh-speak]" not in seen["payload"]["text"]


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
        '<soft>Close.</soft> [pause] [breath]'
    ) == {
        "laughter": 1,
        "emotion": 1,
        "break": 1,
        "speed": 1,
        "volume": 1,
        "spell": 1,
        "xai_inline": 2,
        "xai_wrapping": 1,
        "xai_square_wrapping": 0,
        "xai_total": 3,
    }


def test_summarize_voice_markup_includes_square_wrappers_in_xai_total():
    summary = tts_module.summarize_voice_markup("[soft]Quietly.[/soft]")

    assert summary["xai_square_wrapping"] == 1
    assert summary["xai_total"] == 1


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


def test_strip_voice_control_tags_uses_structural_stage_direction_parser():
    cleaned = tts_module._strip_voice_control_tags(
        "Hi [clears throat] there [grumbles]. Keep [Section 3]."
    )

    assert cleaned == "Hi there. Keep [Section 3]."
    assert "[clears throat]" not in cleaned
    assert "[grumbles]" not in cleaned


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
        "Hi [soft laugh] [gentle sigh] [breath out] [clears throat] [laugh] [sigh] [Section 3]."
    )

    assert cleaned == "Hi [laugh] [sigh] [Section 3]."
    assert "[soft laugh]" not in cleaned
    assert "[gentle sigh]" not in cleaned
    assert "[breath out]" not in cleaned
    assert "[clears throat]" not in cleaned


def test_strip_cartesia_markup_for_xai_repairs_paired_square_wrapping_tags():
    for tag in tts_module._XAI_TTS_WRAPPING_TAGS:
        cleaned = tts_module._strip_cartesia_markup_for_xai(
            f"<{tag}>Keep this.</{tag}> [{tag}] tail [/{tag}] done."
        )
        assert cleaned == f"<{tag}>Keep this.</{tag}> <{tag}>tail</{tag}> done."
        assert f"[{tag}]" not in cleaned
        assert f"[/{tag}]" not in cleaned


def test_strip_cartesia_markup_for_xai_still_strips_unpaired_square_wrapping_tags():
    assert (
        tts_module._strip_cartesia_markup_for_xai(
            "[laugh-speak]Keep this plain. Then [soft]continue."
        )
        == "Keep this plain. Then continue."
    )


def test_xai_fallback_wrapping_vocabulary_covers_documented_tags():
    assert set(tts_module._XAI_TTS_FALLBACK_WRAPPING_TAGS) == set(tts_module._XAI_TTS_WRAPPING_TAGS)
