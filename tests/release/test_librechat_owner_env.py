from __future__ import annotations

import json
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL = REPO_ROOT / "scripts" / "viventium" / "librechat_owner_env.py"


def load_tool_module():
    specification = importlib.util.spec_from_file_location(
        "librechat_owner_env_under_test",
        TOOL,
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def run_tool(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def extract_shell_function(source: str, name: str) -> str:
    start = source.index(f"{name}() {{")
    collected: list[str] = []
    depth = 0
    for line in source[start:].splitlines():
        collected.append(line)
        depth += line.count("{")
        depth -= line.count("}")
        if depth == 0:
            break
    return "\n".join(collected) + "\n"


def make_candidate_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "candidate"
    librechat = repo / "viventium_v0_4" / "LibreChat"
    librechat.mkdir(parents=True)
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
    commit = subprocess.run(
        ["git", "-C", str(librechat), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return repo, commit


def stage_fixture(
    tmp_path: Path,
    contents: str,
    *,
    candidate_contents: str | None = None,
) -> tuple[Path, Path, Path, Path, str]:
    source = tmp_path / "source.env"
    source.write_text(contents, encoding="utf-8")
    source.chmod(0o600)
    runtime = tmp_path / "candidate-runtime"
    runtime.mkdir()
    destination = runtime / "service-env" / "librechat.owner.env"
    manifest = runtime / "service-env" / "librechat.owner.manifest.json"
    repo, commit = make_candidate_repo(tmp_path)
    if candidate_contents is not None:
        candidate_env = repo / "viventium_v0_4" / "LibreChat" / ".env"
        candidate_env.write_text(candidate_contents, encoding="utf-8")
        candidate_env.chmod(0o600)
    completed = run_tool(
        "stage",
        "--source",
        str(source),
        "--runtime-dir",
        str(runtime),
        "--destination",
        str(destination),
        "--manifest",
        str(manifest),
        "--target-repo",
        str(repo),
        "--target-commit",
        commit,
    )
    assert completed.returncode == 0, completed.stderr
    return source, destination, manifest, repo, commit


def test_stage_and_materialize_are_exact_owner_only_and_digest_only(
    tmp_path: Path,
) -> None:
    values = (
        "CREDS_KEY=protected-creds\n"
        "JWT_SECRET=protected-jwt\n"
        "OPENAI_API_KEY=owner-secret\n"
        "OWNER_CUSTOM=keep-me\n"
        "PORT=3080\n"
    )
    _, destination, manifest, repo, commit = stage_fixture(tmp_path, values)
    target = repo / "viventium_v0_4" / "LibreChat" / ".env"

    completed = run_tool(
        "materialize",
        "--manifest",
        str(manifest),
        "--snapshot",
        str(destination),
        "--target-repo",
        str(repo),
        "--target-env",
        str(target),
        "--target-commit",
        commit,
    )

    assert completed.returncode == 0, completed.stderr
    assert target.read_text(encoding="utf-8") == values
    assert target.stat().st_mode & 0o777 == 0o600
    assert destination.stat().st_mode & 0o777 == 0o600
    assert manifest.stat().st_mode & 0o777 == 0o600
    manifest_text = manifest.read_text(encoding="utf-8")
    for secret in ("protected-creds", "protected-jwt", "owner-secret", "keep-me"):
        assert secret not in manifest_text
    payload = json.loads(manifest_text)
    assert payload["kind"] == "librechat-owner-environment-continuity"
    assert payload["schema_version"] == 2
    assert payload["materialization_target_name"].startswith(
        ".env.viventium-materialized-"
    )
    materialized = target.with_name(payload["materialization_target_name"])
    assert materialized.read_text(encoding="utf-8") == values
    assert materialized.stat().st_ino == target.stat().st_ino
    assert str(repo) not in manifest_text


def test_materialize_existing_exact_candidate_creates_transaction_identity_receipt(
    tmp_path: Path,
) -> None:
    values = "CREDS_KEY=protected-creds\nOWNER_CUSTOM=keep-me\nPORT=3180\n"
    _, destination, manifest, repo, commit = stage_fixture(
        tmp_path,
        values,
        candidate_contents=values,
    )
    target = repo / "viventium_v0_4" / "LibreChat" / ".env"
    original_inode = target.stat().st_ino
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    materialized = target.with_name(payload["materialization_target_name"])

    completed = run_tool(
        "materialize",
        "--manifest",
        str(manifest),
        "--snapshot",
        str(destination),
        "--target-repo",
        str(repo),
        "--target-env",
        str(target),
        "--target-commit",
        commit,
    )

    assert completed.returncode == 0, completed.stderr
    assert target.read_text(encoding="utf-8") == values
    assert target.stat().st_ino == original_inode
    assert materialized.stat().st_ino == original_inode


def test_existing_exact_materialization_preserves_atomic_replacement_before_receipt(
    tmp_path: Path,
    monkeypatch,
) -> None:
    values = "CREDS_KEY=protected-creds\nOWNER_CUSTOM=keep-me\n"
    concurrent = b"CREDS_KEY=concurrent\nOWNER_CUSTOM=preserve\n"
    _, destination, manifest, repo, commit = stage_fixture(
        tmp_path,
        values,
        candidate_contents=values,
    )
    target = repo / "viventium_v0_4" / "LibreChat" / ".env"
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    materialized = target.with_name(payload["materialization_target_name"])
    module = load_tool_module()
    original_link = module.os.link
    injected = False

    def replace_before_receipt_link(src, dst, **kwargs):
        nonlocal injected
        if not injected and src == target.name and dst == materialized.name:
            replacement = target.with_name(".env.concurrent")
            replacement.write_bytes(concurrent)
            replacement.chmod(0o600)
            os.replace(replacement, target)
            injected = True
        return original_link(src, dst, **kwargs)

    monkeypatch.setattr(module.os, "link", replace_before_receipt_link)
    with pytest.raises(
        module.OwnerEnvError,
        match="materialization binding changed",
    ):
        module.materialize(
            manifest,
            destination,
            repo,
            target,
            commit,
        )

    assert injected is True
    assert target.read_bytes() == concurrent
    assert not materialized.exists()


def test_verify_allows_only_managed_drift(tmp_path: Path) -> None:
    _, destination, manifest, _, _ = stage_fixture(
        tmp_path,
        "CREDS_KEY=keep\nOWNER_CUSTOM=keep\nPORT=3080\n",
    )
    destination.write_text(
        "CREDS_KEY=keep\nOWNER_CUSTOM=keep\nPORT=3180\n",
        encoding="utf-8",
    )

    verified = run_tool(
        "verify",
        "--manifest",
        str(manifest),
        "--target",
        str(destination),
    )

    assert verified.returncode == 0, verified.stderr
    result = json.loads(verified.stdout)
    assert result["protected_fields_preserved"] is True
    assert result["exact_file_match"] is False


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("CREDS_KEY=keep\n", "CREDS_KEY=rotated\n"),
        ("OPENAI_API_KEY=keep\n", "OPENAI_API_KEY=rotated\n"),
        ("OWNER_CUSTOM=keep\n", ""),
    ],
)
def test_verify_rejects_protected_owner_secret_or_unmanaged_drift(
    tmp_path: Path,
    before: str,
    after: str,
) -> None:
    _, destination, manifest, _, _ = stage_fixture(tmp_path, before)
    destination.write_text(after, encoding="utf-8")

    completed = run_tool(
        "verify",
        "--manifest",
        str(manifest),
        "--target",
        str(destination),
    )

    assert completed.returncode != 0
    assert "continuity failed" in completed.stderr


def test_source_change_after_stage_is_rejected(tmp_path: Path) -> None:
    source, _, manifest, _, _ = stage_fixture(tmp_path, "CREDS_KEY=keep\n")
    source.write_text("CREDS_KEY=changed\n", encoding="utf-8")

    completed = run_tool(
        "verify-source",
        "--manifest",
        str(manifest),
        "--source",
        str(source),
    )

    assert completed.returncode != 0
    assert "changed after it was snapshotted" in completed.stderr


def test_incompatible_candidate_owner_state_is_rejected(tmp_path: Path) -> None:
    _, _, manifest, repo, _ = stage_fixture(
        tmp_path,
        "CREDS_KEY=live\n",
        candidate_contents="CREDS_KEY=stale\n",
    )
    target = repo / "viventium_v0_4" / "LibreChat" / ".env"

    completed = run_tool(
        "verify-compatible",
        "--manifest",
        str(manifest),
        "--target",
        str(target),
    )

    assert completed.returncode != 0
    assert "conflicts with established owner state" in completed.stderr


def test_materialize_rejects_target_appearance_after_compatibility_check(
    tmp_path: Path,
) -> None:
    _, destination, manifest, repo, commit = stage_fixture(
        tmp_path,
        "CREDS_KEY=live\nPORT=3080\n",
    )
    target = repo / "viventium_v0_4" / "LibreChat" / ".env"
    compatible = run_tool(
        "verify-compatible",
        "--manifest",
        str(manifest),
        "--target",
        str(target),
    )
    assert compatible.returncode == 0, compatible.stderr
    target.write_text("PORT=3199\n", encoding="utf-8")

    materialized = run_tool(
        "materialize",
        "--manifest",
        str(manifest),
        "--snapshot",
        str(destination),
        "--target-repo",
        str(repo),
        "--target-env",
        str(target),
        "--target-commit",
        commit,
    )

    assert materialized.returncode != 0
    assert "changed during materialization" in materialized.stderr
    assert target.read_text(encoding="utf-8") == "PORT=3199\n"


def test_materialize_never_overwrites_atomic_concurrent_target_replacement(
    tmp_path: Path,
    monkeypatch,
) -> None:
    values = "CREDS_KEY=live\nOWNER_NOTE=live\n"
    _, destination, manifest, repo, commit = stage_fixture(
        tmp_path,
        values,
        candidate_contents=values,
    )
    target = repo / "viventium_v0_4" / "LibreChat" / ".env"
    concurrent = b"CREDS_KEY=concurrent\nOWNER_NOTE=concurrent\n"
    module = load_tool_module()
    original_reader = module._read_owned_regular_descriptor
    injected = False

    def replace_after_descriptor_read(descriptor):
        nonlocal injected
        contents, metadata = original_reader(descriptor)
        if not injected:
            replacement = target.with_name(".env.concurrent")
            replacement.write_bytes(concurrent)
            replacement.chmod(0o600)
            os.replace(replacement, target)
            injected = True
        return contents, metadata

    monkeypatch.setattr(
        module,
        "_read_owned_regular_descriptor",
        replace_after_descriptor_read,
    )
    with pytest.raises(
        module.OwnerEnvError,
        match="changed during materialization",
    ):
        module.materialize(
            manifest,
            destination,
            repo,
            target,
            commit,
        )

    assert injected is True
    assert target.read_bytes() == concurrent


def test_materialize_preserves_same_inode_concurrent_owner_write(
    tmp_path: Path,
    monkeypatch,
) -> None:
    values = "CREDS_KEY=live\nOWNER_NOTE=live\n"
    _, destination, manifest, repo, commit = stage_fixture(
        tmp_path,
        values,
        candidate_contents=values,
    )
    target = repo / "viventium_v0_4" / "LibreChat" / ".env"
    concurrent = b"CREDS_KEY=concurrent\nOWNER_NOTE=same-inode-edit\n"
    module = load_tool_module()
    original_reader = module._read_owned_regular_descriptor
    reads = 0

    def mutate_quarantined_inode_after_first_read(descriptor):
        nonlocal reads
        contents, metadata = original_reader(descriptor)
        reads += 1
        if reads == 1:
            target.write_bytes(concurrent)
        return contents, metadata

    monkeypatch.setattr(
        module,
        "_read_owned_regular_descriptor",
        mutate_quarantined_inode_after_first_read,
    )
    with pytest.raises(
        module.OwnerEnvError,
        match="changed during materialization",
    ):
        module.materialize(
            manifest,
            destination,
            repo,
            target,
            commit,
        )

    assert reads == 1
    assert target.read_bytes() == concurrent


def test_materialize_refuses_to_overwrite_independent_candidate_owner_env(
    tmp_path: Path,
) -> None:
    source = "CREDS_KEY=keep\nOWNER_NOTE=keep\nPORT=3180\n"
    candidate = "CREDS_KEY=keep\nOWNER_NOTE=keep\nPORT=4190\n"
    _, destination, manifest, repo, commit = stage_fixture(
        tmp_path,
        source,
        candidate_contents=candidate,
    )
    target = repo / "viventium_v0_4" / "LibreChat" / ".env"

    completed = run_tool(
        "materialize",
        "--manifest",
        str(manifest),
        "--snapshot",
        str(destination),
        "--target-repo",
        str(repo),
        "--target-env",
        str(target),
        "--target-commit",
        commit,
    )

    assert completed.returncode != 0
    assert "will not overwrite it" in completed.stderr
    assert target.read_text(encoding="utf-8") == candidate


def test_stage_rejects_symlink_source_and_destination(tmp_path: Path) -> None:
    real = tmp_path / "real.env"
    real.write_text("CREDS_KEY=value\n", encoding="utf-8")
    real.chmod(0o600)
    source = tmp_path / "source.env"
    source.symlink_to(real)
    runtime = tmp_path / "candidate-runtime"
    service = runtime / "service-env"
    service.mkdir(parents=True)
    destination = service / "librechat.owner.env"
    manifest = service / "librechat.owner.manifest.json"
    repo, commit = make_candidate_repo(tmp_path)
    common = (
        "--source",
        str(source),
        "--runtime-dir",
        str(runtime),
        "--destination",
        str(destination),
        "--manifest",
        str(manifest),
        "--target-repo",
        str(repo),
        "--target-commit",
        commit,
    )

    source_result = run_tool("stage", *common)
    assert source_result.returncode != 0

    source.unlink()
    source.write_text("CREDS_KEY=value\n", encoding="utf-8")
    source.chmod(0o600)
    destination.symlink_to(real)
    destination_result = run_tool("stage", *common)
    assert destination_result.returncode != 0


def test_materialize_rejects_wrong_or_changed_nested_commit(tmp_path: Path) -> None:
    _, destination, manifest, repo, commit = stage_fixture(
        tmp_path,
        "CREDS_KEY=keep\n",
    )
    target = repo / "viventium_v0_4" / "LibreChat" / ".env"
    wrong = "0" * len(commit)
    wrong_result = run_tool(
        "materialize",
        "--manifest",
        str(manifest),
        "--snapshot",
        str(destination),
        "--target-repo",
        str(repo),
        "--target-env",
        str(target),
        "--target-commit",
        wrong,
    )
    assert wrong_result.returncode != 0

    librechat = repo / "viventium_v0_4" / "LibreChat"
    (librechat / "marker").write_text("changed\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(librechat), "add", "marker"], check=True)
    subprocess.run(
        ["git", "-C", str(librechat), "commit", "-qm", "changed"],
        check=True,
    )
    changed_result = run_tool(
        "materialize",
        "--manifest",
        str(manifest),
        "--snapshot",
        str(destination),
        "--target-repo",
        str(repo),
        "--target-env",
        str(target),
        "--target-commit",
        commit,
    )
    assert changed_result.returncode != 0


def test_dev_runtime_orders_checkpoint_snapshot_materialize_and_commit() -> None:
    cli_source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    dev_runtime = cli_source.split("dev_runtime_command() {", 1)[1].split(
        "\nworkflows_command() {",
        1,
    )[0]
    prepare_exports = cli_source.split("prepare_runtime_exports() {", 1)[1].split(
        "\ninstall_progress_dir() {",
        1,
    )[0]
    rollback = cli_source.split(
        "restore_previous_dev_runtime_after_failure() {",
        1,
    )[1].split("\nrecover_interrupted_dev_runtime_activations() {", 1)[0]

    resolve = dev_runtime.index("resolve_dev_runtime_librechat_owner_env_source")
    begin = dev_runtime.index("dev_runtime_activation_tool begin-new")
    stage = dev_runtime.index('scripts/viventium/librechat_owner_env.py" stage')
    plan = dev_runtime.index("dev_runtime_activation_tool owner-env-planned")
    materialize = dev_runtime.index(
        'scripts/viventium/librechat_owner_env.py" materialize'
    )
    preflight_compile = dev_runtime.index("scripts/viventium/config_compiler.py")
    compile_candidate = dev_runtime.index(
        "scripts/viventium/config_compiler.py",
        materialize,
    )
    doctor = dev_runtime.index("scripts/viventium/doctor.sh")
    publish = dev_runtime.index("dev_runtime_activation_tool publish")
    verify = dev_runtime.rindex('scripts/viventium/librechat_owner_env.py" verify')
    commit = dev_runtime.index("dev_runtime_activation_tool commit")
    alignment_restart = dev_runtime.index(
        'if [[ "$owner_env_alignment_required" == "1"',
        commit,
    )
    helper_refresh = dev_runtime.index(
        "runtime_checkout_refresh_helper",
        alignment_restart,
    )

    assert preflight_compile < begin
    assert (
        resolve
        < begin
        < stage
        < plan
        < materialize
        < compile_candidate
        < doctor
        < publish
        < verify
        < commit
        < alignment_restart
        < helper_refresh
    )
    assert "--candidate-repo" in dev_runtime
    assert "established_runtime" in dev_runtime
    assert "Established runtime has no provable LibreChat owner environment" in cli_source
    assert "generated_owner_env" not in cli_source
    assert "VIVENTIUM_LIBRECHAT_PROMOTION_OWNER_ENV_FILE" in prepare_exports
    assert 'VIVENTIUM_LIBRECHAT_CANONICAL_ENV_FILE=""' in rollback
    assert "owner_env_source_is_candidate" in dev_runtime
    final_source_verification = dev_runtime.rindex(
        'scripts/viventium/librechat_owner_env.py" verify-source'
    )
    assert (
        dev_runtime.rfind(
            '[[ "$owner_env_source_is_candidate" != "1" ]]',
            0,
            final_source_verification,
        )
        != -1
    )


def test_owner_env_alignment_restart_forces_stop_then_real_start() -> None:
    function = extract_shell_function(
        (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8"),
        "force_restart_stack_after_owner_env_alignment",
    )
    completed = subprocess.run(
        [
            "bash",
            "-c",
            (
                "set -euo pipefail\n"
                "stop_stack_for_upgrade() { "
                "printf 'stop:%s\\n' \"${VIVENTIUM_DEV_RUNTIME_RECOVERY_INTERNAL:-}\"; "
                "}\n"
                "set_helper_runtime_intent() { printf 'intent:%s\\n' \"$1\"; }\n"
                "restart_stack_after_upgrade() { "
                "printf 'start:%s\\n' \"${VIVENTIUM_DEV_RUNTIME_RECOVERY_INTERNAL:-}\"; "
                "}\n"
                f"{function}"
                "force_restart_stack_after_owner_env_alignment\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.splitlines() == [
        "stop:1",
        "intent:running",
        "start:1",
    ]


def test_owner_env_source_resolution_prefers_established_state_and_fails_closed(
    tmp_path: Path,
) -> None:
    fixture_repo = tmp_path / "fixture-repo"
    tool_dir = fixture_repo / "scripts" / "viventium"
    tool_dir.mkdir(parents=True)
    shutil.copy2(TOOL, tool_dir / TOOL.name)
    shutil.copy2(
        REPO_ROOT / "scripts" / "viventium" / "upgrade_transaction.py",
        tool_dir / "upgrade_transaction.py",
    )
    candidate = fixture_repo / "viventium_v0_4" / "LibreChat" / ".env"
    candidate.parent.mkdir(parents=True)
    candidate.write_text("CREDS_KEY=candidate\n", encoding="utf-8")
    previous = tmp_path / "previous" / "viventium_v0_4" / "LibreChat" / ".env"
    previous.parent.mkdir(parents=True)
    previous.write_text("CREDS_KEY=established\n", encoding="utf-8")
    explicit = tmp_path / "explicit.env"
    explicit.write_text("CREDS_KEY=explicit\n", encoding="utf-8")
    private_root = tmp_path / "private"
    private_env = private_root / "configs" / "librechat" / "librechat.env"
    private_env.parent.mkdir(parents=True)
    private_env.write_text("CREDS_KEY=private\n", encoding="utf-8")
    function = extract_shell_function(
        (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8"),
        "resolve_dev_runtime_librechat_owner_env_source",
    )

    def resolve(established: bool, *, explicit_path: Path | None = None):
        environment = {
            **os.environ,
            "FIXTURE_REPO": str(fixture_repo),
            "PREVIOUS_REPO": str(previous.parents[2]),
            "PRIVATE_ROOT": str(private_root),
            "EXPLICIT_ENV": str(explicit_path or ""),
            "ESTABLISHED": "1" if established else "0",
            "PYTHON_FOR_TEST": sys.executable,
        }
        return subprocess.run(
            [
                "bash",
                "-c",
                (
                    "set -u\n"
                    'REPO_ROOT="$FIXTURE_REPO"\n'
                    'PYTHON_BIN="$PYTHON_FOR_TEST"\n'
                    'PRIVATE_CURATED_DIR_DEFAULT="$PRIVATE_ROOT"\n'
                    'VIVENTIUM_LIBRECHAT_CANONICAL_ENV_FILE="$EXPLICIT_ENV"\n'
                    f"{function}"
                    'resolve_dev_runtime_librechat_owner_env_source '
                    '"$PREVIOUS_REPO" "$ESTABLISHED"\n'
                ),
            ],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )

    established = resolve(True, explicit_path=explicit)
    assert established.returncode == 0, established.stderr
    assert established.stdout.strip() == str(previous)

    previous.unlink()
    missing = resolve(True, explicit_path=explicit)
    assert missing.returncode != 0
    assert "no provable LibreChat owner environment" in missing.stderr

    fresh_explicit = resolve(False, explicit_path=explicit)
    assert fresh_explicit.returncode == 0, fresh_explicit.stderr
    assert fresh_explicit.stdout.strip() == str(explicit)

    fresh_private = resolve(False)
    assert fresh_private.returncode == 0, fresh_private.stderr
    assert fresh_private.stdout.strip() == str(private_env)

    private_env.unlink()
    fresh_candidate = resolve(False)
    assert fresh_candidate.returncode == 0, fresh_candidate.stderr
    assert fresh_candidate.stdout.strip() == str(candidate)

    candidate.unlink()
    fresh_empty = resolve(False)
    assert fresh_empty.returncode == 0, fresh_empty.stderr
    assert fresh_empty.stdout == ""


@pytest.mark.parametrize(
    "evidence_path",
    [
        "config.yaml",
        "helper-config.json",
        "runtime/runtime.env",
        "data/mongodb/WiredTiger",
        "state/runtime/isolated/schedules.sqlite",
        "state/continuity/receipt.json",
    ],
)
def test_fresh_activation_proof_rejects_any_durable_install_evidence(
    tmp_path: Path,
    evidence_path: str,
) -> None:
    support = tmp_path / "support"
    runtime = support / "runtime"
    state = support / "state"
    cli_lock = state / "cli-operation.lock"
    runtime.mkdir(parents=True)
    cli_lock.mkdir(parents=True)
    (cli_lock / "pid").write_text("123\n", encoding="utf-8")
    evidence = support / evidence_path
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text("synthetic-established-state\n", encoding="utf-8")
    function = extract_shell_function(
        (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8"),
        "prove_fresh_dev_runtime_activation",
    )
    completed = subprocess.run(
        [
            "bash",
            "-c",
            (
                "set -u\n"
                f"{function}"
                "prove_fresh_dev_runtime_activation\n"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PYTHON_BIN": sys.executable,
            "APP_SUPPORT_DIR": str(support),
            "CONFIG_FILE": str(support / "config.yaml"),
            "RUNTIME_DIR": str(runtime),
            "CLI_LOCK_DIR": str(cli_lock),
        },
    )
    assert completed.returncode != 0


def test_fresh_activation_proof_allows_only_empty_layout_and_current_cli_lock(
    tmp_path: Path,
) -> None:
    support = tmp_path / "support"
    runtime = support / "runtime"
    state = support / "state"
    cli_lock = state / "cli-operation.lock"
    runtime.mkdir(parents=True)
    cli_lock.mkdir(parents=True)
    (cli_lock / "pid").write_text("123\n", encoding="utf-8")
    function = extract_shell_function(
        (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8"),
        "prove_fresh_dev_runtime_activation",
    )
    completed = subprocess.run(
        [
            "bash",
            "-c",
            (
                "set -u\n"
                f"{function}"
                "prove_fresh_dev_runtime_activation\n"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PYTHON_BIN": sys.executable,
            "APP_SUPPORT_DIR": str(support),
            "CONFIG_FILE": str(support / "config.yaml"),
            "RUNTIME_DIR": str(runtime),
            "CLI_LOCK_DIR": str(cli_lock),
        },
    )
    assert completed.returncode == 0, completed.stderr
