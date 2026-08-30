from __future__ import annotations

import base64
import copy
import hashlib
import hmac
import importlib.util
import io
import json
import os
import struct
import subprocess
import sys
import wave
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "qa/parallel-orchestrator/scripts/catalog_case_semantic_verifier.py"
PARALLEL_CASE_IDS = tuple(
    [f"PWK-{number:03d}" for number in range(1, 50)]
    + [f"PWK-UC-{number:03d}" for number in range(1, 14)]
)
RELEASE_CASE_IDS = tuple(
    [f"REL-{number:03d}" for number in range(1, 7)]
    + [f"REL-UC-{number:03d}" for number in range(1, 4)]
)
NOW = datetime(2026, 8, 25, 16, 0, tzinfo=timezone.utc)


def _digest(value: object) -> str:
    if isinstance(value, bytes):
        raw = value
    elif isinstance(value, str):
        raw = value.encode("utf-8")
    else:
        raw = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _stamp(seconds: float = 0) -> str:
    return (NOW + timedelta(seconds=seconds)).isoformat(timespec="milliseconds")


def _png(variant: int) -> bytes:
    width, height = 384, 240
    rows = bytearray()
    for row in range(height):
        rows.append(0)
        rows.extend((column * 5 + row * 3 + variant * 17) % 256 for column in range(width))

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(rows)))
        + chunk(b"IEND", b"")
    )


def _audio() -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(8_000)
        stream.writeframes(
            b"".join(
                struct.pack("<h", 9_000 if index % 2 else -9_000)
                for index in range(8_000)
            )
        )
    return output.getvalue()


def _private(path: Path, value: object) -> str:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    raw = (
        value
        if isinstance(value, bytes)
        else json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
    )
    path.write_bytes(raw)
    path.chmod(0o600)
    return _digest(raw)


