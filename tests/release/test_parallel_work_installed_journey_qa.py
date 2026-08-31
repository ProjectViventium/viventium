from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import shutil
import struct
import subprocess
import sys
import wave
import zlib
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from qa_control_test_support import write_artifact_identity

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "qa" / "parallel-orchestrator" / "scripts" / "installed_journey_qa.py"
SEMANTIC_SCHEMA = "pwk.installed-journey-evidence.v1"


@pytest.fixture(autouse=True)
def _trusted_node_verifier(monkeypatch: pytest.MonkeyPatch) -> None:
    executable = shutil.which("node")
    assert executable is not None
    monkeypatch.setenv("VIVENTIUM_QA_NODE_EXECUTABLE", os.fspath(Path(executable).resolve()))


def _ref(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _png(seed: int) -> bytes:
    width, height = 480, 270
    scanline = bytes((index + seed) % 256 for index in range(width * 3))
    pixels = (b"\x00" + scanline) * height

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(pixels))
        + chunk(b"IEND", b"\x00"[:0])
    )


def _recording() -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as recording:
        recording.setnchannels(1)
        recording.setsampwidth(2)
        recording.setframerate(8_000)
        recording.writeframes(
            b"".join(
                struct.pack("<h", 12_000 if index % 2 else -12_000)
                for index in range(8_000)
            )
        )
    return output.getvalue()


def _private_write(path: Path, content: bytes) -> None:
    path.write_bytes(content)
    path.chmod(0o600)


def _sign_native_attestations(
    unsigned_attestations: list[dict[str, object]],
) -> list[dict[str, object]]:
    script = r"""
const crypto = require('node:crypto');
const fs = require('node:fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const canonical = (value) => {
  if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
  if (value && typeof value === 'object') {
    return '{' + Object.keys(value).sort().map((key) =>
      JSON.stringify(key) + ':' + canonical(value[key])).join(',') + '}';
  }
  return JSON.stringify(value);
};
const keys = new Map();
const records = input.map((base) => {
  if (!keys.has(base.producer)) keys.set(base.producer, crypto.generateKeyPairSync('ed25519'));
  const keysForProducer = keys.get(base.producer);
  const publicDer = keysForProducer.publicKey.export({ type: 'spki', format: 'der' });
  const unsigned = {
    ...base,
    keyId: crypto.createHash('sha256').update(publicDer).digest('hex'),
  };
  const proof = 'ed25519:' + crypto.sign(
    null,
    Buffer.from(canonical(unsigned), 'utf8'),
    keysForProducer.privateKey,
  ).toString('base64url');
  return {
    publicKeySpki: publicDer.toString('base64url'),
    attestation: { ...unsigned, proof },
  };
});
process.stdout.write(JSON.stringify(records));
"""
    result = subprocess.run(
        ["node", "-e", script],
        input=json.dumps(unsigned_attestations),
        text=True,
        capture_output=True,
        check=False,
        timeout=5,
    )
    assert result.returncode == 0, result.stderr
    records = json.loads(result.stdout)
    assert isinstance(records, list)
    return records


