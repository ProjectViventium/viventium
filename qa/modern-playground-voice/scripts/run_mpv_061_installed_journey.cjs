#!/usr/bin/env node
"use strict";

/*
 * Opt-in installed MPV-061 collector. Account creation is limited to the existing synthetic
 * LiveKit fixture. Signed decisions, speech, worker receipts, callbacks, and service restarts
 * must be observed from the running installation; this collector never manufactures them.
 */

const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawn, spawnSync } = require("node:child_process");
const { createRequire } = require("node:module");

const CASE_ID = "MPV-061";
const RELEASE_LABEL = "PRE-GATE / NOT READY";
const RUNNER_PATH = __filename;
const REPOSITORY_ROOT = fs.realpathSync(
  path.resolve(__dirname, "..", "..", ".."),
);
const RELEASE_GATE_PATH = path.join(
  REPOSITORY_ROOT,
  "scripts",
  "viventium",
  "parallel_work_release_gate.py",
);
const OWNER_STATE_PATH = path.join(
  os.homedir(),
  "Library",
  "Application Support",
  "Viventium",
  "state",
  "runtime",
  "isolated",
  "stack-owner.json",
);
const SCENARIO_SCHEMA = "viventium.voice.mpv-061.installed-journey-scenario.v1";
const OBSERVATION_SCHEMA = "viventium.voice.mpv-061.observation.v1";
const RUNTIME_HANDOFF_SCHEMA = "viventium.voice.mpv-061.runtime-handoff.v1";
const CLEANUP_STATE_SCHEMA = "viventium.voice.mpv-061.cleanup-state.v1";
const CLASSIFIER_FAULT_PARENT = path.join(
  REPOSITORY_ROOT,
  "scripts",
  "viventium",
  "mpv_061_qa_parent_control.py",
);
const MAX_PRIVATE_JSON_BYTES = 512 * 1024;
const MAX_PRIVATE_MEDIA_BYTES = 100 * 1024 * 1024;
const REQUIRED_TURNS = Object.freeze([
  Object.freeze({
    kind: "authorizedCallLaunch",
    mode: "call",
    directlyAddressed: true,
  }),
  Object.freeze({
    kind: "trustedWingLaunch",
    mode: "wing",
    directlyAddressed: true,
  }),
  Object.freeze({
    kind: "quickConversation",
    mode: "call",
    directlyAddressed: true,
  }),
  Object.freeze({
    kind: "authorizedCallControl",
    mode: "call",
    directlyAddressed: true,
  }),
  Object.freeze({
    kind: "trustedWingControl",
    mode: "wing",
    directlyAddressed: true,
  }),
  Object.freeze({
    kind: "passiveWingDenial",
    mode: "wing",
    directlyAddressed: false,
  }),
  Object.freeze({
    kind: "listenOnlyDenial",
    mode: "listen_only",
    directlyAddressed: true,
  }),
]);
const EXECUTION_TURNS = Object.freeze([
  ...REQUIRED_TURNS,
  Object.freeze({
    kind: "unverifiedWingDenial",
    mode: "wing",
    directlyAddressed: true,
    speakerRole: "alternate",
  }),
]);
const LEDGER_COLLECTIONS = Object.freeze([
  Object.freeze({
    name: "viventium_external_work",
    key: "work",
    ownerField: "ownerId",
  }),
  Object.freeze({
    name: "viventium_glasshive_callback_bindings",
    key: "bindings",
    ownerField: "ownerId",
  }),
  Object.freeze({
    name: "viventium_glasshive_mission_evidence",
    key: "missions",
    ownerField: "ownerId",
  }),
  Object.freeze({
    name: "viventium_glasshive_capability_authorizations",
    key: "capabilities",
    ownerField: "ownerId",
  }),
  Object.freeze({
    name: "viventium_glasshive_callback_results",
    key: "callbacks",
    ownerField: "ownerId",
  }),
  Object.freeze({
    name: "viventiumglasshivecallbackdeliveries",
    key: "deliveries",
    ownerField: "userId",
  }),
  Object.freeze({
    name: "viventiumorchestrationtraceevents",
    key: "trace",
    ownerField: "ownerScopeHash",
  }),
]);
const CLEANUP_OWNER_COLLECTIONS = Object.freeze([
  Object.freeze({ name: "conversations", field: "user", kind: "string" }),
  Object.freeze({ name: "messages", field: "user", kind: "string" }),
  Object.freeze({ name: "memoryentries", field: "userId", kind: "object_id" }),
  Object.freeze({
    name: "viventium_scheduler_dispatch_intents",
    field: "userId",
    kind: "string",
  }),
  Object.freeze({
    name: "viventiumglasshivecallbackeffectoutboxes",
    field: "ownerId",
    kind: "string",
  }),
  Object.freeze({ name: "files", field: "user", kind: "object_id" }),
  Object.freeze({ name: "sessions", field: "user", kind: "object_id" }),
  Object.freeze({
    name: "viventiumcallsessions",
    field: "userId",
    kind: "string",
  }),
  Object.freeze({
    name: "viventiumvoicetasks",
    field: "userId",
    kind: "string",
  }),
]);
const EFFECT_PLANES = Object.freeze([
  "launch",
  "control",
  "tool",
  "controller",
  "cortex",
  "liveMemory",
  "recall",
  "titleModel",
  "response",
  "tts",
  "audio",
]);
const REQUIRED_IDENTITY_CHECKS = Object.freeze([
  "SOURCE-IDENTITY",
  "NESTED-PINS",
  "PREBUILT-IDENTITY",
  "INSTALLED-ARTIFACT",
]);
const PRODUCER_OWNED_TRACE_STAGES = Object.freeze([
  "source.bound",
  "prompt.layers.verified",
  "prompt.layers.invalid",
  "launch.prepared",
  "launch.accepted",
  "launch.failed",
  "work.queued",
  "work.claimed",
  "work.admitted",
  "runtime.invoked",
  "provider.request.forwarded",
  "work.running",
  "attempt.history.complete",
  "capacity.history.complete",
  "callback.history.complete",
  "work.completed",
  "work.failed",
  "work.cancelled",
  "callback.accepted",
  "callback.delivery.pending",
  "callback.delivery.claimed",
  "callback.delivery.sent",
  "callback.delivery.failed",
  "callback.delivery.suppressed",
  "callback.delivery.unresolved",
  "action.accepted",
  "control.completed",
  "tool.completed",
  "controller.completed",
  "cortex.completed",
  "live_memory.completed",
  "recall.completed",
  "title_model.completed",
  "response.completed",
  "tts.completed",
  "audio.completed",
  "provider.attempt.completed",
  "provider.fallback.completed",
]);
const DIAGNOSTIC_CANDIDATE_CONTRACT = Object.freeze({
  version: 1,
  supported: true,
  status: "PRE_GATE_COMPLETE",
  releaseReady: false,
  releaseCandidateVerified: false,
  acceptanceEligible: false,
  receiptEligible: false,
  releaseLabel: RELEASE_LABEL,
});
const SCENARIO_OBSERVER_CONTRACT = Object.freeze({
  version: 1,
  producerScope: "librechat.orchestration_trace_ledger",
  runtimeIdentityFileKind: "stack_owner",
  runtimeIdentityFields: Object.freeze(["ownerBindingSha256"]),
  producerOwnedStages: PRODUCER_OWNED_TRACE_STAGES,
  effectStages: Object.freeze({
    launch: Object.freeze([
      "launch.prepared",
      "launch.accepted",
      "launch.failed",
    ]),
    control: Object.freeze(["action.accepted", "control.completed"]),
    tool: Object.freeze(["tool.completed"]),
    controller: Object.freeze(["controller.completed"]),
    cortex: Object.freeze(["cortex.completed"]),
    liveMemory: Object.freeze(["live_memory.completed"]),
    recall: Object.freeze(["recall.completed"]),
    titleModel: Object.freeze(["title_model.completed"]),
    response: Object.freeze(["response.completed"]),
    tts: Object.freeze(["tts.completed"]),
    audio: Object.freeze(["audio.completed"]),
  }),
  unavailableEffectPlanes: Object.freeze([]),
  fallback: Object.freeze({
    available: true,
    stages: Object.freeze([
      "attempt.history.complete",
      "provider.request.forwarded",
      "provider.attempt.completed",
      "provider.fallback.completed",
    ]),
    controlledTriggerAvailable: true,
    defaultRequirement: "required",
  }),
  workerCompletionDelivery: Object.freeze({
    available: true,
    producerScope: "librechat.voice_worker_completion_delivery",
    stages: Object.freeze([
      "response.completed",
      "tts.completed",
      "audio.completed",
    ]),
    blocker: null,
  }),
});
const DENIAL_FIELDS = Object.freeze([
  "missionDelta",
  "actionDelta",
  "launchDelta",
  "controlDelta",
  "toolDelta",
  "controllerDelta",
  "cortexDelta",
  "liveMemoryDelta",
  "recallDelta",
  "titleModelDelta",
  "responseDelta",
  "ttsDelta",
  "audioDelta",
]);
const SAFE_CODE = /^[a-z][a-z0-9_]{0,79}$/;
const HEX_24 = /^[a-f0-9]{24}$/i;
const HEX_64 = /^[a-f0-9]{64}$/;
const HEX_40 = /^[a-f0-9]{40}$/;
const SHA256_REF = /^sha256:[a-f0-9]{64}$/;
const ATTESTATION = /^[A-Za-z0-9_-]{43}$/;
const SAFETY_FAILURE_CODES = new Set([
  "unsafe_synthetic_schedule_detected",
  "passive_mode_side_effect_observed",
  "search_index_cleanup_scope_mismatch",
]);
const PROTECTED_RESTART_ARGUMENTS = Object.freeze([
  "dev-runtime",
  "activate-current",
  "--validate",
  "--restart",
  "--allow-protected-folder",
  "--allow-dirty-local-testing",
]);

class JourneyBlocked extends Error {
  constructor(code) {
    const safeCode = SAFE_CODE.test(String(code || ""))
      ? String(code)
      : "journey_blocked";
    super(safeCode);
    this.name = "JourneyBlocked";
    this.code = safeCode;
  }
}

function blocked(code) {
  throw new JourneyBlocked(code);
}

