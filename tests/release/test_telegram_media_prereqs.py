from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
START_SCRIPT_PATH = REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"


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


def first_line_number_containing(text: str, needle: str) -> int:
    for index, line in enumerate(text.splitlines(), start=1):
        if needle in line:
            return index
    raise AssertionError(f"Missing line containing: {needle}")


def test_ensure_telegram_media_prereqs_installs_ffmpeg_via_brew(tmp_path: Path) -> None:
    script_text = START_SCRIPT_PATH.read_text(encoding="utf-8")
    function_def = extract_shell_function(script_text, "ffmpeg_is_usable")
    function_def += extract_shell_function(script_text, "ensure_telegram_media_prereqs")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir(parents=True, exist_ok=True)
    brew_log = tmp_path / "brew.log"
    ffmpeg_path = fake_bin / "ffmpeg"
    brew_path = fake_bin / "brew"
    brew_path.write_text(
        "\n".join(
            [
                "#!/bin/sh",
                "if [ \"$1\" = \"--prefix\" ]; then",
                f"  printf '%s\\n' '{tmp_path}'",
                "  exit 0",
                "fi",
                "if [ \"$1\" = \"install\" ] && [ \"$2\" = \"ffmpeg\" ]; then",
                f"  printf 'install ffmpeg\\n' >> '{brew_log}'",
                f"  /bin/cat > '{ffmpeg_path}' <<'EOF'",
                "#!/bin/sh",
                "exit 0",
                "EOF",
                f"  /bin/chmod +x '{ffmpeg_path}'",
                "  exit 0",
                "fi",
                "exit 1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    brew_path.chmod(0o755)

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                f"PATH='{fake_bin}'\n"
                "uname() { printf 'Darwin\\n'; }\n"
                "log_warn() { printf 'WARN:%s\\n' \"$1\"; }\n"
                "log_error() { printf 'ERR:%s\\n' \"$1\"; }\n"
                "log_success() { printf 'OK:%s\\n' \"$1\"; }\n"
                f"LOG_DIR='{tmp_path}'\n"
                f"{function_def}"
                "ensure_telegram_media_prereqs\n"
                "command -v ffmpeg >/dev/null 2>&1\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "OK:ffmpeg is ready for Telegram media support" in completed.stdout
    assert brew_log.read_text(encoding="utf-8").strip() == "install ffmpeg"


def test_ensure_telegram_media_prereqs_reinstalls_broken_ffmpeg(tmp_path: Path) -> None:
    script_text = START_SCRIPT_PATH.read_text(encoding="utf-8")
    function_def = extract_shell_function(script_text, "ffmpeg_is_usable")
    function_def += extract_shell_function(script_text, "ensure_telegram_media_prereqs")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir(parents=True, exist_ok=True)
    brew_log = tmp_path / "brew.log"
    ffmpeg_path = fake_bin / "ffmpeg"
    ffmpeg_path.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"-hide_banner\" ]; then\n"
        "  printf 'dyld: Library not loaded\\n' >&2\n"
        "  exit 6\n"
        "fi\n"
        "exit 6\n",
        encoding="utf-8",
    )
    ffmpeg_path.chmod(0o755)
    brew_path = fake_bin / "brew"
    brew_path.write_text(
        "\n".join(
            [
                "#!/bin/sh",
                "if [ \"$1\" = \"--prefix\" ]; then",
                f"  printf '%s\\n' '{tmp_path}'",
                "  exit 0",
                "fi",
                "if [ \"$1\" = \"reinstall\" ] && [ \"$2\" = \"ffmpeg\" ]; then",
                f"  printf 'reinstall ffmpeg\\n' >> '{brew_log}'",
                f"  /bin/cat > '{ffmpeg_path}' <<'EOF'",
                "#!/bin/sh",
                "exit 0",
                "EOF",
                f"  /bin/chmod +x '{ffmpeg_path}'",
                "  exit 0",
                "fi",
                "exit 1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    brew_path.chmod(0o755)

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                f"PATH='{fake_bin}'\n"
                "uname() { printf 'Darwin\\n'; }\n"
                "log_warn() { printf 'WARN:%s\\n' \"$1\"; }\n"
                "log_error() { printf 'ERR:%s\\n' \"$1\"; }\n"
                "log_success() { printf 'OK:%s\\n' \"$1\"; }\n"
                f"LOG_DIR='{tmp_path}'\n"
                f"{function_def}"
                "ensure_telegram_media_prereqs\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "WARN:ffmpeg is installed but not runnable" in completed.stdout
    assert "OK:ffmpeg is ready for Telegram media support" in completed.stdout
    assert brew_log.read_text(encoding="utf-8").strip() == "reinstall ffmpeg"


def test_start_telegram_bot_checks_media_prereqs_before_launch() -> None:
    script_text = START_SCRIPT_PATH.read_text(encoding="utf-8")

    assert "ffmpeg_is_usable() {" in script_text
    assert "if ! ensure_telegram_media_prereqs; then" in script_text
    assert "Telegram bot cannot start without ffmpeg for supported voice/video media" in script_text
    assert "if ! start_telegram_local_bot_api; then" in script_text


def test_detached_telegram_start_uses_user_launchd_job() -> None:
    script_text = START_SCRIPT_PATH.read_text(encoding="utf-8")
    launch_fragment = script_text[
        script_text.index('local telegram_legacy_launch_script="$LOG_ROOT/telegram_bot_launch.sh"') :
        script_text.index("local telegram_started_with_launchctl=false")
    ]

    assert "telegram_bot_launch.sh" in script_text
    assert "telegram_bot_runtime.env" in script_text
    assert "chmod 600 \"$telegram_runtime_env_file\"" in script_text
    assert "MS365_MCP_CLIENT_SECRET" not in launch_fragment
    assert 'source "$VIVENTIUM_ENV_FILE"' not in launch_fragment
    assert 'source "$ENV_FILE_LOCAL"' not in launch_fragment
    assert (
        'local telegram_launch_dir="$TELEGRAM_POLLER_STATE_DIR/launches/'
        '${telegram_repo_launch_id}-${telegram_launch_attempt_id}"'
    ) in launch_fragment
    assert "# viventium-launch-package-schema: 1" in launch_fragment
    assert (
        'source "\\$telegram_launch_package_dir/telegram_bot_runtime.env"'
        in launch_fragment
    )
    assert (
        'source "\\$telegram_launch_package_dir/telegram_overlay.env"'
        in launch_fragment
    )
    assert 'source "$telegram_runtime_env_file"' not in launch_fragment
    assert '--candidate-launch-script "$telegram_launch_script"' in launch_fragment
    assert "VIVENTIUM_TELEGRAM_RECONNECT_GRACE_S" in launch_fragment
    assert "VIVENTIUM_TELEGRAM_EMPTY_RESPONSE_MESSAGE" in launch_fragment
    assert "local telegram_clean_env=(" in script_text
    assert "local telegram_launch_program=(" in script_text
    assert "env -i" in script_text
    assert '"HOME=$HOME"' in script_text
    assert "launchctl submit" in script_text
    assert '"${telegram_clean_env[@]}" launchctl submit' in script_text
    assert "-l \"$TELEGRAM_BOT_LAUNCHCTL_LABEL\"" in script_text
    assert '-- "${telegram_launch_program[@]}"' in script_text
    assert 'nohup "${telegram_launch_program[@]}"' in script_text
    assert 'nohup "$telegram_python" bot.py' in script_text
    assert (
        '/bin/cp "$TELEGRAM_CONFIG_ENV_FILE" "$telegram_overlay_env_file"'
        in launch_fragment
    )
    assert 'source "$TELEGRAM_CONFIG_ENV_FILE"' not in launch_fragment
    assert 'if [[ -z "\\${API_KEY:-}" && -n "\\${OPENAI_API_KEY:-}" ]]; then export API_KEY="\\$OPENAI_API_KEY"; fi' in script_text
    assert 'TELEGRAM_BOT_WATCHDOG_PID_FILE="$LOG_ROOT/telegram_bot_watchdog.pid"' in script_text
    assert "start_telegram_bot_watchdog() {" in script_text
    assert "Telegram bot watchdog restarting Telegram bridge" in script_text
    assert "start_telegram_bot_watchdog" in script_text


def test_telegram_watchdog_supervises_foreground_and_detached_launches() -> None:
    script_text = START_SCRIPT_PATH.read_text(encoding="utf-8")
    watchdog_block = script_text[
        script_text.index("start_telegram_bot_watchdog() {") :
        script_text.index("\nstart_prompt_workbench_watchdog() {")
    ]

    assert 'if ! detached_start_requested; then\n    return 0\n  fi' not in watchdog_block
    assert 'if detached_start_requested; then\n    disown "$watchdog_pid"' in watchdog_block


def test_telegram_launcher_requires_application_ready_receipt_not_only_a_live_pid() -> None:
    script_text = START_SCRIPT_PATH.read_text(encoding="utf-8")
    start_block = script_text[
        script_text.index("start_telegram_bot() {") :
        script_text.index("\nschedule_deferred_telegram_bot_start() {")
    ]
    watchdog_block = script_text[
        script_text.index("start_telegram_bot_watchdog() {") :
        script_text.index("\nstart_prompt_workbench_watchdog() {")
    ]
    bot_text = (REPO_ROOT / "viventium_v0_4/telegram-viventium/TelegramVivBot/bot.py").read_text(
        encoding="utf-8"
    )

    assert 'TELEGRAM_BOT_READY_FILE="$LOG_ROOT/telegram_bot.ready"' in script_text
    assert 'export VIVENTIUM_TELEGRAM_READY_FILE="$TELEGRAM_BOT_READY_FILE"' in start_block
    assert (
        'VIVENTIUM_TELEGRAM_READY_FILE="$TELEGRAM_BOT_READY_FILE" \\\n'
        '        nohup "$telegram_python" bot.py' in start_block
    )
    assert "wait_for_telegram_bot_ready" in start_block
    assert '"$TELEGRAM_BOT_PID" "${VIVENTIUM_TELEGRAM_START_READY_RETRIES:-30}"' in start_block
    assert 'telegram_bot_ready "$telegram_pid"' in watchdog_block
    assert 'os.environ.get("VIVENTIUM_TELEGRAM_READY_FILE")' in bot_text
    assert "_write_telegram_ready_marker()" in bot_text


def test_launcher_includes_managed_local_telegram_bot_api_runtime() -> None:
    script_text = START_SCRIPT_PATH.read_text(encoding="utf-8")

    assert "start_telegram_local_bot_api() {" in script_text
    assert "stop_telegram_local_bot_api() {" in script_text
    assert "ensure_telegram_local_bot_api_hosted_logout() {" in script_text
    assert 'TELEGRAM_LOCAL_BOT_API_PID_FILE="$LOG_ROOT/telegram-local-bot-api.pid"' in script_text
    assert 'TELEGRAM_LOCAL_BOT_API_LOG_FILE="$LOG_DIR/telegram-local-bot-api.log"' in script_text
    assert '--local \\' in script_text
    assert '--http-port="$local_port" \\' in script_text
    assert 'https://api.telegram.org/bot${BOT_TOKEN}/logOut' in script_text


def test_launcher_defines_local_telegram_stop_helper_before_stop_path_calls_it() -> None:
    script_text = START_SCRIPT_PATH.read_text(encoding="utf-8")

    definition_line = first_line_number_containing(script_text, "stop_telegram_local_bot_api() {")
    invocation_line = first_line_number_containing(script_text, "  stop_telegram_local_bot_api")

    assert definition_line < invocation_line
