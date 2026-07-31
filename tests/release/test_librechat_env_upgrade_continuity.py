from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
TRANSACTION = REPO_ROOT / "scripts" / "viventium" / "upgrade_transaction.py"
FIRST_UPGRADE_BRIDGE = (
    REPO_ROOT / "scripts" / "viventium" / "first_upgrade_bridge.py"
)
START_SCRIPT = REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"


def run_transaction(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TRANSACTION), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def git(path: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(path), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def build_fixture(tmp_path: Path, env_contents: bytes | None) -> tuple[Path, Path, Path]:
    repo = tmp_path / "repo"
    librechat = repo / "viventium_v0_4" / "LibreChat"
    librechat.mkdir(parents=True)
    git(repo, "init")
    (repo / ".gitignore").write_text(
        "viventium_v0_4/LibreChat/.env\n",
        encoding="utf-8",
    )
    (repo / "components.lock.json").write_text(
        '{"version":1,"components":[]}\n',
        encoding="utf-8",
    )
    (repo / "product.txt").write_text("synthetic product\n", encoding="utf-8")
    git(repo, "add", ".")
    git(
        repo,
        "-c",
        "user.name=QA",
        "-c",
        "user.email=qa@example.com",
        "commit",
        "-m",
        "synthetic fixture",
    )

    env_file = librechat / ".env"
    if env_contents is not None:
        env_file.write_bytes(env_contents)
        env_file.chmod(0o600)

    support = tmp_path / "support"
    runtime = support / "runtime"
    mongo_data = support / "state" / "runtime" / "isolated" / "mongo-data"
    runtime.mkdir(parents=True)
    mongo_data.mkdir(parents=True)
    (support / "config.yaml").write_text("version: 1\n", encoding="utf-8")
    (runtime / "runtime.env").write_text(
        "VIVENTIUM_RUNTIME_PROFILE=isolated\n"
        f"VIVENTIUM_LOCAL_MONGO_DATA_PATH={support / 'data' / 'empty-mongodb'}\n",
        encoding="utf-8",
    )
    (mongo_data / "WiredTiger").write_bytes(b"synthetic database")
    return repo, support, env_file


def begin_and_snapshot(repo: Path, support: Path) -> Path:
    begun = run_transaction(
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
        "false",
    )
    assert begun.returncode == 0, begun.stderr
    transaction = Path(json.loads(begun.stdout)["transaction_path"])
    snapshot = run_transaction(
        "snapshot-stopped-state",
        "--transaction",
        str(transaction),
    )
    assert snapshot.returncode == 0, snapshot.stderr
    return transaction


def load_transaction_module():
    spec = importlib.util.spec_from_file_location(
        "viventium_upgrade_transaction_librechat_env_test",
        TRANSACTION,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_first_upgrade_bridge_module():
    name = "viventium_first_upgrade_bridge_librechat_env_test"
    spec = importlib.util.spec_from_file_location(name, FIRST_UPGRADE_BRIDGE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def write_ready_postcommit_receipt(
    module,
    support: Path,
    environment: dict[str, str],
) -> None:
    module.write_private_json(
        support / module.POSTCOMMIT_API_FINALIZATION_STATE,
        {
            "schemaVersion": 1,
            "runId": environment["VIVENTIUM_POSTCOMMIT_FINALIZATION_ID"],
            "sourceId": environment["VIVENTIUM_POSTCOMMIT_SOURCE_ID"],
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
        },
        boundary=support,
    )


def test_rollback_restores_exact_ignored_librechat_env_and_private_digest(
    tmp_path: Path,
) -> None:
    before = (
        b"# owner customization\n"
        b"JWT_SECRET=synthetic-jwt-before\n"
        b"JWT_REFRESH_SECRET=synthetic-refresh-before\n"
        b"CREDS_KEY=" + b"a" * 64 + b"\n"
        b"CREDS_IV=" + b"b" * 32 + b"\n"
        b"OWNER_ONLY_SETTING='preserve exactly'\n"
        b"PORT=3080\n"
    )
    repo, support, env_file = build_fixture(tmp_path, before)
    transaction = begin_and_snapshot(repo, support)

    ledger = json.loads((transaction / "ledger.json").read_text(encoding="utf-8"))
    protected = next(
        surface
        for surface in ledger["surfaces"]
        if surface["label"] == "librechat-runtime-env"
    )
    semantic = protected["semantic_manifest"]
    serialized = json.dumps(semantic, sort_keys=True)
    assert semantic["exists"] is True
    assert semantic["file_sha256"]
    assert set(semantic["protected_fields"]) == {
        "CREDS_IV",
        "CREDS_KEY",
        "JWT_REFRESH_SECRET",
        "JWT_SECRET",
    }
    assert "synthetic-jwt-before" not in serialized
    assert "preserve exactly" not in serialized
    assert str(env_file) not in serialized

    env_file.write_text("CREDS_KEY=candidate-drift\n", encoding="utf-8")
    rolled_back = run_transaction(
        "rollback",
        "--transaction",
        str(transaction),
    )

    assert rolled_back.returncode == 0, rolled_back.stderr
    assert env_file.read_bytes() == before
    assert env_file.stat().st_mode & 0o777 == 0o600


def test_rollback_restores_ignored_librechat_env_absence(tmp_path: Path) -> None:
    repo, support, env_file = build_fixture(tmp_path, None)
    transaction = begin_and_snapshot(repo, support)

    env_file.write_text("CREDS_KEY=created-by-candidate\n", encoding="utf-8")
    rolled_back = run_transaction(
        "rollback",
        "--transaction",
        str(transaction),
    )

    assert rolled_back.returncode == 0, rolled_back.stderr
    assert not env_file.exists()
    ledger = json.loads((transaction / "ledger.json").read_text(encoding="utf-8"))
    protected = next(
        surface
        for surface in ledger["surfaces"]
        if surface["label"] == "librechat-runtime-env"
    )
    assert protected["semantic_manifest"]["exists"] is False


def test_begin_refuses_symlinked_ignored_librechat_env_before_registration(
    tmp_path: Path,
) -> None:
    repo, support, env_file = build_fixture(tmp_path, None)
    external = tmp_path / "external.env"
    external.write_text("PRIVATE=outside\n", encoding="utf-8")
    env_file.symlink_to(external)

    begun = run_transaction(
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
        "false",
    )

    assert begun.returncode != 0
    assert "symlink" in begun.stderr.lower()
    assert external.read_text(encoding="utf-8") == "PRIVATE=outside\n"
    assert not (support / "state" / "upgrade-transaction-active.json").exists()


def test_librechat_env_checkpoint_rejects_ownership_ambiguity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, _, _ = build_fixture(tmp_path, b"OWNER_ONLY_SETTING=keep-me\n")
    module = load_transaction_module()
    real_uid = os.getuid()
    monkeypatch.setattr(module.os, "getuid", lambda: real_uid + 1)

    with pytest.raises(module.UpgradeTransactionError, match="owned"):
        module.librechat_runtime_env_path(repo)


def test_commit_rejects_protected_or_unknown_librechat_env_drift(
    tmp_path: Path,
) -> None:
    before = (
        "JWT_SECRET=synthetic-jwt-before\n"
        f"CREDS_KEY={'a' * 64}\n"
        "OWNER_ONLY_SETTING=keep-me\n"
        "PORT=3080\n"
    ).encode()
    repo, support, env_file = build_fixture(tmp_path, before)
    transaction = begin_and_snapshot(repo, support)
    env_file.write_text(
        "JWT_SECRET=synthetic-jwt-after\n"
        f"CREDS_KEY={'a' * 64}\n"
        "OWNER_ONLY_SETTING=changed\n"
        "PORT=3180\n",
        encoding="utf-8",
    )

    committed = run_transaction(
        "commit",
        "--transaction",
        str(transaction),
    )

    assert committed.returncode != 0
    assert "LibreChat environment continuity" in committed.stderr
    assert (support / "state" / "upgrade-transaction-active.json").exists()


def test_commit_allows_managed_librechat_env_fields_to_advance(tmp_path: Path) -> None:
    before = (
        "JWT_SECRET=synthetic-jwt-before\n"
        f"CREDS_KEY={'a' * 64}\n"
        "OWNER_ONLY_SETTING=keep-me\n"
        "PORT=3080\n"
        "MONGO_URI=mongodb://127.0.0.1:27017/old\n"
    ).encode()
    repo, support, env_file = build_fixture(tmp_path, before)
    transaction = begin_and_snapshot(repo, support)
    env_file.write_text(
        "JWT_SECRET=synthetic-jwt-before\n"
        f"CREDS_KEY={'a' * 64}\n"
        "OWNER_ONLY_SETTING=keep-me\n"
        "PORT=3180\n"
        "MONGO_URI=mongodb://127.0.0.1:27117/new\n",
        encoding="utf-8",
    )

    committed = run_transaction(
        "commit",
        "--transaction",
        str(transaction),
    )

    assert committed.returncode == 0, committed.stderr
    ledger = json.loads((transaction / "ledger.json").read_text(encoding="utf-8"))
    proof = ledger["librechat_env_continuity"]
    assert proof["verified"] is True
    assert proof["before_file_sha256"] != proof["after_file_sha256"]
    assert proof["protected_fields_preserved"] is True
    assert proof["unmanaged_fields_preserved"] is True
    assert "synthetic-jwt-before" not in json.dumps(proof, sort_keys=True)
    assert str(env_file) not in json.dumps(proof, sort_keys=True)


@pytest.mark.parametrize(
    "credential",
    [
        "GROQ_API_KEY",
        "XAI_API_KEY",
        "GOOGLE_API_KEY",
        "GOOGLE_OAUTH_CLIENT_SECRET",
        "MS365_MCP_CLIENT_SECRET",
        "AZURE_AI_FOUNDRY_API_KEY",
        "FIRECRAWL_API_KEY",
    ],
)
@pytest.mark.parametrize("candidate_value", ["", "rotated-owner-secret"])
def test_commit_rejects_owner_credential_removal_or_rotation(
    tmp_path: Path,
    credential: str,
    candidate_value: str,
) -> None:
    before = f"{credential}=synthetic-owner-secret\nPORT=3080\n".encode()
    repo, support, env_file = build_fixture(tmp_path, before)
    transaction = begin_and_snapshot(repo, support)
    env_file.write_text(
        (f"{credential}={candidate_value}\n" if candidate_value else "") + "PORT=3180\n",
        encoding="utf-8",
    )

    committed = run_transaction("commit", "--transaction", str(transaction))

    assert committed.returncode != 0
    assert "owner credential changed" in committed.stderr


def test_dotenv_manifest_parses_whitespace_export_multiline_and_duplicates(
    tmp_path: Path,
) -> None:
    module = load_transaction_module()
    env_file = tmp_path / ".env"
    env_file.write_text(
        " export GROQ_API_KEY = 'synthetic secret' # owner\n"
        'OWNER_NOTE = "first line\n'
        'second line"\n'
        "GROQ_API_KEY=synthetic-second\n"
        "PORT = 3080\n",
        encoding="utf-8",
    )

    manifest = module.librechat_env_semantic_manifest(env_file)

    assert manifest["owner_secret_fields"]["GROQ_API_KEY"]["present"] is True
    assert manifest["owner_secret_fields"]["GROQ_API_KEY"]["occurrences"] == 2
    assert manifest["unmanaged_fields"]["OWNER_NOTE"]["present"] is True
    assert manifest["managed_fields"]["PORT"]["present"] is True
    assert "synthetic secret" not in json.dumps(manifest)


def test_dotenv_manifest_fails_closed_on_unparsed_or_unterminated_lines(
    tmp_path: Path,
) -> None:
    module = load_transaction_module()
    env_file = tmp_path / ".env"
    env_file.write_text("GROQ_API_KEY='unterminated\n", encoding="utf-8")
    with pytest.raises(module.UpgradeTransactionError, match="unterminated"):
        module.librechat_env_semantic_manifest(env_file)

    env_file.write_text("this is not dotenv\n", encoding="utf-8")
    with pytest.raises(module.UpgradeTransactionError, match="unparsed"):
        module.librechat_env_semantic_manifest(env_file)


def test_rollback_restores_exact_helper_preferences_and_runtime_intent(
    tmp_path: Path,
) -> None:
    repo, support, _ = build_fixture(tmp_path, None)
    helper_config = support / "helper-config.json"
    before = (
        b'{\n'
        b'  "showInStatusBar": false,\n'
        b'  "allowProtectedRepoRoot": true,\n'
        b'  "ownerFutureSetting": {"mode": "private"},\n'
        b'  "runtimeSupervision": {"schemaVersion": 1, "desiredState": "running"}\n'
        b'}\n'
    )
    helper_config.write_bytes(before)
    helper_config.chmod(0o600)
    transaction = begin_and_snapshot(repo, support)

    helper_config.write_text(
        '{"runtimeSupervision":{"desiredState":"stopped"}}\n',
        encoding="utf-8",
    )
    rolled_back = run_transaction(
        "rollback",
        "--transaction",
        str(transaction),
    )

    assert rolled_back.returncode == 0, rolled_back.stderr
    assert helper_config.read_bytes() == before
    assert helper_config.stat().st_mode & 0o777 == 0o600


def test_commit_allows_only_helper_runtime_supervision_to_advance(
    tmp_path: Path,
) -> None:
    repo, support, _ = build_fixture(tmp_path, None)
    helper_config = support / "helper-config.json"
    helper_config.write_text(
        json.dumps(
            {
                "repoRoot": "/synthetic/repo",
                "appSupportDir": "/synthetic/support",
                "showInStatusBar": False,
                "allowProtectedRepoRoot": True,
                "ownerFutureSetting": {"mode": "private"},
                "runtimeSupervision": {
                    "schemaVersion": 1,
                    "desiredState": "running",
                    "consecutiveLaunchAttempts": 3,
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    transaction = begin_and_snapshot(repo, support)
    payload = json.loads(helper_config.read_text(encoding="utf-8"))
    payload["runtimeSupervision"] = {
        "schemaVersion": 1,
        "desiredState": "stopped",
        "consecutiveLaunchAttempts": 0,
        "nextLaunchAttemptAt": None,
        "healthySince": None,
    }
    helper_config.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    committed = run_transaction(
        "commit",
        "--transaction",
        str(transaction),
    )

    assert committed.returncode == 0, committed.stderr
    ledger = json.loads((transaction / "ledger.json").read_text(encoding="utf-8"))
    proof = ledger["helper_config_continuity"]
    assert proof["verified"] is True
    assert proof["protected_fields_preserved"] is True
    assert proof["managed_fields_allowed_to_advance"] == ["runtimeSupervision"]
    serialized = json.dumps(proof, sort_keys=True)
    assert "private" not in serialized
    assert str(helper_config) not in serialized


def test_commit_rejects_helper_preferences_or_unknown_field_drift(
    tmp_path: Path,
) -> None:
    repo, support, _ = build_fixture(tmp_path, None)
    helper_config = support / "helper-config.json"
    helper_config.write_text(
        json.dumps(
            {
                "showInStatusBar": False,
                "allowProtectedRepoRoot": True,
                "ownerFutureSetting": {"mode": "private"},
                "runtimeSupervision": {"desiredState": "running"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    transaction = begin_and_snapshot(repo, support)
    payload = json.loads(helper_config.read_text(encoding="utf-8"))
    payload["showInStatusBar"] = True
    payload["ownerFutureSetting"] = {"mode": "drifted"}
    payload["runtimeSupervision"] = {"desiredState": "stopped"}
    helper_config.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    committed = run_transaction(
        "commit",
        "--transaction",
        str(transaction),
    )

    assert committed.returncode != 0
    assert "helper configuration continuity" in committed.stderr.lower()
    assert (support / "state" / "upgrade-transaction-active.json").exists()


def test_first_upgrade_bridge_recovers_exact_env_after_full_start_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = (
        b"JWT_SECRET=synthetic-first-hop-secret\n"
        b"OWNER_ONLY_SETTING=preserve-first-hop\n"
        b"PORT=3080\n"
    )
    repo, support, env_file = build_fixture(tmp_path, before)
    module = load_first_upgrade_bridge_module()
    transaction = support / "upgrade-backups" / "synthetic-first-hop"
    transaction.mkdir(parents=True, mode=0o700)
    context = module.UpgradeContext(
        repo_root=repo,
        app_support_dir=support,
        transaction=transaction,
        ledger={},
        predecessor="a" * 40,
        successor="b" * 40,
        was_running=True,
    )
    checkpoint = module._checkpoint_librechat_env(context)
    checkpoint_sha256 = module.sha256_file(checkpoint["manifestPath"])
    helper_checkpoint = module._checkpoint_helper_config(context)
    manifest_text = checkpoint["manifestPath"].read_text(encoding="utf-8")
    assert "synthetic-first-hop-secret" not in manifest_text
    assert "preserve-first-hop" not in manifest_text
    assert str(env_file) not in manifest_text

    state_path = support / module.QUIESCED_SESSION_STATE
    module.write_private_json(
        state_path,
        {
            "schemaVersion": module.BRIDGE_SCHEMA_VERSION,
            "receiptKind": "current-upgrade-session",
            "status": "validated",
            "transaction": str(transaction),
            "predecessor": "a" * 40,
            "successor": "b" * 40,
            "wasRunning": True,
            "uploadsDeferredUntilOuterCommit": False,
            "librechatEnvCheckpointSha256": checkpoint_sha256,
            "helperConfigCheckpointSha256": module.sha256_file(
                helper_checkpoint["manifestPath"]
            ),
            "disabledWriters": module.SUCCESSOR_VALIDATION_DISABLED_WRITERS,
            "finalizedAfterOuterCommit": False,
        },
        boundary=support,
    )
    monkeypatch.setattr(
        module.upgrade_transaction,
        "load_ledger",
        lambda _transaction: {
            "status": "committed",
            "repo_root": str(repo),
            "app_support_dir": str(support),
        },
    )
    lifecycle: list[str] = []

    def run_checked(command, *, environment, timeout):
        lifecycle.append(command[-1])
        if command[-1] == "start-full-and-wait":
            write_ready_postcommit_receipt(module, support, environment)
            env_file.write_text(
                "JWT_SECRET=drifted-by-full-start\n"
                "OWNER_ONLY_SETTING=lost\n"
                "PORT=3180\n",
                encoding="utf-8",
            )

    monkeypatch.setattr(module, "_run_checked", run_checked)

    with pytest.raises(
        module.FirstUpgradeBridgeError,
        match="changed protected LibreChat environment state",
    ):
        module.finalize_after_outer_commit(
            repo_root=repo,
            app_support_dir=support,
            config_file=support / "config.yaml",
            runtime_dir=support / "runtime",
            lock_file=repo / "components.lock.json",
            state_relative=module.QUIESCED_SESSION_STATE,
        )

    assert lifecycle == [
        "restore-stopped",
        "start-full-and-wait",
        "restore-stopped",
    ]
    assert env_file.read_bytes() == before
    recovered = json.loads(state_path.read_text(encoding="utf-8"))
    assert recovered["status"] == "librechat_env_recovered"
    assert recovered["librechatEnvRecoveredFromCheckpoint"] is True
    assert recovered["finalizedAfterOuterCommit"] is False


def test_first_upgrade_bridge_recovers_exact_helper_config_after_full_start_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, support, _ = build_fixture(tmp_path, None)
    helper_config = support / "helper-config.json"
    before = (
        b'{\n'
        b'  "showInStatusBar": false,\n'
        b'  "allowProtectedRepoRoot": true,\n'
        b'  "ownerFutureSetting": {"mode": "preserve"},\n'
        b'  "runtimeSupervision": {"desiredState": "running"}\n'
        b'}\n'
    )
    helper_config.write_bytes(before)
    helper_config.chmod(0o600)
    module = load_first_upgrade_bridge_module()
    transaction = support / "upgrade-backups" / "synthetic-helper-first-hop"
    transaction.mkdir(parents=True, mode=0o700)
    context = module.UpgradeContext(
        repo_root=repo,
        app_support_dir=support,
        transaction=transaction,
        ledger={},
        predecessor="a" * 40,
        successor="b" * 40,
        was_running=True,
    )
    env_checkpoint = module._checkpoint_librechat_env(context)
    helper_checkpoint = module._checkpoint_helper_config(context)
    helper_manifest_sha256 = module.sha256_file(helper_checkpoint["manifestPath"])
    helper_manifest_text = helper_checkpoint["manifestPath"].read_text(
        encoding="utf-8"
    )
    assert "preserve" not in helper_manifest_text
    assert str(helper_config) not in helper_manifest_text

    state_path = support / module.QUIESCED_SESSION_STATE
    module.write_private_json(
        state_path,
        {
            "schemaVersion": module.BRIDGE_SCHEMA_VERSION,
            "receiptKind": "current-upgrade-session",
            "status": "validated",
            "transaction": str(transaction),
            "predecessor": "a" * 40,
            "successor": "b" * 40,
            "wasRunning": True,
            "uploadsDeferredUntilOuterCommit": False,
            "librechatEnvCheckpointSha256": module.sha256_file(
                env_checkpoint["manifestPath"]
            ),
            "helperConfigCheckpointSha256": helper_manifest_sha256,
            "disabledWriters": module.SUCCESSOR_VALIDATION_DISABLED_WRITERS,
            "finalizedAfterOuterCommit": False,
        },
        boundary=support,
    )
    monkeypatch.setattr(
        module.upgrade_transaction,
        "load_ledger",
        lambda _transaction: {
            "status": "committed",
            "repo_root": str(repo),
            "app_support_dir": str(support),
        },
    )
    lifecycle: list[str] = []

    def run_checked(command, *, environment, timeout):
        lifecycle.append(command[-1])
        if command[-1] == "start-full-and-wait":
            write_ready_postcommit_receipt(module, support, environment)
            helper_config.write_text(
                '{"showInStatusBar":true,"ownerFutureSetting":{"mode":"lost"},'
                '"runtimeSupervision":{"desiredState":"stopped"}}\n',
                encoding="utf-8",
            )

    monkeypatch.setattr(module, "_run_checked", run_checked)

    with pytest.raises(
        module.FirstUpgradeBridgeError,
        match="changed protected helper configuration",
    ):
        module.finalize_after_outer_commit(
            repo_root=repo,
            app_support_dir=support,
            config_file=support / "config.yaml",
            runtime_dir=support / "runtime",
            lock_file=repo / "components.lock.json",
            state_relative=module.QUIESCED_SESSION_STATE,
        )

    assert lifecycle == [
        "restore-stopped",
        "start-full-and-wait",
        "restore-stopped",
    ]
    assert helper_config.read_bytes() == before
    recovered = json.loads(state_path.read_text(encoding="utf-8"))
    assert recovered["status"] == "helper_config_recovered"
    assert recovered["helperConfigRecoveredFromCheckpoint"] is True
    assert recovered["finalizedAfterOuterCommit"] is False


def test_rollback_restores_telegram_preferences_and_pairings_exactly(
    tmp_path: Path,
) -> None:
    repo, support, _ = build_fixture(tmp_path, None)
    user_configs = support / "state" / "telegram-user-configs"
    pairings = support / "state" / "telegram-codex" / "paired-users"
    user_configs.mkdir(parents=True)
    pairings.mkdir(parents=True)
    (user_configs / "synthetic-user.json").write_text(
        '{"responseMode":"concise"}\n',
        encoding="utf-8",
    )
    (pairings / "synthetic-pairing.json").write_text(
        '{"paired":true}\n',
        encoding="utf-8",
    )
    transaction = begin_and_snapshot(repo, support)

    (user_configs / "synthetic-user.json").write_text(
        '{"responseMode":"drifted"}\n',
        encoding="utf-8",
    )
    (pairings / "synthetic-pairing.json").unlink()
    rolled_back = run_transaction(
        "rollback",
        "--transaction",
        str(transaction),
    )

    assert rolled_back.returncode == 0, rolled_back.stderr
    assert (user_configs / "synthetic-user.json").read_text(encoding="utf-8") == (
        '{"responseMode":"concise"}\n'
    )
    assert (pairings / "synthetic-pairing.json").read_text(encoding="utf-8") == (
        '{"paired":true}\n'
    )


def test_commit_rejects_precommit_telegram_personalization_drift(
    tmp_path: Path,
) -> None:
    repo, support, _ = build_fixture(tmp_path, None)
    user_configs = support / "state" / "telegram-user-configs"
    pairings = support / "state" / "telegram-codex" / "paired-users"
    user_configs.mkdir(parents=True)
    pairings.mkdir(parents=True)
    (user_configs / "synthetic-user.json").write_text(
        '{"responseMode":"concise"}\n',
        encoding="utf-8",
    )
    (pairings / "synthetic-pairing.json").write_text(
        '{"paired":true}\n',
        encoding="utf-8",
    )
    transaction = begin_and_snapshot(repo, support)
    (user_configs / "synthetic-user.json").write_text(
        '{"responseMode":"changed-before-commit"}\n',
        encoding="utf-8",
    )

    committed = run_transaction(
        "commit",
        "--transaction",
        str(transaction),
    )

    assert committed.returncode != 0
    assert "protected local personalization changed" in committed.stderr
    assert (support / "state" / "upgrade-transaction-active.json").exists()


def extract_shell_function(text: str, name: str) -> str:
    lines = text.splitlines()
    start = next(
        (index for index, line in enumerate(lines) if line.strip() == f"{name}() {{"),
        None,
    )
    if start is None:
        raise AssertionError(f"Missing shell function: {name}")
    collected: list[str] = []
    depth = 0
    for line in lines[start:]:
        collected.append(line)
        depth += line.count("{")
        depth -= line.count("}")
        if depth == 0:
            break
    return "\n".join(collected) + "\n"


def test_quiesced_validation_prepares_secrets_without_writing_librechat_env() -> None:
    script = START_SCRIPT.read_text(encoding="utf-8")
    function = extract_shell_function(
        script,
        "prepare_librechat_env_for_quiesced_validation",
    )

    assert "upsert_env_kv" not in function
    assert "remove_env_kv" not in function
    assert "LIBRECHAT_RUNTIME_ENV_FILE" in function
    assert script.count(
        "prepare_librechat_env_for_quiesced_validation || {"
    ) == 2


def test_librechat_env_mutators_preserve_inode_for_semantic_noops(
    tmp_path: Path,
) -> None:
    script = START_SCRIPT.read_text(encoding="utf-8")
    definitions = "".join(
        extract_shell_function(script, name)
        for name in ("upsert_env_kv", "remove_env_kv")
    )
    env_file = tmp_path / ".env"
    env_file.write_text(
        "EXISTING=value\nOWNER_ONLY=preserve\n",
        encoding="utf-8",
    )
    original_inode = env_file.stat().st_ino

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                f"{definitions}"
                f"upsert_env_kv '{env_file}' EXISTING value\n"
                f"remove_env_kv '{env_file}' ABSENT\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert env_file.stat().st_ino == original_inode
    assert env_file.read_text(encoding="utf-8") == (
        "EXISTING=value\nOWNER_ONLY=preserve\n"
    )


def test_full_reconciliation_preserves_existing_auth_secrets_and_unknown_fields(
    tmp_path: Path,
) -> None:
    script = START_SCRIPT.read_text(encoding="utf-8")
    function_names = (
        "first_existing_path",
        "is_librechat_default_secret",
        "read_env_kv",
        "env_file_has_assignment",
        "resolve_persisted_owner_credential",
        "load_google_oauth_from_librechat_env",
        "load_ms365_credentials_from_librechat_env",
        "upsert_env_kv",
        "remove_env_kv",
        "ensure_librechat_env",
    )
    definitions = "".join(
        extract_shell_function(script, name) for name in function_names
    )
    env_file = tmp_path / ".env"
    private_env = tmp_path / "private" / "configs" / "librechat" / "librechat.env"
    private_env.parent.mkdir(parents=True)
    private_env.write_text(
        "GROQ_API_KEY=stale-private-groq\n"
        "XAI_API_KEY=stale-private-xai\n"
        "SERPER_API_KEY=stale-private-serper\n"
        "GOOGLE_OAUTH_CLIENT_ID=stale-private-google-id\n"
        "GOOGLE_OAUTH_CLIENT_SECRET=stale-private-google-secret\n"
        "MS365_MCP_CLIENT_ID=stale-private-ms-id\n"
        "MS365_MCP_TENANT_ID=stale-private-ms-tenant\n"
        "MS365_MCP_CLIENT_SECRET=stale-private-ms-secret\n"
        "MS365_BUSINESS_EMAIL=stale-private@example.invalid\n"
        "CODE_API_KEY=stale-private-code\n",
        encoding="utf-8",
    )
    promotion_env = tmp_path / "promotion-owner.env"
    promotion_env.write_text(
        "GROQ_API_KEY=stale-promotion-groq\n"
        "XAI_API_KEY=stale-promotion-xai\n"
        "SERPER_API_KEY=stale-promotion-serper\n"
        "GOOGLE_OAUTH_CLIENT_ID=stale-promotion-google-id\n"
        "GOOGLE_OAUTH_CLIENT_SECRET=stale-promotion-google-secret\n"
        "MS365_MCP_CLIENT_ID=stale-promotion-ms-id\n"
        "MS365_MCP_TENANT_ID=stale-promotion-ms-tenant\n"
        "MS365_MCP_CLIENT_SECRET=stale-promotion-ms-secret\n"
        "MS365_BUSINESS_EMAIL=stale-promotion@example.invalid\n"
        "CODE_API_KEY=stale-promotion-code\n",
        encoding="utf-8",
    )
    env_file.write_text(
        "JWT_SECRET=existing-jwt\n"
        "JWT_REFRESH_SECRET=existing-refresh\n"
        f"CREDS_KEY={'1' * 64}\n"
        f"CREDS_IV={'2' * 32}\n"
        "MEILI_MASTER_KEY=existing-meili\n"
        "GOOGLE_API_KEY=existing-google\n"
        "LIBRECHAT_CODE_API_KEY=existing-librechat-code\n"
        "CODE_API_KEY=existing-code\n"
        "FIRECRAWL_API_KEY=existing-firecrawl\n"
        "GROQ_API_KEY=existing-groq\n"
        "XAI_API_KEY=existing-xai\n"
        "SERPER_API_KEY=\n"
        "GOOGLE_OAUTH_CLIENT_ID=existing-google-id\n"
        "GOOGLE_OAUTH_CLIENT_SECRET=existing-google-secret\n"
        "MS365_MCP_CLIENT_ID=existing-ms-id\n"
        "MS365_MCP_TENANT_ID=existing-ms-tenant\n"
        "MS365_MCP_CLIENT_SECRET=existing-ms-secret\n"
        "MS365_BUSINESS_EMAIL=existing-ms@example.invalid\n"
        "OWNER_ONLY_SETTING='preserve exactly'\n"
        "PORT=3080\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                f"LIBRECHAT_RUNTIME_ENV_FILE='{env_file}'\n"
                "VIVENTIUM_LOCAL_MONGO_PORT='27117'\n"
                "VIVENTIUM_LOCAL_MONGO_DB='LibreChatViventium'\n"
                "VIVENTIUM_RAG_API_PORT='8110'\n"
                "VIVENTIUM_LOCAL_MEILI_PORT='7700'\n"
                "LC_API_PORT='3180'\n"
                "LC_FRONTEND_URL='http://localhost:3190'\n"
                "LC_API_URL='http://localhost:3180/api'\n"
                "CODE_INTERPRETER_PORT='3210'\n"
                "SEARXNG_PORT='8080'\n"
                "FIRECRAWL_PORT='3002'\n"
                "SKYVERN_BASE_URL='http://localhost:8001'\n"
                "SKYVERN_APP_URL='http://localhost:8002'\n"
                "DEFAULT_VIVENTIUM_OPENAI_MODELS='gpt-5.4'\n"
                "DEFAULT_VIVENTIUM_ASSISTANTS_MODELS='gpt-5.4'\n"
                f"VIVENTIUM_PRIVATE_CURATED_DIR='{private_env.parents[2]}'\n"
                "VIVENTIUM_PRIVATE_MIRROR_DIR=''\n"
                f"LIBRECHAT_CANONICAL_ENV_FILE='{promotion_env}'\n"
                "START_RAG_API='false'\n"
                "SKIP_LIBRECHAT='false'\n"
                "VIVENTIUM_GOOGLE_PROVIDER_ENABLED='false'\n"
                "JWT_SECRET='ambient-jwt-must-not-win'\n"
                "JWT_REFRESH_SECRET='ambient-refresh-must-not-win'\n"
                f"CREDS_KEY='{'3' * 64}'\n"
                f"CREDS_IV='{'4' * 32}'\n"
                "MEILI_MASTER_KEY='ambient-meili-must-not-win'\n"
                "GOOGLE_API_KEY='ambient-google-must-not-win'\n"
                "LIBRECHAT_CODE_API_KEY='ambient-librechat-code-must-not-win'\n"
                "CODE_API_KEY='ambient-code-must-not-win'\n"
                "FIRECRAWL_API_KEY='ambient-firecrawl-must-not-win'\n"
                "resolve_local_meili_master_key() { printf 'synthetic-meili'; }\n"
                "merge_allowed_hosts_csv() { printf ''; }\n"
                "port_in_use() { return 1; }\n"
                "generate_hex_secret() { printf 'generated-must-not-win'; }\n"
                "log_warn() { :; }\n"
                "log_info() { :; }\n"
                f"{definitions}"
                "ensure_librechat_env\n"
                "ensure_librechat_env\n"
                "load_google_oauth_from_librechat_env\n"
                "load_ms365_credentials_from_librechat_env\n"
                "printf '%s|%s|%s|%s|%s|%s|%s|%s|%s|%s\\n' "
                "\"$GROQ_API_KEY\" \"$XAI_API_KEY\" "
                "\"$LIBRECHAT_CODE_API_KEY\" \"$CODE_API_KEY\" "
                "\"$GOOGLE_OAUTH_CLIENT_ID\" \"$GOOGLE_OAUTH_CLIENT_SECRET\" "
                "\"$MS365_MCP_CLIENT_ID\" \"$MS365_MCP_TENANT_ID\" "
                "\"$MS365_MCP_CLIENT_SECRET\" \"$MS365_BUSINESS_EMAIL\"\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    contents = env_file.read_text(encoding="utf-8")
    assert "JWT_SECRET=existing-jwt\n" in contents
    assert "JWT_REFRESH_SECRET=existing-refresh\n" in contents
    assert f"CREDS_KEY={'1' * 64}\n" in contents
    assert f"CREDS_IV={'2' * 32}\n" in contents
    assert "MEILI_MASTER_KEY=existing-meili\n" in contents
    assert "GOOGLE_API_KEY=existing-google\n" in contents
    assert "LIBRECHAT_CODE_API_KEY=existing-librechat-code\n" in contents
    assert "CODE_API_KEY=existing-code\n" in contents
    assert "FIRECRAWL_API_KEY=existing-firecrawl\n" in contents
    assert "GROQ_API_KEY=existing-groq\n" in contents
    assert "XAI_API_KEY=existing-xai\n" in contents
    assert "SERPER_API_KEY=\n" in contents
    assert "OWNER_ONLY_SETTING='preserve exactly'\n" in contents
    assert "PORT=3180\n" in contents
    assert "ambient-jwt-must-not-win" not in contents
    assert "ambient-meili-must-not-win" not in contents
    assert "ambient-google-must-not-win" not in contents
    assert "ambient-librechat-code-must-not-win" not in contents
    assert "ambient-code-must-not-win" not in contents
    assert "ambient-firecrawl-must-not-win" not in contents
    assert "stale-private" not in contents
    assert "stale-promotion" not in contents
    assert completed.stdout.strip() == (
        "existing-groq|existing-xai|existing-librechat-code|existing-code|"
        "existing-google-id|existing-google-secret|existing-ms-id|"
        "existing-ms-tenant|existing-ms-secret|existing-ms@example.invalid"
    )


def test_explicit_persisted_empty_google_and_ms365_credentials_do_not_resurrect_stale_values(
    tmp_path: Path,
) -> None:
    script = START_SCRIPT.read_text(encoding="utf-8")
    definitions = "".join(
        extract_shell_function(script, name)
        for name in (
            "read_env_kv",
            "env_file_has_assignment",
            "resolve_persisted_owner_credential",
            "load_google_oauth_from_librechat_env",
            "load_ms365_credentials_from_librechat_env",
        )
    )
    runtime_env = tmp_path / "runtime.env"
    canonical_env = tmp_path / "canonical.env"
    runtime_env.write_text(
        "GOOGLE_OAUTH_CLIENT_ID=runtime-google-id\n"
        "GOOGLE_OAUTH_CLIENT_SECRET=\n"
        "MS365_MCP_CLIENT_ID=\n"
        "MS365_MCP_TENANT_ID=runtime-ms-tenant\n"
        "MS365_MCP_CLIENT_SECRET=\n"
        "MS365_BUSINESS_EMAIL=\n",
        encoding="utf-8",
    )
    canonical_env.write_text(
        "GOOGLE_OAUTH_CLIENT_ID=stale-google-id\n"
        "GOOGLE_OAUTH_CLIENT_SECRET=stale-google-secret\n"
        "MS365_MCP_CLIENT_ID=stale-ms-id\n"
        "MS365_MCP_TENANT_ID=stale-ms-tenant\n"
        "MS365_MCP_CLIENT_SECRET=stale-ms-secret\n"
        "MS365_BUSINESS_EMAIL=stale@example.invalid\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                f"LIBRECHAT_RUNTIME_ENV_FILE='{runtime_env}'\n"
                f"LIBRECHAT_CANONICAL_ENV_FILE='{canonical_env}'\n"
                "GOOGLE_OAUTH_CLIENT_ID='ambient-google-id'\n"
                "GOOGLE_OAUTH_CLIENT_SECRET='ambient-google-secret'\n"
                "MS365_MCP_CLIENT_ID='ambient-ms-id'\n"
                "MS365_MCP_TENANT_ID='ambient-ms-tenant'\n"
                "MS365_MCP_CLIENT_SECRET='ambient-ms-secret'\n"
                "MS365_BUSINESS_EMAIL='ambient@example.invalid'\n"
                "log_warn() { :; }\n"
                f"{definitions}"
                "google_status=0\n"
                "load_google_oauth_from_librechat_env || google_status=$?\n"
                "ms_status=0\n"
                "load_ms365_credentials_from_librechat_env || ms_status=$?\n"
                "printf '%s|%s|%s|%s|%s|%s|%s|%s\\n' "
                "\"$google_status\" \"$GOOGLE_OAUTH_CLIENT_ID\" "
                "\"$GOOGLE_OAUTH_CLIENT_SECRET\" \"$ms_status\" "
                "\"$MS365_MCP_CLIENT_ID\" \"$MS365_MCP_TENANT_ID\" "
                "\"$MS365_MCP_CLIENT_SECRET\" \"$MS365_BUSINESS_EMAIL\"\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == (
        "1|runtime-google-id||1||runtime-ms-tenant||"
    )
    full_loader = extract_shell_function(script, "load_ms365_credentials")
    assert "explicit persisted empty value is an owner deletion" in full_loader
    assert 'env_file_has_assignment \\\n      "$LIBRECHAT_RUNTIME_ENV_FILE"' in (
        full_loader
    )


def test_alignment_canonical_owner_file_does_not_resurrect_deleted_provider_key(
    tmp_path: Path,
) -> None:
    script = START_SCRIPT.read_text(encoding="utf-8")
    definitions = "".join(
        extract_shell_function(script, name)
        for name in (
            "first_existing_path",
            "is_librechat_default_secret",
            "read_env_kv",
            "env_file_has_assignment",
            "resolve_persisted_owner_credential",
            "load_google_oauth_from_librechat_env",
            "load_ms365_credentials_from_librechat_env",
            "upsert_env_kv",
            "remove_env_kv",
            "ensure_librechat_env",
        )
    )
    env_file = tmp_path / ".env"
    env_file.write_text(
        "JWT_SECRET=existing-jwt\n"
        "JWT_REFRESH_SECRET=existing-refresh\n"
        f"CREDS_KEY={'1' * 64}\n"
        f"CREDS_IV={'2' * 32}\n"
        "OWNER_NOTE=provider-key-intentionally-deleted\n",
        encoding="utf-8",
    )
    stale_snapshot = tmp_path / "stale-owner.env"
    stale_snapshot.write_text(
        "GROQ_API_KEY=must-not-resurrect\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                f"LIBRECHAT_RUNTIME_ENV_FILE='{env_file}'\n"
                f"LIBRECHAT_CANONICAL_ENV_FILE='{env_file}'\n"
                f"STALE_OWNER_SNAPSHOT='{stale_snapshot}'\n"
                "VIVENTIUM_PRIVATE_CURATED_DIR=''\n"
                "VIVENTIUM_PRIVATE_MIRROR_DIR=''\n"
                "VIVENTIUM_LOCAL_MONGO_PORT='27117'\n"
                "VIVENTIUM_LOCAL_MONGO_DB='LibreChatViventium'\n"
                "VIVENTIUM_RAG_API_PORT='8110'\n"
                "VIVENTIUM_LOCAL_MEILI_PORT='7700'\n"
                "LC_API_PORT='3180'\n"
                "LC_FRONTEND_URL='http://localhost:3190'\n"
                "LC_API_URL='http://localhost:3180/api'\n"
                "CODE_INTERPRETER_PORT='3210'\n"
                "SEARXNG_PORT='8080'\n"
                "FIRECRAWL_PORT='3002'\n"
                "SKYVERN_BASE_URL='http://localhost:8001'\n"
                "SKYVERN_APP_URL='http://localhost:8002'\n"
                "DEFAULT_VIVENTIUM_OPENAI_MODELS='gpt-5.4'\n"
                "DEFAULT_VIVENTIUM_ASSISTANTS_MODELS='gpt-5.4'\n"
                "START_RAG_API='false'\n"
                "SKIP_LIBRECHAT='false'\n"
                "VIVENTIUM_GOOGLE_PROVIDER_ENABLED='false'\n"
                "resolve_local_meili_master_key() { printf 'synthetic-meili'; }\n"
                "merge_allowed_hosts_csv() { printf ''; }\n"
                "port_in_use() { return 1; }\n"
                "generate_hex_secret() { printf 'generated-must-not-win'; }\n"
                "log_warn() { :; }\n"
                "log_info() { :; }\n"
                f"{definitions}"
                "ensure_librechat_env\n"
                "printf '%s' \"${GROQ_API_KEY-}\"\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == ""
    contents = env_file.read_text(encoding="utf-8")
    assert "OWNER_NOTE=provider-key-intentionally-deleted\n" in contents
    assert "GROQ_API_KEY=" not in contents
    assert "must-not-resurrect" not in contents
