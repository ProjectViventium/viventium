import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_ROOT = ROOT / ".github" / "workflows"

PINNED_ACTION_RE = re.compile(r"uses:\s+[^\s@]+@([0-9a-f]{40})(?:\s|$)")
FLOATING_ACTION_RE = re.compile(r"uses:\s+[^\s@]+@v\d+(?:\s|$)")
CURRENT_NODE24_ACTION_PINS = {
    "actions/checkout": "df4cb1c069e1874edd31b4311f1884172cec0e10",  # v6.0.3
    "actions/setup-node": "48b55a011bda9f5d6aeb4c2d9c7362e8dae4041e",  # v6.4.0
    "actions/setup-python": "ece7cb06caefa5fff74198d8649806c4678c61a1",  # v6.3.0
    "actions/upload-artifact": "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",  # v7.0.1
    "actions/download-artifact": "3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c",  # v8.0.1
    "actions/attest": "f7c74d28b9d84cb8768d0b8ca14a4bac6ef463e6",  # v4.2.0
}


def _workflow_paths() -> list[Path]:
    return sorted({*WORKFLOW_ROOT.glob("*.yml"), *WORKFLOW_ROOT.glob("*.yaml")})


def _workflow_sources() -> dict[str, str]:
    return {
        path.name: path.read_text(encoding="utf-8")
        for path in _workflow_paths()
    }


def _live_eval_run_script() -> str:
    workflow = yaml.safe_load(
        (WORKFLOW_ROOT / "productivity-activation-live-eval.yml").read_text(encoding="utf-8")
    )
    steps = workflow["jobs"]["live-activation-eval"]["steps"]
    return next(step["run"] for step in steps if step.get("name") == "Run live activation eval gate")


def _native_sequence_run_script() -> str:
    workflow = yaml.safe_load(
        (WORKFLOW_ROOT / "native-payload-release.yml").read_text(encoding="utf-8")
    )
    steps = workflow["jobs"]["verify-release-sequence"]["steps"]
    return next(
        step["run"]
        for step in steps
        if step.get("name") == "Verify the candidate advances every signed Native release"
    )


def _native_component_policy_run_script() -> str:
    workflow = yaml.safe_load(
        (WORKFLOW_ROOT / "native-payload-candidate.yml").read_text(encoding="utf-8")
    )
    steps = workflow["jobs"]["assemble"]["steps"]
    return next(
        step["run"]
        for step in steps
        if step.get("name") == "Require the exact architecture and public component policy"
    )


def _release_component_refs_run_script() -> str:
    workflow = yaml.safe_load(
        (WORKFLOW_ROOT / "release-policy.yml").read_text(encoding="utf-8")
    )
    steps = workflow["jobs"]["manifests"]["steps"]
    return next(
        step["run"]
        for step in steps
        if step.get("name") == "Verify merged component refs are live public main tips"
    )


def _run_release_component_refs_step(
    tmp_path: Path,
    *,
    lock_payload: dict,
    remote_ref: str,
    failures_before_success: int = 0,
) -> subprocess.CompletedProcess[str]:
    (tmp_path / "components.lock.json").write_text(
        json.dumps(lock_payload), encoding="utf-8"
    )
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "python").symlink_to(sys.executable)
    fake_git = fake_bin / "git"
    fake_git.write_text(
        """#!/bin/sh
if [ "$1" != "-c" ] || [ "$2" != "credential.helper=" ] || \
   [ "$3" != "-c" ] || [ "$4" != "http.followRedirects=false" ] || \
   [ "$5" != "ls-remote" ] || [ "$6" != "--exit-code" ] || \
   [ "$7" != "--refs" ] || [ "${9}" != "refs/heads/main" ]; then
  echo "unexpected git arguments" >&2
  exit 2
fi
count=0
if [ -f "$FAKE_COUNTER" ]; then
  count="$(sed -n '1p' "$FAKE_COUNTER")"
fi
count=$((count + 1))
printf '%s\\n' "$count" > "$FAKE_COUNTER"
if [ "$count" -le "$FAKE_FAILURES_BEFORE_SUCCESS" ]; then
  echo "synthetic transient public lookup failure" >&2
  exit 69
fi
printf '%s\\trefs/heads/main\\n' "$FAKE_REMOTE_REF"
""",
        encoding="utf-8",
    )
    fake_git.chmod(0o755)
    return subprocess.run(
        ["bash", "-euo", "pipefail", "-c", _release_component_refs_run_script()],
        cwd=tmp_path,
        env={
            **os.environ,
            "FAKE_COUNTER": str(tmp_path / "git-call-count"),
            "FAKE_FAILURES_BEFORE_SUCCESS": str(failures_before_success),
            "FAKE_REMOTE_REF": remote_ref,
            "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
        },
        check=False,
        capture_output=True,
        text=True,
    )
