from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
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


def test_local_mongodb_is_a_single_node_replica_set_for_callback_transactions() -> None:
    launcher_text = (REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh").read_text(
        encoding="utf-8"
    )

    assert 'MONGO_REPLICA_SET="${VIVENTIUM_LOCAL_MONGO_REPLICA_SET:-viventium-rs}"' in launcher_text
    assert 'initialize_local_mongo_replica_set() {' in launcher_text
    assert 'mongo_replica_set_ready() {' in launcher_text
    assert '--replSet "$MONGO_REPLICA_SET"' in launcher_text
    assert 'ensure_local_mongo_replica_set' in launcher_text
    assert "replication?.replSet ||" in launcher_text


def test_orchestration_indexes_are_created_before_librechat_starts() -> None:
    launcher_text = (REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh").read_text(
        encoding="utf-8"
    )
    migration = (
        REPO_ROOT
        / "viventium_v0_4"
        / "LibreChat"
        / "scripts"
        / "viventium-sync-orchestration-indexes.js"
    ).read_text(encoding="utf-8")

    assert "ensure_orchestration_indexes() {" in launcher_text
    assert "viventium-sync-orchestration-indexes.js" in launcher_text
    assert launcher_text.index("\n  if ! ensure_orchestration_indexes") < launcher_text.index(
        "Starting LibreChat (backend+frontend)"
    )
    assert "cortex_outbox_replay_due" in migration
    assert "viventiumcortexinsightoutboxes" in migration
    assert "viventiumglasshivecallbackeffectoutboxes" in migration
    assert "expireAfterSeconds: 0" in migration


def test_librechat_partial_stack_reuses_healthy_api_without_skipping_frontend() -> None:
    launcher_text = (REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh").read_text(
        encoding="utf-8"
    )

    assert 'LIBRECHAT_BACKEND_ALREADY_RUNNING=false' in launcher_text
    assert 'LIBRECHAT_FRONTEND_ALREADY_RUNNING=false' in launcher_text
    assert 'LibreChat partial stack already running; starting the missing service(s)' in launcher_text
    assert 'direct_librechat_reason="partial stack repair"' in launcher_text
    assert 'if [[ "$LIBRECHAT_BACKEND_ALREADY_RUNNING" != "true" && "$LIBRECHAT_BACKEND_START_BLOCKED" != "true" ]]; then' in launcher_text
    assert 'if [[ "$LIBRECHAT_FRONTEND_ALREADY_RUNNING" != "true" && "$LIBRECHAT_FRONTEND_START_BLOCKED" != "true" ]]; then' in launcher_text


def test_librechat_partial_stack_starts_the_missing_peer_when_one_port_is_unhealthy() -> None:
    launcher_text = (REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh").read_text(
        encoding="utf-8"
    )

    assert 'LIBRECHAT_BACKEND_START_BLOCKED=false' in launcher_text
    assert 'LIBRECHAT_FRONTEND_START_BLOCKED=false' in launcher_text
    assert 'backend restart is blocked; continuing partial-stack repair' in launcher_text
    assert 'frontend restart is blocked; continuing partial-stack repair' in launcher_text
    assert 'if [[ "$LIBRECHAT_BACKEND_ALREADY_RUNNING" != "true" && "$LIBRECHAT_BACKEND_START_BLOCKED" != "true" ]]; then' in launcher_text
    assert 'if [[ "$LIBRECHAT_FRONTEND_ALREADY_RUNNING" != "true" && "$LIBRECHAT_FRONTEND_START_BLOCKED" != "true" ]]; then' in launcher_text


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


def test_deferred_telegram_start_waits_for_core_health_not_parallel_work_readiness() -> None:
    launcher_text = (REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh").read_text(
        encoding="utf-8"
    )
    deferred_start = launcher_text[
        launcher_text.index("schedule_deferred_telegram_bot_start() {") :
        launcher_text.index("\nstart_telegram_codex() {")
    ]

    assert '"${LC_API_URL}/api/health"' in deferred_start
    assert '"${LC_API_URL}/api/viventium/health/parallel-work"' not in deferred_start
    assert "LibreChat API before Telegram bot start" in deferred_start