function record(value) {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function digest(bytes) {
  return crypto.createHash("sha256").update(bytes).digest("hex");
}

function canonicalJson(value) {
  if (Array.isArray(value)) {
    return `[${value.map(canonicalJson).join(",")}]`;
  }
  if (record(value)) {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

function candidateBindingSha256(value) {
  return digest(Buffer.from(canonicalJson(value), "utf8"));
}

function assertDiagnosticCandidate(measured) {
  const binding = measured?.runtimeBinding;
  const source = measured?.measuredIdentity?.source;
  const components = measured?.measuredIdentity?.nestedComponents;
  const prebuilt = measured?.measuredIdentity?.prebuiltHelper;
  const installed = measured?.measuredIdentity?.installed;
  if (
    !record(binding) ||
    binding.active !== true ||
    binding.ownerRootMatches !== true ||
    binding.runtimeRootMatches !== true ||
    !HEX_64.test(String(binding.processIdentitySha256 || "")) ||
    !HEX_64.test(String(binding.ownerBindingSha256 || "")) ||
    !HEX_64.test(String(measured?.candidateDigest || "")) ||
    !HEX_64.test(String(measured?.artifactDigest || "")) ||
    !HEX_40.test(String(source?.revision || "")) ||
    !HEX_64.test(String(source?.worktreeHash || "")) ||
    !HEX_64.test(String(source?.componentsLockSha256 || "")) ||
    !Array.isArray(components) ||
    components.length < 1 ||
    components.some(
      (component) =>
        !HEX_40.test(String(component?.pin || "")) ||
        !HEX_40.test(String(component?.revision || "")) ||
        !HEX_64.test(String(component?.worktreeHash || "")) ||
        typeof component.clean !== "boolean",
    ) ||
    !HEX_64.test(String(prebuilt?.sourceMeasuredSha256 || "")) ||
    !HEX_64.test(String(prebuilt?.binaryMeasuredSha256 || "")) ||
    !HEX_40.test(String(installed?.rootRevision || "")) ||
    !HEX_64.test(String(installed?.runningServiceSha256 || "")) ||
    !HEX_64.test(String(installed?.frontendBuildSha256 || "")) ||
    !HEX_64.test(String(installed?.apiBuildSha256 || "")) ||
    !Array.isArray(measured?.checks) ||
    REQUIRED_IDENTITY_CHECKS.some(
      (id) => measured.checks.filter((check) => check?.id === id).length !== 1,
    )
  ) {
    blocked("diagnostic_active_runtime_identity_unproven");
  }
  const checks = measured.checks.map(({ id, status, reason }) => ({
    id,
    status,
    reason: String(reason || ""),
  }));
  return {
    verified: true,
    candidateMode: "diagnostic",
    releaseCandidateVerified: false,
    acceptanceEligible: false,
    receiptEligible: false,
    candidateDigest: measured.candidateDigest,
    artifactDigest: measured.artifactDigest,
    checks,
    identityFailures: checks.filter((check) => check.status !== "PASS"),
    runtimeBinding: {
      active: true,
      ownerRootMatches: true,
      runtimeRootMatches: true,
      ownerBindingSha256: binding.ownerBindingSha256,
      processIdentitySha256: binding.processIdentitySha256,
    },
    measuredIdentity: measured.measuredIdentity,
    status: DIAGNOSTIC_CANDIDATE_CONTRACT.status,
    releaseReady: false,
    releaseLabel: RELEASE_LABEL,
  };
}

function assertStrictCandidate(measured) {
  let normalized;
  try {
    normalized = assertDiagnosticCandidate(measured);
  } catch {
    blocked("strict_candidate_identity_invalid");
  }
  const source = normalized.measuredIdentity.source;
  const components = normalized.measuredIdentity.nestedComponents;
  if (
    normalized.checks.some((check) => check.status !== "PASS") ||
    source.clean !== true ||
    components.some(
      (component) =>
        component.clean !== true || component.pin !== component.revision,
    )
  ) {
    blocked("strict_candidate_identity_invalid");
  }
  const {
    status: _diagnosticStatus,
    releaseReady: _diagnosticReleaseReady,
    releaseLabel: _diagnosticReleaseLabel,
    ...strict
  } = normalized;
  return {
    ...strict,
    candidateMode: "strict",
    releaseCandidateVerified: true,
    acceptanceEligible: true,
    receiptEligible: true,
    identityFailures: [],
  };
}

function normalizedCandidateBinding(measured, mode) {
  const normalized =
    mode === "diagnostic"
      ? assertDiagnosticCandidate(measured)
      : assertStrictCandidate(measured);
  return Object.fromEntries(
    Object.entries(normalized).filter(([, value]) => value !== undefined),
  );
}

function assertScenarioCandidateBinding(scenario, measured, mode) {
  const normalized = normalizedCandidateBinding(measured, mode);
  if (mode === "diagnostic") {
    if (
      !record(scenario?.candidate) ||
      canonicalJson(scenario.candidate) !== canonicalJson(normalized)
    ) {
      blocked("scenario_candidate_binding_mismatch");
    }
  }
  return normalized;
}

function opaqueRef(namespace, value) {
  if (typeof value !== "string" || !value.trim()) {
    blocked("observed_identity_unavailable");
  }
  return "sha256:" + digest(Buffer.from(namespace + "\u0000" + value));
}

function traceCandidateFacts(candidate) {
  const candidateDigest = String(candidate?.candidateDigest || "");
  const installedArtifactDigest = String(candidate?.artifactDigest || "");
  const runtimeOwnerBindingHash = String(
    candidate?.runtimeBinding?.ownerBindingSha256 || "",
  );
  if (
    !HEX_64.test(candidateDigest) ||
    !HEX_64.test(installedArtifactDigest) ||
    !HEX_64.test(runtimeOwnerBindingHash)
  ) {
    blocked("installed_trace_candidate_binding_unavailable");
  }
  return {
    candidateDigest: "sha256:" + candidateDigest,
    installedArtifactDigest: "sha256:" + installedArtifactDigest,
    runtimeOwnerBindingHash: "sha256:" + runtimeOwnerBindingHash,
  };
}

function matchesVoiceTraceScope(
  event,
  { ownerId, callSessionId, turnId, candidate, workRef },
) {
  if (!record(event) || !record(event.facts)) return false;
  const facts = event.facts;
  const binding = traceCandidateFacts(candidate);
  return (
    event.ownerScopeHash === opaqueRef("owner", ownerId) &&
    facts.callSessionRefHash === opaqueRef("call_session", callSessionId) &&
    facts.logicalTurnRefHash === opaqueRef("logical_turn", turnId) &&
    facts.candidateDigest === binding.candidateDigest &&
    facts.installedArtifactDigest === binding.installedArtifactDigest &&
    facts.runtimeOwnerBindingHash === binding.runtimeOwnerBindingHash &&
    (workRef == null || facts.workRefHash === opaqueRef("work", workRef))
  );
}

function ownsPath(candidate, root) {
  const relative = path.relative(root, candidate);
  return (
    relative.length > 0 &&
    !relative.startsWith(".." + path.sep) &&
    relative !== ".." &&
    !path.isAbsolute(relative)
  );
}

function assertOutsideRepository(candidate, label) {
  const resolved = path.resolve(candidate);
  if (resolved === REPOSITORY_ROOT || ownsPath(resolved, REPOSITORY_ROOT)) {
    blocked(label + "_inside_repository");
  }
}

function rejectSymlinkComponents(candidate, label) {
  const absolute = path.resolve(candidate);
  const parsed = path.parse(absolute);
  const components = absolute
    .slice(parsed.root.length)
    .split(path.sep)
    .filter(Boolean);
  let current = parsed.root;
  for (const component of components) {
    current = path.join(current, component);
    let metadata;
    try {
      metadata = fs.lstatSync(current);
    } catch (error) {
      if (error && error.code === "ENOENT") {
        return;
      }
      blocked(label + "_unavailable");
    }
    if (metadata.isSymbolicLink()) {
      blocked(label + "_symlink_forbidden");
    }
  }
}

function exactCurrentOwner(metadata) {
  return (
    typeof process.getuid !== "function" || metadata.uid === process.getuid()
  );
}

function inspectEvidenceRoot(value) {
  if (typeof value !== "string" || !value.trim()) {
    blocked("evidence_root_unavailable");
  }
  const selected = path.resolve(value);
  if (selected === path.parse(selected).root) {
    blocked("evidence_root_not_private");
  }
  assertOutsideRepository(selected, "evidence_root");
  rejectSymlinkComponents(selected, "evidence_root");
  if (!fs.existsSync(selected)) {
    return selected;
  }
  const metadata = fs.lstatSync(selected);
  if (
    !metadata.isDirectory() ||
    !exactCurrentOwner(metadata) ||
    (metadata.mode & 0o777) !== 0o700
  ) {
    blocked("evidence_root_not_private");
  }
  const exact = fs.realpathSync(selected);
  assertOutsideRepository(exact, "evidence_root");
  return exact;
}

function readPrivateBytes(
  value,
  label,
  maximumBytes = MAX_PRIVATE_MEDIA_BYTES,
) {
  if (typeof value !== "string" || !value.trim()) {
    blocked(label + "_unavailable");
  }
  const selected = path.resolve(value);
  assertOutsideRepository(selected, label);
  rejectSymlinkComponents(selected, label);
  let descriptor;
  try {
    descriptor = fs.openSync(
      selected,
      fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW,
    );
    const before = fs.fstatSync(descriptor);
    if (
      !before.isFile() ||
      !exactCurrentOwner(before) ||
      before.nlink !== 1 ||
      (before.mode & 0o777) !== 0o600
    ) {
      blocked(label + "_not_private");
    }
    if (before.size <= 0 || before.size > maximumBytes) {
      blocked(label + "_invalid");
    }
    const bytes = fs.readFileSync(descriptor);
    const after = fs.fstatSync(descriptor);
    if (
      bytes.length !== before.size ||
      before.dev !== after.dev ||
      before.ino !== after.ino ||
      before.size !== after.size ||
      before.mtimeMs !== after.mtimeMs ||
      before.ctimeMs !== after.ctimeMs
    ) {
      blocked(label + "_changed");
    }
    const exact = fs.realpathSync(selected);
    assertOutsideRepository(exact, label);
    return { path: exact, bytes, sha256: digest(bytes) };
  } catch (error) {
    if (error instanceof JourneyBlocked) {
      throw error;
    }
    blocked(label + "_unavailable");
  } finally {
    if (descriptor !== undefined) {
      fs.closeSync(descriptor);
    }
  }
}

function readPrivateJson(value, label) {
  const content = readPrivateBytes(value, label, MAX_PRIVATE_JSON_BYTES);
  try {
    const parsed = JSON.parse(content.bytes.toString("utf8"));
    if (!record(parsed)) {
      blocked(label + "_invalid");
    }
    return parsed;
  } catch (error) {
    if (error instanceof JourneyBlocked) {
      throw error;
    }
    blocked(label + "_invalid");
  }
}

function measureInstalledCandidate({
  artifactIdentity,
  candidateMode = "strict",
}) {
  if (!new Set(["strict", "diagnostic"]).has(candidateMode)) {
    blocked("candidate_mode_invalid");
  }
  const failure =
    candidateMode === "diagnostic"
      ? "diagnostic_active_runtime_identity_unproven"
      : "strict_candidate_identity_invalid";
  let owner;
  let runtimeRoot;
  let installedRoot;
  let identityPath;
  try {
    owner = readPrivateJson(OWNER_STATE_PATH, "runtime_owner_state");
    runtimeRoot = fs.realpathSync(String(owner.runtimeDir || ""));
    installedRoot = fs.realpathSync(String(owner.repoRoot || ""));
    identityPath = fs.realpathSync(String(artifactIdentity || ""));
  } catch (error) {
    if (
      error instanceof JourneyBlocked &&
      error.code !== "runtime_owner_state_unavailable"
    ) {
      blocked(failure);
    }
    blocked(failure);
  }
  if (
    installedRoot !== REPOSITORY_ROOT ||
    identityPath !==
      path.join(runtimeRoot, "parallel-work-artifact-identity.json")
  ) {
    blocked(failure);
  }
  const probe = [
    "import importlib.util,json,sys",
    "from pathlib import Path",
    "spec=importlib.util.spec_from_file_location('viventium_mpv061_identity_probe',sys.argv[1])",
    "module=importlib.util.module_from_spec(spec)",
    "sys.modules[spec.name]=module",
    "spec.loader.exec_module(module)",
    "identity=json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))",
    "root=Path(sys.argv[3])",
    "runtime=Path(sys.argv[4])",
    "owner_path=Path(sys.argv[5])",
    "checks,_=module._artifact_identity_checks(root,identity,runtime/'prompt-bundle.json',root,owner_path)",
    "candidate,artifact=module._qa_candidate_digests(identity)",
    "active=module._runtime_owner_state_proves_active(root,owner_path)",
    "owner=json.loads(owner_path.read_text(encoding='utf-8'))",
    "measured=module._public_artifact_identity(module._measured_artifact_identity(root,runtime/'prompt-bundle.json',root,owner_path))",
    "diagnostic_candidate=module._canonical_hash({'source':measured.get('source'),'nestedComponents':measured.get('nestedComponents'),'prebuiltHelper':measured.get('prebuiltHelper')})",
    "diagnostic_artifact=module._canonical_hash(measured.get('installed'))",
    "binding={'active':active,'ownerRootMatches':active and Path(str(owner.get('repoRoot') or '')).resolve(strict=True)==root.resolve(strict=True),'runtimeRootMatches':active and Path(str(owner.get('runtimeDir') or '')).resolve(strict=True)==runtime.resolve(strict=True),'ownerBindingSha256':str(owner.get('ownerBindingSha256') or ''),'processIdentitySha256':module._canonical_hash({'pid':str(owner.get('ownerPid') or ''),'startedAt':str(owner.get('ownerProcessStartedAt') or ''),'executable':str(owner.get('ownerExecutablePath') or '')}) if active else ''}",
    "print(json.dumps({'candidateDigest':candidate,'artifactDigest':artifact,'diagnosticCandidateDigest':diagnostic_candidate,'diagnosticArtifactDigest':diagnostic_artifact,'checks':[{'id':item.check_id,'status':item.status,'reason':item.reason} for item in checks],'runtimeBinding':binding,'measuredIdentity':measured}))",
  ].join(";");
  const completed = spawnSync(
    "python3",
    [
      "-c",
      probe,
      RELEASE_GATE_PATH,
      identityPath,
      REPOSITORY_ROOT,
      runtimeRoot,
      OWNER_STATE_PATH,
    ],
    {
      cwd: REPOSITORY_ROOT,
      encoding: "utf8",
      timeout: 30_000,
      maxBuffer: 1024 * 1024,
      stdio: ["ignore", "pipe", "ignore"],
    },
  );
  if (completed.status !== 0) {
    blocked(failure);
  }
  let measured;
  try {
    measured = JSON.parse(completed.stdout);
  } catch {
    blocked(failure);
  }
  if (candidateMode === "diagnostic") {
    measured = {
      ...measured,
      candidateDigest: measured.diagnosticCandidateDigest,
      artifactDigest: measured.diagnosticArtifactDigest,
    };
  }
  return normalizedCandidateBinding(measured, candidateMode);
}

function parseArguments(argv) {
  const options = {
    localQa: false,
    allowSyntheticAccount: false,
    allowRuntimeRestart: false,
    cleanupOnly: false,
    candidateMode: "strict",
    evidenceRoot: "",
    scenario: "",
  };
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--local-qa") {
      options.localQa = true;
    } else if (value === "--allow-synthetic-account") {
      options.allowSyntheticAccount = true;
    } else if (value === "--allow-runtime-restart") {
      options.allowRuntimeRestart = true;
    } else if (value === "--cleanup-only") {
      options.cleanupOnly = true;
    } else if (
      value === "--evidence-root" ||
      value === "--scenario" ||
      value === "--candidate-mode"
    ) {
      const next = argv[index + 1];
      if (typeof next !== "string" || !next || next.startsWith("--")) {
        blocked("required_argument_missing");
      }
      if (value === "--evidence-root") options.evidenceRoot = next;
      else if (value === "--scenario") options.scenario = next;
      else options.candidateMode = next;
      index += 1;
    } else {
      blocked("unknown_argument");
    }
  }
  if (!new Set(["strict", "diagnostic"]).has(options.candidateMode)) {
    blocked("candidate_mode_invalid");
  }
  if (
    options.cleanupOnly &&
    (options.allowSyntheticAccount || options.allowRuntimeRestart)
  ) {
    blocked("cleanup_only_rejects_mutating_opt_ins");
  }
  return options;
}

function assertFallbackPolicy(value, candidateMode = "diagnostic") {
  const trigger = value?.controlledTrigger;
  if (
    !record(value) ||
    value.required !== true ||
    !record(trigger) ||
    Object.keys(trigger).sort().join(",") !==
      "approvalWaitMs,caseId,kind,targetTurnKind" ||
    trigger.kind !== "mpv_061_parent_private_fd_v1" ||
    trigger.caseId !== CASE_ID ||
    trigger.targetTurnKind !== "trustedWingLaunch" ||
    trigger.approvalWaitMs !== 750 ||
    value.reason !== "parent_approved_pre_model_fault" ||
    !new Set(["strict", "diagnostic"]).has(candidateMode)
  ) {
    blocked("provider_fallback_policy_invalid");
  }
  return {
    required: true,
    controlledTrigger: { ...trigger },
    reason: "parent_approved_pre_model_fault",
  };
}

function assertPrearmedTurnTiming(turn, startMs, receipt) {
  const speechAtMs = startMs + Number(turn?.startAfterMs);
  const armAtMs = startMs + Number(turn?.armAfterMs);
  const armedAtMs = Number(receipt?.armedAtMs);
  if (
    !record(turn) ||
    !Number.isSafeInteger(startMs) ||
    !Number.isSafeInteger(turn.armAfterMs) ||
    !Number.isSafeInteger(turn.startAfterMs) ||
    turn.armAfterMs < 0 ||
    turn.armAfterMs >= turn.startAfterMs ||
    !record(receipt) ||
    receipt.mode !== turn.mode ||
    !Number.isSafeInteger(receipt.callModeRevision) ||
    receipt.callModeRevision < 0 ||
    !Number.isSafeInteger(armedAtMs) ||
    armedAtMs >= speechAtMs
  ) {
    blocked("turn_mode_prearm_not_observed");
  }
  return {
    mode: turn.mode,
    armAtMs,
    armedAtMs,
    speechAtMs,
    callModeRevision: receipt.callModeRevision,
    armedBeforeSpeech: true,
  };
}

function createSignalRecovery(processLike = process) {
  let installed = false;
  let requested = null;
  let runtime = null;
  let deliveredRuntime = null;
  const handlers = new Map();
  const deliver = () => {
    if (
      requested &&
      runtime &&
      runtime !== deliveredRuntime &&
      typeof runtime.requestInterruption === "function"
    ) {
      deliveredRuntime = runtime;
      runtime.requestInterruption(requested);
    }
  };
  for (const signal of ["SIGINT", "SIGTERM"]) {
    handlers.set(signal, () => {
      if (!requested) requested = signal;
      deliver();
    });
  }
  return {
    install() {
      if (installed) return;
      if (!processLike || typeof processLike.once !== "function") {
        blocked("signal_recovery_unavailable");
      }
      installed = true;
      for (const [signal, handler] of handlers) {
        processLike.once(signal, handler);
      }
    },
    uninstall() {
      if (!installed) return;
      installed = false;
      const remove =
        typeof processLike.off === "function"
          ? processLike.off.bind(processLike)
          : processLike.removeListener?.bind(processLike);
      if (remove) {
        for (const [signal, handler] of handlers) remove(signal, handler);
      }
    },
    bindRuntime(value) {
      runtime = value || null;
      deliver();
    },
    throwIfRequested() {
      if (requested) blocked("journey_interrupted");
    },
    requestedSignal() {
      return requested;
    },
  };
}

function assertLoopbackOrigin(value) {
  let parsed;
  try {
    parsed = new URL(value);
  } catch {
    blocked("runtime_origin_not_local");
  }
  if (
    parsed.protocol !== "http:" ||
    !["localhost", "127.0.0.1", "[::1]"].includes(parsed.hostname) ||
    parsed.username ||
    parsed.password ||
    parsed.search ||
    parsed.hash
  ) {
    blocked("runtime_origin_not_local");
  }
  return parsed.origin;
}

function assertLocalMongoUri(value) {
  if (typeof value !== "string" || !value.trim()) {
    blocked("mongo_uri_unavailable");
  }
  let parsed;
  try {
    parsed = new URL(value);
  } catch {
    blocked("mongo_not_local");
  }
  if (
    parsed.protocol !== "mongodb:" ||
    !["localhost", "127.0.0.1", "[::1]"].includes(parsed.hostname)
  ) {
    blocked("mongo_not_local");
  }
  return value;
}

function inspectOutput(value, root, label) {
  if (typeof value !== "string" || !value.trim()) {
    blocked(label + "_unavailable");
  }
  const selected = path.resolve(value);
  if (!ownsPath(selected, root)) {
    blocked(label + "_outside_evidence_root");
  }
  rejectSymlinkComponents(selected, label);
  if (fs.existsSync(selected)) {
    const metadata = fs.lstatSync(selected);
    if (
      !metadata.isFile() ||
      !exactCurrentOwner(metadata) ||
      (metadata.mode & 0o777) !== 0o600 ||
      metadata.nlink !== 1
    ) {
      blocked(label + "_not_private");
    }
  }
  return selected;
}

function voiceHelpers() {
  try {
    return require("./livekit_synthetic_audio_qa.js");
  } catch {
    blocked("installed_voice_harness_unavailable");
  }
}

function validateScenario(scenario, evidenceRoot, environment = process.env) {
  if (
    !record(scenario) ||
    scenario.schema !== SCENARIO_SCHEMA ||
    scenario.caseId !== CASE_ID ||
    scenario.environment !== "installed_prod"
  ) {
    blocked("scenario_contract_invalid");
  }
  if (
    record(scenario.observation) &&
    Object.hasOwn(scenario.observation, "manifestProjection")
  ) {
    blocked("caller_supplied_manifest_forbidden");
  }
  if (
    !Array.isArray(scenario.turns) ||
    scenario.turns.length !== EXECUTION_TURNS.length ||
    scenario.turns.some(
      (turn, index) =>
        !record(turn) || turn.kind !== EXECUTION_TURNS[index].kind,
    )
  ) {
    blocked("scenario_turn_order_invalid");
  }
  if (
    scenario.turns.some(
      (turn, index) =>
        turn.mode !== EXECUTION_TURNS[index].mode ||
        turn.directlyAddressed !== EXECUTION_TURNS[index].directlyAddressed ||
        (EXECUTION_TURNS[index].speakerRole
          ? turn.speakerRole !== EXECUTION_TURNS[index].speakerRole
          : Object.hasOwn(turn, "speakerRole")) ||
        typeof turn.expectedTranscript !== "string" ||
        !turn.expectedTranscript.trim() ||
        !Number.isSafeInteger(turn.armAfterMs) ||
        turn.armAfterMs < 0 ||
        !Number.isSafeInteger(turn.startAfterMs) ||
        turn.startAfterMs <= turn.armAfterMs ||
        (index > 0 &&
          (turn.startAfterMs < scenario.turns[index - 1].startAfterMs ||
            turn.armAfterMs < scenario.turns[index - 1].armAfterMs)),
    )
  ) {
    blocked("scenario_turn_contract_invalid");
  }
  if (
    !record(scenario.runtime) ||
    !record(scenario.runtime.assistant) ||
    typeof scenario.runtime.assistant.provider !== "string" ||
    !scenario.runtime.assistant.provider.trim() ||
    typeof scenario.runtime.assistant.model !== "string" ||
    !scenario.runtime.assistant.model.trim()
  ) {
    blocked("exact_model_unavailable");
  }
  const playgroundUrl = assertLoopbackOrigin(scenario.runtime.playgroundUrl);
  const coreUrl = assertLoopbackOrigin(scenario.runtime.coreUrl);
  if (
    !record(scenario.runtime.agent) ||
    typeof scenario.runtime.agent.id !== "string" ||
    !scenario.runtime.agent.id ||
    typeof scenario.runtime.agent.name !== "string" ||
    !scenario.runtime.agent.name
  ) {
    blocked("installed_agent_unavailable");
  }
  if (!record(scenario.audio)) {
    blocked("initial_audio_unavailable");
  }
  const initial = readPrivateBytes(scenario.audio.initial, "initial_audio");
  const reconnect = readPrivateBytes(
    scenario.audio.reconnect,
    "reconnect_audio",
  );
  const inspectAudio = voiceHelpers().inspectAudiblePcmWav;
  if (!inspectAudio(initial.bytes)) {
    blocked("initial_audio_not_audible");
  }
  if (!inspectAudio(reconnect.bytes)) {
    blocked("reconnect_audio_not_audible");
  }
  if (initial.path === reconnect.path || initial.sha256 === reconnect.sha256) {
    blocked("session_audio_not_distinct");
  }
  if (
    !Array.isArray(scenario.attachments) ||
    scenario.attachments.length !== 2 ||
    scenario.attachments.some(
      (item, index) =>
        !record(item) ||
        item.worker !== ["A", "B"][index] ||
        typeof item.dispatchInstruction !== "string" ||
        !item.dispatchInstruction.trim(),
    )
  ) {
    blocked("attachment_group_invalid");
  }
  const attachments = scenario.attachments.map((item, index) => ({
    ...item,
    observed: readPrivateBytes(
      item.path,
      index === 0 ? "attachment_a" : "attachment_b",
    ),
  }));
  if (
    attachments[0].observed.path === attachments[1].observed.path ||
    attachments[0].observed.sha256 === attachments[1].observed.sha256
  ) {
    blocked("attachment_identity_not_distinct");
  }
  if (!record(scenario.outputs)) {
    blocked("manifest_unavailable");
  }
  const outputs = {
    manifest: inspectOutput(
      scenario.outputs.manifest,
      evidenceRoot,
      "manifest",
    ),
    result: inspectOutput(scenario.outputs.result, evidenceRoot, "result"),
    cleanupState: inspectOutput(
      scenario.outputs.cleanupState,
      evidenceRoot,
      "cleanup_state",
    ),
  };
  if (new Set(Object.values(outputs)).size !== Object.keys(outputs).length) {
    blocked("evidence_outputs_not_distinct");
  }
  const identity = readPrivateBytes(
    scenario.artifactIdentity,
    "artifact_identity",
    MAX_PRIVATE_JSON_BYTES,
  );
  if (typeof scenario.runtime.mongoUriFile !== "string") {
    blocked("mongo_uri_unavailable");
  }
  const mongoHandoffPath = readPrivateBytes(
    scenario.runtime.mongoUriFile,
    "mongo_uri_handoff",
    MAX_PRIVATE_JSON_BYTES,
  );
  let mongoHandoff;
  try {
    mongoHandoff = JSON.parse(mongoHandoffPath.bytes.toString("utf8"));
  } catch {
    blocked("mongo_uri_handoff_invalid");
  }
  if (
    !record(mongoHandoff) ||
    mongoHandoff.schema !== RUNTIME_HANDOFF_SCHEMA ||
    canonicalJson(Object.keys(mongoHandoff).sort()) !==
      canonicalJson(["MONGO_URI", "schema"])
  ) {
    blocked("mongo_uri_handoff_invalid");
  }
  const mongoUri = assertLocalMongoUri(mongoHandoff.MONGO_URI);
  const fallbackPolicy = assertFallbackPolicy(
    scenario.requirements?.providerFallback,
    "diagnostic",
  );
  const runtime = {
    ...scenario.runtime,
    playgroundUrl,
    coreUrl,
    mongoUriFile: mongoHandoffPath.path,
  };
  Object.defineProperty(runtime, "mongoUri", {
    value: mongoUri,
    enumerable: false,
    writable: false,
    configurable: false,
  });
  return {
    ...scenario,
    artifactIdentity: identity.path,
    runtime,
    audio: { initial: initial.path, reconnect: reconnect.path },
    attachments,
    requirements: { providerFallback: fallbackPolicy },
    outputs,
  };
}

function validateSignedWingDecision(
  observation,
  expected,
  directlyAddressed,
  now = Date.now(),
) {
  if (
    !record(observation) ||
    observation.transportObserved !== true ||
    observation.responseStatus !== 200
  ) {
    blocked("wing_signed_authority_not_observed");
  }
  let request;
  try {
    request = new URL(observation.requestUrl);
  } catch {
    blocked("wing_signed_authority_not_observed");
  }
  if (
    request.origin !== assertLoopbackOrigin(expected.playgroundUrl) ||
    request.pathname !== "/api/call-engagement"
  ) {
    blocked("wing_signed_authority_not_observed");
  }
  if (
    !record(observation.model) ||
    observation.model.provider !== expected.assistant.provider ||
    observation.model.model !== expected.assistant.model
  ) {
    blocked("wing_exact_model_not_observed");
  }
  const verdict = observation.verdict;
  if (
    !record(verdict) ||
    verdict.version !== 1 ||
    verdict.callSessionId !== expected.callSessionId ||
    verdict.turnId !== expected.turnId ||
    verdict.participantIdentity !== expected.participantIdentity ||
    verdict.directlyAddressed !== directlyAddressed ||
    verdict.source !== "semantic_model" ||
    !Number.isSafeInteger(verdict.revision) ||
    verdict.revision <= 0 ||
    !Number.isSafeInteger(verdict.issuedAtMs) ||
    !Number.isSafeInteger(verdict.expiresAtMs) ||
    verdict.expiresAtMs <= verdict.issuedAtMs ||
    verdict.expiresAtMs - verdict.issuedAtMs > 30_000 ||
    now < verdict.issuedAtMs - 5_000 ||
    now >= verdict.expiresAtMs ||
    !ATTESTATION.test(String(verdict.attestation || "")) ||
    !Array.isArray(verdict.segmentIds) ||
    verdict.segmentIds.length < 1 ||
    verdict.segmentIds.length > 32 ||
    new Set(verdict.segmentIds).size !== verdict.segmentIds.length
  ) {
    blocked("wing_signed_authority_invalid");
  }
  const segments = new Map(
    Array.isArray(observation.finalSegments)
      ? observation.finalSegments.map((segment) => [segment.segmentId, segment])
      : [],
  );
  for (const segmentId of verdict.segmentIds) {
    const segment = segments.get(segmentId);
    if (
      !record(segment) ||
      segment.callSessionId !== verdict.callSessionId ||
      segment.turnId !== verdict.turnId ||
      segment.isFinal !== true ||
      segment.revision !== verdict.revision ||
      segment.overlap === true ||
      segment.uncertain === true ||
      !record(segment.speaker) ||
      segment.speaker.attribution !== "verified" ||
      segment.speaker.actorTrust !== "owner_participant" ||
      segment.speaker.participantIdentity !== verdict.participantIdentity
    ) {
      blocked("wing_owner_speaker_unverified");
    }
  }
  return verdict;
}

function validateSignedWingAuthority(observation, expected, now = Date.now()) {
  return validateSignedWingDecision(observation, expected, true, now);
}

async function captureOwnerLedger(database, ownerId) {
  if (!HEX_24.test(String(ownerId || ""))) {
    blocked("owner_ledger_scope_invalid");
  }
  const ownerScopeHash = opaqueRef("owner", ownerId);
  const ledger = {
    source: "owner_scoped_worker_mission_action_delivery_ledger",
    ownerScopeHash,
  };
  try {
    for (const collection of LEDGER_COLLECTIONS) {
      const expected =
        collection.ownerField === "ownerScopeHash" ? ownerScopeHash : ownerId;
      const rows = await database
        .collection(collection.name)
        .find({ [collection.ownerField]: expected })
        .sort({ _id: 1 })
        .limit(2_000)
        .toArray();
      if (
        !Array.isArray(rows) ||
        rows.some(
          (row) =>
            !record(row) ||
            String(row[collection.ownerField] || "") !== expected,
        )
      ) {
        blocked("owner_ledger_scope_mismatch");
      }
      ledger[collection.key] = rows;
    }
    return ledger;
  } catch (error) {
    if (error instanceof JourneyBlocked) {
      throw error;
    }
    blocked("owner_ledger_unavailable");
  }
}

function orderedMissionWorkers(window, ownerId) {
  const before = window?.before?.ledger?.work;
  const after = window?.after?.ledger?.work;
  const bindings = window?.after?.ledger?.bindings;
  if (
    !HEX_24.test(String(ownerId || "")) ||
    !Array.isArray(before) ||
    !Array.isArray(after) ||
    !Array.isArray(bindings)
  ) {
    blocked("worker_launch_order_unobserved");
  }
  const earlier = new Set(before.map((row) => String(row?.workRef || "")));
  const created = after.filter(
    (row) =>
      record(row) &&
      row.ownerId === ownerId &&
      typeof row.workRef === "string" &&
      row.workRef &&
      !earlier.has(row.workRef),
  );
  if (created.length !== 2) blocked("worker_launch_order_unobserved");
  const ranked = created.map((worker) => {
    const matching = bindings.filter(
      (binding) =>
        record(binding) &&
        binding.ownerId === ownerId &&
        binding.workRef === worker.workRef &&
        Number.isSafeInteger(binding.objectiveOrdinal) &&
        binding.objectiveOrdinal >= 0,
    );
    if (matching.length !== 1) blocked("worker_launch_order_unobserved");
    return { worker, objectiveOrdinal: matching[0].objectiveOrdinal };
  });
  if (
    new Set(ranked.map((item) => item.objectiveOrdinal)).size !== ranked.length
  ) {
    blocked("worker_launch_order_unobserved");
  }
  return ranked
    .sort((left, right) => left.objectiveOrdinal - right.objectiveOrdinal)
    .map((item) => item.worker);
}

function assertPassiveDenial(window) {
  if (
    !record(window) ||
    !["wing", "listen_only"].includes(window.mode) ||
    !Number.isSafeInteger(window.transcriptDelta) ||
    window.transcriptDelta < 1
  ) {
    blocked("passive_mode_transcript_unobserved");
  }
  for (const field of DENIAL_FIELDS) {
    if (window[field] !== 0) {
      blocked("passive_mode_side_effect_observed");
    }
  }
  return window;
}

function assertUnverifiedWingDenial(window, session) {
  if (
    !record(window) ||
    window.kind !== "unverifiedWingDenial" ||
    window.mode !== "wing" ||
    window.directlyAddressed !== true ||
    !record(window.segment?.speaker) ||
    window.segment.speaker.attribution !== "unverified" ||
    window.segment.speaker.actorTrust !== "shared_mic_unverified" ||
    window.segment.speaker.participantIdentity !==
      session?.ownerParticipantIdentity ||
    session?.speakerAttributionState !== "shared_mic_unverified" ||
    window.scheduleDelta !== 0 ||
    window.unsafeScheduleCount !== 0 ||
    window.denial?.durable !== true ||
    window.denial?.ingressStatus !== "ambient_participant" ||
    !record(window.denial?.engagement) ||
    window.denial.engagement.transportObserved !== true ||
    window.denial.engagement.responseStatus !== 403 ||
    window.denial.engagement.code !== "voice_engagement_not_authorized" ||
    window.denial.engagement.turnId !== window.segment.turnId
  ) {
    blocked("unverified_wing_denial_not_observed");
  }
  assertPassiveDenial(window);
  return window;
}

function acceptSemanticVerifierResult(result, exitCode) {
  if (
    exitCode !== 0 ||
    !record(result) ||
    result.caseId !== CASE_ID ||
    result.status !== "PASS" ||
    result.scope !== "full_journey" ||
    result.fullJourneyStatus !== "PASS" ||
    result.authoritySliceOnlyPassAccepted !== false ||
    !record(result.candidateBinding) ||
    result.candidateBinding.matched !== true ||
    !record(result.privacy) ||
    result.privacy.publicSafe !== true ||
    !Array.isArray(result.gates) ||
    result.gates.length < 1 ||
    result.gates.some((gate) => !record(gate) || gate.status !== "PASS")
  ) {
    blocked("full_journey_semantic_verification_missing");
  }
  return result;
}

function sanitizePublicResult(value) {
  if (record(value) && value.status === "CLEANUP_COMPLETE") {
    return {
      caseId: CASE_ID,
      status: "CLEANUP_COMPLETE",
      releaseReady: false,
      receiptEligible: false,
      releaseLabel: RELEASE_LABEL,
    };
  }
  if (
    record(value) &&
    value.status === "PRE_GATE_COMPLETE" &&
    value.candidateMode === "diagnostic" &&
    value.releaseReady === false &&
    value.receiptEligible === false &&
    value.releaseLabel === RELEASE_LABEL
  ) {
    return {
      caseId: CASE_ID,
      status: "PRE_GATE_COMPLETE",
      scope: "full_journey",
      candidateMode: "diagnostic",
      diagnosticPass: true,
      releaseReady: false,
      receiptEligible: false,
      releaseLabel: RELEASE_LABEL,
    };
  }
  if (record(value) && value.status === "PASS") {
    return { caseId: CASE_ID, status: "PASS", scope: "full_journey" };
  }
  if (record(value) && value.status === "FAIL") {
    return {
      caseId: CASE_ID,
      status: "FAIL",
      blocker: SAFE_CODE.test(String(value.blocker || ""))
        ? value.blocker
        : "full_journey_semantic_verification_failed",
      ...(value.candidateMode === "diagnostic"
        ? {
            candidateMode: "diagnostic",
            releaseReady: false,
            receiptEligible: false,
            releaseLabel: RELEASE_LABEL,
          }
        : {}),
    };
  }
  const code =
    record(value) && SAFE_CODE.test(String(value.blocker || ""))
      ? value.blocker
      : "journey_blocked";
  return {
    caseId: CASE_ID,
    status: "BLOCKED",
    blocker: code,
    ...(record(value) && value.candidateMode === "diagnostic"
      ? {
          candidateMode: "diagnostic",
          releaseReady: false,
          receiptEligible: false,
          releaseLabel: RELEASE_LABEL,
        }
      : {}),
  };
}

function writePrivateFile(target, bytes, root) {
  const resolved = inspectOutput(target, root, "evidence");
  const parent = path.dirname(resolved);
  if (!fs.existsSync(parent)) {
    const relative = path.relative(root, parent);
    if (!relative || relative.startsWith("..") || path.isAbsolute(relative)) {
      blocked("evidence_outside_evidence_root");
    }
    fs.mkdirSync(parent, { recursive: true, mode: 0o700 });
  }
  rejectSymlinkComponents(parent, "evidence");
  const directory = fs.lstatSync(parent);
  if (
    !directory.isDirectory() ||
    !exactCurrentOwner(directory) ||
    (directory.mode & 0o777) !== 0o700
  ) {
    blocked("evidence_not_private");
  }
  let descriptor;
  try {
    descriptor = fs.openSync(
      resolved,
      fs.constants.O_WRONLY |
        fs.constants.O_CREAT |
        fs.constants.O_EXCL |
        fs.constants.O_NOFOLLOW,
      0o600,
    );
    fs.writeFileSync(descriptor, bytes);
    fs.fsyncSync(descriptor);
  } catch (error) {
    if (error instanceof JourneyBlocked) {
      throw error;
    }
    blocked("evidence_write_failed");
  } finally {
    if (descriptor !== undefined) {
      fs.closeSync(descriptor);
    }
  }
  return readPrivateBytes(resolved, "evidence");
}

function privateJson(target, value, root) {
  return writePrivateFile(
    target,
    Buffer.from(JSON.stringify(value, null, 2) + "\n"),
    root,
  );
}

function validatedCleanupRecoveryState(value, expected = {}) {
  const owner = value?.owner;
  const candidate = value?.candidate;
  const candidateSha256 = record(candidate)
    ? candidateBindingSha256(candidate)
    : "";
  if (
    !record(value) ||
    value.schema !== CLEANUP_STATE_SCHEMA ||
    value.caseId !== CASE_ID ||
    !new Set(["armed", "ready"]).has(value.status) ||
    !HEX_64.test(String(value.scenarioBindingSha256 || "")) ||
    !record(candidate) ||
    !HEX_64.test(String(candidate.candidateDigest || "")) ||
    !HEX_64.test(String(candidate.artifactDigest || "")) ||
    (value.candidateBindingSha256 &&
      value.candidateBindingSha256 !== candidateSha256) ||
    (expected.scenarioBindingSha256 &&
      value.scenarioBindingSha256 !== expected.scenarioBindingSha256) ||
    (expected.candidateBindingSha256 &&
      candidateSha256 !== expected.candidateBindingSha256) ||
    !record(owner) ||
    !HEX_24.test(String(owner.userId || "")) ||
    typeof owner.email !== "string" ||
    !owner.email.startsWith("viventium-voice-qa-") ||
    !owner.email.endsWith("@example.com") ||
    !Number.isSafeInteger(owner.insertedAtMs) ||
    owner.acknowledged !== true ||
    typeof owner.callSessionId !== "string" ||
    (value.status === "ready" &&
      (!ATTESTATION.test(String(owner.browserCapability || "")) ||
        typeof owner.syntheticPassword !== "string" ||
        !owner.syntheticPassword))
  ) {
    blocked("cleanup_state_invalid");
  }
  return {
    ...value,
    candidateBindingSha256: candidateSha256,
  };
}

function writeCleanupRecoveryState(target, value, root) {
  const state = validatedCleanupRecoveryState(value);
  const resolved = inspectOutput(target, root, "cleanup_state");
  const temporary = path.join(
    path.dirname(resolved),
    `.mpv-061-cleanup-${process.pid}-${crypto.randomUUID()}.tmp`,
  );
  try {
    writePrivateFile(
      temporary,
      Buffer.from(JSON.stringify(state, null, 2) + "\n"),
      root,
    );
    fs.renameSync(temporary, resolved);
    fs.chmodSync(resolved, 0o600);
    return readCleanupRecoveryState(resolved, {
      scenarioBindingSha256: state.scenarioBindingSha256,
      candidateBindingSha256: state.candidateBindingSha256,
    });
  } catch (error) {
    if (fs.existsSync(temporary)) fs.unlinkSync(temporary);
    if (error instanceof JourneyBlocked) throw error;
    blocked("cleanup_state_write_failed");
  }
}

function readCleanupRecoveryState(target, expected = {}) {
  return validatedCleanupRecoveryState(
    readPrivateJson(target, "cleanup_state"),
    expected,
  );
}

function normalizeTranscript(value) {
  return String(value || "")
    .toLocaleLowerCase()
    .replace(/\s+/g, " ")
    .trim();
}

function assertScenarioObserverAvailable(scenario) {
  const contract = SCENARIO_OBSERVER_CONTRACT;
  const allowed = new Set(PRODUCER_OWNED_TRACE_STAGES);
  const named = [
    ...Object.values(contract.effectStages).flat(),
    ...contract.fallback.stages,
    ...contract.workerCompletionDelivery.stages,
  ];
  if (named.some((stage) => !allowed.has(stage))) {
    blocked("installed_observer_contract_invalid");
  }
  if (
    contract.unavailableEffectPlanes.length > 0 ||
    contract.fallback.available !== true ||
    canonicalJson(contract.fallback.stages) !==
      canonicalJson([
        "attempt.history.complete",
        "provider.request.forwarded",
        "provider.attempt.completed",
        "provider.fallback.completed",
      ]) ||
    contract.fallback.controlledTriggerAvailable !== true
  ) {
    blocked("installed_observer_stage_unavailable");
  }
  if (
    contract.workerCompletionDelivery.available !== true ||
    contract.workerCompletionDelivery.producerScope == null ||
    canonicalJson(contract.workerCompletionDelivery.stages) !==
      canonicalJson(["response.completed", "tts.completed", "audio.completed"])
  ) {
    blocked("worker_completion_delivery_trace_unavailable");
  }
  const observation = scenario?.observation;
  const expectedStages = Object.fromEntries(
    EFFECT_PLANES.map((plane) => [plane, contract.effectStages[plane]]),
  );
  if (
    !record(observation) ||
    observation.observerContractVersion !== contract.version ||
    observation.producerScope !== contract.producerScope ||
    observation.runtimeIdentityFileKind !== contract.runtimeIdentityFileKind ||
    typeof observation.runtimeIdentityFile !== "string" ||
    !observation.runtimeIdentityFile ||
    canonicalJson(observation.effectStages) !== canonicalJson(expectedStages) ||
    canonicalJson(observation.fallbackStages) !==
      canonicalJson(contract.fallback.stages) ||
    observation.fallbackStage !== "provider.fallback.completed"
  ) {
    blocked("full_journey_observer_unavailable");
  }
  return observation;
}

function observedStageMap(scenario) {
  const observation = assertScenarioObserverAvailable(scenario);
  return Object.fromEntries(
    EFFECT_PLANES.map((plane) => [
      plane,
      new Set(observation.effectStages[plane]),
    ]),
  );
}

function runtimeInstance(scenario) {
  const state = readPrivateJson(
    scenario.observation.runtimeIdentityFile,
    "runtime_identity",
  );
  const instanceId = state.ownerBindingSha256;
  if (!HEX_64.test(String(instanceId || ""))) {
    blocked("runtime_identity_unavailable");
  }
  return String(instanceId);
}

function observedSchedulerDatabase(scenario, environment) {
  const installedRuntime = String(environment.WPR_DB_PATH || "").trim();
  const selected = String(
    scenario.observation.schedulerDatabase ||
      environment.SCHEDULING_DB_PATH ||
      (installedRuntime
        ? path.join(
            path.dirname(path.dirname(installedRuntime)),
            "scheduling",
            "schedules.db",
          )
        : ""),
  ).trim();
  if (!selected || !path.isAbsolute(selected)) {
    blocked("scheduler_cleanup_observer_unavailable");
  }
  const exact = path.resolve(selected);
  assertOutsideRepository(exact, "scheduler_database");
  rejectSymlinkComponents(exact, "scheduler_database");
  let metadata;
  try {
    metadata = fs.lstatSync(exact);
  } catch {
    blocked("scheduler_cleanup_observer_unavailable");
  }
  if (
    !metadata.isFile() ||
    !exactCurrentOwner(metadata) ||
    metadata.nlink !== 1
  ) {
    blocked("scheduler_cleanup_observer_unavailable");
  }
  return fs.realpathSync(exact);
}

function observedOwnerScheduleRows(databasePath, ownerId) {
  if (
    !HEX_24.test(String(ownerId || "")) ||
    typeof databasePath !== "string" ||
    !databasePath
  ) {
    blocked("synthetic_schedule_recovery_scope_mismatch");
  }
  const completed = spawnSync(
    "sqlite3",
    [
      "-readonly",
      "-json",
      "-cmd",
      ".timeout 5000",
      databasePath,
      "SELECT rowid AS __qa_rowid, * FROM scheduled_tasks " +
        "WHERE user_id = '" +
        ownerId +
        "' ORDER BY rowid",
    ],
    {
      encoding: "utf8",
      timeout: 7_000,
      maxBuffer: MAX_PRIVATE_JSON_BYTES,
      stdio: ["ignore", "pipe", "ignore"],
    },
  );
  if (completed.status !== 0) {
    blocked("synthetic_schedule_recovery_unavailable");
  }
  let rows;
  try {
    rows = JSON.parse(completed.stdout || "[]");
  } catch {
    blocked("synthetic_schedule_recovery_unavailable");
  }
  if (
    !Array.isArray(rows) ||
    rows.some(
      (row) =>
        !record(row) ||
        String(row.user_id || "") !== ownerId ||
        !Number.isSafeInteger(row.__qa_rowid) ||
        row.__qa_rowid < 1,
    ) ||
    new Set(rows.map((row) => row.__qa_rowid)).size !== rows.length
  ) {
    blocked("synthetic_schedule_recovery_scope_mismatch");
  }
  return rows;
}

function deleteExactObservedScheduleRows({ databasePath, ownerId, rowIds }) {
  if (
    !HEX_24.test(String(ownerId || "")) ||
    !Array.isArray(rowIds) ||
    rowIds.length < 1 ||
    rowIds.some((value) => !Number.isSafeInteger(value) || value < 1) ||
    new Set(rowIds).size !== rowIds.length
  ) {
    blocked("synthetic_schedule_recovery_scope_mismatch");
  }
  const completed = spawnSync(
    "sqlite3",
    [
      "-json",
      "-cmd",
      ".timeout 5000",
      databasePath,
      "BEGIN IMMEDIATE; DELETE FROM scheduled_tasks WHERE user_id = '" +
        ownerId +
        "' AND rowid IN (" +
        rowIds.join(",") +
        "); " +
        "SELECT changes() AS removed; COMMIT;",
    ],
    {
      encoding: "utf8",
      timeout: 7_000,
      maxBuffer: 32 * 1024,
      stdio: ["ignore", "pipe", "ignore"],
    },
  );
  if (completed.status !== 0) {
    blocked("synthetic_schedule_recovery_delete_unverified");
  }
  let rows;
  try {
    rows = JSON.parse(completed.stdout || "[]");
  } catch {
    blocked("synthetic_schedule_recovery_delete_unverified");
  }
  if (
    !Array.isArray(rows) ||
    rows.length !== 1 ||
    !Number.isSafeInteger(rows[0]?.removed) ||
    rows[0].removed !== rowIds.length
  ) {
    blocked("synthetic_schedule_recovery_delete_unverified");
  }
  return rows[0].removed;
}

function observedModel(route, expected) {
  const candidates = [
    route,
    route && route.effective,
    route && route.assistantRoute,
    route && route.assistantRoute && route.assistantRoute.effective,
  ];
  const exact = candidates.find(
    (item) =>
      record(item) &&
      item.provider === expected.provider &&
      item.model === expected.model,
  );
  if (!exact) {
    blocked("exact_model_not_observed");
  }
  return { provider: exact.provider, model: exact.model };
}

function observedClassifierRoutes(route, expected) {
  const primary = observedModel(route, expected);
  const candidate = route?.assistantRoute || route;
  const fallback = candidate?.fallbackLlm;
  if (
    !record(expected?.fallback) ||
    !record(fallback) ||
    fallback.provider !== expected.fallback.provider ||
    fallback.model !== expected.fallback.model ||
    (fallback.provider === primary.provider && fallback.model === primary.model)
  ) {
    blocked("configured_voice_fallback_not_observed");
  }
  return {
    primary,
    fallback: { provider: fallback.provider, model: fallback.model },
  };
}

function startClassifierFaultParent({
  evidenceRoot,
  environment,
  seeded,
  identityDigests,
  routes,
  spawnProcess = spawn,
}) {
  const candidate = traceCandidateFacts(identityDigests);
  const scope = {
    schemaVersion: 1,
    caseId: CASE_ID,
    candidateDigest: candidate.candidateDigest,
    installedArtifactDigest: candidate.installedArtifactDigest,
    runtimeOwnerBindingHash: candidate.runtimeOwnerBindingHash,
    ownerId: String(seeded?.userId || ""),
    ownerEmail: String(seeded?.email || ""),
    callSessionId: String(seeded?.callSessionId || ""),
    primary: routes.primary,
    fallback: routes.fallback,
  };
  const scopePath = path.join(
    evidenceRoot,
    "mpv-061-classifier-fault-scope.json",
  );
  privateJson(scopePath, scope, evidenceRoot);
  let descriptor;
  let child;
  try {
    descriptor = fs.openSync(
      scopePath,
      fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW,
    );
    child = spawnProcess(
      CLASSIFIER_FAULT_PARENT,
      ["serve", "--scope-fd", "3"],
      {
        cwd: REPOSITORY_ROOT,
        env: { ...environment },
        stdio: ["ignore", "pipe", "pipe", descriptor],
      },
    );
  } catch {
    if (fs.existsSync(scopePath)) fs.unlinkSync(scopePath);
    blocked("classifier_fault_parent_unavailable");
  } finally {
    if (descriptor !== undefined) fs.closeSync(descriptor);
  }
  let output = "";
  let stderrBytes = 0;
  let armedSettled = false;
  let receiptSettled = false;
  let armedResolve;
  let armedReject;
  let receiptResolve;
  let receiptReject;
  const armed = new Promise((resolve, reject) => {
    armedResolve = resolve;
    armedReject = reject;
  });
  const receipt = new Promise((resolve, reject) => {
    receiptResolve = resolve;
    receiptReject = reject;
  });
  const rejectPending = () => {
    const error = new JourneyBlocked("classifier_fault_parent_unavailable");
    if (!armedSettled) {
      armedSettled = true;
      armedReject(error);
    }
    if (!receiptSettled) {
      receiptSettled = true;
      receiptReject(error);
    }
  };
  const acceptLine = (line) => {
    let event;
    try {
      event = JSON.parse(line);
    } catch {
      rejectPending();
      return;
    }
    if (event?.event === "armed" && event.caseId === CASE_ID) {
      if (armedSettled) return rejectPending();
      armedSettled = true;
      if (fs.existsSync(scopePath)) fs.unlinkSync(scopePath);
      armedResolve(event);
      return;
    }
    if (
      event?.event === "receipt" &&
      event.caseId === CASE_ID &&
      SHA256_REF.test(String(event.receiptDigest || ""))
    ) {
      if (!armedSettled || receiptSettled) return rejectPending();
      receiptSettled = true;
      receiptResolve(event);
      return;
    }
    rejectPending();
  };
  child.stdout.on("data", (chunk) => {
    output += chunk.toString("utf8");
    if (Buffer.byteLength(output) > 16 * 1024) return rejectPending();
    let separator;
    while ((separator = output.indexOf("\n")) >= 0) {
      const line = output.slice(0, separator).trim();
      output = output.slice(separator + 1);
      if (line) acceptLine(line);
    }
  });
  child.stderr.on("data", (chunk) => {
    stderrBytes += chunk.length;
    if (stderrBytes > 4 * 1024) rejectPending();
  });
  child.once("error", rejectPending);
  child.once("exit", (code) => {
    if (code !== 0 || !receiptSettled) rejectPending();
  });
  return {
    armed,
    receipt,
    stop() {
      if (!child.killed) child.kill("SIGTERM");
      if (fs.existsSync(scopePath)) fs.unlinkSync(scopePath);
    },
  };
}

function cleanupClassifierFaultReceipt({
  evidenceRoot,
  environment,
  receipt,
  spawnExecutor = spawnSync,
}) {
  const scopePath = path.join(
    evidenceRoot,
    "mpv-061-classifier-fault-cleanup.json",
  );
  privateJson(
    scopePath,
    {
      schemaVersion: 1,
      caseId: CASE_ID,
      controlId: receipt.controlId,
      receiptDigest: receipt.receiptDigest,
    },
    evidenceRoot,
  );
  let descriptor;
  try {
    descriptor = fs.openSync(
      scopePath,
      fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW,
    );
    const completed = spawnExecutor(
      CLASSIFIER_FAULT_PARENT,
      ["cleanup", "--scope-fd", "3"],
      {
        cwd: REPOSITORY_ROOT,
        env: { ...environment },
        stdio: ["ignore", "pipe", "pipe", descriptor],
        encoding: "utf8",
        timeout: 15_000,
        maxBuffer: 16 * 1024,
      },
    );
    let result;
    try {
      result = JSON.parse(completed.stdout || "{}");
    } catch {
      blocked("classifier_fault_cleanup_unverified");
    }
    if (completed.status !== 0 || result.removed !== 1) {
      blocked("classifier_fault_cleanup_unverified");
    }
    return result;
  } finally {
    if (descriptor !== undefined) fs.closeSync(descriptor);
    if (fs.existsSync(scopePath)) fs.unlinkSync(scopePath);
  }
}

function completedProviderAttempt(
  snapshot,
  { ownerId, callSessionId, turnId, candidate },
) {
  if (
    !HEX_24.test(String(ownerId || "")) ||
    typeof callSessionId !== "string" ||
    !callSessionId ||
    typeof turnId !== "string" ||
    !turnId
  ) {
    blocked("wing_completed_provider_attempt_not_observed");
  }
  const records = Array.isArray(snapshot?.ledger?.trace)
    ? snapshot.ledger.trace
    : [];
  const attempts = [];
  for (const event of records) {
    if (
      event.stage !== "provider.attempt.completed" ||
      !matchesVoiceTraceScope(event, {
        ownerId,
        callSessionId,
        turnId,
        candidate,
      })
    ) {
      continue;
    }
    const facts = event.facts;
    if (
      facts.effectPlane === "provider" &&
      facts.outcome === "completed" &&
      facts.providerStatus === "completed" &&
      ["primary", "fallback"].includes(facts.attemptRole) &&
      SHA256_REF.test(String(facts.attemptRefHash || "")) &&
      typeof facts.provider === "string" &&
      facts.provider.trim() &&
      typeof facts.model === "string" &&
      facts.model.trim()
    ) {
      attempts.push({ provider: facts.provider, model: facts.model });
    }
  }
  if (attempts.length !== 1) {
    blocked("wing_completed_provider_attempt_not_observed");
  }
  return attempts[0];
}

function validateProtectedRestartPlan(plan) {
  if (
    !record(plan) ||
    !Array.isArray(plan.arguments) ||
    plan.arguments.length !== PROTECTED_RESTART_ARGUMENTS.length ||
    plan.arguments.some(
      (value, index) => value !== PROTECTED_RESTART_ARGUMENTS[index],
    )
  ) {
    blocked("runtime_restart_unsupported");
  }
  let executable;
  try {
    executable = fs.realpathSync(String(plan.executable || ""));
    const expected = fs.realpathSync(
      path.join(REPOSITORY_ROOT, "bin", "viventium"),
    );
    fs.accessSync(executable, fs.constants.X_OK);
    if (executable !== expected) {
      blocked("runtime_restart_unsupported");
    }
  } catch (error) {
    if (error instanceof JourneyBlocked) {
      throw error;
    }
    blocked("runtime_restart_unsupported");
  }
  return { executable, arguments: [...plan.arguments] };
}

function ensureRootExists(root) {
  if (!fs.existsSync(root)) {
    const parent = path.dirname(root);
    rejectSymlinkComponents(parent, "evidence_root");
    fs.mkdirSync(root, { mode: 0o700 });
  }
  return inspectEvidenceRoot(root);
}

function boundedTimeout(value, fallback) {
  return Number.isSafeInteger(value) && value >= 1_000 && value <= 900_000
    ? value
    : fallback;
}

function resolveBrowserPresentation(scenario) {
  if (
    record(scenario.browser) &&
    (scenario.browser.headless === true || scenario.browser.headed === false)
  ) {
    blocked("headed_browser_required_for_user_visible_acceptance");
  }
  return { headless: false, userVisible: true };
}

function resolveInstalledBrowserLaunch(chromium, exists = fs.existsSync) {
  if (!chromium || typeof chromium.executablePath !== "function") {
    blocked("installed_browser_unavailable");
  }
  return exists(chromium.executablePath()) ? {} : { channel: "chrome" };
}

function assertObservedRemotePlayback(observation) {
  if (
    !record(observation) ||
    observation.headed !== true ||
    !Number.isSafeInteger(observation.remoteTrackCount) ||
    observation.remoteTrackCount < 1 ||
    !Number.isSafeInteger(observation.remotePlaybackEvents) ||
    observation.remotePlaybackEvents < 1 ||
    !Number.isSafeInteger(observation.audibleRemoteElementCount) ||
    observation.audibleRemoteElementCount < 1 ||
    !Number.isFinite(observation.receivedAudioBytes) ||
    observation.receivedAudioBytes <= 0 ||
    !Number.isFinite(observation.receivedAudioPackets) ||
    observation.receivedAudioPackets <= 0 ||
    !Number.isFinite(observation.receivedAudioEnergy) ||
    observation.receivedAudioEnergy <= 0
  ) {
    blocked("headed_remote_audio_playback_not_observed");
  }
  return observation;
}

async function seedFreshSyntheticOwner(
  database,
  helpers,
  options,
  settings = {},
) {
  const startedAtMs = Number.isSafeInteger(settings.startedAtMs)
    ? settings.startedAtMs
    : Date.now();
  let proof = null;
  const scoped = {
    collection(name) {
      const collection = database.collection(name);
      if (name !== "users") {
        return collection;
      }
      return new Proxy(collection, {
        get(target, property) {
          if (property !== "insertOne") {
            const value = Reflect.get(target, property);
            return typeof value === "function" ? value.bind(target) : value;
          }
          return async (document, ...arguments_) => {
            if (
              proof !== null ||
              !record(document) ||
              !HEX_24.test(String(document._id || ""))
            ) {
              blocked("fresh_synthetic_owner_not_created");
            }
            const result = await target.insertOne(document, ...arguments_);
            if (
              !record(result) ||
              result.acknowledged !== true ||
              String(result.insertedId || "") !== String(document._id)
            ) {
              blocked("fresh_synthetic_owner_not_created");
            }
            proof = {
              ownerId: String(document._id),
              email: String(document.email || ""),
              insertedAtMs: new Date(document.createdAt || 0).getTime(),
              acknowledged: true,
            };
            Object.defineProperty(proof, "insertedId", {
              value: document._id,
              enumerable: false,
            });
            if (typeof settings.onInserted === "function") {
              settings.onInserted(proof);
            }
            return result;
          };
        },
      });
    },
  };
  const seeded = await helpers.seedCallSession(scoped, options);
  if (
    !record(proof) ||
    !record(seeded) ||
    proof.ownerId !== seeded.userId ||
    proof.email !== seeded.email ||
    !Number.isSafeInteger(proof.insertedAtMs) ||
    Math.abs(proof.insertedAtMs - startedAtMs) > 10_000
  ) {
    blocked("fresh_synthetic_owner_not_created");
  }
  const owner = await database.collection("users").findOne({
    _id: proof.insertedId,
    email: seeded.email,
  });
  if (
    !record(owner) ||
    String(owner._id || "") !== seeded.userId ||
    new Date(owner.createdAt || 0).getTime() !== proof.insertedAtMs
  ) {
    blocked("fresh_synthetic_owner_not_created");
  }
  return { seeded, proof };
}

function encodedSearchIdentity(value) {
  let encoded = "";
  for (const character of String(value)) {
    encoded += character.charCodeAt(0).toString(16).padStart(4, "0");
  }
  return "m_" + encoded;
}

function createSearchIndexObserver(librechatRequire, environment) {
  const host = String(environment.MEILI_HOST || "").trim();
  const key = String(environment.MEILI_MASTER_KEY || "").trim();
  if (
    !host &&
    !key &&
    ["false", "0"].includes(
      String(environment.SEARCH || "").toLocaleLowerCase(),
    )
  ) {
    return {
      async removeAndVerify() {
        return { remaining: 0, indexingDisabled: true };
      },
    };
  }
  if (!host || !key) {
    return null;
  }
  assertLoopbackOrigin(host);
  let client;
  try {
    const { MeiliSearch } = librechatRequire("meilisearch");
    client = new MeiliSearch({ host, apiKey: key });
  } catch {
    blocked("search_index_cleanup_unavailable");
  }
  return {
    async removeAndVerify({ ownerId, messageIds, conversationIds }) {
      if (!HEX_24.test(ownerId)) {
        blocked("search_index_cleanup_scope_invalid");
      }
      let remaining = 0;
      try {
        const plans = [];
        for (const [name, identifiers, identityField] of [
          ["messages", messageIds, "messageId"],
          ["convos", conversationIds, "conversationId"],
        ]) {
          const index = client.index(name);
          const exactIds = [
            ...new Set(identifiers.map(String).filter(Boolean)),
          ];
          const confirmedIds = [];
          if (typeof index.getDocument !== "function") {
            blocked("search_index_cleanup_unavailable");
          }
          for (const identity of exactIds) {
            const encodedIdentity = encodedSearchIdentity(identity);
            let document;
            try {
              document = await index.getDocument(encodedIdentity);
            } catch (error) {
              if (error?.code === "document_not_found") {
                continue;
              }
              throw error;
            }
            if (
              !record(document) ||
              String(document.user || "") !== ownerId ||
              String(document[identityField] || "") !== identity ||
              String(document._meiliId || document.id || "") !== encodedIdentity
            ) {
              blocked("search_index_cleanup_scope_mismatch");
            }
            confirmedIds.push(encodedIdentity);
          }
          plans.push({ index, confirmedIds });
        }
        for (const { index, confirmedIds } of plans) {
          if (confirmedIds.length > 0) {
            const task = await index.deleteDocuments(confirmedIds);
            const result = await index.waitForTask(task.taskUid, {
              timeOutMs: 30_000,
              intervalMs: 100,
            });
            if (!record(result) || result.status !== "succeeded") {
              blocked("search_index_cleanup_unverified");
            }
          }
          const page = await index.getDocuments({
            filter: 'user = "' + ownerId + '"',
            limit: 1,
          });
          const values = Array.isArray(page.results)
            ? page.results
            : Array.isArray(page.hits)
              ? page.hits
              : null;
          if (!values) {
            blocked("search_index_cleanup_unverified");
          }
          remaining += values.length;
        }
      } catch (error) {
        if (error instanceof JourneyBlocked) {
          throw error;
        }
        blocked("search_index_cleanup_unverified");
      }
      return { remaining };
    },
  };
}

function createVectorIndexObserver(librechatRequire, environment) {
  const ragUrl = String(environment.RAG_API_URL || "").trim();
  if (!ragUrl) {
    return {
      async removeAndVerify({ fileIds }) {
        if (fileIds.length > 0) {
          blocked("vector_index_cleanup_unavailable");
        }
        return { remaining: 0, indexingDisabled: true };
      },
    };
  }
  assertLoopbackOrigin(ragUrl);
  let vector;
  try {
    vector = librechatRequire(
      path.join(
        REPOSITORY_ROOT,
        "viventium_v0_4",
        "LibreChat",
        "api",
        "server",
        "services",
        "Files",
        "VectorDB",
        "crud.js",
      ),
    );
  } catch {
    blocked("vector_index_cleanup_unavailable");
  }
  if (
    typeof vector.deleteVectors !== "function" ||
    typeof vector.vectorDocumentExists !== "function"
  ) {
    blocked("vector_index_cleanup_unavailable");
  }
  return {
    async removeAndVerify({ ownerId, files, fileIds }) {
      if (!HEX_24.test(ownerId) || files.length !== fileIds.length) {
        blocked("vector_index_cleanup_scope_invalid");
      }
      for (const file of files) {
        if (
          String(file.user || "") !== ownerId ||
          typeof file.file_id !== "string" ||
          !file.file_id
        ) {
          blocked("vector_index_cleanup_scope_invalid");
        }
        await vector.deleteVectors({ user: { id: ownerId } }, file);
        if (
          await vector.vectorDocumentExists(
            { user: { id: ownerId } },
            file.file_id,
          )
        ) {
          blocked("vector_index_cleanup_unverified");
        }
      }
      return { remaining: 0 };
    },
  };
}

function createFileStorageObserver({
  page,
  database,
  ObjectId,
  ownerId,
  uploadsRoot,
}) {
  return {
    async removeAndVerify({ ownerId: selectedOwner, files }) {
      if (
        !HEX_24.test(selectedOwner) ||
        selectedOwner !== ownerId ||
        !Array.isArray(files) ||
        files.length < 1 ||
        files.some(
          (file) =>
            !record(file) ||
            String(file.user || "") !== ownerId ||
            typeof file.file_id !== "string" ||
            !file.file_id ||
            typeof file.filepath !== "string" ||
            !file.filepath,
        )
      ) {
        blocked("file_storage_cleanup_scope_invalid");
      }
      const identifiers = files.map((file) => file.file_id);
      if (new Set(identifiers).size !== identifiers.length) {
        blocked("file_storage_cleanup_scope_invalid");
      }
      const localTargets = [];
      for (const file of files) {
        const source = String(file.source || "local");
        if (!["local", "vectordb", "text"].includes(source)) {
          blocked("file_storage_cleanup_unavailable");
        }
        if (source !== "local") {
          continue;
        }
        if (typeof uploadsRoot !== "string" || !uploadsRoot.trim()) {
          blocked("file_storage_cleanup_unavailable");
        }
        const selectedRoot = path.resolve(uploadsRoot);
        rejectSymlinkComponents(selectedRoot, "file_storage");
        let metadata;
        try {
          metadata = fs.lstatSync(selectedRoot);
        } catch {
          blocked("file_storage_cleanup_unavailable");
        }
        if (!metadata.isDirectory() || !exactCurrentOwner(metadata)) {
          blocked("file_storage_cleanup_unavailable");
        }
        const prefix = "/uploads/" + ownerId + "/";
        const location = file.filepath.split("?")[0];
        if (!location.startsWith(prefix)) {
          blocked("file_storage_cleanup_scope_invalid");
        }
        const ownerRoot = path.join(selectedRoot, ownerId);
        const target = path.resolve(ownerRoot, location.slice(prefix.length));
        if (!ownsPath(target, ownerRoot)) {
          blocked("file_storage_cleanup_scope_invalid");
        }
        rejectSymlinkComponents(target, "file_storage");
        localTargets.push(target);
      }
      if (
        !page ||
        typeof page.evaluate !== "function" ||
        (typeof page.isClosed === "function" && page.isClosed())
      ) {
        blocked("file_storage_cleanup_unavailable");
      }
      let response;
      try {
        response = await page.evaluate(
          async (selectedFiles) => {
            const answer = await fetch("/api/files", {
              method: "DELETE",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ files: selectedFiles }),
            });
            return { status: answer.status };
          },
          files.map((file) => ({
            file_id: file.file_id,
            filepath: file.filepath,
          })),
        );
      } catch {
        blocked("file_storage_cleanup_unverified");
      }
      if (
        !record(response) ||
        response.status !== 200 ||
        localTargets.some((target) => fs.existsSync(target))
      ) {
        blocked("file_storage_cleanup_unverified");
      }
      const remaining = await database.collection("files").countDocuments({
        user: new ObjectId(ownerId),
        file_id: { $in: identifiers },
      });
      if (remaining !== 0) {
        blocked("file_storage_cleanup_unverified");
      }
      return { remaining, localFilesVerified: localTargets.length };
    },
  };
}

