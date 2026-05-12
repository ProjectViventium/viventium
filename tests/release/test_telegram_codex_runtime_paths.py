from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
START_SCRIPT = REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"


def test_launcher_prefers_compiled_telegram_codex_runtime_files() -> None:
    launcher_text = START_SCRIPT.read_text(encoding="utf-8")

    assert "VIVENTIUM_APP_SUPPORT_ROOT/runtime/service-env/telegram-codex.env" in launcher_text
    assert "VIVENTIUM_APP_SUPPORT_ROOT/runtime/telegram-codex/settings.yaml" in launcher_text
    assert "VIVENTIUM_APP_SUPPORT_ROOT/runtime/telegram-codex/projects.yaml" in launcher_text
    assert 'TELEGRAM_CODEX_DIR/config/settings.yaml")}' in launcher_text
    assert 'TELEGRAM_CODEX_DIR/config/projects.yaml")}' in launcher_text
