from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import sys
from datetime import timedelta
from pathlib import Path

import pytest
from qa_control_test_support import _load_release_gate
from test_feelings_qa_parent_control import fixture as installed_fixture
from test_feelings_qa_parent_control import valid_evidence

ROOT = Path(__file__).resolve().parents[2]
VERIFIER_PATH = ROOT / "qa/emotional-cortex/scripts/run_emo_uc_047.py"
PARENT_CONTROL_PATH = ROOT / "scripts/viventium/feelings_qa_parent_control.py"
SHARED_REGISTRY_PATH = ROOT / "scripts/viventium/parallel_work_qa_evidence.py"
REQUIRED_SERVICES = ["glasshive-runtime", "librechat-core"]
SPECIALISTS = (
    "emotional_resonance",
    "product_help",
    "productivity",
    "red_team",
    "research",
)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_verifier():
    return load_module(VERIFIER_PATH, "emo047_focused_semantic_verifier")


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def digest_ref(value: str) -> str:
    return "sha256:" + digest(value)


def canonical_digest(value: object) -> str:
    return digest(json.dumps(value, sort_keys=True, separators=(",", ":")))


def write_private(path: Path, value: object) -> str:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    path.write_text(raw, encoding="utf-8")
    path.chmod(0o600)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def layer_receipt(
    *,
    request_ref: str,
    snapshot_hash: str,
    state_version: int | None,
    capsule_count: int,
) -> dict[str, object]:
    return {
        "requestRef": request_ref,
        "snapshotHash": snapshot_hash,
        "stateVersion": state_version,
        "capsuleSha256": snapshot_hash if capsule_count else "none",
        "capsuleOccurrenceCount": capsule_count,
        "structuralLayerIndex": 1,
        "surfaceLayerIndex": 2,
        "capsuleLayerIndex": 3 if capsule_count else None,
        "finalLayerIndex": 3 if capsule_count else 2,
        "trailingInstructionChars": 0,
    }


def scenario_receipt(
    source: dict[str, object], *, state_version: int | None
) -> dict[str, object]:
    request_ref = str(source["requestRef"])
    snapshot_hash = str(source["snapshotHash"])
    enabled = source["feelingsEnabled"] is True
    main_count = 1 if enabled else 0
    worker_count = 1 if enabled and source["scope"] == "all_agents" else 0
    main = source["winningNativeReceipt"]
    assert isinstance(main, dict)
    workers: list[dict[str, object]] = []
    for worker in source["workers"]:
        native = worker["nativeAuthorityReceipt"]
        workers.append(
            {
                **layer_receipt(
                    request_ref=request_ref,
                    snapshot_hash=snapshot_hash,
                    state_version=state_version,
                    capsule_count=worker_count,
                ),
                "workerRef": worker["workerRef"],
                "runRef": native["runRef"],
                "runtime": native["runtime"],
                "instructionSha256": worker["instructionSha256"],
                "authoritySha256": native["authoritySha256"],
                "nativePlacement": native["placement"],
            }
        )
    semantic = source["semanticVerdict"]
    assert isinstance(semantic, dict)
    return {
        "name": source["name"],
        "requestRef": request_ref,
        "snapshotHash": snapshot_hash,
        "stateVersion": state_version,
        "sourceReceipt": layer_receipt(
            request_ref=request_ref,
            snapshot_hash=snapshot_hash,
            state_version=state_version,
            capsule_count=main_count,
        ),
        "providerReceipt": {
            **layer_receipt(
                request_ref=request_ref,
                snapshot_hash=snapshot_hash,
                state_version=state_version,
                capsule_count=main_count,
            ),
            "receiptRef": main["receiptRef"],
            "nativeRequestSha256": main["nativeRequestSha256"],
            "outputKind": "visible_text_delta",
            "winning": True,
        },
        "workerReceipts": workers,
        "semanticReceipt": {
            "requestRef": request_ref,
            "snapshotHash": snapshot_hash,
            "stateVersion": state_version,
            "answerSha256": semantic["answerSha256"],
            "rubricEvidenceSha256": semantic["rubricEvidenceSha256"],
            "status": "pass",
            "materiallyFollowsPinnedState": enabled,
            "inventedFeelingCount": 0,
            "privateCapsuleDisclosed": False,
            "visibleAnswerCount": 1,
            "surface": "telegram",
        },
    }


