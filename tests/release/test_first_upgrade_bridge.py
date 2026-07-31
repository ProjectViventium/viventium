from __future__ import annotations

import importlib.util
import hashlib
import json
import os
import signal
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "viventium" / "first_upgrade_bridge.py"
HELPER_VERIFY = REPO_ROOT / "scripts" / "viventium" / "helper_artifact_verify.py"
SHIPPED_PREDECESSOR = "d59c710f45adc37bf86abd491fce603308b1bfa9"


def load_module():
    specification = importlib.util.spec_from_file_location("first_upgrade_bridge", MODULE_PATH)
    assert specification and specification.loader
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def load_cli_test_module():
    path = Path(__file__).with_name("test_cli_upgrade.py")
    specification = importlib.util.spec_from_file_location("first_bridge_cli_fixtures", path)
    assert specification and specification.loader
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def _synthetic_process_groups(root: Path) -> set[int]:
    completed = subprocess.run(
        ["ps", "-axo", "pid=,pgid=,command="],
        check=True,
        capture_output=True,
        text=True,
    )
    groups: set[int] = set()
    root_marker = str(root)
    current_group = os.getpgrp()
    for raw_line in completed.stdout.splitlines():
        fields = raw_line.strip().split(None, 2)
        if len(fields) != 3:
            continue
        _, raw_group, command = fields
        if root_marker not in command:
            continue
        if (
            "/repo/bin/viventium" not in command
            and "/repo/viventium_v0_4/viventium-librechat-start.sh"
            not in command
        ):
            continue
        process_group = int(raw_group)
        if process_group != current_group:
            groups.add(process_group)
    return groups


@pytest.fixture
def cleanup_exact_shell_processes(tmp_path: Path):
    yield
    groups = _synthetic_process_groups(tmp_path)
    for process_group in groups:
        try:
            os.killpg(process_group, signal.SIGTERM)
        except (PermissionError, ProcessLookupError):
            pass
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline and _synthetic_process_groups(tmp_path):
        time.sleep(0.05)
    for process_group in _synthetic_process_groups(tmp_path):
        try:
            os.killpg(process_group, signal.SIGKILL)
        except (PermissionError, ProcessLookupError):
            pass


def test_first_upgrade_telegram_root_preserves_legacy_predecessor_precedence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = load_module()
    repo_root = tmp_path / "repo"
    support = tmp_path / "support"
    legacy = (
        repo_root
        / "viventium_v0_4"
        / "telegram-viventium"
        / "TelegramVivBot"
        / "user_configs"
    )
    canonical = support / "state" / "telegram-user-configs"
    legacy.mkdir(parents=True)
    canonical.mkdir(parents=True)
    (legacy / "global.json").write_text('{"source":"legacy"}\n', encoding="utf-8")
    (canonical / "global.json").write_text(
        '{"source":"stale-canonical"}\n',
        encoding="utf-8",
    )
    monkeypatch.delenv("VIVENTIUM_TELEGRAM_USER_CONFIGS_DIR", raising=False)
    monkeypatch.delenv("VIVENTIUM_PRIVATE_CURATED_DIR", raising=False)
    monkeypatch.delenv("VIVENTIUM_PRIVATE_MIRROR_DIR", raising=False)
    context = module.UpgradeContext(
        repo_root=repo_root,
        app_support_dir=support,
        transaction=support / "upgrade-backups" / "upgrade-synthetic",
        ledger={},
        predecessor="a" * 40,
        successor="b" * 40,
        was_running=False,
    )

    assert module._first_upgrade_telegram_preference_root(context) == legacy


