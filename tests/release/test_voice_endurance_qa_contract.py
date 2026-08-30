import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HARNESS = (
    ROOT
    / "qa"
    / "modern-playground-voice"
    / "scripts"
    / "world_class_call_acceptance.js"
)
CASES = ROOT / "qa" / "modern-playground-voice" / "cases.md"
RUNBOOK = ROOT / "qa" / "modern-playground-voice" / "endurance-runbook.md"
RESULT_TEMPLATE = (
    ROOT
    / "qa"
    / "modern-playground-voice"
    / "result-template.v1.json"
)
EXTERNAL_EVIDENCE_TEMPLATE = (
    ROOT
    / "qa"
    / "modern-playground-voice"
    / "external-evidence-template.v1.json"
)
ACCEPTANCE_MANIFEST = (
    ROOT
    / "qa"
    / "modern-playground-voice"
    / "acceptance-manifest.template.v1.json"
)
SYNTHETIC_AUDIO_HARNESS = (
    ROOT
    / "qa"
    / "modern-playground-voice"
    / "scripts"
    / "livekit_synthetic_audio_qa.js"
)

ESCAPED_REGRESSION_FIELDS = {
    "rawSessionIdWithoutBrowserCapabilityRejected": "raw-session-id-browser-capability",
    "suppressionBarrierPreservedAfter1001Tasks": "suppression-barrier-task-pressure",
    "hungOwnerCancelAckWithin250Ms": "hung-owner-cancel-ack",
    "malformedTaskSnapshotFailsVisible": "malformed-task-snapshot-fail-visible",
    "apiRestartPreservesBarrierAndReplay": "api-restart-barrier-replay",
    "speakerHistoryBeyond4096Accessible": "speaker-history-over-4096-access",
}

MPV_061_GATE_IDS = (
    "mpv-061-trusted-wing-launch",
    "mpv-061-trusted-wing-control",
    "mpv-061-passive-wing-denial",
    "mpv-061-listen-only-denial",
)

MPV_061_PASSING_EVIDENCE = {
    "schema": "viventium.voice.worker-bee-authority-evidence.v1",
    "authoritative": True,
    "source": "owner_scoped_worker_mission_action_delivery_ledger",
    "modeAuthoritySource": "persisted_call_session",
    "acceptanceRunBindingMatched": True,
    "installedRuntimeIdentityMatched": True,
    "observationOrder": [
        "trustedWingLaunch",
        "trustedWingControl",
        "passiveWingDenial",
        "listenOnlyDenial",
    ],
    "cases": {
        "trustedWingLaunch": {
            "ordinal": 1,
            "ledgerSequenceBefore": 10,
            "ledgerSequenceAfter": 14,
            "mode": "wing",
            "actorTrust": "owner_participant",
            "directlyAddressed": True,
            "sideEffectAuthorityGranted": True,
            "requestedMissionCount": 2,
            "missionDelta": 2,
            "acceptedLaunchReceiptDelta": 2,
            "rejectedLaunchReceiptDelta": 0,
            "workerLaunchInvocationDelta": 1,
            "mainResponseDelta": 1,
            "ttsInputDelta": 1,
        },
        "trustedWingControl": {
            "ordinal": 2,
            "ledgerSequenceBefore": 14,
            "ledgerSequenceAfter": 16,
            "mode": "wing",
            "actorTrust": "owner_participant",
            "directlyAddressed": True,
            "sideEffectAuthorityGranted": True,
            "controlAction": "steer",
            "missionDelta": 0,
            "acceptedActionReceiptDelta": 1,
            "workerControlInvocationDelta": 1,
            "targetWorkRefMatched": True,
            "targetActionReceiptDelta": 1,
            "nonTargetActionReceiptDelta": 0,
            "mainResponseDelta": 1,
            "ttsInputDelta": 1,
        },
        "passiveWingDenial": {
            "ordinal": 3,
            "ledgerSequenceBefore": 16,
            "ledgerSequenceAfter": 17,
            "mode": "wing",
            "actorTrust": "owner_participant",
            "directlyAddressed": False,
            "transcriptObservationDelta": 1,
            "missionDelta": 0,
            "actionReceiptDelta": 0,
            "workerLaunchInvocationDelta": 0,
            "workerControlInvocationDelta": 0,
            "toolInvocationDelta": 0,
            "cortexInvocationDelta": 0,
            "liveMemoryInvocationDelta": 0,
            "mainResponseDelta": 0,
            "ttsInputDelta": 0,
        },
        "listenOnlyDenial": {
            "ordinal": 4,
            "ledgerSequenceBefore": 17,
            "ledgerSequenceAfter": 18,
            "mode": "listen_only",
            "actorTrust": "owner_participant",
            "directlyAddressed": True,
            "sideEffectAuthorityGranted": False,
            "ambientTranscriptDelta": 1,
            "missionDelta": 0,
            "actionReceiptDelta": 0,
            "workerLaunchInvocationDelta": 0,
            "workerControlInvocationDelta": 0,
            "toolInvocationDelta": 0,
            "agentControllerInvocationDelta": 0,
            "cortexInvocationDelta": 0,
            "liveMemoryInvocationDelta": 0,
            "titleModelInvocationDelta": 0,
            "mainResponseDelta": 0,
            "ttsInputDelta": 0,
        },
    },
}



