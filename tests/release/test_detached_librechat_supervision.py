from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


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
