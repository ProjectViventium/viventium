from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import stat
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from qa_control_test_support import write_artifact_identity

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "viventium" / "feelings_qa_parent_control.py"
SESSION_SCRIPT = ROOT / "scripts" / "viventium" / "local_qa_runtime_control.py"
CLI = ROOT / "bin" / "viventium"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def sha_ref(value: str) -> str:
    return f"sha256:{sha(value)}"


def fixture(tmp_path: Path):
    session = load(SESSION_SCRIPT, "local_qa_runtime_control_for_emo047")
    installed = tmp_path / "installed"
    installed.mkdir()
    runtime = tmp_path / "runtime"
    state = runtime / "local-qa" / "active.json"
    identity = runtime / "parallel-work-artifact-identity.json"
    request = runtime / "parallel-work-local-qa-request.json"
    write_artifact_identity(installed, identity)
    request.write_text(
        '{"contractVersion":1,"mode":"local-qa","requested":true}\n',
        encoding="utf-8",
    )
    os.chmod(request, 0o600)
    now = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
    session.activate_session(
        state_path=state,
        installed_root=installed,
        artifact_identity_path=identity,
        local_qa_request_path=request,
        case_id="EMO-UC-047",
        expires_in_seconds=900,
        now=now,
        token_bytes=lambda size: b"f" * size,
    )
    return installed, state, identity, request, now


def placement(
    request_ref: str, snapshot_hash: str, expected_count: int
) -> dict[str, object]:
    return {
        "event": "feelings.inject.final_run",
        "requestRef": request_ref,
        "route": "main_conscious_agent",
        "snapshotHash": snapshot_hash,
        "capsuleOccurrenceCount": expected_count,
        "placement": "final_instruction_layer" if expected_count else "absent",
        "presentInFinalRun": bool(expected_count),
        "trailingInstructionChars": 0,
    }


def main_receipt(
    name: str, request_ref: str, snapshot_hash: str, expected_count: int
) -> dict[str, object]:
    return {
        "event": "viventium_text_main_winning_native_provider_receipt",
        "requestRef": request_ref,
        "receiptRef": f"native_provider_receipt_sha256:{sha(name + '-receipt')}",
        "nativeRequestSha256": sha(name + "-native-request"),
        "snapshotHash": snapshot_hash,
        "capsuleOccurrenceCount": expected_count,
        "mainInstructionOccurrenceCount": 1,
        "outputKind": "visible_text_delta",
        "provider": "anthropic",
        "model": "claude-opus-5",
        "status": 200,
    }


def semantic(name: str) -> dict[str, object]:
    return {
        "status": "pass",
        "answerSha256": sha(name + "-answer"),
        "rubricEvidenceSha256": sha(name + "-semantic-evidence"),
    }


def worker(name: str, snapshot_hash: str, expected_count: int) -> dict[str, object]:
    runtime = "claude-code" if name.endswith("a") else "codex-cli"
    native_placement = (
        "append_system_prompt_file"
        if runtime == "claude-code"
        else "codex_developer_instructions"
    )
    return {
        "workerRef": sha_ref(name + "-worker"),
        "instructionSha256": sha(name + "-instruction"),
        "projection": {
            "snapshotHash": snapshot_hash,
            "materializedCapsuleSha256": snapshot_hash if expected_count else "none",
            "capsuleOccurrenceCount": expected_count,
            "placement": "final_instruction_layer" if expected_count else "absent",
            "trailingInstructionChars": 0,
        },
        "nativeAuthorityReceipt": {
            "protocol": "glasshive.native_provider_authority_receipt.v1",
            "runRef": sha_ref(name + "-run"),
            "runtime": runtime,
            "authoritySha256": sha(name + "-authority"),
            "feelingCapsuleCount": expected_count,
            "placement": native_placement,
            "materialized": True,
        },
    }


def scenario(
    name: str,
    scope: str,
    snapshot_hash: str,
    expected_count: int,
    worker_count: int,
) -> dict[str, object]:
    request_ref = sha_ref(name + "-request")
    return {
        "name": name,
        "scope": scope,
        "feelingsEnabled": name != "off_during_workers",
        "requestRef": request_ref,
        "snapshotHash": snapshot_hash,
        "sourcePlacement": placement(request_ref, snapshot_hash, expected_count),
        "winningNativeReceipt": main_receipt(
            name, request_ref, snapshot_hash, expected_count
        ),
        "semanticVerdict": semantic(name),
        "workers": [
            worker(f"{name}-{suffix}", snapshot_hash, expected_count if scope == "all_agents" else 0)
            for suffix in ("a", "b")[:worker_count]
        ],
    }