def test_world_class_voice_endurance_contract_is_public_safe_and_exact(tmp_path: Path):
    assert HARNESS.exists()
    assert RUNBOOK.exists()
    assert RESULT_TEMPLATE.exists()
    assert EXTERNAL_EVIDENCE_TEMPLATE.exists()
    assert ACCEPTANCE_MANIFEST.exists()

    result_path = tmp_path / "self-test-result.json"
    completed = subprocess.run(
        [
            "node",
            str(HARNESS),
            "--self-test",
            "--output-root",
            str(tmp_path),
            "--result",
            str(result_path),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr

    result = json.loads(result_path.read_text())
    assert result["schema"] == "viventium.voice.acceptance.result.v1"
    assert result["status"] == "PASS"
    assert result["plan"] == {
        "modeSwitches": 100,
        "reconnects": 50,
        "audibleMinutes": 65,
        "soakMinutes": 120,
    }
    assert result["privacy"]["publicSafe"] is True
    assert result["replay"]["lostTasks"] == 0
    assert result["replay"]["duplicateTasks"] == 0
    assert result["replay"]["lostSegments"] == 0
    assert result["replay"]["duplicateSegments"] == 0
    assert result["replay"]["duplicateResults"] == 0
    assert result["latency"]["traceCount"] == 2
    assert result["latency"]["completeTraceCount"] == 2
    assert result["execution"]["runtimeGatesExecuted"] is False
    assert all(value is None for value in result["escapedRegressions"].values())
    assert result["workerBeeAuthority"]["scope"] == "authority_slice_only"
    assert result["workerBeeAuthority"]["fullJourneyStatus"] == "NOT_RUN"
    assert result["workerBeeAuthority"]["livePassClaimed"] is False
    assert result["workerBeeAuthority"]["evidenceStatus"] == "NOT_EVALUATED"
    assert {gate["id"] for gate in result["gates"]} == {
        "self-test-replay",
        "self-test-traces",
    }

    serialized = json.dumps(result)
    assert str(ROOT) not in serialized
    assert "call-private-123" not in serialized
    assert "user@example.com" not in serialized
    assert "synthetic private transcript" not in serialized

    template = json.loads(RESULT_TEMPLATE.read_text())
    assert template["schema"] == result["schema"]
    assert template["plan"] == result["plan"]
    assert template["environment"] == "dev"


def test_machine_readable_manifest_maps_every_mpv_case_to_fresh_fail_closed_runs():
    manifest = json.loads(ACCEPTANCE_MANIFEST.read_text())
    assert manifest["schema"] == "viventium.voice.acceptance.manifest.v1"
    assert manifest["executionPolicy"] == {
        "sourceFreezeRequired": True,
        "startRuntime": False,
        "rawOutput": "private_only",
        "publicResult": "sanitized_content_free_only",
    }

    coverage = manifest["coverage"]
    expected_coverage = {f"MPV-{case_id:03d}" for case_id in range(32, 57)}
    expected_coverage.add("MPV-061")
    assert set(coverage) == expected_coverage
    for case_id, contract in coverage.items():
        assert contract["runs"], case_id
        assert contract["gates"], case_id

    mpv_061 = coverage["MPV-061"]
    assert mpv_061["runs"] == ["dev-audible-65m"]
    assert mpv_061["gates"] == list(MPV_061_GATE_IDS)
    assert mpv_061["scope"] == "authority_slice_only"
    assert mpv_061["fullJourneyStatus"] == "NOT_RUN"
    assert mpv_061["livePassClaim"] == "forbidden"

    runs = {run["id"]: run for run in manifest["runs"]}
    required_runs = {
        "dev-switches",
        "dev-reconnects",
        "dev-audible-65m",
        "dev-soak-120m",
        "installed-prod-mpv-061-full-journey",
        "installed-prod-real-call",
        "clean-install-parity",
        "livekit-accepted-dependency-set",
        "livekit-candidate-dependency-set",
    }
    assert required_runs <= set(runs)
    assert runs["dev-switches"]["expected"]["modeSwitches"] == 100
    assert runs["dev-reconnects"]["expected"]["reconnects"] == 50
    assert runs["dev-audible-65m"]["expected"]["minutes"] == 65
    assert runs["dev-soak-120m"]["expected"]["minutes"] == 120
    assert (
        runs["dev-audible-65m"]["freshSessionSlot"]
        != runs["dev-soak-120m"]["freshSessionSlot"]
    )
    assert (
        runs["livekit-accepted-dependency-set"]["freshSessionSlot"]
        != runs["livekit-candidate-dependency-set"]["freshSessionSlot"]
    )
    assert runs["livekit-accepted-dependency-set"]["dependencySet"].endswith("1.5.10")
    assert runs["livekit-candidate-dependency-set"]["dependencySet"].endswith("1.6.9")
    assert set(runs["livekit-candidate-dependency-set"]["requiredCompanionProfiles"]) == {
        "focused-and-full-tests",
        "reconnects",
        "soak",
        "production-build",
        "installed-real-call",
        "clean-install-real-call",
    }
    for run in runs.values():
        assert isinstance(run["command"], list)
        assert run["command"], run["id"]

    acquisitions = manifest["externalEvidenceAcquisition"]
    assert acquisitions["localOnlyEgress"]["missingResult"] == "FAIL"
    assert acquisitions["noisySpeakerBank"]["missingResult"] == "FAIL"
    assert acquisitions["localOnlyEgress"]["passValue"] == 0
    assert acquisitions["noisySpeakerBank"]["maximumPassValue"] == 15
    authority = acquisitions["mpv061WorkerBeeAuthority"]
    assert authority["outputField"] == "workerBeeAuthority"
    assert authority["schema"] == "viventium.voice.worker-bee-authority-evidence.v1"
    assert authority["modeAuthoritySource"] == "persisted_call_session"
    assert authority["acceptanceRunBindingRequired"] is True
    assert authority["missingResult"] == "FAIL"
    assert authority["requiredObservationOrder"] == [
        "trustedWingLaunch",
        "trustedWingControl",
        "passiveWingDenial",
        "listenOnlyDenial",
    ]
    assert authority["publicOutput"] == "content_free_counts_and_gate_states_only"
    assert all(command[0] == "jq" for command in acquisitions["verificationCommands"])

    serialized = json.dumps(manifest)
    assert re.search(r"/(?:Users|home)/[^/<]+/", serialized) is None
    assert "callSessionId=actual" not in serialized


def test_mpv_061_worker_bee_authority_assertions_are_executable_and_fail_closed():
    script = r"""
const assert = require('assert');
const {
  applyMeasuredEvidence,
  auditWorkerBeeAuthorityEvidence,
  baseResult,
} = require(process.argv[1]);
const gateIds = JSON.parse(process.argv[2]);

const passingEvidence = JSON.parse(process.argv[3]);

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function apply(evidence) {
  const result = baseResult('audible');
  applyMeasuredEvidence(result, { externalEvidence: { workerBeeAuthority: evidence } }, 'audible');
  return result;
}

const passingAudit = auditWorkerBeeAuthorityEvidence(passingEvidence);
assert.strictEqual(passingAudit.scope, 'authority_slice_only');
assert.strictEqual(passingAudit.fullJourneyStatus, 'NOT_RUN');
assert.strictEqual(passingAudit.livePassClaimed, false);
assert.strictEqual(passingAudit.evidenceStatus, 'VALID');
assert.strictEqual(passingAudit.modeAuthoritySourceVerified, true);
assert.strictEqual(passingAudit.acceptanceRunBindingMatched, true);
assert.strictEqual(passingAudit.observationWindowCount, 4);
for (const check of Object.values(passingAudit.checks)) {
  assert.strictEqual(check.status, 'PASS');
}

const passing = apply(passingEvidence);
assert.strictEqual(passing.evidence.workerBeeAuthorityWindows, 4);
for (const gateId of gateIds) {
  assert.strictEqual(passing.gates.find((gate) => gate.id === gateId).status, 'PASS');
}

const missing = apply(undefined);
assert.strictEqual(missing.workerBeeAuthority.evidenceStatus, 'MISSING');
assert.strictEqual(missing.evidence.workerBeeAuthorityWindows, 0);
for (const gateId of gateIds) {
  assert.strictEqual(missing.gates.find((gate) => gate.id === gateId).status, 'FAIL');
}

const untrustedLaunch = clone(passingEvidence);
untrustedLaunch.cases.trustedWingLaunch.actorTrust = 'guest_participant';
assert.strictEqual(
  auditWorkerBeeAuthorityEvidence(untrustedLaunch).checks.trustedWingLaunch.status,
  'FAIL',
);

for (const field of [
  'missionDelta',
  'actionReceiptDelta',
  'workerLaunchInvocationDelta',
  'workerControlInvocationDelta',
  'toolInvocationDelta',
  'cortexInvocationDelta',
  'liveMemoryInvocationDelta',
  'mainResponseDelta',
  'ttsInputDelta',
]) {
  const passiveSideEffect = clone(passingEvidence);
  passiveSideEffect.cases.passiveWingDenial[field] = 1;
  assert.strictEqual(
    auditWorkerBeeAuthorityEvidence(passiveSideEffect).checks.passiveWingDenial.status,
    'FAIL',
    field,
  );
}

for (const field of [
  'missionDelta',
  'actionReceiptDelta',
  'workerLaunchInvocationDelta',
  'workerControlInvocationDelta',
  'toolInvocationDelta',
  'agentControllerInvocationDelta',
  'cortexInvocationDelta',
  'liveMemoryInvocationDelta',
  'titleModelInvocationDelta',
  'mainResponseDelta',
  'ttsInputDelta',
]) {
  const listenOnlySideEffect = clone(passingEvidence);
  listenOnlySideEffect.cases.listenOnlyDenial[field] = 1;
  assert.strictEqual(
    auditWorkerBeeAuthorityEvidence(listenOnlySideEffect).checks.listenOnlyDenial.status,
    'FAIL',
    field,
  );
}

const crossMissionSteer = clone(passingEvidence);
crossMissionSteer.cases.trustedWingControl.nonTargetActionReceiptDelta = 1;
assert.strictEqual(
  auditWorkerBeeAuthorityEvidence(crossMissionSteer).checks.trustedWingControl.status,
  'FAIL',
);

const outOfOrder = clone(passingEvidence);
outOfOrder.cases.passiveWingDenial.ledgerSequenceBefore = 15;
const outOfOrderAudit = auditWorkerBeeAuthorityEvidence(outOfOrder);
assert.strictEqual(outOfOrderAudit.evidenceStatus, 'INVALID');
assert.ok(Object.values(outOfOrderAudit.checks).every((check) => check.status === 'FAIL'));

const wrongModeAuthority = clone(passingEvidence);
wrongModeAuthority.modeAuthoritySource = 'browser_ui';
assert.strictEqual(
  auditWorkerBeeAuthorityEvidence(wrongModeAuthority).evidenceStatus,
  'INVALID',
);

const staleEvidence = clone(passingEvidence);
staleEvidence.acceptanceRunBindingMatched = false;
assert.strictEqual(
  auditWorkerBeeAuthorityEvidence(staleEvidence).evidenceStatus,
  'INVALID',
);

const privateInput = clone(passingEvidence);
privateInput.cases.trustedWingLaunch.privateMissionIdentifier = 'private-mission-sentinel';
assert.ok(
  !JSON.stringify(auditWorkerBeeAuthorityEvidence(privateInput)).includes(
    'private-mission-sentinel',
  ),
);
"""
    completed = subprocess.run(
        [
            "node",
            "-e",
            script,
            str(HARNESS),
            json.dumps(MPV_061_GATE_IDS),
            json.dumps(MPV_061_PASSING_EVIDENCE),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr



def test_external_evidence_template_covers_all_behavior_and_quality_gates():
    evidence = json.loads(EXTERNAL_EVIDENCE_TEMPLATE.read_text())
    result = json.loads(RESULT_TEMPLATE.read_text())
    assert evidence["schema"] == "viventium.voice.external-evidence.v1"
    assert evidence["quality"] == result["quality"]
    assert evidence["behaviorPaths"] == result["behaviorPaths"]
    assert len(evidence["behaviorPaths"]) >= 28


def test_needs_input_round_trip_gate_is_capability_conditional_and_fail_closed():
    evidence = json.loads(EXTERNAL_EVIDENCE_TEMPLATE.read_text())
    result = json.loads(RESULT_TEMPLATE.read_text())
    manifest = json.loads(ACCEPTANCE_MANIFEST.read_text())

    assert evidence["taskOwnerCapabilityInventory"] == {
        "authoritative": None,
        "source": None,
        "owners": [],
    }
    assert result["behaviorApplicability"]["needsInputRoundTrip"] == {
        "status": None,
        "reason": None,
        "advertisedInputOwnerCount": None,
    }
    assert manifest["conditionalGates"]["behavior-needsInputRoundTrip"] == {
        "capability": "voice_task_owner.provideInput",
        "inventorySource": "runtime_voice_task_owner_registry",
        "whenAdvertised": "PASS requires a successful owner input round trip",
        "whenAbsent": "NOT_APPLICABLE",
        "missingInventory": "FAIL",
    }

    script = r"""
const assert = require('assert');
const { applyMeasuredEvidence, baseResult } = require(process.argv[1]);

function apply(inventory, roundTrip) {
  const result = baseResult('audible');
  applyMeasuredEvidence(result, {
    externalEvidence: {
      taskOwnerCapabilityInventory: inventory,
      behaviorPaths: { needsInputRoundTrip: roundTrip },
    },
  }, 'audible');
  return {
    gate: result.gates.find((item) => item.id === 'behavior-needsInputRoundTrip'),
    applicability: result.behaviorApplicability.needsInputRoundTrip,
  };
}

const missing = apply(undefined, true);
assert.strictEqual(missing.gate.status, 'FAIL');
assert.strictEqual(missing.applicability.status, 'UNKNOWN');
assert.strictEqual(missing.applicability.reason, 'authoritative_owner_inventory_missing');

const unavailable = apply({
  authoritative: true,
  source: 'runtime_voice_task_owner_registry',
  owners: [{ kind: 'glasshive_run', acceptsInput: false }],
}, null);
assert.strictEqual(unavailable.gate.status, 'NOT_APPLICABLE');
assert.strictEqual(unavailable.gate.actual, 'no_advertised_input_capable_owner');
assert.strictEqual(unavailable.applicability.status, 'NOT_APPLICABLE');
assert.strictEqual(unavailable.applicability.advertisedInputOwnerCount, 0);

const passing = apply({
  authoritative: true,
  source: 'runtime_voice_task_owner_registry',
  owners: [{ kind: 'future_owner', acceptsInput: true }],
}, true);
assert.strictEqual(passing.gate.status, 'PASS');
assert.strictEqual(passing.applicability.status, 'APPLICABLE');
assert.strictEqual(passing.applicability.advertisedInputOwnerCount, 1);

const failing = apply({
  authoritative: true,
  source: 'runtime_voice_task_owner_registry',
  owners: [{ kind: 'future_owner', acceptsInput: true }],
}, false);
assert.strictEqual(failing.gate.status, 'FAIL');
assert.strictEqual(failing.applicability.status, 'APPLICABLE');
"""
    completed = subprocess.run(
        ["node", "-e", script, str(HARNESS)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_latest_escaped_regressions_are_fail_closed_and_traceable():
    evidence = json.loads(EXTERNAL_EVIDENCE_TEMPLATE.read_text())
    result = json.loads(RESULT_TEMPLATE.read_text())
    manifest = json.loads(ACCEPTANCE_MANIFEST.read_text())
    cases = CASES.read_text()

    assert evidence["escapedRegressions"] == result["escapedRegressions"]
    assert set(evidence["escapedRegressions"]) == set(ESCAPED_REGRESSION_FIELDS)
    assert all(value is None for value in evidence["escapedRegressions"].values())

    acquisitions = {
        contract["outputField"]: contract
        for contract in manifest["externalEvidenceAcquisition"].values()
        if isinstance(contract, dict) and "outputField" in contract
    }

    for offset, (field, gate_id) in enumerate(ESCAPED_REGRESSION_FIELDS.items(), start=46):
        case_id = f"MPV-{offset:03d}"
        assert case_id in manifest["coverage"]
        assert gate_id in manifest["coverage"][case_id]["gates"]
        assert f"### {case_id}" in cases
        section = cases.split(f"### {case_id}", 1)[1].split("\n### ", 1)[0]
        assert field in section
        assert "- Forbidden Result:" in section
        assert "- PASS Evidence:" in section

        acquisition = acquisitions[f"escapedRegressions.{field}"]
        assert acquisition["missingResult"] == "FAIL"
        assert acquisition["passValue"] is True

    script = r"""
const assert = require('assert');
const { applyMeasuredEvidence, baseResult } = require(process.argv[1]);
const gateIds = JSON.parse(process.argv[2]);

const absent = baseResult('audible');
applyMeasuredEvidence(absent, { externalEvidence: {} }, 'audible');
for (const gateId of gateIds) {
  assert.strictEqual(absent.gates.find((gate) => gate.id === gateId).status, 'FAIL');
}

const present = baseResult('audible');
const escapedRegressions = Object.fromEntries(
  Object.keys(present.escapedRegressions).map((key) => [key, true])
);
applyMeasuredEvidence(present, { externalEvidence: { escapedRegressions } }, 'audible');
for (const gateId of gateIds) {
  assert.strictEqual(present.gates.find((gate) => gate.id === gateId).status, 'PASS');
}
"""
    completed = subprocess.run(
        ["node", "-e", script, str(HARNESS), json.dumps(list(ESCAPED_REGRESSION_FIELDS.values()))],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_world_class_voice_cases_name_each_endurance_gate():
    cases = CASES.read_text()
    for marker in (
        "100 atomic mode switches",
        "50 reconnect cycles",
        "65-minute audible call",
        "120-minute synthetic soak",
        "exact task and speaker replay",
        "structured latency trace",
        "private configurable output root",
    ):
        assert marker in cases


def test_replay_and_latency_auditors_fail_closed():
    script = r"""
const assert = require('assert');
const {
  applyMeasuredEvidence,
  auditReplay,
  baseResult,
  extractVoiceHopTraces,
  summarizeVoiceHopTraces,
} = require(process.argv[1]);
const workerBeeAuthority = JSON.parse(process.argv[2]);

const task = (taskId, sequence, state, resultRef = '') => ({
  version: 1,
  eventId: `event-${taskId}-${sequence}`,
  taskId,
  sequence,
  state,
  ...(resultRef ? { resultRef } : {}),
});
const segment = (segmentId, sequence, revision, text) => ({
  version: 1,
  segmentId,
  sequence,
  revision,
  text,
});

const previous = {
  tasks: [task('task-a', 5, 'completed', 'result-a')],
  segments: [segment('segment-a', 10, 2, 'stable')],
};
const broken = {
  tasks: [
    task('task-a', 6, 'running', 'result-a'),
    task('task-b', 1, 'completed', 'result-a'),
  ],
  segments: [segment('segment-a', 10, 2, 'mutated without revision')],
};
const replay = auditReplay(previous, broken);
assert.ok(replay.regressedTasks > 0);
assert.strictEqual(replay.duplicateResults, 1);
assert.strictEqual(replay.changedStableSegments, 1);

const completeWithoutTool = [
  ['utterance_end', 1000],
  ['gateway_dispatch', 1100],
  ['agent_start', 1200],
  ['first_model_token', 1300],
  ['tts_first_byte', 1400],
  ['audio_output', 1500],
].map(([hop, timestampMs]) =>
  `[VoiceHop] ${JSON.stringify({
    event: 'voice_hop', correlationId: 'trace-a', hop, timestampMs,
  })}`
);
const incomplete = [
  `[VoiceHop] ${JSON.stringify({
    event: 'voice_hop', correlationId: 'trace-b', hop: 'utterance_end', timestampMs: 2000,
  })}`,
];
const summary = summarizeVoiceHopTraces(
  extractVoiceHopTraces([...completeWithoutTool, ...incomplete].join('\n'))
);
assert.strictEqual(summary.traceCount, 2);
assert.strictEqual(summary.completeTraceCount, 1);
assert.strictEqual(summary.incompleteTraceCount, 1);
assert.strictEqual(summary.hopDurationsMs['agent_start->first_model_token'].p95, 100);
assert.strictEqual(summary.outOfOrderTraceCount, 0);

const outOfOrderSummary = summarizeVoiceHopTraces(extractVoiceHopTraces([
  ['utterance_end', 1000],
  ['gateway_dispatch', 1100],
  ['agent_start', 1200],
  ['first_model_token', 1199],
  ['tts_first_byte', 1400],
  ['audio_output', 1500],
].map(([hop, timestampMs]) => `[VoiceHop] ${JSON.stringify({
  event: 'voice_hop', correlationId: 'trace-reordered', hop, timestampMs,
})}`).join('\n')));
assert.strictEqual(outOfOrderSummary.outOfOrderTraceCount, 1);

const absentEvidenceResult = baseResult('audible');
applyMeasuredEvidence(absentEvidenceResult, { externalEvidence: {} }, 'audible');
for (const gateId of [
  'click-to-listening-p95',
  'local-only-cloud-audio-egress',
  'clean-speaker-attributed-word-accuracy',
  'noisy-speaker-bank-der',
  'false-verified-owner-assignments',
  'diarization-caption-added-p95',
  'acknowledgement-p50',
  'separate-track-attribution',
  'unknown-attribution-abstention',
  'no-biometric-identity-claims',
  'post-cancel-suppression-barrier',
  'call-chat-result-source-parity',
  'zero-raw-audio-retention',
  'speaker-map-session-expiry',
  'memory-boundary-enforcement',
  'action-authority-enforcement',
  'behavior-oneClickAlreadyGranted',
  'behavior-conversationDeleteExport',
]) {
  assert.strictEqual(
    absentEvidenceResult.gates.find((gate) => gate.id === gateId).status,
    'FAIL'
  );
}

const passingEvidenceResult = baseResult('audible');
const allBehaviorPaths = Object.fromEntries(
  Object.keys(passingEvidenceResult.behaviorPaths).map((key) => [key, true])
);
applyMeasuredEvidence(passingEvidenceResult, { externalEvidence: {
  workerBeeAuthority,
  taskOwnerCapabilityInventory: {
    authoritative: true,
    source: 'runtime_voice_task_owner_registry',
    owners: [{ kind: 'synthetic_input_owner', acceptsInput: true }],
  },
  latency: {
    clickToListeningMs: [3900],
    taskEventVisibleMs: [240],
    sourceVisibleMs: [490],
    cancelStateMs: [240],
    cancelBarrierMs: [990],
    utteranceToAcknowledgementMs: [990, 1400],
    warmSubstantiveAudioMs: [2400],
    bargeInStopMs: [1300],
    maxActiveWorkSilenceMs: 4900,
  },
  quality: {
    cloudAudioEgressBytes: 0,
    cleanAttributedWordAccuracyPercent: 95,
    noisySpeakerBankDerPercent: 15,
    falseVerifiedOwnerAssignments: 0,
    diarizationAddedCaptionP95Ms: 300,
    separateTrackAttributionPercent: 100,
    unknownAbstentionErrors: 0,
    biometricIdentityClaims: 0,
    postCancelBarrierOutputCount: 0,
    callChatParityPercent: 100,
    rawAudioRetainedBytes: 0,
    speakerMapRowsAfterExpiry: 0,
    memoryBoundaryViolationCount: 0,
    unauthorizedSideEffectCount: 0,
  },
  behaviorPaths: allBehaviorPaths,
  escapedRegressions: Object.fromEntries(
    Object.keys(passingEvidenceResult.escapedRegressions).map((key) => [key, true])
  ),
}}, 'audible');
assert.ok(passingEvidenceResult.gates.length > 40);
assert.ok(passingEvidenceResult.gates.every((gate) => gate.status === 'PASS'));
"""
    completed = subprocess.run(
        [
            "node",
            "-e",
            script,
            str(HARNESS),
            json.dumps(MPV_061_PASSING_EVIDENCE),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_harness_refuses_public_repo_for_private_artifacts():
    completed = subprocess.run(
        [
            "node",
            str(HARNESS),
            "--self-test",
            "--output-root",
            str(ROOT / "output" / "not-private-enough"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 2
    assert "must stay outside the public repository" in completed.stderr


def test_existing_synthetic_audio_harness_requires_private_output_and_sanitizes_result():
    content = SYNTHETIC_AUDIO_HARNESS.read_text()
    assert '"--output-root"' in content
    assert "VIVENTIUM_QA_OUTPUT_ROOT" in content
    assert "must stay outside the public repository" in content
    assert 'transcriptText: ""' not in content
    assert "result.errors.push(String(error?.stack || error))" not in content
    assert "message.text.slice(0, 500)" not in content
    assert "settledVisibleState" in content
    assert "peerConnected" in content


def test_synthetic_audio_harness_keeps_bounded_connection_diagnostics_and_failure_evidence():
    script = r"""
const assert = require('assert');
const { normalizeCallReadinessEvidence } = require(process.argv[1]);

assert.deepStrictEqual(
  normalizeCallReadinessEvidence({
    endButtonReady: true,
    statusText: 'Call · listening',
    peers: [{ connectionState: 'connected', iceConnectionState: 'connected' }],
  }),
  {
    controlReady: true,
    settledVisibleState: true,
    peerConnected: true,
    peerCount: 1,
    peerStates: [{ connectionState: 'connected', iceConnectionState: 'connected' }],
  },
);
assert.deepStrictEqual(
  normalizeCallReadinessEvidence({
    endButtonReady: false,
    statusText: 'Call · connecting',
    peers: [{ connectionState: 'new', iceConnectionState: 'checking' }],
  }),
  {
    controlReady: false,
    settledVisibleState: false,
    peerConnected: false,
    peerCount: 1,
    peerStates: [{ connectionState: 'new', iceConnectionState: 'checking' }],
  },
);
const bounded = normalizeCallReadinessEvidence({
  endButtonReady: true,
  statusText: 'Synthetic private caption listening',
  peers: Array.from({ length: 5 }, (_, index) => ({
    connectionState: `${index}`.repeat(40),
    iceConnectionState: 'connected',
  })),
});
assert.strictEqual(bounded.peerCount, 4);
assert.strictEqual(bounded.peerStates[0].connectionState.length, 32);
assert.strictEqual(Object.hasOwn(bounded, 'statusText'), false);
"""
    completed = subprocess.run(
        ["node", "-e", script, str(SYNTHETIC_AUDIO_HARNESS)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr

    content = SYNTHETIC_AUDIO_HARNESS.read_text()
    assert "connectionReadiness" in content
    assert "connectionReadinessAfterFailure" in content
    assert "fs.existsSync(args.screenshot)" not in content
    assert 'startsWith("call status:")' in content


def test_acceptance_harnesses_authenticate_with_exact_session_scoped_browser_capability():
    script = r"""
const assert = require('assert');
const crypto = require('crypto');
const worldClass = require(process.argv[1]);
const synthetic = require(process.argv[2]);

const generated = synthetic.createBrowserCallCapability(new Date('2026-08-09T00:00:00.000Z'));
assert.match(generated.capability, /^[A-Za-z0-9_-]{43}$/);
assert.strictEqual(
  generated.hash,
  crypto.createHash('sha256').update(generated.capability).digest('hex'),
);
assert.strictEqual(generated.version, 1);
assert.strictEqual(generated.scope, 'call_browser_v1');
assert.throws(() => synthetic.browserCapabilityHeaders(''), /browser capability/i);
assert.throws(() => synthetic.browserCapabilityHeaders('short'), /browser capability/i);

const bootstrap = synthetic.buildCallBootstrapUrl(
  'http://localhost:4300',
  'call-a',
  generated.capability,
);
assert.strictEqual(bootstrap.pathname, '/call-bootstrap');
assert.strictEqual(bootstrap.searchParams.get('callSessionId'), 'call-a');
assert.strictEqual(bootstrap.searchParams.get('autoConnect'), '1');
assert.strictEqual(
  new URLSearchParams(bootstrap.hash.slice(1)).get('viventiumCallCapability'),
  generated.capability,
);

const storage = new Map();
global.sessionStorage = {
  getItem: (key) => storage.get(key) || null,
  setItem: (key, value) => storage.set(key, value),
};
const calls = [];
global.fetch = async (url, init = {}) => {
  const requestUrl = new URL(url, 'http://localhost:4300');
  const callSessionId = requestUrl.searchParams.get('callSessionId');
  const supplied = new Headers(init.headers || {}).get('X-VIVENTIUM-CALL-CAPABILITY');
  const expected = storage.get(`viventium.call.capability.v1:${callSessionId}`) || null;
  const ok = Boolean(expected && supplied === expected);
  calls.push({ callSessionId, headerPresent: Boolean(supplied), ok });
  return {
    ok,
    status: ok ? 200 : 401,
    json: async () => ({ ok }),
  };
};
const page = { evaluate: async (fn, value) => fn(value) };

(async () => {
  const missing = await worldClass.fetchJsonInPage(
    page,
    '/api/call-tasks?callSessionId=call-b',
    undefined,
    'call-b',
  );
  assert.strictEqual(missing.status, 401);
  assert.strictEqual(calls.at(-1).headerPresent, false);

  storage.set('viventium.call.capability.v1:call-a', 'A'.repeat(43));
  const exactKeyIsolation = await worldClass.fetchJsonInPage(
    page,
    '/api/call-tasks?callSessionId=call-b',
    undefined,
    'call-b',
  );
  assert.strictEqual(exactKeyIsolation.status, 401);
  assert.strictEqual(calls.at(-1).headerPresent, false);

  const crossSession = await worldClass.fetchJsonInPage(
    page,
    '/api/call-tasks?callSessionId=call-b',
    undefined,
    'call-a',
  );
  assert.strictEqual(crossSession.status, 401);
  assert.strictEqual(calls.at(-1).headerPresent, false);

  storage.set('viventium.call.capability.v1:call-b', 'malformed');
  const malformed = await worldClass.fetchJsonInPage(
    page,
    '/api/call-tasks?callSessionId=call-b',
    undefined,
    'call-b',
  );
  assert.strictEqual(malformed.status, 401);
  assert.strictEqual(calls.at(-1).headerPresent, false);

  storage.set('viventium.call.capability.v1:call-b', 'B'.repeat(43));
  const success = await worldClass.fetchJsonInPage(
    page,
    '/api/call-tasks?callSessionId=call-b',
    undefined,
    'call-b',
  );
  assert.strictEqual(success.status, 200);
  assert.strictEqual(calls.at(-1).headerPresent, true);
  assert.strictEqual(calls.at(-1).ok, true);

  process.stdout.write(JSON.stringify({
    statuses: [missing.status, exactKeyIsolation.status, crossSession.status, malformed.status, success.status],
  }));
})().catch((error) => {
  process.stderr.write(String(error?.stack || error));
  process.exitCode = 1;
});
"""
    completed = subprocess.run(
        ["node", "-e", script, str(HARNESS), str(SYNTHETIC_AUDIO_HARNESS)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {"statuses": [401, 401, 401, 401, 200]}
    assert "A" * 43 not in completed.stdout
    assert "B" * 43 not in completed.stdout


def test_acceptance_harnesses_strip_fragment_before_evidence_and_never_serialize_capability():
    world_class = HARNESS.read_text()
    synthetic = SYNTHETIC_AUDIO_HARNESS.read_text()
    runbook = RUNBOOK.read_text()
    manifest = json.loads(ACCEPTANCE_MANIFEST.read_text())
    mpv_046 = CASES.read_text().split("### MPV-046", 1)[1].split("\n### ", 1)[0]

    for content in (world_class, synthetic):
        assert "assertCallBootstrapStripped" in content
        assert "window.location.hash" in content
        assert "viventiumCallCapability" in content
        assert "X-VIVENTIUM-CALL-CAPABILITY" in content
        assert "result.browserCapability" not in content
        assert "console.log(browserCapability" not in content
        assert "console.error(browserCapability" not in content

    assert "browserCapabilityHash: browserCapability.hash" in synthetic
    assert "browserCapabilityExpiresAt: expiresAt" in synthetic
    assert "browserCapabilityVersion: 1" in synthetic
    assert "browserCapabilityScope: 'call_browser_v1'" in synthetic
    assert "/call-bootstrap?callSessionId=" in runbook
    assert "bootstrap must remove the fragment" in runbook
    assert "missing, malformed, and cross-session" in mpv_046
    assert "privacy scan" in mpv_046
    assert (
        "signed_call_bootstrap_url_with_ephemeral_exact_session_browser_capability"
        in manifest["prerequisites"]
    )
    assert (
        "bootstrap_fragment_stripped_before_any_evidence_capture"
        in manifest["prerequisites"]
    )


def test_modern_playground_case_ids_are_unique_and_manifest_coverage_resolves():
    cases = CASES.read_text()
    case_ids = re.findall(r"^#{2,3} (MPV-\d{3})\b", cases, flags=re.MULTILINE)
    duplicates = sorted({case_id for case_id in case_ids if case_ids.count(case_id) > 1})
    assert duplicates == []

    manifest = json.loads(ACCEPTANCE_MANIFEST.read_text())
    coverage_ids = set(manifest["coverage"])
    assert coverage_ids <= set(case_ids)
    assert {f"MPV-{number:03d}" for number in range(32, 52)} <= coverage_ids
    assert {f"MPV-{number:03d}" for number in range(57, 62)} <= set(case_ids)

    assert "### MPV-054 LiveKit Dependency Promotion Gate" in cases
    assert "### MPV-061 Full Queen Bee And Worker Bee Voice Parity" in cases
    assert "MPV-054 Full Queen Bee And Worker Bee Voice Parity" not in cases
    assert manifest["coverage"]["MPV-054"]["gates"] == [
        "livekit-dependency-suite-parity",
        "livekit-dependency-qoe-nonregression",
        "livekit-dependency-warning-diff",
        "livekit-dependency-build-install-clean-parity",
        "livekit-dependency-promotion-decision",
    ]
    assert manifest["coverage"]["MPV-061"]["gates"] == list(MPV_061_GATE_IDS)


def test_synthetic_audio_harness_labels_transport_success_as_semantically_unscored() -> None:
    content = SYNTHETIC_AUDIO_HARNESS.read_text()

    assert 'transportOk: false' in content
    assert 'semanticEvaluationStatus: "not_evaluated"' in content
    assert 'result.transportOk =' in content
    assert 'result.ok = result.transportOk;' in content
    assert "Transport/audio success does not score reasoning quality" in content
    assert "transportOk: result.transportOk" in content
    assert "semanticEvaluationStatus: result.semanticEvaluationStatus" in content