def semantic_projection(parent: dict[str, object]) -> dict[str, object]:
    scenarios = [
        scenario_receipt(scenario, state_version=version)
        for scenario, version in zip(
            parent["scenarios"], (17, 18, 19, None), strict=True
        )
    ]
    first, second = scenarios[:2]
    capability_ids = ["connected_accounts", "file_tools", "parallel_work"]
    capability_digest = canonical_digest(capability_ids)
    attempts: list[dict[str, object]] = []
    for role in ("primary", "fallback"):
        winning = role == "fallback"
        attempts.append(
            {
                **layer_receipt(
                    request_ref=str(first["requestRef"]),
                    snapshot_hash=str(first["snapshotHash"]),
                    state_version=17,
                    capsule_count=1,
                ),
                "role": role,
                "attemptRef": digest_ref("first-request-" + role),
                "outcome": "won" if winning else "recoverable_failure",
                "failureClass": None if winning else "provider_quota_exhausted",
                "nativeReceiptRef": (
                    first["providerReceipt"]["receiptRef"]
                    if winning
                    else "native_provider_receipt_sha256:"
                    + digest("first-request-primary-native")
                ),
                "nativeRequestSha256": (
                    first["providerReceipt"]["nativeRequestSha256"]
                    if winning
                    else digest("first-request-primary-payload")
                ),
                "capabilityIds": list(capability_ids),
                "capabilitiesSha256": capability_digest,
            }
        )

    specialists = [
        {
            "specialistId": specialist,
            "requestRef": second["requestRef"],
            "snapshotHash": second["snapshotHash"],
            "stateVersion": 18,
            "authoritySha256": digest("independent-" + specialist),
            "capsuleOccurrenceCount": 0,
            "skipReason": "specialist_cortex_independent",
        }
        for specialist in SPECIALISTS
    ]
    return {
        "caseId": "EMO-UC-047",
        "contractVersion": 1,
        "sessionRef": parent["sessionRef"],
        "artifactIdentityDigest": parent["artifactIdentityDigest"],
        "componentArtifactDigest": parent["componentArtifactDigest"],
        "scenarios": scenarios,
        "fallbackContinuity": {
            "requestRef": first["requestRef"],
            "snapshotHash": first["snapshotHash"],
            "stateVersion": 17,
            "capsuleSha256": first["snapshotHash"],
            "failureClass": "provider_quota_exhausted",
            "fallbackUsed": True,
            "retryAfterHonored": True,
            "declaredCapabilityIds": capability_ids,
            "declaredCapabilitiesSha256": capability_digest,
            "attempts": attempts,
        },
        "phaseBContinuity": {
            **layer_receipt(
                request_ref=str(second["requestRef"]),
                snapshot_hash=str(second["snapshotHash"]),
                state_version=18,
                capsule_count=1,
            ),
            "receiptRef": "native_provider_receipt_sha256:"
            + digest("independent-phase-b-receipt"),
            "mainNativeSessionRef": digest_ref("main-native-session"),
            "phaseBNativeSessionRef": digest_ref("phase-b-native-session"),
            "mainContinuityIdentitySha256": digest("canonical-continuity"),
            "phaseBContinuityIdentitySha256": digest("canonical-continuity"),
            "mainWorkerInterrupted": False,
            "mainWorkerReplaced": False,
        },
        "specialistReceipts": specialists,
        "privacyAudit": {
            "hostPluginDenylistEnabled": True,
            "deniedPluginIds": ["viventium-feelings@project-viventium"],
            "unrelatedPluginsPreserved": True,
            "privateStateMountCount": 0,
            "privateStatePersistenceCount": 0,
            "privateCapsuleProjectionCount": 0,
            "feelingsMcpServerCount": 0,
            "workerFeelingsPluginCount": 0,
        },
    }