def load_module():
    spec = importlib.util.spec_from_file_location(
        "parallel_work_installed_journey_qa", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _valid_manifest(tmp_path: Path, module, case_id: str = "PWK-UC-014"):
    installed = tmp_path / "installed"
    installed.mkdir()
    identity_path = tmp_path / "artifact-identity.json"
    identity = write_artifact_identity(installed, identity_path)
    gate = module._load_release_gate()
    candidate_digest, artifact_digest = gate._qa_candidate_digests(identity)
    evidence_root = tmp_path / "evidence"
    evidence_root.mkdir(mode=0o700)
    evidence_root.chmod(0o700)
    evidence = []
    for kind, minimum in module.CASE_EVIDENCE_MINIMUMS[case_id].items():
        for ordinal in range(minimum):
            evidence_id = f"{kind}-{ordinal}"
            relative = f"{evidence_id}.json"
            content = json.dumps({"kind": kind, "ordinal": ordinal}).encode()
            _private_write(evidence_root / relative, content)
            evidence.append(
                {
                    "id": evidence_id,
                    "kind": kind,
                    "path": relative,
                    "sha256": hashlib.sha256(content).hexdigest(),
                }
            )
    checks = []
    evidence_ids = [item["id"] for item in evidence]
    for index, check_id in enumerate(sorted(module.CASE_CHECKS[case_id])):
        checks.append(
            {
                "id": check_id,
                "status": "PASS",
                "evidence": [evidence_ids[index % len(evidence_ids)]],
            }
        )
    # Every evidence file must support at least one explicit check.
    checks[0]["evidence"] = evidence_ids
    manifest = {
        "artifactDigest": artifact_digest,
        "candidateDigest": candidate_digest,
        "caseId": case_id,
        "checks": checks,
        "contractVersion": 1,
        "evidence": evidence,
        "runAt": datetime.now(timezone.utc).isoformat(),
    }
    manifest_path = evidence_root / "journey.json"
    _private_write(manifest_path, json.dumps(manifest).encode("utf-8"))
    return manifest, manifest_path, evidence_root, identity_path


def _strict_manifest(tmp_path: Path, module, case_id: str = "PWK-UC-014"):
    installed = tmp_path / "installed"
    installed.mkdir()
    identity_path = tmp_path / "artifact-identity.json"
    identity = write_artifact_identity(installed, identity_path)
    candidate_digest, artifact_digest = (
        module._load_release_gate()._qa_candidate_digests(identity)
    )
    evidence_root = tmp_path / "evidence"
    evidence_root.mkdir(mode=0o700)
    evidence_root.chmod(0o700)
    run_at = datetime.now(timezone.utc)
    base = run_at - timedelta(seconds=60)
    stamp = run_at.isoformat()
    owner = _ref("owner-a")
    turn = _ref("logical-turn")
    origin = module.CASE_SURFACES[case_id]
    work_refs = [_ref("work-a"), _ref("work-b")]
    run_refs = [_ref("run-a"), _ref("run-b")]

    def timestamp(seconds: int) -> str:
        return (base + timedelta(seconds=seconds)).isoformat()

    minimums = dict(module.CASE_EVIDENCE_MINIMUMS[case_id])
    minimums["glasshive_rows"] = max(1, minimums.get("glasshive_rows", 0))
    minimums["delivery_ledger"] = max(1, minimums.get("delivery_ledger", 0))
    minimums["trace_export"] = max(1, minimums.get("trace_export", 0))
    minimums["isolation_probe"] = max(1, minimums.get("isolation_probe", 0))
    minimums["telegram_screenshot"] = max(1, minimums.get("telegram_screenshot", 0))
    minimums["telegram_observation"] = 1
    if case_id == "PWK-UC-015":
        minimums["browser_screenshot"] = 2
    if case_id == "PWK-UC-018":
        minimums["artifact_hash"] = 1
    minimums["browser_observation"] = minimums["browser_screenshot"]
    minimums["artifact_bytes"] = minimums.get("artifact_hash", 0)
    if case_id in {"PWK-UC-014", "PWK-UC-015", "PWK-UC-019"}:
        minimums["native_receipt"] = 1
    if case_id == "PWK-UC-019":
        minimums["attachment_bytes"] = 2

    binary_kinds = {
        "telegram_screenshot",
        "browser_screenshot",
        "voice_recording",
        "artifact_bytes",
        "attachment_bytes",
    }
    surfaces = {
        "installed_identity": "runtime",
        "restart_receipt": "runtime",
        "safety_scan": "runtime",
        "telegram_screenshot": "telegram",
        "telegram_observation": "telegram",
        "telegram_turn": "telegram",
        "attachment_hash": "telegram",
        "attachment_bytes": "telegram",
        "browser_screenshot": "web",
        "browser_observation": "web",
        "voice_recording": "voice",
        "voice_transcript": "voice",
        "denial_receipt": "voice",
        "native_receipt": "core",
        "delivery_ledger": "core",
        "trace_export": "core",
        "auth_matrix": "core",
        "rejection_ledger": "core",
        "glasshive_rows": "glasshive",
        "fault_receipt": "glasshive",
        "capacity_ledger": "glasshive",
        "provider_health_ledger": "glasshive",
        "isolation_probe": "glasshive",
        "artifact_hash": "glasshive",
        "artifact_bytes": "glasshive",
        "database_export": "glasshive",
        "capability_ledger": "glasshive",
        "cleanup_receipt": "runtime",
    }
    producers = {
        "installed_identity": "runtime.installed_identity",
        "restart_receipt": "runtime.service_acknowledgement",
        "safety_scan": "runtime.public_safety_scan",
        "telegram_observation": "telegram.desktop_capture",
        "telegram_turn": "telegram.source_ledger",
        "attachment_hash": "telegram.upload_ledger",
        "browser_observation": "browser.headed_capture",
        "voice_transcript": "voice.call_transcript",
        "denial_receipt": "voice.surface_authority",
        "native_receipt": "core.native_receipt",
        "delivery_ledger": "core.delivery_ledger",
        "trace_export": "core.origin_trace",
        "auth_matrix": "core.owner_authority",
        "rejection_ledger": "core.security_audit",
        "glasshive_rows": "glasshive.lifecycle_rows",
        "fault_receipt": "glasshive.installed_qa_control",
        "capacity_ledger": "glasshive.capacity_ledger",
        "provider_health_ledger": "glasshive.provider_health",
        "isolation_probe": "glasshive.worker_isolation",
        "artifact_hash": "glasshive.artifact_ledger",
        "database_export": "glasshive.database_snapshot",
        "capability_ledger": "glasshive.capability_audit",
        "cleanup_receipt": "runner.synthetic_cleanup",
    }

    binary_contents: dict[str, bytes] = {}
    for kind, minimum in minimums.items():
        if kind not in binary_kinds:
            continue
        for ordinal in range(minimum):
            evidence_id = f"{kind}-{ordinal}"
            if kind in {"telegram_screenshot", "browser_screenshot"}:
                binary_contents[evidence_id] = _png(
                    ordinal + (10 if kind == "telegram_screenshot" else 40)
                )
            elif kind == "voice_recording":
                binary_contents[evidence_id] = _recording()
            elif kind == "artifact_bytes":
                hostile_probe = (
                    '<script>document.documentElement.dataset.qaProbe="isolated"</script>'
                    if case_id == "PWK-UC-018"
                    else ""
                )
                binary_contents[evidence_id] = (
                    "<!doctype html><html><head>"
                    f"<title>Installed artifact {ordinal}</title></head>"
                    f"<body><main>Verified mission {ordinal}</main>{hostile_probe}</body></html>"
                ).encode()
            else:
                binary_contents[evidence_id] = f"uploaded attachment {ordinal}".encode()

    artifact_digests = [
        hashlib.sha256(binary_contents[f"artifact_bytes-{ordinal}"]).hexdigest()
        for ordinal in range(minimums["artifact_bytes"])
    ]

    works = []
    runs = []
    attempts = []
    leases = []
    for ordinal, work_ref in enumerate(work_refs):
        invoked = 5 if ordinal == 0 else 15
        finished = 35 if ordinal == 0 else 45
        attempt_ref = _ref(f"attempt-{ordinal}")
        lease_ref = _ref(f"lease-{ordinal}")
        worker_ref = _ref(f"worker-{ordinal}")
        workspace_ref = _ref(f"workspace-{ordinal}")
        container_ref = _ref(f"container-{ordinal}")
        works.append(
            {
                "workRefHash": work_ref,
                "ownerRefHash": owner,
                "originSurface": origin,
                "logicalTurnRefHash": turn,
                "turnRevision": 3,
                "workerRefHash": worker_ref,
                "workspaceRefHash": workspace_ref,
            }
        )
        runs.append(
            {
                "runRefHash": run_refs[ordinal],
                "workRefHash": work_ref,
                "ownerRefHash": owner,
                "workerRefHash": worker_ref,
                "attemptRefHash": attempt_ref,
                "leaseRefHash": lease_ref,
                "workspaceRefHash": workspace_ref,
                "containerRefHash": container_ref,
                "executionMode": "isolated_container",
                "state": "completed",
                "startedAt": timestamp(invoked),
                "runtimeInvokedAt": timestamp(invoked),
                "finishedAt": timestamp(finished),
            }
        )
        attempts.append(
            {
                "attemptRefHash": attempt_ref,
                "runRefHash": run_refs[ordinal],
                "workRefHash": work_ref,
                "ownerRefHash": owner,
                "state": "closed",
                "openedAt": timestamp(invoked - 1),
                "runtimeInvokedAt": timestamp(invoked),
                "closedAt": timestamp(finished),
            }
        )
        leases.append(
            {
                "leaseRefHash": lease_ref,
                "runRefHash": run_refs[ordinal],
                "workRefHash": work_ref,
                "ownerRefHash": owner,
                "workerRefHash": worker_ref,
                "executorRefHash": container_ref,
                "acquiredAt": timestamp(invoked - 2),
                "runtimeInvokedAt": timestamp(invoked),
                "expiresAt": timestamp(invoked + 50),
                "releasedAt": timestamp(finished),
            }
        )
    steer_action = {
        "action": "steer",
        "workRefHash": work_refs[0],
        "runRefHash": run_refs[0],
        "ownerRefHash": owner,
        "receiptRefHash": _ref("steer-receipt"),
        "committedAt": timestamp(22),
    }
    mission_actions = [deepcopy(steer_action)] + [
        {
            "action": action,
            "workRefHash": work_refs[0],
            "runRefHash": run_refs[0],
            "workerRefHash": _ref("worker-0"),
            "ownerRefHash": owner,
            "receiptRefHash": _ref(f"{action}-receipt"),
            "committedAt": timestamp(23 + index),
        }
        for index, action in enumerate(("queue", "message"))
    ]
    feelings_capsule = _ref("feelings-capsule")
    configured_provider = _ref("configured-provider")
    configured_model = _ref("model")
    main_provider_attempt = _ref("provider-attempt")
    native_attestations: list[dict[str, object]] = []
    if case_id == "PWK-UC-019":
        issued_at_ms = int((run_at - timedelta(seconds=5)).timestamp() * 1000)
        expires_at_ms = int((run_at + timedelta(minutes=5)).timestamp() * 1000)
        common_attestation = {
            "capsuleOccurrenceCount": 1,
            "contractVersion": 1,
            "expiresAtMs": expires_at_ms,
            "issuedAtMs": issued_at_ms,
            "modelRefHash": configured_model,
            "ownerRefHash": owner,
            "providerRefHash": configured_provider,
            "snapshotHash": feelings_capsule,
            "surface": origin,
        }
        unsigned_attestations = [
            {
                **common_attestation,
                "actor": "main",
                "nativeRequestSha256": _ref("main-native-request"),
                "producer": "core.native_receipt",
                "providerAttemptRefHash": main_provider_attempt,
                "runRefHash": None,
                "workRefHash": None,
            }
        ] + [
            {
                **common_attestation,
                "actor": "worker",
                "nativeRequestSha256": _ref(f"worker-native-request-{index}"),
                "producer": "glasshive.native_provider_receipt",
                "providerAttemptRefHash": _ref(f"worker-provider-attempt-{index}"),
                "runRefHash": run_refs[index],
                "workRefHash": work_refs[index],
            }
            for index in range(2)
        ]
        native_attestations = _sign_native_attestations(unsigned_attestations)

    def payload_for(kind: str, ordinal: int) -> dict[str, object]:
        if kind == "installed_identity":
            return {
                "measuredCandidateDigest": candidate_digest,
                "measuredArtifactDigest": artifact_digest,
                "runtimeProcessRefHash": _ref("installed-process"),
                "ownerRefHash": owner,
                "originSurface": origin,
            }
        if kind == "telegram_turn":
            return {
                "events": [
                    {
                        "sourceEventRefHash": _ref(f"source-{revision}"),
                        "ownerRefHash": owner,
                        "logicalTurnRefHash": turn,
                        "turnRevision": revision,
                        "sourceSequence": revision,
                        "observedAt": timestamp(17 + revision),
                    }
                    for revision in (2, 3)
                ],
                "presentations": [
                    {
                        "presentationRefHash": _ref("quick-presentation"),
                        "ownerRefHash": owner,
                        "logicalTurnRefHash": turn,
                        "turnRevision": 3,
                        "author": "main",
                        "kind": "quick_answer",
                        "committedAt": timestamp(21),
                    }
                ],
            }
        if kind == "telegram_observation":
            return {
                "captureSource": "telegram_desktop_accessibility",
                "screenshotSha256": hashlib.sha256(
                    binary_contents["telegram_screenshot-0"]
                ).hexdigest(),
                "windowRefHash": _ref("telegram-window"),
                "ownerRefHash": owner,
                "visibleMessageRefHashes": [_ref("message-a"), _ref("message-b")],
            }
        if kind == "native_receipt":
            receipt = {
                "mainAgentRefHash": _ref("main-agent"),
                "feelingsCapsuleSha256": feelings_capsule,
                "route": {
                    "surface": origin,
                    "routeRefHash": _ref("route"),
                    "modelRefHash": configured_model,
                    "providerAttemptRefHash": main_provider_attempt,
                    "effort": "high",
                },
                "launches": [
                    {
                        "workRefHash": work_refs[index],
                        "runRefHash": run_refs[index],
                        "ownerRefHash": owner,
                        "logicalTurnRefHash": turn,
                        "turnRevision": 3,
                        "receiptRefHash": _ref(f"launch-{index}"),
                        "committedAt": timestamp(index + 1),
                    }
                    for index in range(2)
                ],
                "actions": deepcopy(mission_actions)
                if case_id == "PWK-UC-019"
                else [deepcopy(steer_action)],
            }
            if case_id == "PWK-UC-019":
                receipt["producerAttestations"] = deepcopy(native_attestations)
                receipt["routeTruth"] = {
                    "originSurface": origin,
                    "configured": [
                        {
                            "providerRefHash": configured_provider,
                            "modelRefHash": configured_model,
                        }
                    ],
                    "attempts": [
                        {
                            "providerRefHash": configured_provider,
                            "modelRefHash": configured_model,
                            "outcome": "used",
                            "observed": True,
                            "fallback": False,
                        }
                    ],
                }
            return receipt
        if kind == "glasshive_rows":
            return {
                "works": deepcopy(works),
                "runs": deepcopy(runs),
                "attempts": deepcopy(attempts),
                "leases": deepcopy(leases),
                "actions": deepcopy(mission_actions)
                if case_id == "PWK-UC-019"
                else [deepcopy(steer_action)],
            }
        if kind == "delivery_ledger":
            callbacks = []
            deliveries = []
            for index in range(2):
                callback = f"callback_sha256:{_ref(f'callback-{index}')}"
                callbacks.append(
                    {
                        "callbackRef": callback,
                        "ownerRefHash": owner,
                        "workRefHash": work_refs[index],
                        "runRefHash": run_refs[index],
                        "attemptNumber": 1,
                        "transportState": "http_accepted",
                        "acceptedAt": timestamp(47 + index),
                    }
                )
                deliveries.append(
                    {
                        "deliveryRefHash": _ref(f"delivery-{index}"),
                        "callbackRef": callback,
                        "ownerRefHash": owner,
                        "workRefHash": work_refs[index],
                        "runRefHash": run_refs[index],
                        "surface": origin,
                        "state": "sent",
                        "messageRefHash": _ref(f"terminal-message-{index}"),
                        "deliveredAt": timestamp(50 + index),
                    }
                )
            return {
                "callbacks": callbacks,
                "deliveries": deliveries,
                "replays": [
                    {
                        "callbackRef": callbacks[0]["callbackRef"],
                        "ownerRefHash": owner,
                        "workRefHash": work_refs[0],
                        "runRefHash": run_refs[0],
                        "outcome": "suppressed",
                        "deliveryRowsCreated": 0,
                    }
                ],
            }
        if kind == "artifact_hash":
            content = binary_contents[f"artifact_bytes-{ordinal}"]
            return {
                "artifactRefHash": _ref(f"artifact-{ordinal}"),
                "ownerRefHash": owner,
                "workRefHash": work_refs[ordinal],
                "runRefHash": run_refs[ordinal],
                "byteSha256": hashlib.sha256(content).hexdigest(),
                "sizeBytes": len(content),
                "mediaType": "text/html",
                "state": "available",
                "observedAt": timestamp(46 + ordinal),
            }
        if kind == "browser_observation":
            artifact_window = ordinal < minimums["artifact_bytes"]
            observation = {
                "captureSource": "browser_devtools",
                "screenshotSha256": hashlib.sha256(
                    binary_contents[f"browser_screenshot-{ordinal}"]
                ).hexdigest(),
                "windowRefHash": _ref(f"browser-window-{ordinal}"),
                "frameRefHash": _ref(f"browser-frame-{ordinal}"),
                "documentRefHash": _ref(f"browser-document-{ordinal}"),
                "visibleContentSha256": _ref(f"visible-content-{ordinal}"),
                "headed": True,
                "visible": True,
                "view": "artifact" if artifact_window else "active_work",
                "artifactSha256": artifact_digests[ordinal]
                if artifact_window
                else None,
                "sandboxed": True,
                "hostAuthority": False,
            }
            return observation
        if kind == "isolation_probe":
            return {
                "workers": [
                    {
                        "ownerRefHash": owner,
                        "workRefHash": work_refs[index],
                        "runRefHash": run_refs[index],
                        "workerRefHash": _ref(f"worker-{index}"),
                        "containerRefHash": _ref(f"container-{index}"),
                        "workspaceRefHash": _ref(f"workspace-{index}"),
                        "homeRefHash": _ref(f"home-{index}"),
                        "networkRefHash": _ref(f"network-{index}"),
                        "pidNamespaceRefHash": _ref(f"pid-namespace-{index}"),
                        "executionMode": "isolated_container",
                        "hostStateReadable": False,
                        "serviceEnvironmentReadable": False,
                        "dockerSocketReadable": False,
                        "ambientAuthority": False,
                        "peerProbes": [
                            {
                                "workRefHash": work_refs[1 - index],
                                "reachable": False,
                            }
                        ],
                    }
                    for index in range(2)
                ]
            }
        if kind == "trace_export":
            events = []
            previous = "0" * 64
            for index in range(2):
                for event_type in (
                    "source.observed",
                    "work.admitted",
                    "runtime.invoked",
                    "provider.request.forwarded",
                    "callback.accepted",
                    "delivery.sent",
                    "artifact.observed",
                ):
                    event = {
                        "sequence": len(events) + 1,
                        "eventType": event_type,
                        "ownerRefHash": owner,
                        "originSurface": origin,
                        "logicalTurnRefHash": turn,
                        "turnRevision": 3,
                        "workRefHash": work_refs[index],
                        "runRefHash": run_refs[index],
                        "previousSha256": previous,
                    }
                    event["eventSha256"] = module._canonical_hash(event)
                    previous = str(event["eventSha256"])
                    events.append(event)
            return {
                "contractVersion": 2,
                "producerTraceContractVersion": 2,
                "promptProducerScope": "glasshive.worker_prompt_registry",
                "fullChainVerified": True,
                "overflowCount": 0,
                "eventCount": len(events),
                "events": events,
                "chainSha256": previous,
            }
        if kind == "restart_receipt":
            return {
                "service": ("librechat-core", "telegram-bot", "glasshive-runtime")[
                    ordinal
                ],
                "processRefHash": _ref(f"restarted-process-{ordinal}"),
                "processStartedAt": timestamp(24 + ordinal),
                "acknowledgementSha256": _ref(f"restart-ack-{ordinal}"),
                "candidateDigest": candidate_digest,
            }
        if kind == "database_export":
            return {
                "phase": "pre_restart" if ordinal == 0 else "post_restart",
                "works": [
                    {
                        "ownerRefHash": owner,
                        "workRefHash": work_refs[index],
                        "runRefHash": run_refs[index],
                        "workerRefHash": _ref(f"worker-{index}"),
                        "workspaceRefHash": _ref(f"workspace-{index}"),
                        "turnRevision": 3,
                    }
                    for index in range(2)
                ],
                "actions": [deepcopy(steer_action)],
            }
        if kind == "fault_receipt":
            boundaries = (
                (
                    "provider_auth_missing",
                    "provider_quota_cooldown",
                    "provider_fallback_recovery",
                    "provider_unavailable",
                    "capacity_measurement",
                    "atomic_reservation_race",
                    "disk_pressure",
                )
                if case_id == "PWK-UC-016"
                else (
                    "callback_transport_outage",
                    "claimed_timeout",
                    "admitted_timeout",
                    "status_timeout_race",
                    "delivery_lease_race",
                    "duplicate_callback",
                    "artifact_expired",
                    "artifact_unavailable",
                )
            )
            return {
                "boundary": boundaries[ordinal],
                "controlRefHash": _ref(f"fault-control-{ordinal}"),
                "sessionRefHash": _ref("active-fault-session"),
                "ownerRefHash": owner,
                "workRefHash": work_refs[ordinal % 2],
                "runRefHash": run_refs[ordinal % 2],
                "consumedAt": timestamp(30 + ordinal),
                "effectCount": 1,
            }
        if kind == "capacity_ledger":
            available = 4_617_089_843
            required = 5_368_709_120
            return {
                "measurement": {
                    "availableBytes": available,
                    "requiredBytes": required,
                    "shortageBytes": required - available,
                    "nextRetryAt": timestamp(59),
                },
                "reservationAttempts": [
                    {
                        "requestRefHash": _ref(f"reservation-request-{index}"),
                        "slotRefHash": _ref("last-capacity-slot"),
                        "outcome": "reserved" if index == 0 else "rejected",
                        "workRefHash": work_refs[0] if index == 0 else None,
                    }
                    for index in range(2)
                ],
                "overflow": {"decision": "rejected", "workRows": 0, "runRows": 0},
                "disk": {
                    "state": "critical",
                    "availableBytes": available,
                    "requiredBytes": required,
                },
            }
        if kind == "provider_health_ledger":
            return {
                "events": [
                    {
                        "condition": "auth_missing",
                        "outcome": "needs_input",
                        "attempted": False,
                    },
                    {
                        "condition": "quota_cooldown",
                        "outcome": "skipped",
                        "attempted": False,
                        "retryAfter": timestamp(59),
                    },
                    {
                        "condition": "fallback",
                        "outcome": "completed",
                        "attempted": True,
                    },
                    {
                        "condition": "unavailable",
                        "outcome": "unavailable",
                        "attempted": False,
                    },
                ]
            }
        if kind == "auth_matrix":
            other_owner = _ref("owner-b")
            operations = [
                {
                    "actorOwnerRefHash": owner,
                    "targetOwnerRefHash": owner,
                    "operation": "inspect",
                    "outcome": "allowed",
                    "returnedWorkRefHashes": [work_refs[0]],
                }
            ]
            operations.extend(
                {
                    "actorOwnerRefHash": other_owner,
                    "targetOwnerRefHash": owner,
                    "operation": operation,
                    "outcome": "denied",
                    "returnedWorkRefHashes": [],
                }
                for operation in ("list", "inspect", "control", "callback")
            )
            operations.extend(
                {
                    "actorOwnerRefHash": owner,
                    "targetOwnerRefHash": other_owner,
                    "operation": operation,
                    "outcome": "denied",
                    "returnedWorkRefHashes": [],
                }
                for operation in ("list", "inspect", "control", "callback")
            )
            return {
                "ownerRefHash": owner,
                "otherOwnerRefHash": other_owner,
                "operations": operations,
            }
        if kind == "rejection_ledger":
            return {
                "attack": ("forged_callback", "cross_owner_callback", "altered_trace")[
                    ordinal
                ],
                "requestRefHash": _ref(f"rejected-request-{ordinal}"),
                "ownerRefHash": owner,
                "outcome": "denied",
                "effectsCreated": 0,
            }
        if kind == "safety_scan":
            return {
                "scannedArtifactSha256": artifact_digests[0],
                "findingCount": 0,
                "privateLeakCount": 0,
                "hostAuthorityExecutionCount": 0,
            }
        if kind == "voice_transcript":
            segments = []
            for index, (speaker, action, work_index) in enumerate(
                (
                    ("user", "launch", 0),
                    ("user", "launch", 1),
                    ("main", "quick_answer", None),
                    ("user", "steer", 0),
                    ("user", "hangup", None),
                    ("user", "reconnect", None),
                    ("main", "completion", 0),
                    ("main", "completion", 1),
                )
            ):
                segments.append(
                    {
                        "sequence": index + 1,
                        "speaker": speaker,
                        "action": action,
                        "ownerRefHash": owner,
                        "logicalTurnRefHash": turn,
                        "turnRevision": 3,
                        "utteranceRefHash": _ref(f"utterance-{index}"),
                        "workRefHash": work_refs[work_index]
                        if work_index is not None
                        else None,
                    }
                )
            return {
                "recordingSha256": hashlib.sha256(
                    binary_contents["voice_recording-0"]
                ).hexdigest(),
                "mode": "call",
                "segments": segments,
            }
        if kind == "attachment_hash":
            return {
                "groupRefHash": _ref("attachment-group"),
                "ownerRefHash": owner,
                "workRefHash": work_refs[0],
                "runRefHash": run_refs[0],
                "inputs": [
                    {
                        "position": index,
                        "fileRefHash": _ref(f"attachment-{index}"),
                        "evidenceId": f"attachment_bytes-{index}",
                        "byteSha256": hashlib.sha256(
                            binary_contents[f"attachment_bytes-{index}"]
                        ).hexdigest(),
                        "sizeBytes": len(binary_contents[f"attachment_bytes-{index}"]),
                    }
                    for index in range(2)
                ],
            }
        if kind == "capability_ledger":
            capability_kind = (
                "saved_memory",
                "conversation_recall",
                "broker_tool",
                "browser",
                "computer",
                "connected_account",
            )[ordinal]
            return {
                "capabilityKind": capability_kind,
                "ownerRefHash": owner,
                "workRefHash": work_refs[0],
                "runRefHash": run_refs[0],
                "requestRefHash": _ref(f"capability-request-{ordinal}"),
                "responseRefHash": _ref(f"capability-response-{ordinal}"),
                "scopeRefHash": _ref("authorized-owner-scope"),
                "outcome": "granted",
                "permission": "read"
                if capability_kind == "connected_account"
                else None,
                "effects": "read_only"
                if capability_kind == "connected_account"
                else None,
            }
        if kind == "cleanup_receipt":
            return {
                "ownerRefHash": owner,
                "zeroResidue": True,
                "completedAt": timestamp(59),
            }
        if kind == "denial_receipt":
            return {
                "mode": ("passive_wing", "listen_only")[ordinal],
                "ownerRefHash": owner,
                "attemptedAction": "launch",
                "decision": "denied",
                "workRowsCreated": 0,
            }
        raise AssertionError(f"unsupported test evidence kind: {kind}")

    evidence = []
    for kind, minimum in minimums.items():
        for ordinal in range(minimum):
            evidence_id = f"{kind}-{ordinal}"
            is_artifact_window = (
                kind in {"browser_screenshot", "browser_observation"}
                and ordinal < minimums["artifact_bytes"]
            )
            bound_index = (
                ordinal
                if kind in {"artifact_hash", "artifact_bytes"} or is_artifact_window
                else 0
                if kind in {"attachment_hash", "attachment_bytes", "capability_ledger"}
                else ordinal % 2
                if kind == "fault_receipt"
                else None
            )
            metadata = {
                "candidateDigest": candidate_digest,
                "artifactDigest": artifact_digest,
                "ownerRefHash": owner,
                "originSurface": origin,
                "surface": surfaces[kind],
                "logicalTurnRefHash": turn,
                "turnRevision": 3,
                "observedAt": stamp,
                "workRefHash": work_refs[bound_index]
                if bound_index is not None
                else None,
                "runRefHash": run_refs[bound_index]
                if bound_index is not None
                else None,
            }
            if kind in binary_kinds:
                suffix = (
                    ".png"
                    if kind in {"telegram_screenshot", "browser_screenshot"}
                    else ".wav"
                    if kind == "voice_recording"
                    else ".html"
                    if kind == "artifact_bytes"
                    else ".bin"
                )
                content = binary_contents[evidence_id]
            else:
                suffix = ".json"
                document = {
                    "contractVersion": 1,
                    "schema": SEMANTIC_SCHEMA,
                    "kind": kind,
                    "producer": producers[kind],
                    **metadata,
                    "payload": payload_for(kind, ordinal),
                }
                content = json.dumps(document, sort_keys=True).encode("utf-8")
            relative = f"{evidence_id}{suffix}"
            _private_write(evidence_root / relative, content)
            evidence.append(
                {
                    "id": evidence_id,
                    "kind": kind,
                    "path": relative,
                    "sha256": hashlib.sha256(content).hexdigest(),
                    **metadata,
                }
            )

    evidence_ids = [item["id"] for item in evidence]
    manifest = {
        "artifactDigest": artifact_digest,
        "candidateDigest": candidate_digest,
        "caseId": case_id,
        "checks": [
            {"id": check_id, "evidence": evidence_ids}
            for check_id in sorted(module.CASE_CHECKS[case_id])
        ],
        "contractVersion": 1,
        "correlation": {
            "ownerRefHash": owner,
            "surface": origin,
            "logicalTurnRefHash": turn,
            "turnRevision": 3,
        },
        "evidence": evidence,
        "runAt": stamp,
    }
    manifest_path = evidence_root / "journey.json"
    _private_write(manifest_path, json.dumps(manifest).encode("utf-8"))
    return manifest, manifest_path, evidence_root, identity_path


def _rewrite_manifest(path: Path, manifest: dict[str, object]) -> None:
    _private_write(path, json.dumps(manifest).encode("utf-8"))


def _rewrite_evidence(
    manifest: dict[str, object], evidence_root: Path, evidence_id: str, mutate
) -> None:
    entry = next(item for item in manifest["evidence"] if item["id"] == evidence_id)
    path = evidence_root / str(entry["path"])
    document = json.loads(path.read_text(encoding="utf-8"))
    mutate(document)
    content = json.dumps(document, sort_keys=True).encode("utf-8")
    _private_write(path, content)
    entry["sha256"] = hashlib.sha256(content).hexdigest()


def _rewrite_binary(
    manifest: dict[str, object], evidence_root: Path, evidence_id: str, content: bytes
) -> None:
    entry = next(item for item in manifest["evidence"] if item["id"] == evidence_id)
    _private_write(evidence_root / str(entry["path"]), content)
    entry["sha256"] = hashlib.sha256(content).hexdigest()


def test_catalogs_every_required_installed_journey() -> None:
    module = load_module()
    assert set(module.CASE_CHECKS) == {
        "PWK-UC-014",
        "PWK-UC-015",
        "PWK-UC-016",
        "PWK-UC-017",
        "PWK-UC-018",
        "PWK-UC-019",
    }
    assert all(module.CASE_CHECKS.values())
    assert set(module.CASE_EVIDENCE_MINIMUMS) == set(module.CASE_CHECKS)
    assert set().union(*module.CASE_CHECKS.values()) <= set(module.CHECK_EVIDENCE_KINDS)


@pytest.mark.parametrize(
    "case_id",
    sorted(
        (
            "PWK-UC-014",
            "PWK-UC-015",
            "PWK-UC-016",
            "PWK-UC-017",
            "PWK-UC-018",
            "PWK-UC-019",
        )
    ),
)
def test_accepts_complete_candidate_bound_real_surface_evidence(
    tmp_path: Path, case_id: str
) -> None:
    module = load_module()
    _manifest, manifest_path, evidence_root, identity_path = _strict_manifest(
        tmp_path, module, case_id
    )

    result = module.evaluate_journey(
        manifest_path=manifest_path,
        evidence_root=evidence_root,
        artifact_identity_path=identity_path,
        installed_owner_proven=True,
    )

    assert result["status"] == "PASS"
    assert result["caseId"] == case_id
    assert result["checkCount"] == len(module.CASE_CHECKS[case_id])
    assert result["evidenceCount"] > 0
    receipt = module.receipt_manifest(result=result)
    assert receipt["status"] == "PASS"
    assert receipt["surface"] == module.CASE_SURFACES[case_id]
    assert all(set(item) == {"kind", "path", "sha256"} for item in receipt["evidence"])


def test_rejects_trace_without_v2_provider_forwarding_receipt(tmp_path: Path) -> None:
    module = load_module()
    manifest, manifest_path, evidence_root, identity_path = _strict_manifest(
        tmp_path, module
    )

    def remove_provider_forwarding(document: dict[str, object]) -> None:
        payload = document["payload"]
        payload["events"] = [
            event
            for event in payload["events"]
            if event["eventType"] != "provider.request.forwarded"
        ]
        previous = "0" * 64
        for sequence, event in enumerate(payload["events"], start=1):
            event["sequence"] = sequence
            event["previousSha256"] = previous
            unsigned = {
                key: value for key, value in event.items() if key != "eventSha256"
            }
            event["eventSha256"] = module._canonical_hash(unsigned)
            previous = event["eventSha256"]
        payload["eventCount"] = len(payload["events"])
        payload["chainSha256"] = previous

    _rewrite_evidence(
        manifest,
        evidence_root,
        "trace_export-0",
        remove_provider_forwarding,
    )
    _rewrite_manifest(manifest_path, manifest)

    with pytest.raises(ValueError, match="trace evidence"):
        module.evaluate_journey(
            manifest_path=manifest_path,
            evidence_root=evidence_root,
            artifact_identity_path=identity_path,
            installed_owner_proven=True,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("contractVersion", 1),
        ("producerTraceContractVersion", 1),
        ("fullChainVerified", False),
        ("overflowCount", 1),
        ("eventCount", 1),
    ],
)
def test_rejects_legacy_or_partial_trace_pages(
    tmp_path: Path, field: str, value: object
) -> None:
    module = load_module()
    manifest, manifest_path, evidence_root, identity_path = _strict_manifest(
        tmp_path, module
    )
    _rewrite_evidence(
        manifest,
        evidence_root,
        "trace_export-0",
        lambda document: document["payload"].__setitem__(field, value),
    )
    _rewrite_manifest(manifest_path, manifest)

    with pytest.raises(ValueError, match="trace evidence"):
        module.evaluate_journey(
            manifest_path=manifest_path,
            evidence_root=evidence_root,
            artifact_identity_path=identity_path,
            installed_owner_proven=True,
        )


