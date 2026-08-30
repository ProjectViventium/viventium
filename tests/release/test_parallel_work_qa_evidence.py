from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "viventium" / "parallel_work_qa_evidence.py"


def load_module():
    spec = importlib.util.spec_from_file_location("parallel_work_qa_evidence", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def artifact_identity() -> dict[str, object]:
    digest = "a" * 64
    return {
        "contractVersion": 1,
        "readiness": {
            "factsSha256": digest,
            "storagePolicySha256": digest,
            "storageMeasurementSha256": digest,
        },
        "source": {
            "revision": "b" * 40,
            "clean": False,
            "worktreeHash": digest,
            "componentsLockSha256": digest,
        },
        "nestedComponents": [
            {
                "name": "GlassHive",
                "pin": "c" * 40,
                "revision": "d" * 40,
                "clean": False,
                "worktreeHash": digest,
            }
        ],
        "prebuiltHelper": {
            "sourceDeclaredSha256": digest,
            "sourceMeasuredSha256": digest,
            "binaryDeclaredSha256": digest,
            "binaryMeasuredSha256": digest,
            "binaryExecutable": True,
        },
        "installed": {
            key: ("e" * 40 if key == "rootRevision" else digest)
            for key in (
                "rootRevision",
                "componentsLockSha256",
                "nestedRevisionsHash",
                "prebuiltSourceSha256",
                "prebuiltBinarySha256",
                "promptBundleSha256",
                "runtimeEnvSha256",
                "libreChatConfigSha256",
                "frontendBuildSha256",
                "apiBuildSha256",
                "runningServiceSha256",
                "runtimeServiceManifestSha256",
                "runtimeOwnerExecutableSha256",
                "ownerCommandContractSha256",
            )
        },
    }


def write_manifest(
    evidence_root: Path,
    *,
    case_id: str = "TR-026",
    status: str = "PASS",
    surface: str = "telegram",
    run_at: datetime | None = None,
    evidence_path: Path | None = None,
    verifier: dict[str, str] | None = None,
) -> Path:
    evidence_root.mkdir(parents=True, exist_ok=True)
    proof = evidence_path or (evidence_root / "telegram-after.png")
    if not proof.exists():
        proof.write_bytes(b"synthetic screenshot bytes")
    relative = proof.relative_to(evidence_root).as_posix() if proof.is_relative_to(evidence_root) else str(proof)
    payload = {
        "contractVersion": 1,
        "caseId": case_id,
        "runAt": (run_at or datetime.now(timezone.utc)).isoformat(),
        "surface": surface,
        "status": status,
        "evidence": [
            {
                "kind": "telegram_screenshot",
                "path": relative,
                "sha256": hashlib.sha256(proof.read_bytes()).hexdigest(),
            }
        ],
    }
    if status == "PASS":
        verifier_manifest = evidence_root / "caller-verifier.json"
        if not verifier_manifest.exists():
            verifier_manifest.write_text('{"status":"PASS"}\n', encoding="utf-8")
            verifier_manifest.chmod(0o600)
        payload["verifier"] = verifier or {
            "id": "caller-declared",
            "manifest": verifier_manifest.relative_to(evidence_root).as_posix(),
        }
    path = evidence_root / "result.json"
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    return path


def record(module, manifest: Path, evidence_root: Path, **overrides):
    service_ack_status = overrides.pop(
        "service_ack_status",
        {
            "caseId": "TR-026",
            "restartState": "ready",
            "requiredServices": ["librechat-core", "telegram-bot"],
            "acknowledgedServices": ["librechat-core", "telegram-bot"],
            "missingServices": [],
            "serviceAckDigest": "sha256:" + "f" * 64,
            "sessionRef": "qa_" + "a" * 24,
        },
    )
    return module.record_case_receipt(
        manifest_path=manifest,
        evidence_root=evidence_root,
        artifact_identity=overrides.pop("artifact_identity", artifact_identity()),
        existing_receipts=overrides.pop(
            "existing_receipts", {"contractVersion": 1, "receipts": []}
        ),
        required_case_ids=overrides.pop("required_case_ids", {"TR-026"}),
        local_qa_request=overrides.pop(
            "local_qa_request",
            {"contractVersion": 1, "mode": "local-qa", "requested": True},
        ),
        service_ack_status=service_ack_status,
        attestation_authority=overrides.pop(
            "attestation_authority", (b"fixture-attestation-key-material", "b" * 64)
        ),
        installed_owner_proven=overrides.pop("installed_owner_proven", False),
        now=overrides.pop("now", datetime.now(timezone.utc)),
        **overrides,
    )


@pytest.fixture
def externally_signed_release_fixture(tmp_path: Path):
    module_name = "viventium_release_gate_writer_fixture_support"
    support = sys.modules.get(module_name)
    if support is None:
        support_path = REPO_ROOT / "tests" / "release" / "test_parallel_work_release_gate.py"
        specification = importlib.util.spec_from_file_location(module_name, support_path)
        assert specification is not None and specification.loader is not None
        support = importlib.util.module_from_spec(specification)
        sys.modules[module_name] = support
        specification.loader.exec_module(support)
    start = len(support.OWNER_PROCESSES)
    source = tmp_path / "fixture-source"
    installed = tmp_path / "fixture-installed"
    support._write_fixture_root(source)
    gate, prompt_bundle_path, identity, prompt_layers = (
        support._write_release_identity_fixture(
            source, installed, external_attestation=True
        )
    )
    try:
        yield SimpleNamespace(
            support=support,
            gate=gate,
            source=source,
            installed=installed,
            owner_state=support._owner_state_path(prompt_bundle_path),
            prompt_bundle_path=prompt_bundle_path,
            prompt_layers=prompt_layers,
            identity=identity,
        )
    finally:
        support._stop_owner_processes_from(start)


def external_signing_authority(module, fixture):
    sidecar = fixture.gate._load_external_release_attestation()
    policy = fixture.gate._test_external_release_policy
    keys = fixture.support._external_fixture_keys()

    def service_attestor(receipt, service_status):
        checked_at = datetime.fromisoformat(str(receipt["runAt"]))
        return [
            sidecar.sign_service_acknowledgement(
                {
                    "caseId": receipt["caseId"],
                    "surface": receipt["surface"],
                    "candidateDigest": receipt["candidateDigest"],
                    "artifactDigest": receipt["artifactDigest"],
                    "ownerBindingSha256": receipt["ownerBindingSha256"],
                    "serviceId": service_id,
                    "sessionRef": receipt["serviceAckSessionRef"],
                    "acknowledgedAt": checked_at.isoformat(),
                    "acknowledgementDigest": service_status["serviceAckDigest"],
                    "processIdentityDigest": hashlib.sha256(
                        f"fixture-process:{service_id}".encode()
                    ).hexdigest(),
                },
                producer_id=service_id,
                policy=policy,
                signer=fixture.support._ExternalFixtureSigner(keys[service_id]),
                now=checked_at,
            )
            for service_id in fixture.support.FIXTURE_CASE_SERVICES.get(
                str(receipt["caseId"]), ()
            )
        ]

    def producer_attestor(receipt):
        checked_at = datetime.fromisoformat(str(receipt["runAt"]))
        return [
            sidecar.sign_producer_observation(
                {
                    "caseId": receipt["caseId"],
                    "surface": receipt["surface"],
                    "candidateDigest": receipt["candidateDigest"],
                    "artifactDigest": receipt["artifactDigest"],
                    "ownerBindingSha256": receipt["ownerBindingSha256"],
                    "evidenceDigest": receipt["evidenceDigest"],
                    "receiptNonce": receipt["receiptNonce"],
                    "verifierId": receipt["verifierId"],
                    "verifierManifestSha256": receipt["verifierManifestSha256"],
                    "observedAt": checked_at.isoformat(),
                    "observationNonce": hashlib.sha256(
                        f"observation:{receipt['receiptNonce']}".encode()
                    ).hexdigest()[:32],
                    "serviceAckDigest": receipt.get("serviceAckDigest", ""),
                    "serviceAckSessionRef": receipt.get("serviceAckSessionRef", ""),
                },
                producer_id="observation-producer",
                policy=policy,
                signer=fixture.support._ExternalFixtureSigner(
                    keys["observation-producer"]
                ),
                now=checked_at,
            )
        ]

    return module.ExternalReleaseEvidenceSigningAuthority(
        installed_root=fixture.installed,
        runtime_owner_state=fixture.owner_state,
        verification_authority=fixture.gate._test_external_release_authority,
        publisher_signer=fixture.support._ExternalFixtureSigner(keys["publisher"]),
        producer_attestor=producer_attestor,
        service_attestor=service_attestor,
    )


def test_release_evidence_writer_refuses_to_self_create_an_external_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_module()
    evidence_root = tmp_path / "private-evidence"
    manifest = write_manifest(
        evidence_root,
        case_id="TGDOC-010",
        verifier={"id": "tgd010-semantic-v1", "manifest": "caller-verifier.json"},
    )
    monkeypatch.setattr(
        module,
        "_derive_registered_pass",
        lambda **_kwargs: {
            "id": "tgd010-semantic-v1",
            "manifestSha256": "a" * 64,
        },
    )

    with pytest.raises(ValueError, match="external release attestation authority"):
        record(
            module,
            manifest,
            evidence_root,
            required_case_ids={"TGDOC-010"},
            installed_owner_proven=True,
            require_external_attestation=True,
        )


def test_release_evidence_writer_uses_real_publisher_and_producer_signatures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    externally_signed_release_fixture,
) -> None:
    fixture = externally_signed_release_fixture
    module = load_module()
    evidence_root = tmp_path / "private-evidence"
    manifest = write_manifest(
        evidence_root,
        case_id="TGDOC-010",
        verifier={"id": "tgd010-semantic-v1", "manifest": "caller-verifier.json"},
    )
    monkeypatch.setattr(
        module,
        "_derive_registered_pass",
        lambda **_kwargs: {
            "id": "tgd010-semantic-v1",
            "manifestSha256": "a" * 64,
        },
    )
    signing = external_signing_authority(module, fixture)

    result = record(
        module,
        manifest,
        evidence_root,
        artifact_identity=fixture.identity,
        required_case_ids={"TGDOC-010"},
        installed_owner_proven=True,
        attestation_authority=None,
        external_attestation_authority=signing,
        require_external_attestation=True,
    )

    receipt = result["receipts"][0]
    assert "attestation" not in receipt
    assert receipt["publisherAttestation"].startswith("-----BEGIN SSH SIGNATURE-----")
    assert receipt["producerAttestations"][0]["producerId"] == "observation-producer"
    assert receipt["serviceAcknowledgements"] == []
    assert receipt["attestationSequence"] == 1
    assert fixture.gate._load_external_release_attestation().verify_release_receipt(
        receipt,
        policy=fixture.gate._test_external_release_policy,
        ledger_path=signing.verification_authority.ledger_path,
        ledger_witness=signing.verification_authority.ledger_witness,
        expected_case_id="TGDOC-010",
        expected_surface="telegram",
        expected_candidate_digest=receipt["candidateDigest"],
        expected_artifact_digest=receipt["artifactDigest"],
        expected_owner_binding=receipt["ownerBindingSha256"],
        expected_verifier_id="tgd010-semantic-v1",
        expected_verifier_manifest_sha256="a" * 64,
        expected_evidence_digest=receipt["evidenceDigest"],
    ).sequence == 1


