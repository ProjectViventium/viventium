import hashlib
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
    sys.modules.pop("utils.tts", None)
    saved_aient_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == "aient" or name.startswith("aient.")
    }
    for name in list(saved_aient_modules):
        if name == "aient" or name.startswith("aient."):
            sys.modules.pop(name, None)
    try:
        return importlib.import_module("TelegramVivBot.config")
    finally:
        for name in list(sys.modules):
            if (name == "aient" or name.startswith("aient.")) and name not in saved_aient_modules:
                sys.modules.pop(name, None)
        sys.modules.update(saved_aient_modules)


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


def test_local_whisper_corrupt_cache_redownloads_exact_selected_model(monkeypatch, tmp_path):
    config = _fresh_config_import()
    good_content = b"correct selected model"
    expected_sha1 = hashlib.sha1(good_content).hexdigest()
    model_path = tmp_path / "ggml-large-v3-turbo.bin"
    model_path.write_bytes(b"corrupt cached model")

    def fake_urlretrieve(_url, destination):
        Path(destination).write_bytes(good_content)

    monkeypatch.setitem(config._LOCAL_WHISPER_MODEL_SHA1, "ggml-large-v3-turbo.bin", expected_sha1)
    monkeypatch.setattr(config.urllib.request, "urlretrieve", fake_urlretrieve)

    resolved = config._ensure_local_whisper_model_file("large-v3-turbo", tmp_path)

    assert resolved == model_path
    assert model_path.read_bytes() == good_content


def test_local_whisper_download_checksum_mismatch_keeps_existing_cache(monkeypatch, tmp_path):
    config = _fresh_config_import()
    good_content = b"correct selected model"
    expected_sha1 = hashlib.sha1(good_content).hexdigest()
    model_path = tmp_path / "ggml-large-v3-turbo.bin"
    existing_content = b"existing corrupt model"
    model_path.write_bytes(existing_content)

    def fake_urlretrieve(_url, destination):
        Path(destination).write_bytes(b"wrong downloaded model")

    monkeypatch.setitem(config._LOCAL_WHISPER_MODEL_SHA1, "ggml-large-v3-turbo.bin", expected_sha1)
    monkeypatch.setattr(config.urllib.request, "urlretrieve", fake_urlretrieve)

    try:
        config._ensure_local_whisper_model_file("large-v3-turbo", tmp_path)
    except RuntimeError as exc:
        assert "failed checksum" in str(exc)
    else:
        raise AssertionError("checksum mismatch should fail honestly")

    assert model_path.read_bytes() == existing_content
    assert list(tmp_path.glob(".ggml-large-v3-turbo.bin.*.download")) == []


def test_legacy_large_alias_is_not_supported(monkeypatch):
    config = _fresh_config_import()

    try:
        config._ensure_local_whisper_model_file("large", Path("/tmp/unused"))
    except RuntimeError as exc:
        assert "Unsupported local whisper.cpp model" in str(exc)
    else:
        raise AssertionError("legacy large alias must not be silently accepted")


def test_every_supported_local_whisper_model_has_checksum(monkeypatch):
    config = _fresh_config_import()
    missing = [
        filename
        for filename in config._LOCAL_WHISPER_MODEL_FILES.values()
        if filename not in config._LOCAL_WHISPER_MODEL_SHA1
    ]

    assert missing == []


def test_local_whisper_model_file_honors_shared_cache_override(monkeypatch, tmp_path):
    config = _fresh_config_import()
    good_content = b"correct selected model"
    expected_sha1 = hashlib.sha1(good_content).hexdigest()

    def fake_urlretrieve(_url, destination):
        Path(destination).write_bytes(good_content)

    monkeypatch.setenv("VIVENTIUM_WHISPER_CACHE_DIR", str(tmp_path))
    monkeypatch.setitem(config._LOCAL_WHISPER_MODEL_SHA1, "ggml-large-v3-turbo.bin", expected_sha1)
    monkeypatch.setattr(config.urllib.request, "urlretrieve", fake_urlretrieve)

    resolved = config._ensure_local_whisper_model_file("large-v3-turbo")

    assert resolved == tmp_path / "ggml-large-v3-turbo.bin"
    assert resolved.read_bytes() == good_content
