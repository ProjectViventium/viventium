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
    assert set(coverage) == {f"MPV-{case_id:03d}" for case_id in range(25, 45)}
    for case_id, contract in coverage.items():
        assert contract["runs"], case_id
        assert contract["gates"], case_id

    runs = {run["id"]: run for run in manifest["runs"]}
    required_runs = {
        "dev-switches",
        "dev-reconnects",
        "dev-audible-65m",
        "dev-soak-120m",
        "installed-prod-real-call",
        "clean-install-parity",
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
    for run in runs.values():
        assert isinstance(run["command"], list)
        assert run["command"], run["id"]

    acquisitions = manifest["externalEvidenceAcquisition"]
    assert acquisitions["localOnlyEgress"]["missingResult"] == "FAIL"
    assert acquisitions["noisySpeakerBank"]["missingResult"] == "FAIL"
    assert acquisitions["localOnlyEgress"]["passValue"] == 0
    assert acquisitions["noisySpeakerBank"]["maximumPassValue"] == 15
    assert all(command[0] == "jq" for command in acquisitions["verificationCommands"])

    serialized = json.dumps(manifest)
    assert re.search(r"/(?:Users|home)/[^/<]+/", serialized) is None
    assert "callSessionId=actual" not in serialized


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

    for offset, (field, gate_id) in enumerate(ESCAPED_REGRESSION_FIELDS.items(), start=39):
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
        ["node", "-e", script, str(HARNESS)],
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


def test_synthetic_audio_harness_labels_transport_success_as_semantically_unscored() -> None:
    content = SYNTHETIC_AUDIO_HARNESS.read_text()

    assert 'transportOk: false' in content
    assert 'semanticEvaluationStatus: "not_evaluated"' in content
    assert 'result.transportOk =' in content
    assert 'result.ok = result.transportOk;' in content
    assert "Transport/audio success does not score reasoning quality" in content
    assert "transportOk: result.transportOk" in content
    assert "semanticEvaluationStatus: result.semanticEvaluationStatus" in content


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
    mpv_039 = CASES.read_text().split("### MPV-039", 1)[1].split("\n### ", 1)[0]

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
    assert "missing, malformed, and cross-session" in mpv_039
    assert "privacy scan" in mpv_039
    assert (
        "signed_call_bootstrap_url_with_ephemeral_exact_session_browser_capability"
        in manifest["prerequisites"]
    )
    assert (
        "bootstrap_fragment_stripped_before_any_evidence_capture"
        in manifest["prerequisites"]
    )