@pytest.fixture
def installed_bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    verifier = load_verifier()
    installed, state, identity, request, started = installed_fixture(tmp_path)
    run_at = started + timedelta(seconds=30)
    checked_at = run_at + timedelta(seconds=5)
    session = json.loads(state.read_text(encoding="utf-8"))
    parent = valid_evidence(state)
    identity_payload = json.loads(identity.read_text(encoding="utf-8"))
    candidate_digest, artifact_digest = _load_release_gate()._qa_candidate_digests(
        identity_payload
    )
    service_status = {
        "caseId": "EMO-UC-047",
        "expiresAt": session["expiresAt"],
        "mode": "emo_uc_047",
        "sessionRef": session["sessionRef"],
        "restartState": "ready",
        "requiredServices": list(REQUIRED_SERVICES),
        "acknowledgedServices": list(REQUIRED_SERVICES),
        "missingServices": [],
        "serviceAckDigest": digest_ref("exact-live-service-acknowledgements"),
    }
    service_projection = {
        **service_status,
        "contractVersion": 1,
        "artifactIdentityDigest": session["artifactIdentityDigest"],
        "componentArtifactDigest": session["componentArtifactDigest"],
        "observedAt": (started + timedelta(seconds=20)).isoformat(),
    }
    evidence_root = tmp_path / "private-evidence"
    evidence_root.mkdir(mode=0o700)
    documents = {
        "feelings_control_projection": parent,
        "feelings_semantic_receipts": semantic_projection(parent),
        "feelings_service_acknowledgement": service_projection,
    }
    evidence = []
    for kind, payload in documents.items():
        relative = f"proof/{kind}.json"
        evidence.append(
            {
                "kind": kind,
                "path": relative,
                "sha256": write_private(evidence_root / relative, payload),
            }
        )
    manifest = {
        "caseId": "EMO-UC-047",
        "contractVersion": 1,
        "environment": "installed_local_production",
        "runAt": run_at.isoformat(),
        "candidate": {
            "candidateDigest": candidate_digest,
            "artifactDigest": artifact_digest,
        },
        "evidence": evidence,
    }
    parent_control = load_module(
        PARENT_CONTROL_PATH, "emo047_authoritative_parent_for_verifier_tests"
    )
    authority = verifier._LiveAuthority(
        candidate_digest=candidate_digest,
        artifact_digest=artifact_digest,
        session=session,
        service_status=service_status,
        parent_control=parent_control,
        parameters={
            "state_path": state,
            "installed_root": installed,
            "artifact_identity_path": identity,
            "local_qa_request_path": request,
        },
    )
    monkeypatch.setattr(verifier, "probe_live_authority", lambda **_kwargs: authority)
    return {
        "verifier": verifier,
        "manifest": manifest,
        "evidence_root": evidence_root,
        "authority": authority,
        "candidate_digest": candidate_digest,
        "artifact_digest": artifact_digest,
        "checked_at": checked_at,
    }


def assess(bundle: dict[str, object], **overrides: object) -> dict[str, object]:
    parameters = {
        "evidence_root": bundle["evidence_root"],
        "expected_candidate_digest": bundle["candidate_digest"],
        "expected_artifact_digest": bundle["artifact_digest"],
        "installed_owner_proven": True,
        "now": bundle["checked_at"],
    }
    parameters.update(overrides)
    return bundle["verifier"].assess_manifest(bundle["manifest"], **parameters)


def rewrite_document(bundle: dict[str, object], kind: str, mutate) -> None:
    manifest = bundle["manifest"]
    entry = next(item for item in manifest["evidence"] if item["kind"] == kind)
    path = bundle["evidence_root"] / entry["path"]
    document = json.loads(path.read_text(encoding="utf-8"))
    mutate(document)
    entry["sha256"] = write_private(path, document)


