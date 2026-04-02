# VIVENTIUM START
# Tests for openclaw_manager.py with VM-scoped identity model.
# Focus: (user_id, vm_id) isolation, lifecycle semantics, and direct-runtime correctness.
# VIVENTIUM END

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import openclaw_manager as mgr


class TestNormalizeVmId:
    def test_numeric_vm_id_is_zero_padded(self):
        assert mgr.normalize_vm_id("1") == "001"
        assert mgr.normalize_vm_id("02") == "002"

    def test_prefixed_vm_id_is_normalized(self):
        assert mgr.normalize_vm_id("vm-7") == "007"

    def test_custom_vm_label_is_preserved(self):
        assert mgr.normalize_vm_id("alpha-lab") == "alpha-lab"


class TestInstanceUrls:
    def test_direct_runtime_urls_use_single_port(self):
        inst = mgr.OpenClawInstance(user_id="u1", vm_id="001", port=29000)
        assert inst.base_url == "http://127.0.0.1:29000"
        assert inst.tools_invoke_url.endswith("/tools/invoke")
        assert inst.responses_url.endswith("/v1/responses")

    def test_gateway_url_takes_precedence(self):
        inst = mgr.OpenClawInstance(
            user_id="u1",
            vm_id="001",
            gateway_url="https://sandbox-host.example",
            port=29000,
        )
        assert inst.base_url == "https://sandbox-host.example"


class TestStateDirectory:
    def test_state_dir_is_user_and_vm_scoped(self, fresh_manager):
        state_dir = fresh_manager._get_user_state_dir("alice", "2")
        assert state_dir.exists()
        assert state_dir.name == "vm-002"
        assert state_dir.parent.name == "alice"
        assert (state_dir / "workspace").exists()


class TestDirectRuntimeStartup:
    @pytest.mark.asyncio
    async def test_start_instance_uses_expected_cli_flags_and_env(self, fresh_manager):
        state_dir = fresh_manager._get_user_state_dir("alice", "002")

        captured_cmd = None
        captured_env = None

        async def mock_subprocess(*args, **kwargs):
            nonlocal captured_cmd, captured_env
            captured_cmd = list(args)
            captured_env = kwargs.get("env", {})
            proc = MagicMock()
            proc.pid = 4567
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess), patch.object(
            fresh_manager, "_wait_for_ready", new_callable=AsyncMock
        ):
            inst = await fresh_manager._start_instance(
                "alice",
                state_dir,
                29000,
                vm_id="002",
                gateway_token="fixed-token",
            )

        assert captured_cmd is not None
        assert captured_cmd[0] == "openclaw"
        assert captured_cmd[1] == "gateway"
        assert "--port" in captured_cmd
        assert "29000" in captured_cmd
        assert "--bind" in captured_cmd
        assert "loopback" in captured_cmd
        assert "--token" in captured_cmd
        assert "--allow-unconfigured" in captured_cmd
        assert "--force" in captured_cmd

        assert captured_env is not None
        assert captured_env["OPENCLAW_STATE_DIR"] == str(state_dir)
        assert captured_env["OPENCLAW_CONFIG_PATH"] == str(state_dir / "openclaw.json")
        assert captured_env["OPENCLAW_GATEWAY_TOKEN"] == "fixed-token"

        assert inst.vm_id == "002"
        assert inst.runtime == "direct"
        assert inst.port == 29000


