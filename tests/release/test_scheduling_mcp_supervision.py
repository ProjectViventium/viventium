from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEDULING_ROOT = (
    REPO_ROOT / "viventium_v0_4" / "LibreChat" / "viventium" / "MCPs" / "scheduling-cortex"
)
LOOPBACK_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
if str(SCHEDULING_ROOT) not in sys.path:
    sys.path.insert(0, str(SCHEDULING_ROOT))


def extract_shell_function(source: str, name: str) -> str:
    start = source.index(f"{name}() {{")
    collected: list[str] = []
    depth = 0
    for line in source[start:].splitlines():
        collected.append(line)
        depth += line.count("{")
        depth -= line.count("}")
        if depth == 0:
            break
    return "\n".join(collected) + "\n"


def wait_for_scheduler_health(port: int, *, timeout: float = 10.0) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with LOOPBACK_OPENER.open(
                f"http://127.0.0.1:{port}/health",
                timeout=0.5,
            ) as response:
                return json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, json.JSONDecodeError):
            time.sleep(0.05)
    raise AssertionError("synthetic scheduler did not become healthy")


def test_scheduling_mcp_has_health_checked_watchdog_contract() -> None:
    launcher_text = (REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh").read_text(
        encoding="utf-8"
    )

    assert (
        'SCHEDULING_MCP_WATCHDOG_PID_FILE="$LOG_ROOT/scheduling_cortex_mcp_watchdog.pid"'
        in launcher_text
    )
    assert (
        'SCHEDULING_MCP_WATCHDOG_LOG_FILE="$LOG_DIR/scheduling_cortex_mcp_watchdog.log"'
        in launcher_text
    )
    assert "scheduling_mcp_healthy() {" in launcher_text
    assert "restart_scheduling_mcp_runtime() {" in launcher_text
    assert "start_scheduling_mcp_watchdog() {" in launcher_text
    assert "stop_scheduling_mcp_watchdog() {" in launcher_text
    assert launcher_text.count("curl --noproxy '*' -fsS --max-time 3") == 2
    assert 'scheduling_python="$PWD/.venv/bin/python"' in launcher_text
    assert '"$scheduling_python" -m scheduling_cortex.server' in launcher_text
    assert (
        'SCHEDULING_MCP_INSTALLED_DIR="$VIVENTIUM_APP_SUPPORT_ROOT/runtime/components/scheduling-cortex"'
        in launcher_text
    )
    assert (
        'if [[ -n "${VIVENTIUM_HELPER_CORE_ROOT:-}" ]]; then\n'
        '  SCHEDULING_MCP_DIR="$SCHEDULING_MCP_INSTALLED_DIR"'
        in launcher_text
    )
    assert (
        'SCHEDULING_MCP_DIR="${VIVENTIUM_SCHEDULING_MCP_DIR:-$SCHEDULING_MCP_SOURCE_DIR}"'
        in launcher_text
    )
    assert (
        "Scheduling Cortex MCP port $SCHEDULING_MCP_PORT is occupied but health check failed; "
        "attempting scoped repair"
        in launcher_text
    )
    assert "scheduling_mcp_matches_runtime() {" in launcher_text
    assert "db_path_sha256" in launcher_text
    assert (
        "Scheduling Cortex MCP port $SCHEDULING_MCP_PORT is healthy but belongs to a different "
        "runtime or an older health contract; refusing to claim it"
        in launcher_text
    )
    assert "leaving the other runtime untouched" in launcher_text
    assert "leaving it running during this runtime stop" in launcher_text
    stop_block = extract_shell_function(
        launcher_text,
        "stop_scheduling_mcp_for_runtime",
    )
    assert (
        '! -d "$SCHEDULING_MCP_INSTALLED_DIR"'
        not in stop_block.split("if ! port_has_listener", 1)[0]
    )
    assert (
        'kill_port_listeners "$SCHEDULING_MCP_PORT" "$SCHEDULING_MCP_INSTALLED_DIR"'
        in stop_block
    )
    assert stop_block.index("scheduler_matches_runtime=true") < stop_block.index(
        'kill_port_listeners "$SCHEDULING_MCP_PORT" "$SCHEDULING_MCP_INSTALLED_DIR"'
    )
    launcher_without_identity_stop = launcher_text.replace(stop_block, "", 1)
    assert (
        'stop_pid_file_scoped "$SCHEDULING_MCP_PID_FILE"'
        not in launcher_without_identity_stop
    )
    assert (
        'kill_port_listeners "$SCHEDULING_MCP_PORT"'
        not in launcher_without_identity_stop
    )
    assert 'kill "${SCHEDULING_MCP_PID' not in launcher_without_identity_stop
    restart_block = launcher_text.split(
        "restart_scheduling_mcp_runtime() {",
        1,
    )[1].split("start_scheduling_mcp_watchdog() {", 1)[0]
    cleanup_block = launcher_text.split("cleanup() {", 1)[1].split(
        "trap cleanup INT TERM EXIT",
        1,
    )[0]
    stop_running_block = extract_shell_function(
        launcher_text,
        "stop_running_services",
    )
    start_block = launcher_text.split("start_scheduling_mcp() {", 1)[1].split(
        "start_voice_gateway() {",
        1,
    )[0]
    assert "stop_scheduling_mcp_for_runtime" in restart_block
    assert "stop_scheduling_mcp_for_runtime" in cleanup_block
    assert start_block.count("stop_scheduling_mcp_for_runtime") == 2
    assert 'scheduling_stop_failed="$SCHEDULING_MCP_STOP_FAILED"' in stop_running_block
    assert (
        'if [[ "$scheduling_stop_failed" == "true" ]]; then'
        in stop_running_block
    )
    assert "Scheduling Cortex MCP stop failed" in stop_running_block
    assert "uv run python -m scheduling_cortex.server" not in launcher_text
    assert (
        launcher_text.index("refusing to claim it")
        < launcher_text.index(
            "Scheduling Cortex MCP port $SCHEDULING_MCP_PORT is occupied but unhealthy - restarting"
        )
    )
    assert 'wait_for_scheduling_mcp_runtime "Scheduling Cortex MCP"' in launcher_text
    assert 'start_scheduling_mcp_watchdog' in launcher_text
    assert 'stop_scheduling_mcp_watchdog' in launcher_text
    assert "trap - EXIT" in launcher_text


