from __future__ import annotations

import base64
import copy
import hashlib
import hmac
import importlib.util
import json
import struct
import subprocess
import sys
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from qa_control_test_support import _load_release_gate, write_artifact_identity

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "qa/release-readiness/scripts/rel_uc_004_semantic_verifier.py"
ACK_SCRIPT = ROOT / "scripts/viventium/local_qa_service_ack.py"
RECORDER_SCRIPT = ROOT / "scripts/viventium/parallel_work_qa_evidence.py"
BLOCKERS = ["PWK-018", "PROMPT-LAYERS", "STORAGE-PRESSURE"]
CLAIM_PATHS = (
    ("public_cli_release", "release", "cli", "public_cli_capture"),
    ("public_cli_completion", "completion", "cli", "public_cli_capture"),
    ("public_cli_readiness", "readiness", "cli", "public_cli_capture"),
    ("install_summary", "readiness", "installer", "install_summary_capture"),
    ("release_check", "release", "cli", "public_cli_capture"),
    ("installed_web_status", "readiness", "web", "web_status_observation"),
    ("installed_telegram_status", "readiness", "telegram", "telegram_status_observation"),
)


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _digest(value: object) -> str:
    if not isinstance(value, str):
        value = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(value.encode()).hexdigest()


def _stamp(started: datetime, seconds: float) -> str:
    return (started + timedelta(seconds=seconds)).isoformat(timespec="milliseconds")


def _proof(unsigned: dict[str, object], token: str) -> str:
    key = base64.urlsafe_b64decode(token + "=")
    raw = json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
    return "hmac-sha256:" + hmac.new(key, raw, hashlib.sha256).hexdigest()


def _png(variant: int, *, uniform: bool = False) -> bytes:
    width, height = 640, 360
    rows = bytearray()
    for row in range(height):
        rows.append(0)
        rows.extend(
            0 if uniform else (column * 3 + row + variant * 37) % 256
            for column in range(width)
        )

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(rows)))
        + chunk(b"IEND", b"")
    )


