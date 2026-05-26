from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEDULING_ROOT = (
    REPO_ROOT / "viventium_v0_4" / "LibreChat" / "viventium" / "MCPs" / "scheduling-cortex"
)
if str(SCHEDULING_ROOT) not in sys.path:
    sys.path.insert(0, str(SCHEDULING_ROOT))


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
    assert "scheduling_mcp_matches_runtime() {" in launcher_text
    assert "db_path_sha256" in launcher_text
    assert (
        "Scheduling Cortex MCP port $SCHEDULING_MCP_PORT is healthy but belongs to a different "
        "runtime or an older health contract; refusing to claim it"
        in launcher_text
    )
    assert "leaving the other runtime untouched" in launcher_text
    assert "leaving it running during this runtime stop" in launcher_text
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