def valid_evidence(state: Path) -> dict[str, object]:
    session = json.loads(state.read_text(encoding="utf-8"))
    first_hash = sha("request-pinned-state-a")
    second_hash = sha("request-pinned-state-b")
    conscious_hash = sha("conscious-only-state")
    scenarios = [
        scenario("all_agents_before_delegation", "all_agents", first_hash, 1, 0),
        scenario("all_agents_during_workers", "all_agents", second_hash, 1, 2),
        scenario(
            "conscious_agent_during_workers",
            "conscious_agent",
            conscious_hash,
            1,
            2,
        ),
        scenario("off_during_workers", "conscious_agent", "none", 0, 2),
    ]
    return {
        "contractVersion": 1,
        "caseId": "EMO-UC-047",
        "sessionRef": session["sessionRef"],
        "artifactIdentityDigest": session["artifactIdentityDigest"],
        "componentArtifactDigest": session["componentArtifactDigest"],
        "synthetic": True,
        "requestIsolation": {
            "firstRequestRef": scenarios[0]["requestRef"],
            "secondRequestRef": scenarios[1]["requestRef"],
            "firstSnapshotHash": first_hash,
            "secondSnapshotHash": second_hash,
            "firstRequestPinnedAtMs": 1787659200000,
            "firstProviderStartedAtMs": 1787659200010,
            "stateChangedAtMs": 1787659200050,
            "secondRequestPinnedAtMs": 1787659200060,
            "firstPresentationCommittedAtMs": 1787659200500,
            "overlapObserved": True,
            "stateChangedBeforeSecondRequest": True,
            "firstTypedFallback": {
                "failureClass": "provider_quota_exhausted",
                "fallbackUsed": True,
                "retryAfterHonored": True,
                "capabilitiesPreserved": True,
                "winningSnapshotHash": first_hash,
            },
        },
        "safetyAudit": {
            "hostPluginDenylistEnabled": True,
            "parallelWorkDefaultAvailable": False,
            "parallelWorkDefaultMode": "focused",
            "privateStateMountCount": 0,
            "feelingsMcpServerCount": 0,
            "workerFeelingsPluginCount": 0,
            "workerAuditCount": 6,
            "auditEvidenceSha256": sha("scope-mount-mcp-audit"),
        },
        "scenarios": scenarios,
    }


def write_private(path: Path, value: dict[str, object]) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)


def test_verifies_candidate_bound_main_receipts_and_two_worker_scope_parity(
    tmp_path: Path,
) -> None:
    module = load(SCRIPT, "feelings_qa_parent_control")
    installed, state, identity, request, now = fixture(tmp_path)
    evidence = tmp_path / "emo047-evidence.json"
    write_private(evidence, valid_evidence(state))
    descriptor = os.open(evidence, os.O_RDONLY)
    try:
        result = module.verify_installed_evidence(
            state_path=state,
            installed_root=installed,
            artifact_identity_path=identity,
            local_qa_request_path=request,
            evidence_fd=descriptor,
            now=now + timedelta(seconds=1),
        )
    finally:
        os.close(descriptor)

    assert result == {
        "candidateBound": True,
        "caseId": "EMO-UC-047",
        "componentArtifactDigest": json.loads(state.read_text())["componentArtifactDigest"],
        "evidenceDigest": sha_ref(evidence.read_text(encoding="utf-8")),
        "mainReceiptCount": 4,
        "requestPinned": True,
        "scenarioCount": 4,
        "semanticPassCount": 4,
        "sessionRef": json.loads(state.read_text())["sessionRef"],
        "status": "verified",
        "workerReceiptCount": 6,
    }