def test_rejects_legacy_self_declared_pass_and_synthetic_json(tmp_path: Path) -> None:
    module = load_module()
    _manifest, manifest_path, evidence_root, identity_path = _valid_manifest(
        tmp_path, module
    )

    with pytest.raises(ValueError, match="journey manifest shape is invalid"):
        module.evaluate_journey(
            manifest_path=manifest_path,
            evidence_root=evidence_root,
            artifact_identity_path=identity_path,
            installed_owner_proven=True,
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("missing_check", "required journey check is missing"),
        ("candidate_mismatch", "candidate identity does not match"),
        ("non_pass", "journey check is invalid"),
        ("unreferenced", "evidence is not bound to a journey check"),
    ],
)
def test_fails_closed_on_incomplete_or_unbound_claims(
    tmp_path: Path, mutation: str, message: str
) -> None:
    module = load_module()
    manifest, manifest_path, evidence_root, identity_path = _strict_manifest(
        tmp_path, module
    )
    if mutation == "missing_check":
        manifest["checks"].pop()
    elif mutation == "candidate_mismatch":
        manifest["candidateDigest"] = "f" * 64
    elif mutation == "non_pass":
        manifest["checks"][0]["status"] = "PARTIAL"
    elif mutation == "unreferenced":
        orphan = "browser_screenshot-1"
        for check in manifest["checks"]:
            check["evidence"] = [item for item in check["evidence"] if item != orphan]
    _rewrite_manifest(manifest_path, manifest)

    with pytest.raises(ValueError, match=message):
        module.evaluate_journey(
            manifest_path=manifest_path,
            evidence_root=evidence_root,
            artifact_identity_path=identity_path,
            installed_owner_proven=True,
        )


