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
SCRIPT = ROOT / "qa/telegram-runtime/scripts/tr026_installed_journey_semantic_verifier.py"
ACK_SCRIPT = ROOT / "scripts/viventium/local_qa_service_ack.py"
RECORDER_SCRIPT = ROOT / "scripts/viventium/parallel_work_qa_evidence.py"
SERVICES = ("librechat-core", "telegram-bot")


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
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _stamp(started: datetime, seconds: float) -> str:
    return (started + timedelta(seconds=seconds)).isoformat(timespec="milliseconds")


def _backdated(value: str) -> str:
    return (datetime.fromisoformat(value) - timedelta(days=2)).isoformat(
        timespec="milliseconds"
    )


def _proof(unsigned: dict[str, object], token: str) -> str:
    key = base64.urlsafe_b64decode(token + "=")
    encoded = json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
    return "hmac-sha256:" + hmac.new(key, encoded, hashlib.sha256).hexdigest()


def _png(variant: int, *, uniform: bool = False) -> bytes:
    width, height = 640, 360
    rows = bytearray()
    for row in range(height):
        rows.append(0)
        rows.extend(
            0 if uniform else (column + row + variant * 29) % 256
            for column in range(width)
        )

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


def _private(path: Path, payload: object) -> str:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    raw = (
        payload
        if isinstance(payload, bytes)
        else (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    )
    path.write_bytes(raw)
    path.chmod(0o600)
    return hashlib.sha256(raw).hexdigest()


def _acknowledgements(session: dict[str, object], started: datetime):
    records = []
    processes: dict[int, dict[str, object]] = {}
    for offset, service in enumerate(SERVICES, start=1):
        process = {
            "pid": 4000 + offset,
            "startedAt": _stamp(started, offset),
            "startMarker": "sha256:" + _digest(f"synthetic-process-{service}"),
            "executablePath": f"/usr/bin/synthetic-{service}",
            "executableSha256": "sha256:" + _digest(f"synthetic-executable-{service}"),
        }
        unsigned = {
            "acknowledgedAt": _stamp(started, offset + 2),
            "artifactIdentityDigest": session["artifactIdentityDigest"],
            "caseId": "TR-026",
            "componentArtifactDigest": session["componentArtifactDigest"],
            "contractVersion": 1,
            "installedRootHash": session["installedRootHash"],
            "processIdentity": process,
            "serviceId": service,
            "sessionRef": session["sessionRef"],
        }
        records.append({**unsigned, "proof": _proof(unsigned, str(session["caseToken"]))})
        processes[int(process["pid"])] = process
    return records, processes


def _audit(session: dict[str, object], started: datetime) -> list[dict[str, object]]:
    token = str(session["caseToken"])
    records: list[dict[str, object]] = []
    previous = "0" * 64
    for index, (outcome, reason) in enumerate(
        (("claimed", "exact_structured_target"), ("delay_requested", "core_admission_boundary")),
        start=1,
    ):
        unsigned = {
            "schema_version": 3,
            "case_id": "TR-026",
            "artifact_ref": _digest(token)[:16],
            "session_ref": session["sessionRef"],
            "ledger_semantics": "owner_mutable_append_only_tamper_evident",
            "chain_index": index,
            "previous_record_hash": previous,
            "recorded_at_ms": int((started + timedelta(seconds=10 + index)).timestamp() * 1000),
            "outcome": outcome,
            "reason": reason,
            "configured_delay_ms": 280,
            "observed_delay_ms": 0,
            "event_digest": _digest("synthetic-source-event"),
        }
        encoded = json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
        previous = hmac.new(token.encode(), encoded, hashlib.sha256).hexdigest()
        records.append({**unsigned, "record_hash": previous})
    return records


def _source_trace(started: datetime, turn: str) -> dict[str, object]:
    return {
        "turnRefHash": turn,
        "events": [
            {"event": "user_message_observed", "at": _stamp(started, 10), "messageId": 12345, "sourceSequence": 100},
            {"event": "user_message_observed", "at": _stamp(started, 11), "messageId": 12346, "sourceSequence": 101},
            {"event": "stale_send_committed", "at": _stamp(started, 12), "messageId": 12347, "sourceSequence": 100},
            {"event": "core_ingestion_admitted", "at": _stamp(started, 12.280), "messageId": 12346, "sourceSequence": 101, "delayMs": 280},
            {"event": "stale_presentation_retracted", "at": _stamp(started, 13), "messageId": 12347, "sourceSequence": 100},
            {"event": "corrected_final_presented", "at": _stamp(started, 14), "messageId": 12348, "sourceSequence": 101},
        ],
    }


def _core_trace(started: datetime, turn: str) -> dict[str, object]:
    scenarios = []
    for index, (name, order, outcome) in enumerate(
        (
            ("source_order_normal", [100, 101], None),
            ("source_order_reversed", [101, 100], "source_order_superseded"),
        )
    ):
        offset = 11 + index * 9
        scenarios.append(
            {
                "id": name,
                "sourceOrder": [100, 101],
                "admissionOrder": order,
                "sourceObservedAt": _stamp(started, offset),
                "staleCommittedAt": _stamp(started, offset + 1),
                "higherAdmittedAt": _stamp(started, offset + 1.280),
                "staleRetractedAt": _stamp(started, offset + 2),
                "correctedCommittedAt": _stamp(started, offset + 3),
                "initialTurnRefHash": turn,
                "correctedTurnRefHash": turn,
                "initialRevision": 1,
                "correctedRevision": 2,
                "staleMessageId": 12347,
                "finalMessageId": 12348,
                "lowerAdmissionOutcome": outcome,
            }
        )
    return {
        "scenarios": scenarios,
        "postCommitControl": {
            "previousCommittedAt": _stamp(started, 32),
            "sourceObservedAt": _stamp(started, 33),
            "previousTurnRefHash": turn,
            "followUpTurnRefHash": _digest("synthetic-follow-up-turn"),
            "followUpRevision": 1,
        },
    }


def _history(turn: str) -> dict[str, object]:
    messages = [
        {"role": "user", "messageId": 12345, "sourceSequence": 100, "turnRefHash": turn, "textSha256": _digest("synthetic-user-one")},
        {"role": "user", "messageId": 12346, "sourceSequence": 101, "turnRefHash": turn, "textSha256": _digest("synthetic-user-two")},
        {"role": "assistant", "messageId": 12348, "sourceSequence": 101, "turnRefHash": turn, "revision": 2, "textSha256": _digest("synthetic-corrected-answer")},
    ]
    tombstones = [
        {"messageId": 12347, "sourceSequence": 100, "turnRefHash": turn, "revision": 1, "state": "retracted"}
    ]
    return {
        "beforeReopen": {"messages": messages, "tombstones": tombstones},
        "afterReopen": {"messages": copy.deepcopy(messages), "tombstones": copy.deepcopy(tombstones)},
    }


@pytest.fixture
def installed_bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    verifier = _load(SCRIPT, "tr026_focused_installed_semantic_verifier")
    ack_module = _load(ACK_SCRIPT, "tr026_focused_service_ack")
    installed = tmp_path / "installed"
    installed.mkdir()
    identity_path = tmp_path / "artifact-identity.json"
    identity = write_artifact_identity(installed, identity_path)
    candidate, artifact = _load_release_gate()._qa_candidate_digests(identity)
    started = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
    token = base64.urlsafe_b64encode(b"t" * 32).decode().rstrip("=")
    session = {
        "artifactIdentityDigest": "sha256:" + _digest(identity_path.read_text(encoding="utf-8")),
        "caseId": "TR-026",
        "caseToken": token,
        "componentArtifactDigest": "sha256:" + _digest("synthetic-component"),
        "contractVersion": 1,
        "expiresAt": _stamp(started, 900),
        "installedRootHash": "sha256:" + _digest("synthetic-installed-root"),
        "mode": "tr-026",
        "modeVariable": "VIVENTIUM_TELEGRAM_LOCAL_QA_MODE",
        "sessionRef": "qa_" + _digest(token)[:24],
        "startedAt": _stamp(started, 0),
    }
    acknowledgements, processes = _acknowledgements(session, started)
    monkeypatch.setattr(
        ack_module,
        "_service_process_identity_valid",
        lambda service, pid, executable: (
            pid in processes
            and processes[pid]["executablePath"] == str(executable)
            and str(executable).endswith(service)
        ),
    )
    service_status = {
        "caseId": "TR-026",
        "expiresAt": session["expiresAt"],
        "mode": "tr-026",
        "sessionRef": session["sessionRef"],
        "restartState": "ready",
        "requiredServices": list(SERVICES),
        "acknowledgedServices": list(SERVICES),
        "missingServices": [],
        "serviceAckDigest": "sha256:" + _digest(acknowledgements),
    }
    owner = _digest("synthetic-installed-owner")
    audit = _audit(session, started)
    authority = verifier._LiveAuthority(
        candidate_digest=candidate,
        artifact_digest=artifact,
        owner_ref_hash=owner,
        artifact_identity=identity,
        session=session,
        service_status=service_status,
        acknowledgements=acknowledgements,
        acknowledgement_module=ack_module,
        process_probe=lambda pid, _path: processes[pid],
        live_audit=audit,
    )
    monkeypatch.setattr(verifier, "probe_live_authority", lambda **_kwargs: authority)

    evidence_root = tmp_path / "private-evidence"
    evidence_root.mkdir(mode=0o700)
    turn = _digest("synthetic-logical-turn")
    history = _history(turn)
    screenshots: dict[str, str] = {}
    evidence: list[dict[str, str]] = []
    for ordinal, kind in enumerate(
        ("telegram_ui_before", "telegram_ui_settled", "telegram_ui_reopened"), start=1
    ):
        relative = f"captures/{kind}.png"
        measured = _private(evidence_root / relative, _png(ordinal))
        screenshots[kind] = measured
        evidence.append({"kind": kind, "path": relative, "sha256": measured})

    def capture(phase: str, kind: str, seconds: float, messages: list[dict[str, object]]):
        return {
            "phase": phase,
            "observedAt": _stamp(started, seconds),
            "screenshotKind": kind,
            "screenshotSha256": screenshots[kind],
            "captureOrigin": "native_desktop_window_capture",
            "windowVisible": True,
            "bubbles": messages,
        }

    visible = history["beforeReopen"]["messages"]
    stale_visible = [
        *copy.deepcopy(visible[:2]),
        {
            "role": "assistant",
            "messageId": 12347,
            "sourceSequence": 100,
            "turnRefHash": turn,
            "revision": 1,
            "textSha256": _digest("synthetic-stale-answer"),
        },
    ]
    documents = {
        "installed_identity": verifier._identity_projection(authority),
        "telegram_source_trace": _source_trace(started, turn),
        "core_revision_trace": _core_trace(started, turn),
        "mongo_history": history,
        "telegram_ui_observation": {
            "captureMethod": "telegram_desktop_accessibility",
            "bundleId": "ru.keepcoder.Telegram",
            "surface": "telegram",
            "reopenAction": {"method": "native_conversation_reopen", "performedAt": _stamp(started, 15)},
            "captures": [
                capture("before_correction", "telegram_ui_before", 12.1, stale_visible),
                capture("settled", "telegram_ui_settled", 14.1, copy.deepcopy(visible)),
                capture("reopened", "telegram_ui_reopened", 16, copy.deepcopy(visible)),
            ],
        },
        "telegram_race_audit": {"records": audit},
        "service_acknowledgements": {
            "requiredServices": list(SERVICES),
            "acknowledgedServices": list(SERVICES),
            "missingServices": [],
            "restartState": "ready",
            "serviceAckDigest": service_status["serviceAckDigest"],
            "acknowledgements": acknowledgements,
        },
    }

    for ordinal, (kind, payload) in enumerate(documents.items(), start=40):
        unsigned = {
            "caseId": "TR-026",
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
        evidence.append(
            {"kind": kind, "path": relative, "sha256": _private(evidence_root / relative, document)}
        )

    manifest = {
        "caseId": "TR-026",
        "contractVersion": 1,
        "environment": "installed_local_production",
        "runAt": _stamp(started, 90),
        "candidate": {"candidateDigest": candidate, "artifactDigest": artifact},
        "correlation": {"ownerRefHash": owner, "sessionRef": session["sessionRef"], "turnRefHash": turn},
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
        "now": started + timedelta(seconds=95),
    }


def _assess(bundle: dict[str, object], **overrides: object) -> dict[str, object]:
    arguments = {
        "evidence_root": bundle["root"],
        "expected_candidate_digest": bundle["candidate"],
        "expected_artifact_digest": bundle["artifact"],
        "installed_owner_proven": True,
        "now": bundle["now"],
    }
    arguments.update(overrides)
    return bundle["verifier"].assess_manifest(bundle["manifest"], **arguments)


def _rewrite(bundle: dict[str, object], kind: str, mutate, *, resign: bool = True) -> None:
    entry = next(item for item in bundle["manifest"]["evidence"] if item["kind"] == kind)
    target = bundle["root"] / entry["path"]
    document = json.loads(target.read_text(encoding="utf-8"))
    mutate(document)
    if resign:
        unsigned = {key: value for key, value in document.items() if key != "proof"}
        document["proof"] = _proof(unsigned, str(bundle["authority"].session["caseToken"]))
    entry["sha256"] = _private(target, document)


def test_derives_owner_bound_installed_telegram_journey_and_recorder_receipt(installed_bundle):
    verifier = installed_bundle["verifier"]
    result = _assess(installed_bundle)
    receipt = verifier.receipt_manifest(result=result)

    assert verifier.CASE_ID == "TR-026"
    assert verifier.VERIFIER_ID == "tr026-semantic-v1"
    assert result["status"] == "PASS"
    assert result["ready"] is True
    assert result["blockers"] == []
    assert result["surface"] == "telegram"
    assert result["serviceAckDigest"] == installed_bundle["authority"].service_status["serviceAckDigest"]
    assert [item["id"] for item in result["gates"]] == list(verifier.REQUIRED_GATES)
    assert receipt == {
        "caseId": "TR-026",
        "contractVersion": 1,
        "evidence": sorted(installed_bundle["manifest"]["evidence"], key=lambda item: (item["kind"], item["path"])),
        "runAt": installed_bundle["manifest"]["runAt"],
        "status": "PASS",
        "surface": "telegram",
    }
    public = json.dumps({"result": {key: value for key, value in result.items() if not key.startswith("_")}, "receipt": receipt})
    assert str(installed_bundle["root"]) not in public
    assert str(installed_bundle["authority"].session["caseToken"]) not in public


def test_central_registration_and_writer_create_authenticated_case_receipt(
    installed_bundle, monkeypatch: pytest.MonkeyPatch
):
    recorder = _load(RECORDER_SCRIPT, "tr026_focused_shared_recorder")
    registration = recorder.REGISTERED_SEMANTIC_VERIFIERS["TR-026"]
    assert registration == {
        "id": "tr026-semantic-v1",
        "path": Path("qa/telegram-runtime/scripts/tr026_installed_journey_semantic_verifier.py"),
    }
    source = installed_bundle["authority"]
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
            live_audit=source.live_audit,
        )
        monkeypatch.setattr(verifier, "probe_live_authority", lambda **_kwargs: authority)
        return verifier

    monkeypatch.setattr(recorder, "_load_registered_verifier", bound_loader)
    semantic_path = installed_bundle["root"] / "semantic-manifest.json"
    semantic_digest = _private(semantic_path, installed_bundle["manifest"])
    manifest = installed_bundle["verifier"].receipt_manifest(result=_assess(installed_bundle))
    manifest["verifier"] = {"id": "tr026-semantic-v1", "manifest": "semantic-manifest.json"}
    receipt_path = installed_bundle["root"] / "result.json"
    _private(receipt_path, manifest)

    result = recorder.record_case_receipt(
        manifest_path=receipt_path,
        evidence_root=installed_bundle["root"],
        artifact_identity=source.artifact_identity,
        existing_receipts={"contractVersion": 1, "receipts": []},
        required_case_ids={"TR-026"},
        local_qa_request={"contractVersion": 1, "mode": "local-qa", "requested": True},
        service_ack_status=source.service_status,
        service_ack_validator=lambda: dict(source.service_status),
        attestation_authority=(
            hashlib.sha256(b"synthetic-recorder-attestation-key").digest(),
            source.owner_ref_hash,
        ),
        installed_owner_proven=True,
        now=installed_bundle["now"],
    )

    receipt = result["receipts"][0]
    assert receipt["caseId"] == "TR-026"
    assert receipt["verifierId"] == "tr026-semantic-v1"
    assert receipt["verifierManifestSha256"] == semantic_digest
    assert receipt["serviceAckDigest"] == source.service_status["serviceAckDigest"]
    assert receipt["serviceAckSessionRef"] == source.session["sessionRef"]


@pytest.mark.parametrize(
    ("name", "value"),
    (
        ("installed_owner_proven", False),
        ("expected_candidate_digest", "0" * 64),
        ("expected_artifact_digest", "0" * 64),
        ("expected_candidate_digest", "invalid"),
    ),
)
def test_rejects_missing_owner_or_wrong_installed_candidate(installed_bundle, name, value):
    with pytest.raises(ValueError, match="owner|candidate|artifact"):
        _assess(installed_bundle, **{name: value})


@pytest.mark.parametrize(
    "mutation",
    (
        lambda manifest: manifest.update(status="PASS"),
        lambda manifest: manifest.update(environment="source_checkout"),
        lambda manifest: manifest["correlation"].update(ownerRefHash=_digest("other-owner")),
        lambda manifest: manifest["correlation"].update(sessionRef="qa_" + "0" * 24),
        lambda manifest: manifest.update(runAt="2026-08-23T12:00:00.000+00:00"),
        lambda manifest: manifest.update(runAt="2026-08-25T12:10:00.000+00:00"),
        lambda manifest: manifest["evidence"].append(copy.deepcopy(manifest["evidence"][0])),
    ),
)
def test_rejects_declared_pass_stale_session_or_foreign_owner(installed_bundle, mutation):
    mutation(installed_bundle["manifest"])
    with pytest.raises(ValueError):
        _assess(installed_bundle)


@pytest.mark.parametrize(
    ("kind", "mutation"),
    (
        ("telegram_source_trace", lambda payload: payload["events"][1].update(messageId=12347)),
        ("telegram_source_trace", lambda payload: payload["events"][1].update(at="2026-08-25T12:00:13.000+00:00")),
        ("telegram_source_trace", lambda payload: payload["events"][3].update(delayMs=279)),
        ("telegram_source_trace", lambda payload: payload["events"][3].update(at="2026-08-25T12:00:12.279+00:00")),
        ("core_revision_trace", lambda payload: payload["scenarios"][0].update(correctedRevision=1)),
        ("core_revision_trace", lambda payload: payload["scenarios"][0].update(correctedTurnRefHash=_digest("independent-turn"))),
        ("core_revision_trace", lambda payload: payload["scenarios"][1].update(lowerAdmissionOutcome="accepted")),
        ("core_revision_trace", lambda payload: payload["postCommitControl"].update(followUpTurnRefHash=payload["postCommitControl"]["previousTurnRefHash"])),
        ("mongo_history", lambda payload: payload["beforeReopen"]["messages"].append(copy.deepcopy(payload["beforeReopen"]["messages"][2]))),
        ("mongo_history", lambda payload: payload["afterReopen"]["messages"].reverse()),
        ("mongo_history", lambda payload: payload["beforeReopen"]["tombstones"].clear()),
        ("telegram_ui_observation", lambda payload: payload.update(captureMethod="fixture_screenshot")),
        ("telegram_ui_observation", lambda payload: payload["captures"][2]["bubbles"].pop()),
        ("telegram_ui_observation", lambda payload: payload["captures"][1].update(captureOrigin="invented_screenshot")),
        ("installed_identity", lambda payload: payload["runtime"].update(runningServiceSha256=_digest("foreign-runtime"))),
    ),
)
def test_rejects_source_order_stale_correction_duplicate_answer_or_missing_visible_proof(installed_bundle, kind, mutation):
    _rewrite(installed_bundle, kind, lambda document: mutation(document["payload"]))
    result = _assess(installed_bundle)
    assert result["status"] != "PASS"
    with pytest.raises(ValueError):
        installed_bundle["verifier"].receipt_manifest(result=result)


@pytest.mark.parametrize(
    ("kind", "mutation"),
    (
        ("service_acknowledgements", lambda payload: payload["acknowledgements"][0].update(proof="hmac-sha256:" + "0" * 64)),
        ("service_acknowledgements", lambda payload: payload["acknowledgements"].pop()),
        ("service_acknowledgements", lambda payload: payload["acknowledgements"][0].update(acknowledgedAt="2026-08-25T12:02:00.000+00:00")),
        ("telegram_race_audit", lambda payload: payload["records"][1].update(record_hash="0" * 64)),
        ("telegram_race_audit", lambda payload: payload["records"][1].update(outcome="not_applied")),
    ),
)
def test_rejects_forged_or_late_service_ack_and_unauthenticated_race_audit(installed_bundle, kind, mutation):
    _rewrite(installed_bundle, kind, lambda document: mutation(document["payload"]))
    with pytest.raises(ValueError, match="acknowledgement|audit"):
        _assess(installed_bundle)


def test_rejects_forged_document_signature(installed_bundle):
    _rewrite(installed_bundle, "telegram_source_trace", lambda document: document["payload"].update(turnRefHash=_digest("forged-turn")), resign=False)
    with pytest.raises(ValueError, match="signature"):
        _assess(installed_bundle)


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
def test_rejects_foreign_or_stale_signed_document(installed_bundle, field, value):
    _rewrite(
        installed_bundle,
        "core_revision_trace",
        lambda document: document.update({field: value}),
    )
    with pytest.raises(ValueError, match="owner|candidate|artifact|session|timestamp"):
        _assess(installed_bundle)


@pytest.mark.parametrize(
    ("kind", "mutation"),
    (
        (
            "telegram_source_trace",
            lambda payload: [
                event.update(at=_backdated(event["at"]))
                for event in payload["events"]
            ],
        ),
        (
            "core_revision_trace",
            lambda payload: [
                scenario.update(
                    {
                        name: _backdated(scenario[name])
                        for name in (
                            "sourceObservedAt",
                            "staleCommittedAt",
                            "higherAdmittedAt",
                            "staleRetractedAt",
                            "correctedCommittedAt",
                        )
                    }
                )
                for scenario in payload["scenarios"]
            ],
        ),
        (
            "telegram_ui_observation",
            lambda payload: (
                [
                    capture.update(observedAt=_backdated(capture["observedAt"]))
                    for capture in payload["captures"]
                ],
                payload["reopenAction"].update(
                    performedAt=_backdated(payload["reopenAction"]["performedAt"])
                ),
            ),
        ),
    ),
)
def test_rejects_stale_nested_trace_or_visible_ui_timestamps(
    installed_bundle, kind, mutation
):
    _rewrite(installed_bundle, kind, lambda document: mutation(document["payload"]))
    result = _assess(installed_bundle)
    assert result["status"] != "PASS"


@pytest.mark.parametrize(
    "content",
    (b"synthetic screenshot bytes", b"\x89PNG\r\n\x1a\n", _png(1, uniform=True)),
)
def test_rejects_invented_or_invalid_screenshot_bytes(installed_bundle, content):
    entry = next(item for item in installed_bundle["manifest"]["evidence"] if item["kind"] == "telegram_ui_settled")
    entry["sha256"] = _private(installed_bundle["root"] / entry["path"], content)
    with pytest.raises(ValueError, match="screenshot"):
        _assess(installed_bundle)


def test_rejects_reused_visible_screenshot(installed_bundle):
    entries = {
        item["kind"]: item
        for item in installed_bundle["manifest"]["evidence"]
        if item["kind"] in {"telegram_ui_before", "telegram_ui_settled"}
    }
    source = installed_bundle["root"] / entries["telegram_ui_before"]["path"]
    target = installed_bundle["root"] / entries["telegram_ui_settled"]["path"]
    entries["telegram_ui_settled"]["sha256"] = _private(target, source.read_bytes())

    with pytest.raises(ValueError, match="screenshot"):
        _assess(installed_bundle)


def test_rejects_private_paths_in_signed_evidence(installed_bundle):
    synthetic_private_path = "/" + "Users/synthetic-private/Telegram"
    _rewrite(
        installed_bundle,
        "telegram_ui_observation",
        lambda document: document["payload"].update(bundleId=synthetic_private_path),
    )
    with pytest.raises(ValueError, match="private"):
        _assess(installed_bundle)


@pytest.mark.parametrize("exposed", ("root", "directory", "file"))
def test_rejects_world_readable_private_evidence(installed_bundle, exposed):
    root = installed_bundle["root"]
    if exposed == "root":
        target = root
    elif exposed == "directory":
        target = root / "captures"
    else:
        entry = next(
            item
            for item in installed_bundle["manifest"]["evidence"]
            if item["kind"] == "telegram_ui_before"
        )
        target = root / entry["path"]
    target.chmod(0o755 if exposed != "file" else 0o644)

    with pytest.raises(ValueError, match="private evidence"):
        _assess(installed_bundle)


def test_rejects_receipt_copy_and_mutated_derived_pass(installed_bundle):
    verifier = installed_bundle["verifier"]
    result = _assess(installed_bundle)
    with pytest.raises(ValueError):
        verifier.receipt_manifest(result=dict(result))
    result["surface"] = "web"
    with pytest.raises(ValueError):
        verifier.receipt_manifest(result=result)


def test_private_receipt_writer_rejects_symlinked_parent(installed_bundle):
    root = installed_bundle["root"]
    outside = root.parent / "outside-private-evidence"
    outside.mkdir(mode=0o700)
    (root / "escaped-receipts").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="receipt path"):
        installed_bundle["verifier"]._write_receipt(
            Path("escaped-receipts/receipt.json"),
            root=root,
            payload={"caseId": "TR-026"},
        )
    assert not (outside / "receipt.json").exists()


def test_executable_validates_manifest_and_writes_private_recorder_receipt(
    installed_bundle, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
):
    verifier = installed_bundle["verifier"]
    root = installed_bundle["root"]
    manifest_path = root / "semantic-manifest.json"
    _private(manifest_path, installed_bundle["manifest"])
    frozen_now = installed_bundle["now"]

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
    assert output["caseId"] == "TR-026"
    assert output["status"] == "PASS"
    assert receipt["verifier"] == {
        "id": "tr026-semantic-v1",
        "manifest": "semantic-manifest.json",
    }
    assert receipt_path.stat().st_mode & 0o777 == 0o600
    assert receipt_path.parent.stat().st_mode & 0o777 == 0o700
    assert str(root) not in json.dumps(output)
    assert installed_bundle["authority"].session["caseToken"] not in json.dumps(output)


def test_executable_reports_not_run_without_claiming_acceptance():
    completed = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, check=False)
    assert completed.returncode != 0
    payload = json.loads(completed.stdout)
    assert payload["caseId"] == "TR-026"
    assert payload["status"] == "NOT_RUN"
