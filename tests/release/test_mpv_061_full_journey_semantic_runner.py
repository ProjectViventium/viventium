import hashlib
import importlib.util
import json
import struct
import subprocess
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
QA_ROOT = ROOT / "qa" / "modern-playground-voice"
RUNNER = QA_ROOT / "scripts" / "mpv_061_full_journey_semantic_qa.js"
PYTHON_ADAPTER = QA_ROOT / "scripts" / "mpv_061_full_journey_semantic_verifier.py"
EVIDENCE_TEMPLATE = QA_ROOT / "mpv-061-full-journey-evidence.template.v1.json"
RESULT_TEMPLATE = QA_ROOT / "mpv-061-full-journey-result.template.v1.json"
ACCEPTANCE_MANIFEST = QA_ROOT / "acceptance-manifest.template.v1.json"
README = QA_ROOT / "README.md"
CASES = QA_ROOT / "cases.md"
NOW = datetime.now(timezone.utc)
INSTALLED_ARTIFACT_IDENTITY = (
    Path.home()
    / "Library"
    / "Application Support"
    / "Viventium"
    / "runtime"
    / "parallel-work-artifact-identity.json"
)

REQUIRED_EVIDENCE_KIND_COUNTS = {
    "voice_recording": 2,
    "voice_transcript": 2,
    "session_ledger": 1,
    "worker_ledger": 1,
    "action_ledger": 1,
    "upload_ledger": 1,
    "capability_ledger": 1,
    "callback_ledger": 1,
    "delivery_ledger": 1,
    "logical_turn_ledger": 1,
    "linked_chat_capture": 2,
    "active_work_capture": 2,
    "artifact_open_capture": 2,
    "mode_authority_ledger": 1,
    "public_safety_report": 1,
}


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _ref(value: str) -> str:
    return f"sha256:{_digest(value)}"


def _canonical_digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _wav_audio(seed: int) -> bytes:
    samples = b"".join(
        struct.pack("<h", (1400 + seed * 25) if index % 2 else -(1400 + seed * 25))
        for index in range(1600)
    )
    return (
        b"RIFF"
        + struct.pack("<I", 36 + len(samples))
        + b"WAVEfmt "
        + struct.pack("<IHHIIHH", 16, 1, 1, 8000, 16000, 2, 16)
        + b"data"
        + struct.pack("<I", len(samples))
        + samples
    )


