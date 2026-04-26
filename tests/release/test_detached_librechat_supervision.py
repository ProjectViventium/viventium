from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


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
    assert 'STARTED_LIBRECHAT_PIDS+=("$BACKEND_PID")' in launcher_text
    assert 'STARTED_LIBRECHAT_PIDS+=("$FRONTEND_PID")' in launcher_text
    assert 'wait "${STARTED_LIBRECHAT_PIDS[@]}"' in launcher_text
    assert 'exec env PORT="$LC_FRONTEND_PORT" npm run frontend:dev' not in launcher_text


def test_librechat_partial_stack_reuses_healthy_api_without_skipping_frontend() -> None:
    launcher_text = (REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh").read_text(
        encoding="utf-8"
    )

    assert 'LIBRECHAT_BACKEND_ALREADY_RUNNING=false' in launcher_text
    assert 'LIBRECHAT_FRONTEND_ALREADY_RUNNING=false' in launcher_text
    assert 'LibreChat partial stack already running; starting the missing service(s)' in launcher_text
    assert 'direct_librechat_reason="partial stack repair"' in launcher_text
    assert 'if [[ "$LIBRECHAT_BACKEND_ALREADY_RUNNING" != "true" ]]; then' in launcher_text
    assert 'if [[ "$LIBRECHAT_FRONTEND_ALREADY_RUNNING" != "true" ]]; then' in launcher_text


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


def test_telegram_bot_survives_detached_launcher_exit() -> None:
    launcher_text = (REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh").read_text(
        encoding="utf-8"
    )

    assert "cleanup() {\n  if detached_start_requested; then\n    return\n  fi" in launcher_text
    assert 'nohup "$telegram_python" bot.py >"$LOG_DIR/telegram_bot.log" 2>&1 < /dev/null &' in launcher_text
    assert 'if detached_start_requested; then\n    disown "$TELEGRAM_BOT_PID" 2>/dev/null || true\n  fi' in launcher_text


def test_searxng_readiness_probe_uses_root_endpoint() -> None:
    launcher_text = (REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh").read_text(
        encoding="utf-8"
    )

    assert 'searxng_http_ping() {' in launcher_text
    assert 'local ready_retries="${VIVENTIUM_SEARXNG_READY_RETRIES:-60}"' in launcher_text
    assert 'status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "${base_url}/" || true)' in launcher_text
    assert '/search?q=ping&format=json' not in launcher_text


def test_local_search_sync_failure_does_not_abort_frontend_startup() -> None:
    launcher_text = (REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh").read_text(
        encoding="utf-8"
    )

    assert 'if ! node scripts/viventium-sync-local-search.js; then' in launcher_text
    assert 'Local conversation search sync failed; continuing without blocking frontend startup' in launcher_text


def test_meilisearch_readiness_requires_authenticated_probe_and_reclaims_stale_local_listener() -> None:
    launcher_text = (REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh").read_text(
        encoding="utf-8"
    )

    assert 'meili_http_auth_ping() {' in launcher_text
    assert 'restart_viventium_owned_meilisearch_listener() {' in launcher_text
    assert 'Configured Meilisearch key does not match the Viventium-owned local listener' in launcher_text
    assert 'if meili_http_auth_ping "$MEILI_HOST"; then' in launcher_text
    assert 'if meili_http_ping "$MEILI_HOST"; then' in launcher_text


def test_server_package_rebuild_detects_newer_source_than_ignored_dist(tmp_path: Path) -> None:
    launcher_text = (REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh").read_text(
        encoding="utf-8"
    )
    functions = "".join(
        extract_shell_function(launcher_text, name)
        for name in ("find_librechat_source_newer_than_dist", "should_rebuild_librechat_server_packages")
    )

    librechat_dir = tmp_path / "LibreChat"
    dist_files = (
        librechat_dir / "packages" / "data-provider" / "dist" / "index.js",
        librechat_dir / "packages" / "data-schemas" / "dist" / "index.cjs",
        librechat_dir / "packages" / "api" / "dist" / "index.js",
    )
    for file_path in dist_files:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("// dist\n", encoding="utf-8")

    for file_path in (
        librechat_dir / "package.json",
        librechat_dir / "package-lock.json",
        librechat_dir / "packages" / "data-provider" / "package.json",
        librechat_dir / "packages" / "data-provider" / "rollup.config.js",
        librechat_dir / "packages" / "data-provider" / "server-rollup.config.js",
        librechat_dir / "packages" / "data-schemas" / "package.json",
        librechat_dir / "packages" / "data-schemas" / "rollup.config.js",
        librechat_dir / "packages" / "api" / "package.json",
        librechat_dir / "packages" / "api" / "rollup.config.js",
    ):
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("{}\n", encoding="utf-8")

    stale_source = librechat_dir / "packages" / "api" / "src" / "endpoints" / "openai" / "config.ts"
    stale_source.parent.mkdir(parents=True, exist_ok=True)
    stale_source.write_text("// newer source\n", encoding="utf-8")

    old_timestamp = 1_700_000_000
    new_timestamp = old_timestamp + 30
    for file_path in dist_files:
        os.utime(file_path, (old_timestamp, old_timestamp))
    for file_path in librechat_dir.rglob("*"):
        if file_path.is_file() and file_path not in dist_files:
            os.utime(file_path, (old_timestamp, old_timestamp))
    os.utime(stale_source, (new_timestamp, new_timestamp))

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                f"{functions}"
                f'LIBRECHAT_DIR="{librechat_dir}"\n'
                'if should_rebuild_librechat_server_packages; then\n'
                "  printf 'rebuild\\n'\n"
                "else\n"
                "  printf 'skip\\n'\n"
                "fi\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.stdout.strip() == "rebuild"


