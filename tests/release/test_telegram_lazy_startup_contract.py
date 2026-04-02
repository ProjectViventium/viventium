from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_telegram_config_bootstraps_bridge_without_eager_stt() -> None:
    config_source = (
        REPO_ROOT
        / "viventium_v0_4"
        / "telegram-viventium"
        / "TelegramVivBot"
        / "config.py"
    ).read_text(encoding="utf-8")

    assert "def ensure_stt_engine(chat_id=None):" in config_source
    assert "InitEngine(chat_id=None, initialize_stt=False)" in config_source


def test_telegram_audio_scripts_lazy_load_stt_engine() -> None:
    scripts_source = (
        REPO_ROOT
        / "viventium_v0_4"
        / "telegram-viventium"
        / "TelegramVivBot"
        / "aient"
        / "aient"
        / "utils"
        / "scripts.py"
    ).read_text(encoding="utf-8")

    assert scripts_source.count("ensure_stt_engine = getattr(config, \"ensure_stt_engine\", None)") >= 3
    assert "if not config.local_whisper and callable(ensure_stt_engine):" in scripts_source
    assert "if not getattr(config, \"assemblyai_client\", None) and callable(ensure_stt_engine):" in scripts_source
    assert "if not config.whisperBot and callable(ensure_stt_engine):" in scripts_source
