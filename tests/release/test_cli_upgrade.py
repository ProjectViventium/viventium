from __future__ import annotations

import errno
import json
import os
import pty
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


def write_executable(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def copy_cli_fixture(repo_root: Path) -> None:
    shutil.copy2(REPO_ROOT / "bin" / "viventium", repo_root / "bin" / "viventium")
    (repo_root / "scripts" / "viventium").mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        REPO_ROOT / "scripts" / "viventium" / "upgrade_transaction.py",
        repo_root / "scripts" / "viventium" / "upgrade_transaction.py",
    )
    write_executable(
        repo_root / "scripts" / "viventium" / "default_nightly_routines.py",
        "#!/usr/bin/env python3\nraise SystemExit(0)\n",
    )
    shutil.copy2(
        REPO_ROOT / "scripts" / "viventium" / "host_cli_auth.py",
        repo_root / "scripts" / "viventium" / "host_cli_auth.py",
    )
    (repo_root / "components.lock.json").write_text('{"version": 1, "components": []}\n', encoding="utf-8")
    write_executable(
        repo_root / "scripts" / "viventium" / "upgrade_check.py",
        "#!/usr/bin/env python3\n"
        "import json, os\n"
        "from pathlib import Path\n"
        "marker = Path(os.environ.get('TEST_ROOT', '.')) / 'component-drift-after-bootstrap'\n"
        "drift = [{'name': 'LibreChat', 'status': 'dirty_worktree'}] if marker.exists() else []\n"
        "print(json.dumps({'blockers': ['component_lock_drift'] if drift else [], 'component_lock_drift': drift, 'ready_to_upgrade': not drift}))\n"
        "raise SystemExit(3 if drift else 0)\n",
    )
    write_executable(
        repo_root / "scripts" / "viventium" / "continuity_audit.py",
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "from pathlib import Path\n"
        "output = Path(sys.argv[sys.argv.index('--output') + 1])\n"
        "output.parent.mkdir(parents=True, exist_ok=True)\n"
        "output.write_text(json.dumps({'status': 'warning'}) + '\\n', encoding='utf-8')\n",
    )


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


def strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)


def test_compile_config_keeps_compile_phase_for_compiler_process() -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    function_def = extract_shell_function(cli_source, "compile_config")

    export_index = function_def.index('export VIVENTIUM_LIBRECHAT_SOURCE_PHASE="compile"')
    prepare_index = function_def.index("prepare_runtime_exports")
    compiler_index = function_def.index('"$PYTHON_BIN" "$REPO_ROOT/scripts/viventium/config_compiler.py"')
    unset_index = function_def.index("unset VIVENTIUM_LIBRECHAT_SOURCE_PHASE")

    assert export_index < prepare_index < compiler_index < unset_index


def test_doctor_compiler_invocations_ignore_generated_runtime_source_override() -> None:
    doctor_source = (REPO_ROOT / "scripts" / "viventium" / "doctor.sh").read_text(encoding="utf-8")

    assert doctor_source.count("VIVENTIUM_LIBRECHAT_SOURCE_PHASE=compile") >= 2
    assert doctor_source.count("VIVENTIUM_LIBRECHAT_SOURCE_OF_TRUTH=") >= 2
    for snippet in doctor_source.split('"$PYTHON_BIN" "$SCRIPT_DIR/config_compiler.py"')[:2]:
        assert "VIVENTIUM_LIBRECHAT_SOURCE_PHASE=compile" in snippet
        assert "VIVENTIUM_LIBRECHAT_SOURCE_OF_TRUTH=" in snippet


def password_reset_runtime_probe(tmp_path: Path, extra_env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    function_def = extract_shell_function(cli_source, "prepare_password_reset_link_runtime")
    selected_checkout = tmp_path / "selected-librechat"
    (selected_checkout / "config").mkdir(parents=True)
    (selected_checkout / "config" / "issue-password-reset-link.js").write_text(
        "// synthetic reset helper\n", encoding="utf-8"
    )
    env = {
        **os.environ,
        "VIVENTIUM_LIBRECHAT_DIR": str(selected_checkout),
        **extra_env,
    }
    for key in ("DOMAIN_CLIENT", "CLIENT_URL", "VIVENTIUM_PUBLIC_CLIENT_URL"):
        if key not in extra_env:
            env.pop(key, None)
    return subprocess.run(
        [
            "bash",
            "-c",
            "set -euo pipefail\n"
            f"REPO_ROOT={tmp_path!s}\n"
            f"{function_def}\n"
            "prepare_password_reset_link_runtime\n"
            "printf '%s\\n%s\\n' \"$DOMAIN_CLIENT\" \"$PASSWORD_RESET_LINK_SCRIPT\"\n",
        ],
        check=False,
        text=True,
        capture_output=True,
        env=env,
    )


def test_password_reset_link_uses_compiled_local_origin_and_selected_librechat_checkout(
    tmp_path: Path,
) -> None:
    completed = password_reset_runtime_probe(
        tmp_path,
        {"VIVENTIUM_LC_FRONTEND_PORT": "53190"},
    )

    assert completed.returncode == 0, completed.stderr
    origin, script_path = completed.stdout.splitlines()
    assert origin == "http://127.0.0.1:53190"
    assert script_path == str(
        (tmp_path / "selected-librechat" / "config" / "issue-password-reset-link.js").resolve()
    )


@pytest.mark.parametrize(
    ("extra_env", "expected"),
    [
        (
            {
                "DOMAIN_CLIENT": "https://configured.example.invalid",
                "CLIENT_URL": "https://ignored.example.invalid",
            },
            "https://configured.example.invalid",
        ),
        (
            {"CLIENT_URL": "https://configured.example.invalid"},
            "https://configured.example.invalid",
        ),
        (
            {"VIVENTIUM_PUBLIC_CLIENT_URL": "https://public.example.invalid"},
            "https://public.example.invalid",
        ),
    ],
)
def test_password_reset_link_preserves_explicit_non_loopback_origin(
    tmp_path: Path,
    extra_env: dict[str, str],
    expected: str,
) -> None:
    completed = password_reset_runtime_probe(tmp_path, extra_env)

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.splitlines()[0] == expected


def test_password_reset_link_rejects_missing_selected_librechat_checkout(tmp_path: Path) -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    function_def = extract_shell_function(cli_source, "prepare_password_reset_link_runtime")
    missing_checkout = tmp_path / "missing-librechat"
    completed = subprocess.run(
        [
            "bash",
            "-c",
            "set -uo pipefail\n"
            f"REPO_ROOT={tmp_path!s}\n"
            f"{function_def}\n"
            "prepare_password_reset_link_runtime\n",
        ],
        check=False,
        text=True,
        capture_output=True,
        env={**os.environ, "VIVENTIUM_LIBRECHAT_DIR": str(missing_checkout)},
    )

    assert completed.returncode == 1
    assert "selected LibreChat checkout is missing" in completed.stderr


def test_password_reset_link_command_executes_validated_selected_helper() -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    section = cli_source[
        cli_source.index("  password-reset-link)\n", cli_source.index('case "$COMMAND" in')) :
        cli_source.index("  launch)\n", cli_source.index("  password-reset-link)\n", cli_source.index('case "$COMMAND" in')))
    ]

    assert "prepare_password_reset_link_runtime" in section
    assert 'exec node "$PASSWORD_RESET_LINK_SCRIPT"' in section


def run_bash_on_pty(script: str, *, cwd: Path, env: dict[str, str] | None = None) -> tuple[int, str]:
    env_payload = {**os.environ, **(env or {})}
    pid, master_fd = pty.fork()
    if pid == 0:
        os.chdir(cwd)
        os.execvpe("bash", ["bash", "-lc", script], env_payload)
    chunks: list[bytes] = []
    try:
        while True:
            try:
                chunk = os.read(master_fd, 4096)
            except OSError as exc:
                if exc.errno == errno.EIO:
                    break
                raise
            if not chunk:
                break
            chunks.append(chunk)
    finally:
        os.close(master_fd)
    _, status = os.waitpid(pid, 0)
    return (
        os.waitstatus_to_exitcode(status),
        b"".join(chunks).decode("utf-8", errors="replace").replace("\r\n", "\n"),
    )


def test_install_autostart_hands_off_to_detached_health_checked_start() -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    install_section = cli_source.split('if [[ "$AUTO_START" == "1" ]]; then', 1)[1].split(
        "INSTALL_TRAP_ACTIVE=0",
        1,
    )[0]
    detached_section = cli_source.split("start_stack_for_install() {", 1)[1].split(
        "stop_stack_for_upgrade() {",
        1,
    )[0]
    install_surfaces_function = extract_shell_function(cli_source, "install_surfaces_healthy")

    assert "wait_for_install_stack_health() {" in cli_source
    assert "sanitize_macos_locale() {" in cli_source
    assert "sanitize_macos_locale" in cli_source.split("refresh_repo_python() {", 1)[0]
    assert "optional_install_surfaces_healthy() {" in cli_source
    assert "runtime_optional_surfaces_healthy() {" in cli_source
    assert "install_surfaces_healthy() {" in cli_source
    assert "render_install_wait_progress() {" in cli_source
    assert "install_wait_log_activity_summary() {" in cli_source
    assert "print_install_start_expectations() {" in cli_source
    assert "install_wait_pick_next_tagline() {" in cli_source
    assert "install_wait_current_tagline() {" in cli_source
    assert "clear_install_wait_progress_frame() {" in cli_source
    assert "assign_runtime_ports() {" in cli_source
    assert "detached_start_failed_early() {" in cli_source
    assert "needs_connected_accounts_guidance() {" in cli_source
    assert "print_connected_accounts_browser_reminder() {" in cli_source
    assert "add an OpenAI or Anthropic API key" in cli_source
    assert "connect OpenAI or Anthropic" not in cli_source
    assert 'if [[ "${VIVENTIUM_AUTO_APPROVE_PREREQS:-false}" == "true" || "${HEADLESS:-0}" == "1" ]]; then' in cli_source
    assert 'printf \'%s\' "$value" | tr \'[:upper:]\' \'[:lower:]\'' in cli_source
    assert '${value,,}' not in cli_source
    assert 'read -r api_port frontend_port playground_port <<<"$(read_runtime_ports)"' not in cli_source
    assert "start_stack_for_install() {" in cli_source
    assert "local_http_surface_healthy() {" in cli_source
    assert 'http_url_healthy "http://localhost:${port}${path_suffix}"' in cli_source
    assert 'http_url_healthy "http://127.0.0.1:${port}${path_suffix}"' in cli_source
    assert 'local timeout_seconds="${2:-2}"' in cli_source


def test_express_native_readiness_requires_only_api_and_web_and_skips_playground_build() -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")

    experience_function = extract_shell_function(cli_source, "express_install_experience")
    user_surfaces_function = extract_shell_function(cli_source, "all_user_surfaces_healthy")
    waiting_function = extract_shell_function(cli_source, "install_waiting_on_surfaces")
    build_function = extract_shell_function(cli_source, "install_first_run_build_expected")

    assert 'read_generated_env_value "VIVENTIUM_INSTALL_EXPERIENCE" "legacy"' in experience_function
    assert 'express_install_experience || playground_surface_healthy "$playground_port"' in user_surfaces_function
    assert '! sandpack_runtime_required || sandpack_surface_healthy "$sandpack_port"' in user_surfaces_function
    assert 'if sandpack_runtime_required && ! sandpack_surface_healthy "$sandpack_port"; then' in waiting_function
    assert 'waiting_on+=("Isolated browser runtime :$sandpack_port")' in waiting_function
    assert 'if ! express_install_experience && ! playground_surface_healthy "$playground_port"; then' in waiting_function
    assert 'if ! express_install_experience && [[ ! -d "$playground_dir/node_modules" ]]; then' in build_function

    launcher_source = (
        REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"
    ).read_text(encoding="utf-8")
    assert launcher_source.count('if is_truthy "${SEARCH:-false}"; then\n    if ! ensure_meilisearch_ready; then') == 2


def test_destructive_flows_drain_native_stack_before_removing_app_support() -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    install_section = cli_source.split('if [[ "$AUTO_START" == "1" ]]; then', 1)[1].split(
        "INSTALL_TRAP_ACTIVE=0",
        1,
    )[0]
    detached_section = cli_source.split("start_stack_for_install() {", 1)[1].split(
        "stop_stack_for_upgrade() {",
        1,
    )[0]
    install_surfaces_function = extract_shell_function(cli_source, "install_surfaces_healthy")
    drain_function = extract_shell_function(cli_source, "drain_native_stack_before_state_removal")
    removal_backup_function = extract_shell_function(cli_source, "backup_install_state_for_removal")
    reset_function = extract_shell_function(cli_source, "reset_local_install_state")
    uninstall_function = extract_shell_function(cli_source, "uninstall_local_installation")

    assert "prepare_runtime_exports" in drain_function
    assert 'source "$GENERATED_ENV"' in drain_function
    assert 'scripts/viventium/native_stack.sh" stop' in drain_function
    assert "drain_native_stack_before_state_removal" in reset_function
    assert "drain_native_stack_before_state_removal" in uninstall_function
    assert 'mv -- "$APP_SUPPORT_DIR" "$backup_dir"' in removal_backup_function
    assert 'cp "$GENERATED_ENV"' not in removal_backup_function
    assert "preserves databases, state, snapshots" in removal_backup_function
    assert reset_function.index("drain_native_stack_before_state_removal") < reset_function.index("backup_install_state_for_removal")
    assert uninstall_function.index("drain_native_stack_before_state_removal") < uninstall_function.index("backup_install_state_for_removal")
    assert 'local_http_surface_healthy "$port" "/api/health"' in cli_source
    assert 'local_http_surface_healthy "$port" "/"' in cli_source
    assert 'http_url_healthy "${base_url}/" 5' in cli_source
    assert '/search?q=ping&format=json' not in extract_shell_function(cli_source, "searxng_surface_healthy")
    firecrawl_surface_function = extract_shell_function(cli_source, "firecrawl_surface_healthy")
    assert 'http_url_healthy "${base_url}/health"' in firecrawl_surface_function
    assert 'curl -s --max-time 3 "${base_url}/" 2>/dev/null | grep -q "Firecrawl API"' in firecrawl_surface_function
    assert 'docker ps -q --filter "name=^/viventium_firecrawl_api$"' in firecrawl_surface_function
    assert 'if runtime_env_true "START_SEARXNG" "false" && ! searxng_surface_healthy; then' in cli_source
    assert 'if runtime_env_true "START_FIRECRAWL" "false" && ! firecrawl_surface_healthy; then' in cli_source
    runtime_optional_function = extract_shell_function(cli_source, "runtime_optional_surfaces_healthy")
    rag_surface_function = extract_shell_function(cli_source, "rag_api_surface_healthy")
    assert 'http_json_status_up "${base_url}/health"' in rag_surface_function
    assert 'http_url_healthy "${base_url}/"' not in rag_surface_function
    assert 'if runtime_env_true "START_RAG_API" "false" && ! rag_api_surface_healthy; then' in runtime_optional_function
    assert 'if runtime_env_true "START_GOOGLE_MCP" "false" && ! mcp_url_surface_reachable "GOOGLE_WORKSPACE_MCP_URL" "http://localhost:8111/mcp"; then' in runtime_optional_function
    assert 'if runtime_env_true "START_MS365_MCP" "false" && ! mcp_url_surface_reachable "MS365_MCP_SERVER_URL" "http://localhost:6274/mcp"; then' in runtime_optional_function
    assert 'if runtime_env_true "START_TELEGRAM" "false" && ! telegram_bridge_surface_healthy; then' in runtime_optional_function
    assert 'if runtime_env_true "START_TELEGRAM_CODEX" "false" && ! telegram_codex_surface_healthy; then' in runtime_optional_function
    assert '[[ "$code" =~ ^[1-4][0-9][0-9]$ ]]' in extract_shell_function(cli_source, "http_url_reachable")
    assert "runtime_pid_file_running" in extract_shell_function(cli_source, "telegram_bridge_surface_healthy")
    assert "optional_install_surfaces_healthy" in runtime_optional_function
    assert 'waiting_on+=("$(searxng_install_wait_label)")' in cli_source
    assert 'waiting_on+=("$(firecrawl_install_wait_label)")' in cli_source
    assert "all_user_surfaces_healthy" in install_surfaces_function
    assert "optional_install_surfaces_healthy" not in install_surfaces_function
    assert "launch_stack_detached" in detached_section
    assert "cleanup_cli_lock" in detached_section
    assert "user_surface_healthy" in detached_section
    assert "install_surfaces_healthy" in detached_section
    assert "is_stack_running" in detached_section
    assert 'local timeout_seconds="${VIVENTIUM_INSTALL_START_HEALTH_TIMEOUT_SECONDS:-1800}"' in detached_section
    assert 'local progress_interval="${VIVENTIUM_INSTALL_START_PROGRESS_SECONDS:-15}"' in cli_source
    assert 'local inline_render_interval="${VIVENTIUM_INSTALL_START_INLINE_PROGRESS_SECONDS:-0.2}"' in cli_source
    assert 'local repeat_interval="${VIVENTIUM_INSTALL_START_LOG_REPEAT_SECONDS:-60}"' in cli_source
    assert 'render_install_wait_progress "$elapsed" "$waiting_on" "$launch_log"' in cli_source
    assert 'INSTALL_WAIT_PROGRESS_LINES=2' in cli_source
    assert 'Go scroll some reels while I take care of this for you.' in cli_source
    assert "Failed.......................... JK, it's going well ;)" in cli_source
    assert 'Extracting pure epicness...' in cli_source
    assert "What's your favorite political party? I'm pro AI." in cli_source
    assert 'Preparing first-run startup...' in cli_source
    assert 'Building LibreChat and playground assets locally. On a clean Mac this can take around 10-15 minutes.' in cli_source
    assert 'Starting local web-search services in parallel through Docker Desktop.' in cli_source
    assert 'print_install_timeout_log_excerpt "$launch_log"' in detached_section
    assert 'echo "Still waiting on: $waiting_on"' in detached_section
    assert 'waiting_on="core service readiness"' in cli_source
    assert 'echo "Viventium did not become healthy before the install start timeout (${timeout_seconds}s)."' in detached_section
    assert 'echo "Viventium stopped during startup before the required surfaces became healthy."' in detached_section
    assert "Starting Viventium..." in install_section
    assert "maybe_install_macos_helper --no-launch" in cli_source
    assert "if ! start_stack_for_install; then" in install_section
    assert "print_install_summary 1" in install_section
    assert "exit 1" in install_section
    assert "launch_macos_helper_app" in cli_source
    assert 'print_install_summary 1' in cli_source
    assert 'launch_macos_helper_app\n      print_install_summary 1\n      open_default_browser' in cli_source
    assert "print_connected_accounts_browser_reminder" in cli_source
    assert (
        'launch_macos_helper_app\n      print_install_summary 1\n      open_default_browser\n      print_connected_accounts_browser_reminder'
        in cli_source
    )


def test_uninstall_honors_explicit_no_helper_install_contract(tmp_path: Path) -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    uninstall_function = extract_shell_function(cli_source, "uninstall_local_installation")
    app_support = tmp_path / "app-support"
    app_support.mkdir()
    helper_call_marker = tmp_path / "helper-uninstall-called"

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                f"APP_SUPPORT_DIR={str(app_support)!r}\n"
                f"CONFIG_FILE={str(app_support / 'config.yaml')!r}\n"
                "VIVENTIUM_SKIP_HELPER_INSTALL=1\n"
                "is_stack_running() { return 1; }\n"
                "stop_stack_for_upgrade() { return 0; }\n"
                "drain_native_stack_before_state_removal() { return 0; }\n"
                "backup_install_state_for_removal() { printf 'isolated-backup\\n'; }\n"
                "read_install_helper_ownership() { printf 'not-owned\\n'; }\n"
                "legacy_helper_ownership_matches_install() { return 1; }\n"
                "run_macos_helper_installer() {\n"
                f"  touch {str(helper_call_marker)!r}\n"
                "}\n"
                f"{uninstall_function}"
                "uninstall_local_installation\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert not helper_call_marker.exists()
    assert "receipt records no helper ownership" in completed.stdout
    assert not app_support.exists()


def test_uninstall_keeps_helper_removal_for_normal_install(tmp_path: Path) -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    uninstall_function = extract_shell_function(cli_source, "uninstall_local_installation")
    app_support = tmp_path / "app-support"
    app_support.mkdir()
    helper_call_marker = tmp_path / "helper-uninstall-called"

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                f"APP_SUPPORT_DIR={str(app_support)!r}\n"
                f"CONFIG_FILE={str(app_support / 'config.yaml')!r}\n"
                "VIVENTIUM_SKIP_HELPER_INSTALL=0\n"
                "is_stack_running() { return 1; }\n"
                "stop_stack_for_upgrade() { return 0; }\n"
                "drain_native_stack_before_state_removal() { return 0; }\n"
                "backup_install_state_for_removal() { printf 'normal-backup\\n'; }\n"
                "read_install_helper_ownership() { printf 'owned\\n'; }\n"
                "legacy_helper_ownership_matches_install() { return 1; }\n"
                "run_macos_helper_installer() {\n"
                f"  touch {str(helper_call_marker)!r}\n"
                "}\n"
                f"{uninstall_function}"
                "uninstall_local_installation\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert helper_call_marker.exists()
    assert "Skipped macOS helper removal" not in completed.stdout
    assert not app_support.exists()


def test_no_helper_install_receipt_survives_separate_shell_uninstall(tmp_path: Path) -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    receipt_path_function = extract_shell_function(cli_source, "install_ownership_receipt_file")
    write_receipt_function = extract_shell_function(cli_source, "write_install_ownership_receipt")
    read_receipt_function = extract_shell_function(cli_source, "read_install_helper_ownership")
    uninstall_function = extract_shell_function(cli_source, "uninstall_local_installation")
    app_support = tmp_path / "app-support"
    app_support.mkdir()
    helper_call_marker = tmp_path / "helper-uninstall-called"

    write_completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                f"APP_SUPPORT_DIR={str(app_support)!r}\n"
                f"PYTHON_BIN={sys.executable!r}\n"
                f"{receipt_path_function}{write_receipt_function}"
                "write_install_ownership_receipt false\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert write_completed.returncode == 0, write_completed.stderr

    uninstall_completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                f"APP_SUPPORT_DIR={str(app_support)!r}\n"
                f"CONFIG_FILE={str(app_support / 'config.yaml')!r}\n"
                f"PYTHON_BIN={sys.executable!r}\n"
                "is_stack_running() { return 1; }\n"
                "stop_stack_for_upgrade() { return 0; }\n"
                "drain_native_stack_before_state_removal() { return 0; }\n"
                "backup_install_state_for_removal() {\n"
                "  mv \"$APP_SUPPORT_DIR\" \"${APP_SUPPORT_DIR}.backup\"\n"
                "  printf 'separate-shell-backup\\n'\n"
                "}\n"
                "run_macos_helper_installer() {\n"
                f"  touch {str(helper_call_marker)!r}\n"
                "}\n"
                f"{receipt_path_function}{read_receipt_function}{uninstall_function}"
                "uninstall_local_installation\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
        env={key: value for key, value in os.environ.items() if key != "VIVENTIUM_SKIP_HELPER_INSTALL"},
    )

    assert uninstall_completed.returncode == 0, uninstall_completed.stderr
    assert not helper_call_marker.exists()
    assert "receipt records no helper ownership" in uninstall_completed.stdout