def _run_native_component_policy_step(
    tmp_path: Path,
    *,
    lock_payload: dict,
    native_payload: dict,
) -> subprocess.CompletedProcess[str]:
    native_root = tmp_path / "release" / "native-payload"
    native_root.mkdir(parents=True)
    (tmp_path / "components.lock.json").write_text(
        json.dumps(lock_payload), encoding="utf-8"
    )
    (native_root / "components.json").write_text(
        json.dumps(native_payload), encoding="utf-8"
    )
    (native_root / "mongodb-redistribution-approved").write_text(
        "approved\n", encoding="utf-8"
    )
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "python").symlink_to(sys.executable)
    expected_arch = subprocess.run(
        ["uname", "-m"], check=True, capture_output=True, text=True
    ).stdout.strip()
    return subprocess.run(
        ["bash", "-euo", "pipefail", "-c", _native_component_policy_run_script()],
        cwd=tmp_path,
        env={
            **os.environ,
            "EXPECTED_ARCH": expected_arch,
            "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
        },
        check=False,
        capture_output=True,
        text=True,
    )


def test_github_actions_are_read_only_and_pinned_to_full_commit_shas() -> None:
    workflows = _workflow_sources()

    assert workflows
    for name, source in workflows.items():
        assert "permissions:\n  contents: read" in source, name
        assert not FLOATING_ACTION_RE.search(source), name
        for line in source.splitlines():
            if "uses:" in line and not line.lstrip().startswith("#"):
                assert PINNED_ACTION_RE.search(line), f"{name}: {line.strip()}"


def test_official_actions_use_reviewed_node24_pins() -> None:
    for workflow_name, source in _workflow_sources().items():
        for action, commit in CURRENT_NODE24_ACTION_PINS.items():
            for line in source.splitlines():
                if f"uses: {action}@" in line:
                    assert f"{action}@{commit}" in line, f"{workflow_name}: stale {action} pin"


def test_config_compile_uses_explicit_apple_silicon_and_intel_runners() -> None:
    source = _workflow_sources()["config-compile.yml"]

    assert "macos-15" in source
    assert "macos-15-intel" in source
    assert "macos-latest" not in source
    assert "expected_arch: arm64" in source
    assert "expected_arch: x86_64" in source
    assert "EXPECTED_ARCH: ${{ matrix.expected_arch }}" in source
    assert 'test "$(uname -m)" = "$EXPECTED_ARCH"' in source


def test_config_compile_runs_native_continuity_and_release_boundary_suites() -> None:
    source = _workflow_sources()["config-compile.yml"]

    assert "actions/setup-node@" in source
    assert 'node-version: "24"' in source
    assert 'python-version: "3.12"' in source
    assert 'python-version: "3.12.' not in source
    assert "Fetch and validate the exact pinned LibreChat component" in source
    assert "python scripts/viventium/bootstrap_components.py" in source
    assert '--config config.minimal.example.yaml' in source
    assert '--jobs 1' in source
    assert source.index("bootstrap_components.py") < source.index("python -m pytest")
    for suite in (
        "tests/release/test_continuity_bundle.py",
        "tests/release/test_native_candidate_transport.py",
        "tests/release/test_native_component_manifest.py",
        "tests/release/test_native_component_staging.py",
        "tests/release/test_native_continuity.py",
        "tests/release/test_native_macos_compatibility.py",
        "tests/release/test_native_release_sequence.py",
    ):
        assert suite in source