def test_stable_registry_contract_and_derived_installed_semantic_receipt(
    installed_bundle: dict[str, object],
) -> None:
    verifier = installed_bundle["verifier"]

    result = assess(installed_bundle)
    receipt = verifier.receipt_manifest(result=result)

    assert verifier.CASE_ID == "EMO-UC-047"
    assert verifier.VERIFIER_ID == "emo047-semantic-v1"
    assert result["status"] == "PASS"
    assert result["ready"] is True
    assert result["blockers"] == []
    assert result["counts"] == {
        "fallbackAttemptCount": 2,
        "mainReceiptCount": 4,
        "phaseBReceiptCount": 1,
        "scenarioCount": 4,
        "semanticPassCount": 4,
        "specialistReceiptCount": 5,
        "workerReceiptCount": 6,
    }
    assert all(item["status"] == "PASS" for item in result["gates"])
    assert receipt == {
        "caseId": "EMO-UC-047",
        "contractVersion": 1,
        "evidence": sorted(
            installed_bundle["manifest"]["evidence"],
            key=lambda item: (item["kind"], item["path"]),
        ),
        "runAt": installed_bundle["manifest"]["runAt"],
        "status": "PASS",
        "surface": "telegram",
    }
    public_result = {
        key: value for key, value in result.items() if not key.startswith("_")
    }
    serialized = json.dumps({"result": public_result, "receipt": receipt})
    assert str(installed_bundle["evidence_root"]) not in serialized
    assert "<viventium_feeling_state>" not in serialized
    assert "caseToken" not in serialized
    assert not list(installed_bundle["evidence_root"].glob("*receipt*.json"))