def _private(path: Path, payload: object) -> str:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    raw = payload if isinstance(payload, bytes) else (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    path.write_bytes(raw)
    path.chmod(0o600)
    return hashlib.sha256(raw).hexdigest()


def _healthy() -> dict[str, object]:
    return {
        "contractVersion": 1,
        "promptLayers": {
            "contractVersion": 1,
            "producerScope": "viventium.prompt_registry.v1",
            "status": "verified",
            "unknownLayerCount": 0,
            "unknownLayerNames": [],
            "promptCount": 4,
            "layerCount": 2,
            "layerNames": ["dynamic", "static"],
            "registryHash": "a" * 64,
        },
        "storagePressure": {
            "version": 1,
            "status": "healthy",
            "usedPercent": 40.0,
            "availableBytes": 80_000_000_000,
            "thresholdPercent": 95.0,
            "warningMarginPercent": 10.0,
        },
    }


def _injected(healthy: dict[str, object]) -> dict[str, object]:
    result = copy.deepcopy(healthy)
    result["promptLayers"].update(
        status="mismatch", registryHash="0" * 64, reason="local_qa_prompt_hash_mismatch"
    )
    result["storagePressure"] = {
        "version": 1,
        "status": "critical",
        "usedPercent": 96.0,
        "availableBytes": 4_300_000_000,
        "thresholdPercent": 95.0,
        "warningMarginPercent": 10.0,
        "reason": "local_qa_threshold_injection",
    }
    return result


def _service_ack(session: dict[str, object], started: datetime):
    process = {
        "pid": 5101,
        "startedAt": _stamp(started, 1),
        "startMarker": "sha256:" + _digest("synthetic-rel-core-process"),
        "executablePath": "/usr/bin/synthetic-librechat-core",
        "executableSha256": "sha256:" + _digest("synthetic-rel-core-executable"),
    }
    unsigned = {
        "acknowledgedAt": _stamp(started, 3),
        "artifactIdentityDigest": session["artifactIdentityDigest"],
        "caseId": "REL-UC-004",
        "componentArtifactDigest": session["componentArtifactDigest"],
        "contractVersion": 1,
        "installedRootHash": session["installedRootHash"],
        "processIdentity": process,
        "serviceId": "librechat-core",
        "sessionRef": session["sessionRef"],
    }
    return {**unsigned, "proof": _proof(unsigned, str(session["caseToken"]))}, process


def _output(blockers: list[str]) -> str:
    return "PRE-GATE / NOT READY | blockers: " + ", ".join(blockers)


@pytest.fixture
def release_bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    verifier = _load(SCRIPT, "rel_uc_004_focused_semantic_verifier")
    ack_module = _load(ACK_SCRIPT, "rel_uc_004_focused_service_ack")
    installed = tmp_path / "installed"
    installed.mkdir()
    identity_path = tmp_path / "artifact-identity.json"
    identity = write_artifact_identity(installed, identity_path)
    candidate, artifact = _load_release_gate()._qa_candidate_digests(identity)
    started = datetime(2026, 8, 25, 13, 0, tzinfo=timezone.utc)
    token = base64.urlsafe_b64encode(b"r" * 32).decode().rstrip("=")
    session = {
        "artifactIdentityDigest": "sha256:" + _digest(identity_path.read_text(encoding="utf-8")),
        "caseId": "REL-UC-004",
        "caseToken": token,
        "componentArtifactDigest": "sha256:" + _digest("synthetic-release-component"),
        "contractVersion": 1,
        "expiresAt": _stamp(started, 900),
        "installedRootHash": "sha256:" + _digest("synthetic-release-root"),
        "mode": "rel_uc_004",
        "modeVariable": "VIVENTIUM_RELEASE_LOCAL_QA_MODE",
        "sessionRef": "qa_" + _digest(token)[:24],
        "startedAt": _stamp(started, 0),
    }
    acknowledgement, process = _service_ack(session, started)
    monkeypatch.setattr(
        ack_module,
        "_service_process_identity_valid",
        lambda service, pid, executable: (
            service == "librechat-core"
            and pid == process["pid"]
            and str(executable) == process["executablePath"]
        ),
    )
    acknowledgements = [acknowledgement]
    service_status = {
        "caseId": "REL-UC-004",
        "expiresAt": session["expiresAt"],
        "mode": "rel_uc_004",
        "sessionRef": session["sessionRef"],
        "restartState": "ready",
        "requiredServices": ["librechat-core"],
        "acknowledgedServices": ["librechat-core"],
        "missingServices": [],
        "serviceAckDigest": "sha256:" + _digest(acknowledgements),
    }
    healthy = _healthy()
    injected = _injected(healthy)
    owner = _digest("synthetic-release-owner")
    authority = verifier._LiveAuthority(
        candidate_digest=candidate,
        artifact_digest=artifact,
        owner_ref_hash=owner,
        artifact_identity=identity,
        session=session,
        service_status=service_status,
        acknowledgements=acknowledgements,
        acknowledgement_module=ack_module,
        process_probe=lambda pid, _path: process if pid == process["pid"] else None,
        readiness_facts=healthy,
        fault_backup_present=False,
    )
    monkeypatch.setattr(verifier, "probe_live_authority", lambda **_kwargs: authority)
    evidence_root = tmp_path / "private-evidence"
    evidence_root.mkdir(mode=0o700)
    screenshots: dict[str, str] = {}
    evidence: list[dict[str, str]] = []
    for ordinal, kind in enumerate(
        (
            "web_status_screenshot_injected",
            "web_status_screenshot_recovered",
            "telegram_status_screenshot_injected",
            "telegram_status_screenshot_recovered",
        ),
        start=1,
    ):
        relative = f"captures/{kind}.png"
        measured = _private(evidence_root / relative, _png(ordinal))
        screenshots[kind] = measured
        evidence.append({"kind": kind, "path": relative, "sha256": measured})

    backup = {
        "contractVersion": 1,
        "injectedDigest": _digest(injected),
        "original": healthy,
        "originalDigest": _digest(healthy),
        "sessionRef": session["sessionRef"],
    }
    gate_snapshots = {
        "configDefaults": {
            "source": {"availability": False, "mode": "focused"},
            "installed": {"availability": False, "mode": "focused"},
        },
        "injected": {
            "mode": "local-qa",
            "label": "PRE-GATE / NOT READY",
            "releaseReady": False,
            "exposureAllowed": False,
            "sourceDefaultsDark": True,
            "openGates": [
                {
                    "caseId": "PWK-018",
                    "status": "PARTIAL",
                    "owner": "qa/parallel-orchestrator/cases.md",
                    "candidateDigest": candidate,
                    "artifactDigest": artifact,
                }
            ],
            "blockingChecks": [
                {"checkId": "PROMPT-LAYERS", "status": "FAIL", "reason": "prompt_layer_hash_mismatch"},
                {"checkId": "STORAGE-PRESSURE", "status": "FAIL", "reason": "storage_pressure"},
            ],
            "readinessFacts": injected,
        },
        "recovered": {
            "mode": "local-qa",
            "label": "PRE-GATE / NOT READY",
            "releaseReady": False,
            "exposureAllowed": False,
            "sourceDefaultsDark": True,
            "openGates": [
                {
                    "caseId": "PWK-018",
                    "status": "PARTIAL",
                    "owner": "qa/parallel-orchestrator/cases.md",
                    "candidateDigest": candidate,
                    "artifactDigest": artifact,
                }
            ],
            "blockingChecks": [],
            "readinessFacts": healthy,
        },
    }
    claims = []
    captures: dict[str, list[dict[str, object]]] = {
        "public_cli_capture": [],
        "install_summary_capture": [],
        "web_status_observation": [],
        "telegram_status_observation": [],
    }
    for phase, blockers in (("injected", BLOCKERS), ("recovered", ["PWK-018"])):
        for ordinal, (path, intent, surface, capture_kind) in enumerate(CLAIM_PATHS):
            text = _output(blockers)
            observed = _stamp(started, 30 + (0 if phase == "injected" else 30) + ordinal)
            row = {
                "path": path,
                "phase": phase,
                "intent": intent,
                "surface": surface,
                "captureKind": capture_kind,
                "observedAt": observed,
                "label": "PRE-GATE / NOT READY",
                "blockerIds": list(blockers),
                "releaseReady": False,
                "completionClaimed": False,
                "parallelAvailable": False,
                "defaultMode": "focused",
                "outputSha256": _digest(text),
            }
            claims.append(row)
            capture = {
                "path": path,
                "phase": phase,
                "observedAt": observed,
                "captureMethod": {
                    "cli": "installed_process_stdout",
                    "installer": "installed_summary_render",
                    "web": "headed_browser_accessibility",
                    "telegram": "telegram_desktop_accessibility",
                }[surface],
                "output": text,
                "outputSha256": _digest(text),
                "exitCode": 1,
            }
            if surface == "web":
                screenshot = f"web_status_screenshot_{phase}"
                capture.update(screenshotKind=screenshot, screenshotSha256=screenshots[screenshot], captureOrigin="headed_browser_window_capture")
            if surface == "telegram":
                screenshot = f"telegram_status_screenshot_{phase}"
                capture.update(screenshotKind=screenshot, screenshotSha256=screenshots[screenshot], captureOrigin="native_desktop_window_capture")
            captures[capture_kind].append(capture)

    documents = {
        "installed_identity": verifier._identity_projection(authority),
        "fault_injection": {
            "appliedAt": _stamp(started, 10),
            "storageProbe": "synthetic_threshold_only",
            "diskBytesWritten": 4096,
            "before": healthy,
            "injected": injected,
            "backup": backup,
        },
        "gate_evaluator": gate_snapshots,
        "release_claim_matrix": {"claims": claims},
        **{kind: {"captures": values} for kind, values in captures.items()},
        "recovery_evidence": {
            "restoredAt": _stamp(started, 58),
            "restoreReceipt": {"restored": True, "sessionRef": session["sessionRef"]},
            "restoredFacts": healthy,
            "faultBackupPresent": False,
            "currentCandidateEvidence": [
                {"blockerId": "PROMPT-LAYERS", "status": "PASS", "candidateDigest": candidate, "artifactDigest": artifact, "observedAt": _stamp(started, 58)},
                {"blockerId": "STORAGE-PRESSURE", "status": "PASS", "candidateDigest": candidate, "artifactDigest": artifact, "observedAt": _stamp(started, 58)},
            ],
            "staleCandidateProbe": {
                "candidateDigest": "0" * 64,
                "artifactDigest": "1" * 64,
                "outcome": "candidate_mismatch_rejected",
            },
            "remainingOpenGate": {
                "caseId": "PWK-018",
                "status": "PARTIAL",
                "candidateDigest": candidate,
                "artifactDigest": artifact,
            },
        },
        "service_acknowledgements": {
            "requiredServices": ["librechat-core"],
            "acknowledgedServices": ["librechat-core"],
            "missingServices": [],
            "restartState": "ready",
            "serviceAckDigest": service_status["serviceAckDigest"],
            "acknowledgements": acknowledgements,
        },
    }
    for ordinal, (kind, payload) in enumerate(documents.items(), start=70):
        unsigned = {
            "caseId": "REL-UC-004",
            "contractVersion": 1,
            "kind": kind,
            "candidateDigest": candidate,
            "artifactDigest": artifact,
            "ownerRefHash": owner,
            "sessionRef": session["sessionRef"],
            "observedAt": _stamp(started, ordinal),
            "payload": payload,
        }
        document = {**unsigned, "proof": _proof(unsigned, token)}
        relative = f"proof/{kind}.json"
        evidence.append({"kind": kind, "path": relative, "sha256": _private(evidence_root / relative, document)})

    manifest = {
        "caseId": "REL-UC-004",
        "contractVersion": 1,
        "environment": "installed_local_production",
        "runAt": _stamp(started, 110),
        "candidate": {"candidateDigest": candidate, "artifactDigest": artifact},
        "correlation": {"ownerRefHash": owner, "sessionRef": session["sessionRef"]},
        "evidence": evidence,
    }
    return {
        "verifier": verifier,
        "authority": authority,
        "candidate": candidate,
        "artifact": artifact,
        "manifest": manifest,
        "root": evidence_root,
        "started": started,
        "now": started + timedelta(seconds=115),
    }


def _assess(bundle: dict[str, object], **overrides: object) -> dict[str, object]:
    args = {
        "evidence_root": bundle["root"],
        "expected_candidate_digest": bundle["candidate"],
        "expected_artifact_digest": bundle["artifact"],
        "installed_owner_proven": True,
        "now": bundle["now"],
    }
    args.update(overrides)
    return bundle["verifier"].assess_manifest(bundle["manifest"], **args)


def _rewrite(bundle: dict[str, object], kind: str, mutate, *, resign: bool = True) -> None:
    entry = next(item for item in bundle["manifest"]["evidence"] if item["kind"] == kind)
    target = bundle["root"] / entry["path"]
    document = json.loads(target.read_text(encoding="utf-8"))
    mutate(document)
    if resign:
        unsigned = {key: value for key, value in document.items() if key != "proof"}
        document["proof"] = _proof(unsigned, str(bundle["authority"].session["caseToken"]))
    entry["sha256"] = _private(target, document)


def test_derives_all_installed_claim_paths_and_recorder_receipt(release_bundle):
    verifier = release_bundle["verifier"]
    result = _assess(release_bundle)
    receipt = verifier.receipt_manifest(result=result)
    assert verifier.CASE_ID == "REL-UC-004"
    assert verifier.VERIFIER_ID == "rel004-semantic-v1"
    assert result["status"] == "PASS"
    assert result["ready"] is True
    assert result["blockers"] == []
    assert result["claimPathCount"] == len(CLAIM_PATHS)
    assert result["claimObservationCount"] == len(CLAIM_PATHS) * 2
    assert result["surface"] == "cli"
    assert receipt == {
        "caseId": "REL-UC-004",
        "contractVersion": 1,
        "evidence": sorted(release_bundle["manifest"]["evidence"], key=lambda item: (item["kind"], item["path"])),
        "runAt": release_bundle["manifest"]["runAt"],
        "status": "PASS",
        "surface": "cli",
    }
    public = json.dumps({"result": {key: value for key, value in result.items() if not key.startswith("_")}, "receipt": receipt})
    assert str(release_bundle["root"]) not in public
    assert str(release_bundle["authority"].session["caseToken"]) not in public


def test_central_registration_and_writer_create_authenticated_case_receipt(
    release_bundle, monkeypatch: pytest.MonkeyPatch
):
    recorder = _load(RECORDER_SCRIPT, "rel004_focused_shared_recorder")
    registration = recorder.REGISTERED_SEMANTIC_VERIFIERS["REL-UC-004"]
    assert registration == {
        "id": "rel004-semantic-v1",
        "path": Path("qa/release-readiness/scripts/rel_uc_004_semantic_verifier.py"),
    }
    source = release_bundle["authority"]
    original_loader = recorder._load_registered_verifier

    def bound_loader(path: Path, *, case_id: str):
        verifier = original_loader(path, case_id=case_id)
        authority = verifier._LiveAuthority(
            candidate_digest=source.candidate_digest,
            artifact_digest=source.artifact_digest,
            owner_ref_hash=source.owner_ref_hash,
            artifact_identity=source.artifact_identity,
            session=source.session,
            service_status=source.service_status,
            acknowledgements=source.acknowledgements,
            acknowledgement_module=source.acknowledgement_module,
            process_probe=source.process_probe,
            readiness_facts=source.readiness_facts,
            fault_backup_present=source.fault_backup_present,
        )
        monkeypatch.setattr(verifier, "probe_live_authority", lambda **_kwargs: authority)
        return verifier

    monkeypatch.setattr(recorder, "_load_registered_verifier", bound_loader)
    semantic_path = release_bundle["root"] / "semantic-manifest.json"
    semantic_digest = _private(semantic_path, release_bundle["manifest"])
    manifest = release_bundle["verifier"].receipt_manifest(result=_assess(release_bundle))
    manifest["verifier"] = {"id": "rel004-semantic-v1", "manifest": "semantic-manifest.json"}
    receipt_path = release_bundle["root"] / "result.json"
    _private(receipt_path, manifest)

    result = recorder.record_case_receipt(
        manifest_path=receipt_path,
        evidence_root=release_bundle["root"],
        artifact_identity=source.artifact_identity,
        existing_receipts={"contractVersion": 1, "receipts": []},
        required_case_ids={"REL-UC-004"},
        local_qa_request={"contractVersion": 1, "mode": "local-qa", "requested": True},
        service_ack_status=source.service_status,
        service_ack_validator=lambda: dict(source.service_status),
        attestation_authority=(
            hashlib.sha256(b"synthetic-recorder-attestation-key").digest(),
            source.owner_ref_hash,
        ),
        installed_owner_proven=True,
        now=release_bundle["now"],
    )

    receipt = result["receipts"][0]
    assert receipt["caseId"] == "REL-UC-004"
    assert receipt["verifierId"] == "rel004-semantic-v1"
    assert receipt["verifierManifestSha256"] == semantic_digest
    assert receipt["serviceAckDigest"] == source.service_status["serviceAckDigest"]
    assert receipt["serviceAckSessionRef"] == source.session["sessionRef"]


@pytest.mark.parametrize(
    ("name", "value"),
    (("installed_owner_proven", False), ("expected_candidate_digest", "0" * 64), ("expected_artifact_digest", "0" * 64)),
)
def test_rejects_wrong_owner_candidate_or_artifact(release_bundle, name, value):
    with pytest.raises(ValueError, match="owner|candidate|artifact"):
        _assess(release_bundle, **{name: value})


@pytest.mark.parametrize(
    "mutation",
    (
        lambda manifest: manifest.update(status="PASS"),
        lambda manifest: manifest.update(environment="source_checkout"),
        lambda manifest: manifest["correlation"].update(ownerRefHash=_digest("foreign-owner")),
        lambda manifest: manifest["correlation"].update(sessionRef="qa_" + "0" * 24),
        lambda manifest: manifest.update(runAt="2026-08-22T13:00:00.000+00:00"),
        lambda manifest: manifest["evidence"].append(copy.deepcopy(manifest["evidence"][0])),
    ),
)
def test_rejects_self_declared_stale_duplicate_or_foreign_manifest(release_bundle, mutation):
    mutation(release_bundle["manifest"])
    with pytest.raises(ValueError):
        _assess(release_bundle)


@pytest.mark.parametrize(
    ("kind", "mutation"),
    (
        ("fault_injection", lambda payload: payload.update(storageProbe="real_disk_fill")),
        ("fault_injection", lambda payload: payload["injected"]["promptLayers"].update(status="verified")),
        ("fault_injection", lambda payload: payload["injected"]["storagePressure"].update(status="healthy")),
        ("fault_injection", lambda payload: payload["backup"].update(sessionRef="qa_" + "0" * 24)),
        ("gate_evaluator", lambda payload: payload["injected"]["openGates"].clear()),
        ("gate_evaluator", lambda payload: payload["injected"]["blockingChecks"].pop()),
        ("gate_evaluator", lambda payload: payload["configDefaults"]["source"].update(availability=True)),
        ("gate_evaluator", lambda payload: payload["recovered"]["openGates"].clear()),
        ("installed_identity", lambda payload: payload["build"].update(apiBuildSha256=_digest("foreign-build"))),
    ),
)
def test_rejects_missing_injected_blocker_default_exposure_or_wrong_identity(release_bundle, kind, mutation):
    _rewrite(release_bundle, kind, lambda document: mutation(document["payload"]))
    result = _assess(release_bundle)
    assert result["status"] != "PASS"
    with pytest.raises(ValueError):
        release_bundle["verifier"].receipt_manifest(result=result)


@pytest.mark.parametrize(
    "mutation",
    (
        lambda claims: claims.pop(),
        lambda claims: claims[0].update(blockerIds=["PWK-018"]),
        lambda claims: claims[0].update(releaseReady=True),
        lambda claims: claims[0].update(completionClaimed=True),
        lambda claims: claims[0].update(parallelAvailable=True),
        lambda claims: claims[0].update(defaultMode="parallel"),
        lambda claims: claims[0].update(surface="web"),
        lambda claims: claims[0].update(label="READY"),
    ),
)
def test_every_supported_claim_path_fails_closed_with_exact_visible_blockers(release_bundle, mutation):
    _rewrite(release_bundle, "release_claim_matrix", lambda document: mutation(document["payload"]["claims"]))
    result = _assess(release_bundle)
    assert result["status"] != "PASS"


@pytest.mark.parametrize(
    ("kind", "mutation"),
    (
        ("public_cli_capture", lambda payload: payload["captures"][0].update(exitCode=0)),
        ("install_summary_capture", lambda payload: payload["captures"][0].update(output="Ready")),
        ("web_status_observation", lambda payload: payload["captures"][0].update(captureMethod="api_fixture")),
        ("telegram_status_observation", lambda payload: payload["captures"][0].update(captureOrigin="invented_screenshot")),
        ("web_status_observation", lambda payload: payload["captures"][0].update(observedAt="2026-08-23T13:00:00.000+00:00")),
    ),
)
def test_rejects_missing_visible_proof_fake_capture_or_stale_observation(release_bundle, kind, mutation):
    _rewrite(release_bundle, kind, lambda document: mutation(document["payload"]))
    result = _assess(release_bundle)
    assert result["status"] != "PASS"


@pytest.mark.parametrize(
    "mutation",
    (
        lambda payload: payload["currentCandidateEvidence"][0].update(candidateDigest="0" * 64),
        lambda payload: payload["currentCandidateEvidence"].pop(),
        lambda payload: payload["remainingOpenGate"].update(status="PASS"),
        lambda payload: payload["staleCandidateProbe"].update(outcome="accepted"),
        lambda payload: payload.update(faultBackupPresent=True),
        lambda payload: payload["restoredFacts"]["promptLayers"].update(status="mismatch"),
    ),
)
def test_recovery_accepts_only_current_candidate_evidence_and_keeps_owned_gate_open(release_bundle, mutation):
    _rewrite(release_bundle, "recovery_evidence", lambda document: mutation(document["payload"]))
    result = _assess(release_bundle)
    assert result["status"] != "PASS"


def test_rejects_forged_or_missing_service_restart_acknowledgement(release_bundle):
    _rewrite(
        release_bundle,
        "service_acknowledgements",
        lambda document: document["payload"]["acknowledgements"][0].update(proof="hmac-sha256:" + "0" * 64),
    )
    with pytest.raises(ValueError, match="acknowledgement"):
        _assess(release_bundle)


def test_rejects_forged_evidence_signature(release_bundle):
    _rewrite(release_bundle, "gate_evaluator", lambda document: document["payload"]["injected"].update(label="READY"), resign=False)
    with pytest.raises(ValueError, match="signature"):
        _assess(release_bundle)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("ownerRefHash", _digest("synthetic-foreign-owner")),
        ("candidateDigest", "0" * 64),
        ("artifactDigest", "0" * 64),
        ("sessionRef", "qa_" + "0" * 24),
        ("observedAt", "2026-08-23T12:00:00.000+00:00"),
    ),
)
def test_rejects_foreign_or_stale_signed_document(release_bundle, field, value):
    _rewrite(
        release_bundle,
        "release_claim_matrix",
        lambda document: document.update({field: value}),
    )
    with pytest.raises(ValueError, match="owner|candidate|artifact|session|timestamp"):
        _assess(release_bundle)