def test_failed_install_cleanup_drains_recorded_owned_process_group(tmp_path: Path) -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    matches_function = extract_shell_function(cli_source, "install_process_group_matches_scope")
    terminate_function = extract_shell_function(cli_source, "terminate_install_owned_process_group")
    drain_function = extract_shell_function(cli_source, "drain_failed_install_runtime")
    app_support = tmp_path / "app-support"
    runtime_state = app_support / "state" / "runtime" / "isolated"
    runtime_state.mkdir(parents=True)
    owned_runner = app_support / "owned-runner.sh"
    write_executable(owned_runner, "#!/usr/bin/env bash\nsleep 120\n")
    process = subprocess.Popen([str(owned_runner)], cwd=app_support, start_new_session=True)
    (runtime_state / "detached-launch.pgid").write_text(f"{process.pid}\n", encoding="utf-8")

    try:
        completed = subprocess.run(
            [
                "bash",
                "-lc",
                (
                    "set -euo pipefail\n"
                    f"APP_SUPPORT_DIR={str(app_support)!r}\n"
                    f"REPO_ROOT={str(tmp_path / 'repo')!r}\n"
                    "DETACHED_START_PID=''\n"
                    f"{matches_function}{terminate_function}{drain_function}"
                    "drain_failed_install_runtime\n"
                ),
            ],
            cwd=REPO_ROOT,
            check=False,
            text=True,
            capture_output=True,
        )
        assert completed.returncode == 0, completed.stderr
        process.wait(timeout=5)
        assert not (runtime_state / "detached-launch.pgid").exists()
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)


def test_upgrade_restart_hands_off_to_detached_health_checked_start() -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    upgrade_section = cli_source.rsplit("  upgrade|update)", 1)[1].split("  configure|wizard)", 1)[0]
    autorestart_section = upgrade_section.split('if [[ "$AUTO_RESTART" == "1" ]]; then', 1)[1].split(
        '    fi\n    echo "Upgrade complete. Next: bin/viventium start"',
        1,
    )[0]
    restart_section = cli_source.split("restart_stack_after_upgrade() {", 1)[1].split(
        "stop_stack_for_upgrade() {",
        1,
    )[0]

    assert "restart_stack_after_upgrade() {" in cli_source
    assert "capture_continuity_audit() {" in cli_source
    assert "remove_recall_rebuild_marker() {" in cli_source
    assert "continuity-audit  Capture continuity metadata for the current install." in cli_source
    assert "Pre-upgrade continuity audit written to" in upgrade_section
    assert "Post-upgrade continuity audit written to" in upgrade_section
    assert 'case "$POST_UPGRADE_CONTINUITY_STATUS" in' in upgrade_section
    assert "error|unknown|*)" in upgrade_section
    assert "cleanup_cli_lock" in restart_section
    assert "launch_stack_detached" in restart_section
    assert "wait_for_install_stack_health" in restart_section
    assert 'echo "Restarting Viventium..."' in restart_section
    assert "install_waiting_on_surfaces" in restart_section
    assert "print_install_timeout_log_excerpt" in restart_section
    assert "if ! restart_stack_after_upgrade; then" in upgrade_section
    assert '"$REPO_ROOT/bin/viventium" \\' not in autorestart_section
    assert "        start" not in autorestart_section


def test_upgrade_stop_failure_is_terminal_and_not_suppressed() -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    stop_function = extract_shell_function(cli_source, "stop_stack_for_upgrade")
    upgrade_section = cli_source.rsplit("  upgrade|update)", 1)[1].split("  configure|wizard)", 1)[0]

    assert "stop || true" not in stop_function
    assert 'if ! stop_stack_for_upgrade; then' in upgrade_section
    assert "Upgrade aborted because the running stack could not be stopped safely." in upgrade_section


def test_failed_upgrade_recovery_runs_verified_transaction_rollback() -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    recovery_function = extract_shell_function(cli_source, "recover_running_stack_after_failed_upgrade")

    assert "upgrade_transaction_rollback" in recovery_function
    assert "verified pre-upgrade source, config, runtime, and stopped data checkpoint" in recovery_function
    assert "previous verified Viventium runtime and running state were restored" in recovery_function
    assert "partially applied" not in recovery_function
    assert "current on-disk state" not in recovery_function


def test_upgrade_uses_immutable_pre_pull_transaction_runner() -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    begin = extract_shell_function(cli_source, "upgrade_transaction_begin")
    assert 'json.loads(sys.argv[1])["transaction_runner"]' in begin
    for name in (
        "upgrade_transaction_snapshot_stopped_state",
        "upgrade_transaction_prepare_candidate",
        "upgrade_transaction_checkpoint",
        "upgrade_transaction_activate_candidate",
        "upgrade_transaction_rollback",
        "upgrade_transaction_commit",
    ):
        function = extract_shell_function(cli_source, name)
        assert '"$UPGRADE_TRANSACTION_RUNNER"' in function
        assert '"$REPO_ROOT/scripts/viventium/upgrade_transaction.py"' not in function


def test_pre_upgrade_audit_does_not_mutate_bootstrap_python_before_checkpoint() -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    capture = extract_shell_function(cli_source, "capture_continuity_audit")
    upgrade_section = cli_source.rsplit("  upgrade|update)", 1)[1].split("  configure|wizard)", 1)[0]
    pre_audit = upgrade_section.split('PRE_UPGRADE_CONTINUITY_AUDIT="$', 1)[0]

    assert "VIVENTIUM_CONTINUITY_AUDIT_SKIP_PYTHON_REFRESH" in capture
    assert "VIVENTIUM_CONTINUITY_AUDIT_SKIP_PYTHON_REFRESH=1" in pre_audit


def test_continuity_error_disables_automatic_restart() -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    upgrade_section = cli_source.rsplit("  upgrade|update)", 1)[1].split("  configure|wizard)", 1)[0]
    autorestart_section = upgrade_section.rsplit('if [[ "$AUTO_RESTART" == "1" ]]; then', 1)[1]
    post_capture = upgrade_section.index('POST_UPGRADE_CONTINUITY_AUDIT="$(capture_continuity_audit')
    activation = upgrade_section.index("upgrade_transaction_activate_candidate")
    commit = upgrade_section.index("upgrade_transaction_commit")

    assert activation < post_capture < commit
    assert upgrade_section.index("maybe_install_macos_helper --no-launch") > commit
    assert 'case "$POST_UPGRADE_CONTINUITY_STATUS" in' in upgrade_section
    assert 'ok|warning)' in upgrade_section
    assert "rolling back" in upgrade_section
    assert "launch_macos_helper_app" in autorestart_section


def test_upgrade_refuses_running_stack_and_bad_baseline_before_pull_or_stop() -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    upgrade_section = cli_source.rsplit("  upgrade|update)", 1)[1].split("  configure|wizard)", 1)[0]

    running_gate = upgrade_section.index("if is_stack_running; then")
    safety_check = upgrade_section.index('UPGRADE_SAFETY_JSON="$("$PYTHON_BIN"')
    fetch = upgrade_section.index("fetch_current_branch_target")
    activation = upgrade_section.index("fast_forward_current_branch_to_target")
    pre_capture = upgrade_section.index('capture_continuity_audit "pre-upgrade-')
    pre_status = upgrade_section.index('PRE_UPGRADE_CONTINUITY_STATUS="$(continuity_audit_status')
    stop = upgrade_section.index("if ! stop_stack_for_upgrade; then")
    transaction = upgrade_section.index("upgrade_transaction_begin")
    recovery_trap = upgrade_section.index("trap recover_running_stack_after_failed_upgrade EXIT INT TERM")
    stopped_checkpoint = upgrade_section.index("upgrade_transaction_snapshot_stopped_state")
    assert running_gate < safety_check < pre_capture < pre_status < fetch < recovery_trap < transaction < stop < stopped_checkpoint < activation
    assert '[[ "$PRE_UPGRADE_CONTINUITY_STATUS" == "error" || "$PRE_UPGRADE_CONTINUITY_STATUS" == "unknown" ]]' in upgrade_section
    assert "Upgrade aborted because the pre-upgrade continuity audit is not trustworthy." in upgrade_section


def test_upgrade_check_does_not_create_app_support_layout() -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    upgrade_section = cli_source.rsplit("  upgrade|update)", 1)[1].split("  configure|wizard)", 1)[0]

    check_gate = upgrade_section.index('if [[ "$CHECK_ONLY" == "1" ]]; then')
    layout = upgrade_section.index('ensure_app_support_layout "$APP_SUPPORT_DIR"')
    assert check_gate < layout


def test_public_upgrade_check_does_not_bootstrap_or_create_app_support(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "bin").mkdir(parents=True)
    (repo / "scripts" / "viventium").mkdir(parents=True)
    shutil.copy2(REPO_ROOT / "bin" / "viventium", repo / "bin" / "viventium")
    shutil.copy2(REPO_ROOT / "scripts" / "viventium" / "common.sh", repo / "scripts" / "viventium" / "common.sh")
    shutil.copy2(REPO_ROOT / "scripts" / "viventium" / "upgrade_check.py", repo / "scripts" / "viventium" / "upgrade_check.py")
    shutil.copy2(
        REPO_ROOT / "scripts" / "viventium" / "bootstrap_components.py",
        repo / "scripts" / "viventium" / "bootstrap_components.py",
    )
    (repo / "scripts" / "viventium" / "requirements-installer.txt").write_text("", encoding="utf-8")
    (repo / "components.lock.json").write_text('{"components": []}\n', encoding="utf-8")
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "fixture"],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
    )
    branch = subprocess.run(
        ["git", "branch", "--show-current"], cwd=repo, check=True, text=True, stdout=subprocess.PIPE
    ).stdout.strip()
    subprocess.run(["git", "config", f"branch.{branch}.remote", "."], cwd=repo, check=True)
    subprocess.run(["git", "config", f"branch.{branch}.merge", f"refs/heads/{branch}"], cwd=repo, check=True)
    app_support = tmp_path / "must-remain-absent"

    result = subprocess.run(
        [str(repo / "bin" / "viventium"), "--app-support-dir", str(app_support), "upgrade", "--check", "--json"],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "VIVENTIUM_PYTHON_BIN": sys.executable},
    )

    assert result.returncode == 0
    assert json.loads(result.stdout)["schema_version"] == 1
    assert not app_support.exists()
    assert not (repo / "scripts" / "viventium" / "__pycache__").exists()