def load_catalog_module():
    spec = importlib.util.spec_from_file_location(
        "viventium_installed_catalog_semantic_verifier", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _proof(
    payload: dict[str, object],
    key: bytes,
    *,
    namespace: str = "viventium-qa-catalog-source-v1",
) -> str:
    """Cheap isolated-test stand-in; production verifies protected Ed25519 only."""

    encoded = (
        namespace
        + "\0"
        + json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    ).encode("utf-8")
    digest = base64.b64encode(hmac.new(key, encoded, hashlib.sha256).digest()).decode(
        "ascii"
    )
    return (
        "-----BEGIN SSH SIGNATURE-----\n"
        + digest
        + "\n-----END SSH SIGNATURE-----\n"
    )


@pytest.fixture(scope="session")
def catalog_ssh_keys(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    root = tmp_path_factory.mktemp("viventium-catalog-test-keys")
    result: dict[str, Path] = {}
    for role in ("publisher", "observer", "attacker"):
        path = root / role
        subprocess.run(
            [
                "/usr/bin/ssh-keygen",
                "-q",
                "-t",
                "ed25519",
                "-N",
                "",
                "-C",
                f"{role}@qa.example.test",
                "-f",
                str(path),
            ],
            check=True,
            capture_output=True,
        )
        result[role] = path
    return result


def _catalog_policy(
    *,
    bundle: dict[str, Any],
    root: Path,
    keys: dict[str, Path],
) -> tuple[object, object]:
    module = bundle["module"]._load_module(
        ROOT / "scripts/viventium/qa_release_attestation.py",
        "viventium_catalog_test_publisher_attestation",
    )
    policy_path = root / "scripts" / "viventium" / "qa_release_attestation_policy.json"
    signers_path = root / "trust" / "allowed_signers"
    policy_path.parent.mkdir(parents=True)
    signers_path.parent.mkdir(parents=True)

    def public(role: str) -> str:
        return " ".join(
            Path(f"{keys[role]}.pub").read_text(encoding="utf-8").split()[:2]
        )

    def fingerprint(role: str) -> str:
        material = base64.b64decode(public(role).split()[1], validate=True)
        return "SHA256:" + base64.b64encode(hashlib.sha256(material).digest()).decode(
            "ascii"
        ).rstrip("=")

    signers = "".join(
        f"{role}@qa.example.test {public(role)}\n"
        for role in ("publisher", "observer")
    )
    signers_path.write_text(signers, encoding="utf-8")
    policy_payload = {
        "contractVersion": 1,
        "allowedSigners": {
            "path": "trust/allowed_signers",
            "sha256": _digest(signers.encode("utf-8")),
        },
        "publisher": {
            "identity": "publisher@qa.example.test",
            "fingerprint": fingerprint("publisher"),
        },
        "producers": {
            "catalog-observer": {
                "identity": "observer@qa.example.test",
                "fingerprint": fingerprint("observer"),
                "role": "observation",
            }
        },
        "cases": {
            bundle["case_id"]: {
                "surface": bundle["spec"].surface,
                "verifierId": bundle["module"].VERIFIER_ID,
                "producerIds": ["catalog-observer"],
                "serviceProducerIds": [],
            }
        },
        "maximumReceiptAgeSeconds": 86_400,
        "maximumFutureSkewSeconds": 60,
    }
    policy_bytes = (
        json.dumps(
            policy_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        + "\n"
    ).encode("utf-8")
    policy_path.write_bytes(policy_bytes)
    policy = module.load_trust_policy(
        root,
        expected_policy_sha256=_digest(policy_bytes),
        expected_candidate_digest=bundle["candidate"],
    )
    return module, policy


def _ssh_signature(
    source: dict[str, object],
    key: Path,
    *,
    namespace: str,
) -> str:
    unsigned = {field: value for field, value in source.items() if field != "signature"}
    payload = (
        json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    ).encode("utf-8")
    result = subprocess.run(
        ["/usr/bin/ssh-keygen", "-Y", "sign", "-f", str(key), "-n", namespace],
        input=payload,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.decode("ascii")


def _resign_bundle_with_publisher_approved_observer(
    bundle: dict[str, Any], key: Path
) -> None:
    for entry in bundle["manifest"]["evidence"]:
        if entry["kind"].endswith("_capture"):
            continue
        path = bundle["evidence_root"] / entry["path"]
        document = json.loads(path.read_text(encoding="utf-8"))
        source = document["sourceReceipt"]
        source["signature"] = _ssh_signature(
            source,
            key,
            namespace=bundle["module"].SOURCE_SIGNATURE_NAMESPACE,
        )
        bundle["producer_receipts"][source["sourceRefHash"]] = copy.deepcopy(source)
        entry["sha256"] = _private(path, document)


def build_catalog_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case_id: str,
) -> dict[str, Any]:
    module = load_catalog_module()
    candidate = _digest("synthetic-current-candidate")
    artifact = _digest("synthetic-current-installed-artifact")
    owner = _digest("synthetic-owner-account")
    case_token = base64.urlsafe_b64encode(b"c" * 32).decode().rstrip("=")
    session_ref = "qa_" + _digest(case_token)[:24]
    process_services = (
        "runtime-owner",
        "librechat-core",
        "glasshive-runtime",
        "telegram-bot",
    )
    process_keys = {
        service: bytes.fromhex(_digest(f"synthetic-producer-key:{service}"))
        for service in process_services
    }
    processes = {
        service: {
            "pid": 7_000 + index,
            "startedAt": _stamp(-240 + index),
            "startMarker": "sha256:" + _digest(f"synthetic-process:{service}"),
            "executableSha256": "sha256:"
            + _digest(f"synthetic-executable:{service}"),
        }
        for index, service in enumerate(process_services, start=1)
    }
    producer_receipts: dict[str, dict[str, object]] = {}

    def verify_fixture_source(source, producer) -> None:
        if (
            source.get("signerId") != "catalog-observer"
            or source.get("signerIdentity") != "observer@qa.example.test"
        ):
            raise ValueError("isolated fixture signer is not authorized")
        unsigned = {
            field: value for field, value in source.items() if field != "signature"
        }
        expected = _proof(unsigned, process_keys[producer.service_id])
        if not hmac.compare_digest(str(source.get("signature") or ""), expected):
            raise ValueError("isolated fixture signature is invalid")

    authority = module.LiveAuthority(
        candidate_digest=candidate,
        artifact_digest=artifact,
        owner_ref_hash=owner,
        case_id=case_id,
        session_ref=session_ref,
        session_started_at=NOW - timedelta(minutes=5),
        session_expires_at=NOW + timedelta(minutes=10),
        producer_processes=processes,
        producer_receipts=producer_receipts,
        source_signature_verifier=verify_fixture_source,
    )
    live_probe = module.probe_live_authority
    monkeypatch.setattr(
        module,
        "probe_live_authority",
        lambda *, case_id, owner_ref_hash, session_ref, evidence_root, evidence, now=None: authority,
    )
    evidence_root = tmp_path / "private-evidence"
    evidence_root.mkdir(mode=0o700)
    evidence_root.chmod(0o700)
    spec = module.CASE_SPECS[case_id]
    requirements = module.case_requirements(case_id)
    records_by_kind: dict[str, list[dict[str, object]]] = {}
    for index, requirement in enumerate(requirements, start=1):
        facts = dict(requirement.facts)
        if requirement.id == "installed-runtime-identity":
            facts.update(
                candidateDigest=candidate,
                artifactDigest=artifact,
                ownerRefHash=owner,
                activeProcessCount=len(processes),
            )
        if requirement.id == "restart-exact-process-recovery":
            facts.update(
                beforeProcessRefHash=_digest("synthetic-process-before-restart"),
                afterProcessRefHash=_digest("synthetic-process-after-restart"),
                beforeAt=_stamp(-35),
                afterAt=_stamp(-25),
                restoredRecordCount=1,
                duplicateEffectCount=0,
            )
        records_by_kind.setdefault(requirement.kind, []).append(
            {
                "observationId": requirement.id,
                "ownerRefHash": owner,
                "recordedAt": _stamp(-20 + index / 1000),
                "sourceRefHash": _digest(f"{case_id}:{requirement.id}"),
                "facts": facts,
            }
        )

    evidence: list[dict[str, str]] = []
    capture_digests: dict[str, str] = {}
    for index, surface in enumerate(sorted(spec.capture_surfaces), start=1):
        kind = f"{surface}_capture"
        suffix = "wav" if surface == "voice" else "png"
        relative = f"captures/{kind}.{suffix}"
        raw = _audio() if surface == "voice" else _png(index)
        measured = _private(evidence_root / relative, raw)
        evidence.append({"id": kind, "kind": kind, "path": relative, "sha256": measured})
        capture_digests[surface] = measured
        observation_kind = f"{surface}_observation"
        for record in records_by_kind[observation_kind]:
            record["facts"]["captureSha256"] = measured
            record["facts"]["sourceRecordRefHash"] = _digest(
                f"{case_id}:{surface}:visible-record"
            )
            if surface == "voice":
                record["facts"]["audibleFrameCount"] = 8_000
            else:
                record["facts"]["viewportHeight"] = 240
                record["facts"]["viewportWidth"] = 384

    for ordinal, (kind, records) in enumerate(sorted(records_by_kind.items()), start=1):
        producer = module.EVIDENCE_PRODUCERS[kind]
        payload = {"records": records}
        source_ref = _digest(f"{case_id}:{kind}:authoritative-source-receipt")
        unsigned = {
            "artifactDigest": artifact,
            "candidateDigest": candidate,
            "caseId": case_id,
            "contractVersion": 1,
            "observedAt": _stamp(-10 + ordinal / 1000),
            "ownerRefHash": owner,
            "payloadSha256": _digest(payload),
            "processIdentity": processes[producer.service_id],
            "processStartMarker": processes[producer.service_id]["startMarker"],
            "producerId": producer.producer_id,
            "sequence": ordinal,
            "serviceId": producer.service_id,
            "sessionRef": session_ref,
            "signerId": "catalog-observer",
            "signerIdentity": "observer@qa.example.test",
            "sourceRefHash": source_ref,
            "surface": spec.surface,
            "verifierId": module.VERIFIER_ID,
        }
        receipt = {
            **unsigned,
            "signature": _proof(unsigned, process_keys[producer.service_id]),
        }
        producer_receipts[source_ref] = copy.deepcopy(receipt)
        document = {
            "artifactDigest": artifact,
            "candidateDigest": candidate,
            "caseId": case_id,
            "contractVersion": 1,
            "kind": kind,
            "observedAt": receipt["observedAt"],
            "originSurface": spec.surface,
            "ownerRefHash": owner,
            "payload": payload,
            "producerId": producer.producer_id,
            "serviceId": producer.service_id,
            "sessionRef": session_ref,
            "sourceReceipt": receipt,
        }
        relative = f"records/{kind}.json"
        measured = _private(evidence_root / relative, document)
        evidence.append({"id": kind, "kind": kind, "path": relative, "sha256": measured})

    checks = []
    for requirement in requirements:
        references = [requirement.kind]
        if requirement.kind.endswith("_observation"):
            references.append(requirement.kind.replace("_observation", "_capture"))
        checks.append({"id": requirement.id, "evidence": sorted(references)})
    manifest = {
        "candidate": {"artifactDigest": artifact, "candidateDigest": candidate},
        "caseId": case_id,
        "checks": checks,
        "contractVersion": 1,
        "correlation": {
            "ownerRefHash": owner,
            "sessionRef": session_ref,
            "surface": spec.surface,
        },
        "environment": "installed_local_production",
        "evidence": evidence,
        "runAt": _stamp(),
        "schema": module.MANIFEST_SCHEMA,
    }
    return {
        "artifact": artifact,
        "authority": authority,
        "candidate": candidate,
        "captures": capture_digests,
        "case_id": case_id,
        "evidence_root": evidence_root,
        "manifest": manifest,
        "module": module,
        "live_probe": live_probe,
        "owner": owner,
        "producer_keys": process_keys,
        "producer_receipts": producer_receipts,
        "spec": spec,
    }


def assess_bundle(bundle: dict[str, Any], **overrides: object) -> dict[str, object]:
    arguments: dict[str, object] = {
        "evidence_root": bundle["evidence_root"],
        "expected_candidate_digest": bundle["candidate"],
        "expected_artifact_digest": bundle["artifact"],
        "installed_owner_proven": True,
        "now": NOW,
    }
    arguments.update(overrides)
    return bundle["module"].assess_manifest(bundle["manifest"], **arguments)


def rewrite_document(
    bundle: dict[str, Any],
    kind: str,
    mutate,
    *,
    resign: bool = True,
    replace_live_receipt: bool = True,
) -> dict[str, object]:
    entry = next(item for item in bundle["manifest"]["evidence"] if item["kind"] == kind)
    path = bundle["evidence_root"] / entry["path"]
    document = json.loads(path.read_text(encoding="utf-8"))
    mutate(document)
    receipt = document.get("sourceReceipt")
    if resign and isinstance(receipt, dict):
        receipt["payloadSha256"] = _digest(document["payload"])
        unsigned = {key: value for key, value in receipt.items() if key != "signature"}
        service_id = str(receipt.get("serviceId") or "")
        key = bundle["producer_keys"].get(service_id)
        if key is not None:
            receipt["signature"] = _proof(unsigned, key)
        if replace_live_receipt:
            bundle["producer_receipts"][str(receipt.get("sourceRefHash"))] = copy.deepcopy(
                receipt
            )
    entry["sha256"] = _private(path, document)
    return document


def corrupt_case_binding(bundle: dict[str, Any], binding: str) -> None:
    manifest = bundle["manifest"]
    if binding == "case":
        manifest["caseId"] = (
            "PWK-002" if bundle["case_id"] != "PWK-002" else "PWK-001"
        )
    elif binding == "owner":
        manifest["correlation"]["ownerRefHash"] = _digest("different-account-owner")
    elif binding == "surface":
        manifest["correlation"]["surface"] = (
            "web" if bundle["spec"].surface == "voice" else "voice"
        )
    elif binding == "candidate":
        manifest["candidate"]["candidateDigest"] = _digest("different-candidate")
    elif binding == "artifact":
        manifest["candidate"]["artifactDigest"] = _digest("different-artifact")
    else:
        raise AssertionError("unsupported catalog binding mutation")


def test_catalog_contains_every_missing_case_and_no_dedicated_case() -> None:
    module = load_catalog_module()

    assert set(module.CASE_SPECS) == set(PARALLEL_CASE_IDS + RELEASE_CASE_IDS)
    assert len(module.CASE_SPECS) == 71
    assert not set(module.CASE_SPECS).intersection(
        {"PWK-UC-014", "PWK-UC-015", "PWK-UC-016", "PWK-UC-017", "PWK-UC-018", "PWK-UC-019", "TR-026", "REL-UC-004"}
    )


@pytest.mark.parametrize("case_id", PARALLEL_CASE_IDS)
def test_every_parallel_case_derives_pass_from_live_candidate_bound_producers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case_id: str
) -> None:
    bundle = build_catalog_bundle(tmp_path, monkeypatch, case_id)

    result = assess_bundle(bundle)

    assert result["status"] == "PASS"
    assert result["caseId"] == case_id
    assert result["checkCount"] == len(bundle["module"].case_requirements(case_id))
    receipt = bundle["module"].receipt_manifest(result=result)
    assert receipt == {
        "caseId": case_id,
        "contractVersion": 1,
        "evidence": sorted(
            (
                {"kind": item["kind"], "path": item["path"], "sha256": item["sha256"]}
                for item in bundle["manifest"]["evidence"]
            ),
            key=lambda item: (item["kind"], item["path"]),
        ),
        "runAt": _stamp(),
        "status": "PASS",
        "surface": bundle["spec"].surface,
    }


@pytest.mark.parametrize("case_id", PARALLEL_CASE_IDS)
def test_each_parallel_case_rejects_missing_exact_semantic_requirement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case_id: str
) -> None:
    bundle = build_catalog_bundle(tmp_path, monkeypatch, case_id)
    bundle["manifest"]["checks"].pop()

    with pytest.raises(ValueError, match="required catalog check"):
        assess_bundle(bundle)


@pytest.mark.parametrize("case_id", PARALLEL_CASE_IDS)
@pytest.mark.parametrize("binding", ["case", "owner", "surface", "candidate", "artifact"])
def test_every_parallel_case_rejects_cross_case_owner_surface_or_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case_id: str,
    binding: str,
) -> None:
    bundle = build_catalog_bundle(tmp_path, monkeypatch, case_id)
    corrupt_case_binding(bundle, binding)

    with pytest.raises(ValueError):
        assess_bundle(bundle)


