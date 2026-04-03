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
    assert 'local librechat_dev_host="${HOST:-::}"' in launcher_text
    assert 'npm run dev -- --host "$librechat_dev_host" --port "$LC_FRONTEND_PORT"' in launcher_text
    assert 'FRONTEND_PID=$!' in launcher_text
    assert 'wait "$BACKEND_PID" "$FRONTEND_PID"' in launcher_text
    assert 'exec env PORT="$LC_FRONTEND_PORT" npm run frontend:dev' not in launcher_text
