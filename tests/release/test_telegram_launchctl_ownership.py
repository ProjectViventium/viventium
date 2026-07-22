from __future__ import annotations

import subprocess
import sys
import json
import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"


def extract_shell_function(text: str, name: str) -> str:
    lines = text.splitlines()
    start = next(index for index, line in enumerate(lines) if line.strip() == f"{name}() {{")
    depth = 0
    collected: list[str] = []
    for line in lines[start:]:
        collected.append(line)
        depth += line.count("{")
        depth -= line.count("}")
        if depth == 0:
            break
    return "\n".join(collected) + "\n"


def test_disabled_telegram_without_owned_receipt_never_touches_launchctl(tmp_path: Path) -> None:
    launcher_source = LAUNCHER.read_text(encoding="utf-8")
    receipt_path_function = extract_shell_function(launcher_source, "telegram_launchctl_receipt_file")
    receipt_valid_function = extract_shell_function(launcher_source, "telegram_launchctl_receipt_valid")
    migrate_function = extract_shell_function(launcher_source, "migrate_legacy_telegram_launchctl_receipt")
    stop_function = extract_shell_function(launcher_source, "stop_telegram_launchctl_job")
    launchctl_log = tmp_path / "launchctl.log"

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                "START_TELEGRAM=false\n"
                "TELEGRAM_BOT_LAUNCHCTL_LABEL=ai.viventium.telegram-bot\n"
                f"VIVENTIUM_STATE_ROOT={str(tmp_path / 'state')!r}\n"
                f"VIVENTIUM_APP_SUPPORT_ROOT={str(tmp_path / 'app-support')!r}\n"
                f"PYTHON_BIN={str(Path('/usr/bin/python3'))!r}\n"
                f"TELEGRAM_BOT_PID_FILE={str(tmp_path / 'state/telegram_bot.pid')!r}\n"
                f"TELEGRAM_DIR_PRIMARY={str(tmp_path / 'telegram-primary')!r}\n"
                f"TELEGRAM_DIR_FALLBACK={str(tmp_path / 'telegram-fallback')!r}\n"
                "uname() { printf 'Darwin\\n'; }\n"
                "id() { printf '501\\n'; }\n"
                "log_warn() { :; }\n"
                "read_pid_file() { return 0; }\n"
                "pid_matches_scope() { return 1; }\n"
                "write_telegram_launchctl_receipt() { return 1; }\n"
                "launchctl() {\n"
                f"  printf '%s\\n' \"$*\" >> {str(launchctl_log)!r}\n"
                "  return 0\n"
                "}\n"
                f"{receipt_path_function}{receipt_valid_function}{migrate_function}{stop_function}"
                "stop_telegram_launchctl_job\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert not launchctl_log.exists()


def test_owned_telegram_receipt_allows_targeted_launchctl_cleanup(tmp_path: Path) -> None:
    launcher_source = LAUNCHER.read_text(encoding="utf-8")
    receipt_path_function = extract_shell_function(launcher_source, "telegram_launchctl_receipt_file")
    receipt_valid_function = extract_shell_function(launcher_source, "telegram_launchctl_receipt_valid")
    migrate_function = extract_shell_function(launcher_source, "migrate_legacy_telegram_launchctl_receipt")
    stop_function = extract_shell_function(launcher_source, "stop_telegram_launchctl_job")
    launchctl_log = tmp_path / "launchctl.log"
    app_support = tmp_path / "app-support"
    state_root = tmp_path / "state"
    state_root.mkdir()
    receipt = state_root / "telegram-launchctl-owner.json"
    receipt.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "app_support_dir": str(app_support.resolve()),
                "label": "ai.viventium.telegram-bot",
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    os.chmod(receipt, 0o600)

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                "START_TELEGRAM=true\n"
                "TELEGRAM_BOT_LAUNCHCTL_LABEL=ai.viventium.telegram-bot\n"
                f"VIVENTIUM_STATE_ROOT={str(state_root)!r}\n"
                f"VIVENTIUM_APP_SUPPORT_ROOT={str(app_support)!r}\n"
                f"PYTHON_BIN={sys.executable!r}\n"
                f"TELEGRAM_BOT_PID_FILE={str(state_root / 'telegram_bot.pid')!r}\n"
                f"TELEGRAM_DIR_PRIMARY={str(tmp_path / 'telegram-primary')!r}\n"
                f"TELEGRAM_DIR_FALLBACK={str(tmp_path / 'telegram-fallback')!r}\n"
                "uname() { printf 'Darwin\\n'; }\n"
                "id() { printf '501\\n'; }\n"
                "log_warn() { :; }\n"
                "read_pid_file() { return 0; }\n"
                "pid_matches_scope() { return 1; }\n"
                "write_telegram_launchctl_receipt() { return 1; }\n"
                "launchctl() {\n"
                f"  printf '%s\\n' \"$*\" >> {str(launchctl_log)!r}\n"
                "  return 0\n"
                "}\n"
                f"{receipt_path_function}{receipt_valid_function}{migrate_function}{stop_function}"
                "stop_telegram_launchctl_job\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    commands = launchctl_log.read_text(encoding="utf-8")
    assert "print gui/501/ai.viventium.telegram-bot" in commands
    assert "bootout gui/501/ai.viventium.telegram-bot" in commands
    assert not receipt.exists()
