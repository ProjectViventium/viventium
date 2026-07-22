from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
TRANSACTION = REPO_ROOT / "scripts" / "viventium" / "upgrade_transaction.py"


def load_transaction_module():
    spec = importlib.util.spec_from_file_location("viventium_upgrade_transaction_test", TRANSACTION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(
    *args: str,
    check: bool = False,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TRANSACTION), *args],
        check=check,
        capture_output=True,
        text=True,
        env=env,
    )


def git(path: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(path), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def commit(path: Path, message: str) -> str:
    git(path, "add", ".")
    git(path, "-c", "user.name=QA", "-c", "user.email=qa@example.com", "commit", "-m", message)
    return git(path, "rev-parse", "HEAD")


def build_fixture(tmp_path: Path) -> tuple[Path, Path, Path, str, str, str]:
    repo = tmp_path / "repo"
    component = repo / "components" / "example"
    component.mkdir(parents=True)
    git(component, "init")
    (component / "component.txt").write_text("old component\n", encoding="utf-8")
    component_old = commit(component, "old component")
    (component / "component.txt").write_text("new component\n", encoding="utf-8")
    component_target = commit(component, "new component")
    git(component, "checkout", "--detach", component_old)

    git(repo, "init")
    (repo / "product.txt").write_text("old product\n", encoding="utf-8")
    (repo / "components.lock.json").write_text(
        json.dumps(
            {
                "version": 1,
                "components": [
                    {
                        "name": "example",
                        "path": "components/example",
                        "origin": "https://example.com/example.git",
                        "ref": component_target,
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (repo / ".gitignore").write_text("components/\n", encoding="utf-8")
    parent_old = commit(repo, "old product")

    support = tmp_path / "support"
    runtime = support / "runtime"
    state_runtime = support / "state" / "runtime" / "isolated"
    runtime.mkdir(parents=True)
    state_runtime.mkdir(parents=True)
    (support / "config.yaml").write_text("version: old\n", encoding="utf-8")
    (runtime / "runtime.env").write_text("VERSION=old\n", encoding="utf-8")
    (state_runtime / "mongo-data.bin").write_bytes(b"old-database")
    return repo, component, support, parent_old, component_old, component_target


def begin(
    repo: Path,
    support: Path,
    *,
    was_running: bool = True,
    env: dict[str, str] | None = None,
) -> Path:
    result = run(
        "begin",
        "--repo-root",
        str(repo),
        "--app-support-dir",
        str(support),
        "--config-file",
        str(support / "config.yaml"),
        "--runtime-dir",
        str(support / "runtime"),
        "--lock-file",
        str(repo / "components.lock.json"),
        "--was-running",
        "true" if was_running else "false",
        env=env,
    )
    assert result.returncode == 0, result.stderr
    transaction = Path(json.loads(result.stdout)["transaction_path"])
    snapshot = run("snapshot-stopped-state", "--transaction", str(transaction), env=env)
    assert snapshot.returncode == 0, snapshot.stderr
    return transaction


def register_transaction(
    repo: Path,
    support: Path,
    *,
    was_running: bool = True,
    env: dict[str, str] | None = None,
) -> Path:
    result = run(
        "begin",
        "--repo-root",
        str(repo),
        "--app-support-dir",
        str(support),
        "--config-file",
        str(support / "config.yaml"),
        "--runtime-dir",
        str(support / "runtime"),
        "--lock-file",
        str(repo / "components.lock.json"),
        "--was-running",
        "true" if was_running else "false",
        env=env,
    )
    assert result.returncode == 0, result.stderr
    return Path(json.loads(result.stdout)["transaction_path"])


def test_transaction_restores_parent_components_config_runtime_and_database_state(tmp_path: Path) -> None:
    repo, component, support, parent_old, component_old, component_target = build_fixture(tmp_path)
    transaction = begin(repo, support)

    (repo / "product.txt").write_text("new product\n", encoding="utf-8")
    parent_target = commit(repo, "new product")
    assert parent_target != parent_old
    git(component, "checkout", "--detach", component_target)
    (support / "config.yaml").write_text("version: new\n", encoding="utf-8")
    (support / "runtime" / "runtime.env").write_text("VERSION=new\n", encoding="utf-8")
    (support / "state" / "runtime" / "isolated" / "mongo-data.bin").write_bytes(b"migrated-database")

    checkpoint = run("checkpoint", "--transaction", str(transaction), "--stage", "candidate_activated")
    assert checkpoint.returncode == 0, checkpoint.stderr
    rolled_back = run("rollback", "--transaction", str(transaction))

    assert rolled_back.returncode == 0, rolled_back.stderr
    assert git(repo, "rev-parse", "HEAD") == parent_old
    assert git(component, "rev-parse", "HEAD") == component_old
    assert git(repo, "status", "--porcelain", "--untracked-files=no") == ""
    assert git(component, "status", "--porcelain", "--untracked-files=no") == ""
    assert (repo / "product.txt").read_text(encoding="utf-8") == "old product\n"
    assert (support / "config.yaml").read_text(encoding="utf-8") == "version: old\n"
    assert (support / "runtime" / "runtime.env").read_text(encoding="utf-8") == "VERSION=old\n"
    assert (support / "state" / "runtime" / "isolated" / "mongo-data.bin").read_bytes() == b"old-database"
    assert not (support / "state" / "upgrade-transaction-active.json").exists()
    ledger = json.loads((transaction / "ledger.json").read_text(encoding="utf-8"))
    assert ledger["status"] == "rolled_back"
    assert ledger["was_running"] is True
    assert ledger["rollback_verification"]["state_restored"] is True
    assert ledger["rollback_verification"]["semantic_data_migration_reversal"] == "not_proven"


def test_candidate_is_staged_separately_and_activated_only_after_validation(tmp_path: Path) -> None:
    repo, _, support, _, _, _ = build_fixture(tmp_path)
    transaction = begin(repo, support, was_running=False)

    prepared = run("prepare-candidate", "--transaction", str(transaction))
    assert prepared.returncode == 0, prepared.stderr
    candidate = json.loads(prepared.stdout)
    candidate_config = Path(candidate["config_file"])
    candidate_runtime = Path(candidate["runtime_dir"])
    assert candidate_config.read_text(encoding="utf-8") == "version: old\n"
    assert (support / "config.yaml").read_text(encoding="utf-8") == "version: old\n"

    candidate_config.write_text("version: validated-new\n", encoding="utf-8")
    candidate_runtime.mkdir(parents=True)
    (candidate_runtime / "runtime.env").write_text("VERSION=validated-new\n", encoding="utf-8")
    activated = run("activate-candidate", "--transaction", str(transaction))

    assert activated.returncode == 0, activated.stderr
    assert (support / "config.yaml").read_text(encoding="utf-8") == "version: validated-new\n"
    assert (support / "runtime" / "runtime.env").read_text(encoding="utf-8") == "VERSION=validated-new\n"
    assert run("rollback", "--transaction", str(transaction)).returncode == 0
    assert (support / "config.yaml").read_text(encoding="utf-8") == "version: old\n"


def test_successful_commit_removes_full_checkpoint_and_keeps_small_receipt(tmp_path: Path) -> None:
    repo, _, support, _, _, _ = build_fixture(tmp_path)
    transaction = begin(repo, support, was_running=False)
    prepared = run("prepare-candidate", "--transaction", str(transaction))
    assert prepared.returncode == 0, prepared.stderr
    candidate = json.loads(prepared.stdout)
    candidate_config = Path(candidate["config_file"])
    candidate_runtime = Path(candidate["runtime_dir"])
    candidate_config.write_text("version: committed\n", encoding="utf-8")
    candidate_runtime.mkdir(parents=True)
    (candidate_runtime / "runtime.env").write_text("VERSION=committed\n", encoding="utf-8")
    assert run("activate-candidate", "--transaction", str(transaction)).returncode == 0

    committed = run("commit", "--transaction", str(transaction))

    assert committed.returncode == 0, committed.stderr
    for generated in ("checkpoint", "docker-checkpoint", "candidate", "replaced-state"):
        assert not (transaction / generated).exists()
    ledger = json.loads((transaction / "ledger.json").read_text(encoding="utf-8"))
    assert ledger["status"] == "committed"
    assert ledger["cleanup"]["status"] == "complete"
    assert (transaction / "transaction-runner.py").is_file()
    assert not (support / "state" / "upgrade-transaction-active.json").exists()


def test_begin_refuses_capacity_loss_before_registering_transaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _, support, _, _, _ = build_fixture(tmp_path)
    module = load_transaction_module()

    def refuse_capacity(_path: Path, _payload_bytes: int) -> None:
        raise module.UpgradeTransactionError("synthetic insufficient capacity")

    monkeypatch.setattr(module, "ensure_checkpoint_capacity", refuse_capacity)
    args = SimpleNamespace(
        repo_root=repo,
        app_support_dir=support,
        config_file=support / "config.yaml",
        runtime_dir=support / "runtime",
        lock_file=repo / "components.lock.json",
        target_head=None,
        allow_dirty_parent=False,
        was_running="true",
    )

    with pytest.raises(module.UpgradeTransactionError, match="insufficient capacity"):
        module.command_begin(args)

    assert not (support / "upgrade-backups").exists()
    assert not (support / "state" / "upgrade-transaction-active.json").exists()


def test_rollback_refuses_unrecognized_clean_commit_without_overwriting_user_work(tmp_path: Path) -> None:
    repo, _, support, _, _, _ = build_fixture(tmp_path)
    transaction = begin(repo, support)
    (repo / "product.txt").write_text("user work after interruption\n", encoding="utf-8")
    user_head = commit(repo, "user work")
    before_config = (support / "config.yaml").read_bytes()

    result = run("rollback", "--transaction", str(transaction))

    assert result.returncode != 0
    assert git(repo, "rev-parse", "HEAD") == user_head
    assert (repo / "product.txt").read_text(encoding="utf-8") == "user work after interruption\n"
    assert (support / "config.yaml").read_bytes() == before_config
    assert (support / "state" / "upgrade-transaction-active.json").exists()


def test_begin_refuses_symlinked_runtime_state_before_creating_backup(tmp_path: Path) -> None:
    repo, _, support, _, _, _ = build_fixture(tmp_path)
    external = tmp_path / "external-state"
    external.mkdir()
    sentinel = external / "sentinel"
    sentinel.write_text("private", encoding="utf-8")
    runtime_state = support / "state" / "runtime"
    for child in runtime_state.rglob("*"):
        if child.is_file():
            child.unlink()
    for child in sorted(runtime_state.rglob("*"), reverse=True):
        if child.is_dir():
            child.rmdir()
    runtime_state.rmdir()
    runtime_state.symlink_to(external, target_is_directory=True)

    started = run(
        "begin",
        "--repo-root",
        str(repo),
        "--app-support-dir",
        str(support),
        "--config-file",
        str(support / "config.yaml"),
        "--runtime-dir",
        str(support / "runtime"),
        "--lock-file",
        str(repo / "components.lock.json"),
        "--was-running",
        "true",
    )

    assert started.returncode != 0
    assert sentinel.read_text(encoding="utf-8") == "private"
    assert not (support / "upgrade-backups").exists()
    assert not (support / "state" / "upgrade-transaction-active.json").exists()


def test_failed_docker_checkpoint_rollback_never_mutates_unknown_live_volume(tmp_path: Path) -> None:
    repo, _, support, _, _, _ = build_fixture(tmp_path)
    (support / "runtime" / "runtime.env").write_text(
        "VIVENTIUM_RUNTIME_PROFILE=compat\n",
        encoding="utf-8",
    )
    volume = tmp_path / "fake-volume"
    volume.mkdir()
    sentinel = volume / "WiredTiger"
    sentinel.write_bytes(b"original-docker-database")
    call_log = tmp_path / "docker-calls.jsonl"
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    fake_docker = fake_bin / "docker"
    fake_docker.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

args = sys.argv[1:]
volume = Path(os.environ["FAKE_DOCKER_VOLUME_DIR"])
with Path(os.environ["FAKE_DOCKER_CALL_LOG"]).open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(args) + "\\n")
if args[:1] in (["info"], ["ps"]):
    raise SystemExit(0)
if args[:2] == ["container", "inspect"]:
    raise SystemExit(1)
if args[:2] == ["image", "inspect"]:
    raise SystemExit(0)
if args[:2] == ["volume", "inspect"]:
    raise SystemExit(0 if volume.is_dir() else 1)
if args[:2] in (["volume", "rm"], ["volume", "create"]):
    raise SystemExit(90)
if args[:1] == ["run"] and args[-1] == "du -sk /source":
    print("1 /source")
    raise SystemExit(0)
if args[:1] == ["run"] and "tar -cf" in args[-1]:
    raise SystemExit(41)
raise SystemExit(91)
""",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["FAKE_DOCKER_VOLUME_DIR"] = str(volume)
    env["FAKE_DOCKER_CALL_LOG"] = str(call_log)

    transaction = register_transaction(repo, support, env=env)
    snapshot = run("snapshot-stopped-state", "--transaction", str(transaction), env=env)

    assert snapshot.returncode != 0
    ledger = json.loads((transaction / "ledger.json").read_text(encoding="utf-8"))
    assert ledger["storage_inventory"]["mongodb"]["checkpoint_status"] == "pending"
    calls_before_rollback = call_log.read_text(encoding="utf-8")
    rolled_back = run("rollback", "--transaction", str(transaction), env=env)

    assert rolled_back.returncode == 0, rolled_back.stderr
    assert call_log.read_text(encoding="utf-8") == calls_before_rollback
    assert sentinel.read_bytes() == b"original-docker-database"
    assert not (support / "state" / "upgrade-transaction-active.json").exists()


def test_stopped_checkpoint_restores_bootstrap_python_and_legacy_mongo_state(tmp_path: Path) -> None:
    repo, _, support, _, _, _ = build_fixture(tmp_path)
    bootstrap = support / "state" / "bootstrap-python"
    legacy_mongo = support / "state" / "mongo-data"
    bootstrap.mkdir()
    legacy_mongo.mkdir()
    (bootstrap / "requirements.sha256").write_text("old-requirements\n", encoding="utf-8")
    (legacy_mongo / "WiredTiger").write_bytes(b"old-legacy-database")
    transaction = begin(repo, support)

    (bootstrap / "requirements.sha256").write_text("new-requirements\n", encoding="utf-8")
    (legacy_mongo / "WiredTiger").write_bytes(b"migrated-legacy-database")

    result = run("rollback", "--transaction", str(transaction))

    assert result.returncode == 0, result.stderr
    assert (bootstrap / "requirements.sha256").read_text(encoding="utf-8") == "old-requirements\n"
    assert (legacy_mongo / "WiredTiger").read_bytes() == b"old-legacy-database"


def test_bootstrap_python_symlinks_are_restored_without_touching_their_targets(tmp_path: Path) -> None:
    repo, _, support, _, _, _ = build_fixture(tmp_path)
    external_interpreter = tmp_path / "system-python"
    external_interpreter.write_text("external interpreter sentinel\n", encoding="utf-8")
    external_interpreter.chmod(0o755)
    bootstrap_bin = support / "state" / "bootstrap-python" / "bin"
    bootstrap_bin.mkdir(parents=True)
    python_link = bootstrap_bin / "python3"
    python_link.symlink_to(external_interpreter)

    transaction = begin(repo, support)

    assert external_interpreter.read_text(encoding="utf-8") == "external interpreter sentinel\n"
    assert external_interpreter.stat().st_mode & 0o777 == 0o755
    python_link.unlink()
    python_link.write_text("candidate interpreter\n", encoding="utf-8")
    result = run("rollback", "--transaction", str(transaction))

    assert result.returncode == 0, result.stderr
    assert python_link.is_symlink()
    assert os.readlink(python_link) == str(external_interpreter)
    assert external_interpreter.read_text(encoding="utf-8") == "external interpreter sentinel\n"
    assert external_interpreter.stat().st_mode & 0o777 == 0o755


def test_component_cloned_during_failed_upgrade_is_quarantined_not_left_as_drift(tmp_path: Path) -> None:
    repo, component, support, _, _, component_target = build_fixture(tmp_path)
    component_source = tmp_path / "component-source"
    shutil.copytree(component, component_source)
    shutil.rmtree(component)
    transaction = begin(repo, support)

    subprocess.run(["git", "clone", str(component_source), str(component)], check=True, capture_output=True)
    git(component, "checkout", "--detach", component_target)
    checkpoint = run("checkpoint", "--transaction", str(transaction), "--stage", "components_refreshed")
    assert checkpoint.returncode == 0, checkpoint.stderr

    rolled_back = run("rollback", "--transaction", str(transaction))

    assert rolled_back.returncode == 0, rolled_back.stderr
    assert not component.exists()
    quarantined = list((transaction / "replaced-components").iterdir())
    assert len(quarantined) == 1
    assert (quarantined[0] / "component.txt").read_text(encoding="utf-8") == "new component\n"


def test_partial_component_clone_is_preserved_in_quarantine(tmp_path: Path) -> None:
    repo, component, support, _, _, _ = build_fixture(tmp_path)
    shutil.rmtree(component)
    transaction = begin(repo, support)
    component.mkdir(parents=True)
    (component / "partial-download").write_bytes(b"candidate bytes")

    result = run("rollback", "--transaction", str(transaction))

    assert result.returncode == 0, result.stderr
    assert not component.exists()
    quarantined = list((transaction / "replaced-components").iterdir())
    assert len(quarantined) == 1
    assert (quarantined[0] / "partial-download").read_bytes() == b"candidate bytes"


def test_compat_docker_mongodb_volume_is_checkpointed_and_restored(tmp_path: Path) -> None:
    repo, _, support, _, _, _ = build_fixture(tmp_path)
    (support / "runtime" / "runtime.env").write_text(
        "VIVENTIUM_RUNTIME_PROFILE=compat\n",
        encoding="utf-8",
    )
    volume = tmp_path / "fake-volume"
    volume.mkdir()
    (volume / "WiredTiger").write_bytes(b"old-docker-database")
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    fake_docker = fake_bin / "docker"
    fake_docker.write_text(
        """#!/usr/bin/env python3
import os
import shutil
import sys
import tarfile
from pathlib import Path

args = sys.argv[1:]
volume = Path(os.environ["FAKE_DOCKER_VOLUME_DIR"])
if args[:1] in (["info"], ["ps"]):
    raise SystemExit(0)
if args[:2] == ["image", "inspect"]:
    raise SystemExit(0)
if args[:2] == ["volume", "inspect"]:
    raise SystemExit(0 if volume.is_dir() else 1)
if args[:2] == ["volume", "create"]:
    volume.mkdir(parents=True, exist_ok=True)
    print(args[-1])
    raise SystemExit(0)
if args[:2] == ["volume", "rm"]:
    shutil.rmtree(volume)
    raise SystemExit(0)
if args[:1] != ["run"]:
    raise SystemExit(2)
if args[-1] == "du -sk /source":
    size = sum(child.stat().st_size for child in volume.rglob("*") if child.is_file())
    print(max(1, (size + 1023) // 1024), "/source")
    raise SystemExit(0)
mounts = [args[index + 1] for index, value in enumerate(args[:-1]) if value == "-v"]
checkpoint_mount = next(value for value in mounts if ":/checkpoint" in value)
checkpoint = Path(checkpoint_mount.split(":/checkpoint", 1)[0])
command = args[-1]
if "tar -cf" in command:
    archive_name = command.split("/checkpoint/", 1)[1].split(" ", 1)[0]
    with tarfile.open(checkpoint / archive_name, "w") as archive:
        for child in sorted(volume.iterdir()):
            archive.add(child, arcname=f"./{child.name}")
    raise SystemExit(0)
if "tar -C /source -xf" in command:
    archive_name = command.rsplit("/checkpoint/", 1)[1]
    for child in list(volume.iterdir()):
        shutil.rmtree(child) if child.is_dir() else child.unlink()
    with tarfile.open(checkpoint / archive_name, "r:") as archive:
        archive.extractall(volume)
    raise SystemExit(0)
raise SystemExit(2)
""",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["FAKE_DOCKER_VOLUME_DIR"] = str(volume)
    transaction = begin(repo, support, env=env)

    (volume / "WiredTiger").write_bytes(b"migrated-docker-database")
    (volume / "new-file").write_text("candidate", encoding="utf-8")
    result = run("rollback", "--transaction", str(transaction), env=env)

    assert result.returncode == 0, result.stderr
    assert (volume / "WiredTiger").read_bytes() == b"old-docker-database"
    assert not (volume / "new-file").exists()
    ledger = json.loads((transaction / "ledger.json").read_text(encoding="utf-8"))
    mongodb = ledger["storage_inventory"]["mongodb"]
    assert mongodb["backend"] == "docker_named_volume"
    assert mongodb["existed_before"] is True
    assert ledger["rollback_verification"]["docker_mongodb_restored"] is True
