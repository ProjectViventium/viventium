"""Stopping the stack must boot out the Telegram launchd job this runtime registered.

The launchd label is compiled per runtime instance. When a stop runs from another entry path, the
label can differ or the owner receipt can be missing, so the label-only teardown returns early while
launchd's KeepAlive resurrects the bot. That surviving bot is the "Telegram preference writer still
active after shutdown" that aborts a later activation and leaves the product down. The fallback
identifies jobs by this runtime's state root instead and never reads the job environment.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"


def _function_body(text: str, name: str) -> str:
    start = text.index(f"{name}() {{")
    end = text.index("\n}\n", start)
    return text[start:end]


def test_scoped_telegram_launchd_teardown_exists_and_matches_by_state_root() -> None:
    text = LAUNCHER.read_text(encoding="utf-8")
    body = _function_body(text, "stop_scoped_telegram_launchctl_jobs")
    assert 'scope_root="${VIVENTIUM_STATE_ROOT:-}"' in body
    assert "launchctl bootout" in body
    assert re.search(r"grep -E '\^ai\\\.viventium\\\.telegram-bot", body), "must enumerate only Viventium Telegram labels"
    # Only path lines are inspected; the inherited environment block is never matched or echoed.
    assert "stdout path|stderr path" in body
    assert "environment" not in body.split("job_paths=")[1].split("|| true")[0]


def test_label_only_teardown_falls_back_to_scoped_teardown() -> None:
    text = LAUNCHER.read_text(encoding="utf-8")
    body = _function_body(text, "stop_telegram_launchctl_job")
    assert body.count("stop_scoped_telegram_launchctl_jobs") == 2, "both early exits must fall back"
    assert "migrate_legacy_telegram_launchctl_receipt || return 0" not in body


def _extract_shell_function(text: str, name: str) -> str:
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


def _launchctl_stub(scope_root: Path, log: Path) -> str:
    return f"""
launchctl() {{
  case "$1" in
    list)
      printf 'PID\\tStatus\\tLabel\\n'
      printf -- '-\\t0\\tai.viventium.telegram-bot.other\\n'
      printf '123\\t0\\tai.viventium.telegram-bot\\n'
      printf -- '-\\t0\\tcom.example.unrelated\\n'
      ;;
    print)
      case "$2" in
        *ai.viventium.telegram-bot.other)
          printf 'ai.viventium.telegram-bot.other = {{\\n'
          printf '\\tstdout path = {scope_root}/logs/telegram_bot.log\\n'
          printf '\\tstderr path = {scope_root}/logs/telegram_bot.log\\n'
          printf '\\tenvironment = {{\\n\\t\\tSECRET_TOKEN_OTHER = do-not-echo\\n\\t}}\\n}}\\n'
          ;;
        *)
          printf 'ai.viventium.telegram-bot = {{\\n'
          printf '\\tstdout path = /elsewhere/logs/telegram_bot.log\\n'
          printf '\\tenvironment = {{\\n\\t\\tSECRET_TOKEN_BARE = do-not-echo\\n\\t}}\\n}}\\n'
          ;;
      esac
      ;;
    bootout|remove)
      printf '%s\\n' "$*" >> {log}
      ;;
  esac
  return 0
}}
"""


def _run_scoped_teardown(tmp_path: Path, *, state_root: str) -> tuple[subprocess.CompletedProcess[str], Path]:
    scope_root = tmp_path / "state"
    log = tmp_path / "launchctl.log"
    function = _extract_shell_function(LAUNCHER.read_text(encoding="utf-8"), "stop_scoped_telegram_launchctl_jobs")
    script = (
        "set -uo pipefail\n"
        "uname() { printf 'Darwin\\n'; }\n"
        "id() { printf '501\\n'; }\n"
        "log_warn() { printf 'WARN %s\\n' \"$*\"; }\n"
        f"VIVENTIUM_STATE_ROOT={state_root}\n"
        f"{_launchctl_stub(scope_root, log)}"
        f"{function}"
        "stop_scoped_telegram_launchctl_jobs\n"
    )
    completed = subprocess.run(["bash", "-c", script], text=True, capture_output=True, check=False)
    return completed, log


def test_scoped_teardown_boots_out_only_jobs_logging_to_this_state_root(tmp_path: Path) -> None:
    completed, log = _run_scoped_teardown(tmp_path, state_root=str(tmp_path / "state"))

    assert completed.returncode == 0, completed.stderr
    commands = log.read_text(encoding="utf-8") if log.exists() else ""
    assert "bootout gui/501/ai.viventium.telegram-bot.other" in commands
    assert "bootout gui/501/ai.viventium.telegram-bot\n" not in commands
    assert "com.example.unrelated" not in commands
    assert (
        "Stopping Telegram launchctl job registered for this runtime state root: ai.viventium.telegram-bot.other"
        in completed.stdout
    )
    assert "SECRET_TOKEN" not in completed.stdout + completed.stderr


def test_scoped_teardown_is_a_no_op_without_a_state_root(tmp_path: Path) -> None:
    completed, log = _run_scoped_teardown(tmp_path, state_root='""')

    assert completed.returncode == 0, completed.stderr
    assert not log.exists()


def test_scoped_teardown_ignores_a_sibling_root_that_only_shares_the_prefix(tmp_path: Path) -> None:
    # `<root>-other` is a different runtime; substring matching would have torn its job down.
    scope_root = tmp_path / "state"
    sibling_root = tmp_path / "state-other"
    log = tmp_path / "launchctl.log"
    function = _extract_shell_function(LAUNCHER.read_text(encoding="utf-8"), "stop_scoped_telegram_launchctl_jobs")
    script = (
        "set -uo pipefail\n"
        "uname() { printf 'Darwin\\n'; }\n"
        "id() { printf '501\\n'; }\n"
        "log_warn() { printf 'WARN %s\\n' \"$*\"; }\n"
        f"VIVENTIUM_STATE_ROOT={scope_root}\n"
        f"{_launchctl_stub(sibling_root, log)}"
        f"{function}"
        "stop_scoped_telegram_launchctl_jobs\n"
    )
    completed = subprocess.run(["bash", "-c", script], text=True, capture_output=True, check=False)
    assert completed.returncode == 0, completed.stderr
    commands = log.read_text(encoding="utf-8") if log.exists() else ""
    assert "bootout" not in commands
    assert "Stopping Telegram launchctl job" not in completed.stdout