def test_hosted_setup_python_uses_available_minor_selector() -> None:
    selectors: list[tuple[str, str, str]] = []
    for path in _workflow_paths():
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job_name, job in workflow.get("jobs", {}).items():
            runner_contract = json.dumps(
                {
                    "runs-on": job.get("runs-on", ""),
                    "matrix": job.get("strategy", {}).get("matrix", {}),
                }
            )
            if "macos" not in runner_contract.lower():
                continue
            steps = job.get("steps", [])
            for step_index, step in enumerate(steps):
                if not str(step.get("uses", "")).startswith("actions/setup-python@"):
                    continue
                selector = str(step.get("with", {}).get("python-version", ""))
                selectors.append((path.name, job_name, selector))
                assert selector == "3.12", (
                    f"{path.name}:{job_name} must use the hosted 3.12 minor selector, "
                    f"not unsupported selector {selector!r}"
                )
                assert step_index + 1 < len(steps), f"{path.name}:{job_name} does not log Python"
                assert "python -VV" in str(steps[step_index + 1].get("run", "")), (
                    f"{path.name}:{job_name} must log the resolved hosted Python patch"
                )

    assert selectors


def test_pr_gate_push_triggers_only_default_branch() -> None:
    workflows = _workflow_sources()
    required_pr_workflows = (
        "config-compile.yml",
        "productivity-activation-contract.yml",
        "release-policy.yml",
        "secret-scan.yml",
    )
    for workflow_name in required_pr_workflows:
        trigger_source = workflows[workflow_name].split("\npermissions:", maxsplit=1)[0]
        assert "\n  pull_request:\n" in trigger_source
        assert "    paths:" not in trigger_source, (
            f"{workflow_name}: required pull-request checks must always report"
        )

    for workflow_name in (
        "config-compile.yml",
        "release-policy.yml",
        "secret-scan.yml",
    ):
        trigger_source = workflows[workflow_name].split("\npermissions:", maxsplit=1)[0]
        assert re.search(r"\n  push:\n    branches:\n      - main\n", trigger_source), (
            f"{workflow_name}: feature-branch pushes must not duplicate pull-request checks"
        )


def test_changed_release_workflows_do_not_persist_checkout_credentials() -> None:
    workflows = _workflow_sources()

    for name in (
        "config-compile.yml",
        "productivity-activation-live-eval.yml",
        "release-policy.yml",
        "secret-scan.yml",
        "native-payload-candidate.yml",
        "native-payload-release.yml",
    ):
        source = workflows[name]
        assert "concurrency:" in source, name
        assert source.count("persist-credentials: false") == source.count("actions/checkout@"), name


def test_release_policy_runs_qa_operating_contract_and_storage_guard() -> None:
    source = _workflow_sources()["release-policy.yml"]

    assert "tests/release/test_qa_operating_contract.py" in source
    assert "tests/release/test_qa_storage_guard.py" in source


def test_release_policy_executes_all_public_policy_suites_in_one_hosted_step() -> None:
    workflow = yaml.safe_load(
        (WORKFLOW_ROOT / "release-policy.yml").read_text(encoding="utf-8")
    )
    run_script = next(
        step["run"]
        for step in workflow["jobs"]["manifests"]["steps"]
        if "tests/release/test_public_bootstrap_manifests.py" in step.get("run", "")
    )

    for suite in (
        "tests/release/test_public_bootstrap_manifests.py",
        "tests/release/test_private_repo_resolution_contract.py",
        "tests/release/test_qa_storage_guard.py",
    ):
        assert suite in run_script
    assert (
        "tests/release/test_qa_operating_contract.py::"
        "test_release_tests_have_central_qa_ownership"
    ) in run_script


def test_release_policy_verifies_merged_component_refs_against_public_main(
    tmp_path: Path,
) -> None:
    expected_ref = "1" * 40
    lock_payload = {
        "publication_state": "merged",
        "components": [
            {
                "name": "example",
                "origin": "https://github.com/ProjectViventium/example.git",
                "ref": expected_ref,
            }
        ],
    }

    result = _run_release_component_refs_step(
        tmp_path,
        lock_payload=lock_payload,
        remote_ref=expected_ref,
    )

    assert result.returncode == 0, result.stderr
    assert "Verified 1 merged component refs" in result.stdout


