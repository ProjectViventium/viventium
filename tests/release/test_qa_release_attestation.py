from __future__ import annotations

import base64
import copy
import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "viventium" / "qa_release_attestation.py"
SSH_KEYGEN = "/usr/bin/ssh-keygen"
CANDIDATE_DIGEST = "a" * 64
ARTIFACT_DIGEST = "b" * 64
OWNER_BINDING = "c" * 64
EVIDENCE_DIGEST = "d" * 64
VERIFIER_MANIFEST = "e" * 64
SESSION_REF = "qa_" + "1" * 24
NOW = datetime(2026, 8, 25, 16, 30, tzinfo=timezone.utc)


def load_module():
    spec = importlib.util.spec_from_file_location("qa_release_attestation_test", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def canonical(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    ).encode("utf-8")


def public_key(key_path: Path) -> str:
    return " ".join(Path(f"{key_path}.pub").read_text(encoding="utf-8").split()[:2])


def key_fingerprint(key_path: Path) -> str:
    encoded = public_key(key_path).split()[1]
    return "SHA256:" + base64.b64encode(
        hashlib.sha256(base64.b64decode(encoded, validate=True)).digest()
    ).decode("ascii").rstrip("=")


@pytest.fixture(scope="session")
def ssh_keys(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    key_directory = tmp_path_factory.mktemp("viventium-release-attestation-test-keys")
    keys: dict[str, Path] = {}
    for name in ("publisher", "observer", "core", "telegram", "attacker"):
        path = key_directory / name
        subprocess.run(
            [
                SSH_KEYGEN,
                "-q",
                "-t",
                "ed25519",
                "-N",
                "",
                "-C",
                f"{name}@qa.example.test",
                "-f",
                str(path),
            ],
            check=True,
            capture_output=True,
        )
        keys[name] = path
    return keys


class FixtureSigner:
    """An isolated test-only SSH signer; production receives an external signer."""

    def __init__(self, key_path: Path) -> None:
        self.key_path = key_path

    def sign(self, payload: bytes, namespace: str) -> str:
        result = subprocess.run(
            [SSH_KEYGEN, "-Y", "sign", "-f", str(self.key_path), "-n", namespace],
            input=payload,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return result.stdout.decode("ascii")


@dataclass
class FixtureWitness:
    """Stand-in for a protected external, compare-and-swap ledger witness."""

    heads: dict[str, object] = field(default_factory=dict)

    def current(self, scope: str) -> object | None:
        return self.heads.get(scope)

    def advance(self, scope: str, *, expected: object | None, head: object) -> bool:
        if self.heads.get(scope) != expected:
            return False
        self.heads[scope] = head
        return True


@dataclass
class AttestationFixture:
    module: Any
    root: Path
    policy_path: Path
    allowed_signers: Path
    policy_digest: str
    policy: Any
    ledger_path: Path
    witness: FixtureWitness
    signers: dict[str, FixtureSigner]


@pytest.fixture
def authority(tmp_path: Path, ssh_keys: dict[str, Path]) -> AttestationFixture:
    module = load_module()
    root = tmp_path / "installed-candidate"
    policy_path = root / "scripts" / "viventium" / "qa_release_attestation_policy.json"
    allowed_signers = root / "trust" / "qa-release.allowed_signers"
    policy_path.parent.mkdir(parents=True)
    allowed_signers.parent.mkdir(parents=True)

    identities = {
        "publisher": "publisher@qa.example.test",
        "observer": "observer@qa.example.test",
        "core": "core@qa.example.test",
        "telegram": "telegram@qa.example.test",
    }
    allowed_signers.write_text(
        "".join(
            f"{identity} {public_key(ssh_keys[name])}\n"
            for name, identity in identities.items()
        ),
        encoding="utf-8",
    )
    policy_data = {
        "contractVersion": 1,
        "allowedSigners": {
            "path": "trust/qa-release.allowed_signers",
            "sha256": hashlib.sha256(allowed_signers.read_bytes()).hexdigest(),
        },
        "publisher": {
            "identity": identities["publisher"],
            "fingerprint": key_fingerprint(ssh_keys["publisher"]),
        },
        "producers": {
            "telegram-observer": {
                "identity": identities["observer"],
                "fingerprint": key_fingerprint(ssh_keys["observer"]),
                "role": "observation",
            },
            "librechat-core": {
                "identity": identities["core"],
                "fingerprint": key_fingerprint(ssh_keys["core"]),
                "role": "service",
                "serviceId": "librechat-core",
            },
            "telegram-bot": {
                "identity": identities["telegram"],
                "fingerprint": key_fingerprint(ssh_keys["telegram"]),
                "role": "service",
                "serviceId": "telegram-bot",
            },
        },
        "cases": {
            "TR-026": {
                "surface": "telegram",
                "verifierId": "tr026-semantic-v1",
                "producerIds": ["telegram-observer"],
                "serviceProducerIds": ["librechat-core", "telegram-bot"],
            },
            "PWK-UC-019": {
                "surface": "telegram",
                "verifierId": "pwk-installed-journey-v1",
                "producerIds": ["telegram-observer"],
                "serviceProducerIds": [],
            },
        },
        "maximumReceiptAgeSeconds": 86_400,
        "maximumFutureSkewSeconds": 60,
    }
    policy_path.write_bytes(canonical(policy_data))
    policy_digest = hashlib.sha256(policy_path.read_bytes()).hexdigest()
    policy = module.load_trust_policy(
        root,
        expected_policy_sha256=policy_digest,
        expected_candidate_digest=CANDIDATE_DIGEST,
    )
    runtime = tmp_path / "private-runtime"
    runtime.mkdir(mode=0o700)
    return AttestationFixture(
        module=module,
        root=root,
        policy_path=policy_path,
        allowed_signers=allowed_signers,
        policy_digest=policy_digest,
        policy=policy,
        ledger_path=runtime / "qa-release-attestation-ledger.json",
        witness=FixtureWitness(),
        signers={name: FixtureSigner(path) for name, path in ssh_keys.items()},
    )


def service_attestation(
    fixture: AttestationFixture,
    producer_id: str,
    *,
    now: datetime = NOW,
) -> dict[str, object]:
    signer_name = "core" if producer_id == "librechat-core" else "telegram"
    process_digest = "4" * 64 if signer_name == "core" else "5" * 64
    observation = {
        "caseId": "TR-026",
        "surface": "telegram",
        "candidateDigest": CANDIDATE_DIGEST,
        "artifactDigest": ARTIFACT_DIGEST,
        "ownerBindingSha256": OWNER_BINDING,
        "serviceId": producer_id,
        "sessionRef": SESSION_REF,
        "acknowledgedAt": now.isoformat(),
        "acknowledgementDigest": "sha256:" + hashlib.sha256(
            producer_id.encode("utf-8")
        ).hexdigest(),
        "processIdentityDigest": process_digest,
    }
    return fixture.module.sign_service_acknowledgement(
        observation,
        producer_id=producer_id,
        policy=fixture.policy,
        signer=fixture.signers[signer_name],
        now=now,
    )


def base_receipt(
    fixture: AttestationFixture,
    *,
    case_id: str = "TR-026",
    nonce: str = "0" * 32,
    now: datetime = NOW,
    services: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    verifier = (
        "tr026-semantic-v1" if case_id == "TR-026" else "pwk-installed-journey-v1"
    )
    receipt: dict[str, object] = {
        "artifactDigest": ARTIFACT_DIGEST,
        "candidateDigest": CANDIDATE_DIGEST,
        "caseId": case_id,
        "evidenceDigest": EVIDENCE_DIGEST,
        "runAt": now.isoformat(),
        "status": "PASS",
        "surface": "telegram",
        "ownerBindingSha256": OWNER_BINDING,
        "receiptNonce": nonce,
        "verifierId": verifier,
        "verifierManifestSha256": VERIFIER_MANIFEST,
    }
    if case_id == "TR-026":
        assert services is not None
        receipt["serviceAckDigest"] = fixture.module.service_acknowledgement_digest(
            services
        )
        receipt["serviceAckSessionRef"] = SESSION_REF
    return receipt


def producer_attestation(
    fixture: AttestationFixture,
    receipt: dict[str, object],
    *,
    signer: FixtureSigner | None = None,
    now: datetime = NOW,
) -> dict[str, object]:
    observation = {
        "caseId": receipt["caseId"],
        "surface": receipt["surface"],
        "candidateDigest": receipt["candidateDigest"],
        "artifactDigest": receipt["artifactDigest"],
        "ownerBindingSha256": receipt["ownerBindingSha256"],
        "evidenceDigest": receipt["evidenceDigest"],
        "receiptNonce": receipt["receiptNonce"],
        "verifierId": receipt["verifierId"],
        "verifierManifestSha256": receipt["verifierManifestSha256"],
        "observedAt": now.isoformat(),
        "observationNonce": "9" * 32,
        "serviceAckDigest": receipt.get("serviceAckDigest", ""),
        "serviceAckSessionRef": receipt.get("serviceAckSessionRef", ""),
    }
    return fixture.module.sign_producer_observation(
        observation,
        producer_id="telegram-observer",
        policy=fixture.policy,
        signer=signer or fixture.signers["observer"],
        now=now,
    )


def issue(
    fixture: AttestationFixture,
    *,
    case_id: str = "TR-026",
    nonce: str = "0" * 32,
    now: datetime = NOW,
    receipt_updates: dict[str, object] | None = None,
    services: list[dict[str, object]] | None = None,
    producers: list[dict[str, object]] | None = None,
    signer: FixtureSigner | None = None,
    witness: FixtureWitness | None = None,
) -> dict[str, object]:
    actual_services = services
    if actual_services is None:
        actual_services = (
            [
                service_attestation(fixture, "librechat-core", now=now),
                service_attestation(fixture, "telegram-bot", now=now),
            ]
            if case_id == "TR-026"
            else []
        )
    receipt = base_receipt(
        fixture, case_id=case_id, nonce=nonce, now=now, services=actual_services
    )
    if receipt_updates:
        receipt.update(receipt_updates)
    actual_producers = producers
    if actual_producers is None:
        actual_producers = [producer_attestation(fixture, receipt, now=now)]
    return fixture.module.issue_release_receipt(
        receipt,
        producer_attestations=actual_producers,
        service_acknowledgements=actual_services,
        policy=fixture.policy,
        signer=signer or fixture.signers["publisher"],
        ledger_path=fixture.ledger_path,
        ledger_witness=witness or fixture.witness,
        now=now,
    )


def verify(
    fixture: AttestationFixture,
    receipt: dict[str, object],
    **overrides: object,
):
    service_proofs = receipt.get("serviceAcknowledgements", [])
    kwargs = {
        "policy": fixture.policy,
        "ledger_path": fixture.ledger_path,
        "ledger_witness": fixture.witness,
        "expected_case_id": "TR-026",
        "expected_surface": "telegram",
        "expected_candidate_digest": CANDIDATE_DIGEST,
        "expected_artifact_digest": ARTIFACT_DIGEST,
        "expected_owner_binding": OWNER_BINDING,
        "expected_evidence_digest": EVIDENCE_DIGEST,
        "expected_verifier_id": "tr026-semantic-v1",
        "expected_verifier_manifest_sha256": VERIFIER_MANIFEST,
        "expected_service_ack_digest": (
            fixture.module.service_acknowledgement_digest(service_proofs)
            if service_proofs
            else None
        ),
        "expected_service_ack_session_ref": SESSION_REF if service_proofs else None,
        "now": NOW,
    }
    kwargs.update(overrides)
    return fixture.module.verify_release_receipt(receipt, **kwargs)


def test_missing_publisher_pinned_trust_policy_fails_closed(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "installed"
    root.mkdir()

    with pytest.raises(module.AttestationError, match="trusted.*policy"):
        module.load_trust_policy(
            root,
            expected_policy_sha256="a" * 64,
            expected_candidate_digest=CANDIDATE_DIGEST,
        )


def test_unpinned_policy_cannot_establish_its_own_trust(
    authority: AttestationFixture,
) -> None:
    with pytest.raises(authority.module.AttestationError, match="pinned.*policy"):
        authority.module.load_trust_policy(
            authority.root,
            expected_policy_sha256=None,
            expected_candidate_digest=CANDIDATE_DIGEST,
        )


def test_issue_and_verify_publisher_producer_and_service_signed_receipt(
    authority: AttestationFixture,
) -> None:
    receipt = issue(authority)
    verified = verify(authority, receipt)

    assert verified.case_id == "TR-026"
    assert verified.sequence == 1
    assert verified.producer_ids == ("telegram-observer",)
    assert verified.service_ids == ("librechat-core", "telegram-bot")
    assert "BEGIN SSH SIGNATURE" in str(receipt["publisherAttestation"])
    assert stat.S_IMODE(authority.ledger_path.stat().st_mode) == 0o600


def test_receipt_without_external_monotonic_witness_fails_closed(
    authority: AttestationFixture,
) -> None:
    receipt = issue(authority)

    with pytest.raises(authority.module.AttestationError, match="monotonic.*witness"):
        verify(authority, receipt, ledger_witness=None)


def test_receipt_without_external_publisher_signer_fails_closed(
    authority: AttestationFixture,
) -> None:
    receipt = base_receipt(authority, case_id="PWK-UC-019", services=[])
    producer = producer_attestation(authority, receipt)

    with pytest.raises(authority.module.AttestationError, match="external.*signer"):
        authority.module.issue_release_receipt(
            receipt,
            producer_attestations=[producer],
            service_acknowledgements=[],
            policy=authority.policy,
            signer=None,
            ledger_path=authority.ledger_path,
            ledger_witness=authority.witness,
            now=NOW,
        )


def test_owner_readable_hmac_cannot_impersonate_publisher_signature(
    authority: AttestationFixture,
) -> None:
    receipt = issue(authority)
    receipt["publisherAttestation"] = "hmac-sha256:" + "f" * 64

    with pytest.raises(authority.module.AttestationError, match="signature"):
        verify(authority, receipt)


def test_candidate_pinned_allowed_signers_reject_runtime_key_substitution(
    authority: AttestationFixture, ssh_keys: dict[str, Path]
) -> None:
    receipt = issue(authority)
    authority.allowed_signers.write_text(
        f"publisher@qa.example.test {public_key(ssh_keys['attacker'])}\n",
        encoding="utf-8",
    )

    with pytest.raises(authority.module.AttestationError, match="trusted.*signer"):
        verify(authority, receipt)


def test_same_uid_cannot_swap_trust_roots_after_their_hash_is_checked(
    authority: AttestationFixture,
    ssh_keys: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = canonical({"purpose": "attacker-forged-publisher-receipt"})
    forged = authority.signers["attacker"].sign(
        payload, authority.module.RECEIPT_NAMESPACE
    )
    trusted_bytes = authority.allowed_signers.read_bytes()
    untrusted_bytes = (
        f"publisher@qa.example.test {public_key(ssh_keys['attacker'])}\n"
    ).encode("ascii")
    real_run = subprocess.run

    def swap_roots_during_verification(*args: object, **kwargs: object):
        authority.allowed_signers.write_bytes(untrusted_bytes)
        try:
            return real_run(*args, **kwargs)
        finally:
            authority.allowed_signers.write_bytes(trusted_bytes)

    monkeypatch.setattr(authority.module.subprocess, "run", swap_roots_during_verification)

    with pytest.raises(authority.module.AttestationError, match="publisher.*signature"):
        authority.module._verify_signature(
            payload,
            forged,
            policy=authority.policy,
            identity=authority.policy.publisher_identity,
            namespace=authority.module.RECEIPT_NAMESPACE,
            label="publisher",
        )


def test_candidate_pinned_policy_rejects_policy_key_substitution(
    authority: AttestationFixture, ssh_keys: dict[str, Path]
) -> None:
    payload = json.loads(authority.policy_path.read_text(encoding="utf-8"))
    payload["publisher"]["fingerprint"] = key_fingerprint(ssh_keys["attacker"])
    authority.policy_path.write_bytes(canonical(payload))

    with pytest.raises(authority.module.AttestationError, match="policy.*digest"):
        authority.module.load_trust_policy(
            authority.root,
            expected_policy_sha256=authority.policy_digest,
            expected_candidate_digest=CANDIDATE_DIGEST,
        )


def test_wrong_signer_identity_cannot_issue_publisher_receipt(
    authority: AttestationFixture,
) -> None:
    with pytest.raises(authority.module.AttestationError, match="publisher.*signature"):
        issue(authority, case_id="PWK-UC-019", signer=authority.signers["observer"])


def test_fabricated_self_declared_producer_evidence_is_rejected(
    authority: AttestationFixture,
) -> None:
    receipt = base_receipt(authority, case_id="PWK-UC-019", services=[])
    fabricated = producer_attestation(authority, receipt)
    fabricated["signature"] = "hmac-sha256:" + "f" * 64

    with pytest.raises(authority.module.AttestationError, match="producer.*signature"):
        issue(authority, case_id="PWK-UC-019", producers=[fabricated])


def test_attacker_key_cannot_impersonate_real_installed_producer(
    authority: AttestationFixture,
) -> None:
    receipt = base_receipt(authority, case_id="PWK-UC-019", services=[])

    with pytest.raises(authority.module.AttestationError, match="producer.*signature"):
        producer_attestation(authority, receipt, signer=authority.signers["attacker"])


def test_missing_real_installed_producer_cannot_create_release_receipt(
    authority: AttestationFixture,
) -> None:
    with pytest.raises(authority.module.AttestationError, match="producer"):
        issue(authority, case_id="PWK-UC-019", producers=[])


def test_producer_observation_cannot_be_replayed_for_another_receipt_nonce(
    authority: AttestationFixture,
) -> None:
    original = base_receipt(
        authority, case_id="PWK-UC-019", nonce="1" * 32, services=[]
    )
    producer = producer_attestation(authority, original)

    with pytest.raises(authority.module.AttestationError, match="receiptNonce|nonce"):
        issue(
            authority,
            case_id="PWK-UC-019",
            nonce="2" * 32,
            producers=[producer],
        )


@pytest.mark.parametrize(
    ("field", "value", "expected_error"),
    (
        ("caseId", "PWK-UC-019", "case"),
        ("surface", "voice", "surface"),
        ("candidateDigest", "1" * 64, "candidate"),
        ("artifactDigest", "2" * 64, "artifact"),
        ("ownerBindingSha256", "3" * 64, "owner"),
        ("evidenceDigest", "4" * 64, "evidence"),
        ("verifierId", "wrong-verifier-v1", "verifier"),
        ("verifierManifestSha256", "5" * 64, "verifier"),
    ),
)
def test_signed_receipt_rejects_every_tampered_security_binding(
    authority: AttestationFixture,
    field: str,
    value: str,
    expected_error: str,
) -> None:
    receipt = issue(authority)
    receipt[field] = value

    with pytest.raises(authority.module.AttestationError, match=expected_error):
        verify(authority, receipt)


@pytest.mark.parametrize(
    ("option", "value", "expected_error"),
    (
        ("expected_case_id", "PWK-UC-019", "case"),
        ("expected_surface", "voice", "surface"),
        ("expected_candidate_digest", "1" * 64, "candidate"),
        ("expected_artifact_digest", "2" * 64, "artifact"),
        ("expected_owner_binding", "3" * 64, "owner"),
        ("expected_verifier_id", "another-verifier-v1", "verifier"),
        ("expected_verifier_manifest_sha256", "4" * 64, "verifier"),
        ("expected_service_ack_digest", "sha256:" + "5" * 64, "service"),
        ("expected_service_ack_session_ref", "qa_" + "6" * 24, "service"),
    ),
)
def test_signed_receipt_cannot_move_to_a_different_expected_context(
    authority: AttestationFixture,
    option: str,
    value: str,
    expected_error: str,
) -> None:
    receipt = issue(authority)

    with pytest.raises(authority.module.AttestationError, match=expected_error):
        verify(authority, receipt, **{option: value})


def test_copied_core_acknowledgement_cannot_impersonate_telegram(
    authority: AttestationFixture,
) -> None:
    core = service_attestation(authority, "librechat-core")
    copied = copy.deepcopy(core)
    copied["producerId"] = "telegram-bot"
    copied["serviceId"] = "telegram-bot"
    copied["signerIdentity"] = "telegram@qa.example.test"

    with pytest.raises(authority.module.AttestationError, match="service.*signature"):
        issue(authority, services=[core, copied])


def test_unsigned_fake_service_acknowledgement_cannot_approve_restart(
    authority: AttestationFixture,
) -> None:
    core = service_attestation(authority, "librechat-core")
    telegram = service_attestation(authority, "telegram-bot")
    telegram["signature"] = "sha256:" + "f" * 64

    with pytest.raises(authority.module.AttestationError, match="service.*signature"):
        issue(authority, services=[core, telegram])


def test_missing_service_attestation_cannot_approve_restart(
    authority: AttestationFixture,
) -> None:
    core = service_attestation(authority, "librechat-core")

    with pytest.raises(authority.module.AttestationError, match="service"):
        issue(authority, services=[core])


def test_service_acknowledgement_from_another_session_is_rejected(
    authority: AttestationFixture,
) -> None:
    receipt = issue(authority)
    receipt["serviceAckSessionRef"] = "qa_" + "2" * 24

    with pytest.raises(authority.module.AttestationError, match="service"):
        verify(authority, receipt)


def test_old_pass_stays_revoked_after_a_newer_failure(
    authority: AttestationFixture,
) -> None:
    receipt = issue(authority)
    authority.module.record_case_outcome(
        case_id="TR-026",
        status="FAIL",
        owner_binding_sha256=OWNER_BINDING,
        artifact_digest=ARTIFACT_DIGEST,
        policy=authority.policy,
        signer=authority.signers["publisher"],
        ledger_path=authority.ledger_path,
        ledger_witness=authority.witness,
        now=NOW + timedelta(seconds=1),
    )

    with pytest.raises(authority.module.AttestationError, match="superseded|revoked"):
        verify(authority, receipt, now=NOW + timedelta(seconds=2))


def test_restoring_old_signed_ledger_cannot_replay_a_revoked_pass(
    authority: AttestationFixture,
) -> None:
    receipt = issue(authority)
    old_ledger = authority.ledger_path.read_bytes()
    authority.module.record_case_outcome(
        case_id="TR-026",
        status="REVOKED",
        owner_binding_sha256=OWNER_BINDING,
        artifact_digest=ARTIFACT_DIGEST,
        policy=authority.policy,
        signer=authority.signers["publisher"],
        ledger_path=authority.ledger_path,
        ledger_witness=authority.witness,
        now=NOW + timedelta(seconds=1),
    )
    authority.ledger_path.write_bytes(old_ledger)
    authority.ledger_path.chmod(0o600)

    with pytest.raises(authority.module.AttestationError, match="rollback|witness"):
        verify(authority, receipt, now=NOW + timedelta(seconds=2))


def test_transient_external_witness_failure_recovers_without_accepting_unconfirmed_receipts(
    authority: AttestationFixture,
) -> None:
    original = issue(authority, nonce="1" * 32)
    advance = authority.witness.advance
    attempts = 0

    def fail_once(scope: str, *, expected: object | None, head: object) -> bool:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ConnectionError("protected external witness is temporarily unavailable")
        return advance(scope, expected=expected, head=head)

    authority.witness.advance = fail_once

    with pytest.raises(authority.module.AttestationError, match="witness.*unavailable"):
        issue(authority, case_id="PWK-UC-019", nonce="2" * 32)

    with pytest.raises(authority.module.AttestationError, match="rollback|witness"):
        verify(authority, original)
    assert attempts == 1

    recovered = issue(authority, case_id="PWK-UC-019", nonce="2" * 32)

    assert recovered["attestationSequence"] == 1
    assert verify(
        authority,
        recovered,
        expected_case_id="PWK-UC-019",
        expected_verifier_id="pwk-installed-journey-v1",
    ).case_id == "PWK-UC-019"
    assert verify(authority, original).case_id == "TR-026"
    ledger = json.loads(authority.ledger_path.read_text(encoding="utf-8"))
    assert len(ledger["entries"]) == 2


def test_first_signed_entry_recovers_after_unconfirmed_external_witness_failure(
    authority: AttestationFixture,
) -> None:
    advance = authority.witness.advance
    first = True

    def reject_once(scope: str, *, expected: object | None, head: object) -> bool:
        nonlocal first
        if first:
            first = False
            return False
        return advance(scope, expected=expected, head=head)

    authority.witness.advance = reject_once

    with pytest.raises(authority.module.AttestationError, match="witness rejected"):
        issue(authority, case_id="PWK-UC-019", nonce="3" * 32)

    recovered = issue(authority, case_id="PWK-UC-019", nonce="3" * 32)

    assert verify(
        authority,
        recovered,
        expected_case_id="PWK-UC-019",
        expected_verifier_id="pwk-installed-journey-v1",
    ).sequence == 1
    assert len(json.loads(authority.ledger_path.read_text())["entries"]) == 1


@pytest.mark.parametrize("failure", ("after_commit", "confirmation"))
def test_committed_external_witness_checkpoint_retries_without_duplicate_receipts(
    authority: AttestationFixture,
    failure: str,
) -> None:
    advance = authority.witness.advance
    current = authority.witness.current
    attempted = False
    confirmation_pending = False

    def uncertain_advance(scope: str, *, expected: object | None, head: object) -> bool:
        nonlocal attempted, confirmation_pending
        accepted = advance(scope, expected=expected, head=head)
        if not attempted:
            attempted = True
            if failure == "after_commit":
                raise ConnectionError("external witness response was interrupted")
            confirmation_pending = True
        return accepted

    def uncertain_current(scope: str) -> object | None:
        nonlocal confirmation_pending
        if confirmation_pending:
            confirmation_pending = False
            raise ConnectionError("external witness confirmation was interrupted")
        return current(scope)

    authority.witness.advance = uncertain_advance
    authority.witness.current = uncertain_current

    with pytest.raises(authority.module.AttestationError, match="witness.*unavailable"):
        issue(authority, case_id="PWK-UC-019", nonce="4" * 32)

    recovered = issue(authority, case_id="PWK-UC-019", nonce="4" * 32)

    assert recovered["attestationSequence"] == 1
    assert len(json.loads(authority.ledger_path.read_text())["entries"]) == 1


def test_interrupted_concurrent_retries_commit_one_authenticated_ledger_entry(
    authority: AttestationFixture,
) -> None:
    original = issue(authority, nonce="5" * 32)
    advance = authority.witness.advance

    def interrupt(_scope: str, *, expected: object | None, head: object) -> bool:
        del expected, head
        raise KeyboardInterrupt("publisher process stopped before witness confirmation")

    authority.witness.advance = interrupt
    with pytest.raises(KeyboardInterrupt):
        issue(authority, case_id="PWK-UC-019", nonce="6" * 32)
    with pytest.raises(authority.module.AttestationError, match="rollback|witness"):
        verify(authority, original)
    authority.witness.advance = advance

    with ThreadPoolExecutor(max_workers=2) as executor:
        retries = [
            executor.submit(issue, authority, case_id="PWK-UC-019", nonce="6" * 32)
            for _index in range(2)
        ]
        receipts = [retry.result(timeout=15) for retry in retries]

    assert receipts[0] == receipts[1]
    assert len(json.loads(authority.ledger_path.read_text())["entries"]) == 2
    assert verify(
        authority,
        receipts[0],
        expected_case_id="PWK-UC-019",
        expected_verifier_id="pwk-installed-journey-v1",
    ).sequence == 1


def test_recovery_never_accepts_a_tampered_unconfirmed_ledger_entry(
    authority: AttestationFixture,
) -> None:
    issue(authority, nonce="7" * 32)
    advance = authority.witness.advance

    def fail(_scope: str, *, expected: object | None, head: object) -> bool:
        del expected, head
        raise ConnectionError("protected witness temporarily unavailable")

    authority.witness.advance = fail
    with pytest.raises(authority.module.AttestationError, match="witness"):
        issue(authority, case_id="PWK-UC-019", nonce="8" * 32)
    authority.witness.advance = advance
    pending = json.loads(authority.ledger_path.read_text(encoding="utf-8"))
    pending["entries"][-1]["signature"] = "hmac-sha256:" + "f" * 64
    authority.ledger_path.write_bytes(canonical(pending))

    with pytest.raises(authority.module.AttestationError, match="ledger.*signature"):
        issue(authority, case_id="PWK-UC-019", nonce="8" * 32)

    scope = authority.module._witness_scope(authority.policy, authority.ledger_path)
    assert authority.witness.current(scope).sequence == 1


def test_recovered_pending_revocation_remains_effective_before_new_signed_work(
    authority: AttestationFixture,
) -> None:
    original = issue(authority, nonce="d" * 32)
    advance = authority.witness.advance
    first = True

    def fail_revocation_once(
        scope: str, *, expected: object | None, head: object
    ) -> bool:
        nonlocal first
        if first:
            first = False
            raise ConnectionError("protected revocation witness temporarily unavailable")
        return advance(scope, expected=expected, head=head)

    authority.witness.advance = fail_revocation_once

    with pytest.raises(authority.module.AttestationError, match="witness"):
        authority.module.record_case_outcome(
            case_id="TR-026",
            status="REVOKED",
            owner_binding_sha256=OWNER_BINDING,
            artifact_digest=ARTIFACT_DIGEST,
            policy=authority.policy,
            signer=authority.signers["publisher"],
            ledger_path=authority.ledger_path,
            ledger_witness=authority.witness,
            now=NOW + timedelta(seconds=1),
        )

    with pytest.raises(authority.module.AttestationError, match="rollback|witness"):
        verify(authority, original, now=NOW + timedelta(seconds=1))

    recovered = issue(
        authority,
        case_id="PWK-UC-019",
        nonce="e" * 32,
        now=NOW + timedelta(seconds=2),
    )

    assert recovered["attestationSequence"] == 1
    with pytest.raises(authority.module.AttestationError, match="superseded|revoked"):
        verify(authority, original, now=NOW + timedelta(seconds=2))


def test_recovery_cannot_move_an_external_witness_backward_to_a_restored_ledger(
    authority: AttestationFixture,
) -> None:
    original = issue(authority, nonce="a" * 32)
    old_ledger = authority.ledger_path.read_bytes()
    authority.module.record_case_outcome(
        case_id="TR-026",
        status="REVOKED",
        owner_binding_sha256=OWNER_BINDING,
        artifact_digest=ARTIFACT_DIGEST,
        policy=authority.policy,
        signer=authority.signers["publisher"],
        ledger_path=authority.ledger_path,
        ledger_witness=authority.witness,
        now=NOW + timedelta(seconds=1),
    )
    authority.ledger_path.write_bytes(old_ledger)

    with pytest.raises(authority.module.AttestationError, match="rollback|witness"):
        issue(
            authority,
            case_id="PWK-UC-019",
            nonce="b" * 32,
            now=NOW + timedelta(seconds=2),
        )
    with pytest.raises(authority.module.AttestationError, match="rollback|witness"):
        verify(authority, original, now=NOW + timedelta(seconds=2))


def test_same_nonce_with_changed_signed_evidence_remains_a_rejected_replay(
    authority: AttestationFixture,
) -> None:
    issue(authority, case_id="PWK-UC-019", nonce="c" * 32)

    with pytest.raises(authority.module.AttestationError, match="nonce.*replay"):
        issue(
            authority,
            case_id="PWK-UC-019",
            nonce="c" * 32,
            receipt_updates={"evidenceDigest": "1" * 64},
        )


def test_revoked_receipt_nonce_cannot_be_reissued_as_an_idempotent_retry(
    authority: AttestationFixture,
) -> None:
    issue(authority, case_id="PWK-UC-019", nonce="f" * 32)
    authority.module.record_case_outcome(
        case_id="PWK-UC-019",
        status="REVOKED",
        owner_binding_sha256=OWNER_BINDING,
        artifact_digest=ARTIFACT_DIGEST,
        policy=authority.policy,
        signer=authority.signers["publisher"],
        ledger_path=authority.ledger_path,
        ledger_witness=authority.witness,
        now=NOW + timedelta(seconds=1),
    )

    with pytest.raises(authority.module.AttestationError, match="nonce.*replay"):
        issue(
            authority,
            case_id="PWK-UC-019",
            nonce="f" * 32,
            now=NOW + timedelta(seconds=2),
        )


def test_receipt_nonce_cannot_be_replayed_for_another_case(
    authority: AttestationFixture,
) -> None:
    issue(authority, nonce="7" * 32)

    with pytest.raises(authority.module.AttestationError, match="nonce.*replay"):
        issue(authority, case_id="PWK-UC-019", nonce="7" * 32)


@pytest.mark.parametrize(
    ("checked_at", "error"),
    (
        (NOW + timedelta(days=1, seconds=1), "stale"),
        (NOW - timedelta(seconds=61), "future"),
    ),
)
def test_stale_and_future_receipts_fail_closed(
    authority: AttestationFixture,
    checked_at: datetime,
    error: str,
) -> None:
    receipt = issue(authority)

    with pytest.raises(authority.module.AttestationError, match=error):
        verify(authority, receipt, now=checked_at)


def test_receipt_signature_cannot_be_reused_as_ledger_signature(
    authority: AttestationFixture,
) -> None:
    receipt = issue(authority)
    payload = json.loads(authority.ledger_path.read_text(encoding="utf-8"))
    payload["entries"][0]["signature"] = receipt["publisherAttestation"]
    authority.ledger_path.write_bytes(canonical(payload))

    with pytest.raises(authority.module.AttestationError, match="ledger.*signature"):
        verify(authority, receipt)


def test_non_private_runtime_directory_cannot_store_release_ledger(
    authority: AttestationFixture,
) -> None:
    authority.ledger_path.parent.chmod(0o755)

    with pytest.raises(authority.module.AttestationError, match="private.*directory"):
        issue(authority, case_id="PWK-UC-019")


def test_symlinked_or_world_readable_ledger_is_rejected(
    authority: AttestationFixture,
    tmp_path: Path,
) -> None:
    target = tmp_path / "attacker-ledger"
    target.write_text("{}", encoding="utf-8")
    authority.ledger_path.symlink_to(target)

    with pytest.raises(authority.module.AttestationError, match="ledger"):
        issue(authority, case_id="PWK-UC-019")


def test_policy_rejects_duplicate_identity_and_shared_signing_keys(
    authority: AttestationFixture,
) -> None:
    payload = json.loads(authority.policy_path.read_text(encoding="utf-8"))
    payload["producers"]["telegram-observer"]["identity"] = payload["publisher"][
        "identity"
    ]
    payload["producers"]["telegram-observer"]["fingerprint"] = payload["publisher"][
        "fingerprint"
    ]
    authority.policy_path.write_bytes(canonical(payload))

    with pytest.raises(authority.module.AttestationError, match="distinct|duplicate"):
        authority.module.load_trust_policy(
            authority.root,
            expected_policy_sha256=hashlib.sha256(
                authority.policy_path.read_bytes()
            ).hexdigest(),
            expected_candidate_digest=CANDIDATE_DIGEST,
        )


def test_trusted_absolute_ssh_verifier_ignores_poisoned_path(
    authority: AttestationFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = issue(authority)
    monkeypatch.setenv("PATH", "/nonexistent/untrusted-bin")

    assert verify(authority, receipt).case_id == "TR-026"
    assert authority.module.SSH_KEYGEN == Path("/usr/bin/ssh-keygen")


def test_signed_ledger_uses_atomic_private_writes_without_temporary_leftovers(
    authority: AttestationFixture,
) -> None:
    issue(authority, case_id="PWK-UC-019")

    assert stat.S_IMODE(authority.ledger_path.stat().st_mode) == 0o600
    assert authority.ledger_path.stat().st_uid == os.getuid()
    assert not list(authority.ledger_path.parent.glob("*.tmp"))


def test_public_verification_metadata_contains_no_private_key_or_local_path(
    authority: AttestationFixture,
) -> None:
    metadata = authority.module.release_attestation_metadata(
        authority.policy, case_id="TR-026"
    )

    assert metadata == {
        "contractVersion": 1,
        "algorithm": "ssh-ed25519",
        "candidateDigest": CANDIDATE_DIGEST,
        "policySha256": authority.policy_digest,
        "allowedSignersSha256": hashlib.sha256(
            authority.allowed_signers.read_bytes()
        ).hexdigest(),
        "publisherIdentity": "publisher@qa.example.test",
        "publisherFingerprint": key_fingerprint(authority.signers["publisher"].key_path),
        "namespaces": {
            "receipt": authority.module.RECEIPT_NAMESPACE,
            "producer": authority.module.PRODUCER_NAMESPACE,
            "service": authority.module.SERVICE_NAMESPACE,
            "ledger": authority.module.LEDGER_NAMESPACE,
        },
        "case": {
            "caseId": "TR-026",
            "surface": "telegram",
            "verifierId": "tr026-semantic-v1",
            "producerIds": ["telegram-observer"],
            "serviceProducerIds": ["librechat-core", "telegram-bot"],
        },
        "requiresExternalPublisherSigner": True,
        "requiresExternalMonotonicWitness": True,
        "requiresProducerAttestation": True,
        "requiresServiceAttestation": True,
    }
    assert str(authority.root) not in json.dumps(metadata)