def test_first_upgrade_preserves_durably_discovered_custom_telegram_root(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = load_module()
    repo_root = tmp_path / "repo"
    support = tmp_path / "support"
    runtime = support / "runtime"
    custom = tmp_path / "operator-preferences"
    owner = (
        support
        / "state"
        / "runtime"
        / "isolated"
        / "telegram-poller"
        / "owner-synthetic.json"
    )
    for tool_name in (
        "telegram_user_config_migration.py",
        "telegram_runtime_component.py",
    ):
        tool = repo_root / "scripts" / "viventium" / tool_name
        tool.parent.mkdir(parents=True, exist_ok=True)
        tool.write_text("# synthetic\n", encoding="utf-8")
    custom.mkdir()
    owner.parent.mkdir(parents=True)
    owner.write_text(
        json.dumps({"user_configs_root": str(custom)}) + "\n",
        encoding="utf-8",
    )
    owner.chmod(0o600)
    launch_script = (
        support
        / "state"
        / "runtime"
        / "isolated"
        / "telegram_bot_launch.sh"
    )
    launch_script.write_text(
        "export CONFIG_DIR="
        + str(support / "state" / "telegram-user-configs")
        + "\n",
        encoding="utf-8",
    )
    launch_script.chmod(0o700)
    authority = (
        support
        / "state"
        / "telegram-user-config-migration"
        / "authority.json"
    )
    authority.parent.mkdir(parents=True)
    authority.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "kind": "viventium-telegram-preference-authority",
                "status": "committed",
                "authority": "canonical-app-support",
                "generation": "c" * 64,
                "canonical_root": str(
                    support / "state" / "telegram-user-configs"
                ),
                "retired_legacy_roots": [],
                "source_tree_sha256": "d" * 64,
                "operations": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    authority.chmod(0o600)
    context = module.UpgradeContext(
        repo_root=repo_root,
        app_support_dir=support,
        transaction=support / "upgrade-backups" / "upgrade-synthetic",
        ledger={},
        predecessor="a" * 40,
        successor="b" * 40,
        was_running=True,
    )
    commands: list[list[str]] = []

    def record_checked(command, *, environment, timeout):
        commands.append(command)

    def record_capture(command, *, environment, timeout):
        commands.append(command)
        return json.dumps(
            {
                "schema_version": 2,
                "status": "explicit-override-preserved",
                "changed": False,
            }
        )

    monkeypatch.setattr(module, "_run_checked", record_checked)
    monkeypatch.setattr(module, "_run_capture", record_capture)
    monkeypatch.setenv(
        "VIVENTIUM_HELPER_APP_BUNDLE",
        str(tmp_path / "no-helper.app"),
    )
    monkeypatch.delenv("VIVENTIUM_TELEGRAM_USER_CONFIGS_DIR", raising=False)

    result = module._arm_first_upgrade_telegram_continuity(
        context=context,
        runtime_dir=runtime,
    )

    assert result["activePreferenceRoot"] == str(custom)
    assert result["preferenceMigration"] == {
        "status": "deferred-until-outer-commit"
    }
    assert not any(
        any(
            item.endswith("telegram_user_config_migration.py")
            for item in command
        )
        for command in commands
    )
    publication = next(
        command for command in commands if "publish-recovery" in command
    )
    assert publication[publication.index("--user-configs-root") + 1] == str(
        custom
    )


@pytest.mark.parametrize(
    ("migration_status", "expected_root"),
    (
        ("explicit-override-preserved", "active"),
        ("migrated", "canonical"),
    ),
)
def test_first_upgrade_telegram_migration_waits_for_committed_finalization(
    tmp_path: Path,
    monkeypatch,
    migration_status: str,
    expected_root: str,
) -> None:
    module = load_module()
    repo = tmp_path / "repo"
    support = tmp_path / "support"
    active = tmp_path / "active-preferences"
    active.mkdir()
    migration_tool = (
        repo / "scripts" / "viventium" / "telegram_user_config_migration.py"
    )
    migration_tool.parent.mkdir(parents=True)
    migration_tool.write_text("# synthetic\n", encoding="utf-8")
    payload = {
        "telegramContinuity": {
            "status": "rollback-armed",
            "activePreferenceRoot": str(active),
            "preferenceMigration": {
                "status": "deferred-until-outer-commit"
            },
        }
    }
    commands: list[list[str]] = []

    def record_capture(command, *, environment, timeout):
        commands.append(command)
        return json.dumps(
            {
                "schema_version": 2,
                "status": migration_status,
                "changed": migration_status == "migrated",
                "generation": "a" * 64,
            }
        )

    monkeypatch.setattr(module, "_run_capture", record_capture)
    environment = {"SAFE_MARKER": "preserved"}

    effective = module._finalize_first_upgrade_telegram_preferences(
        payload=payload,
        repo_root=repo,
        app_support_dir=support,
        environment=environment,
    )

    canonical = support / "state" / "telegram-user-configs"
    expected = active if expected_root == "active" else canonical
    assert effective == expected
    assert environment["VIVENTIUM_TELEGRAM_USER_CONFIGS_DIR"] == str(expected)
    assert payload["telegramContinuity"]["status"] == "migration-finalized"
    assert payload["telegramContinuity"]["effectivePreferenceRoot"] == str(
        expected
    )
    migration = commands[0]
    assert migration[migration.index("--active-config-root") + 1] == str(active)
    assert "--writer-stopped" in migration

    # A crash after the durable receipt update must resume without a second
    # preference writer handoff.
    second = module._finalize_first_upgrade_telegram_preferences(
        payload=payload,
        repo_root=repo,
        app_support_dir=support,
        environment=environment,
    )
    assert second == expected
    assert len(commands) == 1


def test_terminal_successor_checkpoint_cleanup_removes_only_known_private_files(
    tmp_path: Path,
) -> None:
    module = load_module()
    transaction = tmp_path / "transaction"
    root = transaction / "successor-bridge"
    root.mkdir(parents=True)
    for relative in (
        module.LIBRECHAT_ENV_CHECKPOINT,
        module.LIBRECHAT_ENV_CHECKPOINT_MANIFEST,
        module.HELPER_CONFIG_CHECKPOINT,
        module.HELPER_CONFIG_CHECKPOINT_MANIFEST,
    ):
        path = transaction / relative
        path.write_text("synthetic-private-checkpoint\n", encoding="utf-8")
        path.chmod(0o600)

    assert module._cleanup_successor_private_checkpoints(transaction) is True
    assert not root.exists()

    root.mkdir()
    unexpected = root / "unexpected"
    unexpected.write_text("keep\n", encoding="utf-8")
    assert module._cleanup_successor_private_checkpoints(transaction) is False
    assert unexpected.read_text(encoding="utf-8") == "keep\n"


def test_finalized_receipt_retries_private_checkpoint_cleanup(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = load_module()
    support = tmp_path / "support"
    repo_root = tmp_path / "repo"
    transaction = support / "upgrade-backups" / "upgrade-synthetic"
    root = transaction / "successor-bridge"
    root.mkdir(parents=True)
    monkeypatch.setattr(
        module.upgrade_transaction,
        "load_ledger",
        lambda _transaction: {
            "status": "committed",
            "repo_root": str(repo_root),
            "app_support_dir": str(support),
        },
    )
    unexpected = root / "unexpected"
    unexpected.write_text("keep\n", encoding="utf-8")
    state_path = support / module.BRIDGE_STATE
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        json.dumps(
            {
                "schemaVersion": module.BRIDGE_SCHEMA_VERSION,
                "status": "finalized_private_cleanup_pending",
                "finalizedAfterOuterCommit": True,
                "privateCheckpointCleanupComplete": False,
                "transaction": str(transaction),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    state_path.chmod(0o600)

    pending = module.finalize_after_outer_commit(
        repo_root=repo_root,
        app_support_dir=support,
        config_file=support / "config.yaml",
        runtime_dir=support / "runtime",
        lock_file=tmp_path / "repo" / "components.lock.json",
    )
    assert pending["status"] == "finalized_private_cleanup_pending"
    assert pending["privateCheckpointCleanupComplete"] is False
    assert unexpected.read_text(encoding="utf-8") == "keep\n"

    unexpected.unlink()
    checkpoint = transaction / module.LIBRECHAT_ENV_CHECKPOINT
    checkpoint.write_text("private-checkpoint\n", encoding="utf-8")
    checkpoint.chmod(0o400)
    finalized = module.finalize_after_outer_commit(
        repo_root=repo_root,
        app_support_dir=support,
        config_file=support / "config.yaml",
        runtime_dir=support / "runtime",
        lock_file=tmp_path / "repo" / "components.lock.json",
    )
    assert finalized["status"] == "finalized"
    assert finalized["privateCheckpointCleanupComplete"] is True
    assert not root.exists()


def test_finalized_receipt_refuses_private_cleanup_outside_app_support(
    tmp_path: Path,
) -> None:
    module = load_module()
    support = tmp_path / "support"
    repo_root = tmp_path / "repo"
    transaction = tmp_path / "unrelated-owner-data"
    root = transaction / "successor-bridge"
    root.mkdir(parents=True)
    checkpoint = transaction / module.LIBRECHAT_ENV_CHECKPOINT
    checkpoint.write_text("must-remain\n", encoding="utf-8")
    checkpoint.chmod(0o600)
    state_path = support / module.BRIDGE_STATE
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        json.dumps(
            {
                "schemaVersion": module.BRIDGE_SCHEMA_VERSION,
                "status": "finalized_private_cleanup_pending",
                "finalizedAfterOuterCommit": True,
                "privateCheckpointCleanupComplete": False,
                "transaction": str(transaction),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    state_path.chmod(0o600)

    with pytest.raises(
        module.FirstUpgradeBridgeError,
        match="outside App Support",
    ):
        module.finalize_after_outer_commit(
            repo_root=repo_root,
            app_support_dir=support,
            config_file=support / "config.yaml",
            runtime_dir=support / "runtime",
            lock_file=repo_root / "components.lock.json",
        )

    assert checkpoint.read_text(encoding="utf-8") == "must-remain\n"


def test_internal_capture_passes_each_required_cli_option_once(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_module()
    repo_root = tmp_path / "repo"
    app_support = tmp_path / "support"
    transaction = app_support / "upgrade-backups" / "upgrade-synthetic"
    context = module.UpgradeContext(
        repo_root=repo_root,
        app_support_dir=app_support,
        transaction=transaction,
        ledger={},
        predecessor="a" * 40,
        successor="b" * 40,
        was_running=True,
    )
    commands: list[list[str]] = []

    def record(command, *, environment, timeout):
        commands.append(command)

    monkeypatch.setattr(module, "_run_checked", record)
    module._capture(
        context,
        config_file=transaction / "checkpoint" / "config.yaml",
        runtime_dir=transaction / "checkpoint" / "runtime",
        label="synthetic",
        output=transaction / "capture.json",
    )

    assert len(commands) == 1
    command = commands[0]
    for option in (
        "--repo-root",
        "--app-support-dir",
        "--config-file",
        "--runtime-dir",
        "--label",
        "--output",
    ):
        assert command.count(option) == 1


def test_first_hop_stages_storage_baseline_runtime_and_strict_compare(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_module()
    repo_root = tmp_path / "repo"
    app_support = tmp_path / "support"
    transaction = app_support / "upgrade-backups" / "upgrade-synthetic"
    checkpoint = transaction / "checkpoint"
    checkpoint_config = checkpoint / "config.yaml"
    checkpoint_runtime = checkpoint / "runtime"
    for path in (repo_root, app_support, checkpoint_runtime):
        path.mkdir(parents=True, exist_ok=True)
    checkpoint_config.write_text("version: 1\n", encoding="utf-8")
    context = module.UpgradeContext(
        repo_root=repo_root,
        app_support_dir=app_support,
        transaction=transaction,
        ledger={},
        predecessor="a" * 40,
        successor="b" * 40,
        was_running=False,
    )
    events: list[str] = []

    monkeypatch.setattr(module, "load_active_context", lambda **_: context)
    monkeypatch.setattr(
        module,
        "_arm_first_upgrade_telegram_continuity",
        lambda **_: {"status": "armed"},
    )
    monkeypatch.setattr(
        module,
        "_surface_backup",
        lambda _context, label: checkpoint_config if label == "config" else checkpoint_runtime,
    )

    def run_checked(command, *, environment, timeout):
        if any(item.endswith("helper_artifact_verify.py") for item in command):
            events.append("helper-artifact-verified")
            return
        action = command[-1]
        if action in {
            "start-storage",
            "start-quiesced-and-wait",
            "restore-stopped",
        }:
            events.append(action)
            return
        assert "compare" in command
        output = Path(command[command.index("--output") + 1])
        output.write_text(json.dumps({"status": "ok"}) + "\n", encoding="utf-8")
        events.append("strict-compare")

    def capture(_context, *, config_file, runtime_dir, label, output):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps({"status": "ok", "label": label}) + "\n",
            encoding="utf-8",
        )
        events.append(label)

    monkeypatch.setattr(module, "_run_checked", run_checked)
    monkeypatch.setattr(module, "_capture", capture)
    monkeypatch.setattr(
        module,
        "_start_checkpoint_mongo",
        lambda _context, _runtime: (
            events.append("start-checkpoint-mongo")
            or module.MongoBridgeSession(
                backend="app_support_bind",
                identity={"pid": "4242"},
                environment={},
            )
        ),
    )
    monkeypatch.setattr(
        module,
        "_stop_checkpoint_mongo",
        lambda _context, _session: events.append("stop-checkpoint-mongo"),
    )

    result = module.validate_first_hop(
        repo_root=repo_root,
        app_support_dir=app_support,
        config_file=app_support / "config.yaml",
        runtime_dir=app_support / "runtime",
        lock_file=repo_root / "components.lock.json",
    )

    assert events == [
        "helper-artifact-verified",
        "start-checkpoint-mongo",
        "successor-bridge-stopped-baseline",
        "stop-checkpoint-mongo",
        "start-quiesced-and-wait",
        "successor-bridge-validated-live",
        "strict-compare",
    ]
    assert result["status"] == "validated"
    assert result["wasRunning"] is False
    assert result["telegramContinuity"] == {"status": "armed"}
    assert (app_support / module.BRIDGE_STATE).is_file()


def test_same_source_current_upgrade_still_requires_a_quiesced_session(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_module()
    repo_root = tmp_path / "repo"
    app_support = tmp_path / "support"
    transaction = app_support / "upgrade-backups" / "upgrade-synthetic"
    checkpoint = transaction / "checkpoint"
    checkpoint_config = checkpoint / "config.yaml"
    checkpoint_runtime = checkpoint / "runtime"
    for path in (repo_root, app_support, checkpoint_runtime):
        path.mkdir(parents=True, exist_ok=True)
    checkpoint_config.write_text("version: 1\n", encoding="utf-8")
    same_head = "a" * 40
    context = module.UpgradeContext(
        repo_root=repo_root,
        app_support_dir=app_support,
        transaction=transaction,
        ledger={},
        predecessor=same_head,
        successor=same_head,
        was_running=True,
    )
    load_calls: list[dict[str, object]] = []
    events: list[str] = []

    def load_context(**kwargs):
        load_calls.append(kwargs)
        return context

    monkeypatch.setattr(module, "load_active_context", load_context)
    monkeypatch.setattr(
        module,
        "_surface_backup",
        lambda _context, label: (
            checkpoint_config if label == "config" else checkpoint_runtime
        ),
    )
    monkeypatch.setattr(
        module,
        "_start_checkpoint_mongo",
        lambda _context, _runtime: module.MongoBridgeSession(
            backend="app_support_bind",
            identity={"pid": "4242"},
            environment={},
        ),
    )
    monkeypatch.setattr(module, "_stop_checkpoint_mongo", lambda *_: None)

    def run_checked(command, *, environment, timeout):
        if "compare" in command:
            output = Path(command[command.index("--output") + 1])
            output.write_text('{"status":"ok"}\n', encoding="utf-8")
            events.append("strict-compare")
        elif command[-1] == "start-quiesced-and-wait":
            events.append("quiesced-start")

    def capture(_context, *, config_file, runtime_dir, label, output):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('{"status":"ok"}\n', encoding="utf-8")
        events.append(label)

    monkeypatch.setattr(module, "_run_checked", run_checked)
    monkeypatch.setattr(module, "_capture", capture)

    result = module.validate_current_upgrade_session(
        repo_root=repo_root,
        app_support_dir=app_support,
        config_file=app_support / "config.yaml",
        runtime_dir=app_support / "runtime",
        lock_file=repo_root / "components.lock.json",
    )

    assert load_calls == [
        {
            "repo_root": repo_root,
            "app_support_dir": app_support,
            "required_stage": "candidate_activated",
            "allow_same_source": True,
        }
    ]
    assert events == [
        "successor-bridge-stopped-baseline",
        "quiesced-start",
        "successor-bridge-validated-live",
        "strict-compare",
    ]
    assert result["receiptKind"] == "current-upgrade-session"
    assert result["predecessor"] == result["successor"] == same_head
    assert (app_support / module.QUIESCED_SESSION_STATE).is_file()
    assert not (app_support / module.BRIDGE_STATE).exists()


def test_post_commit_full_runtime_failure_is_resumable_without_state_drift(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_module()
    repo_root = tmp_path / "repo"
    app_support = tmp_path / "support"
    transaction = app_support / "upgrade-backups" / "upgrade-synthetic"
    state_path = app_support / module.QUIESCED_SESSION_STATE
    protected_state = app_support / "state" / "protected-user-state.bin"
    for path in (repo_root, transaction, state_path.parent):
        path.mkdir(parents=True, exist_ok=True)
    (repo_root / "viventium_v0_4" / "LibreChat").mkdir(parents=True)
    context = module.UpgradeContext(
        repo_root=repo_root,
        app_support_dir=app_support,
        transaction=transaction,
        ledger={},
        predecessor="a" * 40,
        successor="a" * 40,
        was_running=True,
    )
    checkpoint = module._checkpoint_librechat_env(context)
    helper_checkpoint = module._checkpoint_helper_config(context)
    protected_state.write_bytes(b"unchanged-personalization")
    payload = {
        "schemaVersion": module.BRIDGE_SCHEMA_VERSION,
        "receiptKind": "current-upgrade-session",
        "status": "validated",
        "transaction": str(transaction),
        "predecessor": "a" * 40,
        "successor": "a" * 40,
        "wasRunning": True,
        "uploadsDeferredUntilOuterCommit": False,
        "librechatEnvCheckpointSha256": module.sha256_file(
            checkpoint["manifestPath"]
        ),
        "helperConfigCheckpointSha256": module.sha256_file(
            helper_checkpoint["manifestPath"]
        ),
        "disabledWriters": module.SUCCESSOR_VALIDATION_DISABLED_WRITERS,
        "finalizedAfterOuterCommit": False,
    }
    state_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    monkeypatch.setattr(
        module.upgrade_transaction,
        "load_ledger",
        lambda _transaction: {
            "status": "committed",
            "repo_root": str(repo_root),
            "app_support_dir": str(app_support),
        },
    )
    attempts = {"full": 0}

    def run_checked(command, *, environment, timeout):
        if command[-1] == "start-full-and-wait":
            attempts["full"] += 1
            if attempts["full"] == 1:
                raise module.FirstUpgradeBridgeError(
                    "synthetic post-commit sidecar failure"
                )
            receipt_path = app_support / module.POSTCOMMIT_API_FINALIZATION_STATE
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            receipt_path.write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "runId": environment[
                            "VIVENTIUM_POSTCOMMIT_FINALIZATION_ID"
                        ],
                        "sourceId": environment[
                            "VIVENTIUM_POSTCOMMIT_SOURCE_ID"
                        ],
                        "status": "ready",
                        "stage": "ready",
                        "attempt": attempts["full"],
                        "completed": list(
                            module.POSTCOMMIT_API_REQUIRED_STAGES
                        ),
                        "degraded": [
                            {
                                "stage": "derived-search-index",
                                "code": "best-effort-derived-state",
                            }
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            receipt_path.chmod(0o600)

    monkeypatch.setattr(module, "_run_checked", run_checked)

    with pytest.raises(
        module.FirstUpgradeBridgeError,
        match="synthetic post-commit sidecar failure",
    ):
        module.finalize_after_outer_commit(
            repo_root=repo_root,
            app_support_dir=app_support,
            config_file=app_support / "config.yaml",
            runtime_dir=app_support / "runtime",
            lock_file=repo_root / "components.lock.json",
            state_relative=module.QUIESCED_SESSION_STATE,
        )

    failed_receipt = json.loads(state_path.read_text(encoding="utf-8"))
    assert failed_receipt["status"] == "validated"
    assert failed_receipt["finalizedAfterOuterCommit"] is False
    assert protected_state.read_bytes() == b"unchanged-personalization"

    recovered = module.finalize_after_outer_commit(
        repo_root=repo_root,
        app_support_dir=app_support,
        config_file=app_support / "config.yaml",
        runtime_dir=app_support / "runtime",
        lock_file=repo_root / "components.lock.json",
        state_relative=module.QUIESCED_SESSION_STATE,
    )
    assert attempts["full"] == 2
    assert recovered["status"] == "finalized"
    assert recovered["finalizedAfterOuterCommit"] is True
    assert recovered["postCommitApiFinalization"]["status"] == "ready"
    assert recovered["postCommitApiFinalization"]["attempt"] == 2
    assert protected_state.read_bytes() == b"unchanged-personalization"


def test_postcommit_api_finalization_rejects_failed_wrong_or_incomplete_receipts(
    tmp_path: Path,
) -> None:
    module = load_module()
    app_support = tmp_path / "support"
    receipt = app_support / module.POSTCOMMIT_API_FINALIZATION_STATE
    receipt.parent.mkdir(parents=True)
    run_id = "a" * 64
    source_id = "b" * 40

    def write(**overrides):
        payload = {
            "schemaVersion": 1,
            "runId": run_id,
            "sourceId": source_id,
            "status": "ready",
            "stage": "ready",
            "attempt": 1,
            "completed": list(module.POSTCOMMIT_API_REQUIRED_STAGES),
            "degraded": [
                {
                    "stage": "derived-search-index",
                    "code": "best-effort-derived-state",
                }
            ],
            **overrides,
        }
        receipt.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        receipt.chmod(0o600)

    write(status="failed", stage="failed")
    with pytest.raises(module.FirstUpgradeBridgeError, match="incomplete"):
        module._verify_postcommit_api_finalization(
            app_support_dir=app_support,
            run_id=run_id,
            source_id=source_id,
        )

    write(runId="c" * 64)
    with pytest.raises(module.FirstUpgradeBridgeError, match="another run"):
        module._verify_postcommit_api_finalization(
            app_support_dir=app_support,
            run_id=run_id,
            source_id=source_id,
        )

    write(completed=["database-connected"])
    with pytest.raises(module.FirstUpgradeBridgeError, match="incomplete"):
        module._verify_postcommit_api_finalization(
            app_support_dir=app_support,
            run_id=run_id,
            source_id=source_id,
        )

    write()
    verified = module._verify_postcommit_api_finalization(
        app_support_dir=app_support,
        run_id=run_id,
        source_id=source_id,
    )
    assert verified["status"] == "ready"
    assert verified["completedStages"] == list(
        module.POSTCOMMIT_API_REQUIRED_STAGES
    )


def test_full_runtime_bridge_exports_and_waits_for_exact_postcommit_receipt() -> None:
    bridge = MODULE_PATH.read_text(encoding="utf-8")
    cli = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")

    assert 'environment["VIVENTIUM_POSTCOMMIT_FINALIZATION_ID"]' in bridge
    assert 'environment["VIVENTIUM_POSTCOMMIT_SOURCE_ID"]' in bridge
    assert "_verify_postcommit_api_finalization(" in bridge
    assert "postcommit_api_finalization_ready()" in cli
    upgrade_wait = cli.split("wait_for_upgrade_runtime_health() {", 1)[1].split(
        "\n}", 1
    )[0]
    restart = cli.split("restart_stack_after_upgrade() {", 1)[1].split(
        "\n}", 1
    )[0]
    detached = cli.split("launch_stack_detached() {", 1)[1].split("\n}", 1)[0]
    launcher = (
        REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"
    ).read_text(encoding="utf-8")
    assert "postcommit_api_finalization_ready" in upgrade_wait
    assert "postcommit_api_finalization_ready" in restart
    assert "postcommit_api_finalization_ready" in detached
    assert "finalize_pending_postcommit_after_first_start()" in launcher
    assert "start_deferred_postcommit_finalizer" in launcher
    assert "finalize-pending-after-first-start" in launcher
    postcommit_wait = launcher.split(
        "wait_for_postcommit_api_readiness() {", 1
    )[1].split("\n}", 1)[0]
    assert "librechat_api_http_healthy" in postcommit_wait
    assert "wait_for_http" not in postcommit_wait
    skipped_health = launcher.split(
        'elif [[ "$SKIP_HEALTH_CHECKS" != "true" ]]', 1
    )[1].split("prewarm_remote_call_access", 1)[0]
    assert "start_deferred_postcommit_finalizer" in skipped_health
    deferred_finalizer = launcher.split(
        "finalize_pending_postcommit_after_first_start() {", 1
    )[1].split("\n}", 1)[0]
    assert "terminal continuity verification failed" in deferred_finalizer
    assert "stop_owned_runtime_after_postcommit_failure" in deferred_finalizer
    deferred_monitor = launcher.split(
        "start_deferred_postcommit_finalizer() {", 1
    )[1].split("\n}", 1)[0]
    assert "Post-upgrade API finalization did not become ready" in deferred_monitor
    assert "stop_owned_runtime_after_postcommit_failure" in deferred_monitor


def test_deferred_terminal_failure_uses_public_stop_without_forged_upgrade_lock(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_module()
    calls = []

    def record(command, *, environment, timeout):
        calls.append((command, environment, timeout))

    monkeypatch.setattr(module, "_run_checked", record)
    module._stop_runtime_for_continuity_recovery(
        context_repo=tmp_path / "repo",
        app_support_dir=tmp_path / "support",
        config_file=tmp_path / "support" / "config.yaml",
        runtime_dir=tmp_path / "support" / "runtime",
        lock_file=tmp_path / "repo" / "components.lock.json",
        environment={
            "VIVENTIUM_CLI_LOCK_HELD": "1",
            "VIVENTIUM_CLI_LOCK_DIR": "/synthetic/outer-lock",
            "VIVENTIUM_CLI_LOCK_OWNER_PID": "123",
            "VIVENTIUM_CLI_LOCK_INHERITED_ONCE": "1",
            "SAFE_MARKER": "preserved",
        },
        deferred_first_start=True,
    )

    assert len(calls) == 1
    command, environment, timeout = calls[0]
    assert command[-1] == "stop"
    assert timeout == 300
    assert environment["SAFE_MARKER"] == "preserved"
    for name in (
        "VIVENTIUM_CLI_LOCK_HELD",
        "VIVENTIUM_CLI_LOCK_DIR",
        "VIVENTIUM_CLI_LOCK_OWNER_PID",
        "VIVENTIUM_CLI_LOCK_INHERITED_ONCE",
    ):
        assert name not in environment


def test_clustered_api_records_every_parent_verified_finalization_stage() -> None:
    module = load_module()
    clustered = (
        REPO_ROOT
        / "viventium_v0_4"
        / "LibreChat"
        / "api"
        / "server"
        / "experimental.js"
    ).read_text(encoding="utf-8")

    for stage in module.POSTCOMMIT_API_REQUIRED_STAGES:
        assert f"recordCompleted('{stage}')" in clustered
    assert "GenerationJobManager.configure(streamServices)" in clustered
    assert "GenerationJobManager.initialize()" in clustered
    assert clustered.index("recordCompleted('generation-runtime-ready')") < (
        clustered.index("upgradeFinalization.markReady()")
    )
    assert "app.get(['/health', '/api/health']" in clustered


def test_shipped_helper_verifier_rejects_digest_mismatch_without_mutation(
    tmp_path: Path,
) -> None:
    package = tmp_path / "ViventiumHelper"
    shutil.copytree(REPO_ROOT / "apps" / "macos" / "ViventiumHelper", package)
    binary = package / "prebuilt" / "ViventiumHelper-universal"
    before = {
        path.relative_to(package).as_posix(): path.read_bytes()
        for path in package.rglob("*")
        if path.is_file()
    }

    healthy = subprocess.run(
        [
            sys.executable,
            str(HELPER_VERIFY),
            "--package-dir",
            str(package),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert healthy.returncode == 0, healthy.stderr

    binary.write_bytes(binary.read_bytes() + b"synthetic-corruption")
    corrupted_before = binary.read_bytes()
    rejected = subprocess.run(
        [
            sys.executable,
            str(HELPER_VERIFY),
            "--package-dir",
            str(package),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert rejected.returncode != 0
    assert "digest" in rejected.stderr.lower()
    assert binary.read_bytes() == corrupted_before
    for relative, content in before.items():
        if relative == "prebuilt/ViventiumHelper-universal":
            continue
        assert (package / relative).read_bytes() == content


def test_first_upgrade_storage_has_one_successor_owned_authority() -> None:
    cli = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    internal_runtime = cli.split("  _first-upgrade-runtime)", 1)[1].split(
        "  start)", 1
    )[0]
    bridge = MODULE_PATH.read_text(encoding="utf-8")

    assert "start-storage)" not in internal_runtime
    assert "_start_checkpoint_mongo(context, checkpoint_runtime)" in bridge
    assert "_stop_checkpoint_mongo(context, mongo_session)" in bridge


def test_successor_validation_is_quiesced_until_outer_commit_and_shared_by_both_controllers() -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    bridge = cli_source.split("  _first-upgrade-runtime)", 1)[1].split(
        "  start)", 1
    )[0]
    upgrade = cli_source.rsplit("  upgrade|update)", 1)[1].split(
        "  configure|wizard)", 1
    )[0]
    quiesced = cli_source.split(
        "restart_quiesced_runtime_after_upgrade() {", 1
    )[1].split("\n}", 1)[0]

    assert "start-quiesced-and-wait)" in bridge
    assert "restart_quiesced_runtime_after_upgrade" in bridge
    assert "wait_for_quiesced_runtime_health" in quiesced
    assert "restart_stack_after_upgrade" not in quiesced

    activated = upgrade.index('upgrade_transaction_checkpoint "candidate_activated"')
    post_capture = upgrade.index(
        'POST_UPGRADE_CONTINUITY_AUDIT="$(capture_continuity_audit'
    )
    ordinary_restart = upgrade.find(
        "if ! restart_stack_after_upgrade; then", activated, post_capture
    )
    assert ordinary_restart == -1
    explicit_quiesced_start = upgrade.index(
        "if ! validate_quiesced_upgrade_session_before_post_capture; then"
    )
    strict_compare = upgrade.index("compare_upgrade_continuity_audits")
    commit = upgrade.index("upgrade_transaction_commit")
    bridge_finalize = upgrade.index(
        "finalize_quiesced_upgrade_session_after_commit"
    )
    uploads_finalize = upgrade.index("finalize_deferred_uploads_after_upgrade_commit")
    schedule_refresh = upgrade.index("if ! sync_memory_hardening_schedule; then")
    helper_refresh = upgrade.index("if ! maybe_install_macos_helper --no-launch; then")
    assert (
        activated
        < explicit_quiesced_start
        < post_capture
        < strict_compare
        < commit
        < bridge_finalize
        < uploads_finalize
        < schedule_refresh
        < helper_refresh
    )
    assert "finalize_quiesced_upgrade_session_after_commit" in upgrade
    assert "validate-session" in cli_source
    assert "finalize-session-after-commit" in cli_source


def test_quiesced_launcher_contract_disables_every_inventory_writer_fail_closed() -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    launcher = (
        REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"
    ).read_text(encoding="utf-8")
    api_index = (
        REPO_ROOT / "viventium_v0_4" / "LibreChat" / "api" / "server" / "index.js"
    ).read_text(encoding="utf-8")
    api_cluster = (
        REPO_ROOT
        / "viventium_v0_4"
        / "LibreChat"
        / "api"
        / "server"
        / "experimental.js"
    ).read_text(encoding="utf-8")
    api_finalization = (
        REPO_ROOT
        / "viventium_v0_4"
        / "LibreChat"
        / "api"
        / "server"
        / "services"
        / "viventium"
        / "upgradeFinalization.js"
    ).read_text(encoding="utf-8")

    writer_ids = {
        "agent-seeding",
        "canonical-uploads",
        "channel-workers",
        "glasshive-callbacks",
        "librechat-mcp-oauth",
        "prompt-workbench",
        "rag-recall",
        "remote-mapping",
        "scheduler",
        "stale-cortex-recovery",
        "telegram",
        "telegram-codex",
        "voice-workers",
    }
    for writer_id in writer_ids:
        assert writer_id in cli_source
        assert writer_id in launcher

    assert 'VIVENTIUM_SUCCESSOR_VALIDATION_MODE:-' in launcher
    assert "VIVENTIUM_SUCCESSOR_VALIDATION_DISABLED_WRITERS" in launcher
    assert "Successor validation writer inventory mismatch" in launcher
    for disabled_flag in (
        "START_GOOGLE_MCP=false",
        "START_MS365_MCP=false",
        "START_SCHEDULING_MCP=false",
        "START_GLASSHIVE=false",
        "START_RAG_API=false",
        "START_SKYVERN=false",
        "START_TELEGRAM=false",
        "START_TELEGRAM_CODEX=false",
        "START_CODE_INTERPRETER=false",
        "START_SEARXNG=false",
        "START_FIRECRAWL=false",
        "START_PROMPT_WORKBENCH=false",
        "START_V1_AGENT=false",
    ):
        assert disabled_flag in launcher
    assert "VIVENTIUM_QUIESCED_API_STARTUP=1" in launcher
    assert "validation_runtime_is_quiesced" in launcher

    for api_source in (api_index, api_cluster):
        assert "upgradeFinalization.isQuiesced()" in api_source
        assert "initializeMCPs" in api_source
        assert "initializeOAuthReconnectManager" in api_source
        assert "restoreChannelWorkers" in api_source
        assert "recoverStaleCortexMessages" in api_source
    assert "VIVENTIUM_QUIESCED_API_STARTUP" in api_finalization


def test_native_stack_mongo_only_bridge_is_internal_and_identity_bound() -> None:
    source = (
        REPO_ROOT / "scripts" / "viventium" / "native_stack.sh"
    ).read_text(encoding="utf-8")
    start_function = source.split("start_mongo_bridge() {", 1)[1].split(
        "\n}", 1
    )[0]
    stop_function = source.split("stop_mongo_bridge() {", 1)[1].split(
        "\n}", 1
    )[0]
    start_case = source.split('case "${1:-}" in', 1)[1].split("  start)", 1)[0]

    assert "VIVENTIUM_FIRST_UPGRADE_BRIDGE_INTERNAL" in start_function
    assert 'port_listening "$MONGO_PORT"' in start_function
    assert "mongo_bridge_pid_matches_expected" in start_function
    assert "VIVENTIUM_BRIDGE_MONGO_PID=" in start_function
    assert "VIVENTIUM_FIRST_UPGRADE_BRIDGE_INTERNAL" in stop_function
    assert '"$actual_pid" != "$expected_pid"' in stop_function
    assert 'mongo_bridge_pid_matches_expected "$expected_pid"' in stop_function
    assert "start-mongo-only)" in start_case
    assert "stop-mongo-only)" in start_case
    assert "start_meili" not in start_case
    assert "start_livekit" not in start_case


def _checkpoint_context(
    module,
    tmp_path: Path,
    *,
    storage: dict[str, object],
    runtime_lines: list[str],
):
    repo_root = tmp_path / "repo"
    app_support = tmp_path / "support"
    transaction = app_support / "upgrade-backups" / "tx"
    checkpoint_runtime = transaction / "checkpoint" / "runtime"
    checkpoint_runtime.mkdir(parents=True)
    runtime_env = checkpoint_runtime / "runtime.env"
    runtime_env.write_text("\n".join(runtime_lines) + "\n", encoding="utf-8")
    runtime_env.chmod(0o400)
    checkpoint_runtime.chmod(0o500)
    transaction.chmod(0o700)
    repo_root.mkdir()
    manifest = {
        "kind": "directory",
        "files": [
            {
                "path": "runtime.env",
                "size": runtime_env.stat().st_size,
                "sha256": hashlib.sha256(runtime_env.read_bytes()).hexdigest(),
            }
        ],
    }
    context = module.UpgradeContext(
        repo_root=repo_root,
        app_support_dir=app_support,
        transaction=transaction,
        ledger={
            "storage_inventory": {"mongodb": storage},
            "surfaces": [
                {
                    "label": "runtime",
                    "backup": str(checkpoint_runtime),
                    "manifest": manifest,
                }
            ],
        },
        predecessor="a" * 40,
        successor="b" * 40,
        was_running=True,
    )
    return context, checkpoint_runtime


def test_native_checkpoint_mongo_forces_recorded_identity_and_mongo_only_actions(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_module()
    data_path = tmp_path / "support" / "data" / "mongodb"
    data_path.mkdir(parents=True)
    mongod = tmp_path / "support" / "runtime-tools" / "mongo" / "bin" / "mongod"
    mongod.parent.mkdir(parents=True)
    mongod.write_text(
        "#!/bin/sh\nprintf '%s\\n' 'db version v8.0.23'\n",
        encoding="utf-8",
    )
    mongod.chmod(0o700)
    mongod_sha256 = hashlib.sha256(mongod.read_bytes()).hexdigest()
    recorded_arguments = [
        str(mongod),
        "--port",
        "28117",
        "--dbpath",
        str(data_path),
    ]
    context, checkpoint_runtime = _checkpoint_context(
        module,
        tmp_path,
        storage={
            "backend": "app_support_bind",
            "runtime_engine": "native",
            "profile": "native",
            "path": str(data_path),
            "observed_from": "running_native_pid",
            "pid": 4141,
            "process_started_at": "Fri Jul 24 10:11:12 2026",
            "executable": str(mongod),
            "executable_sha256": mongod_sha256,
            "arguments": recorded_arguments,
            "version": "db version v8.0.23",
            "code_signature_verified": False,
            "code_signature_team_identifier": "",
            "checkpoint_status": "complete",
            "existed_before": True,
        },
        runtime_lines=[
            "VIVENTIUM_RUNTIME_PROFILE=native",
            "VIVENTIUM_LOCAL_MONGO_PORT=28117",
            "VIVENTIUM_LOCAL_MONGO_DB=RecordedDatabase",
            "VIVENTIUM_INSTALL_EXPERIENCE=express",
        ],
    )
    captures: list[tuple[list[str], dict[str, str]]] = []
    checked: list[tuple[list[str], dict[str, str]]] = []

    def capture(command, *, environment, timeout):
        captures.append((command, environment))
        return "native log\nVIVENTIUM_BRIDGE_MONGO_PID=4242\n"

    def checked_command(command, *, environment, timeout):
        checked.append((command, environment))

    monkeypatch.setenv("VIVENTIUM_LOCAL_MONGO_DATA_PATH", "/candidate/wrong")
    monkeypatch.setattr(module, "_run_capture", capture)
    monkeypatch.setattr(module, "_run_checked", checked_command)
    monkeypatch.setattr(
        module.upgrade_transaction,
        "inspect_native_mongo_process",
        lambda _pid: {
            "pid": 4242,
            "process_started_at": "Fri Jul 24 10:12:12 2026",
            "executable": str(mongod),
            "executable_sha256": mongod_sha256,
            "arguments": recorded_arguments,
            "version": "db version v8.0.23",
            "code_signature_verified": False,
            "code_signature_team_identifier": "",
        },
    )

    session = module._start_checkpoint_mongo(context, checkpoint_runtime)
    module._stop_checkpoint_mongo(context, session)

    assert len(captures) == 1
    start_command, start_env = captures[0]
    assert start_command[-1] == "start-mongo-only"
    assert start_env["VIVENTIUM_APP_SUPPORT_DIR"] == str(context.app_support_dir)
    assert start_env["VIVENTIUM_BASE_STATE_DIR"] == str(
        context.app_support_dir / "state"
    )
    assert start_env["VIVENTIUM_RUNTIME_PROFILE"] == "native"
    assert start_env["VIVENTIUM_LOCAL_MONGO_DATA_PATH"] == str(data_path)
    assert start_env["VIVENTIUM_LOCAL_MONGO_PORT"] == "28117"
    assert start_env["VIVENTIUM_LOCAL_MONGO_DB"] == "RecordedDatabase"
    assert start_env["MONGO_HOST"] == "127.0.0.1"
    assert start_env["VIVENTIUM_INSTALL_EXPERIENCE"] == "express"
    assert start_env["VIVENTIUM_NATIVE_STACK_SKIP_LIVEKIT"] == "1"
    assert start_env["VIVENTIUM_NATIVE_STACK_SKIP_MEILI"] == "1"
    assert start_env["VIVENTIUM_VOICE_ENABLED"] == "false"
    assert start_env["VIVENTIUM_BRIDGE_MONGOD_BINARY"] == str(mongod)
    assert checked[0][0][-2:] == ["stop-mongo-only", "4242"]
    assert checked[0][1] == start_env


def test_checkpoint_mongo_never_infers_engine_from_native_install_mode(
    tmp_path: Path,
) -> None:
    module = load_module()
    data_path = tmp_path / "support" / "data" / "mongodb"
    data_path.mkdir(parents=True)
    context, checkpoint_runtime = _checkpoint_context(
        module,
        tmp_path,
        storage={
            "backend": "app_support_bind",
            "profile": "isolated",
            "path": str(data_path),
            "observed_from": "configured_path_without_running_process",
            "checkpoint_status": "complete",
            "existed_before": True,
        },
        runtime_lines=[
            "VIVENTIUM_RUNTIME_PROFILE=isolated",
            "VIVENTIUM_INSTALL_MODE=native",
        ],
    )

    with pytest.raises(
        module.FirstUpgradeBridgeError,
        match="runtime engine proof is missing",
    ):
        module._checkpoint_mongo_spec(context, checkpoint_runtime)


def test_checkpoint_mongo_rejects_candidate_label_or_uncheckpointed_storage(
    tmp_path: Path,
) -> None:
    module = load_module()
    data_path = tmp_path / "support" / "data" / "mongodb"
    data_path.mkdir(parents=True)
    context, checkpoint_runtime = _checkpoint_context(
        module,
        tmp_path,
        storage={
            "backend": "app_support_bind",
            "runtime_engine": "native",
            "profile": "native",
            "path": str(data_path),
            "checkpoint_status": "pending",
            "existed_before": True,
        },
        runtime_lines=["VIVENTIUM_RUNTIME_PROFILE=compat"],
    )

    with pytest.raises(module.FirstUpgradeBridgeError, match="checkpoint"):
        module._checkpoint_mongo_spec(context, checkpoint_runtime)


def test_docker_checkpoint_mongo_command_is_transaction_bound_and_loopback_only(
    tmp_path: Path,
) -> None:
    module = load_module()
    context, checkpoint_runtime = _checkpoint_context(
        module,
        tmp_path,
        storage={
            "backend": "docker_named_volume",
            "profile": "compat",
            "volume_name": "recorded-mongo-volume",
            "image": "mongo:8.0.17",
            "image_id": "sha256:" + "d" * 64,
            "checkpoint_status": "complete",
            "existed_before": True,
        },
        runtime_lines=[
            "VIVENTIUM_RUNTIME_PROFILE=compat",
            "VIVENTIUM_LOCAL_MONGO_PORT=29117",
        ],
    )

    spec = module._checkpoint_mongo_spec(context, checkpoint_runtime)
    name, labels = module._docker_bridge_identity(context)
    command = module._docker_run_args(spec, name=name, labels=labels)

    assert name.startswith("viventium-first-upgrade-mongo-")
    assert "--restart" in command
    assert command[command.index("--restart") + 1] == "no"
    assert command[command.index("--publish") + 1] == "127.0.0.1:29117:27017"
    assert command[command.index("--mount") + 1] == (
        "type=volume,source=recorded-mongo-volume,target=/data/db"
    )
    assert command[-1] == "sha256:" + "d" * 64
    assert all("/candidate/" not in item for item in command)
    assert labels["com.viventium.first-upgrade.transaction"]


def test_docker_checkpoint_refuses_mutable_tag_without_immutable_image_id(
    tmp_path: Path,
) -> None:
    module = load_module()
    context, checkpoint_runtime = _checkpoint_context(
        module,
        tmp_path,
        storage={
            "backend": "docker_named_volume",
            "profile": "compat",
            "volume_name": "recorded-mongo-volume",
            "image": "mongo:8.0.17",
            "checkpoint_status": "complete",
            "existed_before": True,
        },
        runtime_lines=["VIVENTIUM_RUNTIME_PROFILE=compat"],
    )
    spec = module._checkpoint_mongo_spec(context, checkpoint_runtime)
    name, labels = module._docker_bridge_identity(context)

    with pytest.raises(
        module.FirstUpgradeBridgeError,
        match="immutable image identity",
    ):
        module._docker_run_args(spec, name=name, labels=labels)


def test_native_checkpoint_rejects_recorded_predecessor_version_mismatch(
    tmp_path: Path,
) -> None:
    module = load_module()
    data_path = tmp_path / "support" / "data" / "mongodb"
    data_path.mkdir(parents=True)
    mongod = tmp_path / "support" / "runtime-tools" / "mongo" / "bin" / "mongod"
    mongod.parent.mkdir(parents=True)
    mongod.write_text(
        "#!/bin/sh\nprintf '%s\\n' 'db version v8.0.24'\n",
        encoding="utf-8",
    )
    mongod.chmod(0o700)
    context, checkpoint_runtime = _checkpoint_context(
        module,
        tmp_path,
        storage={
            "backend": "app_support_bind",
            "runtime_engine": "native",
            "profile": "native",
            "path": str(data_path),
            "observed_from": "running_native_pid",
            "pid": 4141,
            "process_started_at": "Fri Jul 24 10:11:12 2026",
            "executable": str(mongod),
            "executable_sha256": hashlib.sha256(mongod.read_bytes()).hexdigest(),
            "arguments": [str(mongod), "--dbpath", str(data_path)],
            "version": "db version v8.0.23",
            "checkpoint_status": "complete",
            "existed_before": True,
        },
        runtime_lines=["VIVENTIUM_RUNTIME_PROFILE=native"],
    )

    with pytest.raises(module.FirstUpgradeBridgeError, match="version changed"):
        module._checkpoint_mongo_spec(context, checkpoint_runtime)


def test_old_docker_bind_ledger_without_engine_image_fails_closed(
    tmp_path: Path,
) -> None:
    module = load_module()
    data_path = tmp_path / "support" / "data" / "mongodb"
    data_path.mkdir(parents=True)
    context, checkpoint_runtime = _checkpoint_context(
        module,
        tmp_path,
        storage={
            "backend": "app_support_bind",
            "profile": "compat",
            "path": str(data_path),
            "observed_from": "container_inspect",
            "checkpoint_status": "complete",
            "existed_before": True,
        },
        runtime_lines=["VIVENTIUM_RUNTIME_PROFILE=compat"],
    )

    with pytest.raises(module.FirstUpgradeBridgeError, match="engine"):
        module._checkpoint_mongo_spec(context, checkpoint_runtime)


def test_exact_d59_isolated_docker_bind_without_engine_proof_fails_closed(
    tmp_path: Path,
) -> None:
    module = load_module()
    data_path = tmp_path / "support" / "state" / "runtime" / "isolated" / "mongo-data"
    data_path.mkdir(parents=True)
    context, checkpoint_runtime = _checkpoint_context(
        module,
        tmp_path,
        storage={
            # Exact storage shape emitted by d59 before it stopped the stack.
            "backend": "app_support_bind",
            "profile": "isolated",
            "path": str(data_path),
            "checkpoint_status": "complete",
            "existed_before": True,
        },
        runtime_lines=[
            "VIVENTIUM_RUNTIME_PROFILE=isolated",
            "VIVENTIUM_INSTALL_MODE=docker",
            "VIVENTIUM_LOCAL_MONGO_DATA_PATH=" + str(data_path),
        ],
    )
    context = module.UpgradeContext(
        **{
            **context.__dict__,
            "predecessor": SHIPPED_PREDECESSOR,
        }
    )

    with pytest.raises(module.FirstUpgradeBridgeError, match="engine proof"):
        module._checkpoint_mongo_spec(context, checkpoint_runtime)


def test_future_docker_bind_ledger_uses_recorded_image_and_exact_bind_mount(
    tmp_path: Path,
) -> None:
    module = load_module()
    data_path = tmp_path / "support" / "data" / "mongodb"
    data_path.mkdir(parents=True)
    context, checkpoint_runtime = _checkpoint_context(
        module,
        tmp_path,
        storage={
            "backend": "app_support_bind",
            "runtime_engine": "docker",
            "profile": "compat",
            "path": str(data_path),
            "image": "mongo:8.0.17",
            "image_id": "sha256:" + "d" * 64,
            "observed_from": "container_inspect",
            "checkpoint_status": "complete",
            "existed_before": True,
        },
        runtime_lines=[
            "VIVENTIUM_RUNTIME_PROFILE=compat",
            "VIVENTIUM_LOCAL_MONGO_PORT=31117",
        ],
    )

    spec = module._checkpoint_mongo_spec(context, checkpoint_runtime)
    name, labels = module._docker_bridge_identity(context)
    command = module._docker_run_args(spec, name=name, labels=labels)

    assert spec.runtime_engine == "docker"
    assert command[command.index("--publish") + 1] == "127.0.0.1:31117:27017"
    assert command[command.index("--mount") + 1] == (
        f"type=bind,source={data_path},target=/data/db"
    )
    assert command[-1] == "sha256:" + "d" * 64


def test_docker_checkpoint_cleanup_refuses_same_name_with_wrong_identity(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_module()
    context, checkpoint_runtime = _checkpoint_context(
        module,
        tmp_path,
        storage={
            "backend": "docker_named_volume",
            "profile": "compat",
            "volume_name": "recorded-mongo-volume",
            "image": "mongo:8.0.17",
            "image_id": "sha256:" + "d" * 64,
            "checkpoint_status": "complete",
            "existed_before": True,
        },
        runtime_lines=["VIVENTIUM_RUNTIME_PROFILE=compat"],
    )
    spec = module._checkpoint_mongo_spec(context, checkpoint_runtime)
    name, labels = module._docker_bridge_identity(context)
    wrong = {
        "Id": "a" * 64,
        "Name": f"/{name}",
        "Config": {
            "Image": spec.image_id,
            "Labels": {
                **labels,
                "com.viventium.first-upgrade.transaction": "wrong",
            },
        },
        "Image": spec.image_id,
        "Mounts": [
            {
                "Destination": "/data/db",
                "Type": "volume",
                "Name": spec.volume_name,
            }
        ],
        "HostConfig": {
            "RestartPolicy": {"Name": "no"},
            "PortBindings": {
                "27017/tcp": [{"HostIp": "127.0.0.1", "HostPort": str(spec.port)}]
            },
        },
    }
    monkeypatch.setattr(module, "_docker_inspect", lambda *_args, **_kwargs: wrong)

    with pytest.raises(module.FirstUpgradeBridgeError, match="identity"):
        module._remove_interrupted_docker_bridge(
            spec,
            name=name,
            labels=labels,
        )


def test_docker_checkpoint_rejects_retargeted_image_identity(
    tmp_path: Path,
) -> None:
    module = load_module()
    context, checkpoint_runtime = _checkpoint_context(
        module,
        tmp_path,
        storage={
            "backend": "docker_named_volume",
            "profile": "compat",
            "volume_name": "recorded-mongo-volume",
            "image": "mongo:8.0.17",
            "image_id": "sha256:" + "d" * 64,
            "checkpoint_status": "complete",
            "existed_before": True,
        },
        runtime_lines=["VIVENTIUM_RUNTIME_PROFILE=compat"],
    )
    spec = module._checkpoint_mongo_spec(context, checkpoint_runtime)
    name, labels = module._docker_bridge_identity(context)
    inspected = {
        "Id": "a" * 64,
        "Name": f"/{name}",
        "Config": {"Image": spec.image_id, "Labels": labels},
        "Image": "sha256:" + "e" * 64,
        "Mounts": [
            {
                "Destination": "/data/db",
                "Type": "volume",
                "Name": spec.volume_name,
            }
        ],
        "HostConfig": {
            "RestartPolicy": {"Name": "no"},
            "PortBindings": {
                "27017/tcp": [{"HostIp": "127.0.0.1", "HostPort": str(spec.port)}]
            },
        },
        "State": {"Running": True},
    }

    with pytest.raises(module.FirstUpgradeBridgeError, match="identity mismatch"):
        module._verify_docker_container(
            inspected,
            spec,
            name=name,
            labels=labels,
            expected_id="a" * 64,
            require_running=True,
        )


def test_docker_checkpoint_mongo_lifecycle_proves_readiness_then_exact_cleanup(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_module()
    context, checkpoint_runtime = _checkpoint_context(
        module,
        tmp_path,
        storage={
            "backend": "docker_named_volume",
            "profile": "compat",
            "volume_name": "recorded-mongo-volume",
            "image": "mongo:8.0.17",
            "image_id": "sha256:" + "d" * 64,
            "checkpoint_status": "complete",
            "existed_before": True,
        },
        runtime_lines=[
            "VIVENTIUM_RUNTIME_PROFILE=compat",
            "VIVENTIUM_LOCAL_MONGO_PORT=30117",
        ],
    )
    spec = module._checkpoint_mongo_spec(context, checkpoint_runtime)
    name, labels = module._docker_bridge_identity(context)
    container_id = "b" * 64
    inspected = {
        "Id": container_id,
        "Name": f"/{name}",
        "Config": {"Image": spec.image_id, "Labels": labels},
        "Image": spec.image_id,
        "Mounts": [
            {
                "Destination": "/data/db",
                "Type": "volume",
                "Name": spec.volume_name,
            }
        ],
        "HostConfig": {
            "RestartPolicy": {"Name": "no"},
            "PortBindings": {
                "27017/tcp": [{"HostIp": "127.0.0.1", "HostPort": str(spec.port)}]
            },
        },
        "State": {"Running": True},
    }
    calls: list[list[str]] = []
    inspect_calls: list[str] = []
    cleanup_started = False

    def docker_call(arguments, *, check=True, timeout=60):
        nonlocal cleanup_started
        calls.append(arguments)
        if arguments[:2] == ["container", "stop"]:
            cleanup_started = True
        stdout = container_id + "\n" if arguments[:1] == ["run"] else ""
        return subprocess.CompletedProcess(arguments, 0, stdout, "")

    def docker_inspect(identifier, *, allow_missing=False):
        inspect_calls.append(identifier)
        if identifier == name:
            return None
        if cleanup_started and identifier == container_id and allow_missing:
            return None
        return inspected

    monkeypatch.setattr(module, "_docker_call", docker_call)
    monkeypatch.setattr(module, "_docker_inspect", docker_inspect)

    session = module._start_checkpoint_mongo(context, checkpoint_runtime)
    module._stop_checkpoint_mongo(context, session)

    assert calls[0] == ["volume", "inspect", "recorded-mongo-volume"]
    assert calls[1] == ["image", "inspect", "sha256:" + "d" * 64]
    run = next(command for command in calls if command[0] == "run")
    assert "--pull" in run and run[run.index("--pull") + 1] == "never"
    readiness = next(
        command for command in calls if command[:2] == ["container", "exec"]
    )
    assert readiness[2] == container_id
    assert "adminCommand({ping:1})" in readiness[-1]
    assert ["container", "stop", "--time", "30", container_id] in calls
    assert ["container", "rm", container_id] in calls
    assert inspect_calls[-1] == container_id


@pytest.mark.parametrize(
    ("corrupt_successor_helper", "kill_after_quiesced_start"),
    [
        pytest.param(False, False, id="healthy"),
        pytest.param(True, False, id="corrupt-helper"),
        pytest.param(False, True, id="sigkill-after-candidate-activation"),
    ],
)
@pytest.mark.parametrize("was_running", [False, True])
def test_exact_shipped_shell_hands_acceptance_to_successor_and_finalizes_uploads(
    tmp_path: Path,
    cleanup_exact_shell_processes,
    corrupt_successor_helper: bool,
    kill_after_quiesced_start: bool,
    was_running: bool,
) -> None:
    """Exercise the exact d59 shell text across a real two-commit fast-forward.

    The repository is synthetic so no real services or user state are touched, but
    the shell process itself is byte-for-byte the accepted predecessor artifact.
    The SIGKILL lane kills only this disposable process group after successor-owned
    quiesced validation begins, then proves a fresh CLI process recovers the exact
    predecessor checkpoint.
    """

    fixtures = load_cli_test_module()
    repo_root, support = fixtures.build_transactional_upgrade_failure_fixture(tmp_path, "none")
    mongo_data = support / "state" / "runtime" / "isolated" / "mongo-data"
    mongo_data.mkdir()
    (mongo_data / "collection.wt").write_bytes(b"synthetic-mongo-checkpoint")
    (mongo_data / "WiredTiger").write_bytes(b"synthetic-engine-anchor")
    # The exact d59 shell cannot create this proof itself. This fixture models
    # the separately reviewed intermediate/recovery lane: it observed the
    # predecessor's running native engine and sealed the owner-only receipt
    # before returning the exact predecessor shell to a stopped state.
    synthetic_mongod = tmp_path / "synthetic-engine" / "mongod"
    synthetic_mongod.parent.mkdir()
    synthetic_mongod_source = synthetic_mongod.with_suffix(".c")
    synthetic_mongod_source.write_text(
        """
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

static volatile sig_atomic_t running = 1;
static void stop_process(int signal_number) {
  (void)signal_number;
  running = 0;
}

int main(int argc, char **argv) {
  if (argc == 2 && strcmp(argv[1], "--version") == 0) {
    puts("db version v8.0.23");
    return 0;
  }
  signal(SIGTERM, stop_process);
  signal(SIGINT, stop_process);
  while (running) {
    pause();
  }
  return 0;
}
""".lstrip(),
        encoding="utf-8",
    )
    subprocess.run(
        ["cc", "-O2", "-o", str(synthetic_mongod), str(synthetic_mongod_source)],
        check=True,
        capture_output=True,
        text=True,
    )
    transaction_module = load_module().upgrade_transaction
    predecessor_engine_identity = {
        "backend": "app_support_bind",
        "runtime_engine": "native",
        "profile": "isolated",
        "path": str(mongo_data),
        "observed_from": "running_native_pid",
        "pid": 4242,
        "process_started_at": "Fri Jul 24 10:11:12 2026",
        "executable": str(synthetic_mongod),
        "executable_sha256": hashlib.sha256(
            synthetic_mongod.read_bytes()
        ).hexdigest(),
        "arguments": [
            str(synthetic_mongod),
            "--port",
            "27117",
            "--dbpath",
            str(mongo_data),
        ],
        "version": "db version v8.0.23",
        "code_signature_verified": False,
        "code_signature_team_identifier": "",
    }
    transaction_module._write_mongo_engine_receipt(
        support,
        {
            "schema_version": (
                transaction_module.MONGO_ENGINE_IDENTITY_SCHEMA_VERSION
            ),
            "recorded_at": "20260724T000000Z",
            "sealed_at": "20260724T000001Z",
            "clean_stopped": True,
            "identity": predecessor_engine_identity,
            "storage_anchor": transaction_module._mongo_storage_anchor(
                predecessor_engine_identity,
                support=support,
            ),
        },
    )
    helper_config = support / "helper-config.json"
    helper_config_before = (
        b'{\n'
        b'  "showInStatusBar": false,\n'
        b'  "allowProtectedRepoRoot": true,\n'
        b'  "ownerFutureSetting": {"mode": "preserve-d59"},\n'
        b'  "runtimeSupervision": {"desiredState": "running"}\n'
        b'}\n'
    )
    helper_config.write_bytes(helper_config_before)
    helper_config.chmod(0o600)
    nested = repo_root / "viventium_v0_4" / "LibreChat"
    subprocess.run(
        ["git", "config", "user.name", "Synthetic QA"],
        cwd=nested,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "qa@example.invalid"],
        cwd=nested,
        check=True,
    )
    (nested / ".gitignore").write_text("uploads/\n", encoding="utf-8")
    subprocess.run(["git", "add", ".gitignore"], cwd=nested, check=True)
    subprocess.run(
        ["git", "commit", "--quiet", "-m", "ignore synthetic uploads"],
        cwd=nested,
        check=True,
    )
    legacy_upload = nested / "uploads" / "files" / "preserved.txt"
    legacy_upload.parent.mkdir(parents=True)
    legacy_upload.write_text("preserved-user-upload\n", encoding="utf-8")
    legacy_telegram_root = (
        repo_root
        / "viventium_v0_4"
        / "telegram-viventium"
        / "TelegramVivBot"
        / "user_configs"
    )
    legacy_telegram_root.mkdir(parents=True)
    legacy_telegram_value = b'{"language":"fr","ownerFutureSetting":"preserve"}\n'
    (legacy_telegram_root / "global.json").write_bytes(legacy_telegram_value)
    parent_ignore = repo_root / ".gitignore"
    parent_ignore.write_text(
        (
            parent_ignore.read_text(encoding="utf-8")
            if parent_ignore.exists()
            else ""
        )
        + "\nviventium_v0_4/telegram-viventium/TelegramVivBot/user_configs/\n",
        encoding="utf-8",
    )

    exact_shell = subprocess.run(
        ["git", "show", f"{SHIPPED_PREDECESSOR}:bin/viventium"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "candidate_activated" in exact_shell
    assert "first_upgrade_bridge" not in exact_shell
    fixtures.write_executable(repo_root / "bin" / "viventium", exact_shell)
    predecessor_runtime = support / "runtime" / "runtime.env"
    predecessor_runtime.write_text(
        predecessor_runtime.read_text(encoding="utf-8")
        + "VIVENTIUM_INSTALL_MODE=native\n"
        + "VIVENTIUM_CALL_SESSION_SECRET=synthetic-predecessor-secret\n",
        encoding="utf-8",
    )
    predecessor_compiler = repo_root / "scripts" / "viventium" / "config_compiler.py"
    predecessor_compiler.write_text(
        predecessor_compiler.read_text(encoding="utf-8").replace(
            '    "VIVENTIUM_INSTALL_EXPERIENCE=express\\n"\n',
            '    "VIVENTIUM_INSTALL_EXPERIENCE=express\\n"\n'
            '    "VIVENTIUM_INSTALL_MODE=native\\n"\n'
            '    "VIVENTIUM_CALL_SESSION_SECRET=synthetic-predecessor-secret\\n"\n',
        ),
        encoding="utf-8",
    )
    fixtures.write_executable(
        tmp_path / "fake-bin" / "curl",
        """#!/usr/bin/env bash
if [[ -f "${TEST_ROOT}/core-running" ]]; then
  printf '200'
  exit 0
fi
printf '000'
exit 1
""",
    )
    fixtures.write_executable(
        tmp_path / "fake-bin" / "ps",
        """#!/usr/bin/env bash
if [[ "${1:-}" == "-axo" ]]; then
  exit 0
fi
exec /bin/ps "$@"
""",
    )
    fixtures.write_executable(
        repo_root / "viventium_v0_4" / "viventium-librechat-start.sh",
        """#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "--stop" ]]; then
  printf 'stop-runtime\\n' >>"${TEST_ROOT}/upgrade-events"
  rm -f "${TEST_ROOT}/core-running"
  touch "${TEST_ROOT}/stop-called"
  exit 0
fi
printf 'restored-predecessor-start\\n' >>"${TEST_ROOT}/upgrade-events"
rm -f "${TEST_ROOT}/stop-called"
touch "${TEST_ROOT}/core-running"
""",
    )
    subprocess.run(
        [
            "git",
            "add",
            "bin/viventium",
            ".gitignore",
            "scripts/viventium/config_compiler.py",
            "viventium_v0_4/LibreChat",
            "viventium_v0_4/viventium-librechat-start.sh",
        ],
        cwd=repo_root,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "--quiet", "-m", "exact d59 shipped shell predecessor"],
        cwd=repo_root,
        check=True,
    )
    predecessor = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    subprocess.run(
        ["git", "checkout", "-b", "release-target"],
        cwd=repo_root,
        check=True,
        capture_output=True,
    )
    for relative in (
        "bin/viventium",
        "scripts/viventium/first_upgrade_bridge.py",
        "scripts/viventium/helper_artifact_verify.py",
        "scripts/viventium/helper_runtime_intent.py",
        "scripts/viventium/telegram_user_config_migration.py",
        "scripts/viventium/upgrade_support.py",
        "scripts/viventium/uploads_migration.py",
    ):
        destination = repo_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / relative, destination)
    fixtures.write_executable(
        repo_root / "scripts" / "viventium" / "telegram_runtime_component.py",
        """#!/usr/bin/env python3
import argparse
import hashlib
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("action")
parser.add_argument("--repo-root")
parser.add_argument("--app-support-dir", required=True)
parser.add_argument("--selection-file")
parser.add_argument("--sync-dependencies", action="store_true")
parser.add_argument("--transaction-kind")
parser.add_argument("--transaction-path")
parser.add_argument("--user-configs-root")
args = parser.parse_args()
support = Path(args.app_support_dir)
continuity = support / "state/continuity"
receipt = continuity / "telegram-recovery-active.json"
generation = continuity / "telegram-recovery-generation.json"

def write_private(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True) + "\\n", encoding="utf-8")
    path.chmod(0o600)

if args.action == "prepare":
    if not args.selection_file:
        parser.error("--selection-file is required for prepare")
    selection = Path(args.selection_file)
    selection.parent.mkdir(parents=True, exist_ok=True)
    component = support / "runtime-components/telegram-viventium/synthetic"
    component.mkdir(parents=True, exist_ok=True)
    component.chmod(0o700)
    launcher = component / "launcher.sh"
    launcher.write_text(
        "#!/usr/bin/env bash\\n"
        "set -euo pipefail\\n"
        'exec "${VIVENTIUM_HELPER_V0_ROOT:?}/viventium-librechat-start.sh" "$@"\\n',
        encoding="utf-8",
    )
    launcher.chmod(0o600)
    handoff = component / "handoff.py"
    handoff.write_text("# synthetic\\n", encoding="utf-8")
    handoff.chmod(0o600)
    component_tool = component / "component.py"
    component_tool.write_bytes(Path(__file__).read_bytes())
    component_tool.chmod(0o600)
    payload = {
        "schema_version": 2,
        "component": "telegram-viventium",
        "code_root": str(component),
        "compat_launcher": str(component / "launcher.sh"),
        "component_tool": str(component_tool),
        "handoff_helper": str(component / "handoff.py"),
    }
    write_private(selection, payload)
    print(json.dumps(payload, sort_keys=True))
elif args.action == "resolve":
    if not args.selection_file:
        parser.error("--selection-file is required for resolve")
    selection_payload = json.loads(
        Path(args.selection_file).read_text(encoding="utf-8")
    )
    print(json.dumps(selection_payload, sort_keys=True))
elif args.action == "publish-recovery":
    if not all((
        args.selection_file,
        args.transaction_kind,
        args.transaction_path,
        args.user_configs_root,
    )):
        parser.error("publish-recovery requires selection, transaction, and preference roots")
    selection_payload = json.loads(
        Path(args.selection_file).read_text(encoding="utf-8")
    )
    ledger = json.loads(
        (Path(args.transaction_path) / "ledger.json").read_text(encoding="utf-8")
    )
    generation_id = hashlib.sha256(
        (
            args.transaction_kind
            + "\\0"
            + args.transaction_path
            + "\\0"
            + json.dumps(selection_payload, sort_keys=True)
        ).encode("utf-8")
    ).hexdigest()
    write_private(generation, {
        "schema_version": 1,
        "kind": "viventium-telegram-recovery-generation",
        "status": "active",
        "generation_id": generation_id,
        "transaction_kind": args.transaction_kind,
        "transaction_path": args.transaction_path,
    })
    write_private(receipt, {
        "schema_version": 1,
        "kind": "viventium-telegram-recovery",
        "status": "armed",
        "generation_id": generation_id,
        "transaction_kind": args.transaction_kind,
        "transaction_path": args.transaction_path,
        "was_running": bool(ledger["was_running"]),
        "user_configs_root": args.user_configs_root,
        "selection_file": args.selection_file,
        "selection": selection_payload,
    })
    print(json.dumps({"status": "armed", "generation_id": generation_id}))
elif args.action == "resolve-recovery":
    recovery_payload = json.loads(receipt.read_text(encoding="utf-8"))
    generation_payload = json.loads(generation.read_text(encoding="utf-8"))
    if (
        recovery_payload["generation_id"] != generation_payload["generation_id"]
        or generation_payload["status"] != "active"
    ):
        raise SystemExit("recovery generation mismatch")
    selection_file = Path(recovery_payload["selection_file"])
    selection_payload = json.loads(selection_file.read_text(encoding="utf-8"))
    if selection_payload != recovery_payload["selection"]:
        raise SystemExit("recovery selection mismatch")
    ledger_payload = json.loads(
        (Path(recovery_payload["transaction_path"]) / "ledger.json").read_text(
            encoding="utf-8"
        )
    )
    print(json.dumps({
        **selection_payload,
        "disposition": (
            "recovery"
            if ledger_payload["status"] == "rolled_back"
            else "passive"
        ),
        "transaction_kind": recovery_payload["transaction_kind"],
        "transaction_path": recovery_payload["transaction_path"],
        "was_running": recovery_payload["was_running"],
        "selection_file": str(selection_file),
        "user_configs_root": recovery_payload["user_configs_root"],
    }, sort_keys=True))
elif args.action == "clear-recovery":
    if generation.is_file():
        payload = json.loads(generation.read_text(encoding="utf-8"))
        payload["status"] = "retired"
        write_private(generation, payload)
    receipt.unlink(missing_ok=True)
    print(json.dumps({"status": "retired"}))
else:
    parser.error("unsupported action")
""",
    )
    fixtures.write_executable(
        repo_root / "viventium_v0_4" / "viventium-librechat-start.sh",
        """#!/usr/bin/env bash
set -euo pipefail
events="${TEST_ROOT}/upgrade-events"
if [[ "${1:-}" == "--stop" ]]; then
  printf 'stop-runtime\\n' >>"$events"
  rm -f "${TEST_ROOT}/core-running"
  touch "${TEST_ROOT}/stop-called"
  exit 0
fi
candidate=0
grep -q '^CANDIDATE=1$' "${TEST_ROOT}/app-support/runtime/runtime.env" && candidate=1
if [[ "${VIVENTIUM_SUCCESSOR_VALIDATION_MODE:-}" == "quiesced" ]]; then
  expected='agent-seeding,canonical-uploads,channel-workers,glasshive-callbacks,librechat-mcp-oauth,prompt-workbench,rag-recall,remote-mapping,scheduler,stale-cortex-recovery,telegram,telegram-codex,voice-workers'
  [[ "${VIVENTIUM_SUCCESSOR_VALIDATION_INTERNAL:-0}" == "1" ]]
  [[ "${VIVENTIUM_SUCCESSOR_VALIDATION_DISABLED_WRITERS:-}" == "$expected" ]]
  [[ -f "${TEST_ROOT}/app-support/state/upgrade-transaction-active.json" ]]
  printf 'quiesced-start\\n' >>"$events"
  if [[ "${VIVENTIUM_QA_BLOCK_AT_QUIESCED_START:-0}" == "1" ]]; then
    touch "${TEST_ROOT}/sigkill-ready"
    while [[ ! -f "${TEST_ROOT}/sigkill-release" ]]; do
      sleep 0.05
    done
  fi
else
  if [[ -f "${TEST_ROOT}/app-support/state/upgrade-transaction-active.json" ]]; then
    printf 'WRITER-START-BEFORE-COMMIT\\n' >>"$events"
    exit 91
  fi
  if [[ "$candidate" == "1" ]]; then
    printf 'full-successor-start\\n' >>"$events"
    if [[ -n "${VIVENTIUM_POSTCOMMIT_FINALIZATION_ID:-}" ]]; then
      receipt="${TEST_ROOT}/app-support/state/continuity/postcommit-api-finalization.json"
      mkdir -p "$(dirname "$receipt")"
      python3 - "$receipt" <<'PY'
import json
import os
import sys
from pathlib import Path

path = Path(sys.argv[1])
path.write_text(json.dumps({
    "schemaVersion": 1,
    "runId": os.environ["VIVENTIUM_POSTCOMMIT_FINALIZATION_ID"],
    "sourceId": os.environ["VIVENTIUM_POSTCOMMIT_SOURCE_ID"],
    "status": "ready",
    "stage": "ready",
    "attempt": 1,
    "completed": [
        "database-connected",
        "database-seed-ready",
        "startup-checks-ready",
        "interface-permissions-ready",
        "mcp-runtime-ready",
        "oauth-reconnect-ready",
        "channel-persistence-ready",
        "permission-migration-inspection",
        "stale-cortex-recovery",
        "generation-runtime-ready",
    ],
    "degraded": [{
        "stage": "derived-search-index",
        "code": "best-effort-derived-state",
    }],
}) + "\\n", encoding="utf-8")
path.chmod(0o600)
PY
    fi
  else
    printf 'restored-predecessor-start\\n' >>"$events"
  fi
fi
rm -f "${TEST_ROOT}/stop-called"
touch "${TEST_ROOT}/core-running"
""",
    )
    fixtures.write_executable(
        repo_root / "scripts" / "viventium" / "native_stack.sh",
        """#!/usr/bin/env bash
set -euo pipefail
case "${1:-}" in
  start-mongo-only)
    [[ "${VIVENTIUM_FIRST_UPGRADE_BRIDGE_INTERNAL:-0}" == "1" ]]
    [[ "${VIVENTIUM_NATIVE_STACK_SKIP_LIVEKIT:-0}" == "1" ]]
    [[ "${VIVENTIUM_NATIVE_STACK_SKIP_MEILI:-0}" == "1" ]]
    [[ "${VIVENTIUM_LOCAL_MONGO_DATA_PATH:-}" == "${TEST_ROOT}/app-support/state/runtime/isolated/mongo-data" ]]
    "${VIVENTIUM_BRIDGE_MONGOD_BINARY:?}" \
      --bind_ip "${MONGO_HOST:-127.0.0.1}" \
      --port "${VIVENTIUM_LOCAL_MONGO_PORT:-27117}" \
      --dbpath "${VIVENTIUM_LOCAL_MONGO_DATA_PATH}" \
      >/dev/null 2>&1 &
    bridge_pid=$!
    printf '%s\\n' "$bridge_pid" >"${TEST_ROOT}/bridge-mongo.pid"
    touch "${TEST_ROOT}/bridge-mongo-running"
    printf 'VIVENTIUM_BRIDGE_MONGO_PID=%s\\n' "$bridge_pid"
    ;;
  stop-mongo-only)
    [[ -f "${TEST_ROOT}/bridge-mongo.pid" ]]
    [[ "${2:-}" == "$(cat "${TEST_ROOT}/bridge-mongo.pid")" ]]
    kill "${2}"
    for _ in $(seq 1 50); do
      kill -0 "${2}" >/dev/null 2>&1 || break
      sleep 0.02
    done
    ! kill -0 "${2}" >/dev/null 2>&1
    rm -f "${TEST_ROOT}/bridge-mongo.pid"
    rm -f "${TEST_ROOT}/bridge-mongo-running"
    ;;
  start|stop) ;;
  *) exit 2 ;;
esac
""",
    )
    helper_package = repo_root / "apps" / "macos" / "ViventiumHelper"
    shutil.copytree(
        REPO_ROOT / "apps" / "macos" / "ViventiumHelper",
        helper_package,
        ignore=shutil.ignore_patterns(".build"),
    )
    if corrupt_successor_helper:
        helper_binary = helper_package / "prebuilt" / "ViventiumHelper-universal"
        helper_binary.write_bytes(helper_binary.read_bytes() + b"synthetic-corruption")
    fixtures.write_executable(
        repo_root / "scripts" / "viventium" / "config_compiler.py",
        """#!/usr/bin/env python3
import argparse
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--config', required=True)
p.add_argument('--output-dir', required=True)
a=p.parse_args()
out=Path(a.output_dir)
out.mkdir(parents=True, exist_ok=True)
(out/'runtime.env').write_text(
    'VIVENTIUM_RUNTIME_PROFILE=isolated\\n'
    'VIVENTIUM_INSTALL_EXPERIENCE=express\\n'
    'VIVENTIUM_INSTALL_MODE=native\\n'
    'VIVENTIUM_LC_API_PORT=3180\\n'
    'VIVENTIUM_LC_FRONTEND_PORT=3190\\n'
    'VIVENTIUM_PLAYGROUND_PORT=3300\\n'
    'VIVENTIUM_CALL_SESSION_SECRET=synthetic-upgrade-secret\\n'
    'CANDIDATE=1\\n',
    encoding='utf-8',
)
(out/'runtime.local.env').write_text('', encoding='utf-8')
(out/'librechat.yaml').write_text('version: 1\\n', encoding='utf-8')
""",
    )
    fixtures.write_executable(
        repo_root / "scripts" / "viventium" / "continuity_audit.py",
        """#!/usr/bin/env python3
import json
import os
import subprocess
import sys
from pathlib import Path

command = sys.argv[1]
output = Path(sys.argv[sys.argv.index('--output') + 1])
output.parent.mkdir(parents=True, exist_ok=True)
if command == 'capture':
    label = sys.argv[sys.argv.index('--label') + 1]
    events = Path(os.environ['TEST_ROOT']) / 'upgrade-events'
    if label == 'successor-bridge-stopped-baseline':
        with events.open('a', encoding='utf-8') as handle:
            handle.write('stopped-baseline-capture\\n')
    elif label == 'successor-bridge-validated-live':
        with events.open('a', encoding='utf-8') as handle:
            handle.write('quiesced-live-capture\\n')
    if label.startswith('post-upgrade-') and os.environ.get('VIVENTIUM_FIRST_UPGRADE_BRIDGE_INTERNAL') != '1':
        repo = Path(sys.argv[sys.argv.index('--repo-root') + 1])
        support = Path(sys.argv[sys.argv.index('--app-support-dir') + 1])
        config = Path(sys.argv[sys.argv.index('--config-file') + 1])
        runtime = Path(sys.argv[sys.argv.index('--runtime-dir') + 1])
        subprocess.run([
            sys.executable,
            str(repo/'scripts'/'viventium'/'first_upgrade_bridge.py'),
            'validate',
            '--repo-root', str(repo),
            '--app-support-dir', str(support),
            '--config-file', str(config),
            '--runtime-dir', str(runtime),
            '--lock-file', str(repo/'components.lock.json'),
        ], check=True)
        with events.open('a', encoding='utf-8') as handle:
            handle.write('outer-post-capture\\n')
        # Force the exact old shell's later restart branch to dispatch again.
        # The durable active bridge receipt must keep that successor launch
        # quiesced even though the old parent process cannot inherit child env.
        (Path(os.environ['TEST_ROOT']) / 'core-running').unlink(missing_ok=True)
    payload = {'schema_version': 2, 'status': 'warning', 'protected': {'synthetic': 'stable'}}
else:
    events = Path(os.environ['TEST_ROOT']) / 'upgrade-events'
    snapshot = Path(sys.argv[sys.argv.index('--snapshot-manifest') + 1])
    with events.open('a', encoding='utf-8') as handle:
        handle.write(
            'bridge-strict-compare\\n'
            if snapshot.name == 'stopped-baseline.json'
            else 'outer-strict-compare\\n'
        )
    payload = {'schema_version': 2, 'status': 'ok', 'protected': {'synthetic': 'stable'}}
output.write_text(json.dumps(payload, sort_keys=True) + '\\n', encoding='utf-8')
""",
    )
    fixtures.write_executable(
        repo_root / "scripts" / "viventium" / "install_macos_helper.sh",
        """#!/usr/bin/env bash
set -euo pipefail
repo=""
support=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-root) repo="$2"; shift 2 ;;
    --app-support-dir) support="$2"; shift 2 ;;
    *) shift ;;
  esac
done
printf 'post-commit-finalize\\n' >>"${TEST_ROOT}/upgrade-events"
component="${support}/runtime-components/telegram-viventium/synthetic/component.py"
python3 "$repo/scripts/viventium/first_upgrade_bridge.py" finalize-after-commit \
  --repo-root "$repo" \
  --app-support-dir "$support" \
  --config-file "$support/config.yaml" \
  --runtime-dir "$support/runtime" \
  --lock-file "$repo/components.lock.json" >/dev/null
python3 "$component" clear-recovery \
  --app-support-dir "$support" >/dev/null
printf 'finalize-complete\\n' >>"${TEST_ROOT}/upgrade-events"
touch "${TEST_ROOT}/helper-finalized"
""",
    )
    policy = json.loads((REPO_ROOT / "release" / "upgrade-support.json").read_text())
    policy["support_floor"]["parent_commit"] = predecessor
    policy["support_floor"]["published_at"] = "2026-07-24T00:00:00Z"
    policy_path = repo_root / "release" / "upgrade-support.json"
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_text(json.dumps(policy, indent=2) + "\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True)
    subprocess.run(
        ["git", "commit", "--quiet", "-m", "successor-owned acceptance bridge"],
        cwd=repo_root,
        check=True,
    )
    successor = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    remote = tmp_path / "release.git"
    subprocess.run(
        ["git", "clone", "--quiet", "--bare", str(repo_root), str(remote)],
        check=True,
    )
    subprocess.run(
        ["git", "checkout", "--quiet", "codex/test-cli"],
        cwd=repo_root,
        check=True,
    )
    assert (
        subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        == predecessor
    )
    subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=repo_root, check=True)
    subprocess.run(
        ["git", "config", "branch.codex/test-cli.remote", "origin"],
        cwd=repo_root,
        check=True,
    )
    subprocess.run(
        ["git", "config", "branch.codex/test-cli.merge", "refs/heads/release-target"],
        cwd=repo_root,
        check=True,
    )
    (tmp_path / "upgrade-events").write_text("", encoding="utf-8")
    if was_running:
        (tmp_path / "stop-called").unlink(missing_ok=True)
        (tmp_path / "core-running").touch()
    else:
        (tmp_path / "stop-called").touch()
        (tmp_path / "core-running").unlink(missing_ok=True)
    config_before = (support / "config.yaml").read_bytes()
    runtime_before = (support / "runtime" / "runtime.env").read_bytes()
    database_before = (
        support / "state" / "runtime" / "isolated" / "database.bin"
    ).read_bytes()
    upgrade_command = [
        str(repo_root / "bin" / "viventium"),
        "--app-support-dir",
        str(support),
        "upgrade",
        "--restart",
    ]
    upgrade_environment = {
        **os.environ,
        "PATH": f"{tmp_path / 'fake-bin'}{os.pathsep}{os.environ.get('PATH', '')}",
        "TEST_ROOT": str(tmp_path),
        "TEST_PYTHON": sys.executable,
        "VIVENTIUM_HELPER_APP_BUNDLE": str(tmp_path / "no-helper.app"),
        "VIVENTIUM_INSTALL_START_HEALTH_TIMEOUT_SECONDS": "3",
        "VIVENTIUM_INSTALL_START_POLL_SECONDS": "0.1",
    }
    if kill_after_quiesced_start:
        interrupted = subprocess.Popen(
            upgrade_command,
            cwd=repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
            env={
                **upgrade_environment,
                "VIVENTIUM_QA_BLOCK_AT_QUIESCED_START": "1",
            },
        )
        try:
            deadline = time.monotonic() + 60
            while not (tmp_path / "sigkill-ready").is_file():
                if interrupted.poll() is not None:
                    stdout, stderr = interrupted.communicate()
                    pytest.fail(
                        "Exact predecessor exited before the SIGKILL boundary "
                        f"(returncode={interrupted.returncode}).\n"
                        f"stdout:\n{stdout}\nstderr:\n{stderr}"
                    )
                if time.monotonic() >= deadline:
                    pytest.fail(
                        "Timed out waiting for exact predecessor to enter "
                        "successor-owned quiesced validation"
                    )
                time.sleep(0.05)
            os.killpg(interrupted.pid, signal.SIGKILL)
            interrupted_stdout, interrupted_stderr = interrupted.communicate(
                timeout=10
            )
        finally:
            if interrupted.poll() is None:
                os.killpg(interrupted.pid, signal.SIGKILL)
                interrupted.wait(timeout=10)
        assert interrupted.returncode == -signal.SIGKILL, (
            interrupted_stdout,
            interrupted_stderr,
        )
        assert (
            support / "state" / "upgrade-transaction-active.json"
        ).is_file()
        upgraded = subprocess.run(
            upgrade_command,
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
            env=upgrade_environment,
        )
    else:
        upgraded = subprocess.run(
            upgrade_command,
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
            env=upgrade_environment,
        )

    if corrupt_successor_helper or kill_after_quiesced_start:
        assert upgraded.returncode != 0
        if corrupt_successor_helper:
            assert "helper binary digest does not match" in upgraded.stderr
        else:
            assert upgraded.returncode == 4
            assert "Interrupted upgrade rolled back successfully" in upgraded.stderr
        assert (
            subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            == predecessor
        )
        assert not (tmp_path / "helper-finalized").exists()
        assert legacy_upload.read_text(encoding="utf-8") == "preserved-user-upload\n"
        assert not (support / "data" / "uploads").exists()
        assert not (support / "state" / "upgrade-transaction-active.json").exists()
        assert (support / "config.yaml").read_bytes() == config_before
        if kill_after_quiesced_start:
            assert (
                support / "runtime" / "runtime.env"
            ).read_bytes() == runtime_before
        assert (
            support / "state" / "runtime" / "isolated" / "database.bin"
        ).read_bytes() == database_before
        if kill_after_quiesced_start and was_running:
            helper_after_recovery = json.loads(
                helper_config.read_text(encoding="utf-8")
            )
            assert helper_after_recovery["showInStatusBar"] is False
            assert helper_after_recovery["allowProtectedRepoRoot"] is True
            assert helper_after_recovery["ownerFutureSetting"] == {
                "mode": "preserve-d59"
            }
            assert (
                helper_after_recovery["runtimeSupervision"]["desiredState"]
                == "running"
            )
        else:
            assert helper_config.read_bytes() == helper_config_before
        telegram_recovery = (
            support / "state" / "continuity" / "telegram-recovery-active.json"
        )
        if kill_after_quiesced_start:
            recovery_payload = json.loads(
                telegram_recovery.read_text(encoding="utf-8")
            )
            assert recovery_payload["transaction_kind"] == "upgrade"
            assert Path(recovery_payload["selection"]["code_root"]).is_relative_to(
                support / "runtime-components" / "telegram-viventium"
            )
        else:
            assert not telegram_recovery.exists()
        assert (
            legacy_upload.read_text(encoding="utf-8")
            == "preserved-user-upload\n"
        )
        assert (
            legacy_telegram_root / "global.json"
        ).read_bytes() == legacy_telegram_value
        failure_events = (
            tmp_path / "upgrade-events"
        ).read_text(encoding="utf-8").splitlines()
        assert "WRITER-START-BEFORE-COMMIT" not in failure_events
        if was_running:
            assert "stop-runtime" in failure_events
            assert failure_events[-1] == "restored-predecessor-start", (
                failure_events,
                upgraded.stdout,
                upgraded.stderr,
            )
            assert (tmp_path / "core-running").is_file()
        else:
            assert "restored-predecessor-start" not in failure_events
            assert not (tmp_path / "core-running").exists()
        return

    assert upgraded.returncode == 0, upgraded.stderr
    assert (
        subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        == successor
    )
    assert (tmp_path / "helper-finalized").is_file()
    bridge_state = json.loads(
        (support / "state" / "continuity" / "first-upgrade-bridge.json").read_text()
    )
    assert bridge_state["status"] == (
        "finalized" if was_running else "pending_first_start"
    )
    assert bridge_state["finalizedAfterOuterCommit"] is was_running
    assert bridge_state["predecessor"] == predecessor
    assert bridge_state["successor"] == successor
    assert bridge_state["wasRunning"] is was_running
    assert bridge_state["helperConfigCheckpointSha256"]
    assert bridge_state["helperConfigContinuity"]["protected_fields_preserved"] is True
    assert bridge_state["telegramContinuity"]["status"] == "migration-finalized"
    assert bridge_state["telegramContinuity"]["helperRecovery"] == "not_installed"
    assert not (
        support / "state" / "continuity" / "telegram-recovery-active.json"
    ).exists()
    recovery_generation = json.loads(
        (
            support
            / "state"
            / "continuity"
            / "telegram-recovery-generation.json"
        ).read_text(encoding="utf-8")
    )
    assert recovery_generation["status"] == "retired"
    assert bridge_state["disabledWriters"] == (
        "agent-seeding,canonical-uploads,channel-workers,glasshive-callbacks,"
        "librechat-mcp-oauth,prompt-workbench,rag-recall,remote-mapping,scheduler,"
        "stale-cortex-recovery,telegram,telegram-codex,voice-workers"
    )
    assert (support / "config.yaml").read_bytes() == config_before
    assert (
        support / "state" / "runtime" / "isolated" / "database.bin"
    ).read_bytes() == database_before
    helper_after = json.loads(helper_config.read_text(encoding="utf-8"))
    assert helper_after["showInStatusBar"] is False
    assert helper_after["allowProtectedRepoRoot"] is True
    assert helper_after["ownerFutureSetting"] == {"mode": "preserve-d59"}
    assert helper_after["runtimeSupervision"]["desiredState"] == (
        "running" if was_running else "stopped"
    )
    canonical_upload = support / "data" / "uploads" / "files" / "preserved.txt"
    assert canonical_upload.read_text(encoding="utf-8") == "preserved-user-upload\n"
    canonical_telegram = (
        support / "state" / "telegram-user-configs" / "global.json"
    )
    assert canonical_telegram.read_bytes() == legacy_telegram_value
    assert (
        legacy_telegram_root / "global.json"
    ).read_bytes() == legacy_telegram_value
    assert (nested / "uploads").is_symlink()
    assert (nested / "uploads").resolve() == support / "data" / "uploads"
    events = (tmp_path / "upgrade-events").read_text(encoding="utf-8").splitlines()
    assert "WRITER-START-BEFORE-COMMIT" not in events
    assert events.count("quiesced-start") == 2
    baseline_index = events.index("stopped-baseline-capture")
    first_quiesced_index = events.index("quiesced-start")
    live_capture_index = events.index("quiesced-live-capture")
    strict_compare_index = events.index("bridge-strict-compare")
    outer_capture_index = events.index("outer-post-capture")
    second_quiesced_index = events.index("quiesced-start", first_quiesced_index + 1)
    finalize_index = events.index("post-commit-finalize")
    final_stop_index = events.index("stop-runtime", finalize_index)
    complete_index = events.index("finalize-complete")
    assert (
        baseline_index
        < first_quiesced_index
        < live_capture_index
        < strict_compare_index
        < outer_capture_index
        < second_quiesced_index
        < finalize_index
        < final_stop_index
        < complete_index
    )
    if was_running:
        assert events.index("stop-runtime") < baseline_index
        full_index = events.index("full-successor-start")
        assert final_stop_index < full_index < complete_index
        assert (tmp_path / "core-running").is_file()
    else:
        assert "full-successor-start" not in events
        assert not (tmp_path / "core-running").exists()
        started = subprocess.run(
            [
                str(repo_root / "bin" / "viventium"),
                "--app-support-dir",
                str(support),
                "start",
                "--restart",
            ],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
            env={
                **os.environ,
                "TEST_ROOT": str(tmp_path),
                "TEST_PYTHON": sys.executable,
                "VIVENTIUM_HELPER_APP_BUNDLE": str(
                    tmp_path / "no-helper.app"
                ),
                "VIVENTIUM_INSTALL_START_HEALTH_TIMEOUT_SECONDS": "3",
                "VIVENTIUM_INSTALL_START_POLL_SECONDS": "0.1",
            },
        )
        assert started.returncode == 0, started.stderr
        postcommit_receipt = json.loads(
            (
                support
                / "state"
                / "continuity"
                / "postcommit-api-finalization.json"
            ).read_text(encoding="utf-8")
        )
        assert postcommit_receipt["status"] == "ready"
        assert postcommit_receipt["runId"] == bridge_state[
            "postCommitFinalizationId"
        ]
        assert postcommit_receipt["sourceId"] == successor
        assert (tmp_path / "core-running").is_file()
        crash_window = subprocess.run(
            [
                sys.executable,
                str(
                    repo_root
                    / "scripts"
                    / "viventium"
                    / "first_upgrade_bridge.py"
                ),
                "pending-postcommit",
                "--repo-root",
                str(repo_root),
                "--app-support-dir",
                str(support),
            ],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert crash_window.returncode == 0, crash_window.stderr
        assert json.loads(crash_window.stdout)["status"] == "pending"
        terminalized = subprocess.run(
            [
                sys.executable,
                str(
                    repo_root
                    / "scripts"
                    / "viventium"
                    / "first_upgrade_bridge.py"
                ),
                "finalize-pending-after-first-start",
                "--repo-root",
                str(repo_root),
                "--app-support-dir",
                str(support),
                "--config-file",
                str(support / "config.yaml"),
                "--runtime-dir",
                str(support / "runtime"),
                "--lock-file",
                str(repo_root / "components.lock.json"),
            ],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
            env={**os.environ, "TEST_ROOT": str(tmp_path)},
        )
        assert terminalized.returncode == 0, terminalized.stderr
        terminal_state = json.loads(
            (
                support
                / "state"
                / "continuity"
                / "first-upgrade-bridge.json"
            ).read_text(encoding="utf-8")
        )
        assert terminal_state["status"] == "finalized"
        assert terminal_state["finalizedAfterOuterCommit"] is True
        assert terminal_state["postCommitApiFinalization"]["status"] == "ready"
        assert terminal_state["librechatEnvContinuity"][
            "protected_fields_preserved"
        ] is True
        assert terminal_state["helperConfigContinuity"][
            "protected_fields_preserved"
        ] is True