def test_release_policy_rejects_stale_or_non_public_component_refs(
    tmp_path: Path,
) -> None:
    expected_ref = "1" * 40
    lock_payload = {
        "publication_state": "merged",
        "components": [
            {
                "name": "stale",
                "origin": "https://github.com/ProjectViventium/stale.git",
                "ref": expected_ref,
            },
            {
                "name": "private-origin",
                "origin": "ssh://git@example.test/private.git",
                "ref": expected_ref,
            },
        ],
    }

    result = _run_release_component_refs_step(
        tmp_path,
        lock_payload=lock_payload,
        remote_ref="2" * 40,
    )

    assert result.returncode == 1
    assert "stale: lock ref" in result.stderr
    assert "private-origin: origin is outside" in result.stderr


def test_release_policy_retries_a_transient_public_ref_failure(
    tmp_path: Path,
) -> None:
    expected_ref = "1" * 40
    lock_payload = {
        "publication_state": "merged",
        "components": [
            {
                "name": "example",
                "origin": "https://github.com/ProjectViventium/example.git",
                "ref": expected_ref,
            }
        ],
    }

    result = _run_release_component_refs_step(
        tmp_path,
        lock_payload=lock_payload,
        remote_ref=expected_ref,
        failures_before_success=1,
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "git-call-count").read_text(encoding="utf-8") == "2\n"


def test_node_ci_uses_project_node_major_and_secret_scan_image_is_immutable() -> None:
    workflows = _workflow_sources()

    assert 'node-version: "24"' in workflows["productivity-activation-live-eval.yml"]
    secret_scan = workflows["secret-scan.yml"]
    assert "zricethezav/gitleaks:v8.30.1@sha256:" in secret_scan
    assert "zricethezav/gitleaks:v8.24.2" not in secret_scan


def test_pull_request_workflows_never_reference_repository_secrets() -> None:
    for workflow_name, source in _workflow_sources().items():
        trigger_source = source.split("\npermissions:", maxsplit=1)[0]
        if not any(
            event in trigger_source
            for event in ("\n  pull_request:", "\n  pull_request_target:")
        ):
            continue
        assert "secrets." not in source, (
            f"{workflow_name}: pull_request-reachable workflows must not reference "
            "repository secrets because same-repository PR code is untrusted"
        )