def test_rejects_fake_screenshot_and_private_path(release_bundle):
    image = next(item for item in release_bundle["manifest"]["evidence"] if item["kind"] == "web_status_screenshot_injected")
    image["sha256"] = _private(release_bundle["root"] / image["path"], b"synthetic screenshot bytes")
    with pytest.raises(ValueError, match="screenshot"):
        _assess(release_bundle)

    image["sha256"] = _private(release_bundle["root"] / image["path"], _png(1))
    synthetic_private_path = "/" + "Users/synthetic-private/install Ready"
    _rewrite(
        release_bundle,
        "install_summary_capture",
        lambda document: document["payload"]["captures"][0].update(
            output=synthetic_private_path
        ),
    )
    with pytest.raises(ValueError, match="private"):
        _assess(release_bundle)


def test_rejects_blank_or_reused_visible_screenshot(release_bundle):
    entries = {
        item["kind"]: item
        for item in release_bundle["manifest"]["evidence"]
        if item["kind"]
        in {"web_status_screenshot_injected", "web_status_screenshot_recovered"}
    }
    injected = entries["web_status_screenshot_injected"]
    injected_path = release_bundle["root"] / injected["path"]
    injected["sha256"] = _private(injected_path, _png(1, uniform=True))
    with pytest.raises(ValueError, match="screenshot"):
        _assess(release_bundle)

    recovered = entries["web_status_screenshot_recovered"]
    recovered_path = release_bundle["root"] / recovered["path"]
    injected["sha256"] = _private(injected_path, recovered_path.read_bytes())
    with pytest.raises(ValueError, match="screenshot"):
        _assess(release_bundle)


