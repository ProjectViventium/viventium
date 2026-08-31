from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = ROOT / "qa/emotional-cortex/scripts/run_emo_uc_048.py"
NOW = datetime(2026, 8, 25, 12, 30, tzinfo=timezone.utc)


def load_runner():
    spec = importlib.util.spec_from_file_location(
        "emo048_focused_semantic_runner", RUNNER_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def receipt_digest(record: dict[str, object]) -> str:
    unsigned = {
        "messageId": record["messageId"],
        "presentationRef": record["presentationRef"],
        "revision": record["messageRevision"],
        "surface": record["surface"],
        "claimToken": record["presentationClaimToken"],
        "claimGeneration": record["claimGeneration"],
        "graphResultHash": record["graphResultHash"],
        "presentationLeaseToken": record["presentationLeaseToken"],
    }
    return digest(json.dumps(unsigned, separators=(",", ":"), ensure_ascii=False))


@pytest.fixture
def delivery_bundle() -> dict[str, object]:
    owner_id = "1" * 24
    conversation_id = "emo_uc_048_conversation_" + "2" * 32
    parent_id = "emo_uc_048_parent_" + "2" * 32
    cortex_id = "emotional-resonance-cortex"
    insight = "An exact, useful insight — café."
    insight_hash = digest(insight)
    identity_hash = digest(f"{owner_id}\0{parent_id}\0{cortex_id}\0{insight_hash}")
    delivery_id = "cidl_" + identity_hash[:24]
    message_id = "emo048_followup_" + "4" * 24
    completion = {
        "caseId": "EMO-UC-048",
        "completedAt": "2026-08-25T12:10:20.000+00:00",
        "completionId": "emo048_completion_" + "5" * 24,
        "conversationId": conversation_id,
        "cortexId": cortex_id,
        "cortexName": "Emotional Resonance",
        "insight": insight,
        "messageRevision": 1,
        "ownerId": owner_id,
        "parentMessageId": parent_id,
        "persistence": {
            "deliveryPending": True,
            "durableAcceptance": "outbox",
            "graphResultHashes": [insight_hash],
            "outboxErrorCode": "cortex_insight_delivery_ledger_write_failed",
            "outboxPending": True,
        },
        "streamId": "emo048_stream_1",
        "surface": "telegram",
    }
    presentations: list[dict[str, object]] = []
    for surface, generation, target in (
        ("web", 2, "durable_replay_store"),
        ("telegram", 3, "promoted_parent_acknowledgement"),
    ):
        record: dict[str, object] = {
            "claimGeneration": generation,
            "graphResultHash": insight_hash,
            "messageId": message_id,
            "messageRevision": 1,
            "presentationClaimToken": f"claim-generation-{generation}",
            "presentationGeneration": generation,
            "presentationLeaseToken": f"lease-generation-{generation}",
            "presentationRef": f"{surface}:{message_id}:1",
            "surface": surface,
            "target": target,
        }
        record["receiptHash"] = receipt_digest(record)
        presentations.append(record)

    delivery = {
        "attemptNumber": 3,
        "claimGeneration": 3,
        "conversationId": conversation_id,
        "cortexId": cortex_id,
        "deliveryId": delivery_id,
        "deliveryKey": "cortex_insight:" + identity_hash,
        "graphResultHash": insight_hash,
        "insight": insight,
        "insightHash": insight_hash,
        "messageRevision": 1,
        "parentMessageId": parent_id,
        "persistedMessageId": message_id,
        "persistenceStatus": "persisted",
        "presentationReceiptHashes": [item["receiptHash"] for item in presentations],
        "presentedSurfaces": ["web", "telegram"],
        "requiredSurfaces": ["web", "telegram"],
        "status": "sent",
        "streamId": "emo048_stream_1",
        "surface": "telegram",
        "userId": owner_id,
    }
    observations = [
        {
            "count": 1,
            "deliveryId": delivery_id,
            "exactInsight": insight,
            "graphResultHash": insight_hash,
            "messageId": message_id,
            "messageRevision": 1,
            "phase": phase,
            "presentationGeneration": 2 if surface == "web" else 3,
            "screenshotEvidenceId": f"{surface}-{phase}",
            "surface": surface,
        }
        for phase in ("settled", "replayed")
        for surface in ("web", "telegram")
    ]
    return {
        "completion": completion,
        "delivery": delivery,
        "presentations": presentations,
        "observations": observations,
    }


def test_exact_completed_insight_delivery_requires_both_linked_surfaces(
    delivery_bundle: dict[str, object],
) -> None:
    result = load_runner().verify_delivery_evidence(**delivery_bundle)

    assert result == {
        "deliveryId": delivery_bundle["delivery"]["deliveryId"],
        "graphResultHash": delivery_bundle["delivery"]["graphResultHash"],
        "surfaces": ["web", "telegram"],
    }


@pytest.mark.parametrize(
    ("section", "field", "replacement"),
    [
        ("completion", "cortexId", "another-cortex"),
        ("delivery", "userId", "9" * 24),
        ("delivery", "conversationId", "different-conversation"),
        ("delivery", "insight", "A different completed insight."),
        ("delivery", "graphResultHash", "0" * 64),
        ("delivery", "deliveryKey", "cortex_insight:" + "0" * 64),
        ("delivery", "surface", "web"),
        ("delivery", "messageRevision", 2),
        ("delivery", "messageRevision", True),
    ],
)
def test_source_owner_surface_revision_and_insight_are_exactly_bound(
    delivery_bundle: dict[str, object],
    section: str,
    field: str,
    replacement: object,
) -> None:
    delivery_bundle[section][field] = replacement

    with pytest.raises(ValueError, match="insight-identity-invalid"):
        load_runner().verify_delivery_evidence(**delivery_bundle)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda bundle: bundle["presentations"].pop(),
        lambda bundle: bundle["presentations"][1].__setitem__("surface", "web"),
        lambda bundle: bundle["presentations"][1].__setitem__("messageRevision", 0),
        lambda bundle: bundle["presentations"][1].__setitem__("messageRevision", True),
        lambda bundle: bundle["presentations"][1].__setitem__(
            "presentationGeneration", 2
        ),
        lambda bundle: bundle["presentations"][1].__setitem__(
            "presentationLeaseToken", "forged-lease"
        ),
        lambda bundle: bundle["delivery"].__setitem__(
            "presentationReceiptHashes", ["0" * 64, "1" * 64]
        ),
    ],
)
def test_missing_forged_or_stale_presentation_cannot_pass(
    delivery_bundle: dict[str, object], mutate
) -> None:
    mutate(delivery_bundle)

    with pytest.raises(ValueError, match="presentation-records-invalid"):
        load_runner().verify_delivery_evidence(**delivery_bundle)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda bundle: bundle["observations"].pop(),
        lambda bundle: bundle["observations"][0].__setitem__("count", 0),
        lambda bundle: bundle["observations"][3].__setitem__("count", 2),
        lambda bundle: bundle["observations"][3].__setitem__("messageRevision", 0),
        lambda bundle: bundle["observations"][3].__setitem__("messageRevision", True),
        lambda bundle: bundle["observations"][3].__setitem__(
            "exactInsight", "Different visible insight."
        ),
    ],
)
def test_replay_must_show_the_exact_insight_once_on_each_surface(
    delivery_bundle: dict[str, object], mutate
) -> None:
    mutate(delivery_bundle)

    with pytest.raises(ValueError, match="visibility-invalid"):
        load_runner().verify_delivery_evidence(**delivery_bundle)