def test_public_restore_rejects_invalid_bundle_before_default_or_target_mutation(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "bin").mkdir(parents=True)
    (repo / "scripts" / "viventium").mkdir(parents=True)
    shutil.copy2(REPO_ROOT / "bin" / "viventium", repo / "bin" / "viventium")
    for name in ("common.sh", "restore.sh", "continuity_bundle.py"):
        shutil.copy2(REPO_ROOT / "scripts" / "viventium" / name, repo / "scripts" / "viventium" / name)
    (repo / "scripts" / "viventium" / "requirements-installer.txt").write_text("", encoding="utf-8")
    invalid_bundle = tmp_path / "invalid-bundle"
    invalid_bundle.mkdir()
    default_home = tmp_path / "default-app-support"
    target_home = tmp_path / "independent-target"

    result = subprocess.run(
        [
            str(repo / "bin" / "viventium"),
            "--app-support-dir",
            str(default_home),
            "restore",
            "--target-config-home",
            str(target_home),
            "--snapshot-dir",
            str(invalid_bundle),
        ],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "VIVENTIUM_PYTHON_BIN": sys.executable},
    )

    assert result.returncode == 3
    assert "producer completeness marker is missing" in result.stderr
    assert "ModuleNotFoundError" not in result.stderr
    assert not default_home.exists()
    assert not target_home.exists()


def test_mutating_upgrade_runs_structured_local_safety_check_before_pull_and_stop() -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    upgrade_section = cli_source.rsplit("  upgrade|update)", 1)[1].split("  configure|wizard)", 1)[0]

    safety_check = upgrade_section.index('UPGRADE_SAFETY_JSON="$("$PYTHON_BIN"')
    activation = upgrade_section.index("fast_forward_current_branch_to_target")
    stop = upgrade_section.index("if ! stop_stack_for_upgrade; then")
    transaction = upgrade_section.index("upgrade_transaction_begin")
    stopped_checkpoint = upgrade_section.index("upgrade_transaction_snapshot_stopped_state")
    assert safety_check < transaction < stop < stopped_checkpoint < activation
    assert '"$REPO_ROOT/scripts/viventium/upgrade_check.py"' in upgrade_section
    assert "--no-fetch" in upgrade_section
    assert "--config-file" in upgrade_section
    assert "Upgrade aborted before pull or component mutation" in upgrade_section


def test_allow_dirty_upgrade_requires_skip_pull() -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    upgrade_section = cli_source.rsplit("  upgrade|update)", 1)[1].split("  configure|wizard)", 1)[0]

    assert 'if [[ "$ALLOW_DIRTY" == "1" && "$SKIP_PULL" != "1" ]]; then' in upgrade_section
    assert "--allow-dirty is only safe with --skip-pull" in upgrade_section


def test_upgrade_uses_the_same_configured_remote_for_check_and_pull_and_protects_untracked_work() -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    git_gate = extract_shell_function(cli_source, "ensure_upgradeable_git_state")
    fetch = extract_shell_function(cli_source, "fetch_current_branch_target")
    activation = extract_shell_function(cli_source, "fast_forward_current_branch_to_target")

    upgrade_check_source = (REPO_ROOT / "scripts" / "viventium" / "upgrade_check.py").read_text(encoding="utf-8")
    assert '"--untracked-files=normal"' in upgrade_check_source
    assert "untracked-files=no" not in git_gate
    assert 'local require_remote="${2:-1}"' in git_gate
    assert "current branch has no configured Git remote" in git_gate
    assert 'ensure_upgradeable_git_state "$ALLOW_DIRTY" "$UPGRADE_REQUIRES_REMOTE"' in cli_source
    assert 'config --get "branch.${current_branch}.remote"' in fetch
    assert 'config --get "branch.${current_branch}.merge"' in fetch
    assert 'fetch "$configured_remote" "$merge_ref"' in fetch
    assert 'merge --ff-only "$target_head"' in activation
    assert "fetch origin" not in fetch
    assert "Preserve or remove the untracked/modified parent files" in cli_source
    assert "--skip-pull --allow-dirty" in cli_source


def test_upgrade_rechecks_component_alignment_structurally_after_bootstrap() -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    checked_bootstrap = extract_shell_function(cli_source, "bootstrap_components_upgrade_checked")

    assert 'report.get("component_lock_drift")' in checked_bootstrap
    assert 'report.get("blockers")' in checked_bootstrap
    assert 'report.get("ready_to_upgrade")' in checked_bootstrap
    assert "kept local dirty checkout" not in checked_bootstrap
    assert "Structured component alignment verification failed" in checked_bootstrap


def test_remote_access_failure_does_not_abort_local_launcher_progress(tmp_path: Path) -> None:
    launcher_text = (REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh").read_text(
        encoding="utf-8"
    )
    detect_livekit_node_ip = extract_shell_function(launcher_text, "detect_livekit_node_ip")
    json_state_value = extract_shell_function(launcher_text, "json_state_value")
    clear_remote_exports = extract_shell_function(launcher_text, "clear_remote_call_runtime_exports")
    persist_failure_state = extract_shell_function(launcher_text, "persist_remote_call_failure_state_if_needed")
    mapping_state_support = extract_shell_function(launcher_text, "remote_call_mapping_state_supports_refresh")
    prepare_remote_access = extract_shell_function(launcher_text, "prepare_remote_call_access")
    start_refresh_worker = extract_shell_function(launcher_text, "start_remote_call_mapping_refresh_worker")

    fake_tunnel = tmp_path / "remote_call_tunnel.py"
    fake_tunnel.write_text(
        """#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

state_file = Path(sys.argv[sys.argv.index("--state-file") + 1])
state_file.parent.mkdir(parents=True, exist_ok=True)
state_file.write_text(
    json.dumps(
        {
            "provider": "public_https_edge",
            "last_error": "Router already forwards TCP 80 to 192.0.2.44:50779",
        }
    )
    + "\\n",
    encoding="utf-8",
)
raise SystemExit(1)
""",
        encoding="utf-8",
    )
    fake_tunnel.chmod(0o755)

    state_file = tmp_path / "state" / "public-network.json"
    refresh_pid_file = tmp_path / "state" / "public-network-refresh.pid"
    refresh_log_file = tmp_path / "logs" / "remote-call-upnp-refresh.log"

    script = f"""
set -euo pipefail
PYTHON_BIN={str(sys.executable)!r}
VIVENTIUM_REMOTE_CALL_TUNNEL_SCRIPT={str(fake_tunnel)!r}
VIVENTIUM_PUBLIC_NETWORK_STATE_FILE={str(state_file)!r}
VIVENTIUM_CALL_TUNNEL_LOG_DIR={str((tmp_path / "logs"))!r}
VIVENTIUM_REMOTE_CALL_MODE=public_https_edge
VIVENTIUM_REMOTE_CALL_TUNNEL_AUTO_INSTALL=true
VIVENTIUM_REMOTE_CALL_MAPPING_REFRESH_PID_FILE={str(refresh_pid_file)!r}
VIVENTIUM_REMOTE_CALL_MAPPING_REFRESH_LOG_FILE={str(refresh_log_file)!r}
VIVENTIUM_CORE_DIR={str(tmp_path)!r}
VIVENTIUM_VOICE_ENABLED=false
SKIP_PLAYGROUND=true
SKIP_LIVEKIT=true
VIVENTIUM_PUBLIC_CLIENT_URL=https://stale.example.test
LIVEKIT_NODE_IP=192.0.2.44
export PYTHON_BIN VIVENTIUM_REMOTE_CALL_TUNNEL_SCRIPT VIVENTIUM_PUBLIC_NETWORK_STATE_FILE
export VIVENTIUM_CALL_TUNNEL_LOG_DIR VIVENTIUM_REMOTE_CALL_MODE VIVENTIUM_REMOTE_CALL_TUNNEL_AUTO_INSTALL
export VIVENTIUM_REMOTE_CALL_MAPPING_REFRESH_PID_FILE VIVENTIUM_REMOTE_CALL_MAPPING_REFRESH_LOG_FILE
export VIVENTIUM_CORE_DIR VIVENTIUM_VOICE_ENABLED SKIP_PLAYGROUND SKIP_LIVEKIT
export VIVENTIUM_PUBLIC_CLIENT_URL LIVEKIT_NODE_IP

log_info() {{ printf 'INFO:%s\\n' "$*"; }}
log_warn() {{ printf 'WARN:%s\\n' "$*"; }}
remote_call_mode_enabled() {{ return 0; }}
remote_call_public_edge_mode() {{ return 0; }}
remote_call_mapping_refresh_pid_is_running() {{ return 1; }}
get_client_port() {{ printf '3190\\n'; }}
get_api_port() {{ printf '3180\\n'; }}
get_playground_port() {{ printf '3300\\n'; }}
get_livekit_port() {{ printf '7888\\n'; }}
is_truthy() {{
  case "${{1:-}}" in
    1|true|TRUE|yes|YES)
      return 0
      ;;
  esac
  return 1
}}

    {detect_livekit_node_ip}
    {json_state_value}
    {clear_remote_exports}
    {persist_failure_state}
    {mapping_state_support}
    {prepare_remote_access}
    {start_refresh_worker}

prepare_remote_call_access
LIVEKIT_NODE_IP="${{LIVEKIT_NODE_IP:-$(detect_livekit_node_ip)}}"
mkdir -p "$(dirname "$VIVENTIUM_PUBLIC_NETWORK_STATE_FILE")"
printf '%s\n' '{{"provider":"public_https_edge","last_error":"Router already forwards TCP 80 to 192.0.2.44:50779"}}' > "$VIVENTIUM_PUBLIC_NETWORK_STATE_FILE"
printf 'AFTER_CLIENT=%s\\n' "${{VIVENTIUM_PUBLIC_CLIENT_URL:-}}"
printf 'AFTER_NODE_IP=%s\\n' "${{LIVEKIT_NODE_IP:-}}"
start_remote_call_mapping_refresh_worker
if [[ -f {str(refresh_pid_file)!r} ]]; then
  printf 'REFRESH_PID_EXISTS=yes\\n'
else
  printf 'REFRESH_PID_EXISTS=no\\n'
fi
"""

    completed = subprocess.run(
        ["bash", "-lc", script],
        check=True,
        text=True,
        capture_output=True,
    )

    combined_output = completed.stdout + completed.stderr
    assert "Remote access setup failed; local startup will continue without it" in combined_output
    assert "AFTER_CLIENT=" in completed.stdout
    assert "AFTER_NODE_IP=" in completed.stdout
    assert "AFTER_CLIENT=https://stale.example.test" not in completed.stdout
    assert "AFTER_NODE_IP=192.0.2.44" not in completed.stdout
    assert "AFTER_NODE_IP=" in completed.stdout and "AFTER_NODE_IP=\n" not in completed.stdout
    assert "REFRESH_PID_EXISTS=no" in completed.stdout
    assert state_file.exists()
    assert "Router already forwards TCP 80" in state_file.read_text(encoding="utf-8")