def test_live_activation_eval_is_protected_and_scopes_secrets_to_the_eval_step() -> None:
    source = _workflow_sources()["productivity-activation-live-eval.yml"]
    trigger_source = source.split("\npermissions:", maxsplit=1)[0]
    workflow = yaml.load(source, Loader=yaml.BaseLoader)

    assert set(workflow["on"]) == {"workflow_dispatch"}
    assert "\n  pull_request:" not in trigger_source
    assert "\n  pull_request_target:" not in trigger_source
    assert "\n  push:" not in trigger_source
    assert "\n  workflow_dispatch:" in trigger_source
    assert "environment: productivity-activation-live-eval" in source
    assert "github.ref_protected == true" in source
    assert "github.ref == format('refs/heads/{0}', github.event.repository.default_branch)" in source

    job_prefix, eval_step = source.split("      - name: Run live activation eval gate", maxsplit=1)
    assert "Fetch and validate the exact pinned LibreChat component" in job_prefix
    assert "scripts/viventium/bootstrap_components.py" in job_prefix
    assert "--validate-only" in job_prefix
    assert "Skipping live activation eval" not in source
    assert "Install LibreChat workspace dependencies" in job_prefix
    assert "npm ci --ignore-scripts" in job_prefix
    assert "actions/setup-python@" not in job_prefix
    assert "pip install" not in job_prefix
    for secret_name in ("GROQ_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        secret_expression = "${{ secrets." + secret_name + " }}"
        assert secret_expression not in job_prefix
        assert secret_expression in eval_step


@pytest.mark.parametrize(
    ("summary", "eval_status", "expected_status", "expected_message"),
    [
        (
            {"resultCount": 4, "passCount": 4, "failCount": 0, "unavailableCount": 0},
            0,
            0,
            "",
        ),
        (
            {"resultCount": 4, "passCount": 3, "failCount": 0, "unavailableCount": 1},
            1,
            0,
            "recovered but still saw provider outages",
        ),
        (
            {"resultCount": 4, "passCount": 0, "failCount": 0, "unavailableCount": 4},
            1,
            1,
            "could not reach any classifier provider",
        ),
        (
            {"resultCount": 4, "passCount": 3, "failCount": 1, "unavailableCount": 0},
            1,
            1,
            "wrong activation decisions",
        ),
        (
            {"resultCount": 4, "passCount": 4, "failCount": 0, "unavailableCount": 0},
            1,
            1,
            "all scenarios passed but the eval process exited non-zero",
        ),
        (
            {"resultCount": 4, "passCount": 2, "failCount": 0, "unavailableCount": 1},
            0,
            1,
            "inconsistent scenario counts",
        ),
    ],
)
def test_live_activation_eval_shell_preserves_pass_failure_and_outage_semantics(
    tmp_path: Path,
    summary: dict[str, int],
    eval_status: int,
    expected_status: int,
    expected_message: str,
) -> None:
    real_node = shutil.which("node")
    assert real_node is not None

    report_source = tmp_path / "fake-report.json"
    report_source.write_text(json.dumps({"summary": summary, "results": []}), encoding="utf-8")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_node = fake_bin / "node"
    fake_node.write_text(
        """#!/bin/sh
if [ "$1" = "-" ]; then
  exec "$REAL_NODE" "$@"
fi
mkdir -p "$RUNNER_TEMP/productivity-activation-eval"
cp "$FAKE_REPORT_SOURCE" "$RUNNER_TEMP/productivity-activation-eval/productivity-activation-eval.json"
exit "$FAKE_EVAL_STATUS"
""",
        encoding="utf-8",
    )
    fake_node.chmod(0o755)

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "REAL_NODE": real_node,
            "RUNNER_TEMP": str(tmp_path / "runner"),
            "FAKE_REPORT_SOURCE": str(report_source),
            "FAKE_EVAL_STATUS": str(eval_status),
            "GROQ_API_KEY": "synthetic-test-value",
            "OPENAI_API_KEY": "synthetic-test-value",
            "ANTHROPIC_API_KEY": "synthetic-test-value",
        }
    )
    result = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", _live_eval_run_script()],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == expected_status, result.stdout + result.stderr
    if expected_message:
        assert expected_message.lower() in (result.stdout + result.stderr).lower()


def test_native_payload_release_is_protected_pinned_and_fails_closed_on_authority() -> None:
    source = _workflow_sources()["native-payload-release.yml"]

    assert "workflow_dispatch:" in source
    assert "pull_request_target" not in source
    assert "environment: native-payload-release" in source
    assert "contents: write" in source
    assert "attestations: write" in source
    assert "id-token: write" in source
    assert "release/native-payload/allowed_signers" in source
    assert "release/native-payload/apple-team-id" in source
    assert "Missing approved Native manifest allowed-signers policy" in source
    assert "Missing approved Apple Developer ID team policy" in source
    assert "Missing approved MongoDB redistribution policy" in source
    assert "NATIVE_MANIFEST_SIGNING_KEY_BASE64" in source
    assert "APPLE_DEVELOPER_ID_APPLICATION_P12_BASE64" in source
    assert "APPLE_NOTARY_KEY_P8_BASE64" in source
    assert "--options runtime" in source
    assert "--timestamp" in source
    assert "notarytool submit" in source
    assert "--wait" in source
    assert "stapler staple" in source
    assert "stapler validate" in source
    assert "spctl --assess --type execute" in source
    assert '"repos/${GITHUB_REPOSITORY}/immutable-releases"' in source
    assert 'policy.get("enabled") is not True' in source
    assert "gh release create" in source
    assert "--draft" in source
    assert "--verify-tag" in source
    assert "--channel stable" in source
    assert "--channel local-qa" not in source
    assert "unlisted Mach-O code paths" in source
    assert source.count("verify_native_public_safety.py") >= 2
    assert '--forbid-prefix "$GITHUB_WORKSPACE"' in source
    assert '--forbid-prefix "$RUNNER_TEMP"' in source
    assert source.count('--forbid-prefix "$HOME"') == source.count(
        "verify_native_public_safety.py"
    )