def test_capture_refuses_a_self_declared_pass(tmp_path: Path) -> None:
    root = tmp_path / "evidence"
    root.mkdir(mode=0o700)
    capture_path = root / "capture.json"
    capture_path.write_text(
        json.dumps(
            {
                "capturedAt": NOW.isoformat(),
                "caseId": "EMO-UC-048",
                "contractVersion": 1,
                "evidence": [],
                "fixtureRef": "emo048_fixture_" + "1" * 24,
                "status": "PASS",
            }
        ),
        encoding="utf-8",
    )
    capture_path.chmod(0o600)
    receipt_path = root / "receipt.json"

    result = load_runner().verify_capture(
        capture_path=capture_path,
        evidence_root=root,
        session_state={},
        live_status={},
        live_controls={},
        receipt_path=receipt_path,
        now=NOW,
    )

    assert result["status"] == "BLOCKED"
    assert result["failureCodes"] == ["capture-contract-invalid"]
    assert not receipt_path.exists()


@pytest.mark.parametrize(
    ("candidate_digest", "artifact_digest", "owner_proven"),
    [
        ("8" * 64, "9" * 64, False),
        ("invalid-candidate", "9" * 64, True),
        ("8" * 64, "invalid-artifact", True),
    ],
)
def test_registered_adapter_requires_a_valid_installed_candidate_and_owner(
    tmp_path: Path,
    candidate_digest: str,
    artifact_digest: str,
    owner_proven: bool,
) -> None:
    with pytest.raises(ValueError, match="installed candidate binding is invalid"):
        load_runner().assess_manifest(
            {},
            evidence_root=tmp_path,
            expected_candidate_digest=candidate_digest,
            expected_artifact_digest=artifact_digest,
            installed_owner_proven=owner_proven,
            now=NOW,
        )