def test_external_writer_receipt_reaches_the_real_release_evaluator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    externally_signed_release_fixture,
) -> None:
    fixture = externally_signed_release_fixture
    module = load_module()
    evidence_root = tmp_path / "private-evidence"
    manifest = write_manifest(
        evidence_root,
        case_id="TGDOC-010",
        verifier={"id": "tgd010-semantic-v1", "manifest": "caller-verifier.json"},
    )
    monkeypatch.setattr(
        module,
        "_derive_registered_pass",
        lambda **_kwargs: {
            "id": "tgd010-semantic-v1",
            "manifestSha256": "a" * 64,
        },
    )
    previous = fixture.support._qa_case_receipts(
        fixture.gate,
        fixture.identity,
        externally_authenticated=True,
    )
    signing = external_signing_authority(module, fixture)
    sidecar = fixture.gate._load_external_release_attestation()
    candidate_digest, artifact_digest = fixture.gate._qa_candidate_digests(
        fixture.identity
    )
    owner_binding = fixture.gate._qa_receipt_owner_binding(
        fixture.installed, fixture.owner_state
    )
    prior_by_case = {
        receipt["caseId"]: receipt for receipt in previous["receipts"]
    }
    assert set(prior_by_case) == set(fixture.support.FIXTURE_CASE_IDS)
    for case_id, receipt in prior_by_case.items():
        assert receipt["candidateDigest"] == candidate_digest
        assert receipt["artifactDigest"] == artifact_digest
        assert receipt["ownerBindingSha256"] == owner_binding
        assert receipt["publisherAttestation"].startswith(
            "-----BEGIN SSH SIGNATURE-----"
        )
        assert receipt["producerAttestations"][0]["producerId"] == (
            "observation-producer"
        )
        assert {
            acknowledgement["serviceId"]
            for acknowledgement in receipt["serviceAcknowledgements"]
        } == set(fixture.support.FIXTURE_CASE_SERVICES.get(case_id, ()))
        assert receipt["attestationSequence"] == 1
    ledger_path = signing.verification_authority.ledger_path
    ledger_before = json.loads(ledger_path.read_text(encoding="utf-8"))

    emitted = record(
        module,
        manifest,
        evidence_root,
        artifact_identity=fixture.identity,
        existing_receipts=previous,
        required_case_ids={"TGDOC-010"},
        installed_owner_proven=True,
        attestation_authority=None,
        external_attestation_authority=signing,
        require_external_attestation=True,
    )
    current_by_case = {
        receipt["caseId"]: receipt for receipt in emitted["receipts"]
    }
    assert set(current_by_case) == set(prior_by_case)
    assert {
        case_id: receipt
        for case_id, receipt in current_by_case.items()
        if case_id != "TGDOC-010"
    } == {
        case_id: receipt
        for case_id, receipt in prior_by_case.items()
        if case_id != "TGDOC-010"
    }
    ledger_after = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert ledger_after["entries"][:-1] == ledger_before["entries"]
    assert [entry["globalSequence"] for entry in ledger_after["entries"]] == list(
        range(1, len(ledger_after["entries"]) + 1)
    )
    witness_scope = sidecar._witness_scope(
        fixture.gate._test_external_release_policy, ledger_path
    )
    assert signing.verification_authority.ledger_witness.current(
        witness_scope
    ).sequence == len(ledger_after["entries"])
    result = fixture.gate.evaluate_release_gate(
        fixture.source,
        mode="local-qa",
        allow_local_qa_override=True,
        readiness_facts=fixture.support._healthy_readiness_facts(fixture.prompt_layers),
        artifact_identity=fixture.identity,
        installed_prompt_bundle_path=fixture.prompt_bundle_path,
        installed_root=fixture.installed,
        runtime_owner_state=fixture.owner_state,
        qa_case_receipts=emitted,
        external_attestation_authority=signing.verification_authority,
    )

    assert current_by_case["TGDOC-010"]["attestationSequence"] == 2
    assert result.open_gates == ()
    assert result.qa_receipt_summary["status"] == "verified"
    assert result.release_ready is False
    assert result.label == "PRE-GATE / NOT READY"

    production_result = fixture.gate.evaluate_release_gate(
        fixture.source,
        mode="release",
        readiness_facts=fixture.support._healthy_readiness_facts(fixture.prompt_layers),
        artifact_identity=fixture.identity,
        installed_prompt_bundle_path=fixture.prompt_bundle_path,
        installed_root=fixture.installed,
        runtime_owner_state=fixture.owner_state,
        qa_case_receipts=emitted,
    )
    assert fixture.gate._resolve_external_release_attestation_authority.__module__ == (
        fixture.gate.__name__
    )
    assert production_result.release_ready is False
    assert production_result.label == "NOT READY"
    assert {
        gate.detail for gate in production_result.open_gates
    } == {"qa_receipt_external_attestation_missing"}