def test_remote_access_failure_replaces_stale_healthy_state_when_helper_dies_early(tmp_path: Path) -> None:
    launcher_text = (REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh").read_text(
        encoding="utf-8"
    )
    detect_livekit_node_ip = extract_shell_function(launcher_text, "detect_livekit_node_ip")
    json_state_value = extract_shell_function(launcher_text, "json_state_value")
    clear_remote_exports = extract_shell_function(launcher_text, "clear_remote_call_runtime_exports")
    persist_failure_state = extract_shell_function(launcher_text, "persist_remote_call_failure_state_if_needed")
    mapping_state_support = extract_shell_function(launcher_text, "remote_call_mapping_state_supports_refresh")
    prepare_remote_access = extract_shell_function(launcher_text, "prepare_remote_call_access")
    start_refresh_worker = extract_shell_function(launcher_text, "start_remote_call_mapping_refresh_worker")

    fake_tunnel = tmp_path / "remote_call_tunnel.py"
    fake_tunnel.write_text(
        """#!/usr/bin/env python3
from __future__ import annotations

import sys

sys.stderr.write("helper crashed before persisting state\\n")
raise SystemExit(1)
""",
        encoding="utf-8",
    )
    fake_tunnel.chmod(0o755)

    state_file = tmp_path / "state" / "public-network.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(
        json.dumps(
            {
                "provider": "public_https_edge",
                "public_client_url": "https://stale.example.test",
                "router": {
                    "mappings": [
                        {
                            "external_port": 80,
                            "internal_port": 3190,
                            "protocol": "TCP",
                        }
                    ]
                },
                "client": {
                    "target": "http://localhost:3190",
                    "public_url": "https://stale.example.test",
                },
                "caddy": {"pid": 99999},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    refresh_pid_file = tmp_path / "state" / "public-network-refresh.pid"
    refresh_log_file = tmp_path / "logs" / "remote-call-upnp-refresh.log"

    script = f"""
set -euo pipefail
PYTHON_BIN={str(sys.executable)!r}
VIVENTIUM_REMOTE_CALL_TUNNEL_SCRIPT={str(fake_tunnel)!r}
VIVENTIUM_PUBLIC_NETWORK_STATE_FILE={str(state_file)!r}
VIVENTIUM_CALL_TUNNEL_LOG_DIR={str((tmp_path / "logs"))!r}
VIVENTIUM_REMOTE_CALL_MODE=public_https_edge
VIVENTIUM_REMOTE_CALL_TUNNEL_AUTO_INSTALL=true
VIVENTIUM_REMOTE_CALL_MAPPING_REFRESH_PID_FILE={str(refresh_pid_file)!r}
VIVENTIUM_REMOTE_CALL_MAPPING_REFRESH_LOG_FILE={str(refresh_log_file)!r}
VIVENTIUM_CORE_DIR={str(tmp_path)!r}
VIVENTIUM_VOICE_ENABLED=false
SKIP_PLAYGROUND=true
SKIP_LIVEKIT=true
VIVENTIUM_PUBLIC_CLIENT_URL=https://stale.example.test
LIVEKIT_NODE_IP=192.0.2.44
export PYTHON_BIN VIVENTIUM_REMOTE_CALL_TUNNEL_SCRIPT VIVENTIUM_PUBLIC_NETWORK_STATE_FILE
export VIVENTIUM_CALL_TUNNEL_LOG_DIR VIVENTIUM_REMOTE_CALL_MODE VIVENTIUM_REMOTE_CALL_TUNNEL_AUTO_INSTALL
export VIVENTIUM_REMOTE_CALL_MAPPING_REFRESH_PID_FILE VIVENTIUM_REMOTE_CALL_MAPPING_REFRESH_LOG_FILE
export VIVENTIUM_CORE_DIR VIVENTIUM_VOICE_ENABLED SKIP_PLAYGROUND SKIP_LIVEKIT
export VIVENTIUM_PUBLIC_CLIENT_URL LIVEKIT_NODE_IP

log_info() {{ printf 'INFO:%s\\n' "$*"; }}
log_warn() {{ printf 'WARN:%s\\n' "$*"; }}
remote_call_mode_enabled() {{ return 0; }}
remote_call_public_edge_mode() {{ return 0; }}
remote_call_mapping_refresh_pid_is_running() {{ return 1; }}
get_client_port() {{ printf '3190\\n'; }}
get_api_port() {{ printf '3180\\n'; }}
get_playground_port() {{ printf '3300\\n'; }}
get_livekit_port() {{ printf '7888\\n'; }}
is_truthy() {{
  case "${{1:-}}" in
    1|true|TRUE|yes|YES)
      return 0
      ;;
  esac
  return 1
}}

{detect_livekit_node_ip}
{json_state_value}
{clear_remote_exports}
{persist_failure_state}
{mapping_state_support}
{prepare_remote_access}
{start_refresh_worker}

prepare_remote_call_access
LIVEKIT_NODE_IP="${{LIVEKIT_NODE_IP:-$(detect_livekit_node_ip)}}"
printf 'AFTER_CLIENT=%s\\n' "${{VIVENTIUM_PUBLIC_CLIENT_URL:-}}"
printf 'AFTER_NODE_IP=%s\\n' "${{LIVEKIT_NODE_IP:-}}"
start_remote_call_mapping_refresh_worker
if [[ -f {str(refresh_pid_file)!r} ]]; then
  printf 'REFRESH_PID_EXISTS=yes\\n'
else
  printf 'REFRESH_PID_EXISTS=no\\n'
fi
"""

    completed = subprocess.run(
        ["bash", "-lc", script],
        check=False,
        text=True,
        capture_output=True,
    )

    combined_output = completed.stdout + completed.stderr
    assert "Remote access setup failed; local startup will continue without it" in combined_output
    assert "helper crashed before persisting state" in combined_output
    assert "AFTER_CLIENT=https://stale.example.test" not in completed.stdout
    assert "AFTER_NODE_IP=192.0.2.44" not in completed.stdout
    assert "AFTER_NODE_IP=" in completed.stdout and "AFTER_NODE_IP=\n" not in completed.stdout
    assert "REFRESH_PID_EXISTS=no" in completed.stdout

    saved_state = json.loads(state_file.read_text(encoding="utf-8"))
    assert saved_state["provider"] == "public_https_edge"
    assert saved_state["last_error"] == "helper crashed before persisting state"
    assert "router" not in saved_state
    assert "client" not in saved_state
    assert "public_client_url" not in saved_state


def test_maybe_install_macos_helper_accepts_explicit_no_launch_override() -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    function_def = extract_shell_function(cli_source, "maybe_install_macos_helper")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                "HEADLESS=0\n"
                "AUTO_START=1\n"
                "VIVENTIUM_SKIP_HELPER_INSTALL=0\n"
                "uname() { printf 'Darwin\\n'; }\n"
                "run_macos_helper_install_command() {\n"
                "  printf 'INSTALL:%s\\n' \"$*\"\n"
                "}\n"
                "write_install_ownership_receipt() { printf 'RECEIPT:%s\\n' \"$1\"; }\n"
                f"{function_def}"
                "maybe_install_macos_helper --no-launch\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "INSTALL:0 --no-launch" in completed.stdout
    assert "RECEIPT:true" in completed.stdout


def test_cli_usage_lists_runtime_recovery_commands() -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    usage_section = cli_source.split("usage() {", 1)[1].split("USAGE", 2)[1]

    assert "update            Alias for upgrade." in usage_section
    assert "status            Show live service health and access URLs." in usage_section
    assert "status-bar        Turn the macOS Viventium status-bar helper on or off." in usage_section
    assert "runtime-checkout  Show or choose the checkout used by helper/start commands." in usage_section
    assert "reset             Factory-reset the local Viventium install state under App Support." in usage_section
    assert "uninstall         Remove the local Viventium install state and helper app." in usage_section


def test_cli_reconciles_default_nightly_routines_on_supported_entrypoints() -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    command_cases = cli_source.rsplit('case "$COMMAND" in', 1)[1]
    install_section = command_cases.split("  install|bootstrap)", 1)[1].split("  upgrade|update)", 1)[0]
    upgrade_section = command_cases.split("  upgrade|update)", 1)[1].split("  configure|wizard)", 1)[0]
    configure_section = command_cases.split("  configure|wizard)", 1)[1].split("  reset)", 1)[0]
    compile_config_section = command_cases.split("  compile-config)", 1)[1].split("  prepare-runtime-exports)", 1)[0]
    start_section = command_cases.split("  start)", 1)[1].split("  stop)", 1)[0]

    assert "apply_default_nightly_routines() {" in cli_source
    assert 'scripts/viventium/default_nightly_routines.py' in cli_source
    assert install_section.count("apply_default_nightly_routines") == 2
    assert install_section.index("apply_default_nightly_routines") < install_section.index("run_preflight apply")
    assert upgrade_section.count("apply_default_nightly_routines") == 2
    assert upgrade_section.index("apply_default_nightly_routines") < upgrade_section.index("run_preflight check")
    assert "run_preflight apply" not in upgrade_section
    assert "apply_default_nightly_routines" in configure_section
    assert "apply_default_nightly_routines" in compile_config_section
    assert "apply_default_nightly_routines\n    compile_config" in start_section


def test_runtime_checkout_use_writes_machine_local_setting_without_helper_refresh(tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    app_support = fake_home / "Library" / "Application Support" / "Viventium"
    runtime_repo = tmp_path / "runtime-repo"
    write_executable(runtime_repo / "bin" / "viventium", "#!/bin/sh\nexit 0\n")
    (runtime_repo / "scripts" / "viventium").mkdir(parents=True)
    (runtime_repo / "scripts" / "viventium" / "common.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (runtime_repo / "viventium_v0_4").mkdir(parents=True)
    (runtime_repo / "viventium_v0_4" / "viventium-librechat-start.sh").write_text(
        "#!/usr/bin/env bash\nexit 0\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            str(REPO_ROOT / "bin" / "viventium"),
            "--app-support-dir",
            str(app_support),
            "runtime-checkout",
            "use",
            str(runtime_repo),
            "--no-helper-refresh",
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
        env={**os.environ, "HOME": str(fake_home)},
    )

    setting = json.loads((app_support / "state" / "active-checkout.json").read_text(encoding="utf-8"))
    assert setting["repoRoot"] == str(runtime_repo.resolve())
    assert setting["allowProtectedFolderAccess"] is False
    assert "Active runtime checkout set" in completed.stdout
    assert "Skipped helper refresh" in completed.stdout
    assert not (app_support / "helper-config.json").exists()


def test_runtime_checkout_clear_removes_machine_local_setting(tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    app_support = fake_home / "Library" / "Application Support" / "Viventium"
    state_file = app_support / "state" / "active-checkout.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text('{"repoRoot": "/tmp/viventium"}\n', encoding="utf-8")

    completed = subprocess.run(
        [
            str(REPO_ROOT / "bin" / "viventium"),
            "--app-support-dir",
            str(app_support),
            "runtime-checkout",
            "clear",
            "--no-helper-refresh",
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
        env={**os.environ, "HOME": str(fake_home)},
    )

    assert not state_file.exists()
    assert "Active runtime checkout cleared" in completed.stdout
    assert "Skipped helper refresh" in completed.stdout


def test_runtime_checkout_reexecs_helper_command_through_active_checkout(tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    app_support = fake_home / "Library" / "Application Support" / "Viventium"
    active_repo = tmp_path / "active-repo"
    marker = tmp_path / "active-bin-args.txt"
    write_executable(
        active_repo / "bin" / "viventium",
        "#!/bin/sh\n"
        "for arg in \"$@\"; do printf 'arg:%s\\n' \"$arg\"; done > \"$VIVENTIUM_REEXEC_MARKER\"\n"
        "printf 'env:%s\\n' \"${VIVENTIUM_COMPONENTS_LOCK_FILE:-}\" >> \"$VIVENTIUM_REEXEC_MARKER\"\n"
        "exit 0\n",
    )
    (active_repo / "scripts" / "viventium").mkdir(parents=True)
    (active_repo / "scripts" / "viventium" / "common.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (active_repo / "viventium_v0_4").mkdir(parents=True)
    (active_repo / "viventium_v0_4" / "viventium-librechat-start.sh").write_text(
        "#!/usr/bin/env bash\nexit 0\n",
        encoding="utf-8",
    )
    state_file = app_support / "state" / "active-checkout.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(json.dumps({"repoRoot": str(active_repo)}) + "\n", encoding="utf-8")

    subprocess.run(
        [
            str(REPO_ROOT / "bin" / "viventium"),
            "--app-support-dir",
            str(app_support),
            "status-bar",
            "status",
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
        env={
            **os.environ,
            "HOME": str(fake_home),
            "VIVENTIUM_COMPONENTS_LOCK_FILE": str(tmp_path / "stale" / "components.lock.json"),
            "VIVENTIUM_REEXEC_MARKER": str(marker),
        },
    )

    lines = marker.read_text(encoding="utf-8").splitlines()
    args = [line.removeprefix("arg:") for line in lines if line.startswith("arg:")]
    env_value = next(line.removeprefix("env:") for line in lines if line.startswith("env:"))
    active_lock_file = str(active_repo / "components.lock.json")
    assert "--app-support-dir" in args
    assert str(app_support) in args
    assert "--config-file" in args
    assert "--runtime-dir" in args
    assert "--lock-file" in args
    assert args[args.index("--lock-file") + 1] == active_lock_file
    assert env_value == active_lock_file
    assert args[-2:] == ["status-bar", "status"]


def test_launch_log_indicates_startup_failure_treats_required_surface_skip_as_terminal(tmp_path: Path) -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    function_def = extract_shell_function(cli_source, "launch_log_indicates_startup_failure")
    launch_log = tmp_path / "helper-start.log"
    launch_log.write_text(
        "[viventium] LibreChat port 3190 still in use (outside scope); skipping startup\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                f"{function_def}"
                f"if launch_log_indicates_startup_failure '{launch_log}'; then\n"
                "  printf 'RESULT=true\\n'\n"
                "else\n"
                "  printf 'RESULT=false\\n'\n"
                "fi\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "RESULT=true" in completed.stdout


def test_launch_log_indicates_startup_failure_treats_playground_pnpm_bootstrap_error_as_terminal(
    tmp_path: Path,
) -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    function_def = extract_shell_function(cli_source, "launch_log_indicates_startup_failure")
    launch_log = tmp_path / "helper-start.log"
    launch_log.write_text(
        "Failed to switch pnpm to v9.15.9. Looks like pnpm CLI is missing.\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                f"{function_def}"
                f"if launch_log_indicates_startup_failure '{launch_log}'; then\n"
                "  printf 'RESULT=true\\n'\n"
                "else\n"
                "  printf 'RESULT=false\\n'\n"
                "fi\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "RESULT=true" in completed.stdout


def test_launch_log_failure_detection_is_scoped_to_the_current_start_attempt(tmp_path: Path) -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    function_def = extract_shell_function(cli_source, "launch_log_indicates_startup_failure")
    launch_log = tmp_path / "helper-start.log"
    launch_log.write_text(
        "npm error Lifecycle script build failed\n",
        encoding="utf-8",
    )
    start_offset = launch_log.stat().st_size
    with launch_log.open("a", encoding="utf-8") as handle:
        handle.write("[viventium] Beginning a new detached start attempt\n")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                f"{function_def}"
                f"if launch_log_indicates_startup_failure '{launch_log}' '{start_offset}'; then\n"
                "  printf 'clean_attempt=failed\\n'\n"
                "else\n"
                "  printf 'clean_attempt=clean\\n'\n"
                "fi\n"
                f"printf '%s\\n' 'npm error Lifecycle script build failed' >> '{launch_log}'\n"
                f"if launch_log_indicates_startup_failure '{launch_log}' '{start_offset}'; then\n"
                "  printf 'failed_attempt=failed\\n'\n"
                "else\n"
                "  printf 'failed_attempt=clean\\n'\n"
                "fi\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "clean_attempt=clean" in completed.stdout
    assert "failed_attempt=failed" in completed.stdout


def test_launch_log_does_not_treat_express_docker_cleanup_skip_as_failure(tmp_path: Path) -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    function_def = extract_shell_function(cli_source, "launch_log_indicates_startup_failure")
    launch_log = tmp_path / "helper-start.log"
    launch_log.write_text(
        "[viventium] Docker is not running; skipping container cleanup\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                f"{function_def}"
                f"if launch_log_indicates_startup_failure '{launch_log}'; then\n"
                "  printf 'RESULT=failed\\n'\n"
                "else\n"
                "  printf 'RESULT=clean\\n'\n"
                "fi\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.stdout.strip() == "RESULT=clean"


def test_launch_log_allows_dependency_install_retry_before_terminal_failure(tmp_path: Path) -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    function_def = extract_shell_function(cli_source, "launch_log_indicates_startup_failure")
    launch_log = tmp_path / "helper-start.log"
    launch_log.write_text(
        "[viventium] LibreChat dependency install failed; cleaning dependency trees and retrying once...\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                f"{function_def}"
                f"if launch_log_indicates_startup_failure '{launch_log}'; then\n"
                "  printf 'retry=failed\\n'\n"
                "else\n"
                "  printf 'retry=clean\\n'\n"
                "fi\n"
                f"printf '%s\\n' '[viventium] LibreChat dependency check failed: @google/genai not found' >> '{launch_log}'\n"
                f"if launch_log_indicates_startup_failure '{launch_log}'; then\n"
                "  printf 'terminal=failed\\n'\n"
                "else\n"
                "  printf 'terminal=clean\\n'\n"
                "fi\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "retry=clean" in completed.stdout
    assert "terminal=failed" in completed.stdout


def test_cli_usage_documents_status_bar_and_shell_init_commands() -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")

    assert "run_status_bar_command() {" in cli_source
    assert 'echo "Viventium status-bar helper is enabled."' in cli_source
    assert 'echo "Viventium status-bar helper is hidden."' in cli_source
    assert 'echo "Run bin/viventium status-bar on to bring it back."' in cli_source
    assert "bin/viventium status-bar on" in cli_source
    assert "bin/viventium status-bar off" in cli_source
    assert "runtime_checkout_command() {" in cli_source
    assert "maybe_reexec_active_runtime_checkout() {" in cli_source
    assert "Using active runtime checkout:" in cli_source


def test_install_script_defaults_to_main_branch() -> None:
    install_source = (REPO_ROOT / "install.sh").read_text(encoding="utf-8")

    assert 'BRANCH="${VIVENTIUM_REPO_BRANCH:-main}"' in install_source
    assert "main-viventium" not in install_source


def test_reattach_stdin_from_tty_if_available_restores_terminal_input() -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    function_def = extract_shell_function(cli_source, "reattach_stdin_from_tty_if_available")

    returncode, output = run_bash_on_pty(
        (
            "set -euo pipefail\n"
            f"{function_def}"
            "exec 0< <(printf 'bootstrap-pipe\\n')\n"
            "printf 'before=%s\\n' \"$([[ -t 0 ]] && printf 'tty' || printf 'pipe')\"\n"
            "reattach_stdin_from_tty_if_available || true\n"
            "printf 'after=%s\\n' \"$([[ -t 0 ]] && printf 'tty' || printf 'pipe')\"\n"
        ),
        cwd=REPO_ROOT,
    )

    assert returncode == 0
    assert "before=pipe" in output
    assert "after=tty" in output


def test_install_restores_terminal_input_for_wizard_and_preflight_when_stdin_is_piped(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / "bin").mkdir(parents=True, exist_ok=True)

    copy_cli_fixture(repo_root)

    common_sh = """#!/usr/bin/env bash
set -euo pipefail

ensure_brew_paths_on_path() {
  :
}

ensure_app_support_layout() {
  local dir="$1"
  mkdir -p "$dir/runtime" "$dir/state" "$dir/logs" "$dir/snapshots"
}

resolve_repo_python() {
  printf 'python3\\n'
}

ensure_python_requirements_file() {
  printf '%s\\n' "$1"
}
"""
    write_executable(repo_root / "scripts" / "viventium" / "common.sh", common_sh)

    wizard_py = """#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--output", required=True)
args = parser.parse_args()

output_path = Path(args.output)
output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text("version: 1\\n", encoding="utf-8")
print(f"wizard-stdin-tty={int(sys.stdin.isatty())}")
"""
    write_executable(repo_root / "scripts" / "viventium" / "wizard.py", wizard_py)

    preflight_py = """#!/usr/bin/env python3
from __future__ import annotations

import sys

print(f"preflight-stdin-tty={int(sys.stdin.isatty())}")
"""
    write_executable(repo_root / "scripts" / "viventium" / "preflight.py", preflight_py)

    write_executable(
        repo_root / "scripts" / "viventium" / "bootstrap_components.py",
        "#!/usr/bin/env python3\nprint('bootstrap-components-ok')\n",
    )
    write_executable(
        repo_root / "scripts" / "viventium" / "config_compiler.py",
        "#!/usr/bin/env python3\nprint('config-compiler-ok')\n",
    )
    write_executable(
        repo_root / "scripts" / "viventium" / "install_summary.py",
        "#!/usr/bin/env python3\nprint('install-summary-ok')\n",
    )
    write_executable(repo_root / "scripts" / "viventium" / "doctor.sh", "#!/usr/bin/env bash\nexit 0\n")
    write_executable(
        repo_root / "scripts" / "viventium" / "install_macos_helper.sh",
        "#!/usr/bin/env bash\nexit 0\n",
    )

    app_support_dir = tmp_path / "app-support"
    returncode, output = run_bash_on_pty(
        (
            "set -euo pipefail\n"
            "exec 0< <(printf '')\n"
            f"VIVENTIUM_APP_SUPPORT_DIR='{app_support_dir}' '{repo_root / 'bin' / 'viventium'}' install --no-start\n"
        ),
        cwd=repo_root,
    )

    assert returncode == 0
    assert "wizard-stdin-tty=1" in output
    assert "preflight-stdin-tty=1" in output


def test_install_wait_log_activity_summary_reports_current_build_phase(tmp_path: Path) -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    function_def = extract_shell_function(cli_source, "install_wait_log_activity_summary")
    launch_log = tmp_path / "helper-start.log"
    launch_log.write_text(
        "\n".join(
            [
                "[viventium] Installing LibreChat dependencies (missing node_modules)...",
                "[viventium] Building LibreChat server packages...",
                "[viventium] Building LibreChat client bundle...",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                f"{function_def}"
                f"install_wait_log_activity_summary '{launch_log}'\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.stdout.strip() == "Building LibreChat web app"


def test_detached_launch_process_group_running_detects_active_group(tmp_path: Path) -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    pgid_file_def = extract_shell_function(cli_source, "detached_launch_process_group_file")
    read_pgid_def = extract_shell_function(cli_source, "read_detached_launch_process_group")
    group_running_def = extract_shell_function(cli_source, "detached_launch_process_group_running")

    fake_bin = tmp_path / "bin"
    write_executable(
        fake_bin / "ps",
        """#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "-Ao" ]]; then
  printf '10078 94626 S\\n'
  printf '10085 94626 S\\n'
  exit 0
fi
exit 1
""",
    )

    app_support_dir = tmp_path / "app-support"
    pgid_file = app_support_dir / "state" / "runtime" / "isolated" / "detached-launch.pgid"
    pgid_file.parent.mkdir(parents=True, exist_ok=True)
    pgid_file.write_text("94626\n", encoding="utf-8")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                f"PATH='{fake_bin}':\"$PATH\"\n"
                f"APP_SUPPORT_DIR='{app_support_dir}'\n"
                "VIVENTIUM_RUNTIME_PROFILE=isolated\n"
                f"{pgid_file_def}"
                f"{read_pgid_def}"
                f"{group_running_def}"
                "detached_launch_process_group_running\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0


def test_detached_start_failed_early_prioritizes_explicit_log_failure_over_live_sidecars() -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    function_def = extract_shell_function(cli_source, "detached_start_failed_early")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                f"{function_def}"
                "DETACHED_START_PID=12345\n"
                "pid_is_running() { return 1; }\n"
                "detached_launch_process_group_running() { return 0; }\n"
                "is_stack_running() { return 1; }\n"
                "user_surface_healthy() { return 1; }\n"
                "launch_log_indicates_startup_failure() { return 0; }\n"
                "if detached_start_failed_early /tmp/missing.log; then\n"
                "  printf 'result=failed\\n'\n"
                "else\n"
                "  printf 'result=waiting\\n'\n"
                "fi\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.stdout.strip() == "result=failed"


def test_launch_stack_detached_skips_restart_while_detached_group_is_alive() -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    function_def = extract_shell_function(cli_source, "launch_stack_detached")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                f"{function_def}"
                "APP_SUPPORT_DIR=/tmp/app-support\n"
                "CONFIG_FILE=/tmp/config.yaml\n"
                "touch \"$CONFIG_FILE\"\n"
                "ensure_app_support_layout() { :; }\n"
                "user_surface_healthy() { return 1; }\n"
                "detached_launch_process_group_running() { return 0; }\n"
                "is_stack_running() { printf 'stack-check\\n' >&2; return 0; }\n"
                "stop_stack_for_upgrade() { printf 'restarted\\n'; }\n"
                "if launch_stack_detached; then\n"
                "  printf 'ok\\n'\n"
                "fi\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.stdout.splitlines() == [
        "Viventium is already starting.",
        "ok",
    ]
    assert "stack-check" not in completed.stderr


def test_launch_stack_detached_waits_when_sidecar_repair_is_already_starting(
    tmp_path: Path,
) -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    function_def = extract_shell_function(cli_source, "launch_stack_detached")
    fake_python = tmp_path / "python"
    write_executable(fake_python, "#!/bin/sh\nprintf '4242\\n'\n")
    app_support = tmp_path / "app-support"
    config = tmp_path / "config.yaml"
    runtime = tmp_path / "runtime"
    config.write_text("version: 1\n", encoding="utf-8")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                f"{function_def}"
                f"PYTHON_BIN={fake_python}\n"
                f"APP_SUPPORT_DIR={app_support}\n"
                f"CONFIG_FILE={config}\n"
                f"RUNTIME_DIR={runtime}\n"
                "LOCK_FILE=/tmp/viventium-test.lock\n"
                f"REPO_ROOT={REPO_ROOT}\n"
                "ensure_app_support_layout() { mkdir -p \"$1/logs\"; }\n"
                "user_surface_healthy() { return 0; }\n"
                "runtime_optional_surfaces_healthy() { return 1; }\n"
                "detached_launch_process_group_running() { return 0; }\n"
                "is_stack_running() { printf 'stack-check\\n' >&2; return 0; }\n"
                "stop_stack_for_upgrade() { printf 'unexpected-stop\\n'; return 0; }\n"
                "if launch_stack_detached; then\n"
                "  printf 'ok\\n'\n"
                "fi\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.stdout.splitlines() == [
        "Viventium is already starting.",
        "ok",
    ]
    assert "stack-check" not in completed.stderr


def test_launch_stack_detached_starts_repair_when_core_healthy_and_sidecars_unhealthy(
    tmp_path: Path,
) -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    function_def = extract_shell_function(cli_source, "launch_stack_detached")
    fake_python = tmp_path / "python"
    write_executable(fake_python, "#!/bin/sh\nprintf '4242\\n'\n")
    app_support = tmp_path / "app-support"
    config = tmp_path / "config.yaml"
    runtime = tmp_path / "runtime"
    config.write_text("version: 1\n", encoding="utf-8")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                f"{function_def}"
                f"PYTHON_BIN={fake_python}\n"
                f"APP_SUPPORT_DIR={app_support}\n"
                f"CONFIG_FILE={config}\n"
                f"RUNTIME_DIR={runtime}\n"
                "LOCK_FILE=/tmp/viventium-test.lock\n"
                f"REPO_ROOT={REPO_ROOT}\n"
                "ensure_app_support_layout() { mkdir -p \"$1/logs\"; }\n"
                "user_surface_healthy() { return 0; }\n"
                "runtime_optional_surfaces_healthy() { return 1; }\n"
                "detached_launch_process_group_running() { return 1; }\n"
                "is_stack_running() { printf 'stack-check\\n' >&2; return 0; }\n"
                "stop_stack_for_upgrade() { printf 'unexpected-stop\\n'; return 0; }\n"
                "if launch_stack_detached; then\n"
                "  printf 'ok\\n'\n"
                "fi\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.stdout.splitlines() == [
        "Viventium core surfaces are running, but enabled sidecars need startup. Repairing...",
        "Launched Viventium in the background (pid 4242).",
        "ok",
    ]
    assert "stack-check" not in completed.stderr
    assert "restarted" not in completed.stdout


def test_install_wait_current_tagline_types_text_quickly() -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    pick_def = extract_shell_function(cli_source, "install_wait_pick_next_tagline")
    current_def = extract_shell_function(cli_source, "install_wait_current_tagline")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                'INSTALL_WAIT_TAGLINES=("abcdefghij")\n'
                "INSTALL_WAIT_TAGLINE_INDEX=-1\n"
                'INSTALL_WAIT_TAGLINE=""\n'
                "INSTALL_WAIT_TAGLINE_STARTED_TICK=0\n"
                "VIVENTIUM_INSTALL_TAGLINE_CHARS_PER_TICK=3\n"
                "VIVENTIUM_INSTALL_TAGLINE_HOLD_TICKS=2\n"
                f"{pick_def}"
                f"{current_def}"
                "install_wait_current_tagline 0\n"
                "install_wait_current_tagline 1\n"
                "install_wait_current_tagline 2\n"
                "install_wait_current_tagline 3\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.stdout.splitlines() == [
        "abc_",
        "abcdef_",
        "abcdefghi_",
        "abcdefghij",
    ]


def test_install_wait_current_tagline_can_be_disabled() -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    pick_def = extract_shell_function(cli_source, "install_wait_pick_next_tagline")
    current_def = extract_shell_function(cli_source, "install_wait_current_tagline")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                'INSTALL_WAIT_TAGLINES=("abcdefghij")\n'
                "INSTALL_WAIT_TAGLINE_INDEX=-1\n"
                'INSTALL_WAIT_TAGLINE=""\n'
                "INSTALL_WAIT_TAGLINE_STARTED_TICK=0\n"
                "VIVENTIUM_INSTALL_FUN_TAGLINES=0\n"
                f"{pick_def}"
                f"{current_def}"
                "install_wait_current_tagline 0\n"
                "printf 'INDEX=%s\\n' \"$INSTALL_WAIT_TAGLINE_INDEX\"\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.stdout.splitlines() == ["INDEX=-1"]


def test_install_wait_pick_next_tagline_never_repeats_back_to_back() -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    function_def = extract_shell_function(cli_source, "install_wait_pick_next_tagline")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                'INSTALL_WAIT_TAGLINES=("alpha" "beta")\n'
                "INSTALL_WAIT_TAGLINE_INDEX=-1\n"
                'INSTALL_WAIT_TAGLINE=""\n'
                "INSTALL_WAIT_TAGLINE_STARTED_TICK=0\n"
                f"{function_def}"
                "for tick in 0 1 2 3 4 5 6 7; do\n"
                "  previous=\"$INSTALL_WAIT_TAGLINE_INDEX\"\n"
                "  install_wait_pick_next_tagline \"$tick\"\n"
                "  if [[ \"$previous\" == \"$INSTALL_WAIT_TAGLINE_INDEX\" ]]; then\n"
                "    printf 'repeat\\n'\n"
                "    exit 1\n"
                "  fi\n"
                "done\n"
                "printf 'ok\\n'\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.stdout.strip() == "ok"


def test_render_install_wait_progress_prints_progress_line_and_tagline() -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    function_def = extract_shell_function(cli_source, "render_install_wait_progress")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                "INSTALL_WAIT_PROGRESS_ACTIVE=0\n"
                "INSTALL_WAIT_PROGRESS_LINES=0\n"
                "INSTALL_WAIT_INLINE_TICK=7\n"
                'INSTALL_WAIT_CURRENT_STEP="Building LibreChat web app"\n'
                "install_wait_inline_enabled() { return 0; }\n"
                "install_wait_spinner_frame() { printf '>\\n'; }\n"
                "install_wait_current_tagline() { printf -v \"$2\" '%s' 'Extracting pure epicness...'; }\n"
                "clear_install_wait_progress_frame() { :; }\n"
                "format_install_wait_elapsed() { printf '0m07s\\n'; }\n"
                f"{function_def}"
                "render_install_wait_progress 7 'Web :3080' '/tmp/missing'\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "\x1b[38;5;208m" in completed.stdout
    rendered = strip_ansi(completed.stdout)

    assert "[>] Starting Viventium 0m07s | Building LibreChat web app | Waiting for: Web :3080" in rendered
    assert "While you wait: Extracting pure epicness..." in rendered


def test_install_wait_spinner_frame_uses_single_width_backslash() -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    function_def = extract_shell_function(cli_source, "install_wait_spinner_frame")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                f"{function_def}"
                "install_wait_spinner_frame 1 | awk '{ print length($0) \":\" $0 }'\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.stdout.strip() == "1:\\"


def init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "Codex"], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "config", "user.email", "codex@example.com"],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(["git", "add", "."], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "checkout", "-b", "codex/test-cli"], cwd=path, check=True, capture_output=True, text=True)


def build_transactional_upgrade_failure_fixture(tmp_path: Path, failure_stage: str) -> tuple[Path, Path]:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True)
    (repo_root / "bin").mkdir()
    copy_cli_fixture(repo_root)
    write_executable(
        repo_root / "scripts" / "viventium" / "common.sh",
        """#!/usr/bin/env bash
set -euo pipefail
prepend_path_if_dir() {
  local candidate="$1"
  if [[ -d "$candidate" && ":${PATH}:" != *":${candidate}:"* ]]; then PATH="${candidate}:${PATH}"; fi
}
ensure_brew_paths_on_path() { prepend_path_if_dir "${TEST_ROOT}/fake-bin"; export PATH; }
ensure_app_support_layout() { mkdir -p "$1/runtime" "$1/state" "$1/logs"; }
viventium_port_listener_active() { [[ ! -f "${TEST_ROOT}/stop-called" ]]; }
python_has_module() { return 0; }
resolve_repo_python() { printf '%s\n' "${TEST_PYTHON}"; }
ensure_python_module() { return 0; }
ensure_python_requirements_file() { printf '%s\n' "${TEST_PYTHON}"; }
""",
    )
    preflight_status = 17 if failure_stage == "preflight" else 0
    write_executable(
        repo_root / "scripts" / "viventium" / "preflight.py",
        f"#!/usr/bin/env python3\nraise SystemExit({preflight_status})\n",
    )
    bootstrap_status = 18 if failure_stage == "bootstrap" else 0
    write_executable(
        repo_root / "scripts" / "viventium" / "bootstrap_components.py",
        f"#!/usr/bin/env python3\nraise SystemExit({bootstrap_status})\n",
    )
    if failure_stage == "compile":
        compiler = "#!/usr/bin/env python3\nraise SystemExit(19)\n"
    else:
        compiler = """#!/usr/bin/env python3
import argparse
from pathlib import Path
parser = argparse.ArgumentParser()
parser.add_argument("--config", required=True)
parser.add_argument("--output-dir", required=True)
args = parser.parse_args()
out = Path(args.output_dir)
out.mkdir(parents=True, exist_ok=True)
(out / "runtime.env").write_text(
    "VIVENTIUM_RUNTIME_PROFILE=isolated\\n"
    "VIVENTIUM_INSTALL_EXPERIENCE=express\\n"
    "VIVENTIUM_LC_API_PORT=3180\\n"
    "VIVENTIUM_LC_FRONTEND_PORT=3190\\n"
    "VIVENTIUM_PLAYGROUND_PORT=3300\\n"
    "CANDIDATE=1\\n",
    encoding="utf-8",
)
(out / "runtime.local.env").write_text("", encoding="utf-8")
(out / "librechat.yaml").write_text("version: 1\\n", encoding="utf-8")
"""
    write_executable(repo_root / "scripts" / "viventium" / "config_compiler.py", compiler)
    doctor_status = 20 if failure_stage == "doctor" else 0
    write_executable(
        repo_root / "scripts" / "viventium" / "doctor.sh",
        f"#!/usr/bin/env bash\nset -euo pipefail\nexit {doctor_status}\n",
    )
    write_executable(
        repo_root / "scripts" / "viventium" / "install_macos_helper.sh",
        "#!/usr/bin/env bash\nset -euo pipefail\nexit 0\n",
    )
    write_executable(
        repo_root / "scripts" / "viventium" / "native_stack.sh",
        "#!/usr/bin/env bash\nset -euo pipefail\nexit 0\n",
    )
    write_executable(
        repo_root / "viventium_v0_4" / "viventium-librechat-start.sh",
        """#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "--stop" ]]; then
  touch "${TEST_ROOT}/stop-called"
else
  count_file="${TEST_ROOT}/start-count"
  count=0
  [[ -f "$count_file" ]] && count="$(cat "$count_file")"
  printf '%s\n' "$((count + 1))" > "$count_file"
fi
""",
    )
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    write_executable(fake_bin / "lsof", "#!/usr/bin/env bash\nexit 1\n")
    write_executable(fake_bin / "pgrep", "#!/usr/bin/env bash\nexit 1\n")
    write_executable(
        fake_bin / "curl",
        """#!/usr/bin/env bash
set -euo pipefail
runtime="${TEST_ROOT}/app-support/runtime/runtime.env"
active="${TEST_ROOT}/app-support/state/upgrade-transaction-active.json"
if [[ ! -e "$active" ]] && grep -q '^CANDIDATE=0$' "$runtime" 2>/dev/null; then
  printf '200'
  exit 0
fi
printf '000'
exit 1
""",
    )
    support = tmp_path / "app-support"
    (support / "runtime").mkdir(parents=True)
    (support / "state" / "runtime" / "isolated").mkdir(parents=True)
    (support / "config.yaml").write_text(
        "version: 1\ninstall:\n  mode: native\n  experience: express\nvoice:\n  mode: disabled\n",
        encoding="utf-8",
    )
    (support / "runtime" / "runtime.env").write_text(
        "VIVENTIUM_RUNTIME_PROFILE=isolated\n"
        "VIVENTIUM_INSTALL_EXPERIENCE=express\n"
        "VIVENTIUM_LC_API_PORT=3180\n"
        "VIVENTIUM_LC_FRONTEND_PORT=3190\n"
        "VIVENTIUM_PLAYGROUND_PORT=3300\n"
        "CANDIDATE=0\n",
        encoding="utf-8",
    )
    (support / "runtime" / "runtime.local.env").write_text("", encoding="utf-8")
    (support / "state" / "runtime" / "isolated" / "database.bin").write_bytes(b"old-database")
    init_git_repo(repo_root)
    return repo_root, support


@pytest.mark.parametrize("failure_stage", ["preflight", "bootstrap", "compile", "doctor", "restart"])
def test_upgrade_phase_failure_restores_exact_checkpoint_and_prior_running_state(
    tmp_path: Path,
    failure_stage: str,
) -> None:
    repo_root, support = build_transactional_upgrade_failure_fixture(tmp_path, failure_stage)
    old_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_root, check=True, capture_output=True, text=True
    ).stdout.strip()
    old_config = (support / "config.yaml").read_bytes()
    old_runtime = (support / "runtime" / "runtime.env").read_bytes()
    old_database = (support / "state" / "runtime" / "isolated" / "database.bin").read_bytes()

    completed = subprocess.run(
        [
            str(repo_root / "bin" / "viventium"),
            "--app-support-dir",
            str(support),
            "upgrade",
            "--skip-pull",
            "--restart",
        ],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "TEST_ROOT": str(tmp_path),
            "TEST_PYTHON": sys.executable,
            "VIVENTIUM_INSTALL_START_HEALTH_TIMEOUT_SECONDS": "1",
            "VIVENTIUM_INSTALL_START_POLL_SECONDS": "0.1",
        },
    )

    assert completed.returncode != 0
    assert "previous verified Viventium runtime and running state were restored" in completed.stderr
    assert (support / "config.yaml").read_bytes() == old_config
    assert (support / "runtime" / "runtime.env").read_bytes() == old_runtime
    assert (support / "state" / "runtime" / "isolated" / "database.bin").read_bytes() == old_database
    assert not (support / "state" / "upgrade-transaction-active.json").exists()
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_root, check=True, capture_output=True, text=True
    ).stdout.strip()
    assert head == old_head


def test_upgrade_pull_divergence_rolls_back_without_mixed_state(tmp_path: Path) -> None:
    repo_root, support = build_transactional_upgrade_failure_fixture(tmp_path, "none")
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "clone", "--bare", str(repo_root), str(remote)], check=True, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=repo_root, check=True)
    subprocess.run(
        ["git", "push", "--set-upstream", "origin", "codex/test-cli"],
        cwd=repo_root,
        check=True,
        capture_output=True,
    )
    remote_work = tmp_path / "remote-work"
    subprocess.run(["git", "clone", str(remote), str(remote_work)], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "QA"], cwd=remote_work, check=True)
    subprocess.run(["git", "config", "user.email", "qa@example.com"], cwd=remote_work, check=True)
    (remote_work / "remote.txt").write_text("remote candidate\n", encoding="utf-8")
    subprocess.run(["git", "add", "remote.txt"], cwd=remote_work, check=True)
    subprocess.run(["git", "commit", "-m", "remote candidate"], cwd=remote_work, check=True, capture_output=True)
    subprocess.run(["git", "push"], cwd=remote_work, check=True, capture_output=True)
    (repo_root / "local.txt").write_text("local retained work\n", encoding="utf-8")
    subprocess.run(["git", "add", "local.txt"], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-m", "local retained commit"], cwd=repo_root, check=True, capture_output=True)
    old_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_root, check=True, capture_output=True, text=True
    ).stdout.strip()
    old_runtime = (support / "runtime" / "runtime.env").read_bytes()

    completed = subprocess.run(
        [
            str(repo_root / "bin" / "viventium"),
            "--app-support-dir",
            str(support),
            "upgrade",
            "--restart",
        ],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "TEST_ROOT": str(tmp_path), "TEST_PYTHON": sys.executable},
    )

    assert completed.returncode != 0
    assert "previous verified Viventium runtime and running state were restored" in completed.stderr
    assert (repo_root / "local.txt").read_text(encoding="utf-8") == "local retained work\n"
    assert (support / "runtime" / "runtime.env").read_bytes() == old_runtime
    assert subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_root, check=True, capture_output=True, text=True
    ).stdout.strip() == old_head


def test_next_upgrade_recovers_interrupted_transaction_before_new_mutation(tmp_path: Path) -> None:
    repo_root, support = build_transactional_upgrade_failure_fixture(tmp_path, "none")
    transaction_script = repo_root / "scripts" / "viventium" / "upgrade_transaction.py"
    env = {**os.environ, "TEST_ROOT": str(tmp_path), "TEST_PYTHON": sys.executable}
    started = subprocess.run(
        [
            sys.executable,
            str(transaction_script),
            "begin",
            "--repo-root",
            str(repo_root),
            "--app-support-dir",
            str(support),
            "--config-file",
            str(support / "config.yaml"),
            "--runtime-dir",
            str(support / "runtime"),
            "--lock-file",
            str(repo_root / "components.lock.json"),
            "--was-running",
            "true",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    transaction = Path(json.loads(started.stdout)["transaction_path"])
    (tmp_path / "stop-called").touch()
    subprocess.run(
        [sys.executable, str(transaction_script), "snapshot-stopped-state", "--transaction", str(transaction)],
        check=True,
        capture_output=True,
        env=env,
    )
    old_config = (support / "config.yaml").read_bytes()
    old_runtime = (support / "runtime" / "runtime.env").read_bytes()
    old_database = (support / "state" / "runtime" / "isolated" / "database.bin").read_bytes()
    (support / "config.yaml").write_text("candidate interrupted\n", encoding="utf-8")
    (support / "runtime" / "runtime.env").write_text("CANDIDATE=1\n", encoding="utf-8")
    (support / "state" / "runtime" / "isolated" / "database.bin").write_bytes(b"interrupted")
    subprocess.run(
        [
            sys.executable,
            str(transaction_script),
            "checkpoint",
            "--transaction",
            str(transaction),
            "--stage",
            "candidate_activated",
        ],
        check=True,
        capture_output=True,
        env=env,
    )

    recovered = subprocess.run(
        [
            str(repo_root / "bin" / "viventium"),
            "--app-support-dir",
            str(support),
            "upgrade",
            "--skip-pull",
            "--restart",
        ],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert recovered.returncode == 4, recovered.stderr
    assert "Interrupted upgrade rolled back successfully" in recovered.stderr
    assert (support / "config.yaml").read_bytes() == old_config
    assert (support / "runtime" / "runtime.env").read_bytes() == old_runtime
    assert (support / "state" / "runtime" / "isolated" / "database.bin").read_bytes() == old_database
    assert not (support / "state" / "upgrade-transaction-active.json").exists()


def test_upgrade_refreshes_python_after_preflight_install(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / "bin").mkdir(parents=True, exist_ok=True)

    copy_cli_fixture(repo_root)

    common_sh = """#!/usr/bin/env bash
set -euo pipefail

prepend_path_if_dir() {
  local candidate="$1"
  if [[ -d "$candidate" && ":${PATH}:" != *":${candidate}:"* ]]; then
    PATH="${candidate}:${PATH}"
  fi
}

ensure_brew_paths_on_path() {
  prepend_path_if_dir "${TEST_ROOT}/fakebrew/bin"
  export PATH
}

ensure_app_support_layout() {
  local dir="$1"
  mkdir -p "$dir/runtime" "$dir/state"
}

python_has_module() {
  return 0
}

resolve_repo_python() {
  if [[ -x "${TEST_ROOT}/fakebrew/bin/python3.12" ]]; then
    printf '%s\\n' "${TEST_ROOT}/fakebrew/bin/python3.12"
  elif command -v python3.12 >/dev/null 2>&1; then
    printf 'python3.12\\n'
  else
    printf 'python3\\n'
  fi
}

ensure_python_module() {
  return 0
}
"""
    write_executable(repo_root / "scripts" / "viventium" / "common.sh", common_sh)

    preflight_py = """#!/usr/bin/env python3
from __future__ import annotations

import os
import shlex
import sys
from pathlib import Path

fake_python = Path(os.environ["TEST_ROOT"]) / "fakebrew" / "bin" / "python3.12"
fake_python.parent.mkdir(parents=True, exist_ok=True)
fake_python.write_text(
    "#!/bin/sh\\n"
    "export VIVENTIUM_SELECTED_PYTHON=python3.12\\n"
    f"exec {shlex.quote(sys.executable)} \\\"$@\\\"\\n",
    encoding="utf-8",
)
fake_python.chmod(0o755)
raise SystemExit(0)
"""
    write_executable(repo_root / "scripts" / "viventium" / "preflight.py", preflight_py)

    bootstrap_py = """#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path

Path(os.environ["TEST_ROOT"], "selected-python.txt").write_text(
    os.environ.get("VIVENTIUM_SELECTED_PYTHON", "missing"),
    encoding="utf-8",
)
"""
    write_executable(repo_root / "scripts" / "viventium" / "bootstrap_components.py", bootstrap_py)

    config_compiler_py = """#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--config", required=True)
parser.add_argument("--output-dir", required=True)
args = parser.parse_args()
out = Path(args.output_dir)
out.mkdir(parents=True, exist_ok=True)
(out / "runtime.env").write_text("VIVENTIUM_CALL_SESSION_SECRET=test\\n", encoding="utf-8")
(out / "runtime.local.env").write_text("", encoding="utf-8")
(out / "librechat.yaml").write_text("version: 1\\n", encoding="utf-8")
"""
    write_executable(repo_root / "scripts" / "viventium" / "config_compiler.py", config_compiler_py)

    doctor_sh = """#!/usr/bin/env bash
set -euo pipefail
exit 0
"""
    write_executable(repo_root / "scripts" / "viventium" / "doctor.sh", doctor_sh)
    helper_install_sh = """#!/usr/bin/env bash
set -euo pipefail
exit 0
"""
    write_executable(repo_root / "scripts" / "viventium" / "install_macos_helper.sh", helper_install_sh)

    start_sh = """#!/usr/bin/env bash
set -euo pipefail
exit 0
"""
    write_executable(repo_root / "viventium_v0_4" / "viventium-librechat-start.sh", start_sh)

    fake_lsof = tmp_path / "fakebrew" / "bin" / "lsof"
    fake_lsof.parent.mkdir(parents=True, exist_ok=True)
    fake_lsof.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
exit 1
""",
        encoding="utf-8",
    )
    fake_lsof.chmod(0o755)

    config_path = tmp_path / "app-support" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("version: 1\ninstall:\n  mode: native\nvoice:\n  mode: local\n", encoding="utf-8")

    init_git_repo(repo_root)

    completed = subprocess.run(
        [
            str(repo_root / "bin" / "viventium"),
            "--app-support-dir",
            str(config_path.parent),
            "upgrade",
            "--skip-pull",
            "--allow-dirty",
        ],
        cwd=repo_root,
        check=False,
        text=True,
        capture_output=True,
        env={
            **dict(os.environ),
            "TEST_ROOT": str(tmp_path),
            "VIVENTIUM_AUTO_APPROVE_PREREQS": "true",
        },
    )

    assert "Upgrade complete. Next: bin/viventium start" in completed.stdout
    assert completed.returncode == 0, completed.stderr
    assert (tmp_path / "selected-python.txt").read_text(encoding="utf-8") == "python3.12"


def test_upgrade_restart_stops_running_stack_before_bootstrap(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / "bin").mkdir(parents=True, exist_ok=True)

    copy_cli_fixture(repo_root)

    common_sh = """#!/usr/bin/env bash
set -euo pipefail

prepend_path_if_dir() {
  local candidate="$1"
  if [[ -d "$candidate" && ":${PATH}:" != *":${candidate}:"* ]]; then
    PATH="${candidate}:${PATH}"
  fi
}

ensure_brew_paths_on_path() {
  prepend_path_if_dir "${TEST_ROOT}/fakebrew/bin"
  export PATH
}

ensure_app_support_layout() {
  local dir="$1"
  mkdir -p "$dir/runtime" "$dir/state"
}

viventium_port_listener_active() { return 0; }

python_has_module() { return 0; }
resolve_repo_python() { printf '%s\\n' "${TEST_PYTHON:-python3}"; }
ensure_python_module() { return 0; }
ensure_python_requirements_file() { printf '%s\\n' "${TEST_PYTHON:-$1}"; }
"""
    write_executable(repo_root / "scripts" / "viventium" / "common.sh", common_sh)

    preflight_py = """#!/usr/bin/env python3
raise SystemExit(0)
"""
    write_executable(repo_root / "scripts" / "viventium" / "preflight.py", preflight_py)

    bootstrap_py = """#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path

test_root = Path(os.environ["TEST_ROOT"])
marker = test_root / "stop-called"
(test_root / "bootstrap-observed-stop.txt").write_text(
    "yes" if marker.exists() else "no",
    encoding="utf-8",
)
"""
    write_executable(repo_root / "scripts" / "viventium" / "bootstrap_components.py", bootstrap_py)

    config_compiler_py = """#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--config", required=True)
parser.add_argument("--output-dir", required=True)
args = parser.parse_args()
out = Path(args.output_dir)
out.mkdir(parents=True, exist_ok=True)
(out / "runtime.env").write_text(
    "VIVENTIUM_CALL_SESSION_SECRET=test\\n"
    "VIVENTIUM_INSTALL_EXPERIENCE=express\\n"
    "VIVENTIUM_LC_API_PORT=3180\\n"
    "VIVENTIUM_LC_FRONTEND_PORT=3190\\n"
    "VIVENTIUM_PLAYGROUND_PORT=3300\\n",
    encoding="utf-8",
)
(out / "runtime.local.env").write_text("", encoding="utf-8")
(out / "librechat.yaml").write_text("version: 1\\n", encoding="utf-8")
"""
    write_executable(repo_root / "scripts" / "viventium" / "config_compiler.py", config_compiler_py)

    doctor_sh = """#!/usr/bin/env bash
set -euo pipefail
exit 0
"""
    write_executable(repo_root / "scripts" / "viventium" / "doctor.sh", doctor_sh)

    start_sh = """#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "--stop" ]]; then
  touch "${TEST_ROOT}/stop-called"
fi
exit 0
"""
    write_executable(repo_root / "viventium_v0_4" / "viventium-librechat-start.sh", start_sh)

    native_stack_sh = """#!/usr/bin/env bash
set -euo pipefail
exit 0
"""
    write_executable(repo_root / "scripts" / "viventium" / "native_stack.sh", native_stack_sh)

    fake_lsof = tmp_path / "fakebrew" / "bin" / "lsof"
    fake_lsof.parent.mkdir(parents=True, exist_ok=True)
    fake_lsof.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
printf '1234\\n'
""",
        encoding="utf-8",
    )
    fake_lsof.chmod(0o755)

    fake_curl = tmp_path / "fakebrew" / "bin" / "curl"
    fake_curl.write_text(
        """#!/usr/bin/env bash
set -euo pipefail

write_code_only=0
url=""
while (($#)); do
  case "$1" in
    -w)
      shift
      [[ "${1:-}" == "%{http_code}" ]] && write_code_only=1
      ;;
    http://*|https://*)
      url="$1"
      ;;
  esac
  shift || true
done

case "$url" in
  http://localhost:3180/api/health|http://127.0.0.1:3180/api/health|http://localhost:3190/|http://127.0.0.1:3190/|http://localhost:3300/|http://127.0.0.1:3300/|http://localhost:3300/api/health|http://127.0.0.1:3300/api/health)
    if [[ "$write_code_only" == "1" ]]; then
      printf '200'
    fi
    exit 0
    ;;
esac

if [[ "$write_code_only" == "1" ]]; then
  printf '000'
fi
exit 1
""",
        encoding="utf-8",
    )
    fake_curl.chmod(0o755)

    config_path = tmp_path / "app-support" / "config.yaml"
    runtime_dir = config_path.parent / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    config_path.write_text("version: 1\ninstall:\n  mode: native\nvoice:\n  mode: local\n", encoding="utf-8")
    (runtime_dir / "runtime.env").write_text(
        "VIVENTIUM_CALL_SESSION_SECRET=test\n"
        "VIVENTIUM_INSTALL_EXPERIENCE=express\n"
        "VIVENTIUM_LC_API_PORT=3180\n"
        "VIVENTIUM_LC_FRONTEND_PORT=3190\n"
        "VIVENTIUM_PLAYGROUND_PORT=3300\n",
        encoding="utf-8",
    )
    (runtime_dir / "runtime.local.env").write_text("", encoding="utf-8")

    init_git_repo(repo_root)

    completed = subprocess.run(
      [
          str(repo_root / "bin" / "viventium"),
          "--app-support-dir",
          str(config_path.parent),
          "upgrade",
          "--skip-pull",
          "--allow-dirty",
          "--restart",
      ],
      cwd=repo_root,
      check=True,
      text=True,
      capture_output=True,
      env={**dict(os.environ), "TEST_ROOT": str(tmp_path), "VIVENTIUM_AUTO_APPROVE_PREREQS": "true"},
    )

    assert "Running Viventium stack detected. Stopping before component refresh..." in completed.stdout
    assert (tmp_path / "stop-called").exists()
    assert (tmp_path / "bootstrap-observed-stop.txt").read_text(encoding="utf-8") == "yes"


def test_upgrade_restart_recovers_running_stack_after_structured_component_refusal(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / "bin").mkdir(parents=True, exist_ok=True)

    copy_cli_fixture(repo_root)

    common_sh = """#!/usr/bin/env bash
set -euo pipefail

prepend_path_if_dir() {
  local candidate="$1"
  if [[ -d "$candidate" && ":${PATH}:" != *":${candidate}:"* ]]; then
    PATH="${candidate}:${PATH}"
  fi
}

ensure_brew_paths_on_path() {
  prepend_path_if_dir "${TEST_ROOT}/fakebrew/bin"
  export PATH
}

ensure_app_support_layout() {
  local dir="$1"
  mkdir -p "$dir/runtime" "$dir/state"
}

viventium_port_listener_active() {
  [[ ! -f "${TEST_ROOT}/stop-called" ]]
}
python_has_module() { return 0; }
resolve_repo_python() { printf '%s\\n' "${TEST_PYTHON:-python3}"; }
ensure_python_module() { return 0; }
ensure_python_requirements_file() { printf '%s\\n' "${TEST_PYTHON:-$1}"; }
"""
    write_executable(repo_root / "scripts" / "viventium" / "common.sh", common_sh)
    write_executable(repo_root / "scripts" / "viventium" / "preflight.py", "#!/usr/bin/env python3\nraise SystemExit(0)\n")
    write_executable(
        repo_root / "scripts" / "viventium" / "bootstrap_components.py",
        "#!/usr/bin/env python3\n"
        "import os\n"
        "from pathlib import Path\n"
        "Path(os.environ['TEST_ROOT'], 'component-drift-after-bootstrap').touch()\n"
        "print('component bootstrap finished; structured verification follows')\n",
    )

    config_compiler_py = """#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--config", required=True)
parser.add_argument("--output-dir", required=True)
args = parser.parse_args()
out = Path(args.output_dir)
out.mkdir(parents=True, exist_ok=True)
(out / "runtime.env").write_text(
    "VIVENTIUM_CALL_SESSION_SECRET=test\\n"
    "VIVENTIUM_INSTALL_EXPERIENCE=express\\n"
    "VIVENTIUM_LC_API_PORT=3180\\n"
    "VIVENTIUM_LC_FRONTEND_PORT=3190\\n"
    "VIVENTIUM_PLAYGROUND_PORT=3300\\n",
    encoding="utf-8",
)
(out / "runtime.local.env").write_text("", encoding="utf-8")
(out / "librechat.yaml").write_text("version: 1\\n", encoding="utf-8")
"""
    write_executable(repo_root / "scripts" / "viventium" / "config_compiler.py", config_compiler_py)
    write_executable(repo_root / "scripts" / "viventium" / "doctor.sh", "#!/usr/bin/env bash\nset -euo pipefail\nexit 0\n")
    write_executable(repo_root / "scripts" / "viventium" / "install_macos_helper.sh", "#!/usr/bin/env bash\nset -euo pipefail\nexit 0\n")
    write_executable(
        repo_root / "viventium_v0_4" / "viventium-librechat-start.sh",
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "if [[ \"${1:-}\" == \"--stop\" ]]; then\n"
        "  touch \"${TEST_ROOT}/stop-called\"\n"
        "else\n"
        "  touch \"${TEST_ROOT}/restarted-after-refusal\"\n"
        "fi\n",
    )
    write_executable(
        repo_root / "scripts" / "viventium" / "native_stack.sh",
        "#!/usr/bin/env bash\nset -euo pipefail\nexit 0\n",
    )

    fake_bin = tmp_path / "fakebrew" / "bin"
    fake_bin.mkdir(parents=True, exist_ok=True)
    (fake_bin / "lsof").write_text("#!/usr/bin/env bash\nset -euo pipefail\nexit 1\n", encoding="utf-8")
    (fake_bin / "lsof").chmod(0o755)
    (fake_bin / "curl").write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "if [[ -f \"${TEST_ROOT}/restarted-after-refusal\" ]]; then\n"
        "  printf '200'\n"
        "  exit 0\n"
        "fi\n"
        "printf '000'\n"
        "exit 1\n",
        encoding="utf-8",
    )
    (fake_bin / "curl").chmod(0o755)

    config_path = tmp_path / "app-support" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("version: 1\ninstall:\n  mode: native\nvoice:\n  mode: local\n", encoding="utf-8")
    runtime_dir = config_path.parent / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "runtime.env").write_text(
        "VIVENTIUM_CALL_SESSION_SECRET=test\n"
        "VIVENTIUM_INSTALL_EXPERIENCE=express\n"
        "VIVENTIUM_LC_API_PORT=3180\n"
        "VIVENTIUM_LC_FRONTEND_PORT=3190\n"
        "VIVENTIUM_PLAYGROUND_PORT=3300\n",
        encoding="utf-8",
    )
    (runtime_dir / "runtime.local.env").write_text("", encoding="utf-8")

    init_git_repo(repo_root)

    completed = subprocess.run(
        [
            str(repo_root / "bin" / "viventium"),
            "--app-support-dir",
            str(config_path.parent),
            "upgrade",
            "--skip-pull",
            "--allow-dirty",
            "--restart",
        ],
        cwd=repo_root,
        check=False,
        text=True,
        capture_output=True,
        env={**dict(os.environ), "TEST_ROOT": str(tmp_path), "VIVENTIUM_AUTO_APPROVE_PREREQS": "true"},
    )

    assert completed.returncode != 0
    assert "component bootstrap finished; structured verification follows" in completed.stdout
    assert "Managed component is not aligned: LibreChat (dirty_worktree)" in completed.stderr
    assert "selected components did not reach their declared pinned state" in completed.stderr
    assert "verified pre-upgrade source, config, runtime, and stopped data checkpoint" in completed.stderr
    assert "previous verified Viventium runtime and running state were restored" in completed.stderr
    assert "partially applied" not in completed.stderr
    assert (tmp_path / "stop-called").exists()
    assert (tmp_path / "restarted-after-refusal").exists()


def test_start_uses_generated_librechat_yaml_at_runtime(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / "bin").mkdir(parents=True, exist_ok=True)

    copy_cli_fixture(repo_root)

    common_sh = """#!/usr/bin/env bash
set -euo pipefail

prepend_path_if_dir() {
  local candidate="$1"
  if [[ -d "$candidate" && ":${PATH}:" != *":${candidate}:"* ]]; then
    PATH="${candidate}:${PATH}"
  fi
}

ensure_brew_paths_on_path() {
  prepend_path_if_dir "${TEST_ROOT}/fakebrew/bin"
  export PATH
}

ensure_app_support_layout() {
  local dir="$1"
  mkdir -p "$dir/runtime" "$dir/state"
}

python_has_module() { return 0; }
resolve_repo_python() { printf '%s\\n' "${TEST_PYTHON:-python3}"; }
ensure_python_module() { return 0; }
ensure_python_requirements_file() { printf '%s\\n' "${TEST_PYTHON:-$1}"; }
"""
    write_executable(repo_root / "scripts" / "viventium" / "common.sh", common_sh)

    write_executable(
        repo_root / "scripts" / "viventium" / "preflight.py",
        "#!/usr/bin/env python3\nraise SystemExit(0)\n",
    )
    write_executable(
        repo_root / "scripts" / "viventium" / "bootstrap_components.py",
        "#!/usr/bin/env python3\nraise SystemExit(0)\n",
    )
    write_executable(
        repo_root / "scripts" / "viventium" / "doctor.sh",
        "#!/usr/bin/env bash\nset -euo pipefail\nexit 0\n",
    )
    write_executable(
        repo_root / "scripts" / "viventium" / "native_stack.sh",
        "#!/usr/bin/env bash\nset -euo pipefail\nexit 0\n",
    )

    config_compiler_py = """#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--config", required=True)
parser.add_argument("--output-dir", required=True)
args = parser.parse_args()
out = Path(args.output_dir)
out.mkdir(parents=True, exist_ok=True)
(out / "runtime.env").write_text(
    "VIVENTIUM_CALL_SESSION_SECRET=test\\n"
    "VIVENTIUM_INSTALL_MODE=docker\\n"
    "VIVENTIUM_VOICE_ENABLED=false\\n",
    encoding="utf-8",
)
(out / "runtime.local.env").write_text("", encoding="utf-8")
(out / "librechat.yaml").write_text("generated: true\\n", encoding="utf-8")
Path(os.environ["TEST_ROOT"], "compile-source.txt").write_text(
    os.environ.get("VIVENTIUM_LIBRECHAT_SOURCE_OF_TRUTH", ""),
    encoding="utf-8",
)
"""
    write_executable(repo_root / "scripts" / "viventium" / "config_compiler.py", config_compiler_py)

    start_sh = """#!/usr/bin/env bash
set -euo pipefail
printf '%s' "${VIVENTIUM_LIBRECHAT_SOURCE_OF_TRUTH:-}" > "${TEST_ROOT}/runtime-source.txt"
"""
    write_executable(repo_root / "viventium_v0_4" / "viventium-librechat-start.sh", start_sh)

    private_root = tmp_path / "private"
    private_source = private_root / "curated" / "configs" / "librechat" / "source_of_truth" / "local.librechat.yaml"
    private_source.parent.mkdir(parents=True, exist_ok=True)
    private_source.write_text("private: true\n", encoding="utf-8")

    test_python = tmp_path / "with-pyyaml-python"
    write_executable(
        test_python,
        """#!/usr/bin/env bash
set -euo pipefail
exec uv run --with pyyaml python "$@"
""",
    )

    config_path = tmp_path / "app-support" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        "version: 1\ninstall:\n  mode: docker\nvoice:\n  mode: disabled\n",
        encoding="utf-8",
    )

    init_git_repo(repo_root)

    env = {
        **dict(os.environ),
        "TEST_ROOT": str(tmp_path),
        "TEST_PYTHON": str(test_python),
        "VIVENTIUM_PRIVATE_REPO_DIR": str(private_root),
        "VIVENTIUM_PRIVATE_CURATED_DIR": str(private_root / "curated"),
    }

    subprocess.run(
        [
            str(repo_root / "bin" / "viventium"),
            "--app-support-dir",
            str(config_path.parent),
            "start",
        ],
        cwd=repo_root,
        check=True,
        text=True,
        capture_output=True,
        env=env,
    )

    generated_yaml = config_path.parent / "runtime" / "librechat.yaml"
    assert (tmp_path / "compile-source.txt").read_text(encoding="utf-8") == str(private_source)
    assert (tmp_path / "runtime-source.txt").read_text(encoding="utf-8") == str(generated_yaml)


