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
    assert "librechat_api_health_url() {" in launcher_text
    assert 'local origin="${VIVENTIUM_LIBRECHAT_ORIGIN:-$LC_API_URL}"' in launcher_text
    assert "restart_detached_librechat_backend() {" in launcher_text
    assert "start_detached_librechat_api_watchdog() {" in launcher_text
    assert "stop_detached_librechat_api_watchdog() {" in launcher_text
    assert 'port_has_listener "$VIVENTIUM_SANDPACK_BUNDLER_PORT"' in launcher_text
    assert 'local initial_retries="${LIBRECHAT_API_WATCHDOG_INITIAL_RETRIES:-1800}"' in launcher_text
    assert 'local initial_recovery_retries="${LIBRECHAT_API_WATCHDOG_INITIAL_RECOVERY_RETRIES:-60}"' in launcher_text
    assert 'wait_for_librechat_runtime "Detached LibreChat runtime watchdog initial probe"' in launcher_text
    assert "Detached LibreChat API watchdog did not observe complete runtime health; attempting backend recovery" in launcher_text
    assert 'wait_for_librechat_runtime "LibreChat runtime after detached backend restart"' in launcher_text
    assert "continuing recovery loop" in launcher_text
    assert 'failed_recoveries=$((failed_recoveries + 1))' in launcher_text
    assert 'consecutive_failures="$failure_threshold"' in launcher_text
    assert "stop_detached_librechat_api_watchdog" in launcher_text
    assert "start_detached_librechat_api_watchdog" in launcher_text
    assert (
        "detached watchdog will monitor LibreChat API/artifact health while helper/user surfaces monitor readiness"
        in launcher_text
    )


def test_detached_watchdog_initial_probe_enters_recovery_loop() -> None:
    launcher_text = (REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh").read_text(
        encoding="utf-8"
    )

    initial_probe = launcher_text.index(
        'while ! wait_for_librechat_runtime "Detached LibreChat runtime watchdog initial probe" "$initial_recovery_retries"; do'
    )
    recovery_notice = launcher_text.index(
        "Detached LibreChat API watchdog did not observe complete runtime health; attempting backend recovery",
        initial_probe,
    )
    restart_call = launcher_text.index("restart_detached_librechat_backend", recovery_notice)
    recovery_probe = launcher_text.index(
        'wait_for_librechat_runtime "LibreChat runtime after detached backend restart" "$recovery_retries"',
        restart_call,
    )
    continue_notice = launcher_text.index("continuing recovery loop", recovery_probe)

    assert initial_probe < recovery_notice < restart_call < recovery_probe < continue_notice
