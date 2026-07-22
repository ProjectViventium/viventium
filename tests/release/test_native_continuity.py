from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
NATIVE_RUNTIME = REPO_ROOT / "scripts" / "viventium" / "native_runtime.py"
NATIVE_CLI = REPO_ROOT / "scripts" / "viventium" / "native_cli.sh"
ASSEMBLER = REPO_ROOT / "scripts" / "viventium" / "assemble_native_payload.py"
CONTINUITY_BUNDLE = REPO_ROOT / "scripts" / "viventium" / "continuity_bundle.py"


def load_native_runtime():
    spec = importlib.util.spec_from_file_location("viventium_native_continuity_runtime", NATIVE_RUNTIME)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_continuity_bundle():
    spec = importlib.util.spec_from_file_location("viventium_native_continuity_bundle_test", CONTINUITY_BUNDLE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def private_file(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_bytes(content)
    path.chmod(0o600)
    return path


def private_tree(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    for current in [path, *path.parents]:
        if current.name.startswith(("support", ".native-restore")):
            current.chmod(0o700)
    return path


def privatize_tree(path: Path) -> None:
    for current in sorted(path.rglob("*"), reverse=True):
        if current.is_symlink():
            continue
        current.chmod(0o700 if current.is_dir() else 0o600)
    path.chmod(0o700)


def make_active_state(support: Path, marker: bytes) -> None:
    private_tree(support)
    private_file(support / "config.yaml", b"version: 1\nstate: " + marker + b"\n")
    private_file(support / "data" / "mongodb" / "WiredTiger", marker + b"-mongo")
    private_file(support / "data" / "uploads" / "asset.txt", marker + b"-upload")
    private_file(
        support / "state" / "runtime" / "native" / "scheduling" / "schedules.db",
        marker + b"-schedule",
    )
    private_file(
        support / "state" / "runtime" / "native" / "continuity" / "old.json",
        marker + b"-continuity",
    )
    private_tree(support / "backups")
    privatize_tree(support)


def make_staged_state(stage: Path, marker: bytes) -> None:
    private_tree(stage)
    private_file(stage / "config.yaml", b"version: 1\nstate: " + marker + b"\n")
    private_file(stage / "data" / "mongodb" / "WiredTiger", marker + b"-mongo")
    private_file(stage / "data" / "uploads" / "asset.txt", marker + b"-upload")
    private_file(
        stage / "state" / "runtime" / "native" / "scheduling" / "schedules.db",
        marker + b"-schedule",
    )
    private_file(
        stage / "state" / "runtime" / "native" / "continuity" / "reauthentication-required.json",
        b'{"schemaVersion":1}\n',
    )
    privatize_tree(stage)


def test_native_uninstall_removes_owned_payload_cache_but_preserves_user_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = load_native_runtime()
    support = tmp_path / "support"
    make_active_state(support, b"owner-state")
    private_file(support / "native" / "releases" / "release-a" / "payload.bin", b"payload")
    private_file(support / "runtime" / "runtime.env", b"generated=true\n")
    private_file(support / "logs" / "native.log", b"synthetic log\n")
    private_file(support / "helper-config.json", b"{}\n")
    private_file(support / "state" / "native-runtime.json", b"{}\n")
    privatize_tree(support)
    monkeypatch.setattr(runtime, "stop", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(runtime, "user_home", lambda: tmp_path / "home")

    runtime.uninstall(SimpleNamespace(app_support_dir=support), _lock_held=True)

    assert not (support / "native").exists()
    assert not (support / "runtime").exists()
    assert not (support / "logs").exists()
    assert not (support / "helper-config.json").exists()
    assert not (support / "state" / "native-runtime.json").exists()
    assert (support / "config.yaml").is_file()
    assert (support / "data" / "mongodb" / "WiredTiger").is_file()
    assert (support / "data" / "uploads" / "asset.txt").is_file()
    assert (support / "backups").is_dir()
    assert (support / "state" / "runtime" / "native" / "scheduling" / "schedules.db").is_file()


def test_native_uninstall_refuses_runtime_symlink_without_touching_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = load_native_runtime()
    support = tmp_path / "support"
    support.mkdir(mode=0o700)
    external = tmp_path / "personal"
    external.mkdir(mode=0o700)
    sentinel = private_file(external / "keep.txt", b"keep\n")
    (support / "runtime").symlink_to(external, target_is_directory=True)
    monkeypatch.setattr(runtime, "stop", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(runtime, "user_home", lambda: tmp_path / "home")

    with pytest.raises(runtime.RuntimeError_, match="runtime storage path is unsafe"):
        runtime.uninstall(SimpleNamespace(app_support_dir=support), _lock_held=True)

    assert sentinel.read_bytes() == b"keep\n"


def digest_tree(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix().encode()
        digest.update(relative)
        if path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()


def digest_active_state(support: Path) -> str:
    digest = hashlib.sha256()
    for relative in (
        "config.yaml",
        "data/mongodb",
        "data/uploads",
        "state/runtime/native/scheduling",
        "state/runtime/native/continuity",
        "state/native-runtime.json",
    ):
        path = support / relative
        if path.exists():
            digest.update(relative.encode())
            digest.update(digest_tree(path).encode() if path.is_dir() else path.read_bytes())
    return digest.hexdigest()


def test_native_public_cli_advertises_snapshot_and_restore() -> None:
    source = NATIVE_CLI.read_text(encoding="utf-8")
    assert "snapshot" in source
    assert "restore" in source
    assert "backup/restore" not in source


def test_native_payload_ships_the_shared_continuity_validator_and_adapter() -> None:
    source = ASSEMBLER.read_text(encoding="utf-8")
    assert "continuity_bundle.py" in source
    assert "continuity_mongo.cjs" in source


def test_native_restore_activation_rolls_back_every_owned_root_after_injected_failure(
    tmp_path: Path,
) -> None:
    runtime = load_native_runtime()
    support = tmp_path / "support"
    make_active_state(support, b"old")
    immutable_state = private_file(
        support / "state" / "native-runtime.json",
        b'{"schema_version":1,"release_root":"/immutable/release"}\n',
    )
    immutable_before = immutable_state.read_bytes()
    active_before = digest_active_state(support)
    transaction_id = "a" * 32
    stage = support / f".native-restore-stage.{transaction_id}"
    make_staged_state(stage, b"new")

    with pytest.raises(runtime.RuntimeError_, match="Injected Native restore fault"):
        runtime.activate_native_restore_state(
            support,
            stage,
            transaction_id,
            release_identity="b" * 40,
            fault_after="mongodb",
        )

    assert immutable_state.read_bytes() == immutable_before
    assert digest_active_state(support) == active_before
    assert not stage.exists()
    assert not (support / "state" / "native-restore-transaction.json").exists()


def test_native_restore_activation_commits_staged_state_without_changing_release_pointer(
    tmp_path: Path,
) -> None:
    runtime = load_native_runtime()
    support = tmp_path / "support"
    make_active_state(support, b"old")
    immutable_state = private_file(
        support / "state" / "native-runtime.json",
        b'{"schema_version":1,"release_root":"/immutable/release"}\n',
    )
    immutable_before = immutable_state.read_bytes()
    transaction_id = "c" * 32
    stage = support / f".native-restore-stage.{transaction_id}"
    make_staged_state(stage, b"new")

    checkpoint = runtime.activate_native_restore_state(
        support,
        stage,
        transaction_id,
        release_identity="d" * 40,
    )

    assert immutable_state.read_bytes() == immutable_before
    assert (support / "data" / "mongodb" / "WiredTiger").read_bytes() == b"new-mongo"
    assert (support / "data" / "uploads" / "asset.txt").read_bytes() == b"new-upload"
    assert checkpoint.is_dir()
    assert (checkpoint / "prior" / "data" / "mongodb" / "WiredTiger").read_bytes() == b"old-mongo"
    assert not stage.exists()
    assert not (support / "state" / "native-restore-transaction.json").exists()


def test_native_restore_refuses_symlink_or_non_private_staging_before_mutation(tmp_path: Path) -> None:
    runtime = load_native_runtime()
    support = tmp_path / "support"
    make_active_state(support, b"old")
    before = digest_active_state(support)
    transaction_id = "e" * 32
    stage = support / f".native-restore-stage.{transaction_id}"
    make_staged_state(stage, b"new")
    (stage / "data" / "mongodb" / "WiredTiger").unlink()
    (stage / "data" / "mongodb" / "WiredTiger").symlink_to("/tmp/escape")

    with pytest.raises(runtime.RuntimeError_, match="symlink|unsafe"):
        runtime.activate_native_restore_state(
            support,
            stage,
            transaction_id,
            release_identity="f" * 40,
        )
    assert digest_active_state(support) == before
    assert not (support / "state" / "native-restore-transaction.json").exists()

    (stage / "data" / "mongodb" / "WiredTiger").unlink()
    private_file(stage / "data" / "mongodb" / "WiredTiger", b"new-mongo").chmod(0o644)
    with pytest.raises(runtime.RuntimeError_, match="permissions|unsafe"):
        runtime.activate_native_restore_state(
            support,
            stage,
            transaction_id,
            release_identity="f" * 40,
        )
    assert digest_active_state(support) == before


def test_native_snapshot_pointer_is_published_only_after_success(tmp_path: Path, monkeypatch) -> None:
    runtime = load_native_runtime()
    support = tmp_path / "support"
    make_active_state(support, b"old")
    snapshots = private_tree(support / "snapshots")
    prior = private_tree(snapshots / "prior")
    pointer = private_file(snapshots / "LATEST_PATH", (str(prior) + "\n").encode())

    monkeypatch.setattr(runtime, "installed_release_root", lambda *_args, **_kwargs: tmp_path / "release")
    monkeypatch.setattr(runtime, "packaged_health", lambda _root: None)
    monkeypatch.setattr(runtime, "recover_native_restore", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(runtime, "owned_mongodb_socket_pid", lambda *_args: 123)
    monkeypatch.setattr(runtime, "require_owned_service", lambda *_args: 123)
    monkeypatch.setattr(runtime, "mongodb_uri", lambda _support: "mongodb://native-socket/LibreChat")
    monkeypatch.setattr(runtime, "stop_service", lambda *_args: None)
    monkeypatch.setattr(runtime, "assert_native_snapshot_capture_state", lambda *_args: None)
    monkeypatch.setattr(runtime, "restore_exact_service_state", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(runtime, "inspect_data_schema", lambda *_args: 1)
    monkeypatch.setattr(runtime, "build_metadata", lambda _root: {"source_commit": "a" * 40})

    class FailingContinuity:
        @staticmethod
        def capture_bundle(**_kwargs):
            raise RuntimeError("capture failed")

    monkeypatch.setattr(runtime, "load_continuity_module", lambda _root: FailingContinuity)
    args = type("Args", (), {"app_support_dir": support, "timeout": 1.0})()
    with pytest.raises(RuntimeError, match="capture failed"):
        runtime.snapshot(args, _lock_held=True)
    assert pointer.read_text(encoding="utf-8") == str(prior) + "\n"

    created = private_tree(snapshots / "created")

    class PassingContinuity:
        @staticmethod
        def capture_bundle(**_kwargs):
            return {"snapshotDir": str(created), "recoverable": True}

        @staticmethod
        def validate_bundle(_path):
            return {"recoverable": True}

        @staticmethod
        def validate_owned_private_bundle(_path):
            return None

    monkeypatch.setattr(runtime, "load_continuity_module", lambda _root: PassingContinuity)
    runtime.snapshot(args, _lock_held=True)
    assert pointer.read_text(encoding="utf-8") == str(created) + "\n"
    assert oct(pointer.stat().st_mode & 0o777) == "0o600"


def test_native_restore_journal_recovery_restores_prior_state(tmp_path: Path) -> None:
    runtime = load_native_runtime()
    support = tmp_path / "support"
    make_active_state(support, b"old")
    transaction_id = "1" * 32
    stage = support / f".native-restore-stage.{transaction_id}"
    make_staged_state(stage, b"new")

    with pytest.raises(runtime.RuntimeError_, match="Injected Native restore fault"):
        runtime.activate_native_restore_state(
            support,
            stage,
            transaction_id,
            release_identity="2" * 40,
            fault_after="mongodb",
            defer_rollback_for_test=True,
        )
    assert (support / "state" / "native-restore-transaction.json").is_file()

    runtime.recover_native_restore(support, release_identity="2" * 40)
    assert (support / "data" / "mongodb" / "WiredTiger").read_bytes() == b"old-mongo"
    assert not (support / "state" / "native-restore-transaction.json").exists()


def test_native_restore_staging_must_share_the_app_support_filesystem(tmp_path: Path, monkeypatch) -> None:
    runtime = load_native_runtime()
    support = tmp_path / "support"
    make_active_state(support, b"old")
    transaction_id = "3" * 32
    stage = support / f".native-restore-stage.{transaction_id}"
    make_staged_state(stage, b"new")
    real_stat = os.stat

    def different_device(path, *args, **kwargs):
        result = real_stat(path, *args, **kwargs)
        if Path(path) == stage:
            values = list(result)
            values[2] = result.st_dev + 1
            return os.stat_result(values)
        return result

    monkeypatch.setattr(runtime.os, "stat", different_device)
    with pytest.raises(runtime.RuntimeError_, match="same filesystem"):
        runtime.activate_native_restore_state(
            support,
            stage,
            transaction_id,
            release_identity="4" * 40,
        )
    assert (support / "data" / "mongodb" / "WiredTiger").read_bytes() == b"old-mongo"


def test_native_staging_journal_recovery_removes_only_transaction_owned_stage(tmp_path: Path) -> None:
    runtime = load_native_runtime()
    support = tmp_path / "support"
    make_active_state(support, b"old")
    before = digest_active_state(support)
    transaction_id = "5" * 32
    runtime.begin_native_restore(
        support,
        transaction_id,
        release_identity="6" * 40,
    )
    stage = support / f".native-restore-stage.{transaction_id}"
    make_staged_state(stage, b"new")

    runtime.recover_native_restore(support, release_identity="6" * 40)

    assert digest_active_state(support) == before
    assert not stage.exists()
    assert not (support / "state" / "native-restore-transaction.json").exists()


def test_native_restore_rejects_hardlinked_staging_file_before_journal(tmp_path: Path) -> None:
    runtime = load_native_runtime()
    support = tmp_path / "support"
    make_active_state(support, b"old")
    before = digest_active_state(support)
    transaction_id = "7" * 32
    stage = support / f".native-restore-stage.{transaction_id}"
    make_staged_state(stage, b"new")
    linked = stage / "config-copy.yaml"
    os.link(stage / "config.yaml", linked)

    with pytest.raises(runtime.RuntimeError_, match="hard-linked"):
        runtime.activate_native_restore_state(
            support,
            stage,
            transaction_id,
            release_identity="8" * 40,
        )
    assert digest_active_state(support) == before
    assert not (support / "state" / "native-restore-transaction.json").exists()


def test_continuity_adapter_selects_the_bundled_native_node_runtime(
    tmp_path: Path, monkeypatch
) -> None:
    continuity = load_continuity_bundle()
    root = tmp_path / "release"
    node = private_file(root / "runtime" / "node" / "bin" / "node", b"#!/bin/sh\n")
    node.chmod(0o700)
    private_file(root / "runtime" / "librechat" / "package.json", b"{}\n")
    private_tree(root / "runtime" / "librechat" / "node_modules")
    adapter = private_file(root / "runtime" / "scripts" / "continuity_mongo.cjs", b"// adapter\n")
    monkeypatch.setattr(continuity.shutil, "which", lambda _name: None)
    monkeypatch.setattr(continuity, "__file__", str(adapter))

    selected = continuity.node_mongo_adapter(root)

    assert selected == (str(node), adapter)
    socket_path = tmp_path / "private.sock"
    uri = continuity.native_mongo_uri(socket_path)
    assert uri.startswith("mongodb://%2F")
    assert uri.endswith("/LibreChat")


def test_native_restore_journal_rejects_impossible_phase_and_flag_combinations(
    tmp_path: Path,
) -> None:
    runtime = load_native_runtime()
    support = tmp_path / "support"
    make_active_state(support, b"old")
    release_identity = "9" * 40
    payload = runtime.new_native_restore_journal("a" * 32, release_identity)

    payload["phase"] = "unknown"
    runtime.write_native_restore_journal(support, payload)
    with pytest.raises(runtime.RuntimeError_, match="phase|state"):
        runtime.read_native_restore_journal(support, release_identity=release_identity)

    payload = runtime.new_native_restore_journal("a" * 32, release_identity)
    payload["phase"] = "activation_pending"
    first = payload["roots"][runtime.NATIVE_RESTORE_ROOTS[0]]
    first["priorMoved"] = True
    runtime.write_native_restore_journal(support, payload)
    with pytest.raises(runtime.RuntimeError_, match="root state"):
        runtime.read_native_restore_journal(support, release_identity=release_identity)

    payload = runtime.new_native_restore_journal("a" * 32, release_identity)
    del payload["priorServices"]
    runtime.write_native_restore_journal(support, payload)
    with pytest.raises(runtime.RuntimeError_, match="journal"):
        runtime.read_native_restore_journal(support, release_identity=release_identity)


def test_native_restore_recovery_prevalidates_complete_checkpoint_before_deleting_new_state(
    tmp_path: Path,
) -> None:
    runtime = load_native_runtime()
    support = tmp_path / "support"
    make_active_state(support, b"old")
    transaction_id = "b" * 32
    release_identity = "c" * 40
    stage = support / f".native-restore-stage.{transaction_id}"
    make_staged_state(stage, b"new")

    with pytest.raises(runtime.RuntimeError_, match="Injected Native restore fault"):
        runtime.activate_native_restore_state(
            support,
            stage,
            transaction_id,
            release_identity=release_identity,
            fault_after="mongodb",
            defer_rollback_for_test=True,
        )
    checkpoint = support / "backups" / f"native-restore-{transaction_id}" / "prior"
    (checkpoint / "config.yaml").unlink()
    active_new_before = (support / "data" / "mongodb" / "WiredTiger").read_bytes()

    with pytest.raises(runtime.RuntimeError_) as error:
        runtime.recover_native_restore(support, release_identity=release_identity)

    assert "untouched" not in str(error.value).lower()
    assert (support / "data" / "mongodb" / "WiredTiger").read_bytes() == active_new_before
    assert runtime.native_restore_journal_path(support).is_file()


def test_native_restore_resumes_after_process_loss_mid_rollback_prior_move(
    tmp_path: Path,
) -> None:
    runtime = load_native_runtime()
    support = tmp_path / "support"
    make_active_state(support, b"old")
    active_before = digest_active_state(support)
    transaction_id = "6" * 32
    release_identity = "7" * 40
    stage = support / f".native-restore-stage.{transaction_id}"
    make_staged_state(stage, b"new")

    with pytest.raises(runtime.RuntimeError_, match="Injected Native restore fault"):
        runtime.activate_native_restore_state(
            support,
            stage,
            transaction_id,
            release_identity=release_identity,
            fault_after="mongodb",
            defer_rollback_for_test=True,
        )
    payload = runtime.read_native_restore_journal(
        support,
        release_identity=release_identity,
    )
    with pytest.raises(runtime.RuntimeError_, match="Injected Native rollback fault"):
        runtime.rollback_native_restore_from_journal(
            support,
            payload,
            fault_after_prior_restore="mongodb",
        )

    interrupted = runtime.read_native_restore_journal(
        support,
        release_identity=release_identity,
    )
    assert interrupted["phase"] == "rolling_back"
    assert interrupted["roots"]["data/mongodb"]["rollbackState"] == "prior_restore_pending"

    runtime.recover_native_restore(support, release_identity=release_identity)

    assert digest_active_state(support) == active_before
    assert not runtime.native_restore_journal_path(support).exists()


def test_native_restore_quiescence_fails_closed_when_pid_records_are_missing_but_listener_remains(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = load_native_runtime()
    support = tmp_path / "support"
    make_active_state(support, b"old")
    root = tmp_path / "release"
    monkeypatch.setattr(runtime, "live_pid", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(runtime, "listener_pids", lambda port: {4242} if port == 3190 else set())
    monkeypatch.setattr(runtime, "unix_socket_pids", lambda _path: set())
    monkeypatch.setattr(runtime, "processes_using_native_mutable_state", lambda *_args: set())

    with pytest.raises(runtime.RuntimeError_, match="quiesc|listener"):
        runtime.assert_native_restore_quiesced(support, root, transaction_id="d" * 32)


def test_native_restore_quiescence_includes_isolated_sandpack_listener(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = load_native_runtime()
    support = tmp_path / "support"
    root = tmp_path / "release"
    monkeypatch.setattr(runtime, "listener_pids", lambda port: {4242} if port == 3191 else set())
    monkeypatch.setattr(runtime, "unix_socket_pids", lambda _path: set())
    monkeypatch.setattr(runtime, "live_pid", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(runtime, "processes_using_native_mutable_state", lambda *_args, **_kwargs: set())

    with pytest.raises(runtime.RuntimeError_, match="quiesc|listener"):
        runtime.assert_native_restore_quiesced(support, root, transaction_id="e" * 32)


def test_invalid_snapshot_is_staged_before_journal_or_runtime_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = load_native_runtime()
    support = tmp_path / "support"
    make_active_state(support, b"old")
    private_file(
        support / "state" / "native-runtime.json",
        b'{"schema_version":1,"release_root":"/immutable/release"}\n',
    )
    root = tmp_path / "release"
    events: list[str] = []
    monkeypatch.setattr(runtime, "installed_release_root", lambda *_args, **_kwargs: root)
    monkeypatch.setattr(runtime, "packaged_health", lambda _root: None)
    monkeypatch.setattr(runtime, "build_metadata", lambda _root: {"source_commit": "e" * 40})
    monkeypatch.setattr(runtime, "recover_native_restore_before_lifecycle", lambda *_args: None)
    monkeypatch.setattr(runtime, "validate_native_socket_lengths", lambda _support: None)
    monkeypatch.setattr(
        runtime,
        "guard_pid_snapshot",
        lambda *_args: {name: None for name in runtime.SERVICE_ORDER},
    )
    monkeypatch.setattr(runtime, "load_continuity_module", lambda _root: object())
    monkeypatch.setattr(runtime, "begin_native_restore", lambda *_args, **_kwargs: events.append("journal"))

    def reject_stage(*_args, **_kwargs):
        events.append("stage")
        raise runtime.RuntimeError_("invalid snapshot")

    monkeypatch.setattr(runtime, "prepare_native_restore_stage", reject_stage)
    monkeypatch.setattr(runtime, "stop_service", lambda *_args: events.append("stop"))
    args = SimpleNamespace(
        app_support_dir=support,
        snapshot=tmp_path / "invalid-snapshot",
        timeout=1.0,
        no_start=True,
    )

    with pytest.raises(runtime.RuntimeError_, match="invalid snapshot"):
        runtime.restore(args, _lock_held=True)

    assert events == ["stage"]


def test_native_restore_rejects_an_overlong_socket_path_before_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = load_native_runtime()
    support = tmp_path / "support"
    make_active_state(support, b"old")
    private_file(
        support / "state" / "native-runtime.json",
        b'{"schema_version":1,"release_root":"/immutable/release"}\n',
    )
    root = tmp_path / "release"
    events: list[str] = []
    monkeypatch.setattr(runtime, "installed_release_root", lambda *_args, **_kwargs: root)
    monkeypatch.setattr(runtime, "packaged_health", lambda _root: None)
    monkeypatch.setattr(runtime, "build_metadata", lambda _root: {"source_commit": "e" * 40})
    monkeypatch.setattr(runtime, "recover_native_restore_before_lifecycle", lambda *_args: None)
    monkeypatch.setattr(
        runtime,
        "guard_pid_snapshot",
        lambda *_args: {name: None for name in runtime.SERVICE_ORDER},
    )
    monkeypatch.setattr(runtime, "load_continuity_module", lambda _root: object())
    monkeypatch.setattr(
        runtime,
        "validate_native_socket_lengths",
        lambda _support: (_ for _ in ()).throw(
            runtime.RuntimeError_("too long for private service sockets")
        ),
    )

    def stage_should_not_run(*_args, **_kwargs):
        events.append("stage")
        raise runtime.RuntimeError_("stage ran")

    monkeypatch.setattr(runtime, "prepare_native_restore_stage", stage_should_not_run)
    args = SimpleNamespace(
        app_support_dir=support,
        snapshot=tmp_path / "snapshot",
        timeout=1.0,
        no_start=True,
    )

    with pytest.raises(runtime.RuntimeError_, match="too long for private service sockets"):
        runtime.restore(args, _lock_held=True)

    assert events == []


def test_process_loss_recovery_replays_exact_prior_service_intent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = load_native_runtime()
    support = tmp_path / "support"
    make_active_state(support, b"old")
    root = tmp_path / "release"
    prior = {"mongodb": 101, "librechat": 102, "frontend-proxy": 103}
    runtime.begin_native_restore(
        support,
        "2" * 32,
        release_identity="3" * 40,
        prior_services=prior,
    )
    events: list[str] = []
    monkeypatch.setattr(
        runtime,
        "build_metadata",
        lambda _root: {"source_commit": "3" * 40},
    )
    monkeypatch.setattr(
        runtime,
        "stop_restore_mongod",
        lambda *_args: events.append("stop-staging"),
    )
    monkeypatch.setattr(
        runtime,
        "stop_service",
        lambda service, *_args: events.append(f"stop:{service}"),
    )

    def restore_exact(_support, _root, observed, *, timeout):
        del timeout
        events.append("restore-exact")
        assert {name for name, pid in observed.items() if pid is not None} == set(
            runtime.SERVICE_ORDER
        )

    monkeypatch.setattr(runtime, "restore_exact_service_state", restore_exact)

    runtime.recover_native_restore_before_lifecycle(support, root)

    assert events == [
        "stop-staging",
        "stop:frontend-proxy",
        "stop:librechat",
        "stop:mongodb",
        "restore-exact",
    ]
    assert not runtime.native_restore_journal_path(support).exists()


def test_top_level_restore_restores_prior_services_after_activation_auto_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = load_native_runtime()
    support = tmp_path / "support"
    make_active_state(support, b"old")
    private_file(
        support / "state" / "native-runtime.json",
        b'{"schema_version":1,"release_root":"/immutable/release"}\n',
    )
    root = tmp_path / "release"
    stage = support / f".native-restore-stage.{'4' * 32}"
    make_staged_state(stage, b"new")
    prior = {"mongodb": 101, "librechat": 102, "frontend-proxy": 103}
    restored: list[set[str]] = []
    monkeypatch.setattr(runtime.uuid, "uuid4", lambda: SimpleNamespace(hex="4" * 32))
    monkeypatch.setattr(runtime, "installed_release_root", lambda *_args, **_kwargs: root)
    monkeypatch.setattr(runtime, "packaged_health", lambda _root: None)
    monkeypatch.setattr(runtime, "build_metadata", lambda _root: {"source_commit": "5" * 40})
    monkeypatch.setattr(runtime, "recover_native_restore_before_lifecycle", lambda *_args: None)
    monkeypatch.setattr(runtime, "validate_native_socket_lengths", lambda _support: None)
    monkeypatch.setattr(runtime, "guard_pid_snapshot", lambda *_args: prior.copy())
    monkeypatch.setattr(runtime, "load_continuity_module", lambda _root: object())
    monkeypatch.setattr(runtime, "prepare_native_restore_stage", lambda *_args, **_kwargs: stage)
    monkeypatch.setattr(runtime, "stop_service", lambda *_args: None)
    monkeypatch.setattr(runtime, "stop_restore_mongod", lambda *_args: None)
    monkeypatch.setattr(runtime, "assert_native_restore_quiesced", lambda *_args, **_kwargs: None)

    def fail_after_auto_rollback(*_args, **_kwargs):
        runtime.native_restore_journal_path(support).unlink()
        raise runtime.RuntimeError_("activation failed after automatic rollback")

    monkeypatch.setattr(runtime, "activate_native_restore_state", fail_after_auto_rollback)
    monkeypatch.setattr(
        runtime,
        "restore_exact_service_state",
        lambda _support, _root, observed, **_kwargs: restored.append(
            {name for name, pid in observed.items() if pid is not None}
        ),
    )
    args = SimpleNamespace(
        app_support_dir=support,
        snapshot=tmp_path / "snapshot",
        timeout=1.0,
        no_start=False,
    )

    with pytest.raises(runtime.RuntimeError_, match="activation failed"):
        runtime.restore(args, _lock_held=True)

    assert restored == [set(runtime.SERVICE_ORDER)]


def test_native_snapshot_quiesces_writers_and_restores_exact_prior_service_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = load_native_runtime()
    support = tmp_path / "support"
    make_active_state(support, b"old")
    root = tmp_path / "release"
    created = private_tree(support / "snapshots" / "created")
    events: list[str] = []
    prior = {"mongodb": 101, "librechat": 102, "frontend-proxy": 103}
    monkeypatch.setattr(runtime, "installed_release_root", lambda *_args, **_kwargs: root)
    monkeypatch.setattr(runtime, "packaged_health", lambda _root: None)
    monkeypatch.setattr(runtime, "recover_native_restore_before_lifecycle", lambda *_args: None)
    monkeypatch.setattr(runtime, "guard_pid_snapshot", lambda *_args: prior.copy())
    monkeypatch.setattr(runtime, "owned_mongodb_socket_pid", lambda *_args: 101)
    monkeypatch.setattr(runtime, "require_owned_service", lambda service, *_args: prior[service])
    monkeypatch.setattr(runtime, "stop_service", lambda service, *_args: events.append(f"stop:{service}"))
    monkeypatch.setattr(runtime, "assert_native_snapshot_capture_state", lambda *_args: events.append("capture-state"))
    monkeypatch.setattr(runtime, "restore_exact_service_state", lambda *_args, **_kwargs: events.append("restore-exact"))
    monkeypatch.setattr(runtime, "inspect_data_schema", lambda *_args: 1)
    monkeypatch.setattr(runtime, "build_metadata", lambda _root: {"source_commit": "f" * 40})

    class Continuity:
        @staticmethod
        def capture_bundle(**kwargs):
            assert kwargs["data_schema"] == 1
            events.append("capture")
            return {"snapshotDir": str(created), "recoverable": True}

        @staticmethod
        def validate_bundle(_path):
            return {"recoverable": True}

        @staticmethod
        def validate_owned_private_bundle(_path):
            return None

    monkeypatch.setattr(runtime, "load_continuity_module", lambda _root: Continuity)
    args = SimpleNamespace(app_support_dir=support, timeout=1.0)

    runtime.snapshot(args, _lock_held=True)

    assert events == [
        "stop:frontend-proxy",
        "stop:librechat",
        "capture-state",
        "capture",
        "restore-exact",
    ]


def test_native_restore_rejects_incompatible_snapshot_data_schema(tmp_path: Path) -> None:
    runtime = load_native_runtime()
    support = tmp_path / "support"
    make_active_state(support, b"old")
    metadata = {"data_schema": {"minimum": 2, "maximum": 4, "target": 3}}

    with pytest.raises(runtime.RuntimeError_, match="data schema"):
        runtime.validate_native_snapshot_data_schema(
            {"runtimeSelection": {"dataSchema": 1}},
            metadata,
            current_schema=3,
        )

    runtime.validate_native_snapshot_data_schema(
        {"runtimeSelection": {"dataSchema": 3}},
        metadata,
        current_schema=3,
    )


def test_native_restore_disk_preflight_fails_before_copy_when_capacity_is_insufficient(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = load_native_runtime()
    support = tmp_path / "support"
    snapshot = private_tree(tmp_path / "snapshot")
    private_file(snapshot / "payload", b"x" * 1024)
    make_active_state(support, b"old")
    monkeypatch.setattr(runtime.shutil, "disk_usage", lambda _path: SimpleNamespace(free=1))

    with pytest.raises(runtime.RuntimeError_, match="disk space"):
        runtime.preflight_native_restore_capacity(snapshot, support, timeout=1.0)


def test_native_restore_expansion_preflight_uses_declared_logical_size(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = load_native_runtime()
    support = private_tree(tmp_path / "support")
    manifest = {
        "artifacts": [
            {
                "size": 1024,
                "uncompressedSize": 4 * 1024 * 1024,
            }
        ]
    }
    monkeypatch.setattr(
        runtime.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(free=runtime.NATIVE_CONTINUITY_MIN_FREE_RESERVE + 1),
    )

    with pytest.raises(runtime.RuntimeError_, match="disk space"):
        runtime.preflight_native_restore_expansion_capacity(manifest, support)


def test_read_only_lifecycle_command_fails_closed_on_pending_restore(tmp_path: Path) -> None:
    runtime = load_native_runtime()
    support = tmp_path / "support"
    make_active_state(support, b"old")
    runtime.begin_native_restore(support, "f" * 32, release_identity="1" * 40)

    with pytest.raises(runtime.RuntimeError_, match="recovery"):
        runtime.reject_pending_restore_for_read(support)
    with pytest.raises(runtime.RuntimeError_, match="recovery"):
        runtime.status(SimpleNamespace(app_support_dir=support))


def test_native_restore_private_input_copy_detects_mid_copy_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = load_native_runtime()
    source = private_tree(tmp_path / "snapshot")
    payload = private_file(source / "payload.json", b'{"value":"before"}\n')
    destination = tmp_path / "support" / f".native-restore-stage.{'a' * 32}" / ".snapshot-input"
    private_tree(destination.parent.parent)
    private_tree(destination.parent)
    original = runtime.copy_private_file
    mutated = False

    def mutate_after_copy(source_path: Path, destination_path: Path) -> None:
        nonlocal mutated
        original(source_path, destination_path)
        if not mutated:
            payload.write_bytes(b'{"value":"changed"}\n')
            payload.chmod(0o600)
            mutated = True

    monkeypatch.setattr(runtime, "copy_private_file", mutate_after_copy)

    with pytest.raises(runtime.RuntimeError_, match="changed"):
        runtime.copy_verified_private_tree(source, destination, timeout=2.0)

    assert not destination.exists()


def test_private_file_copy_binds_nofollow_source_descriptor_to_validated_inode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = load_native_runtime()
    source = private_file(tmp_path / "source" / "payload", b"validated")
    destination = tmp_path / "destination" / "payload"
    original_open = runtime.os.open
    swapped = False

    def swap_before_source_open(path, flags, *args, **kwargs):
        nonlocal swapped
        if Path(path) == source and not swapped:
            swapped = True
            source.unlink()
            source.write_bytes(b"replacement")
            source.chmod(0o600)
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(runtime.os, "open", swap_before_source_open)

    with pytest.raises(runtime.RuntimeError_, match="changed|unsafe"):
        runtime.copy_private_file(source, destination)

    assert not destination.exists()


def test_durable_restore_rename_fsyncs_both_parents_and_transaction_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = load_native_runtime()
    source_parent = private_tree(tmp_path / "source")
    destination_parent = private_tree(tmp_path / "destination")
    transaction = private_tree(tmp_path / "transaction")
    source = private_file(source_parent / "state", b"old")
    destination = destination_parent / "state"
    synced: list[Path] = []
    monkeypatch.setattr(runtime, "fsync_directory", lambda path: synced.append(path))

    runtime.durable_replace(source, destination, transaction)

    assert destination.read_bytes() == b"old"
    assert set(synced) == {source_parent, destination_parent, transaction}