@pytest.mark.parametrize("require_external_attestation", (False, True))
def test_external_writer_rejects_locally_signed_prior_receipts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    externally_signed_release_fixture,
    require_external_attestation: bool,
) -> None:
    fixture = externally_signed_release_fixture
    module = load_module()
    evidence_root = tmp_path / "private-evidence"
    manifest = write_manifest(
        evidence_root,
        case_id="TGDOC-010",
        verifier={"id": "tgd010-semantic-v1", "manifest": "caller-verifier.json"},
    )
    monkeypatch.setattr(
        module,
        "_derive_registered_pass",
        lambda **_kwargs: {
            "id": "tgd010-semantic-v1",
            "manifestSha256": "a" * 64,
        },
    )
    previous = fixture.support._qa_case_receipts(fixture.gate, fixture.identity)
    signing = external_signing_authority(module, fixture)
    local_authority = fixture.gate._qa_receipt_attestation_authority(
        fixture.installed, fixture.owner_state
    )
    assert local_authority is not None
    assert not signing.verification_authority.ledger_path.exists()

    with pytest.raises(ValueError, match="existing external QA receipt attestation"):
        record(
            module,
            manifest,
            evidence_root,
            artifact_identity=fixture.identity,
            existing_receipts=previous,
            required_case_ids={"TGDOC-010"},
            installed_owner_proven=True,
            attestation_authority=local_authority,
            external_attestation_authority=signing,
            require_external_attestation=require_external_attestation,
        )

    assert not signing.verification_authority.ledger_path.exists()
    assert signing.verification_authority.ledger_witness.heads == {}


def test_writer_rejects_signed_prior_receipt_from_another_installed_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    externally_signed_release_fixture,
) -> None:
    fixture = externally_signed_release_fixture
    module = load_module()
    evidence_root = tmp_path / "private-evidence"
    manifest = write_manifest(
        evidence_root,
        case_id="TGDOC-010",
        verifier={"id": "tgd010-semantic-v1", "manifest": "caller-verifier.json"},
    )
    monkeypatch.setattr(
        module,
        "_derive_registered_pass",
        lambda **_kwargs: {
            "id": "tgd010-semantic-v1",
            "manifestSha256": "a" * 64,
        },
    )
    previous = fixture.support._qa_case_receipts(fixture.gate, fixture.identity)
    local_authority = fixture.gate._qa_receipt_attestation_authority(
        fixture.installed, fixture.owner_state
    )
    assert local_authority is not None
    stale = next(
        receipt for receipt in previous["receipts"] if receipt["caseId"] != "TGDOC-010"
    )
    stale["artifactDigest"] = "f" * 64
    stale["attestation"] = fixture.gate._sign_qa_receipt(stale, local_authority)

    with pytest.raises(ValueError, match="existing QA receipt artifact"):
        record(
            module,
            manifest,
            evidence_root,
            artifact_identity=fixture.identity,
            existing_receipts=previous,
            required_case_ids={"TGDOC-010"},
            installed_owner_proven=True,
            attestation_authority=local_authority,
        )


def test_writer_preserves_legacy_local_pass_when_only_source_candidate_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    externally_signed_release_fixture,
) -> None:
    fixture = externally_signed_release_fixture
    module = load_module()
    evidence_root = tmp_path / "private-evidence"
    manifest = write_manifest(
        evidence_root,
        case_id="TGDOC-010",
        verifier={"id": "tgd010-semantic-v1", "manifest": "caller-verifier.json"},
    )
    monkeypatch.setattr(
        module,
        "_derive_registered_pass",
        lambda **_kwargs: {
            "id": "tgd010-semantic-v1",
            "manifestSha256": "a" * 64,
        },
    )
    previous = fixture.support._qa_case_receipts(fixture.gate, fixture.identity)
    local_authority = fixture.gate._qa_receipt_attestation_authority(
        fixture.installed,
        fixture.owner_state,
    )
    assert local_authority is not None
    preserved = next(
        receipt for receipt in previous["receipts"] if receipt["caseId"] != "TGDOC-010"
    )
    preserved["candidateDigest"] = "f" * 64
    preserved["attestation"] = fixture.gate._sign_qa_receipt(
        preserved,
        local_authority,
    )
    preserved_before = json.loads(json.dumps(preserved))

    emitted = record(
        module,
        manifest,
        evidence_root,
        artifact_identity=fixture.identity,
        existing_receipts=previous,
        required_case_ids={"TGDOC-010"},
        installed_owner_proven=True,
        attestation_authority=local_authority,
    )

    emitted_by_case = {
        receipt["caseId"]: receipt for receipt in emitted["receipts"]
    }
    assert emitted_by_case[preserved["caseId"]] == preserved_before


def test_release_evidence_writer_requires_actual_signed_service_acknowledgments(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    externally_signed_release_fixture,
) -> None:
    fixture = externally_signed_release_fixture
    module = load_module()
    evidence_root = tmp_path / "private-evidence"
    manifest = write_manifest(evidence_root)
    monkeypatch.setattr(
        module,
        "_derive_registered_pass",
        lambda **_kwargs: {
            "id": "tr026-semantic-v1",
            "manifestSha256": "a" * 64,
        },
    )
    service_status = {
        "caseId": "TR-026",
        "restartState": "ready",
        "requiredServices": ["librechat-core", "telegram-bot"],
        "acknowledgedServices": ["librechat-core", "telegram-bot"],
        "missingServices": [],
        "serviceAckDigest": "sha256:" + hashlib.sha256(b"actual-service-event").hexdigest(),
        "sessionRef": "qa_" + "a" * 24,
    }
    signing = external_signing_authority(module, fixture)

    result = record(
        module,
        manifest,
        evidence_root,
        artifact_identity=fixture.identity,
        installed_owner_proven=True,
        attestation_authority=None,
        service_ack_status=service_status,
        service_ack_validator=lambda: dict(service_status),
        external_attestation_authority=signing,
        require_external_attestation=True,
    )

    receipt = result["receipts"][0]
    assert {
        entry["serviceId"] for entry in receipt["serviceAcknowledgements"]
    } == {"librechat-core", "telegram-bot"}
    assert all(
        entry["acknowledgementDigest"] == service_status["serviceAckDigest"]
        for entry in receipt["serviceAcknowledgements"]
    )
    assert receipt["serviceAckDigest"] != service_status["serviceAckDigest"]
    assert receipt["serviceAckDigest"] == (
        fixture.gate._load_external_release_attestation().service_acknowledgement_digest(
            receipt["serviceAcknowledgements"]
        )
    )


@pytest.mark.parametrize(
    ("attack", "expected_error"),
    (
        ("missing_witness", "external release attestation authority is unavailable"),
        ("publisher_key_substitution", "external release evidence attestation is invalid"),
        ("fabricated_producer", "external release evidence attestation is invalid"),
    ),
)
def test_release_evidence_writer_rejects_same_owner_external_authority_forgery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    externally_signed_release_fixture,
    attack: str,
    expected_error: str,
) -> None:
    fixture = externally_signed_release_fixture
    module = load_module()
    evidence_root = tmp_path / "private-evidence"
    manifest = write_manifest(
        evidence_root,
        case_id="TGDOC-010",
        verifier={"id": "tgd010-semantic-v1", "manifest": "caller-verifier.json"},
    )
    monkeypatch.setattr(
        module,
        "_derive_registered_pass",
        lambda **_kwargs: {
            "id": "tgd010-semantic-v1",
            "manifestSha256": "a" * 64,
        },
    )
    signing = external_signing_authority(module, fixture)
    if attack == "missing_witness":
        current = signing.verification_authority
        signing.verification_authority = fixture.gate.ExternalReleaseAttestationAuthority(
            expected_policy_sha256=current.expected_policy_sha256,
            ledger_path=current.ledger_path,
            ledger_witness=None,
        )
    elif attack == "publisher_key_substitution":
        signing.publisher_signer = fixture.support._ExternalFixtureSigner(
            fixture.support._external_fixture_keys()["observation-producer"]
        )
    else:
        signing.producer_attestor = lambda _receipt: [
            {"signature": "hmac-sha256:" + "f" * 64}
        ]

    with pytest.raises(ValueError, match=expected_error):
        record(
            module,
            manifest,
            evidence_root,
            artifact_identity=fixture.identity,
            required_case_ids={"TGDOC-010"},
            installed_owner_proven=True,
            attestation_authority=None,
            external_attestation_authority=signing,
            require_external_attestation=True,
        )