def test_reuses_authoritative_live_parent_verifier(
    installed_bundle: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    authority = installed_bundle["authority"]
    original = authority.parent_control.verify_installed_evidence
    calls: list[int] = []

    def observed(**kwargs: object) -> dict[str, object]:
        calls.append(int(kwargs["evidence_fd"]))
        return original(**kwargs)

    monkeypatch.setattr(authority.parent_control, "verify_installed_evidence", observed)

    assert assess(installed_bundle)["status"] == "PASS"
    assert len(calls) == 1


def test_shared_registry_loads_and_derives_the_exact_semantic_adapter(
    installed_bundle: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = load_module(
        SHARED_REGISTRY_PATH, "emo047_shared_receipt_registry_integration"
    )
    registration = registry.REGISTERED_SEMANTIC_VERIFIERS["EMO-UC-047"]
    original_loader = registry._load_registered_verifier
    source_authority = installed_bundle["authority"]

    def load_bound_verifier(path: Path, *, case_id: str):
        verifier = original_loader(path, case_id=case_id)
        authority = verifier._LiveAuthority(
            candidate_digest=source_authority.candidate_digest,
            artifact_digest=source_authority.artifact_digest,
            session=source_authority.session,
            service_status=source_authority.service_status,
            parent_control=source_authority.parent_control,
            parameters=source_authority.parameters,
        )
        monkeypatch.setattr(verifier, "probe_live_authority", lambda **_kwargs: authority)
        return verifier

    monkeypatch.setattr(registry, "_load_registered_verifier", load_bound_verifier)
    manifest_path = installed_bundle["evidence_root"] / "semantic-manifest.json"
    manifest_digest = write_private(manifest_path, installed_bundle["manifest"])

    claim = registry._derive_registered_pass(
        case_id="EMO-UC-047",
        verifier_claim={
            "id": "emo047-semantic-v1",
            "manifest": "semantic-manifest.json",
        },
        evidence_root=installed_bundle["evidence_root"],
        candidate_digest=installed_bundle["candidate_digest"],
        artifact_digest=installed_bundle["artifact_digest"],
        caller_run_at=installed_bundle["manifest"]["runAt"],
        caller_surface="telegram",
        caller_evidence=sorted(
            installed_bundle["manifest"]["evidence"],
            key=lambda item: (item["kind"], item["path"]),
        ),
        installed_owner_proven=True,
        now=installed_bundle["checked_at"],
    )

    assert registration == {
        "id": "emo047-semantic-v1",
        "path": Path("qa/emotional-cortex/scripts/run_emo_uc_047.py"),
    }
    assert claim == {
        "id": "emo047-semantic-v1",
        "manifestSha256": manifest_digest,
    }
    assert not list(installed_bundle["evidence_root"].glob("*receipt*.json"))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("installed_owner_proven", False),
        ("expected_candidate_digest", "0" * 64),
        ("expected_artifact_digest", "0" * 64),
        ("expected_candidate_digest", "invalid"),
    ],
)
def test_rejects_missing_owner_and_wrong_installed_candidate(
    installed_bundle: dict[str, object], field: str, value: object
) -> None:
    with pytest.raises(ValueError, match="candidate|owner"):
        assess(installed_bundle, **{field: value})


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.update(status="PASS"),
        lambda value: value.update(environment="source_checkout"),
        lambda value: value["candidate"].update(candidateDigest=digest("other")),
        lambda value: value.update(runAt="2026-08-23T12:00:00+00:00"),
        lambda value: value.update(runAt="2026-08-25T12:20:00+00:00"),
        lambda value: value["evidence"].append(copy.deepcopy(value["evidence"][0])),
    ],
)
def test_rejects_self_declared_stale_duplicate_or_foreign_manifest(
    installed_bundle: dict[str, object], mutate
) -> None:
    mutate(installed_bundle["manifest"])

    with pytest.raises(ValueError):
        assess(installed_bundle)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value["scenarios"][1]["workers"].clear(),
        lambda value: value["scenarios"][1]["workers"][0]["nativeAuthorityReceipt"].update(
            feelingCapsuleCount=0
        ),
        lambda value: value["scenarios"][3]["winningNativeReceipt"].update(
            capsuleOccurrenceCount=1
        ),
        lambda value: value["requestIsolation"]["firstTypedFallback"].update(
            winningSnapshotHash=digest("replacement-state")
        ),
        lambda value: value["safetyAudit"].update(hostPluginDenylistEnabled=False),
        lambda value: value["safetyAudit"].update(privateStateMountCount=1),
        lambda value: value.update(privateCapsule="SYNTHETIC-PRIVATE-CAPSULE-CANARY"),
    ],
)
def test_authoritative_parent_rejects_original_escaped_incident_and_private_projection(
    installed_bundle: dict[str, object], mutate
) -> None:
    rewrite_document(installed_bundle, "feelings_control_projection", mutate)

    with pytest.raises(ValueError):
        assess(installed_bundle)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value["scenarios"][1]["providerReceipt"].update(stateVersion=17),
        lambda value: value["scenarios"][1]["workerReceipts"][0].update(
            snapshotHash=digest("stale-worker-state")
        ),
        lambda value: value["scenarios"][1]["workerReceipts"][0].update(stateVersion=17),
        lambda value: value["scenarios"][1]["sourceReceipt"].update(
            capsuleLayerIndex=1
        ),
        lambda value: value["scenarios"][1]["providerReceipt"].update(
            trailingInstructionChars=1
        ),
        lambda value: value["scenarios"][1]["providerReceipt"].update(
            capsuleOccurrenceCount=2
        ),
        lambda value: value["scenarios"][1]["providerReceipt"].update(winning=False),
        lambda value: value["scenarios"][1]["workerReceipts"].pop(),
        lambda value: value["scenarios"][1]["semanticReceipt"].update(
            materiallyFollowsPinnedState=False
        ),
        lambda value: value["scenarios"][1]["semanticReceipt"].update(
            inventedFeelingCount=1
        ),
        lambda value: value["scenarios"][2]["workerReceipts"][0].update(
            capsuleOccurrenceCount=1
        ),
        lambda value: value["scenarios"][3]["providerReceipt"].update(
            capsuleSha256=digest("stale-disabled-capsule")
        ),
        lambda value: value["scenarios"][3].update(stateVersion=19),
    ],
)
def test_same_pinned_version_native_receipts_scope_and_disabled_state_fail_closed(
    installed_bundle: dict[str, object], mutate
) -> None:
    rewrite_document(installed_bundle, "feelings_semantic_receipts", mutate)

    result = assess(installed_bundle)

    assert result["status"] == "FAIL"
    assert result["ready"] is False
    assert result["blockers"]
    with pytest.raises(ValueError, match="derived PASS"):
        installed_bundle["verifier"].receipt_manifest(result=result)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value["fallbackContinuity"]["attempts"][1].update(
            snapshotHash=digest("fallback-replacement")
        ),
        lambda value: value["fallbackContinuity"]["attempts"][1].update(
            stateVersion=18
        ),
        lambda value: value["fallbackContinuity"]["attempts"][1]["capabilityIds"].pop(),
        lambda value: value["fallbackContinuity"].update(fallbackUsed=False),
        lambda value: value["phaseBContinuity"].update(
            phaseBNativeSessionRef=value["phaseBContinuity"]["mainNativeSessionRef"]
        ),
        lambda value: value["phaseBContinuity"].update(mainWorkerInterrupted=True),
        lambda value: value["phaseBContinuity"].update(
            phaseBContinuityIdentitySha256=digest("different-continuity")
        ),
        lambda value: value["specialistReceipts"].pop(),
        lambda value: value["specialistReceipts"][0].update(capsuleOccurrenceCount=1),
        lambda value: value["specialistReceipts"][0].update(skipReason="scope_disabled"),
    ],
)
def test_fallback_phase_b_and_specialist_independence_require_exact_receipts(
    installed_bundle: dict[str, object], mutate
) -> None:
    rewrite_document(installed_bundle, "feelings_semantic_receipts", mutate)

    assert assess(installed_bundle)["status"] == "FAIL"


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("hostPluginDenylistEnabled", False),
        ("deniedPluginIds", []),
        ("unrelatedPluginsPreserved", False),
        ("privateStateMountCount", 1),
        ("privateStatePersistenceCount", 1),
        ("privateCapsuleProjectionCount", 1),
        ("feelingsMcpServerCount", 1),
        ("workerFeelingsPluginCount", 1),
    ],
)
def test_private_state_and_existing_plugin_denylist_remain_isolated(
    installed_bundle: dict[str, object], field: str, replacement: object
) -> None:
    rewrite_document(
        installed_bundle,
        "feelings_semantic_receipts",
        lambda value: value["privacyAudit"].update({field: replacement}),
    )

    assert assess(installed_bundle)["status"] == "FAIL"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.update(requiredServices=["librechat-core"]),
        lambda value: value.update(acknowledgedServices=["librechat-core"]),
        lambda value: value.update(serviceAckDigest=digest_ref("forged-service-ack")),
        lambda value: value.update(sessionRef="qa_" + "0" * 24),
        lambda value: value.update(componentArtifactDigest=digest_ref("stale-artifact")),
        lambda value: value.update(restartState="waiting"),
    ],
)
def test_exact_live_service_acknowledgements_and_session_are_mandatory(
    installed_bundle: dict[str, object], mutate
) -> None:
    rewrite_document(installed_bundle, "feelings_service_acknowledgement", mutate)

    with pytest.raises(ValueError, match="service|session|artifact"):
        assess(installed_bundle)