@pytest.mark.parametrize(
    ("health_kind", "installed_present", "expected_scopes", "listener_after"),
    [
        ("matching", True, ["source component", "installed component"], "0"),
        ("matching", False, ["source component", "installed component"], "0"),
        ("mismatching", False, [], "1"),
        ("empty", False, ["source component"], "1"),
    ],
)
def test_scheduler_stop_broadens_to_installed_scope_only_after_identity_match(
    tmp_path: Path,
    health_kind: str,
    installed_present: bool,
    expected_scopes: list[str],
    listener_after: str,
) -> None:
    launcher_text = (
        REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"
    ).read_text(encoding="utf-8")
    function = extract_shell_function(
        launcher_text,
        "stop_scheduling_mcp_for_runtime",
    )
    source_dir = tmp_path / "source component"
    installed_dir = tmp_path / "installed component"
    if installed_present:
        installed_dir.mkdir()
    db_path = tmp_path / "state" / "schedules.db"
    expected_hash = hashlib.sha256(str(db_path.resolve()).encode("utf-8")).hexdigest()
    if health_kind == "matching":
        health = json.dumps({"status": "ok", "db_path_sha256": expected_hash})
    elif health_kind == "mismatching":
        health = json.dumps({"status": "ok", "db_path_sha256": "0" * 64})
    else:
        health = ""
    completed = subprocess.run(
        [
            "bash",
            "-c",
            (
                "set -euo pipefail\n"
                "LISTENER=1\n"
                "stop_pid_file_scoped() { :; }\n"
                "port_has_listener() { [[ \"$LISTENER\" == 1 ]]; }\n"
                "curl() { printf '%s' \"$HEALTH_PAYLOAD\"; }\n"
                "log_warn() { printf 'warn:%s\\n' \"$1\"; }\n"
                "kill_port_listeners() { "
                "printf 'kill:%s\\n' \"$2\"; "
                "if [[ \"$2\" == \"$ACTIVE_SCOPE\" ]]; then LISTENER=0; fi; "
                "}\n"
                f"{function}"
                "stop_scheduling_mcp_for_runtime\n"
                "printf 'listener:%s\\n' \"$LISTENER\"\n"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "ACTIVE_SCOPE": str(installed_dir),
            "HEALTH_PAYLOAD": health,
            "PYTHON_BIN": sys.executable,
            "SCHEDULING_DB_PATH": str(db_path),
            "SCHEDULING_MCP_DIR": str(source_dir),
            "SCHEDULING_MCP_INSTALLED_DIR": str(installed_dir),
            "SCHEDULING_MCP_PID_FILE": str(tmp_path / "scheduler.pid"),
            "SCHEDULING_MCP_PORT": "7110",
            "VIVENTIUM_SCHEDULING_MCP_STOP_SETTLE_INTERVAL_S": "0.01",
            "VIVENTIUM_SCHEDULING_MCP_STOP_SETTLE_RETRIES": "1",
        },
    )

    assert completed.returncode == 0, completed.stderr
    killed_scopes = [
        Path(line.removeprefix("kill:")).name
        for line in completed.stdout.splitlines()
        if line.startswith("kill:")
    ]
    assert killed_scopes == expected_scopes
    assert completed.stdout.splitlines()[-1] == f"listener:{listener_after}"


def test_scheduler_stop_reports_survivor_without_errexit_truncating_caller(
    tmp_path: Path,
) -> None:
    launcher_text = (
        REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"
    ).read_text(encoding="utf-8")
    function = extract_shell_function(
        launcher_text,
        "stop_scheduling_mcp_for_runtime",
    )
    source_dir = tmp_path / "source component"
    installed_dir = tmp_path / "installed component"
    db_path = tmp_path / "state" / "schedules.db"
    expected_hash = hashlib.sha256(str(db_path.resolve()).encode("utf-8")).hexdigest()
    health = json.dumps({"status": "ok", "db_path_sha256": expected_hash})

    completed = subprocess.run(
        [
            "bash",
            "-c",
            (
                "set -euo pipefail\n"
                "LISTENER=1\n"
                "stop_pid_file_scoped() { :; }\n"
                "port_has_listener() { [[ \"$LISTENER\" == 1 ]]; }\n"
                "curl() { printf '%s' \"$HEALTH_PAYLOAD\"; }\n"
                "log_warn() { printf 'warn:%s\\n' \"$1\"; }\n"
                "kill_port_listeners() { printf 'kill:%s\\n' \"$2\"; }\n"
                f"{function}"
                "stop_scheduling_mcp_for_runtime\n"
                "printf 'teardown:completed\\n'\n"
                "if [[ \"$SCHEDULING_MCP_STOP_FAILED\" == true ]]; then "
                "STOP_RESULT=1; else STOP_RESULT=0; fi\n"
                "printf 'continued:%s:listener:%s:stop:%s\\n' "
                "\"$SCHEDULING_MCP_STOP_FAILED\" \"$LISTENER\" \"$STOP_RESULT\"\n"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "HEALTH_PAYLOAD": health,
            "PYTHON_BIN": sys.executable,
            "SCHEDULING_DB_PATH": str(db_path),
            "SCHEDULING_MCP_DIR": str(source_dir),
            "SCHEDULING_MCP_INSTALLED_DIR": str(installed_dir),
            "SCHEDULING_MCP_PID_FILE": str(tmp_path / "scheduler.pid"),
            "SCHEDULING_MCP_PORT": "7110",
            "VIVENTIUM_SCHEDULING_MCP_STOP_SETTLE_INTERVAL_S": "0.01",
            "VIVENTIUM_SCHEDULING_MCP_STOP_SETTLE_RETRIES": "1",
        },
    )

    assert completed.returncode == 0, completed.stderr
    killed_scopes = [
        Path(line.removeprefix("kill:")).name
        for line in completed.stdout.splitlines()
        if line.startswith("kill:")
    ]
    assert killed_scopes == ["source component", "installed component"]
    assert "still listening after identity-bound stop" in completed.stdout
    assert "teardown:completed" in completed.stdout
    assert completed.stdout.splitlines()[-1] == "continued:true:listener:1:stop:1"


@pytest.mark.parametrize(
    ("active_scope_kind", "expected_process", "expected_pid_file"),
    [
        ("installed", "0", "missing"),
        ("declared-source-helper", "0", "missing"),
        ("foreign", "1", "present"),
    ],
)
def test_scheduler_stop_handles_installed_pid_in_pre_bind_gap_without_touching_foreign_pid(
    tmp_path: Path,
    active_scope_kind: str,
    expected_process: str,
    expected_pid_file: str,
) -> None:
    launcher_text = (
        REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"
    ).read_text(encoding="utf-8")
    pid_helper = extract_shell_function(launcher_text, "stop_pid_file_scoped")
    stop_function = extract_shell_function(
        launcher_text,
        "stop_scheduling_mcp_for_runtime",
    )
    source_dir = tmp_path / "source component"
    installed_dir = tmp_path / "installed component"
    foreign_dir = tmp_path / "foreign component"
    if active_scope_kind == "installed":
        active_scope = installed_dir
        selected_dir = source_dir
    elif active_scope_kind == "declared-source-helper":
        active_scope = source_dir
        selected_dir = installed_dir
    else:
        active_scope = foreign_dir
        selected_dir = source_dir
    pid_file = tmp_path / "scheduler.pid"
    pid_file.write_text("4242\n", encoding="utf-8")

    completed = subprocess.run(
        [
            "bash",
            "-c",
            (
                "set -euo pipefail\n"
                "PROCESS=1\n"
                "ps() { [[ \"$PROCESS\" == 1 ]]; }\n"
                "pid_matches_scope() { [[ \"$2\" == \"$ACTIVE_SCOPE\" ]]; }\n"
                "port_has_listener() { return 1; }\n"
                "log_warn() { printf 'warn:%s\\n' \"$1\"; }\n"
                "kill_pids() { printf 'signal:%s\\n' \"$1\"; PROCESS=0; }\n"
                f"{pid_helper}"
                f"{stop_function}"
                "stop_scheduling_mcp_for_runtime\n"
                "if [[ -e \"$SCHEDULING_MCP_PID_FILE\" ]]; then PID_STATE=present; "
                "else PID_STATE=missing; fi\n"
                "printf 'final:%s:%s\\n' \"$PROCESS\" \"$PID_STATE\"\n"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "ACTIVE_SCOPE": str(active_scope),
            "PYTHON_BIN": sys.executable,
            "SCHEDULING_DB_PATH": str(tmp_path / "schedules.db"),
            "SCHEDULING_MCP_DIR": str(selected_dir),
            "SCHEDULING_MCP_INSTALLED_DIR": str(installed_dir),
            "SCHEDULING_MCP_PID_FILE": str(pid_file),
            "SCHEDULING_MCP_PORT": "7110",
            "SCHEDULING_MCP_SOURCE_DIR": str(source_dir),
        },
    )

    assert completed.returncode == 0, completed.stderr
    assert (
        completed.stdout.splitlines()[-1]
        == f"final:{expected_process}:{expected_pid_file}"
    )
    if active_scope_kind == "foreign":
        assert "signal:" not in completed.stdout


@pytest.mark.parametrize(
    ("scenario", "matching_identity", "expected_running"),
    [
        ("renamed-installed", True, False),
        ("renamed-installed", False, True),
        ("helper-selected-installed-source-process", True, False),
    ],
)
def test_scheduler_stop_handles_real_process_across_activation_scopes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
    matching_identity: bool,
    expected_running: bool,
) -> None:
    if not shutil.which("lsof"):
        pytest.skip("lsof is required for real scheduler ownership acceptance")

    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)

    launcher_text = (
        REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"
    ).read_text(encoding="utf-8")
    function_names = (
        "kill_pids",
        "read_pid_cwd",
        "normalize_scope_path",
        "path_is_trashed_checkout",
        "scope_component_signature",
        "pid_matches_trashed_scope_variant",
        "pid_matches_scope",
        "find_port_listener_pids",
        "kill_port_listeners",
        "port_has_listener",
        "stop_pid_file_scoped",
        "stop_scheduling_mcp_for_runtime",
    )
    functions = "".join(
        extract_shell_function(launcher_text, name) for name in function_names
    )
    common_text = (REPO_ROOT / "scripts" / "viventium" / "common.sh").read_text(
        encoding="utf-8"
    )
    functions = (
        extract_shell_function(common_text, "viventium_port_listener_active")
        + functions
    )

    installed_dir = tmp_path / "runtime" / "components" / "scheduling-cortex"
    backup_dir = tmp_path / ".runtime.viventium-backup-synthetic"
    source_dir = tmp_path / "source" / "scheduling-cortex"
    if scenario == "renamed-installed":
        process_root = installed_dir
        selected_dir = source_dir
    else:
        process_root = source_dir
        selected_dir = installed_dir
    process_root.mkdir(parents=True)
    db_path = tmp_path / "state" / "scheduling" / "schedules.db"
    db_path.parent.mkdir(parents=True)
    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE schedule_fixture (value TEXT NOT NULL)")
        connection.execute("INSERT INTO schedule_fixture VALUES ('preserve-me')")
    db_before = db_path.read_bytes()
    expected_hash = hashlib.sha256(str(db_path.resolve()).encode("utf-8")).hexdigest()
    served_hash = expected_hash if matching_identity else "0" * 64

    server_script = process_root / "server.py"
    server_script.write_text(
        """
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

payload = json.dumps({"status": "ok", "db_path_sha256": sys.argv[2]}).encode()

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/health":
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_args):
        return

ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), Handler).serve_forever()
""".lstrip(),
        encoding="utf-8",
    )
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port = int(probe.getsockname()[1])

    process = subprocess.Popen(
        [sys.executable, str(server_script), str(port), served_hash],
        cwd=process_root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        assert wait_for_scheduler_health(port)["db_path_sha256"] == served_hash
        if scenario == "renamed-installed":
            installed_dir.rename(backup_dir)
            assert not installed_dir.exists()
        else:
            assert selected_dir == installed_dir
            assert process_root == source_dir
        assert process.poll() is None

        completed = subprocess.run(
            [
                "bash",
                "-c",
                (
                    "set -euo pipefail\n"
                    "log_warn() { printf 'warn:%s\\n' \"$1\"; }\n"
                    f"{functions}"
                    "stop_scheduling_mcp_for_runtime\n"
                ),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
            env={
                **os.environ,
                "PYTHON_BIN": sys.executable,
                "SCHEDULING_DB_PATH": str(db_path),
                "SCHEDULING_MCP_DIR": str(selected_dir),
                "SCHEDULING_MCP_INSTALLED_DIR": str(installed_dir),
                "SCHEDULING_MCP_PID_FILE": str(tmp_path / "missing-scheduler.pid"),
                "SCHEDULING_MCP_PORT": str(port),
                "SCHEDULING_MCP_SOURCE_DIR": str(source_dir),
                "VIVENTIUM_PORT_CHECK_HOST": "127.0.0.1",
                "VIVENTIUM_PYTHON_BIN": sys.executable,
            },
        )

        assert completed.returncode == 0, completed.stderr
        deadline = time.monotonic() + 5
        while process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        assert (process.poll() is None) is expected_running
        assert db_path.read_bytes() == db_before
        with sqlite3.connect(db_path) as connection:
            assert connection.execute("PRAGMA quick_check").fetchone() == ("ok",)
        if matching_identity:
            assert "Stopping scoped processes that may own port" in completed.stdout
        else:
            assert "leaving it running during this runtime stop" in completed.stdout
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


@pytest.mark.parametrize(
    (
        "health_kind",
        "active_scope_kind",
        "expected_process",
        "expected_pid_file",
    ),
    [
        ("mismatching", "source", "1", "present"),
        ("empty", "installed", "1", "present"),
        ("empty", "source", "0", "missing"),
        ("matching", "installed", "0", "missing"),
    ],
)
def test_scheduler_identity_precedes_production_pid_signal_and_removal(
    tmp_path: Path,
    health_kind: str,
    active_scope_kind: str,
    expected_process: str,
    expected_pid_file: str,
) -> None:
    launcher_text = (
        REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"
    ).read_text(encoding="utf-8")
    pid_helper = extract_shell_function(launcher_text, "stop_pid_file_scoped")
    stop_function = extract_shell_function(
        launcher_text,
        "stop_scheduling_mcp_for_runtime",
    )
    source_dir = tmp_path / "source component"
    installed_dir = tmp_path / "installed component"
    source_dir.mkdir()
    installed_dir.mkdir()
    active_scope = source_dir if active_scope_kind == "source" else installed_dir
    pid_file = tmp_path / "scheduler.pid"
    pid_file.write_text("4242\n", encoding="utf-8")
    db_path = tmp_path / "state" / "schedules.db"
    expected_hash = hashlib.sha256(str(db_path.resolve()).encode("utf-8")).hexdigest()
    if health_kind == "matching":
        health = json.dumps({"status": "ok", "db_path_sha256": expected_hash})
    elif health_kind == "mismatching":
        health = json.dumps({"status": "ok", "db_path_sha256": "0" * 64})
    else:
        health = ""

    completed = subprocess.run(
        [
            "bash",
            "-c",
            (
                "set -euo pipefail\n"
                "LISTENER=1\n"
                "PROCESS=1\n"
                "ps() { [[ \"$PROCESS\" == 1 ]]; }\n"
                "pid_matches_scope() { [[ \"$2\" == \"$ACTIVE_SCOPE\" ]]; }\n"
                "port_has_listener() { [[ \"$LISTENER\" == 1 ]]; }\n"
                "curl() { printf '%s' \"$HEALTH_PAYLOAD\"; }\n"
                "log_warn() { printf 'warn:%s\\n' \"$1\"; }\n"
                "kill_pids() { printf 'signal:%s\\n' \"$1\"; PROCESS=0; LISTENER=0; }\n"
                "kill_port_listeners() { "
                "printf 'scope:%s\\n' \"$2\"; "
                "if [[ \"$2\" == \"$ACTIVE_SCOPE\" ]]; then kill_pids 4242; fi; "
                "}\n"
                f"{pid_helper}"
                f"{stop_function}"
                "stop_scheduling_mcp_for_runtime\n"
                "if [[ -e \"$SCHEDULING_MCP_PID_FILE\" ]]; then PID_STATE=present; "
                "else PID_STATE=missing; fi\n"
                "printf 'final:%s:%s\\n' \"$PROCESS\" \"$PID_STATE\"\n"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "ACTIVE_SCOPE": str(active_scope),
            "HEALTH_PAYLOAD": health,
            "PYTHON_BIN": sys.executable,
            "SCHEDULING_DB_PATH": str(db_path),
            "SCHEDULING_MCP_DIR": str(source_dir),
            "SCHEDULING_MCP_INSTALLED_DIR": str(installed_dir),
            "SCHEDULING_MCP_PID_FILE": str(pid_file),
            "SCHEDULING_MCP_PORT": "7110",
        },
    )

    assert completed.returncode == 0, completed.stderr
    assert (
        completed.stdout.splitlines()[-1]
        == f"final:{expected_process}:{expected_pid_file}"
    )
    if expected_process == "1":
        assert "signal:" not in completed.stdout


def test_scheduling_mcp_health_payload_is_public_safe_runtime_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastmcp")

    from scheduling_cortex.server import build_health_payload
    from scheduling_cortex.storage import ScheduleStorage, StorageConfig

    db_path = tmp_path / "runtime" / "scheduling" / "schedules.db"
    state_root = tmp_path / "runtime"
    monkeypatch.setenv("VIVENTIUM_STATE_ROOT", str(state_root))
    monkeypatch.setenv("VIVENTIUM_RUNTIME_PROFILE", "isolated")
    monkeypatch.setenv("VIVENTIUM_DEV_ENV_ENABLED", "true")
    monkeypatch.setenv("VIVENTIUM_DEV_ENV_NAME", "synthetic-dev")

    storage = ScheduleStorage(StorageConfig(db_path=str(db_path)))
    payload = build_health_payload(storage)

    expected_db_hash = hashlib.sha256(str(db_path.resolve()).encode("utf-8")).hexdigest()
    expected_state_hash = hashlib.sha256(str(state_root.resolve()).encode("utf-8")).hexdigest()
    expected_name_hash = hashlib.sha256("synthetic-dev".encode("utf-8")).hexdigest()
    serialized = json.dumps(payload, sort_keys=True)

    assert payload["status"] == "ok"
    assert payload["service"] == "scheduling-cortex"
    assert payload["db_path_sha256"] == expected_db_hash
    assert payload["state_root_sha256"] == expected_state_hash
    assert payload["runtime_profile"] == "isolated"
    assert payload["dev_env_enabled"] is True
    assert payload["dev_env_name_sha256"] == expected_name_hash
    assert str(tmp_path) not in serialized
    assert "synthetic-dev" not in serialized