def test_release_evidence_writer_rejects_missing_or_forged_service_signatures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    externally_signed_release_fixture,
) -> None:
    fixture = externally_signed_release_fixture
    module = load_module()
    evidence_root = tmp_path / "private-evidence"
    manifest = write_manifest(evidence_root)
    monkeypatch.setattr(
        module,
        "_derive_registered_pass",
        lambda **_kwargs: {
            "id": "tr026-semantic-v1",
            "manifestSha256": "a" * 64,
        },
    )
    service_status = {
        "caseId": "TR-026",
        "restartState": "ready",
        "requiredServices": ["librechat-core", "telegram-bot"],
        "acknowledgedServices": ["librechat-core", "telegram-bot"],
        "missingServices": [],
        "serviceAckDigest": "sha256:" + "f" * 64,
        "sessionRef": "qa_" + "a" * 24,
    }
    signing = external_signing_authority(module, fixture)
    valid_service_attestor = signing.service_attestor
    arguments = {
        "artifact_identity": fixture.identity,
        "installed_owner_proven": True,
        "attestation_authority": None,
        "service_ack_status": service_status,
        "service_ack_validator": lambda: dict(service_status),
        "external_attestation_authority": signing,
        "require_external_attestation": True,
    }

    signing.service_attestor = None
    with pytest.raises(ValueError, match="external service attestation authority"):
        record(module, manifest, evidence_root, **arguments)

    assert valid_service_attestor is not None

    def forged_service_attestor(receipt, status):
        return [
            {**item, "signature": "hmac-sha256:" + "f" * 64}
            for item in valid_service_attestor(receipt, status)
        ]

    signing.service_attestor = forged_service_attestor
    with pytest.raises(ValueError, match="external release evidence attestation"):
        record(module, manifest, evidence_root, **arguments)


def test_failed_release_evidence_revokes_the_previous_signed_pass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    externally_signed_release_fixture,
) -> None:
    fixture = externally_signed_release_fixture
    module = load_module()
    evidence_root = tmp_path / "private-evidence"
    manifest = write_manifest(
        evidence_root,
        case_id="TGDOC-010",
        verifier={"id": "tgd010-semantic-v1", "manifest": "caller-verifier.json"},
    )
    monkeypatch.setattr(
        module,
        "_derive_registered_pass",
        lambda **_kwargs: {
            "id": "tgd010-semantic-v1",
            "manifestSha256": "a" * 64,
        },
    )
    signing = external_signing_authority(module, fixture)
    arguments = {
        "artifact_identity": fixture.identity,
        "required_case_ids": {"TGDOC-010"},
        "installed_owner_proven": True,
        "attestation_authority": None,
        "external_attestation_authority": signing,
        "require_external_attestation": True,
    }
    passed = record(module, manifest, evidence_root, **arguments)
    previous = passed["receipts"][0]
    failed_manifest = write_manifest(
        evidence_root,
        case_id="TGDOC-010",
        status="FAIL",
    )

    failed = record(
        module,
        failed_manifest,
        evidence_root,
        existing_receipts=passed,
        **arguments,
    )

    assert failed["receipts"][0]["status"] == "FAIL"
    with pytest.raises(RuntimeError, match="superseded or revoked"):
        fixture.gate._load_external_release_attestation().verify_release_receipt(
            previous,
            policy=fixture.gate._test_external_release_policy,
            ledger_path=signing.verification_authority.ledger_path,
            ledger_witness=signing.verification_authority.ledger_witness,
            expected_case_id="TGDOC-010",
            expected_surface="telegram",
            expected_candidate_digest=previous["candidateDigest"],
            expected_artifact_digest=previous["artifactDigest"],
            expected_owner_binding=previous["ownerBindingSha256"],
            expected_verifier_id="tgd010-semantic-v1",
            expected_verifier_manifest_sha256="a" * 64,
        )


def test_interrupted_revocation_recovers_only_the_same_authenticated_case(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    externally_signed_release_fixture,
) -> None:
    fixture = externally_signed_release_fixture
    module = load_module()
    evidence_root = tmp_path / "private-evidence"
    manifest = write_manifest(
        evidence_root,
        case_id="TGDOC-010",
        verifier={"id": "tgd010-semantic-v1", "manifest": "caller-verifier.json"},
    )
    monkeypatch.setattr(
        module,
        "_derive_registered_pass",
        lambda **_kwargs: {
            "id": "tgd010-semantic-v1",
            "manifestSha256": "a" * 64,
        },
    )
    signing = external_signing_authority(module, fixture)
    arguments = {
        "artifact_identity": fixture.identity,
        "required_case_ids": {"TGDOC-010"},
        "installed_owner_proven": True,
        "attestation_authority": None,
        "external_attestation_authority": signing,
        "require_external_attestation": True,
    }
    passed = record(module, manifest, evidence_root, **arguments)
    failed_manifest = write_manifest(
        evidence_root,
        case_id="TGDOC-010",
        status="FAIL",
    )

    # The trusted witness records revocation, then the process exits before
    # its private receipt-file replacement is durable.
    record(
        module,
        failed_manifest,
        evidence_root,
        existing_receipts=passed,
        **arguments,
    )

    recovered = record(
        module,
        failed_manifest,
        evidence_root,
        existing_receipts=passed,
        **arguments,
    )

    assert len(recovered["receipts"]) == 1
    assert recovered["receipts"][0]["caseId"] == "TGDOC-010"
    assert recovered["receipts"][0]["status"] == "FAIL"

    forged = {
        "contractVersion": passed["contractVersion"],
        "receipts": [
            {
                **passed["receipts"][0],
                "publisherAttestation": "synthetic-forged-signature",
            }
        ],
    }
    with pytest.raises(ValueError, match="existing external QA receipt attestation"):
        record(
            module,
            failed_manifest,
            evidence_root,
            existing_receipts=forged,
            **arguments,
        )

    for field in ("ownerBindingSha256", "candidateDigest", "artifactDigest"):
        wrong_binding = {
            "contractVersion": passed["contractVersion"],
            "receipts": [{**passed["receipts"][0], field: "f" * 64}],
        }
        with pytest.raises(ValueError, match="existing external QA receipt attestation"):
            record(
                module,
                failed_manifest,
                evidence_root,
                existing_receipts=wrong_binding,
                **arguments,
            )


def test_caller_declared_pass_and_synthetic_screenshot_cannot_create_receipt(
    tmp_path: Path,
) -> None:
    module = load_module()
    evidence_root = tmp_path / "private-evidence"
    manifest = write_manifest(evidence_root)

    with pytest.raises(
        ValueError,
        match="registered semantic verifier|semantic verifier is not registered",
    ):
        record(module, manifest, evidence_root)


@pytest.mark.parametrize(
    ("module_name", "loader_name", "expected_error"),
    (
        (
            "parallel_work_release_gate",
            "_load_release_gate",
            "release gate module provenance is invalid",
        ),
        (
            "local_qa_runtime_control_for_qa_evidence",
            "_load_local_qa_control",
            "local-QA runtime control provenance is invalid",
        ),
    ),
)
def test_untrusted_preloaded_modules_cannot_impersonate_security_authorities(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    module_name: str,
    loader_name: str,
    expected_error: str,
) -> None:
    module = load_module()
    forged = SimpleNamespace(__file__=str(tmp_path / "forged-authority.py"))
    monkeypatch.setitem(sys.modules, module_name, forged)

    with pytest.raises(RuntimeError, match=expected_error):
        getattr(module, loader_name)()


def test_recorder_uses_the_release_evaluator_future_timestamp_limit(
    tmp_path: Path,
) -> None:
    module = load_module()
    now = datetime.now(timezone.utc)
    evidence_root = tmp_path / "private-evidence"
    manifest = write_manifest(
        evidence_root,
        status="PARTIAL",
        run_at=now + timedelta(seconds=90),
    )

    with pytest.raises(ValueError, match="stale or in the future"):
        record(module, manifest, evidence_root, now=now)


def test_verifier_manifest_is_verified_and_parsed_from_one_private_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_module()
    manifest = tmp_path / "semantic-manifest.json"
    manifest.write_text('{"status":"PASS"}\n', encoding="utf-8")
    manifest.chmod(0o600)
    original_read = module.os.read
    swapped = False

    def replace_after_read(descriptor: int, size: int) -> bytes:
        nonlocal swapped
        value = original_read(descriptor, size)
        if not swapped:
            swapped = True
            manifest.write_text('{"status":"FAIL"}\n', encoding="utf-8")
        return value

    monkeypatch.setattr(module.os, "read", replace_after_read)

    with pytest.raises(ValueError, match="semantic verifier manifest changed"):
        module._private_verifier_manifest_snapshot(manifest)