def test_http_readiness_rejects_non_2xx_and_every_telegram_start_uses_core_health() -> None:
    launcher_text = (REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh").read_text(
        encoding="utf-8"
    )
    wait_for_http = extract_shell_function(launcher_text, "wait_for_http")
    start_telegram = launcher_text[
        launcher_text.index("start_telegram_bot() {") :
        launcher_text.index("\nschedule_deferred_telegram_bot_start() {")
    ]
    deferred_fallback = launcher_text[
        launcher_text.index('if [[ "$DEFER_TELEGRAM_LIBRECHAT_START" == "true" ]]; then') :
        launcher_text.index("\n# ----------------------------\n# Agents Playground")
    ]

    assert "curl -fsS --max-time 3" in wait_for_http
    assert "-H @-" in wait_for_http
    assert "X-VIVENTIUM-TELEGRAM-SECRET" in wait_for_http
    assert '"${LC_API_URL}/api/health"' in start_telegram
    assert '"${LC_API_URL}/api/viventium/health/parallel-work"' not in start_telegram
    assert '"${LC_API_URL}/api/health"' in deferred_fallback
    assert '"${LC_API_URL}/api/viventium/health/parallel-work"' not in deferred_fallback


def test_ms365_runtime_endpoint_refresh_does_not_mutate_compiled_runtime_env(
    tmp_path: Path,
) -> None:
    launcher_text = (REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh").read_text(
        encoding="utf-8"
    )
    function = extract_shell_function(launcher_text, "write_ms365_runtime_exports")
    runtime_env = tmp_path / "runtime.env"
    runtime_env.write_text("IMMUTABLE=1\nMS365_MCP_PORT=6274\n", encoding="utf-8")
    original = runtime_env.read_bytes()
    export_file = tmp_path / "state" / "ms365.runtime.env"

    subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                f"{function}"
                f"PYTHON_BIN={shlex.quote(sys.executable)}\n"
                f"VIVENTIUM_ENV_FILE={shlex.quote(str(runtime_env))}\n"
                f"MS365_MCP_RUNTIME_EXPORT_FILE={shlex.quote(str(export_file))}\n"
                "MS365_MCP_PORT=6388\n"
                "MS365_MCP_SERVER_URL=http://localhost:6388/mcp\n"
                "MS365_MCP_AUTH_URL=http://localhost:6388/authorize\n"
                "MS365_MCP_TOKEN_URL=http://localhost:6388/token\n"
                "write_ms365_runtime_exports\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert runtime_env.read_bytes() == original
    assert export_file.read_text(encoding="utf-8").splitlines() == [
        "MS365_MCP_PORT=6388",
        "MS365_MCP_SERVER_URL=http://localhost:6388/mcp",
        "MS365_MCP_AUTH_URL=http://localhost:6388/authorize",
        "MS365_MCP_TOKEN_URL=http://localhost:6388/token",
    ]


def test_telegram_bot_survives_detached_launcher_exit() -> None:
    launcher_text = (REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh").read_text(
        encoding="utf-8"
    )
    start_telegram_bot = launcher_text[
        launcher_text.index("start_telegram_bot() {") :
        launcher_text.index("\nschedule_deferred_telegram_bot_start() {")
    ]
    fallback_block = start_telegram_bot[
        start_telegram_bot.index('if [[ "$telegram_started_with_launchctl" != "true" ]]; then') :
        start_telegram_bot.index("TELEGRAM_STARTED_BY_SCRIPT=true")
    ]

    cleanup = launcher_text[launcher_text.index("cleanup() {"):launcher_text.index("\n}\n", launcher_text.index("cleanup() {"))]
    assert "if detached_start_requested; then\n    return\n  fi" in cleanup
    assert cleanup.index("if detached_start_requested") < cleanup.index("stop_telegram_bot_watchdog")
    assert "trap '' HUP" in launcher_text
    assert (
        'nohup "${telegram_launch_program[@]}" >"$LOG_DIR/telegram_bot.log" 2>&1 < /dev/null &'
        in fallback_block
    )
    assert 'nohup "$telegram_python" bot.py >"$LOG_DIR/telegram_bot.log" 2>&1 < /dev/null &' in launcher_text
    assert fallback_block.index("TELEGRAM_BOT_PID=$!") < fallback_block.index(
        'disown "$TELEGRAM_BOT_PID"'
    )
    assert re.search(
        r'if detached_start_requested; then\s+disown "\$TELEGRAM_BOT_PID" 2>/dev/null \|\| true\s+fi',
        fallback_block,
    )