@pytest.mark.parametrize(
    "case_id",
    ["PWK-001", "PWK-011", "PWK-017", "PWK-048", "PWK-UC-004", "PWK-UC-013"],
)
def test_all_user_surfaces_require_capture_and_signed_visible_observation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case_id: str
) -> None:
    bundle = build_catalog_bundle(tmp_path, monkeypatch, case_id)
    assert bundle["spec"].capture_surfaces
    surface = sorted(bundle["spec"].capture_surfaces)[0]
    bundle["manifest"]["evidence"] = [
        item
        for item in bundle["manifest"]["evidence"]
        if item["kind"] != f"{surface}_capture"
    ]

    with pytest.raises(ValueError, match="visible|audible|capture"):
        assess_bundle(bundle)


@pytest.mark.parametrize(
    "mutation",
    [
        "owner_not_proven",
        "candidate",
        "artifact",
        "case",
        "owner",
        "surface",
        "environment",
        "unknown_field",
        "stale_run",
        "future_run",
        "expired_session",
        "wrong_session",
        "self_declared_pass",
        "self_declared_observation",
        "wrong_producer",
        "wrong_service",
        "unsigned_source",
        "forged_source",
        "owner_readable_hmac_source",
        "wrong_signer",
        "wrong_signer_identity",
        "wrong_signature_namespace",
        "missing_protected_verifier",
        "missing_live_source",
        "replayed_source",
        "wrong_process",
        "wrong_document_owner",
        "wrong_document_candidate",
        "wrong_document_artifact",
        "wrong_document_surface",
        "wrong_record_owner",
        "wrong_measurement",
        "duplicate_check",
        "duplicate_evidence",
        "unreferenced_evidence",
        "tampered_file",
        "fake_capture",
        "public_root",
        "world_readable_file",
        "path_escape",
        "symlink",
        "hardlink",
    ],
)
def test_rejects_forgery_replay_cross_owner_synthetic_and_unsafe_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    bundle = build_catalog_bundle(tmp_path, monkeypatch, "PWK-001")
    manifest = bundle["manifest"]
    requirements = bundle["module"].case_requirements("PWK-001")
    substantive = next(
        rule
        for rule in requirements
        if rule.id != "installed-runtime-identity" and not rule.kind.endswith("_observation")
    )
    entry = next(item for item in manifest["evidence"] if item["kind"] == substantive.kind)
    overrides: dict[str, object] = {}

    if mutation == "owner_not_proven":
        overrides["installed_owner_proven"] = False
    elif mutation == "candidate":
        manifest["candidate"]["candidateDigest"] = _digest("different-candidate")
    elif mutation == "artifact":
        manifest["candidate"]["artifactDigest"] = _digest("different-artifact")
    elif mutation == "case":
        manifest["caseId"] = "PWK-002"
    elif mutation == "owner":
        manifest["correlation"]["ownerRefHash"] = _digest("different-owner")
    elif mutation == "surface":
        manifest["correlation"]["surface"] = "voice"
    elif mutation == "environment":
        manifest["environment"] = "synthetic_fixture"
    elif mutation == "unknown_field":
        manifest["status"] = "PASS"
    elif mutation == "stale_run":
        manifest["runAt"] = (NOW - timedelta(hours=25)).isoformat()
    elif mutation == "future_run":
        manifest["runAt"] = (NOW + timedelta(seconds=61)).isoformat()
    elif mutation == "expired_session":
        bundle["authority"].session_expires_at = NOW - timedelta(seconds=1)
    elif mutation == "wrong_session":
        manifest["correlation"]["sessionRef"] = "qa_" + "f" * 24
    elif mutation == "self_declared_pass":
        manifest["checks"][0]["status"] = "PASS"
    elif mutation == "self_declared_observation":
        rewrite_document(
            bundle,
            substantive.kind,
            lambda document: document["payload"]["records"][0].update(status="PASS"),
        )
    elif mutation == "wrong_producer":
        rewrite_document(
            bundle,
            substantive.kind,
            lambda document: document.update(producerId="user.self_declared"),
        )
    elif mutation == "wrong_service":
        def wrong_service(document: dict[str, object]) -> None:
            document["serviceId"] = "telegram-bot"
            document["sourceReceipt"]["serviceId"] = "telegram-bot"

        rewrite_document(bundle, substantive.kind, wrong_service)
    elif mutation == "unsigned_source":
        rewrite_document(
            bundle,
            substantive.kind,
            lambda document: document["sourceReceipt"].pop("signature"),
            resign=False,
        )
    elif mutation == "forged_source":
        rewrite_document(
            bundle,
            substantive.kind,
            lambda document: document["sourceReceipt"].update(
                signature=(
                    "-----BEGIN SSH SIGNATURE-----\n"
                    + "f" * 64
                    + "\n-----END SSH SIGNATURE-----\n"
                )
            ),
            resign=False,
        )
    elif mutation == "owner_readable_hmac_source":
        rewrite_document(
            bundle,
            substantive.kind,
            lambda document: document["sourceReceipt"].update(
                signature="hmac-sha256:" + "f" * 64
            ),
            resign=False,
        )
    elif mutation == "wrong_signer":
        rewrite_document(
            bundle,
            substantive.kind,
            lambda document: document["sourceReceipt"].update(
                signerId="same-owner-attacker"
            ),
        )
    elif mutation == "wrong_signer_identity":
        rewrite_document(
            bundle,
            substantive.kind,
            lambda document: document["sourceReceipt"].update(
                signerIdentity="attacker@qa.example.test"
            ),
        )
    elif mutation == "wrong_signature_namespace":
        def sign_wrong_domain(document: dict[str, object]) -> None:
            source = document["sourceReceipt"]
            unsigned = {
                field: value for field, value in source.items() if field != "signature"
            }
            source["signature"] = _proof(
                unsigned,
                bundle["producer_keys"][source["serviceId"]],
                namespace="self-declared-attacker-domain",
            )

        rewrite_document(bundle, substantive.kind, sign_wrong_domain, resign=False)
    elif mutation == "missing_protected_verifier":
        bundle["authority"].source_signature_verifier = None
    elif mutation == "missing_live_source":
        bundle["producer_receipts"].clear()
    elif mutation == "replayed_source":
        other = next(
            item
            for item in manifest["evidence"]
            if item["kind"] != substantive.kind and item["kind"].endswith("_ledger")
        )
        other_document = json.loads(
            (bundle["evidence_root"] / other["path"]).read_text(encoding="utf-8")
        )
        rewrite_document(
            bundle,
            substantive.kind,
            lambda document: document.update(sourceReceipt=other_document["sourceReceipt"]),
            resign=False,
        )
    elif mutation == "wrong_process":
        rewrite_document(
            bundle,
            substantive.kind,
            lambda document: document["sourceReceipt"].update(
                processStartMarker="sha256:" + _digest("different-process")
            ),
        )
    elif mutation == "wrong_document_owner":
        rewrite_document(
            bundle,
            substantive.kind,
            lambda document: document.update(ownerRefHash=_digest("different-owner")),
        )
    elif mutation == "wrong_document_candidate":
        rewrite_document(
            bundle,
            substantive.kind,
            lambda document: document.update(candidateDigest=_digest("different-candidate")),
        )
    elif mutation == "wrong_document_artifact":
        rewrite_document(
            bundle,
            substantive.kind,
            lambda document: document.update(artifactDigest=_digest("different-artifact")),
        )
    elif mutation == "wrong_document_surface":
        rewrite_document(
            bundle,
            substantive.kind,
            lambda document: document.update(originSurface="voice"),
        )
    elif mutation == "wrong_record_owner":
        rewrite_document(
            bundle,
            substantive.kind,
            lambda document: document["payload"]["records"][0].update(
                ownerRefHash=_digest("different-owner")
            ),
        )
    elif mutation == "wrong_measurement":
        def corrupt_fact(document: dict[str, object]) -> None:
            facts = document["payload"]["records"][0]["facts"]
            key = next(iter(facts))
            facts[key] = "self-declared-pass"

        rewrite_document(bundle, substantive.kind, corrupt_fact)
    elif mutation == "duplicate_check":
        manifest["checks"].append(copy.deepcopy(manifest["checks"][0]))
    elif mutation == "duplicate_evidence":
        manifest["evidence"].append(copy.deepcopy(manifest["evidence"][0]))
    elif mutation == "unreferenced_evidence":
        for check in manifest["checks"]:
            check["evidence"] = [
                value for value in check["evidence"] if value != substantive.kind
            ]
    elif mutation == "tampered_file":
        (bundle["evidence_root"] / entry["path"]).write_bytes(b"tampered")
    elif mutation == "fake_capture":
        capture = next(item for item in manifest["evidence"] if item["kind"].endswith("_capture"))
        capture["sha256"] = _private(
            bundle["evidence_root"] / capture["path"], b"not-a-real-user-capture"
        )
    elif mutation == "public_root":
        bundle["evidence_root"].chmod(0o755)
    elif mutation == "world_readable_file":
        (bundle["evidence_root"] / entry["path"]).chmod(0o644)
    elif mutation == "path_escape":
        entry["path"] = "../outside.json"
    elif mutation == "symlink":
        target = bundle["evidence_root"] / entry["path"]
        actual = bundle["evidence_root"] / "records" / "other.json"
        actual.write_bytes(target.read_bytes())
        actual.chmod(0o600)
        target.unlink()
        target.symlink_to(actual)
    elif mutation == "hardlink":
        target = bundle["evidence_root"] / entry["path"]
        os.link(target, bundle["evidence_root"] / "records" / "extra-link.json")

    with pytest.raises(ValueError):
        assess_bundle(bundle, **overrides)