def test_public_cli_exposes_private_fd_verifier_without_forwarding_the_path() -> None:
    source = CLI.read_text(encoding="utf-8")
    branch = source.split("      verify-emo-feelings)", 1)[1].split(
        "      arm-telegram-race)", 1
    )[0]

    assert "verify-emo-feelings --evidence <private-emo-uc-047.json>" in source
    assert 'exec 9<"$3"' in branch
    assert "feelings_qa_parent_control.py" in branch
    assert "--evidence-fd 9" in branch
    assert '"$3"' not in branch.split("feelings_qa_parent_control.py", 1)[1]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value["scenarios"][1]["workers"].pop(),
        lambda value: value["scenarios"][1]["workers"][0]["projection"].update(
            {"snapshotHash": sha("wrong-state")}
        ),
        lambda value: value["scenarios"][1]["workers"][0]["nativeAuthorityReceipt"].update(
            {"feelingCapsuleCount": 0}
        ),
        lambda value: value["scenarios"][1]["workers"][0]["projection"].update(
            {"materializedCapsuleSha256": sha("wrong-materialized-capsule")}
        ),
        lambda value: value["scenarios"][2]["workers"][0]["projection"].update(
            {"capsuleOccurrenceCount": 1}
        ),
        lambda value: value["scenarios"][3]["winningNativeReceipt"].update(
            {"capsuleOccurrenceCount": 1}
        ),
        lambda value: value["scenarios"][1]["winningNativeReceipt"].update(
            {"requestRef": sha_ref("wrong-request")}
        ),
    ],
)
def test_rejects_missing_duplicate_or_scope_wrong_worker_capsules(
    tmp_path: Path, mutate
) -> None:
    module = load(SCRIPT, "feelings_qa_parent_control_parity")
    _installed, state, _identity, _request, _now = fixture(tmp_path)
    value = valid_evidence(state)
    mutate(value)
    with pytest.raises(ValueError, match="evidence"):
        module.validate_evidence(value)


def test_rejects_cross_request_fallback_hash_or_unproven_overlap(tmp_path: Path) -> None:
    module = load(SCRIPT, "feelings_qa_parent_control_isolation")
    _installed, state, _identity, _request, _now = fixture(tmp_path)
    value = valid_evidence(state)
    value["requestIsolation"]["firstTypedFallback"]["winningSnapshotHash"] = sha(
        "request-pinned-state-b"
    )
    with pytest.raises(ValueError, match="evidence"):
        module.validate_evidence(value)

    value = valid_evidence(state)
    value["requestIsolation"]["overlapObserved"] = False
    with pytest.raises(ValueError, match="evidence"):
        module.validate_evidence(value)

    value = valid_evidence(state)
    value["requestIsolation"]["secondRequestPinnedAtMs"] = value[
        "requestIsolation"
    ]["firstPresentationCommittedAtMs"]
    with pytest.raises(ValueError, match="evidence"):
        module.validate_evidence(value)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("hostPluginDenylistEnabled", False),
        ("parallelWorkDefaultAvailable", True),
        ("parallelWorkDefaultMode", "parallel"),
        ("privateStateMountCount", 1),
        ("feelingsMcpServerCount", 1),
        ("workerFeelingsPluginCount", 1),
    ],
)
def test_rejects_dark_default_denylist_mount_mcp_or_duplicate_plugin_gap(
    tmp_path: Path, field: str, value: object
) -> None:
    module = load(SCRIPT, "feelings_qa_parent_control_safety")
    _installed, state, _identity, _request, _now = fixture(tmp_path)
    evidence = valid_evidence(state)
    evidence["safetyAudit"][field] = value
    with pytest.raises(ValueError, match="evidence"):
        module.validate_evidence(evidence)


def test_private_fd_and_strict_json_fail_closed_without_leaking_values(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module = load(SCRIPT, "feelings_qa_parent_control_private_fd")
    installed, state, identity, request, _now = fixture(tmp_path)
    evidence = tmp_path / "private-canary-evidence.json"
    value = valid_evidence(state)
    value["privateUserEmail"] = "private-canary@example.invalid"
    write_private(evidence, value)
    evidence.chmod(0o644)
    descriptor = os.open(evidence, os.O_RDONLY)
    try:
        assert module.main(
            [
                "verify",
                "--state",
                str(state),
                "--installed-root",
                str(installed),
                "--artifact-identity",
                str(identity),
                "--local-qa-request",
                str(request),
                "--evidence-fd",
                str(descriptor),
            ]
        ) == 2
    finally:
        os.close(descriptor)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err) == {
        "caseId": "EMO-UC-047",
        "error": "operation_failed",
    }
    assert "private-canary" not in captured.err


