"""The launcher supervises the GlassHive runtime like its other sidecars.

Main's provider lives in the GlassHive runtime process. Without a watchdog, one crash silently
takes Main down on every surface until a manual restart. This test pins the wiring of the
watchdog that mirrors the Scheduling Cortex, Telegram, and Prompt Workbench watchdogs.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"


def _launcher_text() -> str:
    return LAUNCHER.read_text(encoding="utf-8")


def test_glasshive_runtime_watchdog_is_defined_like_the_other_sidecar_watchdogs() -> None:
    text = _launcher_text()
    for function_name in (
        "glasshive_runtime_healthy",
        "restart_glasshive_runtime_stack",
        "start_glasshive_runtime_watchdog",
        "stop_glasshive_runtime_watchdog",
    ):
        assert re.search(rf"^{function_name}\(\) \{{", text, re.MULTILINE), function_name
    assert 'GLASSHIVE_RUNTIME_WATCHDOG_PID_FILE="$LOG_ROOT/glasshive_runtime_watchdog.pid"' in text
    assert 'GLASSHIVE_RUNTIME_WATCHDOG_LOG_FILE="$LOG_DIR/glasshive_runtime_watchdog.log"' in text
    assert 'http://127.0.0.1:${GLASSHIVE_RUNTIME_PORT}/health' in text


def test_glasshive_runtime_watchdog_restarts_only_the_scoped_stack() -> None:
    text = _launcher_text()
    body = text[text.index("restart_glasshive_runtime_stack() {") :]
    body = body[: body.index("\n}\n")]
    assert "stop_candidate_glasshive_stack" in body
    assert "start_glasshive" in body
    assert "kill_port_listeners" not in body, "restart must reuse the scoped teardown, not kill ports directly"


def test_glasshive_runtime_watchdog_is_started_and_stopped_with_the_stack() -> None:
    text = _launcher_text()
    start_block = 'if [[ "$START_GLASSHIVE" == "true" ]]; then\n  start_glasshive_runtime_watchdog\nfi\n'
    assert start_block in text
    assert text.index("start_scheduling_mcp_watchdog\nfi") < text.index(start_block)
    stop_calls = [
        match.start()
        for match in re.finditer(r"^\s+stop_glasshive_runtime_watchdog$", text, re.MULTILINE)
    ]
    scheduling_stop_calls = [
        match.start()
        for match in re.finditer(r"^\s+stop_scheduling_mcp_watchdog$", text, re.MULTILINE)
    ]
    # Every stack stop path that stops the scheduling watchdog also stops the GlassHive watchdog;
    # the extra occurrence is the self-stop at the top of start_glasshive_runtime_watchdog.
    assert len(stop_calls) == len(scheduling_stop_calls)


def _shell_function(name: str) -> str:
    text = _launcher_text()
    start = text.index(name + "() {\n")
    return text[start : text.index("\n}\n", start) + 3] + "\n"


def _confirmed_unresponsive(listener: str, health: str, topology: str = "") -> tuple[int, str]:
    import subprocess

    script = (
        _shell_function("glasshive_runtime_confirmed_unresponsive")
        + f"""
GLASSHIVE_SERVICE_TOPOLOGY={topology}
GLASSHIVE_RUNTIME_PORT=18766
GLASSHIVE_RUNTIME_BASE_URL=http://127.0.0.1:18766
glasshive_local_listener_matches() {{ return {listener}; }}
viventium_glasshive_runtime_healthy() {{ echo "timeout=$2" >&2; return {health}; }}
glasshive_runtime_confirmed_unresponsive
"""
    )
    result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    return result.returncode, result.stderr


def test_watchdog_does_not_restart_a_slow_runtime_that_is_alive() -> None:
    # A slow but owned runtime that returns valid health within the confirmation window is alive.
    code, stderr = _confirmed_unresponsive(listener="0", health="0")
    assert code == 1
    assert "timeout=45" in stderr


def test_watchdog_still_restarts_a_foreign_invalid_or_silent_runtime() -> None:
    assert _confirmed_unresponsive(listener="1", health="0")[0] == 0
    # Silence for the whole confirmation window restarts; consumed CPU is not proof of progress.
    assert _confirmed_unresponsive(listener="0", health="1")[0] == 0
    assert _confirmed_unresponsive(listener="1", health="1", topology="external_split")[0] == 0
    assert _confirmed_unresponsive(listener="1", health="0", topology="external_split")[0] == 1


def test_watchdog_confirms_unresponsiveness_before_restarting() -> None:
    text = _launcher_text()
    body = text[text.index("start_glasshive_runtime_watchdog() {") :]
    body = body[: body.index("\n}\n")]
    assert body.index("glasshive_runtime_confirmed_unresponsive") < body.index(
        "restart_glasshive_runtime_stack"
    )


def test_xperfect_stops_port_owning_servers_before_their_wrappers() -> None:
    # Killing a `uv run` wrapper first lets its server close the port and linger as an orphan.
    import subprocess

    script = (
        _shell_function("stop_glasshive_services_listener_first")
        + _shell_function("stop_candidate_glasshive_stack")
        + """
calls=()
glasshive_local_ports_owned() { return 0; }
glasshive_local_listener_matches() { [[ "$2" != "mcp" ]]; }
kill_port_listeners() { calls+=("port:$1"); }
stop_pid_file_scoped() { calls+=("pidfile"); }
port_in_use() { return 1; }
GLASSHIVE_UI_PORT=18780 GLASSHIVE_MCP_PORT=18767 GLASSHIVE_RUNTIME_PORT=18766
stop_candidate_glasshive_stack
printf '%s\\n' "${calls[@]}"
"""
    )
    result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    # Only exactly identified listeners are stopped by port, all before any wrapper.
    assert result.stdout.split() == ["port:18780", "port:18766", "pidfile", "pidfile", "pidfile"]


def test_every_xperfect_stop_path_uses_the_listener_first_stop() -> None:
    text = _launcher_text()
    start = text.index("stop_glasshive_services_listener_first() {\n")
    end = text.index("\n}\n", start) + 3
    outside = text[:start] + text[end:]
    assert outside.count("stop_glasshive_services_listener_first") == 4
    for pid_file in ("GLASSHIVE_RUNTIME_PID_FILE", "GLASSHIVE_MCP_PID_FILE", "GLASSHIVE_UI_PID_FILE"):
        assert f'stop_pid_file_scoped "${pid_file}"' not in outside


def test_listener_first_stop_is_defined_before_its_top_level_stop_caller() -> None:
    # `--stop` runs the stop block as top-level code; bash needs the helper defined earlier.
    text = _launcher_text()
    first_call = min(
        text.index(indent + "stop_glasshive_services_listener_first\n")
        for indent in ("\n  ", "\n    ", "\n      ")
        if indent + "stop_glasshive_services_listener_first\n" in text
    )
    for name in ("stop_glasshive_services_listener_first", "glasshive_local_listener_matches"):
        assert text.index(name + "() {\n") < first_call, name