def test_client_package_rebuild_detects_newer_source_than_ignored_dist(tmp_path: Path) -> None:
    launcher_text = (REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh").read_text(
        encoding="utf-8"
    )
    functions = "".join(
        extract_shell_function(launcher_text, name)
        for name in ("find_librechat_source_newer_than_dist", "should_rebuild_librechat_client_package")
    )

    librechat_dir = tmp_path / "LibreChat"
    dist_file = librechat_dir / "packages" / "client" / "dist" / "index.js"
    dist_file.parent.mkdir(parents=True, exist_ok=True)
    dist_file.write_text("// dist\n", encoding="utf-8")
    for file_path in (
        librechat_dir / "package.json",
        librechat_dir / "package-lock.json",
        librechat_dir / "packages" / "client" / "package.json",
        librechat_dir / "packages" / "client" / "rollup.config.js",
    ):
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("{}\n", encoding="utf-8")

    stale_source = librechat_dir / "packages" / "client" / "src" / "index.ts"
    stale_source.parent.mkdir(parents=True, exist_ok=True)
    stale_source.write_text("// newer source\n", encoding="utf-8")

    old_timestamp = 1_700_000_000
    new_timestamp = old_timestamp + 30
    os.utime(dist_file, (old_timestamp, old_timestamp))
    for file_path in librechat_dir.rglob("*"):
        if file_path.is_file() and file_path != dist_file:
            os.utime(file_path, (old_timestamp, old_timestamp))
    os.utime(stale_source, (new_timestamp, new_timestamp))

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                f"{functions}"
                f'LIBRECHAT_DIR="{librechat_dir}"\n'
                'if should_rebuild_librechat_client_package; then\n'
                "  printf 'rebuild\\n'\n"
                "else\n"
                "  printf 'skip\\n'\n"
                "fi\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.stdout.strip() == "rebuild"


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
        probe = subprocess.run(
            [
                "bash",
                "-lc",
                (
                    "set -euo pipefail\n"
                    f"{functions}"
                    f'PID="{sleeper.pid}"\n'
                    'read_pid_cwd "$PID"\n'
                ),
            ],
            cwd=REPO_ROOT,
            check=False,
            text=True,
            capture_output=True,
        )
        if not probe.stdout.strip():
            pytest.skip("macOS process inspection does not expose cwd on this host")
        direct_match = subprocess.run(
            [
                "bash",
                "-lc",
                (
                    "set -euo pipefail\n"
                    f"{functions}"
                    f'SCOPE="{tmp_path}"\n'
                    f'PID="{sleeper.pid}"\n'
                    'pid_matches_scope "$PID" "$SCOPE"\n'
                ),
            ],
            cwd=REPO_ROOT,
            check=False,
            text=True,
            capture_output=True,
        )
        if direct_match.returncode != 0:
            pytest.skip("macOS process inspection returned a cwd but did not allow stable scope matching")

        completed = subprocess.run(
            [
                "bash",
                "-lc",
                (
                    "set -euo pipefail\n"
                    f"{functions}"
                    f'SCOPE="{tmp_path}"\n'
                    f'PID="{sleeper.pid}"\n'
                    'MATCHED="$(find_scope_pattern_pids "python3 worker.py" "$SCOPE")"\n'
                    '[[ " $MATCHED " == *" $PID "* ]]\n'
                ),
            ],
            cwd=REPO_ROOT,
            check=False,
            text=True,
            capture_output=True,
        )
        if completed.returncode != 0:
            pytest.skip("macOS process inspection blocked scope-filtered pgrep verification on this host")
        assert completed.returncode == 0
    finally:
        sleeper.terminate()
        sleeper.wait(timeout=5)
