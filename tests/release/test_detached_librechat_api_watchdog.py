from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_detached_launch_installs_librechat_api_watchdog_contract() -> None:
    launcher_text = (REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh").read_text(
        encoding="utf-8"
    )

    assert 'LIBRECHAT_API_WATCHDOG_PID_FILE="$LOG_ROOT/librechat-api-watchdog.pid"' in launcher_text
    assert 'LIBRECHAT_API_WATCHDOG_LOG_FILE="$LOG_DIR/librechat-api-watchdog.log"' in launcher_text
    assert "librechat_api_healthy() {" in launcher_text
    assert "restart_detached_librechat_backend() {" in launcher_text
    assert "start_detached_librechat_api_watchdog() {" in launcher_text
    assert "stop_detached_librechat_api_watchdog() {" in launcher_text
    assert 'while [[ "$port_release_tries" -lt 10 ]] && port_has_listener "$LC_API_PORT"; do' in launcher_text
    assert 'wait_for_http "${LC_API_URL}/health" "Detached LibreChat API watchdog initial probe"' in launcher_text
    assert 'wait_for_http "${LC_API_URL}/health" "LibreChat API after detached backend restart"' in launcher_text
    assert 'failed_recoveries=$((failed_recoveries + 1))' in launcher_text
    assert 'consecutive_failures="$failure_threshold"' in launcher_text
    assert "stop_detached_librechat_api_watchdog" in launcher_text
    assert "start_detached_librechat_api_watchdog" in launcher_text
    assert (
        "detached watchdog will monitor LibreChat API health while helper/user surfaces monitor readiness"
        in launcher_text
    )