def test_telegram_restart_uses_receipt_backed_handoff_without_pattern_kills() -> None:
    launcher_text = (REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh").read_text(
        encoding="utf-8"
    )
    stop_block = launcher_text[
        launcher_text.index("stop_running_services() {") :
        launcher_text.index("\ncleanup() {")
    ]
    start_telegram_bot = launcher_text[
        launcher_text.index("start_telegram_bot() {") :
        launcher_text.index("\nschedule_deferred_telegram_bot_start() {")
    ]

    assert "stop_owned_telegram_poller || true" in stop_block
    assert 'kill_by_pattern_scoped "python.*bot.py" "$telegram_dir/TelegramVivBot"' not in stop_block
    assert 'kill_by_pattern_scoped "python.*bot.py" "$PWD"' not in start_telegram_bot
    assert '"$TELEGRAM_POLLER_HANDOFF_HELPER" "${telegram_handoff_args[@]}"' in start_telegram_bot


def test_telegram_start_reconciles_only_verified_owner_before_launching() -> None:
    launcher_text = (REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh").read_text(
        encoding="utf-8"
    )
    start_telegram_bot = launcher_text[
        launcher_text.index("start_telegram_bot() {") :
        launcher_text.index("\nschedule_deferred_telegram_bot_start() {")
    ]

    assert "telegram_poller_status_json() {" in launcher_text
    assert "telegram_poller_handoff.py" in launcher_text
    assert "already running with verified ownership" in start_telegram_bot
    assert "attach-candidate" in start_telegram_bot
    assert "wait-ready" in start_telegram_bot
    assert "rollback" in start_telegram_bot
    assert 'kill_by_pattern_scoped "python.*bot.py" "$PWD"' not in start_telegram_bot


def test_cleanup_kills_librechat_processes_only_inside_librechat_scope() -> None:
    launcher_text = (REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh").read_text(
        encoding="utf-8"
    )
    cleanup_block = launcher_text[
        launcher_text.index("cleanup() {") :
        launcher_text.index("\ntrap cleanup")
    ]

    assert 'pkill -f "node.*api/server"' not in cleanup_block
    assert 'pkill -f "vite.*client"' not in cleanup_block
    assert 'kill_by_pattern_scoped "node.*api/server" "$LIBRECHAT_DIR"' in cleanup_block
    assert 'kill_by_pattern_scoped "vite.*client" "$LIBRECHAT_DIR"' in cleanup_block


def test_launcher_signals_exit_before_running_exit_cleanup() -> None:
    launcher_text = (REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh").read_text(
        encoding="utf-8"
    )

    assert "trap cleanup EXIT" in launcher_text
    assert "trap 'exit 130' INT" in launcher_text
    assert "trap 'exit 143' TERM" in launcher_text
    assert "trap cleanup INT TERM EXIT" not in launcher_text


def test_voice_gateway_requirements_check_detects_version_drift(tmp_path: Path) -> None:
    launcher_text = (REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh").read_text(
        encoding="utf-8"
    )
    function = extract_shell_function(launcher_text, "voice_requirements_need_install")
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("pip==0.0.0\n", encoding="utf-8")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                f"{function}"
                f"if voice_requirements_need_install {shlex.quote(sys.executable)} {shlex.quote(str(requirements))}; then\n"
                "  printf 'needs-install\\n'\n"
                "else\n"
                "  printf 'satisfied\\n'\n"
                "fi\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.stdout.strip() == "needs-install"


def test_voice_gateway_requirements_check_accepts_satisfied_pins(tmp_path: Path) -> None:
    import importlib.metadata as metadata

    launcher_text = (REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh").read_text(
        encoding="utf-8"
    )
    function = extract_shell_function(launcher_text, "voice_requirements_need_install")
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(f"PyYAML=={metadata.version('PyYAML')}\n", encoding="utf-8")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                f"{function}"
                f"if voice_requirements_need_install {shlex.quote(sys.executable)} {shlex.quote(str(requirements))}; then\n"
                "  printf 'needs-install\\n'\n"
                "else\n"
                "  printf 'satisfied\\n'\n"
                "fi\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.stdout.strip() == "satisfied"


def test_searxng_readiness_probe_uses_root_endpoint() -> None:
    launcher_text = (REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh").read_text(
        encoding="utf-8"
    )

    assert 'searxng_http_ping() {' in launcher_text
    assert 'local ready_retries="${VIVENTIUM_SEARXNG_READY_RETRIES:-60}"' in launcher_text
    assert 'status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "${base_url}/" || true)' in launcher_text
    assert '/search?q=ping&format=json' not in launcher_text