@pytest.mark.parametrize("exposed", ("root", "directory", "file"))
def test_rejects_world_readable_private_evidence(release_bundle, exposed):
    root = release_bundle["root"]
    if exposed == "root":
        target = root
    elif exposed == "directory":
        target = root / "captures"
    else:
        entry = next(
            item
            for item in release_bundle["manifest"]["evidence"]
            if item["kind"] == "web_status_screenshot_injected"
        )
        target = root / entry["path"]
    target.chmod(0o755 if exposed != "file" else 0o644)

    with pytest.raises(ValueError, match="private evidence"):
        _assess(release_bundle)


def test_rejects_copied_or_mutated_derived_receipt(release_bundle):
    verifier = release_bundle["verifier"]
    result = _assess(release_bundle)
    with pytest.raises(ValueError):
        verifier.receipt_manifest(result=dict(result))
    result["surface"] = "telegram"
    with pytest.raises(ValueError):
        verifier.receipt_manifest(result=result)


def test_private_receipt_writer_rejects_symlinked_parent(release_bundle):
    root = release_bundle["root"]
    outside = root.parent / "outside-private-evidence"
    outside.mkdir(mode=0o700)
    (root / "escaped-receipts").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="receipt path"):
        release_bundle["verifier"]._write_receipt(
            Path("escaped-receipts/receipt.json"),
            root=root,
            payload={"caseId": "REL-UC-004"},
        )
    assert not (outside / "receipt.json").exists()


