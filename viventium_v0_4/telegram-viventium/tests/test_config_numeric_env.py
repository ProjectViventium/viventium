import importlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
TELEGRAM_ROOT = ROOT / "TelegramVivBot"
if str(TELEGRAM_ROOT) not in sys.path:
    sys.path.insert(0, str(TELEGRAM_ROOT))


def _fresh_config_import():
    sys.modules.pop("config", None)
    sys.modules.pop("TelegramVivBot.config", None)
    return importlib.import_module("TelegramVivBot.config")


def test_empty_numeric_env_values_fall_back_to_defaults(monkeypatch):
    for name in (
        "LOCAL_WHISPER_THREADS",
        "PORT",
        "VIVENTIUM_TELEGRAM_MAX_FILE_SIZE",
        "RESET_TIME",
        "CONNECTION_POOL_SIZE",
        "GET_UPDATES_CONNECTION_POOL_SIZE",
        "TIMEOUT",
        "POLLING_TIMEOUT",
        "VIVENTIUM_CARTESIA_SAMPLE_RATE",
        "VIVENTIUM_XAI_TTS_SAMPLE_RATE",
        "VIVENTIUM_XAI_SAMPLE_RATE",
        "VIVENTIUM_XAI_TTS_BIT_RATE",
        "VIVENTIUM_TELEGRAM_CALL_LINK_CACHE_TTL_S",
    ):
        monkeypatch.setenv(name, "")

    config = _fresh_config_import()

    assert config.LOCAL_WHISPER_THREADS == 4
    assert config.PORT == 8080
    assert config.VIVENTIUM_TELEGRAM_MAX_FILE_SIZE == 10485760
    assert config.RESET_TIME == 3600
    assert config.CONNECTION_POOL_SIZE == 8
    assert config.GET_UPDATES_CONNECTION_POOL_SIZE == 8
    assert config.TIMEOUT == 30
    assert config.POLLING_TIMEOUT == 30
    assert config.VIVENTIUM_CARTESIA_SAMPLE_RATE == 44100
    assert config.VIVENTIUM_XAI_TTS_SAMPLE_RATE == 24000
    assert config.VIVENTIUM_XAI_TTS_BIT_RATE == 128000


def test_empty_call_link_cache_ttl_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("VIVENTIUM_TELEGRAM_CALL_LINK_CACHE_TTL_S", "")

    config = _fresh_config_import()

    assert config._get_int_env("VIVENTIUM_TELEGRAM_CALL_LINK_CACHE_TTL_S", 480) == 480


def test_numeric_env_values_accept_float_strings(monkeypatch):
    monkeypatch.setenv("VIVENTIUM_XAI_TTS_SAMPLE_RATE", "24000.0")
    monkeypatch.setenv("VIVENTIUM_XAI_TTS_BIT_RATE", "128000.0")

    config = _fresh_config_import()

    assert config.VIVENTIUM_XAI_TTS_SAMPLE_RATE == 24000
    assert config.VIVENTIUM_XAI_TTS_BIT_RATE == 128000
