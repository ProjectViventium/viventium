from __future__ import annotations

import json
import importlib.util
import hashlib
import errno
import os
import shutil
import socket
import stat
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL = REPO_ROOT / "scripts" / "viventium" / "dev_runtime_activation.py"
CLI = REPO_ROOT / "bin" / "viventium"


def load_module():
    specification = importlib.util.spec_from_file_location(
        "dev_runtime_activation_under_test",
        TOOL,
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def load_upgrade_module():
    path = REPO_ROOT / "scripts" / "viventium" / "upgrade_transaction.py"
    specification = importlib.util.spec_from_file_location(
        "upgrade_transaction_for_activation_test",
        path,
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def run_tool(*args: object) -> dict[str, object]:
    completed = subprocess.run(
        [sys.executable, str(TOOL), *(str(item) for item in args)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def make_candidate_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "candidate-checkout"
    librechat = repo / "viventium_v0_4" / "LibreChat"
    if (librechat / ".git").exists():
        return repo
    librechat.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(librechat)], check=True)
    subprocess.run(
        ["git", "-C", str(librechat), "config", "user.name", "Synthetic QA"],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(librechat),
            "config",
            "user.email",
            "synthetic@example.invalid",
        ],
        check=True,
    )
    (librechat / "marker").write_text("candidate\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(librechat), "add", "marker"], check=True)
    subprocess.run(
        ["git", "-C", str(librechat), "commit", "-qm", "candidate"],
        check=True,
    )
    return repo


def make_isolated_activation_cli(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "isolated-activation-checkout"
    (repo / "bin").mkdir(parents=True)
    shutil.copy2(CLI, repo / "bin" / "viventium")
    shutil.copytree(
        REPO_ROOT / "scripts" / "viventium",
        repo / "scripts" / "viventium",
    )
    (repo / "scripts" / "viventium" / "requirements-installer.txt").write_text(
        "",
        encoding="utf-8",
    )
    (repo / "scripts" / "viventium" / "upgrade_check.py").write_text(
        "import json\n"
        'print(json.dumps({"ready_to_upgrade": True, "blockers": [], '
        '"component_lock_drift": []}))\n',
        encoding="utf-8",
    )
    (repo / "scripts" / "viventium" / "bootstrap_components.py").write_text(
        "raise SystemExit(0)\n",
        encoding="utf-8",
    )
    (repo / "scripts" / "viventium" / "config_compiler.py").write_text(
        'raise SystemExit("synthetic invalid candidate config")\n',
        encoding="utf-8",
    )
    (repo / "components.lock.json").write_text(
        '{"version":1,"components":[]}\n',
        encoding="utf-8",
    )
    launcher = repo / "viventium_v0_4" / "viventium-librechat-start.sh"
    launcher.parent.mkdir(parents=True)
    launcher.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    launcher.chmod(0o755)

    librechat = repo / "viventium_v0_4" / "LibreChat"
    librechat.mkdir()
    subprocess.run(["git", "init", "-q", str(librechat)], check=True)
    subprocess.run(
        ["git", "-C", str(librechat), "config", "user.name", "Synthetic QA"],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(librechat),
            "config",
            "user.email",
            "synthetic@example.invalid",
        ],
        check=True,
    )
    (librechat / "marker").write_text("candidate\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(librechat), "add", "marker"], check=True)
    subprocess.run(
        ["git", "-C", str(librechat), "commit", "-qm", "candidate"],
        check=True,
    )
    candidate_env = librechat / ".env"
    candidate_env.write_text(
        "CREDS_KEY=synthetic-existing\n",
        encoding="utf-8",
    )
    candidate_env.chmod(0o600)

    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "Synthetic QA"],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "config",
            "user.email",
            "synthetic@example.invalid",
        ],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "add",
            "bin",
            "scripts",
            "components.lock.json",
            "viventium_v0_4/viventium-librechat-start.sh",
        ],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-qm", "isolated activation fixture"],
        check=True,
    )
    return repo, repo / "bin" / "viventium"


def unused_local_ports(count: int) -> list[int]:
    sockets: list[socket.socket] = []
    try:
        for _ in range(count):
            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            listener.bind(("127.0.0.1", 0))
            sockets.append(listener)
        return [int(listener.getsockname()[1]) for listener in sockets]
    finally:
        for listener in sockets:
            listener.close()