def test_executable_validates_manifest_and_writes_private_recorder_receipt(
    release_bundle, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
):
    verifier = release_bundle["verifier"]
    root = release_bundle["root"]
    manifest_path = root / "semantic-manifest.json"
    _private(manifest_path, release_bundle["manifest"])
    frozen_now = release_bundle["now"]

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return frozen_now.astimezone(tz) if tz else frozen_now.replace(tzinfo=None)

    monkeypatch.setattr(verifier, "datetime", FrozenDatetime)
    status = verifier.main(
        [
            "--manifest",
            str(manifest_path),
            "--evidence-root",
            str(root),
            "--receipt-manifest",
            "receipts/recorder.json",
        ]
    )

    output = json.loads(capsys.readouterr().out)
    receipt_path = root / "receipts/recorder.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert status == 0
    assert output["caseId"] == "REL-UC-004"
    assert output["status"] == "PASS"
    assert receipt["verifier"] == {
        "id": "rel004-semantic-v1",
        "manifest": "semantic-manifest.json",
    }
    assert receipt_path.stat().st_mode & 0o777 == 0o600
    assert receipt_path.parent.stat().st_mode & 0o777 == 0o700
    assert str(root) not in json.dumps(output)
    assert release_bundle["authority"].session["caseToken"] not in json.dumps(output)


def test_executable_reports_not_run_without_claiming_readiness():
    completed = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, check=False)
    assert completed.returncode != 0
    payload = json.loads(completed.stdout)
    assert payload["caseId"] == "REL-UC-004"
    assert payload["status"] == "NOT_RUN"
    assert payload["ready"] is False