def test_start_recompiles_runtime_even_when_generated_env_is_newer_than_config(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / "bin").mkdir(parents=True, exist_ok=True)

    copy_cli_fixture(repo_root)

    common_sh = """#!/usr/bin/env bash
set -euo pipefail

prepend_path_if_dir() {
  local candidate="$1"
  if [[ -d "$candidate" && ":${PATH}:" != *":${candidate}:"* ]]; then
    PATH="${candidate}:${PATH}"
  fi
}

ensure_brew_paths_on_path() {
  prepend_path_if_dir "${TEST_ROOT}/fakebrew/bin"
  export PATH
}

ensure_app_support_layout() {
  local dir="$1"
  mkdir -p "$dir/runtime" "$dir/state"
}

python_has_module() { return 0; }
resolve_repo_python() { printf 'python3\\n'; }
ensure_python_module() { return 0; }
"""
    write_executable(repo_root / "scripts" / "viventium" / "common.sh", common_sh)
    write_executable(repo_root / "scripts" / "viventium" / "preflight.py", "#!/usr/bin/env python3\nraise SystemExit(0)\n")
    write_executable(repo_root / "scripts" / "viventium" / "bootstrap_components.py", "#!/usr/bin/env python3\nraise SystemExit(0)\n")

    config_compiler_py = """#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--config", required=True)
parser.add_argument("--output-dir", required=True)
args = parser.parse_args()
out = Path(args.output_dir)
out.mkdir(parents=True, exist_ok=True)
counter_path = Path(os.environ["TEST_ROOT"]) / "compile-count.txt"
count = int(counter_path.read_text(encoding="utf-8") or "0") if counter_path.exists() else 0
count += 1
counter_path.write_text(str(count), encoding="utf-8")
(out / "runtime.env").write_text(
    "VIVENTIUM_CALL_SESSION_SECRET=test\\n"
    "VIVENTIUM_INSTALL_MODE=docker\\n"
    "VIVENTIUM_VOICE_ENABLED=false\\n"
    f"COMPILED={count}\\n",
    encoding="utf-8",
)
(out / "runtime.local.env").write_text("", encoding="utf-8")
(out / "librechat.yaml").write_text("version: 1\\n", encoding="utf-8")
"""
    write_executable(repo_root / "scripts" / "viventium" / "config_compiler.py", config_compiler_py)

    start_sh = """#!/usr/bin/env bash
set -euo pipefail
exit 0
"""
    write_executable(repo_root / "viventium_v0_4" / "viventium-librechat-start.sh", start_sh)

    fake_bin = tmp_path / "fakebrew" / "bin"
    fake_bin.mkdir(parents=True, exist_ok=True)
    (fake_bin / "lsof").write_text("#!/usr/bin/env bash\nset -euo pipefail\nexit 1\n", encoding="utf-8")
    (fake_bin / "lsof").chmod(0o755)
    (fake_bin / "pgrep").write_text("#!/usr/bin/env bash\nset -euo pipefail\nexit 1\n", encoding="utf-8")
    (fake_bin / "pgrep").chmod(0o755)

    config_path = tmp_path / "app-support" / "config.yaml"
    runtime_dir = config_path.parent / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    config_path.write_text("version: 1\ninstall:\n  mode: native\nvoice:\n  mode: local\n", encoding="utf-8")
    (runtime_dir / "runtime.env").write_text("VIVENTIUM_CALL_SESSION_SECRET=stale\nCOMPILED=0\n", encoding="utf-8")
    (runtime_dir / "runtime.local.env").write_text("", encoding="utf-8")

    init_git_repo(repo_root)

    completed = subprocess.run(
        [
            str(repo_root / "bin" / "viventium"),
            "--app-support-dir",
            str(config_path.parent),
            "start",
        ],
        cwd=repo_root,
        check=True,
        text=True,
        capture_output=True,
        env={**dict(os.environ), "TEST_ROOT": str(tmp_path)},
    )

    assert completed.returncode == 0
    assert (tmp_path / "compile-count.txt").read_text(encoding="utf-8") == "1"