def test_restart_cases_reject_same_process_or_duplicate_recovery_effect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = build_catalog_bundle(tmp_path, monkeypatch, "PWK-048")
    assert bundle["spec"].restart_required

    def same_process(document: dict[str, object]) -> None:
        facts = document["payload"]["records"][0]["facts"]
        facts["afterProcessRefHash"] = facts["beforeProcessRefHash"]

    rewrite_document(bundle, "restart_ledger", same_process)

    with pytest.raises(ValueError, match="restart"):
        assess_bundle(bundle)


@pytest.mark.parametrize("case_id", ["PWK-016", "REL-001"])
def test_real_publisher_pinned_ed25519_observer_authenticates_catalog_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    catalog_ssh_keys: dict[str, Path],
    case_id: str,
) -> None:
    bundle = build_catalog_bundle(tmp_path, monkeypatch, case_id)
    installed = tmp_path / "publisher-pinned-candidate"
    attestation, policy = _catalog_policy(
        bundle=bundle,
        root=installed,
        keys=catalog_ssh_keys,
    )
    bundle["authority"].source_signature_verifier = bundle[
        "module"
    ]._protected_source_verifier(attestation, policy, case_id=case_id)
    _resign_bundle_with_publisher_approved_observer(
        bundle, catalog_ssh_keys["observer"]
    )

    assert assess_bundle(bundle)["status"] == "PASS"


