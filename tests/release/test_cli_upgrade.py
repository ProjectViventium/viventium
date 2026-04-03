from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def write_executable(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


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
    assert "optional_install_surfaces_healthy() {" in cli_source
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
    assert 'if [[ "${VIVENTIUM_AUTO_APPROVE_PREREQS:-false}" == "true" || "${HEADLESS:-0}" == "1" ]]; then' in cli_source
    assert 'printf \'%s\' "$value" | tr \'[:upper:]\' \'[:lower:]\'' in cli_source
    assert '${value,,}' not in cli_source
    assert 'read -r api_port frontend_port playground_port <<<"$(read_runtime_ports)"' not in cli_source
    assert "start_stack_for_install() {" in cli_source
    assert "local_http_surface_healthy() {" in cli_source
    assert 'http_url_healthy "http://localhost:${port}${path_suffix}"' in cli_source
    assert 'http_url_healthy "http://127.0.0.1:${port}${path_suffix}"' in cli_source
    assert 'local_http_surface_healthy "$port" "/api/health"' in cli_source
    assert 'local_http_surface_healthy "$port" "/"' in cli_source
    assert 'if runtime_env_true "START_SEARXNG" "false" && ! searxng_surface_healthy; then' in cli_source
    assert 'if runtime_env_true "START_FIRECRAWL" "false" && ! firecrawl_surface_healthy; then' in cli_source
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
    assert "print_install_summary 0" in install_section
    assert "exit 1" in install_section
    assert "launch_macos_helper_app" in cli_source
    assert 'print_install_summary 1' in cli_source
    assert 'launch_macos_helper_app\n      print_install_summary 1\n      open_default_browser' in cli_source
    assert "print_connected_accounts_browser_reminder" in cli_source
    assert (
        'launch_macos_helper_app\n      print_install_summary 1\n      open_default_browser\n      print_connected_accounts_browser_reminder'
        in cli_source
    )


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


def test_cli_usage_lists_runtime_recovery_commands() -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    usage_section = cli_source.split("usage() {", 1)[1].split("USAGE", 2)[1]

    assert "update            Alias for upgrade." in usage_section
    assert "status            Show live service health and access URLs." in usage_section
    assert "status-bar        Turn the macOS Viventium status-bar helper on or off." in usage_section
    assert "reset             Factory-reset the local Viventium install state under App Support." in usage_section
    assert "uninstall         Remove the local Viventium install state and helper app." in usage_section


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


def test_cli_usage_documents_status_bar_and_shell_init_commands() -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")

    assert "run_status_bar_command() {" in cli_source
    assert 'echo "Viventium status-bar helper is enabled."' in cli_source
    assert 'echo "Viventium status-bar helper is hidden."' in cli_source
    assert 'echo "Run bin/viventium status-bar on to bring it back."' in cli_source
    assert "bin/viventium status-bar on" in cli_source
    assert "bin/viventium status-bar off" in cli_source


def test_install_script_defaults_to_main_branch() -> None:
    install_source = (REPO_ROOT / "install.sh").read_text(encoding="utf-8")

    assert 'BRANCH="${VIVENTIUM_REPO_BRANCH:-main}"' in install_source
    assert "main-viventium" not in install_source


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


def test_upgrade_refreshes_python_after_preflight_install(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / "bin").mkdir(parents=True, exist_ok=True)

    shutil.copy2(REPO_ROOT / "bin" / "viventium", repo_root / "bin" / "viventium")

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
import sys
from pathlib import Path

fake_python = Path(os.environ["TEST_ROOT"]) / "fakebrew" / "bin" / "python3.12"
fake_python.parent.mkdir(parents=True, exist_ok=True)
fake_python.write_text(
    "#!/bin/sh\\n"
    "export VIVENTIUM_SELECTED_PYTHON=python3.12\\n"
    f"exec {sys.executable} \\\"$@\\\"\\n",
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
        check=True,
        text=True,
        capture_output=True,
        env={
            **dict(os.environ),
            "TEST_ROOT": str(tmp_path),
            "VIVENTIUM_AUTO_APPROVE_PREREQS": "true",
        },
    )

    assert "Upgrade complete. Next: bin/viventium start" in completed.stdout
    assert (tmp_path / "selected-python.txt").read_text(encoding="utf-8") == "python3.12"


def test_upgrade_restart_stops_running_stack_before_bootstrap(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / "bin").mkdir(parents=True, exist_ok=True)

    shutil.copy2(REPO_ROOT / "bin" / "viventium", repo_root / "bin" / "viventium")

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


def test_start_uses_generated_librechat_yaml_at_runtime(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / "bin").mkdir(parents=True, exist_ok=True)

    shutil.copy2(REPO_ROOT / "bin" / "viventium", repo_root / "bin" / "viventium")

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
        "TEST_PYTHON": sys.executable,
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

    shutil.copy2(REPO_ROOT / "bin" / "viventium", repo_root / "bin" / "viventium")

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


def test_start_in_native_mode_does_not_force_skip_docker(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / "bin").mkdir(parents=True, exist_ok=True)

    shutil.copy2(REPO_ROOT / "bin" / "viventium", repo_root / "bin" / "viventium")

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
(out / "runtime.env").write_text(
    "VIVENTIUM_CALL_SESSION_SECRET=test\\n"
    "VIVENTIUM_INSTALL_MODE=native\\n"
    "VIVENTIUM_VOICE_ENABLED=true\\n",
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


def test_cli_refuses_concurrent_operation_when_lock_is_active(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / "bin").mkdir(parents=True, exist_ok=True)

    shutil.copy2(REPO_ROOT / "bin" / "viventium", repo_root / "bin" / "viventium")

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


def test_cli_clears_stale_operation_lock_before_running(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / "bin").mkdir(parents=True, exist_ok=True)

    shutil.copy2(REPO_ROOT / "bin" / "viventium", repo_root / "bin" / "viventium")

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

    shutil.copy2(REPO_ROOT / "bin" / "viventium", repo_root / "bin" / "viventium")

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
    write_executable(repo_root / "scripts" / "viventium" / "config_compiler.py", "#!/usr/bin/env python3\nraise SystemExit(0)\n")
    write_executable(repo_root / "scripts" / "viventium" / "doctor.sh", "#!/usr/bin/env bash\nset -euo pipefail\nexit 0\n")
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

    shutil.copy2(REPO_ROOT / "bin" / "viventium", repo_root / "bin" / "viventium")

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
