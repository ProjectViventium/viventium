# VIVENTIUM START
# Tests for multi-user + multi-vm isolation semantics.
# VIVENTIUM END

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

import openclaw_manager as mgr


class TestMultiUserIsolation:
    @pytest.mark.asyncio
    async def test_separate_ports_across_users(self, fresh_manager):
        async def mock_start(user_id, state_dir, port, vm_id="001", gateway_token=None):
            return mgr.OpenClawInstance(
                user_id=user_id,
                vm_id=vm_id,
                runtime="direct",
                state="running",
                port=port,
                pid=100 + port,
                state_dir=state_dir,
                gateway_token=gateway_token or "token",
            )

        with patch.object(fresh_manager, "_start_instance", side_effect=mock_start):
            inst_a = await fresh_manager.get_or_create_instance("alice", "001")
            inst_b = await fresh_manager.get_or_create_instance("bob", "001")

        assert inst_a.port != inst_b.port
        assert inst_a.user_id != inst_b.user_id

    @pytest.mark.asyncio
    async def test_same_user_different_vms_are_isolated(self, fresh_manager):
        async def mock_start(user_id, state_dir, port, vm_id="001", gateway_token=None):
            return mgr.OpenClawInstance(
                user_id=user_id,
                vm_id=vm_id,
                runtime="direct",
                state="running",
                port=port,
                pid=100 + port,
                state_dir=state_dir,
                gateway_token=gateway_token or "token",
            )

        with patch.object(fresh_manager, "_start_instance", side_effect=mock_start):
            vm1 = await fresh_manager.get_or_create_instance("demo", "001")
            vm2 = await fresh_manager.get_or_create_instance("demo", "002")

        assert vm1.key != vm2.key
        assert vm1.port != vm2.port

    @pytest.mark.asyncio
    async def test_pausing_one_vm_does_not_pause_sibling_vm(self, fresh_manager):
        vm1 = mgr.OpenClawInstance(
            user_id="demo",
            vm_id="001",
            runtime="direct",
            state="running",
            port=29000,
            pid=111,
            state_dir=Path("/tmp/demo-vm-001"),
        )
        vm2 = mgr.OpenClawInstance(
            user_id="demo",
            vm_id="002",
            runtime="direct",
            state="running",
            port=29001,
            pid=222,
            state_dir=Path("/tmp/demo-vm-002"),
        )
        fresh_manager._set_instance(vm1)
        fresh_manager._set_instance(vm2)

        with patch.object(fresh_manager, "_stop_direct_process", new_callable=AsyncMock):
            await fresh_manager.stop_instance("demo", "001")

        assert fresh_manager.get_instance("demo", "001").state == "paused"
        assert fresh_manager.get_instance("demo", "002").state == "running"

    @pytest.mark.asyncio
    async def test_concurrent_create_same_user_vm_creates_once(self, fresh_manager):
        call_count = 0

        async def mock_start(user_id, state_dir, port, vm_id="001", gateway_token=None):
            nonlocal call_count
            call_count += 1
            import asyncio

            await asyncio.sleep(0.05)
            return mgr.OpenClawInstance(
                user_id=user_id,
                vm_id=vm_id,
                runtime="direct",
                state="running",
                port=port,
                pid=999,
                state_dir=state_dir,
                gateway_token=gateway_token or "token",
            )

        fresh_manager.instances.clear()
        with patch.object(fresh_manager, "_start_instance", side_effect=mock_start), patch.object(
            fresh_manager, "_is_alive", new_callable=AsyncMock, return_value=True
        ):
            import asyncio

            results = await asyncio.gather(
                fresh_manager.get_or_create_instance("demo", "001"),
                fresh_manager.get_or_create_instance("demo", "001"),
            )

        assert call_count == 1
        assert results[0].port == results[1].port