@pytest.mark.parametrize("mode", (0o640, 0o644, 0o666))
def test_semantic_verifier_manifest_must_remain_owner_private(
    tmp_path: Path,
    mode: int,
) -> None:
    module = load_module()
    manifest = tmp_path / "semantic-manifest.json"
    manifest.write_text('{"status":"PASS"}\n', encoding="utf-8")
    manifest.chmod(mode)

    with pytest.raises(ValueError, match="semantic verifier manifest must be private"):
        module._private_verifier_manifest_snapshot(manifest)


def test_semantic_verifier_does_not_inherit_runtime_authority_overrides(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_module()
    evidence_root = tmp_path / "private-evidence"
    manifest = write_manifest(
        evidence_root,
        case_id="TGDOC-010",
        surface="telegram",
        verifier={"id": "tgd010-semantic-v1", "manifest": "caller-verifier.json"},
    )
    declared = json.loads(manifest.read_text(encoding="utf-8"))
    monkeypatch.setenv("VIVENTIUM_RUNTIME_DIR", "/synthetic/runtime-override")
    monkeypatch.setenv("VIVENTIUM_LOCAL_QA_CASE_TOKEN", "synthetic-secret")

    class Verifier:
        @staticmethod
        def assess_manifest(*_args, **_kwargs):
            assert "VIVENTIUM_RUNTIME_DIR" not in module.os.environ
            assert "VIVENTIUM_LOCAL_QA_CASE_TOKEN" not in module.os.environ
            return {"status": "PASS"}

        @staticmethod
        def receipt_manifest(*, result):
            assert result == {"status": "PASS"}
            return {key: value for key, value in declared.items() if key != "verifier"}

    monkeypatch.setattr(module, "_load_registered_verifier", lambda *_args, **_kwargs: Verifier())

    result = record(
        module,
        manifest,
        evidence_root,
        required_case_ids={"TGDOC-010"},
        installed_owner_proven=True,
    )

    assert result["receipts"][0]["status"] == "PASS"
    assert module.os.environ["VIVENTIUM_RUNTIME_DIR"] == "/synthetic/runtime-override"
    assert module.os.environ["VIVENTIUM_LOCAL_QA_CASE_TOKEN"] == "synthetic-secret"


def test_caller_json_cannot_impersonate_registered_semantic_verifier(
    tmp_path: Path,
) -> None:
    module = load_module()
    evidence_root = tmp_path / "private-evidence"
    manifest = write_manifest(
        evidence_root,
        case_id="TGDOC-010",
        surface="telegram",
        verifier={"id": "tgd010-semantic-v1", "manifest": "caller-verifier.json"},
    )

    with pytest.raises(ValueError, match="did not derive PASS"):
        record(
            module,
            manifest,
            evidence_root,
            required_case_ids={"TGDOC-010"},
            installed_owner_proven=True,
        )


@pytest.mark.parametrize(
    ("case_id", "verifier_id", "verifier_path"),
    [
        (
            f"PWK-UC-{number:03d}",
            "pwk-installed-journey-v1",
            "qa/parallel-orchestrator/scripts/installed_journey_qa.py",
        )
        for number in range(14, 20)
    ]
    + [
        (
            "EMO-UC-047",
            "emo047-semantic-v1",
            "qa/emotional-cortex/scripts/run_emo_uc_047.py",
        ),
        (
            "EMO-UC-048",
            "emo048-semantic-v1",
            "qa/emotional-cortex/scripts/run_emo_uc_048.py",
        ),
        (
            "MPV-061",
            "mpv061-semantic-v1",
            "qa/modern-playground-voice/scripts/mpv_061_full_journey_semantic_verifier.py",
        ),
        (
            "REL-UC-004",
            "rel004-semantic-v1",
            "qa/release-readiness/scripts/rel_uc_004_semantic_verifier.py",
        ),
        (
            "TGDOC-010",
            "tgd010-semantic-v1",
            "qa/telegram-document-attachments/scripts/worker_bee_file_parity_qa.py",
        ),
        (
            "TR-026",
            "tr026-semantic-v1",
            "qa/telegram-runtime/scripts/tr026_installed_journey_semantic_verifier.py",
        ),
    ],
)
def test_required_installed_journeys_have_registered_semantic_owners(
    case_id: str,
    verifier_id: str,
    verifier_path: str,
) -> None:
    module = load_module()

    assert module.REGISTERED_SEMANTIC_VERIFIERS[case_id] == {
        "id": verifier_id,
        "path": Path(verifier_path),
    }


def test_semantic_verifier_manifest_cannot_escape_evidence_root(tmp_path: Path) -> None:
    module = load_module()
    evidence_root = tmp_path / "private-evidence"
    outside = tmp_path / "outside.json"
    outside.write_text('{"status":"PASS"}\n', encoding="utf-8")
    manifest = write_manifest(
        evidence_root,
        case_id="TGDOC-010",
        surface="telegram",
        verifier={"id": "tgd010-semantic-v1", "manifest": "../outside.json"},
    )

    with pytest.raises(ValueError, match="inside the evidence root"):
        record(
            module,
            manifest,
            evidence_root,
            required_case_ids={"TGDOC-010"},
            installed_owner_proven=True,
        )


def test_registered_semantic_verifier_can_derive_pass(tmp_path: Path) -> None:
    module = load_module()
    support_path = REPO_ROOT / "tests" / "release" / "test_telegram_worker_file_parity_qa.py"
    spec = importlib.util.spec_from_file_location("tgd010_qa_evidence_test_support", support_path)
    assert spec is not None and spec.loader is not None
    support = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(support)
    semantic_manifest, evidence_root, _old_candidate, _old_artifact = support.complete_manifest(
        tmp_path
    )
    identity = artifact_identity()
    candidate_digest, artifact_digest = module._load_release_gate()._qa_candidate_digests(
        identity
    )
    semantic_manifest["candidate"] = {
        "candidateDigest": candidate_digest,
        "artifactDigest": artifact_digest,
    }
    for entry in semantic_manifest["evidence"]:
        entry["candidateDigest"] = candidate_digest
        entry["artifactDigest"] = artifact_digest
        evidence_path = evidence_root / entry["path"]
        if evidence_path.suffix == ".json":
            document = json.loads(evidence_path.read_text(encoding="utf-8"))
            document["candidateDigest"] = candidate_digest
            document["artifactDigest"] = artifact_digest
            content = (
                json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
                + b"\n"
            )
            evidence_path.write_bytes(content)
            evidence_path.chmod(0o600)
            entry["sha256"] = hashlib.sha256(content).hexdigest()
    semantic_path = evidence_root / "semantic-manifest.json"
    semantic_path.write_text(json.dumps(semantic_manifest), encoding="utf-8")
    semantic_path.chmod(0o600)
    registration = module.REGISTERED_SEMANTIC_VERIFIERS["TGDOC-010"]
    verifier = module._load_registered_verifier(
        REPO_ROOT / registration["path"], case_id="TGDOC-010"
    )
    verifier_result = verifier.assess_manifest(
        semantic_manifest,
        evidence_root=evidence_root,
        expected_candidate_digest=candidate_digest,
        expected_artifact_digest=artifact_digest,
        installed_owner_proven=True,
        now=support.NOW,
    )
    receipt_manifest = verifier.receipt_manifest(result=verifier_result)
    receipt_manifest["verifier"] = {
        "id": registration["id"],
        "manifest": semantic_path.relative_to(evidence_root).as_posix(),
    }
    manifest = evidence_root / "result.json"
    manifest.write_text(json.dumps(receipt_manifest), encoding="utf-8")

    result = record(
        module,
        manifest,
        evidence_root,
        artifact_identity=identity,
        required_case_ids={"TGDOC-010"},
        installed_owner_proven=True,
        now=support.NOW,
    )

    assert result["receipts"][0]["caseId"] == "TGDOC-010"
    assert result["receipts"][0]["status"] == "PASS"
    receipt = result["receipts"][0]
    assert receipt["verifierId"] == "tgd010-semantic-v1"
    assert receipt["ownerBindingSha256"] == "b" * 64
    assert receipt["attestation"].startswith("hmac-sha256:")
    assert module._load_release_gate()._qa_receipt_attestation_valid(
        receipt,
        (b"fixture-attestation-key-material", "b" * 64),
    )

    arbitrary = evidence_root / "arbitrary.png"
    arbitrary.write_bytes(b"arbitrary screenshot bytes")
    arbitrary_digest = hashlib.sha256(arbitrary.read_bytes()).hexdigest()
    receipt_manifest["evidence"][0] = {
        "kind": "telegram_ui",
        "path": arbitrary.relative_to(evidence_root).as_posix(),
        "sha256": arbitrary_digest,
    }
    manifest.write_text(json.dumps(receipt_manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="does not match the semantic verifier result"):
        record(
            module,
            manifest,
            evidence_root,
            artifact_identity=identity,
            required_case_ids={"TGDOC-010"},
            installed_owner_proven=True,
            now=support.NOW,
        )


def test_registered_voice_journey_derives_a_candidate_bound_pass(tmp_path: Path) -> None:
    module = load_module()
    support_path = (
        REPO_ROOT / "tests" / "release" / "test_mpv_061_full_journey_semantic_runner.py"
    )
    spec = importlib.util.spec_from_file_location("mpv061_qa_evidence_test_support", support_path)
    assert spec is not None and spec.loader is not None
    support = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(support)
    identity = artifact_identity()
    candidate_digest, artifact_digest = module._load_release_gate()._qa_candidate_digests(
        identity
    )
    semantic_manifest, evidence_root, _old_candidate, _old_artifact = support.complete_manifest(
        tmp_path,
        candidate_digest=candidate_digest,
        artifact_digest=artifact_digest,
    )
    semantic_path = evidence_root / "semantic-manifest.json"
    semantic_path.write_text(json.dumps(semantic_manifest), encoding="utf-8")
    semantic_path.chmod(0o600)
    registration = module.REGISTERED_SEMANTIC_VERIFIERS["MPV-061"]
    verifier = module._load_registered_verifier(
        REPO_ROOT / registration["path"], case_id="MPV-061"
    )
    checked_at = datetime.fromisoformat(str(semantic_manifest["runAt"]))
    derived = verifier.assess_manifest(
        semantic_manifest,
        evidence_root=evidence_root,
        expected_candidate_digest=candidate_digest,
        expected_artifact_digest=artifact_digest,
        installed_owner_proven=True,
        now=checked_at,
    )
    receipt_manifest = verifier.receipt_manifest(result=derived)
    receipt_manifest["verifier"] = {
        "id": registration["id"],
        "manifest": semantic_path.relative_to(evidence_root).as_posix(),
    }
    manifest = evidence_root / "result.json"
    manifest.write_text(json.dumps(receipt_manifest), encoding="utf-8")

    result = record(
        module,
        manifest,
        evidence_root,
        artifact_identity=identity,
        required_case_ids={"MPV-061"},
        installed_owner_proven=True,
        now=checked_at,
    )

    assert result["receipts"][0]["caseId"] == "MPV-061"
    assert result["receipts"][0]["surface"] == "voice"
    assert result["receipts"][0]["status"] == "PASS"


def test_registered_parallel_journey_derives_a_candidate_bound_pass(tmp_path: Path) -> None:
    module = load_module()
    support_path = REPO_ROOT / "tests" / "release" / "test_parallel_work_installed_journey_qa.py"
    spec = importlib.util.spec_from_file_location("pwk_qa_evidence_test_support", support_path)
    assert spec is not None and spec.loader is not None
    support = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(support)
    registration = module.REGISTERED_SEMANTIC_VERIFIERS["PWK-UC-014"]
    verifier = module._load_registered_verifier(
        REPO_ROOT / registration["path"], case_id="PWK-UC-014"
    )
    semantic_manifest, semantic_path, evidence_root, identity_path = support._strict_manifest(
        tmp_path, verifier
    )
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    candidate_digest, artifact_digest = module._load_release_gate()._qa_candidate_digests(
        identity
    )
    checked_at = datetime.fromisoformat(str(semantic_manifest["runAt"]))
    derived = verifier.assess_manifest(
        semantic_manifest,
        evidence_root=evidence_root,
        expected_candidate_digest=candidate_digest,
        expected_artifact_digest=artifact_digest,
        installed_owner_proven=True,
        now=checked_at,
    )
    receipt_manifest = verifier.receipt_manifest(result=derived)
    receipt_manifest["verifier"] = {
        "id": registration["id"],
        "manifest": semantic_path.relative_to(evidence_root).as_posix(),
    }
    manifest = evidence_root / "result.json"
    manifest.write_text(json.dumps(receipt_manifest), encoding="utf-8")

    result = record(
        module,
        manifest,
        evidence_root,
        artifact_identity=identity,
        required_case_ids={"PWK-UC-014"},
        installed_owner_proven=True,
        now=checked_at,
    )

    assert result["receipts"][0]["caseId"] == "PWK-UC-014"
    assert result["receipts"][0]["surface"] == "telegram"
    assert result["receipts"][0]["status"] == "PASS"


def test_pass_receipt_requires_the_private_runtime_signing_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_module()
    evidence_root = tmp_path / "private-evidence"
    manifest = write_manifest(
        evidence_root,
        case_id="TGDOC-010",
        surface="telegram",
    )
    monkeypatch.setattr(
        module,
        "_derive_registered_pass",
        lambda **_kwargs: {
            "id": "tgd010-semantic-v1",
            "manifestSha256": "a" * 64,
        },
    )

    with pytest.raises(ValueError, match="authenticated QA receipt authority"):
        record(
            module,
            manifest,
            evidence_root,
            required_case_ids={"TGDOC-010"},
            installed_owner_proven=True,
            attestation_authority=None,
        )


def test_fabricated_service_acknowledgment_cannot_create_authenticated_pass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_module()
    evidence_root = tmp_path / "private-evidence"
    manifest = write_manifest(evidence_root)
    monkeypatch.setattr(
        module,
        "_derive_registered_pass",
        lambda **_kwargs: {
            "id": "tr026-semantic-v1",
            "manifestSha256": "a" * 64,
        },
    )

    with pytest.raises(ValueError, match="restart proof is not authenticated"):
        record(
            module,
            manifest,
            evidence_root,
            installed_owner_proven=True,
        )


def test_authenticated_service_acknowledgment_is_bound_to_signed_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_module()
    evidence_root = tmp_path / "private-evidence"
    manifest = write_manifest(evidence_root)
    monkeypatch.setattr(
        module,
        "_derive_registered_pass",
        lambda **_kwargs: {
            "id": "tr026-semantic-v1",
            "manifestSha256": "a" * 64,
        },
    )
    service_acknowledgment = {
        "caseId": "TR-026",
        "restartState": "ready",
        "requiredServices": ["librechat-core", "telegram-bot"],
        "acknowledgedServices": ["librechat-core", "telegram-bot"],
        "missingServices": [],
        "serviceAckDigest": "sha256:" + hashlib.sha256(b"signed-service-proof").hexdigest(),
        "sessionRef": "qa_" + "a" * 24,
    }

    result = record(
        module,
        manifest,
        evidence_root,
        installed_owner_proven=True,
        service_ack_status=service_acknowledgment,
        service_ack_validator=lambda: dict(service_acknowledgment),
    )

    receipt = result["receipts"][0]
    assert receipt["serviceAckDigest"] == service_acknowledgment["serviceAckDigest"]
    assert receipt["serviceAckSessionRef"] == service_acknowledgment["sessionRef"]
    assert module._load_release_gate()._qa_receipt_attestation_valid(
        receipt,
        (b"fixture-attestation-key-material", "b" * 64),
    )

    with pytest.raises(ValueError, match="restart proof is not authenticated"):
        record(
            module,
            manifest,
            evidence_root,
            installed_owner_proven=True,
            service_ack_status=service_acknowledgment,
            service_ack_validator=lambda: {
                **service_acknowledgment,
                "serviceAckDigest": "sha256:" + "f" * 64,
            },
        )


@pytest.mark.parametrize(
    "service_ack_status",
    [
        None,
        {
            "caseId": "TR-026",
            "restartState": "waiting",
            "requiredServices": ["librechat-core", "telegram-bot"],
            "acknowledgedServices": ["librechat-core"],
            "missingServices": ["telegram-bot"],
            "serviceAckDigest": "",
        },
    ],
)
def test_pass_receipt_fails_closed_without_complete_live_service_restart_proof(
    tmp_path: Path, service_ack_status: object
) -> None:
    module = load_module()
    evidence_root = tmp_path / "private-evidence"
    manifest = write_manifest(evidence_root)

    with pytest.raises(ValueError, match="restart proof"):
        record(
            module,
            manifest,
            evidence_root,
            service_ack_status=service_ack_status,
        )


def test_executable_catalog_includes_voice_and_file_worker_cases() -> None:
    module = load_module()

    required = module._required_case_ids(REPO_ROOT)

    assert {"MPV-061", "TGDOC-010"} <= required


@pytest.mark.parametrize(
    ("case_id", "surface"),
    (("MPV-061", "voice"), ("TGDOC-010", "telegram")),
)
def test_voice_and_file_worker_receipts_require_the_owning_surface(
    tmp_path: Path,
    case_id: str,
    surface: str,
) -> None:
    module = load_module()
    evidence_root = tmp_path / "private-evidence"
    manifest = write_manifest(
        evidence_root,
        case_id=case_id,
        status="PARTIAL",
        surface=surface,
    )

    result = record(
        module,
        manifest,
        evidence_root,
        required_case_ids={"MPV-061", "TGDOC-010"},
    )
    assert result["receipts"][0]["caseId"] == case_id
    assert result["receipts"][0]["surface"] == surface

    wrong_surface_manifest = write_manifest(
        evidence_root,
        case_id=case_id,
        status="PARTIAL",
        surface="api",
    )
    with pytest.raises(ValueError, match="surface"):
        record(
            module,
            wrong_surface_manifest,
            evidence_root,
            required_case_ids={"MPV-061", "TGDOC-010"},
        )


def test_rejects_missing_local_qa_authority(tmp_path: Path) -> None:
    module = load_module()
    evidence_root = tmp_path / "private-evidence"
    manifest = write_manifest(evidence_root)

    with pytest.raises(ValueError, match="local QA"):
        record(
            module,
            manifest,
            evidence_root,
            local_qa_request={"contractVersion": 1, "mode": "local-qa", "requested": False},
        )


def test_rejects_unknown_case_and_non_pass_receipt(tmp_path: Path) -> None:
    module = load_module()
    evidence_root = tmp_path / "private-evidence"
    unknown = write_manifest(evidence_root, case_id="PWK-UNKNOWN")
    with pytest.raises(ValueError, match="required QA case"):
        record(module, unknown, evidence_root)

    partial = write_manifest(evidence_root, status="PARTIAL")
    result = record(module, partial, evidence_root)
    assert result["receipts"][0]["status"] == "PARTIAL"


def test_rejects_outside_or_tampered_evidence(tmp_path: Path) -> None:
    module = load_module()
    evidence_root = tmp_path / "private-evidence"
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"outside")
    manifest = write_manifest(evidence_root, evidence_path=outside)
    with pytest.raises(ValueError, match="inside the private evidence root"):
        record(module, manifest, evidence_root)

    manifest = write_manifest(evidence_root)
    (evidence_root / "telegram-after.png").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="digest"):
        record(module, manifest, evidence_root)