@pytest.mark.parametrize("attack", ["untrusted_key", "wrong_namespace", "wrong_identity"])
def test_real_publisher_pinned_observer_rejects_same_owner_forgery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    catalog_ssh_keys: dict[str, Path],
    attack: str,
) -> None:
    bundle = build_catalog_bundle(tmp_path, monkeypatch, "PWK-016")
    attestation, policy = _catalog_policy(
        bundle=bundle,
        root=tmp_path / "publisher-pinned-candidate",
        keys=catalog_ssh_keys,
    )
    bundle["authority"].source_signature_verifier = bundle[
        "module"
    ]._protected_source_verifier(attestation, policy, case_id="PWK-016")
    _resign_bundle_with_publisher_approved_observer(
        bundle, catalog_ssh_keys["observer"]
    )
    entry = next(
        item
        for item in bundle["manifest"]["evidence"]
        if item["kind"] == "network_ledger"
    )
    path = bundle["evidence_root"] / entry["path"]
    document = json.loads(path.read_text(encoding="utf-8"))
    source = document["sourceReceipt"]
    namespace = bundle["module"].SOURCE_SIGNATURE_NAMESPACE
    key = catalog_ssh_keys["observer"]
    if attack == "untrusted_key":
        key = catalog_ssh_keys["attacker"]
    elif attack == "wrong_namespace":
        namespace = "same-owner-self-declared-domain"
    elif attack == "wrong_identity":
        source["signerIdentity"] = "attacker@qa.example.test"
    source["signature"] = _ssh_signature(source, key, namespace=namespace)
    bundle["producer_receipts"][source["sourceRefHash"]] = copy.deepcopy(source)
    entry["sha256"] = _private(path, document)

    with pytest.raises(ValueError, match="signature|signer"):
        assess_bundle(bundle)