def test_rejects_tampered_or_escaping_evidence(tmp_path: Path) -> None:
    module = load_module()
    manifest, manifest_path, evidence_root, identity_path = _strict_manifest(
        tmp_path, module
    )
    target = evidence_root / manifest["evidence"][0]["path"]
    _private_write(target, b"tampered")
    with pytest.raises(ValueError, match="evidence digest did not match"):
        module.evaluate_journey(
            manifest_path=manifest_path,
            evidence_root=evidence_root,
            artifact_identity_path=identity_path,
            installed_owner_proven=True,
        )

    manifest["evidence"][0]["path"] = "../outside.json"
    _rewrite_manifest(manifest_path, manifest)
    with pytest.raises(ValueError, match="evidence path is invalid"):
        module.evaluate_journey(
            manifest_path=manifest_path,
            evidence_root=evidence_root,
            artifact_identity_path=identity_path,
            installed_owner_proven=True,
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("candidate_metadata", "evidence candidate identity"),
        ("candidate_document", "semantic evidence identity"),
        ("artifact_document", "semantic evidence identity"),
        ("owner_metadata", "evidence owner"),
        ("owner_document", "semantic evidence identity"),
        ("origin_surface", "evidence origin surface"),
        ("capture_surface", "evidence capture surface"),
        ("turn_metadata", "evidence logical turn"),
        ("revision_metadata", "evidence turn revision"),
        ("revision_document", "semantic evidence identity"),
        ("producer", "semantic evidence producer"),
        ("synthetic_document", "semantic evidence shape"),
        ("self_declared_check", "journey check is invalid"),
        ("missing_browser", "required real-surface evidence"),
        ("fake_browser_capture", "screenshot evidence"),
        ("duplicate_path", "evidence file is duplicated"),
    ],
)
def test_rejects_unbound_synthetic_or_missing_evidence(
    tmp_path: Path, mutation: str, message: str
) -> None:
    module = load_module()
    manifest, manifest_path, evidence_root, identity_path = _strict_manifest(
        tmp_path, module
    )
    target = next(
        item for item in manifest["evidence"] if item["id"] == "glasshive_rows-0"
    )
    if mutation == "candidate_metadata":
        target["candidateDigest"] = _ref("other-candidate")
    elif mutation == "candidate_document":
        _rewrite_evidence(
            manifest,
            evidence_root,
            "glasshive_rows-0",
            lambda document: document.update(candidateDigest=_ref("other-candidate")),
        )
    elif mutation == "artifact_document":
        _rewrite_evidence(
            manifest,
            evidence_root,
            "glasshive_rows-0",
            lambda document: document.update(artifactDigest=_ref("other-artifact")),
        )
    elif mutation == "owner_metadata":
        target["ownerRefHash"] = _ref("owner-b")
    elif mutation == "owner_document":
        _rewrite_evidence(
            manifest,
            evidence_root,
            "glasshive_rows-0",
            lambda document: document.update(ownerRefHash=_ref("owner-b")),
        )
    elif mutation == "origin_surface":
        target["originSurface"] = "voice"
    elif mutation == "capture_surface":
        target["surface"] = "telegram"
    elif mutation == "turn_metadata":
        target["logicalTurnRefHash"] = _ref("another-turn")
    elif mutation == "revision_metadata":
        target["turnRevision"] = 4
    elif mutation == "revision_document":
        _rewrite_evidence(
            manifest,
            evidence_root,
            "glasshive_rows-0",
            lambda document: document.update(turnRevision=4),
        )
    elif mutation == "producer":
        _rewrite_evidence(
            manifest,
            evidence_root,
            "glasshive_rows-0",
            lambda document: document.update(producer="self.declared_fixture"),
        )
    elif mutation == "synthetic_document":
        _rewrite_evidence(
            manifest,
            evidence_root,
            "glasshive_rows-0",
            lambda document: (
                document.clear(),
                document.update(kind="glasshive_rows", status="PASS"),
            ),
        )
    elif mutation == "self_declared_check":
        manifest["checks"][0]["status"] = "PASS"
    elif mutation == "missing_browser":
        removed = "browser_observation-1"
        manifest["evidence"] = [
            item for item in manifest["evidence"] if item["id"] != removed
        ]
        for check in manifest["checks"]:
            check["evidence"] = [item for item in check["evidence"] if item != removed]
    elif mutation == "fake_browser_capture":
        _rewrite_binary(
            manifest, evidence_root, "browser_screenshot-0", b"synthetic screenshot"
        )
    elif mutation == "duplicate_path":
        duplicate = next(
            item
            for item in manifest["evidence"]
            if item["id"] == "browser_screenshot-1"
        )
        original = next(
            item
            for item in manifest["evidence"]
            if item["id"] == "browser_screenshot-0"
        )
        duplicate["path"] = original["path"]
        duplicate["sha256"] = original["sha256"]
    _rewrite_manifest(manifest_path, manifest)

    with pytest.raises(ValueError, match=message):
        module.evaluate_journey(
            manifest_path=manifest_path,
            evidence_root=evidence_root,
            artifact_identity_path=identity_path,
            installed_owner_proven=True,
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("missing_invocation", "runtime invocation"),
        ("wrong_attempt", "runtime attempt"),
        ("wrong_lease_run", "runtime lease"),
        ("expired_lease", "runtime lease"),
        ("serial_execution", "runtime windows do not overlap"),
        ("cross_owner_work", "work owner"),
        ("duplicate_worker", "worker isolation"),
        ("shared_worker_network", "worker isolation"),
        ("peer_access", "worker isolation"),
        ("duplicate_callback", "callback"),
        ("duplicate_delivery", "delivery"),
        ("transport_only", "delivery"),
        ("cross_work_delivery", "delivery"),
        ("changed_artifact", "artifact bytes"),
        ("same_browser_window", "browser windows"),
        ("headless_browser", "browser proof"),
        ("duplicate_main_reply", "source revision"),
        ("altered_trace", "trace"),
    ],
)
def test_rejects_forged_lifecycle_isolation_delivery_and_browser_proof(
    tmp_path: Path, mutation: str, message: str
) -> None:
    module = load_module()
    manifest, manifest_path, evidence_root, identity_path = _strict_manifest(
        tmp_path, module
    )

    def change_rows(document: dict[str, object]) -> None:
        rows = document["payload"]
        if mutation == "missing_invocation":
            rows["runs"][0]["runtimeInvokedAt"] = None
        elif mutation == "wrong_attempt":
            rows["runs"][0]["attemptRefHash"] = _ref("wrong-attempt")
        elif mutation == "wrong_lease_run":
            rows["leases"][0]["runRefHash"] = rows["runs"][1]["runRefHash"]
        elif mutation == "expired_lease":
            rows["leases"][0]["expiresAt"] = rows["leases"][0]["acquiredAt"]
        elif mutation == "serial_execution":
            first_finish = datetime.fromisoformat(rows["runs"][0]["finishedAt"])
            invoked = first_finish + timedelta(seconds=2)
            finished = invoked + timedelta(seconds=8)
            rows["runs"][1]["runtimeInvokedAt"] = invoked.isoformat()
            rows["runs"][1]["startedAt"] = invoked.isoformat()
            rows["runs"][1]["finishedAt"] = finished.isoformat()
            rows["attempts"][1]["openedAt"] = (
                invoked - timedelta(seconds=1)
            ).isoformat()
            rows["attempts"][1]["runtimeInvokedAt"] = invoked.isoformat()
            rows["attempts"][1]["closedAt"] = finished.isoformat()
            rows["leases"][1]["acquiredAt"] = (
                invoked - timedelta(seconds=2)
            ).isoformat()
            rows["leases"][1]["runtimeInvokedAt"] = invoked.isoformat()
            rows["leases"][1]["expiresAt"] = (
                finished + timedelta(seconds=2)
            ).isoformat()
            rows["leases"][1]["releasedAt"] = finished.isoformat()
        elif mutation == "cross_owner_work":
            rows["works"][0]["ownerRefHash"] = _ref("owner-b")
        elif mutation == "duplicate_worker":
            rows["works"][1]["workerRefHash"] = rows["works"][0]["workerRefHash"]
            rows["runs"][1]["workerRefHash"] = rows["runs"][0]["workerRefHash"]
            rows["leases"][1]["workerRefHash"] = rows["leases"][0]["workerRefHash"]

    if mutation in {
        "missing_invocation",
        "wrong_attempt",
        "wrong_lease_run",
        "expired_lease",
        "serial_execution",
        "cross_owner_work",
        "duplicate_worker",
    }:
        _rewrite_evidence(manifest, evidence_root, "glasshive_rows-0", change_rows)
    elif mutation in {"shared_worker_network", "peer_access"}:

        def change_isolation(document: dict[str, object]) -> None:
            workers = document["payload"]["workers"]
            if mutation == "shared_worker_network":
                workers[1]["networkRefHash"] = workers[0]["networkRefHash"]
            else:
                workers[0]["peerProbes"][0]["reachable"] = True

        _rewrite_evidence(
            manifest, evidence_root, "isolation_probe-0", change_isolation
        )
    elif mutation in {
        "duplicate_callback",
        "duplicate_delivery",
        "transport_only",
        "cross_work_delivery",
    }:

        def change_delivery(document: dict[str, object]) -> None:
            ledger = document["payload"]
            if mutation == "duplicate_callback":
                ledger["callbacks"].append(deepcopy(ledger["callbacks"][0]))
            elif mutation == "duplicate_delivery":
                ledger["deliveries"].append(deepcopy(ledger["deliveries"][0]))
            elif mutation == "transport_only":
                ledger["deliveries"][0]["state"] = "http_accepted"
            else:
                ledger["deliveries"][0]["workRefHash"] = ledger["deliveries"][1][
                    "workRefHash"
                ]

        _rewrite_evidence(manifest, evidence_root, "delivery_ledger-0", change_delivery)
    elif mutation == "changed_artifact":
        _rewrite_binary(
            manifest,
            evidence_root,
            "artifact_bytes-0",
            b"<!doctype html><html><body>different artifact</body></html>",
        )
    elif mutation in {"same_browser_window", "headless_browser"}:

        def change_browser(document: dict[str, object]) -> None:
            if mutation == "same_browser_window":
                document["payload"]["windowRefHash"] = _ref("browser-window-0")
            else:
                document["payload"]["headed"] = False

        _rewrite_evidence(
            manifest,
            evidence_root,
            "browser_observation-1"
            if mutation == "same_browser_window"
            else "browser_observation-0",
            change_browser,
        )
    elif mutation == "duplicate_main_reply":
        _rewrite_evidence(
            manifest,
            evidence_root,
            "telegram_turn-0",
            lambda document: document["payload"]["presentations"].append(
                deepcopy(document["payload"]["presentations"][0])
            ),
        )
    elif mutation == "altered_trace":
        _rewrite_evidence(
            manifest,
            evidence_root,
            "trace_export-0",
            lambda document: document["payload"]["events"][0].update(
                eventType="delivery.sent"
            ),
        )
    _rewrite_manifest(manifest_path, manifest)

    with pytest.raises(ValueError, match=message):
        module.evaluate_journey(
            manifest_path=manifest_path,
            evidence_root=evidence_root,
            artifact_identity_path=identity_path,
            installed_owner_proven=True,
        )