def test_native_payload_candidate_refuses_unmerged_review_heads() -> None:
    source = _workflow_sources()["native-payload-candidate.yml"]

    assert 'lock_state = lock.get("publication_state")' in source
    assert 'policy_state = policy.get("publication_state")' in source
    assert 'lock_state != "merged" or policy_state != "merged"' in source
    assert "Native candidate pins are not merged release commits" in source
    assert "Native LibreChat policy and parent component pin disagree" in source


def test_native_payload_candidate_policy_step_fails_closed_for_pending_pins(
    tmp_path: Path,
) -> None:
    lock_payload = json.loads((ROOT / "components.lock.json").read_text())
    native_payload = json.loads(
        (ROOT / "release" / "native-payload" / "components.json").read_text()
    )
    lock_payload["publication_state"] = "review-head-pending-merge"
    native_payload["publication_state"] = "review-head-pending-merge"

    completed = _run_native_component_policy_step(
        tmp_path,
        lock_payload=lock_payload,
        native_payload=native_payload,
    )

    assert completed.returncode != 0
    assert "Native candidate pins are not merged release commits" in completed.stderr


def test_native_payload_candidate_policy_step_accepts_merged_aligned_pins(
    tmp_path: Path,
) -> None:
    lock_payload = json.loads((ROOT / "components.lock.json").read_text())
    native_payload = json.loads(
        (ROOT / "release" / "native-payload" / "components.json").read_text()
    )

    assert lock_payload["publication_state"] == "merged"
    assert native_payload["publication_state"] == "merged"

    completed = _run_native_component_policy_step(
        tmp_path,
        lock_payload=lock_payload,
        native_payload=native_payload,
    )

    assert completed.returncode == 0, completed.stderr


def test_native_payload_candidate_policy_step_rejects_merged_misaligned_pin(
    tmp_path: Path,
) -> None:
    lock_payload = json.loads((ROOT / "components.lock.json").read_text())
    native_payload = json.loads(
        (ROOT / "release" / "native-payload" / "components.json").read_text()
    )
    lock_payload["publication_state"] = "merged"
    native_payload["publication_state"] = "merged"
    native_payload["librechat"]["commit"] = "0" * 40

    completed = _run_native_component_policy_step(
        tmp_path,
        lock_payload=lock_payload,
        native_payload=native_payload,
    )

    assert completed.returncode != 0
    assert "Native LibreChat policy and parent component pin disagree" in completed.stderr


def test_native_payload_release_serializes_and_advances_signed_release_history() -> None:
    source = _workflow_sources()["native-payload-release.yml"]

    assert "group: native-payload-release\n" in source
    assert "group: native-payload-release-${{ inputs.release_tag }}" not in source
    assert "verify_native_release_sequence.py" in source
    assert "verify_native_bootstrap_policy.py" in source
    assert '--candidate-sequence "$SEQUENCE"' in source
    assert '--allowed-signers "$api_root/bootstrap-allowed-signers"' in source
    assert "first Native release sequence must be 1" in (
        ROOT / "scripts" / "viventium" / "verify_native_release_sequence.py"
    ).read_text(encoding="utf-8")
    assert '"sequence": int(os.environ["SEQUENCE"])' in source
    assert '--sequence "$SEQUENCE"' in source
    assert "signed bootstrap app policy does not match its outer index" in source
    assert "signed payload policy does not match its bootstrap index" in source


