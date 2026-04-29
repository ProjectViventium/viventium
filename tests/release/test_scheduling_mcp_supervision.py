from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


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
    assert 'scheduling_python="$PWD/.venv/bin/python"' in launcher_text
    assert '"$scheduling_python" -m scheduling_cortex.server' in launcher_text
    assert (
        "Scheduling Cortex MCP port $SCHEDULING_MCP_PORT is occupied but health check failed; "
        "attempting scoped repair"
        in launcher_text
    )
    assert 'wait_for_http "$(scheduling_mcp_health_url)" "Scheduling Cortex MCP"' in launcher_text
    assert 'start_scheduling_mcp_watchdog' in launcher_text
    assert 'stop_scheduling_mcp_watchdog' in launcher_text
    assert "trap - EXIT" in launcher_text