def test_live_catalog_probe_does_not_require_a_privileged_fault_injection_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    catalog_ssh_keys: dict[str, Path],
) -> None:
    bundle = build_catalog_bundle(tmp_path, monkeypatch, "PWK-016")
    module = bundle["module"]
    attestation, policy = _catalog_policy(
        bundle=bundle,
        root=tmp_path / "publisher-pinned-candidate",
        keys=catalog_ssh_keys,
    )
    _resign_bundle_with_publisher_approved_observer(
        bundle,
        catalog_ssh_keys["observer"],
    )
    home = tmp_path / "synthetic-home"
    home.mkdir()
    support = home / "Library" / "Application Support" / "Viventium"
    runtime = support / "runtime"
    owner_path = support / "state" / "runtime" / "isolated" / "stack-owner.json"
    owner_process = bundle["authority"].producer_processes["runtime-owner"]
    _private(
        owner_path,
        {"ownerPid": owner_process["pid"], "ownerExecutablePath": "/bin/sh"},
    )
    _private(runtime / "parallel-work-artifact-identity.json", {"installed": True})
    session_ref = bundle["authority"].session_ref
    by_service: dict[str, list[dict[str, object]]] = {}
    for receipt in bundle["producer_receipts"].values():
        by_service.setdefault(receipt["serviceId"], []).append(receipt)

    trusted = SimpleNamespace(expected_policy_sha256=policy.policy_sha256)
    gate = SimpleNamespace(
        _runtime_owner_state_proves_active=lambda *_args: True,
        _qa_candidate_digests=lambda _identity: (
            bundle["candidate"],
            bundle["artifact"],
        ),
        _resolve_external_release_attestation_authority=lambda **_kwargs: trusted,
        _external_release_attestation_context=lambda _trusted, **_kwargs: (
            attestation,
            policy,
            tmp_path / "protected-ledger",
            SimpleNamespace(
                current=lambda _scope: None,
                advance=lambda _scope, **_kwargs: True,
            ),
        ),
    )
    control = SimpleNamespace(
        _read_private_json=lambda path, **_kwargs: (
            b"",
            json.loads(path.read_text(encoding="utf-8")),
        )
    )
    acknowledgement = SimpleNamespace(
        probe_process=lambda _pid, _executable: owner_process
    )

    def load_module(path: Path, _name: str) -> object:
        if path.name == "parallel_work_release_gate.py":
            return gate
        if path.name == "local_qa_runtime_control.py":
            return control
        if path.name == "local_qa_service_ack.py":
            return acknowledgement
        raise AssertionError("unexpected installed runtime module")

    monkeypatch.setattr(module, "_load_module", load_module)
    monkeypatch.setattr(
        module,
        "__file__",
        str(
            policy.installed_root
            / "qa"
            / "parallel-orchestrator"
            / "scripts"
            / "catalog_case_semantic_verifier.py"
        ),
    )
    monkeypatch.setattr(
        module.pwd,
        "getpwuid",
        lambda _uid: SimpleNamespace(pw_dir=str(home)),
    )

    authority = bundle["live_probe"](
        case_id="PWK-016",
        owner_ref_hash=bundle["owner"],
        session_ref=session_ref,
        evidence_root=bundle["evidence_root"],
        evidence=bundle["manifest"]["evidence"],
        now=NOW,
    )

    assert authority.owner_ref_hash == bundle["owner"]
    assert set(authority.producer_processes) == set(by_service)
    assert not hasattr(control, "active_session")
    assert not (runtime / "local-qa" / "catalog-producer-receipts").exists()
    monkeypatch.setattr(module, "probe_live_authority", lambda **_kwargs: authority)
    assert assess_bundle(bundle)["status"] == "PASS"