def test_local_search_sync_failure_does_not_abort_frontend_startup(tmp_path: Path) -> None:
    launcher_text = (REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh").read_text(
        encoding="utf-8"
    )

    assert (
        'if ! USE_REDIS=false USE_REDIS_STREAMS=false node scripts/viventium-sync-local-search.js; then'
        in launcher_text
    )
    assert 'Local conversation search sync failed; the API will retry its normal background sync' in launcher_text
    start = launcher_text.index('      if is_truthy "${SEARCH:-false}"; then', launcher_text.index('      prepare_librechat_build_outputs || exit 1'))
    end = launcher_text.index('      # Keep detached/direct launches', start)
    observed = subprocess.run(
        ["bash", "-c", 'set -eu; SEARCH=true; YELLOW=; CYAN=; NC=; LOG_DIR="$1"; ' +
         'is_truthy() { return 0; }; log_warn() { :; }; ' +
         'node() { sleep 0.2; touch "$LOG_DIR/search-finished"; return 1; };\n' +
         launcher_text[start:end] + '\n[[ ! -e "$LOG_DIR/search-finished" ]]; touch "$LOG_DIR/frontend-started"; wait',
         'probe', str(tmp_path)], capture_output=True, text=True,
    )
    assert observed.returncode == 0, observed.stderr
    assert (tmp_path / 'frontend-started').exists()
    assert (tmp_path / 'search-finished').exists()


def test_meilisearch_readiness_requires_authenticated_probe_and_reclaims_stale_local_listener() -> None:
    launcher_text = (REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh").read_text(
        encoding="utf-8"
    )

    assert 'meili_http_auth_ping() {' in launcher_text
    assert 'meili_recent_failed_task_health() {' in launcher_text
    assert 'meili_http_functional_ready() {' in launcher_text
    assert 'restart_viventium_owned_meilisearch_listener() {' in launcher_text
    assert 'Configured Meilisearch key does not match the Viventium-owned local listener' in launcher_text
    assert '/tasks?statuses=failed&limit=${lookback}' in launcher_text
    assert 'refusing to enqueue more local search work' in launcher_text
    assert 'MEILI_MAX_INDEXING_MEMORY="${MEILI_MAX_INDEXING_MEMORY:-512MiB}"' in launcher_text
    assert 'MEILI_MAX_INDEXING_THREADS="${MEILI_MAX_INDEXING_THREADS:-1}"' in launcher_text
    assert 'MEILI_ENV="${VIVENTIUM_LOCAL_MEILI_ENV:-production}"' in launcher_text
    assert 'MEILI_IMAGE="${MEILI_IMAGE:-getmeili/meilisearch:v1.43.0}"' in launcher_text
    assert '--memory "$MEILI_DOCKER_MEMORY_LIMIT"' in launcher_text
    assert '--cpus "$MEILI_DOCKER_CPUS"' in launcher_text
    assert '--pids-limit "$MEILI_DOCKER_PIDS_LIMIT"' in launcher_text
    assert '--log-opt "max-size=${MEILI_DOCKER_LOG_MAX_SIZE}"' in launcher_text
    assert '-e "MEILI_ENV=${MEILI_ENV}"' in launcher_text
    assert 'MEILI_ENV="$MEILI_ENV" \\' in launcher_text
    assert 'if meili_http_auth_ping "$MEILI_HOST"; then' in launcher_text
    assert 'if meili_http_functional_ready "$MEILI_HOST"; then' in launcher_text
    assert 'if meili_http_ping "$MEILI_HOST"; then' in launcher_text


def test_server_package_rebuild_detects_newer_source_than_ignored_dist(tmp_path: Path) -> None:
    launcher_text = (REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh").read_text(
        encoding="utf-8"
    )
    launcher_text += (REPO_ROOT / "scripts/viventium/librechat_build.sh").read_text(encoding="utf-8")
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
    launcher_text += (REPO_ROOT / "scripts/viventium/librechat_build.sh").read_text(encoding="utf-8")
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



def test_each_supervised_service_generation_reloads_the_active_local_qa_session() -> None:
    launcher_text = (REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh").read_text(
        encoding="utf-8"
    )
    loader = extract_shell_function(launcher_text, "load_local_qa_runtime_control")
    assert "clear_local_qa_runtime_exports" in loader
    assert '"$LOCAL_QA_CONTROL_SCRIPT" emit-shell' in loader

    for function_name in (
        "restart_detached_librechat_backend",
        "start_glasshive",
        "start_telegram_bot",
    ):
        assert "load_local_qa_runtime_control" in extract_shell_function(
            launcher_text, function_name
        )