def test_native_release_sequence_workflow_accepts_first_synthetic_release(tmp_path: Path) -> None:
    key = tmp_path / "signing-key"
    subprocess.run(
        [
            "/usr/bin/ssh-keygen",
            "-q",
            "-t",
            "ed25519",
            "-C",
            "qa@example.invalid",
            "-N",
            "",
            "-f",
            str(key),
        ],
        check=True,
    )
    public_fields = key.with_suffix(".pub").read_text(encoding="utf-8").split()
    public = " ".join(public_fields[:2])
    (tmp_path / "release/native-payload").mkdir(parents=True)
    (tmp_path / "release/native-payload/allowed_signers").write_text(
        f"releases@viventium.example {public}\n", encoding="utf-8"
    )
    (tmp_path / "release/native-payload/apple-team-id").write_text(
        "ABCDE12345\n", encoding="utf-8"
    )
    (tmp_path / "install.sh").write_text(
        f'NATIVE_BOOTSTRAP_ALLOWED_SIGNER="bootstrap@viventium.example {public}"\n'
        'NATIVE_BOOTSTRAP_TEAM_ID="ABCDE12345"\n'
        'NATIVE_BOOTSTRAP_MINIMUM_SEQUENCE="1"\n',
        encoding="utf-8",
    )
    scripts = tmp_path / "scripts/viventium"
    scripts.mkdir(parents=True)
    for name in ("verify_native_bootstrap_policy.py", "verify_native_release_sequence.py"):
        shutil.copy2(ROOT / "scripts/viventium" / name, scripts / name)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "python").symlink_to(sys.executable)
    fake_gh = fake_bin / "gh"
    fake_gh.write_text("#!/bin/sh\nprintf '[]\\n'\n", encoding="utf-8")
    fake_gh.chmod(0o755)
    environment = {
        **os.environ,
        "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
        "RUNNER_TEMP": str(tmp_path / "runner"),
        "GITHUB_REPOSITORY": "ProjectViventium/viventium",
        "GH_TOKEN": "synthetic-not-a-secret",
        "RELEASE_TAG": "v0.4.0",
        "SEQUENCE": "1",
    }

    completed = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", _native_sequence_run_script()],
        cwd=tmp_path,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_native_payload_release_pins_candidate_to_same_repo_commit_and_architecture() -> None:
    source = _workflow_sources()["native-payload-release.yml"]

    assert 'candidate["head_sha"] != os.environ["GITHUB_SHA"]' in source
    assert 'candidate["head_repository"]["full_name"] != os.environ["GITHUB_REPOSITORY"]' in source
    assert 'candidate["path"] != ".github/workflows/native-payload-candidate.yml"' in source
    assert 'candidate["event"] != "workflow_dispatch"' in source
    assert "build_native_payload._inventory_payload(payload_root)" in source
    assert "native-payload-root-${EXPECTED_ARCH}" in source
    assert 'test "$(uname -m)" = "$EXPECTED_ARCH"' in source
    assert "macos-15" in source
    assert "macos-15-intel" in source
    assert "macos-latest" not in source
    assert "import assemble_native_payload" in source
    assert re.search(
        r"assemble_native_payload\.release_component_manifest\(\s*components,\s*os\.environ\[\"EXPECTED_ARCH\"\]\s*\)",
        source,
    )
    assert 'metadata.get("components") != expected_components' in source
    assert "transport_native_candidate.py unpack" in source
    assert "native-payload-root-${EXPECTED_ARCH}.tar" in source
    assert "native-payload-root-${EXPECTED_ARCH}.tar.sha256" in source
    assert "path: dist/candidate/*" not in _workflow_sources()["native-payload-candidate.yml"]


def test_native_release_signs_notarizes_packages_and_reverifies_bootstrap_asset() -> None:
    source = _workflow_sources()["native-payload-release.yml"]

    for required in (
        "candidate/bootstrap/ViventiumBootstrap.app",
        "release.json",
        '"$bootstrap_resources/allowed_signers"',
        "ViventiumBootstrap-${EXPECTED_ARCH}.zip",
        "pre-staple-bootstrap.zip",
        "stapler staple \"$bootstrap_app\"",
        "spctl --assess --type execute --verbose=2 \"$bootstrap_app\"",
        '"$bootstrap_app/Contents/MacOS/ViventiumBootstrap" --self-check',
        "ViventiumBootstrap-arm64.zip",
        "ViventiumBootstrap-x86_64.zip",
    ):
        assert required in source
    assert source.count("notarytool submit") >= 3
    assert "candidate/bootstrap" in source


