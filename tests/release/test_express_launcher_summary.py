from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"


def test_express_launcher_summary_hides_deferred_service_urls_and_voice_instructions() -> None:
    source = LAUNCHER.read_text(encoding="utf-8")
    summary = source[source.index('echo -e "  ${CYAN}LibreChat Frontend:') :]

    assert "express_install_experience() {" in source
    assert "Optional services:" in summary
    assert "deferred by Easy Install" in summary
    assert "deferred by Express" not in summary
    assert "Connect an AI account:" in summary
    assert "if express_install_experience; then" in summary
    assert "First Run" in summary
    assert "Testing Voice Call Button" in summary

    express_branch, custom_branch = summary.split("if express_install_experience; then", 1)[1].split(
        "else", 1
    )
    assert "VIVENTIUM_PLAYGROUND_URL" not in express_branch
    assert "LIVEKIT_URL" not in express_branch
    assert "Testing Voice Call Button" in custom_branch


def test_detached_launcher_does_not_tell_the_user_to_press_control_c() -> None:
    source = LAUNCHER.read_text(encoding="utf-8")
    assert "if ! detached_start_requested; then" in source
    assert "Press Ctrl+C to stop all services" in source


def test_loopback_launcher_never_advertises_an_unreachable_lan_url() -> None:
    source = LAUNCHER.read_text(encoding="utf-8")

    assert 'FRONTEND_BIND_HOST="${HOST:-::}"' in source
    assert '"$FRONTEND_BIND_HOST" != "127.0.0.1"' in source
    assert '"$FRONTEND_BIND_HOST" != "localhost"' in source
