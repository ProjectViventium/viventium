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


def test_ensure_telegram_media_prereqs_installs_ffmpeg_via_brew(tmp_path: Path) -> None:
    script_text = START_SCRIPT_PATH.read_text(encoding="utf-8")
    function_def = extract_shell_function(script_text, "ensure_telegram_media_prereqs")
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


def test_start_telegram_bot_checks_media_prereqs_before_launch() -> None:
    script_text = START_SCRIPT_PATH.read_text(encoding="utf-8")

    assert "if ! ensure_telegram_media_prereqs; then" in script_text
    assert "Telegram bot cannot start without ffmpeg for supported voice/video media" in script_text
    assert "if ! start_telegram_local_bot_api; then" in script_text


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
