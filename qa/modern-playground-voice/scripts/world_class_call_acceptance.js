#!/usr/bin/env node
/*
 * World-class call endurance acceptance harness.
 *
 * Runtime inputs and raw evidence stay in an explicitly selected private output root. The compact
 * result is deliberately content-free: it contains only case IDs, counts, timings, gate states,
 * and bounded error codes. This script never starts or restarts the Viventium runtime.
 */

const crypto = require("crypto");
const fs = require("fs");
const os = require("os");
const path = require("path");
const { execFile, execFileSync } = require("child_process");
const { createRequire } = require("module");

const ROOT = path.resolve(__dirname, "..", "..", "..");
const PLAN = Object.freeze({
  modeSwitches: 100,
  reconnects: 50,
  audibleMinutes: 65,
  soakMinutes: 120,
});
const MODES = Object.freeze(["call", "wing", "listen_only"]);
const CALL_CAPABILITY_HEADER = "X-VIVENTIUM-CALL-CAPABILITY";
const CALL_CAPABILITY_STORAGE_PREFIX = "viventium.call.capability.v1:";
const SAFE_BROWSER_CAPABILITY = /^[A-Za-z0-9_-]{43}$/;
const ACTIVE_TASK_STATES = new Set([
  "queued",
  "running",
  "needs_input",
  "recovering",
  "cancelling",
]);
const TERMINAL_TASK_STATES = new Set([
  "completed",
  "failed",
  "cancelled_confirmed",
  "cancelled_unenforceable",
]);
const HOP_ORDER = Object.freeze([
  "utterance_end",
  "gateway_dispatch",
  "agent_start",
  "tool_start",
  "tool_end",
  "first_model_token",
  "tts_first_byte",
  "audio_output",
]);
const REQUIRED_BEHAVIOR_PATHS = Object.freeze([
  "oneClickAlreadyGranted",
  "firstUseBrowserPermissionOnly",
  "microphoneDeniedInlineRecovery",
  "authExpiredInlineRecovery",
  "invalidSignatureRecovery",
  "noRouteInlineRecovery",
  "gatewayUnavailableRecovery",
  "sttFailureClassified",
  "llmFailureClassified",
  "ttsFailureClassified",
  "toolFailureClassified",
  "livekitFailureClassified",
  "sharedMicOwnerAbstention",
  "speakerRevisionAfterSecondSpeaker",
  "separateTrackJoinLeaveAttribution",
  "interruptionStopsSpeechWorkContinues",
  "cooperativeCancellation",
  "unenforceableCancellation",
  "alreadyCompletedCancellationTruthful",
  "cancelRaceIdempotent",
  "hangupContinuesLinkedChat",
  "listenOnlyZeroAuthorityPlanes",
  "wingGuestZeroSideEffectAuthority",
  "needsInputRoundTrip",
  "retryRoundTrip",
  "postCallMemoryHardening",
  "conversationDeleteExport",
  "localOnlyUnknownDegradation",
]);
const ESCAPED_REGRESSION_GATES = Object.freeze({
  rawSessionIdWithoutBrowserCapabilityRejected:
    "raw-session-id-browser-capability",
  suppressionBarrierPreservedAfter1001Tasks:
    "suppression-barrier-task-pressure",
  hungOwnerCancelAckWithin250Ms: "hung-owner-cancel-ack",
  malformedTaskSnapshotFailsVisible: "malformed-task-snapshot-fail-visible",
  apiRestartPreservesBarrierAndReplay: "api-restart-barrier-replay",
  speakerHistoryBeyond4096Accessible: "speaker-history-over-4096-access",
});

function parseArgs(argv) {
  const args = {
    selfTest: false,
    outputRoot: "",
    result: "",
    config: "",
    profile: "switches",
    headed: false,
    allowCommandActions: false,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const item = argv[index];
    const next = argv[index + 1];
    if (item === "--self-test") {
      args.selfTest = true;
    } else if (item === "--output-root") {
      args.outputRoot = next || "";
      index += 1;
    } else if (item === "--result") {
      args.result = next || "";
      index += 1;
    } else if (item === "--config") {
      args.config = next || "";
      index += 1;
    } else if (item === "--profile") {
      args.profile = next || args.profile;
      index += 1;
    } else if (item === "--headed") {
      args.headed = true;
    } else if (item === "--allow-command-actions") {
      args.allowCommandActions = true;
    } else {
      throw new Error(`unknown argument: ${item}`);
    }
  }
  if (!args.outputRoot) {
    throw new Error(
      "--output-root is required and must point outside the public repository",
    );
  }
  args.outputRoot = path.resolve(args.outputRoot);
  assertPrivateOutputRoot(args.outputRoot);
  if (!["switches", "reconnects", "audible", "soak"].includes(args.profile)) {
    throw new Error("--profile must be switches, reconnects, audible, or soak");
  }
  if (!args.selfTest && !args.config) {
    throw new Error("--config is required for a runtime acceptance run");
  }
  if (args.config) {
    args.config = path.resolve(args.config);
    assertOutsidePublicRepo(args.config, "--config");
  }
  args.result = args.result
    ? path.resolve(args.result)
    : path.join(args.outputRoot, "sanitized-result.v1.json");
  assertUnderOutputRoot(args.result, args.outputRoot, "--result");
  return args;
}

function assertOutsidePublicRepo(value, label) {
  const relative = path.relative(ROOT, value);
  if (!relative.startsWith("..") && !path.isAbsolute(relative)) {
    throw new Error(`${label} must stay outside the public repository`);
  }
}

function assertPrivateOutputRoot(outputRoot) {
  if (outputRoot === path.parse(outputRoot).root) {
    throw new Error("--output-root cannot be a filesystem root");
  }
  assertOutsidePublicRepo(outputRoot, "--output-root");
}

function assertUnderOutputRoot(value, outputRoot, label) {
  const relative = path.relative(outputRoot, value);
  if (relative.startsWith("..") || path.isAbsolute(relative)) {
    throw new Error(`${label} must stay under --output-root`);
  }
}

function shortHash(value) {
  return crypto
    .createHash("sha256")
    .update(String(value || ""))
    .digest("hex")
    .slice(0, 12);
}

function percentile(values, fraction) {
  if (!values.length) {
    return null;
  }
  const ordered = [...values].sort((left, right) => left - right);
  const index = Math.max(0, Math.ceil(ordered.length * fraction) - 1);
  return Math.round(ordered[index] * 1000) / 1000;
}

function metricSummary(values) {
  const finite = asArray(values)
    .map(Number)
    .filter((value) => Number.isFinite(value) && value >= 0);
  return {
    count: finite.length,
    p50: percentile(finite, 0.5),
    p95: percentile(finite, 0.95),
    max: finite.length ? Math.max(...finite) : null,
  };
}