@pytest.mark.parametrize("offset", [timedelta(days=-2), timedelta(minutes=10)])
def test_rejects_stale_or_future_manifest(tmp_path: Path, offset: timedelta) -> None:
    module = load_module()
    now = datetime.now(timezone.utc)
    evidence_root = tmp_path / "private-evidence"
    manifest = write_manifest(evidence_root, run_at=now + offset)

    with pytest.raises(ValueError, match="timestamp"):
        record(module, manifest, evidence_root, now=now)


def test_exact_case_upsert_never_creates_duplicates(tmp_path: Path) -> None:
    module = load_module()
    evidence_root = tmp_path / "private-evidence"
    first_manifest = write_manifest(evidence_root, status="PARTIAL")
    first = record(module, first_manifest, evidence_root)
    second_manifest = write_manifest(evidence_root, status="PARTIAL")
    second = record(
        module,
        second_manifest,
        evidence_root,
        existing_receipts=first,
    )

    assert [receipt["caseId"] for receipt in second["receipts"]] == ["TR-026"]


def test_exact_case_upsert_preserves_prior_candidate_partial_receipts(
    tmp_path: Path,
) -> None:
    module = load_module()
    gate = module._load_release_gate()
    evidence_root = tmp_path / "private-evidence"
    current_identity = artifact_identity()
    current_candidate, current_artifact = gate._qa_candidate_digests(current_identity)
    old_candidate = "1" * 64
    old_artifact = "2" * 64
    run_at = datetime.now(timezone.utc).isoformat()
    preserved_case_ids = [f"PWK-{number:03d}" for number in range(1, 11)]
    prior_receipts = [
        {
            "artifactDigest": old_artifact,
            "candidateDigest": old_candidate,
            "caseId": case_id,
            "evidenceDigest": hashlib.sha256(case_id.encode()).hexdigest(),
            "runAt": run_at,
            "status": "PARTIAL",
            "surface": "web",
        }
        for case_id in preserved_case_ids
    ]
    prior_receipts.append(
        {
            "artifactDigest": old_artifact,
            "candidateDigest": old_candidate,
            "caseId": "PWK-UC-015",
            "evidenceDigest": "3" * 64,
            "runAt": run_at,
            "status": "PARTIAL",
            "surface": "web",
        }
    )
    existing = {"contractVersion": 1, "receipts": prior_receipts}
    preserved_before = {
        receipt["caseId"]: json.loads(json.dumps(receipt))
        for receipt in prior_receipts
        if receipt["caseId"] != "PWK-UC-015"
    }
    manifest = write_manifest(
        evidence_root,
        case_id="PWK-UC-015",
        status="PARTIAL",
        surface="web",
    )

    emitted = record(
        module,
        manifest,
        evidence_root,
        artifact_identity=current_identity,
        existing_receipts=existing,
        required_case_ids={"PWK-UC-015"},
    )

    emitted_by_case = {
        receipt["caseId"]: receipt for receipt in emitted["receipts"]
    }
    assert len(emitted["receipts"]) == len(emitted_by_case) == 11
    assert {
        case_id: emitted_by_case[case_id] for case_id in preserved_case_ids
    } == preserved_before
    assert emitted_by_case["PWK-UC-015"]["candidateDigest"] == current_candidate
    assert emitted_by_case["PWK-UC-015"]["artifactDigest"] == current_artifact
    assert emitted_by_case["PWK-UC-015"] != prior_receipts[-1]

    target = tmp_path / "runtime" / "parallel-work-qa-case-receipts.json"
    module.write_receipt_set(target, emitted)
    assert target.stat().st_mode & 0o777 == 0o600
    assert json.loads(target.read_text(encoding="utf-8")) == emitted
    assert not list(target.parent.glob(f".{target.name}.*.tmp"))

    records = tuple(
        gate.GateRecord(case_id, "PASS", f"qa/{case_id}.md", "fixture")
        for case_id in (*preserved_case_ids, "PWK-UC-015")
    )
    bound, summary = gate._bind_catalog_gates_to_qa_receipts(
        records,
        emitted,
        current_identity,
        mode="local-qa",
        installed_root=None,
        runtime_owner_state=None,
    )
    bound_by_case = {record.case_id: record for record in bound}
    assert summary["status"] == "blocked"
    assert all(
        bound_by_case[case_id].status == "UNKNOWN"
        and bound_by_case[case_id].detail == "qa_receipt_not_pass"
        for case_id in preserved_case_ids
    )

    stale_pass_set = json.loads(json.dumps(existing))
    stale_pass = stale_pass_set["receipts"][0]
    stale_pass.update(
        {
            "status": "PASS",
            "ownerBindingSha256": "b" * 64,
            "receiptNonce": "4" * 32,
            "verifierId": "fixture-semantic-v1",
            "verifierManifestSha256": "5" * 64,
        }
    )
    stale_pass["attestation"] = gate._sign_qa_receipt(
        stale_pass,
        (b"fixture-attestation-key-material", "b" * 64),
    )
    with pytest.raises(
        ValueError,
        match="existing QA receipt artifact",
    ):
        record(
            module,
            manifest,
            evidence_root,
            artifact_identity=current_identity,
            existing_receipts=stale_pass_set,
            required_case_ids={"PWK-UC-015"},
        )