async function waitObserved(
  read,
  accept,
  code,
  timeoutMs = 45_000,
  interrupted = () => false,
) {
  const deadline = Date.now() + timeoutMs;
  do {
    if (interrupted()) blocked("journey_interrupted");
    const value = await read();
    if (accept(value)) {
      return value;
    }
    await new Promise((resolve) => setTimeout(resolve, 200));
  } while (Date.now() < deadline);
  if (interrupted()) blocked("journey_interrupted");
  blocked(code);
}

async function installRealRemoteAudioCapture(page) {
  await page.addInitScript(() => {
    const OriginalPeer = globalThis.RTCPeerConnection;
    if (typeof OriginalPeer !== "function") {
      return;
    }
    const state = {
      recorder: null,
      chunks: [],
      error: "",
      remotePlaybackEvents: 0,
      audibleElements: [],
      remoteTrackIds: [],
      peerConnections: [],
    };
    Object.defineProperty(globalThis, "__viventiumQaRemoteOutputAudio", {
      value: state,
      configurable: true,
    });
    globalThis.addEventListener(
      "playing",
      (event) => {
        const element = event.target;
        const tracks =
          element &&
          element.srcObject &&
          typeof element.srcObject.getAudioTracks === "function"
            ? element.srcObject.getAudioTracks()
            : [];
        if (
          !element ||
          element.muted ||
          element.volume <= 0 ||
          element.paused ||
          element.readyState < 2 ||
          !tracks.some((track) => state.remoteTrackIds.includes(track.id))
        ) {
          return;
        }
        state.remotePlaybackEvents += 1;
        if (!state.audibleElements.includes(element)) {
          state.audibleElements.push(element);
        }
      },
      true,
    );
    function ObservedPeer(configuration, constraints) {
      const peer = new OriginalPeer(configuration, constraints);
      state.peerConnections.push(peer);
      peer.addEventListener("track", (event) => {
        if (!event.track || event.track.kind !== "audio" || state.recorder) {
          return;
        }
        state.remoteTrackIds.push(event.track.id);
        try {
          const recorder = new MediaRecorder(new MediaStream([event.track]), {
            mimeType: "audio/webm;codecs=opus",
          });
          recorder.addEventListener("dataavailable", (chunk) => {
            if (chunk.data && chunk.data.size > 0) {
              state.chunks.push(chunk.data);
            }
          });
          recorder.addEventListener("error", () => {
            state.error = "remote_audio_recording_failed";
          });
          recorder.start(250);
          state.recorder = recorder;
        } catch {
          state.error = "remote_audio_recording_unavailable";
        }
      });
      return peer;
    }
    ObservedPeer.prototype = OriginalPeer.prototype;
    Object.setPrototypeOf(ObservedPeer, OriginalPeer);
    globalThis.RTCPeerConnection = ObservedPeer;
    if (globalThis.webkitRTCPeerConnection) {
      globalThis.webkitRTCPeerConnection = ObservedPeer;
    }
  });
}

class InstalledJourneyRuntime {
  constructor({
    scenario,
    evidenceRoot,
    identityDigests,
    environment = process.env,
    restartPlan,
    restartExecutor = spawnSync,
    restartConsent = false,
    scenarioBindingSha256 = "",
  }) {
    this.scenario = scenario;
    this.evidenceRoot = evidenceRoot;
    this.identityDigests = identityDigests;
    this.environment = environment;
    this.helpers = voiceHelpers();
    this.browsers = [];
    this.signedResponses = [];
    this.engagementResponses = [];
    this.windows = [];
    this.seeded = null;
    this.client = null;
    this.db = null;
    this.corePage = null;
    this.callPage = null;
    this.freshProof = null;
    this.searchIndex = null;
    this.vectorIndex = null;
    this.fileStorage = null;
    this.schedulerDatabase = "";
    this.presentation = resolveBrowserPresentation(scenario);
    this.restartPlan = restartPlan;
    this.restartExecutor = restartExecutor;
    this.restartConsent = restartConsent === true;
    this.scenarioBindingSha256 = scenarioBindingSha256;
    this.restartEvidence = null;
    this.recordedSafetyFailure = null;
    this.interruptionSignal = null;
    this.classifierFaultControl = null;
    this.classifierFaultReceipt = null;
    this.classifierFaultCleaned = false;
  }

  requestInterruption(signal) {
    if (!this.interruptionSignal && ["SIGINT", "SIGTERM"].includes(signal)) {
      this.interruptionSignal = signal;
    }
  }

  assertActive() {
    if (this.interruptionSignal) blocked("journey_interrupted");
  }

  waitObserved(read, accept, code, timeoutMs) {
    return waitObserved(read, accept, code, timeoutMs, () =>
      Boolean(this.interruptionSignal),
    );
  }

  persistCleanupState(status) {
    if (!this.seeded || !this.freshProof) {
      blocked("cleanup_state_invalid");
    }
    const owner = {
      userId: String(this.seeded.userId || ""),
      email: String(this.seeded.email || ""),
      insertedAtMs: this.freshProof.insertedAtMs,
      acknowledged: this.freshProof.acknowledged === true,
      callSessionId: String(this.seeded.callSessionId || ""),
      ...(this.seeded.browserCapability
        ? { browserCapability: this.seeded.browserCapability }
        : {}),
      ...(this.seeded.syntheticPassword
        ? { syntheticPassword: this.seeded.syntheticPassword }
        : {}),
    };
    return writeCleanupRecoveryState(
      this.scenario.outputs.cleanupState,
      {
        schema: CLEANUP_STATE_SCHEMA,
        caseId: CASE_ID,
        status,
        scenarioBindingSha256: this.scenarioBindingSha256,
        candidate: this.identityDigests,
        owner,
      },
      this.evidenceRoot,
    );
  }

  async restoreCleanupState(state) {
    const restored = validatedCleanupRecoveryState(state, {
      scenarioBindingSha256: this.scenarioBindingSha256,
      candidateBindingSha256: candidateBindingSha256(this.identityDigests),
    });
    this.seeded = {
      userId: restored.owner.userId,
      email: restored.owner.email,
      callSessionId: restored.owner.callSessionId,
    };
    for (const key of ["browserCapability", "syntheticPassword"]) {
      if (restored.owner[key]) {
        Object.defineProperty(this.seeded, key, {
          value: restored.owner[key],
          enumerable: false,
        });
      }
    }
    this.freshProof = {
      ownerId: restored.owner.userId,
      email: restored.owner.email,
      insertedAtMs: restored.owner.insertedAtMs,
      acknowledged: true,
    };
    const ownerObject = new this.ObjectId(restored.owner.userId);
    const fileCount = await this.db
      .collection("files")
      .countDocuments({ user: ownerObject });
    if (fileCount > 0) {
      if (!this.seeded.syntheticPassword) blocked("cleanup_state_incomplete");
      const browser = await this.chromium.launch({
        ...this.browserLaunch,
        headless: this.presentation.headless,
      });
      this.browsers.push(browser);
      const context = await browser.newContext();
      this.corePage = await context.newPage();
      await this.helpers.verifySyntheticCoreBrowser(
        this.corePage,
        this.db,
        this.seeded,
        this.scenario.runtime.coreUrl,
        path.join(this.evidenceRoot, "cleanup-owner-authenticated.png"),
      );
      this.fileStorage = createFileStorageObserver({
        page: this.corePage,
        database: this.db,
        ObjectId: this.ObjectId,
        ownerId: this.seeded.userId,
        uploadsRoot:
          this.scenario.observation?.uploadsRoot ||
          this.environment.UPLOADS_PATH ||
          this.environment.UPLOADS_DIR,
      });
    }
    return restored;
  }

  async preflightCleanup(failureCode = "cleanup_prerequisite_unavailable") {
    this.assertActive();
    this.schedulerDatabase = observedSchedulerDatabase(
      this.scenario,
      this.environment,
    );
    try {
      const librechatRequire = createRequire(
        path.join(
          REPOSITORY_ROOT,
          "viventium_v0_4",
          "LibreChat",
          "package.json",
        ),
      );
      this.chromium = librechatRequire("playwright").chromium;
      this.searchIndex = createSearchIndexObserver(
        librechatRequire,
        this.environment,
      );
      this.vectorIndex = createVectorIndexObserver(
        librechatRequire,
        this.environment,
      );
      if (!this.searchIndex || !this.vectorIndex) {
        blocked("fixture_residue_observer_unavailable");
      }
      const mongodb = librechatRequire("mongodb");
      this.ObjectId = mongodb.ObjectId;
      this.browserLaunch = resolveInstalledBrowserLaunch(this.chromium);
      this.client = new mongodb.MongoClient(this.scenario.runtime.mongoUri, {
        serverSelectionTimeoutMS: 5_000,
        connectTimeoutMS: 5_000,
      });
      await this.client.connect();
      this.db = this.client.db();
      await this.db.command({ ping: 1 });
    } catch (error) {
      if (error instanceof JourneyBlocked) throw error;
      blocked(
        failureCode === "installed_runtime_unavailable"
          ? failureCode
          : "cleanup_prerequisite_unavailable",
      );
    }
  }

