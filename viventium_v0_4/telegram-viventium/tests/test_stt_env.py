from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from TelegramVivBot.utils.stt_env import (
    resolve_api_whisper_config,
    resolve_tts_model,
    resolve_tts_provider,
    resolve_tts_provider_fallback,
    resolve_whisper_mode,
)


def test_resolve_whisper_mode_prefers_explicit_env():
    env = {
        "WHISPER_MODE": "assemblyai",
        "VIVENTIUM_STT_PROVIDER": "whisper_local",
    }

    assert resolve_whisper_mode(env) == "assemblyai"


def test_resolve_whisper_mode_maps_canonical_local_provider():
    env = {"VIVENTIUM_STT_PROVIDER": "whisper_local"}

    assert resolve_whisper_mode(env) == "pywhispercpp"


def test_resolve_whisper_mode_maps_legacy_provider_alias():
    env = {"STT_PROVIDER": "assemblyai"}

    assert resolve_whisper_mode(env) == "assemblyai"


def test_resolve_whisper_mode_defaults_to_openai():
    assert resolve_whisper_mode({}) == "openai"


def test_resolve_api_whisper_config_falls_back_to_default_env_values():
    api_key, api_url = resolve_api_whisper_config(
        user_api_key="",
        user_api_url="",
        default_api_key="env-key",
        default_api_url="https://example.test/v1",
    )

    assert api_key == "env-key"
    assert api_url == "https://example.test/v1"


def test_resolve_api_whisper_config_ignores_url_only_user_override():
    api_key, api_url = resolve_api_whisper_config(
        user_api_key="",
        user_api_url="https://api.x.ai/v1/chat/completions",
        default_api_key="env-key",
        default_api_url="https://api.openai.com/v1",
    )

    assert api_key == "env-key"
    assert api_url == "https://api.openai.com/v1"


def test_resolve_api_whisper_config_keeps_full_user_override():
    api_key, api_url = resolve_api_whisper_config(
        user_api_key="user-key",
        user_api_url="https://custom.example/v1",
        default_api_key="env-key",
        default_api_url="https://api.openai.com/v1",
    )

    assert api_key == "user-key"
    assert api_url == "https://custom.example/v1"


def test_resolve_tts_provider_prefers_explicit_telegram_env():
    env = {
        "TTS_PROVIDER": "cartesia",
        "VIVENTIUM_TTS_PROVIDER": "openai",
    }

    assert resolve_tts_provider(env) == "cartesia"


def test_resolve_tts_provider_uses_canonical_runtime_provider():
    env = {
        "VIVENTIUM_TTS_PROVIDER": "x_ai",
    }

    assert resolve_tts_provider(env) == "x_ai"


def test_resolve_tts_provider_fallback_uses_canonical_runtime_fallback():
    env = {
        "VIVENTIUM_TTS_PROVIDER_FALLBACK": "elevenlabs",
    }

    assert resolve_tts_provider_fallback(env, "cartesia") == "elevenlabs"


def test_resolve_tts_model_uses_voice_gateway_openai_model_when_present():
    env = {
        "VIVENTIUM_OPENAI_TTS_MODEL": "gpt-4o-audio-preview",
    }

    assert (
        resolve_tts_model("", "openai", "grok-4-fast-reasoning", env)
        == "gpt-4o-audio-preview"
    )


def test_resolve_tts_model_defaults_to_voice_gateway_openai_model_when_unset():
    assert (
        resolve_tts_model("", "openai", "grok-4-fast-reasoning", {})
        == "gpt-4o-mini-tts"
    )


def test_resolve_tts_model_defaults_to_cartesia_model_when_provider_is_cartesia():
    assert resolve_tts_model("", "cartesia", "grok-4-fast-reasoning", {}) == "sonic-3"


def test_resolve_tts_model_defaults_to_local_chatterbox_model_when_provider_is_local_chatterbox():
    assert (
        resolve_tts_model("", "local_chatterbox_turbo_mlx_8bit", "grok-4-fast-reasoning", {})
        == "mlx-community/chatterbox-turbo-8bit"
    )


def test_resolve_tts_model_preserves_explicit_model():
    assert (
        resolve_tts_model("custom-tts-model", "openai", "grok-4-fast-reasoning", {})
        == "custom-tts-model"
    )
