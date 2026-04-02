# VIVENTIUM START
# Integration tests for E2B-backed VM lifecycle in OpenClaw bridge.
# Requires:
#   - E2B_API_KEY
#   - e2b + e2b-desktop Python deps
#   - OpenClaw provider key(s) for agent-task assertions
# VIVENTIUM END

from __future__ import annotations

import importlib.util
import os
import uuid

import pytest

import openclaw_manager as mgr

pytestmark = pytest.mark.integration


def _require_e2b_or_skip() -> None:
    if not os.environ.get("E2B_API_KEY", "").strip():
        pytest.skip("E2B_API_KEY not set")
    if importlib.util.find_spec("e2b") is None:
        pytest.skip("e2b package not installed")
    if importlib.util.find_spec("e2b_desktop") is None:
        pytest.skip("e2b-desktop package not installed")


@pytest.mark.asyncio
async def test_e2b_vm_lifecycle_and_isolation(monkeypatch):
    _require_e2b_or_skip()

    monkeypatch.setenv("OPENCLAW_RUNTIME", "e2b")
    user_id = f"it-{uuid.uuid4().hex[:8]}"
    vm1 = "001"
    vm2 = "002"

    manager = mgr.OpenClawManager()
    if manager.runtime_mode != "e2b":
        pytest.skip(f"Manager runtime resolved to {manager.runtime_mode}, expected e2b")

    one = await manager.start_instance(user_id, vm1)
    two = await manager.start_instance(user_id, vm2)

    assert one.sandbox_id
    assert two.sandbox_id
    assert one.sandbox_id != two.sandbox_id

    await manager.stop_instance(user_id, vm1)
    info_paused = manager.get_instance_info(user_id, vm1)
    assert info_paused is not None
    assert info_paused["state"] == "paused"

    resumed = await manager.resume_instance(user_id, vm1)
    assert resumed.state == "running"

    marker = manager.run_shell(
        user_id,
        vm1,
        "test -f /workspace/.viventium/openclaw/vm-001/.bootstrap_complete && echo OK || echo MISSING",
        timeout=60,
    )
    assert "OK" in marker.get("stdout", "")

    await manager.terminate_instance(user_id, vm2)
    assert manager.get_instance_info(user_id, vm2) is None

    # cleanup primary VM
    await manager.terminate_instance(user_id, vm1)