def test_native_release_bootstrap_index_round_trips_through_independent_verifier(
    tmp_path: Path,
) -> None:
    workflow = yaml.safe_load(
        (WORKFLOW_ROOT / "native-payload-release.yml").read_text(encoding="utf-8")
    )
    build_run = next(
        step["run"]
        for step in workflow["jobs"]["sign-bootstrap-manifest"]["steps"]
        if step.get("name") == "Build and sign exact dual-architecture bootstrap index"
    )
    build_python = build_run.split("python - <<'PY'\n", 1)[1].split("\nPY", 1)[0]
    verify_run = next(
        step["run"]
        for step in workflow["jobs"]["verify-installed-artifacts"]["steps"]
        if step.get("name") == "Verify, stage, and health-check exact assets"
    )
    verify_python = verify_run.split(
        'python - "$bootstrap_index" "$EXPECTED_ARCH" "$bootstrap_archive" '
        '"$embedded_policy" "$payload_manifest" <<\'PY\'\n',
        1,
    )[1].split("\nPY", 1)[0]

    assets = tmp_path / "bootstrap-assets"
    assets.mkdir()
    (tmp_path / "bootstrap-index").mkdir()
    expected_uncompressed: dict[str, int] = {}
    for arch in ("arm64", "x86_64"):
        filename = f"ViventiumBootstrap-{arch}.zip"
        archive = assets / filename
        content = f"synthetic-{arch}-bootstrap".encode()
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("ViventiumBootstrap.app/Contents/MacOS/ViventiumBootstrap", content)
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        (assets / f"{filename}.sha256").write_text(
            f"{digest} {filename}\n", encoding="utf-8"
        )
        expected_uncompressed[arch] = len(content)

    env = {
        **os.environ,
        "RELEASE_TAG": "v0.0.0-synthetic",
        "RELEASE_ID": "synthetic-release",
        "SEQUENCE": "7",
    }
    built = subprocess.run(
        [sys.executable, "-c", build_python],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
    )
    assert built.returncode == 0, built.stderr

    index = tmp_path / "bootstrap-index" / "viventium-native-bootstrap-manifest.json"
    manifest = json.loads(index.read_text(encoding="utf-8"))
    for arch, expected_size in expected_uncompressed.items():
        assert manifest["artifacts"][arch]["uncompressed_size"] == expected_size

    embedded = tmp_path / "release.json"
    embedded.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "release_base": "https://github.com/ProjectViventium/viventium/releases/download",
                "release_tag": env["RELEASE_TAG"],
                "release_id": env["RELEASE_ID"],
                "sequence": int(env["SEQUENCE"]),
            }
        ),
        encoding="utf-8",
    )
    payload_manifest = tmp_path / "payload-manifest.json"
    payload_manifest.write_text(
        json.dumps({"release_id": env["RELEASE_ID"], "sequence": int(env["SEQUENCE"])}),
        encoding="utf-8",
    )
    verified = subprocess.run(
        [
            sys.executable,
            "-c",
            verify_python,
            str(index),
            "arm64",
            str(assets / "ViventiumBootstrap-arm64.zip"),
            str(embedded),
            str(payload_manifest),
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
    )
    assert verified.returncode == 0, verified.stderr


def test_native_release_uploads_only_allowlisted_sanitized_public_assets() -> None:
    source = _workflow_sources()["native-payload-release.yml"]

    assert '"$output_dir/final-notarization.json"' not in source
    assert '"${work_root}/final-notarization.json"' in source
    assert "mapfile -t assets < <(find release-assets" not in source
    assert "allowed_asset_names" in source
    assert "notarization-status" not in source
    assert "viventium-native-bootstrap-manifest.json" in source
    assert "viventium-native-bootstrap-manifest.json.sig" in source


def test_native_release_requires_exact_compliance_bundle_and_license_scan() -> None:
    source = _workflow_sources()["native-payload-release.yml"]

    for required in (
        "native-sbom.spdx.json",
        "native-third-party-notices.txt",
        "native-license-scan.json",
        "generate_native_compliance.py",
        "verify_native_compliance.py",
    ):
        assert required in source
