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


def test_telegram_codex_restart_cleans_scoped_sidecar_orphans() -> None:
    launcher_text = START_SCRIPT.read_text(encoding="utf-8")
    start_telegram_codex = launcher_text[
        launcher_text.index("start_telegram_codex() {") :
        launcher_text.index("\ngoogle_mcp_can_start_in_parallel_with_librechat() {")
    ]

    assert 'kill_by_pattern_scoped "telegram-codex" "$telegram_codex_dir"' in start_telegram_codex
    assert 'kill_by_pattern_scoped "uv run telegram-codex" "$telegram_codex_dir"' in start_telegram_codex
    assert start_telegram_codex.index('if [[ "$RESTART_SERVICES" == "true" ]]; then') < start_telegram_codex.index(
        'local existing_pids=""'
    )