def test_rejects_duplicate_json_keys_nonregular_fd_and_candidate_drift(
    tmp_path: Path,
) -> None:
    module = load(SCRIPT, "feelings_qa_parent_control_adversarial")
    installed, state, identity, request, now = fixture(tmp_path)
    evidence = tmp_path / "emo047-evidence.json"
    value = valid_evidence(state)
    raw = json.dumps(value).replace(
        '"caseId": "EMO-UC-047"',
        '"caseId": "EMO-UC-047", "caseId": "EMO-UC-047"',
        1,
    )
    evidence.write_text(raw, encoding="utf-8")
    evidence.chmod(0o600)
    descriptor = os.open(evidence, os.O_RDONLY)
    try:
        with pytest.raises(ValueError, match="evidence"):
            module.verify_installed_evidence(
                state_path=state,
                installed_root=installed,
                artifact_identity_path=identity,
                local_qa_request_path=request,
                evidence_fd=descriptor,
                now=now + timedelta(seconds=1),
            )
    finally:
        os.close(descriptor)

    read_fd, write_fd = os.pipe()
    try:
        with pytest.raises(ValueError, match="evidence"):
            module.read_private_evidence_fd(read_fd)
    finally:
        os.close(read_fd)
        os.close(write_fd)

    write_private(evidence, valid_evidence(state))
    identity.write_text('{"contractVersion":1,"changed":true}\n', encoding="utf-8")
    descriptor = os.open(evidence, os.O_RDONLY)
    try:
        with pytest.raises(ValueError, match="artifact identity"):
            module.verify_installed_evidence(
                state_path=state,
                installed_root=installed,
                artifact_identity_path=identity,
                local_qa_request_path=request,
                evidence_fd=descriptor,
                now=now + timedelta(seconds=1),
            )
    finally:
        os.close(descriptor)


def test_unknown_fields_raw_text_and_duplicate_worker_receipts_fail_closed(
    tmp_path: Path,
) -> None:
    module = load(SCRIPT, "feelings_qa_parent_control_public_safe")
    _installed, state, _identity, _request, _now = fixture(tmp_path)
    value = valid_evidence(state)
    value["rawTelegramAnswer"] = "synthetic but raw text"
    with pytest.raises(ValueError, match="evidence"):
        module.validate_evidence(value)

    value = valid_evidence(state)
    workers = value["scenarios"][1]["workers"]
    workers[1]["workerRef"] = workers[0]["workerRef"]
    with pytest.raises(ValueError, match="evidence"):
        module.validate_evidence(value)


@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        (("scenarios", 3, "sourcePlacement", "capsuleOccurrenceCount"), False),
        (("scenarios", 1, "winningNativeReceipt", "capsuleOccurrenceCount"), True),
        (("scenarios", 2, "workers", 0, "projection", "trailingInstructionChars"), False),
        (("safetyAudit", "privateStateMountCount"), False),
    ],
)
def test_integer_receipt_fields_reject_boolean_type_confusion(
    tmp_path: Path, path: tuple[object, ...], replacement: object
) -> None:
    module = load(SCRIPT, "feelings_qa_parent_control_type_confusion")
    _installed, state, _identity, _request, _now = fixture(tmp_path)
    value = valid_evidence(state)
    target: object = value
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = replacement

    with pytest.raises(ValueError, match="evidence"):
        module.validate_evidence(value)


def test_expired_session_cannot_verify_installed_evidence(tmp_path: Path) -> None:
    module = load(SCRIPT, "feelings_qa_parent_control_expired")
    installed, state, identity, request, now = fixture(tmp_path)
    evidence = tmp_path / "emo047-evidence.json"
    write_private(evidence, valid_evidence(state))
    descriptor = os.open(evidence, os.O_RDONLY)
    try:
        with pytest.raises(ValueError, match="expired"):
            module.verify_installed_evidence(
                state_path=state,
                installed_root=installed,
                artifact_identity_path=identity,
                local_qa_request_path=request,
                evidence_fd=descriptor,
                now=now + timedelta(minutes=16),
            )
    finally:
        os.close(descriptor)


def test_parent_cli_has_no_raw_scope_or_private_path_options() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "--evidence-fd" in source
    assert "--owner" not in source
    assert "--user" not in source
    assert "--conversation" not in source
    assert "--message" not in source
    assert "--worker-id" not in source
    assert "--run-id" not in source
    assert "--evidence-path" not in source
    assert stat.S_ISREG(SCRIPT.stat().st_mode)