def _structural_observations(
    evidence_id: str,
    manifest: dict[str, object],
    evidence_by_id: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    voice = manifest["voice"]
    turns = [*voice["turns"].values(), *voice["completionTurns"]]
    workers = manifest["workers"]
    deliveries = manifest["deliveries"]
    run = manifest["run"]

    def turn_record(turn: dict[str, object]) -> dict[str, object]:
        record = {
            "type": "turn",
            "logicalTurnRef": turn["logicalTurnRef"],
            "logicalRevision": turn["logicalRevision"],
            "sessionRef": turn["sessionRef"],
            "conversationRef": turn["conversationRef"],
            "mode": turn["mode"],
            "effects": turn["effects"],
            "assistantSpeakerRef": turn["assistantSpeakerRef"],
        }
        for key in (
            "actorTrust",
            "directlyAddressed",
            "sideEffectAuthorityGranted",
            "action",
            "actionRef",
            "acceptedActionReceiptRef",
            "targetWorkerRef",
            "targetMissionRef",
            "targetAttemptRef",
            "nonTargetWorkerRef",
            "requestedWorkerRefs",
            "acceptedWorkerRefs",
            "acceptedLaunchReceiptRefs",
            "rejectedLaunchReceiptCount",
            "currentReply",
            "unrelatedToWorkerMissions",
            "activeWorkerRefs",
            "workerMutationCount",
            "targetActionReceiptCount",
            "nonTargetActionReceiptCount",
            "targetMutationCount",
            "nonTargetMutationCount",
            "transcriptObservationCount",
            "ambientTranscriptCount",
            "workerRef",
            "missionRef",
            "attemptRef",
            "artifactRef",
            "truthful",
            "spokenStatusOrCompletionCount",
            "duplicateSpeechCount",
            "transcriptVisible",
            "transcriptMatchedAudio",
        ):
            if key in turn:
                record[key] = turn[key]
        for field in ("inputAudioEvidence", "outputAudioEvidence"):
            if turn.get(field):
                record[field.replace("Evidence", "Sha256")] = evidence_by_id[
                    turn[field]
                ]["sha256"]
        return record

    referenced_turns = [
        turn
        for turn in turns
        if evidence_id in turn.get("evidence", [])
        or turn.get("transcriptEvidence") == evidence_id
    ]
    if evidence_id in {
        "initial-transcript",
        "reconnect-transcript",
        "logical-turn-ledger",
        "mode-ledger",
    }:
        return [turn_record(turn) for turn in referenced_turns]
    if evidence_id == "action-ledger":
        probe = voice["wingProbe"]
        return [
            *(turn_record(turn) for turn in referenced_turns),
            {
                "type": "probe_cleanup",
                **{
                    key: probe[key]
                    for key in (
                        "workerRef",
                        "missionRef",
                        "attemptRef",
                        "cleanupAction",
                        "cleanupActionRef",
                        "cleanupReceiptRef",
                        "cleanupActionReceiptCount",
                        "terminalState",
                        "deliveryCount",
                        "completedBeforeHangup",
                    )
                },
            },
        ]
    if evidence_id == "worker-ledger":
        observations = [
            {
                "type": "worker",
                **{
                    key: worker[key]
                    for key in (
                        "workerRef",
                        "missionRef",
                        "attemptRef",
                        "acceptedLaunchReceiptRef",
                        "launchTurnRef",
                        "launchMode",
                        "accepted",
                        "independent",
                        "inputRefs",
                        "observedInputRefs",
                        "activeAtHangup",
                        "cancelledByHangup",
                        "reconnectMissionRef",
                        "terminalState",
                        "attemptCount",
                        "callbackCount",
                        "deliveryCount",
                        "artifactRef",
                        "spokenCompletionCount",
                    )
                },
            }
            for worker in workers
        ]
        observations.extend(
            {
                **turn_record(turn),
                "type": "launch",
            }
            for turn in referenced_turns
            if "acceptedWorkerRefs" in turn
        )
        observations.append(
            {
                "type": "wing_probe",
                **{
                    key: value
                    for key, value in voice["wingProbe"].items()
                    if key != "evidence"
                },
            }
        )
        return observations
    if evidence_id == "upload-ledger":
        return [
            {
                "type": "input",
                **{
                    key: item[key]
                    for key in (
                        "ordinal",
                        "uploadRef",
                        "sha256",
                        "bytes",
                        "targetWorkerRef",
                        "sourceEvidence",
                    )
                },
            }
            for item in manifest["inputGroup"]["ordered"]
        ]
    if evidence_id == "capability-ledger":
        observations = [
            {
                "type": "capability",
                **{
                    key: worker[key]
                    for key in (
                        "workerRef",
                        "missionRef",
                        "contextBindingMatched",
                        "requiredCapabilitiesPreserved",
                        "fallbackCapabilityLossCount",
                        "memoryRecallReceiptCount",
                        "connectedToolReceiptCount",
                    )
                },
            }
            for worker in workers
        ]
        observations.append({"type": "fallback", **manifest["resilience"]["fallback"]})
        return observations
    if evidence_id == "session-ledger":
        return [
            {
                "type": "session",
                "initialSessionRef": run["initialSessionRef"],
                "reconnectSessionRef": run["reconnectSessionRef"],
                "conversationRef": run["conversationRef"],
                "initialSessionEnded": run["initialSessionEnded"],
                "reconnectExplicitlyStarted": run["reconnectExplicitlyStarted"],
                "acceptedWorkCancelledByHangupCount": run[
                    "acceptedWorkCancelledByHangupCount"
                ],
                "unsolicitedResultCallCount": run["unsolicitedResultCallCount"],
            },
            {"type": "restart", **manifest["resilience"]["restart"]},
        ]
    if evidence_id in {"callback-ledger", "delivery-ledger"}:
        records = [
            {
                "type": "delivery",
                **{
                    key: delivery[key]
                    for key in (
                        "workerRef",
                        "missionRef",
                        "attemptRef",
                        "artifactRef",
                        "artifactSha256",
                        "artifactEvidence",
                        "callbackCount",
                        "linkedChatDeliveryCount",
                        "activeWorkDeliveryCount",
                        "duplicateDeliveryCount",
                        "deliveredAfterHangup",
                        "reconnectSessionRef",
                        "opened",
                        "openOrDownloadActionWorked",
                    )
                },
            }
            for delivery in deliveries
        ]
        if evidence_id == "delivery-ledger":
            records.extend(turn_record(turn) for turn in voice["completionTurns"])
        return records
    if evidence_id in {
        "linked-before",
        "linked-after",
        "active-before",
        "active-after",
    }:
        surface = "linked_chat" if evidence_id.startswith("linked") else "active_work"
        after = evidence_id.endswith("after")
        return [
            {
                "type": "surface",
                "surface": surface,
                "phase": "after_reconnect" if after else "before_hangup",
                "workerRefs": [worker["workerRef"] for worker in workers],
                "artifactRefs": [worker["artifactRef"] for worker in workers]
                if after
                else [],
            }
        ]
    if evidence_id in {"artifact-a-open", "artifact-b-open"}:
        delivery = deliveries[0 if evidence_id == "artifact-a-open" else 1]
        return [
            {
                "type": "artifact_open",
                **{
                    key: delivery[key]
                    for key in (
                        "workerRef",
                        "missionRef",
                        "attemptRef",
                        "artifactRef",
                        "artifactSha256",
                        "artifactEvidence",
                        "opened",
                        "openOrDownloadActionWorked",
                    )
                },
            }
        ]
    if evidence_id == "public-safety":
        safety = manifest["publicSafety"]
        return [
            {
                "type": "public_safety",
                "rawEvidencePrivate": safety["rawEvidencePrivate"],
                "publicReportContentFree": safety["publicReportContentFree"],
                "reviewed": safety["reviewed"],
            }
        ]
    raise AssertionError(f"unknown synthetic evidence: {evidence_id}")


def _artifact_identity() -> dict[str, object]:
    hashes = {
        key: _digest(key)
        for key in (
            "components-lock",
            "source-worktree",
            "nested-worktree",
            "prebuilt-source",
            "prebuilt-binary",
            "nested-revisions",
            "prompt-bundle",
            "runtime-env",
            "librechat-config",
            "frontend-build",
            "api-build",
            "running-service",
            "service-manifest",
            "owner-executable",
            "owner-command-contract",
        )
    }
    return {
        "contractVersion": 1,
        "source": {
            "revision": "1" * 40,
            "clean": True,
            "worktreeHash": hashes["source-worktree"],
            "componentsLockSha256": hashes["components-lock"],
        },
        "nestedComponents": [
            {
                "name": "GlassHive",
                "pin": "2" * 40,
                "revision": "2" * 40,
                "clean": True,
                "worktreeHash": hashes["nested-worktree"],
            }
        ],
        "prebuiltHelper": {
            "sourceDeclaredSha256": hashes["prebuilt-source"],
            "sourceMeasuredSha256": hashes["prebuilt-source"],
            "binaryDeclaredSha256": hashes["prebuilt-binary"],
            "binaryMeasuredSha256": hashes["prebuilt-binary"],
            "binaryExecutable": True,
        },
        "installed": {
            "rootRevision": "1" * 40,
            "componentsLockSha256": hashes["components-lock"],
            "nestedRevisionsHash": hashes["nested-revisions"],
            "prebuiltSourceSha256": hashes["prebuilt-source"],
            "prebuiltBinarySha256": hashes["prebuilt-binary"],
            "promptBundleSha256": hashes["prompt-bundle"],
            "runtimeEnvSha256": hashes["runtime-env"],
            "libreChatConfigSha256": hashes["librechat-config"],
            "frontendBuildSha256": hashes["frontend-build"],
            "apiBuildSha256": hashes["api-build"],
            "runningServiceSha256": hashes["running-service"],
            "runtimeServiceManifestSha256": hashes["service-manifest"],
            "runtimeOwnerExecutableSha256": hashes["owner-executable"],
            "ownerCommandContractSha256": hashes["owner-command-contract"],
        },
    }


def _effects(**overrides: int) -> dict[str, int]:
    values = {
        "missionCount": 0,
        "actionCount": 0,
        "launchInvocationCount": 0,
        "controlInvocationCount": 0,
        "toolInvocationCount": 0,
        "controllerInvocationCount": 0,
        "cortexInvocationCount": 0,
        "liveMemoryInvocationCount": 0,
        "recallInvocationCount": 0,
        "titleModelInvocationCount": 0,
        "mainResponseCount": 0,
        "ttsInputCount": 0,
        "assistantAudioOutputCount": 0,
    }
    values.update(overrides)
    return values


def _write_full_journey_fixture(
    root: Path,
) -> tuple[Path, Path, Path, dict[str, object]]:
    root.mkdir(mode=0o700, parents=True)
    root.chmod(0o700)
    run_ref = _ref("run")
    initial_session = _ref("initial-session")
    reconnect_session = _ref("reconnect-session")
    conversation_ref = _ref("conversation")
    queen_ref = _ref("main-queen")
    worker_a = _ref("worker-a")
    worker_b = _ref("worker-b")
    wing_worker = _ref("wing-probe-worker")
    mission_a = _ref("mission-a")
    mission_b = _ref("mission-b")
    wing_mission = _ref("wing-probe-mission")
    attempt_a = _ref("attempt-a")
    attempt_b = _ref("attempt-b")
    wing_attempt = _ref("wing-probe-attempt")
    launch_a = _ref("launch-receipt-a")
    launch_b = _ref("launch-receipt-b")
    wing_launch = _ref("wing-probe-launch-receipt")
    wing_cleanup = _ref("wing-probe-cleanup")
    wing_cleanup_receipt = _ref("wing-probe-cleanup-receipt")
    call_action_ref = _ref("call-message-a")
    call_action_receipt = _ref("call-message-a-receipt")
    action_ref = _ref("steer-a")
    action_receipt = _ref("steer-a-receipt")
    upload_a = _ref("upload-a")
    upload_b = _ref("upload-b")
    artifact_a = _ref("artifact-a")
    artifact_b = _ref("artifact-b")
    fallback_primary = _ref("fallback-primary")
    fallback_attempt = _ref("fallback-attempt")
    fallback_control_receipt = _ref("fallback-control-receipt")
    restart_before = _ref("runtime-before-restart")
    restart_after = _ref("runtime-after-restart")

    evidence_specs = [
        ("initial-audio", "voice_recording", [initial_session]),
        ("reconnect-audio", "voice_recording", [reconnect_session]),
        ("initial-transcript", "voice_transcript", [initial_session]),
        ("reconnect-transcript", "voice_transcript", [reconnect_session]),
        ("session-ledger", "session_ledger", [initial_session, reconnect_session]),
        ("worker-ledger", "worker_ledger", [initial_session, reconnect_session]),
        ("action-ledger", "action_ledger", [initial_session]),
        ("upload-ledger", "upload_ledger", [initial_session]),
        ("capability-ledger", "capability_ledger", [initial_session]),
        ("callback-ledger", "callback_ledger", [initial_session, reconnect_session]),
        ("delivery-ledger", "delivery_ledger", [reconnect_session]),
        (
            "logical-turn-ledger",
            "logical_turn_ledger",
            [initial_session, reconnect_session],
        ),
        ("linked-before", "linked_chat_capture", [initial_session]),
        ("linked-after", "linked_chat_capture", [reconnect_session]),
        ("active-before", "active_work_capture", [initial_session]),
        ("active-after", "active_work_capture", [reconnect_session]),
        ("artifact-a-open", "artifact_open_capture", [reconnect_session]),
        ("artifact-b-open", "artifact_open_capture", [reconnect_session]),
        ("input-a-file", "input_file", [initial_session]),
        ("input-b-file", "input_file", [initial_session]),
        ("artifact-a-file", "delivered_artifact", [reconnect_session]),
        ("artifact-b-file", "delivered_artifact", [reconnect_session]),
        ("mode-ledger", "mode_authority_ledger", [initial_session]),
        ("public-safety", "public_safety_report", [initial_session, reconnect_session]),
    ]
    turn_refs = [_ref(f"turn-{ordinal}") for ordinal in range(1, 10)]
    run_refs = [run_ref, initial_session, reconnect_session, conversation_ref]
    worker_identity_refs = [
        worker_a,
        worker_b,
        mission_a,
        mission_b,
        attempt_a,
        attempt_b,
        launch_a,
        launch_b,
        artifact_a,
        artifact_b,
        wing_worker,
        wing_mission,
        wing_attempt,
        wing_launch,
        wing_cleanup,
        wing_cleanup_receipt,
    ]
    action_identity_refs = [
        call_action_ref,
        call_action_receipt,
        action_ref,
        action_receipt,
        worker_a,
        mission_a,
        attempt_a,
        worker_b,
        launch_a,
        launch_b,
        wing_worker,
        wing_mission,
        wing_attempt,
        wing_launch,
        wing_cleanup,
        wing_cleanup_receipt,
    ]
    evidence_entity_refs = {
        "initial-audio": turn_refs[:7],
        "reconnect-audio": turn_refs[7:],
        "initial-transcript": turn_refs[:7],
        "reconnect-transcript": turn_refs[7:],
        "session-ledger": [
            *run_refs,
            restart_before,
            restart_after,
            worker_a,
            worker_b,
        ],
        "worker-ledger": [*run_refs, *worker_identity_refs, *turn_refs],
        "action-ledger": [*run_refs, *action_identity_refs, *turn_refs[:7]],
        "upload-ledger": [upload_a, upload_b, worker_a, worker_b],
        "capability-ledger": [
            worker_a,
            worker_b,
            mission_a,
            mission_b,
            fallback_control_receipt,
            fallback_primary,
            fallback_attempt,
        ],
        "callback-ledger": [
            worker_a,
            worker_b,
            mission_a,
            mission_b,
            attempt_a,
            attempt_b,
            artifact_a,
            artifact_b,
        ],
        "delivery-ledger": [
            worker_a,
            worker_b,
            mission_a,
            mission_b,
            attempt_a,
            attempt_b,
            artifact_a,
            artifact_b,
            *turn_refs[7:],
        ],
        "logical-turn-ledger": turn_refs,
        "linked-before": [worker_a, worker_b],
        "linked-after": [worker_a, worker_b, artifact_a, artifact_b],
        "active-before": [worker_a, worker_b],
        "active-after": [worker_a, worker_b, artifact_a, artifact_b],
        "artifact-a-open": [worker_a, mission_a, attempt_a, artifact_a],
        "artifact-b-open": [worker_b, mission_b, attempt_b, artifact_b],
        "input-a-file": [upload_a, worker_a],
        "input-b-file": [upload_b, worker_b],
        "artifact-a-file": [worker_a, mission_a, attempt_a, artifact_a],
        "artifact-b-file": [worker_b, mission_b, attempt_b, artifact_b],
        "mode-ledger": [*run_refs, *turn_refs[:7]],
        "public-safety": run_refs,
    }
    evidence: list[dict[str, object]] = []
    for evidence_id, kind, session_refs in evidence_specs:
        if kind == "voice_recording":
            suffix = ".wav"
        elif kind in {"input_file", "delivered_artifact"}:
            suffix = ".bin"
        else:
            suffix = ".json"
        relative = Path("evidence") / f"{evidence_id}{suffix}"
        target = root / relative
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        target.parent.chmod(0o700)
        payload = f"synthetic {kind} proof for MPV-061 {evidence_id}\n".encode()
        target.write_bytes(payload)
        target.chmod(0o600)
        evidence.append(
            {
                "id": evidence_id,
                "kind": kind,
                "path": relative.as_posix(),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "runRef": run_ref,
                "sessionRefs": session_refs,
                "entityRefs": list(dict.fromkeys(evidence_entity_refs[evidence_id])),
            }
        )

    def turn(
        ordinal: int,
        kind: str,
        *,
        mode: str,
        directly_addressed: bool,
        output_audio: str | None,
        effects: dict[str, int],
    ) -> dict[str, object]:
        return {
            "ordinal": ordinal,
            "kind": kind,
            "runRef": run_ref,
            "sessionRef": initial_session,
            "conversationRef": conversation_ref,
            "mode": mode,
            "modeAuthoritySource": "persisted_call_session",
            "actorTrust": "owner_participant",
            "directlyAddressed": directly_addressed,
            "sideEffectAuthorityGranted": directly_addressed
            and mode in {"call", "wing"},
            "logicalTurnRef": _ref(f"turn-{ordinal}"),
            "logicalRevision": ordinal,
            "transcriptVisible": True,
            "inputAudioCaptured": True,
            "transcriptMatchedAudio": True,
            "transcriptEvidence": "initial-transcript",
            "inputAudioEvidence": "initial-audio",
            "outputAudioEvidence": output_audio,
            "assistantSpeakerRef": queen_ref if output_audio else None,
            "effects": effects,
            "evidence": ["initial-transcript", "initial-audio", "logical-turn-ledger"],
        }

    call_launch = turn(
        1,
        "authorizedCallLaunch",
        mode="call",
        directly_addressed=True,
        output_audio="initial-audio",
        effects=_effects(
            missionCount=2,
            launchInvocationCount=1,
            toolInvocationCount=1,
            controllerInvocationCount=1,
            mainResponseCount=1,
            ttsInputCount=1,
            assistantAudioOutputCount=1,
        ),
    )
    call_launch["requestedWorkerRefs"] = [worker_a, worker_b]
    call_launch["acceptedWorkerRefs"] = [worker_a, worker_b]
    call_launch["acceptedLaunchReceiptRefs"] = [launch_a, launch_b]
    call_launch["rejectedLaunchReceiptCount"] = 0
    call_launch["evidence"] += ["worker-ledger", "action-ledger", "mode-ledger"]

    trusted_launch = turn(
        2,
        "trustedWingLaunch",
        mode="wing",
        directly_addressed=True,
        output_audio="initial-audio",
        effects=_effects(
            missionCount=1,
            launchInvocationCount=1,
            toolInvocationCount=1,
            controllerInvocationCount=1,
            mainResponseCount=1,
            ttsInputCount=1,
            assistantAudioOutputCount=1,
        ),
    )
    trusted_launch["requestedWorkerRefs"] = [wing_worker]
    trusted_launch["acceptedWorkerRefs"] = [wing_worker]
    trusted_launch["acceptedLaunchReceiptRefs"] = [wing_launch]
    trusted_launch["rejectedLaunchReceiptCount"] = 0
    trusted_launch["evidence"] += ["worker-ledger", "action-ledger", "mode-ledger"]

    quick_turn = turn(
        3,
        "quickConversation",
        mode="call",
        directly_addressed=True,
        output_audio="initial-audio",
        effects=_effects(
            mainResponseCount=1,
            ttsInputCount=1,
            assistantAudioOutputCount=1,
        ),
    )
    quick_turn.update(
        {
            "currentReply": True,
            "unrelatedToWorkerMissions": True,
            "activeWorkerRefs": [worker_a, worker_b],
            "workerMutationCount": 0,
        }
    )

    call_control = turn(
        4,
        "authorizedCallControl",
        mode="call",
        directly_addressed=True,
        output_audio="initial-audio",
        effects=_effects(
            actionCount=1,
            controlInvocationCount=1,
            toolInvocationCount=1,
            controllerInvocationCount=1,
            mainResponseCount=1,
            ttsInputCount=1,
            assistantAudioOutputCount=1,
        ),
    )
    call_control.update(
        {
            "action": "message",
            "actionRef": call_action_ref,
            "acceptedActionReceiptRef": call_action_receipt,
            "targetWorkerRef": worker_a,
            "targetMissionRef": mission_a,
            "targetAttemptRef": attempt_a,
            "nonTargetWorkerRef": worker_b,
            "targetActionReceiptCount": 1,
            "nonTargetActionReceiptCount": 0,
            "targetMutationCount": 1,
            "nonTargetMutationCount": 0,
        }
    )
    call_control["evidence"] += ["action-ledger", "worker-ledger", "mode-ledger"]

    trusted_control = turn(
        5,
        "trustedWingControl",
        mode="wing",
        directly_addressed=True,
        output_audio="initial-audio",
        effects=_effects(
            actionCount=1,
            controlInvocationCount=1,
            toolInvocationCount=1,
            controllerInvocationCount=1,
            mainResponseCount=1,
            ttsInputCount=1,
            assistantAudioOutputCount=1,
        ),
    )
    trusted_control.update(
        {
            "action": "steer",
            "actionRef": action_ref,
            "acceptedActionReceiptRef": action_receipt,
            "targetWorkerRef": worker_a,
            "targetMissionRef": mission_a,
            "targetAttemptRef": attempt_a,
            "nonTargetWorkerRef": worker_b,
            "targetActionReceiptCount": 1,
            "nonTargetActionReceiptCount": 0,
            "targetMutationCount": 1,
            "nonTargetMutationCount": 0,
        }
    )
    trusted_control["evidence"] += ["action-ledger", "worker-ledger", "mode-ledger"]

    passive_denial = turn(
        6,
        "passiveWingDenial",
        mode="wing",
        directly_addressed=False,
        output_audio=None,
        effects=_effects(),
    )
    passive_denial["sideEffectAuthorityGranted"] = False
    passive_denial["transcriptObservationCount"] = 1
    passive_denial["evidence"] += ["mode-ledger", "action-ledger"]

    listen_only_denial = turn(
        7,
        "listenOnlyDenial",
        mode="listen_only",
        directly_addressed=True,
        output_audio=None,
        effects=_effects(),
    )
    listen_only_denial["sideEffectAuthorityGranted"] = False
    listen_only_denial["ambientTranscriptCount"] = 1
    listen_only_denial["evidence"] += ["mode-ledger", "action-ledger"]

    def completion(
        ordinal: int,
        worker_ref: str,
        mission_ref: str,
        attempt_ref: str,
        artifact_ref: str,
    ) -> dict[str, object]:
        return {
            "ordinal": ordinal,
            "kind": "workerCompletion",
            "runRef": run_ref,
            "sessionRef": reconnect_session,
            "conversationRef": conversation_ref,
            "mode": "call",
            "logicalTurnRef": _ref(f"turn-{ordinal}"),
            "logicalRevision": ordinal,
            "workerRef": worker_ref,
            "missionRef": mission_ref,
            "attemptRef": attempt_ref,
            "artifactRef": artifact_ref,
            "truthful": True,
            "spokenStatusOrCompletionCount": 1,
            "duplicateSpeechCount": 0,
            "transcriptVisible": True,
            "transcriptMatchedAudio": True,
            "transcriptEvidence": "reconnect-transcript",
            "outputAudioEvidence": "reconnect-audio",
            "assistantSpeakerRef": queen_ref,
            "effects": _effects(
                mainResponseCount=1,
                ttsInputCount=1,
                assistantAudioOutputCount=1,
            ),
            "evidence": [
                "reconnect-transcript",
                "reconnect-audio",
                "logical-turn-ledger",
                "delivery-ledger",
            ],
        }

    workers = [
        {
            "label": "A",
            "runRef": run_ref,
            "launchSessionRef": initial_session,
            "workerRef": worker_a,
            "missionRef": mission_a,
            "attemptRef": attempt_a,
            "acceptedLaunchReceiptRef": launch_a,
            "launchTurnRef": _ref("turn-1"),
            "launchMode": "call",
            "accepted": True,
            "independent": True,
            "contextBindingMatched": True,
            "requiredCapabilitiesPreserved": True,
            "fallbackCapabilityLossCount": 0,
            "memoryRecallReceiptCount": 1,
            "connectedToolReceiptCount": 0,
            "inputRefs": [upload_a],
            "observedInputRefs": [upload_a],
            "activeAtHangup": True,
            "cancelledByHangup": False,
            "reconnectMissionRef": mission_a,
            "terminalState": "completed",
            "attemptCount": 1,
            "callbackCount": 1,
            "deliveryCount": 1,
            "artifactRef": artifact_a,
            "spokenCompletionCount": 1,
            "evidence": [
                "worker-ledger",
                "capability-ledger",
                "callback-ledger",
                "delivery-ledger",
                "artifact-a-open",
            ],
        },
        {
            "label": "B",
            "runRef": run_ref,
            "launchSessionRef": initial_session,
            "workerRef": worker_b,
            "missionRef": mission_b,
            "attemptRef": attempt_b,
            "acceptedLaunchReceiptRef": launch_b,
            "launchTurnRef": _ref("turn-1"),
            "launchMode": "call",
            "accepted": True,
            "independent": True,
            "contextBindingMatched": True,
            "requiredCapabilitiesPreserved": True,
            "fallbackCapabilityLossCount": 0,
            "memoryRecallReceiptCount": 0,
            "connectedToolReceiptCount": 1,
            "inputRefs": [upload_b],
            "observedInputRefs": [upload_b],
            "activeAtHangup": True,
            "cancelledByHangup": False,
            "reconnectMissionRef": mission_b,
            "terminalState": "completed",
            "attemptCount": 1,
            "callbackCount": 1,
            "deliveryCount": 1,
            "artifactRef": artifact_b,
            "spokenCompletionCount": 1,
            "evidence": [
                "worker-ledger",
                "capability-ledger",
                "callback-ledger",
                "delivery-ledger",
                "artifact-b-open",
            ],
        },
    ]

    deliveries = []
    for worker, artifact_sha, open_evidence, artifact_evidence in (
        (workers[0], _digest("artifact-a-bytes"), "artifact-a-open", "artifact-a-file"),
        (workers[1], _digest("artifact-b-bytes"), "artifact-b-open", "artifact-b-file"),
    ):
        deliveries.append(
            {
                "runRef": run_ref,
                "workerRef": worker["workerRef"],
                "missionRef": worker["missionRef"],
                "attemptRef": worker["attemptRef"],
                "artifactRef": worker["artifactRef"],
                "artifactSha256": artifact_sha,
                "artifactEvidence": artifact_evidence,
                "callbackCount": 1,
                "linkedChatDeliveryCount": 1,
                "activeWorkDeliveryCount": 1,
                "duplicateDeliveryCount": 0,
                "deliveredAfterHangup": True,
                "reconnectSessionRef": reconnect_session,
                "opened": True,
                "openOrDownloadActionWorked": True,
                "evidence": [
                    "callback-ledger",
                    "delivery-ledger",
                    "linked-after",
                    "active-after",
                    open_evidence,
                ],
            }
        )

    identity = _artifact_identity()
    candidate_digest = _canonical_digest(
        {
            "source": identity["source"],
            "nestedComponents": identity["nestedComponents"],
            "prebuiltHelper": identity["prebuiltHelper"],
        }
    )
    artifact_digest = _canonical_digest(identity["installed"])
    manifest: dict[str, object] = {
        "schema": "viventium.voice.mpv-061.full-journey-evidence.v1",
        "caseId": "MPV-061",
        "scope": "full_journey",
        "runAt": NOW.isoformat(),
        "candidate": {
            "candidateDigest": candidate_digest,
            "artifactDigest": artifact_digest,
        },
        "run": {
            "runRef": run_ref,
            "initialSessionRef": initial_session,
            "reconnectSessionRef": reconnect_session,
            "conversationRef": conversation_ref,
            "reconnectConversationRef": conversation_ref,
            "initialSessionEnded": True,
            "reconnectExplicitlyStarted": True,
            "acceptedWorkCancelledByHangupCount": 0,
            "unsolicitedResultCallCount": 0,
            "modeAuthoritySource": "persisted_call_session",
            "evidence": ["session-ledger", "mode-ledger"],
        },
        "evidence": evidence,
        "voice": {
            "queenSpeakerRef": queen_ref,
            "observedAssistantSpeakerRefs": [queen_ref],
            "wingProbe": {
                "runRef": run_ref,
                "sessionRef": initial_session,
                "workerRef": wing_worker,
                "missionRef": wing_mission,
                "attemptRef": wing_attempt,
                "acceptedLaunchReceiptRef": wing_launch,
                "launchTurnRef": _ref("turn-2"),
                "cleanupAction": "stop",
                "cleanupActionRef": wing_cleanup,
                "cleanupReceiptRef": wing_cleanup_receipt,
                "cleanupActionReceiptCount": 1,
                "terminalState": "cancelled_confirmed",
                "deliveryCount": 0,
                "completedBeforeHangup": True,
                "evidence": ["worker-ledger", "action-ledger"],
            },
            "turnOrder": [
                "authorizedCallLaunch",
                "trustedWingLaunch",
                "quickConversation",
                "authorizedCallControl",
                "trustedWingControl",
                "passiveWingDenial",
                "listenOnlyDenial",
            ],
            "turns": {
                "authorizedCallLaunch": call_launch,
                "trustedWingLaunch": trusted_launch,
                "quickConversation": quick_turn,
                "authorizedCallControl": call_control,
                "trustedWingControl": trusted_control,
                "passiveWingDenial": passive_denial,
                "listenOnlyDenial": listen_only_denial,
            },
            "completionTurns": [
                completion(8, worker_a, mission_a, attempt_a, artifact_a),
                completion(9, worker_b, mission_b, attempt_b, artifact_b),
            ],
        },
        "workers": workers,
        "inputGroup": {
            "ingressSurface": "linked_chat",
            "ordered": [
                {
                    "ordinal": 1,
                    "uploadRef": upload_a,
                    "sha256": _digest("upload-a-bytes"),
                    "bytes": len(b"upload-a-bytes"),
                    "targetWorkerRef": worker_a,
                    "sourceEvidence": "input-a-file",
                },
                {
                    "ordinal": 2,
                    "uploadRef": upload_b,
                    "sha256": _digest("upload-b-bytes"),
                    "bytes": len(b"upload-b-bytes"),
                    "targetWorkerRef": worker_b,
                    "sourceEvidence": "input-b-file",
                },
            ],
            "crossWorkerLeakCount": 0,
            "evidence": ["upload-ledger"],
        },
        "deliveries": deliveries,
        "surfaceContinuity": {
            "linkedChatBeforeHangupWorkerRefs": [worker_a, worker_b],
            "linkedChatAfterReconnectWorkerRefs": [worker_a, worker_b],
            "activeWorkBeforeHangupWorkerRefs": [worker_a, worker_b],
            "activeWorkAfterReconnectWorkerRefs": [worker_a, worker_b],
            "evidence": [
                "linked-before",
                "linked-after",
                "active-before",
                "active-after",
            ],
        },
        "resilience": {
            "fallback": {
                "required": True,
                "observed": True,
                "controlReceiptRef": fallback_control_receipt,
                "controlReceiptCount": 1,
                "failure": "provider_temporarily_unavailable",
                "preModel": True,
                "primaryProvider": "fixture-primary-provider",
                "primaryModel": "fixture-primary-model",
                "primaryStartedCount": 0,
                "primaryCompletedCount": 0,
                "providerHealthMutationCount": 0,
                "providerHealthSuppressed": False,
                "fallbackProvider": "fixture-fallback-provider",
                "fallbackModel": "fixture-fallback-model",
                "fallbackStartedCount": 1,
                "fallbackCompletedCount": 1,
                "providerFallbackCompletedCount": 1,
                "primaryAttemptRef": fallback_primary,
                "fallbackAttemptRef": fallback_attempt,
                "workerRefs": [worker_a, worker_b],
                "missionRefs": [mission_a, mission_b],
                "requiredCapabilitiesPreserved": True,
                "mainAvailable": True,
                "duplicateLaunchReceiptCount": 0,
                "evidence": ["capability-ledger", "worker-ledger"],
            },
            "restart": {
                "required": True,
                "observed": True,
                "beforeRuntimeRef": restart_before,
                "afterRuntimeRef": restart_after,
                "workerRefs": [worker_a, worker_b],
                "missionRefs": [mission_a, mission_b],
                "mainAvailableBefore": True,
                "mainAvailableAfter": True,
                "lostMissionCount": 0,
                "duplicateLaunchReceiptCount": 0,
                "evidence": ["session-ledger", "worker-ledger"],
            },
        },
        "publicSafety": {
            "rawEvidencePrivate": True,
            "publicReportContentFree": True,
            "reviewed": True,
            "evidence": ["public-safety"],
        },
    }
    evidence_by_id = {item["id"]: item for item in evidence}
    binary_payloads = {
        "initial-audio": _wav_audio(1),
        "reconnect-audio": _wav_audio(2),
        "input-a-file": b"upload-a-bytes",
        "input-b-file": b"upload-b-bytes",
        "artifact-a-file": b"artifact-a-bytes",
        "artifact-b-file": b"artifact-b-bytes",
    }
    for item in evidence:
        item["candidateDigest"] = candidate_digest
        item["artifactDigest"] = artifact_digest
        item["observedAt"] = manifest["runAt"]
        if item["id"] not in binary_payloads:
            continue
        payload = binary_payloads[item["id"]]
        target = root / item["path"]
        target.write_bytes(payload)
        target.chmod(0o600)
        item["sha256"] = hashlib.sha256(payload).hexdigest()

    for item in evidence:
        if item["id"] in binary_payloads:
            continue
        document = {
            "contractVersion": 1,
            "schema": "viventium.voice.mpv-061.observation.v1",
            "kind": item["kind"],
            "runRef": item["runRef"],
            "sessionRefs": item["sessionRefs"],
            "entityRefs": item["entityRefs"],
            "candidateDigest": item["candidateDigest"],
            "artifactDigest": item["artifactDigest"],
            "observedAt": item["observedAt"],
            "observations": _structural_observations(
                item["id"], manifest, evidence_by_id
            ),
        }
        payload = (
            json.dumps(document, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        )
        target = root / item["path"]
        target.write_bytes(payload)
        target.chmod(0o600)
        item["sha256"] = hashlib.sha256(payload).hexdigest()

    manifest_path = root / "mpv-061-evidence.json"
    identity_path = root / "candidate-identity.json"
    result_path = root / "mpv-061-result.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    identity_path.write_text(json.dumps(identity, indent=2) + "\n", encoding="utf-8")
    manifest_path.chmod(0o600)
    identity_path.chmod(0o600)
    return manifest_path, identity_path, result_path, manifest


def rebind_manifest_candidate(
    manifest: dict[str, object],
    evidence_root: Path,
    *,
    candidate_digest: str,
    artifact_digest: str,
) -> None:
    manifest["candidate"] = {
        "candidateDigest": candidate_digest,
        "artifactDigest": artifact_digest,
    }
    for entry in manifest["evidence"]:
        entry["candidateDigest"] = candidate_digest
        entry["artifactDigest"] = artifact_digest
        if entry["kind"] in {"voice_recording", "input_file", "delivered_artifact"}:
            continue
        evidence_path = evidence_root / entry["path"]
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


def complete_manifest(
    tmp_path: Path,
    *,
    candidate_digest: str | None = None,
    artifact_digest: str | None = None,
) -> tuple[dict[str, object], Path, str, str]:
    evidence_root = tmp_path / "mpv-061-private-evidence"
    manifest_path, _, _, manifest = _write_full_journey_fixture(evidence_root)
    original_candidate = manifest["candidate"]["candidateDigest"]
    original_artifact = manifest["candidate"]["artifactDigest"]
    if (candidate_digest is None) != (artifact_digest is None):
        raise ValueError("candidate and artifact digests must be provided together")
    if candidate_digest is not None and artifact_digest is not None:
        rebind_manifest_candidate(
            manifest,
            evidence_root,
            candidate_digest=candidate_digest,
            artifact_digest=artifact_digest,
        )
        manifest_path.write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        manifest_path.chmod(0o600)
    return manifest, evidence_root, original_candidate, original_artifact


def _run_fixture(
    root: Path,
) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    manifest_path, identity_path, result_path, _ = _write_full_journey_fixture(root)
    return _run_paths(root, manifest_path, identity_path, result_path)


def _run_paths(
    root: Path,
    manifest_path: Path,
    identity_path: Path,
    result_path: Path,
) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    completed = subprocess.run(
        [
            "node",
            str(RUNNER),
            "--manifest",
            str(manifest_path),
            "--evidence-root",
            str(root),
            "--artifact-identity",
            str(identity_path),
            "--result",
            str(result_path),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    result = (
        json.loads(result_path.read_text(encoding="utf-8"))
        if result_path.exists()
        else {}
    )
    return completed, result


def _load_python_adapter():
    spec = importlib.util.spec_from_file_location(
        "mpv_061_semantic_verifier_test", PYTHON_ADAPTER
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _set_path(
    value: dict[str, object], keys: tuple[object, ...], replacement: object
) -> None:
    current: object = value
    for key in keys[:-1]:
        current = current[key]  # type: ignore[index]
    current[keys[-1]] = replacement  # type: ignore[index]


def test_mpv_061_full_journey_runner_assets_are_explicit_and_fail_closed() -> None:
    assert RUNNER.exists()
    assert EVIDENCE_TEMPLATE.exists()
    assert RESULT_TEMPLATE.exists()

    evidence = json.loads(EVIDENCE_TEMPLATE.read_text(encoding="utf-8"))
    result = json.loads(RESULT_TEMPLATE.read_text(encoding="utf-8"))

    assert evidence["schema"] == ("viventium.voice.mpv-061.full-journey-evidence.v1")
    assert evidence["caseId"] == "MPV-061"
    assert evidence["scope"] == "full_journey"
    assert result["schema"] == "viventium.voice.mpv-061.full-journey-result.v1"
    assert result["caseId"] == "MPV-061"
    assert result["status"] == "BLOCKED"
    assert result["scope"] == "full_journey"
    assert result["fullJourneyStatus"] == "NOT_RUN"
    assert result["authoritySliceOnlyPassAccepted"] is False

    source = RUNNER.read_text(encoding="utf-8")
    assert "authority_slice_only" in source
    assert "full_journey" in source
    assert "authoritySliceOnlyPassAccepted" in source


def test_mpv_061_complete_bound_semantic_journey_passes_content_free(
    tmp_path: Path,
) -> None:
    completed, result = _run_fixture(tmp_path / "private-evidence")

    assert completed.returncode == 0, completed.stderr
    assert result["schema"] == "viventium.voice.mpv-061.full-journey-result.v1"
    assert result["caseId"] == "MPV-061"
    assert result["status"] == "PASS"
    assert result["scope"] == "full_journey"
    assert result["fullJourneyStatus"] == "PASS"
    assert result["authoritySliceOnlyPassAccepted"] is False
    assert result["candidateBinding"]["matched"] is True
    assert result["counts"] == {
        "sessions": 2,
        "workers": 2,
        "actions": 2,
        "inputs": 2,
        "deliveries": 2,
        "artifactsOpened": 2,
        "audiblePositiveTurns": 7,
        "denialTurns": 2,
        "verifiedEvidenceFiles": 24,
    }
    assert result["gates"]
    assert all(gate["status"] == "PASS" for gate in result["gates"])
    assert result["privacy"] == {
        "publicSafe": True,
        "rawIdentifiersIncluded": False,
        "rawTranscriptIncluded": False,
        "localPathsIncluded": False,
    }

    serialized = json.dumps(result)
    assert str(tmp_path) not in serialized
    for private_value in (
        _ref("run"),
        _ref("initial-session"),
        _ref("worker-a"),
        _ref("steer-a"),
        "synthetic voice_recording proof",
    ):
        assert private_value not in serialized


@pytest.mark.parametrize(
    ("name", "path", "replacement", "failed_gate"),
    [
        (
            "authority-slice",
            ("scope",),
            "authority_slice_only",
            "full-journey-scope",
        ),
        (
            "candidate-mismatch",
            ("candidate", "candidateDigest"),
            "f" * 64,
            "candidate-binding",
        ),
        (
            "session-mismatch",
            ("run", "reconnectConversationRef"),
            _ref("wrong-conversation"),
            "exact-session-and-reconnect-binding",
        ),
        (
            "worker-alias",
            ("workers", 1, "workerRef"),
            _ref("worker-a"),
            "two-exact-independent-workers",
        ),
        (
            "launch-not-addressed",
            ("voice", "turns", "trustedWingLaunch", "directlyAddressed"),
            False,
            "trusted-direct-wing-launch",
        ),
        (
            "call-launch-untrusted-speaker",
            ("voice", "turns", "authorizedCallLaunch", "actorTrust"),
            "unverified_participant",
            "authorized-call-launch",
        ),
        (
            "call-launch-without-authority",
            ("voice", "turns", "authorizedCallLaunch", "sideEffectAuthorityGranted"),
            False,
            "authorized-call-launch",
        ),
        (
            "call-control-wrong-worker",
            ("voice", "turns", "authorizedCallControl", "targetWorkerRef"),
            _ref("worker-b"),
            "authorized-call-control-a-only",
        ),
        (
            "call-control-wrong-action",
            ("voice", "turns", "authorizedCallControl", "action"),
            "queue",
            "authorized-call-control-a-only",
        ),
        (
            "trusted-wing-probe-not-cleaned-up",
            ("voice", "wingProbe", "terminalState"),
            "running",
            "trusted-direct-wing-launch",
        ),
        (
            "trusted-wing-probe-leaks-delivery",
            ("voice", "wingProbe", "deliveryCount"),
            1,
            "trusted-direct-wing-launch",
        ),
        (
            "main-not-available-during-work",
            ("voice", "turns", "quickConversation", "currentReply"),
            False,
            "main-responsive-quick-turn",
        ),
        (
            "quick-turn-mutates-worker",
            ("voice", "turns", "quickConversation", "workerMutationCount"),
            1,
            "main-responsive-quick-turn",
        ),
        (
            "cross-worker-steer",
            ("voice", "turns", "trustedWingControl", "targetWorkerRef"),
            _ref("worker-b"),
            "trusted-direct-wing-steer-a-only",
        ),
        (
            "passive-wing-side-effect",
            (
                "voice",
                "turns",
                "passiveWingDenial",
                "effects",
                "toolInvocationCount",
            ),
            1,
            "passive-wing-zero-authority",
        ),
        (
            "listen-only-response",
            (
                "voice",
                "turns",
                "listenOnlyDenial",
                "effects",
                "mainResponseCount",
            ),
            1,
            "listen-only-zero-authority",
        ),
        (
            "listen-only-recall",
            ("voice", "turns", "listenOnlyDenial", "effects", "recallInvocationCount"),
            1,
            "listen-only-zero-authority",
        ),
        (
            "listen-only-live-memory",
            (
                "voice",
                "turns",
                "listenOnlyDenial",
                "effects",
                "liveMemoryInvocationCount",
            ),
            1,
            "listen-only-zero-authority",
        ),
        (
            "passive-wing-launch",
            ("voice", "turns", "passiveWingDenial", "effects", "missionCount"),
            1,
            "passive-wing-zero-authority",
        ),
        (
            "input-file-reordered",
            ("inputGroup", "ordered", 0, "ordinal"),
            2,
            "exact-ordered-file-binding",
        ),
        (
            "input-file-leaks-between-workers",
            ("inputGroup", "crossWorkerLeakCount"),
            1,
            "exact-ordered-file-binding",
        ),
        (
            "worker-loses-required-capability",
            ("workers", 0, "requiredCapabilitiesPreserved"),
            False,
            "worker-context-capability-parity",
        ),
        (
            "worker-fallback-loses-capability",
            ("workers", 0, "fallbackCapabilityLossCount"),
            1,
            "worker-context-capability-parity",
        ),
        (
            "duplicate-result-delivery",
            ("deliveries", 0, "duplicateDeliveryCount"),
            1,
            "callback-delivery-and-artifact-once",
        ),
        (
            "artifact-cannot-open",
            ("deliveries", 0, "openOrDownloadActionWorked"),
            False,
            "callback-delivery-and-artifact-once",
        ),
        (
            "artifact-bytes-do-not-match",
            ("deliveries", 0, "artifactSha256"),
            _digest("wrong-artifact"),
            "callback-delivery-and-artifact-once",
        ),
        (
            "duplicate-spoken-completion",
            ("voice", "completionTurns", 0, "duplicateSpeechCount"),
            1,
            "audible-transcript-audio-and-sole-queen",
        ),
        (
            "unsolicited-result-call",
            ("run", "unsolicitedResultCallCount"),
            1,
            "exact-session-and-reconnect-binding",
        ),
        (
            "hangup-cancels-worker",
            ("workers", 0, "cancelledByHangup"),
            True,
            "hangup-reconnect-surface-continuity",
        ),
        (
            "fallback-silently-removes-capability",
            ("resilience", "fallback", "requiredCapabilitiesPreserved"),
            False,
            "required-fallback-capability-parity",
        ),
        (
            "fallback-makes-main-unavailable",
            ("resilience", "fallback", "mainAvailable"),
            False,
            "required-fallback-capability-parity",
        ),
        (
            "fallback-control-receipt-missing",
            ("resilience", "fallback", "controlReceiptCount"),
            0,
            "required-fallback-capability-parity",
        ),
        (
            "controlled-primary-started",
            ("resilience", "fallback", "primaryStartedCount"),
            1,
            "required-fallback-capability-parity",
        ),
        (
            "configured-fallback-not-started",
            ("resilience", "fallback", "fallbackStartedCount"),
            0,
            "required-fallback-capability-parity",
        ),
        (
            "provider-health-mutated",
            ("resilience", "fallback", "providerHealthMutationCount"),
            1,
            "required-fallback-capability-parity",
        ),
        (
            "restart-loses-mission",
            ("resilience", "restart", "lostMissionCount"),
            1,
            "required-restart-main-availability",
        ),
        (
            "restart-makes-main-unavailable",
            ("resilience", "restart", "mainAvailableAfter"),
            False,
            "required-restart-main-availability",
        ),
        (
            "missing-audible-output",
            ("voice", "turns", "trustedWingLaunch", "outputAudioEvidence"),
            None,
            "trusted-direct-wing-launch",
        ),
        (
            "audio-transcript-mismatch",
            ("voice", "turns", "trustedWingControl", "transcriptMatchedAudio"),
            False,
            "trusted-direct-wing-steer-a-only",
        ),
        (
            "cross-session-audio",
            ("voice", "turns", "trustedWingLaunch", "inputAudioEvidence"),
            "reconnect-audio",
            "trusted-direct-wing-launch",
        ),
        (
            "replayed-logical-revision",
            ("voice", "turns", "trustedWingControl", "logicalRevision"),
            1,
            "ordered-logical-turn-revisions",
        ),
    ],
)
def test_mpv_061_semantic_runner_rejects_partial_or_mismatched_journeys(
    tmp_path: Path,
    name: str,
    path: tuple[object, ...],
    replacement: object,
    failed_gate: str,
) -> None:
    root = tmp_path / name
    manifest_path, identity_path, result_path, manifest = _write_full_journey_fixture(
        root
    )
    _set_path(manifest, path, replacement)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    completed, result = _run_paths(root, manifest_path, identity_path, result_path)

    assert completed.returncode == 1, completed.stderr
    assert result["status"] == "FAIL"
    assert result["fullJourneyStatus"] == "FAIL"
    assert result["authoritySliceOnlyPassAccepted"] is False
    gates = {gate["id"]: gate["status"] for gate in result["gates"]}
    assert gates[failed_gate] == "FAIL"
    assert "PASS\n" not in completed.stdout


@pytest.mark.parametrize(
    ("evidence_id", "missing_ref", "failed_gate"),
    [
        ("initial-audio", _ref("turn-1"), "authorized-call-launch"),
        (
            "session-ledger",
            _ref("reconnect-session"),
            "exact-session-and-reconnect-binding",
        ),
        ("worker-ledger", _ref("worker-a"), "worker-context-capability-parity"),
        ("action-ledger", _ref("steer-a"), "trusted-direct-wing-steer-a-only"),
    ],
)
def test_mpv_061_raw_evidence_must_bind_the_exact_semantic_entity(
    tmp_path: Path,
    evidence_id: str,
    missing_ref: str,
    failed_gate: str,
) -> None:
    root = tmp_path / evidence_id
    manifest_path, identity_path, result_path, manifest = _write_full_journey_fixture(
        root
    )
    evidence = next(item for item in manifest["evidence"] if item["id"] == evidence_id)
    evidence["entityRefs"].remove(missing_ref)
    if evidence["kind"] not in {"voice_recording", "input_file", "delivered_artifact"}:
        evidence_path = root / evidence["path"]
        document = json.loads(evidence_path.read_text(encoding="utf-8"))
        document["entityRefs"].remove(missing_ref)
        payload = (
            json.dumps(document, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        )
        evidence_path.write_bytes(payload)
        evidence["sha256"] = hashlib.sha256(payload).hexdigest()
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    completed, result = _run_paths(root, manifest_path, identity_path, result_path)

    assert completed.returncode == 1, completed.stderr
    assert result["status"] == "FAIL"
    gates = {gate["id"]: gate["status"] for gate in result["gates"]}
    assert gates[failed_gate] == "FAIL"


def test_mpv_061_candidate_identity_is_measured_not_self_asserted(
    tmp_path: Path,
) -> None:
    root = tmp_path / "candidate-changed"
    manifest_path, identity_path, result_path, _ = _write_full_journey_fixture(root)
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    identity["source"]["revision"] = "3" * 40
    identity_path.write_text(json.dumps(identity, indent=2) + "\n", encoding="utf-8")

    completed, result = _run_paths(root, manifest_path, identity_path, result_path)

    assert completed.returncode == 2
    assert result["status"] == "BLOCKED"
    assert result["candidateBinding"]["matched"] is False
    assert result["failures"] == [{"code": "evidence_candidate_binding_mismatch"}]


def test_mpv_061_tampered_raw_evidence_blocks_before_semantic_pass(
    tmp_path: Path,
) -> None:
    root = tmp_path / "tampered-evidence"
    manifest_path, identity_path, result_path, manifest = _write_full_journey_fixture(
        root
    )
    audio = next(item for item in manifest["evidence"] if item["id"] == "initial-audio")
    (root / audio["path"]).write_bytes(b"tampered audio evidence")

    completed, result = _run_paths(root, manifest_path, identity_path, result_path)

    assert completed.returncode == 2
    assert result["status"] == "BLOCKED"
    assert result["fullJourneyStatus"] == "NOT_RUN"
    assert result["authoritySliceOnlyPassAccepted"] is False
    assert result["failures"] == [{"code": "evidence_digest_mismatch"}]


@pytest.mark.parametrize(
    ("payload", "failure_code"),
    (
        (b"caller says this audio is audible", "audio_evidence_invalid"),
        (
            _wav_audio(1)[:44] + b"\x00" * (len(_wav_audio(1)) - 44),
            "audio_evidence_invalid",
        ),
    ),
)
def test_mpv_061_audio_must_be_real_non_silent_wav(
    tmp_path: Path,
    payload: bytes,
    failure_code: str,
) -> None:
    root = tmp_path / "invalid-audio"
    manifest_path, identity_path, result_path, manifest = _write_full_journey_fixture(
        root
    )
    audio = next(item for item in manifest["evidence"] if item["id"] == "initial-audio")
    (root / audio["path"]).write_bytes(payload)
    audio["sha256"] = hashlib.sha256(payload).hexdigest()
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    completed, result = _run_paths(root, manifest_path, identity_path, result_path)

    assert completed.returncode == 2
    assert result["status"] == "BLOCKED"
    assert result["failures"] == [{"code": failure_code}]


def test_mpv_061_structural_document_cannot_bind_another_candidate(
    tmp_path: Path,
) -> None:
    root = tmp_path / "cross-candidate-document"
    manifest_path, identity_path, result_path, manifest = _write_full_journey_fixture(
        root
    )
    entry = next(item for item in manifest["evidence"] if item["id"] == "worker-ledger")
    evidence_path = root / entry["path"]
    document = json.loads(evidence_path.read_text(encoding="utf-8"))
    document["candidateDigest"] = "f" * 64
    payload = (
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    )
    evidence_path.write_bytes(payload)
    entry["sha256"] = hashlib.sha256(payload).hexdigest()
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    completed, result = _run_paths(root, manifest_path, identity_path, result_path)

    assert completed.returncode == 2
    assert result["failures"] == [{"code": "evidence_semantic_invalid"}]


@pytest.mark.parametrize("handoff_field", ("inputRefs", "observedInputRefs"))
def test_mpv_061_worker_file_handoff_requires_structural_worker_observation(
    tmp_path: Path,
    handoff_field: str,
) -> None:
    root = tmp_path / "unobserved-file-handoff"
    manifest_path, identity_path, result_path, manifest = _write_full_journey_fixture(
        root
    )
    ledger = next(
        item for item in manifest["evidence"] if item["id"] == "worker-ledger"
    )
    ledger_path = root / ledger["path"]
    document = json.loads(ledger_path.read_text(encoding="utf-8"))
    observation = next(
        item
        for item in document["observations"]
        if item["type"] == "worker" and item["workerRef"] == _ref("worker-a")
    )
    observation[handoff_field] = [_ref("another-worker-upload")]
    payload = (
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    )
    ledger_path.write_bytes(payload)
    ledger["sha256"] = hashlib.sha256(payload).hexdigest()
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    completed, result = _run_paths(root, manifest_path, identity_path, result_path)

    assert completed.returncode == 1
    assert result["status"] == "FAIL"
    assert (
        next(
            gate
            for gate in result["gates"]
            if gate["id"] == "exact-ordered-file-binding"
        )["status"]
        == "FAIL"
    )


@pytest.mark.parametrize(
    ("turn_name", "failed_gate"),
    (
        ("passiveWingDenial", "passive-wing-zero-authority"),
        ("listenOnlyDenial", "listen-only-zero-authority"),
    ),
)
def test_mpv_061_passive_modes_cannot_hide_unrecognized_side_effects(
    tmp_path: Path,
    turn_name: str,
    failed_gate: str,
) -> None:
    root = tmp_path / "unrecognized-passive-effect"
    manifest_path, identity_path, result_path, manifest = _write_full_journey_fixture(
        root
    )
    turn = manifest["voice"]["turns"][turn_name]
    turn["effects"]["unrecognizedInvocationCount"] = 1
    for evidence in manifest["evidence"]:
        if evidence["kind"] in {"voice_recording", "input_file", "delivered_artifact"}:
            continue
        evidence_path = root / evidence["path"]
        document = json.loads(evidence_path.read_text(encoding="utf-8"))
        changed = False
        for observation in document["observations"]:
            if observation.get("logicalTurnRef") == turn["logicalTurnRef"]:
                observation["effects"]["unrecognizedInvocationCount"] = 1
                changed = True
        if changed:
            payload = (
                json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
                + b"\n"
            )
            evidence_path.write_bytes(payload)
            evidence["sha256"] = hashlib.sha256(payload).hexdigest()
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    completed, result = _run_paths(root, manifest_path, identity_path, result_path)

    assert completed.returncode == 1
    assert result["status"] == "FAIL"
    assert next(gate for gate in result["gates"] if gate["id"] == failed_gate)[
        "status"
    ] == ("FAIL")


@pytest.mark.parametrize(
    ("turn_name", "observed_action", "failed_gate"),
    (
        ("authorizedCallControl", "steer", "authorized-call-control-a-only"),
        ("trustedWingControl", "message", "trusted-direct-wing-steer-a-only"),
    ),
)
def test_mpv_061_worker_control_action_must_match_structural_receipt(
    tmp_path: Path,
    turn_name: str,
    observed_action: str,
    failed_gate: str,
) -> None:
    root = tmp_path / "mismatched-control-action"
    manifest_path, identity_path, result_path, manifest = _write_full_journey_fixture(
        root
    )
    ledger = next(
        item for item in manifest["evidence"] if item["id"] == "action-ledger"
    )
    ledger_path = root / ledger["path"]
    document = json.loads(ledger_path.read_text(encoding="utf-8"))
    logical_turn = manifest["voice"]["turns"][turn_name]["logicalTurnRef"]
    observation = next(
        item
        for item in document["observations"]
        if item.get("logicalTurnRef") == logical_turn
    )
    observation["action"] = observed_action
    payload = (
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    )
    ledger_path.write_bytes(payload)
    ledger["sha256"] = hashlib.sha256(payload).hexdigest()
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    completed, result = _run_paths(root, manifest_path, identity_path, result_path)

    assert completed.returncode == 1
    assert next(gate for gate in result["gates"] if gate["id"] == failed_gate)[
        "status"
    ] == ("FAIL")


@pytest.mark.parametrize(
    ("evidence_id", "observation_type", "field", "replacement", "failed_gate"),
    (
        (
            "mode-ledger",
            "turn",
            "actorTrust",
            "unverified_participant",
            "authorized-call-launch",
        ),
        (
            "worker-ledger",
            "worker",
            "terminalState",
            "failed",
            "worker-context-capability-parity",
        ),
        (
            "capability-ledger",
            "fallback",
            "mainAvailable",
            False,
            "required-fallback-capability-parity",
        ),
        (
            "session-ledger",
            "restart",
            "mainAvailableAfter",
            False,
            "required-restart-main-availability",
        ),
        (
            "delivery-ledger",
            "delivery",
            "duplicateDeliveryCount",
            1,
            "callback-delivery-and-artifact-once",
        ),
    ),
)
def test_mpv_061_semantic_truth_must_come_from_bound_structural_observations(
    tmp_path: Path,
    evidence_id: str,
    observation_type: str,
    field: str,
    replacement: object,
    failed_gate: str,
) -> None:
    root = tmp_path / f"mismatched-{evidence_id}"
    manifest_path, identity_path, result_path, manifest = _write_full_journey_fixture(
        root
    )
    entry = next(item for item in manifest["evidence"] if item["id"] == evidence_id)
    evidence_path = root / entry["path"]
    document = json.loads(evidence_path.read_text(encoding="utf-8"))
    observation = next(
        item for item in document["observations"] if item["type"] == observation_type
    )
    observation[field] = replacement
    payload = (
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    )
    evidence_path.write_bytes(payload)
    entry["sha256"] = hashlib.sha256(payload).hexdigest()
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    completed, result = _run_paths(root, manifest_path, identity_path, result_path)

    assert completed.returncode == 1
    assert (
        next(gate for gate in result["gates"] if gate["id"] == failed_gate)["status"]
        == "FAIL"
    )


@pytest.mark.parametrize(
    ("evidence_id", "failed_gate"),
    (
        ("input-a-file", "exact-ordered-file-binding"),
        ("artifact-a-file", "callback-delivery-and-artifact-once"),
    ),
)
def test_mpv_061_exact_input_and_output_bytes_are_measured(
    tmp_path: Path,
    evidence_id: str,
    failed_gate: str,
) -> None:
    root = tmp_path / f"wrong-{evidence_id}"
    manifest_path, identity_path, result_path, manifest = _write_full_journey_fixture(
        root
    )
    entry = next(item for item in manifest["evidence"] if item["id"] == evidence_id)
    payload = b"different synthetic bytes"
    (root / entry["path"]).write_bytes(payload)
    entry["sha256"] = hashlib.sha256(payload).hexdigest()
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    completed, result = _run_paths(root, manifest_path, identity_path, result_path)

    assert completed.returncode == 1
    assert (
        next(gate for gate in result["gates"] if gate["id"] == failed_gate)["status"]
        == "FAIL"
    )


def test_mpv_061_private_evidence_rejects_group_or_public_permissions(
    tmp_path: Path,
) -> None:
    root = tmp_path / "public-evidence"
    manifest_path, identity_path, result_path, manifest = _write_full_journey_fixture(
        root
    )
    evidence_path = root / manifest["evidence"][0]["path"]
    evidence_path.chmod(0o644)

    completed, result = _run_paths(root, manifest_path, identity_path, result_path)

    assert completed.returncode == 2
    assert result["failures"] == [{"code": "evidence_file_invalid"}]


@pytest.mark.parametrize("offset", (timedelta(hours=-25), timedelta(minutes=6)))
def test_mpv_061_rejects_stale_or_future_evidence_runs(
    tmp_path: Path,
    offset: timedelta,
) -> None:
    root = tmp_path / "invalid-run-time"
    manifest_path, identity_path, result_path, manifest = _write_full_journey_fixture(
        root
    )
    manifest["runAt"] = (datetime.now(timezone.utc) + offset).isoformat()
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    completed, result = _run_paths(root, manifest_path, identity_path, result_path)

    assert completed.returncode == 2
    assert result["failures"] == [{"code": "run_timestamp_invalid"}]


def test_mpv_061_reused_audio_cannot_prove_two_exact_sessions(tmp_path: Path) -> None:
    root = tmp_path / "reused-session-audio"
    manifest_path, identity_path, result_path, manifest = _write_full_journey_fixture(
        root
    )
    initial_audio = next(
        item for item in manifest["evidence"] if item["id"] == "initial-audio"
    )
    reconnect_audio = next(
        item for item in manifest["evidence"] if item["id"] == "reconnect-audio"
    )
    reused_audio = (root / initial_audio["path"]).read_bytes()
    (root / reconnect_audio["path"]).write_bytes(reused_audio)
    reconnect_audio["sha256"] = hashlib.sha256(reused_audio).hexdigest()
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    completed, result = _run_paths(root, manifest_path, identity_path, result_path)

    assert completed.returncode == 2
    assert result["status"] == "BLOCKED"
    assert result["failures"] == [{"code": "duplicate_session_evidence_content"}]


def test_mpv_061_result_symlink_cannot_escape_private_evidence_root(
    tmp_path: Path,
) -> None:
    root = tmp_path / "result-link"
    manifest_path, identity_path, result_path, _ = _write_full_journey_fixture(root)
    outside = tmp_path / "outside.json"
    sentinel = '{"sentinel":true}\n'
    outside.write_text(sentinel, encoding="utf-8")
    result_path.symlink_to(outside)

    completed, result = _run_paths(root, manifest_path, identity_path, result_path)

    assert completed.returncode == 2
    assert completed.stderr == "result_write_failed\n"
    assert result == {"sentinel": True}
    assert outside.read_text(encoding="utf-8") == sentinel


def test_mpv_061_wing_only_journey_cannot_close_normal_call_parity(
    tmp_path: Path,
) -> None:
    root = tmp_path / "wing-without-call"
    manifest_path, identity_path, result_path, manifest = _write_full_journey_fixture(
        root
    )
    manifest["voice"]["turns"].pop("authorizedCallLaunch", None)
    manifest["voice"]["turnOrder"] = [
        turn
        for turn in manifest["voice"]["turnOrder"]
        if turn != "authorizedCallLaunch"
    ]
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    completed, result = _run_paths(root, manifest_path, identity_path, result_path)

    assert completed.returncode == 1
    assert result["status"] == "FAIL"
    assert (
        next(
            gate for gate in result["gates"] if gate["id"] == "authorized-call-launch"
        )["status"]
        == "FAIL"
    )


def test_mpv_061_normal_call_must_also_control_the_exact_worker(
    tmp_path: Path,
) -> None:
    root = tmp_path / "call-without-control"
    manifest_path, identity_path, result_path, manifest = _write_full_journey_fixture(
        root
    )
    manifest["voice"]["turns"].pop("authorizedCallControl", None)
    manifest["voice"]["turnOrder"] = [
        turn
        for turn in manifest["voice"]["turnOrder"]
        if turn != "authorizedCallControl"
    ]
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    completed, result = _run_paths(root, manifest_path, identity_path, result_path)

    assert completed.returncode == 1
    assert result["status"] == "FAIL"
    assert (
        next(
            gate
            for gate in result["gates"]
            if gate["id"] == "authorized-call-control-a-only"
        )["status"]
        == "FAIL"
    )


def test_mpv_061_normal_call_must_launch_both_durable_worker_bees(
    tmp_path: Path,
) -> None:
    root = tmp_path / "call-launches-only-one"
    manifest_path, identity_path, result_path, manifest = _write_full_journey_fixture(
        root
    )
    call = manifest["voice"]["turns"]["authorizedCallLaunch"]
    call["requestedWorkerRefs"] = [_ref("worker-a")]
    call["acceptedWorkerRefs"] = [_ref("worker-a")]
    call["acceptedLaunchReceiptRefs"] = [_ref("launch-receipt-a")]
    call["effects"]["missionCount"] = 1
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    completed, result = _run_paths(root, manifest_path, identity_path, result_path)

    assert completed.returncode == 1
    assert (
        next(
            gate for gate in result["gates"] if gate["id"] == "authorized-call-launch"
        )["status"]
        == "FAIL"
    )


def test_mpv_061_caller_declared_pass_is_not_accepted(tmp_path: Path) -> None:
    root = tmp_path / "caller-declared-pass"
    manifest_path, identity_path, result_path, manifest = _write_full_journey_fixture(
        root
    )
    manifest["status"] = "PASS"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    completed, result = _run_paths(root, manifest_path, identity_path, result_path)

    assert completed.returncode == 2
    assert result["status"] == "BLOCKED"
    assert result["failures"] == [{"code": "caller_declared_pass_forbidden"}]


def test_mpv_061_every_private_evidence_file_must_bind_the_installed_candidate(
    tmp_path: Path,
) -> None:
    root = tmp_path / "cross-candidate-evidence"
    manifest_path, identity_path, result_path, manifest = _write_full_journey_fixture(
        root
    )
    manifest["evidence"][0]["candidateDigest"] = "f" * 64
    manifest["evidence"][0]["artifactDigest"] = manifest["candidate"]["artifactDigest"]
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    completed, result = _run_paths(root, manifest_path, identity_path, result_path)

    assert completed.returncode == 2
    assert result["status"] == "BLOCKED"
    assert result["failures"] == [{"code": "evidence_candidate_binding_mismatch"}]


def test_mpv_061_caller_declared_ledger_pass_cannot_replace_structural_proof(
    tmp_path: Path,
) -> None:
    root = tmp_path / "caller-declared-ledger"
    manifest_path, identity_path, result_path, manifest = _write_full_journey_fixture(
        root
    )
    ledger = next(
        item for item in manifest["evidence"] if item["id"] == "worker-ledger"
    )
    payload = b'{"status":"PASS"}\n'
    (root / ledger["path"]).write_bytes(payload)
    ledger["sha256"] = hashlib.sha256(payload).hexdigest()
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    completed, result = _run_paths(root, manifest_path, identity_path, result_path)

    assert completed.returncode == 2
    assert result["status"] == "BLOCKED"
    assert result["failures"] == [{"code": "evidence_semantic_invalid"}]


@pytest.mark.parametrize(
    ("branch", "failed_gate"),
    (
        ("fallback", "required-fallback-capability-parity"),
        ("restart", "required-restart-main-availability"),
    ),
)
def test_mpv_061_required_resilience_cannot_be_caller_asserted_without_bound_proof(
    tmp_path: Path,
    branch: str,
    failed_gate: str,
) -> None:
    root = tmp_path / f"missing-{branch}-proof"
    manifest_path, identity_path, result_path, manifest = _write_full_journey_fixture(
        root
    )
    resilience = manifest.setdefault("resilience", {})
    resilience[branch] = {"required": True, "observed": False, "evidence": []}
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    completed, result = _run_paths(root, manifest_path, identity_path, result_path)

    assert completed.returncode == 1
    assert result["status"] == "FAIL"
    assert (
        next(gate for gate in result["gates"] if gate["id"] == failed_gate)["status"]
        == "FAIL"
    )


def test_mpv_061_receipt_adapter_derives_only_a_bound_full_journey_pass(
    tmp_path: Path,
) -> None:
    root = tmp_path / "receipt-adapter"
    _, _, _, manifest = _write_full_journey_fixture(root)
    adapter = _load_python_adapter()

    result = adapter.assess_manifest(
        manifest,
        evidence_root=root,
        expected_candidate_digest=manifest["candidate"]["candidateDigest"],
        expected_artifact_digest=manifest["candidate"]["artifactDigest"],
        installed_owner_proven=True,
        now=datetime.fromisoformat(manifest["runAt"]),
    )
    receipt = adapter.receipt_manifest(result=result)

    assert result["status"] == "PASS"
    assert receipt == {
        "caseId": "MPV-061",
        "contractVersion": 1,
        "runAt": datetime.fromisoformat(manifest["runAt"]).isoformat(),
        "status": "PASS",
        "surface": "voice",
        "evidence": sorted(
            (
                {
                    "kind": item["kind"],
                    "path": item["path"],
                    "sha256": item["sha256"],
                }
                for item in manifest["evidence"]
            ),
            key=lambda item: (item["kind"], item["path"]),
        ),
    }


def test_mpv_061_parent_registry_support_helper_rebinds_one_authentic_pass(
    tmp_path: Path,
) -> None:
    registry_path = ROOT / "scripts" / "viventium" / "parallel_work_qa_evidence.py"
    spec = importlib.util.spec_from_file_location(
        "mpv_061_registered_receipt_owner", registry_path
    )
    assert spec is not None and spec.loader is not None
    registry = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(registry)
    registration = registry.REGISTERED_SEMANTIC_VERIFIERS["MPV-061"]
    assert registration == {
        "id": "mpv061-semantic-v1",
        "path": Path(
            "qa/modern-playground-voice/scripts/mpv_061_full_journey_semantic_verifier.py"
        ),
    }
    candidate_digest = _digest("parent-measured-candidate")
    artifact_digest = _digest("parent-measured-installed-artifact")
    manifest, evidence_root, old_candidate, old_artifact = complete_manifest(
        tmp_path,
        candidate_digest=candidate_digest,
        artifact_digest=artifact_digest,
    )
    adapter = registry._load_registered_verifier(
        ROOT / registration["path"], case_id="MPV-061"
    )

    result = adapter.assess_manifest(
        manifest,
        evidence_root=evidence_root,
        expected_candidate_digest=candidate_digest,
        expected_artifact_digest=artifact_digest,
        installed_owner_proven=True,
        now=datetime.fromisoformat(manifest["runAt"]),
    )
    receipt = adapter.receipt_manifest(result=result)

    assert old_candidate != candidate_digest
    assert old_artifact != artifact_digest
    assert result["candidateBinding"] == {
        "matched": True,
        "candidateDigest": candidate_digest,
        "artifactDigest": artifact_digest,
    }
    assert receipt["status"] == "PASS"
    assert receipt["surface"] == "voice"


def test_mpv_061_parent_support_helper_exposes_rebindable_structural_json(
    tmp_path: Path,
) -> None:
    manifest, evidence_root, _, _ = complete_manifest(tmp_path)

    for evidence in manifest["evidence"]:
        evidence_path = evidence_root / evidence["path"]
        if evidence["kind"] == "voice_recording":
            assert evidence_path.suffix == ".wav"
        elif evidence["kind"] in {"input_file", "delivered_artifact"}:
            assert evidence_path.suffix == ".bin"
        else:
            assert evidence_path.suffix == ".json"
            document = json.loads(evidence_path.read_text(encoding="utf-8"))
            assert (
                document["candidateDigest"] == manifest["candidate"]["candidateDigest"]
            )
            assert document["artifactDigest"] == manifest["candidate"]["artifactDigest"]


@pytest.mark.skipif(
    not INSTALLED_ARTIFACT_IDENTITY.is_file(),
    reason="installed Viventium artifact identity is unavailable",
)
def test_mpv_061_runner_accepts_the_real_installed_candidate_with_synthetic_evidence(
    tmp_path: Path,
) -> None:
    identity = json.loads(INSTALLED_ARTIFACT_IDENTITY.read_text(encoding="utf-8"))
    candidate_digest = _canonical_digest(
        {
            "source": identity["source"],
            "nestedComponents": identity["nestedComponents"],
            "prebuiltHelper": identity["prebuiltHelper"],
        }
    )
    artifact_digest = _canonical_digest(identity["installed"])
    manifest, evidence_root, _, _ = complete_manifest(
        tmp_path,
        candidate_digest=candidate_digest,
        artifact_digest=artifact_digest,
    )
    result_path = evidence_root / "installed-candidate-result.json"

    completed, result = _run_paths(
        evidence_root,
        evidence_root / "mpv-061-evidence.json",
        INSTALLED_ARTIFACT_IDENTITY,
        result_path,
    )

    assert completed.returncode == 0, completed.stderr
    assert result["status"] == "PASS"
    assert result["candidateBinding"] == {
        "matched": True,
        "candidateDigest": manifest["candidate"]["candidateDigest"],
        "artifactDigest": manifest["candidate"]["artifactDigest"],
    }
    assert result["counts"]["verifiedEvidenceFiles"] == 24


def test_mpv_061_receipt_adapter_refuses_caller_declared_pass() -> None:
    adapter = _load_python_adapter()

    with pytest.raises(adapter.EvidenceContractError):
        adapter.receipt_manifest(
            result={
                "caseId": "MPV-061",
                "contractVersion": 1,
                "status": "PASS",
                "ready": True,
                "gates": [],
                "_receiptEvidence": [],
            }
        )


@pytest.mark.parametrize(
    ("owner_proven", "candidate_suffix", "clock_offset"),
    (
        (False, "", timedelta()),
        (True, "f" * 64, timedelta()),
        (True, "", timedelta(hours=25)),
    ),
)
def test_mpv_061_receipt_adapter_refuses_unproven_changed_or_stale_installed_run(
    tmp_path: Path,
    owner_proven: bool,
    candidate_suffix: str,
    clock_offset: timedelta,
) -> None:
    root = tmp_path / "unsafe-receipt"
    _, _, _, manifest = _write_full_journey_fixture(root)
    adapter = _load_python_adapter()

    with pytest.raises(adapter.EvidenceContractError):
        adapter.assess_manifest(
            manifest,
            evidence_root=root,
            expected_candidate_digest=(
                candidate_suffix or manifest["candidate"]["candidateDigest"]
            ),
            expected_artifact_digest=manifest["candidate"]["artifactDigest"],
            installed_owner_proven=owner_proven,
            now=datetime.fromisoformat(manifest["runAt"]) + clock_offset,
        )


def test_mpv_061_receipt_adapter_refuses_mutated_derived_pass(tmp_path: Path) -> None:
    root = tmp_path / "mutated-receipt"
    _, _, _, manifest = _write_full_journey_fixture(root)
    adapter = _load_python_adapter()
    result = adapter.assess_manifest(
        manifest,
        evidence_root=root,
        expected_candidate_digest=manifest["candidate"]["candidateDigest"],
        expected_artifact_digest=manifest["candidate"]["artifactDigest"],
        installed_owner_proven=True,
        now=datetime.fromisoformat(manifest["runAt"]),
    )
    result["_receiptEvidence"][0]["sha256"] = "f" * 64

    with pytest.raises(adapter.EvidenceContractError):
        adapter.receipt_manifest(result=result)


def test_mpv_061_templates_manifest_and_docs_require_the_complete_runner() -> None:
    evidence = json.loads(EVIDENCE_TEMPLATE.read_text(encoding="utf-8"))
    result = json.loads(RESULT_TEMPLATE.read_text(encoding="utf-8"))
    acceptance = json.loads(ACCEPTANCE_MANIFEST.read_text(encoding="utf-8"))

    assert {
        "candidate",
        "run",
        "evidence",
        "voice",
        "workers",
        "inputGroup",
        "deliveries",
        "surfaceContinuity",
        "publicSafety",
    } <= set(evidence)
    assert Counter(item["kind"] for item in evidence["evidence"]) == (
        REQUIRED_EVIDENCE_KIND_COUNTS
    )
    assert all(item["entityRefs"] for item in evidence["evidence"])
    assert all(
        all(ref.startswith("sha256:") for ref in item["entityRefs"])
        for item in evidence["evidence"]
    )
    assert evidence["voice"]["turnOrder"] == [
        "trustedWingLaunch",
        "quickConversation",
        "trustedWingControl",
        "passiveWingDenial",
        "listenOnlyDenial",
    ]
    assert [worker["label"] for worker in evidence["workers"]] == ["A", "B"]
    assert len(evidence["deliveries"]) == 2

    assert result["candidateBinding"]["matched"] is False
    assert result["counts"]["sessions"] == 0
    assert result["privacy"]["publicSafe"] is True
    assert result["gates"] == []

    journey = acceptance["crossFeatureJourneys"]["MPV-061"]
    assert journey["runner"] == (
        "qa/modern-playground-voice/scripts/mpv_061_full_journey_semantic_qa.js"
    )
    assert journey["scope"] == "full_journey"
    assert journey["authoritySliceOnlyPass"] == "forbidden"
    run = next(item for item in acceptance["runs"] if item["id"] == journey["run"])
    assert "--artifact-identity" in run["command"]
    assert "--evidence-root" in run["command"]
    assert acceptance["coverage"]["MPV-061"]["scope"] == "authority_slice_only"
    assert acceptance["coverage"]["MPV-061"]["livePassClaim"] == "forbidden"

    readme = README.read_text(encoding="utf-8")
    cases = CASES.read_text(encoding="utf-8")
    for content in (readme, cases):
        assert "mpv_061_full_journey_semantic_qa.js" in content
        assert "authority slice" in content.lower()
        assert "full_journey" in content

    serialized = json.dumps(evidence)
    assert "/Users/" not in serialized
    assert "/home/" not in serialized


INSTALLED_JOURNEY_RUNNER = QA_ROOT / "scripts" / "run_mpv_061_installed_journey.cjs"
INSTALLED_JOURNEY_RUNNER_TEST = (
    QA_ROOT / "scripts" / "run_mpv_061_installed_journey.test.cjs"
)


def _run_installed_journey(
    *arguments: str,
) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    completed = subprocess.run(
        ["node", str(INSTALLED_JOURNEY_RUNNER), *arguments],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = {}
    return completed, payload


def test_mpv_061_installed_journey_requires_opt_in_before_any_write(
    tmp_path: Path,
) -> None:
    evidence_root = tmp_path / "must-not-be-created"

    completed, payload = _run_installed_journey("--evidence-root", str(evidence_root))

    assert completed.returncode == 2
    assert payload["caseId"] == "MPV-061"
    assert payload["status"] == "BLOCKED"
    assert payload["blocker"] == "local_qa_opt_in_required"
    assert not evidence_root.exists()


def test_mpv_061_installed_journey_requires_explicit_synthetic_fixture_consent(
    tmp_path: Path,
) -> None:
    evidence_root = tmp_path / "must-not-be-created"

    completed, payload = _run_installed_journey(
        "--local-qa", "--evidence-root", str(evidence_root)
    )

    assert completed.returncode == 2
    assert payload["status"] == "BLOCKED"
    assert payload["blocker"] == "synthetic_fixture_opt_in_required"
    assert not evidence_root.exists()


def test_mpv_061_installed_journey_rejects_public_repository_evidence() -> None:
    completed, payload = _run_installed_journey(
        "--local-qa",
        "--allow-synthetic-account",
        "--evidence-root",
        str(QA_ROOT),
    )

    assert completed.returncode == 2
    assert payload["status"] == "BLOCKED"
    assert payload["blocker"] == "evidence_root_inside_repository"


def test_mpv_061_installed_journey_rejects_group_readable_private_evidence(
    tmp_path: Path,
) -> None:
    evidence_root = tmp_path / "public-evidence"
    evidence_root.mkdir(mode=0o755)
    evidence_root.chmod(0o755)

    completed, payload = _run_installed_journey(
        "--local-qa",
        "--allow-synthetic-account",
        "--evidence-root",
        str(evidence_root),
    )

    assert completed.returncode == 2
    assert payload["status"] == "BLOCKED"
    assert payload["blocker"] == "evidence_root_not_private"
    assert (evidence_root.stat().st_mode & 0o777) == 0o755


def test_mpv_061_installed_journey_rejects_symlinked_private_evidence(
    tmp_path: Path,
) -> None:
    actual_root = tmp_path / "actual-evidence"
    actual_root.mkdir(mode=0o700)
    linked_root = tmp_path / "linked-evidence"
    linked_root.symlink_to(actual_root, target_is_directory=True)

    completed, payload = _run_installed_journey(
        "--local-qa",
        "--allow-synthetic-account",
        "--evidence-root",
        str(linked_root),
    )

    assert completed.returncode == 2
    assert payload["status"] == "BLOCKED"
    assert payload["blocker"] == "evidence_root_symlink_forbidden"
    assert not tuple(actual_root.iterdir())


def test_mpv_061_installed_journey_reports_missing_scenario_before_mutation(
    tmp_path: Path,
) -> None:
    evidence_root = tmp_path / "private-evidence"
    evidence_root.mkdir(mode=0o700)
    scenario_path = evidence_root / "missing-scenario.json"

    completed, payload = _run_installed_journey(
        "--local-qa",
        "--allow-synthetic-account",
        "--evidence-root",
        str(evidence_root),
        "--scenario",
        str(scenario_path),
    )

    assert completed.returncode == 2
    assert payload["status"] == "BLOCKED"
    assert payload["blocker"] == "scenario_unavailable"
    assert not tuple(evidence_root.iterdir())


def test_mpv_061_installed_journey_has_executable_isolated_contract_tests() -> None:
    assert INSTALLED_JOURNEY_RUNNER.exists()
    assert INSTALLED_JOURNEY_RUNNER_TEST.exists()

    completed = subprocess.run(
        ["node", "--test", str(INSTALLED_JOURNEY_RUNNER_TEST)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