def test_receipt_refuses_a_caller_invented_pass() -> None:
    forged = {
        "caseId": "EMO-UC-048",
        "contractVersion": 1,
        "evidence": [],
        "runAt": NOW.isoformat(),
        "status": "PASS",
        "surface": "telegram",
    }

    with pytest.raises(ValueError, match="derived PASS is invalid"):
        load_runner().receipt_manifest(result=copy.deepcopy(forged))


def test_receipt_refuses_a_forged_pass_with_stolen_marker_and_recomputed_digest() -> None:
    runner = load_runner()
    forged = {
        "_derivedPass": runner._DERIVED_PASS,
        "_receiptEvidence": [
            {
                "kind": kind,
                "path": f"proof/{evidence_id}.json",
                "sha256": digest(evidence_id),
            }
            for evidence_id, kind in runner.REQUIRED_EVIDENCE.items()
        ],
        "artifactDigest": "9" * 64,
        "candidateDigest": "8" * 64,
        "caseId": "EMO-UC-048",
        "checks": [
            {"id": check, "status": "PASS"} for check in runner.REQUIRED_CHECKS
        ],
        "contractVersion": 1,
        "failureCodes": [],
        "runAt": NOW.isoformat(),
        "status": "PASS",
        "surface": "telegram",
    }
    forged["_derivationDigest"] = runner._derived_result_digest(forged)

    with pytest.raises(ValueError, match="derived PASS is invalid"):
        runner.receipt_manifest(result=forged)


@pytest.mark.parametrize(
    ("candidate_digest", "artifact_digest"),
    [
        ("8" * 64, "b" * 64),
        ("a" * 64, "9" * 64),
    ],
)
def test_registered_adapter_rejects_a_different_installed_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    candidate_digest: str,
    artifact_digest: str,
) -> None:
    runner = load_runner()
    session = runner._BoundSession({})
    session.candidate_digest = "a" * 64
    session.artifact_digest = "b" * 64
    monkeypatch.setattr(runner, "probe_live_authority", lambda: (session, {}, {}))

    with pytest.raises(ValueError, match="installed candidate binding is invalid"):
        runner.assess_manifest(
            {},
            evidence_root=tmp_path,
            expected_candidate_digest=candidate_digest,
            expected_artifact_digest=artifact_digest,
            installed_owner_proven=True,
            now=NOW,
        )


def test_private_evidence_refuses_a_symlinked_parent(tmp_path: Path) -> None:
    root = tmp_path / "evidence"
    root.mkdir(mode=0o700)
    actual = root / "actual"
    actual.mkdir(mode=0o700)
    evidence = actual / "record.json"
    evidence.write_text("{}", encoding="utf-8")
    evidence.chmod(0o600)
    (root / "alias").symlink_to(actual, target_is_directory=True)

    with pytest.raises(ValueError, match="private-evidence-invalid"):
        load_runner()._read_private_file(
            Path("alias/record.json"),
            root=root,
            max_bytes=1024,
        )


def test_private_evidence_refuses_duplicate_json_keys() -> None:
    with pytest.raises(ValueError, match="invalid-json-evidence"):
        load_runner()._strict_json(b'{"owner":"first","owner":"second"}')


def test_private_evidence_refuses_a_directory_inside_the_public_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = load_runner()
    public_root = tmp_path / "public-checkout"
    evidence_root = public_root / "private-looking-evidence"
    evidence_root.mkdir(mode=0o700, parents=True)
    monkeypatch.setattr(
        runner,
        "__file__",
        str(
            public_root
            / "qa"
            / "emotional-cortex"
            / "scripts"
            / "run_emo_uc_048.py"
        ),
    )

    with pytest.raises(ValueError, match="private-evidence-invalid"):
        runner._private_directory(evidence_root)