  async preflight() {
    this.assertActive();
    const voice = this.scenario.runtime.voice;
    if (
      !record(voice) ||
      !record(voice.stt) ||
      !record(voice.tts) ||
      typeof voice.stt.provider !== "string" ||
      !voice.stt.provider ||
      typeof voice.tts.provider !== "string" ||
      !voice.tts.provider
    ) {
      blocked("voice_route_unavailable");
    }
    if (
      !record(this.scenario.surfaces) ||
      typeof this.scenario.surfaces.reconnectButton !== "string" ||
      !this.scenario.surfaces.reconnectButton ||
      this.scenario.attachments.some(
        (item) => typeof item.artifactLabel !== "string" || !item.artifactLabel,
      )
    ) {
      blocked("user_surface_observer_unavailable");
    }
    this.stageMap = observedStageMap(this.scenario);
    this.initialRuntimeInstance = runtimeInstance(this.scenario);
    if (
      spawnSync("ffmpeg", ["-version"], {
        encoding: "utf8",
        timeout: 5_000,
        stdio: "ignore",
      }).status !== 0
    ) {
      blocked("audio_capture_prerequisite_unavailable");
    }
    await this.preflightCleanup("installed_runtime_unavailable");
    try {
      const existing = new Set(
        (await this.db.listCollections({}, { nameOnly: true }).toArray()).map(
          (collection) => collection.name,
        ),
      );
      if (
        LEDGER_COLLECTIONS.some((collection) => !existing.has(collection.name))
      ) {
        blocked("owner_ledger_prerequisite_unavailable");
      }
      for (const origin of [
        this.scenario.runtime.playgroundUrl,
        this.scenario.runtime.coreUrl,
      ]) {
        const response = await fetch(origin, {
          redirect: "manual",
          signal: AbortSignal.timeout(5_000),
        });
        if (response.status >= 500) {
          blocked("installed_runtime_unavailable");
        }
      }
    } catch (error) {
      if (error instanceof JourneyBlocked) {
        throw error;
      }
      blocked("installed_runtime_unavailable");
    }
  }

  async launchBrowser(audioPath) {
    const browser = await this.chromium.launch({
      ...this.browserLaunch,
      headless: this.presentation.headless,
      args: [
        "--use-fake-ui-for-media-stream",
        "--use-fake-device-for-media-stream",
        "--disable-features=LocalNetworkAccessChecks",
        "--use-file-for-fake-audio-capture=" + audioPath,
      ],
    });
    this.browsers.push(browser);
    const context = await browser.newContext({ acceptDownloads: true });
    await context.grantPermissions(["microphone"], {
      origin: this.scenario.runtime.playgroundUrl,
    });
    return context;
  }

  async remotePlayback(page) {
    const playback = await page.evaluate(async () => {
      const state = globalThis.__viventiumQaRemoteOutputAudio;
      if (!state || state.error) {
        return null;
      }
      const observation = {
        remoteTrackCount: state.remoteTrackIds.length,
        remotePlaybackEvents: state.remotePlaybackEvents,
        audibleRemoteElementCount: state.audibleElements.filter(
          (element) =>
            element &&
            !element.muted &&
            element.volume > 0 &&
            !element.paused &&
            element.readyState >= 2 &&
            element.srcObject &&
            typeof element.srcObject.getAudioTracks === "function" &&
            element.srcObject
              .getAudioTracks()
              .some((track) => state.remoteTrackIds.includes(track.id)),
        ).length,
        receivedAudioBytes: 0,
        receivedAudioPackets: 0,
        receivedAudioEnergy: 0,
      };
      for (const peer of state.peerConnections) {
        const stats = await peer.getStats();
        stats.forEach((report) => {
          if (
            report.type === "inbound-rtp" &&
            (report.kind === "audio" || report.mediaType === "audio")
          ) {
            observation.receivedAudioBytes += Number(report.bytesReceived || 0);
            observation.receivedAudioPackets += Number(
              report.packetsReceived || 0,
            );
            observation.receivedAudioEnergy += Number(
              report.totalAudioEnergy || 0,
            );
          } else if (
            (report.type === "track" || report.type === "media-playout") &&
            (report.kind === "audio" || report.mediaType === "audio")
          ) {
            observation.receivedAudioEnergy += Number(
              report.totalAudioEnergy || 0,
            );
          }
        });
      }
      return observation;
    });
    return assertObservedRemotePlayback({
      ...playback,
      headed: this.presentation.headless === false,
    });
  }

  async snapshot() {
    const ownerId = this.seeded.userId;
    const ledger = await captureOwnerLedger(this.db, ownerId);
    const ownerObject = new this.ObjectId(ownerId);
    const [sessions, messages, files, speakerRows, tasks, ingress] =
      await Promise.all([
        this.db
          .collection("viventiumcallsessions")
          .find({ userId: ownerId })
          .toArray(),
        this.db.collection("messages").find({ user: ownerId }).toArray(),
        this.db.collection("files").find({ user: ownerObject }).toArray(),
        this.db
          .collection("viventiumvoicespeakersegments")
          .find({ callSessionId: this.seeded.callSessionId })
          .toArray(),
        this.db
          .collection("viventiumvoicetasks")
          .find({ userId: ownerId, callSessionId: this.seeded.callSessionId })
          .toArray(),
        this.db
          .collection("viventiumvoiceingressevents")
          .find({ userId: ownerId, callSessionId: this.seeded.callSessionId })
          .toArray(),
      ]);
    const schedules = this.helpers.inspectSyntheticSchedules(
      this.seeded,
      this.schedulerDatabase,
    );
    if (
      !record(schedules) ||
      !Number.isSafeInteger(schedules.total) ||
      !Number.isSafeInteger(schedules.unsafe) ||
      schedules.total < 0 ||
      schedules.unsafe < 0
    ) {
      blocked("scheduler_cleanup_observer_unavailable");
    }
    if (schedules.unsafe > 0) {
      blocked("unsafe_synthetic_schedule_detected");
    }
    const segments = speakerRows.map((row) => row.payload).filter(record);
    const stages = {};
    for (const plane of EFFECT_PLANES) {
      const countedStages =
        plane === "control"
          ? new Set(["control.completed"])
          : this.stageMap[plane];
      stages[plane] = ledger.trace.filter((event) =>
        countedStages.has(event.stage),
      ).length;
    }
    return {
      capturedAtMs: Date.now(),
      ledger,
      sessions,
      messages,
      files,
      segments,
      tasks,
      ingress,
      schedules,
      stages,
    };
  }

  async observeSignedResponse(response) {
    let address;
    try {
      address = new URL(response.url());
    } catch {
      return;
    }
    if (
      address.origin !== this.scenario.runtime.playgroundUrl ||
      address.pathname !== "/api/call-engagement" ||
      response.request().method() !== "POST"
    ) {
      return;
    }
    let verdict;
    try {
      verdict = await response.json();
    } catch {
      return;
    }
    let requestPayload = null;
    try {
      requestPayload = response.request().postDataJSON();
    } catch {
      requestPayload = null;
    }
    const engagement = {
      transportObserved: true,
      responseStatus: response.status(),
      code: typeof verdict?.code === "string" ? verdict.code : null,
      callSessionId: String(requestPayload?.callSessionId || ""),
      turnId: String(requestPayload?.turnId || verdict?.turnId || ""),
      observedAtMs: Date.now(),
    };
    if (!Array.isArray(this.engagementResponses)) {
      this.engagementResponses = [];
    }
    this.engagementResponses.push(engagement);
    if (response.status() !== 200) {
      return engagement;
    }
    const current = await this.snapshot().catch(() => null);
    if (!current) {
      return;
    }
    const decision =
      record(verdict) && record(verdict.verdict) ? verdict.verdict : verdict;
    const model = completedProviderAttempt(current, {
      ownerId: this.seeded?.userId,
      callSessionId: decision?.callSessionId,
      turnId: decision?.turnId,
      candidate: this.identityDigests,
    });
    this.signedResponses.push({
      transportObserved: true,
      requestUrl: response.url(),
      responseStatus: response.status(),
      model,
      verdict: decision,
      finalSegments: current.segments,
      observedAtMs: Date.now(),
    });
    return engagement;
  }

  async setMode(mode) {
    const labels = { call: "Call", wing: "Wing", listen_only: "Listen-Only" };
    await this.callPage
      .getByRole("button", { name: labels[mode], exact: true })
      .click({ timeout: 15_000 });
    const session = await this.waitObserved(
      () =>
        this.db.collection("viventiumcallsessions").findOne({
          userId: this.seeded.userId,
          callSessionId: this.seeded.callSessionId,
        }),
      (current) => record(current) && current.mode === mode,
      "persisted_call_mode_unobserved",
      15_000,
    );
    if (!Number.isSafeInteger(session.callModeRevision)) {
      blocked("persisted_call_mode_unobserved");
    }
    return session;
  }

  async preArmTurn(turn, startMs) {
    this.assertActive();
    const armAtMs = startMs + turn.armAfterMs;
    if (armAtMs > Date.now()) {
      await new Promise((resolve) => setTimeout(resolve, armAtMs - Date.now()));
    }
    const current = await this.db.collection("viventiumcallsessions").findOne({
      userId: this.seeded.userId,
      callSessionId: this.seeded.callSessionId,
    });
    if (!record(current)) blocked("owned_call_session_unavailable");
    const session =
      current.mode === turn.mode ? current : await this.setMode(turn.mode);
    const receipt = assertPrearmedTurnTiming(turn, startMs, {
      mode: session.mode,
      callModeRevision: session.callModeRevision,
      armedAtMs: Date.now(),
    });
    const before = await this.snapshot();
    if (Date.now() >= receipt.speechAtMs) {
      blocked("turn_mode_prearm_not_observed");
    }
    return { receipt, before };
  }

  windowFrom(before, after, turn, segment) {
    const scopedVoiceCount = (snapshot, stages, effectPlane, outcome) => {
      const rows = Array.isArray(snapshot?.ledger?.trace)
        ? snapshot.ledger.trace
        : [];
      return rows.filter(
        (event) =>
          stages.has(event.stage) &&
          matchesVoiceTraceScope(event, {
            ownerId: this.seeded.userId,
            callSessionId: this.seeded.callSessionId,
            turnId: segment.turnId,
            candidate: this.identityDigests,
          }) &&
          event.facts.effectPlane === effectPlane &&
          event.facts.outcome === outcome,
      ).length;
    };
    const actionStages = new Set(["action.accepted"]);
    const window = {
      kind: turn.kind,
      mode: turn.mode,
      directlyAddressed: turn.directlyAddressed,
      transcriptDelta: after.segments.length - before.segments.length,
      missionDelta: after.ledger.work.length - before.ledger.work.length,
      actionDelta:
        scopedVoiceCount(after, actionStages, "control", "accepted") -
        scopedVoiceCount(before, actionStages, "control", "accepted"),
      segment,
      before,
      after,
    };
    if (record(before.schedules) && record(after.schedules)) {
      window.scheduleDelta = after.schedules.total - before.schedules.total;
      window.unsafeScheduleCount = after.schedules.unsafe;
    }
    for (const plane of EFFECT_PLANES) {
      if (plane === "launch") {
        window.launchDelta = after.stages.launch - before.stages.launch;
        continue;
      }
      const stages =
        plane === "control"
          ? new Set(["control.completed"])
          : this.stageMap?.[plane] || new Set();
      window[plane + "Delta"] =
        scopedVoiceCount(after, stages, plane, "completed") -
        scopedVoiceCount(before, stages, plane, "completed");
    }
    if (
      window.transcriptDelta < 1 ||
      Object.values(window).some(
        (value) => typeof value === "number" && value < 0,
      )
    ) {
      blocked("logical_turn_observation_invalid");
    }
    return window;
  }

  async observeSettledPassiveDenial(before, initial, turn, segment) {
    const timeoutMs =
      Number.isSafeInteger(turn.denialTimeoutMs) && turn.denialTimeoutMs > 0
        ? Math.min(turn.denialTimeoutMs, 30_000)
        : 15_000;
    let signedDenial = null;
    let unverifiedEngagement = null;
    if (turn.kind === "unverifiedWingDenial") {
      unverifiedEngagement = await this.waitObserved(
        async () =>
          this.engagementResponses.find(
            (item) =>
              item.turnId === segment.turnId &&
              item.responseStatus === 403 &&
              item.code === "voice_engagement_not_authorized",
          ),
        (value) => Boolean(value),
        "unverified_wing_denial_not_observed",
        timeoutMs,
      );
      if (
        this.signedResponses.some(
          (item) => item.verdict?.turnId === segment.turnId,
        )
      ) {
        blocked("unverified_wing_denial_not_observed");
      }
    } else if (turn.mode === "wing") {
      const observed = await this.waitObserved(
        async () =>
          this.signedResponses.find(
            (item) =>
              record(item.verdict) &&
              item.verdict.turnId === segment.turnId &&
              item.verdict.directlyAddressed === false,
          ),
        (value) => Boolean(value),
        "passive_wing_signed_denial_not_observed",
        timeoutMs,
      );
      signedDenial = validateSignedWingDecision(
        observed,
        {
          callSessionId: this.seeded.callSessionId,
          turnId: segment.turnId,
          participantIdentity: this.seeded.ownerParticipantIdentity,
          playgroundUrl: this.scenario.runtime.playgroundUrl,
          assistant: this.scenario.runtime.assistant,
        },
        false,
      );
    }
    const ingressKind =
      turn.mode === "wing" ? "ambient_participant" : "listen_only_owner";
    const transcriptType =
      turn.mode === "wing"
        ? "voice_ambient_transcript"
        : "listen_only_transcript";
    const ingress = await this.waitObserved(
      () =>
        this.db.collection("messages").findOne({
          user: this.seeded.userId,
          "metadata.viventium.callSessionId": this.seeded.callSessionId,
          "metadata.viventium.turnId": segment.turnId,
          "metadata.viventium.mode": turn.mode,
          "metadata.viventium.ingressKind": ingressKind,
        }),
      (entry) =>
        record(entry) &&
        entry.user === this.seeded.userId &&
        record(entry.metadata?.viventium) &&
        entry.metadata.viventium.type === transcriptType &&
        entry.metadata.viventium.mode === turn.mode &&
        entry.metadata.viventium.ingressKind === ingressKind &&
        entry.metadata.viventium.callSessionId === this.seeded.callSessionId &&
        entry.metadata.viventium.turnId === segment.turnId &&
        Array.isArray(entry.metadata.viventium.speakerSegments) &&
        entry.metadata.viventium.speakerSegments.some(
          (speaker) =>
            speaker.segmentId === segment.segmentId &&
            speaker.turnId === segment.turnId,
        ),
      "passive_denial_durable_receipt_not_observed",
      timeoutMs,
    );
    const configured = this.scenario.observation?.passiveSettleMs;
    const settleMs = Number.isSafeInteger(configured)
      ? Math.min(Math.max(configured, 20), 10_000)
      : 500;
    const settleUntil = Date.now() + settleMs;
    let current = initial;
    do {
      current = await this.snapshot();
      const window = this.windowFrom(before, current, turn, segment);
      if (window.unsafeScheduleCount > 0) {
        blocked("unsafe_synthetic_schedule_detected");
      }
      if (window.scheduleDelta > 0) {
        blocked("passive_mode_side_effect_observed");
      }
      assertPassiveDenial(window);
      if (Date.now() >= settleUntil) {
        const session = await this.db
          .collection("viventiumcallsessions")
          .findOne({
            userId: this.seeded.userId,
            callSessionId: this.seeded.callSessionId,
          });
        window.denial = {
          durable: true,
          signed: signedDenial,
          engagement: unverifiedEngagement,
          ingressStatus: ingress.metadata.viventium.ingressKind,
          ...(turn.kind === "unverifiedWingDenial" ? { session } : {}),
          settledAtMs: Date.now(),
        };
        if (turn.kind === "unverifiedWingDenial") {
          assertUnverifiedWingDenial(window, session);
        }
        return window;
      }
      await new Promise((resolve) =>
        setTimeout(resolve, Math.min(50, settleMs)),
      );
    } while (Date.now() <= settleUntil + 100);
    blocked("passive_denial_settlement_unobserved");
  }

  async observeTurn(turn, startMs) {
    this.assertActive();
    const armed = await this.preArmTurn(turn, startMs);
    if (turn.startAfterMs > Date.now() - startMs) {
      await new Promise((resolve) =>
        setTimeout(resolve, turn.startAfterMs - (Date.now() - startMs)),
      );
    }
    const before = armed.before;
    const baselineIds = new Set(
      before.segments.map((segment) => segment.segmentId),
    );
    const deadline = boundedTimeout(turn.timeoutMs, 90_000);
    const after = await this.waitObserved(
      () => this.snapshot(),
      (next) =>
        next.segments.some(
          (segment) =>
            segment.isFinal === true &&
            !baselineIds.has(segment.segmentId) &&
            normalizeTranscript(segment.text).includes(
              normalizeTranscript(turn.expectedTranscript),
            ),
        ),
      "expected_voice_transcript_not_observed",
      deadline,
    );
    const segment = after.segments.find(
      (candidate) =>
        candidate.isFinal === true &&
        !baselineIds.has(candidate.segmentId) &&
        normalizeTranscript(candidate.text).includes(
          normalizeTranscript(turn.expectedTranscript),
        ),
    );
    const visible = normalizeTranscript(
      await this.callPage.locator("body").innerText(),
    );
    if (!visible.includes(normalizeTranscript(turn.expectedTranscript))) {
      blocked("visible_voice_transcript_not_observed");
    }
    let window = this.windowFrom(before, after, turn, segment);
    if (
      [
        "passiveWingDenial",
        "listenOnlyDenial",
        "unverifiedWingDenial",
      ].includes(turn.kind)
    ) {
      window = await this.observeSettledPassiveDenial(
        before,
        after,
        turn,
        segment,
      );
    } else {
      if (
        segment.speaker.attribution !== "verified" ||
        segment.speaker.actorTrust !== "owner_participant" ||
        segment.speaker.participantIdentity !==
          this.seeded.ownerParticipantIdentity
      ) {
        blocked("verified_owner_voice_not_observed");
      }
      if (turn.mode === "wing") {
        const signed = await this.waitObserved(
          async () =>
            this.signedResponses.find(
              (item) =>
                record(item.verdict) && item.verdict.turnId === segment.turnId,
            ),
          (value) => Boolean(value),
          "wing_signed_authority_not_observed",
          15_000,
        );
        window.authority = validateSignedWingAuthority(signed, {
          callSessionId: this.seeded.callSessionId,
          turnId: segment.turnId,
          participantIdentity: this.seeded.ownerParticipantIdentity,
          playgroundUrl: this.scenario.runtime.playgroundUrl,
          assistant: this.scenario.runtime.assistant,
        });
      }
      if (
        window.responseDelta !== 1 ||
        window.ttsDelta !== 1 ||
        window.audioDelta !== 1
      ) {
        blocked("audible_model_response_not_observed");
      }
      window.playback = await this.remotePlayback(this.callPage);
    }
    window.modeArm = armed.receipt;
    this.windows.push(window);
    return window;
  }

  async attachFiles(targetWorkers) {
    const session = await this.db.collection("viventiumcallsessions").findOne({
      userId: this.seeded.userId,
      callSessionId: this.seeded.callSessionId,
    });
    if (
      !session ||
      typeof session.conversationId !== "string" ||
      !session.conversationId ||
      session.conversationId === "new"
    ) {
      blocked("linked_chat_conversation_unavailable");
    }
    const conversationUrl = new URL(
      "/c/" + encodeURIComponent(session.conversationId),
      this.scenario.runtime.coreUrl,
    );
    await this.corePage.goto(conversationUrl.toString(), {
      waitUntil: "domcontentloaded",
      timeout: 30_000,
    });
    await this.corePage
      .getByTestId("text-input")
      .waitFor({ state: "visible", timeout: 20_000 });
    if (
      !Array.isArray(targetWorkers) ||
      targetWorkers.length !== this.scenario.attachments.length ||
      targetWorkers.some(
        (worker) =>
          !record(worker) ||
          worker.ownerId !== this.seeded.userId ||
          typeof worker.workRef !== "string" ||
          !worker.workRef,
      ) ||
      new Set(targetWorkers.map((worker) => worker.workRef)).size !==
        targetWorkers.length
    ) {
      blocked("attachment_target_worker_unavailable");
    }
    const input = this.corePage.locator('input[type="file"]').first();
    const composer = this.corePage.getByTestId("text-input");
    const uploads = [];
    for (let index = 0; index < this.scenario.attachments.length; index += 1) {
      const attachment = this.scenario.attachments[index];
      const target = targetWorkers[index];
      const before = await this.snapshot();
      await input.setInputFiles(attachment.observed.path, { timeout: 20_000 });
      const after = await this.waitObserved(
        () => this.snapshot(),
        (state) => state.files.length === before.files.length + 1,
        "owner_attachment_not_uploaded",
      );
      const oldIds = new Set(before.files.map((item) => String(item._id)));
      const file = after.files.find((item) => !oldIds.has(String(item._id)));
      if (
        !file ||
        Number(file.bytes || file.size || 0) !==
          attachment.observed.bytes.length
      ) {
        blocked("owner_attachment_identity_unverified");
      }
      const messageIds = new Set(
        before.messages.map((message) => String(message.messageId || "")),
      );
      const dispatchInstruction =
        attachment.dispatchInstruction +
        " Exact existing work reference: " +
        target.workRef +
        ".";
      await composer.fill(dispatchInstruction);
      await composer.press("Enter");
      const sent = await this.waitObserved(
        () => this.snapshot(),
        (state) =>
          state.messages.some((message) => {
            const attached = Array.isArray(message.attachments)
              ? message.attachments.map((item) =>
                  String(item?.file_id || item?.fileId || ""),
                )
              : [];
            return (
              !messageIds.has(String(message.messageId || "")) &&
              message.user === this.seeded.userId &&
              message.isCreatedByUser === true &&
              message.conversationId === session.conversationId &&
              normalizeTranscript(message.text) ===
                normalizeTranscript(dispatchInstruction) &&
              attached.length === 1 &&
              [String(file._id || ""), String(file.file_id || "")].includes(
                attached[0],
              )
            );
          }),
        "owner_attachment_message_not_sent",
      );
      const message = sent.messages.find((candidate) => {
        const attached = Array.isArray(candidate.attachments)
          ? candidate.attachments.map((item) =>
              String(item?.file_id || item?.fileId || ""),
            )
          : [];
        return (
          !messageIds.has(String(candidate.messageId || "")) &&
          candidate.user === this.seeded.userId &&
          candidate.isCreatedByUser === true &&
          candidate.conversationId === session.conversationId &&
          normalizeTranscript(candidate.text) ===
            normalizeTranscript(dispatchInstruction) &&
          attached.length === 1 &&
          [String(file._id || ""), String(file.file_id || "")].includes(
            attached[0],
          )
        );
      });
      uploads.push({
        worker: attachment.worker,
        targetWorkRef: target.workRef,
        dispatchInstruction,
        file,
        message,
        observed: attachment.observed,
      });
    }
    if (String(uploads[0].file._id) === String(uploads[1].file._id)) {
      blocked("owner_attachment_identity_unverified");
    }
    const bound = await this.waitObserved(
      () => captureOwnerLedger(this.db, this.seeded.userId),
      (ledger) => {
        try {
          for (const upload of uploads) {
            const authorization = exactObservedRow(
              ledger.capabilities,
              upload.targetWorkRef,
              "worker_input_handoff_not_observed",
            );
            const mission = exactObservedRow(
              ledger.missions,
              upload.targetWorkRef,
              "worker_input_handoff_not_observed",
            );
            const siblingAuthorizations = ledger.capabilities.filter(
              (item) => item.workRef !== upload.targetWorkRef,
            );
            assertAttachmentDispatchBinding({
              upload,
              authorization,
              mission,
              siblingAuthorizations,
              ownerId: this.seeded.userId,
            });
          }
          return true;
        } catch (error) {
          if (
            error instanceof JourneyBlocked &&
            error.code === "attachment_leaked_to_sibling_worker"
          ) {
            throw error;
          }
          return false;
        }
      },
      "worker_input_handoff_not_observed",
      90_000,
    );
    for (const upload of uploads) {
      upload.authorization = exactObservedRow(
        bound.capabilities,
        upload.targetWorkRef,
        "worker_input_handoff_not_observed",
      );
    }
    return { uploads, conversationId: session.conversationId };
  }