def test_missing_publisher_authenticated_root_never_accepts_same_owner_policy() -> None:
    module = load_catalog_module()

    with pytest.raises(ValueError, match="publisher-authenticated"):
        module._publisher_trust_policy(
            gate=SimpleNamespace(),
            installed_root=ROOT,
            runtime_owner_state=ROOT / "synthetic-owner-state.json",
            candidate_digest=_digest("synthetic-current-candidate"),
        )


def test_catalog_reuses_release_gate_publisher_root_and_external_witness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    catalog_ssh_keys: dict[str, Path],
) -> None:
    bundle = build_catalog_bundle(tmp_path, monkeypatch, "PWK-016")
    root = tmp_path / "publisher-pinned-candidate"
    attestation, policy = _catalog_policy(
        bundle=bundle,
        root=root,
        keys=catalog_ssh_keys,
    )
    trusted = SimpleNamespace(expected_policy_sha256=policy.policy_sha256)
    owner_state = tmp_path / "synthetic-runtime-owner.json"
    protected_witness = object()
    calls: list[tuple[str, object]] = []

    def resolve_authority(**arguments: object) -> object:
        calls.append(("authority", arguments))
        return trusted

    def resolve_context(authority: object, **arguments: object) -> object:
        calls.append(("context", arguments))
        assert authority is trusted
        return attestation, policy, tmp_path / "protected-ledger", protected_witness

    gate = SimpleNamespace(
        _resolve_external_release_attestation_authority=resolve_authority,
        _external_release_attestation_context=resolve_context,
    )

    assert bundle["module"]._publisher_trust_policy(
        gate=gate,
        installed_root=root,
        runtime_owner_state=owner_state,
        candidate_digest=bundle["candidate"],
    ) == (attestation, policy)
    assert [name for name, _arguments in calls] == ["authority", "context"]
    assert all(
        arguments
        == {
            "installed_root": root,
            "runtime_owner_state": owner_state,
            "candidate_digest": bundle["candidate"],
        }
        for _name, arguments in calls
    )


