# VIVENTIUM START
# Tests for openclaw_manager.py with VM-scoped identity model.
# Focus: (user_id, vm_id) isolation, lifecycle semantics, and direct-runtime correctness.
# VIVENTIUM END

from __future__ import annotations

import json
import os
import socket
import stat
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import openclaw_manager as mgr
from vm_registry import VMRegistry, VMRegistryRecord


class TestNormalizeVmId:
    def test_numeric_vm_id_is_zero_padded(self):
        assert mgr.normalize_vm_id("1") == "001"
        assert mgr.normalize_vm_id("02") == "002"

    def test_prefixed_vm_id_is_normalized(self):
        assert mgr.normalize_vm_id("vm-7") == "007"

    def test_custom_vm_label_is_preserved(self):
        assert mgr.normalize_vm_id("alpha-lab") == "alpha-lab"

    @pytest.mark.parametrize(
        "vm_id",
        ["", "../escape", "/tmp/escape", "a/b", "a\\b", "x" * 65, "café"],
    )
    def test_hostile_vm_ids_are_rejected(self, vm_id):
        with pytest.raises(ValueError, match="VM id"):
            mgr.normalize_vm_id(vm_id)


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

    @pytest.mark.parametrize(
        "user_id",
        ["", "../escape", "/tmp/escape", "a/b", "a\\b", "x" * 65, "café"],
    )
    def test_hostile_user_ids_are_rejected_without_creating_paths(
        self, fresh_manager, tmp_path, user_id
    ):
        outside = tmp_path / "escape"

        with pytest.raises(ValueError, match="User id"):
            fresh_manager._get_user_state_dir(user_id, "001")

        assert not outside.exists()

    def test_symlinked_user_directory_is_rejected(self, fresh_manager, tmp_path):
        data_root = tmp_path / "users"
        outside = tmp_path / "outside"
        outside.mkdir()
        (data_root / "alice").symlink_to(outside, target_is_directory=True)

        with pytest.raises(RuntimeError, match="unsafe"):
            fresh_manager._get_user_state_dir("alice", "001")

        assert not (outside / "vm-001").exists()

    def test_state_and_secret_config_are_owner_only(self, fresh_manager):
        state_dir = fresh_manager._get_user_state_dir("alice", "001")
        config_path = fresh_manager._generate_config(
            "alice", state_dir, 29000, gateway_token="synthetic-token"
        )

        for directory in (state_dir.parent.parent, state_dir.parent, state_dir, state_dir / "workspace"):
            assert stat.S_IMODE(directory.stat().st_mode) == 0o700
        assert stat.S_IMODE(config_path.stat().st_mode) == 0o600


class TestPrivateRegistry:
    def test_registry_is_atomic_owner_only_state(self, tmp_path):
        root = tmp_path / "registry"
        root.mkdir(mode=0o700)
        path = root / "vm_registry.json"
        registry = VMRegistry(path)
        registry.upsert(
            VMRegistryRecord(
                user_id="synthetic-user",
                vm_id="001",
                runtime="direct",
                gateway_token="synthetic-token",
            )
        )

        assert stat.S_IMODE(root.stat().st_mode) == 0o700
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert list(root.glob("*.tmp")) == []

    def test_registry_rejects_symlink_target(self, tmp_path):
        root = tmp_path / "registry"
        root.mkdir(mode=0o700)
        outside = tmp_path / "outside.json"
        outside.write_text("do-not-touch")
        path = root / "vm_registry.json"
        path.symlink_to(outside)

        with pytest.raises(RuntimeError, match="unsafe"):
            VMRegistry(path)

        assert outside.read_text() == "do-not-touch"


class TestRegistryReconciliation:
    def test_invalid_remote_metadata_is_ignored_without_creating_paths(
        self, fresh_manager, monkeypatch
    ):
        fresh_manager.runtime_mode = "e2b"
        fresh_manager.e2b_runtime = MagicMock(available=True)
        fresh_manager.e2b_runtime.list_vm_sandboxes.return_value = [
            {
                "metadata": {
                    "viventium_user": "../escape",
                    "viventium_vm_id": "../escape",
                },
                "sandbox_id": "synthetic-foreign",
                "state": "running",
            }
        ]
        monkeypatch.setenv("E2B_API_KEY", "synthetic-key")

        fresh_manager._reconcile_registry()

        assert fresh_manager.list_instances() == []


