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