@pytest.mark.parametrize("corruption", ["missing_witness", "wrong_policy_pin"])
def test_catalog_rejects_unprotected_or_replaced_release_trust_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    catalog_ssh_keys: dict[str, Path],
    corruption: str,
) -> None:
    bundle = build_catalog_bundle(tmp_path, monkeypatch, "PWK-016")
    root = tmp_path / "publisher-pinned-candidate"
    attestation, policy = _catalog_policy(
        bundle=bundle,
        root=root,
        keys=catalog_ssh_keys,
    )
    pin = policy.policy_sha256 if corruption != "wrong_policy_pin" else "f" * 64
    trusted = SimpleNamespace(expected_policy_sha256=pin)
    context = (
        None
        if corruption == "missing_witness"
        else (attestation, policy, tmp_path / "protected-ledger", object())
    )
    gate = SimpleNamespace(
        _resolve_external_release_attestation_authority=lambda **_kwargs: trusted,
        _external_release_attestation_context=lambda _authority, **_kwargs: context,
    )

    with pytest.raises(ValueError, match="publisher-authenticated"):
        bundle["module"]._publisher_trust_policy(
            gate=gate,
            installed_root=root,
            runtime_owner_state=tmp_path / "synthetic-runtime-owner.json",
            candidate_digest=bundle["candidate"],
        )


def test_ordinary_catalog_cases_accept_already_running_installed_services(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = build_catalog_bundle(tmp_path, monkeypatch, "PWK-016")
    for process in bundle["authority"].producer_processes.values():
        process["startedAt"] = _stamp(-900)
    for entry in bundle["manifest"]["evidence"]:
        kind = entry["kind"]
        if kind.endswith("_capture"):
            continue

        def update_process(document: dict[str, object]) -> None:
            source = document["sourceReceipt"]
            source["processIdentity"] = bundle["authority"].producer_processes[
                source["serviceId"]
            ]

        rewrite_document(bundle, kind, update_process)

    assert assess_bundle(bundle)["status"] == "PASS"


@pytest.mark.parametrize(
    ("case_id", "kind", "observation_id", "field", "within_budget", "outside_budget"),
    [
        (
            "PWK-016",
            "network_ledger",
            "focused-local-overhead-meets-budget",
            "maximumOverheadMs",
            5,
            26,
        ),
        (
            "PWK-027",
            "delivery_ledger",
            "same-account-completion-coalesces-in-budget",
            "maximumCoalescingMs",
            1_200,
            2_001,
        ),
    ],
)
def test_installed_timing_budgets_accept_faster_real_measurements_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case_id: str,
    kind: str,
    observation_id: str,
    field: str,
    within_budget: int,
    outside_budget: int,
) -> None:
    bundle = build_catalog_bundle(tmp_path, monkeypatch, case_id)

    def set_measurement(value: int) -> None:
        def change(document: dict[str, object]) -> None:
            record = next(
                item
                for item in document["payload"]["records"]
                if item["observationId"] == observation_id
            )
            record["facts"][field] = value

        rewrite_document(bundle, kind, change)

    set_measurement(within_budget)
    assert assess_bundle(bundle)["status"] == "PASS"

    set_measurement(outside_budget)
    with pytest.raises(ValueError, match="measurement"):
        assess_bundle(bundle)


def test_receipt_emission_rejects_fabricated_copied_or_mutated_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = build_catalog_bundle(tmp_path, monkeypatch, "PWK-011")
    verifier = bundle["module"]

    with pytest.raises(ValueError, match="derived PASS"):
        verifier.receipt_manifest(result={"caseId": "PWK-011", "status": "PASS"})

    result = assess_bundle(bundle)
    with pytest.raises(ValueError, match="derived PASS"):
        verifier.receipt_manifest(result=dict(result))

    result["caseId"] = "PWK-012"
    with pytest.raises(ValueError, match="derived PASS"):
        verifier.receipt_manifest(result=result)


def test_registration_contract_is_one_shared_script_for_all_71_cases() -> None:
    module = load_catalog_module()

    assert module.VERIFIER_ID == "viventium-installed-catalog-v1"
    assert module.REGISTRATION_PATH == Path(
        "qa/parallel-orchestrator/scripts/catalog_case_semantic_verifier.py"
    )
    assert module.registration_contract() == {
        case_id: {"id": module.VERIFIER_ID, "path": module.REGISTRATION_PATH}
        for case_id in PARALLEL_CASE_IDS + RELEASE_CASE_IDS
    }