def test_tampered_private_file_is_rejected_before_semantic_evaluation(
    installed_bundle: dict[str, object]
) -> None:
    entry = installed_bundle["manifest"]["evidence"][1]
    target = installed_bundle["evidence_root"] / entry["path"]
    target.write_text("{}\n", encoding="utf-8")
    target.chmod(0o600)

    with pytest.raises(ValueError, match="evidence"):
        assess(installed_bundle)


def test_private_evidence_rejects_world_readable_files_and_symlinked_parents(
    installed_bundle: dict[str, object]
) -> None:
    entry = installed_bundle["manifest"]["evidence"][1]
    target = installed_bundle["evidence_root"] / entry["path"]
    target.chmod(0o644)

    with pytest.raises(ValueError, match="evidence"):
        assess(installed_bundle)

    target.chmod(0o600)
    alias = installed_bundle["evidence_root"] / "alias"
    alias.symlink_to(installed_bundle["evidence_root"] / "proof", target_is_directory=True)
    entry["path"] = "alias/feelings_semantic_receipts.json"

    with pytest.raises(ValueError, match="evidence"):
        assess(installed_bundle)


def test_public_private_content_and_duplicate_json_keys_are_rejected(
    installed_bundle: dict[str, object]
) -> None:
    rewrite_document(
        installed_bundle,
        "feelings_semantic_receipts",
        lambda value: value.update(
            privateCapsule="SYNTHETIC-PRIVATE-CAPSULE-CANARY",
            privateState={"synthetic": "SYNTHETIC-PRIVATE-STATE-CANARY"},
        ),
    )

    with pytest.raises(ValueError, match="evidence"):
        assess(installed_bundle)

    entry = installed_bundle["manifest"]["evidence"][1]
    target = installed_bundle["evidence_root"] / entry["path"]
    raw = '{"caseId":"EMO-UC-047","caseId":"EMO-UC-047"}\n'
    target.write_text(raw, encoding="utf-8")
    target.chmod(0o600)
    entry["sha256"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()

    with pytest.raises(ValueError, match="evidence"):
        assess(installed_bundle)


def test_receipt_rejects_invented_copied_or_mutated_passes(
    installed_bundle: dict[str, object]
) -> None:
    verifier = installed_bundle["verifier"]
    result = assess(installed_bundle)
    invented = {
        "caseId": "EMO-UC-047",
        "contractVersion": 1,
        "status": "PASS",
        "ready": True,
        "blockers": [],
    }

    with pytest.raises(ValueError, match="derived PASS"):
        verifier.receipt_manifest(result=invented)
    with pytest.raises(ValueError, match="derived PASS"):
        verifier.receipt_manifest(result=dict(result))

    result["counts"]["workerReceiptCount"] = 51
    with pytest.raises(ValueError, match="derived PASS"):
        verifier.receipt_manifest(result=result)


def test_recomputed_digest_cannot_rebind_a_modified_issued_pass(
    installed_bundle: dict[str, object]
) -> None:
    verifier = installed_bundle["verifier"]
    result = assess(installed_bundle)
    result["counts"]["workerReceiptCount"] = 51
    result["_derivationDigest"] = verifier._derived_result_digest(result)

    with pytest.raises(ValueError, match="derived PASS"):
        verifier.receipt_manifest(result=result)


def test_changed_state_must_advance_the_second_request_pinned_version(
    installed_bundle: dict[str, object]
) -> None:
    def reuse_first_version(document: dict[str, object]) -> None:
        scenario = document["scenarios"][1]
        scenario["stateVersion"] = 17
        scenario["sourceReceipt"]["stateVersion"] = 17
        scenario["providerReceipt"]["stateVersion"] = 17
        scenario["semanticReceipt"]["stateVersion"] = 17
        for worker in scenario["workerReceipts"]:
            worker["stateVersion"] = 17
        document["phaseBContinuity"]["stateVersion"] = 17
        for specialist in document["specialistReceipts"]:
            specialist["stateVersion"] = 17

    rewrite_document(
        installed_bundle, "feelings_semantic_receipts", reuse_first_version
    )

    assert assess(installed_bundle)["status"] == "FAIL"


def test_expired_active_session_cannot_create_semantic_receipt(
    installed_bundle: dict[str, object]
) -> None:
    checked_at = installed_bundle["checked_at"] + timedelta(minutes=16)
    installed_bundle["manifest"]["runAt"] = (
        checked_at - timedelta(seconds=1)
    ).isoformat()

    with pytest.raises(ValueError, match="expired|session"):
        assess(installed_bundle, now=checked_at)


def test_provider_receipt_integer_fields_reject_boolean_type_confusion(
    installed_bundle: dict[str, object]
) -> None:
    rewrite_document(
        installed_bundle,
        "feelings_semantic_receipts",
        lambda value: value["scenarios"][1]["providerReceipt"].update(
            capsuleOccurrenceCount=True
        ),
    )

    assert assess(installed_bundle)["status"] == "FAIL"


def test_private_root_permissions_are_required(
    installed_bundle: dict[str, object]
) -> None:
    root = installed_bundle["evidence_root"]
    os.chmod(root, 0o755)

    with pytest.raises(ValueError, match="evidence"):
        assess(installed_bundle)


def test_live_owner_probe_rejects_untrusted_runtime_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verifier = load_verifier()
    monkeypatch.setenv("VIVENTIUM_APP_SUPPORT_DIR", "synthetic-untrusted-location")

    with pytest.raises(ValueError, match="owner"):
        verifier.probe_live_authority()


def test_private_evidence_hardlink_is_rejected(
    installed_bundle: dict[str, object]
) -> None:
    entry = installed_bundle["manifest"]["evidence"][1]
    target = installed_bundle["evidence_root"] / entry["path"]
    os.link(target, installed_bundle["evidence_root"] / "linked-evidence.json")

    with pytest.raises(ValueError, match="evidence"):
        assess(installed_bundle)


def test_installed_semantic_cli_derives_candidate_from_live_owner_only(
    installed_bundle: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    verifier = installed_bundle["verifier"]
    manifest_path = installed_bundle["evidence_root"] / "manifest.json"
    write_private(manifest_path, installed_bundle["manifest"])
    monkeypatch.setattr(
        verifier, "_utc_now", lambda: installed_bundle["checked_at"], raising=False
    )

    exit_code = verifier.main(
        [
            "--manifest",
            "manifest.json",
            "--evidence-root",
            str(installed_bundle["evidence_root"]),
        ]
    )
    output = capsys.readouterr().out
    result = json.loads(output)

    assert exit_code == 0
    assert result["caseId"] == "EMO-UC-047"
    assert result["status"] == "PASS"
    assert result["counts"]["workerReceiptCount"] == 6
    assert not any(key.startswith("_") for key in result)
    assert str(installed_bundle["evidence_root"]) not in output


def test_installed_semantic_cli_blocks_missing_live_authority_without_private_leaks(
    installed_bundle: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    verifier = installed_bundle["verifier"]
    private_canary = "PRIVATE-EMO-047-AUTHORITY-CANARY"

    def unavailable(**_kwargs: object) -> object:
        raise ValueError(private_canary)

    monkeypatch.setattr(verifier, "probe_live_authority", unavailable)

    exit_code = verifier.main(
        [
            "--manifest",
            "manifest.json",
            "--evidence-root",
            str(installed_bundle["evidence_root"]),
        ]
    )
    captured = capsys.readouterr()
    result = json.loads(captured.out)

    assert exit_code == 2
    assert result == {
        "blockers": ["live-authority-unavailable"],
        "caseId": "EMO-UC-047",
        "status": "BLOCKED",
    }
    assert private_canary not in captured.out + captured.err
    assert str(installed_bundle["evidence_root"]) not in captured.out + captured.err


def test_installed_semantic_cli_refuses_caller_declared_status(
    installed_bundle: dict[str, object], capsys: pytest.CaptureFixture[str]
) -> None:
    verifier = installed_bundle["verifier"]

    exit_code = verifier.main(
        [
            "--manifest",
            "manifest.json",
            "--evidence-root",
            str(installed_bundle["evidence_root"]),
            "--status",
            "PASS",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "PASS" not in captured.err
    assert str(installed_bundle["evidence_root"]) not in captured.err
