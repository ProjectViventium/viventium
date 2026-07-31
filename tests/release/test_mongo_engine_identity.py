from __future__ import annotations

import importlib.util
import json
import os
import shutil
import socket
import stat
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
TRANSACTION_PATH = REPO_ROOT / "scripts" / "viventium" / "upgrade_transaction.py"
IDENTITY_CLI = REPO_ROOT / "scripts" / "viventium" / "mongo_engine_identity.py"
LAUNCHER = REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"
NATIVE_STACK = REPO_ROOT / "scripts" / "viventium" / "native_stack.sh"


def load_transaction_module():
    specification = importlib.util.spec_from_file_location(
        "mongo_engine_identity_transaction_test",
        TRANSACTION_PATH,
    )
    assert specification and specification.loader
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def build_bind_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    support = tmp_path / "support"
    runtime = support / "runtime"
    data_path = support / "state" / "runtime" / "isolated" / "mongo-data"
    runtime.mkdir(parents=True)
    data_path.mkdir(parents=True)
    (data_path / "WiredTiger").write_bytes(b"synthetic-wiredtiger-anchor")
    (data_path / "WiredTiger.turtle").write_bytes(b"synthetic-turtle-anchor")
    (runtime / "runtime.env").write_text(
        "\n".join(
            [
                "VIVENTIUM_RUNTIME_PROFILE=isolated",
                "VIVENTIUM_LOCAL_MONGO_PORT=27117",
                "VIVENTIUM_LOCAL_MONGO_CONTAINER=viventium-mongodb-isolated",
                f"VIVENTIUM_LOCAL_MONGO_DATA_PATH={data_path}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return support, runtime, data_path


def native_inventory(data_path: Path) -> dict[str, object]:
    return {
        "backend": "app_support_bind",
        "runtime_engine": "native",
        "profile": "isolated",
        "path": str(data_path),
        "observed_from": "running_native_pid",
        "pid": 4242,
        "process_started_at": "Fri Jul 24 10:11:12 2026",
        "executable": "/opt/viventium/mongod",
        "executable_sha256": "a" * 64,
        "arguments": [
            "/opt/viventium/mongod",
            "--port",
            "27117",
            "--dbpath",
            str(data_path),
        ],
        "version": "db version v8.0.23",
        "code_signature_verified": True,
        "code_signature_team_identifier": "4XWMY46275",
    }


def native_process_view(identity: dict[str, object]) -> dict[str, object]:
    return {
        key: identity[key]
        for key in (
            "pid",
            "process_started_at",
            "executable",
            "executable_sha256",
            "arguments",
            "version",
            "code_signature_verified",
            "code_signature_team_identifier",
        )
    }


def write_running_native_receipt(module, support: Path, identity: dict[str, object]):
    return module._write_mongo_engine_receipt(
        support,
        {
            "schema_version": module.MONGO_ENGINE_IDENTITY_SCHEMA_VERSION,
            "recorded_at": "2026-07-24T10:11:12Z",
            "sealed_at": "",
            "clean_stopped": False,
            "identity": identity,
            "storage_anchor": None,
        },
    )


def test_identity_bound_native_stop_then_seal_removes_matching_pid_records(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_transaction_module()
    support, runtime, data_path = build_bind_fixture(tmp_path)
    identity = native_inventory(data_path)
    canonical_pid = support / "state" / "native" / "mongod.pid"
    legacy_pid = support / "state" / "runtime" / "isolated" / "mongodb-native.pid"
    canonical_pid.parent.mkdir(parents=True)
    canonical_pid.write_text("4242\n", encoding="utf-8")
    legacy_pid.write_text("4242\n", encoding="utf-8")
    running = {"value": True}
    monkeypatch.setattr(
        module,
        "_observe_running_mongo_storage",
        lambda *_args, **_kwargs: (
            (identity if running["value"] else None),
            [],
        ),
    )
    monkeypatch.setattr(
        module,
        "inspect_native_mongo_process",
        lambda _pid: native_process_view(identity),
    )

    def fake_kill(pid: int, signal_number: int) -> None:
        assert pid == 4242
        if signal_number == module.signal.SIGTERM:
            running["value"] = False
            return
        if not running["value"]:
            raise ProcessLookupError(pid)

    monkeypatch.setattr(module.os, "kill", fake_kill)

    module.record_mongo_engine_identity(support, runtime)
    module.stop_recorded_native_mongo_engine(
        support,
        runtime,
        pid_files=(canonical_pid,),
        timeout_seconds=1,
    )
    sealed = module.seal_mongo_engine_identity(support, runtime)

    assert sealed["clean_stopped"] is True
    assert sealed["storage_anchor"]["kind"] == "bind-directory"
    assert not canonical_pid.exists()
    assert not legacy_pid.exists()


def test_real_native_prestart_is_identity_stopped_and_sealed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_transaction_module()
    mongod = shutil.which("mongod")
    if not mongod:
        pytest.skip("mongod is not installed")
    support = tmp_path / "support"
    runtime = support / "runtime"
    data_path = support / "state" / "runtime" / "isolated" / "mongo-data"
    runtime.mkdir(parents=True)
    data_path.mkdir(parents=True)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        mongo_port = listener.getsockname()[1]
    (runtime / "runtime.env").write_text(
        "\n".join(
            [
                "VIVENTIUM_RUNTIME_PROFILE=isolated",
                f"VIVENTIUM_LOCAL_MONGO_PORT={mongo_port}",
                "VIVENTIUM_LOCAL_MONGO_CONTAINER=viventium-mongodb-isolated",
                f"VIVENTIUM_LOCAL_MONGO_DATA_PATH={data_path}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    process = subprocess.Popen(
        [
            mongod,
            "--bind_ip",
            "127.0.0.1",
            "--port",
            str(mongo_port),
            "--dbpath",
            str(data_path),
            "--logpath",
            str(tmp_path / "mongod.log"),
            "--setParameter",
            "diagnosticDataCollectionEnabled=false",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    pid_file = support / "state" / "native" / "mongod.pid"
    pid_file.parent.mkdir(parents=True)
    pid_file.write_text(f"{process.pid}\n", encoding="utf-8")

    def docker_unavailable():
        raise module.UpgradeTransactionError("synthetic Docker unavailable")

    monkeypatch.setattr(module, "docker_ready", docker_unavailable)
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if process.poll() is not None:
                pytest.fail(
                    f"real mongod exited before identity capture: {process.returncode}"
                )
            try:
                with socket.create_connection(
                    ("127.0.0.1", mongo_port),
                    timeout=0.1,
                ):
                    break
            except OSError:
                time.sleep(0.05)
        else:
            pytest.fail("real mongod did not become reachable")
        recorded = module.record_mongo_engine_identity(support, runtime)
        reaper = threading.Thread(target=process.wait, daemon=True)
        reaper.start()
        module.stop_recorded_native_mongo_engine(
            support,
            runtime,
            pid_files=(pid_file,),
            timeout_seconds=5,
        )
        reaper.join(timeout=5)
        sealed = module.seal_mongo_engine_identity(support, runtime)
    finally:
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=10)

    assert recorded["identity"]["pid"] == process.pid
    assert sealed["clean_stopped"] is True
    assert not pid_file.exists()


def test_identity_bound_native_stop_rejects_stale_pid_without_signaling(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_transaction_module()
    support, runtime, data_path = build_bind_fixture(tmp_path)
    identity = native_inventory(data_path)
    write_running_native_receipt(module, support, identity)
    foreign = native_process_view(identity)
    foreign["process_started_at"] = "Fri Jul 24 10:12:13 2026"
    monkeypatch.setattr(
        module,
        "inspect_native_mongo_process",
        lambda _pid: foreign,
    )
    signals: list[tuple[int, int]] = []
    monkeypatch.setattr(
        module.os,
        "kill",
        lambda pid, signal_number: signals.append((pid, signal_number)),
    )

    with pytest.raises(module.UpgradeTransactionError, match="identity changed"):
        module.stop_recorded_native_mongo_engine(support, runtime)

    assert signals == []


def test_identity_bound_native_stop_rejects_unsafe_pid_target_before_signaling(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_transaction_module()
    support, runtime, data_path = build_bind_fixture(tmp_path)
    identity = native_inventory(data_path)
    write_running_native_receipt(module, support, identity)
    outside_pid_file = tmp_path / "outside.pid"
    outside_pid_file.write_text("4242\n", encoding="utf-8")
    monkeypatch.setattr(
        module,
        "inspect_native_mongo_process",
        lambda _pid: native_process_view(identity),
    )
    signals: list[tuple[int, int]] = []
    monkeypatch.setattr(
        module.os,
        "kill",
        lambda pid, signal_number: signals.append((pid, signal_number)),
    )

    with pytest.raises(module.UpgradeTransactionError, match="escapes"):
        module.stop_recorded_native_mongo_engine(
            support,
            runtime,
            pid_files=(outside_pid_file,),
        )

    assert signals == []


def test_validated_native_pid_cleanup_preserves_replaced_inode(tmp_path: Path) -> None:
    module = load_transaction_module()
    support = tmp_path / "support"
    pid_file = support / "state" / "native" / "mongod.pid"
    pid_file.parent.mkdir(parents=True)
    pid_file.write_text("4242\n", encoding="utf-8")
    record = module._validate_native_mongo_pid_file(pid_file, support=support)
    replacement = pid_file.with_suffix(".replacement")
    replacement.write_text("4242\n", encoding="utf-8")
    os.replace(replacement, pid_file)

    removed = module._remove_validated_native_mongo_pid_file(record, pid=4242)

    assert removed is False
    assert pid_file.read_text(encoding="utf-8") == "4242\n"


def test_stale_native_pid_prune_removes_only_a_proven_dead_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_transaction_module()
    support = tmp_path / "support"
    pid_file = support / "state" / "native" / "mongod.pid"
    pid_file.parent.mkdir(parents=True)
    pid_file.write_text("4242\n", encoding="utf-8")

    def dead_process(pid: int, signal_number: int) -> None:
        assert (pid, signal_number) == (4242, 0)
        raise ProcessLookupError(pid)

    monkeypatch.setattr(module.os, "kill", dead_process)

    result = module.discard_stale_native_mongo_pid_file(support, pid_file)

    assert result == {"removed": True, "pid": 4242}
    assert not pid_file.exists()


def test_stale_native_pid_prune_preserves_a_live_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_transaction_module()
    support = tmp_path / "support"
    pid_file = support / "state" / "native" / "mongod.pid"
    pid_file.parent.mkdir(parents=True)
    pid_file.write_text("4242\n", encoding="utf-8")
    probes: list[tuple[int, int]] = []
    monkeypatch.setattr(
        module.os,
        "kill",
        lambda pid, signal_number: probes.append((pid, signal_number)),
    )

    with pytest.raises(module.UpgradeTransactionError, match="live process"):
        module.discard_stale_native_mongo_pid_file(support, pid_file)

    assert probes == [(4242, 0)]
    assert pid_file.read_text(encoding="utf-8") == "4242\n"


def test_identity_bound_native_stop_recovers_valid_legacy_pid_without_canonical(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_transaction_module()
    support, runtime, data_path = build_bind_fixture(tmp_path)
    identity = native_inventory(data_path)
    write_running_native_receipt(module, support, identity)
    legacy_pid = support / "state" / "runtime" / "isolated" / "mongodb-native.pid"
    legacy_pid.write_text("4242\n", encoding="utf-8")
    running = {"value": True}
    monkeypatch.setattr(
        module,
        "inspect_native_mongo_process",
        lambda _pid: native_process_view(identity),
    )

    def fake_kill(pid: int, signal_number: int) -> None:
        assert pid == 4242
        if signal_number == module.signal.SIGTERM:
            running["value"] = False
        elif not running["value"]:
            raise ProcessLookupError(pid)

    monkeypatch.setattr(module.os, "kill", fake_kill)

    module.stop_recorded_native_mongo_engine(support, runtime, timeout_seconds=1)

    assert not legacy_pid.exists()
    assert not (support / "state" / "native" / "mongod.pid").exists()


def test_identity_bound_native_stop_leaves_docker_engine_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_transaction_module()
    support, runtime, data_path = build_bind_fixture(tmp_path)
    identity = {
        "backend": "app_support_bind",
        "runtime_engine": "docker",
        "profile": "isolated",
        "path": str(data_path),
        "image": "mongo:8.0.17",
        "image_id": "sha256:" + "b" * 64,
        "container_name": "viventium-mongodb-isolated",
        "container_running": True,
        "observed_from": "container_inspect",
    }
    receipt = write_running_native_receipt(module, support, identity)
    signals: list[tuple[int, int]] = []
    monkeypatch.setattr(
        module.os,
        "kill",
        lambda pid, signal_number: signals.append((pid, signal_number)),
    )

    stopped = module.stop_recorded_native_mongo_engine(support, runtime)

    assert stopped == receipt
    assert signals == []


def test_native_stack_stop_prunes_a_dead_pid_and_is_a_real_noop(
    tmp_path: Path,
) -> None:
    support = tmp_path / "support"
    runtime = support / "runtime"
    data_path = support / "state" / "runtime" / "isolated" / "mongo-data"
    runtime.mkdir(parents=True)
    data_path.mkdir(parents=True)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        mongo_port = listener.getsockname()[1]
    (runtime / "runtime.env").write_text(
        "\n".join(
            [
                "VIVENTIUM_RUNTIME_PROFILE=isolated",
                f"VIVENTIUM_LOCAL_MONGO_PORT={mongo_port}",
                "VIVENTIUM_LOCAL_MONGO_CONTAINER=viventium-mongodb-isolated",
                f"VIVENTIUM_LOCAL_MONGO_DATA_PATH={data_path}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    pid_file = support / "state" / "native" / "mongod.pid"
    pid_file.parent.mkdir(parents=True)
    pid_file.write_text("99999999\n", encoding="utf-8")

    completed = subprocess.run(
        [str(NATIVE_STACK), "stop"],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PYTHON_BIN": sys.executable,
            "VIVENTIUM_APP_SUPPORT_DIR": str(support),
            "VIVENTIUM_RUNTIME_DIR": str(runtime),
            "VIVENTIUM_RUNTIME_PROFILE": "isolated",
            "VIVENTIUM_LOCAL_MONGO_PORT": str(mongo_port),
            "VIVENTIUM_LOCAL_MONGO_DATA_PATH": str(data_path),
            "VIVENTIUM_NATIVE_STACK_SKIP_LIVEKIT": "1",
            "VIVENTIUM_NATIVE_STACK_SKIP_MEILI": "1",
            "VIVENTIUM_VOICE_ENABLED": "false",
        },
    )

    assert completed.returncode == 0, completed.stderr
    assert not pid_file.exists()
    assert not (
        support / "state" / "continuity" / "mongo-engine-identity.json"
    ).exists()


def test_process_arguments_preserve_spaced_app_support_path(tmp_path: Path) -> None:
    module = load_transaction_module()
    spaced_data_path = tmp_path / "Application Support" / "Viventium" / "mongo-data"
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import time; time.sleep(30)",
            "--dbpath",
            str(spaced_data_path),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        arguments = module._process_arguments(process.pid)
    finally:
        process.terminate()
        process.wait(timeout=10)

    assert arguments[-2:] == ["--dbpath", str(spaced_data_path)]


def test_linux_process_arguments_preserve_spaced_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_transaction_module()
    raw = b"/usr/bin/mongod\0--dbpath\0/tmp/Application Support/Viventium/mongo-data\0"
    monkeypatch.setattr(module.Path, "read_bytes", lambda _path: raw)

    assert module._linux_process_arguments(123) == [
        "/usr/bin/mongod",
        "--dbpath",
        "/tmp/Application Support/Viventium/mongo-data",
    ]


def test_linux_process_arguments_reject_interior_empty_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_transaction_module()
    raw = b"/usr/bin/mongod\0--dbpath\0\0/tmp/allowed/mongo-data\0"
    monkeypatch.setattr(module.Path, "read_bytes", lambda _path: raw)

    with pytest.raises(module.UpgradeTransactionError, match="malformed"):
        module._linux_process_arguments(123)


@pytest.mark.parametrize("raw", [b"", b"/usr/bin/mongod\0--dbpath"])
def test_linux_process_arguments_reject_incomplete_cmdline(
    monkeypatch: pytest.MonkeyPatch,
    raw: bytes,
) -> None:
    module = load_transaction_module()
    monkeypatch.setattr(module.Path, "read_bytes", lambda _path: raw)

    with pytest.raises(module.UpgradeTransactionError, match="malformed"):
        module._linux_process_arguments(123)


def test_linux_process_arguments_fail_closed_when_cmdline_is_unreadable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_transaction_module()

    def fail_read(_path: Path) -> bytes:
        raise FileNotFoundError("synthetic process exit")

    monkeypatch.setattr(module.Path, "read_bytes", fail_read)

    with pytest.raises(module.UpgradeTransactionError, match="inspected exactly"):
        module._linux_process_arguments(123)


def test_running_native_identity_is_written_owner_only_and_fsynced(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_transaction_module()
    support, runtime, data_path = build_bind_fixture(tmp_path)
    directory_fsyncs: list[Path] = []
    monkeypatch.setattr(
        module,
        "_observe_running_mongo_storage",
        lambda *_args, **_kwargs: (native_inventory(data_path), []),
    )
    monkeypatch.setattr(
        module,
        "_fsync_directory",
        lambda path: directory_fsyncs.append(Path(path)),
    )

    payload = module.record_mongo_engine_identity(support, runtime)

    receipt = support / module.MONGO_ENGINE_IDENTITY_RECEIPT
    assert receipt.is_file() and not receipt.is_symlink()
    assert stat.S_IMODE(receipt.stat().st_mode) == 0o600
    assert payload["schema_version"] == 1
    assert payload["clean_stopped"] is False
    assert payload["identity"]["runtime_engine"] == "native"
    assert payload["identity"]["executable_sha256"] == "a" * 64
    assert payload["receipt_sha256"] == module.mongo_engine_receipt_digest(payload)
    assert receipt.parent in directory_fsyncs


def test_clean_stop_seals_exact_bind_storage_anchor_and_stopped_inventory_reuses_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_transaction_module()
    support, runtime, data_path = build_bind_fixture(tmp_path)
    observed = native_inventory(data_path)
    monkeypatch.setattr(
        module,
        "_observe_running_mongo_storage",
        lambda *_args, **_kwargs: (observed, []),
    )
    module.record_mongo_engine_identity(support, runtime)
    monkeypatch.setattr(
        module,
        "_observe_running_mongo_storage",
        lambda *_args, **_kwargs: (None, []),
    )

    sealed = module.seal_mongo_engine_identity(support, runtime)
    assert sealed["clean_stopped"] is True
    assert sealed["storage_anchor"]["kind"] == "bind-directory"
    assert sealed["storage_anchor"]["root_device"] == data_path.stat().st_dev
    assert sealed["storage_anchor"]["root_inode"] == data_path.stat().st_ino
    assert [item["name"] for item in sealed["storage_anchor"]["files"]] == [
        "WiredTiger",
        "WiredTiger.turtle",
    ]
    monkeypatch.setattr(
        module,
        "_revalidate_native_receipt_engine",
        lambda _identity: None,
    )

    inventory, extra_surfaces = module.mongo_storage_inventory(support, runtime)
    assert inventory["runtime_engine"] == "native"
    assert inventory["path"] == str(data_path)
    assert inventory["observed_from"] == "engine_identity_receipt"
    assert inventory["receipt_sha256"] == sealed["receipt_sha256"]
    assert extra_surfaces == []


def test_stopped_receipt_rejects_storage_anchor_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_transaction_module()
    support, runtime, data_path = build_bind_fixture(tmp_path)
    monkeypatch.setattr(
        module,
        "_observe_running_mongo_storage",
        lambda *_args, **_kwargs: (native_inventory(data_path), []),
    )
    module.record_mongo_engine_identity(support, runtime)
    monkeypatch.setattr(
        module,
        "_observe_running_mongo_storage",
        lambda *_args, **_kwargs: (None, []),
    )
    module.seal_mongo_engine_identity(support, runtime)
    (data_path / "WiredTiger").write_bytes(b"different-storage")
    monkeypatch.setattr(
        module,
        "_revalidate_native_receipt_engine",
        lambda _identity: None,
    )

    with pytest.raises(
        module.UpgradeTransactionError,
        match="storage identity changed after its clean stop",
    ):
        module.mongo_storage_inventory(support, runtime)


def test_unclean_receipt_is_not_engine_proof_for_stopped_storage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_transaction_module()
    support, runtime, data_path = build_bind_fixture(tmp_path)
    monkeypatch.setattr(
        module,
        "_observe_running_mongo_storage",
        lambda *_args, **_kwargs: (native_inventory(data_path), []),
    )
    module.record_mongo_engine_identity(support, runtime)
    monkeypatch.setattr(
        module,
        "_observe_running_mongo_storage",
        lambda *_args, **_kwargs: (None, []),
    )

    with pytest.raises(
        module.UpgradeTransactionError,
        match="does not prove a cleanly stopped engine",
    ):
        module.mongo_storage_inventory(support, runtime)


def test_docker_receipt_uses_immutable_image_id_after_mutable_tag_retarget(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_transaction_module()
    support, runtime, data_path = build_bind_fixture(tmp_path)
    old_image_id = "sha256:" + "b" * 64
    observed = {
        "backend": "app_support_bind",
        "runtime_engine": "docker",
        "profile": "isolated",
        "path": str(data_path),
        "image": "mongo:8.0",
        "image_id": old_image_id,
        "container_name": "viventium-mongodb-isolated",
        "container_running": True,
        "observed_from": "container_inspect",
    }
    monkeypatch.setattr(
        module,
        "_observe_running_mongo_storage",
        lambda *_args, **_kwargs: (observed, []),
    )
    module.record_mongo_engine_identity(support, runtime)
    monkeypatch.setattr(
        module,
        "_observe_running_mongo_storage",
        lambda *_args, **_kwargs: (None, []),
    )
    module.seal_mongo_engine_identity(support, runtime)
    monkeypatch.setattr(module, "docker_ready", lambda: "/fake/docker")
    inspected: list[tuple[str, ...]] = []

    def docker_command(_docker, *args, check=True):
        inspected.append(tuple(args))
        if args == ("image", "inspect", old_image_id):
            return subprocess.CompletedProcess(
                args,
                0,
                json.dumps([{"Id": old_image_id}]).encode("utf-8"),
                b"",
            )
        # The mutable tag now points elsewhere; it must not be consulted.
        if args == ("image", "inspect", "mongo:8.0"):
            return subprocess.CompletedProcess(
                args,
                0,
                json.dumps([{"Id": "sha256:" + "c" * 64}]).encode("utf-8"),
                b"",
            )
        return subprocess.CompletedProcess(args, 1, b"", b"")

    monkeypatch.setattr(module, "docker_command", docker_command)

    inventory, _ = module.mongo_storage_inventory(support, runtime)

    assert inventory["image_id"] == old_image_id
    assert inventory["image"] == "mongo:8.0"
    assert ("image", "inspect", old_image_id) in inspected
    assert ("image", "inspect", "mongo:8.0") not in inspected


def test_stopped_docker_receipt_fails_when_immutable_image_prerequisite_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_transaction_module()
    support, runtime, data_path = build_bind_fixture(tmp_path)
    observed = {
        "backend": "app_support_bind",
        "runtime_engine": "docker",
        "profile": "isolated",
        "path": str(data_path),
        "image": "mongo:8.0.17",
        "image_id": "sha256:" + "d" * 64,
        "container_name": "viventium-mongodb-isolated",
        "container_running": True,
        "observed_from": "container_inspect",
    }
    monkeypatch.setattr(
        module,
        "_observe_running_mongo_storage",
        lambda *_args, **_kwargs: (observed, []),
    )
    module.record_mongo_engine_identity(support, runtime)
    monkeypatch.setattr(
        module,
        "_observe_running_mongo_storage",
        lambda *_args, **_kwargs: (None, []),
    )
    module.seal_mongo_engine_identity(support, runtime)
    monkeypatch.setattr(
        module,
        "docker_ready",
        lambda: (_ for _ in ()).throw(
            module.UpgradeTransactionError("Docker is unavailable")
        ),
    )

    with pytest.raises(
        module.UpgradeTransactionError,
        match="recorded immutable Docker engine is unavailable",
    ):
        module.mongo_storage_inventory(support, runtime)


def test_stopped_docker_named_volume_revalidates_volume_and_immutable_image(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_transaction_module()
    support, runtime, _ = build_bind_fixture(tmp_path)
    container = "viventium-mongodb-isolated"
    volume = "viventium-mongodb-isolated-data"
    image_id = "sha256:" + "e" * 64
    (runtime / "runtime.env").write_text(
        "\n".join(
            [
                "VIVENTIUM_RUNTIME_PROFILE=isolated",
                f"VIVENTIUM_LOCAL_MONGO_CONTAINER={container}",
                f"VIVENTIUM_LOCAL_MONGO_VOLUME={volume}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    observed = {
        "backend": "docker_named_volume",
        "runtime_engine": "docker",
        "profile": "isolated",
        "volume_name": volume,
        "image": "mongo:8.0",
        "image_id": image_id,
        "container_name": container,
        "container_running": True,
        "observed_from": "container_inspect",
    }
    observations = iter(((observed, []), (None, []), (None, [])))
    monkeypatch.setattr(
        module,
        "_observe_running_mongo_storage",
        lambda *_args, **_kwargs: next(observations),
    )
    monkeypatch.setattr(module, "docker_ready", lambda: "/fake/docker")
    inspected: list[tuple[str, ...]] = []

    def docker_command(_docker, *args, check=True):
        inspected.append(tuple(args))
        if args == ("volume", "inspect", volume):
            payload = [
                {
                    "Name": volume,
                    "Driver": "local",
                    "Scope": "local",
                    "Labels": {"com.viventium.runtime": "isolated"},
                    "Options": {},
                }
            ]
            return subprocess.CompletedProcess(
                args, 0, json.dumps(payload).encode("utf-8"), b""
            )
        if args == ("image", "inspect", image_id):
            return subprocess.CompletedProcess(
                args,
                0,
                json.dumps([{"Id": image_id}]).encode("utf-8"),
                b"",
            )
        return subprocess.CompletedProcess(args, 1, b"", b"")

    monkeypatch.setattr(module, "docker_command", docker_command)

    module.record_mongo_engine_identity(support, runtime)
    sealed = module.seal_mongo_engine_identity(support, runtime)
    inventory, extra_surfaces = module.mongo_storage_inventory(support, runtime)

    assert sealed["storage_anchor"]["kind"] == "docker-volume"
    assert inventory["backend"] == "docker_named_volume"
    assert inventory["volume_name"] == volume
    assert inventory["image_id"] == image_id
    assert inventory["observed_from"] == "engine_identity_receipt"
    assert extra_surfaces == []
    assert inspected.count(("volume", "inspect", volume)) == 2
    assert ("image", "inspect", image_id) in inspected


def test_stopped_native_receipt_fails_when_recorded_executable_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_transaction_module()
    support, runtime, data_path = build_bind_fixture(tmp_path)
    executable = tmp_path / "runtime-tools" / "mongod"
    executable.parent.mkdir()
    executable.write_text(
        "#!/bin/sh\nprintf '%s\\n' 'db version v8.0.23'\n",
        encoding="utf-8",
    )
    executable.chmod(0o700)
    observed = native_inventory(data_path)
    observed["executable"] = str(executable)
    observed["executable_sha256"] = module.sha256_file(executable)
    observations = iter(((observed, []), (None, []), (None, [])))
    monkeypatch.setattr(
        module,
        "_observe_running_mongo_storage",
        lambda *_args, **_kwargs: next(observations),
    )

    module.record_mongo_engine_identity(support, runtime)
    module.seal_mongo_engine_identity(support, runtime)
    executable.unlink()

    with pytest.raises(
        module.UpgradeTransactionError,
        match="recorded native MongoDB engine is unavailable",
    ):
        module.mongo_storage_inventory(support, runtime)


def test_receipt_rejects_group_readable_or_symlink_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_transaction_module()
    support, runtime, data_path = build_bind_fixture(tmp_path)
    monkeypatch.setattr(
        module,
        "_observe_running_mongo_storage",
        lambda *_args, **_kwargs: (native_inventory(data_path), []),
    )
    module.record_mongo_engine_identity(support, runtime)
    receipt = support / module.MONGO_ENGINE_IDENTITY_RECEIPT
    receipt.chmod(0o640)
    monkeypatch.setattr(
        module,
        "_observe_running_mongo_storage",
        lambda *_args, **_kwargs: (None, []),
    )

    with pytest.raises(module.UpgradeTransactionError, match="owner-only"):
        module.mongo_storage_inventory(support, runtime)

    receipt.unlink()
    receipt.symlink_to(runtime / "runtime.env")
    with pytest.raises(module.UpgradeTransactionError, match="unsafe"):
        module.mongo_storage_inventory(support, runtime)


def test_failed_receipt_replace_preserves_previous_proof(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_transaction_module()
    support, runtime, data_path = build_bind_fixture(tmp_path)
    monkeypatch.setattr(
        module,
        "_observe_running_mongo_storage",
        lambda *_args, **_kwargs: (native_inventory(data_path), []),
    )
    module.record_mongo_engine_identity(support, runtime)
    receipt = support / module.MONGO_ENGINE_IDENTITY_RECEIPT
    before = receipt.read_bytes()
    real_replace = os.replace

    def fail_receipt_replace(source, destination):
        if Path(destination) == receipt:
            raise OSError("synthetic replace failure")
        return real_replace(source, destination)

    monkeypatch.setattr(module.os, "replace", fail_receipt_replace)

    with pytest.raises(OSError, match="synthetic replace failure"):
        module.record_mongo_engine_identity(support, runtime)

    assert receipt.read_bytes() == before


def test_runtime_start_and_clean_stop_paths_refresh_and_seal_engine_proof() -> None:
    launcher = LAUNCHER.read_text(encoding="utf-8")
    native_stack = NATIVE_STACK.read_text(encoding="utf-8")
    stop_only_gate = launcher.index('if [[ "$STOP_ONLY" == "true" ]]')

    assert IDENTITY_CLI.is_file()
    assert (
        'MONGO_NATIVE_PID_FILE="${VIVENTIUM_MONGO_NATIVE_PID_FILE:-'
        '$VIVENTIUM_APP_SUPPORT_ROOT/state/native/mongod.pid}"'
        in launcher
    )
    assert (
        'MONGO_PID_FILE="${VIVENTIUM_MONGO_NATIVE_PID_FILE:-'
        '$NATIVE_STATE_DIR/mongod.pid}"'
        in native_stack
    )
    assert "stop-recorded-native-engine" in launcher
    assert "stop-recorded-native-engine" in native_stack
    stop_services = launcher[
        launcher.index("stop_running_services() {") :
        launcher.index("cleanup_stale_containers() {")
    ]
    assert stop_services.index("stop_recorded_native_mongo_engine") < stop_services.index(
        "seal_mongo_engine_identity_after_stop"
    )
    assert "record_mongo_engine_identity" in launcher
    assert "prepare_mongo_engine_identity_for_stop" in launcher
    assert "seal_mongo_engine_identity_after_stop" in launcher
    assert launcher.index("prepare_mongo_engine_identity_for_stop") < launcher.index(
        'docker rm -f "$mongo_container"'
    )
    prepare_function = launcher.split(
        "prepare_mongo_engine_identity_for_stop() {", 1
    )[1].split("\n}", 1)[0]
    assert "record_mongo_engine_identity" in prepare_function
    assert "port_has_listener" in prepare_function
    assert "port_in_use" not in prepare_function
    assert launcher.index("port_has_listener() {") < stop_only_gate
    assert "State.Running" in prepare_function
    assert "mongo_ping" not in prepare_function
    assert "record-mongo-engine" in native_stack
    assert "seal-mongo-engine" in native_stack
    start_case = native_stack.split('  start)', 1)[1].split('    ;;', 1)[0]
    stop_case = native_stack.split('  stop)', 1)[1].split('    ;;', 1)[0]
    assert start_case.index("record-mongo-engine") > start_case.index("start_mongo")
    assert stop_case.index("prepare_native_mongo_engine_identity_for_stop") < stop_case.index(
        "stop_recorded_native_mongo_engine"
    )
    assert stop_case.index("seal_native_mongo_engine_identity_after_stop") > stop_case.index(
        "stop_recorded_native_mongo_engine"
    )
    assert 'stop_pid_file "$MONGO_PID_FILE"' not in stop_case


def test_engine_receipt_is_a_dedicated_transaction_surface(
    tmp_path: Path,
) -> None:
    module = load_transaction_module()
    support, runtime, _ = build_bind_fixture(tmp_path)
    candidates = module.checkpoint_surface_candidates(
        support,
        support / "config.yaml",
        runtime,
    )

    assert (
        module.MONGO_ENGINE_IDENTITY_SURFACE_LABEL,
        support / module.MONGO_ENGINE_IDENTITY_RECEIPT,
        False,
    ) in candidates