@pytest.mark.parametrize(
    ("case_id", "evidence_id", "mutation", "message"),
    [
        (
            "PWK-UC-015",
            "restart_receipt-1",
            "duplicate_service",
            "restart acknowledgements",
        ),
        ("PWK-UC-015", "database_export-1", "changed_work", "restart continuity"),
        ("PWK-UC-016", "capacity_ledger-0", "two_reservations", "capacity reservation"),
        ("PWK-UC-016", "capacity_ledger-0", "overflow_work", "capacity overflow"),
        (
            "PWK-UC-016",
            "provider_health_ledger-0",
            "cooldown_attempt",
            "provider cooldown",
        ),
        ("PWK-UC-017", "delivery_ledger-0", "unsuppressed_replay", "callback replay"),
        ("PWK-UC-017", "fault_receipt-1", "wrong_boundary", "fault boundary"),
        ("PWK-UC-018", "auth_matrix-0", "cross_owner_allowed", "owner authorization"),
        ("PWK-UC-018", "auth_matrix-0", "missing_reverse_owner", "owner authorization"),
        ("PWK-UC-018", "rejection_ledger-0", "forged_effect", "security rejection"),
        ("PWK-UC-018", "browser_observation-0", "unsafe_artifact", "browser isolation"),
        (
            "PWK-UC-019",
            "attachment_hash-0",
            "wrong_attachment_order",
            "attachment bytes or order",
        ),
        (
            "PWK-UC-019",
            "capability_ledger-1",
            "missing_capability",
            "worker capability",
        ),
        ("PWK-UC-019", "denial_receipt-1", "passive_launch", "passive surface denial"),
        ("PWK-UC-019", "voice_transcript-0", "worker_speaks", "voice transcript"),
        (
            "PWK-UC-019",
            "voice_transcript-0",
            "reconnect_before_hangup",
            "voice transcript",
        ),
    ],
)
def test_rejects_case_specific_restart_capacity_security_and_voice_regressions(
    tmp_path: Path, case_id: str, evidence_id: str, mutation: str, message: str
) -> None:
    module = load_module()
    manifest, manifest_path, evidence_root, identity_path = _strict_manifest(
        tmp_path, module, case_id
    )

    def mutate(document: dict[str, object]) -> None:
        payload = document["payload"]
        if mutation == "duplicate_service":
            payload["service"] = "librechat-core"
        elif mutation == "changed_work":
            payload["works"][0]["workRefHash"] = _ref("replaced-work")
        elif mutation == "two_reservations":
            payload["reservationAttempts"][1]["outcome"] = "reserved"
            payload["reservationAttempts"][1]["workRefHash"] = _ref("extra-work")
        elif mutation == "overflow_work":
            payload["overflow"]["workRows"] = 1
        elif mutation == "cooldown_attempt":
            payload["events"][1]["attempted"] = True
        elif mutation == "unsuppressed_replay":
            payload["replays"][0]["deliveryRowsCreated"] = 1
        elif mutation == "wrong_boundary":
            payload["boundary"] = "admitted_timeout"
        elif mutation == "cross_owner_allowed":
            payload["operations"][1]["outcome"] = "allowed"
        elif mutation == "missing_reverse_owner":
            payload["operations"] = [
                operation
                for operation in payload["operations"]
                if operation["actorOwnerRefHash"] != payload["ownerRefHash"]
                or operation["targetOwnerRefHash"] == payload["ownerRefHash"]
            ]
        elif mutation == "forged_effect":
            payload["effectsCreated"] = 1
        elif mutation == "unsafe_artifact":
            payload["sandboxed"] = False
        elif mutation == "wrong_attachment_order":
            payload["inputs"][0]["position"] = 1
        elif mutation == "missing_capability":
            payload["outcome"] = "blocked"
        elif mutation == "passive_launch":
            payload["workRowsCreated"] = 1
        elif mutation == "worker_speaks":
            payload["segments"][2]["speaker"] = "worker"
        elif mutation == "reconnect_before_hangup":
            payload["segments"][4]["action"] = "reconnect"
            payload["segments"][5]["action"] = "hangup"

    _rewrite_evidence(manifest, evidence_root, evidence_id, mutate)
    _rewrite_manifest(manifest_path, manifest)

    with pytest.raises(ValueError, match=message):
        module.evaluate_journey(
            manifest_path=manifest_path,
            evidence_root=evidence_root,
            artifact_identity_path=identity_path,
            installed_owner_proven=True,
        )