class TestDirectRuntimeStartup:
    def test_port_reservation_never_takes_over_a_foreign_listener(self, fresh_manager):
        foreign = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        foreign.bind(("127.0.0.1", 0))
        foreign.listen(1)
        port = foreign.getsockname()[1]
        try:
            with patch.object(mgr, "PORT_RANGE_START", port), patch.object(
                mgr, "PORT_RANGE_END", port + 1
            ):
                with pytest.raises(RuntimeError, match="No free ports"):
                    fresh_manager._get_free_port()

            probe = socket.create_connection(("127.0.0.1", port), timeout=1)
            probe.close()
        finally:
            foreign.close()

    @pytest.mark.asyncio
    async def test_persisted_pid_is_never_signaled_without_owned_process_handle(
        self, fresh_manager
    ):
        instance = mgr.OpenClawInstance(
            user_id="synthetic-user",
            vm_id="001",
            runtime="direct",
            pid=os.getpid(),
            port=29000,
        )

        with patch("openclaw_manager.os.kill") as kill:
            await fresh_manager._stop_direct_process(instance)

        kill.assert_not_called()
        assert instance.pid is None

    def test_log_open_rejects_symlink_target(self, tmp_path):
        root = tmp_path / "logs"
        root.mkdir(mode=0o700)
        outside = tmp_path / "outside.log"
        outside.write_text("untouched")
        path = root / "runtime.log"
        path.symlink_to(outside)

        with pytest.raises(OSError):
            mgr._open_private_append(path)

        assert outside.read_text() == "untouched"

    @pytest.mark.asyncio
    async def test_start_instance_uses_expected_cli_flags_and_env(self, fresh_manager, caplog):
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

        reviewed_version = MagicMock(
            returncode=0,
            stdout=f"{mgr.OPENCLAW_REQUIRED_VERSION}\n",
        )
        with patch("subprocess.run", return_value=reviewed_version), patch(
            "asyncio.create_subprocess_exec", side_effect=mock_subprocess
        ), patch.object(fresh_manager, "_wait_for_ready", new_callable=AsyncMock):
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
        assert "--force" not in captured_cmd

        assert captured_env is not None
        assert captured_env["OPENCLAW_STATE_DIR"] == str(state_dir)
        assert captured_env["OPENCLAW_CONFIG_PATH"] == str(state_dir / "openclaw.json")
        assert captured_env["OPENCLAW_GATEWAY_TOKEN"] == "fixed-token"

        assert inst.vm_id == "002"
        assert inst.runtime == "direct"
        assert inst.port == 29000
        assert "fixed-token" not in caplog.text

    @pytest.mark.asyncio
    @pytest.mark.parametrize("foreign_status", [401, 404])
    async def test_readiness_rejects_foreign_http_services(self, fresh_manager, foreign_status):
        instance = mgr.OpenClawInstance(
            user_id="demo",
            vm_id="001",
            runtime="direct",
            gateway_token="synthetic-token",
            port=29000,
            pid=123,
        )
        response = MagicMock(status_code=foreign_status)
        client = AsyncMock()
        client.get.return_value = response
        context = MagicMock()
        context.__aenter__ = AsyncMock(return_value=client)
        context.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=context), patch(
            "openclaw_manager.time.time", side_effect=[0, 0, 2]
        ), patch("openclaw_manager.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RuntimeError, match="not ready"):
                await fresh_manager._wait_for_ready(instance, timeout=1)

    @pytest.mark.asyncio
    async def test_readiness_requires_exact_openclaw_health_identity(self, fresh_manager):
        instance = mgr.OpenClawInstance(
            user_id="demo",
            vm_id="001",
            runtime="direct",
            gateway_token="synthetic-token",
            port=29000,
            pid=123,
        )
        response = MagicMock(status_code=200)
        response.json.return_value = {"ok": True, "status": "live"}
        client = AsyncMock()
        client.get.return_value = response
        context = MagicMock()
        context.__aenter__ = AsyncMock(return_value=client)
        context.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=context):
            await fresh_manager._wait_for_ready(instance, timeout=1)

        client.get.assert_awaited_once_with(f"{instance.base_url}/health", timeout=3)

    def test_rejects_mismatched_openclaw_runtime(self):
        wrong_version = MagicMock(returncode=0, stdout="0.0.0\n")
        with patch("subprocess.run", return_value=wrong_version):
            with pytest.raises(RuntimeError, match="reviewed 2026.7.1-2"):
                mgr.OpenClawManager._reviewed_openclaw_command()

    def test_accepts_reviewed_openclaw_provenance_suffix(self):
        reviewed = MagicMock(
            returncode=0,
            stdout=f"OpenClaw {mgr.OPENCLAW_REQUIRED_VERSION} (synthetic)\n",
        )
        with patch("subprocess.run", return_value=reviewed):
            assert mgr.OpenClawManager._reviewed_openclaw_command() == ["openclaw"]


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


class TestRuntimeIsolationGuard:
    def test_direct_runtime_requires_explicit_host_execution_opt_in(self, tmp_path):
        with patch.object(mgr, "DATA_DIR", tmp_path / "users"), \
             patch.object(mgr, "LOG_DIR", tmp_path / "logs"), \
             patch.object(mgr, "REGISTRY_PATH", tmp_path / "registry.json"), \
             patch.object(mgr, "OPENCLAW_RUNTIME", "direct"), \
             patch.object(mgr, "OPENCLAW_DIRECT_HOST_EXEC_ALLOWED", False):
            with pytest.raises(RuntimeError, match="OPENCLAW_ALLOW_DIRECT_HOST_EXEC"):
                mgr.OpenClawManager()
