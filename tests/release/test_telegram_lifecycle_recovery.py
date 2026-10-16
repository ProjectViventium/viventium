"""Causal bridge recovery checks; all processes and state here are synthetic."""
from __future__ import annotations

import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / 'viventium_v0_4/viventium-librechat-start.sh'
CLI = ROOT / 'bin/viventium'


def function(path: Path, name: str) -> str:
    text = path.read_text()
    start = text.index(f'{name}() {{\n')
    next_function = re.search(r'\n[A-Za-z_][A-Za-z_0-9]*\(\) \{\n', text[start + 1:])
    assert next_function is not None
    return text[start:start + 1 + next_function.start()] + '\n'


def shell(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(['bash', '-c', 'set -euo pipefail\n' + script], text=True,
                          capture_output=True, timeout=15)


def test_log_rotation_retains_prior_runs_without_touching_a_live_owner(tmp_path: Path) -> None:
    log = tmp_path / 'telegram_bot.log'
    log.write_text('previous failure\n')
    prefix = (f'PYTHON_BIN={shlex.quote(sys.executable)}\n'
              f'VIVENTIUM_CORE_DIR={shlex.quote(str(ROOT))}\n'
              f'LOG_DIR={shlex.quote(str(tmp_path))}\n'
              + function(LAUNCHER, 'prepare_telegram_bot_log'))
    result = shell(prefix + 'prepare_telegram_bot_log\n')
    assert result.returncode == 0, result.stderr
    assert log.with_name(log.name + '.1').read_text() == 'previous failure\n'
    for run in range(4):
        log.write_text(f'run {run}\n')
        result = shell(prefix + 'prepare_telegram_bot_log\n')
        assert result.returncode == 0, result.stderr
    assert log.with_name(log.name + '.1').read_text() == 'run 3\n'
    assert log.with_name(log.name + '.3').read_text() == 'run 1\n'
    source = function(LAUNCHER, 'start_telegram_bot')
    assert source.index('telegram_handoff_action" == "already-running') < source.index('prepare_telegram_bot_log')
    assert source.index('prepare_telegram_bot_log') < source.index('launchctl submit')
    assert 'nohup "${telegram_launch_program[@]}" >>"$LOG_DIR/telegram_bot.log"' in source


def test_log_rotation_refuses_symlink_without_modifying_target(tmp_path: Path) -> None:
    target = tmp_path / 'private-target'
    target.write_text('untouched\n')
    (tmp_path / 'telegram_bot.log').symlink_to(target)
    result = shell(f'PYTHON_BIN={shlex.quote(sys.executable)}\n'
                   f'VIVENTIUM_CORE_DIR={shlex.quote(str(ROOT))}\n'
                   f'LOG_DIR={shlex.quote(str(tmp_path))}\n'
                   + function(LAUNCHER, 'prepare_telegram_bot_log')
                   + 'prepare_telegram_bot_log\n')
    assert result.returncode == 78
    assert target.read_text() == 'untouched\n'


def test_component_integrity_failure_is_nonretryable_before_bot_mutation(tmp_path: Path) -> None:
    selection = tmp_path / 'selection.json'
    selection.write_text('{}\n')
    result = shell(function(LAUNCHER, 'start_telegram_bot') + f'''
START_TELEGRAM=true
TELEGRAM_BOT_DEFERRED_PID_FILE={shlex.quote(str(tmp_path / 'deferred.pid'))}
TELEGRAM_BOT_DEFERRED_MARKER_FILE={shlex.quote(str(tmp_path / 'deferred.marker'))}
TELEGRAM_BOT_READY_FILE={shlex.quote(str(tmp_path / 'ready'))}
TELEGRAM_COMPONENT_SELECTION_FILE={shlex.quote(str(selection))}
TELEGRAM_COMPONENT_TOOL=synthetic-component
VIVENTIUM_APP_SUPPORT_ROOT={shlex.quote(str(tmp_path))}
LC_API_URL=http://127.0.0.1:1
load_local_qa_runtime_control() {{ :; }}
wait_for_http() {{ return 0; }}
detached_start_requested() {{ return 0; }}
log_error() {{ printf '%s\\n' "$*"; }}
PYTHON_BIN=failed_component
failed_component() {{ return 4; }}
if start_telegram_bot; then exit 99; else printf 'status=%s\\n' "$?"; fi
''')
    assert result.returncode == 0, result.stderr
    assert 'status=78' in result.stdout
    assert 'integrity verification' in result.stdout


@pytest.mark.parametrize(('first_status', 'calls'), [(78, 1), (1, 2)])
def test_watchdog_stops_nonretryable_loop_but_retries_transient_failure(
    tmp_path: Path, first_status: int, calls: int,
) -> None:
    counter = tmp_path / 'calls'
    result = shell(function(LAUNCHER, 'telegram_bot_watchdog_exited')
                   + function(LAUNCHER, 'start_telegram_bot_watchdog') + f'''
START_TELEGRAM=true
TELEGRAM_BOT_PID_FILE={shlex.quote(str(tmp_path / 'bot.pid'))}
TELEGRAM_BOT_WATCHDOG_PID_FILE={shlex.quote(str(tmp_path / 'watchdog.pid'))}
LOG_DIR={shlex.quote(str(tmp_path))}
VIVENTIUM_TELEGRAM_WATCHDOG_INTERVAL_S=0.01
VIVENTIUM_TELEGRAM_WATCHDOG_FAILURE_THRESHOLD=1
stop_telegram_bot_watchdog() {{ :; }}
read_pid_file() {{ cat "$1" 2>/dev/null || true; }}
telegram_poller_is_ready() {{ return 1; }}
telegram_bot_ready() {{ return 1; }}
detached_start_requested() {{ return 1; }}
log_info() {{ printf 'INFO %s\\n' "$*"; }}
log_warn() {{ printf 'WARN %s\\n' "$*"; }}
log_error() {{ printf 'ERROR %s\\n' "$*"; }}
start_telegram_bot() {{
  n=0
  [[ ! -f {shlex.quote(str(counter))} ]] || n=$(cat {shlex.quote(str(counter))})
  n=$((n + 1))
  printf '%s\\n' "$n" > {shlex.quote(str(counter))}
  if [[ "$n" == 1 ]]; then return {first_status}; fi
  return 78
}}
start_telegram_bot_watchdog
pid=$(cat "$TELEGRAM_BOT_WATCHDOG_PID_FILE")
if wait "$pid"; then exit 99; else printf 'exit=%s\\n' "$?"; fi
''')
    assert result.returncode == 0, result.stderr
    assert 'exit=78' in result.stdout
    assert int(counter.read_text()) == calls
    assert not (tmp_path / 'watchdog.pid').exists()
    log = (tmp_path / 'telegram_bot_watchdog.log').read_text()
    assert 'complete runtime start' in log
    assert 'exited (status: 78)' in log


@pytest.mark.parametrize(('enabled', 'bot', 'watchdog', 'missing'), [
    (False, False, False, False),
    (True, True, False, False),
    (True, False, True, False),
    (True, False, False, True),
])
def test_missing_recovery_owner_requires_both_bridge_and_watchdog_absent(
    enabled: bool, bot: bool, watchdog: bool, missing: bool,
) -> None:
    result = shell(function(CLI, 'telegram_recovery_owner_missing') + f'''
runtime_env_true() {{ return {0 if enabled else 1}; }}
runtime_pid_file_running() {{
  case "$1" in
    telegram_bot.pid) return {0 if bot else 1};;
    telegram_bot_watchdog.pid) return {0 if watchdog else 1};;
    *) exit 99;;
  esac
}}
if telegram_recovery_owner_missing; then printf missing; else printf owned; fi
''')
    assert result.returncode == 0, result.stderr
    assert result.stdout == ('missing' if missing else 'owned')


@pytest.mark.parametrize(('claim', 'missing', 'healthy', 'launch'), [
    (True, True, False, False),
    (False, False, False, False),
    (False, True, True, False),
    (False, True, False, True),
])
def test_existing_launcher_admits_recovery_only_after_startup_and_recovery_owners_end(
    tmp_path: Path, claim: bool, missing: bool, healthy: bool, launch: bool,
) -> None:
    config = tmp_path / 'config.yaml'
    config.write_text('version: 1\n')
    fake_python = tmp_path / 'fake-python'
    fake_python.write_text('#!/bin/sh\ncat >/dev/null\nprintf "4242\\n"\n')
    fake_python.chmod(0o700)
    result = shell(function(CLI, 'launch_stack_detached') + f'''
APP_SUPPORT_DIR={shlex.quote(str(tmp_path))}
CONFIG_FILE={shlex.quote(str(config))}
RUNTIME_DIR={shlex.quote(str(tmp_path / 'runtime'))}
REPO_ROOT={shlex.quote(str(ROOT))}
LOCK_FILE={shlex.quote(str(tmp_path / 'lock'))}
PYTHON_BIN={shlex.quote(str(fake_python))}
ensure_app_support_layout() {{ mkdir -p "$1/logs"; }}
initialize_telegram_user_config_authority() {{ :; }}
user_surface_healthy() {{ return 0; }}
runtime_optional_surfaces_healthy() {{ return {0 if healthy else 1}; }}
postcommit_api_finalization_ready() {{ return 0; }}
runtime_start_claim_active() {{ return {0 if claim else 1}; }}
detached_launch_process_group_running() {{ return 0; }}
telegram_recovery_owner_missing() {{ return {0 if missing else 1}; }}
is_stack_running() {{ exit 97; }}
stop_stack_for_upgrade() {{ exit 98; }}
capture_detached_start_log_offset() {{ :; }}
launch_stack_detached
''')
    assert result.returncode == 0, result.stderr
    assert ('Launched Viventium in the background' in result.stdout) is launch
    assert ('repairing through the current runtime owner' in result.stdout) is launch


def test_lifecycle_messages_use_utc_timestamps() -> None:
    result = shell('CYAN= YELLOW= RED= GREEN= NC=\n' + ''.join(
        function(LAUNCHER, 'log_' + level) for level in ('info', 'warn', 'error', 'success')
    ) + 'log_info start\nlog_warn retry\nlog_error rejected\nlog_success ready\n')
    assert result.returncode == 0, result.stderr
    import re
    assert len(result.stdout.splitlines()) == 4
    for line in result.stdout.splitlines():
        assert re.fullmatch(r'\[viventium\] \[\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ\] \w+', line)


@pytest.mark.parametrize(('helper_status', 'expected'), [(2, 78), (1, 1)])
def test_handoff_argument_failure_preserves_config_class_and_cleanup(helper_status: int, expected: int) -> None:
    source = function(LAUNCHER, 'start_telegram_bot')
    start = source.index('  local telegram_handoff_status=0\n')
    end = source.index('  telegram_handoff_action=', start)
    result = shell(f'''attempt() {{
{source[start:end]}
}}
PYTHON_BIN=synthetic_helper
TELEGRAM_POLLER_HANDOFF_HELPER=helper
telegram_handoff_args=(prepare)
synthetic_helper() {{ return {helper_status}; }}
log_error() {{ :; }}
cleanup_current_telegram_launch_package() {{ printf 'package-cleaned\\n'; }}
restore_telegram_env() {{ printf 'environment-restored\\n'; }}
popd() {{ :; }}
if attempt; then exit 99; else printf 'status=%s\\n' "$?"; fi
''')
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ['package-cleaned', 'environment-restored', f'status={expected}']


@pytest.mark.parametrize('empty_current', [True, False])
def test_empty_or_missing_bot_log_does_not_evict_prior_failure(tmp_path: Path, empty_current: bool) -> None:
    log = tmp_path / 'telegram_bot.log'
    if empty_current:
        log.touch()
    previous = log.with_name(log.name + '.1')
    previous.write_text('original failure\n')
    result = shell(f'PYTHON_BIN={shlex.quote(sys.executable)}\n'
                   f'VIVENTIUM_CORE_DIR={shlex.quote(str(ROOT))}\n'
                   f'LOG_DIR={shlex.quote(str(tmp_path))}\n'
                   + function(LAUNCHER, 'prepare_telegram_bot_log')
                   + 'prepare_telegram_bot_log\nprepare_telegram_bot_log\n')
    assert result.returncode == 0, result.stderr
    assert previous.read_text() == 'original failure\n'
    assert not log.with_name(log.name + '.2').exists()


def test_temporary_log_rotation_io_error_keeps_diagnostics_and_remains_retryable(tmp_path: Path) -> None:
    modules = tmp_path / 'source/scripts/viventium'
    modules.mkdir(parents=True)
    (modules / 'native_runtime.py').write_text('class RuntimeError_(RuntimeError): pass\n'
        'def rotate_log(*args, **kwargs): raise PermissionError("synthetic transient I/O")\n')
    log = tmp_path / 'telegram_bot.log'
    log.write_text('prior failure\n')
    result = shell(f'PYTHON_BIN={shlex.quote(sys.executable)}\n'
                   f'VIVENTIUM_CORE_DIR={shlex.quote(str(tmp_path / "source"))}\n'
                   f'LOG_DIR={shlex.quote(str(tmp_path))}\n'
                   + function(LAUNCHER, 'prepare_telegram_bot_log')
                   + 'prepare_telegram_bot_log\n')
    assert result.returncode == 1
    assert log.read_text() == 'prior failure\n'
    assert 'PermissionError' in result.stderr
    assert 'synthetic transient I/O' not in result.stderr


@pytest.mark.parametrize(('recorded', 'removed'), [('123', True), ('456', False)])
def test_watchdog_exit_clears_only_its_own_pid_record(tmp_path: Path, recorded: str, removed: bool) -> None:
    marker = tmp_path / 'watchdog.pid'
    marker.write_text(recorded + '\n')
    result = shell(function(LAUNCHER, 'telegram_bot_watchdog_exited') + f'''
TELEGRAM_BOT_WATCHDOG_PID_FILE={shlex.quote(str(marker))}
read_pid_file() {{ cat "$1"; }}
log_info() {{ :; }}
telegram_bot_watchdog_exited 78 123
''')
    assert result.returncode == 0, result.stderr
    assert marker.exists() is not removed


@pytest.mark.parametrize(('repo_matches', 'group_matches', 'owned'), [
    (False, True, False), (True, False, False), (True, True, True),
])
def test_watchdog_pid_reuse_requires_existing_repo_and_group_identity(
    tmp_path: Path, repo_matches: bool, group_matches: bool, owned: bool,
) -> None:
    (tmp_path / 'telegram_bot_watchdog.pid').write_text('123\n')
    result = shell(function(CLI, 'runtime_pid_file_running') + f'''
APP_SUPPORT_DIR={shlex.quote(str(tmp_path))}
read_generated_env_value() {{ printf '%s\\n' {shlex.quote(str(tmp_path))}; }}
pid_is_running() {{ return 0; }}
pid_matches_repo_scope() {{ return {0 if repo_matches else 1}; }}
pid_matches_runtime_process_group() {{ return {0 if group_matches else 1}; }}
if runtime_pid_file_running telegram_bot_watchdog.pid true; then printf owned; else printf absent; fi
''')
    assert result.returncode == 0, result.stderr
    assert result.stdout == ('owned' if owned else 'absent')


def test_stale_watchdog_record_of_unrelated_real_process_does_not_block_recovery(tmp_path: Path) -> None:
    process = subprocess.Popen(['/bin/sleep', '30'], start_new_session=True)
    try:
        (tmp_path / 'telegram_bot_watchdog.pid').write_text(f'{process.pid}\n')
        script = ''.join(function(CLI, name) for name in (
            'runtime_pid_file_running', 'pid_is_running', 'pid_matches_repo_scope',
            'pid_matches_runtime_process_group'))
        result = shell(script + f'''
APP_SUPPORT_DIR={shlex.quote(str(tmp_path))}
REPO_ROOT={shlex.quote(str(tmp_path / 'source'))}
read_generated_env_value() {{ printf '%s\\n' {shlex.quote(str(tmp_path))}; }}
read_detached_launch_process_group() {{ printf '%s\\n' {process.pid}; }}
if runtime_pid_file_running telegram_bot_watchdog.pid; then printf 'live\\n'; fi
if runtime_pid_file_running telegram_bot_watchdog.pid true; then printf owned; else printf absent; fi
''')
        assert result.returncode == 0, result.stderr
        assert result.stdout == 'live\nabsent'
        assert process.poll() is None
    finally:
        process.terminate()
        process.wait(timeout=5)