def test_registry_api_requires_installed_owner_and_unforgeable_derived_pass(
    tmp_path: Path,
) -> None:
    module = load_module()
    manifest, manifest_path, evidence_root, identity_path = _strict_manifest(
        tmp_path, module
    )
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    candidate_digest, artifact_digest = (
        module._load_release_gate()._qa_candidate_digests(identity)
    )

    with pytest.raises(ValueError, match="installed-runtime owner"):
        module.assess_manifest(
            manifest,
            evidence_root=evidence_root,
            expected_candidate_digest=candidate_digest,
            expected_artifact_digest=artifact_digest,
            installed_owner_proven=False,
        )
    with pytest.raises(ValueError, match="installed-runtime owner"):
        module.evaluate_journey(
            manifest_path=manifest_path,
            evidence_root=evidence_root,
            artifact_identity_path=identity_path,
        )

    result = module.assess_manifest(
        manifest,
        evidence_root=evidence_root,
        expected_candidate_digest=candidate_digest,
        expected_artifact_digest=artifact_digest,
        installed_owner_proven=True,
    )
    assert module.receipt_manifest(result=result)["caseId"] == "PWK-UC-014"
    with pytest.raises(ValueError, match="only a passing installed journey"):
        module.receipt_manifest(result={"caseId": "PWK-UC-014", "status": "PASS"})
    forged = dict(result)
    forged["caseId"] = "PWK-UC-015"
    with pytest.raises(ValueError, match="only a passing installed journey"):
        module.receipt_manifest(result=forged)
    forged_evidence = dict(result)
    forged_evidence["_receiptEvidence"] = [
        dict(item) for item in result["_receiptEvidence"]
    ]
    forged_evidence["_receiptEvidence"][0]["sha256"] = _ref("forged-evidence")
    with pytest.raises(ValueError, match="only a passing installed journey"):
        module.receipt_manifest(result=forged_evidence)
    with pytest.raises(ValueError, match="candidate identity does not match"):
        module.assess_manifest(
            manifest,
            evidence_root=evidence_root,
            expected_candidate_digest=_ref("another-installed-candidate"),
            expected_artifact_digest=artifact_digest,
            installed_owner_proven=True,
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("public_root", "evidence root is not owner-only"),
        ("public_manifest", "journey manifest is invalid"),
        ("public_evidence", "journey evidence file is invalid"),
        ("symlink_evidence", "evidence path is invalid"),
        ("hardlink_evidence", "journey evidence file is invalid"),
        ("stale_observation", "evidence observation time"),
        ("duplicate_document_key", "semantic evidence is invalid"),
        ("weak_png", "screenshot evidence"),
    ],
)
def test_rejects_nonprivate_stale_ambiguous_or_synthetic_capture_files(
    tmp_path: Path, mutation: str, message: str
) -> None:
    module = load_module()
    manifest, manifest_path, evidence_root, identity_path = _strict_manifest(
        tmp_path, module
    )
    if mutation == "public_root":
        evidence_root.chmod(0o755)
    elif mutation == "public_manifest":
        manifest_path.chmod(0o644)
    elif mutation == "public_evidence":
        (evidence_root / "glasshive_rows-0.json").chmod(0o644)
    elif mutation == "symlink_evidence":
        original = evidence_root / "glasshive_rows-0.json"
        moved = evidence_root / "actual-glasshive-rows.json"
        original.rename(moved)
        original.symlink_to(moved.name)
    elif mutation == "hardlink_evidence":
        os.link(
            evidence_root / "glasshive_rows-0.json", evidence_root / "linked-rows.json"
        )
    elif mutation == "stale_observation":
        target = next(
            item for item in manifest["evidence"] if item["id"] == "glasshive_rows-0"
        )
        stale = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        target["observedAt"] = stale
        _rewrite_evidence(
            manifest,
            evidence_root,
            "glasshive_rows-0",
            lambda document: document.update(observedAt=stale),
        )
        _rewrite_manifest(manifest_path, manifest)
    elif mutation == "duplicate_document_key":
        entry = next(
            item for item in manifest["evidence"] if item["id"] == "glasshive_rows-0"
        )
        path = evidence_root / str(entry["path"])
        original = path.read_bytes()
        content = b'{"candidateDigest":"duplicated",' + original[1:]
        _private_write(path, content)
        entry["sha256"] = hashlib.sha256(content).hexdigest()
        _rewrite_manifest(manifest_path, manifest)
    elif mutation == "weak_png":
        target = next(
            item
            for item in manifest["evidence"]
            if item["id"] == "browser_screenshot-0"
        )
        content = bytearray((evidence_root / str(target["path"])).read_bytes())
        content[-1] ^= 0x01
        _rewrite_binary(manifest, evidence_root, "browser_screenshot-0", bytes(content))
        _rewrite_manifest(manifest_path, manifest)

    with pytest.raises(ValueError, match=message):
        module.evaluate_journey(
            manifest_path=manifest_path,
            evidence_root=evidence_root,
            artifact_identity_path=identity_path,
            installed_owner_proven=True,
        )