def test_pwk_uc_015_receipt_uses_server_derived_hmac_covered_artifact_claims(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_module()
    evidence_root = tmp_path / "private-evidence"
    manifest = write_manifest(
        evidence_root,
        case_id="PWK-UC-015",
        surface="web",
    )
    monkeypatch.setattr(
        module,
        "_derive_registered_pass",
        lambda **_kwargs: {
            "id": "pwk-installed-journey-v1",
            "manifestSha256": "a" * 64,
        },
    )
    identity = artifact_identity()
    expected_fields = (
        "runningServiceSha256",
        "frontendBuildSha256",
        "apiBuildSha256",
        "promptBundleSha256",
        "runtimeEnvSha256",
    )

    emitted = record(
        module,
        manifest,
        evidence_root,
        artifact_identity=identity,
        required_case_ids={"PWK-UC-015"},
        service_ack_status=None,
    )

    receipt = emitted["receipts"][0]
    assert receipt["artifactClaims"] == {
        field: identity["installed"][field] for field in expected_fields
    }
    gate = module._load_release_gate()
    authority = (b"fixture-attestation-key-material", "b" * 64)
    assert gate._qa_receipt_attestation_valid(receipt, authority) is True
    receipt["artifactClaims"]["runningServiceSha256"] = "f" * 64
    assert gate._qa_receipt_attestation_valid(receipt, authority) is False


def test_writer_preserves_scoped_pass_when_only_unclaimed_identity_fields_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_module()
    evidence_root = tmp_path / "private-evidence"
    scoped_manifest = write_manifest(
        evidence_root,
        case_id="PWK-UC-015",
        surface="web",
    )
    monkeypatch.setattr(
        module,
        "_derive_registered_pass",
        lambda **_kwargs: {
            "id": "pwk-installed-journey-v1",
            "manifestSha256": "a" * 64,
        },
    )
    original_identity = artifact_identity()
    original = record(
        module,
        scoped_manifest,
        evidence_root,
        artifact_identity=original_identity,
        required_case_ids={"PWK-UC-015"},
        service_ack_status=None,
    )
    preserved = json.loads(json.dumps(original["receipts"][0]))
    current_identity = json.loads(json.dumps(original_identity))
    current_identity["source"]["worktreeHash"] = "1" * 64
    current_identity["installed"]["libreChatConfigSha256"] = "2" * 64
    partial_manifest = write_manifest(
        evidence_root,
        case_id="TR-026",
        status="PARTIAL",
        surface="telegram",
    )

    emitted = record(
        module,
        partial_manifest,
        evidence_root,
        artifact_identity=current_identity,
        existing_receipts=original,
    )

    emitted_by_case = {
        receipt["caseId"]: receipt for receipt in emitted["receipts"]
    }
    assert emitted_by_case["PWK-UC-015"] == preserved


def test_atomic_writer_is_private_and_round_trips(tmp_path: Path) -> None:
    module = load_module()
    target = tmp_path / "runtime" / "parallel-work-qa-case-receipts.json"
    payload = {"contractVersion": 1, "receipts": []}

    module.write_receipt_set(target, payload)

    assert json.loads(target.read_text(encoding="utf-8")) == payload
    assert target.stat().st_mode & 0o777 == 0o600
    assert not list(target.parent.glob(f".{target.name}.*.tmp"))


def test_evidence_cli_prints_only_public_case_summary_and_keeps_receipts_private(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = load_module()
    installed_root = tmp_path / "installed"
    installed_root.mkdir()
    owner_state = tmp_path / "owner.json"
    owner_state.write_text(json.dumps({"repoRoot": str(installed_root)}), encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"caseId": "TR-026", "status": "PARTIAL"}), encoding="utf-8")
    artifact = tmp_path / "artifact.json"
    artifact.write_text("{}", encoding="utf-8")
    local_request = tmp_path / "request.json"
    local_request.write_text("{}", encoding="utf-8")
    secret_nonce = "synthetic-secret-nonce-do-not-display"
    secret_attestation = "synthetic-secret-attestation-do-not-display"
    full_payload = {
        "contractVersion": 1,
        "receipts": [
            {
                "caseId": "TR-026",
                "status": "PARTIAL",
                "surface": "telegram",
                "candidateDigest": "a" * 64,
                "artifactDigest": "b" * 64,
                "runAt": "2026-08-25T12:00:00+00:00",
                "receiptNonce": secret_nonce,
                "attestation": secret_attestation,
                "ownerBindingSha256": "c" * 64,
                "publisherAttestation": {"signature": "another-secret-signature"},
            }
        ],
    }
    gate = SimpleNamespace(
        validate_runtime_owner_state_file=lambda _path: True,
        _qa_receipt_attestation_authority=lambda *_args, **_kwargs: (b"a" * 32, "b" * 64),
    )
    written: dict[str, object] = {}
    monkeypatch.setattr(module, "_load_release_gate", lambda: gate)
    monkeypatch.setattr(module, "_required_case_ids", lambda _root: {"TR-026"})
    monkeypatch.setattr(module, "record_case_receipt", lambda **_kwargs: full_payload)
    monkeypatch.setattr(
        module,
        "write_receipt_set",
        lambda _path, payload: written.update(payload),
    )

    exit_code = module.main(
        [
            "--root", str(tmp_path),
            "--installed-root", str(installed_root),
            "--runtime-owner-state", str(owner_state),
            "--artifact-identity", str(artifact),
            "--receipts", str(tmp_path / "receipts.json"),
            "--local-qa-request", str(local_request),
            "--local-qa-state", str(tmp_path / "local-state.json"),
            "--evidence-root", str(tmp_path / "evidence"),
            "--manifest", str(manifest),
        ]
    )

    output = capsys.readouterr().out
    summary = json.loads(output)
    assert exit_code == 0
    assert summary["receiptCount"] == 1
    assert summary["recordedCase"] == {
        "caseId": "TR-026",
        "status": "PARTIAL",
        "surface": "telegram",
        "candidateDigest": "a" * 64,
        "artifactDigest": "b" * 64,
        "runAt": "2026-08-25T12:00:00+00:00",
    }
    assert "receipts" not in summary
    assert secret_nonce not in output
    assert secret_attestation not in output
    assert "another-secret-signature" not in output
    assert written == full_payload