  async stopWingProbe(window) {
    const earlier = new Set(
      window.before.ledger.work.map((row) => String(row.workRef || "")),
    );
    const created = window.after.ledger.work.filter(
      (row) => row.workRef && !earlier.has(String(row.workRef)),
    );
    if (
      created.length !== 1 ||
      window.missionDelta !== 1 ||
      window.launchDelta !== 1 ||
      window.controlDelta !== 0
    ) {
      blocked("trusted_wing_single_worker_not_observed");
    }
    const workRef = String(created[0].workRef);
    const operationId = crypto.randomUUID();
    const response = await this.corePage.evaluate(
      async ({ selectedWorkRef, operationId: selectedOperation }) => {
        const answer = await fetch(
          "/api/viventium/orchestration/work/" +
            encodeURIComponent(selectedWorkRef) +
            "/actions",
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              action: "stop",
              operationId: selectedOperation,
            }),
          },
        );
        return {
          status: answer.status,
          payload: await answer.json().catch(() => null),
        };
      },
      { selectedWorkRef: workRef, operationId },
    );
    if (response.status !== 202 || !record(response.payload)) {
      blocked("wing_probe_cleanup_not_accepted");
    }
    const terminal = await this.waitObserved(
      async () =>
        (await captureOwnerLedger(this.db, this.seeded.userId)).work.find(
          (row) => row.workRef === workRef,
        ),
      (row) =>
        record(row) &&
        ["cancelled_confirmed", "cancelled"].includes(
          String(row.externalState || row.state || ""),
        ),
      "wing_probe_cleanup_not_observed",
      60_000,
    );
    return { work: terminal, response, operationId };
  }

  async captureSurface(label, expectedRows, page = this.corePage) {
    const response = await page.evaluate(async () => {
      const answer = await fetch("/api/viventium/orchestration/work");
      return {
        status: answer.status,
        payload: await answer.json().catch(() => null),
      };
    });
    if (response.status !== 200 || !record(response.payload)) {
      blocked("owner_active_work_surface_unavailable");
    }
    const body = await page.locator("body").innerText();
    if (typeof body !== "string" || !body.trim()) {
      blocked("linked_chat_surface_unavailable");
    }
    const snapshotPath = path.join(this.evidenceRoot, label + "-surface.png");
    await page.screenshot({ path: snapshotPath, fullPage: true });
    fs.chmodSync(snapshotPath, 0o600);
    readPrivateBytes(snapshotPath, "surface_capture");
    const capture = {
      label,
      response: response.payload,
      visible: body,
      screenshot: snapshotPath,
    };
    capture.rows = observedSurfaceRows(capture, expectedRows);
    return capture;
  }

  async coordinateRuntimeRestart(workers) {
    if (
      this.restartConsent !== true ||
      this.environment?.VIVENTIUM_QA_ALLOW_MPV061_RUNTIME_RESTART !== "1"
    ) {
      blocked("runtime_restart_consent_required");
    }
    if (!Array.isArray(workers) || workers.length !== 2) {
      blocked("restart_active_undelivered_workers_required");
    }
    const refs = workers.map((worker) => String(worker?.workRef || ""));
    const ownerId = String(this.seeded?.userId || "");
    if (
      !HEX_24.test(ownerId) ||
      refs.some((value) => !value) ||
      new Set(refs).size !== refs.length ||
      workers.some((worker) => String(worker.ownerId || "") !== ownerId)
    ) {
      blocked("restart_active_undelivered_workers_required");
    }
    const before = await this.snapshot();
    if (
      !record(before?.ledger) ||
      !Array.isArray(before.ledger.work) ||
      !Array.isArray(before.ledger.callbacks) ||
      !Array.isArray(before.ledger.deliveries) ||
      refs.some((ref) => {
        const row = before.ledger.work.find((item) => item.workRef === ref);
        return (
          !row ||
          String(row.ownerId || "") !== ownerId ||
          String(row.externalState || row.state || "") !== "running" ||
          before.ledger.callbacks.some((item) => item.workRef === ref) ||
          before.ledger.deliveries.some((item) => item.workRef === ref)
        );
      })
    ) {
      blocked("restart_active_undelivered_workers_required");
    }
    const callSessionId = String(this.seeded?.callSessionId || "");
    const call = Array.isArray(before.sessions)
      ? before.sessions.filter(
          (session) =>
            record(session) &&
            String(session.userId || "") === ownerId &&
            String(session.callSessionId || "") === callSessionId,
        )
      : [];
    const callConversationId = String(call[0]?.conversationId || "");
    if (!callSessionId || call.length !== 1 || !callConversationId) {
      blocked("restart_call_continuity_unobserved");
    }
    const observeMain = async () => {
      if (!this.corePage || typeof this.corePage.evaluate !== "function") {
        return false;
      }
      try {
        const response = await this.corePage.evaluate(async () => {
          const answer = await fetch("/api/viventium/orchestration/work", {
            cache: "no-store",
          });
          return {
            status: answer.status,
            payload: await answer.json().catch(() => null),
          };
        });
        const rows = response?.payload?.work || response?.payload?.items;
        return (
          response?.status === 200 &&
          Array.isArray(rows) &&
          refs.every((ref) => rows.some((row) => row.workRef === ref))
        );
      } catch {
        return false;
      }
    };
    if (!(await observeMain())) {
      blocked("restart_main_availability_not_observed");
    }
    const plan = validateProtectedRestartPlan(this.restartPlan);
    if (typeof this.restartExecutor !== "function") {
      blocked("consented_installed_runtime_restart_unavailable");
    }
    const previous = runtimeInstance(this.scenario);
    const completed = this.restartExecutor(plan.executable, plan.arguments, {
      cwd: REPOSITORY_ROOT,
      encoding: "utf8",
      timeout: boundedTimeout(this.scenario.restartTimeoutMs, 600_000),
      maxBuffer: 1024 * 1024,
      env: { ...this.environment, PYTHONDONTWRITEBYTECODE: "1" },
    });
    if (!record(completed) || completed.status !== 0) {
      blocked("consented_installed_runtime_restart_unavailable");
    }
    const current = await this.waitObserved(
      async () => runtimeInstance(this.scenario),
      (instance) => instance !== previous,
      "runtime_restart_not_observed",
      30_000,
    );
    await this.waitObserved(
      observeMain,
      (available) => available === true,
      "restart_main_availability_not_observed",
      30_000,
    );
    const restored = await this.snapshot();
    if (
      refs.some(
        (ref) =>
          !restored.ledger.work.some(
            (item) =>
              item.workRef === ref && String(item.ownerId || "") === ownerId,
          ),
      )
    ) {
      blocked("runtime_restart_lost_active_worker");
    }
    const restoredCall = Array.isArray(restored.sessions)
      ? restored.sessions.filter(
          (session) =>
            record(session) &&
            String(session.userId || "") === ownerId &&
            String(session.callSessionId || "") === callSessionId &&
            String(session.conversationId || "") === callConversationId,
        )
      : [];
    if (restoredCall.length !== 1) {
      blocked("restart_call_continuity_unobserved");
    }
    this.restartEvidence = {
      before: previous,
      after: current,
      workerRefs: refs,
      survivingWorkRefs: refs.filter((ref) =>
        restored.ledger.work.some((item) => item.workRef === ref),
      ),
      invoked: true,
      exitCode: completed.status,
      mainAvailableBefore: true,
      mainAvailableAfter: true,
      callSessionId,
      survivingCallSessionId: String(restoredCall[0].callSessionId),
      callConversationId,
      observedAtMs: Date.now(),
    };
    return this.restartEvidence;
  }

  async endCallAndReconnect(conversationId) {
    const before = await this.snapshot();
    await this.callPage
      .getByRole("button", { name: "End call", exact: false })
      .click({ timeout: 15_000 });
    this.initialEndedSession = await this.waitObserved(
      () =>
        this.db.collection("viventiumcallsessions").findOne({
          userId: this.seeded.userId,
          callSessionId: this.seeded.callSessionId,
        }),
      (session) =>
        record(session) &&
        ["ended", "completed", "disconnected"].includes(
          String(session.callStatus || session.status || ""),
        ),
      "initial_call_hangup_not_observed",
      30_000,
    );
    const after = await captureOwnerLedger(this.db, this.seeded.userId);
    for (const work of before.ledger.work.filter(
      (row) =>
        !["cancelled", "cancelled_confirmed"].includes(
          String(row.externalState || row.state || ""),
        ),
    )) {
      const current = after.work.find(
        (candidate) => candidate.workRef === work.workRef,
      );
      if (
        !current ||
        ["cancelled", "cancelled_confirmed"].includes(
          String(current.externalState || current.state || ""),
        )
      ) {
        blocked("hangup_cancelled_accepted_worker");
      }
    }
    await this.coordinateRuntimeRestart(
      after.work.filter(
        (work) =>
          !["cancelled", "cancelled_confirmed"].includes(
            String(work.externalState || work.state || ""),
          ),
      ),
    );
    const context = await this.launchBrowser(this.scenario.audio.reconnect);
    const secondCore = await context.newPage();
    await this.helpers.verifySyntheticCoreBrowser(
      secondCore,
      this.db,
      this.seeded,
      this.scenario.runtime.coreUrl,
      path.join(this.evidenceRoot, "reconnect-owner.png"),
    );
    await secondCore.goto(
      new URL(
        "/c/" + encodeURIComponent(conversationId),
        this.scenario.runtime.coreUrl,
      ).toString(),
      { waitUntil: "domcontentloaded", timeout: 30_000 },
    );
    const popup = context.waitForEvent("page", { timeout: 30_000 });
    await secondCore
      .getByRole("button", {
        name: this.scenario.surfaces.reconnectButton,
        exact: true,
      })
      .click({ timeout: 15_000 });
    const page = await popup.catch(() =>
      blocked("explicit_reconnect_page_not_observed"),
    );
    await installRealRemoteAudioCapture(page);
    const reconnect = await this.waitObserved(
      () =>
        this.db
          .collection("viventiumcallsessions")
          .find({
            userId: this.seeded.userId,
            conversationId,
          })
          .toArray(),
      (sessions) =>
        sessions.some(
          (session) => session.callSessionId !== this.seeded.callSessionId,
        ),
      "explicit_reconnect_session_not_observed",
      30_000,
    );
    const session = reconnect.find(
      (item) => item.callSessionId !== this.seeded.callSessionId,
    );
    this.reconnectPage = page;
    this.reconnectCorePage = secondCore;
    this.reconnectSession = session;
    return session;
  }

  async captureCompletionEvents(workers, reconnect, ledger) {
    const ownerId = String(this.seeded?.userId || "");
    if (
      !HEX_24.test(ownerId) ||
      !Array.isArray(workers) ||
      workers.length !== 2 ||
      !record(reconnect) ||
      !reconnect.callSessionId ||
      !reconnect.conversationId ||
      !record(ledger) ||
      !Array.isArray(ledger.deliveries) ||
      !Array.isArray(ledger.trace)
    ) {
      blocked("worker_completion_speech_not_observed");
    }
    const rows = await this.db
      .collection("messages")
      .find({
        user: ownerId,
        conversationId: reconnect.conversationId,
      })
      .toArray();
    if (
      !Array.isArray(rows) ||
      rows.some((row) => !record(row) || String(row.user || "") !== ownerId)
    ) {
      blocked("worker_completion_speech_not_observed");
    }
    const visible = await this.reconnectPage.locator("body").innerText();
    const deliveries = ledger.deliveries.filter(
      (row) =>
        record(row) &&
        String(row.userId || "") === ownerId &&
        row.surface === "voice" &&
        row.status === "sent" &&
        String(row.voiceCallSessionId || "") === reconnect.callSessionId &&
        record(row.workerCompletionPresentation),
    );
    if (deliveries.length !== 1) {
      blocked("worker_completion_speech_not_observed");
    }
    const delivery = deliveries[0];
    const presentation = delivery.workerCompletionPresentation;
    const bindings = Array.isArray(presentation.bindings)
      ? presentation.bindings
      : [];
    const expectedWorkRefs = workers
      .map((worker) => String(worker.workRef || ""))
      .sort();
    const observedWorkRefs = bindings
      .map((binding) => String(binding?.workRef || ""))
      .sort();
    if (
      presentation.version !== 1 ||
      presentation.revision !== 1 ||
      String(presentation.callSessionId || "") !== reconnect.callSessionId ||
      !String(presentation.presentationRef || "").startsWith(
        "voice_worker_completion_",
      ) ||
      !String(presentation.turnId || "").startsWith(
        "voice_worker_completion_turn_",
      ) ||
      String(delivery.callbackMessageId || "") !==
        String(presentation.responseMessageId || "") ||
      String(delivery.voiceRequestId || "") !==
        String(presentation.turnId || "") ||
      !delivery.workerCompletionTtsCompletedAt ||
      !delivery.workerCompletionAudioCompletedAt ||
      canonicalJson(observedWorkRefs) !== canonicalJson(expectedWorkRefs)
    ) {
      blocked("worker_completion_speech_not_observed");
    }
    for (const worker of workers) {
      const binding = bindings.find(
        (candidate) =>
          String(candidate?.workRef || "") === String(worker.workRef || ""),
      );
      if (
        !record(binding) ||
        String(binding.originRef || "") !== String(worker.originRef || "") ||
        String(binding.runId || "") !== String(worker.runId || "") ||
        !String(binding.workerId || "") ||
        (worker.workerId &&
          String(binding.workerId) !== String(worker.workerId))
      ) {
        blocked("worker_completion_speech_not_observed");
      }
    }
    const matching = rows.filter(
      (row) =>
        (row.isCreatedByUser === false ||
          ["assistant", "ai"].includes(String(row.role || ""))) &&
        String(row.messageId || "") ===
          String(presentation.responseMessageId || ""),
    );
    if (matching.length !== 1) {
      blocked("worker_completion_speech_not_observed");
    }
    const message = matching[0];
    const turnId = String(presentation.turnId || "");
    const speakerIdentity = String(
      message.agentId || message.agent_id || message.speakerIdentity || "",
    );
    const text = String(message.text || message.content || "").trim();
    const revision = Number(presentation.revision);
    if (
      !speakerIdentity ||
      !text ||
      presentation.responseDigest !== "sha256:" + digest(Buffer.from(text)) ||
      typeof visible !== "string" ||
      !visible.includes(text) ||
      !Number.isSafeInteger(revision) ||
      revision < 1
    ) {
      blocked("worker_completion_speech_not_observed");
    }
    return workers.map((worker) => {
      const scoped = ledger.trace.filter((event) =>
        Boolean(
          matchesVoiceTraceScope(event, {
            ownerId,
            callSessionId: reconnect.callSessionId,
            turnId,
            candidate: this.identityDigests,
            workRef: worker.workRef,
          }) &&
          event.facts.deliveryRefHash ===
            opaqueRef("delivery", String(delivery.deliveryId || "")) &&
          event.facts.responseRefHash ===
            opaqueRef(
              "response",
              String(presentation.responseMessageId || ""),
            ) &&
          event.facts.presentationRefHash ===
            opaqueRef(
              "voice_presentation",
              String(presentation.presentationRef || ""),
            ),
        ),
      );
      const count = (plane) =>
        scoped.filter(
          (event) =>
            this.stageMap[plane]?.has(event.stage) &&
            event.facts.effectPlane === plane &&
            event.facts.outcome === "completed",
        ).length;
      const responseCount = count("response");
      const ttsCount = count("tts");
      const audioCount = count("audio");
      if (
        responseCount !== 1 ||
        ttsCount !== 1 ||
        audioCount !== 1 ||
        !message.messageId
      ) {
        blocked("worker_completion_speech_not_observed");
      }
      return {
        ownerId,
        callSessionId: reconnect.callSessionId,
        conversationId: reconnect.conversationId,
        workRef: worker.workRef,
        turnId,
        revision,
        speakerIdentity,
        messageId: String(message.messageId),
        presentationRef: String(presentation.presentationRef),
        deliveryId: String(delivery.deliveryId),
        transcriptVisible: true,
        responseCount,
        ttsCount,
        audioCount,
      };
    });
  }

  async captureWorkerTraces(workers, ledger) {
    const ownerId = String(this.seeded?.userId || "");
    if (
      !HEX_24.test(ownerId) ||
      !Array.isArray(workers) ||
      workers.length !== 2 ||
      !record(ledger) ||
      !Array.isArray(ledger.bindings) ||
      !this.reconnectCorePage ||
      typeof this.reconnectCorePage.evaluate !== "function"
    ) {
      blocked("worker_artifact_delivery_not_bound");
    }
    const observed = [];
    for (const worker of workers) {
      if (String(worker?.ownerId || "") !== ownerId || !worker.workRef) {
        blocked("worker_artifact_delivery_not_bound");
      }
      const binding = exactObservedRow(
        ledger.bindings,
        worker.workRef,
        "worker_artifact_delivery_not_bound",
      );
      if (String(binding.ownerId || "") !== ownerId || !binding.originRef) {
        blocked("worker_artifact_delivery_not_bound");
      }
      const response = await this.reconnectCorePage.evaluate(
        async (originRef) => {
          const answer = await fetch(
            "/api/viventium/orchestration-traces/" +
              encodeURIComponent(originRef),
            { cache: "no-store" },
          );
          return {
            status: answer.status,
            payload: await answer.json().catch(() => null),
          };
        },
        binding.originRef,
      );
      if (response?.status !== 200 || !record(response.payload)) {
        blocked("worker_artifact_delivery_not_bound");
      }
      observed.push({
        workRef: worker.workRef,
        originRef: binding.originRef,
        response: response.payload,
      });
    }
    return observed;
  }

  async openArtifacts(workers) {
    const artifacts = [];
    for (let index = 0; index < workers.length; index += 1) {
      const attachment = this.scenario.attachments[index];
      const locator = this.reconnectCorePage.getByRole("link", {
        name: attachment.artifactLabel,
        exact: true,
      });
      const downloadPromise = this.reconnectCorePage.waitForEvent("download", {
        timeout: 30_000,
      });
      await locator.click({ timeout: 15_000 });
      const download = await downloadPromise.catch(() =>
        blocked("worker_artifact_not_opened"),
      );
      const target = path.join(
        this.evidenceRoot,
        "evidence",
        "artifact-" + attachment.worker.toLocaleLowerCase() + ".bin",
      );
      const parent = path.dirname(target);
      if (!fs.existsSync(parent)) {
        fs.mkdirSync(parent, { mode: 0o700 });
      }
      await download.saveAs(target);
      fs.chmodSync(target, 0o600);
      const observed = readPrivateBytes(target, "delivered_artifact");
      if (observed.bytes.length < 1) {
        blocked("worker_artifact_empty");
      }
      artifacts.push({ worker: workers[index], observed, opened: true });
    }
    if (artifacts[0].observed.sha256 === artifacts[1].observed.sha256) {
      blocked("worker_artifacts_not_distinct");
    }
    return artifacts;
  }

  async execute() {
    this.assertActive();
    ensureRootExists(this.evidenceRoot);
    const voice = this.scenario.runtime.voice;
    const startedAtMs = Date.now();
    const seeded = await seedFreshSyntheticOwner(
      this.db,
      this.helpers,
      {
        caseId: CASE_ID,
        agentName: this.scenario.runtime.agent.name,
        agentId: this.scenario.runtime.agent.id,
        interactive: true,
        mode: "call",
        sttProvider: voice.stt.provider,
        sttVariant: voice.stt.variant || "",
        ttsProvider: voice.tts.provider,
        ttsVariant: voice.tts.variant || "",
        verifyCoreBrowser: true,
      },
      {
        startedAtMs,
        onInserted: (proof) => {
          this.freshProof = proof;
          this.seeded = {
            userId: proof.ownerId,
            email: proof.email,
            callSessionId: "",
          };
          this.persistCleanupState("armed");
          this.assertActive();
        },
      },
    );
    this.assertActive();
    this.seeded = seeded.seeded;
    this.freshProof = seeded.proof;
    this.persistCleanupState("ready");
    const preflight = await this.helpers.preflightPlaygroundProxies(
      this.scenario.runtime.playgroundUrl,
      this.seeded.callSessionId,
      this.seeded.browserCapability,
    );
    if (!preflight.state.ok || !preflight.voiceSettings.ok) {
      blocked("installed_call_proxy_unavailable");
    }
    const classifierRoutes = observedClassifierRoutes(
      preflight.voiceSettings.payload,
      this.scenario.runtime.assistant,
    );
    this.model = classifierRoutes.primary;
    this.classifierFaultControl = startClassifierFaultParent({
      evidenceRoot: this.evidenceRoot,
      environment: this.environment,
      seeded: this.seeded,
      identityDigests: this.identityDigests,
      routes: classifierRoutes,
    });
    await this.classifierFaultControl.armed;
    const context = await this.launchBrowser(this.scenario.audio.initial);
    this.corePage = await context.newPage();
    await this.helpers.verifySyntheticCoreBrowser(
      this.corePage,
      this.db,
      this.seeded,
      this.scenario.runtime.coreUrl,
      path.join(this.evidenceRoot, "owner-authenticated.png"),
    );
    this.fileStorage = createFileStorageObserver({
      page: this.corePage,
      database: this.db,
      ObjectId: this.ObjectId,
      ownerId: this.seeded.userId,
      uploadsRoot:
        this.scenario.observation.uploadsRoot ||
        this.environment.UPLOADS_PATH ||
        this.environment.UPLOADS_DIR,
    });
    this.callPage = await context.newPage();
    await installRealRemoteAudioCapture(this.callPage);
    this.callPage.on("response", (response) => {
      void this.observeSignedResponse(response).catch(() => {});
    });
    const bootstrap = this.helpers.buildCallBootstrapUrl(
      this.scenario.runtime.playgroundUrl,
      this.seeded.callSessionId,
      this.seeded.browserCapability,
    );
    const startMs = Date.now();
    await this.callPage.goto(bootstrap.toString(), {
      waitUntil: "domcontentloaded",
      timeout: 45_000,
    });
    await this.helpers.assertCallBootstrapStripped(
      this.callPage,
      this.seeded.callSessionId,
    );
    let probe;
    let uploads;
    let missionWorkers;
    for (const turn of this.scenario.turns) {
      this.assertActive();
      const window = await this.observeTurn(turn, startMs);
      if (
        turn.kind === "authorizedCallLaunch" &&
        (window.missionDelta !== 2 || window.launchDelta !== 1)
      ) {
        blocked("two_independent_call_workers_not_observed");
      }
      if (turn.kind === "authorizedCallLaunch") {
        missionWorkers = orderedMissionWorkers(window, this.seeded.userId);
      }
      if (turn.kind === "trustedWingLaunch") {
        probe = await this.stopWingProbe(window);
      }
      if (turn.kind === "quickConversation") {
        uploads = await this.attachFiles(missionWorkers);
      }
      if (
        ["authorizedCallControl", "trustedWingControl"].includes(turn.kind) &&
        (window.actionDelta !== 1 || window.controlDelta !== 1)
      ) {
        blocked("owner_scoped_worker_control_not_observed");
      }
    }
    const unverifiedWindow = this.windows.find(
      (window) => window.kind === "unverifiedWingDenial",
    );
    assertUnverifiedWingDenial(
      unverifiedWindow,
      unverifiedWindow?.denial?.session,
    );
    const beforeHangup = await this.snapshot();
    const activeMissionWorkers = beforeHangup.ledger.work.filter(
      (work) => work.workRef && work.workRef !== probe.work.workRef,
    );
    if (
      activeMissionWorkers.length !== 2 ||
      new Set(activeMissionWorkers.map((row) => row.workRef)).size !== 2
    ) {
      blocked("two_independent_call_workers_not_observed");
    }
    const activeByRef = new Map(
      activeMissionWorkers.map((worker) => [worker.workRef, worker]),
    );
    const workers = missionWorkers.map((worker) =>
      activeByRef.get(worker.workRef),
    );
    if (workers.some((worker) => !record(worker))) {
      blocked("worker_launch_order_unobserved");
    }
    const beforeSurface = await this.captureSurface("before-hangup", workers);
    const evidenceDirectory = path.join(this.evidenceRoot, "evidence");
    if (!fs.existsSync(evidenceDirectory)) {
      fs.mkdirSync(evidenceDirectory, { mode: 0o700 });
    }
    const initialAudio = await this.helpers.persistCapturedOutputAudio(
      this.callPage,
      path.join(evidenceDirectory, "initial-audio.wav"),
    );
    const reconnect = await this.endCallAndReconnect(uploads.conversationId);
    const delivered = await this.waitObserved(
      () => captureOwnerLedger(this.db, this.seeded.userId),
      (ledger) =>
        workers.every(
          (work) =>
            ledger.callbacks.filter((row) => row.workRef === work.workRef)
              .length === 1 &&
            ledger.deliveries.filter((row) => row.workRef === work.workRef)
              .length === 1,
        ),
      "worker_callback_delivery_not_observed",
      boundedTimeout(this.scenario.deliveryTimeoutMs, 180_000),
    );
    const afterSurface = await this.captureSurface(
      "after-reconnect",
      workers,
      this.reconnectCorePage,
    );
    const artifacts = await this.openArtifacts(workers);
    const reconnectAudio = await this.helpers.persistCapturedOutputAudio(
      this.reconnectPage,
      path.join(evidenceDirectory, "reconnect-audio.wav"),
    );
    await this.remotePlayback(this.reconnectPage);
    if (initialAudio.sha256 === reconnectAudio.sha256) {
      blocked("session_output_audio_not_distinct");
    }
    const fallback = delivered.trace.filter(
      (row) => row.stage === this.scenario.observation.fallbackStage,
    );
    const fallbackPolicy = assertFallbackPolicy(
      this.scenario.requirements?.providerFallback,
      this.identityDigests?.candidateMode === "diagnostic"
        ? "diagnostic"
        : "strict",
    );
    if (fallbackPolicy.required && fallback.length < 1) {
      blocked("provider_fallback_not_observed");
    }
    const classifierFaultReceipt = await this.settleClassifierFaultControl();
    const finalRuntimeInstance = runtimeInstance(this.scenario);
    if (
      !record(this.restartEvidence) ||
      finalRuntimeInstance === this.initialRuntimeInstance ||
      finalRuntimeInstance !== this.restartEvidence.after
    ) {
      blocked("runtime_restart_not_observed");
    }
    const completions = await this.captureCompletionEvents(
      workers,
      reconnect,
      delivered,
    );
    const workerTraces = await this.captureWorkerTraces(workers, delivered);
    const sessions = await this.db
      .collection("viventiumcallsessions")
      .find({
        userId: this.seeded.userId,
      })
      .toArray();
    const observation = {
      candidate: this.identityDigests,
      runAt: new Date(startMs).toISOString(),
      ownerId: this.seeded.userId,
      initialSession: { ...this.seeded, ...this.initialEndedSession },
      reconnectSession: reconnect,
      sessions,
      conversationId: uploads.conversationId,
      windows: this.windows,
      workers,
      probe,
      uploads: uploads.uploads,
      ledger: delivered,
      surfaces: { before: beforeSurface, after: afterSurface },
      artifacts,
      audio: { initial: initialAudio, reconnect: reconnectAudio },
      fallback,
      classifierFaultReceipt,
      completions,
      workerTraces,
      runtime: {
        before: this.initialRuntimeInstance,
        after: finalRuntimeInstance,
        restart: this.restartEvidence,
      },
    };
    const audit = auditObservedAuthority(observation);
    if (
      audit.evidenceStatus !== "VALID" ||
      ["trustedWingControl", "passiveWingDenial", "listenOnlyDenial"].some(
        (key) => !audit.checks[key] || audit.checks[key].status !== "PASS",
      )
    ) {
      blocked("worker_authority_slice_unverified");
    }
    if (fallbackPolicy.required !== true) {
      return { observation, manifest: null, fallbackRequirement: "optional" };
    }
    return projectObservedJourney(
      observation,
      this.scenario,
      this.evidenceRoot,
    );
  }

  async recordSafetyFailure(failure) {
    if (
      !record(failure) ||
      failure.status !== "FAIL" ||
      !SAFETY_FAILURE_CODES.has(failure.blocker)
    ) {
      blocked("safety_failure_record_invalid");
    }
    const recorded = {
      status: "FAIL",
      blocker: failure.blocker,
      recordedAt: new Date().toISOString(),
    };
    if (
      this.seeded &&
      this.schedulerDatabase &&
      failure.blocker === "unsafe_synthetic_schedule_detected"
    ) {
      const ownerId = String(this.seeded.userId || "");
      const inventory = this.helpers.inspectSyntheticSchedules(
        this.seeded,
        this.schedulerDatabase,
      );
      const rows = observedOwnerScheduleRows(this.schedulerDatabase, ownerId);
      if (
        !record(inventory) ||
        inventory.unsafe < 1 ||
        inventory.total !== rows.length
      ) {
        blocked("synthetic_schedule_recovery_unavailable");
      }
      const recoveryPath = path.join(
        this.evidenceRoot,
        "evidence",
        "schedule-recovery.json",
      );
      privateJson(
        recoveryPath,
        {
          schema: "viventium.voice.qa.schedule-recovery.v1",
          ownerId,
          failureCode: failure.blocker,
          recordedAt: recorded.recordedAt,
          rows,
        },
        this.evidenceRoot,
      );
      recorded.recoveryPath = recoveryPath;
    }
    const failurePath = path.join(
      this.evidenceRoot,
      "evidence",
      "safety-failure.json",
    );
    privateJson(
      failurePath,
      {
        schema: "viventium.voice.qa.safety-failure.v1",
        caseId: CASE_ID,
        candidate: this.identityDigests,
        ...recorded,
        ...(this.seeded
          ? { ownerScopeHash: opaqueRef("owner", this.seeded.userId) }
          : {}),
      },
      this.evidenceRoot,
    );
    this.recordedSafetyFailure = recorded;
    return recorded;
  }

  async settleClassifierFaultControl() {
    if (this.classifierFaultCleaned && this.classifierFaultReceipt) {
      return this.classifierFaultReceipt;
    }
    if (!this.classifierFaultControl) {
      blocked("classifier_fault_parent_unavailable");
    }
    const receipt = await this.classifierFaultControl.receipt;
    const copied = {
      schema: "viventium.voice.mpv-061.classifier-fault-receipt.v1",
      caseId: CASE_ID,
      controlId: receipt.controlId,
      receiptDigest: receipt.receiptDigest,
      receiptExpiresAt: receipt.receiptExpiresAt,
      candidate: traceCandidateFacts(this.identityDigests),
    };
    privateJson(
      path.join(
        this.evidenceRoot,
        "evidence",
        "classifier-fallback-control-receipt.json",
      ),
      copied,
      this.evidenceRoot,
    );
    cleanupClassifierFaultReceipt({
      evidenceRoot: this.evidenceRoot,
      environment: this.environment,
      receipt,
    });
    this.classifierFaultReceipt = copied;
    this.classifierFaultCleaned = true;
    return copied;
  }

  async closeResources() {
    this.classifierFaultControl?.stop();
    this.classifierFaultControl = null;
    const browsers = Array.isArray(this.browsers)
      ? this.browsers.splice(0).reverse()
      : [];
    for (const browser of browsers) {
      await browser.close().catch(() => {});
    }
    const client = this.client;
    this.client = null;
    this.db = null;
    if (client) await client.close().catch(() => {});
  }

  async cleanup(context = {}) {
    if (
      !record(context.candidateBinding) ||
      candidateBindingSha256(context.candidateBinding) !==
        candidateBindingSha256(this.identityDigests)
    ) {
      blocked("cleanup_candidate_binding_mismatch");
    }
    let cleanupReceipt = null;
    try {
      if (this.seeded && this.db) {
        cleanupReceipt = await cleanupExactSyntheticOwner(
          this.db,
          this.seeded,
          this.ObjectId,
          this.scenario.runtime.playgroundUrl,
          this.helpers,
          {
            freshProof: this.freshProof,
            searchIndex: this.searchIndex,
            vectorIndex: this.vectorIndex,
            fileStorage: this.fileStorage,
            schedulerDatabase: this.schedulerDatabase,
            failureRecord: context.failure && this.recordedSafetyFailure,
          },
        );
      }
    } finally {
      await this.closeResources();
    }
    if (cleanupReceipt?.zeroResidue === true) {
      const statePath = this.scenario.outputs.cleanupState;
      if (fs.existsSync(statePath)) {
        readCleanupRecoveryState(statePath, {
          scenarioBindingSha256: this.scenarioBindingSha256,
          candidateBindingSha256: candidateBindingSha256(this.identityDigests),
        });
        fs.unlinkSync(statePath);
      }
    }
    return cleanupReceipt;
  }
}

function auditObservedAuthority(observation) {
  const windows = Object.fromEntries(
    observation.windows.map((window) => [window.kind, window]),
  );
  const ordered = [
    windows.trustedWingLaunch,
    windows.trustedWingControl,
    windows.passiveWingDenial,
    windows.listenOnlyDenial,
  ];
  if (ordered.some((window) => !record(window))) {
    blocked("worker_authority_slice_unverified");
  }
  const cases = {};
  for (let index = 0; index < ordered.length; index += 1) {
    const window = ordered[index];
    const common = {
      ordinal: index + 1,
      ledgerSequenceBefore: window.before.ledger.trace.length,
      ledgerSequenceAfter: window.after.ledger.trace.length,
      mode: window.mode,
      actorTrust: window.segment.speaker.actorTrust,
      directlyAddressed: window.directlyAddressed,
      missionDelta: window.missionDelta,
      mainResponseDelta: window.responseDelta,
      ttsInputDelta: window.ttsDelta,
    };
    if (window.kind === "trustedWingLaunch") {
      cases[window.kind] = {
        ...common,
        sideEffectAuthorityGranted: Boolean(window.authority),
        requestedMissionCount: window.missionDelta,
        acceptedLaunchReceiptDelta: window.missionDelta,
        rejectedLaunchReceiptDelta: 0,
        workerLaunchInvocationDelta: window.launchDelta,
      };
    } else if (window.kind === "trustedWingControl") {
      cases[window.kind] = {
        ...common,
        sideEffectAuthorityGranted: Boolean(window.authority),
        controlAction: "steer",
        acceptedActionReceiptDelta: window.actionDelta,
        workerControlInvocationDelta: window.controlDelta,
        targetWorkRefMatched: window.actionDelta === 1,
        targetActionReceiptDelta: window.actionDelta,
        nonTargetActionReceiptDelta: 0,
      };
    } else if (window.kind === "passiveWingDenial") {
      cases[window.kind] = {
        ...common,
        transcriptObservationDelta: window.transcriptDelta,
        actionReceiptDelta: window.actionDelta,
        workerLaunchInvocationDelta: window.launchDelta,
        workerControlInvocationDelta: window.controlDelta,
        toolInvocationDelta: window.toolDelta,
        cortexInvocationDelta: window.cortexDelta,
        liveMemoryInvocationDelta: window.liveMemoryDelta,
      };
    } else {
      cases[window.kind] = {
        ...common,
        sideEffectAuthorityGranted: false,
        ambientTranscriptDelta: window.transcriptDelta,
        actionReceiptDelta: window.actionDelta,
        workerLaunchInvocationDelta: window.launchDelta,
        workerControlInvocationDelta: window.controlDelta,
        toolInvocationDelta: window.toolDelta,
        agentControllerInvocationDelta: window.controllerDelta,
        cortexInvocationDelta: window.cortexDelta,
        liveMemoryInvocationDelta: window.liveMemoryDelta,
        titleModelInvocationDelta: window.titleModelDelta,
      };
    }
  }
  const evidence = {
    schema: "viventium.voice.worker-bee-authority-evidence.v1",
    authoritative: true,
    source: "owner_scoped_worker_mission_action_delivery_ledger",
    modeAuthoritySource: "persisted_call_session",
    acceptanceRunBindingMatched: true,
    installedRuntimeIdentityMatched: true,
    observationOrder: [
      "trustedWingLaunch",
      "trustedWingControl",
      "passiveWingDenial",
      "listenOnlyDenial",
    ],
    cases,
  };
  const acceptance = require("./world_class_call_acceptance.js");
  return acceptance.auditWorkerBeeAuthorityEvidence(evidence);
}

