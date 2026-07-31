from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "viventium" / "upgrade_support.py"
POLICY = REPO_ROOT / "release" / "upgrade-support.json"
CLI = REPO_ROOT / "bin" / "viventium"


def load_module():
    spec = importlib.util.spec_from_file_location("upgrade_support", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reviewed_upgrade_policy_is_complete_and_current_checkout_is_supported() -> None:
    module = load_module()
    policy = module.load_policy(POLICY)
    result = module.assess_predecessor(REPO_ROOT, policy)

    assert result["supported"] is True
    assert result["status"] == "supported"
    assert policy["support_floor"]["parent_commit"] == (
        "d59c710f45adc37bf86abd491fce603308b1bfa9"
    )
    assert policy["supported_canonical_config_versions"] == [1]
    assert policy["supported_continuity_manifest_versions"] == [2]
    assert set(policy["state_contracts"]) == module.EXPECTED_STATE_CONTRACTS
    assert (
        policy["predecessor_state_requirements"]["mongo_engine_identity"]
        == module.MONGO_ENGINE_REQUIREMENT
    )


def test_pre_support_floor_commit_is_explicitly_unsupported() -> None:
    module = load_module()
    policy = module.load_policy(POLICY)
    floor = policy["support_floor"]["parent_commit"]
    predecessor = (
        __import__("subprocess")
        .run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", f"{floor}^"],
            check=True,
            capture_output=True,
            text=True,
        )
        .stdout.strip()
    )
    result = module.assess_predecessor(REPO_ROOT, policy, predecessor)
    assert result["supported"] is False
    assert result["status"] == "predecessor_before_support_floor"


def test_cli_checks_support_floor_before_fetch_or_transaction() -> None:
    source = CLI.read_text(encoding="utf-8")
    upgrade = source.rsplit("  upgrade|update)", 1)[1].split("  configure|wizard)", 1)[0]
    policy_check = upgrade.index("ensure_supported_upgrade_predecessor")
    fetch = upgrade.index("fetch_current_branch_target")
    transaction = upgrade.index("upgrade_transaction_begin")

    assert policy_check < fetch < transaction
    support_function = source.split(
        "ensure_supported_upgrade_predecessor() {", 1
    )[1].split("\n}", 1)[0]
    assert '--app-support-dir "$APP_SUPPORT_DIR"' in support_function
    assert '--runtime-dir "$RUNTIME_DIR"' in support_function


def test_durable_stopped_storage_without_engine_proof_fails_before_upgrade_mutation(
    tmp_path: Path,
) -> None:
    support = tmp_path / "support"
    runtime = support / "runtime"
    data_path = support / "state" / "runtime" / "isolated" / "mongo-data"
    runtime.mkdir(parents=True)
    data_path.mkdir(parents=True)
    (data_path / "WiredTiger").write_bytes(b"legacy-engine-ambiguous")
    (runtime / "runtime.env").write_text(
        "\n".join(
            [
                "VIVENTIUM_RUNTIME_PROFILE=isolated",
                f"VIVENTIUM_LOCAL_MONGO_DATA_PATH={data_path}",
                "VIVENTIUM_LOCAL_MONGO_CONTAINER=unclaimed-test-container",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(REPO_ROOT),
            "--policy",
            str(POLICY),
            "--app-support-dir",
            str(support),
            "--runtime-dir",
            str(runtime),
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 4
    report = json.loads(result.stdout)
    assert report["supported"] is False
    assert report["status"] == "mongo_engine_proof_required"
    assert report["recovery"] == (
        "observed-intermediate-clean-stop-or-supported-snapshot-restore"
    )
    assert not (support / "upgrade-backups").exists()
    assert not (
        support / "state" / "upgrade-transaction-active.json"
    ).exists()
