from __future__ import annotations

import copy
import functools
import hashlib
import importlib.util
import json
import os
import subprocess
import struct
import sys
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "qa"
    / "telegram-document-attachments"
    / "scripts"
    / "worker_bee_file_parity_qa.py"
)
NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


def load_module(name: str = "worker_bee_file_parity_qa"):
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def canonical_digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def write_private(path: Path, content: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_bytes(content)
    path.chmod(0o600)
    return hashlib.sha256(content).hexdigest()


@functools.lru_cache(maxsize=8)
def synthetic_png(
    width: int = 640,
    height: int = 360,
    *,
    variant: int = 0,
    uniform: bool = False,
) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    rows = []
    for y in range(height):
        row = bytearray(b"\x00")
        for x in range(width):
            if uniform:
                row.extend((0x7F, 0x7F, 0x7F, 0xFF))
            else:
                row.extend(
                    (
                        (x + variant * 37) % 256,
                        (y * 3 + variant * 53) % 256,
                        (x + y + variant * 71) % 256,
                        0xFF,
                    )
                )
        rows.append(bytes(row))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"".join(rows), level=9))
        + chunk(b"IEND", b"")
    )


def complete_manifest(tmp_path: Path) -> tuple[dict[str, object], Path, str, str]:
    evidence_root = tmp_path / "private-evidence"
    evidence_root.mkdir(mode=0o700, parents=True)
    observed_at = (NOW - timedelta(minutes=2)).isoformat()
    output_bytes = b"synthetic worker artifact\n"
    output_sha256 = hashlib.sha256(output_bytes).hexdigest()
    candidate_digest = digest("candidate")
    artifact_digest = digest("installed artifact")
    owner_ref = digest("synthetic owner")
    work_ref = digest("synthetic work")
    run_ref = digest("synthetic terminal run")
    journey_ref = digest("journey")
    evidence: list[dict[str, object]] = []

    def add_evidence(
        evidence_id: str,
        kind: str,
        payload: bytes | dict[str, object],
        *,
        suffix: str,
    ) -> str:
        if isinstance(payload, dict):
            payload = (
                json.dumps(
                    {
                        "artifactDigest": artifact_digest,
                        "candidateDigest": candidate_digest,
                        "contractVersion": 1,
                        "journeyRefHash": journey_ref,
                        "kind": kind,
                        "observedAt": observed_at,
                        "ownerRefHash": owner_ref,
                        "payload": payload,
                        "runRefHash": run_ref,
                        "schema": "tgd010.semantic-evidence.v1",
                        "workRefHash": work_ref,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
                + b"\n"
            )
        relative = f"proof/{evidence_id}{suffix}"
        measured = write_private(evidence_root / relative, payload)
        evidence.append(
            {
                "artifactDigest": artifact_digest,
                "candidateDigest": candidate_digest,
                "evidenceId": evidence_id,
                "journeyRefHash": journey_ref,
                "kind": kind,
                "observedAt": observed_at,
                "ownerRefHash": owner_ref,
                "path": relative,
                "runRefHash": run_ref,
                "sha256": measured,
                "workRefHash": work_ref,
            }
        )
        return measured

    group_ref = digest("synthetic captioned group")
    same_name = digest("same-name.png")
    input_specs = [
        (
            "document",
            "document.txt",
            "TGDOC-DOC-01",
            b"document fixture bytes\n",
            "",
            "",
        ),
        (
            "image",
            "same-name.png",
            "TGDOC-IMAGE-01",
            b"first image fixture bytes\n",
            group_ref,
            digest("caption text"),
        ),
        (
            "image",
            "same-name.png",
            "TGDOC-IMAGE-02",
            b"second image fixture bytes\n",
            group_ref,
            "",
        ),
        ("audio", "audio.wav", "TGDOC-AUDIO-01", b"audio fixture bytes\n", "", ""),
        ("video", "video.mp4", "TGDOC-VIDEO-01", b"video fixture bytes\n", "", ""),
        (
            "prior_artifact",
            "prior.md",
            "TGDOC-PRIOR-01",
            b"prior artifact fixture bytes\n",
            "",
            "",
        ),
    ]
    inputs: list[dict[str, object]] = []
    for position, (family, filename, identity, content, group, caption) in enumerate(
        input_specs
    ):
        telegram_evidence_id = f"telegram-input-{position}"
        worker_evidence_id = f"worker-input-{position}"
        add_evidence(
            telegram_evidence_id,
            "telegram_input",
            content,
            suffix=".bin",
        )
        add_evidence(
            worker_evidence_id,
            "worker_input",
            content,
            suffix=".bin",
        )
        inputs.append(
            {
                "byteSha256": hashlib.sha256(content).hexdigest(),
                "captionSha256": caption,
                "family": family,
                "fileRefHash": digest(f"file ref {position}"),
                "groupRefHash": group,
                "nameSha256": (
                    same_name if filename == "same-name.png" else digest(filename)
                ),
                "ownerRefHash": owner_ref,
                "position": position,
                "sizeBytes": len(content),
                "telegramEvidenceId": telegram_evidence_id,
                "visibleIdentity": identity,
                "workerEvidenceId": worker_evidence_id,
            }
        )

    input_manifest_sha256 = canonical_digest(inputs)
    artifact_ref = digest("output artifact ref")
    output_identity = "TGDOC-OUTPUT-01.html"
    telegram_ui_sha = add_evidence(
        "telegram-ui", "telegram_ui", synthetic_png(variant=1), suffix=".png"
    )
    active_work_ui_sha = add_evidence(
        "active-work-ui", "active_work_ui", synthetic_png(variant=2), suffix=".png"
    )
    artifact_open_ui_sha = add_evidence(
        "artifact-open-ui", "artifact_open_ui", synthetic_png(variant=3), suffix=".png"
    )
    opened_artifact_sha = add_evidence(
        "opened-artifact", "opened_artifact", output_bytes, suffix=".bin"
    )
    assert opened_artifact_sha == output_sha256

    add_evidence(
        "telegram-upload-ledger",
        "telegram_upload_ledger",
        {
            "inputManifestSha256": input_manifest_sha256,
            "inputs": inputs,
            "logicalTurnRefHash": journey_ref,
        },
        suffix=".json",
    )
    add_evidence(
        "worker-materialization",
        "worker_materialization",
        {
            "inputManifestSha256": input_manifest_sha256,
            "inputs": copy.deepcopy(inputs),
            "materializedInputCount": len(inputs),
        },
        suffix=".json",
    )
    visible_identities = [str(item["visibleIdentity"]) for item in inputs]
    add_evidence(
        "telegram-ui-semantics",
        "telegram_ui_semantics",
        {
            "attachmentIdentities": visible_identities,
            "captureMethod": "telegram_desktop_accessibility",
            "completion": {
                "artifactRefHash": artifact_ref,
                "attachmentIdentity": output_identity,
                "count": 1,
                "queenAuthored": True,
                "runRefHash": run_ref,
                "workRefHash": work_ref,
            },
            "screenshotEvidenceId": "telegram-ui",
            "screenshotSha256": telegram_ui_sha,
            "visibleText": [
                "TGDOC-010",
                "Worker Bee completion",
                *visible_identities,
                output_identity,
            ],
        },
        suffix=".json",
    )
    add_evidence(
        "active-work-ui-semantics",
        "active_work_ui_semantics",
        {
            "artifactOpenScreenshotEvidenceId": "artifact-open-ui",
            "artifactOpenScreenshotSha256": artifact_open_ui_sha,
            "artifactRefHash": artifact_ref,
            "captureMethod": "headed_browser_accessibility",
            "openedArtifactEvidenceId": "opened-artifact",
            "openedArtifactSha256": output_sha256,
            "runRefHash": run_ref,
            "screenshotEvidenceId": "active-work-ui",
            "screenshotSha256": active_work_ui_sha,
            "visibleText": ["TGDOC-010", "Active Work", output_identity],
            "workRefHash": work_ref,
        },
        suffix=".json",
    )
    add_evidence(
        "artifact-ledger",
        "artifact_ledger",
        {
            "artifactRefHash": artifact_ref,
            "byteSha256": output_sha256,
            "openedArtifactEvidenceId": "opened-artifact",
            "runRefHash": run_ref,
            "sizeBytes": len(output_bytes),
            "state": "available",
            "visibleIdentity": output_identity,
            "workRefHash": work_ref,
        },
        suffix=".json",
    )
    primary_attempt = digest("primary attempt")
    fallback_attempt = digest("fallback attempt")
    add_evidence(
        "provider-attempts",
        "provider_attempts",
        {
            "attempts": [
                {
                    "attemptRefHash": primary_attempt,
                    "inputManifestSha256": input_manifest_sha256,
                    "ordinal": 0,
                    "runRefHash": run_ref,
                    "state": "quota_cooldown",
                    "workRefHash": work_ref,
                },
                {
                    "attemptRefHash": fallback_attempt,
                    "inputManifestSha256": input_manifest_sha256,
                    "ordinal": 1,
                    "runRefHash": run_ref,
                    "state": "completed",
                    "workRefHash": work_ref,
                },
            ],
            "inputManifestSha256": input_manifest_sha256,
        },
        suffix=".json",
    )
    control_receipt = digest("control receipt")
    add_evidence(
        "control-receipt",
        "control_receipt",
        {
            "accepted": True,
            "action": "steer",
            "inputManifestSha256": input_manifest_sha256,
            "receiptRefHash": control_receipt,
            "runRefHash": run_ref,
            "workRefHash": work_ref,
        },
        suffix=".json",
    )
    before_runtime = digest("runtime before")
    after_runtime = digest("runtime after")
    add_evidence(
        "restart-trace",
        "restart_trace",
        {
            "events": [
                {
                    "inputManifestSha256": input_manifest_sha256,
                    "ordinal": 0,
                    "runtimeRefHash": before_runtime,
                    "state": "stopped",
                    "workRefHash": work_ref,
                },
                {
                    "inputManifestSha256": input_manifest_sha256,
                    "ordinal": 1,
                    "runtimeRefHash": after_runtime,
                    "state": "recovered",
                    "workRefHash": work_ref,
                },
            ],
            "services": ["core", "glasshive", "telegram", "worker"],
            "workRefHash": work_ref,
        },
        suffix=".json",
    )
    add_evidence(
        "isolation-trace",
        "isolation_trace",
        {
            "inputManifestSha256": input_manifest_sha256,
            "probes": [
                {"result": "read_allowed", "subject": "intended_worker"},
                {"result": "worker_scope_denied", "subject": "sibling_worker"},
                {"result": "owner_scope_denied", "subject": "cross_owner"},
            ],
            "runRefHash": run_ref,
            "workRefHash": work_ref,
        },
        suffix=".json",
    )
    failure_cases = [
        ("missing_parser", "parser_unavailable", "not_supported"),
        ("missing_bytes", "input_bytes_missing", "recovered_same_work"),
        ("expired_link", "artifact_link_expired", "recovered_same_artifact"),
        (
            "delivery_unavailable",
            "delivery_unavailable",
            "delivered_same_artifact",
        ),
        ("cross_owner", "owner_scope_denied", "denied"),
    ]
    add_evidence(
        "failure-matrix",
        "failure_matrix",
        {
            "cases": [
                {
                    "attemptRefHash": digest(f"negative attempt {kind}"),
                    "kind": kind,
                    "ordinal": ordinal,
                    "recovery": recovery,
                    "result": result,
                    "runRefHash": run_ref,
                    "workRefHash": work_ref,
                }
                for ordinal, (kind, result, recovery) in enumerate(failure_cases)
            ],
            "runRefHash": run_ref,
            "workRefHash": work_ref,
        },
        suffix=".json",
    )
    delivery_kinds = [
        "artifact_delivery",
        "assistant_row",
        "delivery_receipt",
        "queen_completion",
        "telegram_bubble",
    ]
    add_evidence(
        "delivery-ledger",
        "delivery_ledger",
        {
            "artifactRefHash": artifact_ref,
            "events": [
                {
                    "artifactRefHash": artifact_ref,
                    "eventRefHash": digest(f"delivery event {kind}"),
                    "kind": kind,
                    "ordinal": ordinal,
                    "runRefHash": run_ref,
                    "state": "committed",
                    "workRefHash": work_ref,
                }
                for ordinal, kind in enumerate(delivery_kinds)
            ],
            "runRefHash": run_ref,
            "workRefHash": work_ref,
        },
        suffix=".json",
    )

    telegram_input_evidence = [str(item["telegramEvidenceId"]) for item in inputs]
    worker_input_evidence = [str(item["workerEvidenceId"]) for item in inputs]
    manifest: dict[str, object] = {
        "candidate": {
            "artifactDigest": artifact_digest,
            "candidateDigest": candidate_digest,
        },
        "caseId": "TGDOC-010",
        "contractVersion": 1,
        "correlation": {
            "journeyRefHash": journey_ref,
            "ownerRefHash": owner_ref,
            "runRefHash": run_ref,
            "workRefHash": work_ref,
        },
        "delivery": {
            "artifactDeliveryCount": 1,
            "artifactRefHash": artifact_ref,
            "assistantRowCount": 1,
            "deliveryReceiptCount": 1,
            "queenCompletionCount": 1,
            "state": "sent",
            "telegramBubbleCount": 1,
            "workRefHash": work_ref,
            "evidenceIds": ["delivery-ledger", "telegram-ui"],
        },
        "environment": "installed_local_production",
        "evidence": evidence,
        "failures": {
            "evidenceIds": ["failure-matrix"],
            "runRefHash": run_ref,
            "workRefHash": work_ref,
        },
        "fixture": {
            "kind": "synthetic_public_safe",
            "manifestSha256": input_manifest_sha256,
        },
        "inputs": {"telegram": inputs, "worker": copy.deepcopy(inputs)},
        "isolation": {
            "crossOwnerResult": "owner_scope_denied",
            "crossOwnerDenied": True,
            "evidenceIds": ["isolation-trace"],
            "intendedWorkerRead": True,
            "ownerRefHash": owner_ref,
            "siblingResult": "worker_scope_denied",
            "siblingDenied": True,
            "workRefHash": work_ref,
        },
        "output": {
            "activeWorkSha256": output_sha256,
            "artifactRefHash": artifact_ref,
            "byteSha256": output_sha256,
            "evidenceIds": [
                "active-work-ui-semantics",
                "artifact-ledger",
                "artifact-open-ui",
                "opened-artifact",
            ],
            "openedSha256": output_sha256,
            "openedSurfaces": ["telegram", "active_work"],
            "sizeBytes": len(output_bytes),
            "telegramSha256": output_sha256,
            "visibleIdentity": output_identity,
        },
        "resilience": {
            "control": {
                "accepted": True,
                "action": "steer",
                "evidenceIds": ["control-receipt"],
                "receiptRefHash": control_receipt,
                "workRefHash": work_ref,
            },
            "fallback": {
                "afterInputManifestSha256": input_manifest_sha256,
                "beforeInputManifestSha256": input_manifest_sha256,
                "evidenceIds": ["provider-attempts"],
                "exercised": True,
                "fallbackAttemptRefHash": fallback_attempt,
                "fallbackState": "completed",
                "primaryAttemptRefHash": primary_attempt,
                "primaryState": "quota_cooldown",
                "workRefHash": work_ref,
            },
            "restart": {
                "afterInputManifestSha256": input_manifest_sha256,
                "afterRuntimeRefHash": after_runtime,
                "beforeInputManifestSha256": input_manifest_sha256,
                "beforeRuntimeRefHash": before_runtime,
                "evidenceIds": ["restart-trace"],
                "performed": True,
                "recovered": True,
                "services": ["core", "glasshive", "telegram", "worker"],
                "workRefHash": work_ref,
            },
        },
        "runAt": (NOW - timedelta(minutes=1)).isoformat(),
        "surfaces": {
            "activeWork": {
                "evidenceIds": [
                    "active-work-ui",
                    "active-work-ui-semantics",
                    "artifact-open-ui",
                ],
                "headed": True,
                "linked": True,
                "opened": True,
                "workRefHash": work_ref,
            },
            "telegram": {
                "client": "telegram_desktop",
                "completionVisible": True,
                "evidenceIds": [
                    "telegram-ui",
                    "telegram-ui-semantics",
                    "telegram-upload-ledger",
                    *telegram_input_evidence,
                ],
                "installed": True,
                "workRefHash": work_ref,
            },
        },
        "worker": {
            "evidenceIds": ["worker-materialization", *worker_input_evidence],
            "inputManifestSha256": input_manifest_sha256,
            "materializedInputCount": len(inputs),
            "ownerRefHash": owner_ref,
            "workRefHash": work_ref,
        },
    }
    return manifest, evidence_root, candidate_digest, artifact_digest


def mutate_semantic_evidence(
    manifest: dict[str, object],
    evidence_root: Path,
    evidence_id: str,
    mutate,
) -> None:
    entry = next(
        item for item in manifest["evidence"] if item["evidenceId"] == evidence_id
    )
    path = evidence_root / entry["path"]
    document = json.loads(path.read_text(encoding="utf-8"))
    mutate(document)
    content = (
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
        + b"\n"
    )
    entry["sha256"] = write_private(path, content)


def assess(
    module, manifest: dict[str, object], root: Path, candidate: str, artifact: str
):
    return module.assess_manifest(
        manifest,
        evidence_root=root,
        expected_candidate_digest=candidate,
        expected_artifact_digest=artifact,
        installed_owner_proven=True,
        now=NOW,
    )


def test_missing_manifest_reports_not_run_for_every_required_gate(capsys) -> None:
    module = load_module("worker_bee_file_parity_not_run")

    exit_code = module.main([])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == module.EXIT_NOT_RUN
    assert output["caseId"] == "TGDOC-010"
    assert output["status"] == "NOT_RUN"
    assert output["ready"] is False
    assert {gate["id"] for gate in output["gates"]} == set(module.REQUIRED_GATES)
    assert {gate["status"] for gate in output["gates"]} == {"NOT_RUN"}


def test_complete_exact_candidate_bound_installed_contract_passes(
    tmp_path: Path,
) -> None:
    module = load_module("worker_bee_file_parity_pass")
    manifest, evidence_root, candidate, artifact = complete_manifest(tmp_path)

    result = assess(module, manifest, evidence_root, candidate, artifact)

    assert result["status"] == "PASS"
    assert result["ready"] is True
    assert result["candidateDigest"] == candidate
    assert result["artifactDigest"] == artifact
    assert result["blockers"] == []
    assert {gate["status"] for gate in result["gates"]} == {"PASS"}


@pytest.mark.parametrize(
    ("gate_id", "mutate"),
    [
        (
            "candidate_binding",
            lambda value: value["candidate"].update(candidateDigest=digest("wrong")),
        ),
        (
            "candidate_binding",
            lambda value: value["fixture"].update(manifestSha256=digest("wrong")),
        ),
        (
            "installed_telegram",
            lambda value: value["surfaces"]["telegram"].update(installed=False),
        ),
        (
            "worker_materialization",
            lambda value: value["worker"].update(materializedInputCount=0),
        ),
        (
            "linked_active_work",
            lambda value: value["surfaces"]["activeWork"].update(linked=False),
        ),
        ("input_hashes_order", lambda value: value["inputs"]["worker"].reverse()),
        (
            "output_hash_open",
            lambda value: value["output"].update(activeWorkSha256=digest("wrong")),
        ),
        (
            "provider_fallback",
            lambda value: value["resilience"]["fallback"].update(exercised=False),
        ),
        (
            "provider_fallback",
            lambda value: value["resilience"]["fallback"].update(
                fallbackAttemptRefHash=value["resilience"]["fallback"][
                    "primaryAttemptRefHash"
                ]
            ),
        ),
        (
            "worker_control",
            lambda value: value["resilience"]["control"].update(accepted=False),
        ),
        (
            "restart_recovery",
            lambda value: value["resilience"]["restart"].update(recovered=False),
        ),
        (
            "restart_recovery",
            lambda value: value["resilience"]["restart"].update(
                afterInputManifestSha256=digest("wrong")
            ),
        ),
        (
            "owner_isolation",
            lambda value: value["isolation"].update(crossOwnerDenied=False),
        ),
        (
            "owner_isolation",
            lambda value: value["isolation"].update(crossOwnerResult="allowed"),
        ),
        (
            "negative_failures",
            lambda value: value["failures"].update(runRefHash=digest("wrong")),
        ),
        (
            "single_delivery",
            lambda value: value["delivery"].update(telegramBubbleCount=2),
        ),
    ],
)
def test_every_required_proof_gate_fails_closed(
    tmp_path: Path, gate_id: str, mutate
) -> None:
    module = load_module(f"worker_bee_file_parity_{gate_id}")
    manifest, evidence_root, candidate, artifact = complete_manifest(tmp_path)
    mutate(manifest)

    result = assess(module, manifest, evidence_root, candidate, artifact)

    assert result["status"] == "PARTIAL"
    assert result["ready"] is False
    assert gate_id in result["blockers"]
    assert (
        next(gate for gate in result["gates"] if gate["id"] == gate_id)["status"]
        == "PARTIAL"
    )


def test_input_matrix_requires_all_families_same_name_distinction_and_captioned_group(
    tmp_path: Path,
) -> None:
    module = load_module("worker_bee_file_parity_input_matrix")
    manifest, evidence_root, candidate, artifact = complete_manifest(tmp_path)
    telegram_inputs = manifest["inputs"]["telegram"]
    worker_inputs = manifest["inputs"]["worker"]
    for items in (telegram_inputs, worker_inputs):
        for item in items:
            if item["family"] == "video":
                item["family"] = "document"
            item["nameSha256"] = digest(f"unique-{item['position']}")
            item["captionSha256"] = ""
            item["groupRefHash"] = ""
    updated_digest = canonical_digest(telegram_inputs)
    manifest["fixture"]["manifestSha256"] = updated_digest
    manifest["worker"]["inputManifestSha256"] = updated_digest
    manifest["worker"]["materializedInputCount"] = len(telegram_inputs)
    manifest["resilience"]["fallback"]["beforeInputManifestSha256"] = updated_digest
    manifest["resilience"]["fallback"]["afterInputManifestSha256"] = updated_digest
    manifest["resilience"]["restart"]["beforeInputManifestSha256"] = updated_digest
    manifest["resilience"]["restart"]["afterInputManifestSha256"] = updated_digest

    result = assess(module, manifest, evidence_root, candidate, artifact)

    assert result["status"] == "PARTIAL"
    assert "input_hashes_order" in result["blockers"]


def test_tampered_or_outside_evidence_is_rejected_not_downgraded_to_ui_proof(
    tmp_path: Path,
) -> None:
    module = load_module("worker_bee_file_parity_tamper")
    manifest, evidence_root, candidate, artifact = complete_manifest(tmp_path)
    (evidence_root / "proof" / "telegram-ui.png").write_bytes(b"tampered")
    (evidence_root / "proof" / "telegram-ui.png").chmod(0o600)

    with pytest.raises(module.EvidenceContractError, match="evidence_contract_invalid"):
        assess(module, manifest, evidence_root, candidate, artifact)

    outside = tmp_path / "outside.json"
    write_private(outside, b"outside")
    manifest, evidence_root, candidate, artifact = complete_manifest(
        tmp_path / "second"
    )
    manifest["evidence"][0]["path"] = str(outside)
    manifest["evidence"][0]["sha256"] = hashlib.sha256(b"outside").hexdigest()
    with pytest.raises(module.EvidenceContractError, match="evidence_contract_invalid"):
        assess(module, manifest, evidence_root, candidate, artifact)


def test_total_evidence_bytes_are_bounded_not_only_each_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_module("worker_bee_file_parity_total_bytes")
    manifest, evidence_root, candidate, artifact = complete_manifest(tmp_path)
    largest_file = max(
        (evidence_root / item["path"]).stat().st_size for item in manifest["evidence"]
    )
    monkeypatch.setattr(module, "MAX_EVIDENCE_BYTES", largest_file + 1)

    with pytest.raises(module.EvidenceContractError, match="evidence_contract_invalid"):
        assess(module, manifest, evidence_root, candidate, artifact)


def test_ui_evidence_must_be_an_actual_bounded_png_capture(tmp_path: Path) -> None:
    module = load_module("worker_bee_file_parity_ui_capture")
    manifest, evidence_root, candidate, artifact = complete_manifest(tmp_path)
    fake_capture = b'{"not":"a headed UI capture"}\n'
    capture = evidence_root / "proof" / "telegram-ui.png"
    write_private(capture, fake_capture)
    telegram_evidence = next(
        item for item in manifest["evidence"] if item["evidenceId"] == "telegram-ui"
    )
    telegram_evidence["sha256"] = hashlib.sha256(fake_capture).hexdigest()

    with pytest.raises(module.EvidenceContractError, match="evidence_contract_invalid"):
        assess(module, manifest, evidence_root, candidate, artifact)


def test_uniform_png_cannot_count_as_visible_ui_evidence() -> None:
    module = load_module("worker_bee_file_parity_uniform_png")

    assert module._valid_png_capture(synthetic_png(uniform=True)) is False


def test_png_capture_facts_come_from_decoded_pixels() -> None:
    module = load_module("worker_bee_file_parity_png_facts")

    facts = module._png_capture_facts(synthetic_png(width=640, height=360, variant=4))

    assert facts is not None
    assert facts["width"] == 640
    assert facts["height"] == 360
    assert facts["uniqueColors"] >= 8
    assert facts["differentPixels"] >= 256


def test_png_capture_rejects_small_dimensions_and_bad_crc() -> None:
    module = load_module("worker_bee_file_parity_png_integrity")
    assert module._png_capture_facts(synthetic_png(width=639, height=360)) is None

    corrupted = bytearray(synthetic_png(width=640, height=360, variant=5))
    corrupted[-13] ^= 0x01
    assert module._png_capture_facts(bytes(corrupted)) is None

    unknown_kind = b"ABCD"
    unknown_payload = b"unsupported critical data"
    unknown_chunk = (
        struct.pack(">I", len(unknown_payload))
        + unknown_kind
        + unknown_payload
        + struct.pack(">I", zlib.crc32(unknown_kind + unknown_payload) & 0xFFFFFFFF)
    )
    original = synthetic_png(width=640, height=360, variant=6)
    with_unknown_critical_chunk = original[:33] + unknown_chunk + original[33:]
    assert module._png_capture_facts(with_unknown_critical_chunk) is None


def test_caller_declared_json_cannot_count_as_semantic_evidence(
    tmp_path: Path,
) -> None:
    module = load_module("worker_bee_file_parity_declared_json")
    evidence_root = tmp_path / "private-evidence"
    evidence_root.mkdir(mode=0o700)
    payload = b'{"synthetic":"caller-declared-pass"}\n'
    relative = "proof/worker-materialization.json"
    evidence = [
        {
            "artifactDigest": digest("installed artifact"),
            "candidateDigest": digest("candidate"),
            "evidenceId": "worker-materialization",
            "journeyRefHash": digest("journey"),
            "kind": "worker_materialization",
            "observedAt": (NOW - timedelta(minutes=2)).isoformat(),
            "ownerRefHash": digest("synthetic owner"),
            "path": relative,
            "runRefHash": digest("synthetic terminal run"),
            "sha256": write_private(evidence_root / relative, payload),
            "workRefHash": digest("synthetic work"),
        }
    ]

    with pytest.raises(module.EvidenceContractError, match="evidence_contract_invalid"):
        module._verify_evidence(
            evidence,
            evidence_root=evidence_root,
            run_at=NOW - timedelta(minutes=1),
            expected_candidate_digest=digest("candidate"),
            expected_artifact_digest=digest("installed artifact"),
            journey_ref=digest("journey"),
            owner_ref=digest("synthetic owner"),
            run_ref=digest("synthetic terminal run"),
            work_ref=digest("synthetic work"),
        )


def test_telegram_semantics_require_visible_text_and_attachment_identities(
    tmp_path: Path,
) -> None:
    module = load_module("worker_bee_file_parity_telegram_semantics")
    manifest, evidence_root, candidate, artifact = complete_manifest(tmp_path)

    def remove_identity(document: dict[str, object]) -> None:
        identity = document["payload"]["attachmentIdentities"].pop()
        document["payload"]["visibleText"].remove(identity)

    mutate_semantic_evidence(
        manifest, evidence_root, "telegram-ui-semantics", remove_identity
    )

    result = assess(module, manifest, evidence_root, candidate, artifact)

    assert result["status"] == "PARTIAL"
    assert "installed_telegram" in result["blockers"]
    assert "output_hash_open" in result["blockers"]
    assert "single_delivery" in result["blockers"]


@pytest.mark.parametrize("field", ["candidateDigest", "artifactDigest"])
def test_semantic_evidence_is_bound_to_candidate_and_installed_artifact(
    tmp_path: Path,
    field: str,
) -> None:
    module = load_module(f"worker_bee_file_parity_semantic_{field}")
    manifest, evidence_root, candidate, artifact = complete_manifest(tmp_path)
    mutate_semantic_evidence(
        manifest,
        evidence_root,
        "delivery-ledger",
        lambda document: document.update({field: digest(f"wrong {field}")}),
    )

    with pytest.raises(module.EvidenceContractError, match="evidence_contract_invalid"):
        assess(module, manifest, evidence_root, candidate, artifact)


def test_measured_worker_file_bytes_drive_exact_input_parity(tmp_path: Path) -> None:
    module = load_module("worker_bee_file_parity_measured_bytes")
    manifest, evidence_root, candidate, artifact = complete_manifest(tmp_path)
    worker_entry = next(
        item for item in manifest["evidence"] if item["evidenceId"] == "worker-input-2"
    )
    changed = b"different materialized worker bytes\n"
    worker_entry["sha256"] = write_private(
        evidence_root / worker_entry["path"], changed
    )

    result = assess(module, manifest, evidence_root, candidate, artifact)

    assert result["status"] == "PARTIAL"
    assert "worker_materialization" in result["blockers"]
    assert "input_hashes_order" in result["blockers"]


@pytest.mark.parametrize("field", ["workRefHash", "runRefHash"])
def test_every_semantic_record_requires_exact_work_and_run_correlation(
    tmp_path: Path,
    field: str,
) -> None:
    module = load_module(f"worker_bee_file_parity_correlation_{field}")
    manifest, evidence_root, candidate, artifact = complete_manifest(tmp_path)
    mutate_semantic_evidence(
        manifest,
        evidence_root,
        "provider-attempts",
        lambda document: document.update({field: digest(f"wrong {field}")}),
    )

    with pytest.raises(module.EvidenceContractError, match="evidence_contract_invalid"):
        assess(module, manifest, evidence_root, candidate, artifact)


def test_delivery_pass_is_derived_from_exact_correlated_events(
    tmp_path: Path,
) -> None:
    module = load_module("worker_bee_file_parity_delivery_events")
    manifest, evidence_root, candidate, artifact = complete_manifest(tmp_path)

    def duplicate_bubble(document: dict[str, object]) -> None:
        duplicate = copy.deepcopy(document["payload"]["events"][-1])
        duplicate["eventRefHash"] = digest("duplicate telegram bubble")
        duplicate["ordinal"] = len(document["payload"]["events"])
        document["payload"]["events"].append(duplicate)

    mutate_semantic_evidence(
        manifest, evidence_root, "delivery-ledger", duplicate_bubble
    )

    result = assess(module, manifest, evidence_root, candidate, artifact)

    assert manifest["delivery"]["telegramBubbleCount"] == 1
    assert result["status"] == "PARTIAL"
    assert "single_delivery" in result["blockers"]


def test_extra_artifact_cannot_be_hidden_in_an_unrelated_evidence_reference(
    tmp_path: Path,
) -> None:
    module = load_module("worker_bee_file_parity_extra_artifact")
    manifest, evidence_root, candidate, artifact = complete_manifest(tmp_path)
    opened = next(
        item for item in manifest["evidence"] if item["evidenceId"] == "opened-artifact"
    )
    extra = dict(opened)
    extra["evidenceId"] = "extra-opened-artifact"
    extra["path"] = "proof/extra-opened-artifact.bin"
    content = (evidence_root / opened["path"]).read_bytes()
    extra["sha256"] = write_private(evidence_root / extra["path"], content)
    manifest["evidence"].append(extra)
    manifest["delivery"]["evidenceIds"].append(extra["evidenceId"])

    with pytest.raises(module.EvidenceContractError, match="evidence_contract_invalid"):
        assess(module, manifest, evidence_root, candidate, artifact)


@pytest.mark.parametrize(
    ("case_kind", "field", "value"),
    [
        ("missing_parser", "result", "completed"),
        ("missing_bytes", "recovery", "new_work_created"),
        ("expired_link", "recovery", "dead_link_accepted"),
        ("delivery_unavailable", "result", "sent"),
        ("cross_owner", "result", "read_allowed"),
    ],
)
def test_each_negative_failure_case_is_required_for_pass(
    tmp_path: Path,
    case_kind: str,
    field: str,
    value: str,
) -> None:
    module = load_module(f"worker_bee_file_parity_negative_{case_kind}_{field}")
    manifest, evidence_root, candidate, artifact = complete_manifest(tmp_path)

    def change_case(document: dict[str, object]) -> None:
        target = next(
            item for item in document["payload"]["cases"] if item["kind"] == case_kind
        )
        target[field] = value

    mutate_semantic_evidence(manifest, evidence_root, "failure-matrix", change_case)

    result = assess(module, manifest, evidence_root, candidate, artifact)

    assert result["status"] == "PARTIAL"
    assert "negative_failures" in result["blockers"]


def test_receipt_manifest_is_emitted_only_from_fully_derived_pass(
    tmp_path: Path,
) -> None:
    module = load_module("worker_bee_file_parity_receipt")
    manifest, evidence_root, candidate, artifact = complete_manifest(tmp_path)
    result = assess(module, manifest, evidence_root, candidate, artifact)

    receipt = module.receipt_manifest(result=result)

    assert receipt == {
        "caseId": "TGDOC-010",
        "contractVersion": 1,
        "evidence": result["_receiptEvidence"],
        "runAt": manifest["runAt"],
        "status": "PASS",
        "surface": "telegram",
    }

    tampered_result = dict(result)
    tampered_result["_receiptEvidence"] = [
        dict(item) for item in result["_receiptEvidence"]
    ]
    tampered_result["_receiptEvidence"][0]["sha256"] = digest(
        "changed after assessment"
    )
    with pytest.raises(module.EvidenceContractError, match="evidence_contract_invalid"):
        module.receipt_manifest(result=tampered_result)

    manifest["delivery"]["telegramBubbleCount"] = 2
    partial = assess(module, manifest, evidence_root, candidate, artifact)
    with pytest.raises(module.EvidenceContractError, match="evidence_contract_invalid"):
        module.receipt_manifest(result=partial)


def test_caller_cannot_forge_a_pass_result_into_a_receipt_manifest() -> None:
    module = load_module("worker_bee_file_parity_forged_receipt")
    forged = {
        "_receiptEvidence": [
            {
                "kind": "telegram_ui",
                "path": "proof/telegram-ui.png",
                "sha256": digest("forged screenshot"),
            }
        ],
        "blockers": [],
        "caseId": "TGDOC-010",
        "contractVersion": 1,
        "gates": [
            {"evidenceIds": [], "id": gate_id, "status": "PASS"}
            for gate_id in module.REQUIRED_GATES
        ],
        "ready": True,
        "runAt": NOW.isoformat(),
        "status": "PASS",
    }

    with pytest.raises(module.EvidenceContractError, match="evidence_contract_invalid"):
        module.receipt_manifest(result=forged)


def test_cli_writes_receipt_only_for_a_fully_derived_pass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    module = load_module("worker_bee_file_parity_cli_receipt")
    manifest, evidence_root, candidate, artifact = complete_manifest(tmp_path)
    manifest_path = evidence_root / "journey.json"
    write_private(manifest_path, json.dumps(manifest).encode("utf-8"))
    monkeypatch.setattr(
        module,
        "_installed_binding",
        lambda **_kwargs: (candidate, artifact, True),
    )
    monkeypatch.setattr(
        module,
        "_manifest_inside_root",
        lambda _manifest_path, _evidence_root: manifest,
    )
    original_assess_manifest = module.assess_manifest
    monkeypatch.setattr(
        module,
        "assess_manifest",
        lambda *_args, **_kwargs: original_assess_manifest(
            manifest,
            evidence_root=evidence_root,
            expected_candidate_digest=candidate,
            expected_artifact_digest=artifact,
            installed_owner_proven=True,
            now=NOW,
        ),
    )

    exit_code = module.main(
        [
            "--manifest",
            str(manifest_path),
            "--evidence-root",
            str(evidence_root),
            "--installed-root",
            str(tmp_path),
            "--runtime-owner-state",
            str(tmp_path / "owner.json"),
            "--artifact-identity",
            str(tmp_path / "identity.json"),
            "--receipt-manifest",
            "receipt.json",
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == module.EXIT_PASS
    assert output["status"] == "PASS"
    assert all(not key.startswith("_") for key in output)
    receipt = json.loads((evidence_root / "receipt.json").read_text(encoding="utf-8"))
    assert receipt == module.receipt_manifest(
        result=original_assess_manifest(
            manifest,
            evidence_root=evidence_root,
            expected_candidate_digest=candidate,
            expected_artifact_digest=artifact,
            installed_owner_proven=True,
            now=NOW,
        )
    )

    manifest["delivery"]["telegramBubbleCount"] = 2
    partial_exit = module.main(
        [
            "--manifest",
            str(manifest_path),
            "--evidence-root",
            str(evidence_root),
            "--installed-root",
            str(tmp_path),
            "--runtime-owner-state",
            str(tmp_path / "owner.json"),
            "--artifact-identity",
            str(tmp_path / "identity.json"),
            "--receipt-manifest",
            "partial-receipt.json",
        ]
    )
    partial_output = json.loads(capsys.readouterr().out)
    assert partial_exit == module.EXIT_PARTIAL
    assert partial_output["status"] == "PARTIAL"
    assert not (evidence_root / "partial-receipt.json").exists()


def test_receipt_writer_rejects_escape_and_symlink_targets(tmp_path: Path) -> None:
    module = load_module("worker_bee_file_parity_receipt_path")
    manifest, evidence_root, candidate, artifact = complete_manifest(tmp_path)
    result = assess(module, manifest, evidence_root, candidate, artifact)
    receipt = module.receipt_manifest(result=result)

    with pytest.raises(module.EvidenceContractError, match="evidence_contract_invalid"):
        module._write_receipt_manifest(
            target=tmp_path / "outside.json",
            evidence_root=evidence_root,
            payload=receipt,
        )

    outside = tmp_path / "outside-target.json"
    linked = evidence_root / "linked.json"
    linked.symlink_to(outside)
    with pytest.raises(module.EvidenceContractError, match="evidence_contract_invalid"):
        module._write_receipt_manifest(
            target=linked,
            evidence_root=evidence_root,
            payload=receipt,
        )


def test_stale_manifest_and_unproven_installed_owner_fail_closed(
    tmp_path: Path,
) -> None:
    module = load_module("worker_bee_file_parity_stale")
    manifest, evidence_root, candidate, artifact = complete_manifest(tmp_path)
    manifest["runAt"] = (NOW - timedelta(days=2)).isoformat()
    with pytest.raises(module.EvidenceContractError, match="evidence_contract_invalid"):
        assess(module, manifest, evidence_root, candidate, artifact)

    manifest, evidence_root, candidate, artifact = complete_manifest(tmp_path / "owner")
    result = module.assess_manifest(
        manifest,
        evidence_root=evidence_root,
        expected_candidate_digest=candidate,
        expected_artifact_digest=artifact,
        installed_owner_proven=False,
        now=NOW,
    )
    assert result["status"] == "PARTIAL"
    assert "candidate_binding" in result["blockers"]
    assert "installed_telegram" in result["blockers"]


def test_manifest_parser_rejects_duplicate_keys_and_unknown_fields() -> None:
    module = load_module("worker_bee_file_parity_strict_json")
    with pytest.raises(module.EvidenceContractError, match="evidence_contract_invalid"):
        module.loads_strict_json(b'{"caseId":"TGDOC-010","caseId":"TGDOC-010"}')

    with pytest.raises(module.EvidenceContractError, match="evidence_contract_invalid"):
        module.assess_manifest(
            {"contractVersion": 1, "caseId": "TGDOC-010", "unexpected": True},
            evidence_root=Path("/does/not/matter"),
            expected_candidate_digest=digest("candidate"),
            expected_artifact_digest=digest("artifact"),
            installed_owner_proven=True,
            now=NOW,
        )


def test_private_candidate_inputs_reject_symlinks(tmp_path: Path) -> None:
    module = load_module("worker_bee_file_parity_private_symlink")
    target = tmp_path / "candidate.json"
    write_private(target, b'{"contractVersion":1}\n')
    linked = tmp_path / "linked.json"
    linked.symlink_to(target)

    with pytest.raises(module.EvidenceContractError, match="evidence_contract_invalid"):
        module._private_json(linked)


def test_runner_file_is_executable() -> None:
    assert os.access(SCRIPT, os.X_OK)


INSTALLED_JOURNEY = SCRIPT.with_name("run_tgdoc_010_installed_journey.cjs")
INSTALLED_JOURNEY_TESTS = SCRIPT.with_name("run_tgdoc_010_installed_journey.test.cjs")


def test_installed_telegram_journey_file_is_directly_executable() -> None:
    assert os.access(INSTALLED_JOURNEY, os.X_OK)


def test_installed_telegram_journey_keeps_its_exact_public_qa_owner() -> None:
    owners = (ROOT / "qa" / "release-test-owners.yaml").read_text(encoding="utf-8")
    cases = (ROOT / "qa" / "telegram-document-attachments" / "cases.md").read_text(
        encoding="utf-8"
    )

    assert (
        "  tests/release/test_telegram_worker_file_parity_qa.py:\n"
        "    qa_owner: qa/telegram-document-attachments/cases.md\n"
    ) in owners
    assert "tests/release/test_telegram_worker_file_parity_qa.py" in cases
    assert "run_tgdoc_010_installed_journey.cjs" in cases
    assert "- Last run: NOT RUN — cataloged 2026-08-24." in cases


def test_installed_telegram_journey_is_an_executable_trigger_not_a_semantic_verifier() -> None:
    source = INSTALLED_JOURNEY.read_text(encoding="utf-8")

    for required in (
        "executeInstalledJourney",
        "probeTelegramIdentity",
        "sendGroupedTelegramAttachments",
        "observeTelegramIngress",
        "observeOwnerScopedMission",
        "observeWorkerMaterialization",
        "observeAuthorizedBrokerReceipts",
        "observeProviderFallback",
        "restartMissionRuntime",
        "openDeliveredArtifact",
        "collectIndependentTrace",
        "@oai/sky",
        "get_app_state",
        "do_action",
        "assertAuthenticatedComputerDesktopDriver",
        "writeObservedComputerCapture",
        "headless: false",
        "page.waitForResponse",
        "node:sqlite",
        "readOnly: true",
    ):
        assert required in source


def test_installed_telegram_journey_has_independent_consent_privacy_and_truth_gates() -> None:
    source = INSTALLED_JOURNEY.read_text(encoding="utf-8")

    for required in (
        "VIVENTIUM_QA_ALLOW_TGDOC_010_DIAGNOSTIC",
        "VIVENTIUM_QA_ALLOW_TGDOC_010_TELEGRAM_MUTATION",
        "VIVENTIUM_QA_ALLOW_TGDOC_010_RESTART",
        "VIVENTIUM_QA_OWNER_TELEGRAM_USER_ID",
        "personal_telegram_account_refused",
        "owner_safe_telegram_identity_unavailable",
        "required_provider_unavailable",
        "required_tool_unavailable",
        "worker_runtime_overlap_unavailable",
        "runtime_restart_unsupported",
        "evidence_root_inside_repository",
        "evidence_root_symlink_forbidden",
        "PRE-GATE / NOT READY",
        "releaseReady: false",
        "receiptEligible: false",
        "0o700",
        "0o600",
    ):
        assert required in source

    assert "--receipt-manifest" not in source


def test_installed_telegram_journey_uses_authenticated_computer_sky_only() -> None:
    source = INSTALLED_JOURNEY.read_text(encoding="utf-8")

    for required in (
        "VIVENTIUM_QA_ALLOW_TGDOC_010_COMPUTER_BRIDGE",
        "computer_plugin_node_repl",
        "sky.get_app_state/sky-primitives",
        "@oai/sky.get_app_state",
        "computer_desktop_driver_unavailable",
        "computer_desktop_driver_authentication_failed",
        "computer_desktop_driver_owner_mismatch",
        "computer_desktop_observation_owner_mismatch",
        "assertExternalComputerAuthority",
        "verifyExternalComputerProof",
        "readComputerDesktopState",
        "performComputerDesktopAction",
    ):
        assert required in source

    for forbidden in (
        "osascript",
        "AppleScript",
        "System Events",
        "clipboard",
        "keystroke",
        "screencapture",
        "CGEvent",
    ):
        assert forbidden not in source


def test_installed_telegram_journey_reuses_owner_safe_ephemeral_browser_session() -> None:
    source = INSTALLED_JOURNEY.read_text(encoding="utf-8")

    for required in (
        "run_installed_parallel_work_journey.cjs",
        "assertEphemeralSessionSafety",
        "createEphemeralBrowserSession",
        "VIVENTIUM_QA_ALLOW_LOCAL_JWT",
        "VIVENTIUM_QA_EMAIL",
        "JWT_SECRET",
        "JWT_REFRESH_SECRET",
        "/api/auth/refresh",
        "session.cleanup()",
        "--allow-dirty-local-testing",
        "runtime_restart_dirty_checkout_protection_required",
    ):
        assert required in source

    assert "VIVENTIUM_QA_PASSWORD" not in source
    assert 'input[name="password"]' not in source


def test_installed_telegram_journey_never_invents_runtime_or_delivery_evidence() -> None:
    source = INSTALLED_JOURNEY.read_text(encoding="utf-8")

    for required in (
        "deriveObservedUploadMetadata",
        "observedFallbackAttemptManifests",
        "assessCoordinatedRestartStatus",
        "observedArtifactIdentity",
        "work_trace_events",
        "artifact.observed",
        "serviceAckDigest",
        "fallback_input_manifest_evidence_unavailable",
        "telegram_upload_visible_identity_unavailable",
        "visible.visibleText.some((item) => item.includes(scenario.mission.outputIdentity))",
    ):
        assert required in source

    for invented in (
        "family: expected.family",
        "visibleIdentity: expected.visibleIdentity",
        "groupId: expected.groupId",
        "caption: expected.caption",
        "inputManifestSha256: parity.inputManifestSha256",
        "services: [...scenario.restart.services]",
        "groupCount: 1",
    ):
        assert invented not in source


def test_installed_telegram_journey_dry_run_has_no_live_side_effects(
    tmp_path: Path,
) -> None:
    untouched = tmp_path / "must-not-be-created"
    completed = subprocess.run(
        [str(INSTALLED_JOURNEY), "--dry-run"],
        cwd=ROOT,
        env={
            "PATH": os.environ.get("PATH", ""),
            "VIVENTIUM_QA_PRIVATE_DIR": str(untouched),
        },
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["caseId"] == "TGDOC-010"
    assert payload["status"] == "DRY_RUN"
    assert payload["sideEffects"] is False
    assert payload["accessesDatabase"] is False
    assert payload["sendsTelegramMessages"] is False
    assert payload["restartsRuntime"] is False
    assert payload["releaseReady"] is False
    assert payload["receiptEligible"] is False
    assert not untouched.exists()


def test_installed_telegram_journey_rejects_missing_opt_ins_before_writes(
    tmp_path: Path,
) -> None:
    untouched = tmp_path / "must-not-be-created"
    completed = subprocess.run(
        ["node", str(INSTALLED_JOURNEY), "--evidence-root", str(untouched)],
        cwd=ROOT,
        env={"PATH": os.environ.get("PATH", "")},
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 2
    payload = json.loads(completed.stdout)
    assert payload["status"] == "BLOCKED"
    assert payload["blocker"] == "local_qa_opt_in_required"
    assert payload["releaseLabel"] == "PRE-GATE / NOT READY"
    assert not untouched.exists()


def test_installed_telegram_journey_has_source_only_scenario_contract_tests() -> None:
    assert INSTALLED_JOURNEY.exists()
    assert INSTALLED_JOURNEY_TESTS.exists()

    completed = subprocess.run(
        ["node", "--test", str(INSTALLED_JOURNEY_TESTS)],
        cwd=ROOT,
        env={"PATH": os.environ.get("PATH", "")},
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "fail 0" in completed.stdout