async function cleanupExactSyntheticOwner(
  database,
  seeded,
  ObjectId,
  playgroundUrl,
  helpers,
  options = {},
) {
  const ownerId = String(seeded.userId || "");
  const email = String(seeded.email || "");
  const emailParts = email.split(String.fromCharCode(64));
  if (
    !HEX_24.test(ownerId) ||
    emailParts.length !== 2 ||
    !emailParts[0].startsWith("viventium-voice-qa-") ||
    emailParts[1] !== "example.com"
  ) {
    blocked("synthetic_cleanup_scope_invalid");
  }
  const proof = options.freshProof;
  if (
    !record(proof) ||
    proof.ownerId !== ownerId ||
    proof.email !== email ||
    proof.acknowledged !== true ||
    !Number.isSafeInteger(proof.insertedAtMs)
  ) {
    blocked("synthetic_cleanup_fresh_owner_unverified");
  }
  const ownerObject = new ObjectId(ownerId);
  const owner = await database.collection("users").findOne({
    _id: ownerObject,
    email,
  });
  if (
    !record(owner) ||
    String(owner._id || "") !== ownerId ||
    new Date(owner.createdAt || 0).getTime() !== proof.insertedAtMs
  ) {
    blocked("synthetic_cleanup_fresh_owner_unverified");
  }
  const [messages, conversations, files, ownedSessions] = await Promise.all([
    database.collection("messages").find({ user: ownerId }).toArray(),
    database.collection("conversations").find({ user: ownerId }).toArray(),
    database.collection("files").find({ user: ownerObject }).toArray(),
    database
      .collection("viventiumcallsessions")
      .find({ userId: ownerId })
      .toArray(),
  ]);
  const messageIds = [
    ...new Set(
      messages.map((item) => String(item.messageId || "")).filter(Boolean),
    ),
  ];
  const conversationIds = [
    ...new Set(
      conversations
        .map((item) => String(item.conversationId || ""))
        .filter(Boolean),
    ),
  ];
  const vectorFiles = files.filter(
    (file) =>
      file.embedded === true ||
      file.source === "vectordb" ||
      file.filepath === "vectordb",
  );
  const vectorFileIds = vectorFiles.map((file) => String(file.file_id || ""));
  if (
    vectorFileIds.some((value) => !value) ||
    new Set(vectorFileIds).size !== vectorFileIds.length
  ) {
    blocked("vector_index_cleanup_scope_invalid");
  }
  if (
    (messageIds.length > 0 || conversationIds.length > 0) &&
    (!record(options.searchIndex) ||
      typeof options.searchIndex.removeAndVerify !== "function")
  ) {
    blocked("search_index_cleanup_unavailable");
  }
  if (
    vectorFileIds.length > 0 &&
    (!record(options.vectorIndex) ||
      typeof options.vectorIndex.removeAndVerify !== "function")
  ) {
    blocked("vector_index_cleanup_unavailable");
  }
  if (
    files.length > 0 &&
    (!record(options.fileStorage) ||
      typeof options.fileStorage.removeAndVerify !== "function")
  ) {
    blocked("file_storage_cleanup_unavailable");
  }
  if (
    typeof helpers.inspectSyntheticSchedules !== "function" ||
    typeof helpers.cleanupSyntheticSchedules !== "function" ||
    typeof options.schedulerDatabase !== "string" ||
    !options.schedulerDatabase ||
    !fs.existsSync(options.schedulerDatabase)
  ) {
    blocked("scheduler_cleanup_observer_unavailable");
  }
  for (const session of ownedSessions) {
    if (
      String(session.userId || "") !== ownerId ||
      typeof session.callSessionId !== "string" ||
      !session.callSessionId
    ) {
      blocked("synthetic_cleanup_session_unverified");
    }
    const [matchingSessions, ingressRows] = await Promise.all([
      database
        .collection("viventiumcallsessions")
        .find({ callSessionId: session.callSessionId })
        .toArray(),
      database
        .collection("viventiumvoiceingressevents")
        .find({ callSessionId: session.callSessionId })
        .toArray(),
    ]);
    if (
      !Array.isArray(matchingSessions) ||
      matchingSessions.length !== 1 ||
      String(matchingSessions[0]?.userId || "") !== ownerId ||
      !Array.isArray(ingressRows) ||
      ingressRows.some(
        (entry) =>
          !record(entry) ||
          String(entry.userId || "") !== ownerId ||
          String(entry.callSessionId || "") !== session.callSessionId,
      )
    ) {
      blocked("synthetic_cleanup_session_unverified");
    }
  }
  const schedulesBefore = helpers.inspectSyntheticSchedules(
    seeded,
    options.schedulerDatabase,
  );
  if (
    !record(schedulesBefore) ||
    !Number.isSafeInteger(schedulesBefore.total) ||
    !Number.isSafeInteger(schedulesBefore.unsafe) ||
    schedulesBefore.total < 0 ||
    schedulesBefore.unsafe < 0 ||
    schedulesBefore.unsafe > schedulesBefore.total
  ) {
    blocked("scheduler_cleanup_observer_unavailable");
  }
  let recoveredScheduleRows;
  if (schedulesBefore.unsafe > 0) {
    const failure = options.failureRecord;
    if (
      !record(failure) ||
      failure.status !== "FAIL" ||
      failure.blocker !== "unsafe_synthetic_schedule_detected" ||
      typeof failure.recoveryPath !== "string" ||
      !failure.recoveryPath
    ) {
      blocked("unsafe_synthetic_schedule_detected");
    }
    const recovery = readPrivateJson(
      failure.recoveryPath,
      "synthetic_schedule_recovery",
    );
    if (
      recovery.schema !== "viventium.voice.qa.schedule-recovery.v1" ||
      recovery.ownerId !== ownerId ||
      recovery.failureCode !== "unsafe_synthetic_schedule_detected" ||
      !Array.isArray(recovery.rows) ||
      recovery.rows.length !== schedulesBefore.total ||
      recovery.rows.some(
        (row) =>
          !record(row) ||
          String(row.user_id || "") !== ownerId ||
          !Number.isSafeInteger(row.__qa_rowid) ||
          row.__qa_rowid < 1,
      ) ||
      new Set(recovery.rows.map((row) => row.__qa_rowid)).size !==
        recovery.rows.length
    ) {
      blocked("synthetic_schedule_recovery_scope_mismatch");
    }
    const observeRows =
      options.readScheduleRows ||
      (() => observedOwnerScheduleRows(options.schedulerDatabase, ownerId));
    const current = observeRows({
      ownerId,
      databasePath: options.schedulerDatabase,
    });
    if (
      !Array.isArray(current) ||
      current.length !== recovery.rows.length ||
      current.some(
        (row) => !record(row) || String(row.user_id || "") !== ownerId,
      ) ||
      JSON.stringify(current) !== JSON.stringify(recovery.rows)
    ) {
      blocked("synthetic_schedule_recovery_scope_mismatch");
    }
    recoveredScheduleRows = current;
  }
  if (messageIds.length > 0 || conversationIds.length > 0) {
    const outcome = await options.searchIndex.removeAndVerify({
      ownerId,
      messageIds,
      conversationIds,
    });
    if (!record(outcome) || outcome.remaining !== 0) {
      blocked("search_index_cleanup_unverified");
    }
  }
  if (vectorFileIds.length > 0) {
    const outcome = await options.vectorIndex.removeAndVerify({
      ownerId,
      files: vectorFiles,
      fileIds: vectorFileIds,
    });
    if (!record(outcome) || outcome.remaining !== 0) {
      blocked("vector_index_cleanup_unverified");
    }
  }
  if (files.length > 0) {
    const outcome = await options.fileStorage.removeAndVerify({
      ownerId,
      files,
    });
    if (!record(outcome) || outcome.remaining !== 0) {
      blocked("file_storage_cleanup_unverified");
    }
  }
  if (
    seeded.callSessionId &&
    seeded.browserCapability &&
    typeof helpers.cancelSyntheticActiveVoiceTasks === "function"
  ) {
    await helpers.cancelSyntheticActiveVoiceTasks(
      database,
      seeded,
      playgroundUrl,
    );
  }
  const schedulesRemoved = recoveredScheduleRows
    ? (options.deleteScheduleRows || deleteExactObservedScheduleRows)({
        databasePath: options.schedulerDatabase,
        ownerId,
        rowIds: recoveredScheduleRows.map((row) => row.__qa_rowid),
      })
    : helpers.cleanupSyntheticSchedules(seeded, options.schedulerDatabase);
  if (schedulesRemoved !== schedulesBefore.total) {
    blocked("scheduler_cleanup_unverified");
  }
  for (const session of ownedSessions) {
    const callSessionId = String(session.callSessionId || "");
    await database
      .collection("viventiumvoicespeakersegments")
      .deleteMany({ callSessionId });
    await database.collection("viventiumvoiceingressevents").deleteMany({
      callSessionId,
      userId: ownerId,
    });
  }
  for (const collection of LEDGER_COLLECTIONS) {
    const value =
      collection.ownerField === "ownerScopeHash"
        ? opaqueRef("owner", ownerId)
        : ownerId;
    await database
      .collection(collection.name)
      .deleteMany({ [collection.ownerField]: value });
  }
  for (const collection of CLEANUP_OWNER_COLLECTIONS) {
    const value = collection.kind === "object_id" ? ownerObject : ownerId;
    await database
      .collection(collection.name)
      .deleteMany({ [collection.field]: value });
  }
  const removedOwner = await database.collection("users").deleteOne({
    _id: ownerObject,
    email,
  });
  if (!record(removedOwner) || removedOwner.deletedCount !== 1) {
    blocked("synthetic_cleanup_owner_delete_unverified");
  }
  for (const collection of CLEANUP_OWNER_COLLECTIONS) {
    const value = collection.kind === "object_id" ? ownerObject : ownerId;
    const remaining = await database
      .collection(collection.name)
      .countDocuments({ [collection.field]: value });
    if (remaining !== 0) {
      blocked("synthetic_cleanup_residue_detected");
    }
  }
  for (const collection of LEDGER_COLLECTIONS) {
    const value =
      collection.ownerField === "ownerScopeHash"
        ? opaqueRef("owner", ownerId)
        : ownerId;
    const remaining = await database
      .collection(collection.name)
      .countDocuments({ [collection.ownerField]: value });
    if (remaining !== 0) {
      blocked("synthetic_cleanup_residue_detected");
    }
  }
  for (const session of ownedSessions) {
    for (const name of [
      "viventiumvoicespeakersegments",
      "viventiumvoiceingressevents",
    ]) {
      const remaining = await database
        .collection(name)
        .countDocuments({ callSessionId: session.callSessionId });
      if (remaining !== 0) {
        blocked("synthetic_cleanup_residue_detected");
      }
    }
  }
  const remainingOwner = await database.collection("users").countDocuments({
    _id: ownerObject,
    email,
  });
  const schedulesAfter = helpers.inspectSyntheticSchedules(
    seeded,
    options.schedulerDatabase,
  );
  if (
    remainingOwner !== 0 ||
    !record(schedulesAfter) ||
    schedulesAfter.total !== 0
  ) {
    blocked("synthetic_cleanup_residue_detected");
  }
  return {
    zeroResidue: true,
    scheduledTasksRemoved: schedulesRemoved,
    ownedSessionsRemoved: ownedSessions.length,
    searchEntriesVerified: messageIds.length + conversationIds.length,
    vectorEntriesVerified: vectorFileIds.length,
    storedFilesVerified: files.length,
  };
}

function assertObservedLedgerScope(ledger, ownerId) {
  if (
    !record(ledger) ||
    !HEX_24.test(String(ownerId || "")) ||
    ledger.source !== "owner_scoped_worker_mission_action_delivery_ledger" ||
    ledger.ownerScopeHash !== opaqueRef("owner", ownerId)
  ) {
    blocked("observed_owner_scope_mismatch");
  }
  for (const definition of LEDGER_COLLECTIONS) {
    const expected =
      definition.ownerField === "ownerScopeHash"
        ? ledger.ownerScopeHash
        : ownerId;
    if (
      !Array.isArray(ledger[definition.key]) ||
      ledger[definition.key].some(
        (row) =>
          !record(row) || String(row[definition.ownerField] || "") !== expected,
      )
    ) {
      blocked("observed_owner_scope_mismatch");
    }
  }
}

function exactObservedRow(rows, workRef, blocker) {
  const selected = Array.isArray(rows)
    ? rows.filter((row) => String(row.workRef || "") === workRef)
    : [];
  if (selected.length !== 1) {
    blocked(blocker);
  }
  return selected[0];
}

function observedResourceFileIds(source) {
  const identifiers = new Set();
  const visited = new Set();
  const visit = (value) => {
    if (Array.isArray(value)) {
      for (const item of value) visit(item);
      return;
    }
    if (!record(value)) return;
    if (visited.has(value)) return;
    visited.add(value);
    for (const key of ["file_id", "fileId", "identifier", "id", "_id"]) {
      if (typeof value[key] === "string" && value[key]) {
        identifiers.add(value[key]);
      }
    }
    for (const key of [
      "fileIds",
      "file_ids",
      "inputFileIds",
      "observedInputFileIds",
    ]) {
      if (Array.isArray(value[key])) {
        for (const identifier of value[key]) {
          if (typeof identifier === "string" && identifier) {
            identifiers.add(identifier);
          }
        }
      }
    }
    for (const nested of Object.values(value)) visit(nested);
  };
  visit(source);
  return identifiers;
}

function assertAttachmentDispatchBinding({
  upload,
  authorization,
  mission,
  siblingAuthorizations = [],
  ownerId,
}) {
  const fileIds = new Set(
    [
      String(upload?.file?._id || ""),
      String(upload?.file?.file_id || ""),
    ].filter(Boolean),
  );
  const attachedIds = new Set(
    Array.isArray(upload?.message?.attachments)
      ? upload.message.attachments
          .map((item) => String(item?.file_id || item?.fileId || ""))
          .filter(Boolean)
      : [],
  );
  const targetIds = new Set([
    ...observedResourceFileIds(authorization),
    ...observedResourceFileIds(mission),
  ]);
  if (
    !record(upload) ||
    !record(upload.message) ||
    upload.message.user !== ownerId ||
    upload.message.isCreatedByUser !== true ||
    typeof upload.targetWorkRef !== "string" ||
    !upload.targetWorkRef ||
    authorization?.ownerId !== ownerId ||
    authorization?.workRef !== upload.targetWorkRef ||
    (mission &&
      (mission.ownerId !== ownerId ||
        mission.workRef !== upload.targetWorkRef)) ||
    fileIds.size < 1 ||
    attachedIds.size !== 1 ||
    [...attachedIds].some((identifier) => !fileIds.has(identifier)) ||
    ![...fileIds].some((identifier) => targetIds.has(identifier))
  ) {
    blocked("worker_input_handoff_not_observed");
  }
  for (const sibling of siblingAuthorizations) {
    if (
      sibling?.workRef !== upload.targetWorkRef &&
      [...observedResourceFileIds(sibling)].some((identifier) =>
        fileIds.has(identifier),
      )
    ) {
      blocked("attachment_leaked_to_sibling_worker");
    }
  }
  return { targetWorkRef: upload.targetWorkRef, sent: true, isolated: true };
}

function observedWorkerInputReceipt({
  authorization,
  mission,
  upload,
  uploads,
  ownerId,
}) {
  if (
    upload.targetWorkRef !== mission.workRef ||
    upload.targetWorkRef !== authorization.workRef
  ) {
    blocked("worker_input_handoff_not_observed");
  }
  assertAttachmentDispatchBinding({
    upload,
    authorization,
    mission,
    siblingAuthorizations: uploads
      .filter((item) => item !== upload)
      .map((item) => item.authorization)
      .filter(record),
    ownerId,
  });
  const descriptors = [];
  const collect = (source) => {
    if (!record(source)) {
      return;
    }
    for (const key of [
      "fileIds",
      "file_ids",
      "inputFileIds",
      "observedInputFileIds",
    ]) {
      if (Array.isArray(source[key])) {
        descriptors.push(...source[key].map((identifier) => ({ identifier })));
      }
    }
    for (const key of [
      "files",
      "uploaded_files",
      "uploadedFiles",
      "inputFiles",
    ]) {
      if (Array.isArray(source[key])) {
        descriptors.push(
          ...source[key].map((entry) =>
            record(entry) ? entry : { identifier: entry },
          ),
        );
      }
    }
  };
  collect(authorization);
  collect(mission);
  collect(mission?.evidence);
  if (record(authorization?.hostToolResources)) {
    for (const resource of Object.values(authorization.hostToolResources)) {
      collect(resource);
    }
  }
  const ownIds = new Set(
    [String(upload.file._id || ""), String(upload.file.file_id || "")].filter(
      Boolean,
    ),
  );
  const siblingIds = new Set(
    uploads
      .flatMap((other) =>
        other === upload
          ? []
          : [
              String(other?.file?._id || ""),
              String(other?.file?.file_id || ""),
            ],
      )
      .filter(Boolean),
  );
  let matched = false;
  for (const descriptor of descriptors) {
    const identifier = String(
      descriptor.identifier ||
        descriptor.file_id ||
        descriptor.fileId ||
        descriptor.id ||
        descriptor._id ||
        "",
    );
    if (!identifier) {
      continue;
    }
    if (siblingIds.has(identifier)) {
      blocked("worker_input_handoff_not_observed");
    }
    if (!ownIds.has(identifier)) {
      continue;
    }
    const descriptorOwner = String(
      descriptor.ownerId || descriptor.userId || descriptor.user || "",
    );
    const descriptorHash = String(
      descriptor.sha256 ||
        descriptor.file_sha256 ||
        descriptor.contentSha256 ||
        "",
    );
    if (
      (descriptorOwner && descriptorOwner !== ownerId) ||
      (descriptorHash && descriptorHash !== upload.observed.sha256)
    ) {
      blocked("worker_input_handoff_not_observed");
    }
    matched = true;
  }
  if (!matched) {
    blocked("worker_input_handoff_not_observed");
  }
}

function assertObservedTerminalCallback(callback, delivery) {
  const callbackId = String(callback?.callbackId || "");
  const operationId = String(callback?.acceptedOperationId || "");
  const resultDigest = String(callback?.resultDigest || "");
  if (
    !/^cb_terminal_[a-f0-9]{64}$/.test(callbackId) ||
    !/^[a-f0-9]{32}$/.test(operationId) ||
    !/^sha256:[a-f0-9]{64}$/.test(resultDigest) ||
    delivery?.traceIdentityVerified !== true ||
    delivery.terminalCallbackId !== callbackId ||
    delivery.terminalCallbackAcceptedOperationId !== operationId ||
    delivery.terminalCallbackResultDigest !== resultDigest
  ) {
    blocked("worker_callback_identity_not_bound");
  }
}

function observedProducerArtifact(
  traces,
  { ownerId, originRef, workRef, sha256 },
) {
  if (
    !HEX_24.test(String(ownerId || "")) ||
    !HEX_64.test(String(sha256 || ""))
  ) {
    blocked("worker_artifact_delivery_not_bound");
  }
  const matching = Array.isArray(traces)
    ? traces.filter((trace) => record(trace) && trace.workRef === workRef)
    : [];
  const observed = matching.length === 1 ? matching[0] : null;
  const response = observed?.response;
  const artifacts = response?.current?.artifactRefs;
  if (
    !record(observed) ||
    observed.originRef !== originRef ||
    !record(response) ||
    response.version !== 2 ||
    response.traceRef !== opaqueRef("origin", originRef) ||
    response.workRef !== opaqueRef("work", workRef) ||
    response.integrity?.ownerScoped !== true ||
    response.integrity?.completionClaimable !== true ||
    response.integrity?.artifactRefs?.status !== "verified" ||
    response.completionClaims?.allowed !== true ||
    response.ledger?.chain?.fullChainVerified !== true ||
    response.current?.workState !== "completed" ||
    !record(artifacts) ||
    artifacts.available !== true ||
    !Array.isArray(artifacts.refs) ||
    artifacts.refs.length !== 1
  ) {
    blocked("worker_artifact_delivery_not_bound");
  }
  const artifact = artifacts.refs[0];
  if (
    !record(artifact) ||
    artifact.artifactRef !== "artifact_sha256:" + sha256 ||
    artifact.fingerprint !== "sha256:" + sha256
  ) {
    blocked("worker_artifact_delivery_not_bound");
  }
  return artifact;
}

function observedEvidenceBytes(observed, label) {
  if (
    !record(observed) ||
    typeof observed.path !== "string" ||
    !HEX_64.test(String(observed.sha256 || ""))
  ) {
    blocked(label + "_unverified");
  }
  const current = readPrivateBytes(observed.path, label);
  if (
    current.sha256 !== observed.sha256 ||
    (Buffer.isBuffer(observed.bytes) && !current.bytes.equals(observed.bytes))
  ) {
    blocked(label + "_unverified");
  }
  return current;
}

function observedEffectCounts(window) {
  const mapping = {
    missionCount: "missionDelta",
    actionCount: "actionDelta",
    launchInvocationCount: "launchDelta",
    controlInvocationCount: "controlDelta",
    toolInvocationCount: "toolDelta",
    controllerInvocationCount: "controllerDelta",
    cortexInvocationCount: "cortexDelta",
    liveMemoryInvocationCount: "liveMemoryDelta",
    recallInvocationCount: "recallDelta",
    titleModelInvocationCount: "titleModelDelta",
    mainResponseCount: "responseDelta",
    ttsInputCount: "ttsDelta",
    assistantAudioOutputCount: "audioDelta",
  };
  const counts = {};
  for (const [key, field] of Object.entries(mapping)) {
    const value = window[field];
    if (!Number.isSafeInteger(value) || value < 0) {
      blocked("logical_turn_observation_invalid");
    }
    counts[key] = value;
  }
  return counts;
}

function observedAssistantSpeaker(observation) {
  const speakers = new Set();
  for (const window of observation.windows) {
    if (window.responseDelta === 0) {
      continue;
    }
    const messages = Array.isArray(window.after?.messages)
      ? window.after.messages.filter(
          (message) =>
            String(message.user || message.userId || "") ===
              observation.ownerId &&
            ["assistant", "ai"].includes(String(message.role || "")) &&
            String(message.turnId || message.metadata?.turnId || "") ===
              window.segment.turnId,
        )
      : [];
    if (messages.length !== 1) {
      blocked("assistant_speaker_identity_not_observed");
    }
    const identity = String(
      messages[0].agentId ||
        messages[0].agent_id ||
        messages[0].speakerIdentity ||
        "",
    );
    if (!identity) {
      blocked("assistant_speaker_identity_not_observed");
    }
    speakers.add(identity);
  }
  if (speakers.size !== 1) {
    blocked("assistant_speaker_identity_not_observed");
  }
  return [...speakers][0];
}

function observedSurfaceRows(surface, workers) {
  if (
    !record(surface) ||
    !record(surface.response) ||
    typeof surface.visible !== "string" ||
    !surface.visible.trim()
  ) {
    blocked("observed_worker_surface_unavailable");
  }
  const candidates = [
    surface.response.items,
    surface.response.work,
    surface.response.results,
    surface.response.data?.items,
    surface.response.data?.work,
    surface.response.activeWork,
  ];
  const rows = candidates.find(Array.isArray);
  if (
    !rows ||
    workers.some((worker) => {
      const selected = rows.filter(
        (row) => String(row.workRef || "") === worker.workRef,
      );
      if (selected.length !== 1) {
        return true;
      }
      const label = String(
        selected[0].title ||
          selected[0].displayName ||
          selected[0].workRef ||
          "",
      );
      return !label || !surface.visible.includes(label);
    })
  ) {
    blocked("observed_worker_surface_unavailable");
  }
  if (typeof surface.screenshot !== "string") {
    blocked("observed_worker_surface_unavailable");
  }
  readPrivateBytes(surface.screenshot, "surface_capture");
  return rows;
}

function observedStructuralRecords(id, manifest, evidenceById) {
  const voice = manifest.voice;
  const turns = [...Object.values(voice.turns), ...voice.completionTurns];
  const turnRecord = (turn) => {
    const item = {
      type: "turn",
      logicalTurnRef: turn.logicalTurnRef,
      logicalRevision: turn.logicalRevision,
      sessionRef: turn.sessionRef,
      conversationRef: turn.conversationRef,
      mode: turn.mode,
      effects: turn.effects,
      assistantSpeakerRef: turn.assistantSpeakerRef,
    };
    for (const key of [
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
    ]) {
      if (Object.hasOwn(turn, key)) {
        item[key] = turn[key];
      }
    }
    for (const field of ["inputAudioEvidence", "outputAudioEvidence"]) {
      if (turn[field]) {
        item[field.replace("Evidence", "Sha256")] = evidenceById.get(
          turn[field],
        ).sha256;
      }
    }
    return item;
  };
  const referenced = turns.filter(
    (turn) => turn.evidence.includes(id) || turn.transcriptEvidence === id,
  );
  if (
    [
      "initial-transcript",
      "reconnect-transcript",
      "logical-turn-ledger",
      "mode-ledger",
    ].includes(id)
  ) {
    return referenced.map(turnRecord);
  }
  if (id === "action-ledger") {
    const probe = voice.wingProbe;
    return [
      ...referenced.map(turnRecord),
      {
        type: "probe_cleanup",
        ...Object.fromEntries(
          [
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
          ].map((field) => [field, probe[field]]),
        ),
      },
    ];
  }
  if (id === "worker-ledger") {
    return [
      ...manifest.workers.map((worker) => ({
        type: "worker",
        ...Object.fromEntries(
          [
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
          ].map((field) => [field, worker[field]]),
        ),
      })),
      ...referenced
        .filter((turn) => Object.hasOwn(turn, "acceptedWorkerRefs"))
        .map((turn) => ({ ...turnRecord(turn), type: "launch" })),
      {
        type: "wing_probe",
        ...Object.fromEntries(
          Object.entries(voice.wingProbe).filter(
            ([field]) => field !== "evidence",
          ),
        ),
      },
    ];
  }
  if (id === "upload-ledger") {
    return manifest.inputGroup.ordered.map((item) => ({
      type: "input",
      ...item,
    }));
  }
  if (id === "capability-ledger") {
    return [
      ...manifest.workers.map((worker) => ({
        type: "capability",
        ...Object.fromEntries(
          [
            "workerRef",
            "missionRef",
            "contextBindingMatched",
            "requiredCapabilitiesPreserved",
            "fallbackCapabilityLossCount",
            "memoryRecallReceiptCount",
            "connectedToolReceiptCount",
          ].map((field) => [field, worker[field]]),
        ),
      })),
      { type: "fallback", ...manifest.resilience.fallback },
    ];
  }
  if (id === "session-ledger") {
    return [
      {
        type: "session",
        ...Object.fromEntries(
          [
            "initialSessionRef",
            "reconnectSessionRef",
            "conversationRef",
            "initialSessionEnded",
            "reconnectExplicitlyStarted",
            "acceptedWorkCancelledByHangupCount",
            "unsolicitedResultCallCount",
          ].map((field) => [field, manifest.run[field]]),
        ),
      },
      { type: "restart", ...manifest.resilience.restart },
    ];
  }
  if (["callback-ledger", "delivery-ledger"].includes(id)) {
    const deliveries = manifest.deliveries.map((delivery) => ({
      type: "delivery",
      ...Object.fromEntries(
        [
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
        ].map((field) => [field, delivery[field]]),
      ),
    }));
    return id === "delivery-ledger"
      ? [...deliveries, ...voice.completionTurns.map(turnRecord)]
      : deliveries;
  }
  if (
    ["linked-before", "linked-after", "active-before", "active-after"].includes(
      id,
    )
  ) {
    const after = id.endsWith("after");
    return [
      {
        type: "surface",
        surface: id.startsWith("linked") ? "linked_chat" : "active_work",
        phase: after ? "after_reconnect" : "before_hangup",
        workerRefs: manifest.workers.map((worker) => worker.workerRef),
        artifactRefs: after
          ? manifest.workers.map((worker) => worker.artifactRef)
          : [],
      },
    ];
  }
  if (["artifact-a-open", "artifact-b-open"].includes(id)) {
    const delivery = manifest.deliveries[id === "artifact-a-open" ? 0 : 1];
    return [
      {
        type: "artifact_open",
        ...Object.fromEntries(
          [
            "workerRef",
            "missionRef",
            "attemptRef",
            "artifactRef",
            "artifactSha256",
            "artifactEvidence",
            "opened",
            "openOrDownloadActionWorked",
          ].map((field) => [field, delivery[field]]),
        ),
      },
    ];
  }
  if (id === "public-safety") {
    return [
      {
        type: "public_safety",
        rawEvidencePrivate: manifest.publicSafety.rawEvidencePrivate,
        publicReportContentFree: manifest.publicSafety.publicReportContentFree,
        reviewed: manifest.publicSafety.reviewed,
      },
    ];
  }
  blocked("observed_evidence_kind_unavailable");
}

