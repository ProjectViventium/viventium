from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_telegram_scripts_use_structured_transcription_results() -> None:
    scripts_source = (
        REPO_ROOT
        / "viventium_v0_4"
        / "telegram-viventium"
        / "TelegramVivBot"
        / "utils"
        / "scripts.py"
    ).read_text(encoding="utf-8")

    assert "class TelegramTranscriptionResult:" in scripts_source
    assert "async def download_telegram_file_result(" in scripts_source
    assert 'error_text=f"Timed out downloading this {media_label} from Telegram. Please retry."' in scripts_source
    assert 'return _transcription_download_error("voice note", download_result.error_code)' in scripts_source
    assert "voice_file_id = update_message.voice.file_id" in scripts_source
    assert "elif update_message.video_note:" in scripts_source
    assert "elif update_message.video:" in scripts_source
    assert "voice_error_text = voice_result.error_text" in scripts_source
    assert "def classify_telegram_download_error(exc: Exception) -> str:" in scripts_source
    assert 'return f"error: Temporarily unable to process video note:' not in scripts_source
    assert 'return f"error: Temporarily unable to use voice function:' not in scripts_source


def test_telegram_bot_supports_optional_local_bot_api_server() -> None:
    bot_source = (
        REPO_ROOT
        / "viventium_v0_4"
        / "telegram-viventium"
        / "TelegramVivBot"
        / "bot.py"
    ).read_text(encoding="utf-8")
    config_source = (
        REPO_ROOT
        / "viventium_v0_4"
        / "telegram-viventium"
        / "TelegramVivBot"
        / "config.py"
    ).read_text(encoding="utf-8")

    assert "VIVENTIUM_TELEGRAM_BOT_API_ORIGIN" in config_source
    assert "VIVENTIUM_TELEGRAM_BOT_API_BASE_URL" in config_source
    assert "VIVENTIUM_TELEGRAM_BOT_API_BASE_FILE_URL" in config_source
    assert "VIVENTIUM_TELEGRAM_LOCAL_BOT_API_ENABLED" in config_source
    assert ".base_url(telegram_bot_api_base_url)" in bot_source
    assert ".base_file_url(telegram_bot_api_base_file_url)" in bot_source
    assert "builder = builder.local_mode(True)" in bot_source


def test_telegram_runtime_prefers_generated_service_env() -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    launcher_source = (
        REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"
    ).read_text(encoding="utf-8")
    schema_source = (REPO_ROOT / "config.schema.yaml").read_text(encoding="utf-8")
    example_source = (REPO_ROOT / "config.full.example.yaml").read_text(encoding="utf-8")

    assert 'generated_telegram_env="$RUNTIME_DIR/service-env/telegram.config.env"' in cli_source
    assert 'export VIVENTIUM_TELEGRAM_ENV_FILE="$generated_telegram_env"' in cli_source
    assert 'TELEGRAM_RUNTIME_CONFIG_ENV_FILE="${VIVENTIUM_TELEGRAM_RUNTIME_ENV_FILE:-}"' in launcher_source
    assert 'runtime/service-env/telegram.config.env' in launcher_source
    assert 'bot_api_origin:' in schema_source
    assert 'bot_api_base_url:' in schema_source
    assert 'bot_api_base_file_url:' in schema_source
    assert 'max_file_size_bytes:' in schema_source
    assert 'local_bot_api:' in schema_source
    assert 'api_id:' in schema_source
    assert 'api_hash:' in schema_source
    assert 'bot_api_origin: ""' in example_source
    assert 'max_file_size_bytes: 10485760' in example_source
    assert 'local_bot_api:' in example_source
    assert 'api_id: keychain://viventium/telegram_api_id' in example_source


def test_telegram_bot_stops_before_forwarding_failed_transcription() -> None:
    bot_source = (
        REPO_ROOT
        / "viventium_v0_4"
        / "telegram-viventium"
        / "TelegramVivBot"
        / "bot.py"
    ).read_text(encoding="utf-8")

    assert "async def _resolve_voice_input_message(" in bot_source
    assert "message, voice_input_failed = await _resolve_voice_input_message(" in bot_source
    assert "if voice_input_failed:" in bot_source
    assert "show_transcription=False" in bot_source
    assert "message = voice_text" not in bot_source
    assert "if message is not None:" in bot_source
    assert "return message, False" in bot_source
    assert 'transcription_display = f"🎤 Transcription:\\n> {voice_text}"' in bot_source
    assert "return voice_text, False" in bot_source


def test_telegram_launcher_supports_managed_local_bot_api_contract() -> None:
    launcher_source = (
        REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"
    ).read_text(encoding="utf-8")

    assert "start_telegram_local_bot_api() {" in launcher_source
    assert "stop_telegram_local_bot_api() {" in launcher_source
    assert "ensure_telegram_local_bot_api_hosted_logout() {" in launcher_source
    assert 'VIVENTIUM_TELEGRAM_LOCAL_BOT_API_ENABLED' in launcher_source
    assert 'VIVENTIUM_TELEGRAM_LOCAL_BOT_API_API_ID' in launcher_source
    assert 'VIVENTIUM_TELEGRAM_LOCAL_BOT_API_API_HASH' in launcher_source
    assert 'VIVENTIUM_TELEGRAM_MAX_FILE_SIZE' in launcher_source
    assert '--local \\' in launcher_source
    assert '--api-id="$local_api_id" \\' in launcher_source
    assert '--api-hash="$local_api_hash" \\' in launcher_source
    assert 'if ! start_telegram_local_bot_api; then' in launcher_source