def test_start_native_preserves_custom_surfaces_and_skips_deferred_express_surfaces(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / "bin").mkdir(parents=True, exist_ok=True)

    copy_cli_fixture(repo_root)

    common_sh = """#!/usr/bin/env bash
set -euo pipefail

prepend_path_if_dir() {
  local candidate="$1"
  if [[ -d "$candidate" && ":${PATH}:" != *":${candidate}:"* ]]; then
    PATH="${candidate}:${PATH}"
  fi
}

ensure_brew_paths_on_path() {
  prepend_path_if_dir "${TEST_ROOT}/fakebrew/bin"
  export PATH
}

ensure_app_support_layout() {
  local dir="$1"
  mkdir -p "$dir/runtime" "$dir/state"
}

python_has_module() { return 0; }
resolve_repo_python() { printf 'python3\\n'; }
ensure_python_module() { return 0; }
"""
    write_executable(repo_root / "scripts" / "viventium" / "common.sh", common_sh)
    write_executable(
        repo_root / "scripts" / "viventium" / "bootstrap_components.py",
        "#!/usr/bin/env python3\nraise SystemExit(0)\n",
    )

    config_compiler_py = """#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--config", required=True)
parser.add_argument("--output-dir", required=True)
args = parser.parse_args()
out = Path(args.output_dir)
out.mkdir(parents=True, exist_ok=True)
config_text = Path(args.config).read_text(encoding="utf-8")
experience = "express" if "experience: express" in config_text else "legacy"
voice_enabled = "false" if experience == "express" else "true"
(out / "runtime.env").write_text(
    "VIVENTIUM_CALL_SESSION_SECRET=test\\n"
    "VIVENTIUM_INSTALL_MODE=native\\n"
    f"VIVENTIUM_INSTALL_EXPERIENCE={experience}\\n"
    f"VIVENTIUM_VOICE_ENABLED={voice_enabled}\\n",
    encoding="utf-8",
)
(out / "runtime.local.env").write_text("", encoding="utf-8")
(out / "librechat.yaml").write_text("version: 1\\n", encoding="utf-8")
"""
    write_executable(repo_root / "scripts" / "viventium" / "config_compiler.py", config_compiler_py)

    start_sh = """#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" > "${TEST_ROOT}/start-args.txt"
exit 0
"""
    write_executable(repo_root / "viventium_v0_4" / "viventium-librechat-start.sh", start_sh)

    native_stack_sh = """#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$1" > "${TEST_ROOT}/native-stack-action.txt"
printf '%s\\n' "${VIVENTIUM_NATIVE_STACK_SKIP_MEILI:-0}" > "${TEST_ROOT}/native-stack-skip-meili.txt"
exit 0
"""
    write_executable(repo_root / "scripts" / "viventium" / "native_stack.sh", native_stack_sh)

    fake_bin = tmp_path / "fakebrew" / "bin"
    fake_bin.mkdir(parents=True, exist_ok=True)
    (fake_bin / "lsof").write_text("#!/usr/bin/env bash\nset -euo pipefail\nexit 1\n", encoding="utf-8")
    (fake_bin / "lsof").chmod(0o755)

    config_path = tmp_path / "app-support" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("version: 1\ninstall:\n  mode: native\nvoice:\n  mode: local\n", encoding="utf-8")

    init_git_repo(repo_root)

    completed = subprocess.run(
        [
            str(repo_root / "bin" / "viventium"),
            "--app-support-dir",
            str(config_path.parent),
            "start",
        ],
        cwd=repo_root,
        check=True,
        text=True,
        capture_output=True,
        env={**dict(os.environ), "TEST_ROOT": str(tmp_path)},
    )

    assert completed.returncode == 0
    assert (tmp_path / "native-stack-action.txt").read_text(encoding="utf-8").strip() == "start"
    start_args = (tmp_path / "start-args.txt").read_text(encoding="utf-8").strip()
    assert "--skip-docker" not in start_args
    assert "--skip-playground" not in start_args
    assert (tmp_path / "native-stack-skip-meili.txt").read_text(encoding="utf-8").strip() == "0"

    config_path.write_text(
        "version: 1\ninstall:\n  mode: native\n  experience: express\nvoice:\n  mode: disabled\n",
        encoding="utf-8",
    )
    express_completed = subprocess.run(
        [
            str(repo_root / "bin" / "viventium"),
            "--app-support-dir",
            str(config_path.parent),
            "start",
        ],
        cwd=repo_root,
        check=True,
        text=True,
        capture_output=True,
        env={**dict(os.environ), "TEST_ROOT": str(tmp_path)},
    )

    assert express_completed.returncode == 0
    express_start_args = (tmp_path / "start-args.txt").read_text(encoding="utf-8").strip()
    assert "--skip-docker" not in express_start_args
    assert "--skip-playground" in express_start_args
    assert "--skip-voice-gateway" in express_start_args
    assert "--skip-livekit" in express_start_args
    assert (tmp_path / "native-stack-skip-meili.txt").read_text(encoding="utf-8").strip() == "1"