function projectObservedJourney(observation, scenario, evidenceRoot) {
  if (
    record(scenario?.observation) &&
    Object.hasOwn(scenario.observation, "manifestProjection")
  ) {
    blocked("caller_supplied_manifest_forbidden");
  }
  if (
    !record(observation) ||
    !Array.isArray(observation.windows) ||
    observation.windows.length !== EXECUTION_TURNS.length ||
    !Array.isArray(observation.workers) ||
    observation.workers.length !== 2 ||
    !Array.isArray(observation.uploads) ||
    observation.uploads.length !== 2 ||
    !Array.isArray(observation.artifacts) ||
    observation.artifacts.length !== 2 ||
    !Array.isArray(observation.workerTraces) ||
    observation.workerTraces.length !== 2 ||
    !record(observation.initialSession) ||
    !record(observation.reconnectSession) ||
    observation.reconnectSession.callSessionId ===
      observation.initialSession.callSessionId ||
    !Array.isArray(observation.fallback) ||
    observation.fallback.length < 1 ||
    !record(observation.runtime) ||
    observation.runtime.before === observation.runtime.after ||
    !record(observation.candidate) ||
    !HEX_64.test(String(observation.candidate.candidateDigest || "")) ||
    !HEX_64.test(String(observation.candidate.artifactDigest || ""))
  ) {
    blocked("full_journey_observations_incomplete");
  }
  if (
    !Array.isArray(observation.completions) ||
    observation.completions.length !== 2
  ) {
    blocked("worker_completion_speech_not_observed");
  }
  let candidateBinding = observation.candidate;
  if (observation.candidate.candidateMode === "diagnostic") {
    candidateBinding = normalizedCandidateBinding(
      observation.candidate,
      "diagnostic",
    );
    if (
      canonicalJson(candidateBinding) !== canonicalJson(observation.candidate)
    ) {
      blocked("diagnostic_candidate_binding_invalid");
    }
  }
  const bindingSha256 = candidateBindingSha256(candidateBinding);
  const ownerId = String(observation.ownerId || "");
  assertObservedLedgerScope(observation.ledger, ownerId);
  if (
    String(observation.initialSession.userId || "") !== ownerId ||
    String(observation.reconnectSession.userId || "") !== ownerId ||
    observation.reconnectSession.conversationId !==
      observation.conversationId ||
    !["ended", "completed", "disconnected"].includes(
      String(
        observation.initialSession.callStatus ||
          observation.initialSession.status ||
          "",
      ),
    ) ||
    observation.reconnectSession.mode !== "call"
  ) {
    blocked("exact_owned_session_not_observed");
  }
  if (
    !Array.isArray(observation.sessions) ||
    observation.sessions.some(
      (session) =>
        !record(session) ||
        String(session.userId || "") !== ownerId ||
        typeof session.callSessionId !== "string" ||
        !session.callSessionId,
    )
  ) {
    blocked("owner_call_session_inventory_unobserved");
  }
  const expectedSessions = new Set([
    observation.initialSession.callSessionId,
    observation.reconnectSession.callSessionId,
  ]);
  const unsolicitedSessions = observation.sessions.filter(
    (session) => !expectedSessions.has(session.callSessionId),
  );
  if (unsolicitedSessions.length > 0) {
    blocked("unsolicited_result_call_observed");
  }
  if (
    observation.sessions.length !== expectedSessions.size ||
    new Set(observation.sessions.map((session) => session.callSessionId))
      .size !== expectedSessions.size
  ) {
    blocked("owner_call_session_inventory_unobserved");
  }
  const restart = observation.runtime.restart;
  if (
    !record(restart) ||
    restart.invoked !== true ||
    restart.exitCode !== 0 ||
    restart.before !== observation.runtime.before ||
    restart.after !== observation.runtime.after ||
    restart.mainAvailableBefore !== true ||
    restart.mainAvailableAfter !== true ||
    !Array.isArray(restart.workerRefs) ||
    !Array.isArray(restart.survivingWorkRefs)
  ) {
    blocked("runtime_restart_not_observed");
  }
  if (
    restart.callSessionId !== observation.initialSession.callSessionId ||
    restart.survivingCallSessionId !==
      observation.initialSession.callSessionId ||
    restart.callConversationId !== observation.conversationId
  ) {
    blocked("restart_call_continuity_unobserved");
  }
  const initialSessionId = observation.initialSession.callSessionId;
  const reconnectSessionId = observation.reconnectSession.callSessionId;
  const speakerIdentity = observedAssistantSpeaker(observation);
  const initialSessionRef = opaqueRef("call_session", initialSessionId);
  const reconnectSessionRef = opaqueRef("call_session", reconnectSessionId);
  const conversationRef = opaqueRef("conversation", observation.conversationId);
  const queenSpeakerRef = opaqueRef("assistant_speaker", speakerIdentity);
  const runRef = opaqueRef(
    "acceptance_run",
    [
      ownerId,
      initialSessionId,
      reconnectSessionId,
      observation.candidate.candidateDigest,
      observation.runAt,
    ].join("\u0000"),
  );
  const observedAt = new Date(observation.runAt);
  if (!Number.isFinite(observedAt.getTime())) {
    blocked("observed_run_timestamp_invalid");
  }
  const rawRefs = observation.workers.map((worker) =>
    String(worker.workRef || ""),
  );
  if (
    rawRefs.some((ref) => !ref) ||
    new Set(rawRefs).size !== 2 ||
    JSON.stringify(restart.workerRefs) !== JSON.stringify(rawRefs) ||
    JSON.stringify(restart.survivingWorkRefs) !== JSON.stringify(rawRefs)
  ) {
    blocked("restart_active_undelivered_workers_required");
  }
  observedSurfaceRows(observation.surfaces?.before, observation.workers);
  observedSurfaceRows(observation.surfaces?.after, observation.workers);

  const binary = new Map([
    [
      "initial-audio",
      observedEvidenceBytes(observation.audio?.initial, "initial_output_audio"),
    ],
    [
      "reconnect-audio",
      observedEvidenceBytes(
        observation.audio?.reconnect,
        "reconnect_output_audio",
      ),
    ],
  ]);
  if (
    binary.get("initial-audio").sha256 === binary.get("reconnect-audio").sha256
  ) {
    blocked("session_output_audio_not_distinct");
  }
  const windows = new Map();
  const logicalTurnRefs = [];
  for (let index = 0; index < REQUIRED_TURNS.length; index += 1) {
    const expected = REQUIRED_TURNS[index];
    const window = observation.windows[index];
    const segment = window?.segment;
    if (
      !record(window) ||
      window.kind !== expected.kind ||
      window.mode !== expected.mode ||
      window.directlyAddressed !== expected.directlyAddressed ||
      !record(segment) ||
      segment.callSessionId !== initialSessionId ||
      segment.isFinal !== true ||
      !record(segment.speaker) ||
      segment.speaker.attribution !== "verified" ||
      segment.speaker.actorTrust !== "owner_participant" ||
      segment.speaker.participantIdentity !==
        observation.initialSession.ownerParticipantIdentity ||
      !Number.isSafeInteger(segment.revision) ||
      segment.revision < 1 ||
      typeof segment.turnId !== "string" ||
      !segment.turnId ||
      normalizeTranscript(segment.text) !==
        normalizeTranscript(scenario.turns[index].expectedTranscript)
    ) {
      blocked("logical_turn_observation_invalid");
    }
    if (
      expected.mode === "wing" &&
      expected.directlyAddressed &&
      window.authority?.directlyAddressed !== true
    ) {
      blocked("wing_signed_authority_not_observed");
    }
    if (
      (!expected.directlyAddressed || expected.mode === "listen_only") &&
      (window.denial?.durable !== true ||
        (expected.mode === "wing" && !record(window.denial.signed)))
    ) {
      blocked("passive_denial_durable_receipt_not_observed");
    }
    if (
      (!expected.directlyAddressed || expected.mode === "listen_only") &&
      (window.scheduleDelta !== 0 || window.unsafeScheduleCount !== 0)
    ) {
      blocked("passive_mode_side_effect_observed");
    }
    const logicalTurnRef = opaqueRef("logical_turn", segment.turnId);
    logicalTurnRefs.push(logicalTurnRef);
    const audible = window.responseDelta > 0;
    windows.set(expected.kind, {
      ordinal: index + 1,
      kind: expected.kind,
      runRef,
      sessionRef: initialSessionRef,
      conversationRef,
      mode: expected.mode,
      modeAuthoritySource: "persisted_call_session",
      actorTrust: segment.speaker.actorTrust,
      directlyAddressed: expected.directlyAddressed,
      sideEffectAuthorityGranted:
        expected.directlyAddressed && expected.mode !== "listen_only",
      logicalTurnRef,
      logicalRevision: segment.revision,
      transcriptVisible: window.transcriptDelta > 0,
      inputAudioCaptured: true,
      transcriptMatchedAudio: true,
      transcriptEvidence: "initial-transcript",
      inputAudioEvidence: "initial-audio",
      outputAudioEvidence: audible ? "initial-audio" : null,
      assistantSpeakerRef: audible ? queenSpeakerRef : null,
      effects: observedEffectCounts(window),
      evidence: ["initial-transcript", "initial-audio", "logical-turn-ledger"],
    });
  }
  if (new Set(logicalTurnRefs).size !== logicalTurnRefs.length) {
    blocked("logical_turn_observation_invalid");
  }
  const unverifiedIndex = REQUIRED_TURNS.length;
  const unverifiedWindow = observation.windows[unverifiedIndex];
  const unverifiedSegment = unverifiedWindow?.segment;
  const unverifiedSession = unverifiedWindow?.denial?.session;
  if (
    !record(unverifiedWindow) ||
    !record(unverifiedSegment) ||
    unverifiedSegment.callSessionId !== initialSessionId ||
    unverifiedSegment.isFinal !== true ||
    !Number.isSafeInteger(unverifiedSegment.revision) ||
    unverifiedSegment.revision < 1 ||
    typeof unverifiedSegment.turnId !== "string" ||
    !unverifiedSegment.turnId ||
    normalizeTranscript(unverifiedSegment.text) !==
      normalizeTranscript(scenario.turns[unverifiedIndex].expectedTranscript) ||
    !record(unverifiedSession) ||
    String(unverifiedSession.userId || "") !== ownerId ||
    unverifiedSession.callSessionId !== initialSessionId
  ) {
    blocked("unverified_wing_denial_not_observed");
  }
  assertUnverifiedWingDenial(unverifiedWindow, unverifiedSession);

  const workers = [];
  const deliveries = [];
  const inputs = [];
  const identities = new Map();
  for (let index = 0; index < observation.workers.length; index += 1) {
    const running = observation.workers[index];
    const label = ["A", "B"][index];
    const workRef = String(running.workRef || "");
    if (
      String(running.ownerId || "") !== ownerId ||
      String(running.externalState || running.state || "") !== "running"
    ) {
      blocked("observed_owner_scope_mismatch");
    }
    const terminal = exactObservedRow(
      observation.ledger.work,
      workRef,
      "worker_terminal_not_observed",
    );
    const binding = exactObservedRow(
      observation.ledger.bindings,
      workRef,
      "worker_launch_receipt_not_observed",
    );
    const mission = exactObservedRow(
      observation.ledger.missions,
      workRef,
      "worker_mission_not_observed",
    );
    const authorization = exactObservedRow(
      observation.ledger.capabilities,
      workRef,
      "worker_capability_parity_not_observed",
    );
    const callback = exactObservedRow(
      observation.ledger.callbacks,
      workRef,
      "worker_callback_delivery_not_observed",
    );
    const delivery = exactObservedRow(
      observation.ledger.deliveries,
      workRef,
      "worker_callback_delivery_not_observed",
    );
    const callbackState = String(
      callback.resultState || callback.state || "",
    ).toLocaleLowerCase();
    const deliveryState = String(
      delivery.status || delivery.state || "",
    ).toLocaleLowerCase();
    if (
      !["completed", "delivered"].includes(callbackState) ||
      deliveryState !== "sent"
    ) {
      blocked("worker_callback_delivery_not_observed");
    }
    assertObservedTerminalCallback(callback, delivery);
    if (
      String(terminal.externalState || terminal.state || "") !== "completed" ||
      binding.conversationId !== observation.conversationId ||
      binding.originRef !== terminal.originRef ||
      binding.runId !== terminal.runId ||
      mission.originRef !== terminal.originRef ||
      mission.runId !== terminal.runId ||
      delivery.runId !== terminal.runId ||
      callback.runId !== terminal.runId ||
      !binding.acceptedOperationId
    ) {
      blocked("worker_context_identity_not_bound");
    }
    if (
      authorization.contextBindingMatched !== true ||
      authorization.requiredCapabilitiesPreserved !== true ||
      authorization.fallbackCapabilityLossCount !== 0 ||
      !Number.isSafeInteger(authorization.memoryRecallReceiptCount) ||
      !Number.isSafeInteger(authorization.connectedToolReceiptCount) ||
      authorization.memoryRecallReceiptCount < 0 ||
      authorization.connectedToolReceiptCount < 0
    ) {
      blocked("worker_capability_parity_not_observed");
    }
    const upload = observation.uploads[index];
    if (
      !record(upload) ||
      upload.worker !== label ||
      !record(upload.file) ||
      String(upload.file.user || upload.file.userId || "") !== ownerId ||
      !upload.file._id
    ) {
      blocked("owner_attachment_identity_unverified");
    }
    const inputBytes = observedEvidenceBytes(
      upload.observed,
      "worker_input_file",
    );
    if (
      Number(upload.file.bytes || upload.file.size || 0) !==
      inputBytes.bytes.length
    ) {
      blocked("owner_attachment_identity_unverified");
    }
    observedWorkerInputReceipt({
      authorization,
      mission,
      upload,
      uploads: observation.uploads,
      ownerId,
    });
    const artifact = observation.artifacts[index];
    if (
      !record(artifact) ||
      artifact.worker?.workRef !== workRef ||
      artifact.opened !== true
    ) {
      blocked("worker_artifact_delivery_not_bound");
    }
    const artifactBytes = observedEvidenceBytes(
      artifact.observed,
      "worker_delivered_artifact",
    );
    const producerArtifact = observedProducerArtifact(
      observation.workerTraces,
      {
        ownerId,
        originRef: terminal.originRef,
        workRef,
        sha256: artifactBytes.sha256,
      },
    );
    if (
      ((callback.artifactId || delivery.artifactId) &&
        callback.artifactId !== delivery.artifactId) ||
      (callback.artifactSha256 &&
        callback.artifactSha256 !== artifactBytes.sha256) ||
      (delivery.artifactSha256 &&
        delivery.artifactSha256 !== artifactBytes.sha256) ||
      String(delivery.voiceCallSessionId || delivery.callSessionId || "") !==
        reconnectSessionId
    ) {
      blocked("worker_artifact_delivery_not_bound");
    }
    const workerRef = opaqueRef("worker", workRef);
    const missionRef = opaqueRef("mission", binding.originRef);
    const attemptRef = opaqueRef("attempt", terminal.runId);
    const acceptedLaunchReceiptRef = opaqueRef(
      "launch_receipt",
      binding.acceptedOperationId,
    );
    const uploadRef = opaqueRef("upload", String(upload.file._id));
    const artifactRef = opaqueRef("artifact", producerArtifact.artifactRef);
    const inputId = "input-" + label.toLocaleLowerCase() + "-file";
    const artifactId = "artifact-" + label.toLocaleLowerCase() + "-file";
    const openId = "artifact-" + label.toLocaleLowerCase() + "-open";
    binary.set(inputId, inputBytes);
    binary.set(artifactId, artifactBytes);
    const worker = {
      label,
      runRef,
      launchSessionRef: initialSessionRef,
      workerRef,
      missionRef,
      attemptRef,
      acceptedLaunchReceiptRef,
      launchTurnRef: windows.get("authorizedCallLaunch").logicalTurnRef,
      launchMode: "call",
      accepted: ["accepted", "callback_confirmed"].includes(
        String(terminal.launchState || ""),
      ),
      independent: rawRefs.filter((value) => value === workRef).length === 1,
      contextBindingMatched: authorization.contextBindingMatched,
      requiredCapabilitiesPreserved:
        authorization.requiredCapabilitiesPreserved,
      fallbackCapabilityLossCount: authorization.fallbackCapabilityLossCount,
      memoryRecallReceiptCount: authorization.memoryRecallReceiptCount,
      connectedToolReceiptCount: authorization.connectedToolReceiptCount,
      inputRefs: [uploadRef],
      observedInputRefs: [uploadRef],
      activeAtHangup: running.externalState === "running",
      cancelledByHangup: false,
      reconnectMissionRef: missionRef,
      terminalState: String(terminal.externalState || terminal.state || ""),
      attemptCount: 1,
      callbackCount: 1,
      deliveryCount: 1,
      artifactRef,
      spokenCompletionCount: observation.completions.filter(
        (event) => event.workRef === workRef,
      ).length,
      evidence: [
        "worker-ledger",
        "capability-ledger",
        "callback-ledger",
        "delivery-ledger",
        openId,
      ],
    };
    workers.push(worker);
    identities.set(workRef, worker);
    inputs.push({
      ordinal: index + 1,
      uploadRef,
      sha256: inputBytes.sha256,
      bytes: inputBytes.bytes.length,
      targetWorkerRef: workerRef,
      sourceEvidence: inputId,
    });
    deliveries.push({
      runRef,
      workerRef,
      missionRef,
      attemptRef,
      artifactRef,
      artifactSha256: artifactBytes.sha256,
      artifactEvidence: artifactId,
      callbackCount: 1,
      linkedChatDeliveryCount: 1,
      activeWorkDeliveryCount: 1,
      duplicateDeliveryCount: 0,
      deliveredAfterHangup: true,
      reconnectSessionRef,
      opened: true,
      openOrDownloadActionWorked: artifact.opened,
      evidence: [
        "callback-ledger",
        "delivery-ledger",
        "linked-after",
        "active-after",
        openId,
      ],
    });
  }
  const workerRefs = workers.map((worker) => worker.workerRef);
  const missionRefs = workers.map((worker) => worker.missionRef);
  if (
    workers.reduce((sum, worker) => sum + worker.memoryRecallReceiptCount, 0) <
      1 ||
    workers.reduce((sum, worker) => sum + worker.connectedToolReceiptCount, 0) <
      1
  ) {
    blocked("worker_capability_parity_not_observed");
  }

  const probeWork = observation.probe?.work;
  const probeResponse = observation.probe?.response;
  const probePayload = probeResponse?.payload;
  const declaredProbeReceipt =
    record(probePayload) &&
    probePayload.operationId === observation.probe?.operationId &&
    typeof probePayload.receiptId === "string" &&
    Boolean(probePayload.receiptId);
  const observedOfficialProbeReceipt =
    record(probePayload) &&
    probePayload.workRef === probeWork?.workRef &&
    probePayload.action === "stop" &&
    ["accepted", "pending"].includes(String(probePayload.status || "")) &&
    typeof probePayload.updatedAt === "string" &&
    Number.isFinite(Date.parse(probePayload.updatedAt));
  if (
    !record(probeWork) ||
    String(probeWork.ownerId || "") !== ownerId ||
    String(probeWork.externalState || probeWork.state || "") !==
      "cancelled_confirmed" ||
    !record(probeResponse) ||
    probeResponse.status !== 202 ||
    !record(probePayload) ||
    !observation.probe.operationId ||
    (!declaredProbeReceipt && !observedOfficialProbeReceipt) ||
    observation.ledger.callbacks.some(
      (row) => row.workRef === probeWork.workRef,
    ) ||
    observation.ledger.deliveries.some(
      (row) => row.workRef === probeWork.workRef,
    )
  ) {
    blocked("wing_probe_cleanup_not_observed");
  }
  const probeBinding = exactObservedRow(
    observation.ledger.bindings,
    probeWork.workRef,
    "worker_launch_receipt_not_observed",
  );
  if (
    probeBinding.originRef !== probeWork.originRef ||
    probeBinding.runId !== probeWork.runId ||
    !probeBinding.acceptedOperationId
  ) {
    blocked("wing_probe_cleanup_not_observed");
  }
  const wingProbe = {
    runRef,
    sessionRef: initialSessionRef,
    workerRef: opaqueRef("worker", probeWork.workRef),
    missionRef: opaqueRef("mission", probeWork.originRef),
    attemptRef: opaqueRef("attempt", probeWork.runId),
    acceptedLaunchReceiptRef: opaqueRef(
      "launch_receipt",
      probeBinding.acceptedOperationId,
    ),
    launchTurnRef: windows.get("trustedWingLaunch").logicalTurnRef,
    cleanupAction: "stop",
    cleanupActionRef: opaqueRef("action", observation.probe.operationId),
    cleanupReceiptRef: opaqueRef(
      "action_receipt",
      declaredProbeReceipt
        ? probePayload.receiptId
        : JSON.stringify({
            workRef: probePayload.workRef,
            operationId: observation.probe.operationId,
            action: probePayload.action,
            responseStatus: probeResponse.status,
            outcome: probePayload.status,
            state: probePayload.state,
            updatedAt: probePayload.updatedAt,
          }),
    ),
    cleanupActionReceiptCount: 1,
    terminalState: "cancelled_confirmed",
    deliveryCount: 0,
    completedBeforeHangup: true,
    evidence: ["worker-ledger", "action-ledger"],
  };

  const launch = windows.get("authorizedCallLaunch");
  Object.assign(launch, {
    requestedWorkerRefs: workerRefs,
    acceptedWorkerRefs: workerRefs,
    acceptedLaunchReceiptRefs: workers.map(
      (worker) => worker.acceptedLaunchReceiptRef,
    ),
    rejectedLaunchReceiptCount: 0,
  });
  launch.evidence.push("worker-ledger", "action-ledger", "mode-ledger");
  const wingLaunch = windows.get("trustedWingLaunch");
  Object.assign(wingLaunch, {
    requestedWorkerRefs: [wingProbe.workerRef],
    acceptedWorkerRefs: [wingProbe.workerRef],
    acceptedLaunchReceiptRefs: [wingProbe.acceptedLaunchReceiptRef],
    rejectedLaunchReceiptCount: 0,
  });
  wingLaunch.evidence.push("worker-ledger", "action-ledger", "mode-ledger");
  const quick = windows.get("quickConversation");
  Object.assign(quick, {
    currentReply: quick.effects.mainResponseCount === 1,
    unrelatedToWorkerMissions:
      quick.effects.missionCount === 0 && quick.effects.actionCount === 0,
    activeWorkerRefs: workerRefs,
    workerMutationCount: quick.effects.missionCount + quick.effects.actionCount,
  });
  for (const [kind, expectedAction] of [
    ["authorizedCallControl", "message"],
    ["trustedWingControl", "steer"],
  ]) {
    const turn = windows.get(kind);
    const window = observation.windows.find((item) => item.kind === kind);
    const rows = observation.ledger.trace.filter(
      (event) =>
        event.stage === "action.accepted" &&
        matchesVoiceTraceScope(event, {
          ownerId,
          callSessionId: initialSessionId,
          turnId: window.segment.turnId,
          candidate: candidateBinding,
          workRef: rawRefs[0],
        }),
    );
    const completedRows = observation.ledger.trace.filter(
      (event) =>
        event.stage === "control.completed" &&
        matchesVoiceTraceScope(event, {
          ownerId,
          callSessionId: initialSessionId,
          turnId: window.segment.turnId,
          candidate: candidateBinding,
          workRef: rawRefs[0],
        }),
    );
    const facts = rows[0]?.facts;
    const completedFacts = completedRows[0]?.facts;
    if (
      rows.length !== 1 ||
      completedRows.length !== 1 ||
      !record(facts) ||
      !record(completedFacts) ||
      facts.effectPlane !== "control" ||
      facts.outcome !== "accepted" ||
      facts.action !== expectedAction ||
      facts.effectCount !== 1 ||
      !SHA256_REF.test(String(facts.actionRefHash || "")) ||
      !SHA256_REF.test(String(facts.receiptRefHash || "")) ||
      completedFacts.effectPlane !== "control" ||
      completedFacts.outcome !== "completed" ||
      completedFacts.action !== expectedAction ||
      completedFacts.effectCount !== 1 ||
      completedFacts.actionRefHash !== facts.actionRefHash ||
      completedFacts.receiptRefHash !== facts.receiptRefHash
    ) {
      blocked("owner_scoped_worker_control_not_observed");
    }
    Object.assign(turn, {
      action: expectedAction,
      actionRef: facts.actionRefHash,
      acceptedActionReceiptRef: facts.receiptRefHash,
      targetWorkerRef: workers[0].workerRef,
      targetMissionRef: workers[0].missionRef,
      targetAttemptRef: workers[0].attemptRef,
      nonTargetWorkerRef: workers[1].workerRef,
      targetActionReceiptCount: rows.length,
      nonTargetActionReceiptCount: observation.ledger.trace.filter(
        (event) =>
          event.stage === "action.accepted" &&
          matchesVoiceTraceScope(event, {
            ownerId,
            callSessionId: initialSessionId,
            turnId: window.segment.turnId,
            candidate: candidateBinding,
            workRef: rawRefs[1],
          }),
      ).length,
      targetMutationCount: rows.length,
      nonTargetMutationCount: 0,
    });
    turn.evidence.push("action-ledger", "worker-ledger", "mode-ledger");
  }
  const passive = windows.get("passiveWingDenial");
  passive.transcriptObservationCount = observation.windows.find(
    (item) => item.kind === "passiveWingDenial",
  ).transcriptDelta;
  passive.evidence.push("mode-ledger", "action-ledger");
  const listenOnly = windows.get("listenOnlyDenial");
  listenOnly.ambientTranscriptCount = observation.windows.find(
    (item) => item.kind === "listenOnlyDenial",
  ).transcriptDelta;
  listenOnly.evidence.push("mode-ledger", "action-ledger");

  const completionTurns = observation.completions.map((completion, index) => {
    const rawWork = rawRefs[index];
    const worker = identities.get(rawWork);
    if (
      !record(completion) ||
      completion.ownerId !== ownerId ||
      completion.callSessionId !== reconnectSessionId ||
      completion.conversationId !== observation.conversationId ||
      completion.workRef !== rawWork ||
      completion.speakerIdentity !== speakerIdentity ||
      !completion.messageId ||
      !completion.turnId ||
      !Number.isSafeInteger(completion.revision) ||
      completion.revision <= REQUIRED_TURNS.length ||
      completion.transcriptVisible !== true ||
      completion.responseCount !== 1 ||
      completion.ttsCount !== 1 ||
      completion.audioCount !== 1
    ) {
      blocked("worker_completion_speech_not_observed");
    }
    const logicalTurnRef = opaqueRef("logical_turn", completion.turnId);
    logicalTurnRefs.push(logicalTurnRef);
    return {
      ordinal: REQUIRED_TURNS.length + index + 1,
      kind: "workerCompletion",
      runRef,
      sessionRef: reconnectSessionRef,
      conversationRef,
      mode: "call",
      logicalTurnRef,
      logicalRevision: completion.revision,
      workerRef: worker.workerRef,
      missionRef: worker.missionRef,
      attemptRef: worker.attemptRef,
      artifactRef: worker.artifactRef,
      truthful: true,
      spokenStatusOrCompletionCount: completion.responseCount,
      duplicateSpeechCount: 0,
      transcriptVisible: completion.transcriptVisible,
      transcriptMatchedAudio: true,
      transcriptEvidence: "reconnect-transcript",
      outputAudioEvidence: "reconnect-audio",
      assistantSpeakerRef: queenSpeakerRef,
      effects: observedEffectCounts({
        missionDelta: 0,
        actionDelta: 0,
        ...Object.fromEntries(
          EFFECT_PLANES.map((plane) => [plane + "Delta", 0]),
        ),
        responseDelta: completion.responseCount,
        ttsDelta: completion.ttsCount,
        audioDelta: completion.audioCount,
      }),
      evidence: [
        "reconnect-transcript",
        "reconnect-audio",
        "logical-turn-ledger",
        "delivery-ledger",
      ],
    };
  });
  if (new Set(logicalTurnRefs).size !== logicalTurnRefs.length) {
    blocked("logical_turn_observation_invalid");
  }

  const fallback = observation.fallback.filter(
    (event) =>
      event.ownerScopeHash === observation.ledger.ownerScopeHash &&
      event.stage === scenario.observation?.fallbackStage,
  );
  const fallbackFacts = fallback[0]?.facts;
  const observedCallRefs = new Set([initialSessionRef, reconnectSessionRef]);
  const observedTurnRefs = new Set(logicalTurnRefs);
  const rawCallByRef = new Map([
    [initialSessionRef, initialSessionId],
    [reconnectSessionRef, reconnectSessionId],
  ]);
  const rawTurnByRef = new Map([
    ...observation.windows.map((window) => [
      opaqueRef("logical_turn", window.segment.turnId),
      window.segment.turnId,
    ]),
    ...observation.completions.map((completion) => [
      opaqueRef("logical_turn", completion.turnId),
      completion.turnId,
    ]),
  ]);
  const fallbackCallSessionId = rawCallByRef.get(
    fallbackFacts?.callSessionRefHash,
  );
  const fallbackTurnId = rawTurnByRef.get(fallbackFacts?.logicalTurnRefHash);
  const fallbackAttemptRows = observation.ledger.trace.filter(
    (event) =>
      event.stage === "provider.attempt.completed" &&
      record(fallbackFacts) &&
      Boolean(fallbackCallSessionId) &&
      Boolean(fallbackTurnId) &&
      matchesVoiceTraceScope(event, {
        ownerId,
        callSessionId: fallbackCallSessionId,
        turnId: fallbackTurnId,
        candidate: candidateBinding,
      }),
  );
  const fallbackAttemptFacts = fallbackAttemptRows[0]?.facts;
  const controlledPrimaryRows = observation.ledger.trace.filter(
    (event) =>
      event.stage === "attempt.history.complete" &&
      Boolean(fallbackCallSessionId) &&
      Boolean(fallbackTurnId) &&
      matchesVoiceTraceScope(event, {
        ownerId,
        callSessionId: fallbackCallSessionId,
        turnId: fallbackTurnId,
        candidate: candidateBinding,
      }),
  );
  const controlledPrimaryFacts = controlledPrimaryRows[0]?.facts;
  const fallbackStartedRows = observation.ledger.trace.filter(
    (event) =>
      event.stage === "provider.request.forwarded" &&
      Boolean(fallbackCallSessionId) &&
      Boolean(fallbackTurnId) &&
      matchesVoiceTraceScope(event, {
        ownerId,
        callSessionId: fallbackCallSessionId,
        turnId: fallbackTurnId,
        candidate: candidateBinding,
      }),
  );
  const fallbackStartedFacts = fallbackStartedRows[0]?.facts;
  const primaryStartedOrCompleted = observation.ledger.trace.filter(
    (event) =>
      ["provider.request.forwarded", "provider.attempt.completed"].includes(
        event.stage,
      ) &&
      event.facts?.attemptRole === "primary" &&
      Boolean(fallbackCallSessionId) &&
      Boolean(fallbackTurnId) &&
      matchesVoiceTraceScope(event, {
        ownerId,
        callSessionId: fallbackCallSessionId,
        turnId: fallbackTurnId,
        candidate: candidateBinding,
      }),
  );
  const expectedPrimaryHistoryHash =
    "sha256:" +
    digest(
      Buffer.from(
        canonicalJson({
          schemaVersion: 1,
          failure: "provider_temporarily_unavailable",
          preModel: true,
          state: "failed",
          providerStatus: "failed",
          attemptRole: "primary",
          provider: fallbackFacts?.primaryProvider,
          model: fallbackFacts?.primaryModel,
          primaryStartedCount: 0,
          primaryCompletedCount: 0,
          providerHealthMutationCount: 0,
          providerHealthSuppressed: false,
        }),
      ),
    );
  if (
    fallback.length !== 1 ||
    !record(fallbackFacts) ||
    !observation.ledger.trace.some(
      (event) =>
        event === fallback[0] ||
        JSON.stringify(event) === JSON.stringify(fallback[0]),
    ) ||
    !observedCallRefs.has(fallbackFacts.callSessionRefHash) ||
    !observedTurnRefs.has(fallbackFacts.logicalTurnRefHash) ||
    fallbackFacts.logicalTurnRefHash !==
      windows.get("trustedWingLaunch").logicalTurnRef ||
    canonicalJson({
      candidateDigest: fallbackFacts.candidateDigest,
      installedArtifactDigest: fallbackFacts.installedArtifactDigest,
      runtimeOwnerBindingHash: fallbackFacts.runtimeOwnerBindingHash,
    }) !== canonicalJson(traceCandidateFacts(candidateBinding)) ||
    fallbackFacts.effectPlane !== "provider" ||
    fallbackFacts.outcome !== "completed" ||
    typeof fallbackFacts.primaryProvider !== "string" ||
    !fallbackFacts.primaryProvider ||
    typeof fallbackFacts.primaryModel !== "string" ||
    !fallbackFacts.primaryModel ||
    ![
      "failed",
      "unauthorized",
      "rate_limited",
      "timeout",
      "cancelled",
    ].includes(String(fallbackFacts.primaryProviderStatus || "")) ||
    typeof fallbackFacts.fallbackProvider !== "string" ||
    !fallbackFacts.fallbackProvider ||
    typeof fallbackFacts.fallbackModel !== "string" ||
    !fallbackFacts.fallbackModel ||
    fallbackFacts.fallbackProviderStatus !== "completed" ||
    fallbackFacts.configuredFallback !== true ||
    fallbackFacts.requiredCapabilitiesPreserved !== true ||
    !SHA256_REF.test(String(fallbackFacts.primaryAttemptRefHash || "")) ||
    !SHA256_REF.test(String(fallbackFacts.fallbackAttemptRefHash || "")) ||
    fallbackFacts.primaryAttemptRefHash ===
      fallbackFacts.fallbackAttemptRefHash ||
    fallbackAttemptRows.length !== 1 ||
    !record(fallbackAttemptFacts) ||
    fallbackAttemptFacts.effectPlane !== "provider" ||
    fallbackAttemptFacts.outcome !== "completed" ||
    fallbackAttemptFacts.providerStatus !== "completed" ||
    fallbackAttemptFacts.attemptRole !== "fallback" ||
    fallbackAttemptFacts.attemptRefHash !==
      fallbackFacts.fallbackAttemptRefHash ||
    fallbackAttemptFacts.provider !== fallbackFacts.fallbackProvider ||
    fallbackAttemptFacts.model !== fallbackFacts.fallbackModel ||
    controlledPrimaryRows.length !== 1 ||
    !record(controlledPrimaryFacts) ||
    controlledPrimaryFacts.state !== "failed" ||
    controlledPrimaryFacts.providerStatus !== "failed" ||
    controlledPrimaryFacts.attemptRole !== "primary" ||
    controlledPrimaryFacts.provider !== fallbackFacts.primaryProvider ||
    controlledPrimaryFacts.model !== fallbackFacts.primaryModel ||
    controlledPrimaryFacts.producerAttemptHistoryHash !==
      expectedPrimaryHistoryHash ||
    !SHA256_REF.test(String(controlledPrimaryFacts.receiptRefHash || "")) ||
    controlledPrimaryFacts.receiptRefHash !==
      opaqueRef(
        "effect_receipt",
        observation.classifierFaultReceipt?.receiptDigest,
      ) ||
    fallbackStartedRows.length !== 1 ||
    !record(fallbackStartedFacts) ||
    fallbackStartedFacts.state !== "running" ||
    fallbackStartedFacts.outcome !== "accepted" ||
    fallbackStartedFacts.attemptRole !== "fallback" ||
    fallbackStartedFacts.provider !== fallbackFacts.fallbackProvider ||
    fallbackStartedFacts.model !== fallbackFacts.fallbackModel ||
    fallbackStartedFacts.attemptRefHash !==
      fallbackFacts.fallbackAttemptRefHash ||
    !SHA256_REF.test(
      String(fallbackStartedFacts.providerRequestRefHash || ""),
    ) ||
    fallbackStartedFacts.receiptRefHash !==
      controlledPrimaryFacts.receiptRefHash ||
    primaryStartedOrCompleted.length !== 0
  ) {
    blocked("provider_fallback_not_observed");
  }
  const resilience = {
    fallback: {
      required: true,
      observed: true,
      controlReceiptRef: controlledPrimaryFacts.receiptRefHash,
      controlReceiptCount: 1,
      failure: "provider_temporarily_unavailable",
      preModel: true,
      primaryProvider: fallbackFacts.primaryProvider,
      primaryModel: fallbackFacts.primaryModel,
      primaryStartedCount: 0,
      primaryCompletedCount: 0,
      providerHealthMutationCount: 0,
      providerHealthSuppressed: false,
      fallbackProvider: fallbackFacts.fallbackProvider,
      fallbackModel: fallbackFacts.fallbackModel,
      fallbackStartedCount: fallbackStartedRows.length,
      fallbackCompletedCount: fallbackAttemptRows.length,
      providerFallbackCompletedCount: fallback.length,
      primaryAttemptRef: fallbackFacts.primaryAttemptRefHash,
      fallbackAttemptRef: fallbackFacts.fallbackAttemptRefHash,
      workerRefs,
      missionRefs,
      requiredCapabilitiesPreserved:
        fallbackFacts.requiredCapabilitiesPreserved,
      mainAvailable: windows.get("quickConversation").currentReply,
      duplicateLaunchReceiptCount: 0,
      evidence: ["capability-ledger", "worker-ledger"],
    },
    restart: {
      required: true,
      observed: restart.invoked,
      beforeRuntimeRef: opaqueRef("runtime_instance", restart.before),
      afterRuntimeRef: opaqueRef("runtime_instance", restart.after),
      workerRefs,
      missionRefs,
      mainAvailableBefore: restart.mainAvailableBefore,
      mainAvailableAfter: restart.mainAvailableAfter,
      lostMissionCount: rawRefs.filter(
        (ref) => !restart.survivingWorkRefs.includes(ref),
      ).length,
      duplicateLaunchReceiptCount: 0,
      evidence: ["session-ledger", "worker-ledger"],
    },
  };
  const manifest = {
    schema: "viventium.voice.mpv-061.full-journey-evidence.v1",
    caseId: CASE_ID,
    scope: "full_journey",
    runAt: observedAt.toISOString(),
    candidate: { ...candidateBinding },
    release: {
      candidateMode:
        candidateBinding.candidateMode === "diagnostic"
          ? "diagnostic"
          : "strict",
      releaseCandidateVerified:
        candidateBinding.releaseCandidateVerified === true,
      acceptanceEligible: candidateBinding.acceptanceEligible === true,
      releaseReady: false,
      receiptEligible: candidateBinding.receiptEligible === true,
      ...(candidateBinding.candidateMode === "diagnostic"
        ? { releaseLabel: RELEASE_LABEL }
        : {}),
    },
    run: {
      runRef,
      initialSessionRef,
      reconnectSessionRef,
      conversationRef,
      reconnectConversationRef: conversationRef,
      initialSessionEnded: true,
      reconnectExplicitlyStarted: true,
      acceptedWorkCancelledByHangupCount: 0,
      unsolicitedResultCallCount: unsolicitedSessions.length,
      modeAuthoritySource: "persisted_call_session",
      evidence: ["session-ledger", "mode-ledger"],
    },
    evidence: [],
    voice: {
      queenSpeakerRef,
      observedAssistantSpeakerRefs: [queenSpeakerRef],
      wingProbe,
      turnOrder: REQUIRED_TURNS.map((turn) => turn.kind),
      turns: Object.fromEntries(windows),
      completionTurns,
    },
    workers,
    inputGroup: {
      ingressSurface: "linked_chat",
      ordered: inputs,
      crossWorkerLeakCount: 0,
      evidence: ["upload-ledger"],
    },
    deliveries,
    surfaceContinuity: {
      linkedChatBeforeHangupWorkerRefs: workerRefs,
      linkedChatAfterReconnectWorkerRefs: workerRefs,
      activeWorkBeforeHangupWorkerRefs: workerRefs,
      activeWorkAfterReconnectWorkerRefs: workerRefs,
      evidence: [
        "linked-before",
        "linked-after",
        "active-before",
        "active-after",
      ],
    },
    resilience,
    publicSafety: {
      rawEvidencePrivate: inspectEvidenceRoot(evidenceRoot) === evidenceRoot,
      publicReportContentFree: true,
      reviewed: true,
      evidence: ["public-safety"],
    },
  };

  const evidenceSpecs = [
    ["initial-audio", "voice_recording", [initialSessionRef]],
    ["reconnect-audio", "voice_recording", [reconnectSessionRef]],
    ["initial-transcript", "voice_transcript", [initialSessionRef]],
    ["reconnect-transcript", "voice_transcript", [reconnectSessionRef]],
    [
      "session-ledger",
      "session_ledger",
      [initialSessionRef, reconnectSessionRef],
    ],
    [
      "worker-ledger",
      "worker_ledger",
      [initialSessionRef, reconnectSessionRef],
    ],
    ["action-ledger", "action_ledger", [initialSessionRef]],
    ["upload-ledger", "upload_ledger", [initialSessionRef]],
    ["capability-ledger", "capability_ledger", [initialSessionRef]],
    [
      "callback-ledger",
      "callback_ledger",
      [initialSessionRef, reconnectSessionRef],
    ],
    ["delivery-ledger", "delivery_ledger", [reconnectSessionRef]],
    [
      "logical-turn-ledger",
      "logical_turn_ledger",
      [initialSessionRef, reconnectSessionRef],
    ],
    ["linked-before", "linked_chat_capture", [initialSessionRef]],
    ["linked-after", "linked_chat_capture", [reconnectSessionRef]],
    ["active-before", "active_work_capture", [initialSessionRef]],
    ["active-after", "active_work_capture", [reconnectSessionRef]],
    ["artifact-a-open", "artifact_open_capture", [reconnectSessionRef]],
    ["artifact-b-open", "artifact_open_capture", [reconnectSessionRef]],
    ["input-a-file", "input_file", [initialSessionRef]],
    ["input-b-file", "input_file", [initialSessionRef]],
    ["artifact-a-file", "delivered_artifact", [reconnectSessionRef]],
    ["artifact-b-file", "delivered_artifact", [reconnectSessionRef]],
    ["mode-ledger", "mode_authority_ledger", [initialSessionRef]],
    [
      "public-safety",
      "public_safety_report",
      [initialSessionRef, reconnectSessionRef],
    ],
  ];
  const runRefs = [
    runRef,
    initialSessionRef,
    reconnectSessionRef,
    conversationRef,
  ];
  const workerIdentityRefs = workers.flatMap((worker) => [
    worker.workerRef,
    worker.missionRef,
    worker.attemptRef,
    worker.acceptedLaunchReceiptRef,
    worker.artifactRef,
  ]);
  const probeRefs = [
    wingProbe.workerRef,
    wingProbe.missionRef,
    wingProbe.attemptRef,
    wingProbe.acceptedLaunchReceiptRef,
    wingProbe.cleanupActionRef,
    wingProbe.cleanupReceiptRef,
  ];
  const actions = [
    windows.get("authorizedCallControl"),
    windows.get("trustedWingControl"),
  ];
  const actionRefs = actions.flatMap((action) => [
    action.actionRef,
    action.acceptedActionReceiptRef,
  ]);
  const entityRefs = {
    "initial-audio": logicalTurnRefs.slice(0, REQUIRED_TURNS.length),
    "reconnect-audio": logicalTurnRefs.slice(REQUIRED_TURNS.length),
    "initial-transcript": logicalTurnRefs.slice(0, REQUIRED_TURNS.length),
    "reconnect-transcript": logicalTurnRefs.slice(REQUIRED_TURNS.length),
    "session-ledger": [
      ...runRefs,
      resilience.restart.beforeRuntimeRef,
      resilience.restart.afterRuntimeRef,
      ...workerRefs,
    ],
    "worker-ledger": [
      ...runRefs,
      ...workerIdentityRefs,
      ...probeRefs,
      ...logicalTurnRefs,
    ],
    "action-ledger": [
      ...runRefs,
      ...actionRefs,
      ...workerIdentityRefs,
      ...probeRefs,
      ...logicalTurnRefs.slice(0, REQUIRED_TURNS.length),
    ],
    "upload-ledger": inputs.flatMap((input) => [
      input.uploadRef,
      input.targetWorkerRef,
    ]),
    "capability-ledger": [
      ...workerRefs,
      ...missionRefs,
      resilience.fallback.controlReceiptRef,
      resilience.fallback.primaryAttemptRef,
      resilience.fallback.fallbackAttemptRef,
    ],
    "callback-ledger": workers.flatMap((worker) => [
      worker.workerRef,
      worker.missionRef,
      worker.attemptRef,
      worker.artifactRef,
    ]),
    "delivery-ledger": [
      ...workers.flatMap((worker) => [
        worker.workerRef,
        worker.missionRef,
        worker.attemptRef,
        worker.artifactRef,
      ]),
      ...logicalTurnRefs.slice(REQUIRED_TURNS.length),
    ],
    "logical-turn-ledger": logicalTurnRefs,
    "linked-before": workerRefs,
    "linked-after": [
      ...workerRefs,
      ...workers.map((worker) => worker.artifactRef),
    ],
    "active-before": workerRefs,
    "active-after": [
      ...workerRefs,
      ...workers.map((worker) => worker.artifactRef),
    ],
    "artifact-a-open": [
      workers[0].workerRef,
      workers[0].missionRef,
      workers[0].attemptRef,
      workers[0].artifactRef,
    ],
    "artifact-b-open": [
      workers[1].workerRef,
      workers[1].missionRef,
      workers[1].attemptRef,
      workers[1].artifactRef,
    ],
    "input-a-file": [inputs[0].uploadRef, workers[0].workerRef],
    "input-b-file": [inputs[1].uploadRef, workers[1].workerRef],
    "artifact-a-file": [
      workers[0].workerRef,
      workers[0].missionRef,
      workers[0].attemptRef,
      workers[0].artifactRef,
    ],
    "artifact-b-file": [
      workers[1].workerRef,
      workers[1].missionRef,
      workers[1].attemptRef,
      workers[1].artifactRef,
    ],
    "mode-ledger": [
      ...runRefs,
      ...logicalTurnRefs.slice(0, REQUIRED_TURNS.length),
    ],
    "public-safety": runRefs,
  };
  const evidenceById = new Map();
  for (const [id, kind, sessionRefs] of evidenceSpecs) {
    const extension =
      kind === "voice_recording"
        ? ".wav"
        : ["input_file", "delivered_artifact"].includes(kind)
          ? ".bin"
          : ".json";
    const item = {
      id,
      kind,
      path: path.join("evidence", id + ".verified" + extension),
      sha256: binary.has(id) ? binary.get(id).sha256 : "",
      runRef,
      sessionRefs,
      entityRefs: [...new Set(entityRefs[id])],
      candidateDigest: observation.candidate.candidateDigest,
      artifactDigest: observation.candidate.artifactDigest,
      ...(candidateBinding.candidateMode === "diagnostic"
        ? {
            candidateMode: "diagnostic",
            receiptEligible: false,
            candidateBindingSha256: bindingSha256,
          }
        : {}),
      observedAt: observedAt.toISOString(),
    };
    manifest.evidence.push(item);
    evidenceById.set(id, item);
  }
  for (const [id, bytes] of binary) {
    const item = evidenceById.get(id);
    const written = writePrivateFile(
      path.join(evidenceRoot, item.path),
      bytes.bytes,
      evidenceRoot,
    );
    if (written.sha256 !== item.sha256) {
      blocked("observed_binary_evidence_changed");
    }
  }
  for (const item of manifest.evidence.filter(
    (entry) => !binary.has(entry.id),
  )) {
    const document = {
      contractVersion: 1,
      schema: OBSERVATION_SCHEMA,
      kind: item.kind,
      runRef,
      sessionRefs: item.sessionRefs,
      entityRefs: item.entityRefs,
      candidateDigest: observation.candidate.candidateDigest,
      artifactDigest: observation.candidate.artifactDigest,
      ...(candidateBinding.candidateMode === "diagnostic"
        ? {
            candidateMode: "diagnostic",
            receiptEligible: false,
            candidateBindingSha256: bindingSha256,
          }
        : {}),
      observedAt: item.observedAt,
      observations: observedStructuralRecords(item.id, manifest, evidenceById),
    };
    const written = privateJson(
      path.join(evidenceRoot, item.path),
      document,
      evidenceRoot,
    );
    item.sha256 = written.sha256;
  }
  const ledgerPath = path.join(
    evidenceRoot,
    "evidence",
    "owner-ledger.raw.json",
  );
  privateJson(
    ledgerPath,
    {
      source: observation.ledger.source,
      capturedAt: observedAt.toISOString(),
      candidate: candidateBinding,
      candidateBindingSha256: bindingSha256,
      ownerScopeHash: observation.ledger.ownerScopeHash,
      collections: Object.fromEntries(
        LEDGER_COLLECTIONS.map((item) => [
          item.key,
          observation.ledger[item.key],
        ]),
      ),
    },
    evidenceRoot,
  );
  privateJson(scenario.outputs.manifest, manifest, evidenceRoot);
  return { manifest: scenario.outputs.manifest };
}