def test_rejects_silent_synthetic_voice_recording(tmp_path: Path) -> None:
    module = load_module()
    manifest, manifest_path, evidence_root, identity_path = _strict_manifest(
        tmp_path, module, "PWK-UC-019"
    )
    output = io.BytesIO()
    with wave.open(output, "wb") as recording:
        recording.setnchannels(1)
        recording.setsampwidth(2)
        recording.setframerate(8_000)
        recording.writeframes(b"\x00\x00" * 8_000)
    _rewrite_binary(manifest, evidence_root, "voice_recording-0", output.getvalue())
    _rewrite_manifest(manifest_path, manifest)

    with pytest.raises(ValueError, match="audible installed-call evidence"):
        module.evaluate_journey(
            manifest_path=manifest_path,
            evidence_root=evidence_root,
            artifact_identity_path=identity_path,
            installed_owner_proven=True,
        )


def test_rejects_benign_artifact_as_hostile_browser_isolation_proof(
    tmp_path: Path,
) -> None:
    module = load_module()
    manifest, manifest_path, evidence_root, identity_path = _strict_manifest(
        tmp_path, module, "PWK-UC-018"
    )
    benign = b"<!doctype html><html><body><main>Benign document</main></body></html>"
    digest = hashlib.sha256(benign).hexdigest()
    _rewrite_binary(manifest, evidence_root, "artifact_bytes-0", benign)
    _rewrite_evidence(
        manifest,
        evidence_root,
        "artifact_hash-0",
        lambda document: document["payload"].update(
            byteSha256=digest, sizeBytes=len(benign)
        ),
    )
    _rewrite_evidence(
        manifest,
        evidence_root,
        "browser_observation-0",
        lambda document: document["payload"].update(artifactSha256=digest),
    )
    _rewrite_evidence(
        manifest,
        evidence_root,
        "safety_scan-0",
        lambda document: document["payload"].update(scannedArtifactSha256=digest),
    )
    _rewrite_manifest(manifest_path, manifest)

    with pytest.raises(ValueError, match="hostile artifact"):
        module.evaluate_journey(
            manifest_path=manifest_path,
            evidence_root=evidence_root,
            artifact_identity_path=identity_path,
            installed_owner_proven=True,
        )