class TestManagerLifecycle:
    @pytest.mark.asyncio
    async def test_same_user_different_vms_get_distinct_instances(self, fresh_manager):
        async def mock_start(user_id, state_dir, port, vm_id="001", gateway_token=None):
            return mgr.OpenClawInstance(
                user_id=user_id,
                vm_id=vm_id,
                runtime="direct",
                port=port,
                pid=1000 + port,
                state_dir=state_dir,
                gateway_token=gateway_token or "token",
            )

        with patch.object(fresh_manager, "_start_instance", side_effect=mock_start):
            vm1 = await fresh_manager.get_or_create_instance("demo", "001")
            vm2 = await fresh_manager.get_or_create_instance("demo", "002")

        assert vm1.vm_id == "001"
        assert vm2.vm_id == "002"
        assert vm1.port != vm2.port
        assert vm1.key != vm2.key

    @pytest.mark.asyncio
    async def test_stop_sets_paused_state(self, fresh_manager):
        inst = mgr.OpenClawInstance(
            user_id="demo",
            vm_id="001",
            runtime="direct",
            state="running",
            port=29000,
            pid=123,
            state_dir=Path("/tmp/demo-vm-001"),
        )
        fresh_manager._set_instance(inst)

        with patch.object(fresh_manager, "_stop_direct_process", new_callable=AsyncMock):
            await fresh_manager.stop_instance("demo", "001")

        updated = fresh_manager.get_instance("demo", "001")
        assert updated is not None
        assert updated.state == "paused"

    @pytest.mark.asyncio
    async def test_resume_restarts_direct_runtime_when_not_alive(self, fresh_manager):
        paused = mgr.OpenClawInstance(
            user_id="demo",
            vm_id="001",
            runtime="direct",
            state="paused",
            port=29000,
            pid=None,
            state_dir=Path("/tmp/demo-vm-001"),
            gateway_token="persisted-token",
        )
        fresh_manager._set_instance(paused)

        async def mock_start(user_id, state_dir, port, vm_id="001", gateway_token=None):
            return mgr.OpenClawInstance(
                user_id=user_id,
                vm_id=vm_id,
                runtime="direct",
                state="running",
                port=port,
                pid=4444,
                state_dir=state_dir,
                gateway_token=gateway_token or "persisted-token",
            )

        with patch.object(fresh_manager, "_is_alive", new_callable=AsyncMock, return_value=False), patch.object(
            fresh_manager,
            "_start_instance",
            side_effect=mock_start,
        ):
            resumed = await fresh_manager.resume_instance("demo", "001")

        assert resumed.state == "running"
        assert resumed.port == 29000

    @pytest.mark.asyncio
    async def test_terminate_removes_instance_and_releases_port(self, fresh_manager):
        inst = mgr.OpenClawInstance(
            user_id="demo",
            vm_id="001",
            runtime="direct",
            state="running",
            port=29000,
            pid=123,
            state_dir=Path("/tmp/demo-vm-001"),
        )
        fresh_manager._set_instance(inst)
        fresh_manager.used_ports.add(29000)

        with patch.object(fresh_manager, "_stop_direct_process", new_callable=AsyncMock):
            await fresh_manager.terminate_instance("demo", "001")

        assert fresh_manager.get_instance("demo", "001") is None
        assert 29000 not in fresh_manager.used_ports

    @pytest.mark.asyncio
    async def test_cleanup_idle_instances_uses_user_vm_key(self, fresh_manager):
        stale = mgr.OpenClawInstance(
            user_id="demo",
            vm_id="002",
            runtime="direct",
            state="running",
            port=29001,
            pid=321,
            state_dir=Path("/tmp/demo-vm-002"),
            last_activity=datetime.now() - timedelta(hours=3),
        )
        fresh_manager._set_instance(stale)

        with patch.object(fresh_manager, "stop_instance", new_callable=AsyncMock) as mock_stop:
            await fresh_manager.cleanup_idle_instances()
            mock_stop.assert_called_once_with("demo", "002")


class TestRegistryAndListing:
    @pytest.mark.asyncio
    async def test_list_instances_includes_vm_id(self, fresh_manager):
        async def mock_start(user_id, state_dir, port, vm_id="001", gateway_token=None):
            return mgr.OpenClawInstance(
                user_id=user_id,
                vm_id=vm_id,
                runtime="direct",
                state="running",
                port=port,
                pid=2000 + port,
                state_dir=state_dir,
                gateway_token=gateway_token or "token",
            )

        with patch.object(fresh_manager, "_start_instance", side_effect=mock_start):
            await fresh_manager.get_or_create_instance("demo", "001")
            await fresh_manager.get_or_create_instance("demo", "002")

        listed = fresh_manager.list_instances(user_id="demo")
        assert [item["vm_id"] for item in listed] == ["001", "002"]

    def test_generate_config_is_valid_openclaw_json(self, fresh_manager):
        state_dir = fresh_manager._get_user_state_dir("demo", "001")
        cfg_path = fresh_manager._generate_config("demo", state_dir, 29000, gateway_token="t1")
        cfg = json.loads(cfg_path.read_text())

        assert cfg_path.name == "openclaw.json"
        assert cfg["gateway"]["port"] == 29000
        assert cfg["gateway"]["auth"]["token"] == "t1"
        assert cfg["gateway"]["http"]["endpoints"]["responses"]["enabled"] is True


class TestTakeoverGuard:
    @pytest.mark.asyncio
    async def test_takeover_requires_e2b_runtime(self, fresh_manager):
        fresh_manager.runtime_mode = "direct"
        with pytest.raises(RuntimeError, match="Takeover requires OPENCLAW_RUNTIME=e2b"):
            await fresh_manager.takeover_instance("demo", "001")