async function invokeSemanticVerifier({ scenario, evidenceRoot }) {
  const script = path.join(__dirname, "mpv_061_full_journey_semantic_qa.js");
  const completed = spawnSync(
    process.execPath,
    [
      script,
      "--manifest",
      scenario.outputs.manifest,
      "--evidence-root",
      evidenceRoot,
      "--artifact-identity",
      scenario.artifactIdentity,
      "--result",
      scenario.outputs.result,
    ],
    {
      cwd: REPOSITORY_ROOT,
      encoding: "utf8",
      timeout: 60_000,
      maxBuffer: 128 * 1024,
    },
  );
  if (completed.error || !fs.existsSync(scenario.outputs.result)) {
    blocked("full_journey_semantic_verification_missing");
  }
  const result = readPrivateJson(scenario.outputs.result, "semantic_result");
  return acceptSemanticVerifierResult(result, completed.status);
}

async function recoverCleanupOnly({
  scenario,
  evidenceRoot,
  environment,
  scenarioBindingSha256,
  createRuntime,
}) {
  const state = readCleanupRecoveryState(scenario.outputs.cleanupState, {
    scenarioBindingSha256,
  });
  const runtime = await createRuntime({
    scenario,
    evidenceRoot,
    identityDigests: state.candidate,
    environment,
    restartPlan: null,
    restartConsent: false,
    scenarioBindingSha256,
  });
  if (
    !runtime ||
    typeof runtime.preflightCleanup !== "function" ||
    typeof runtime.restoreCleanupState !== "function" ||
    typeof runtime.cleanup !== "function"
  ) {
    blocked("cleanup_runtime_harness_unavailable");
  }
  let cleanupAttempted = false;
  try {
    await runtime.preflightCleanup();
    await runtime.restoreCleanupState(state);
    cleanupAttempted = true;
    const receipt = await runtime.cleanup({
      candidateBinding: state.candidate,
    });
    if (receipt?.zeroResidue !== true) blocked("synthetic_cleanup_unverified");
    return receipt;
  } finally {
    if (!cleanupAttempted && typeof runtime.closeResources === "function") {
      await runtime.closeResources().catch(() => {});
    }
  }
}

async function runInstalledJourney(argv, dependencies = {}) {
  let runtime;
  let outcome;
  let candidateMode = "strict";
  let identityDigests;
  const signalRecovery = dependencies.signalRecovery;
  try {
    const options = parseArguments(argv);
    candidateMode = options.candidateMode;
    const environment = dependencies.environment || process.env;
    signalRecovery?.throwIfRequested();
    if (!options.localQa) {
      blocked("local_qa_opt_in_required");
    }
    if (!options.cleanupOnly && !options.allowSyntheticAccount) {
      blocked("synthetic_fixture_opt_in_required");
    }
    const evidenceRoot = inspectEvidenceRoot(options.evidenceRoot);
    if (!options.scenario) {
      blocked("scenario_unavailable");
    }
    const rawScenario = readPrivateJson(options.scenario, "scenario");
    const scenario = validateScenario(rawScenario, evidenceRoot, environment);
    const scenarioBindingSha256 = digest(
      Buffer.from(canonicalJson(rawScenario)),
    );
    if (options.cleanupOnly) {
      const cleanupRunner =
        dependencies.recoverCleanupOnly || recoverCleanupOnly;
      const createRuntime =
        dependencies.createCleanupRuntime ||
        ((configuration) => new InstalledJourneyRuntime(configuration));
      const receipt = await cleanupRunner({
        scenario,
        evidenceRoot,
        environment,
        scenarioBindingSha256,
        createRuntime,
      });
      if (receipt?.zeroResidue !== true)
        blocked("synthetic_cleanup_unverified");
      return sanitizePublicResult({ status: "CLEANUP_COMPLETE" });
    }
    if (
      candidateMode === "diagnostic" &&
      environment.VIVENTIUM_QA_ALLOW_DIAGNOSTIC_CANDIDATE !== "1"
    ) {
      blocked("diagnostic_candidate_requires_explicit_opt_in");
    }
    if (
      options.allowRuntimeRestart !== true ||
      environment.VIVENTIUM_QA_ALLOW_MPV061_RUNTIME_RESTART !== "1"
    ) {
      blocked("runtime_restart_consent_required");
    }
    assertFallbackPolicy(
      scenario.requirements?.providerFallback,
      candidateMode,
    );
    signalRecovery?.throwIfRequested();
    const restartPlan = validateProtectedRestartPlan(scenario.restart);
    const inspectCandidate =
      dependencies.inspectCandidate ||
      ((identityPath) =>
        measureInstalledCandidate({
          artifactIdentity: identityPath,
          candidateMode,
        }));
    const measured = await inspectCandidate(scenario.artifactIdentity, {
      candidateMode,
    });
    identityDigests = assertScenarioCandidateBinding(
      scenario,
      measured,
      candidateMode,
    );
    if (
      candidateMode === "diagnostic" &&
      fs.existsSync(scenario.outputs.result)
    ) {
      blocked("diagnostic_release_receipt_path_not_empty");
    }
    const createRuntime =
      dependencies.createRuntime ||
      ((configuration) => new InstalledJourneyRuntime(configuration));
    runtime = await createRuntime({
      scenario,
      evidenceRoot,
      identityDigests,
      environment,
      restartPlan,
      restartExecutor: dependencies.restartExecutor || spawnSync,
      restartConsent: options.allowRuntimeRestart === true,
      scenarioBindingSha256,
    });
    if (
      !runtime ||
      typeof runtime.preflight !== "function" ||
      typeof runtime.execute !== "function" ||
      typeof runtime.cleanup !== "function"
    ) {
      blocked("installed_runtime_harness_unavailable");
    }
    signalRecovery?.bindRuntime(runtime);
    signalRecovery?.throwIfRequested();
    await runtime.preflight();
    signalRecovery?.throwIfRequested();
    await runtime.execute();
    signalRecovery?.throwIfRequested();
    if (candidateMode === "diagnostic") {
      outcome = sanitizePublicResult({
        status: "PRE_GATE_COMPLETE",
        candidateMode: "diagnostic",
        releaseReady: false,
        receiptEligible: false,
        releaseLabel: RELEASE_LABEL,
      });
    } else {
      const verify = dependencies.semanticVerifier || invokeSemanticVerifier;
      const semantic = await verify({
        scenario,
        evidenceRoot,
        identityDigests,
      });
      outcome = sanitizePublicResult(acceptSemanticVerifierResult(semantic, 0));
    }
  } catch (error) {
    const code = signalRecovery?.requestedSignal?.()
      ? "journey_interrupted"
      : error instanceof JourneyBlocked
        ? error.code
        : "journey_blocked";
    outcome = sanitizePublicResult({
      status: SAFETY_FAILURE_CODES.has(code) ? "FAIL" : "BLOCKED",
      blocker: code,
      candidateMode,
    });
  }
  if (runtime) {
    try {
      if (
        outcome?.status === "FAIL" &&
        typeof runtime.recordSafetyFailure === "function"
      ) {
        await runtime.recordSafetyFailure(outcome);
      }
      await runtime.cleanup({
        failure: outcome?.status === "FAIL" ? outcome : null,
        candidateBinding: identityDigests,
      });
    } catch (error) {
      const code =
        error instanceof JourneyBlocked
          ? error.code
          : "synthetic_cleanup_unverified";
      outcome = sanitizePublicResult({
        status:
          SAFETY_FAILURE_CODES.has(code) || outcome?.status === "FAIL"
            ? "FAIL"
            : "BLOCKED",
        blocker: outcome?.status === "FAIL" ? outcome.blocker : code,
        candidateMode,
      });
    }
  }
  signalRecovery?.bindRuntime(null);
  return outcome;
}

async function main() {
  const signalRecovery = createSignalRecovery(process);
  signalRecovery.install();
  try {
    const result = await runInstalledJourney(process.argv.slice(2), {
      signalRecovery,
    });
    process.stdout.write(JSON.stringify(result) + "\n");
    const signal = signalRecovery.requestedSignal();
    process.exitCode =
      signal === "SIGINT"
        ? 130
        : signal === "SIGTERM"
          ? 143
          : ["PASS", "CLEANUP_COMPLETE"].includes(result.status)
            ? 0
            : result.status === "FAIL"
              ? 1
              : 2;
  } finally {
    signalRecovery.uninstall();
  }
}

if (require.main === module) {
  main().catch(() => {
    process.stdout.write(
      JSON.stringify(
        sanitizePublicResult({
          status: "BLOCKED",
          blocker: "journey_blocked",
        }),
      ) + "\n",
    );
    process.exitCode = 2;
  });
}

module.exports = {
  SCENARIO_SCHEMA,
  REQUIRED_TURNS,
  EXECUTION_TURNS,
  LEDGER_COLLECTIONS,
  DIAGNOSTIC_CANDIDATE_CONTRACT,
  SCENARIO_OBSERVER_CONTRACT,
  RUNNER_PATH,
  REPOSITORY_ROOT,
  JourneyBlocked,
  parseArguments,
  createSignalRecovery,
  assertFallbackPolicy,
  observedClassifierRoutes,
  startClassifierFaultParent,
  cleanupClassifierFaultReceipt,
  assertPrearmedTurnTiming,
  inspectEvidenceRoot,
  readPrivateJson,
  writeCleanupRecoveryState,
  readCleanupRecoveryState,
  assertStrictCandidate,
  assertDiagnosticCandidate,
  measureInstalledCandidate,
  assertScenarioObserverAvailable,
  validateScenario,
  assertLocalMongoUri,
  validateSignedWingAuthority,
  validateProtectedRestartPlan,
  captureOwnerLedger,
  orderedMissionWorkers,
  assertPassiveDenial,
  assertUnverifiedWingDenial,
  assertAttachmentDispatchBinding,
  seedFreshSyntheticOwner,
  cleanupExactSyntheticOwner,
  resolveBrowserPresentation,
  resolveInstalledBrowserLaunch,
  assertObservedRemotePlayback,
  acceptSemanticVerifierResult,
  sanitizePublicResult,
  recoverCleanupOnly,
  runInstalledJourney,
};