def test_cli_refuses_concurrent_operation_when_lock_is_active(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / "bin").mkdir(parents=True, exist_ok=True)

    copy_cli_fixture(repo_root)

    common_sh = """#!/usr/bin/env bash
set -euo pipefail

ensure_brew_paths_on_path() { :; }
ensure_app_support_layout() {
  local dir="$1"
  mkdir -p "$dir/runtime" "$dir/state"
}
python_has_module() { return 0; }
resolve_repo_python() { printf 'python3\\n'; }
ensure_python_module() { return 0; }
"""
    write_executable(repo_root / "scripts" / "viventium" / "common.sh", common_sh)

    config_path = tmp_path / "app-support" / "config.yaml"
    lock_dir = config_path.parent / "state" / "cli-operation.lock"
    lock_dir.mkdir(parents=True, exist_ok=True)
    (lock_dir / "pid").write_text(str(os.getpid()), encoding="utf-8")
    (lock_dir / "command").write_text("upgrade", encoding="utf-8")
    current_command = subprocess.run(
        ["ps", "-p", str(os.getpid()), "-o", "command="],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    (lock_dir / "process_command").write_text(current_command, encoding="utf-8")

    completed = subprocess.run(
        [
            str(repo_root / "bin" / "viventium"),
            "--app-support-dir",
            str(config_path.parent),
            "start",
        ],
        cwd=repo_root,
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert "Another Viventium CLI operation is already running (upgrade, pid" in completed.stderr


def test_cli_clears_reused_pid_operation_lock_before_running(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / "bin").mkdir(parents=True, exist_ok=True)

    copy_cli_fixture(repo_root)

    common_sh = """#!/usr/bin/env bash
set -euo pipefail

ensure_brew_paths_on_path() { :; }
ensure_app_support_layout() {
  local dir="$1"
  mkdir -p "$dir/runtime" "$dir/state"
}
python_has_module() { return 0; }
resolve_repo_python() { printf 'python3\n'; }
ensure_python_module() { return 0; }
"""
    write_executable(repo_root / "scripts" / "viventium" / "common.sh", common_sh)
    write_executable(repo_root / "scripts" / "viventium" / "preflight.py", "#!/usr/bin/env python3\nraise SystemExit(0)\n")

    config_path = tmp_path / "app-support" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("version: 1\ninstall:\n  mode: native\n", encoding="utf-8")

    lock_dir = config_path.parent / "state" / "cli-operation.lock"
    lock_dir.mkdir(parents=True, exist_ok=True)
    (lock_dir / "pid").write_text(str(os.getpid()), encoding="utf-8")
    (lock_dir / "command").write_text("install", encoding="utf-8")
    (lock_dir / "process_command").write_text("stale-viventium-process-fingerprint", encoding="utf-8")

    completed = subprocess.run(
        [
            str(repo_root / "bin" / "viventium"),
            "--app-support-dir",
            str(config_path.parent),
            "preflight",
        ],
        cwd=repo_root,
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0
    assert not lock_dir.exists()


def test_cli_clears_stale_operation_lock_before_running(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / "bin").mkdir(parents=True, exist_ok=True)

    copy_cli_fixture(repo_root)

    common_sh = """#!/usr/bin/env bash
set -euo pipefail

ensure_brew_paths_on_path() { :; }
ensure_app_support_layout() {
  local dir="$1"
  mkdir -p "$dir/runtime" "$dir/state"
}
python_has_module() { return 0; }
resolve_repo_python() { printf 'python3\\n'; }
ensure_python_module() { return 0; }
"""
    write_executable(repo_root / "scripts" / "viventium" / "common.sh", common_sh)
    write_executable(repo_root / "scripts" / "viventium" / "preflight.py", "#!/usr/bin/env python3\nraise SystemExit(0)\n")

    config_path = tmp_path / "app-support" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("version: 1\ninstall:\n  mode: native\n", encoding="utf-8")

    lock_dir = config_path.parent / "state" / "cli-operation.lock"
    lock_dir.mkdir(parents=True, exist_ok=True)
    (lock_dir / "pid").write_text("999999", encoding="utf-8")
    (lock_dir / "command").write_text("start", encoding="utf-8")

    completed = subprocess.run(
        [
            str(repo_root / "bin" / "viventium"),
            "--app-support-dir",
            str(config_path.parent),
            "preflight",
        ],
        cwd=repo_root,
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0
    assert not lock_dir.exists()


def test_upgrade_refuses_running_stack_without_restart(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / "bin").mkdir(parents=True, exist_ok=True)

    copy_cli_fixture(repo_root)

    common_sh = """#!/usr/bin/env bash
set -euo pipefail

prepend_path_if_dir() {
  local candidate="$1"
  if [[ -d "$candidate" && ":${PATH}:" != *":${candidate}:"* ]]; then
    PATH="${candidate}:${PATH}"
  fi
}

ensure_brew_paths_on_path() {
  prepend_path_if_dir "${TEST_ROOT}/fakebrew/bin"
  export PATH
}

ensure_app_support_layout() {
  local dir="$1"
  mkdir -p "$dir/runtime" "$dir/state"
}

viventium_port_listener_active() { return 0; }

python_has_module() { return 0; }
resolve_repo_python() { printf 'python3\\n'; }
ensure_python_module() { return 0; }
"""
    write_executable(repo_root / "scripts" / "viventium" / "common.sh", common_sh)
    write_executable(repo_root / "scripts" / "viventium" / "preflight.py", "#!/usr/bin/env python3\nraise SystemExit(0)\n")
    write_executable(repo_root / "scripts" / "viventium" / "bootstrap_components.py", "#!/usr/bin/env python3\nraise SystemExit(0)\n")
    write_executable(repo_root / "scripts" / "viventium" / "config_compiler.py", "#!/usr/bin/env python3\nraise SystemExit(0)\n")
    write_executable(repo_root / "scripts" / "viventium" / "doctor.sh", "#!/usr/bin/env bash\nset -euo pipefail\nexit 0\n")
    write_executable(repo_root / "scripts" / "viventium" / "install_macos_helper.sh", "#!/usr/bin/env bash\nset -euo pipefail\nexit 0\n")
    write_executable(repo_root / "viventium_v0_4" / "viventium-librechat-start.sh", "#!/usr/bin/env bash\nset -euo pipefail\nexit 0\n")

    fake_lsof = tmp_path / "fakebrew" / "bin" / "lsof"
    fake_lsof.parent.mkdir(parents=True, exist_ok=True)
    fake_lsof.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
printf '1234\\n'
""",
        encoding="utf-8",
    )
    fake_lsof.chmod(0o755)

    config_path = tmp_path / "app-support" / "config.yaml"
    runtime_dir = config_path.parent / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    config_path.write_text("version: 1\ninstall:\n  mode: native\nvoice:\n  mode: local\n", encoding="utf-8")
    (runtime_dir / "runtime.env").write_text(
        "VIVENTIUM_CALL_SESSION_SECRET=test\n"
        "VIVENTIUM_LC_API_PORT=3180\n"
        "VIVENTIUM_LC_FRONTEND_PORT=3190\n"
        "VIVENTIUM_PLAYGROUND_PORT=3300\n",
        encoding="utf-8",
    )
    (runtime_dir / "runtime.local.env").write_text("", encoding="utf-8")

    init_git_repo(repo_root)

    completed = subprocess.run(
        [
            str(repo_root / "bin" / "viventium"),
            "--app-support-dir",
            str(config_path.parent),
            "upgrade",
            "--skip-pull",
            "--allow-dirty",
        ],
        cwd=repo_root,
        check=False,
        text=True,
        capture_output=True,
        env={**dict(os.environ), "TEST_ROOT": str(tmp_path)},
    )

    assert completed.returncode != 0
    assert "Upgrade refused because the Viventium stack is currently running." in completed.stderr


def test_upgrade_restart_stops_scoped_dependency_jobs_before_bootstrap(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / "bin").mkdir(parents=True, exist_ok=True)

    copy_cli_fixture(repo_root)

    common_sh = """#!/usr/bin/env bash
set -euo pipefail

prepend_path_if_dir() {
  local candidate="$1"
  if [[ -d "$candidate" && ":${PATH}:" != *":${candidate}:"* ]]; then
    PATH="${candidate}:${PATH}"
  fi
}

ensure_brew_paths_on_path() {
  prepend_path_if_dir "${TEST_ROOT}/fakebrew/bin"
  export PATH
}

ensure_app_support_layout() {
  local dir="$1"
  mkdir -p "$dir/runtime" "$dir/state"
}

python_has_module() { return 0; }
resolve_repo_python() { printf 'python3\\n'; }
ensure_python_module() { return 0; }
"""
    write_executable(repo_root / "scripts" / "viventium" / "common.sh", common_sh)
    write_executable(repo_root / "scripts" / "viventium" / "preflight.py", "#!/usr/bin/env python3\nraise SystemExit(0)\n")

    bootstrap_py = """#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path

test_root = Path(os.environ["TEST_ROOT"])
marker = test_root / "stop-called"
(test_root / "bootstrap-observed-stop.txt").write_text(
    "yes" if marker.exists() else "no",
    encoding="utf-8",
)
"""
    write_executable(repo_root / "scripts" / "viventium" / "bootstrap_components.py", bootstrap_py)

    config_compiler_py = """#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--config", required=True)
parser.add_argument("--output-dir", required=True)
args = parser.parse_args()
out = Path(args.output_dir)
out.mkdir(parents=True, exist_ok=True)
(out / "runtime.env").write_text(
    "VIVENTIUM_CALL_SESSION_SECRET=test\\n"
    "VIVENTIUM_INSTALL_EXPERIENCE=express\\n"
    "VIVENTIUM_LC_API_PORT=3180\\n"
    "VIVENTIUM_LC_FRONTEND_PORT=3190\\n"
    "VIVENTIUM_PLAYGROUND_PORT=3300\\n",
    encoding="utf-8",
)
(out / "runtime.local.env").write_text("", encoding="utf-8")
(out / "librechat.yaml").write_text("version: 1\\n", encoding="utf-8")
"""
    write_executable(repo_root / "scripts" / "viventium" / "config_compiler.py", config_compiler_py)
    write_executable(repo_root / "scripts" / "viventium" / "doctor.sh", "#!/usr/bin/env bash\nset -euo pipefail\nexit 0\n")

    start_sh = """#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "--stop" ]]; then
  touch "${TEST_ROOT}/stop-called"
fi
exit 0
"""
    write_executable(repo_root / "viventium_v0_4" / "viventium-librechat-start.sh", start_sh)
    write_executable(repo_root / "scripts" / "viventium" / "native_stack.sh", "#!/usr/bin/env bash\nset -euo pipefail\nexit 0\n")

    fake_bin = tmp_path / "fakebrew" / "bin"
    fake_bin.mkdir(parents=True, exist_ok=True)

    (fake_bin / "lsof").write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\nexit 1\n",
        encoding="utf-8",
    )
    (fake_bin / "lsof").chmod(0o755)

    (fake_bin / "curl").write_text(
        """#!/usr/bin/env bash
set -euo pipefail

write_code_only=0
url=""
while (($#)); do
  case "$1" in
    -w)
      shift
      [[ "${1:-}" == "%{http_code}" ]] && write_code_only=1
      ;;
    http://*|https://*)
      url="$1"
      ;;
  esac
  shift || true
done

case "$url" in
  http://localhost:3180/api/health|http://127.0.0.1:3180/api/health|http://localhost:3190/|http://127.0.0.1:3190/|http://localhost:3300/|http://127.0.0.1:3300/|http://localhost:3300/api/health|http://127.0.0.1:3300/api/health)
    if [[ "$write_code_only" == "1" ]]; then
      printf '200'
    fi
    exit 0
    ;;
esac

if [[ "$write_code_only" == "1" ]]; then
  printf '000'
fi
exit 1
""",
        encoding="utf-8",
    )
    (fake_bin / "curl").chmod(0o755)

    (fake_bin / "pgrep").write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        "if [[ \"$*\" == *\"npm ci\"* ]]; then\n"
        "  printf '5678\\n'\n"
        "fi\n",
        encoding="utf-8",
    )
    (fake_bin / "pgrep").chmod(0o755)

    (fake_bin / "ps").write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        "if [[ \"$*\" == *\"-p 5678 -o command=\"* ]]; then\n"
        f"  printf '%s\\n' '{repo_root}/viventium_v0_4/LibreChat npm ci'\n"
        "  exit 0\n"
        "fi\n"
        "exit 1\n",
        encoding="utf-8",
    )
    (fake_bin / "ps").chmod(0o755)

    config_path = tmp_path / "app-support" / "config.yaml"
    runtime_dir = config_path.parent / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    config_path.write_text("version: 1\ninstall:\n  mode: native\nvoice:\n  mode: local\n", encoding="utf-8")
    (runtime_dir / "runtime.env").write_text(
        "VIVENTIUM_CALL_SESSION_SECRET=test\n"
        "VIVENTIUM_INSTALL_EXPERIENCE=express\n"
        "VIVENTIUM_LC_API_PORT=3180\n"
        "VIVENTIUM_LC_FRONTEND_PORT=3190\n"
        "VIVENTIUM_PLAYGROUND_PORT=3300\n",
        encoding="utf-8",
    )
    (runtime_dir / "runtime.local.env").write_text("", encoding="utf-8")

    init_git_repo(repo_root)

    completed = subprocess.run(
        [
            str(repo_root / "bin" / "viventium"),
            "--app-support-dir",
            str(config_path.parent),
            "upgrade",
            "--skip-pull",
            "--allow-dirty",
            "--restart",
        ],
        cwd=repo_root,
        check=True,
        text=True,
        capture_output=True,
        env={**dict(os.environ), "TEST_ROOT": str(tmp_path), "VIVENTIUM_AUTO_APPROVE_PREREQS": "true"},
    )

    assert "Running Viventium stack detected. Stopping before component refresh..." in completed.stdout
    assert (tmp_path / "stop-called").exists()
    assert (tmp_path / "bootstrap-observed-stop.txt").read_text(encoding="utf-8") == "yes"