function canonicalJson(value) {
  if (Array.isArray(value)) {
    return `[${value.map(canonicalJson).join(",")}]`;
  }
  if (value && typeof value === "object") {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function normalizeTaskOwnerCapabilityInventory(value) {
  if (
    !value ||
    value.authoritative !== true ||
    value.source !== "runtime_voice_task_owner_registry" ||
    !Array.isArray(value.owners) ||
    value.owners.length > 64
  ) {
    return null;
  }
  const owners = [];
  for (const owner of value.owners) {
    if (
      !owner ||
      typeof owner.kind !== "string" ||
      !/^[a-z0-9_:-]{1,80}$/i.test(owner.kind) ||
      typeof owner.acceptsInput !== "boolean"
    ) {
      return null;
    }
    owners.push({ kind: owner.kind, acceptsInput: owner.acceptsInput });
  }
  return owners;
}

function normalizeTaskSnapshot(payload) {
  const events = asArray(payload?.events);
  return events.filter(
    (event) =>
      event &&
      event.version === 1 &&
      typeof event.taskId === "string" &&
      Number.isSafeInteger(event.sequence),
  );
}

function normalizeSpeakerPage(payload) {
  return asArray(payload?.segments).filter(
    (segment) =>
      segment &&
      segment.version === 1 &&
      typeof segment.segmentId === "string" &&
      Number.isSafeInteger(segment.sequence) &&
      Number.isSafeInteger(segment.revision),
  );
}

function duplicateCount(items, keyOf) {
  const seen = new Set();
  let duplicates = 0;
  for (const item of items) {
    const key = keyOf(item);
    if (seen.has(key)) {
      duplicates += 1;
    }
    seen.add(key);
  }
  return duplicates;
}

function auditReplay(previous, current) {
  const previousTasks = new Map(
    previous.tasks.map((item) => [item.taskId, item]),
  );
  const currentTasks = new Map(
    current.tasks.map((item) => [item.taskId, item]),
  );
  const previousSegments = new Map(
    previous.segments.map((item) => [item.segmentId, item]),
  );
  const currentSegments = new Map(
    current.segments.map((item) => [item.segmentId, item]),
  );
  let lostTasks = 0;
  let regressedTasks = 0;
  let changedStableTasks = 0;
  let lostSegments = 0;
  let regressedSegments = 0;
  let changedStableSegments = 0;

  for (const [taskId, prior] of previousTasks) {
    const next = currentTasks.get(taskId);
    if (!next) {
      lostTasks += 1;
      continue;
    }
    if (next.sequence < prior.sequence) {
      regressedTasks += 1;
    } else if (
      next.sequence === prior.sequence &&
      canonicalJson(next) !== canonicalJson(prior)
    ) {
      changedStableTasks += 1;
    }
    if (
      TERMINAL_TASK_STATES.has(prior.state) &&
      ACTIVE_TASK_STATES.has(next.state)
    ) {
      regressedTasks += 1;
    }
  }

  for (const [segmentId, prior] of previousSegments) {
    const next = currentSegments.get(segmentId);
    if (!next) {
      lostSegments += 1;
      continue;
    }
    if (next.revision < prior.revision || next.sequence !== prior.sequence) {
      regressedSegments += 1;
    } else if (
      next.revision === prior.revision &&
      canonicalJson(next) !== canonicalJson(prior)
    ) {
      changedStableSegments += 1;
    }
  }

  const resultRefs = current.tasks
    .map((task) => task.resultRef || task.resultMessageId || "")
    .filter(Boolean);
  return {
    lostTasks,
    duplicateTasks: duplicateCount(current.tasks, (task) => task.taskId),
    regressedTasks,
    changedStableTasks,
    lostSegments,
    duplicateSegments: duplicateCount(
      current.segments,
      (segment) => segment.segmentId,
    ),
    regressedSegments,
    changedStableSegments,
    duplicateResults: duplicateCount(resultRefs, (value) => value),
  };
}

function addReplayTotals(target, delta) {
  for (const key of Object.keys(target)) {
    target[key] += Number(delta[key] || 0);
  }
}

function replayPassed(replay) {
  return Object.values(replay).every((value) => value === 0);
}

function extractVoiceHopTraces(text) {
  const traces = new Map();
  for (const line of String(text || "").split(/\r?\n/)) {
    const marker = line.indexOf("[VoiceHop]");
    if (marker < 0) {
      continue;
    }
    const start = line.indexOf("{", marker);
    if (start < 0) {
      continue;
    }
    let payload;
    try {
      payload = JSON.parse(line.slice(start));
    } catch {
      continue;
    }
    const correlationId = String(payload.correlationId || "");
    if (!correlationId) {
      continue;
    }
    const trace = traces.get(correlationId) || {
      timestampsMs: {},
      terminalStatus: "",
      missingHops: [],
      firstBreach: null,
    };
    if (
      payload.event === "voice_hop" &&
      HOP_ORDER.includes(payload.hop) &&
      Number.isFinite(payload.timestampMs) &&
      !Number.isFinite(trace.timestampsMs[payload.hop])
    ) {
      trace.timestampsMs[payload.hop] = Number(payload.timestampMs);
    } else if (payload.event === "voice_hop_trace_terminal") {
      trace.terminalStatus = String(payload.status || "");
      trace.missingHops = asArray(payload.missingHops).filter((hop) =>
        HOP_ORDER.includes(hop),
      );
      trace.firstBreach = payload.firstBreach || null;
      for (const [hop, timestamp] of Object.entries(
        payload.timestampsMs || {},
      )) {
        if (HOP_ORDER.includes(hop) && Number.isFinite(timestamp)) {
          trace.timestampsMs[hop] = Number(timestamp);
        }
      }
    }
    traces.set(correlationId, trace);
  }
  return traces;
}

function summarizeVoiceHopTraces(traces) {
  const durations = {};
  const totalAudioMs = [];
  let completeTraceCount = 0;
  let incompleteTraceCount = 0;
  let firstBreachCount = 0;
  let outOfOrderTraceCount = 0;
  const firstBreachByHop = {};
  for (const trace of traces.values()) {
    const required =
      Number.isFinite(trace.timestampsMs.tool_start) ||
      Number.isFinite(trace.timestampsMs.tool_end)
        ? HOP_ORDER
        : HOP_ORDER.filter((hop) => hop !== "tool_start" && hop !== "tool_end");
    const complete = required.every((hop) =>
      Number.isFinite(trace.timestampsMs[hop]),
    );
    if (complete) {
      completeTraceCount += 1;
    } else {
      incompleteTraceCount += 1;
    }
    if (trace.firstBreach) {
      firstBreachCount += 1;
      const breachHop = String(trace.firstBreach.hop || "");
      const validBreachHops = HOP_ORDER.slice(0, -1).map(
        (hop, index) => `${hop}->${HOP_ORDER[index + 1]}`,
      );
      if (validBreachHops.includes(breachHop)) {
        firstBreachByHop[breachHop] =
          Number(firstBreachByHop[breachHop] || 0) + 1;
      }
    }
    let traceOutOfOrder = false;
    for (let index = 0; index < required.length - 1; index += 1) {
      const left = required[index];
      const right = required[index + 1];
      if (
        !Number.isFinite(trace.timestampsMs[left]) ||
        !Number.isFinite(trace.timestampsMs[right])
      ) {
        continue;
      }
      const key = `${left}->${right}`;
      if (trace.timestampsMs[right] < trace.timestampsMs[left]) {
        traceOutOfOrder = true;
      }
      durations[key] ||= [];
      durations[key].push(trace.timestampsMs[right] - trace.timestampsMs[left]);
    }
    if (traceOutOfOrder) {
      outOfOrderTraceCount += 1;
    }
    if (
      Number.isFinite(trace.timestampsMs.utterance_end) &&
      Number.isFinite(trace.timestampsMs.audio_output)
    ) {
      totalAudioMs.push(
        trace.timestampsMs.audio_output - trace.timestampsMs.utterance_end,
      );
    }
  }
  const hopDurationsMs = {};
  for (const [key, values] of Object.entries(durations)) {
    hopDurationsMs[key] = {
      count: values.length,
      p50: percentile(values, 0.5),
      p95: percentile(values, 0.95),
      max: values.length ? Math.max(...values) : null,
    };
  }
  return {
    traceCount: traces.size,
    completeTraceCount,
    incompleteTraceCount,
    firstBreachCount,
    firstBreachByHop,
    outOfOrderTraceCount,
    utteranceToAudioMs: {
      count: totalAudioMs.length,
      p50: percentile(totalAudioMs, 0.5),
      p95: percentile(totalAudioMs, 0.95),
      max: totalAudioMs.length ? Math.max(...totalAudioMs) : null,
    },
    hopDurationsMs,
  };
}

function readTraceSummary(logFiles) {
  const combined = new Map();
  for (const logFile of logFiles) {
    const traces = extractVoiceHopTraces(fs.readFileSync(logFile, "utf8"));
    for (const [key, value] of traces) {
      const current = combined.get(key) || {
        timestampsMs: {},
        terminalStatus: "",
        missingHops: [],
        firstBreach: null,
      };
      current.timestampsMs = { ...current.timestampsMs, ...value.timestampsMs };
      current.terminalStatus = value.terminalStatus || current.terminalStatus;
      current.missingHops = value.missingHops.length
        ? value.missingHops
        : current.missingHops;
      current.firstBreach = value.firstBreach || current.firstBreach;
      combined.set(key, current);
    }
  }
  return summarizeVoiceHopTraces(combined);
}

function applyMeasuredEvidence(result, runtime, profile) {
  const latencyEvidence = runtime.externalEvidence?.latency || {};
  const qualityEvidence = runtime.externalEvidence?.quality || {};
  const behaviorEvidence = runtime.externalEvidence?.behaviorPaths || {};
  const escapedRegressionEvidence =
    runtime.externalEvidence?.escapedRegressions || {};
  const ownerCapabilityInventory = normalizeTaskOwnerCapabilityInventory(
    runtime.externalEvidence?.taskOwnerCapabilityInventory,
  );
  const combined = {
    clickToListeningMs: asArray(latencyEvidence.clickToListeningMs),
    taskEventVisibleMs: [
      ...result._timingSamples.taskEventVisibleMs,
      ...asArray(latencyEvidence.taskEventVisibleMs),
    ],
    sourceVisibleMs: [
      ...result._timingSamples.sourceVisibleMs,
      ...asArray(latencyEvidence.sourceVisibleMs),
    ],
    cancelStateMs: [
      ...result._timingSamples.cancelStateMs,
      ...asArray(latencyEvidence.cancelStateMs),
    ],
    cancelBarrierMs: [
      ...result._timingSamples.cancelBarrierMs,
      ...asArray(latencyEvidence.cancelBarrierMs),
    ],
    utteranceToAcknowledgementMs: asArray(
      latencyEvidence.utteranceToAcknowledgementMs,
    ),
    warmSubstantiveAudioMs: asArray(latencyEvidence.warmSubstantiveAudioMs),
    bargeInStopMs: asArray(latencyEvidence.bargeInStopMs),
  };
  result.latency.callStartToListeningMs = metricSummary(
    result._timingSamples.callStartToListeningMs,
  );
  for (const [key, values] of Object.entries(combined)) {
    result.latency[key] = metricSummary(values);
  }
  const activeWorkSilence = latencyEvidence.maxActiveWorkSilenceMs;
  result.latency.maxActiveWorkSilenceMs =
    activeWorkSilence !== null &&
    activeWorkSilence !== undefined &&
    activeWorkSilence !== "" &&
    Number.isFinite(Number(activeWorkSilence))
      ? Number(activeWorkSilence)
      : null;
  for (const key of Object.keys(result.quality)) {
    const rawValue = qualityEvidence[key];
    const value = Number(rawValue);
    result.quality[key] =
      rawValue !== null &&
      rawValue !== undefined &&
      rawValue !== "" &&
      Number.isFinite(value)
        ? value
        : null;
  }
  for (const key of REQUIRED_BEHAVIOR_PATHS) {
    result.behaviorPaths[key] =
      typeof behaviorEvidence[key] === "boolean" ? behaviorEvidence[key] : null;
  }
  if (ownerCapabilityInventory === null) {
    result.behaviorApplicability.needsInputRoundTrip = {
      status: "UNKNOWN",
      reason: "authoritative_owner_inventory_missing",
      advertisedInputOwnerCount: null,
    };
  } else {
    const advertisedInputOwnerCount = ownerCapabilityInventory.filter(
      (owner) => owner.acceptsInput,
    ).length;
    result.behaviorApplicability.needsInputRoundTrip = {
      status: advertisedInputOwnerCount > 0 ? "APPLICABLE" : "NOT_APPLICABLE",
      reason:
        advertisedInputOwnerCount > 0
          ? null
          : "no_advertised_input_capable_owner",
      advertisedInputOwnerCount,
    };
  }
  for (const key of Object.keys(ESCAPED_REGRESSION_GATES)) {
    result.escapedRegressions[key] =
      typeof escapedRegressionEvidence[key] === "boolean"
        ? escapedRegressionEvidence[key]
        : null;
  }

  gate(
    result,
    "click-to-listening-p95",
    result.latency.clickToListeningMs.count > 0 &&
      result.latency.clickToListeningMs.p95 <= 4000,
    result.latency.clickToListeningMs.p95,
    4000,
  );
  if (profile !== "audible") {
    return;
  }
  const latencyGates = [
    ["task-event-visible-p95", "taskEventVisibleMs", 250],
    ["source-visible-p95", "sourceVisibleMs", 500],
    ["cancel-state-p95", "cancelStateMs", 250],
    ["cancel-barrier-p95", "cancelBarrierMs", 1000],
    ["acknowledgement-p95", "utteranceToAcknowledgementMs", 1500],
    ["warm-substantive-audio-p95", "warmSubstantiveAudioMs", 2500],
    ["barge-in-stop-p95", "bargeInStopMs", 1400],
  ];
  for (const [id, key, threshold] of latencyGates) {
    const metric = result.latency[key];
    gate(
      result,
      id,
      metric.count > 0 && metric.p95 <= threshold,
      metric.p95,
      threshold,
    );
  }
  gate(
    result,
    "acknowledgement-p50",
    result.latency.utteranceToAcknowledgementMs.count > 0 &&
      result.latency.utteranceToAcknowledgementMs.p50 <= 1000,
    result.latency.utteranceToAcknowledgementMs.p50,
    1000,
  );
  gate(
    result,
    "active-work-silence-max",
    result.latency.maxActiveWorkSilenceMs !== null &&
      result.latency.maxActiveWorkSilenceMs <= 5000,
    result.latency.maxActiveWorkSilenceMs,
    5000,
  );
  gate(
    result,
    "local-only-cloud-audio-egress",
    result.quality.cloudAudioEgressBytes === 0,
    result.quality.cloudAudioEgressBytes,
    0,
  );
  gate(
    result,
    "clean-speaker-attributed-word-accuracy",
    result.quality.cleanAttributedWordAccuracyPercent !== null &&
      result.quality.cleanAttributedWordAccuracyPercent >= 95,
    result.quality.cleanAttributedWordAccuracyPercent,
    95,
  );
  gate(
    result,
    "noisy-speaker-bank-der",
    result.quality.noisySpeakerBankDerPercent !== null &&
      result.quality.noisySpeakerBankDerPercent <= 15,
    result.quality.noisySpeakerBankDerPercent,
    15,
  );
  gate(
    result,
    "false-verified-owner-assignments",
    result.quality.falseVerifiedOwnerAssignments === 0,
    result.quality.falseVerifiedOwnerAssignments,
    0,
  );
  gate(
    result,
    "diarization-caption-added-p95",
    result.quality.diarizationAddedCaptionP95Ms !== null &&
      result.quality.diarizationAddedCaptionP95Ms <= 300,
    result.quality.diarizationAddedCaptionP95Ms,
    300,
  );
  const exactQualityGates = [
    ["separate-track-attribution", "separateTrackAttributionPercent", 100],
    ["unknown-attribution-abstention", "unknownAbstentionErrors", 0],
    ["no-biometric-identity-claims", "biometricIdentityClaims", 0],
    ["post-cancel-suppression-barrier", "postCancelBarrierOutputCount", 0],
    ["call-chat-result-source-parity", "callChatParityPercent", 100],
    ["zero-raw-audio-retention", "rawAudioRetainedBytes", 0],
    ["speaker-map-session-expiry", "speakerMapRowsAfterExpiry", 0],
    ["memory-boundary-enforcement", "memoryBoundaryViolationCount", 0],
    ["action-authority-enforcement", "unauthorizedSideEffectCount", 0],
  ];
  for (const [id, key, expected] of exactQualityGates) {
    gate(
      result,
      id,
      result.quality[key] === expected,
      result.quality[key],
      expected,
    );
  }
  for (const key of REQUIRED_BEHAVIOR_PATHS) {
    if (key === "needsInputRoundTrip") {
      const applicability = result.behaviorApplicability.needsInputRoundTrip;
      if (applicability.status === "UNKNOWN") {
        conditionalGate(
          result,
          `behavior-${key}`,
          "FAIL",
          applicability.reason,
          "authoritative_owner_capability_inventory",
        );
        continue;
      }
      if (applicability.status !== "NOT_APPLICABLE") {
        gate(
          result,
          `behavior-${key}`,
          result.behaviorPaths[key] === true,
          result.behaviorPaths[key],
          true,
        );
        continue;
      }
      conditionalGate(
        result,
        `behavior-${key}`,
        "NOT_APPLICABLE",
        "no_advertised_input_capable_owner",
        "production_owner_advertises_provide_input",
      );
      continue;
    }
    gate(
      result,
      `behavior-${key}`,
      result.behaviorPaths[key] === true,
      result.behaviorPaths[key],
      true,
    );
  }
  for (const [key, gateId] of Object.entries(ESCAPED_REGRESSION_GATES)) {
    gate(
      result,
      gateId,
      result.escapedRegressions[key] === true,
      result.escapedRegressions[key],
      true,
    );
  }
}

function emptyReplay() {
  return {
    lostTasks: 0,
    duplicateTasks: 0,
    regressedTasks: 0,
    changedStableTasks: 0,
    lostSegments: 0,
    duplicateSegments: 0,
    regressedSegments: 0,
    changedStableSegments: 0,
    duplicateResults: 0,
  };
}

function baseResult(profile, environment = "self_test") {
  const result = {
    schema: "viventium.voice.acceptance.result.v1",
    generatedAt: new Date().toISOString(),
    profile,
    environment,
    status: "BLOCKED",
    plan: { ...PLAN },
    execution: {
      modeSwitchesCompleted: 0,
      reconnectsCompleted: 0,
      audibleMinutesObserved: 0,
      soakMinutesObserved: 0,
      browserConnected: false,
      audioPlaybackEvents: 0,
      audibleEvidenceWindows: 0,
      maxAudibleEvidenceGapSeconds: null,
      snapshots: 0,
      runtimeGatesExecuted: false,
      scenario: {
        authoritativeSources: 0,
        distinctSpeakerKeys: 0,
        bargeIns: 0,
        cancellations: 0,
        networkLosses: 0,
        providerDegradations: 0,
        observedDegradedStates: 0,
        participantJoins: 0,
        participantLeaves: 0,
        refreshes: 0,
        modeChanges: 0,
        cleanHangups: 0,
      },
    },
    replay: emptyReplay(),
    latency: {
      traceCount: 0,
      completeTraceCount: 0,
      incompleteTraceCount: 0,
      firstBreachCount: 0,
      firstBreachByHop: {},
      outOfOrderTraceCount: 0,
      utteranceToAudioMs: { count: 0, p50: null, p95: null, max: null },
      hopDurationsMs: {},
      callStartToListeningMs: { count: 0, p50: null, p95: null, max: null },
      clickToListeningMs: { count: 0, p50: null, p95: null, max: null },
      taskEventVisibleMs: { count: 0, p50: null, p95: null, max: null },
      sourceVisibleMs: { count: 0, p50: null, p95: null, max: null },
      cancelStateMs: { count: 0, p50: null, p95: null, max: null },
      cancelBarrierMs: { count: 0, p50: null, p95: null, max: null },
      utteranceToAcknowledgementMs: {
        count: 0,
        p50: null,
        p95: null,
        max: null,
      },
      warmSubstantiveAudioMs: { count: 0, p50: null, p95: null, max: null },
      bargeInStopMs: { count: 0, p50: null, p95: null, max: null },
      maxActiveWorkSilenceMs: null,
    },
    quality: {
      cloudAudioEgressBytes: null,
      cleanAttributedWordAccuracyPercent: null,
      noisySpeakerBankDerPercent: null,
      falseVerifiedOwnerAssignments: null,
      diarizationAddedCaptionP95Ms: null,
      separateTrackAttributionPercent: null,
      unknownAbstentionErrors: null,
      biometricIdentityClaims: null,
      postCancelBarrierOutputCount: null,
      callChatParityPercent: null,
      rawAudioRetainedBytes: null,
      speakerMapRowsAfterExpiry: null,
      memoryBoundaryViolationCount: null,
      unauthorizedSideEffectCount: null,
    },
    behaviorPaths: Object.fromEntries(
      REQUIRED_BEHAVIOR_PATHS.map((key) => [key, null]),
    ),
    behaviorApplicability: {
      needsInputRoundTrip: {
        status: null,
        reason: null,
        advertisedInputOwnerCount: null,
      },
    },
    escapedRegressions: Object.fromEntries(
      Object.keys(ESCAPED_REGRESSION_GATES).map((key) => [key, null]),
    ),
    resources: {
      processesObserved: 0,
      processCrashes: 0,
      maxPostWarmGrowthPercent: null,
      overTenPercentGrowth: 0,
      missingPostWarmSamples: 0,
      leakedTasks: 0,
    },
    gates: [],
    evidence: {
      screenshots: 0,
      structuredSnapshots: 0,
      latencyLogs: 0,
      rawArtifactsPrivate: true,
    },
    privacy: {
      publicSafe: true,
      rawIdentifiersIncluded: false,
      rawTranscriptIncluded: false,
      localPathsIncluded: false,
    },
    failures: [],
  };
  Object.defineProperty(result, "_timingSamples", {
    enumerable: false,
    value: {
      callStartToListeningMs: [],
      taskEventVisibleMs: [],
      sourceVisibleMs: [],
      cancelStateMs: [],
      cancelBarrierMs: [],
    },
  });
  return result;
}

function gate(result, id, passed, actual, threshold) {
  result.gates.push({
    id,
    status: passed ? "PASS" : "FAIL",
    actual,
    threshold,
  });
}

function conditionalGate(result, id, status, actual, threshold) {
  if (!["PASS", "FAIL", "NOT_APPLICABLE"].includes(status)) {
    throw new Error("invalid conditional gate status");
  }
  result.gates.push({ id, status, actual, threshold });
}

function writeJson(filePath, value) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`, {
    mode: 0o600,
  });
}

function appendPrivateEvent(outputRoot, event) {
  fs.mkdirSync(outputRoot, { recursive: true });
  fs.appendFileSync(
    path.join(outputRoot, "raw-events.ndjson"),
    `${JSON.stringify({ at: new Date().toISOString(), ...event })}\n`,
    { mode: 0o600 },
  );
}

function assertSanitizedResult(result) {
  const serialized = JSON.stringify(result);
  const forbidden = [
    ROOT,
    os.homedir(),
    "callSessionId",
    "conversationId",
    "messageId",
    "participantIdentity",
    "transcriptText",
    "http://",
    "https://",
    "mongodb://",
    "viventiumCallCapability",
    CALL_CAPABILITY_HEADER,
  ];
  const leak = forbidden.find((item) => item && serialized.includes(item));
  if (leak) {
    throw new Error("sanitized_result_leak");
  }
}

function selfTestResult() {
  const task = (taskId, sequence, state, resultRef = "") => ({
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
  const first = {
    tasks: [task("task-a", 1, "running")],
    segments: [segment("segment-a", 1, 0, "synthetic private transcript")],
  };
  const second = {
    tasks: [
      task("task-a", 2, "completed", "result-a"),
      task("task-b", 1, "running"),
    ],
    segments: [
      segment("segment-a", 1, 1, "synthetic private transcript revised"),
      segment("segment-b", 2, 0, "second synthetic segment"),
    ],
  };
  const replay = emptyReplay();
  addReplayTotals(replay, auditReplay(first, second));
  addReplayTotals(replay, auditReplay(second, second));
  const traceLines = [];
  for (const [traceId, base] of [
    ["call-private-123", 1000],
    ["user@example.com", 3000],
  ]) {
    const hops = HOP_ORDER.filter(
      (hop) => hop !== "tool_start" && hop !== "tool_end",
    );
    hops.forEach((hop, index) => {
      traceLines.push(
        `[VoiceHop] ${JSON.stringify({
          event: "voice_hop",
          correlationId: traceId,
          callSessionId: "call-private-123",
          hop,
          timestampMs: base + index * 100,
        })}`,
      );
    });
  }
  const result = baseResult("self-test");
  result.status = replayPassed(replay) ? "PASS" : "FAIL";
  result.replay = replay;
  result.latency = summarizeVoiceHopTraces(
    extractVoiceHopTraces(traceLines.join("\n")),
  );
  result.gates = [
    { id: "self-test-replay", status: result.status, actual: 0, threshold: 0 },
    { id: "self-test-traces", status: "PASS", actual: 2, threshold: 2 },
  ];
  return result;
}

function loadRuntimeConfig(configPath, profile) {
  const config = JSON.parse(fs.readFileSync(configPath, "utf8"));
  if (!config.callUrl || typeof config.callUrl !== "string") {
    throw new Error("config_call_url_missing");
  }
  const callUrl = new URL(config.callUrl);
  const callSessionId = callUrl.searchParams.get("callSessionId");
  if (!callSessionId || !/^[A-Za-z0-9._:-]{1,200}$/.test(callSessionId)) {
    throw new Error("config_call_session_missing");
  }
  const browserCapability = new URLSearchParams(callUrl.hash.slice(1)).get(
    "viventiumCallCapability",
  );
  if (
    !callUrl.pathname.endsWith("/call-bootstrap") ||
    !SAFE_BROWSER_CAPABILITY.test(String(browserCapability || ""))
  ) {
    throw new Error("config_call_browser_capability_missing");
  }
  const runtime = {
    ...config,
    profile,
    callUrl: callUrl.toString(),
    playgroundOrigin: callUrl.origin,
    callSessionId,
    logs: asArray(config.logs).map((value) => path.resolve(value)),
    processes: asArray(config.processes).filter(
      (item) =>
        item &&
        /^[a-z0-9_-]{1,40}$/i.test(String(item.name || "")) &&
        Number.isSafeInteger(Number(item.pid)) &&
        Number(item.pid) > 1,
    ),
    actions: asArray(config.actions),
    snapshotIntervalMs: Math.max(
      1000,
      Number(config.snapshotIntervalMs || 10_000),
    ),
    reconnectOfflineMs: Math.max(250, Number(config.reconnectOfflineMs || 750)),
    warmupMinutes: Math.max(1, Number(config.warmupMinutes || 10)),
    externalEvidence: {},
  };
  if (
    !["dev", "installed_prod", "clean_install"].includes(config.environment)
  ) {
    throw new Error("config_environment_invalid");
  }
  runtime.environment = config.environment;
  if (runtime.audioFile) {
    runtime.audioFile = path.resolve(runtime.audioFile);
    if (!fs.existsSync(runtime.audioFile)) {
      throw new Error("config_audio_missing");
    }
    assertOutsidePublicRepo(runtime.audioFile, "audioFile");
  }
  for (const logFile of runtime.logs) {
    if (!fs.existsSync(logFile)) {
      throw new Error("config_log_missing");
    }
    assertOutsidePublicRepo(logFile, "logs");
  }
  if (config.externalEvidenceFile) {
    const evidencePath = path.resolve(config.externalEvidenceFile);
    assertOutsidePublicRepo(evidencePath, "externalEvidenceFile");
    const evidence = JSON.parse(fs.readFileSync(evidencePath, "utf8"));
    if (evidence.schema !== "viventium.voice.external-evidence.v1") {
      throw new Error("external_evidence_schema_invalid");
    }
    runtime.externalEvidence = evidence;
  }
  return runtime;
}

function requirePlaywright() {
  const librechatDir =
    process.env.LIBRECHAT_DIR || path.join(ROOT, "viventium_v0_4", "LibreChat");
  const localRequire = createRequire(path.join(librechatDir, "package.json"));
  return localRequire("playwright");
}

async function installBrowserProbe(page) {
  await page.addInitScript(() => {
    const OriginalPeerConnection = globalThis.RTCPeerConnection;
    globalThis.__viventiumQa = {
      peerConnections: [],
      audioPlaybackEvents: 0,
      modeRequests: 0,
      taskVisibleAtMs: [],
      sourceVisibleAtMs: [],
      cancelBarrierMs: [],
    };
    if (OriginalPeerConnection) {
      function QaPeerConnection(...args) {
        const peer = new OriginalPeerConnection(...args);
        const entry = { peer, states: [] };
        const record = () => {
          entry.states.push({
            connectionState: peer.connectionState,
            iceConnectionState: peer.iceConnectionState,
          });
        };
        peer.addEventListener("connectionstatechange", record);
        peer.addEventListener("iceconnectionstatechange", record);
        record();
        globalThis.__viventiumQa.peerConnections.push(entry);
        return peer;
      }
      QaPeerConnection.prototype = OriginalPeerConnection.prototype;
      Object.setPrototypeOf(QaPeerConnection, OriginalPeerConnection);
      globalThis.RTCPeerConnection = QaPeerConnection;
      if (globalThis.webkitRTCPeerConnection) {
        globalThis.webkitRTCPeerConnection = QaPeerConnection;
      }
    }
    const originalPlay = HTMLMediaElement.prototype.play;
    HTMLMediaElement.prototype.play = function qaPlay(...args) {
      globalThis.__viventiumQa.audioPlaybackEvents += 1;
      return originalPlay.apply(this, args);
    };
    const originalFetch = globalThis.fetch;
    globalThis.fetch = function qaFetch(input, init) {
      const url = typeof input === "string" ? input : input?.url || "";
      if (
        String(url).includes("/api/call-session-state") &&
        init?.method === "POST"
      ) {
        globalThis.__viventiumQa.modeRequests += 1;
      }
      const cancelRequest =
        String(url).includes("/api/call-tasks/") &&
        String(url).endsWith("/cancel");
      const startedAt = cancelRequest ? performance.now() : 0;
      const request = originalFetch.apply(this, arguments);
      if (cancelRequest) {
        request.finally(() => {
          globalThis.__viventiumQa.cancelBarrierMs.push(
            performance.now() - startedAt,
          );
        });
      }
      return request;
    };
    const startVisibilityObserver = () => {
      if (!document.body) {
        return;
      }
      let lastActivity = "";
      let lastSources = "";
      const inspect = () => {
        const activity = document.querySelector(
          'section[aria-label="Call activity"]',
        );
        const activityText = activity?.textContent || "";
        if (activityText && activityText !== lastActivity) {
          globalThis.__viventiumQa.taskVisibleAtMs.push(Date.now());
          lastActivity = activityText;
        }
        const sourceText = [
          ...document.querySelectorAll('[aria-label^="Sources for "]'),
        ]
          .map((item) => item.textContent || "")
          .join("\n");
        if (sourceText && sourceText !== lastSources) {
          globalThis.__viventiumQa.sourceVisibleAtMs.push(Date.now());
          lastSources = sourceText;
        }
      };
      new MutationObserver(inspect).observe(document.body, {
        subtree: true,
        childList: true,
        characterData: true,
      });
      inspect();
    };
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", startVisibilityObserver, {
        once: true,
      });
    } else {
      startVisibilityObserver();
    }
  });
}

async function browserProbe(page) {
  return page.evaluate(async () => {
    const state = globalThis.__viventiumQa || {};
    const peerConnections = [];
    let receivedAudioEnergy = 0;
    for (const entry of asArrayForBrowser(state.peerConnections)) {
      const stats = await entry.peer.getStats().catch(() => null);
      if (stats) {
        stats.forEach((stat) => {
          if (
            stat.type === "inbound-rtp" &&
            stat.kind === "audio" &&
            Number.isFinite(stat.totalAudioEnergy)
          ) {
            receivedAudioEnergy += Number(stat.totalAudioEnergy);
          }
        });
      }
      peerConnections.push({
        connectionState: entry.peer.connectionState,
        iceConnectionState: entry.peer.iceConnectionState,
        states: entry.states,
      });
    }
    return {
      peerConnections,
      audioPlaybackEvents: Number(state.audioPlaybackEvents || 0),
      receivedAudioEnergy,
      modeRequests: Number(state.modeRequests || 0),
      taskVisibleAtMs: asArrayForBrowser(state.taskVisibleAtMs),
      sourceVisibleAtMs: asArrayForBrowser(state.sourceVisibleAtMs),
      cancelBarrierMs: asArrayForBrowser(state.cancelBarrierMs),
    };
    function asArrayForBrowser(value) {
      return Array.isArray(value) ? value : [];
    }
  });
}

async function waitForConnected(page, timeoutMs = 45_000) {
  await page.waitForFunction(
    () => {
      const endButton = [...document.querySelectorAll("button")].find(
        (button) =>
          button.getAttribute("aria-label")?.toLowerCase() === "end call",
      );
      const status = [...document.querySelectorAll('[role="status"]')]
        .map((item) => item.textContent || "")
        .join(" ")
        .toLowerCase();
      const settledVisibleState = [
        "listening",
        "speaking",
        "working",
        "needs input",
      ].some((state) => status.includes(state));
      const peerConnected = (
        globalThis.__viventiumQa?.peerConnections || []
      ).some(
        (entry) =>
          entry.peer.connectionState === "connected" &&
          ["connected", "completed"].includes(entry.peer.iceConnectionState),
      );
      return Boolean(
        endButton &&
        !endButton.disabled &&
        settledVisibleState &&
        peerConnected,
      );
    },
    undefined,
    { timeout: timeoutMs },
  );
}

async function assertCallBootstrapStripped(page, callSessionId) {
  await page.waitForFunction(
    ({ expectedCallSessionId, storagePrefix }) => {
      const stored =
        window.sessionStorage.getItem(
          `${storagePrefix}${expectedCallSessionId}`,
        ) || "";
      return (
        window.location.hash === "" &&
        !window.location.pathname.endsWith("/call-bootstrap") &&
        /^[A-Za-z0-9_-]{43}$/.test(stored)
      );
    },
    {
      expectedCallSessionId: callSessionId,
      storagePrefix: CALL_CAPABILITY_STORAGE_PREFIX,
    },
    { timeout: 10_000 },
  );
  const safeState = await page.evaluate(
    ({ expectedCallSessionId, storagePrefix }) => ({
      fragmentStripped: window.location.hash === "",
      bootstrapExited: !window.location.pathname.endsWith("/call-bootstrap"),
      capabilityStored: /^[A-Za-z0-9_-]{43}$/.test(
        window.sessionStorage.getItem(
          `${storagePrefix}${expectedCallSessionId}`,
        ) || "",
      ),
    }),
    {
      expectedCallSessionId: callSessionId,
      storagePrefix: CALL_CAPABILITY_STORAGE_PREFIX,
    },
  );
  if (
    !safeState.fragmentStripped ||
    !safeState.bootstrapExited ||
    !safeState.capabilityStored
  ) {
    throw new Error("call_capability_bootstrap_failed");
  }
}

async function fetchJsonInPage(page, url, init, callSessionId) {
  return page.evaluate(
    async ({
      requestUrl,
      requestInit,
      expectedCallSessionId,
      storagePrefix,
      capabilityHeader,
    }) => {
      const requestHeaders = new Headers(requestInit?.headers || {});
      const resolvedRequestUrl = new URL(
        requestUrl,
        globalThis.location?.origin || "http://localhost",
      );
      const requestedCallSessionId =
        resolvedRequestUrl.searchParams.get("callSessionId") || "";
      const exactSession = requestedCallSessionId === expectedCallSessionId;
      const capability =
        exactSession && /^[A-Za-z0-9._:-]{1,160}$/.test(expectedCallSessionId)
          ? globalThis.sessionStorage.getItem(
              `${storagePrefix}${expectedCallSessionId}`,
            ) || ""
          : "";
      if (/^[A-Za-z0-9_-]{43}$/.test(capability)) {
        requestHeaders.set(capabilityHeader, capability);
      } else {
        requestHeaders.delete(capabilityHeader);
      }
      const response = await fetch(requestUrl, {
        ...(requestInit || {}),
        headers: requestHeaders,
      });
      const payload = await response.json().catch(() => ({}));
      return { ok: response.ok, status: response.status, payload };
    },
    {
      requestUrl: url,
      requestInit: init,
      expectedCallSessionId: callSessionId,
      storagePrefix: CALL_CAPABILITY_STORAGE_PREFIX,
      capabilityHeader: CALL_CAPABILITY_HEADER,
    },
  );
}

async function fetchSnapshot(page, callSessionId) {
  const taskResponse = await fetchJsonInPage(
    page,
    `/api/call-tasks?callSessionId=${encodeURIComponent(callSessionId)}`,
    undefined,
    callSessionId,
  );
  if (!taskResponse.ok) {
    throw new Error("task_snapshot_failed");
  }
  const segments = [];
  let cursor = "";
  for (let pageNumber = 0; pageNumber < 64; pageNumber += 1) {
    const speakerResponse = await fetchJsonInPage(
      page,
      `/api/call-speakers?callSessionId=${encodeURIComponent(callSessionId)}${cursor}`,
      undefined,
      callSessionId,
    );
    if (!speakerResponse.ok) {
      throw new Error("speaker_snapshot_failed");
    }
    segments.push(...normalizeSpeakerPage(speakerResponse.payload));
    if (!speakerResponse.payload?.hasMore) {
      break;
    }
    const sequence = speakerResponse.payload.nextBeforeSequence;
    const segmentId = speakerResponse.payload.nextBeforeSegmentId;
    if (!Number.isSafeInteger(sequence) || typeof segmentId !== "string") {
      throw new Error("speaker_cursor_invalid");
    }
    cursor = `&beforeSequence=${encodeURIComponent(sequence)}&beforeSegmentId=${encodeURIComponent(segmentId)}`;
  }
  return {
    tasks: normalizeTaskSnapshot(taskResponse.payload),
    segments,
    taskOwnerCapabilityInventory:
      taskResponse.payload?.taskOwnerCapabilityInventory || null,
  };
}

async function currentCallState(page, callSessionId) {
  const response = await fetchJsonInPage(
    page,
    `/api/call-session-state?callSessionId=${encodeURIComponent(callSessionId)}`,
    undefined,
    callSessionId,
  );
  if (!response.ok) {
    throw new Error("call_state_failed");
  }
  return response.payload;
}

async function clickMode(page, callSessionId, mode) {
  const labels = { call: "Call", wing: "Wing", listen_only: "Listen-Only" };
  const button = page.getByRole("button", { name: labels[mode], exact: true });
  await button.click({ timeout: 10_000 });
  await page.waitForFunction(
    ({ label }) => {
      const candidate = [...document.querySelectorAll("button")].find(
        (item) => item.textContent?.trim() === label,
      );
      return (
        candidate?.getAttribute("aria-pressed") === "true" &&
        !candidate.disabled
      );
    },
    { label: labels[mode] },
    { timeout: 10_000 },
  );
  const state = await currentCallState(page, callSessionId);
  if (
    state.mode !== mode ||
    state.version !== 1 ||
    !Number.isSafeInteger(state.revision)
  ) {
    throw new Error("mode_state_mismatch");
  }
  return state;
}

async function runModeSwitches(page, config, result, outputRoot) {
  const beforeProbe = await browserProbe(page);
  const initialState = await currentCallState(page, config.callSessionId);
  let priorRevision = Number(initialState.revision);
  let currentMode = MODES.includes(initialState.mode)
    ? initialState.mode
    : "call";
  for (let index = 0; index < PLAN.modeSwitches; index += 1) {
    const target = MODES[(MODES.indexOf(currentMode) + 1) % MODES.length];
    const state = await clickMode(page, config.callSessionId, target);
    if (
      !Number.isSafeInteger(priorRevision) ||
      state.revision !== priorRevision + 1
    ) {
      throw new Error("mode_revision_non_atomic");
    }
    priorRevision = state.revision;
    currentMode = target;
    result.execution.modeSwitchesCompleted += 1;
    appendPrivateEvent(outputRoot, {
      event: "mode_switch",
      ordinal: index + 1,
      mode: target,
      revision: state.revision,
    });
  }
  const afterProbe = await browserProbe(page);
  const disconnected = afterProbe.peerConnections.some((entry) =>
    entry.states.some((state) =>
      ["disconnected", "failed", "closed"].includes(state.connectionState),
    ),
  );
  gate(
    result,
    "mode-switches-atomic",
    result.execution.modeSwitchesCompleted === PLAN.modeSwitches &&
      beforeProbe.peerConnections.length ===
        afterProbe.peerConnections.length &&
      !disconnected,
    result.execution.modeSwitchesCompleted,
    PLAN.modeSwitches,
  );
}

async function compareSnapshot(
  page,
  config,
  result,
  previous,
  outputRoot,
  event,
  ordinal,
) {
  const current = await fetchSnapshot(page, config.callSessionId);
  config.externalEvidence.taskOwnerCapabilityInventory =
    current.taskOwnerCapabilityInventory;
  const delta = auditReplay(previous, current);
  addReplayTotals(result.replay, delta);
  result.execution.snapshots += 1;
  result.evidence.structuredSnapshots += 1;
  const probe = await browserProbe(page);
  result.execution.audioPlaybackEvents = Math.max(
    result.execution.audioPlaybackEvents,
    probe.audioPlaybackEvents,
  );
  config._seenTaskEvents ||= new Set();
  config._seenSourceEvents ||= new Set();
  for (const task of current.tasks) {
    const emittedAtMs = Date.parse(task.emittedAt || "");
    if (!Number.isFinite(emittedAtMs)) {
      continue;
    }
    if (!config._seenTaskEvents.has(task.eventId)) {
      const visibleAt = probe.taskVisibleAtMs.find(
        (timestamp) => timestamp >= emittedAtMs,
      );
      if (Number.isFinite(visibleAt)) {
        result._timingSamples.taskEventVisibleMs.push(visibleAt - emittedAtMs);
        config._seenTaskEvents.add(task.eventId);
      }
    }
    const hasSource = asArray(task.sources).length > 0 || Boolean(task.source);
    if (hasSource && !config._seenSourceEvents.has(task.eventId)) {
      const visibleAt = probe.sourceVisibleAtMs.find(
        (timestamp) => timestamp >= emittedAtMs,
      );
      if (Number.isFinite(visibleAt)) {
        result._timingSamples.sourceVisibleMs.push(visibleAt - emittedAtMs);
        config._seenSourceEvents.add(task.eventId);
      }
    }
  }
  const sources = current.tasks.flatMap((task) => [
    ...asArray(task.sources),
    ...(task.source && typeof task.source === "object" ? [task.source] : []),
  ]);
  result.execution.scenario.authoritativeSources = Math.max(
    result.execution.scenario.authoritativeSources,
    sources.length,
  );
  result.execution.scenario.distinctSpeakerKeys = Math.max(
    result.execution.scenario.distinctSpeakerKeys,
    new Set(
      current.segments
        .map((segment) => segment?.speaker?.key || segment?.speakerKey || "")
        .filter(Boolean),
    ).size,
  );
  appendPrivateEvent(outputRoot, {
    event,
    ordinal,
    taskCount: current.tasks.length,
    segmentCount: current.segments.length,
    replay: delta,
  });
  return current;
}

async function runReconnects(page, context, config, result, outputRoot) {
  let previous = await fetchSnapshot(page, config.callSessionId);
  for (let index = 0; index < PLAN.reconnects; index += 1) {
    await context.setOffline(true);
    await page.waitForTimeout(config.reconnectOfflineMs);
    await context.setOffline(false);
    await page.reload({ waitUntil: "domcontentloaded", timeout: 45_000 });
    await waitForConnected(page, 30_000);
    previous = await compareSnapshot(
      page,
      config,
      result,
      previous,
      outputRoot,
      "reconnect_snapshot",
      index + 1,
    );
    result.execution.reconnectsCompleted += 1;
  }
  gate(
    result,
    "reconnects-exact-replay",
    result.execution.reconnectsCompleted === PLAN.reconnects &&
      replayPassed(result.replay),
    result.execution.reconnectsCompleted,
    PLAN.reconnects,
  );
}

function processSample(processes) {
  return processes.map((processConfig) => {
    try {
      process.kill(Number(processConfig.pid), 0);
      const rssKb = Number(
        execFileSync("ps", ["-o", "rss=", "-p", String(processConfig.pid)], {
          encoding: "utf8",
        }).trim(),
      );
      return { name: processConfig.name, alive: true, rssKb };
    } catch {
      return { name: processConfig.name, alive: false, rssKb: 0 };
    }
  });
}

function runCommandAction(action) {
  return new Promise((resolve, reject) => {
    if (!action.executable || !Array.isArray(action.args)) {
      reject(new Error("command_action_invalid"));
      return;
    }
    const executable = path.resolve(action.executable);
    try {
      assertOutsidePublicRepo(executable, "command executable");
    } catch {
      reject(new Error("command_action_not_private"));
      return;
    }
    execFile(
      executable,
      action.args.map(String),
      { timeout: 60_000 },
      (error) => {
        if (error) {
          reject(new Error("command_action_failed"));
        } else {
          resolve();
        }
      },
    );
  });
}

async function joinScenarioParticipant(action, runtime) {
  if (!action.name || !/^[a-z0-9_-]{1,40}$/i.test(action.name)) {
    throw new Error("participant_name_invalid");
  }
  if (!action.callUrl || typeof action.callUrl !== "string") {
    throw new Error("participant_call_url_missing");
  }
  const participantUrl = new URL(action.callUrl);
  const participantCallSessionId =
    participantUrl.searchParams.get("callSessionId") || "";
  const participantCapability = new URLSearchParams(
    participantUrl.hash.slice(1),
  ).get("viventiumCallCapability");
  if (
    !participantUrl.pathname.endsWith("/call-bootstrap") ||
    !/^[A-Za-z0-9._:-]{1,160}$/.test(participantCallSessionId) ||
    !SAFE_BROWSER_CAPABILITY.test(String(participantCapability || ""))
  ) {
    throw new Error("participant_call_browser_capability_missing");
  }
  const launchArgs = [
    "--use-fake-ui-for-media-stream",
    "--use-fake-device-for-media-stream",
  ];
  if (action.audioFile) {
    const audioFile = path.resolve(action.audioFile);
    if (!fs.existsSync(audioFile)) {
      throw new Error("participant_audio_missing");
    }
    assertOutsidePublicRepo(audioFile, "participant audioFile");
    launchArgs.push(`--use-file-for-fake-audio-capture=${audioFile}`);
  }
  const { chromium } = requirePlaywright();
  const browser = await chromium.launch({
    channel: "chrome",
    headless: true,
    args: launchArgs,
  });
  const context = await browser.newContext();
  await context.grantPermissions(["microphone"], {
    origin: participantUrl.origin,
  });
  const page = await context.newPage();
  await installBrowserProbe(page);
  await page.goto(participantUrl.toString(), {
    waitUntil: "domcontentloaded",
    timeout: 45_000,
  });
  await assertCallBootstrapStripped(page, participantCallSessionId);
  await waitForConnected(page, 45_000);
  runtime._participants ||= new Map();
  runtime._participants.set(action.name, { browser, page });
}

async function leaveScenarioParticipant(action, runtime) {
  const participant = runtime._participants?.get(action.name);
  if (!participant) {
    throw new Error("participant_not_joined");
  }
  await participant.browser.close();
  runtime._participants.delete(action.name);
}

async function cancelLatestTask(page, config) {
  const snapshot = await fetchSnapshot(page, config.callSessionId);
  const task = [...snapshot.tasks]
    .reverse()
    .find((item) => ACTIVE_TASK_STATES.has(item.state));
  if (!task) {
    throw new Error("cancel_target_missing");
  }
  const actionStartedAt = Date.now();
  const cancelButton = page
    .locator('section[aria-label="Call activity"] button')
    .filter({ hasText: /^Cancel$/ })
    .first();
  if ((await cancelButton.count()) === 0) {
    throw new Error("cancel_button_missing");
  }
  await cancelButton.click({ timeout: 10_000 });
  while (Date.now() - actionStartedAt < 15_000) {
    const current = await fetchSnapshot(page, config.callSessionId);
    const updated = current.tasks.find((item) => item.taskId === task.taskId);
    if (
      updated &&
      ["cancelling", "cancelled_confirmed", "cancelled_unenforceable"].includes(
        updated.state,
      )
    ) {
      await page.waitForFunction(
        () => {
          const text =
            document.querySelector('section[aria-label="Call activity"]')
              ?.textContent || "";
          return /cancelling|cancelled confirmed|cancelled unenforceable/i.test(
            text,
          );
        },
        undefined,
        { timeout: 5_000 },
      );
      const probe = await browserProbe(page);
      return {
        state: updated.state,
        stateMs: Date.now() - actionStartedAt,
        barrierMs: probe.cancelBarrierMs.at(-1) ?? null,
      };
    }
    await page.waitForTimeout(250);
  }
  throw new Error("cancel_state_not_observed");
}

async function performScenarioAction(
  action,
  runtime,
  page,
  context,
  options,
  result,
  outputRoot,
) {
  if (action.kind === "mode" && MODES.includes(action.mode)) {
    await clickMode(page, runtime.callSessionId, action.mode);
    result.execution.scenario.modeChanges += 1;
  } else if (action.kind === "network_loss") {
    await context.setOffline(true);
    await page.waitForTimeout(Math.max(250, Number(action.durationMs || 1500)));
    await context.setOffline(false);
    await waitForConnected(page, 30_000);
    result.execution.scenario.networkLosses += 1;
  } else if (action.kind === "refresh") {
    await page.reload({ waitUntil: "domcontentloaded", timeout: 45_000 });
    await waitForConnected(page, 45_000);
    result.execution.scenario.refreshes += 1;
  } else if (action.kind === "cancel") {
    const timing = await cancelLatestTask(page, runtime);
    result._timingSamples.cancelStateMs.push(timing.stateMs);
    if (Number.isFinite(timing.barrierMs)) {
      result._timingSamples.cancelBarrierMs.push(timing.barrierMs);
    }
    result.execution.scenario.cancellations += 1;
  } else if (
    action.kind === "provider_degrade" ||
    action.kind === "provider_recover"
  ) {
    if (!options.allowCommandActions) {
      throw new Error("command_actions_not_allowed");
    }
    await runCommandAction(action);
    if (action.kind === "provider_degrade") {
      result.execution.scenario.providerDegradations += 1;
      const startedAt = Date.now();
      while (
        Date.now() - startedAt <
        Math.max(1_000, Number(action.waitForStateMs || 20_000))
      ) {
        const state = await currentCallState(page, runtime.callSessionId);
        if (state.status === "degraded" || state.status === "failed") {
          result.execution.scenario.observedDegradedStates += 1;
          break;
        }
        await page.waitForTimeout(250);
      }
      if (result.execution.scenario.observedDegradedStates === 0) {
        throw new Error("provider_degradation_not_observed");
      }
    }
  } else if (action.kind === "participant_join") {
    await joinScenarioParticipant(action, runtime);
    result.execution.scenario.participantJoins += 1;
  } else if (action.kind === "participant_leave") {
    await leaveScenarioParticipant(action, runtime);
    result.execution.scenario.participantLeaves += 1;
  } else if (action.kind === "barge_in") {
    await page.waitForFunction(
      () =>
        [...document.querySelectorAll('[role="status"]')]
          .map((item) => item.textContent || "")
          .join(" ")
          .toLowerCase()
          .includes("speaking"),
      undefined,
      { timeout: Math.max(1_000, Number(action.waitForSpeakingMs || 20_000)) },
    );
    await joinScenarioParticipant(action, runtime);
    await page.waitForTimeout(Math.max(250, Number(action.durationMs || 1500)));
    await leaveScenarioParticipant(action, runtime);
    result.execution.scenario.bargeIns += 1;
  } else if (action.kind === "hangup") {
    await page
      .getByRole("button", { name: /end call/i })
      .click({ timeout: 10_000 });
    const state = await currentCallState(page, runtime.callSessionId);
    if (state.status !== "ended") {
      throw new Error("hangup_not_terminal");
    }
    result.execution.scenario.cleanHangups += 1;
  } else if (action.kind === "checkpoint") {
    // Snapshot below is the checkpoint action.
  } else {
    throw new Error("scenario_action_unsupported");
  }
  appendPrivateEvent(outputRoot, {
    event: "scenario_action",
    kind: String(action.kind || "unknown"),
    atSeconds: Number(action.atSeconds || 0),
  });
  await page.screenshot({
    path: path.join(
      outputRoot,
      `scenario-${String(result.execution.snapshots + 1).padStart(4, "0")}-${String(action.kind).replace(/[^a-z0-9_-]/gi, "_")}.png`,
    ),
    fullPage: true,
  });
  result.evidence.screenshots += 1;
  result.execution.snapshots += 1;
}

async function runTimedProfile(
  kind,
  page,
  context,
  runtime,
  options,
  result,
  outputRoot,
) {
  const minutes = kind === "audible" ? PLAN.audibleMinutes : PLAN.soakMinutes;
  const durationMs = minutes * 60_000;
  const startedAt = Date.now();
  const actions = runtime.actions
    .filter((action) => action.profile === kind || action.profile === "both")
    .sort(
      (left, right) =>
        Number(left.atSeconds || 0) - Number(right.atSeconds || 0),
    );
  let actionIndex = 0;
  let previous = await fetchSnapshot(page, runtime.callSessionId);
  runtime.externalEvidence.taskOwnerCapabilityInventory =
    previous.taskOwnerCapabilityInventory;
  const processSamples = [];
  let lastAudioEnergy = 0;
  const audibleEvidenceAtMs = [];
  while (Date.now() - startedAt < durationMs) {
    const elapsedMs = Date.now() - startedAt;
    while (
      actionIndex < actions.length &&
      Number(actions[actionIndex].atSeconds || 0) * 1000 <= elapsedMs
    ) {
      await performScenarioAction(
        actions[actionIndex],
        runtime,
        page,
        context,
        options,
        result,
        outputRoot,
      );
      actionIndex += 1;
    }
    if (page.isClosed()) {
      throw new Error("browser_page_closed");
    }
    previous = await compareSnapshot(
      page,
      runtime,
      result,
      previous,
      outputRoot,
      `${kind}_snapshot`,
      result.execution.snapshots + 1,
    );
    if (kind === "audible") {
      const probe = await browserProbe(page);
      if (probe.receivedAudioEnergy + 0.001 < lastAudioEnergy) {
        lastAudioEnergy = 0;
      }
      if (probe.receivedAudioEnergy - lastAudioEnergy >= 0.001) {
        audibleEvidenceAtMs.push(elapsedMs);
        lastAudioEnergy = probe.receivedAudioEnergy;
      }
    }
    const sample = processSample(runtime.processes);
    processSamples.push({ elapsedMs, sample });
    appendPrivateEvent(outputRoot, {
      event: "process_sample",
      elapsedMs,
      sample,
    });
    if (sample.some((entry) => !entry.alive)) {
      result.resources.processCrashes += sample.filter(
        (entry) => !entry.alive,
      ).length;
      throw new Error("runtime_process_crashed");
    }
    await page.waitForTimeout(
      Math.min(
        runtime.snapshotIntervalMs,
        Math.max(0, durationMs - (Date.now() - startedAt)),
      ),
    );
  }
  const elapsedMinutes = (Date.now() - startedAt) / 60_000;
  if (kind === "audible") {
    result.execution.audibleMinutesObserved =
      Math.round(elapsedMinutes * 1000) / 1000;
    const probe = await browserProbe(page);
    result.execution.audioPlaybackEvents = Math.max(
      result.execution.audioPlaybackEvents,
      probe.audioPlaybackEvents,
    );
    const audibleGaps = [];
    let priorEvidenceAt = 0;
    for (const evidenceAt of audibleEvidenceAtMs) {
      audibleGaps.push(evidenceAt - priorEvidenceAt);
      priorEvidenceAt = evidenceAt;
    }
    audibleGaps.push(durationMs - priorEvidenceAt);
    result.execution.audibleEvidenceWindows = new Set(
      audibleEvidenceAtMs.map((timestamp) =>
        timestamp < 20 * 60_000
          ? "early"
          : timestamp < 45 * 60_000
            ? "middle"
            : "late",
      ),
    ).size;
    result.execution.maxAudibleEvidenceGapSeconds =
      Math.round((Math.max(...audibleGaps) / 1000) * 1000) / 1000;
    gate(
      result,
      "audible-65-minute-scenario",
      elapsedMinutes >= PLAN.audibleMinutes &&
        result.execution.audibleEvidenceWindows === 3 &&
        result.execution.maxAudibleEvidenceGapSeconds <= 1200,
      result.execution.audibleMinutesObserved,
      PLAN.audibleMinutes,
    );
    const scenario = result.execution.scenario;
    const scenarioComplete =
      scenario.authoritativeSources > 0 &&
      scenario.distinctSpeakerKeys >= 2 &&
      scenario.bargeIns > 0 &&
      scenario.cancellations > 0 &&
      scenario.networkLosses > 0 &&
      scenario.providerDegradations > 0 &&
      scenario.observedDegradedStates > 0 &&
      scenario.participantJoins > 0 &&
      scenario.participantLeaves > 0 &&
      scenario.refreshes > 0 &&
      scenario.modeChanges > 0 &&
      scenario.cleanHangups > 0;
    gate(
      result,
      "audible-scenario-coverage",
      scenarioComplete,
      scenarioComplete ? 12 : 0,
      12,
    );
  } else {
    result.execution.soakMinutesObserved =
      Math.round(elapsedMinutes * 1000) / 1000;
    result.resources.processesObserved = runtime.processes.length;
    const warmAtMs = runtime.warmupMinutes * 60_000;
    let maxGrowth = 0;
    for (const processConfig of runtime.processes) {
      const baselineEntry = processSamples
        .find((entry) => entry.elapsedMs >= warmAtMs)
        ?.sample.find((sample) => sample.name === processConfig.name);
      const finalEntry = processSamples
        .at(-1)
        ?.sample.find((sample) => sample.name === processConfig.name);
      if (!baselineEntry?.rssKb || !finalEntry?.rssKb) {
        result.resources.missingPostWarmSamples += 1;
        continue;
      }
      const growth =
        ((finalEntry.rssKb - baselineEntry.rssKb) / baselineEntry.rssKb) * 100;
      maxGrowth = Math.max(maxGrowth, growth);
      if (growth > 10) {
        result.resources.overTenPercentGrowth += 1;
      }
    }
    result.resources.maxPostWarmGrowthPercent =
      Math.round(maxGrowth * 1000) / 1000;
    result.resources.leakedTasks = previous.tasks.filter((task) =>
      ACTIVE_TASK_STATES.has(task.state),
    ).length;
    gate(
      result,
      "automated-120-minute-soak",
      elapsedMinutes >= PLAN.soakMinutes &&
        runtime.processes.length > 0 &&
        result.resources.processCrashes === 0 &&
        result.resources.overTenPercentGrowth === 0 &&
        result.resources.missingPostWarmSamples === 0 &&
        result.resources.leakedTasks === 0 &&
        replayPassed(result.replay),
      result.execution.soakMinutesObserved,
      PLAN.soakMinutes,
    );
  }
}

async function runRuntime(args) {
  const runtime = loadRuntimeConfig(args.config, args.profile);
  const result = baseResult(args.profile, runtime.environment);
  result.execution.runtimeGatesExecuted = true;
  const { chromium } = requirePlaywright();
  const launchArgs = [
    "--use-fake-ui-for-media-stream",
    "--use-fake-device-for-media-stream",
  ];
  if (runtime.audioFile) {
    launchArgs.push(`--use-file-for-fake-audio-capture=${runtime.audioFile}`);
  }
  let browser;
  try {
    browser = await chromium.launch({
      channel: "chrome",
      headless: !args.headed,
      args: launchArgs,
    });
    const context = await browser.newContext();
    await context.grantPermissions(["microphone"], {
      origin: runtime.playgroundOrigin,
    });
    const page = await context.newPage();
    await installBrowserProbe(page);
    const callStartAt = Date.now();
    await page.goto(runtime.callUrl, {
      waitUntil: "domcontentloaded",
      timeout: 45_000,
    });
    await assertCallBootstrapStripped(page, runtime.callSessionId);
    await waitForConnected(page);
    result._timingSamples.callStartToListeningMs.push(Date.now() - callStartAt);
    result.execution.browserConnected = true;
    appendPrivateEvent(args.outputRoot, { event: "browser_connected" });
    await page.screenshot({
      path: path.join(args.outputRoot, "browser-connected.png"),
      fullPage: true,
    });
    result.evidence.screenshots += 1;

    if (args.profile === "switches") {
      await runModeSwitches(page, runtime, result, args.outputRoot);
    }
    if (args.profile === "reconnects") {
      await runReconnects(page, context, runtime, result, args.outputRoot);
    }
    if (args.profile === "audible") {
      await runTimedProfile(
        "audible",
        page,
        context,
        runtime,
        args,
        result,
        args.outputRoot,
      );
    }
    if (args.profile === "soak") {
      await runTimedProfile(
        "soak",
        page,
        context,
        runtime,
        args,
        result,
        args.outputRoot,
      );
    }

    if (runtime.logs.length) {
      result.latency = readTraceSummary(runtime.logs);
      result.evidence.latencyLogs = runtime.logs.length;
    }
    applyMeasuredEvidence(result, runtime, args.profile);
    gate(
      result,
      "task-speaker-result-replay",
      replayPassed(result.replay),
      0,
      0,
    );
    if (args.profile === "audible" || args.profile === "soak") {
      gate(
        result,
        "structured-latency-traces",
        result.latency.traceCount > 0 &&
          result.latency.incompleteTraceCount === 0,
        result.latency.completeTraceCount,
        result.latency.traceCount,
      );
      gate(
        result,
        "voice-hop-ordering",
        result.latency.outOfOrderTraceCount === 0,
        result.latency.outOfOrderTraceCount,
        0,
      );
      gate(
        result,
        "voice-hop-first-breach",
        result.latency.firstBreachCount === 0,
        result.latency.firstBreachCount,
        0,
      );
    }
    result.status = result.gates.every((item) =>
      ["PASS", "NOT_APPLICABLE"].includes(item.status),
    )
      ? "PASS"
      : "FAIL";
    return result;
  } catch (error) {
    result.status = result.execution.browserConnected ? "FAIL" : "BLOCKED";
    result.failures.push({
      code: /^[a-z0-9_]{1,80}$/i.test(String(error?.message || ""))
        ? String(error.message)
        : "runtime_acceptance_failed",
      caseId: "MPV-025-044",
    });
    return result;
  } finally {
    for (const participant of runtime._participants?.values?.() || []) {
      await participant.browser.close().catch(() => {});
    }
    await browser?.close().catch(() => {});
  }
}

async function main() {
  let args;
  try {
    args = parseArgs(process.argv.slice(2));
    fs.mkdirSync(args.outputRoot, { recursive: true, mode: 0o700 });
    const result = args.selfTest ? selfTestResult() : await runRuntime(args);
    assertSanitizedResult(result);
    writeJson(args.result, result);
    process.stdout.write(`${result.status}\n`);
    process.exitCode = result.status === "PASS" ? 0 : 1;
  } catch (error) {
    process.stderr.write(
      `${String(error?.message || "acceptance_harness_failed")}\n`,
    );
    process.exitCode = 2;
  }
}

if (require.main === module) {
  void main();
}

module.exports = {
  PLAN,
  applyMeasuredEvidence,
  assertCallBootstrapStripped,
  auditReplay,
  baseResult,
  extractVoiceHopTraces,
  fetchJsonInPage,
  parseArgs,
  summarizeVoiceHopTraces,
};
