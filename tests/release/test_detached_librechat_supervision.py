from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def extract_shell_function(text: str, name: str) -> str:
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.strip() == f"{name}() {{":
            start = index
            break
    if start is None:
        raise AssertionError(f"Missing shell function: {name}")

    collected: list[str] = []
    depth = 0
    for line in lines[start:]:
        collected.append(line)
        depth += line.count("{")
        depth -= line.count("}")
        if depth == 0:
            break
    return "\n".join(collected) + "\n"


def test_direct_detached_librechat_fallback_supervises_backend_and_frontend() -> None:
    launcher_text = (REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh").read_text(
        encoding="utf-8"
    )

    assert 'log_info "Using direct LibreChat startup fallback' in launcher_text
    assert 'npm run backend:dev &' in launcher_text
    assert 'BACKEND_PID=$!' in launcher_text
    assert 'librechat_dev_host="${HOST:-::}"' in launcher_text
    assert 'npm run dev -- --host "$librechat_dev_host" --port "$LC_FRONTEND_PORT"' in launcher_text
    assert 'FRONTEND_PID=$!' in launcher_text
    assert 'wait "$BACKEND_PID" "$FRONTEND_PID"' in launcher_text
    assert 'exec env PORT="$LC_FRONTEND_PORT" npm run frontend:dev' not in launcher_text


def test_deferred_telegram_start_retries_in_background_until_librechat_api_is_ready() -> None:
    launcher_text = (REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh").read_text(
        encoding="utf-8"
    )

    assert 'TELEGRAM_BOT_DEFERRED_PID_FILE="$LOG_ROOT/telegram_bot_deferred.pid"' in launcher_text
    assert 'TELEGRAM_BOT_DEFERRED_MARKER_FILE="$LOG_ROOT/telegram_bot_deferred.pending"' in launcher_text
    assert "schedule_deferred_telegram_bot_start() {" in launcher_text
    assert ': >"$TELEGRAM_BOT_DEFERRED_MARKER_FILE"' in launcher_text
    assert 'background_retries="${TELEGRAM_LIBRECHAT_DEFERRED_START_RETRIES:-${TELEGRAM_LIBRECHAT_START_RETRIES:-1800}}"' in launcher_text
    assert 'printf \'%s\\n\' "$deferred_pid" >"$TELEGRAM_BOT_DEFERRED_PID_FILE"' in launcher_text
    assert 'log_info "Queued deferred Telegram bot startup watcher (PID: $deferred_pid)"' in launcher_text
    assert 'if ! schedule_deferred_telegram_bot_start; then' in launcher_text
    assert 'log_warn "Unable to queue deferred Telegram bot startup; falling back to inline wait"' in launcher_text
    assert 'telegram_deferred_start_pending() {' in launcher_text
    assert 'elif telegram_deferred_start_pending; then' in launcher_text
    assert 'starting (waiting for LibreChat API)' in launcher_text


def test_searxng_readiness_probe_uses_root_endpoint() -> None:
    launcher_text = (REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh").read_text(
        encoding="utf-8"
    )

    assert 'searxng_http_ping() {' in launcher_text
    assert 'local ready_retries="${VIVENTIUM_SEARXNG_READY_RETRIES:-60}"' in launcher_text
    assert 'status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "${base_url}/" || true)' in launcher_text
    assert '/search?q=ping&format=json' not in launcher_text


def test_scope_detection_matches_processes_by_working_directory(tmp_path: Path) -> None:
    launcher_text = (REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh").read_text(
        encoding="utf-8"
    )
    functions = "".join(
        extract_shell_function(launcher_text, name)
        for name in (
            "read_pid_cwd",
            "normalize_scope_path",
            "path_is_trashed_checkout",
            "scope_component_signature",
            "pid_matches_trashed_scope_variant",
            "pid_matches_scope",
            "find_scope_pattern_pids",
        )
    )

    worker = tmp_path / "worker.py"
    worker.write_text("import time\nwhile True:\n    time.sleep(1)\n", encoding="utf-8")

    sleeper = subprocess.Popen(
        ["python3", "worker.py"],
        cwd=tmp_path,
    )
    try:
        completed = subprocess.run(
            [
                "bash",
                "-lc",
                (
                        "set -euo pipefail\n"
                        f"{functions}"
                        f'SCOPE="{tmp_path}"\n'
                        f'PID="{sleeper.pid}"\n'
                        'pid_matches_scope "$PID" "$SCOPE"\n'
                        'MATCHED="$(find_scope_pattern_pids "python3 worker.py" "$SCOPE")"\n'
                        '[[ " $MATCHED " == *" $PID "* ]]\n'
                    ),
                ],
                cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        assert completed.returncode == 0
    finally:
        sleeper.terminate()
        sleeper.wait(timeout=5)