def test_cli_rejects_unproven_installed_runtime_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    module = load_module()
    _manifest, manifest_path, evidence_root, identity_path = _strict_manifest(
        tmp_path, module
    )
    installed_root = tmp_path / "installed"
    owner_state = evidence_root / "stack-owner.json"
    _private_write(
        owner_state, json.dumps({"repoRoot": str(installed_root.resolve())}).encode()
    )
    monkeypatch.setattr(
        module._load_release_gate(),
        "validate_runtime_owner_state_file",
        lambda _path: False,
    )

    exit_code = module.main(
        [
            "--manifest",
            os.fspath(manifest_path),
            "--evidence-root",
            os.fspath(evidence_root),
            "--artifact-identity",
            os.fspath(identity_path),
            "--installed-root",
            os.fspath(installed_root),
            "--runtime-owner-state",
            os.fspath(owner_state),
        ]
    )

    assert exit_code == 2
    assert json.loads(capsys.readouterr().out) == {
        "caseId": "unknown",
        "reason": "active installed-runtime owner identity is not proven",
        "status": "BLOCKED",
    }


@pytest.mark.parametrize(
    "case_id",
    sorted(
        (
            "PWK-UC-014",
            "PWK-UC-015",
            "PWK-UC-016",
            "PWK-UC-017",
            "PWK-UC-018",
            "PWK-UC-019",
        )
    ),
)
def test_cli_emits_registered_candidate_bound_semantic_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    case_id: str,
) -> None:
    module = load_module()
    _manifest, manifest_path, evidence_root, identity_path = _strict_manifest(
        tmp_path, module, case_id
    )
    installed_root = tmp_path / "installed"
    owner_state = evidence_root / "stack-owner.json"
    _private_write(
        owner_state, json.dumps({"repoRoot": str(installed_root.resolve())}).encode()
    )
    gate = module._load_release_gate()
    monkeypatch.setattr(
        gate,
        "validate_runtime_owner_state_file",
        lambda path: Path(path).resolve() == owner_state.resolve(),
    )
    recorder_path = evidence_root / "recorder.json"
    exit_code = module.main(
        [
            "--case-id",
            case_id,
            "--manifest",
            os.fspath(manifest_path),
            "--evidence-root",
            os.fspath(evidence_root),
            "--artifact-identity",
            os.fspath(identity_path),
            "--installed-root",
            os.fspath(installed_root),
            "--runtime-owner-state",
            os.fspath(owner_state),
            "--receipt-manifest",
            os.fspath(recorder_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0, captured.out + captured.err
    public_result = json.loads(captured.out)
    assert public_result["status"] == "PASS"
    assert public_result["caseId"] == case_id
    recorder = json.loads(recorder_path.read_text(encoding="utf-8"))
    assert recorder["verifier"] == {
        "id": "pwk-installed-journey-v1",
        "manifest": "journey.json",
    }

    shared_path = ROOT / "scripts" / "viventium" / "parallel_work_qa_evidence.py"
    spec = importlib.util.spec_from_file_location(
        "pwk_shared_evidence_integration", shared_path
    )
    assert spec is not None and spec.loader is not None
    shared = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(shared)
    assert shared.REGISTERED_SEMANTIC_VERIFIERS[case_id]["id"] == module.VERIFIER_ID
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    candidate_digest, artifact_digest = gate._qa_candidate_digests(identity)
    required_services = shared.SERVICE_ACK_REQUIRED_SERVICES.get(case_id)
    service_ack = (
        {
            "caseId": case_id,
            "restartState": "ready",
            "requiredServices": list(required_services),
            "acknowledgedServices": list(required_services),
            "missingServices": [],
            "sessionRef": "qa_" + "a" * 24,
            "serviceAckDigest": f"sha256:{_ref(f'ack-{case_id}')}",
        }
        if required_services is not None
        else None
    )
    arguments = {
        "manifest_path": recorder_path,
        "evidence_root": evidence_root,
        "artifact_identity": identity,
        "existing_receipts": {"contractVersion": 1, "receipts": []},
        "required_case_ids": {case_id},
        "local_qa_request": {
            "contractVersion": 1,
            "mode": "local-qa",
            "requested": True,
        },
        "service_ack_status": service_ack,
        "service_ack_validator": (
            (lambda: dict(service_ack)) if service_ack is not None else None
        ),
        "attestation_authority": (
            hashlib.sha256(b"synthetic-local-qa-only").digest(),
            _ref("synthetic-local-qa-owner"),
        ),
        "installed_owner_proven": True,
    }
    recorded = shared.record_case_receipt(**arguments)
    receipt = recorded["receipts"][0]
    assert receipt["caseId"] == case_id
    assert receipt["status"] == "PASS"
    assert receipt["candidateDigest"] == candidate_digest
    assert receipt["artifactDigest"] == artifact_digest
    if service_ack is not None:
        assert receipt["serviceAckDigest"] == service_ack["serviceAckDigest"]

    recorder["verifier"]["id"] = "forged-unregistered-pwk-verifier"
    _private_write(recorder_path, json.dumps(recorder).encode("utf-8"))
    with pytest.raises(
        ValueError, match="semantic verifier is not registered for this case"
    ):
        shared.record_case_receipt(**arguments)
def test_shared_artifact_identity_fixture_matches_current_readiness_contract(
    tmp_path: Path,
) -> None:
    installed = tmp_path / "installed"
    installed.mkdir()
    identity_path = tmp_path / "artifact-identity.json"
    identity = write_artifact_identity(installed, identity_path)
    release_gate = load_module()._load_release_gate()

    assert set(identity["readiness"]) == set(
        release_gate.READINESS_IDENTITY_HASH_KEYS
    )
    assert release_gate._artifact_identity_shape_valid(identity)
    candidate_digest, artifact_digest = release_gate._qa_candidate_digests(identity)
    assert len(candidate_digest) == 64 and set(candidate_digest) <= set("0123456789abcdef")
    assert len(artifact_digest) == 64 and set(artifact_digest) <= set("0123456789abcdef")

    stale_identity = dict(identity)
    stale_identity.pop("readiness")
    assert not release_gate._artifact_identity_shape_valid(stale_identity)
    assert release_gate._qa_candidate_digests(stale_identity) == ("", "")
