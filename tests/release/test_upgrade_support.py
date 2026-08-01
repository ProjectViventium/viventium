from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "viventium" / "upgrade_support.py"
POLICY = REPO_ROOT / "release" / "upgrade-support.json"
CLI = REPO_ROOT / "bin" / "viventium"
INSTALLER = REPO_ROOT / "install.sh"


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


def test_public_installer_limits_fresh_history_and_repairs_it_before_upgrade() -> None:
    source = INSTALLER.read_text(encoding="utf-8")

    assert 'git clone --depth 1 --single-branch --branch "$BRANCH"' in source
    assert 'git -C "$INSTALL_DIR" rev-parse --is-shallow-repository' in source
    assert 'git -C "$INSTALL_DIR" fetch --unshallow origin "$BRANCH"' in source


def test_mutating_upgrade_repairs_legacy_shallow_history_before_support_gate() -> None:
    source = CLI.read_text(encoding="utf-8")
    upgrade = source.rsplit("  upgrade|update)", 1)[1].split(
        "  configure|wizard)",
        1,
    )[0]

    safety = upgrade.index('UPGRADE_SAFETY_JSON="$(')
    repair = upgrade.index("repair_shallow_upgrade_history")
    support = upgrade.index("ensure_supported_upgrade_predecessor")
    target_fetch = upgrade.index("fetch_current_branch_target")
    transaction = upgrade.index("upgrade_transaction_begin")

    assert safety < repair < support < target_fetch < transaction
    repair_function = source.split(
        "repair_shallow_upgrade_history() {",
        1,
    )[1].split("\n}", 1)[0]
    assert "rev-parse --is-shallow-repository" in repair_function
    assert "fetch --unshallow" in repair_function
    assert "allow_remote" not in repair_function
    assert "repair_shallow_upgrade_history\n" in upgrade


def _make_public_installer_fixture(tmp_path: Path) -> tuple[Path, str]:
    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=source, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Viventium Test"],
        cwd=source,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "viventium-test@example.com"],
        cwd=source,
        check=True,
    )
    (source / "bin").mkdir()
    cli = source / "bin" / "viventium"
    cli.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    cli.chmod(0o755)
    (source / "history.txt").write_text("first\n", encoding="utf-8")
    subprocess.run(["git", "add", "bin/viventium", "history.txt"], cwd=source, check=True)
    subprocess.run(["git", "commit", "-m", "first"], cwd=source, check=True, capture_output=True)
    (source / "history.txt").write_text("first\nsecond\n", encoding="utf-8")
    subprocess.run(["git", "add", "history.txt"], cwd=source, check=True)
    subprocess.run(["git", "commit", "-m", "second"], cwd=source, check=True, capture_output=True)

    origin = tmp_path / "origin.git"
    subprocess.run(["git", "clone", "--bare", str(source), str(origin)], check=True, capture_output=True)
    installer = tmp_path / "install.sh"
    shutil.copy2(INSTALLER, installer)
    installer.chmod(0o755)
    return installer, origin.as_uri()


def _run_public_installer(installer: Path, origin_url: str, install_dir: Path) -> None:
    subprocess.run(
        [str(installer)],
        check=True,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "VIVENTIUM_INSTALL_DISTRIBUTION": "source",
            "VIVENTIUM_INSTALL_DIR": str(install_dir),
            "VIVENTIUM_REPO_URL": origin_url,
            "VIVENTIUM_REPO_BRANCH": "main",
        },
    )


def _repair_shallow_function() -> str:
    source = CLI.read_text(encoding="utf-8")
    body = source.split("repair_shallow_upgrade_history() {", 1)[1].split(
        "\n}",
        1,
    )[0]
    return f"repair_shallow_upgrade_history() {{{body}\n}}"


def _run_shallow_repair(checkout: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                f"REPO_ROOT={str(checkout)!r}\n"
                f"{_repair_shallow_function()}\n"
                "repair_shallow_upgrade_history\n"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def test_public_installer_creates_a_tip_only_checkout_without_historical_metadata(
    tmp_path: Path,
) -> None:
    installer, origin_url = _make_public_installer_fixture(tmp_path)
    install_dir = tmp_path / "installed"

    _run_public_installer(installer, origin_url, install_dir)

    shallow = subprocess.run(
        ["git", "rev-parse", "--is-shallow-repository"],
        cwd=install_dir,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    history_count = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=install_dir,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert shallow == "true"
    assert history_count == "1"


def test_cli_shallow_repair_fetches_required_branch_history(tmp_path: Path) -> None:
    _, origin_url = _make_public_installer_fixture(tmp_path)
    checkout = tmp_path / "legacy-shallow"
    subprocess.run(
        ["git", "clone", "--depth", "1", "--branch", "main", origin_url, str(checkout)],
        check=True,
        capture_output=True,
    )

    repaired = _run_shallow_repair(checkout)

    assert repaired.returncode == 0, repaired.stderr
    assert subprocess.run(
        ["git", "rev-parse", "--is-shallow-repository"],
        cwd=checkout,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip() == "false"
    assert subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=checkout,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip() == "2"


def test_cli_shallow_repair_fails_without_remote_and_preserves_checkout(
    tmp_path: Path,
) -> None:
    _, origin_url = _make_public_installer_fixture(tmp_path)
    checkout = tmp_path / "legacy-shallow"
    subprocess.run(
        ["git", "clone", "--depth", "1", "--branch", "main", origin_url, str(checkout)],
        check=True,
        capture_output=True,
    )
    head_before = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=checkout,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(["git", "remote", "remove", "origin"], cwd=checkout, check=True)

    failed = _run_shallow_repair(checkout)

    assert failed.returncode != 0
    assert "without its configured remote branch" in failed.stderr
    assert subprocess.run(
        ["git", "rev-parse", "--is-shallow-repository"],
        cwd=checkout,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip() == "true"
    assert subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=checkout,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip() == head_before
    assert subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=checkout,
        check=True,
        capture_output=True,
        text=True,
    ).stdout == ""


def test_public_installer_repairs_existing_shallow_checkout(tmp_path: Path) -> None:
    installer, origin_url = _make_public_installer_fixture(tmp_path)
    install_dir = tmp_path / "installed"
    subprocess.run(
        ["git", "clone", "--depth", "1", "--branch", "main", origin_url, str(install_dir)],
        check=True,
        capture_output=True,
    )
    assert (
        subprocess.run(
            ["git", "rev-parse", "--is-shallow-repository"],
            cwd=install_dir,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        == "true"
    )

    _run_public_installer(installer, origin_url, install_dir)

    shallow = subprocess.run(
        ["git", "rev-parse", "--is-shallow-repository"],
        cwd=install_dir,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    history_count = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=install_dir,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert shallow == "false"
    assert history_count == "2"


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
