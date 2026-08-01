from __future__ import annotations

import importlib.util
import hashlib
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


def _telegram_tree_digest(files: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for relative, value in sorted(files.items()):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(value).hexdigest().encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def _write_committed_telegram_migration(
    *,
    support: Path,
    legacy_root: Path,
    before: dict[str, bytes],
    after: dict[str, bytes],
) -> None:
    canonical = support / "state" / "telegram-user-configs"
    canonical.mkdir(parents=True, exist_ok=True, mode=0o700)
    canonical.chmod(0o700)
    legacy_files: dict[str, bytes] = {}
    operations = []
    for relative, value in sorted(after.items()):
        target = canonical / relative
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        target.parent.chmod(0o700)
        target.write_bytes(value)
        target.chmod(0o600)
        legacy_value = (legacy_root / relative).read_bytes()
        legacy_files[relative] = legacy_value
        if before.get(relative) == value:
            continue
        operations.append(
            {
                "path": relative,
                "legacy_sha256": hashlib.sha256(legacy_value).hexdigest(),
                "canonical_before_sha256": (
                    hashlib.sha256(before[relative]).hexdigest()
                    if relative in before
                    else None
                ),
                "canonical_after_sha256": hashlib.sha256(value).hexdigest(),
                "backup": "",
            }
        )
    state = support / "state" / "telegram-user-config-migration"
    state.mkdir(parents=True, mode=0o700)
    authority = {
        "schema_version": 2,
        "kind": "viventium-telegram-preference-authority",
        "status": "committed",
        "authority": "canonical-app-support",
        "generation": "a" * 64,
        "canonical_root": str(canonical),
        "retired_legacy_roots": [str(legacy_root)],
        "source_tree_sha256": _telegram_tree_digest(legacy_files),
        "operations": operations,
    }
    authority_path = state / "authority.json"
    authority_path.write_text(json.dumps(authority) + "\n", encoding="utf-8")
    authority_path.chmod(0o600)


def test_commit_accepts_only_proven_telegram_preference_authority_handoff(
    tmp_path: Path,
) -> None:
    repo, _, support, _, _, _ = build_fixture(tmp_path)
    legacy = repo / "viventium_v0_4" / "telegram-viventium" / "user_configs"
    legacy.mkdir(parents=True)
    legacy_value = b'{"language":"fr"}\n'
    (legacy / "global.json").write_bytes(legacy_value)
    transaction = begin(repo, support, was_running=False)

    _write_committed_telegram_migration(
        support=support,
        legacy_root=legacy,
        before={},
        after={"global.json": legacy_value},
    )

    result = run("commit", "--transaction", str(transaction))

    assert result.returncode == 0, result.stderr
    ledger = json.loads((transaction / "ledger.json").read_text(encoding="utf-8"))
    proof = ledger["static_personalization_continuity"]["telegram-user-configs"]
    assert proof["verified"] is True
    assert proof["transition"] == "verified-authority-handoff"


def test_commit_rejects_unproven_file_during_telegram_authority_handoff(
    tmp_path: Path,
) -> None:
    repo, _, support, _, _, _ = build_fixture(tmp_path)
    legacy = repo / "viventium_v0_4" / "telegram-viventium" / "user_configs"
    legacy.mkdir(parents=True)
    legacy_value = b'{"language":"fr"}\n'
    (legacy / "global.json").write_bytes(legacy_value)
    transaction = begin(repo, support, was_running=False)
    _write_committed_telegram_migration(
        support=support,
        legacy_root=legacy,
        before={},
        after={"global.json": legacy_value},
    )
    injected = support / "state" / "telegram-user-configs" / "injected.json"
    injected.write_bytes(b'{"unexpected":true}\n')
    injected.chmod(0o600)

    result = run("commit", "--transaction", str(transaction))

    assert result.returncode != 0
    assert "Telegram preference authority handoff" in result.stderr


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


def test_committed_transaction_with_surviving_pointer_finishes_idempotently(
    tmp_path: Path,
) -> None:
    repo, _, support, _, _, _ = build_fixture(tmp_path)
    transaction = begin(repo, support, was_running=False)
    prepared = run("prepare-candidate", "--transaction", str(transaction))
    assert prepared.returncode == 0, prepared.stderr
    candidate = json.loads(prepared.stdout)
    Path(candidate["config_file"]).write_text("version: committed\n", encoding="utf-8")
    candidate_runtime = Path(candidate["runtime_dir"])
    candidate_runtime.mkdir(parents=True)
    (candidate_runtime / "runtime.env").write_text(
        "VERSION=committed\n",
        encoding="utf-8",
    )
    assert run("activate-candidate", "--transaction", str(transaction)).returncode == 0
    committed = run("commit", "--transaction", str(transaction))
    assert committed.returncode == 0, committed.stderr

    pointer = support / "state" / "upgrade-transaction-active.json"
    pointer.write_text(
        json.dumps({"transaction_path": str(transaction)}) + "\n",
        encoding="utf-8",
    )
    pointer.chmod(0o600)

    retried = run("commit", "--transaction", str(transaction))

    assert retried.returncode == 0, retried.stderr
    assert json.loads(retried.stdout)["committed"] is True
    assert not pointer.exists()
    assert json.loads((transaction / "ledger.json").read_text(encoding="utf-8"))[
        "status"
    ] == "committed"


def test_rolled_back_transaction_with_surviving_pointer_finishes_idempotently(
    tmp_path: Path,
) -> None:
    repo, _, support, _, _, _ = build_fixture(tmp_path)
    transaction = begin(repo, support, was_running=False)
    rolled_back = run("rollback", "--transaction", str(transaction))
    assert rolled_back.returncode == 0, rolled_back.stderr

    pointer = support / "state" / "upgrade-transaction-active.json"
    pointer.write_text(
        json.dumps({"transaction_path": str(transaction)}) + "\n",
        encoding="utf-8",
    )
    pointer.chmod(0o600)

    retried = run("rollback", "--transaction", str(transaction))

    assert retried.returncode == 0, retried.stderr
    assert json.loads(retried.stdout)["rolled_back"] is True
    assert not pointer.exists()
    assert json.loads((transaction / "ledger.json").read_text(encoding="utf-8"))[
        "status"
    ] == "rolled_back"


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
    print(json.dumps([{
        "Config": {"Image": "mongo:8.0.17"},
        "Image": "sha256:" + "a" * 64,
        "State": {"Running": False},
        "Mounts": [{
            "Destination": "/data/db",
            "Type": "volume",
            "Name": "viventium-mongodb-data",
        }],
    }]))
    raise SystemExit(0)
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
    configured_empty_mongo = support / "data" / "empty-mongodb"
    (support / "runtime" / "runtime.env").write_text(
        f"VIVENTIUM_LOCAL_MONGO_DATA_PATH={configured_empty_mongo}\n",
        encoding="utf-8",
    )
    (bootstrap / "requirements.sha256").write_text("old-requirements\n", encoding="utf-8")
    (legacy_mongo / "WiredTiger").write_bytes(b"old-legacy-database")
    transaction = begin(repo, support)

    (bootstrap / "requirements.sha256").write_text("new-requirements\n", encoding="utf-8")
    (legacy_mongo / "WiredTiger").write_bytes(b"migrated-legacy-database")

    result = run("rollback", "--transaction", str(transaction))

    assert result.returncode == 0, result.stderr
    assert (bootstrap / "requirements.sha256").read_text(encoding="utf-8") == "old-requirements\n"
    assert (legacy_mongo / "WiredTiger").read_bytes() == b"old-legacy-database"


def test_stopped_checkpoint_restores_mongo_engine_receipt_byte_exactly(
    tmp_path: Path,
) -> None:
    repo, _, support, _, _, _ = build_fixture(tmp_path)
    transaction = register_transaction(repo, support, was_running=False)
    receipt = (
        support / "state" / "continuity" / "mongo-engine-identity.json"
    )
    receipt.parent.mkdir(parents=True)
    original = b'{"synthetic":"pre-upgrade-engine-proof"}\n'
    receipt.write_bytes(original)
    receipt.chmod(0o600)
    snapshot = run(
        "snapshot-stopped-state",
        "--transaction",
        str(transaction),
    )
    assert snapshot.returncode == 0, snapshot.stderr

    receipt.write_bytes(b'{"synthetic":"candidate-engine-proof"}\n')
    receipt.chmod(0o600)
    result = run("rollback", "--transaction", str(transaction))

    assert result.returncode == 0, result.stderr
    assert receipt.read_bytes() == original
    assert receipt.stat().st_mode & 0o777 == 0o600


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
import json
import os
import shutil
import sys
import tarfile
from pathlib import Path

args = sys.argv[1:]
volume = Path(os.environ["FAKE_DOCKER_VOLUME_DIR"])
if args[:1] in (["info"], ["ps"]):
    raise SystemExit(0)
if args[:2] == ["container", "inspect"]:
    print(json.dumps([{
        "Config": {"Image": "mongo:8.0.17"},
        "Image": "sha256:" + "a" * 64,
        "State": {"Running": False},
        "Mounts": [{
            "Destination": "/data/db",
            "Type": "volume",
            "Name": "viventium-mongodb-data",
        }],
    }]))
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


def test_docker_bind_inventory_records_runtime_engine_and_inspected_image(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_transaction_module()
    support = tmp_path / "support"
    runtime = support / "runtime"
    data_path = support / "data" / "mongodb"
    runtime.mkdir(parents=True)
    data_path.mkdir(parents=True)
    (runtime / "runtime.env").write_text(
        "\n".join(
            [
                "VIVENTIUM_RUNTIME_PROFILE=isolated",
                "VIVENTIUM_INSTALL_MODE=native",
                f"VIVENTIUM_LOCAL_MONGO_DATA_PATH={data_path}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    inspected = [
        {
            "Config": {"Image": "mongo@sha256:" + "a" * 64},
            "Image": "sha256:" + "b" * 64,
            "State": {"Running": True},
            "Mounts": [
                {
                    "Destination": "/data/db",
                    "Type": "bind",
                    "Source": str(data_path),
                }
            ],
        }
    ]

    monkeypatch.setattr(module, "docker_ready", lambda: "/fake/docker")

    def docker_command(_docker, *args, check=True):
        assert args[:2] == ("container", "inspect")
        return subprocess.CompletedProcess(
            args,
            0,
            json.dumps(inspected).encode("utf-8"),
            b"",
        )

    monkeypatch.setattr(module, "docker_command", docker_command)

    inventory, extra_surfaces = module.mongo_storage_inventory(support, runtime)

    assert inventory == {
        "backend": "app_support_bind",
        "runtime_engine": "docker",
        "profile": "isolated",
        "path": str(data_path),
        "image": "mongo@sha256:" + "a" * 64,
        "image_id": "sha256:" + "b" * 64,
        "container_name": "viventium-mongodb",
        "container_running": True,
        "observed_from": "container_inspect",
    }
    assert extra_surfaces == []


@pytest.mark.parametrize(
    "pid_relative",
    [
        Path("state/native/mongod.pid"),
        Path("state/runtime/isolated/mongodb-native.pid"),
    ],
)
def test_native_inventory_records_live_pid_process_and_dbpath_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    pid_relative: Path,
) -> None:
    module = load_transaction_module()
    support = tmp_path / "support"
    runtime = support / "runtime"
    data_path = support / "state" / "runtime" / "isolated" / "mongo-data"
    pid_path = support / pid_relative
    runtime.mkdir(parents=True)
    data_path.mkdir(parents=True)
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text("4242\n", encoding="utf-8")
    (runtime / "runtime.env").write_text(
        "VIVENTIUM_RUNTIME_PROFILE=isolated\nVIVENTIUM_INSTALL_MODE=docker\n",
        encoding="utf-8",
    )
    identity = {
        "pid": 4242,
        "process_started_at": "Fri Jul 24 10:11:12 2026",
        "executable": "/opt/viventium/mongod",
        "arguments": [
            "/opt/viventium/mongod",
            "--port",
            "27117",
            "--dbpath",
            str(data_path),
        ],
        "version": "db version v8.0.23",
        "executable_sha256": "c" * 64,
        "code_signature_verified": True,
        "code_signature_team_identifier": "4XWMY46275",
    }
    monkeypatch.setattr(module, "inspect_native_mongo_process", lambda _pid: identity)
    monkeypatch.setattr(module, "docker_ready", lambda: (_ for _ in ()).throw(
        module.UpgradeTransactionError("no docker")
    ))

    inventory, extra_surfaces = module.mongo_storage_inventory(support, runtime)

    assert inventory == {
        "backend": "app_support_bind",
        "runtime_engine": "native",
        "profile": "isolated",
        "path": str(data_path),
        "observed_from": "running_native_pid",
        "pid": 4242,
        "process_started_at": "Fri Jul 24 10:11:12 2026",
        "executable": "/opt/viventium/mongod",
        "executable_sha256": "c" * 64,
        "arguments": identity["arguments"],
        "version": "db version v8.0.23",
        "code_signature_verified": True,
        "code_signature_team_identifier": "4XWMY46275",
    }
    assert extra_surfaces == []


def test_existing_stopped_mongo_bind_without_runtime_proof_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_transaction_module()
    support = tmp_path / "support"
    runtime = support / "runtime"
    data_path = support / "state" / "runtime" / "isolated" / "mongo-data"
    runtime.mkdir(parents=True)
    data_path.mkdir(parents=True)
    (data_path / "WiredTiger").write_bytes(b"synthetic database")
    (runtime / "runtime.env").write_text(
        "VIVENTIUM_RUNTIME_PROFILE=isolated\nVIVENTIUM_INSTALL_MODE=native\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "docker_ready", lambda: (_ for _ in ()).throw(
        module.UpgradeTransactionError("no docker")
    ))

    with pytest.raises(
        module.UpgradeTransactionError,
        match="runtime engine cannot be proven",
    ):
        module.mongo_storage_inventory(support, runtime)
