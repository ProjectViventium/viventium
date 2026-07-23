from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER_PATH = REPO_ROOT / "scripts" / "viventium" / "agent_migration_state.py"
SPEC = importlib.util.spec_from_file_location("agent_migration_state", HELPER_PATH)
assert SPEC and SPEC.loader
MIGRATION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MIGRATION)

PREDECESSOR = "1" * 40
SUCCESSOR = "2" * 40


def make_vendored_source(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "viventium"
    librechat = repo / "viventium_v0_4" / "LibreChat"
    (librechat / "scripts").mkdir(parents=True)
    (librechat / "viventium" / "source_of_truth").mkdir(parents=True)
    (librechat / "scripts" / "viventium-seed-agents.js").write_text(
        "// synthetic seed\n", encoding="utf-8"
    )
    (librechat / "viventium" / "source_of_truth" / "local.viventium-agents.yaml").write_text(
        "version: 1\n", encoding="utf-8"
    )
    registry_content = {
        "schema_version": 1,
        "migrations": [{"predecessor_source_refs": [PREDECESSOR]}],
    }
    registry = {
        **registry_content,
        "artifact_sha256": MIGRATION.sha256_stable(registry_content),
    }
    (librechat / "viventium" / "source_of_truth" / "managed-agent-baseline-migration.json").write_text(
        json.dumps(registry), encoding="utf-8"
    )
    (repo / "components.lock.json").write_text(
        json.dumps(
            {
                "version": 1,
                "components": [
                    {
                        "name": "LibreChat",
                        "path": "viventium_v0_4/LibreChat",
                        "ref": SUCCESSOR,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    support = tmp_path / "app-support"
    support.mkdir(mode=0o700)
    return repo, support


def run_prepare(repo: Path, support: Path, *, transaction: str, successor: str = SUCCESSOR):
    return subprocess.run(
        [
            "python3",
            str(HELPER_PATH),
            "prepare",
            "--repo-root",
            str(repo),
            "--app-support-dir",
            str(support),
            "--predecessor-ref",
            PREDECESSOR,
            "--successor-ref",
            successor,
            "--transaction-id",
            transaction,
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def make_upgrade_evidence(
    repo: Path,
    support: Path,
    *,
    tamper_runner: bool = False,
    transaction_id: str = "upgrade-test-legacy-0001",
    predecessor_ref: str = PREDECESSOR,
    created_at: str = "2026-07-22T12:00:00Z",
) -> Path:
    librechat = repo / "viventium_v0_4" / "LibreChat"
    transaction = support / "upgrade-backups" / transaction_id
    transaction.mkdir(parents=True, mode=0o700)
    runner = transaction / "transaction-runner.py"
    runner.write_text("# immutable synthetic runner\n", encoding="utf-8")
    runner.chmod(0o500)
    runner_hash = MIGRATION.sha256_bytes(runner.read_bytes())
    if tamper_runner:
        runner_hash = "f" * 64
    ledger = {
        "schema_version": 7,
        "transaction_path": str(transaction),
        "transaction_runner": str(runner),
        "transaction_runner_sha256": runner_hash,
        "app_support_dir": str(support),
        "repo_root": str(repo),
        "created_at": created_at,
        "status": "committed",
        "stage": "committed",
        "repositories": [
            {
                "name": "LibreChat",
                "path": str(librechat),
                "old_head": predecessor_ref,
                "observed_heads": [predecessor_ref, SUCCESSOR],
            }
        ],
    }
    ledger_path = transaction / "ledger.json"
    ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
    ledger_path.chmod(0o600)
    return transaction


def run_import_legacy(repo: Path, support: Path, runtime_env: Path, *, ambient: str = ""):
    env = None
    if ambient:
        env = {**os.environ, MIGRATION.LEGACY_PREDECESSOR_KEY: ambient}
    return subprocess.run(
        [
            "python3",
            str(HELPER_PATH),
            "import-legacy",
            "--repo-root",
            str(repo),
            "--app-support-dir",
            str(support),
            "--runtime-env",
            str(runtime_env),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def test_source_identity_uses_exact_component_lock_for_vendored_payload(tmp_path: Path) -> None:
    repo, _ = make_vendored_source(tmp_path)

    source_ref, source_kind, librechat = MIGRATION.resolve_source_ref(repo)

    assert source_ref == SUCCESSOR
    assert source_kind == "vendored_lock"
    assert librechat == repo / "viventium_v0_4" / "LibreChat"


def test_prepare_is_durable_private_and_exact_same_upgrade_retry_is_idempotent(
    tmp_path: Path,
) -> None:
    repo, support = make_vendored_source(tmp_path)

    first = run_prepare(repo, support, transaction="upgrade-test-resume-0001")
    second = run_prepare(repo, support, transaction="upgrade-test-resume-0001")

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    first_report = json.loads(first.stdout)
    second_report = json.loads(second.stdout)
    state_path = support / "state" / "runtime" / "agent-managed-migration-pending.json"
    assert first_report == second_report == json.loads(state_path.read_text(encoding="utf-8")) | {
        "state_path": str(state_path)
    }
    assert stat.S_IMODE(state_path.stat().st_mode) == 0o600


def test_prepare_rejects_stale_successor_and_different_pending_transaction_without_drift(
    tmp_path: Path,
) -> None:
    repo, support = make_vendored_source(tmp_path)
    accepted = run_prepare(repo, support, transaction="upgrade-test-retained-0001")
    assert accepted.returncode == 0, accepted.stderr
    state_path = support / "state" / "runtime" / "agent-managed-migration-pending.json"
    before = state_path.read_bytes()

    stale = run_prepare(
        repo,
        support,
        transaction="upgrade-test-retained-0001",
        successor="3" * 40,
    )
    different = run_prepare(repo, support, transaction="upgrade-test-different-0002")

    assert stale.returncode == 1
    assert "successor identity changed" in stale.stderr
    assert different.returncode == 1
    assert "different managed agent migration is already pending" in different.stderr
    assert state_path.read_bytes() == before


def test_prepare_rejects_tampered_registry_before_creating_state(tmp_path: Path) -> None:
    repo, support = make_vendored_source(tmp_path)
    registry = (
        repo
        / "viventium_v0_4"
        / "LibreChat"
        / "viventium"
        / "source_of_truth"
        / "managed-agent-baseline-migration.json"
    )
    registry.write_text(registry.read_text(encoding="utf-8") + " ", encoding="utf-8")
    value = json.loads(registry.read_text(encoding="utf-8"))
    value["migrations"] = []
    registry.write_text(json.dumps(value), encoding="utf-8")

    rejected = run_prepare(repo, support, transaction="upgrade-test-tamper-0001")

    assert rejected.returncode == 1
    assert "registry hash is invalid" in rejected.stderr
    assert not (support / "state" / "runtime" / "agent-managed-migration-pending.json").exists()


def test_nested_git_source_must_match_component_lock(tmp_path: Path) -> None:
    repo, _ = make_vendored_source(tmp_path)
    librechat = repo / "viventium_v0_4" / "LibreChat"
    subprocess.run(["git", "init", "-q", str(librechat)], check=True)
    subprocess.run(["git", "-C", str(librechat), "config", "user.name", "Synthetic QA"], check=True)
    subprocess.run(
        ["git", "-C", str(librechat), "config", "user.email", "qa@example.invalid"], check=True
    )
    subprocess.run(["git", "-C", str(librechat), "add", "."], check=True)
    subprocess.run(["git", "-C", str(librechat), "commit", "-qm", "synthetic"], check=True)

    with pytest.raises(MIGRATION.MigrationStateError, match="does not match the component lock"):
        MIGRATION.resolve_source_ref(repo)


def test_legacy_runtime_handoff_requires_upgrade_evidence_and_is_consumed_once(
    tmp_path: Path,
) -> None:
    repo, support = make_vendored_source(tmp_path)
    make_upgrade_evidence(repo, support)
    runtime_env = support / "runtime" / "runtime.env"
    runtime_env.parent.mkdir()
    runtime_env.write_text(
        f"SAFE_SETTING=1\n{MIGRATION.LEGACY_PREDECESSOR_KEY}={PREDECESSOR}\n",
        encoding="utf-8",
    )
    runtime_env.chmod(0o600)

    imported = run_import_legacy(repo, support, runtime_env, ambient="e" * 40)
    replay = run_import_legacy(repo, support, runtime_env, ambient="e" * 40)

    assert imported.returncode == 0, imported.stderr
    assert json.loads(imported.stdout)["imported"] is True
    assert runtime_env.read_text(encoding="utf-8") == "SAFE_SETTING=1\n"
    assert replay.returncode == 0, replay.stderr
    assert json.loads(replay.stdout) == {"imported": False}
    state = json.loads(
        (support / "state" / "runtime" / "agent-managed-migration-pending.json").read_text(
            encoding="utf-8"
        )
    )
    assert state["predecessor_source_ref"] == PREDECESSOR
    assert state["successor_source_ref"] == SUCCESSOR
    assert state["transaction_id"] == "upgrade-test-legacy-0001"


def test_first_upgrade_from_shipped_cli_discovers_predecessor_from_verified_ledger_once(
    tmp_path: Path,
) -> None:
    repo, support = make_vendored_source(tmp_path)
    make_upgrade_evidence(repo, support)
    runtime_env = support / "runtime" / "runtime.env"
    runtime_env.parent.mkdir()
    runtime_env.write_text("SAFE_SETTING=1\n", encoding="utf-8")
    runtime_env.chmod(0o600)

    imported = run_import_legacy(repo, support, runtime_env)

    assert imported.returncode == 0, imported.stderr
    report = json.loads(imported.stdout)
    assert report["imported"] is True
    assert report["source"] == "verified_upgrade_ledger"
    state_path = support / "state" / "runtime" / "agent-managed-migration-pending.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["predecessor_source_ref"] == PREDECESSOR
    assert state["successor_source_ref"] == SUCCESSOR
    assert state["transaction_id"] == "upgrade-test-legacy-0001"
    state_path.unlink()

    replay = run_import_legacy(repo, support, runtime_env)

    assert replay.returncode == 0, replay.stderr
    assert json.loads(replay.stdout) == {"imported": False}
    assert not state_path.exists()
    receipt = (
        support
        / "state"
        / "runtime"
        / "agent-managed-migration-imports"
        / "upgrade-test-legacy-0001.json"
    )
    assert receipt.is_file()
    assert stat.S_IMODE(receipt.stat().st_mode) == 0o600


def test_shipped_cli_ledger_discovery_rejects_a_tampered_import_receipt(
    tmp_path: Path,
) -> None:
    repo, support = make_vendored_source(tmp_path)
    make_upgrade_evidence(repo, support)
    runtime_env = support / "runtime" / "runtime.env"
    runtime_env.parent.mkdir()
    runtime_env.write_text("SAFE_SETTING=1\n", encoding="utf-8")
    runtime_env.chmod(0o600)
    imported = run_import_legacy(repo, support, runtime_env)
    assert imported.returncode == 0, imported.stderr
    pending = support / "state" / "runtime" / "agent-managed-migration-pending.json"
    pending.unlink()
    receipt = (
        support
        / "state"
        / "runtime"
        / "agent-managed-migration-imports"
        / "upgrade-test-legacy-0001.json"
    )
    receipt.write_text('{"schema_version":1}\n', encoding="utf-8")
    receipt.chmod(0o600)

    rejected = run_import_legacy(repo, support, runtime_env)

    assert rejected.returncode == 1
    assert "receipt does not match upgrade evidence" in rejected.stderr
    assert not pending.exists()


def test_shipped_cli_discovery_does_not_fall_back_past_a_newer_unsupported_upgrade(
    tmp_path: Path,
) -> None:
    repo, support = make_vendored_source(tmp_path)
    make_upgrade_evidence(repo, support)
    make_upgrade_evidence(
        repo,
        support,
        transaction_id="upgrade-test-legacy-0002",
        predecessor_ref="9" * 40,
        created_at="2026-07-22T13:00:00Z",
    )
    runtime_env = support / "runtime" / "runtime.env"
    runtime_env.parent.mkdir()
    runtime_env.write_text("SAFE_SETTING=1\n", encoding="utf-8")
    runtime_env.chmod(0o600)

    rejected = run_import_legacy(repo, support, runtime_env)

    assert rejected.returncode == 1
    assert "outside the automatic migration floor" in rejected.stderr
    assert not (support / "state" / "runtime" / "agent-managed-migration-pending.json").exists()


def test_legacy_runtime_handoff_rejects_tampered_upgrade_evidence_without_scrubbing(
    tmp_path: Path,
) -> None:
    repo, support = make_vendored_source(tmp_path)
    make_upgrade_evidence(repo, support, tamper_runner=True)
    runtime_env = support / "runtime" / "runtime.env"
    runtime_env.parent.mkdir()
    original = f"{MIGRATION.LEGACY_PREDECESSOR_KEY}={PREDECESSOR}\n"
    runtime_env.write_text(original, encoding="utf-8")
    runtime_env.chmod(0o600)

    rejected = run_import_legacy(repo, support, runtime_env)

    assert rejected.returncode == 1
    assert "does not match a verified upgrade transaction" in rejected.stderr
    assert runtime_env.read_text(encoding="utf-8") == original
    assert not (support / "state" / "runtime" / "agent-managed-migration-pending.json").exists()