def plan_owner_env(
    support: Path,
    transaction: Path,
    contents: bytes,
    *,
    materialize: bool = True,
) -> None:
    module = load_upgrade_module()
    manifest = (
        transaction
        / "candidate-runtime"
        / "service-env"
        / "librechat.owner.manifest.json"
    )
    manifest.parent.mkdir(parents=True, exist_ok=True)
    activation = run_tool(
        "status",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    repo = Path(activation["candidateEnv"]["repoRoot"])
    commit = subprocess.run(
        [
            "git",
            "-C",
            str(repo / "viventium_v0_4" / "LibreChat"),
            "rev-parse",
            "HEAD",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "kind": "librechat-owner-environment-continuity",
                "semantic_manifest": module.librechat_env_semantic_manifest_from_bytes(
                    contents
                ),
                "target_binding": {
                    "repo_sha256": hashlib.sha256(
                        str(repo).encode("utf-8")
                    ).hexdigest(),
                    "git_commit": commit,
                },
                "materialization_target_name": (
                    ".env.viventium-materialized-synthetic"
                ),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    manifest.chmod(0o600)
    run_tool(
        "owner-env-planned",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
        "--owner-env-manifest",
        manifest,
    )
    if not materialize:
        return
    activation = run_tool(
        "status",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    record = activation["candidateEnv"]
    candidate_env = (
        Path(str(record["repoRoot"])) / "viventium_v0_4" / "LibreChat" / ".env"
    )
    materialized = candidate_env.with_name(
        activation["ownerEnvPlan"]["materializationTargetName"]
    )
    candidate_env.unlink(missing_ok=True)
    materialized.write_bytes(contents)
    materialized.chmod(0o600)
    os.link(materialized, candidate_env)
    run_tool(
        "owner-env-materialized",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )


def prepare(
    tmp_path: Path,
    *,
    candidate_env: bytes | None = None,
    candidate_env_mode: int = 0o600,
    runtime_venv_links: bool = False,
    helper_quiesced: bool = True,
    helper_process_quiesced: bool = True,
    helper_executables: list[Path] | None = None,
) -> tuple[Path, Path, Path, Path, Path]:
    support = tmp_path / "support"
    runtime = support / "runtime"
    state = support / "state"
    transaction = state / "dev-runtime-activation.synthetic"
    candidate = transaction / "candidate-runtime"
    checkout = state / "active-checkout.json"
    helper = support / "helper-config.json"
    candidate_repo = make_candidate_repo(tmp_path)
    if candidate_env is not None:
        candidate_env_file = (
            candidate_repo / "viventium_v0_4" / "LibreChat" / ".env"
        )
        candidate_env_file.write_bytes(candidate_env)
        candidate_env_file.chmod(candidate_env_mode)
    runtime.mkdir(parents=True)
    candidate.mkdir(parents=True)
    (runtime / "runtime.env").write_text("VERSION=old\n", encoding="utf-8")
    if runtime_venv_links:
        bin_dir = (
            runtime
            / "components"
            / "scheduling-cortex"
            / "synthetic"
            / ".venv"
            / "bin"
        )
        bin_dir.mkdir(parents=True)
        external_interpreter = tmp_path / "external-python"
        external_interpreter.write_text("synthetic interpreter\n", encoding="utf-8")
        (bin_dir / "python").symlink_to(external_interpreter)
        (bin_dir / "python3").symlink_to("python")
        (bin_dir / "python3.11").symlink_to("python")
    (candidate / "runtime.env").write_text("VERSION=new\n", encoding="utf-8")
    checkout.write_text('{"repoRoot":"/old"}\n', encoding="utf-8")
    helper.write_text(
        '{"runtimeSupervision":{"desiredState":"running"}}\n',
        encoding="utf-8",
    )
    run_tool(
        "begin",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
        "--candidate-runtime",
        candidate,
        "--runtime-dir",
        runtime,
        "--runtime-checkout-file",
        checkout,
        "--helper-config-file",
        helper,
        "--previous-repo",
        REPO_ROOT,
        "--candidate-repo",
        candidate_repo,
        "--was-running",
    )
    if helper_quiesced:
        run_tool(
            "quiesce-helper",
            "--transaction-dir",
            transaction,
            "--app-support-dir",
            support,
        )
        if sys.platform == "darwin" and helper_process_quiesced:
            process_paths = helper_executables or [
                (
                    tmp_path
                    / "Viventium.app"
                    / "Contents"
                    / "MacOS"
                    / "ViventiumHelper"
                )
            ]
            process_args: list[object] = [
                "quiesce-helper-process",
                "--transaction-dir",
                transaction,
                "--app-support-dir",
                support,
            ]
            for executable in process_paths:
                process_args.extend(["--helper-executable", executable])
            run_tool(*process_args)
    return support, runtime, transaction, checkout, helper


def make_synthetic_helper_executable(tmp_path: Path) -> Path:
    executable = (
        tmp_path
        / "Viventium.app"
        / "Contents"
        / "MacOS"
        / "ViventiumHelper"
    )
    executable.parent.mkdir(parents=True)
    source = tmp_path / "synthetic-helper.c"
    source.write_text(
        "#include <unistd.h>\nint main(void) { for (;;) pause(); }\n",
        encoding="utf-8",
    )
    subprocess.run(
        ["xcrun", "clang", str(source), "-o", str(executable)],
        check=True,
        capture_output=True,
        text=True,
    )
    executable.chmod(0o700)
    return executable


def test_helper_process_quiescence_stops_exact_legacy_helper_and_blocks_resurrection(
    tmp_path: Path,
) -> None:
    executable = make_synthetic_helper_executable(tmp_path)
    legacy_helper = subprocess.Popen([str(executable)])
    support, runtime, transaction, checkout, _ = prepare(
        tmp_path,
        helper_executables=[executable],
    )
    try:
        quiesced = run_tool(
            "status",
            "--transaction-dir",
            transaction,
            "--app-support-dir",
            support,
        )
        assert quiesced["helperProcessQuiescence"] == {
            "executablePaths": [str(executable)],
            "runningExecutablePaths": [str(executable)],
            "status": "applied",
            "wasRunning": True,
        }
        assert legacy_helper.wait(timeout=5) < 0
        stopped = run_tool(
            "helper-process-status",
            "--transaction-dir",
            transaction,
            "--app-support-dir",
            support,
        )
        assert stopped["running"] is False

        resurrected = subprocess.Popen([str(executable)])
        try:
            running = run_tool(
                "helper-process-status",
                "--transaction-dir",
                transaction,
                "--app-support-dir",
                support,
            )
            assert running["running"] is True
            publish = subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "publish",
                    "--transaction-dir",
                    str(transaction),
                    "--app-support-dir",
                    str(support),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            assert publish.returncode != 0
            assert "helper process resumed after quiescence" in publish.stderr
            assert (
                runtime / "runtime.env"
            ).read_text(encoding="utf-8") == "VERSION=old\n"
            assert checkout.read_text(encoding="utf-8") == '{"repoRoot":"/old"}\n'
        finally:
            resurrected.terminate()
            resurrected.wait(timeout=5)

        rolled_back = run_tool(
            "rollback",
            "--transaction-dir",
            transaction,
            "--app-support-dir",
            support,
        )
        assert rolled_back["helperProcessRestoration"]["status"] == "pending"
        restored_helper = subprocess.Popen([str(executable)])
        try:
            restored = run_tool(
                "restore-helper-process",
                "--transaction-dir",
                transaction,
                "--app-support-dir",
                support,
            )
            assert restored["helperProcessRestoration"]["status"] == "complete"
        finally:
            restored_helper.terminate()
            restored_helper.wait(timeout=5)
    finally:
        if legacy_helper.poll() is None:
            legacy_helper.terminate()
            legacy_helper.wait(timeout=5)


def test_helper_process_can_quiesce_before_supervision_receipt(
    tmp_path: Path,
) -> None:
    executable = make_synthetic_helper_executable(tmp_path)
    helper_process = subprocess.Popen([str(executable)])
    support, _, transaction, _, helper = prepare(
        tmp_path,
        helper_quiesced=False,
        helper_process_quiesced=False,
    )
    try:
        process_receipt = run_tool(
            "quiesce-helper-process",
            "--transaction-dir",
            transaction,
            "--app-support-dir",
            support,
            "--helper-executable",
            executable,
        )
        assert process_receipt["helperProcessQuiescence"]["status"] == "applied"
        assert helper_process.wait(timeout=5) < 0

        supervision_receipt = run_tool(
            "quiesce-helper",
            "--transaction-dir",
            transaction,
            "--app-support-dir",
            support,
        )
        token = supervision_receipt["helperQuiescence"]["token"]
        supervision = json.loads(helper.read_text(encoding="utf-8"))[
            "runtimeSupervision"
        ]
        assert supervision["activationTransactionId"] == token
        assert supervision["desiredState"] == "stopped"
    finally:
        if helper_process.poll() is None:
            helper_process.terminate()
            helper_process.wait(timeout=5)


def test_helper_process_quiescence_rejects_non_helper_executable(
    tmp_path: Path,
) -> None:
    support, _, transaction, _, _ = prepare(
        tmp_path,
        helper_process_quiesced=False,
    )
    executable = tmp_path / "not-the-helper"
    shutil.copy(shutil.which("sleep"), executable)
    executable.chmod(0o700)

    completed = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "quiesce-helper-process",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
            "--helper-executable",
            str(executable),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "Viventium helper bundle executable" in completed.stderr


def test_required_helper_process_quiescence_cannot_be_skipped(
    tmp_path: Path,
) -> None:
    support, runtime, transaction, checkout, _ = prepare(
        tmp_path,
        helper_process_quiesced=False,
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "publish",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "helper process quiescence receipt is missing" in completed.stderr
    assert (runtime / "runtime.env").read_text(encoding="utf-8") == "VERSION=old\n"
    assert checkout.read_text(encoding="utf-8") == '{"repoRoot":"/old"}\n'


def test_helper_process_quiescence_revalidates_start_identity_before_signal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = make_synthetic_helper_executable(tmp_path)
    support, _, transaction, _, _ = prepare(
        tmp_path,
        helper_process_quiesced=False,
    )
    module = load_module()
    original_identity = {
        "pid": 4242,
        "executablePath": os.path.realpath(executable),
        "startToken": "original-start",
    }
    calls = 0

    def running_processes(_executables):
        nonlocal calls
        calls += 1
        return [original_identity] if calls <= 2 else []

    monkeypatch.setattr(module, "running_helper_processes", running_processes)
    monkeypatch.setattr(
        module,
        "process_identity",
        lambda _pid: {
            **original_identity,
            "startToken": "reused-start",
        },
    )

    def forbidden_kill(_pid, _signal):
        raise AssertionError("PID-reused process must not be signalled")

    monkeypatch.setattr(module.os, "kill", forbidden_kill)
    args = module.build_parser().parse_args(
        [
            "quiesce-helper-process",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
            "--helper-executable",
            str(executable),
        ]
    )

    result = module.quiesce_helper_process(args)

    assert result["helperProcessQuiescence"]["status"] == "applied"
    assert result["helperProcessQuiescence"]["runningExecutablePaths"] == [
        str(executable)
    ]


def test_activation_preserves_expected_runtime_virtualenv_links_on_rollback(
    tmp_path: Path,
) -> None:
    support, runtime, transaction, _, _ = prepare(
        tmp_path,
        runtime_venv_links=True,
    )
    external_interpreter = tmp_path / "external-python"
    before_external = external_interpreter.read_bytes()
    published = run_tool(
        "publish",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )

    assert (runtime / "runtime.env").read_text(encoding="utf-8") == "VERSION=new\n"
    backup = Path(str(published["runtimeBackup"]))
    backup_bin = (
        backup
        / "components"
        / "scheduling-cortex"
        / "synthetic"
        / ".venv"
        / "bin"
    )
    assert os.readlink(backup_bin / "python") == str(external_interpreter)
    assert os.readlink(backup_bin / "python3") == "python"
    assert os.readlink(backup_bin / "python3.11") == "python"

    rolled_back = run_tool(
        "rollback",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )

    runtime_bin = (
        runtime
        / "components"
        / "scheduling-cortex"
        / "synthetic"
        / ".venv"
        / "bin"
    )
    assert rolled_back["status"] == "rolled_back"
    assert (runtime / "runtime.env").read_text(encoding="utf-8") == "VERSION=old\n"
    assert os.readlink(runtime_bin / "python") == str(external_interpreter)
    assert os.readlink(runtime_bin / "python3") == "python"
    assert os.readlink(runtime_bin / "python3.11") == "python"
    assert external_interpreter.read_bytes() == before_external


@pytest.mark.parametrize("final_action", ["rollback", "commit"])
def test_activation_preserves_candidate_links_without_reading_external_targets(
    tmp_path: Path,
    final_action: str,
) -> None:
    support, runtime, transaction, _, _ = prepare(tmp_path)
    candidate = transaction / "candidate-runtime"
    external_file = tmp_path / "private-external-file"
    external_file.write_bytes(b"PRIVATE_EXTERNAL_BYTES")
    external_directory = tmp_path / "private-external-directory"
    external_directory.mkdir()
    (external_directory / "private").write_bytes(b"PRIVATE_DIRECTORY_BYTES")
    before_file = external_file.read_bytes()
    before_directory = (external_directory / "private").read_bytes()
    (candidate / "linked-file").symlink_to(external_file)
    (candidate / "linked-directory").symlink_to(
        external_directory,
        target_is_directory=True,
    )

    run_tool(
        "publish",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )

    assert (runtime / "linked-file").is_symlink()
    assert os.readlink(runtime / "linked-file") == str(external_file)
    assert (runtime / "linked-directory").is_symlink()
    assert os.readlink(runtime / "linked-directory") == str(external_directory)
    if final_action == "rollback":
        run_tool(
            "rollback",
            "--transaction-dir",
            transaction,
            "--app-support-dir",
            support,
        )
        assert not (runtime / "linked-file").exists()
        assert not (runtime / "linked-file").is_symlink()
        assert not (runtime / "linked-directory").exists()
        assert not (runtime / "linked-directory").is_symlink()
    else:
        run_tool(
            "binding-applied",
            "--transaction-dir",
            transaction,
            "--app-support-dir",
            support,
        )
        committed = run_tool(
            "commit",
            "--transaction-dir",
            transaction,
            "--app-support-dir",
            support,
        )
        assert committed["status"] == "core_committed"
        assert (runtime / "linked-file").is_symlink()
        assert (runtime / "linked-directory").is_symlink()
    assert external_file.read_bytes() == before_file
    assert (external_directory / "private").read_bytes() == before_directory


def downgrade_activation_manifest_to_v1(
    transaction: Path,
    *,
    status: str | None = None,
) -> dict:
    manifest_path = transaction / "activation.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["schemaVersion"] = 1
    if status is not None:
        payload["status"] = status
    for field in (
        "candidateEnv",
        "helperQuiescence",
        "ownerEnvMaterialized",
        "ownerEnvPlan",
        "ownerEnvAccepted",
        "runtimePrecondition",
        "runtimeCandidateIdentity",
    ):
        payload.pop(field, None)
    manifest_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    manifest_path.chmod(0o600)
    return payload


def test_schema_v1_prepared_activation_still_rolls_back_state(
    tmp_path: Path,
) -> None:
    support, runtime, transaction, checkout, helper = prepare(tmp_path)
    helper.write_text(
        '{"runtimeSupervision":{"desiredState":"stopped"}}\n',
        encoding="utf-8",
    )
    downgrade_activation_manifest_to_v1(transaction)

    rolled_back = run_tool(
        "rollback",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )

    assert rolled_back["status"] == "rolled_back"
    assert (runtime / "runtime.env").read_text(encoding="utf-8") == "VERSION=old\n"
    assert "running" in helper.read_text(encoding="utf-8")
    assert checkout.read_text(encoding="utf-8") == '{"repoRoot":"/old"}\n'


def test_schema_v1_publishing_before_runtime_rename_rolls_back_staging(
    tmp_path: Path,
) -> None:
    support, runtime, transaction, checkout, _ = prepare(tmp_path)
    staging = runtime.parent / ".runtime.viventium-candidate-legacy"
    shutil.copytree(transaction / "candidate-runtime", staging)
    payload = downgrade_activation_manifest_to_v1(
        transaction,
        status="publishing",
    )
    payload.update(
        {
            "runtimeOriginallyPresent": True,
            "runtimeBackup": str(
                runtime.parent / ".runtime.viventium-backup-legacy"
            ),
            "runtimeStaging": str(staging),
        }
    )
    (transaction / "activation.json").write_text(
        json.dumps(payload) + "\n",
        encoding="utf-8",
    )

    rolled_back = run_tool(
        "rollback",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )

    assert rolled_back["status"] == "rolled_back"
    assert (runtime / "runtime.env").read_text(encoding="utf-8") == "VERSION=old\n"
    assert not staging.exists()
    assert checkout.read_text(encoding="utf-8") == '{"repoRoot":"/old"}\n'


@pytest.mark.parametrize("legacy_status", ["runtime_backed_up", "published"])
def test_schema_v1_postpublish_activation_restores_runtime_and_state(
    tmp_path: Path,
    legacy_status: str,
) -> None:
    support, runtime, transaction, checkout, _ = prepare(tmp_path)
    run_tool(
        "publish",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    checkout.write_text('{"repoRoot":"/candidate"}\n', encoding="utf-8")
    downgrade_activation_manifest_to_v1(transaction, status=legacy_status)

    rolled_back = run_tool(
        "rollback",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )

    assert rolled_back["status"] == "rolled_back"
    assert (runtime / "runtime.env").read_text(encoding="utf-8") == "VERSION=old\n"
    assert checkout.read_text(encoding="utf-8") == '{"repoRoot":"/old"}\n'


def test_schema_v1_binding_applied_remains_fail_closed(
    tmp_path: Path,
) -> None:
    support, _, transaction, checkout, _ = prepare(tmp_path)
    run_tool(
        "publish",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    checkout.write_text('{"repoRoot":"/candidate"}\n', encoding="utf-8")
    run_tool(
        "binding-applied",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    downgrade_activation_manifest_to_v1(transaction)

    completed = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "rollback",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "automatic rollback is not safe" in completed.stderr


def test_published_activation_rolls_back_runtime_binding_and_helper_intent(
    tmp_path: Path,
) -> None:
    support, runtime, transaction, checkout, helper = prepare(tmp_path)

    published = run_tool(
        "publish",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    assert published["status"] == "published"
    assert (runtime / "runtime.env").read_text(encoding="utf-8") == "VERSION=new\n"
    checkout.write_text('{"repoRoot":"/candidate"}\n', encoding="utf-8")

    rolled_back = run_tool(
        "rollback",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    assert rolled_back["status"] == "rolled_back"
    assert (runtime / "runtime.env").read_text(encoding="utf-8") == "VERSION=old\n"
    assert checkout.read_text(encoding="utf-8") == '{"repoRoot":"/old"}\n'
    assert (
        helper.read_text(encoding="utf-8")
        == '{"runtimeSupervision":{"desiredState":"running"}}\n'
    )


def test_rollback_restores_only_helper_intent_and_preserves_concurrent_personalization(
    tmp_path: Path,
) -> None:
    support, runtime, transaction, checkout, helper = prepare(tmp_path)
    run_tool(
        "publish",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    checkout.write_text('{"repoRoot":"/candidate"}\n', encoding="utf-8")
    helper_payload = json.loads(helper.read_text(encoding="utf-8"))
    helper_payload["ownerPreference"] = {"theme": "keep-concurrent"}
    helper_payload["runtimeSupervision"]["ownerRetryPreference"] = (
        "keep-concurrent"
    )
    helper.write_text(json.dumps(helper_payload) + "\n", encoding="utf-8")

    rolled_back = run_tool(
        "rollback",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )

    assert rolled_back["status"] == "rolled_back"
    assert (runtime / "runtime.env").read_text(encoding="utf-8") == "VERSION=old\n"
    assert checkout.read_text(encoding="utf-8") == '{"repoRoot":"/old"}\n'
    restored = json.loads(helper.read_text(encoding="utf-8"))
    assert restored["ownerPreference"] == {"theme": "keep-concurrent"}
    assert restored["runtimeSupervision"] == {
        "desiredState": "running",
        "ownerRetryPreference": "keep-concurrent",
    }


def test_crash_after_stop_before_publish_restores_prepared_helper_state(
    tmp_path: Path,
) -> None:
    support, runtime, transaction, checkout, helper = prepare(tmp_path)

    recovered = run_tool(
        "rollback",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    assert recovered["status"] == "rolled_back"
    assert recovered["wasRunning"] is True
    assert "running" in helper.read_text(encoding="utf-8")
    assert (runtime / "runtime.env").read_text(encoding="utf-8") == "VERSION=old\n"


def test_prepared_rollback_without_quiescence_receipt_preserves_owner_intent(
    tmp_path: Path,
) -> None:
    support, _, transaction, _, helper = prepare(
        tmp_path,
        helper_quiesced=False,
    )
    helper.write_text(
        json.dumps(
            {
                "runtimeSupervision": {
                    "desiredState": "stopped",
                    "ownerChoice": "preserve",
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )

    rolled_back = run_tool(
        "rollback",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )

    assert rolled_back["status"] == "rolled_back"
    assert json.loads(helper.read_text(encoding="utf-8")) == {
        "runtimeSupervision": {
            "desiredState": "stopped",
            "ownerChoice": "preserve",
        }
    }


def test_planned_quiescence_crash_preserves_later_owner_intent(
    tmp_path: Path,
) -> None:
    support, _, transaction, _, helper = prepare(
        tmp_path,
        helper_quiesced=False,
    )
    manifest_path = transaction / "activation.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["helperQuiescence"] = {
        "status": "planned",
        "token": "synthetic-planned-token",
    }
    manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")
    owner_helper = {
        "runtimeSupervision": {
            "desiredState": "stopped",
            "ownerChoice": "preserve-after-plan",
        }
    }
    helper.write_text(json.dumps(owner_helper) + "\n", encoding="utf-8")

    rolled_back = run_tool(
        "rollback",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )

    assert rolled_back["status"] == "rolled_back"
    assert json.loads(helper.read_text(encoding="utf-8")) == owner_helper


def test_planned_quiescence_retry_rejects_matching_token_with_managed_drift(
    tmp_path: Path,
) -> None:
    support, runtime, transaction, checkout, helper = prepare(
        tmp_path,
        helper_quiesced=False,
    )
    token = "synthetic-planned-token"
    manifest_path = transaction / "activation.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["helperQuiescence"] = {"status": "planned", "token": token}
    manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")
    drifted_helper = json.loads(helper.read_text(encoding="utf-8"))
    drifted_helper["runtimeSupervision"].update(
        {
            "activationTransactionId": token,
            "desiredState": "running",
            "consecutiveLaunchAttempts": 77,
            "nextLaunchAttemptAt": "2099-01-01T00:00:00Z",
            "healthySince": "2099-01-01T00:00:00Z",
        }
    )
    helper.write_text(json.dumps(drifted_helper) + "\n", encoding="utf-8")

    quiesce = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "quiesce-helper",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    publish = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "publish",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert quiesce.returncode != 0
    assert "changed during quiescence" in quiesce.stderr
    assert publish.returncode != 0
    assert "receipt is invalid" in publish.stderr
    assert (runtime / "runtime.env").read_text(encoding="utf-8") == "VERSION=old\n"
    assert checkout.read_text(encoding="utf-8") == '{"repoRoot":"/old"}\n'
    assert json.loads(helper.read_text(encoding="utf-8")) == drifted_helper


def test_planned_quiescence_retry_accepts_exact_owned_state_and_personal_drift(
    tmp_path: Path,
) -> None:
    support, _, transaction, _, helper = prepare(
        tmp_path,
        helper_quiesced=False,
    )
    token = "synthetic-planned-token"
    manifest_path = transaction / "activation.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["helperQuiescence"] = {"status": "planned", "token": token}
    manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")
    quiesced_helper = json.loads(helper.read_text(encoding="utf-8"))
    quiesced_helper["ownerPreference"] = {"theme": "preserve"}
    quiesced_helper["runtimeSupervision"].update(
        {
            "activationTransactionId": token,
            "schemaVersion": 1,
            "desiredState": "stopped",
            "consecutiveLaunchAttempts": 0,
            "nextLaunchAttemptAt": None,
            "healthySince": None,
            "ownerRetryPreference": "preserve",
        }
    )
    helper.write_text(json.dumps(quiesced_helper) + "\n", encoding="utf-8")

    applied = run_tool(
        "quiesce-helper",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    rolled_back = run_tool(
        "rollback",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )

    assert applied["helperQuiescence"]["status"] == "applied"
    assert rolled_back["status"] == "rolled_back"
    restored = json.loads(helper.read_text(encoding="utf-8"))
    assert restored["runtimeSupervision"]["desiredState"] == "running"
    assert "activationTransactionId" not in restored["runtimeSupervision"]
    assert restored["runtimeSupervision"]["ownerRetryPreference"] == "preserve"
    assert restored["ownerPreference"] == {"theme": "preserve"}


def test_publish_rejects_managed_helper_drift_after_quiescence_receipt(
    tmp_path: Path,
) -> None:
    support, runtime, transaction, checkout, helper = prepare(tmp_path)
    owner_helper = json.loads(helper.read_text(encoding="utf-8"))
    owner_helper["runtimeSupervision"]["desiredState"] = "running"
    helper.write_text(json.dumps(owner_helper) + "\n", encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "publish",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "changed after quiescence" in completed.stderr
    assert (runtime / "runtime.env").read_text(encoding="utf-8") == "VERSION=old\n"
    assert checkout.read_text(encoding="utf-8") == '{"repoRoot":"/old"}\n'
    assert json.loads(helper.read_text(encoding="utf-8")) == owner_helper


def test_rollback_rejects_managed_helper_drift_with_owned_token(
    tmp_path: Path,
) -> None:
    support, runtime, transaction, checkout, helper = prepare(tmp_path)
    owner_helper = json.loads(helper.read_text(encoding="utf-8"))
    owner_helper["runtimeSupervision"]["desiredState"] = "running"
    owner_helper["runtimeSupervision"]["ownerChoice"] = "preserve"
    helper.write_text(json.dumps(owner_helper) + "\n", encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "rollback",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "changed after quiescence" in completed.stderr
    assert (runtime / "runtime.env").read_text(encoding="utf-8") == "VERSION=old\n"
    assert checkout.read_text(encoding="utf-8") == '{"repoRoot":"/old"}\n'
    assert json.loads(helper.read_text(encoding="utf-8")) == owner_helper


def test_rollback_recovers_exact_quiesced_helper_view_after_tokenless_shutdown_write(
    tmp_path: Path,
) -> None:
    executable = make_synthetic_helper_executable(tmp_path)
    helper_process = subprocess.Popen([str(executable)])
    support, _, transaction, _, helper = prepare(
        tmp_path,
        helper_executables=[executable],
    )
    try:
        assert helper_process.wait(timeout=5) < 0
        quiesced = json.loads(helper.read_text(encoding="utf-8"))
        quiesced["runtimeSupervision"].pop("activationTransactionId")
        quiesced["ownerPreference"] = {"theme": "preserve"}
        helper.write_text(json.dumps(quiesced) + "\n", encoding="utf-8")

        rolled_back = run_tool(
            "rollback",
            "--transaction-dir",
            transaction,
            "--app-support-dir",
            support,
        )

        assert rolled_back["status"] == "rolled_back"
        restored = json.loads(helper.read_text(encoding="utf-8"))
        assert restored["runtimeSupervision"]["desiredState"] == "running"
        assert "activationTransactionId" not in restored["runtimeSupervision"]
        assert restored["ownerPreference"] == {"theme": "preserve"}
    finally:
        if helper_process.poll() is None:
            helper_process.terminate()
            helper_process.wait(timeout=5)


def test_rollback_rejects_tokenless_quiesced_view_without_running_helper_receipt(
    tmp_path: Path,
) -> None:
    support, _, transaction, _, helper = prepare(tmp_path)
    quiesced = json.loads(helper.read_text(encoding="utf-8"))
    quiesced["runtimeSupervision"].pop("activationTransactionId")
    helper.write_text(json.dumps(quiesced) + "\n", encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "rollback",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "ownership changed before restoration" in completed.stderr


def test_planned_but_unmaterialized_owner_env_preserves_concurrent_edit(
    tmp_path: Path,
) -> None:
    original = b"CREDS_KEY=original\n"
    planned = b"CREDS_KEY=planned\n"
    support, _, transaction, _, helper = prepare(
        tmp_path,
        candidate_env=original,
    )
    plan_owner_env(support, transaction, planned, materialize=False)
    payload = run_tool(
        "status",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    candidate_env = (
        Path(str(payload["candidateEnv"]["repoRoot"]))
        / "viventium_v0_4"
        / "LibreChat"
        / ".env"
    )
    concurrent = b"CREDS_KEY=concurrent-owner-choice\n"
    candidate_env.write_bytes(concurrent)

    rolled_back = run_tool(
        "rollback",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )

    assert rolled_back["status"] == "rolled_back"
    assert candidate_env.read_bytes() == concurrent
    restored_helper = json.loads(helper.read_text(encoding="utf-8"))
    assert restored_helper["runtimeSupervision"]["desiredState"] == "running"
    assert "activationTransactionId" not in restored_helper["runtimeSupervision"]


def test_candidate_owner_env_checkpoint_restores_exact_bytes_mode_and_hides_values(
    tmp_path: Path,
) -> None:
    original = b"CREDS_KEY=synthetic-candidate-original\nOWNER_NOTE=keep\n"
    live = b"CREDS_KEY=synthetic-live-owner\nOWNER_NOTE=live\nPORT=3180\n"
    support, runtime, transaction, checkout, helper = prepare(
        tmp_path,
        candidate_env=original,
        candidate_env_mode=0o640,
    )
    payload = run_tool(
        "status",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    record = payload["candidateEnv"]
    snapshot = Path(str(record["snapshot"]))
    candidate_env = (
        Path(str(record["repoRoot"])) / "viventium_v0_4" / "LibreChat" / ".env"
    )
    assert snapshot.read_bytes() == original
    assert snapshot.stat().st_mode & 0o777 == 0o600
    serialized = json.dumps(payload, sort_keys=True)
    assert "synthetic-candidate-original" not in serialized
    assert "synthetic-live-owner" not in serialized

    plan_owner_env(support, transaction, live)
    candidate_env.write_bytes(live)
    candidate_env.chmod(0o600)
    rolled_back = run_tool(
        "rollback",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )

    assert rolled_back["status"] == "rolled_back"
    assert candidate_env.read_bytes() == original
    assert candidate_env.stat().st_mode & 0o777 == 0o640
    assert (runtime / "runtime.env").read_text(encoding="utf-8") == "VERSION=old\n"
    assert checkout.read_text(encoding="utf-8") == '{"repoRoot":"/old"}\n'
    assert "running" in helper.read_text(encoding="utf-8")


def test_candidate_owner_env_original_absence_restores_exactly_and_is_idempotent(
    tmp_path: Path,
) -> None:
    live = b"CREDS_KEY=synthetic-live-owner\nOWNER_NOTE=live\n"
    support, _, transaction, _, _ = prepare(tmp_path)
    payload = run_tool(
        "status",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    record = payload["candidateEnv"]
    candidate_env = (
        Path(str(record["repoRoot"])) / "viventium_v0_4" / "LibreChat" / ".env"
    )
    plan_owner_env(support, transaction, live, materialize=False)
    planned_payload = run_tool(
        "status",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    materialized = candidate_env.with_name(
        planned_payload["ownerEnvPlan"]["materializationTargetName"]
    )
    materialized.write_bytes(live)
    materialized.chmod(0o600)
    os.link(materialized, candidate_env)

    module = load_module()
    module.restore_candidate_env_atomically(
        record,
        planned_payload,
        transaction,
    )
    assert not candidate_env.exists()

    rolled_back = run_tool(
        "rollback",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    assert rolled_back["status"] == "rolled_back"
    assert not candidate_env.exists()
    assert not materialized.exists()


@pytest.mark.parametrize("published", [False, True])
def test_rollback_cleans_detached_materialization_only_after_original_env_is_already_exact(
    tmp_path: Path,
    published: bool,
) -> None:
    original = b"CREDS_KEY=synthetic-original\nOWNER_NOTE=keep\n"
    support, _, transaction, checkout, _ = prepare(
        tmp_path,
        candidate_env=original,
        candidate_env_mode=0o640,
    )
    plan_owner_env(support, transaction, original)
    payload = run_tool(
        "status",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    record = payload["candidateEnv"]
    candidate_env = (
        Path(str(record["repoRoot"])) / "viventium_v0_4" / "LibreChat" / ".env"
    )
    materialized = candidate_env.with_name(
        payload["ownerEnvPlan"]["materializationTargetName"]
    )
    materialized_inode = materialized.stat().st_ino

    if published:
        run_tool(
            "publish",
            "--transaction-dir",
            transaction,
            "--app-support-dir",
            support,
        )
        checkout.write_text('{"repoRoot":"/candidate"}\n', encoding="utf-8")
        run_tool(
            "binding-applied",
            "--transaction-dir",
            transaction,
            "--app-support-dir",
            support,
        )

    replacement = candidate_env.with_name(".env.synthetic-runtime-rewrite")
    replacement.write_bytes(original)
    replacement.chmod(0o640)
    os.replace(replacement, candidate_env)
    assert candidate_env.stat().st_ino != materialized_inode
    assert materialized.exists()

    rolled_back = run_tool(
        "rollback",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )

    assert rolled_back["status"] == "rolled_back"
    assert candidate_env.read_bytes() == original
    assert candidate_env.stat().st_mode & 0o777 == 0o640
    assert not materialized.exists()
    assert not candidate_env.with_name(
        record["materializationClaimDirectoryName"]
    ).exists()


def test_rollback_preserves_detached_materialization_when_candidate_env_is_not_original(
    tmp_path: Path,
) -> None:
    original = b"CREDS_KEY=synthetic-original\nOWNER_NOTE=keep\n"
    concurrent = b"CREDS_KEY=synthetic-concurrent\nOWNER_NOTE=preserve\n"
    support, runtime, transaction, checkout, _ = prepare(
        tmp_path,
        candidate_env=original,
    )
    plan_owner_env(support, transaction, original)
    payload = run_tool(
        "status",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    record = payload["candidateEnv"]
    candidate_env = (
        Path(str(record["repoRoot"])) / "viventium_v0_4" / "LibreChat" / ".env"
    )
    materialized = candidate_env.with_name(
        payload["ownerEnvPlan"]["materializationTargetName"]
    )
    replacement = candidate_env.with_name(".env.synthetic-concurrent")
    replacement.write_bytes(concurrent)
    replacement.chmod(0o600)
    os.replace(replacement, candidate_env)
    before_runtime = (runtime / "runtime.env").read_bytes()
    before_checkout = checkout.read_bytes()

    completed = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "rollback",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "detached materialization is ambiguous" in completed.stderr
    assert candidate_env.read_bytes() == concurrent
    assert materialized.read_bytes() == original
    assert (runtime / "runtime.env").read_bytes() == before_runtime
    assert checkout.read_bytes() == before_checkout
    current = run_tool(
        "status",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    assert current["status"] == "prepared"


def test_detached_materialization_first_no_replace_claim_detects_replacement(
    tmp_path: Path,
    monkeypatch,
) -> None:
    original = b"CREDS_KEY=synthetic-original\nOWNER_NOTE=keep\n"
    concurrent = b"CREDS_KEY=synthetic-concurrent-artifact\n"
    support, runtime, transaction, checkout, _ = prepare(
        tmp_path,
        candidate_env=original,
    )
    plan_owner_env(support, transaction, original)
    payload = run_tool(
        "status",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    record = payload["candidateEnv"]
    candidate_env = (
        Path(str(record["repoRoot"])) / "viventium_v0_4" / "LibreChat" / ".env"
    )
    materialized = candidate_env.with_name(
        payload["ownerEnvPlan"]["materializationTargetName"]
    )
    receipted_anchor = candidate_env.with_name(".env.synthetic-receipted-anchor")
    replacement_source = candidate_env.with_name(".env.synthetic-racing-source")
    replacement = candidate_env.with_name(".env.synthetic-runtime-rewrite")
    replacement.write_bytes(original)
    replacement.chmod(0o600)
    os.replace(replacement, candidate_env)
    replacement_source.write_bytes(concurrent)
    replacement_source.chmod(0o600)
    before_runtime = (runtime / "runtime.env").read_bytes()
    before_checkout = checkout.read_bytes()

    module = load_module()
    real_claim = module.atomic_rename_no_replace_at
    injected = False

    def replace_at_claim(directory_descriptor, source_name, destination_name):
        nonlocal injected
        if (
            not injected
            and source_name == materialized.name
            and destination_name == record["rollbackCleanupName"]
        ):
            os.rename(materialized, receipted_anchor)
            os.rename(replacement_source, materialized)
            injected = True
        return real_claim(directory_descriptor, source_name, destination_name)

    monkeypatch.setattr(
        module,
        "atomic_rename_no_replace_at",
        replace_at_claim,
    )
    args = module.build_parser().parse_args(
        [
            "rollback",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ]
    )
    with pytest.raises(
        module.ActivationError,
        match="detached materialization receipt changed",
    ):
        module.rollback(args)

    assert injected is True
    assert candidate_env.read_bytes() == original
    assert materialized.read_bytes() == concurrent
    assert receipted_anchor.read_bytes() == original
    assert not replacement_source.exists()
    assert (runtime / "runtime.env").read_bytes() == before_runtime
    assert checkout.read_bytes() == before_checkout
    current = run_tool(
        "status",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    assert current["status"] == "prepared"


def test_detached_materialization_private_no_replace_claim_detects_replacement(
    tmp_path: Path,
    monkeypatch,
) -> None:
    original = b"CREDS_KEY=synthetic-original\nOWNER_NOTE=keep\n"
    concurrent = b"CREDS_KEY=synthetic-final-race\n"
    support, runtime, transaction, checkout, _ = prepare(
        tmp_path,
        candidate_env=original,
    )
    plan_owner_env(support, transaction, original)
    payload = run_tool(
        "status",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    record = payload["candidateEnv"]
    candidate_env = (
        Path(str(record["repoRoot"])) / "viventium_v0_4" / "LibreChat" / ".env"
    )
    materialized = candidate_env.with_name(
        payload["ownerEnvPlan"]["materializationTargetName"]
    )
    cleanup = candidate_env.with_name(record["rollbackCleanupName"])
    claim_directory = candidate_env.with_name(
        record["materializationClaimDirectoryName"]
    )
    receipted_anchor = candidate_env.with_name(".env.synthetic-final-anchor")
    replacement_source = candidate_env.with_name(".env.synthetic-final-source")
    replacement = candidate_env.with_name(".env.synthetic-runtime-rewrite")
    replacement.write_bytes(original)
    replacement.chmod(0o600)
    os.replace(replacement, candidate_env)
    replacement_source.write_bytes(concurrent)
    replacement_source.chmod(0o600)
    before_runtime = (runtime / "runtime.env").read_bytes()
    before_checkout = checkout.read_bytes()

    module = load_module()
    real_move = module.atomic_rename_no_replace_between
    injected = False

    def replace_before_final_quarantine(
        source_directory_descriptor,
        source_name,
        destination_directory_descriptor,
        destination_name,
    ):
        nonlocal injected
        if (
            not injected
            and source_name == cleanup.name
            and destination_name == "owner.env"
        ):
            os.rename(cleanup, receipted_anchor)
            os.rename(replacement_source, cleanup)
            injected = True
        return real_move(
            source_directory_descriptor,
            source_name,
            destination_directory_descriptor,
            destination_name,
        )

    monkeypatch.setattr(
        module,
        "atomic_rename_no_replace_between",
        replace_before_final_quarantine,
    )
    args = module.build_parser().parse_args(
        [
            "rollback",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ]
    )
    with pytest.raises(
        module.ActivationError,
        match="detached materialization receipt changed",
    ):
        module.rollback(args)

    assert injected is True
    assert candidate_env.read_bytes() == original
    assert not materialized.exists()
    assert receipted_anchor.read_bytes() == original
    assert not cleanup.exists()
    assert (claim_directory / "owner.env").read_bytes() == concurrent
    assert (runtime / "runtime.env").read_bytes() == before_runtime
    assert checkout.read_bytes() == before_checkout
    current = run_tool(
        "status",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    assert current["status"] == "prepared"


def test_detached_materialization_cleanup_claim_is_crash_recoverable(
    tmp_path: Path,
) -> None:
    original = b"CREDS_KEY=synthetic-original\nOWNER_NOTE=keep\n"
    support, _, transaction, _, _ = prepare(
        tmp_path,
        candidate_env=original,
    )
    plan_owner_env(support, transaction, original)
    payload = run_tool(
        "status",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    record = payload["candidateEnv"]
    candidate_env = (
        Path(str(record["repoRoot"])) / "viventium_v0_4" / "LibreChat" / ".env"
    )
    materialized = candidate_env.with_name(
        payload["ownerEnvPlan"]["materializationTargetName"]
    )
    cleanup = candidate_env.with_name(record["rollbackCleanupName"])
    replacement = candidate_env.with_name(".env.synthetic-runtime-rewrite")
    replacement.write_bytes(original)
    replacement.chmod(0o600)
    os.replace(replacement, candidate_env)
    os.rename(materialized, cleanup)

    rolled_back = run_tool(
        "rollback",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )

    assert rolled_back["status"] == "rolled_back"
    assert candidate_env.read_bytes() == original
    assert not materialized.exists()
    assert not cleanup.exists()
    assert not candidate_env.with_name(
        record["materializationClaimDirectoryName"]
    ).exists()


def test_detached_materialization_empty_private_claim_cleanup_is_retryable(
    tmp_path: Path,
) -> None:
    original = b"CREDS_KEY=synthetic-original\nOWNER_NOTE=keep\n"
    support, _, transaction, _, _ = prepare(
        tmp_path,
        candidate_env=original,
    )
    plan_owner_env(support, transaction, original)
    payload = run_tool(
        "status",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    record = payload["candidateEnv"]
    candidate_env = (
        Path(str(record["repoRoot"])) / "viventium_v0_4" / "LibreChat" / ".env"
    )
    materialized = candidate_env.with_name(
        payload["ownerEnvPlan"]["materializationTargetName"]
    )
    claim_directory = candidate_env.with_name(
        record["materializationClaimDirectoryName"]
    )
    replacement = candidate_env.with_name(".env.synthetic-runtime-rewrite")
    replacement.write_bytes(original)
    replacement.chmod(0o600)
    os.replace(replacement, candidate_env)
    claim_directory.mkdir(mode=0o700)
    os.rename(materialized, claim_directory / "owner.env")
    os.rename(claim_directory / "owner.env", claim_directory / "deleting.env")
    os.unlink(claim_directory / "deleting.env")

    rolled_back = run_tool(
        "rollback",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )

    assert rolled_back["status"] == "rolled_back"
    assert candidate_env.read_bytes() == original
    assert not claim_directory.exists()


def test_detached_materialization_rollback_never_moves_artifact_into_app_support(
    tmp_path: Path,
    monkeypatch,
) -> None:
    original = b"CREDS_KEY=synthetic-original\nOWNER_NOTE=keep\n"
    support, _, transaction, _, _ = prepare(
        tmp_path,
        candidate_env=original,
    )
    plan_owner_env(support, transaction, original)
    payload = run_tool(
        "status",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    record = payload["candidateEnv"]
    candidate_env = (
        Path(str(record["repoRoot"])) / "viventium_v0_4" / "LibreChat" / ".env"
    )
    replacement = candidate_env.with_name(".env.synthetic-runtime-rewrite")
    replacement.write_bytes(original)
    replacement.chmod(0o600)
    os.replace(replacement, candidate_env)

    module = load_module()
    real_move = module.atomic_rename_no_replace_between
    transaction_inode = transaction.stat().st_ino
    observed_moves: list[tuple[int, int]] = []

    def reject_app_support_cross_volume_claim(
        source_directory_descriptor,
        source_name,
        destination_directory_descriptor,
        destination_name,
    ):
        source = os.fstat(source_directory_descriptor)
        destination = os.fstat(destination_directory_descriptor)
        observed_moves.append((source.st_dev, destination.st_dev))
        if destination.st_ino == transaction_inode:
            raise OSError(errno.EXDEV, "synthetic cross-device claim refusal")
        assert source.st_dev == destination.st_dev
        return real_move(
            source_directory_descriptor,
            source_name,
            destination_directory_descriptor,
            destination_name,
        )

    monkeypatch.setattr(
        module,
        "atomic_rename_no_replace_between",
        reject_app_support_cross_volume_claim,
    )
    args = module.build_parser().parse_args(
        [
            "rollback",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ]
    )

    assert module.rollback(args)["status"] == "rolled_back"
    assert observed_moves
    assert all(source == destination for source, destination in observed_moves)


def test_partial_transaction_materialization_is_crash_recoverable(
    tmp_path: Path,
) -> None:
    live = b"CREDS_KEY=synthetic-live-owner\nOWNER_NOTE=live\n"
    support, runtime, transaction, checkout, _ = prepare(tmp_path)
    plan_owner_env(support, transaction, live, materialize=False)
    payload = run_tool(
        "status",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    candidate_env = (
        Path(str(payload["candidateEnv"]["repoRoot"]))
        / "viventium_v0_4"
        / "LibreChat"
        / ".env"
    )
    materialized = candidate_env.with_name(
        payload["ownerEnvPlan"]["materializationTargetName"]
    )
    materialized.write_bytes(b"CREDS_KEY=partial")
    materialized.chmod(0o600)

    rolled_back = run_tool(
        "rollback",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )

    assert rolled_back["status"] == "rolled_back"
    assert not candidate_env.exists()
    assert not materialized.exists()
    assert (runtime / "runtime.env").read_text(encoding="utf-8") == "VERSION=old\n"
    assert checkout.read_text(encoding="utf-8") == '{"repoRoot":"/old"}\n'


@pytest.mark.parametrize(
    "name",
    (
        ".env.viventium-materialize-stale",
        ".env.viventium-materialized-stale",
        ".env.viventium-rollback-stale",
        ".env.viventium-accepted-stale",
        ".env.viventium-restore-stale",
        ".env.viventium-cleanup-stale",
        ".env.viventium-private-stale",
    ),
)
def test_candidate_checkpoint_rejects_any_stale_owner_env_transaction_file(
    tmp_path: Path,
    name: str,
) -> None:
    module = load_module()
    repo = make_candidate_repo(tmp_path)
    stale = repo / "viventium_v0_4" / "LibreChat" / name
    stale.write_text("CREDS_KEY=must-not-be-discarded\n", encoding="utf-8")
    stale.chmod(0o600)

    with pytest.raises(
        module.ActivationError,
        match="contains stale activation state",
    ):
        module.safe_candidate_env_snapshot(
            repo,
            tmp_path / "candidate-librechat.env",
        )

    assert stale.read_text(encoding="utf-8") == (
        "CREDS_KEY=must-not-be-discarded\n"
    )


def test_prepared_rollback_preserves_unplanned_candidate_owner_edit(
    tmp_path: Path,
) -> None:
    support, runtime, transaction, checkout, _ = prepare(tmp_path)
    payload = run_tool(
        "status",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    candidate_env = (
        Path(str(payload["candidateEnv"]["repoRoot"]))
        / "viventium_v0_4"
        / "LibreChat"
        / ".env"
    )
    candidate_env.write_text("OWNER_NOTE=concurrent-user-edit\n", encoding="utf-8")
    before_runtime = (runtime / "runtime.env").read_bytes()
    before_checkout = checkout.read_bytes()

    rolled_back = run_tool(
        "rollback",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )

    assert rolled_back["status"] == "rolled_back"
    assert candidate_env.read_text(encoding="utf-8") == (
        "OWNER_NOTE=concurrent-user-edit\n"
    )
    assert (runtime / "runtime.env").read_bytes() == before_runtime
    assert checkout.read_bytes() == before_checkout


def test_prepared_rollback_preserves_live_runtime_and_checkout_changes(
    tmp_path: Path,
) -> None:
    support, runtime, transaction, checkout, helper = prepare(tmp_path)
    runtime_file = runtime / "runtime.env"
    runtime_file.write_text("VERSION=old\nNATURAL_ACTIVITY=1\n", encoding="utf-8")
    runtime_cache = runtime / "natural-runtime-cache"
    runtime_cache.write_text("preserve\n", encoding="utf-8")
    checkout.write_text('{"repoRoot":"/concurrent-owner-choice"}\n', encoding="utf-8")
    helper_payload = json.loads(helper.read_text(encoding="utf-8"))
    helper_payload["ownerPreference"] = {"keep": True}
    helper_payload["runtimeSupervision"]["ownerRetryPreference"] = "preserve"
    helper.write_text(json.dumps(helper_payload) + "\n", encoding="utf-8")

    rolled_back = run_tool(
        "rollback",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )

    assert rolled_back["status"] == "rolled_back"
    assert runtime_file.read_text(encoding="utf-8") == (
        "VERSION=old\nNATURAL_ACTIVITY=1\n"
    )
    assert runtime_cache.read_text(encoding="utf-8") == "preserve\n"
    assert checkout.read_text(encoding="utf-8") == (
        '{"repoRoot":"/concurrent-owner-choice"}\n'
    )
    restored = json.loads(helper.read_text(encoding="utf-8"))
    assert restored["ownerPreference"] == {"keep": True}
    assert restored["runtimeSupervision"] == {
        "desiredState": "running",
        "ownerRetryPreference": "preserve",
    }


def test_candidate_owner_env_concurrent_edit_after_quarantine_is_never_overwritten(
    tmp_path: Path,
    monkeypatch,
) -> None:
    original = b"CREDS_KEY=original\nOWNER_NOTE=original\n"
    planned = b"CREDS_KEY=established\nOWNER_NOTE=established\n"
    concurrent = b"CREDS_KEY=concurrent\nOWNER_NOTE=concurrent-after-claim\n"
    support, runtime, transaction, checkout, _ = prepare(
        tmp_path,
        candidate_env=original,
    )
    plan_owner_env(support, transaction, planned)
    payload = run_tool(
        "status",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    record = payload["candidateEnv"]
    candidate_env = (
        Path(str(record["repoRoot"])) / "viventium_v0_4" / "LibreChat" / ".env"
    )
    candidate_env.write_bytes(planned)
    before_runtime = (runtime / "runtime.env").read_bytes()
    before_checkout = checkout.read_bytes()

    module = load_module()
    original_reader = module.current_candidate_env_bytes
    injected = False

    def inject_after_quarantine(directory_descriptor, name=".env"):
        nonlocal injected
        contents = original_reader(directory_descriptor, name)
        if (
            not injected
            and name == record["rollbackQuarantineName"]
            and contents is not None
        ):
            candidate_env.write_bytes(concurrent)
            injected = True
        return contents

    monkeypatch.setattr(module, "current_candidate_env_bytes", inject_after_quarantine)
    args = module.build_parser().parse_args(
        [
            "rollback",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ]
    )
    with pytest.raises(
        module.ActivationError,
        match="Concurrent candidate LibreChat owner state appeared",
    ):
        module.rollback(args)

    assert injected is True
    assert candidate_env.read_bytes() == concurrent
    assert (runtime / "runtime.env").read_bytes() == before_runtime
    assert checkout.read_bytes() == before_checkout
    current = run_tool(
        "status",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    assert current["status"] == "prepared"


@pytest.mark.parametrize(
    "status",
    ["publishing", "runtime_backed_up", "published", "binding_applied"],
)
def test_missing_original_runtime_backup_never_reports_rolled_back(
    tmp_path: Path,
    status: str,
) -> None:
    support, runtime, transaction, checkout, _ = prepare(tmp_path)
    published = run_tool(
        "publish",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    backup = Path(str(published["runtimeBackup"]))
    staging = Path(str(published["runtimeStaging"]))
    manifest_path = transaction / "activation.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if status in {"publishing", "runtime_backed_up"}:
        os.replace(runtime, staging)
    manifest["status"] = status
    manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")
    manifest_path.chmod(0o600)
    checkout.write_text('{"repoRoot":"/candidate"}\n', encoding="utf-8")
    shutil.rmtree(backup)

    completed = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "rollback",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "rollback backup is unavailable" in completed.stderr
    assert checkout.read_text(encoding="utf-8") == '{"repoRoot":"/candidate"}\n'
    current = run_tool(
        "status",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    assert current["status"] == status
    if status in {"published", "binding_applied"}:
        assert (runtime / "runtime.env").read_text(encoding="utf-8") == "VERSION=new\n"
    else:
        assert not runtime.exists()
        assert (staging / "runtime.env").read_text(encoding="utf-8") == "VERSION=new\n"


def test_core_commit_is_not_rollbackable_while_helper_refresh_is_pending(
    tmp_path: Path,
) -> None:
    support, runtime, transaction, checkout, helper = prepare(tmp_path)
    run_tool(
        "publish",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    checkout.write_text('{"repoRoot":"/candidate"}\n', encoding="utf-8")
    run_tool(
        "binding-applied",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )

    core_committed = run_tool(
        "commit",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    assert core_committed["status"] == "core_committed"
    rollback = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "rollback",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert rollback.returncode != 0
    assert "cannot roll back" in rollback.stderr
    assert (runtime / "runtime.env").read_text(encoding="utf-8") == "VERSION=new\n"
    assert checkout.read_text(encoding="utf-8") == '{"repoRoot":"/candidate"}\n'

    committed = run_tool(
        "finalize-helper",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    assert committed["status"] == "committed"
    assert (runtime / "runtime.env").read_text(encoding="utf-8") == "VERSION=new\n"
    assert checkout.read_text(encoding="utf-8") == '{"repoRoot":"/candidate"}\n'
    assert not list(runtime.parent.glob(f".{runtime.name}.viventium-backup-*"))


def test_commit_acceptance_boundary_preserves_a_concurrent_owner_rotation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    planned = b"CREDS_KEY=established\nOWNER_NOTE=established\n"
    rotated = b"CREDS_KEY=rotated-after-claim\nOWNER_NOTE=concurrent\n"
    support, runtime, transaction, checkout, _ = prepare(tmp_path)
    plan_owner_env(support, transaction, planned)
    payload = run_tool(
        "status",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    candidate_env = (
        Path(str(payload["candidateEnv"]["repoRoot"]))
        / "viventium_v0_4"
        / "LibreChat"
        / ".env"
    )
    candidate_env.write_bytes(planned)
    run_tool(
        "publish",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    checkout.write_text('{"repoRoot":"/candidate"}\n', encoding="utf-8")
    run_tool(
        "binding-applied",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )

    module = load_module()
    original_write = module.write_json
    injected = False

    def inject_after_acceptance(path, manifest, boundary):
        nonlocal injected
        original_write(path, manifest, boundary)
        if manifest.get("status") == "commit_env_accepted" and not injected:
            candidate_env.write_bytes(rotated)
            injected = True

    monkeypatch.setattr(module, "write_json", inject_after_acceptance)
    args = module.build_parser().parse_args(
        [
            "commit",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ]
    )
    with pytest.raises(
        module.ActivationError,
        match="Concurrent candidate LibreChat owner state appeared",
    ):
        module.commit(args)

    assert injected is True
    assert candidate_env.read_bytes() == rotated
    assert (runtime / "runtime.env").read_text(encoding="utf-8") == "VERSION=new\n"
    assert checkout.read_text(encoding="utf-8") == '{"repoRoot":"/candidate"}\n'
    current = run_tool(
        "status",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    assert current["status"] == "commit_env_accepted"
    retry = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "commit",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert retry.returncode != 0
    assert "Only a bound activation can commit" in retry.stderr
    assert candidate_env.read_bytes() == rotated


def test_commit_accepts_and_cleans_exact_transaction_materialization_links(
    tmp_path: Path,
) -> None:
    planned = b"CREDS_KEY=established\nOWNER_NOTE=established\n"
    support, runtime, transaction, checkout, _ = prepare(tmp_path)
    plan_owner_env(support, transaction, planned)
    payload = run_tool(
        "status",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    record = payload["candidateEnv"]
    candidate_env = (
        Path(str(record["repoRoot"]))
        / "viventium_v0_4"
        / "LibreChat"
        / ".env"
    )
    materialized = candidate_env.with_name(
        payload["ownerEnvPlan"]["materializationTargetName"]
    )
    accepted = candidate_env.with_name(record["commitAcceptanceName"])
    run_tool(
        "publish",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    checkout.write_text('{"repoRoot":"/candidate"}\n', encoding="utf-8")
    run_tool(
        "binding-applied",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )

    committed = run_tool(
        "commit",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )

    assert committed["status"] == "core_committed"
    assert candidate_env.read_bytes() == planned
    assert not materialized.exists()
    assert not accepted.exists()
    retirement_slots = tuple(
        candidate_env.with_name(record[field])
        for field in (
            "materializationRetirementName",
            "ownerEnvRetirementName",
            "retirementTombstoneName",
        )
    )
    assert all(slot.read_bytes() == b"" for slot in retirement_slots)
    assert all(slot.stat().st_nlink == 1 for slot in retirement_slots)
    assert all(
        slot.stat().st_ino != candidate_env.stat().st_ino
        for slot in retirement_slots
    )
    replacement = candidate_env.with_name(".env.synthetic-after-commit-save")
    replacement.write_bytes(b"CREDS_KEY=rotated-after-commit\n")
    replacement.chmod(0o600)
    os.replace(replacement, candidate_env)
    assert all(slot.read_bytes() == b"" for slot in retirement_slots)
    assert (runtime / "runtime.env").read_text(encoding="utf-8") == "VERSION=new\n"


@pytest.mark.parametrize(
    ("replacement", "expected"),
    [
        (
            b"CREDS_KEY=established\nOWNER_NOTE=established\nPORT=3180\n",
            b"CREDS_KEY=established\nOWNER_NOTE=established\nPORT=3180\n",
        ),
        (
            b"CREDS_KEY=established\nOWNER_NOTE=established\nPORT=3199\n",
            b"CREDS_KEY=established\nOWNER_NOTE=established\nPORT=3199\n",
        ),
    ],
    ids=("same-content", "managed-port"),
)
def test_commit_accepts_allowed_atomic_owner_env_rewrite_after_candidate_start(
    tmp_path: Path,
    replacement: bytes,
    expected: bytes,
) -> None:
    planned = b"CREDS_KEY=established\nOWNER_NOTE=established\nPORT=3180\n"
    support, runtime, transaction, checkout, _ = prepare(
        tmp_path,
        candidate_env=planned,
    )
    plan_owner_env(support, transaction, planned)
    payload = run_tool(
        "status",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    record = payload["candidateEnv"]
    candidate_env = (
        Path(str(record["repoRoot"]))
        / "viventium_v0_4"
        / "LibreChat"
        / ".env"
    )
    materialized = candidate_env.with_name(
        payload["ownerEnvPlan"]["materializationTargetName"]
    )
    original_materialized_inode = materialized.stat().st_ino
    run_tool(
        "publish",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    checkout.write_text('{"repoRoot":"/candidate"}\n', encoding="utf-8")
    run_tool(
        "binding-applied",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    atomic_save = candidate_env.with_name(".env.synthetic-launcher-save")
    atomic_save.write_bytes(replacement)
    atomic_save.chmod(0o600)
    os.replace(atomic_save, candidate_env)
    assert candidate_env.stat().st_ino != original_materialized_inode

    committed = run_tool(
        "commit",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )

    assert committed["status"] == "core_committed"
    assert candidate_env.read_bytes() == expected
    assert not materialized.exists()
    assert not candidate_env.with_name(
        record["materializationClaimDirectoryName"]
    ).exists()
    assert (runtime / "runtime.env").read_text(encoding="utf-8") == "VERSION=new\n"


@pytest.mark.parametrize(
    "replacement",
    (
        b"CREDS_KEY=rotated-outside-plan\nOWNER_NOTE=established\nPORT=3180\n",
        b"CREDS_KEY=established\nOWNER_NOTE=established\nPORT=3180\nUNKNOWN_OWNER_FIELD=changed\n",
    ),
    ids=("protected-field", "unknown-field"),
)
def test_commit_rejects_owner_env_rewrite_outside_activation_plan(
    tmp_path: Path,
    replacement: bytes,
) -> None:
    planned = b"CREDS_KEY=established\nOWNER_NOTE=established\nPORT=3180\n"
    support, _, transaction, checkout, _ = prepare(
        tmp_path,
        candidate_env=planned,
    )
    plan_owner_env(support, transaction, planned)
    payload = run_tool(
        "status",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    record = payload["candidateEnv"]
    candidate_env = (
        Path(str(record["repoRoot"]))
        / "viventium_v0_4"
        / "LibreChat"
        / ".env"
    )
    run_tool(
        "publish",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    checkout.write_text('{"repoRoot":"/candidate"}\n', encoding="utf-8")
    run_tool(
        "binding-applied",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    atomic_save = candidate_env.with_name(".env.synthetic-owner-edit")
    atomic_save.write_bytes(replacement)
    atomic_save.chmod(0o600)
    os.replace(atomic_save, candidate_env)

    completed = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "commit",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "changed outside the activation plan" in completed.stderr
    assert candidate_env.read_bytes() == replacement


def test_commit_claim_never_renames_owner_env_artifact_into_app_support(
    tmp_path: Path,
    monkeypatch,
) -> None:
    planned = b"CREDS_KEY=established\nOWNER_NOTE=established\n"
    support, _, transaction, checkout, _ = prepare(tmp_path)
    plan_owner_env(support, transaction, planned)
    run_tool(
        "publish",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    checkout.write_text('{"repoRoot":"/candidate"}\n', encoding="utf-8")
    run_tool(
        "binding-applied",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    module = load_module()
    real_move = module.atomic_rename_no_replace_between
    transaction_inode = transaction.stat().st_ino
    observed_moves: list[tuple[int, int]] = []

    def reject_app_support_cross_volume_claim(
        source_directory_descriptor,
        source_name,
        destination_directory_descriptor,
        destination_name,
    ):
        source = os.fstat(source_directory_descriptor)
        destination = os.fstat(destination_directory_descriptor)
        observed_moves.append((source.st_dev, destination.st_dev))
        if destination.st_ino == transaction_inode:
            raise OSError(errno.EXDEV, "synthetic cross-device claim refusal")
        assert source.st_dev == destination.st_dev
        return real_move(
            source_directory_descriptor,
            source_name,
            destination_directory_descriptor,
            destination_name,
        )

    monkeypatch.setattr(
        module,
        "atomic_rename_no_replace_between",
        reject_app_support_cross_volume_claim,
    )
    args = module.build_parser().parse_args(
        [
            "commit",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ]
    )

    assert module.commit(args)["status"] == "core_committed"
    assert observed_moves
    assert all(source == destination for source, destination in observed_moves)


def test_commit_claim_empty_private_directory_cleanup_is_retryable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    planned = b"CREDS_KEY=established\nOWNER_NOTE=established\n"
    support, _, transaction, checkout, _ = prepare(tmp_path)
    plan_owner_env(support, transaction, planned)
    payload = run_tool(
        "status",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    record = payload["candidateEnv"]
    candidate_env = (
        Path(str(record["repoRoot"]))
        / "viventium_v0_4"
        / "LibreChat"
        / ".env"
    )
    claim_directory = candidate_env.with_name(
        record["materializationClaimDirectoryName"]
    )
    run_tool(
        "publish",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    checkout.write_text('{"repoRoot":"/candidate"}\n', encoding="utf-8")
    run_tool(
        "binding-applied",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    module = load_module()
    real_rmdir = module.os.rmdir
    interrupted = False

    def interrupt_first_claim_directory_removal(path, *args, **kwargs):
        nonlocal interrupted
        if not interrupted and path == record["materializationClaimDirectoryName"]:
            interrupted = True
            raise OSError("synthetic interruption before private directory removal")
        return real_rmdir(path, *args, **kwargs)

    monkeypatch.setattr(module.os, "rmdir", interrupt_first_claim_directory_removal)
    commit_args = module.build_parser().parse_args(
        [
            "commit",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ]
    )

    assert module.commit(commit_args)["status"] == "core_committed"
    assert interrupted is True
    assert claim_directory.is_dir()
    assert not list(claim_directory.iterdir())
    alignment_args = module.build_parser().parse_args(
        [
            "alignment-status",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ]
    )
    assert module.alignment_status(alignment_args)["required"] is False
    assert not claim_directory.exists()


def test_commit_private_cleanup_claim_detects_racing_replacement(
    tmp_path: Path,
    monkeypatch,
) -> None:
    planned = b"CREDS_KEY=established\nOWNER_NOTE=established\n"
    racing = b"CREDS_KEY=racing-cleanup-artifact\nOWNER_NOTE=preserve\n"
    support, _, transaction, checkout, _ = prepare(tmp_path)
    plan_owner_env(support, transaction, planned)
    payload = run_tool(
        "status",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    record = payload["candidateEnv"]
    candidate_env = (
        Path(str(record["repoRoot"]))
        / "viventium_v0_4"
        / "LibreChat"
        / ".env"
    )
    claim_directory = candidate_env.with_name(
        record["materializationClaimDirectoryName"]
    )
    original_anchor = candidate_env.with_name(".env.synthetic-cleanup-anchor")
    racing_source = candidate_env.with_name(".env.synthetic-cleanup-racing")
    racing_source.write_bytes(racing)
    racing_source.chmod(0o600)
    run_tool(
        "publish",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    checkout.write_text('{"repoRoot":"/candidate"}\n', encoding="utf-8")
    run_tool(
        "binding-applied",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )

    module = load_module()
    real_claim = module.atomic_rename_no_replace_at
    injected = False

    def replace_before_cleanup_claim(
        directory_descriptor,
        source_name,
        destination_name,
    ):
        nonlocal injected
        if (
            not injected
            and source_name == "owner.env"
            and destination_name == "deleting.env"
        ):
            os.rename(claim_directory / "owner.env", original_anchor)
            os.rename(racing_source, claim_directory / "owner.env")
            injected = True
        return real_claim(
            directory_descriptor,
            source_name,
            destination_name,
        )

    monkeypatch.setattr(
        module,
        "atomic_rename_no_replace_at",
        replace_before_cleanup_claim,
    )
    args = module.build_parser().parse_args(
        [
            "commit",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ]
    )

    assert module.commit(args)["status"] == "core_committed"
    assert injected is True
    assert original_anchor.read_bytes() == planned
    assert (claim_directory / "deleting.env").read_bytes() == racing
    assert not racing_source.exists()
    alignment_args = module.build_parser().parse_args(
        [
            "alignment-status",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ]
    )
    finalize_args = module.build_parser().parse_args(
        [
            "finalize-helper",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ]
    )
    alignment = module.alignment_status(alignment_args)
    assert alignment["required"] is False
    assert alignment["cleanupState"] == "pending"
    with pytest.raises(
        module.ActivationError,
        match="cleanup remains pending",
    ):
        module.finalize_helper(finalize_args)
    assert (claim_directory / "deleting.env").read_bytes() == racing


def test_commit_materialization_no_replace_claim_detects_racing_replacement(
    tmp_path: Path,
    monkeypatch,
) -> None:
    planned = b"CREDS_KEY=established\nOWNER_NOTE=established\n"
    racing = b"CREDS_KEY=racing-artifact\nOWNER_NOTE=must-not-bless\n"
    support, _, transaction, checkout, _ = prepare(tmp_path)
    plan_owner_env(support, transaction, planned)
    payload = run_tool(
        "status",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    record = payload["candidateEnv"]
    candidate_env = (
        Path(str(record["repoRoot"]))
        / "viventium_v0_4"
        / "LibreChat"
        / ".env"
    )
    materialized = candidate_env.with_name(
        payload["ownerEnvPlan"]["materializationTargetName"]
    )
    original_anchor = candidate_env.with_name(".env.synthetic-original-anchor")
    racing_source = candidate_env.with_name(".env.synthetic-racing-artifact")
    claim_directory = candidate_env.with_name(
        record["materializationClaimDirectoryName"]
    )
    racing_source.write_bytes(racing)
    racing_source.chmod(0o600)
    run_tool(
        "publish",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    checkout.write_text('{"repoRoot":"/candidate"}\n', encoding="utf-8")
    run_tool(
        "binding-applied",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    module = load_module()
    real_move = module.atomic_rename_no_replace_between
    injected = False

    def replace_during_claim(
        source_directory_descriptor,
        source_name,
        destination_directory_descriptor,
        destination_name,
    ):
        nonlocal injected
        if (
            not injected
            and source_name == materialized.name
            and destination_name == "owner.env"
        ):
            os.rename(materialized, original_anchor)
            os.rename(racing_source, materialized)
            injected = True
        return real_move(
            source_directory_descriptor,
            source_name,
            destination_directory_descriptor,
            destination_name,
        )

    monkeypatch.setattr(
        module,
        "atomic_rename_no_replace_between",
        replace_during_claim,
    )
    args = module.build_parser().parse_args(
        [
            "commit",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ]
    )

    with pytest.raises(
        module.ActivationError,
        match="materialization receipt changed",
    ):
        module.commit(args)

    assert injected is True
    assert candidate_env.read_bytes() == planned
    assert original_anchor.read_bytes() == planned
    assert (claim_directory / "owner.env").read_bytes() == racing


def test_post_acceptance_owner_edit_is_preserved_and_requires_alignment_restart(
    tmp_path: Path,
    monkeypatch,
) -> None:
    planned = b"CREDS_KEY=established\nOWNER_NOTE=established\n"
    rotated = b"CREDS_KEY=rotated\nOWNER_NOTE=post-boundary-edit\n"
    support, _, transaction, checkout, _ = prepare(tmp_path)
    plan_owner_env(support, transaction, planned)
    payload = run_tool(
        "status",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    record = payload["candidateEnv"]
    candidate_env = (
        Path(str(record["repoRoot"]))
        / "viventium_v0_4"
        / "LibreChat"
        / ".env"
    )
    materialized = candidate_env.with_name(
        payload["ownerEnvPlan"]["materializationTargetName"]
    )
    accepted = candidate_env.with_name(record["commitAcceptanceName"])
    run_tool(
        "publish",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    checkout.write_text('{"repoRoot":"/candidate"}\n', encoding="utf-8")
    run_tool(
        "binding-applied",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )

    module = load_module()
    original_validate = module.validate_accepted_candidate_env_target
    validations = 0

    def edit_after_first_acceptance_boundary(record, manifest, transaction_dir):
        nonlocal validations
        validations += 1
        result = original_validate(record, manifest, transaction_dir)
        if validations == 1:
            replacement = candidate_env.with_name(".env.owner-atomic-save")
            replacement.write_bytes(rotated)
            replacement.chmod(0o600)
            os.replace(replacement, candidate_env)
        return result

    monkeypatch.setattr(
        module,
        "validate_accepted_candidate_env_target",
        edit_after_first_acceptance_boundary,
    )
    args = module.build_parser().parse_args(
        [
            "commit",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ]
    )
    committed = module.commit(args)

    assert validations == 2
    assert committed["status"] == "core_committed"
    assert committed["ownerEnvChangedAfterAcceptance"] is True
    assert candidate_env.read_bytes() == rotated
    assert not accepted.exists()
    assert not materialized.exists()
    alignment_args = module.build_parser().parse_args(
        [
            "alignment-status",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ]
    )
    alignment = module.alignment_status(alignment_args)
    assert alignment["required"] is True
    expected_receipt = json.dumps(alignment["currentReceipt"], sort_keys=True)
    finalize_args = module.build_parser().parse_args(
        [
            "finalize-helper",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ]
    )
    with pytest.raises(
        module.ActivationError,
        match="alignment restart",
    ):
        module.finalize_helper(finalize_args)
    mark_args = module.build_parser().parse_args(
        [
            "mark-aligned",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
            "--expected-receipt-json",
            expected_receipt,
        ]
    )
    module.mark_aligned(mark_args)
    assert module.alignment_status(alignment_args)["required"] is False
    assert module.finalize_helper(finalize_args)["status"] == "committed"


def test_mark_aligned_rejects_owner_edit_during_alignment_restart(
    tmp_path: Path,
    monkeypatch,
) -> None:
    planned = b"CREDS_KEY=established\nOWNER_NOTE=established\n"
    rotated = b"CREDS_KEY=rotated\nOWNER_NOTE=owner-edit\n"
    support, runtime, transaction, checkout, _ = prepare(tmp_path)
    plan_owner_env(support, transaction, planned)
    activation = run_tool(
        "status",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    candidate_env = (
        Path(activation["candidateEnv"]["repoRoot"])
        / "viventium_v0_4"
        / "LibreChat"
        / ".env"
    )
    materialized = candidate_env.with_name(
        activation["ownerEnvPlan"]["materializationTargetName"]
    )
    run_tool(
        "publish",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    checkout.write_text('{"repoRoot":"/candidate"}\n', encoding="utf-8")
    run_tool(
        "binding-applied",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )

    module = load_module()
    validations = 0
    original_validate = module.validate_accepted_candidate_env_target

    def edit_after_first_acceptance_boundary(*args, **kwargs):
        nonlocal validations
        validations += 1
        result = original_validate(*args, **kwargs)
        if validations == 1:
            replacement = candidate_env.with_name(".env.owner-atomic-save")
            replacement.write_bytes(rotated)
            replacement.chmod(0o600)
            os.replace(replacement, candidate_env)
        return result

    monkeypatch.setattr(
        module,
        "validate_accepted_candidate_env_target",
        edit_after_first_acceptance_boundary,
    )
    commit_args = module.build_parser().parse_args(
        [
            "commit",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ]
    )
    module.commit(commit_args)
    alignment_args = module.build_parser().parse_args(
        [
            "alignment-status",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ]
    )
    alignment = module.alignment_status(alignment_args)
    expected_receipt = json.dumps(alignment["currentReceipt"], sort_keys=True)

    second_edit = b"CREDS_KEY=second\nOWNER_NOTE=during-restart\n"
    replacement = candidate_env.with_name(".env.owner-second-atomic-save")
    replacement.write_bytes(second_edit)
    replacement.chmod(0o600)
    os.replace(replacement, candidate_env)
    mark_args = module.build_parser().parse_args(
        [
            "mark-aligned",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
            "--expected-receipt-json",
            expected_receipt,
        ]
    )
    with pytest.raises(
        module.ActivationError,
        match="changed during the alignment restart",
    ):
        module.mark_aligned(mark_args)
    assert candidate_env.read_bytes() == second_edit
    assert module.alignment_status(alignment_args)["required"] is True


def test_mark_aligned_accepts_same_content_launcher_atomic_rewrite(
    tmp_path: Path,
    monkeypatch,
) -> None:
    planned = b"CREDS_KEY=established\nOWNER_NOTE=established\n"
    support, _, transaction, checkout, _ = prepare(tmp_path)
    plan_owner_env(support, transaction, planned)
    activation = run_tool(
        "status",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    candidate_env = (
        Path(activation["candidateEnv"]["repoRoot"])
        / "viventium_v0_4"
        / "LibreChat"
        / ".env"
    )
    materialized = candidate_env.with_name(
        activation["ownerEnvPlan"]["materializationTargetName"]
    )
    run_tool(
        "publish",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    checkout.write_text('{"repoRoot":"/candidate"}\n', encoding="utf-8")
    run_tool(
        "binding-applied",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )

    module = load_module()
    validations = 0
    original_validate = module.validate_accepted_candidate_env_target

    def require_alignment_after_acceptance(*args, **kwargs):
        nonlocal validations
        validations += 1
        result = original_validate(*args, **kwargs)
        if validations == 1:
            replacement = candidate_env.with_name(".env.owner-edit")
            replacement.write_bytes(
                b"CREDS_KEY=rotated\nOWNER_NOTE=post-boundary-edit\n"
            )
            replacement.chmod(0o600)
            os.replace(replacement, candidate_env)
        return result

    monkeypatch.setattr(
        module,
        "validate_accepted_candidate_env_target",
        require_alignment_after_acceptance,
    )
    commit_args = module.build_parser().parse_args(
        [
            "commit",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ]
    )
    module.commit(commit_args)
    alignment_args = module.build_parser().parse_args(
        [
            "alignment-status",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ]
    )
    alignment = module.alignment_status(alignment_args)
    expected_receipt = alignment["currentReceipt"]

    replacement = candidate_env.with_name(".env.launcher-rewrite")
    replacement.write_bytes(candidate_env.read_bytes())
    replacement.chmod(0o600)
    os.replace(replacement, candidate_env)
    assert candidate_env.stat().st_ino != expected_receipt["inode"]

    mark_args = module.build_parser().parse_args(
        [
            "mark-aligned",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
            "--expected-receipt-json",
            json.dumps(expected_receipt, sort_keys=True),
        ]
    )
    module.mark_aligned(mark_args)
    assert module.alignment_status(alignment_args)["required"] is False


def test_crash_during_commit_env_finalizing_rolls_back_exactly(
    tmp_path: Path,
    monkeypatch,
) -> None:
    planned = b"CREDS_KEY=established\nOWNER_NOTE=established\n"
    support, runtime, transaction, checkout, _ = prepare(tmp_path)
    plan_owner_env(support, transaction, planned)
    payload = run_tool(
        "status",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    candidate_env = (
        Path(str(payload["candidateEnv"]["repoRoot"]))
        / "viventium_v0_4"
        / "LibreChat"
        / ".env"
    )
    candidate_env.write_bytes(planned)
    run_tool(
        "publish",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    checkout.write_text('{"repoRoot":"/candidate"}\n', encoding="utf-8")
    run_tool(
        "binding-applied",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )

    module = load_module()
    original_write = module.write_json

    def crash_after_finalizing_receipt(path, manifest, boundary):
        original_write(path, manifest, boundary)
        if manifest.get("status") == "commit_env_finalizing":
            raise OSError("synthetic crash during final acceptance")

    monkeypatch.setattr(module, "write_json", crash_after_finalizing_receipt)
    args = module.build_parser().parse_args(
        [
            "commit",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ]
    )
    with pytest.raises(OSError, match="synthetic crash"):
        module.commit(args)
    current = run_tool(
        "status",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    assert current["status"] == "commit_env_finalizing"

    rolled_back = run_tool(
        "rollback",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )

    assert rolled_back["status"] == "rolled_back"
    assert not candidate_env.exists()
    assert (runtime / "runtime.env").read_text(encoding="utf-8") == "VERSION=old\n"
    assert checkout.read_text(encoding="utf-8") == '{"repoRoot":"/old"}\n'


def test_core_commit_crash_recovery_detects_atomic_owner_edit_before_finalization(
    tmp_path: Path,
    monkeypatch,
) -> None:
    planned = b"CREDS_KEY=established\nOWNER_NOTE=established\n"
    rotated = b"CREDS_KEY=rotated\nOWNER_NOTE=crash-window-save\n"
    support, _, transaction, checkout, _ = prepare(tmp_path)
    plan_owner_env(support, transaction, planned)
    payload = run_tool(
        "status",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    record = payload["candidateEnv"]
    candidate_env = (
        Path(str(record["repoRoot"]))
        / "viventium_v0_4"
        / "LibreChat"
        / ".env"
    )
    materialized = candidate_env.with_name(
        payload["ownerEnvPlan"]["materializationTargetName"]
    )
    accepted = candidate_env.with_name(record["commitAcceptanceName"])
    run_tool(
        "publish",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    checkout.write_text('{"repoRoot":"/candidate"}\n', encoding="utf-8")
    run_tool(
        "binding-applied",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )

    module = load_module()
    original_write = module.write_json

    def crash_after_core_receipt(path, manifest, boundary):
        original_write(path, manifest, boundary)
        if manifest.get("status") == "core_committed":
            replacement = candidate_env.with_name(".env.owner-atomic-save")
            replacement.write_bytes(rotated)
            replacement.chmod(0o600)
            os.replace(replacement, candidate_env)
            raise OSError("synthetic crash after core receipt")

    monkeypatch.setattr(module, "write_json", crash_after_core_receipt)
    commit_args = module.build_parser().parse_args(
        [
            "commit",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ]
    )
    with pytest.raises(OSError, match="synthetic crash"):
        module.commit(commit_args)
    current = run_tool(
        "status",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    assert current["status"] == "core_committed"
    assert candidate_env.read_bytes() == rotated

    alignment_args = module.build_parser().parse_args(
        [
            "alignment-status",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ]
    )
    assert module.alignment_status(alignment_args)["required"] is True
    assert not accepted.exists()
    assert not materialized.exists()
    finalize_args = module.build_parser().parse_args(
        [
            "finalize-helper",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ]
    )
    with pytest.raises(module.ActivationError, match="alignment restart"):
        module.finalize_helper(finalize_args)


def test_commit_rejects_same_inode_owner_mutation_after_acceptance_link(
    tmp_path: Path,
    monkeypatch,
) -> None:
    planned = b"CREDS_KEY=established\nOWNER_NOTE=established\n"
    rotated = b"CREDS_KEY=rotated\nOWNER_NOTE=owner-edit\n"
    support, runtime, transaction, checkout, _ = prepare(tmp_path)
    plan_owner_env(support, transaction, planned)
    payload = run_tool(
        "status",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    candidate_env = (
        Path(str(payload["candidateEnv"]["repoRoot"]))
        / "viventium_v0_4"
        / "LibreChat"
        / ".env"
    )
    candidate_env.write_bytes(planned)
    run_tool(
        "publish",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    checkout.write_text('{"repoRoot":"/candidate"}\n', encoding="utf-8")
    run_tool(
        "binding-applied",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )

    module = load_module()
    original_link = module.os.link
    injected = False

    def mutate_after_acceptance_link(*args, **kwargs):
        nonlocal injected
        result = original_link(*args, **kwargs)
        if kwargs.get("dst_dir_fd") is not None and args[1] == ".env":
            candidate_env.write_bytes(rotated)
            injected = True
        return result

    monkeypatch.setattr(module.os, "link", mutate_after_acceptance_link)
    args = module.build_parser().parse_args(
        [
            "commit",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ]
    )
    with pytest.raises(
        module.ActivationError,
        match="changed after commit acceptance",
    ):
        module.commit(args)

    assert injected is True
    assert candidate_env.read_bytes() == rotated
    current = run_tool(
        "status",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    assert current["status"] == "commit_env_accepted"
    assert (runtime / "runtime.env").read_text(encoding="utf-8") == "VERSION=new\n"


def test_nested_revision_change_blocks_publish_but_not_rollback(
    tmp_path: Path,
) -> None:
    planned = b"CREDS_KEY=established\nOWNER_NOTE=established\n"
    support, runtime, transaction, checkout, _ = prepare(tmp_path)
    plan_owner_env(support, transaction, planned)
    payload = run_tool(
        "status",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    repo = Path(str(payload["candidateEnv"]["repoRoot"]))
    candidate_env = repo / "viventium_v0_4" / "LibreChat" / ".env"
    candidate_env.write_bytes(planned)
    librechat = repo / "viventium_v0_4" / "LibreChat"
    (librechat / "marker").write_text("changed-before-publish\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(librechat), "add", "marker"], check=True)
    subprocess.run(
        ["git", "-C", str(librechat), "commit", "-qm", "changed-before-publish"],
        check=True,
    )

    publish = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "publish",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert publish.returncode != 0
    assert "checkout revision changed" in publish.stderr
    assert (runtime / "runtime.env").read_text(encoding="utf-8") == "VERSION=old\n"

    rolled_back = run_tool(
        "rollback",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    assert rolled_back["status"] == "rolled_back"
    assert not candidate_env.exists()
    assert checkout.read_text(encoding="utf-8") == '{"repoRoot":"/old"}\n'


def test_nested_revision_change_after_publish_blocks_commit_and_rolls_back(
    tmp_path: Path,
) -> None:
    planned = b"CREDS_KEY=established\nOWNER_NOTE=established\n"
    support, runtime, transaction, checkout, _ = prepare(tmp_path)
    plan_owner_env(support, transaction, planned)
    payload = run_tool(
        "status",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    repo = Path(str(payload["candidateEnv"]["repoRoot"]))
    candidate_env = repo / "viventium_v0_4" / "LibreChat" / ".env"
    candidate_env.write_bytes(planned)
    run_tool(
        "publish",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    checkout.write_text('{"repoRoot":"/candidate"}\n', encoding="utf-8")
    run_tool(
        "binding-applied",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    librechat = repo / "viventium_v0_4" / "LibreChat"
    (librechat / "marker").write_text("changed-before-commit\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(librechat), "add", "marker"], check=True)
    subprocess.run(
        ["git", "-C", str(librechat), "commit", "-qm", "changed-before-commit"],
        check=True,
    )

    commit = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "commit",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert commit.returncode != 0
    assert "checkout revision changed" in commit.stderr
    assert (runtime / "runtime.env").read_text(encoding="utf-8") == "VERSION=new\n"

    rolled_back = run_tool(
        "rollback",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    assert rolled_back["status"] == "rolled_back"
    assert (runtime / "runtime.env").read_text(encoding="utf-8") == "VERSION=old\n"
    assert checkout.read_text(encoding="utf-8") == '{"repoRoot":"/old"}\n'


def test_core_commit_restores_helper_intent_without_drifting_unknown_fields(
    tmp_path: Path,
) -> None:
    support, runtime, transaction, checkout, helper = prepare(tmp_path)
    original = {
        "showInStatusBar": False,
        "privateOwnerSetting": {"keep": True},
        "runtimeSupervision": {
            "schemaVersion": 1,
            "desiredState": "running",
            "consecutiveLaunchAttempts": 7,
            "nextLaunchAttemptAt": "2026-07-24T12:00:00Z",
            "healthySince": "2026-07-24T11:00:00Z",
            "privateNestedSetting": "keep-old",
        },
    }
    helper.write_text(json.dumps(original) + "\n", encoding="utf-8")
    # Recreate the transaction so its snapshot contains the richer owner state.
    shutil.rmtree(transaction)
    transaction.mkdir()
    candidate = transaction / "candidate-runtime"
    candidate.mkdir()
    (candidate / "runtime.env").write_text("VERSION=new\n", encoding="utf-8")
    candidate_repo = make_candidate_repo(tmp_path)
    run_tool(
        "begin",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
        "--candidate-runtime",
        candidate,
        "--runtime-dir",
        runtime,
        "--runtime-checkout-file",
        checkout,
        "--helper-config-file",
        helper,
        "--previous-repo",
        REPO_ROOT,
        "--candidate-repo",
        candidate_repo,
        "--no-was-running",
    )
    run_tool(
        "quiesce-helper",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    if sys.platform == "darwin":
        run_tool(
            "quiesce-helper-process",
            "--transaction-dir",
            transaction,
            "--app-support-dir",
            support,
            "--helper-executable",
            tmp_path
            / "Viventium.app"
            / "Contents"
            / "MacOS"
            / "ViventiumHelper",
        )
    run_tool(
        "publish",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    checkout.write_text('{"repoRoot":"/candidate"}\n', encoding="utf-8")
    concurrent_helper = json.loads(helper.read_text(encoding="utf-8"))
    concurrent_helper["concurrentTopLevelSetting"] = "keep-new"
    concurrent_helper["runtimeSupervision"]["concurrentNestedSetting"] = "keep-new"
    helper.write_text(json.dumps(concurrent_helper) + "\n", encoding="utf-8")
    run_tool(
        "binding-applied",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )

    committed = run_tool(
        "commit",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )

    assert committed["status"] == "core_committed"
    restored = json.loads(helper.read_text(encoding="utf-8"))
    assert restored["showInStatusBar"] is False
    assert restored["privateOwnerSetting"] == {"keep": True}
    assert restored["concurrentTopLevelSetting"] == "keep-new"
    assert restored["runtimeSupervision"] == {
        "schemaVersion": 1,
        "desiredState": "running",
        "consecutiveLaunchAttempts": 7,
        "nextLaunchAttemptAt": "2026-07-24T12:00:00Z",
        "healthySince": "2026-07-24T11:00:00Z",
        "privateNestedSetting": "keep-old",
        "concurrentNestedSetting": "keep-new",
    }
    assert helper.stat().st_mode & 0o777 == 0o600


def test_postcommit_backup_identity_race_does_not_trigger_split_brain_rollback(
    tmp_path: Path, monkeypatch
) -> None:
    support, runtime, transaction, checkout, helper = prepare(tmp_path)
    published = run_tool(
        "publish",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    checkout.write_text('{"repoRoot":"/candidate"}\n', encoding="utf-8")
    run_tool(
        "binding-applied",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    module = load_module()
    original_write = module.write_json
    backup = Path(str(published["runtimeBackup"]))
    outside = tmp_path / "unrelated"
    outside.mkdir()
    sentinel = outside / "sentinel"
    sentinel.write_text("keep\n", encoding="utf-8")
    def replace_backup_after_commit(path, payload, boundary):
        original_write(path, payload, boundary)
        if payload.get("status") == "core_committed":
            shutil.rmtree(backup)
            backup.symlink_to(outside, target_is_directory=True)

    monkeypatch.setattr(module, "write_json", replace_backup_after_commit)
    args = module.build_parser().parse_args(
        [
            "commit",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ]
    )
    core_committed = module.commit(args)

    assert core_committed["status"] == "core_committed"
    assert (runtime / "runtime.env").read_text(encoding="utf-8") == "VERSION=new\n"
    assert checkout.read_text(encoding="utf-8") == '{"repoRoot":"/candidate"}\n'
    assert sentinel.read_text(encoding="utf-8") == "keep\n"


def test_activation_rejects_transaction_outside_app_support(tmp_path: Path) -> None:
    support = tmp_path / "support"
    outside = tmp_path / "outside"
    candidate = outside / "candidate"
    candidate.mkdir(parents=True)
    completed = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "begin",
            "--transaction-dir",
            str(outside),
            "--app-support-dir",
            str(support),
            "--candidate-runtime",
            str(candidate),
            "--runtime-dir",
            str(support / "runtime"),
            "--runtime-checkout-file",
            str(support / "state" / "active-checkout.json"),
            "--helper-config-file",
            str(support / "helper-config.json"),
            "--previous-repo",
            str(REPO_ROOT),
            "--candidate-repo",
            str(REPO_ROOT),
            "--no-was-running",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode != 0
    assert "escapes its trusted boundary" in completed.stderr


def test_begin_new_allocates_candidate_and_manifest_in_one_transaction(
    tmp_path: Path,
) -> None:
    support = tmp_path / "support"
    state = support / "state"
    runtime = support / "runtime"
    checkout = state / "active-checkout.json"
    helper = support / "helper-config.json"
    candidate_repo = make_candidate_repo(tmp_path)
    state.mkdir(parents=True)
    runtime.mkdir()
    checkout.write_text('{"repoRoot":"/old"}\n', encoding="utf-8")
    helper.write_text(
        '{"runtimeSupervision":{"desiredState":"running"}}\n',
        encoding="utf-8",
    )
    recovery_selection = (
        state
        / "runtime-component-staging"
        / "telegram-viventium-predecessor.json.synthetic"
    )
    recovery_selection.parent.mkdir(mode=0o700)
    recovery_selection.write_text('{"synthetic":true}\n', encoding="utf-8")
    recovery_selection.chmod(0o600)

    begun = run_tool(
        "begin-new",
        "--transaction-parent",
        state,
        "--app-support-dir",
        support,
        "--runtime-dir",
        runtime,
        "--runtime-checkout-file",
        checkout,
        "--helper-config-file",
        helper,
        "--previous-repo",
        REPO_ROOT,
        "--candidate-repo",
        candidate_repo,
        "--telegram-recovery-selection",
        recovery_selection,
        "--no-was-running",
    )

    transaction = Path(str(begun["transactionDir"]))
    assert transaction.parent == state
    assert (transaction / "activation.json").is_file()
    assert Path(str(begun["candidateRuntime"])).is_dir()
    assert begun["telegramRecoverySelection"] == str(recovery_selection)
    assert not [
        path
        for path in state.glob("dev-runtime-activation.*")
        if not (path / "activation.json").is_file()
    ]


def test_begin_new_rejects_symlinked_app_support_before_any_external_write(
    tmp_path: Path,
) -> None:
    external_support = tmp_path / "external-support"
    state = external_support / "state"
    state.mkdir(parents=True)
    checkout = state / "active-checkout.json"
    checkout.write_text('{"repoRoot":"/old"}\n', encoding="utf-8")
    helper = external_support / "helper-config.json"
    helper.write_text(
        '{"runtimeSupervision":{"desiredState":"running"}}\n',
        encoding="utf-8",
    )
    support = tmp_path / "support"
    support.symlink_to(external_support, target_is_directory=True)
    candidate_repo = make_candidate_repo(tmp_path)
    before = {
        path.relative_to(external_support).as_posix(): (
            path.read_bytes() if path.is_file() else None
        )
        for path in external_support.rglob("*")
    }

    completed = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "begin-new",
            "--transaction-parent",
            str(support / "state"),
            "--app-support-dir",
            str(support),
            "--runtime-dir",
            str(support / "runtime"),
            "--runtime-checkout-file",
            str(support / "state" / "active-checkout.json"),
            "--helper-config-file",
            str(support / "helper-config.json"),
            "--previous-repo",
            str(REPO_ROOT),
            "--candidate-repo",
            str(candidate_repo),
            "--no-was-running",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    after = {
        path.relative_to(external_support).as_posix(): (
            path.read_bytes() if path.is_file() else None
        )
        for path in external_support.rglob("*")
    }

    assert completed.returncode != 0
    assert "symlink" in completed.stderr.lower()
    assert after == before
    assert not list(state.glob("dev-runtime-activation.*"))
    assert not (external_support / "runtime").exists()


@pytest.mark.parametrize("command", ["status", "publish", "rollback", "commit"])
def test_existing_activation_commands_reject_symlinked_app_support_chain(
    tmp_path: Path,
    command: str,
) -> None:
    external_support = tmp_path / "external-support"
    transaction = external_support / "state" / "dev-runtime-activation.synthetic"
    transaction.mkdir(parents=True)
    manifest = transaction / "activation.json"
    manifest.write_text("{}\n", encoding="utf-8")
    support = tmp_path / "support"
    support.symlink_to(external_support, target_is_directory=True)
    before = manifest.read_bytes()

    completed = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            command,
            "--transaction-dir",
            str(support / "state" / transaction.name),
            "--app-support-dir",
            str(support),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "symlink" in completed.stderr.lower()
    assert manifest.read_bytes() == before
    assert set(transaction.iterdir()) == {manifest}


def test_tampered_runtime_target_is_rejected_before_rollback_mutation(
    tmp_path: Path,
) -> None:
    support, runtime, transaction, checkout, helper = prepare(tmp_path)
    outside = tmp_path / "outside-runtime"
    outside.mkdir()
    sentinel = outside / "sentinel"
    sentinel.write_text("keep\n", encoding="utf-8")
    before_helper = helper.read_bytes()
    manifest_path = transaction / "activation.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["runtimeDir"] = str(outside)
    manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "rollback",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "outside the canonical App Support runtime" in completed.stderr
    assert sentinel.read_text(encoding="utf-8") == "keep\n"
    assert (runtime / "runtime.env").read_text(encoding="utf-8") == "VERSION=old\n"
    assert checkout.read_text(encoding="utf-8") == '{"repoRoot":"/old"}\n'
    assert helper.read_bytes() == before_helper


def test_activate_current_invalid_candidate_preserves_all_live_state(
    tmp_path: Path,
) -> None:
    candidate_repo, candidate_cli = make_isolated_activation_cli(tmp_path)
    support = tmp_path / "support"
    runtime = support / "runtime"
    state = support / "state"
    runtime.mkdir(parents=True)
    state.mkdir(parents=True)
    config = support / "config.yaml"
    checkout = state / "active-checkout.json"
    helper = support / "helper-config.json"
    previous_repo = tmp_path / "previous-checkout"
    previous_env = previous_repo / "viventium_v0_4" / "LibreChat" / ".env"
    previous_env.parent.mkdir(parents=True)
    candidate_env = candidate_repo / "viventium_v0_4" / "LibreChat" / ".env"
    suffix = "0123456789abcdefabcd"
    legacy_owner = candidate_env.with_name(
        f".env.viventium-retired-env-{suffix}"
    )
    legacy_materialization = candidate_env.with_name(
        f".env.viventium-retired-mat-{suffix}"
    )
    legacy_tombstone = candidate_env.with_name(
        f".env.viventium-retired-zero-{suffix}"
    )
    legacy_owner.write_bytes(b"CREDS_KEY=synthetic-retired-owner\n")
    legacy_owner.chmod(0o400)
    os.link(legacy_owner, legacy_materialization)
    legacy_tombstone.write_bytes(b"")
    legacy_tombstone.chmod(0o600)
    legacy_paths = (
        legacy_owner,
        legacy_materialization,
        legacy_tombstone,
    )
    legacy_before = tuple(
        (
            path.read_bytes(),
            path.stat().st_ino,
            path.stat().st_nlink,
            stat.S_IMODE(path.stat().st_mode),
            path.stat().st_mtime_ns,
        )
        for path in legacy_paths
    )
    previous_env.write_bytes(candidate_env.read_bytes())
    previous_env.chmod(0o600)
    config.write_text("version: invalid\n", encoding="utf-8")
    api_port, frontend_port, playground_port, sandpack_port = unused_local_ports(4)
    (runtime / "runtime.env").write_text(
        "LIVE_SENTINEL=1\n"
        f"VIVENTIUM_LC_API_PORT={api_port}\n"
        f"VIVENTIUM_LC_FRONTEND_PORT={frontend_port}\n"
        f"VIVENTIUM_PLAYGROUND_PORT={playground_port}\n"
        f"SANDPACK_BUNDLER_LISTEN_PORT={sandpack_port}\n",
        encoding="utf-8",
    )
    checkout.write_text(
        json.dumps(
            {
                "repoRoot": str(previous_repo),
                "allowProtectedFolderAccess": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    helper.write_text(
        '{"runtimeSupervision":{"desiredState":"stopped"}}\n',
        encoding="utf-8",
    )
    before = {
        "runtime": (runtime / "runtime.env").read_bytes(),
        "checkout": checkout.read_bytes(),
        "helper": helper.read_bytes(),
    }
    synthetic_home = tmp_path / "home"
    synthetic_tmp = tmp_path / "tmp"
    synthetic_helper_apps = tmp_path / "helper-apps"
    synthetic_home.mkdir()
    synthetic_tmp.mkdir()
    synthetic_helper_apps.mkdir()
    child_env = {
        "HOME": str(synthetic_home),
        "LANG": os.environ.get("LANG", "C"),
        "PATH": os.environ["PATH"],
        "TMPDIR": str(synthetic_tmp),
        "VIVENTIUM_APP_SUPPORT_DIR": str(support),
        "VIVENTIUM_BOOTSTRAP_PYTHON_ROOT": str(
            support / "state" / "bootstrap-python"
        ),
        "VIVENTIUM_CLI_LOCK_DIR": str(state / "cli-operation.lock"),
        "VIVENTIUM_COMPONENTS_LOCK_FILE": str(
            candidate_repo / "components.lock.json"
        ),
        "VIVENTIUM_CONFIG_FILE": str(config),
        "VIVENTIUM_HELPER_APP_BUNDLE": str(
            synthetic_helper_apps / "Viventium.app"
        ),
        "VIVENTIUM_HELPER_APP_DIR": str(synthetic_helper_apps),
        "VIVENTIUM_HELPER_LEGACY_APP_BUNDLE": str(
            synthetic_helper_apps / "Viventium Helper.app"
        ),
        "VIVENTIUM_LIBRECHAT_CANONICAL_ENV_FILE": "",
        "VIVENTIUM_PRIVATE_CURATED_DIR": "",
        "VIVENTIUM_PRIVATE_REPO_DIR": "",
        "VIVENTIUM_PYTHON_BIN": sys.executable,
        "VIVENTIUM_RUNTIME_DIR": str(runtime),
        "VIVENTIUM_RUNTIME_PROFILE": "synthetic-activation-qa",
        "VIVENTIUM_STATE_ROOT": str(
            support / "state" / "runtime" / "synthetic-activation-qa"
        ),
    }

    completed = subprocess.run(
        [
            str(candidate_cli),
            "--app-support-dir",
            str(support),
            "--config-file",
            str(config),
            "--runtime-dir",
            str(runtime),
            "dev-runtime",
            "activate-current",
            "--validate",
            "--restart",
            "--allow-protected-folder",
            "--allow-dirty-local-testing",
        ],
        cwd=candidate_repo,
        check=False,
        capture_output=True,
        text=True,
        timeout=90,
        env=child_env,
    )

    assert completed.returncode != 0
    assert "binding, live runtime, helper, and running state were not changed" in (
        completed.stderr
    )
    assert (runtime / "runtime.env").read_bytes() == before["runtime"]
    assert checkout.read_bytes() == before["checkout"]
    assert helper.read_bytes() == before["helper"]
    assert not list(state.glob("dev-runtime-activation.*"))
    assert candidate_env.read_text(encoding="utf-8") == (
        "CREDS_KEY=synthetic-existing\n"
    )
    assert tuple(
        (
            path.read_bytes(),
            path.stat().st_ino,
            path.stat().st_nlink,
            stat.S_IMODE(path.stat().st_mode),
            path.stat().st_mtime_ns,
        )
        for path in legacy_paths
    ) == legacy_before


def test_crash_after_live_runtime_backup_recovers_from_predeclared_journal(
    tmp_path: Path, monkeypatch
) -> None:
    support, runtime, transaction, checkout, helper = prepare(tmp_path)
    module = load_module()
    original_write = module.write_json

    def crash_after_backup(path, payload, boundary):
        if payload.get("status") == "runtime_backed_up":
            raise OSError("synthetic crash after backup")
        return original_write(path, payload, boundary)

    monkeypatch.setattr(module, "write_json", crash_after_backup)
    args = module.build_parser().parse_args(
        [
            "publish",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ]
    )
    with pytest.raises(OSError, match="synthetic crash"):
        module.publish(args)
    manifest = json.loads(
        (transaction / module.MANIFEST_NAME).read_text(encoding="utf-8")
    )
    assert manifest["status"] == "publishing"
    assert not runtime.exists()

    recovered = run_tool(
        "rollback",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    assert recovered["status"] == "rolled_back"
    assert (runtime / "runtime.env").read_text(encoding="utf-8") == "VERSION=old\n"
    assert checkout.read_text(encoding="utf-8") == '{"repoRoot":"/old"}\n'
    assert "running" in helper.read_text(encoding="utf-8")


def test_crash_after_candidate_swap_recovers_before_binding(
    tmp_path: Path, monkeypatch
) -> None:
    support, runtime, transaction, checkout, helper = prepare(tmp_path)
    module = load_module()
    original_write = module.write_json

    def crash_after_candidate(path, payload, boundary):
        if payload.get("status") == "published":
            raise OSError("synthetic crash after candidate swap")
        return original_write(path, payload, boundary)

    monkeypatch.setattr(module, "write_json", crash_after_candidate)
    args = module.build_parser().parse_args(
        [
            "publish",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ]
    )
    with pytest.raises(OSError, match="synthetic crash"):
        module.publish(args)
    manifest = json.loads(
        (transaction / module.MANIFEST_NAME).read_text(encoding="utf-8")
    )
    assert manifest["status"] == "runtime_backed_up"
    assert (runtime / "runtime.env").read_text(encoding="utf-8") == "VERSION=new\n"

    run_tool(
        "rollback",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    assert (runtime / "runtime.env").read_text(encoding="utf-8") == "VERSION=old\n"


def test_post_commit_cleanup_failure_cannot_wedge_finalization(
    tmp_path: Path,
    monkeypatch,
) -> None:
    planned = b"CREDS_KEY=established\nOWNER_NOTE=established\n"
    support, _, transaction, checkout, _ = prepare(tmp_path)
    plan_owner_env(support, transaction, planned)
    run_tool(
        "publish",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    checkout.write_text('{"repoRoot":"/candidate"}\n', encoding="utf-8")
    run_tool(
        "binding-applied",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    module = load_module()
    real_cleanup = module.cleanup_candidate_env_transaction_links

    def fail_cleanup(*_args, **_kwargs):
        raise module.ActivationError("synthetic post-commit cleanup failure")

    monkeypatch.setattr(
        module,
        "cleanup_candidate_env_transaction_links",
        fail_cleanup,
    )
    commit_args = module.build_parser().parse_args(
        [
            "commit",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ]
    )
    alignment_args = module.build_parser().parse_args(
        [
            "alignment-status",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ]
    )
    finalize_args = module.build_parser().parse_args(
        [
            "finalize-helper",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ]
    )

    assert module.commit(commit_args)["status"] == "core_committed"
    alignment = module.alignment_status(alignment_args)
    assert alignment["required"] is False
    assert alignment["cleanupState"] == "pending"
    with pytest.raises(
        module.ActivationError,
        match="cleanup remains pending",
    ):
        module.finalize_helper(finalize_args)
    monkeypatch.setattr(
        module,
        "cleanup_candidate_env_transaction_links",
        real_cleanup,
    )
    assert module.finalize_helper(finalize_args)["status"] == "committed"


def test_retirement_move_preserves_terminal_window_replacement(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = load_module()
    repo = make_candidate_repo(tmp_path)
    librechat = repo / "viventium_v0_4" / "LibreChat"
    live = librechat / ".env"
    source = librechat / ".env.viventium-accepted-synthetic"
    anchor = librechat / ".env.synthetic-anchor"
    racer = librechat / ".env.synthetic-racer"
    planned = b"CREDS_KEY=planned\nOWNER_NOTE=keep\n"
    racing = b"CREDS_KEY=racing\nOWNER_NOTE=preserve\n"
    live.write_bytes(planned)
    live.chmod(0o600)
    os.link(live, source)
    racer.write_bytes(racing)
    racer.chmod(0o600)
    metadata = source.stat()
    receipt = {
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
        "size": len(planned),
        "sha256": hashlib.sha256(planned).hexdigest(),
    }
    record = {"repoRoot": str(repo)}
    retirement = module.candidate_env_retirement_name(
        record,
        "ownerEnvRetirementName",
        "env",
    )
    tombstone = module.candidate_env_retirement_name(
        record,
        "retirementTombstoneName",
        "zero",
    )
    real_rename = module.os.rename
    injected = False

    def swap_immediately_before_terminal_move(
        source_name,
        destination_name,
        *args,
        **kwargs,
    ):
        nonlocal injected
        if (
            not injected
            and source_name == source.name
            and destination_name == retirement
        ):
            real_rename(source, anchor)
            real_rename(racer, source)
            injected = True
        return real_rename(source_name, destination_name, *args, **kwargs)

    monkeypatch.setattr(
        module.os,
        "rename",
        swap_immediately_before_terminal_move,
    )
    directory_descriptor = os.open(librechat, os.O_RDONLY)
    try:
        with pytest.raises(
            module.ActivationError,
            match="changed during retirement",
        ):
            module.retire_owner_env_artifact(
                directory_descriptor,
                source.name,
                directory_descriptor,
                retirement,
                tombstone,
                receipt=receipt,
            )
    finally:
        os.close(directory_descriptor)

    assert injected is True
    assert live.read_bytes() == planned
    assert anchor.read_bytes() == planned
    assert source.read_bytes() == racing
    assert not racer.exists()


def test_retirement_zeroes_detached_secret_and_keeps_residue_bounded(
    tmp_path: Path,
) -> None:
    module = load_module()
    repo = make_candidate_repo(tmp_path)
    librechat = repo / "viventium_v0_4" / "LibreChat"
    record = {"repoRoot": str(repo)}
    retirement = module.candidate_env_retirement_name(
        record,
        "materializationRetirementName",
        "mat",
    )
    tombstone = module.candidate_env_retirement_name(
        record,
        "retirementTombstoneName",
        "zero",
    )
    directory_descriptor = os.open(librechat, os.O_RDONLY)
    try:
        for index in range(3):
            source_name = f".env.viventium-materialized-{index}"
            source = librechat / source_name
            synthetic_secret = f"CREDS_KEY=synthetic-{index}\n".encode()
            source.write_bytes(synthetic_secret)
            source.chmod(0o400 if index == 2 else 0o600)
            metadata = source.stat()
            receipt = {
                "device": metadata.st_dev,
                "inode": metadata.st_ino,
                "size": len(synthetic_secret),
                "sha256": hashlib.sha256(synthetic_secret).hexdigest(),
            }
            assert module.retire_owner_env_artifact(
                directory_descriptor,
                source_name,
                directory_descriptor,
                retirement,
                tombstone,
                receipt=receipt,
            )
            assert not source.exists()
            assert (librechat / retirement).read_bytes() == b""
            if index == 2:
                assert stat.S_IMODE((librechat / retirement).stat().st_mode) == 0o400
        assert sorted(
            path.name
            for path in librechat.glob(".env.viventium-retired-*")
        ) == sorted((retirement, tombstone))
    finally:
        os.close(directory_descriptor)


def test_retirement_collapses_two_detached_aliases_before_finalization(
    tmp_path: Path,
) -> None:
    module = load_module()
    repo = make_candidate_repo(tmp_path)
    librechat = repo / "viventium_v0_4" / "LibreChat"
    accepted = librechat / ".env.viventium-accepted-two-alias"
    materialized = librechat / ".env.viventium-materialized-two-alias"
    old = b"CREDS_KEY=old-must-not-persist\n"
    accepted.write_bytes(old)
    accepted.chmod(0o600)
    os.link(accepted, materialized)
    live = librechat / ".env"
    live.write_bytes(b"CREDS_KEY=current\n")
    live.chmod(0o600)
    metadata = accepted.stat()
    receipt = {
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
        "size": len(old),
        "sha256": hashlib.sha256(old).hexdigest(),
    }
    record = {
        "repoRoot": str(repo),
        "materializationRetirementName": ".env.viventium-retired-mat",
        "ownerEnvRetirementName": ".env.viventium-retired-env",
        "retirementTombstoneName": ".env.viventium-retired-zero",
    }
    directory_descriptor = os.open(librechat, os.O_RDONLY)
    try:
        module.retire_owner_env_artifact(
            directory_descriptor,
            accepted.name,
            directory_descriptor,
            record["ownerEnvRetirementName"],
            record["retirementTombstoneName"],
            receipt=receipt,
        )
        module.retire_owner_env_artifact(
            directory_descriptor,
            materialized.name,
            directory_descriptor,
            record["materializationRetirementName"],
            record["retirementTombstoneName"],
            receipt=receipt,
        )
        assert (
            librechat / record["ownerEnvRetirementName"]
        ).stat().st_ino == (
            librechat / record["materializationRetirementName"]
        ).stat().st_ino
        module.normalize_owner_env_retirement_slots(
            directory_descriptor,
            record,
        )
    finally:
        os.close(directory_descriptor)

    for field in (
        "materializationRetirementName",
        "ownerEnvRetirementName",
        "retirementTombstoneName",
    ):
        slot = librechat / record[field]
        assert slot.read_bytes() == b""
        assert slot.stat().st_nlink == 1
    assert live.read_bytes() == b"CREDS_KEY=current\n"


@pytest.mark.parametrize(
    "crash_point",
    ("after-zero", "after-tombstone-replace", "after-source-move"),
)
def test_retirement_retries_every_durable_crash_boundary(
    tmp_path: Path,
    monkeypatch,
    crash_point: str,
) -> None:
    module = load_module()
    repo = make_candidate_repo(tmp_path)
    librechat = repo / "viventium_v0_4" / "LibreChat"
    source = librechat / ".env.viventium-materialized-crash"
    contents = b"CREDS_KEY=synthetic-crash-boundary\n"
    source.write_bytes(contents)
    source.chmod(0o600)
    metadata = source.stat()
    receipt = {
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
        "size": len(contents),
        "sha256": hashlib.sha256(contents).hexdigest(),
    }
    record = {"repoRoot": str(repo)}
    retirement = module.candidate_env_retirement_name(
        record,
        "materializationRetirementName",
        "mat",
    )
    tombstone = module.candidate_env_retirement_name(
        record,
        "retirementTombstoneName",
        "zero",
    )
    injected = False
    if crash_point == "after-zero":
        real_zero = module.zero_detached_owner_artifact

        def crash_after_zero(*args, **kwargs):
            nonlocal injected
            result = real_zero(*args, **kwargs)
            if not injected:
                injected = True
                raise OSError("synthetic crash after descriptor zero")
            return result

        monkeypatch.setattr(
            module,
            "zero_detached_owner_artifact",
            crash_after_zero,
        )
    elif crash_point == "after-tombstone-replace":
        real_replace = module.os.replace

        def crash_after_tombstone_replace(src, dst, *args, **kwargs):
            nonlocal injected
            result = real_replace(src, dst, *args, **kwargs)
            if not injected and src == tombstone and dst == retirement:
                injected = True
                raise OSError("synthetic crash after tombstone replacement")
            return result

        monkeypatch.setattr(module.os, "replace", crash_after_tombstone_replace)
    else:
        real_rename = module.os.rename

        def crash_after_source_move(src, dst, *args, **kwargs):
            nonlocal injected
            result = real_rename(src, dst, *args, **kwargs)
            if not injected and src == source.name and dst == retirement:
                injected = True
                raise OSError("synthetic crash after source move")
            return result

        monkeypatch.setattr(module.os, "rename", crash_after_source_move)

    directory_descriptor = os.open(librechat, os.O_RDONLY)
    try:
        with pytest.raises(OSError, match="synthetic crash"):
            module.retire_owner_env_artifact(
                directory_descriptor,
                source.name,
                directory_descriptor,
                retirement,
                tombstone,
                receipt=receipt,
            )
        assert injected is True
        assert module.retire_owner_env_artifact(
            directory_descriptor,
            source.name,
            directory_descriptor,
            retirement,
            tombstone,
            receipt=receipt,
        )
    finally:
        os.close(directory_descriptor)

    assert not source.exists()
    assert (librechat / retirement).read_bytes() == b""


def test_retirement_crash_after_moving_racer_fails_closed_on_retry(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = load_module()
    repo = make_candidate_repo(tmp_path)
    librechat = repo / "viventium_v0_4" / "LibreChat"
    live = librechat / ".env"
    source = librechat / ".env.viventium-accepted-crash-race"
    anchor = librechat / ".env.synthetic-crash-anchor"
    racer = librechat / ".env.synthetic-crash-racer"
    planned = b"CREDS_KEY=planned\n"
    racing = b"CREDS_KEY=racing-must-survive\n"
    live.write_bytes(planned)
    live.chmod(0o600)
    os.link(live, source)
    racer.write_bytes(racing)
    racer.chmod(0o600)
    metadata = source.stat()
    receipt = {
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
        "size": len(planned),
        "sha256": hashlib.sha256(planned).hexdigest(),
    }
    record = {"repoRoot": str(repo)}
    retirement = module.candidate_env_retirement_name(
        record,
        "ownerEnvRetirementName",
        "env",
    )
    tombstone = module.candidate_env_retirement_name(
        record,
        "retirementTombstoneName",
        "zero",
    )
    real_rename = module.os.rename
    injected = False

    def crash_after_moving_racer(src, dst, *args, **kwargs):
        nonlocal injected
        if not injected and src == source.name and dst == retirement:
            real_rename(source, anchor)
            real_rename(racer, source)
            real_rename(src, dst, *args, **kwargs)
            injected = True
            raise OSError("synthetic crash after moving racing replacement")
        return real_rename(src, dst, *args, **kwargs)

    monkeypatch.setattr(module.os, "rename", crash_after_moving_racer)
    directory_descriptor = os.open(librechat, os.O_RDONLY)
    try:
        with pytest.raises(OSError, match="synthetic crash"):
            module.retire_owner_env_artifact(
                directory_descriptor,
                source.name,
                directory_descriptor,
                retirement,
                tombstone,
                receipt=receipt,
            )
        assert injected is True
        with pytest.raises(
            module.ActivationError,
            match="retirement slot conflicts",
        ):
            module.retire_owner_env_artifact(
                directory_descriptor,
                source.name,
                directory_descriptor,
                retirement,
                tombstone,
                receipt=receipt,
                allow_missing=True,
            )
    finally:
        os.close(directory_descriptor)

    assert live.read_bytes() == planned
    assert anchor.read_bytes() == planned
    assert (librechat / retirement).read_bytes() == racing
    assert not racer.exists()


def test_detached_cleanup_preserves_foreign_materialization_retirement_slot(
    tmp_path: Path,
) -> None:
    original = b"CREDS_KEY=synthetic-original\nOWNER_NOTE=keep\n"
    foreign = b"CREDS_KEY=foreign-retirement\nOWNER_NOTE=preserve\n"
    support, _, transaction, _, _ = prepare(
        tmp_path,
        candidate_env=original,
    )
    plan_owner_env(support, transaction, original)
    payload = run_tool(
        "status",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    record = payload["candidateEnv"]
    candidate_env = (
        Path(str(record["repoRoot"])) / "viventium_v0_4" / "LibreChat" / ".env"
    )
    materialized = candidate_env.with_name(
        payload["ownerEnvPlan"]["materializationTargetName"]
    )
    original_anchor = candidate_env.with_name(
        ".env.synthetic-receipted-anchor"
    )
    replacement = candidate_env.with_name(".env.synthetic-runtime-rewrite")
    replacement.write_bytes(original)
    replacement.chmod(0o600)
    os.replace(replacement, candidate_env)
    os.rename(materialized, original_anchor)
    foreign_slot = candidate_env.with_name(
        record["materializationRetirementName"]
    )
    foreign_slot.write_bytes(foreign)
    foreign_slot.chmod(0o600)

    completed = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "rollback",
            "--transaction-dir",
            str(transaction),
            "--app-support-dir",
            str(support),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "retirement slot conflicts with the receipt" in completed.stderr
    assert candidate_env.read_bytes() == original
    assert original_anchor.read_bytes() == original
    assert foreign_slot.read_bytes() == foreign


def test_restore_quarantine_never_overwrites_concurrent_owner_state(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = load_module()
    repo = make_candidate_repo(tmp_path)
    librechat = repo / "viventium_v0_4" / "LibreChat"
    quarantine = librechat / ".env.viventium-rollback-synthetic"
    quarantine.write_bytes(b"CREDS_KEY=planned\n")
    quarantine.chmod(0o600)
    concurrent = b"CREDS_KEY=concurrent\n"
    real_current = module.current_candidate_env_bytes
    injected = False

    def create_after_absence_probe(directory_descriptor, name=".env"):
        nonlocal injected
        result = real_current(directory_descriptor, name)
        if not injected and name == ".env" and result is None:
            (librechat / ".env").write_bytes(concurrent)
            (librechat / ".env").chmod(0o600)
            injected = True
        return result

    monkeypatch.setattr(
        module,
        "current_candidate_env_bytes",
        create_after_absence_probe,
    )
    record = {"repoRoot": str(repo)}
    directory_descriptor = os.open(librechat, os.O_RDONLY)
    try:
        with pytest.raises(
            module.ActivationError,
            match="Concurrent candidate LibreChat owner state appeared",
        ):
            module._restore_quarantine_without_overwrite(
                directory_descriptor,
                quarantine.name,
                module.candidate_env_retirement_name(
                    record,
                    "ownerEnvRetirementName",
                    "env",
                ),
                module.candidate_env_retirement_name(
                    record,
                    "retirementTombstoneName",
                    "zero",
                ),
            )
    finally:
        os.close(directory_descriptor)

    assert injected is True
    assert (librechat / ".env").read_bytes() == concurrent
    assert quarantine.read_bytes() == b"CREDS_KEY=planned\n"


@pytest.mark.parametrize("unsafe_kind", ("symlink", "directory"))
def test_candidate_checkpoint_rejects_unsafe_retirement_state(
    tmp_path: Path,
    unsafe_kind: str,
) -> None:
    module = load_module()
    repo = make_candidate_repo(tmp_path)
    librechat = repo / "viventium_v0_4" / "LibreChat"
    retirement = librechat / ".env.viventium-retired-env"
    if unsafe_kind == "symlink":
        retirement.symlink_to(librechat / ".env")
    else:
        retirement.mkdir()

    with pytest.raises(
        (module.ActivationError, OSError),
        match="retirement state is unsafe|Too many levels of symbolic links",
    ):
        module.safe_candidate_env_snapshot(
            repo,
            tmp_path / "candidate-librechat.env",
        )


def test_candidate_checkpoint_accepts_zero_retirement_slots_after_checkout_move(
    tmp_path: Path,
) -> None:
    module = load_module()
    repo = make_candidate_repo(tmp_path)
    librechat = repo / "viventium_v0_4" / "LibreChat"
    for name in (
        ".env.viventium-retired-mat",
        ".env.viventium-retired-env",
        ".env.viventium-retired-zero",
    ):
        slot = librechat / name
        slot.write_bytes(b"")
        slot.chmod(0o600)
    moved_repo = tmp_path / "moved-candidate-checkout"
    os.rename(repo, moved_repo)

    record = module.safe_candidate_env_snapshot(
        moved_repo,
        tmp_path / "moved-candidate-librechat.env",
    )

    assert record["materializationRetirementName"] == (
        ".env.viventium-retired-mat"
    )
    assert record["ownerEnvRetirementName"] == ".env.viventium-retired-env"
    assert record["retirementTombstoneName"] == ".env.viventium-retired-zero"


def test_candidate_checkpoint_is_read_only_then_cleanup_migrates_legacy_slots(
    tmp_path: Path,
) -> None:
    module = load_module()
    repo = make_candidate_repo(tmp_path)
    librechat = repo / "viventium_v0_4" / "LibreChat"
    live = librechat / ".env"
    live_contents = b"CREDS_KEY=current-owner\n"
    stale_contents = b"CREDS_KEY=old-retired-owner\n"
    live.write_bytes(live_contents)
    live.chmod(0o600)
    legacy_env = librechat / (
        ".env.viventium-retired-env-0123456789abcdefabcd"
    )
    legacy_mat = librechat / (
        ".env.viventium-retired-mat-0123456789abcdefabcd"
    )
    legacy_zero = librechat / (
        ".env.viventium-retired-zero-0123456789abcdefabcd"
    )
    legacy_env.write_bytes(stale_contents)
    legacy_env.chmod(0o600)
    os.link(legacy_env, legacy_mat)
    legacy_zero.write_bytes(b"")
    legacy_zero.chmod(0o600)
    moved_repo = tmp_path / "moved-legacy-candidate"
    os.rename(repo, moved_repo)

    transaction = tmp_path / "activation"
    snapshots = transaction / "snapshots"
    snapshots.mkdir(parents=True)
    record = module.safe_candidate_env_snapshot(
        moved_repo,
        snapshots / "candidate-librechat.env",
    )

    moved_librechat = moved_repo / "viventium_v0_4" / "LibreChat"
    assert (moved_librechat / ".env").read_bytes() == live_contents
    assert (moved_librechat / legacy_env.name).read_bytes() == stale_contents
    assert (moved_librechat / legacy_mat.name).read_bytes() == stale_contents
    assert (moved_librechat / legacy_zero.name).read_bytes() == b""
    legacy_identity = (
        (moved_librechat / legacy_env.name).stat().st_ino,
        (moved_librechat / legacy_mat.name).stat().st_ino,
        (moved_librechat / legacy_zero.name).stat().st_ino,
    )

    module.normalize_candidate_env_retirement(record, transaction)

    assert (moved_librechat / legacy_env.name).read_bytes() == stale_contents
    assert (moved_librechat / legacy_mat.name).read_bytes() == stale_contents
    assert (moved_librechat / legacy_zero.name).read_bytes() == b""
    assert (
        (moved_librechat / legacy_env.name).stat().st_ino,
        (moved_librechat / legacy_mat.name).stat().st_ino,
        (moved_librechat / legacy_zero.name).stat().st_ino,
    ) == legacy_identity

    module.normalize_candidate_env_retirement(
        record,
        transaction,
        migrate_legacy=True,
    )

    assert (moved_librechat / ".env").read_bytes() == live_contents
    assert not (moved_librechat / legacy_env.name).exists()
    assert not (moved_librechat / legacy_mat.name).exists()
    assert not (moved_librechat / legacy_zero.name).exists()
    for field in (
        "materializationRetirementName",
        "ownerEnvRetirementName",
        "retirementTombstoneName",
    ):
        slot = moved_librechat / record[field]
        assert slot.read_bytes() == b""
        assert slot.stat().st_nlink == 1


def test_in_progress_legacy_journal_retirement_names_remain_recoverable(
    tmp_path: Path,
) -> None:
    planned = b"CREDS_KEY=established\nOWNER_NOTE=established\n"
    support, _, transaction, checkout, _ = prepare(tmp_path)
    plan_owner_env(support, transaction, planned)
    manifest_path = transaction / "activation.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    suffix = "0123456789abcdefabcd"
    payload["candidateEnv"].update(
        {
            "materializationRetirementName": (
                f".env.viventium-retired-mat-{suffix}"
            ),
            "ownerEnvRetirementName": (
                f".env.viventium-retired-env-{suffix}"
            ),
            "retirementTombstoneName": (
                f".env.viventium-retired-zero-{suffix}"
            ),
        }
    )
    manifest_path.write_text(
        json.dumps(payload) + "\n",
        encoding="utf-8",
    )
    run_tool(
        "publish",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )
    checkout.write_text('{"repoRoot":"/candidate"}\n', encoding="utf-8")
    run_tool(
        "binding-applied",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )

    committed = run_tool(
        "commit",
        "--transaction-dir",
        transaction,
        "--app-support-dir",
        support,
    )

    assert committed["status"] == "core_committed"
    record = committed["candidateEnv"]
    candidate_env = (
        Path(str(record["repoRoot"]))
        / "viventium_v0_4"
        / "LibreChat"
        / ".env"
    )
    assert candidate_env.read_bytes() == planned
    for field in (
        "materializationRetirementName",
        "ownerEnvRetirementName",
        "retirementTombstoneName",
    ):
        slot = candidate_env.with_name(record[field])
        assert slot.read_bytes() == b""
        assert slot.stat().st_nlink == 1