def test_evidence_cli_redacts_private_operational_error_details(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = load_module()
    installed_root = tmp_path / "installed"
    installed_root.mkdir()
    owner_state = tmp_path / "owner.json"
    owner_state.write_text("{}", encoding="utf-8")

    def raise_private_error(_path: Path) -> bool:
        raise OSError("synthetic-secret-marker /private/synthetic-account/state.json")

    monkeypatch.setattr(
        module,
        "_load_release_gate",
        lambda: SimpleNamespace(validate_runtime_owner_state_file=raise_private_error),
    )

    with pytest.raises(SystemExit):
        module.main(
            [
                "--root", str(tmp_path),
                "--installed-root", str(installed_root),
                "--runtime-owner-state", str(owner_state),
                "--artifact-identity", str(tmp_path / "artifact.json"),
                "--receipts", str(tmp_path / "receipts.json"),
                "--local-qa-request", str(tmp_path / "request.json"),
                "--local-qa-state", str(tmp_path / "local-state.json"),
                "--evidence-root", str(tmp_path / "evidence"),
                "--manifest", str(tmp_path / "manifest.json"),
            ]
        )

    error = capsys.readouterr().err
    assert "qa_evidence_io_failed" in error
    assert "synthetic-secret-marker" not in error
    assert "/private/synthetic-account" not in error


def test_public_cli_exposes_only_candidate_bound_qa_evidence_recording() -> None:
    source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    assert "qa-evidence     Record candidate-bound private QA evidence receipts." in source
    usage = source.split("    qa-evidence)", 1)[1].split("    release-check)", 1)[0]
    assert "qa-evidence record --manifest <private-result.json>" in usage
    command = source.rsplit("  qa-evidence)", 1)[1].split("  qa-control)", 1)[0]
    assert '"$RUNTIME_DIR/parallel-work-artifact-identity.json"' in command
    assert '"$RUNTIME_DIR/parallel-work-qa-case-receipts.json"' in command
    assert '"$RUNTIME_DIR/parallel-work-local-qa-request.json"' in command
    assert '"$RUNTIME_DIR/local-qa/active.json"' in command
    assert '"$APP_SUPPORT_DIR/qa/evidence"' in command
    assert '"$(stack_owner_state_file)"' in command


def test_public_cli_does_not_accept_caller_controlled_candidate_paths() -> None:
    source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    command = source.rsplit("  qa-evidence)", 1)[1].split("  qa-control)", 1)[0]
    assert "qa-evidence accepts only record --manifest <path>" in command
    assert '"$@"' not in command
    assert '--artifact-identity "$RUNTIME_DIR/parallel-work-artifact-identity.json"' in command
    assert '--receipts "$RUNTIME_DIR/parallel-work-qa-case-receipts.json"' in command
    assert '--local-qa-state "$RUNTIME_DIR/local-qa/active.json"' in command
    assert '--runtime-owner-state "$(stack_owner_state_file)"' in command
