#!/usr/bin/env node
"use strict";

const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const Module = require("node:module");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const { EventEmitter } = require("node:events");
const { afterEach, test } = require("node:test");

const runner = require("./run_mpv_061_installed_journey.cjs");
const preparer = require("./prepare_mpv_061_installed_scenario.cjs");
const temporaryRoots = new Set();

function privateRoot() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "mpv061-contract-"));
  fs.chmodSync(root, 0o700);
  temporaryRoots.add(root);
  return fs.realpathSync(root);
}

function privateFile(root, name, value) {
  const target = path.join(root, name);
  const content = Buffer.isBuffer(value)
    ? value
    : Buffer.from(typeof value === "string" ? value : JSON.stringify(value));
  fs.writeFileSync(target, content, { mode: 0o600, flag: "wx" });
  fs.chmodSync(target, 0o600);
  return target;
}

function audibleWav(seed = 1) {
  const samples = Buffer.alloc(3200);
  for (let offset = 0; offset < samples.length; offset += 2) {
    samples.writeInt16LE(offset % 4 === 0 ? 1400 + seed : -1400 - seed, offset);
  }
  const header = Buffer.alloc(44);
  header.write("RIFF", 0);
  header.writeUInt32LE(36 + samples.length, 4);
  header.write("WAVE", 8);
  header.write("fmt ", 12);
  header.writeUInt32LE(16, 16);
  header.writeUInt16LE(1, 20);
  header.writeUInt16LE(1, 22);
  header.writeUInt32LE(8000, 24);
  header.writeUInt32LE(16000, 28);
  header.writeUInt16LE(2, 32);
  header.writeUInt16LE(16, 34);
  header.write("data", 36);
  header.writeUInt32LE(samples.length, 40);
  return Buffer.concat([header, samples]);
}

function scenarioFixture(root) {
  const initialAudio = privateFile(root, "initial.wav", audibleWav(1));
  const reconnectAudio = privateFile(root, "reconnect.wav", audibleWav(2));
  const attachmentA = privateFile(root, "attachment-a.bin", "fixture input A");
  const attachmentB = privateFile(root, "attachment-b.bin", "fixture input B");
  const identity = privateFile(root, "identity.json", { contractVersion: 1 });
  const mongoUriFile = privateFile(root, "runtime-handoff.json", {
    schema: "viventium.voice.mpv-061.runtime-handoff.v1",
    MONGO_URI: "mongodb://127.0.0.1:27017/fixture",
  });
  return {
    schema: runner.SCENARIO_SCHEMA,
    caseId: "MPV-061",
    environment: "installed_prod",
    artifactIdentity: identity,
    runtime: {
      playgroundUrl: "http://127.0.0.1:3300",
      coreUrl: "http://127.0.0.1:3190",
      mongoUriFile,
      assistant: { provider: "fixture-provider", model: "fixture-exact-model" },
      agent: { id: "agent_fixture_main", name: "fixture-voice-gateway" },
    },
    audio: { initial: initialAudio, reconnect: reconnectAudio },
    turns: runner.EXECUTION_TURNS.map((turn, index) => ({
      kind: turn.kind,
      mode: turn.mode,
      directlyAddressed: turn.directlyAddressed,
      ...(turn.speakerRole ? { speakerRole: turn.speakerRole } : {}),
      expectedTranscript: `Fixture speech turn ${index + 1}`,
      armAfterMs: index * 2000 + 1000,
      startAfterMs: index * 2000 + 2000,
    })),
    attachments: [
      {
        worker: "A",
        path: attachmentA,
        dispatchInstruction: "Send only this file to mission alpha.",
      },
      {
        worker: "B",
        path: attachmentB,
        dispatchInstruction: "Send only this file to mission bravo.",
      },
    ],
    requirements: {
      providerFallback: {
        required: true,
        controlledTrigger: {
          kind: "mpv_061_parent_private_fd_v1",
          caseId: "MPV-061",
          targetTurnKind: "trustedWingLaunch",
          approvalWaitMs: 750,
        },
        reason: "parent_approved_pre_model_fault",
      },
    },
    restart: {
      executable: path.join(runner.REPOSITORY_ROOT, "bin", "viventium"),
      arguments: [
        "dev-runtime",
        "activate-current",
        "--validate",
        "--restart",
        "--allow-protected-folder",
        "--allow-dirty-local-testing",
      ],
    },
    outputs: {
      manifest: path.join(root, "full-journey-evidence.v1.json"),
      result: path.join(root, "full-journey-result.v1.json"),
      cleanupState: path.join(root, "cleanup-state.v1.json"),
    },
  };
}

function scenarioPath(root, scenario = scenarioFixture(root)) {
  return privateFile(root, "scenario.json", scenario);
}

function blockerIs(code) {
  return (error) =>
    error instanceof runner.JourneyBlocked && error.code === code;
}

function traceRef(kind, value) {
  return (
    "sha256:" +
    crypto
      .createHash("sha256")
      .update(kind + "\u0000" + value)
      .digest("hex")
  );
}

function traceCandidateFacts(candidate) {
  return {
    candidateDigest: "sha256:" + candidate.candidateDigest,
    installedArtifactDigest: "sha256:" + candidate.artifactDigest,
    runtimeOwnerBindingHash:
      "sha256:" + candidate.runtimeBinding.ownerBindingSha256,
  };
}

function canonicalJson(value) {
  if (Array.isArray(value)) {
    return `[${value.map((entry) => canonicalJson(entry)).join(",")}]`;
  }
  if (value && typeof value === "object") {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

function measuredCandidateFixture({ dirty = false } = {}) {
  const checks = [
    "SOURCE-IDENTITY",
    "NESTED-PINS",
    "PREBUILT-IDENTITY",
    "INSTALLED-ARTIFACT",
  ].map((id, index) => ({
    id,
    status: dirty && index < 2 ? "FAIL" : "PASS",
    reason: dirty && index < 2 ? "measured_dirty_candidate" : "",
  }));
  return {
    candidateDigest: "a".repeat(64),
    artifactDigest: "b".repeat(64),
    checks,
    runtimeBinding: {
      active: true,
      ownerRootMatches: true,
      runtimeRootMatches: true,
      ownerBindingSha256: "c".repeat(64),
      processIdentitySha256: "d".repeat(64),
    },
    measuredIdentity: {
      source: {
        revision: "1".repeat(40),
        worktreeHash: "e".repeat(64),
        componentsLockSha256: "f".repeat(64),
        clean: !dirty,
      },
      nestedComponents: [
        {
          name: "LibreChat",
          pin: "2".repeat(40),
          revision: dirty ? "3".repeat(40) : "2".repeat(40),
          worktreeHash: "4".repeat(64),
          clean: !dirty,
        },
      ],
      prebuiltHelper: {
        sourceMeasuredSha256: "5".repeat(64),
        binaryMeasuredSha256: "6".repeat(64),
      },
      installed: {
        rootRevision: "7".repeat(40),
        runningServiceSha256: "8".repeat(64),
        frontendBuildSha256: "9".repeat(64),
        apiBuildSha256: "0".repeat(64),
      },
    },
  };
}

function candidateBindingFixture(mode = "strict") {
  const measured = measuredCandidateFixture({ dirty: mode === "diagnostic" });
  const checks = measured.checks.map(({ id, status, reason }) => ({
    id,
    status,
    reason,
  }));
  const base = {
    verified: true,
    candidateMode: mode,
    releaseCandidateVerified: mode === "strict",
    acceptanceEligible: mode === "strict",
    receiptEligible: mode === "strict",
    candidateDigest: measured.candidateDigest,
    artifactDigest: measured.artifactDigest,
    checks,
    identityFailures: checks.filter((check) => check.status !== "PASS"),
    runtimeBinding: measured.runtimeBinding,
    measuredIdentity: measured.measuredIdentity,
  };
  return mode === "diagnostic"
    ? {
        ...base,
        status: "PRE_GATE_COMPLETE",
        releaseReady: false,
        releaseLabel: "PRE-GATE / NOT READY",
      }
    : base;
}

function privateRunnerBindings() {
  const loaded = new Module(runner.RUNNER_PATH, module);
  loaded.filename = runner.RUNNER_PATH;
  loaded.paths = Module._nodeModulePaths(path.dirname(runner.RUNNER_PATH));
  loaded._compile(
    fs.readFileSync(runner.RUNNER_PATH, "utf8") +
      "\nObject.assign(module.exports, { createSearchIndexObserver, " +
      "InstalledJourneyRuntime, projectObservedJourney, completedProviderAttempt });\n",
    runner.RUNNER_PATH,
  );
  return loaded.exports;
}

function signedObservation(overrides = {}) {
  const now = 1_780_000_000_000;
  const verdict = {
    version: 1,
    callSessionId: "fixture-call-session",
    turnId: "fixture-logical-turn",
    participantIdentity: "fixture-owner-participant",
    segmentIds: ["fixture-final-segment"],
    directlyAddressed: true,
    source: "semantic_model",
    revision: 4,
    issuedAtMs: now - 1000,
    expiresAtMs: now + 29_000,
    attestation: "a".repeat(43),
  };
  return {
    now,
    observation: {
      transportObserved: true,
      requestUrl: "http://127.0.0.1:3300/api/call-engagement",
      responseStatus: 200,
      model: { provider: "fixture-provider", model: "fixture-exact-model" },
      verdict: { ...verdict, ...(overrides.verdict || {}) },
      finalSegments: [
        {
          segmentId: "fixture-final-segment",
          turnId: "fixture-logical-turn",
          callSessionId: "fixture-call-session",
          isFinal: true,
          revision: 4,
          overlap: false,
          uncertain: false,
          speaker: {
            attribution: "verified",
            actorTrust: "owner_participant",
            participantIdentity: "fixture-owner-participant",
          },
        },
      ],
      ...overrides,
    },
    expected: {
      callSessionId: "fixture-call-session",
      turnId: "fixture-logical-turn",
      participantIdentity: "fixture-owner-participant",
      playgroundUrl: "http://127.0.0.1:3300",
      assistant: { provider: "fixture-provider", model: "fixture-exact-model" },
    },
  };
}

function passiveTurnFixture({ signed = true, delayedUnsafe = false } = {}) {
  const internal = privateRunnerBindings();
  const fixture = signedObservation();
  const now = Date.now();
  fixture.observation.verdict.directlyAddressed = false;
  fixture.observation.verdict.issuedAtMs = now - 100;
  fixture.observation.verdict.expiresAtMs = now + 29_000;
  const segment = {
    ...fixture.observation.finalSegments[0],
    text: "Synthetic passive speech",
  };
  fixture.observation.finalSegments = [segment];
  const planes = [
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
  ];
  const emptyLedger = () => ({
    work: [],
    trace: [],
    bindings: [],
    missions: [],
    capabilities: [],
    callbacks: [],
    deliveries: [],
  });
  let reads = 0;
  const runtime = Object.create(internal.InstalledJourneyRuntime.prototype);
  runtime.seeded = {
    userId: "aaaaaaaaaaaaaaaaaaaaaaaa",
    callSessionId: fixture.observation.verdict.callSessionId,
    ownerParticipantIdentity: fixture.observation.verdict.participantIdentity,
  };
  runtime.scenario = {
    runtime: {
      playgroundUrl: "http://127.0.0.1:3300",
      assistant: fixture.expected.assistant,
    },
    observation: { passiveSettleMs: 20 },
  };
  runtime.schedulerDatabase = "/private/test-only-schedules.db";
  runtime.helpers = {
    inspectSyntheticSchedules() {
      return delayedUnsafe && reads >= 3
        ? { total: 1, bootstrap: 0, unsafe: 1 }
        : { total: 0, bootstrap: 0, unsafe: 0 };
    },
  };
  runtime.signedResponses = signed ? [fixture.observation] : [];
  runtime.windows = [];
  runtime.callPage = {
    locator: () => ({ innerText: async () => "Synthetic passive speech" }),
  };
  runtime.db = {
    collection(name) {
      return {
        async findOne() {
          if (name === "viventiumcallsessions") {
            return {
              mode: "wing",
              userId: runtime.seeded.userId,
              callModeRevision: 1,
            };
          }
          if (name === "messages") {
            return {
              user: runtime.seeded.userId,
              metadata: {
                viventium: {
                  type: "voice_ambient_transcript",
                  mode: "wing",
                  ingressKind: "ambient_participant",
                  callSessionId: runtime.seeded.callSessionId,
                  turnId: segment.turnId,
                  speakerSegments: [segment],
                },
              },
            };
          }
          return {
            userId: runtime.seeded.userId,
            callSessionId: runtime.seeded.callSessionId,
            status: "listen_only",
            saved: true,
            segments: [{ speakerSegments: [segment] }],
          };
        },
      };
    },
  };
  runtime.snapshot = async () => {
    reads += 1;
    const unsafe = delayedUnsafe && reads >= 3;
    const ledger = emptyLedger();
    if (unsafe) {
      ledger.work.push({ workRef: "unauthorized-worker" });
      ledger.trace.push({ stage: "tool.called" });
    }
    return {
      ledger,
      segments: reads === 1 ? [] : [segment],
      stages: Object.fromEntries(
        planes.map((plane) => [plane, unsafe && plane === "tool" ? 1 : 0]),
      ),
      tasks: [],
      messages: [],
      schedules: runtime.helpers.inspectSyntheticSchedules(),
    };
  };
  return {
    runtime,
    turn: {
      kind: "passiveWingDenial",
      mode: "wing",
      directlyAddressed: false,
      armAfterMs: 0,
      startAfterMs: 100,
      timeoutMs: 1000,
      denialTimeoutMs: 40,
      expectedTranscript: "Synthetic passive speech",
    },
    reads: () => reads,
  };
}

function mockCollection(rows, calls, name) {
  return {
    find(filter) {
      calls.push({ name, filter });
      return {
        sort() {
          return this;
        },
        limit() {
          return this;
        },
        async toArray() {
          return rows[name] || [];
        },
      };
    },
  };
}

class FixtureObjectId {
  constructor(value) {
    this.value = String(value);
  }

  toString() {
    return this.value;
  }
}

function exactFixtureFilter(row, filter) {
  return Object.entries(filter).every(([key, expected]) => {
    if (
      expected &&
      typeof expected === "object" &&
      Array.isArray(expected.$in)
    ) {
      return expected.$in.some((value) => String(value) === String(row[key]));
    }
    return String(row[key]) === String(expected);
  });
}

function residueFixture() {
  const ownerId = "aaaaaaaaaaaaaaaaaaaaaaaa";
  const personalId = "bbbbbbbbbbbbbbbbbbbbbbbb";
  const email = ["viventium-voice-qa-fixture", "example.com"].join("@");
  const startedAtMs = 1_780_000_000_000;
  const schedulerDatabase = privateFile(
    privateRoot(),
    "schedules.db",
    "fixture scheduler",
  );
  const ownerObject = new FixtureObjectId(ownerId);
  const personalObject = new FixtureObjectId(personalId);
  const ownerScopeHash =
    "sha256:" +
    crypto
      .createHash("sha256")
      .update("owner\u0000" + ownerId)
      .digest("hex");
  const personalScopeHash =
    "sha256:" +
    crypto
      .createHash("sha256")
      .update("owner\u0000" + personalId)
      .digest("hex");
  const rows = {
    users: [
      { _id: ownerObject, email, createdAt: new Date(startedAtMs) },
      { _id: personalObject, email: "owner@viventium.local" },
    ],
    conversations: [
      {
        _id: "conversation-a",
        user: ownerId,
        conversationId: "synthetic-conversation",
      },
      {
        _id: "conversation-personal",
        user: personalId,
        conversationId: "personal-conversation",
      },
    ],
    messages: [
      { _id: "message-a", user: ownerId, messageId: "synthetic-message" },
      {
        _id: "message-personal",
        user: personalId,
        messageId: "personal-message",
      },
    ],
    memoryentries: [
      { _id: "memory-a", userId: ownerObject },
      { _id: "memory-personal", userId: personalObject },
    ],
    viventium_scheduler_dispatch_intents: [
      { _id: "dispatch-a", userId: ownerId },
      { _id: "dispatch-personal", userId: personalId },
    ],
    viventiumglasshivecallbackeffectoutboxes: [
      { _id: "outbox-a", ownerId },
      { _id: "outbox-personal", ownerId: personalId },
    ],
    files: [
      {
        _id: "file-a",
        user: ownerObject,
        file_id: "synthetic-vector",
        embedded: true,
      },
      {
        _id: "file-personal",
        user: personalObject,
        file_id: "personal-vector",
        embedded: true,
      },
    ],
    sessions: [
      { _id: "session-a", user: ownerObject },
      { _id: "session-personal", user: personalObject },
    ],
    viventiumcallsessions: [
      { _id: "call-a", userId: ownerId, callSessionId: "synthetic-call" },
      {
        _id: "call-personal",
        userId: personalId,
        callSessionId: "personal-call",
      },
    ],
    viventiumvoicetasks: [
      { _id: "voice-task-a", userId: ownerId, callSessionId: "synthetic-call" },
      {
        _id: "voice-task-personal",
        userId: personalId,
        callSessionId: "personal-call",
      },
    ],
    viventiumvoicespeakersegments: [
      { _id: "speaker-a", callSessionId: "synthetic-call" },
      { _id: "speaker-personal", callSessionId: "personal-call" },
    ],
    viventiumvoiceingressevents: [
      { _id: "ingress-a", userId: ownerId, callSessionId: "synthetic-call" },
      {
        _id: "ingress-personal",
        userId: personalId,
        callSessionId: "personal-call",
      },
    ],
  };
  for (const definition of runner.LEDGER_COLLECTIONS) {
    const syntheticScope =
      definition.ownerField === "ownerScopeHash" ? ownerScopeHash : ownerId;
    const personalScope =
      definition.ownerField === "ownerScopeHash"
        ? personalScopeHash
        : personalId;
    rows[definition.name] = [
      {
        _id: definition.key + "-synthetic",
        [definition.ownerField]: syntheticScope,
      },
      {
        _id: definition.key + "-personal",
        [definition.ownerField]: personalScope,
      },
    ];
  }
  const deleted = [];
  const database = {
    collection(name) {
      rows[name] ||= [];
      return {
        async findOne(filter) {
          return (
            rows[name].find((row) => exactFixtureFilter(row, filter)) || null
          );
        },
        find(filter) {
          return {
            async toArray() {
              return rows[name].filter((row) =>
                exactFixtureFilter(row, filter),
              );
            },
          };
        },
        async countDocuments(filter) {
          return rows[name].filter((row) => exactFixtureFilter(row, filter))
            .length;
        },
        async deleteMany(filter) {
          deleted.push({ name, filter });
          const before = rows[name].length;
          rows[name] = rows[name].filter(
            (row) => !exactFixtureFilter(row, filter),
          );
          return { deletedCount: before - rows[name].length };
        },
        async deleteOne(filter) {
          deleted.push({ name, filter });
          const index = rows[name].findIndex((row) =>
            exactFixtureFilter(row, filter),
          );
          if (index >= 0) {
            rows[name].splice(index, 1);
          }
          return { deletedCount: index >= 0 ? 1 : 0 };
        },
      };
    },
  };
  let schedules = 1;
  const helpers = {
    async cancelSyntheticActiveVoiceTasks() {},
    inspectSyntheticSchedules(_seeded, selectedDatabase) {
      assert.equal(selectedDatabase, schedulerDatabase);
      return { total: schedules, bootstrap: schedules, unsafe: 0 };
    },
    cleanupSyntheticSchedules(_seeded, selectedDatabase) {
      assert.equal(selectedDatabase, schedulerDatabase);
      const removed = schedules;
      schedules = 0;
      return removed;
    },
  };
  const indexed = [];
  const vectors = [];
  const storedFiles = [];
  const searchIndex = {
    async removeAndVerify(value) {
      indexed.push(value);
      return { remaining: 0 };
    },
  };
  const vectorIndex = {
    async removeAndVerify(value) {
      vectors.push(value);
      return { remaining: 0 };
    },
  };
  const fileStorage = {
    async removeAndVerify(value) {
      storedFiles.push(value);
      return { remaining: 0 };
    },
  };
  return {
    database,
    rows,
    deleted,
    helpers,
    indexed,
    vectors,
    storedFiles,
    searchIndex,
    vectorIndex,
    fileStorage,
    schedulerDatabase,
    seeded: {
      userId: ownerId,
      email,
      callSessionId: "synthetic-call",
      browserCapability: "a".repeat(43),
    },
    proof: { ownerId, email, insertedAtMs: startedAtMs, acknowledged: true },
    personalId,
  };
}

function observedJourneyFixture(root) {
  const scenario = scenarioFixture(root);
  scenario.observation = { fallbackStage: "provider.fallback.completed" };
  const ownerId = "aaaaaaaaaaaaaaaaaaaaaaaa";
  const ownerScopeHash =
    "sha256:" +
    crypto
      .createHash("sha256")
      .update("owner\u0000" + ownerId)
      .digest("hex");
  const sessionId = "observed-initial-session";
  const reconnectId = "observed-reconnect-session";
  const conversationId = "observed-conversation";
  const speakerIdentity = "observed-main-speaker";
  const candidate = candidateBindingFixture();
  const now = Date.now();
  const observedFile = (name, content) => {
    const filePath = privateFile(root, name, content);
    const bytes = fs.readFileSync(filePath);
    return {
      path: filePath,
      bytes,
      sha256: crypto.createHash("sha256").update(bytes).digest("hex"),
    };
  };
  const outputAudio = {
    initial: observedFile("captured-initial-output.wav", audibleWav(11)),
    reconnect: observedFile("captured-reconnect-output.wav", audibleWav(12)),
  };
  const outputArtifacts = [
    observedFile(
      "captured-artifact-a.bin",
      "independently delivered artifact A",
    ),
    observedFile(
      "captured-artifact-b.bin",
      "independently delivered artifact B",
    ),
  ];
  const rawWorkers = ["A", "B"].map((label, index) => ({
    ownerId,
    workRef: "observed-work-" + label.toLowerCase(),
    originRef: "observed-mission-" + label.toLowerCase(),
    runId: "observed-attempt-" + label.toLowerCase(),
    launchState: "accepted",
    externalState: "completed",
    title: "Observed worker " + label,
    terminalAt: new Date(now + index + 1).toISOString(),
  }));
  const liveWorkers = rawWorkers.map((worker) => ({
    ...worker,
    externalState: "running",
  }));
  const probe = {
    ownerId,
    workRef: "observed-wing-probe",
    originRef: "observed-probe-mission",
    runId: "observed-probe-attempt",
    launchState: "accepted",
    externalState: "cancelled_confirmed",
  };
  const bindings = [...rawWorkers, probe].map((worker, index) => ({
    ownerId,
    workRef: worker.workRef,
    originRef: worker.originRef,
    runId: worker.runId,
    objectiveOrdinal: index,
    conversationId,
    acceptedOperationId: "observed-launch-" + worker.workRef,
  }));
  const missions = rawWorkers.map((worker) => ({
    ownerId,
    workRef: worker.workRef,
    originRef: worker.originRef,
    runId: worker.runId,
    conversationId,
  }));
  const callbacks = rawWorkers.map((worker, index) => ({
    ownerId,
    workRef: worker.workRef,
    runId: worker.runId,
    callbackId:
      "cb_terminal_" +
      crypto
        .createHash("sha256")
        .update("observed-callback-" + index)
        .digest("hex"),
    acceptedOperationId: crypto
      .createHash("sha256")
      .update("observed-terminal-operation-" + index)
      .digest("hex")
      .slice(0, 32),
    resultDigest:
      "sha256:" +
      crypto
        .createHash("sha256")
        .update("observed-terminal-result-" + index)
        .digest("hex"),
    artifactId: "observed-artifact-" + index,
    artifactSha256: outputArtifacts[index].sha256,
    state: "delivered",
  }));
  const deliveries = rawWorkers.map((worker, index) => ({
    userId: ownerId,
    workRef: worker.workRef,
    runId: worker.runId,
    artifactId: "observed-artifact-" + index,
    artifactSha256: outputArtifacts[index].sha256,
    state: "sent",
    callSessionId: reconnectId,
    traceIdentityVerified: true,
    terminalCallbackId: callbacks[index].callbackId,
    terminalCallbackAcceptedOperationId: callbacks[index].acceptedOperationId,
    terminalCallbackResultDigest: callbacks[index].resultDigest,
  }));
  const capabilities = rawWorkers.map((worker, index) => ({
    ownerId,
    workRef: worker.workRef,
    originRef: worker.originRef,
    contextBindingMatched: true,
    requiredCapabilitiesPreserved: true,
    fallbackCapabilityLossCount: 0,
    memoryRecallReceiptCount: index === 0 ? 1 : 0,
    connectedToolReceiptCount: index === 1 ? 1 : 0,
  }));
  const actionEvents = [
    [
      {
        ownerScopeHash,
        stage: "action.accepted",
        facts: {
          callSessionRefHash: traceRef("call_session", sessionId),
          logicalTurnRefHash: traceRef("logical_turn", "observed-turn-4"),
          workRefHash: traceRef("work", rawWorkers[0].workRef),
          actionRefHash: traceRef("work_action", "observed-message-operation"),
          receiptRefHash: traceRef(
            "effect_receipt",
            "observed-message-receipt",
          ),
          ...traceCandidateFacts(candidate),
          effectPlane: "control",
          outcome: "accepted",
          action: "message",
          effectCount: 1,
        },
      },
      {
        ownerScopeHash,
        stage: "control.completed",
        facts: {
          callSessionRefHash: traceRef("call_session", sessionId),
          logicalTurnRefHash: traceRef("logical_turn", "observed-turn-4"),
          workRefHash: traceRef("work", rawWorkers[0].workRef),
          actionRefHash: traceRef("work_action", "observed-message-operation"),
          receiptRefHash: traceRef(
            "effect_receipt",
            "observed-message-receipt",
          ),
          ...traceCandidateFacts(candidate),
          effectPlane: "control",
          outcome: "completed",
          action: "message",
          effectCount: 1,
        },
      },
    ],
    [
      {
        ownerScopeHash,
        stage: "action.accepted",
        facts: {
          callSessionRefHash: traceRef("call_session", sessionId),
          logicalTurnRefHash: traceRef("logical_turn", "observed-turn-5"),
          workRefHash: traceRef("work", rawWorkers[0].workRef),
          actionRefHash: traceRef("work_action", "observed-steer-operation"),
          receiptRefHash: traceRef("effect_receipt", "observed-steer-receipt"),
          ...traceCandidateFacts(candidate),
          effectPlane: "control",
          outcome: "accepted",
          action: "steer",
          effectCount: 1,
        },
      },
      {
        ownerScopeHash,
        stage: "control.completed",
        facts: {
          callSessionRefHash: traceRef("call_session", sessionId),
          logicalTurnRefHash: traceRef("logical_turn", "observed-turn-5"),
          workRefHash: traceRef("work", rawWorkers[0].workRef),
          actionRefHash: traceRef("work_action", "observed-steer-operation"),
          receiptRefHash: traceRef("effect_receipt", "observed-steer-receipt"),
          ...traceCandidateFacts(candidate),
          effectPlane: "control",
          outcome: "completed",
          action: "steer",
          effectCount: 1,
        },
      },
    ],
  ];
  const fallbackEvent = {
    ownerScopeHash,
    stage: scenario.observation.fallbackStage,
    facts: {
      callSessionRefHash: traceRef("call_session", sessionId),
      logicalTurnRefHash: traceRef("logical_turn", "observed-turn-2"),
      ...traceCandidateFacts(candidate),
      effectPlane: "provider",
      outcome: "completed",
      primaryProvider: "fixture-primary-provider",
      primaryModel: "fixture-primary-model",
      primaryProviderStatus: "failed",
      fallbackProvider: "fixture-fallback-provider",
      fallbackModel: "fixture-fallback-model",
      fallbackProviderStatus: "completed",
      configuredFallback: true,
      requiredCapabilitiesPreserved: true,
      primaryAttemptRefHash: traceRef(
        "provider_attempt",
        "observed-primary-attempt",
      ),
      fallbackAttemptRefHash: traceRef(
        "provider_attempt",
        "observed-fallback-attempt",
      ),
    },
  };
  const fallbackAttemptEvent = {
    ownerScopeHash,
    stage: "provider.attempt.completed",
    facts: {
      callSessionRefHash: fallbackEvent.facts.callSessionRefHash,
      logicalTurnRefHash: fallbackEvent.facts.logicalTurnRefHash,
      ...traceCandidateFacts(candidate),
      effectPlane: "provider",
      outcome: "completed",
      provider: fallbackEvent.facts.fallbackProvider,
      model: fallbackEvent.facts.fallbackModel,
      providerStatus: "completed",
      attemptRole: "fallback",
      attemptRefHash: fallbackEvent.facts.fallbackAttemptRefHash,
    },
  };
  const classifierFaultReceipt = {
    schema: "viventium.voice.mpv-061.classifier-fault-receipt.v1",
    caseId: "MPV-061",
    controlId: "mpv061_" + "c".repeat(24),
    receiptDigest: "sha256:" + "d".repeat(64),
    receiptExpiresAt: new Date(now + 15 * 60 * 1000).toISOString(),
    candidate: traceCandidateFacts(candidate),
  };
  const receiptRefHash = traceRef(
    "effect_receipt",
    classifierFaultReceipt.receiptDigest,
  );
  const primaryHistoryEvent = {
    ownerScopeHash,
    stage: "attempt.history.complete",
    facts: {
      callSessionRefHash: fallbackEvent.facts.callSessionRefHash,
      logicalTurnRefHash: fallbackEvent.facts.logicalTurnRefHash,
      ...traceCandidateFacts(candidate),
      effectPlane: "provider",
      outcome: "completed",
      state: "failed",
      providerStatus: "failed",
      attemptRole: "primary",
      provider: fallbackEvent.facts.primaryProvider,
      model: fallbackEvent.facts.primaryModel,
      attemptRefHash: fallbackEvent.facts.primaryAttemptRefHash,
      receiptRefHash,
      producerAttemptHistoryHash:
        "sha256:" +
        crypto
          .createHash("sha256")
          .update(
            canonicalJson({
              schemaVersion: 1,
              failure: "provider_temporarily_unavailable",
              preModel: true,
              state: "failed",
              providerStatus: "failed",
              attemptRole: "primary",
              provider: fallbackEvent.facts.primaryProvider,
              model: fallbackEvent.facts.primaryModel,
              primaryStartedCount: 0,
              primaryCompletedCount: 0,
              providerHealthMutationCount: 0,
              providerHealthSuppressed: false,
            }),
          )
          .digest("hex"),
    },
  };
  const fallbackStartedEvent = {
    ownerScopeHash,
    stage: "provider.request.forwarded",
    facts: {
      callSessionRefHash: fallbackEvent.facts.callSessionRefHash,
      logicalTurnRefHash: fallbackEvent.facts.logicalTurnRefHash,
      ...traceCandidateFacts(candidate),
      effectPlane: "provider",
      outcome: "accepted",
      state: "running",
      attemptRole: "fallback",
      provider: fallbackEvent.facts.fallbackProvider,
      model: fallbackEvent.facts.fallbackModel,
      attemptRefHash: fallbackEvent.facts.fallbackAttemptRefHash,
      providerRequestRefHash: traceRef(
        "provider_request",
        "observed-fallback-request",
      ),
      receiptRefHash,
      configuredFallback: true,
    },
  };
  const ledger = {
    source: "owner_scoped_worker_mission_action_delivery_ledger",
    ownerScopeHash,
    work: [...rawWorkers, probe],
    bindings,
    missions,
    capabilities,
    callbacks,
    deliveries,
    trace: [
      ...actionEvents.flat(),
      primaryHistoryEvent,
      fallbackStartedEvent,
      fallbackAttemptEvent,
      fallbackEvent,
    ],
  };
  const stageKeys = [
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
  ];
  const snapshot = (work = liveWorkers, trace = []) => ({
    ledger: { ...ledger, work, trace, callbacks: [], deliveries: [] },
    stages: Object.fromEntries(stageKeys.map((key) => [key, 0])),
    messages: [],
    sessions: [
      {
        userId: ownerId,
        callSessionId: sessionId,
        conversationId,
        mode: "call",
      },
    ],
    segments: [],
    schedules: { total: 0, bootstrap: 0, unsafe: 0 },
  });
  const effectCounts = [
    {
      mission: 2,
      launch: 1,
      tool: 1,
      controller: 1,
      response: 1,
      tts: 1,
      audio: 1,
    },
    {
      mission: 1,
      launch: 1,
      tool: 1,
      controller: 1,
      response: 1,
      tts: 1,
      audio: 1,
    },
    { response: 1, tts: 1, audio: 1 },
    {
      action: 1,
      control: 1,
      tool: 1,
      controller: 1,
      response: 1,
      tts: 1,
      audio: 1,
    },
    {
      action: 1,
      control: 1,
      tool: 1,
      controller: 1,
      response: 1,
      tts: 1,
      audio: 1,
    },
    {},
    {},
  ];
  const windows = runner.REQUIRED_TURNS.map((turn, index) => {
    const counts = effectCounts[index];
    const segment = {
      segmentId: "observed-segment-" + (index + 1),
      turnId: "observed-turn-" + (index + 1),
      callSessionId: sessionId,
      isFinal: true,
      revision: index + 1,
      text: scenario.turns[index].expectedTranscript,
      speaker: {
        attribution: "verified",
        actorTrust: "owner_participant",
        participantIdentity: "observed-owner-participant",
      },
    };
    const before = snapshot(index === 0 ? [] : liveWorkers);
    const after = snapshot(
      index === 1
        ? [...liveWorkers, { ...probe, externalState: "running" }]
        : liveWorkers,
      index === 3 ? actionEvents[0] : index === 4 ? actionEvents[1] : [],
    );
    if (counts.response) {
      after.messages.push({
        user: ownerId,
        role: "assistant",
        agentId: speakerIdentity,
        turnId: segment.turnId,
        conversationId,
      });
    }
    return {
      ...turn,
      segment,
      before,
      after,
      transcriptDelta: 1,
      missionDelta: counts.mission || 0,
      actionDelta: counts.action || 0,
      scheduleDelta: 0,
      unsafeScheduleCount: 0,
      ...Object.fromEntries(
        stageKeys.map((key) => [key + "Delta", counts[key] || 0]),
      ),
      ...(turn.mode === "wing" && turn.directlyAddressed
        ? { authority: { directlyAddressed: true } }
        : {}),
      ...(!turn.directlyAddressed || turn.mode === "listen_only"
        ? {
            denial: { durable: true, signed: turn.mode === "wing" ? {} : null },
          }
        : {}),
    };
  });
  const unverifiedIndex = runner.REQUIRED_TURNS.length;
  const unverifiedTurn = runner.EXECUTION_TURNS[unverifiedIndex];
  const unverifiedSegment = {
    segmentId: "observed-segment-unverified",
    turnId: "observed-turn-unverified",
    callSessionId: sessionId,
    isFinal: true,
    revision: unverifiedIndex + 1,
    text: scenario.turns[unverifiedIndex].expectedTranscript,
    speaker: {
      attribution: "unverified",
      actorTrust: "shared_mic_unverified",
      participantIdentity: "observed-owner-participant",
    },
  };
  windows.push({
    ...unverifiedTurn,
    segment: unverifiedSegment,
    before: snapshot(liveWorkers),
    after: { ...snapshot(liveWorkers), segments: [unverifiedSegment] },
    transcriptDelta: 1,
    scheduleDelta: 0,
    unsafeScheduleCount: 0,
    ...Object.fromEntries(
      ["mission", "action", ...stageKeys].map((key) => [key + "Delta", 0]),
    ),
    denial: {
      durable: true,
      signed: null,
      engagement: {
        transportObserved: true,
        responseStatus: 403,
        code: "voice_engagement_not_authorized",
        turnId: unverifiedSegment.turnId,
      },
      ingressStatus: "ambient_participant",
      session: {
        userId: ownerId,
        callSessionId: sessionId,
        ownerParticipantIdentity: "observed-owner-participant",
        speakerAttributionState: "shared_mic_unverified",
      },
    },
  });
  const uploads = scenario.attachments.map((attachment, index) => {
    const bytes = fs.readFileSync(attachment.path);
    return {
      worker: attachment.worker,
      targetWorkRef: rawWorkers[index].workRef,
      file: {
        _id: "observed-upload-" + index,
        file_id: "observed-file-" + index,
        user: ownerId,
        bytes: bytes.length,
      },
      message: {
        user: ownerId,
        conversationId,
        isCreatedByUser: true,
        messageId: "observed-upload-message-" + index,
        attachments: [{ file_id: "observed-file-" + index }],
      },
      observed: {
        path: attachment.path,
        bytes,
        sha256: crypto.createHash("sha256").update(bytes).digest("hex"),
      },
    };
  });
  for (let index = 0; index < uploads.length; index += 1) {
    capabilities[index].hostToolResources = {
      file_search: {
        files: [
          {
            file_id: uploads[index].file.file_id,
            sha256: uploads[index].observed.sha256,
          },
        ],
      },
    };
  }
  const surfaces = {
    before: {
      label: "before-hangup",
      response: { items: liveWorkers },
      visible: liveWorkers.map((worker) => worker.title).join(" "),
      rows: liveWorkers,
      screenshot: privateFile(
        root,
        "surface-before.png",
        "observed before screenshot",
      ),
    },
    after: {
      label: "after-reconnect",
      response: { items: rawWorkers },
      visible: rawWorkers.map((worker) => worker.title).join(" "),
      rows: rawWorkers,
      screenshot: privateFile(
        root,
        "surface-after.png",
        "observed after screenshot",
      ),
    },
  };
  const completions = rawWorkers.map((worker, index) => ({
    ownerId,
    callSessionId: reconnectId,
    conversationId,
    workRef: worker.workRef,
    turnId: "observed-turn-" + (index + 8),
    revision: index + 8,
    speakerIdentity,
    messageId: "observed-completion-message-" + index,
    transcriptVisible: true,
    responseCount: 1,
    ttsCount: 1,
    audioCount: 1,
  }));
  const workerTraces = rawWorkers.map((worker, index) => {
    const reference = (kind, value) =>
      "sha256:" +
      crypto
        .createHash("sha256")
        .update(kind + "\u0000" + value)
        .digest("hex");
    return {
      workRef: worker.workRef,
      originRef: worker.originRef,
      response: {
        version: 2,
        traceRef: reference("origin", worker.originRef),
        workRef: reference("work", worker.workRef),
        completionClaims: { allowed: true },
        ledger: { chain: { fullChainVerified: true } },
        integrity: {
          ownerScoped: true,
          completionClaimable: true,
          artifactRefs: { status: "verified" },
        },
        current: {
          workState: "completed",
          artifactRefs: {
            available: true,
            refs: [
              {
                artifactRef: "artifact_sha256:" + outputArtifacts[index].sha256,
                fingerprint: "sha256:" + outputArtifacts[index].sha256,
              },
            ],
          },
        },
      },
    };
  });
  return {
    scenario,
    observation: {
      candidate,
      runAt: new Date(now).toISOString(),
      ownerId,
      initialSession: {
        userId: ownerId,
        callSessionId: sessionId,
        ownerParticipantIdentity: "observed-owner-participant",
        conversationId,
        callStatus: "ended",
      },
      reconnectSession: {
        userId: ownerId,
        callSessionId: reconnectId,
        conversationId,
        mode: "call",
      },
      sessions: [
        { userId: ownerId, callSessionId: sessionId, conversationId },
        { userId: ownerId, callSessionId: reconnectId, conversationId },
      ],
      conversationId,
      windows,
      workers: liveWorkers,
      probe: {
        work: probe,
        operationId: "observed-probe-stop-operation",
        response: {
          status: 202,
          payload: {
            operationId: "observed-probe-stop-operation",
            receiptId: "observed-probe-stop-receipt",
          },
        },
      },
      uploads,
      ledger,
      surfaces,
      artifacts: rawWorkers.map((worker, index) => ({
        worker,
        observed: outputArtifacts[index],
        opened: true,
      })),
      audio: outputAudio,
      fallback: [fallbackEvent],
      classifierFaultReceipt,
      completions,
      workerTraces,
      runtime: {
        before: "observed-runtime-before",
        after: "observed-runtime-after",
        restart: {
          before: "observed-runtime-before",
          after: "observed-runtime-after",
          workerRefs: rawWorkers.map((worker) => worker.workRef),
          invoked: true,
          exitCode: 0,
          survivingWorkRefs: rawWorkers.map((worker) => worker.workRef),
          mainAvailableBefore: true,
          mainAvailableAfter: true,
          callSessionId: sessionId,
          survivingCallSessionId: sessionId,
          callConversationId: conversationId,
        },
      },
    },
  };
}

afterEach(() => {
  for (const root of temporaryRoots) {
    fs.rmSync(root, { recursive: true, force: true });
  }
  temporaryRoots.clear();
});

test("CLI refuses both explicit consent boundaries before creating evidence", () => {
  const root = privateRoot();
  const target = path.join(root, "not-created");
  for (const [arguments_, expected] of [
    [["--evidence-root", target], "local_qa_opt_in_required"],
    [
      ["--local-qa", "--evidence-root", target],
      "synthetic_fixture_opt_in_required",
    ],
  ]) {
    const completed = spawnSync(
      process.execPath,
      [runner.RUNNER_PATH, ...arguments_],
      {
        cwd: runner.REPOSITORY_ROOT,
        encoding: "utf8",
      },
    );
    assert.equal(completed.status, 2);
    assert.deepEqual(JSON.parse(completed.stdout), {
      caseId: "MPV-061",
      status: "BLOCKED",
      blocker: expected,
    });
    assert.equal(fs.existsSync(target), false);
  }
});

test("argument parsing rejects unknown flags without exposing their values", () => {
  assert.throws(
    () => runner.parseArguments(["--local-qa", "--private-token=do-not-print"]),
    blockerIs("unknown_argument"),
  );
});

test("diagnostic candidate mode is explicit, visible, and never receipt eligible", () => {
  assert.deepEqual(runner.DIAGNOSTIC_CANDIDATE_CONTRACT, {
    version: 1,
    supported: true,
    status: "PRE_GATE_COMPLETE",
    releaseReady: false,
    releaseCandidateVerified: false,
    acceptanceEligible: false,
    receiptEligible: false,
    releaseLabel: "PRE-GATE / NOT READY",
  });
  assert.equal(
    runner.parseArguments(["--candidate-mode", "diagnostic"]).candidateMode,
    "diagnostic",
  );
  assert.throws(
    () => runner.parseArguments(["--candidate-mode", "release-ish"]),
    blockerIs("candidate_mode_invalid"),
  );
});

test("strict and diagnostic candidate validators never share release identity", () => {
  const clean = runner.assertStrictCandidate(measuredCandidateFixture());
  assert.equal(clean.candidateMode, "strict");
  assert.equal(clean.releaseCandidateVerified, true);
  assert.equal(clean.acceptanceEligible, true);
  assert.equal(clean.receiptEligible, true);

  const dirtyMeasurement = measuredCandidateFixture({ dirty: true });
  assert.throws(
    () => runner.assertStrictCandidate(dirtyMeasurement),
    blockerIs("strict_candidate_identity_invalid"),
  );
  const diagnostic = runner.assertDiagnosticCandidate(dirtyMeasurement);
  assert.equal(diagnostic.candidateMode, "diagnostic");
  assert.equal(diagnostic.releaseCandidateVerified, false);
  assert.equal(diagnostic.acceptanceEligible, false);
  assert.equal(diagnostic.receiptEligible, false);
  assert.equal(diagnostic.releaseLabel, "PRE-GATE / NOT READY");
  assert.equal(diagnostic.identityFailures.length, 2);
  assert.throws(
    () =>
      runner.assertDiagnosticCandidate({
        ...dirtyMeasurement,
        runtimeBinding: {
          ...dirtyMeasurement.runtimeBinding,
          processIdentitySha256: "",
        },
      }),
    blockerIs("diagnostic_active_runtime_identity_unproven"),
  );
});

test("observer contract names only real producer-owned stages and exposes every gap", () => {
  const allowed = new Set([
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
    "work.running",
    "work.completed",
    "work.failed",
    "work.cancelled",
    "attempt.history.complete",
    "capacity.history.complete",
    "callback.history.complete",
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
    "provider.request.forwarded",
    "provider.fallback.completed",
  ]);
  const contract = runner.SCENARIO_OBSERVER_CONTRACT;
  const producerSource = fs.readFileSync(
    path.join(
      runner.REPOSITORY_ROOT,
      "viventium_v0_4",
      "LibreChat",
      "packages",
      "api",
      "src",
      "trace",
      "orchestrationTraceLedger.ts",
    ),
    "utf8",
  );
  const stageType = producerSource.match(
    /export type TraceStage =([\s\S]*?);\n\nexport interface TraceEventFactsInput/,
  );
  assert.ok(stageType);
  const sourceStages = [...stageType[1].matchAll(/\| '([^']+)'/g)].map(
    (match) => match[1],
  );
  assert.equal(contract.version, 1);
  assert.deepEqual(contract.producerOwnedStages, sourceStages);
  assert.equal(contract.runtimeIdentityFileKind, "stack_owner");
  assert.deepEqual(contract.runtimeIdentityFields, ["ownerBindingSha256"]);
  const namedStages = [
    ...Object.values(contract.effectStages).flat(),
    ...(contract.fallback?.stages || []),
  ];
  assert.ok(namedStages.length > 0);
  assert.ok(namedStages.every((stage) => allowed.has(stage)));
  assert.deepEqual(contract.effectStages, {
    launch: ["launch.prepared", "launch.accepted", "launch.failed"],
    control: ["action.accepted", "control.completed"],
    tool: ["tool.completed"],
    controller: ["controller.completed"],
    cortex: ["cortex.completed"],
    liveMemory: ["live_memory.completed"],
    recall: ["recall.completed"],
    titleModel: ["title_model.completed"],
    response: ["response.completed"],
    tts: ["tts.completed"],
    audio: ["audio.completed"],
  });
  assert.deepEqual(contract.unavailableEffectPlanes, []);
  assert.deepEqual(contract.fallback, {
    available: true,
    stages: [
      "attempt.history.complete",
      "provider.request.forwarded",
      "provider.attempt.completed",
      "provider.fallback.completed",
    ],
    controlledTriggerAvailable: true,
    defaultRequirement: "required",
  });
  assert.deepEqual(contract.workerCompletionDelivery, {
    available: true,
    producerScope: "librechat.voice_worker_completion_delivery",
    stages: ["response.completed", "tts.completed", "audio.completed"],
    blocker: null,
  });
  assert.throws(
    () => runner.assertScenarioObserverAvailable({ observation: {} }),
    blockerIs("full_journey_observer_unavailable"),
  );
  const observation = {
    observerContractVersion: contract.version,
    producerScope: contract.producerScope,
    runtimeIdentityFileKind: contract.runtimeIdentityFileKind,
    runtimeIdentityFile: "/private/runtime-owner.json",
    effectStages: contract.effectStages,
    fallbackStage: "provider.fallback.completed",
    fallbackStages: contract.fallback.stages,
  };
  assert.equal(
    runner.assertScenarioObserverAvailable({ observation }),
    observation,
  );
});

test("turn effects count only exact owner call turn and candidate trace facts", () => {
  const internal = privateRunnerBindings();
  const ownerId = "aaaaaaaaaaaaaaaaaaaaaaaa";
  const callSessionId = "exact-call";
  const turnId = "exact-turn";
  const candidate = candidateBindingFixture();
  const runtime = Object.create(internal.InstalledJourneyRuntime.prototype);
  runtime.seeded = { userId: ownerId, callSessionId };
  runtime.identityDigests = candidate;
  runtime.stageMap = Object.fromEntries(
    Object.entries(runner.SCENARIO_OBSERVER_CONTRACT.effectStages).map(
      ([plane, stages]) => [plane, new Set(stages)],
    ),
  );
  const event = (stage, effectPlane, overrides = {}) => ({
    ownerScopeHash: traceRef("owner", ownerId),
    stage,
    facts: {
      callSessionRefHash: traceRef("call_session", callSessionId),
      logicalTurnRefHash: traceRef("logical_turn", turnId),
      ...traceCandidateFacts(candidate),
      effectPlane,
      outcome: stage === "action.accepted" ? "accepted" : "completed",
      ...overrides,
    },
  });
  const validAction = event("action.accepted", "control", {
    action: "steer",
  });
  const validControl = event("control.completed", "control", {
    action: "steer",
  });
  const validResponse = event("response.completed", "response");
  const foreignCandidate = event("response.completed", "response", {
    candidateDigest: "sha256:" + "f".repeat(64),
  });
  const stageCounts = Object.fromEntries(
    Object.keys(runtime.stageMap).map((plane) => [plane, 0]),
  );
  const before = {
    segments: [],
    ledger: { work: [], trace: [] },
    stages: stageCounts,
  };
  const after = {
    segments: [{}],
    ledger: {
      work: [],
      trace: [validAction, validControl, validResponse, foreignCandidate],
    },
    stages: { ...stageCounts, control: 2, response: 2 },
  };
  const window = runtime.windowFrom(
    before,
    after,
    { kind: "trustedWingControl", mode: "wing", directlyAddressed: true },
    { turnId },
  );

  assert.equal(window.actionDelta, 1);
  assert.equal(window.controlDelta, 1);
  assert.equal(window.responseDelta, 1);
});

test("existing evidence roots must be exact private owner directories", () => {
  const root = privateRoot();
  assert.equal(runner.inspectEvidenceRoot(root), fs.realpathSync(root));
  fs.chmodSync(root, 0o750);
  assert.throws(
    () => runner.inspectEvidenceRoot(root),
    blockerIs("evidence_root_not_private"),
  );
  assert.equal(fs.statSync(root).mode & 0o777, 0o750);
});

test("evidence roots reject a symlinked root and symlinked ancestor", () => {
  const root = privateRoot();
  const actual = path.join(root, "actual");
  fs.mkdirSync(actual, 0o700);
  const alias = path.join(root, "alias");
  fs.symlinkSync(actual, alias, "dir");
  assert.throws(
    () => runner.inspectEvidenceRoot(alias),
    blockerIs("evidence_root_symlink_forbidden"),
  );
  assert.throws(
    () => runner.inspectEvidenceRoot(path.join(alias, "nested")),
    blockerIs("evidence_root_symlink_forbidden"),
  );
});

test("scenario files reject public permissions, aliases, and public repository paths", () => {
  const root = privateRoot();
  const source = scenarioPath(root);
  fs.chmodSync(source, 0o640);
  assert.throws(
    () => runner.readPrivateJson(source, "scenario"),
    blockerIs("scenario_not_private"),
  );
  fs.chmodSync(source, 0o600);
  const alias = path.join(root, "scenario-alias.json");
  fs.symlinkSync(source, alias);
  assert.throws(
    () => runner.readPrivateJson(alias, "scenario"),
    blockerIs("scenario_symlink_forbidden"),
  );
  assert.throws(
    () => runner.readPrivateJson(runner.RUNNER_PATH, "scenario"),
    blockerIs("scenario_inside_repository"),
  );
});

test("a complete private scenario preserves seven semantic phases and the unverified denial probe", () => {
  const root = privateRoot();
  const scenario = scenarioFixture(root);
  const validated = runner.validateScenario(scenario, root, {
    MPV061_CONTRACT_MONGO_URI: "mongodb://127.0.0.1:27017/fixture",
  });
  assert.deepEqual(
    validated.turns.map((turn) => turn.kind),
    runner.EXECUTION_TURNS.map((turn) => turn.kind),
  );
  assert.equal(validated.attachments.length, 2);
});

test("scenario rejects an incomplete journey before a synthetic account exists", () => {
  const root = privateRoot();
  const scenario = scenarioFixture(root);
  scenario.turns.pop();
  assert.throws(
    () => runner.validateScenario(scenario, root, {}),
    blockerIs("scenario_turn_order_invalid"),
  );
});

test("scenario rejects mode or owner-addressing assertions that change the case", () => {
  for (const mutation of [
    (scenario) => {
      scenario.turns[1].mode = "call";
    },
    (scenario) => {
      scenario.turns[5].directlyAddressed = true;
    },
  ]) {
    const root = privateRoot();
    const scenario = scenarioFixture(root);
    mutation(scenario);
    assert.throws(
      () => runner.validateScenario(scenario, root, {}),
      blockerIs("scenario_turn_contract_invalid"),
    );
  }
});

test("scenario must declare one exact installed model and local-only origins", () => {
  const root = privateRoot();
  const scenario = scenarioFixture(root);
  delete scenario.runtime.assistant.model;
  assert.throws(
    () => runner.validateScenario(scenario, root, {}),
    blockerIs("exact_model_unavailable"),
  );
  scenario.runtime.assistant.model = "fixture-exact-model";
  scenario.runtime.playgroundUrl = "https://remote.example.test";
  assert.throws(
    () => runner.validateScenario(scenario, root, {}),
    blockerIs("runtime_origin_not_local"),
  );
});

test("scenario never generates or substitutes missing prerecorded user audio", () => {
  const root = privateRoot();
  const scenario = scenarioFixture(root);
  scenario.audio.initial = path.join(root, "unrecorded.wav");
  assert.throws(
    () => runner.validateScenario(scenario, root, {}),
    blockerIs("initial_audio_unavailable"),
  );
  assert.equal(fs.existsSync(scenario.audio.initial), false);
});

test("scenario rejects silent user media and aliased attachment bytes", () => {
  const root = privateRoot();
  const scenario = scenarioFixture(root);
  fs.writeFileSync(scenario.audio.initial, Buffer.alloc(44));
  fs.chmodSync(scenario.audio.initial, 0o600);
  assert.throws(
    () => runner.validateScenario(scenario, root, {}),
    blockerIs("initial_audio_not_audible"),
  );

  fs.writeFileSync(scenario.audio.initial, audibleWav(1));
  fs.chmodSync(scenario.audio.initial, 0o600);
  scenario.attachments[1].path = scenario.attachments[0].path;
  assert.throws(
    () => runner.validateScenario(scenario, root, {}),
    blockerIs("attachment_identity_not_distinct"),
  );
});

test("scenario rejects evidence outputs outside the selected root", () => {
  const root = privateRoot();
  const scenario = scenarioFixture(root);
  scenario.outputs.result = path.join(
    os.tmpdir(),
    "mpv061-result-outside.json",
  );
  assert.throws(
    () => runner.validateScenario(scenario, root, {}),
    blockerIs("result_outside_evidence_root"),
  );
});

test("MongoDB prerequisites remain loopback-only and never expose credentials", () => {
  assert.doesNotThrow(() =>
    runner.assertLocalMongoUri("mongodb://127.0.0.1:27017/fixture"),
  );
  assert.throws(
    () =>
      runner.assertLocalMongoUri(
        "mongodb://fixture-user:fixture-password@viventium.local/fixture",
      ),
    blockerIs("mongo_not_local"),
  );
  assert.throws(
    () => runner.assertLocalMongoUri(""),
    blockerIs("mongo_uri_unavailable"),
  );
});

test("signed owner Wing authority accepts only an observed exact-model Core response", () => {
  const { observation, expected, now } = signedObservation();
  const actual = runner.validateSignedWingAuthority(observation, expected, now);
  assert.equal(actual.directlyAddressed, true);
  assert.equal(actual.source, "semantic_model");
});

test("Wing authority rejects an unobserved or self-declared signature", () => {
  for (const override of [
    { transportObserved: false },
    { responseStatus: 503 },
    { requestUrl: "http://attacker.example.test/api/call-engagement" },
    { verdict: { source: "browser_assertion" } },
    { verdict: { attestation: "not-a-signature" } },
  ]) {
    const { observation, expected, now } = signedObservation(override);
    assert.throws(() =>
      runner.validateSignedWingAuthority(observation, expected, now),
    );
  }
});

test("Wing authority rejects stale, cross-turn, cross-owner, and negative verdicts", () => {
  for (const verdict of [
    { expiresAtMs: 1_779_999_999_999 },
    { turnId: "different-turn" },
    { participantIdentity: "different-owner" },
    { directlyAddressed: false },
    { segmentIds: ["unobserved-segment"] },
  ]) {
    const { observation, expected, now } = signedObservation({ verdict });
    assert.throws(() =>
      runner.validateSignedWingAuthority(observation, expected, now),
    );
  }
});

test("Wing authority rejects an unverified owner speaker or a changed model", () => {
  const fixture = signedObservation();
  fixture.observation.finalSegments[0].speaker.attribution = "unverified";
  assert.throws(
    () =>
      runner.validateSignedWingAuthority(
        fixture.observation,
        fixture.expected,
        fixture.now,
      ),
    blockerIs("wing_owner_speaker_unverified"),
  );

  const changedModel = signedObservation({
    model: { provider: "fixture-provider", model: "other-model" },
  });
  assert.throws(
    () =>
      runner.validateSignedWingAuthority(
        changedModel.observation,
        changedModel.expected,
        changedModel.now,
      ),
    blockerIs("wing_exact_model_not_observed"),
  );
});

test("owner ledger uses exact account filters and never reads another owner", async () => {
  const calls = [];
  const ownerId = "aaaaaaaaaaaaaaaaaaaaaaaa";
  const ownerScopeHash = `sha256:${crypto
    .createHash("sha256")
    .update(`owner\u0000${ownerId}`)
    .digest("hex")}`;
  const rows = Object.fromEntries(
    runner.LEDGER_COLLECTIONS.map((entry) => [
      entry.name,
      [
        {
          [entry.ownerField]:
            entry.ownerField === "ownerScopeHash" ? ownerScopeHash : ownerId,
        },
      ],
    ]),
  );
  const database = { collection: (name) => mockCollection(rows, calls, name) };
  const ledger = await runner.captureOwnerLedger(database, ownerId);
  assert.equal(
    ledger.source,
    "owner_scoped_worker_mission_action_delivery_ledger",
  );
  assert.equal(calls.length, runner.LEDGER_COLLECTIONS.length);
  for (const call of calls) {
    const definition = runner.LEDGER_COLLECTIONS.find(
      (entry) => entry.name === call.name,
    );
    assert.equal(
      call.filter[definition.ownerField],
      definition.ownerField === "ownerScopeHash" ? ownerScopeHash : ownerId,
    );
  }
});

test("owner ledger rejects a foreign or unbound returned document", async () => {
  const calls = [];
  const ownerId = "aaaaaaaaaaaaaaaaaaaaaaaa";
  const collection = runner.LEDGER_COLLECTIONS[0];
  const rows = {
    [collection.name]: [{ [collection.ownerField]: "different-owner" }],
  };
  const database = { collection: (name) => mockCollection(rows, calls, name) };
  await assert.rejects(
    () => runner.captureOwnerLedger(database, ownerId),
    blockerIs("owner_ledger_scope_mismatch"),
  );
});

test("passive Wing and Listen-Only deny every observed side-effect plane", () => {
  for (const mode of ["wing", "listen_only"]) {
    runner.assertPassiveDenial({
      mode,
      transcriptDelta: 1,
      missionDelta: 0,
      actionDelta: 0,
      launchDelta: 0,
      controlDelta: 0,
      toolDelta: 0,
      controllerDelta: 0,
      cortexDelta: 0,
      liveMemoryDelta: 0,
      recallDelta: 0,
      titleModelDelta: 0,
      responseDelta: 0,
      ttsDelta: 0,
      audioDelta: 0,
    });
  }
  assert.throws(
    () =>
      runner.assertPassiveDenial({
        mode: "wing",
        transcriptDelta: 1,
        missionDelta: 1,
      }),
    blockerIs("passive_mode_side_effect_observed"),
  );
  assert.throws(
    () =>
      runner.assertPassiveDenial({ mode: "listen_only", transcriptDelta: 0 }),
    blockerIs("passive_mode_transcript_unobserved"),
  );
});

test("semantic PASS is accepted only from the authoritative full-journey verifier", () => {
  const result = {
    caseId: "MPV-061",
    status: "PASS",
    scope: "full_journey",
    fullJourneyStatus: "PASS",
    authoritySliceOnlyPassAccepted: false,
    candidateBinding: { matched: true },
    privacy: { publicSafe: true },
    gates: [{ id: "full-journey-scope", status: "PASS" }],
  };
  assert.equal(runner.acceptSemanticVerifierResult(result, 0).status, "PASS");
  assert.throws(
    () =>
      runner.acceptSemanticVerifierResult(
        { ...result, scope: "authority_slice_only" },
        0,
      ),
    blockerIs("full_journey_semantic_verification_missing"),
  );
  assert.throws(
    () =>
      runner.acceptSemanticVerifierResult(
        { ...result, gates: [{ status: "FAIL" }] },
        0,
      ),
    blockerIs("full_journey_semantic_verification_missing"),
  );
});

test("public results never disclose owner identifiers, paths, URLs, or credentials", () => {
  const result = runner.sanitizePublicResult({
    caseId: "MPV-061",
    status: "BLOCKED",
    blocker: "owner_ledger_unavailable",
    evidenceRoot: "/private/customer/account",
    ownerId: "aaaaaaaaaaaaaaaaaaaaaaaa",
    token: "secret-token",
    modelResponse: "private response",
  });
  assert.deepEqual(result, {
    caseId: "MPV-061",
    status: "BLOCKED",
    blocker: "owner_ledger_unavailable",
  });
});

test("diagnostic execution requires opt-in and the exact measured scenario binding", async () => {
  const root = privateRoot();
  const scenario = scenarioFixture(root);
  const candidate = candidateBindingFixture("diagnostic");
  scenario.candidate = candidate;
  const source = scenarioPath(root, scenario);
  const args = [
    "--local-qa",
    "--allow-synthetic-account",
    "--allow-runtime-restart",
    "--candidate-mode",
    "diagnostic",
    "--evidence-root",
    root,
    "--scenario",
    source,
  ];
  let created = false;
  const dependencies = {
    environment: {
      MPV061_CONTRACT_MONGO_URI: "mongodb://127.0.0.1:27017/fixture",
      VIVENTIUM_QA_ALLOW_MPV061_RUNTIME_RESTART: "1",
    },
    inspectCandidate: () => candidate,
    createRuntime: () => {
      created = true;
      return { async preflight() {}, async execute() {}, async cleanup() {} };
    },
  };
  const noOptIn = await runner.runInstalledJourney(args, dependencies);
  assert.deepEqual(noOptIn, {
    caseId: "MPV-061",
    status: "BLOCKED",
    blocker: "diagnostic_candidate_requires_explicit_opt_in",
    candidateMode: "diagnostic",
    releaseReady: false,
    receiptEligible: false,
    releaseLabel: "PRE-GATE / NOT READY",
  });
  assert.equal(created, false);

  dependencies.environment.VIVENTIUM_QA_ALLOW_DIAGNOSTIC_CANDIDATE = "1";
  const mismatch = structuredClone(candidate);
  mismatch.candidateDigest = "f".repeat(64);
  scenario.candidate = mismatch;
  fs.writeFileSync(source, JSON.stringify(scenario));
  fs.chmodSync(source, 0o600);
  const wrongBinding = await runner.runInstalledJourney(args, dependencies);
  assert.equal(wrongBinding.status, "BLOCKED");
  assert.equal(wrongBinding.blocker, "scenario_candidate_binding_mismatch");
  assert.equal(wrongBinding.receiptEligible, false);
  assert.equal(created, false);
});

test("completed diagnostic journey stays PRE-GATE, skips receipt verifier, and binds cleanup", async () => {
  const root = privateRoot();
  const scenario = scenarioFixture(root);
  const candidate = candidateBindingFixture("diagnostic");
  scenario.candidate = candidate;
  const source = scenarioPath(root, scenario);
  let verifierInvoked = false;
  let runtimeCandidate;
  let cleanupContext;
  const result = await runner.runInstalledJourney(
    [
      "--local-qa",
      "--allow-synthetic-account",
      "--allow-runtime-restart",
      "--candidate-mode",
      "diagnostic",
      "--evidence-root",
      root,
      "--scenario",
      source,
    ],
    {
      environment: {
        MPV061_CONTRACT_MONGO_URI: "mongodb://127.0.0.1:27017/fixture",
        VIVENTIUM_QA_ALLOW_MPV061_RUNTIME_RESTART: "1",
        VIVENTIUM_QA_ALLOW_DIAGNOSTIC_CANDIDATE: "1",
      },
      inspectCandidate: () => candidate,
      createRuntime: (configuration) => {
        runtimeCandidate = configuration.identityDigests;
        return {
          async preflight() {},
          async execute() {},
          async cleanup(context) {
            cleanupContext = context;
          },
        };
      },
      semanticVerifier: async () => {
        verifierInvoked = true;
        return { status: "PASS" };
      },
    },
  );
  assert.deepEqual(result, {
    caseId: "MPV-061",
    status: "PRE_GATE_COMPLETE",
    scope: "full_journey",
    candidateMode: "diagnostic",
    diagnosticPass: true,
    releaseReady: false,
    receiptEligible: false,
    releaseLabel: "PRE-GATE / NOT READY",
  });
  assert.deepEqual(runtimeCandidate, candidate);
  assert.deepEqual(cleanupContext.candidateBinding, candidate);
  assert.equal(cleanupContext.failure, null);
  assert.equal(verifierInvoked, false);
  assert.equal(fs.existsSync(scenario.outputs.result), false);
});

test("diagnostic mode refuses a pre-existing release result without overwriting it", async () => {
  const root = privateRoot();
  const scenario = scenarioFixture(root);
  const candidate = candidateBindingFixture("diagnostic");
  scenario.candidate = candidate;
  const source = scenarioPath(root, scenario);
  const stale = Buffer.from('{"status":"PASS","forged":true}\n');
  fs.writeFileSync(scenario.outputs.result, stale, { mode: 0o600, flag: "wx" });
  let created = false;
  const result = await runner.runInstalledJourney(
    [
      "--local-qa",
      "--allow-synthetic-account",
      "--allow-runtime-restart",
      "--candidate-mode",
      "diagnostic",
      "--evidence-root",
      root,
      "--scenario",
      source,
    ],
    {
      environment: {
        MPV061_CONTRACT_MONGO_URI: "mongodb://127.0.0.1:27017/fixture",
        VIVENTIUM_QA_ALLOW_MPV061_RUNTIME_RESTART: "1",
        VIVENTIUM_QA_ALLOW_DIAGNOSTIC_CANDIDATE: "1",
      },
      inspectCandidate: () => candidate,
      createRuntime: () => {
        created = true;
      },
    },
  );
  assert.equal(result.status, "BLOCKED");
  assert.equal(result.blocker, "diagnostic_release_receipt_path_not_empty");
  assert.equal(result.receiptEligible, false);
  assert.equal(created, false);
  assert.deepEqual(fs.readFileSync(scenario.outputs.result), stale);
});

test("an incomplete private scenario cannot invoke an injected runtime or write evidence", async () => {
  const root = privateRoot();
  const scenario = scenarioFixture(root);
  scenario.turns.pop();
  const source = scenarioPath(root, scenario);
  let executed = false;
  const result = await runner.runInstalledJourney(
    [
      "--local-qa",
      "--allow-synthetic-account",
      "--evidence-root",
      root,
      "--scenario",
      source,
    ],
    {
      environment: {
        MPV061_CONTRACT_MONGO_URI: "mongodb://127.0.0.1:27017/fixture",
      },
      createRuntime: () => {
        executed = true;
      },
    },
  );
  assert.equal(result.status, "BLOCKED");
  assert.equal(result.blocker, "scenario_turn_order_invalid");
  assert.equal(executed, false);
  assert.equal(fs.existsSync(scenario.outputs.manifest), false);
  assert.equal(fs.existsSync(scenario.outputs.result), false);
});

test("missing observed resilience blocks diagnostic execution before any receipt", async () => {
  const root = privateRoot();
  const scenario = scenarioFixture(root);
  const candidate = candidateBindingFixture("diagnostic");
  scenario.candidate = candidate;
  const source = scenarioPath(root, scenario);
  let verifierInvoked = false;
  const result = await runner.runInstalledJourney(
    [
      "--local-qa",
      "--allow-synthetic-account",
      "--allow-runtime-restart",
      "--candidate-mode",
      "diagnostic",
      "--evidence-root",
      root,
      "--scenario",
      source,
    ],
    {
      environment: {
        MPV061_CONTRACT_MONGO_URI: "mongodb://127.0.0.1:27017/fixture",
        VIVENTIUM_QA_ALLOW_MPV061_RUNTIME_RESTART: "1",
        VIVENTIUM_QA_ALLOW_DIAGNOSTIC_CANDIDATE: "1",
      },
      inspectCandidate: () => candidate,
      createRuntime: () => ({
        async preflight() {},
        async execute() {
          throw new runner.JourneyBlocked("runtime_restart_not_observed");
        },
        async cleanup() {},
      }),
      semanticVerifier: async () => {
        verifierInvoked = true;
      },
    },
  );
  assert.equal(result.status, "BLOCKED");
  assert.equal(result.blocker, "runtime_restart_not_observed");
  assert.equal(verifierInvoked, false);
  assert.equal(fs.existsSync(scenario.outputs.result), false);
});

test("fresh synthetic owner proof requires this run's acknowledged exact insertion", async () => {
  const inserted = [];
  const ownerId = "aaaaaaaaaaaaaaaaaaaaaaaa";
  const email = ["viventium-voice-qa-fixture", "example.com"].join("@");
  const createdAt = new Date(1_780_000_000_000);
  const user = { _id: ownerId, email, createdAt };
  const database = {
    collection(name) {
      assert.equal(name, "users");
      return {
        async insertOne(row) {
          inserted.push(row);
          return { acknowledged: true, insertedId: row._id };
        },
        async findOne(filter) {
          return exactFixtureFilter(user, filter) ? user : null;
        },
      };
    },
  };
  const helpers = {
    async seedCallSession(scoped) {
      await scoped.collection("users").insertOne(user);
      return { userId: ownerId, email, callSessionId: "fresh-call" };
    },
  };
  const observed = await runner.seedFreshSyntheticOwner(
    database,
    helpers,
    {},
    {
      startedAtMs: createdAt.getTime(),
    },
  );
  assert.equal(observed.proof.ownerId, ownerId);
  assert.equal(observed.proof.acknowledged, true);
  assert.equal(inserted.length, 1);
});

test("an existing or swapped account cannot become this run's cleanup target", async () => {
  const database = {
    collection() {
      return {
        async findOne() {
          throw new Error("existing_owner_must_not_be_read");
        },
      };
    },
  };
  const helpers = {
    async seedCallSession() {
      return {
        userId: "bbbbbbbbbbbbbbbbbbbbbbbb",
        email: "owner@viventium.local",
        callSessionId: "personal-call",
      };
    },
  };
  await assert.rejects(
    () =>
      runner.seedFreshSyntheticOwner(
        database,
        helpers,
        {},
        { startedAtMs: Date.now() },
      ),
    blockerIs("fresh_synthetic_owner_not_created"),
  );
});

test("exact fresh-owner cleanup removes conversations, memories, dispatch, search, vectors, and schedules", async () => {
  const fixture = residueFixture();
  const result = await runner.cleanupExactSyntheticOwner(
    fixture.database,
    fixture.seeded,
    FixtureObjectId,
    "http://127.0.0.1:3300",
    fixture.helpers,
    {
      freshProof: fixture.proof,
      searchIndex: fixture.searchIndex,
      vectorIndex: fixture.vectorIndex,
      fileStorage: fixture.fileStorage,
      schedulerDatabase: fixture.schedulerDatabase,
    },
  );
  assert.equal(result.zeroResidue, true);
  assert.equal(fixture.indexed.length, 1);
  assert.equal(fixture.vectors.length, 1);
  assert.equal(fixture.storedFiles.length, 1);
  assert.equal(fixture.indexed[0].ownerId, fixture.seeded.userId);
  assert.deepEqual(fixture.indexed[0].messageIds, ["synthetic-message"]);
  assert.deepEqual(fixture.vectors[0].fileIds, ["synthetic-vector"]);
  assert.equal(fixture.storedFiles[0].ownerId, fixture.seeded.userId);
  assert.deepEqual(
    fixture.storedFiles[0].files.map((file) => file.file_id),
    ["synthetic-vector"],
  );
  for (const name of [
    "users",
    "conversations",
    "messages",
    "memoryentries",
    "viventium_scheduler_dispatch_intents",
    "viventiumglasshivecallbackeffectoutboxes",
    "files",
    "sessions",
    "viventiumcallsessions",
    "viventiumvoicetasks",
    "viventiumvoicespeakersegments",
    "viventiumvoiceingressevents",
  ]) {
    assert.equal(fixture.rows[name].length, 1, name);
    if (name === "users") {
      assert.equal(String(fixture.rows[name][0]._id), fixture.personalId, name);
    } else {
      assert.match(String(fixture.rows[name][0]._id), /personal/, name);
    }
  }
  for (const collection of runner.LEDGER_COLLECTIONS) {
    assert.equal(fixture.rows[collection.name].length, 1, collection.name);
    assert.match(String(fixture.rows[collection.name][0]._id), /personal/);
  }
});

test("cleanup refuses an unproven fresh owner before deleting anything", async () => {
  const fixture = residueFixture();
  await assert.rejects(
    () =>
      runner.cleanupExactSyntheticOwner(
        fixture.database,
        fixture.seeded,
        FixtureObjectId,
        "http://127.0.0.1:3300",
        fixture.helpers,
        { freshProof: { ...fixture.proof, ownerId: fixture.personalId } },
      ),
    blockerIs("synthetic_cleanup_fresh_owner_unverified"),
  );
  assert.equal(fixture.deleted.length, 0);
  assert.equal(fixture.rows.users.length, 2);
});

test("cleanup refuses unverifiable search or vector residue before deleting the owner", async () => {
  for (const [adapters, expected] of [
    [
      { vectorIndex: residueFixture().vectorIndex },
      "search_index_cleanup_unavailable",
    ],
    [
      { searchIndex: residueFixture().searchIndex },
      "vector_index_cleanup_unavailable",
    ],
  ]) {
    const fixture = residueFixture();
    await assert.rejects(
      () =>
        runner.cleanupExactSyntheticOwner(
          fixture.database,
          fixture.seeded,
          FixtureObjectId,
          "http://127.0.0.1:3300",
          fixture.helpers,
          { freshProof: fixture.proof, ...adapters },
        ),
      blockerIs(expected),
    );
    assert.equal(fixture.deleted.length, 0);
    assert.equal(fixture.rows.users.length, 2);
  }
});

test("cleanup refuses unobserved uploaded backing storage before deleting anything", async () => {
  const fixture = residueFixture();
  await assert.rejects(
    () =>
      runner.cleanupExactSyntheticOwner(
        fixture.database,
        fixture.seeded,
        FixtureObjectId,
        "http://127.0.0.1:3300",
        fixture.helpers,
        {
          freshProof: fixture.proof,
          searchIndex: fixture.searchIndex,
          vectorIndex: fixture.vectorIndex,
          schedulerDatabase: fixture.schedulerDatabase,
        },
      ),
    blockerIs("file_storage_cleanup_unavailable"),
  );
  assert.equal(fixture.deleted.length, 0);
  assert.equal(fixture.rows.users.length, 2);
});

test("cleanup refuses a backing-storage survivor without touching the owner", async () => {
  const fixture = residueFixture();
  await assert.rejects(
    () =>
      runner.cleanupExactSyntheticOwner(
        fixture.database,
        fixture.seeded,
        FixtureObjectId,
        "http://127.0.0.1:3300",
        fixture.helpers,
        {
          freshProof: fixture.proof,
          searchIndex: fixture.searchIndex,
          vectorIndex: fixture.vectorIndex,
          schedulerDatabase: fixture.schedulerDatabase,
          fileStorage: {
            async removeAndVerify() {
              return { remaining: 1 };
            },
          },
        },
      ),
    blockerIs("file_storage_cleanup_unverified"),
  );
  assert.equal(fixture.rows.users.length, 2);
});

test("cleanup cannot treat an undiscovered scheduler database as zero residue", async () => {
  const fixture = residueFixture();
  await assert.rejects(
    () =>
      runner.cleanupExactSyntheticOwner(
        fixture.database,
        fixture.seeded,
        FixtureObjectId,
        "http://127.0.0.1:3300",
        fixture.helpers,
        {
          freshProof: fixture.proof,
          searchIndex: fixture.searchIndex,
          vectorIndex: fixture.vectorIndex,
          fileStorage: fixture.fileStorage,
        },
      ),
    blockerIs("scheduler_cleanup_observer_unavailable"),
  );
  assert.equal(fixture.deleted.length, 0);
  assert.equal(fixture.rows.users.length, 2);
});

test("full installed acceptance defaults to headed and rejects headless claims", () => {
  assert.deepEqual(runner.resolveBrowserPresentation({}), {
    headless: false,
    userVisible: true,
  });
  assert.throws(
    () => runner.resolveBrowserPresentation({ browser: { headless: true } }),
    blockerIs("headed_browser_required_for_user_visible_acceptance"),
  );
});

test("installed Voice QA uses existing Chrome when bundled Chromium is absent", () => {
  const browser = { executablePath: () => "/synthetic/browser/chromium" };

  assert.deepEqual(
    runner.resolveInstalledBrowserLaunch(browser, () => false),
    { channel: "chrome" },
  );
  assert.deepEqual(
    runner.resolveInstalledBrowserLaunch(browser, () => true),
    {},
  );
});

test("audible acceptance requires observed headed remote playback and received audio", () => {
  assert.doesNotThrow(() =>
    runner.assertObservedRemotePlayback({
      headed: true,
      remoteTrackCount: 1,
      remotePlaybackEvents: 1,
      receivedAudioBytes: 512,
      receivedAudioPackets: 4,
      receivedAudioEnergy: 1,
      audibleRemoteElementCount: 1,
    }),
  );
  for (const changed of [
    { headed: false },
    { remotePlaybackEvents: 0 },
    { remoteTrackCount: 0 },
    { receivedAudioBytes: 0 },
    { receivedAudioEnergy: 0 },
    { audibleRemoteElementCount: 0 },
  ]) {
    assert.throws(
      () =>
        runner.assertObservedRemotePlayback({
          headed: true,
          remoteTrackCount: 1,
          remotePlaybackEvents: 1,
          receivedAudioBytes: 512,
          receivedAudioPackets: 4,
          receivedAudioEnergy: 1,
          audibleRemoteElementCount: 1,
          ...changed,
        }),
      blockerIs("headed_remote_audio_playback_not_observed"),
    );
  }
});

test("a cleanup failure overrides a completed diagnostic journey", async () => {
  const root = privateRoot();
  const scenario = scenarioFixture(root);
  const candidate = candidateBindingFixture("diagnostic");
  scenario.candidate = candidate;
  const source = scenarioPath(root, scenario);
  const result = await runner.runInstalledJourney(
    [
      "--local-qa",
      "--allow-synthetic-account",
      "--allow-runtime-restart",
      "--candidate-mode",
      "diagnostic",
      "--evidence-root",
      root,
      "--scenario",
      source,
    ],
    {
      environment: {
        MPV061_CONTRACT_MONGO_URI: "mongodb://127.0.0.1:27017/fixture",
        VIVENTIUM_QA_ALLOW_MPV061_RUNTIME_RESTART: "1",
        VIVENTIUM_QA_ALLOW_DIAGNOSTIC_CANDIDATE: "1",
      },
      inspectCandidate: () => candidate,
      createRuntime: () => ({
        async preflight() {},
        async execute() {},
        async cleanup() {
          throw new runner.JourneyBlocked("synthetic_cleanup_residue_detected");
        },
      }),
      semanticVerifier: async () => ({
        caseId: "MPV-061",
        status: "PASS",
        scope: "full_journey",
        fullJourneyStatus: "PASS",
        authoritySliceOnlyPassAccepted: false,
        candidateBinding: { matched: true },
        privacy: { publicSafe: true },
        gates: [{ status: "PASS" }],
      }),
    },
  );
  assert.equal(result.status, "BLOCKED");
  assert.equal(result.blocker, "synthetic_cleanup_residue_detected");
});

test("search cleanup never deletes a different owner's colliding message identifier", async () => {
  const ownerId = "aaaaaaaaaaaaaaaaaaaaaaaa";
  const personalId = "bbbbbbbbbbbbbbbbbbbbbbbb";
  const collisionId = "same-message-id";
  const encodedCollision =
    "m_" +
    [...collisionId]
      .map((character) => character.charCodeAt(0).toString(16).padStart(4, "0"))
      .join("");
  const documents = {
    messages: [
      { id: encodedCollision, messageId: collisionId, user: personalId },
    ],
    convos: [],
  };
  const deletes = [];
  class FakeSearch {
    index(name) {
      return {
        async getDocument(identifier) {
          const document = documents[name].find(
            (item) => item.id === identifier,
          );
          if (!document) {
            throw Object.assign(new Error("document not found"), {
              code: "document_not_found",
            });
          }
          return document;
        },
        async deleteDocuments(identifiers) {
          deletes.push({ name, identifiers });
          documents[name] = documents[name].filter(
            (item) => !identifiers.includes(item.id),
          );
          return { taskUid: 1 };
        },
        async waitForTask() {
          return { status: "succeeded" };
        },
        async getDocuments({ filter }) {
          const requestedOwner = String(filter).match(/"([a-f0-9]{24})"/)?.[1];
          return {
            results: documents[name].filter(
              (item) => item.user === requestedOwner,
            ),
          };
        },
      };
    }
  }
  const internal = privateRunnerBindings();
  const observer = internal.createSearchIndexObserver(
    () => ({ MeiliSearch: FakeSearch }),
    {
      MEILI_HOST: "http://127.0.0.1:7700",
      MEILI_MASTER_KEY: "test-only-search-key",
    },
  );

  await assert.rejects(
    () =>
      observer.removeAndVerify({
        ownerId,
        messageIds: [collisionId],
        conversationIds: [],
      }),
    (error) => error.code === "search_index_cleanup_scope_mismatch",
  );
  assert.equal(deletes.length, 0);
  assert.equal(documents.messages.length, 1);
  assert.equal(documents.messages[0].user, personalId);
});

test("unsafe passive-Wing reminder fails before any index, schedule, or account cleanup", async () => {
  const fixture = residueFixture();
  let remaining = 1;
  let scheduleDeletes = 0;
  fixture.helpers.inspectSyntheticSchedules = () => ({
    total: remaining,
    bootstrap: 0,
    unsafe: remaining,
  });
  fixture.helpers.cleanupSyntheticSchedules = () => {
    scheduleDeletes += 1;
    const removed = remaining;
    remaining = 0;
    return removed;
  };

  await assert.rejects(
    () =>
      runner.cleanupExactSyntheticOwner(
        fixture.database,
        fixture.seeded,
        FixtureObjectId,
        "http://127.0.0.1:3300",
        fixture.helpers,
        {
          freshProof: fixture.proof,
          searchIndex: fixture.searchIndex,
          vectorIndex: fixture.vectorIndex,
          fileStorage: fixture.fileStorage,
          schedulerDatabase: fixture.schedulerDatabase,
        },
      ),
    blockerIs("unsafe_synthetic_schedule_detected"),
  );
  assert.equal(scheduleDeletes, 0);
  assert.equal(fixture.deleted.length, 0);
  assert.equal(fixture.indexed.length, 0);
  assert.equal(fixture.vectors.length, 0);
  assert.equal(fixture.storedFiles.length, 0);
  assert.equal(remaining, 1);
});

test("signed Wing response uses the completed provider attempt, not configured route", async () => {
  const internal = privateRunnerBindings();
  const fixture = signedObservation();
  const ownerId = "aaaaaaaaaaaaaaaaaaaaaaaa";
  const fallback = {
    provider: "actual-fallback-provider",
    model: "actual-fallback-model",
  };
  const runtime = Object.create(internal.InstalledJourneyRuntime.prototype);
  runtime.scenario = {
    runtime: {
      playgroundUrl: "http://127.0.0.1:3300",
      assistant: { provider: "fixture-provider", model: "fixture-exact-model" },
    },
  };
  runtime.seeded = {
    userId: ownerId,
    callSessionId: fixture.observation.verdict.callSessionId,
  };
  runtime.identityDigests = candidateBindingFixture();
  runtime.model = runtime.scenario.runtime.assistant;
  runtime.signedResponses = [];
  runtime.snapshot = async () => ({
    segments: fixture.observation.finalSegments,
    ledger: {
      trace: [
        {
          ownerScopeHash: traceRef("owner", ownerId),
          stage: "provider.attempt.completed",
          facts: {
            callSessionRefHash: traceRef(
              "call_session",
              fixture.observation.verdict.callSessionId,
            ),
            logicalTurnRefHash: traceRef(
              "logical_turn",
              fixture.observation.verdict.turnId,
            ),
            ...traceCandidateFacts(runtime.identityDigests),
            effectPlane: "provider",
            outcome: "completed",
            providerStatus: "completed",
            attemptRole: "fallback",
            attemptRefHash: traceRef("provider_attempt", "attempt-fallback"),
            ...fallback,
          },
        },
      ],
    },
    tasks: [],
    messages: [],
  });

  await runtime.observeSignedResponse({
    url: () => "http://127.0.0.1:3300/api/call-engagement",
    request: () => ({ method: () => "POST" }),
    status: () => 200,
    json: async () => fixture.observation.verdict,
  });

  assert.equal(runtime.signedResponses.length, 1);
  assert.deepEqual(runtime.signedResponses[0].model, fallback);
});

test("configured model cannot masquerade as an unobserved completed provider attempt", async () => {
  const internal = privateRunnerBindings();
  const fixture = signedObservation();
  const runtime = Object.create(internal.InstalledJourneyRuntime.prototype);
  runtime.scenario = {
    runtime: {
      playgroundUrl: "http://127.0.0.1:3300",
      assistant: { provider: "fixture-provider", model: "fixture-exact-model" },
    },
  };
  runtime.seeded = {
    userId: "aaaaaaaaaaaaaaaaaaaaaaaa",
    callSessionId: fixture.observation.verdict.callSessionId,
  };
  runtime.identityDigests = candidateBindingFixture();
  runtime.model = runtime.scenario.runtime.assistant;
  runtime.signedResponses = [];
  runtime.snapshot = async () => ({
    segments: fixture.observation.finalSegments,
    ledger: { trace: [] },
    tasks: [],
    messages: [],
  });

  await assert.rejects(
    () =>
      runtime.observeSignedResponse({
        url: () => "http://127.0.0.1:3300/api/call-engagement",
        request: () => ({ method: () => "POST" }),
        status: () => 200,
        json: async () => fixture.observation.verdict,
      }),
    (error) => error.code === "wing_completed_provider_attempt_not_observed",
  );
  assert.equal(runtime.signedResponses.length, 0);
});

test("runtime restart requires a separate explicit flag and environment consent", async () => {
  const root = privateRoot();
  const scenario = scenarioFixture(root);
  const source = scenarioPath(root, scenario);
  let runtimeCreated = false;
  const passingVerifier = async () => ({
    caseId: "MPV-061",
    status: "PASS",
    scope: "full_journey",
    fullJourneyStatus: "PASS",
    authoritySliceOnlyPassAccepted: false,
    candidateBinding: { matched: true },
    privacy: { publicSafe: true },
    gates: [{ status: "PASS" }],
  });
  const result = await runner.runInstalledJourney(
    [
      "--local-qa",
      "--allow-synthetic-account",
      "--evidence-root",
      root,
      "--scenario",
      source,
    ],
    {
      environment: {
        MPV061_CONTRACT_MONGO_URI: "mongodb://127.0.0.1:27017/fixture",
      },
      inspectCandidate: () => candidateBindingFixture(),
      createRuntime: () => {
        runtimeCreated = true;
        return { async preflight() {}, async execute() {}, async cleanup() {} };
      },
      semanticVerifier: passingVerifier,
    },
  );

  assert.equal(result.status, "BLOCKED");
  assert.equal(result.blocker, "runtime_restart_consent_required");
  assert.equal(runtimeCreated, false);
});

test("restart plan accepts only protected dirty-local official activation", () => {
  const supported = {
    executable: path.join(runner.REPOSITORY_ROOT, "bin", "viventium"),
    arguments: [
      "dev-runtime",
      "activate-current",
      "--validate",
      "--restart",
      "--allow-protected-folder",
      "--allow-dirty-local-testing",
    ],
  };

  assert.deepEqual(runner.validateProtectedRestartPlan(supported), supported);
  for (const changed of [
    { executable: process.execPath },
    { arguments: supported.arguments.filter((item) => item !== "--validate") },
    {
      arguments: supported.arguments.filter(
        (item) => item !== "--allow-protected-folder",
      ),
    },
    {
      arguments: supported.arguments.filter(
        (item) => item !== "--allow-dirty-local-testing",
      ),
    },
    { arguments: [...supported.arguments, "--unsafe-extra-argument"] },
  ]) {
    assert.throws(
      () => runner.validateProtectedRestartPlan({ ...supported, ...changed }),
      blockerIs("runtime_restart_unsupported"),
    );
  }
});

test("externally supplied evidence manifest cannot certify unrelated observed workers", () => {
  const internal = privateRunnerBindings();
  const root = privateRoot();
  const scenario = scenarioFixture(root);
  const initialId = "synthetic-initial-session";
  const reconnectId = "synthetic-reconnect-session";
  const hashed = (namespace, value) =>
    "sha256:" +
    crypto
      .createHash("sha256")
      .update(namespace + "\u0000" + value)
      .digest("hex");
  const forged = privateFile(root, "forged-manifest.json", {
    schema: "viventium.voice.mpv-061.full-journey-evidence.v1",
    caseId: "MPV-061",
    scope: "full_journey",
    candidate: {
      candidateDigest: "a".repeat(64),
      artifactDigest: "b".repeat(64),
    },
    run: {
      initialSessionRef: hashed("call_session", initialId),
      reconnectSessionRef: hashed("call_session", reconnectId),
    },
    workers: [
      { workerRef: hashed("worker", "forged-a") },
      { workerRef: hashed("worker", "forged-b") },
    ],
    deliveries: [{ forged: true }, { forged: true }],
    resilience: { fallback: { observed: true }, restart: { observed: true } },
  });
  scenario.observation = { manifestProjection: { path: forged } };
  const observation = {
    candidate: {
      candidateDigest: "a".repeat(64),
      artifactDigest: "b".repeat(64),
    },
    ownerId: "aaaaaaaaaaaaaaaaaaaaaaaa",
    initialSession: { callSessionId: initialId },
    reconnectSession: { callSessionId: reconnectId },
    windows: runner.REQUIRED_TURNS.map(() => ({})),
    workers: [{ workRef: "observed-a" }, { workRef: "observed-b" }],
    uploads: [{}, {}],
    artifacts: [{}, {}],
    fallback: [{}],
    runtime: { before: "old-runtime", after: "new-runtime" },
    ledger: {
      source: "owner_scoped_worker_mission_action_delivery_ledger",
      ownerScopeHash: hashed("owner", "aaaaaaaaaaaaaaaaaaaaaaaa"),
      ...Object.fromEntries(
        runner.LEDGER_COLLECTIONS.map((item) => [item.key, []]),
      ),
    },
  };

  assert.throws(
    () => internal.projectObservedJourney(observation, scenario, root),
    (error) => error.code === "caller_supplied_manifest_forbidden",
  );
  assert.equal(fs.existsSync(scenario.outputs.manifest), false);
});

test("passive Wing cannot pass when no owner-bound signed denial was observed", async () => {
  const { runtime, turn } = passiveTurnFixture({ signed: false });

  await assert.rejects(
    () => runtime.observeTurn(turn, Date.now()),
    (error) => error.code === "passive_wing_signed_denial_not_observed",
  );
  assert.equal(runtime.windows.length, 0);
});

test("passive Wing catches a reminder or worker created after its first transcript snapshot", async () => {
  const { runtime, turn, reads } = passiveTurnFixture({ delayedUnsafe: true });

  await assert.rejects(
    () => runtime.observeTurn(turn, Date.now()),
    (error) =>
      [
        "unsafe_synthetic_schedule_detected",
        "passive_mode_side_effect_observed",
      ].includes(error.code),
  );
  assert.ok(reads() >= 3);
  assert.equal(runtime.windows.length, 0);
});

test("protected restart is invoked only while exact workers remain active and undelivered", async () => {
  const internal = privateRunnerBindings();
  const root = privateRoot();
  const beforeBinding = "a".repeat(64);
  const afterBinding = "b".repeat(64);
  const runtimeIdentity = privateFile(root, "runtime-identity.json", {
    ownerBindingSha256: beforeBinding,
  });
  const restart = {
    executable: path.join(runner.REPOSITORY_ROOT, "bin", "viventium"),
    arguments: [
      "dev-runtime",
      "activate-current",
      "--validate",
      "--restart",
      "--allow-protected-folder",
      "--allow-dirty-local-testing",
    ],
  };
  const workers = [
    {
      ownerId: "aaaaaaaaaaaaaaaaaaaaaaaa",
      workRef: "synthetic-work-a",
      externalState: "running",
    },
    {
      ownerId: "aaaaaaaaaaaaaaaaaaaaaaaa",
      workRef: "synthetic-work-b",
      externalState: "running",
    },
  ];
  const runtime = Object.create(internal.InstalledJourneyRuntime.prototype);
  runtime.scenario = { observation: { runtimeIdentityFile: runtimeIdentity } };
  runtime.restartPlan = restart;
  runtime.seeded = {
    userId: "aaaaaaaaaaaaaaaaaaaaaaaa",
    callSessionId: "surviving-owner-call",
  };
  runtime.initialRuntimeInstance = beforeBinding;
  runtime.environment = { VIVENTIUM_QA_ALLOW_MPV061_RUNTIME_RESTART: "1" };
  runtime.restartConsent = true;
  runtime.restartEvidence = null;
  runtime.snapshot = async () => ({
    ledger: { work: workers, callbacks: [], deliveries: [], trace: [] },
    sessions: [
      {
        userId: "aaaaaaaaaaaaaaaaaaaaaaaa",
        callSessionId: "surviving-owner-call",
        conversationId: "surviving-owner-conversation",
      },
    ],
  });
  runtime.corePage = {
    async evaluate() {
      return { status: 200, payload: { work: workers } };
    },
  };
  const calls = [];
  runtime.restartExecutor = (executable, arguments_, options) => {
    calls.push({ executable, arguments: arguments_, options });
    fs.writeFileSync(
      runtimeIdentity,
      JSON.stringify({ ownerBindingSha256: afterBinding }),
      { mode: 0o600 },
    );
    fs.chmodSync(runtimeIdentity, 0o600);
    return { status: 0 };
  };

  const result = await runtime.coordinateRuntimeRestart(workers);

  assert.equal(calls.length, 1);
  assert.equal(calls[0].executable, restart.executable);
  assert.deepEqual(calls[0].arguments, restart.arguments);
  assert.equal(result.before, beforeBinding);
  assert.equal(result.after, afterBinding);
  assert.deepEqual(
    result.workerRefs,
    workers.map((worker) => worker.workRef),
  );
  assert.equal(result.invoked, true);
  assert.equal(result.exitCode, 0);
  assert.deepEqual(
    result.survivingWorkRefs,
    workers.map((worker) => worker.workRef),
  );
  assert.equal(result.mainAvailableBefore, true);
  assert.equal(result.mainAvailableAfter, true);
  assert.equal(result.callSessionId, "surviving-owner-call");
  assert.equal(result.survivingCallSessionId, "surviving-owner-call");
  assert.equal(result.callConversationId, "surviving-owner-conversation");
});

test("restart refuses a completed or already delivered worker before invoking its executor", async () => {
  const internal = privateRunnerBindings();
  const workers = [
    { workRef: "synthetic-work-a", externalState: "completed" },
    { workRef: "synthetic-work-b", externalState: "running" },
  ];
  const runtime = Object.create(internal.InstalledJourneyRuntime.prototype);
  runtime.seeded = { userId: "aaaaaaaaaaaaaaaaaaaaaaaa" };
  runtime.restartPlan = {};
  runtime.restartConsent = true;
  runtime.environment = { VIVENTIUM_QA_ALLOW_MPV061_RUNTIME_RESTART: "1" };
  runtime.snapshot = async () => ({
    ledger: {
      work: workers,
      callbacks: [{ workRef: "synthetic-work-a" }],
      deliveries: [],
      trace: [],
    },
  });
  let invoked = false;
  runtime.restartExecutor = () => {
    invoked = true;
    return { status: 0 };
  };

  await assert.rejects(
    () => runtime.coordinateRuntimeRestart(workers),
    (error) => error.code === "restart_active_undelivered_workers_required",
  );
  assert.equal(invoked, false);
});

test("independent observed events produce all authenticated full-journey evidence", () => {
  const internal = privateRunnerBindings();
  const root = privateRoot();
  const { scenario, observation } = observedJourneyFixture(root);

  const projected = internal.projectObservedJourney(
    observation,
    scenario,
    root,
  );
  const manifest = runner.readPrivateJson(
    projected.manifest,
    "observed_manifest",
  );
  const verifier = require("./mpv_061_full_journey_semantic_qa.js");
  const assessed = verifier.assessManifest(manifest, {
    evidenceRoot: root,
    identityDigests: observation.candidate,
  });

  assert.equal(assessed.result.status, "PASS");
  assert.equal(assessed.evidence.verified.length, 24);
  assert.equal(manifest.workers.length, 2);
  assert.equal(manifest.resilience.restart.observed, true);
  assert.equal(manifest.resilience.fallback.observed, true);
  assert.equal(
    Object.hasOwn(scenario.observation, "manifestProjection"),
    false,
  );
  assert.ok(
    manifest.evidence.every(
      (item) =>
        (fs.statSync(path.join(root, item.path)).mode & 0o777) === 0o600,
    ),
  );
});

test("diagnostic candidate binding survives manifest, evidence, and cleanup", async () => {
  const internal = privateRunnerBindings();
  const root = privateRoot();
  const { scenario, observation } = observedJourneyFixture(root);
  const candidate = candidateBindingFixture("diagnostic");
  observation.candidate = candidate;

  const projected = internal.projectObservedJourney(
    observation,
    scenario,
    root,
  );
  const manifest = runner.readPrivateJson(
    projected.manifest,
    "observed_manifest",
  );
  assert.deepEqual(manifest.candidate, candidate);
  assert.deepEqual(manifest.release, {
    candidateMode: "diagnostic",
    releaseCandidateVerified: false,
    acceptanceEligible: false,
    releaseReady: false,
    receiptEligible: false,
    releaseLabel: "PRE-GATE / NOT READY",
  });
  assert.ok(
    manifest.evidence.every(
      (item) =>
        item.candidateMode === "diagnostic" &&
        item.receiptEligible === false &&
        /^[a-f0-9]{64}$/.test(item.candidateBindingSha256),
    ),
  );
  const structural = runner.readPrivateJson(
    path.join(
      root,
      manifest.evidence.find((item) => item.kind === "session_ledger").path,
    ),
    "diagnostic_evidence",
  );
  assert.equal(structural.candidateMode, "diagnostic");
  assert.equal(structural.receiptEligible, false);
  assert.equal(
    structural.candidateBindingSha256,
    manifest.evidence[0].candidateBindingSha256,
  );

  const runtime = new internal.InstalledJourneyRuntime({
    scenario,
    evidenceRoot: root,
    identityDigests: candidate,
    restartPlan: {},
  });
  await assert.rejects(
    () =>
      runtime.cleanup({
        failure: null,
        candidateBinding: {
          ...candidate,
          candidateDigest: "f".repeat(64),
        },
      }),
    (error) => error.code === "cleanup_candidate_binding_mismatch",
  );
});

test("unobserved completion speech cannot be replaced by a caller claim", () => {
  const internal = privateRunnerBindings();
  const root = privateRoot();
  const { scenario, observation } = observedJourneyFixture(root);
  observation.completions = [];

  assert.throws(
    () => internal.projectObservedJourney(observation, scenario, root),
    (error) => error.code === "worker_completion_speech_not_observed",
  );
  assert.equal(fs.existsSync(scenario.outputs.manifest), false);
});

test("forged artifact, owner, and fallback claims cannot produce evidence", () => {
  for (const [mutation, expected] of [
    [
      (value) => {
        value.ledger.callbacks[0].ownerId = "bbbbbbbbbbbbbbbbbbbbbbbb";
      },
      "observed_owner_scope_mismatch",
    ],
    [
      (value) => {
        value.ledger.callbacks[0].artifactSha256 = "f".repeat(64);
      },
      "worker_artifact_delivery_not_bound",
    ],
    [
      (value) => {
        value.fallback[0].facts.fallbackProviderStatus = "pending";
      },
      "provider_fallback_not_observed",
    ],
    [
      (value) => {
        value.ledger.trace.find(
          (event) => event.stage === "action.accepted",
        ).facts.candidateDigest = "sha256:" + "f".repeat(64);
      },
      "owner_scoped_worker_control_not_observed",
    ],
    [
      (value) => {
        value.fallback[0].facts.callSessionRefHash = traceRef(
          "call_session",
          "foreign-call",
        );
      },
      "provider_fallback_not_observed",
    ],
    [
      (value) => {
        value.fallback[0].facts.runtimeOwnerBindingHash =
          "sha256:" + "f".repeat(64);
      },
      "provider_fallback_not_observed",
    ],
    [
      (value) => {
        value.runtime.restart.invoked = false;
      },
      "runtime_restart_not_observed",
    ],
  ]) {
    const internal = privateRunnerBindings();
    const root = privateRoot();
    const { scenario, observation } = observedJourneyFixture(root);
    mutation(observation);

    assert.throws(
      () => internal.projectObservedJourney(observation, scenario, root),
      (error) => error.code === expected,
    );
    assert.equal(fs.existsSync(scenario.outputs.manifest), false);
  }
});

test("unsafe Wing reminder is durably reported FAIL before recoverable cleanup", async () => {
  const root = privateRoot();
  const scenario = scenarioFixture(root);
  const candidate = candidateBindingFixture("diagnostic");
  scenario.candidate = candidate;
  const source = scenarioPath(root, scenario);
  const events = [];
  const result = await runner.runInstalledJourney(
    [
      "--local-qa",
      "--allow-synthetic-account",
      "--allow-runtime-restart",
      "--candidate-mode",
      "diagnostic",
      "--evidence-root",
      root,
      "--scenario",
      source,
    ],
    {
      environment: {
        MPV061_CONTRACT_MONGO_URI: "mongodb://127.0.0.1:27017/isolated-test",
        VIVENTIUM_QA_ALLOW_MPV061_RUNTIME_RESTART: "1",
        VIVENTIUM_QA_ALLOW_DIAGNOSTIC_CANDIDATE: "1",
      },
      inspectCandidate: async () => candidate,
      createRuntime: async () => ({
        async preflight() {},
        async execute() {
          throw new runner.JourneyBlocked("unsafe_synthetic_schedule_detected");
        },
        async recordSafetyFailure(failure) {
          events.push({
            type: "fail",
            status: failure.status,
            blocker: failure.blocker,
          });
          return { status: "FAIL", recoverable: true };
        },
        async cleanup(context) {
          events.push({ type: "cleanup", status: context.failure.status });
        },
      }),
    },
  );

  assert.deepEqual(result, {
    caseId: "MPV-061",
    status: "FAIL",
    blocker: "unsafe_synthetic_schedule_detected",
    candidateMode: "diagnostic",
    releaseReady: false,
    receiptEligible: false,
    releaseLabel: "PRE-GATE / NOT READY",
  });
  assert.deepEqual(events, [
    {
      type: "fail",
      status: "FAIL",
      blocker: "unsafe_synthetic_schedule_detected",
    },
    { type: "cleanup", status: "FAIL" },
  ]);
});

test("reviewed unsafe synthetic schedules are snapshotted before owner-only cleanup", async () => {
  const fixture = residueFixture();
  const root = privateRoot();
  let schedules = [
    {
      __qa_rowid: 17,
      user_id: fixture.seeded.userId,
      title: "Unsafe fixture reminder",
    },
  ];
  const events = [];
  fixture.helpers.inspectSyntheticSchedules = () => ({
    total: schedules.length,
    bootstrap: 0,
    unsafe: schedules.length,
  });
  fixture.helpers.cleanupSyntheticSchedules = () => {
    throw new Error("unsafe broad schedule deletion must never execute");
  };
  const backup = privateFile(root, "owner-schedule-backup.json", {
    schema: "viventium.voice.qa.schedule-recovery.v1",
    ownerId: fixture.seeded.userId,
    failureCode: "unsafe_synthetic_schedule_detected",
    rows: schedules,
  });

  const outcome = await runner.cleanupExactSyntheticOwner(
    fixture.database,
    fixture.seeded,
    FixtureObjectId,
    "http://127.0.0.1:3300",
    fixture.helpers,
    {
      freshProof: fixture.proof,
      searchIndex: fixture.searchIndex,
      vectorIndex: fixture.vectorIndex,
      fileStorage: fixture.fileStorage,
      schedulerDatabase: fixture.schedulerDatabase,
      failureRecord: {
        status: "FAIL",
        blocker: "unsafe_synthetic_schedule_detected",
        recoveryPath: backup,
      },
      readScheduleRows: () => schedules.map((row) => ({ ...row })),
      deleteScheduleRows: ({ ownerId, rowIds }) => {
        events.push({ ownerId, rowIds, backupPresent: fs.existsSync(backup) });
        assert.equal(ownerId, fixture.seeded.userId);
        const previous = schedules.length;
        schedules = schedules.filter((row) => !rowIds.includes(row.__qa_rowid));
        return previous - schedules.length;
      },
    },
  );

  assert.equal(outcome.zeroResidue, true);
  assert.equal(outcome.scheduledTasksRemoved, 1);
  assert.deepEqual(events, [
    {
      ownerId: fixture.seeded.userId,
      rowIds: [17],
      backupPresent: true,
    },
  ]);
  assert.equal(fixture.rows.users.length, 1);
  assert.equal(String(fixture.rows.users[0]._id), fixture.personalId);
});

test("recoverable cleanup refuses foreign-account rows before any deletion", async () => {
  const fixture = residueFixture();
  const root = privateRoot();
  const foreignRows = [
    {
      __qa_rowid: 12,
      user_id: fixture.personalId,
      title: "Personal reminder",
    },
  ];
  fixture.helpers.inspectSyntheticSchedules = () => ({
    total: 1,
    bootstrap: 0,
    unsafe: 1,
  });
  const backup = privateFile(root, "foreign-backup.json", {
    schema: "viventium.voice.qa.schedule-recovery.v1",
    ownerId: fixture.seeded.userId,
    failureCode: "unsafe_synthetic_schedule_detected",
    rows: foreignRows,
  });
  let attemptedDelete = false;

  await assert.rejects(
    () =>
      runner.cleanupExactSyntheticOwner(
        fixture.database,
        fixture.seeded,
        FixtureObjectId,
        "http://127.0.0.1:3300",
        fixture.helpers,
        {
          freshProof: fixture.proof,
          searchIndex: fixture.searchIndex,
          vectorIndex: fixture.vectorIndex,
          fileStorage: fixture.fileStorage,
          schedulerDatabase: fixture.schedulerDatabase,
          failureRecord: {
            status: "FAIL",
            blocker: "unsafe_synthetic_schedule_detected",
            recoveryPath: backup,
          },
          readScheduleRows: () => foreignRows,
          deleteScheduleRows: () => {
            attemptedDelete = true;
          },
        },
      ),
    blockerIs("synthetic_schedule_recovery_scope_mismatch"),
  );
  assert.equal(attemptedDelete, false);
  assert.equal(fixture.deleted.length, 0);
  assert.equal(fixture.indexed.length, 0);
});

test("surface capture refuses caller-supplied rows missing from the actual owner response", async () => {
  const internal = privateRunnerBindings();
  const root = privateRoot();
  const runtime = Object.create(internal.InstalledJourneyRuntime.prototype);
  runtime.evidenceRoot = root;
  runtime.corePage = {
    async evaluate() {
      return { status: 200, payload: { items: [] } };
    },
    locator: () => ({
      innerText: async () => "Observed worker A Observed worker B",
    }),
    async screenshot({ path: target }) {
      fs.writeFileSync(target, "isolated screenshot", { mode: 0o600 });
    },
  };

  await assert.rejects(
    () =>
      runtime.captureSurface("missing-workers", [
        { workRef: "work-a", title: "Observed worker A" },
        { workRef: "work-b", title: "Observed worker B" },
      ]),
    (error) => error.code === "observed_worker_surface_unavailable",
  );
});

test("completion speech derives only from persisted owner messages and owner-scoped trace", async () => {
  const internal = privateRunnerBindings();
  const root = privateRoot();
  const { observation } = observedJourneyFixture(root);
  const ownerId = observation.ownerId;
  const text = "Both observed Workers completed.";
  const messageId = "observed-coalesced-completion";
  const turnId = "voice_worker_completion_turn_" + "c".repeat(64);
  const presentationRef = "voice_worker_completion_" + "c".repeat(64);
  const deliveryId = "ghcd-observed-coalesced";
  const bindings = observation.workers.map((worker, index) => ({
    originRef: worker.originRef,
    workRef: worker.workRef,
    workerId: "observed-worker-" + index,
    runId: worker.runId,
    callbackRef: "callback_sha256:" + String(index + 1).repeat(64),
    attemptNumber: 1,
    resultKey: "ghtr_" + String(index + 1).repeat(64),
    acceptedOperationId: String(index + 1).repeat(32),
    terminalCallbackId: "cb_terminal_" + String(index + 1).repeat(64),
    resultDigest: "sha256:" + String(index + 1).repeat(64),
    resultRevision: 1,
    effectGeneration: 1,
  }));
  const presentation = {
    version: 1,
    presentationRef,
    callSessionId: observation.reconnectSession.callSessionId,
    turnId,
    revision: 1,
    responseMessageId: messageId,
    responseDigest:
      "sha256:" + crypto.createHash("sha256").update(text).digest("hex"),
    bindings,
  };
  const delivery = {
    deliveryId,
    userId: ownerId,
    surface: "voice",
    status: "sent",
    callbackMessageId: messageId,
    voiceCallSessionId: observation.reconnectSession.callSessionId,
    voiceRequestId: turnId,
    workerCompletionPresentation: presentation,
    workerCompletionTtsCompletedAt: new Date().toISOString(),
    workerCompletionAudioCompletedAt: new Date().toISOString(),
  };
  const rows = [
    {
      user: ownerId,
      role: "assistant",
      conversationId: observation.conversationId,
      messageId,
      agentId: observation.completions[0].speakerIdentity,
      text,
    },
  ];
  const traces = observation.workers.flatMap((worker) =>
    [
      { stage: "response.completed", effectPlane: "response" },
      { stage: "tts.completed", effectPlane: "tts" },
      { stage: "audio.completed", effectPlane: "audio" },
    ].map((event) => ({
      ownerScopeHash: observation.ledger.ownerScopeHash,
      stage: event.stage,
      facts: {
        callSessionRefHash: traceRef(
          "call_session",
          observation.reconnectSession.callSessionId,
        ),
        logicalTurnRefHash: traceRef("logical_turn", turnId),
        workRefHash: traceRef("work", worker.workRef),
        deliveryRefHash: traceRef("delivery", deliveryId),
        responseRefHash: traceRef("response", messageId),
        presentationRefHash: traceRef("voice_presentation", presentationRef),
        ...traceCandidateFacts(observation.candidate),
        effectPlane: event.effectPlane,
        outcome: "completed",
      },
    })),
  );
  const runtime = Object.create(internal.InstalledJourneyRuntime.prototype);
  runtime.seeded = observation.initialSession;
  runtime.identityDigests = observation.candidate;
  runtime.stageMap = {
    response: new Set(["response.completed"]),
    tts: new Set(["tts.completed"]),
    audio: new Set(["audio.completed"]),
  };
  runtime.db = {
    collection(name) {
      assert.equal(name, "messages");
      return {
        find(filter) {
          assert.equal(filter.user, ownerId);
          assert.equal(filter.conversationId, observation.conversationId);
          return {
            async toArray() {
              return rows;
            },
          };
        },
      };
    },
  };
  runtime.reconnectPage = {
    locator: () => ({
      innerText: async () => rows.map((row) => row.text).join(" "),
    }),
  };

  const events = await runtime.captureCompletionEvents(
    observation.workers,
    observation.reconnectSession,
    { ...observation.ledger, deliveries: [delivery], trace: traces },
  );

  assert.equal(events.length, 2);
  assert.deepEqual(
    events.map((event) => event.workRef),
    observation.workers.map((worker) => worker.workRef),
  );
  assert.ok(
    events.every(
      (event) =>
        event.responseCount === 1 &&
        event.ttsCount === 1 &&
        event.audioCount === 1,
    ),
  );
  assert.ok(events.every((event) => event.messageId === messageId));
  assert.ok(events.every((event) => event.turnId === turnId));
});

test("completion capture rejects foreign-owner or unobserved assistant speech", async () => {
  const internal = privateRunnerBindings();
  const runtime = Object.create(internal.InstalledJourneyRuntime.prototype);
  runtime.seeded = { userId: "aaaaaaaaaaaaaaaaaaaaaaaa" };
  runtime.db = {
    collection() {
      return {
        find() {
          return {
            async toArray() {
              return [
                {
                  user: "bbbbbbbbbbbbbbbbbbbbbbbb",
                  role: "assistant",
                  workRef: "work-a",
                },
              ];
            },
          };
        },
      };
    },
  };
  runtime.reconnectPage = {
    locator: () => ({ innerText: async () => "foreign content" }),
  };

  await assert.rejects(
    () =>
      runtime.captureCompletionEvents(
        [{ workRef: "work-a" }, { workRef: "work-b" }],
        { callSessionId: "reconnect", conversationId: "conversation" },
        { trace: [] },
      ),
    (error) => error.code === "worker_completion_speech_not_observed",
  );
});

test("runtime object itself cannot restart without both explicit consent boundaries", async () => {
  for (const [consent, environment] of [
    [false, { VIVENTIUM_QA_ALLOW_MPV061_RUNTIME_RESTART: "1" }],
    [true, {}],
  ]) {
    const internal = privateRunnerBindings();
    const workers = [
      { workRef: "synthetic-work-a", externalState: "running" },
      { workRef: "synthetic-work-b", externalState: "running" },
    ];
    const runtime = Object.create(internal.InstalledJourneyRuntime.prototype);
    runtime.seeded = { userId: "aaaaaaaaaaaaaaaaaaaaaaaa" };
    runtime.restartConsent = consent;
    runtime.environment = environment;
    runtime.snapshot = async () => ({
      ledger: { work: workers, callbacks: [], deliveries: [], trace: [] },
    });
    let invoked = false;
    runtime.restartExecutor = () => {
      invoked = true;
      return { status: 0 };
    };

    await assert.rejects(
      () => runtime.coordinateRuntimeRestart(workers),
      (error) => error.code === "runtime_restart_consent_required",
    );
    assert.equal(invoked, false);
  }
});

test("completed provider identity honors flat hashed owner, call, turn, candidate, and status", () => {
  const internal = privateRunnerBindings();
  const ownerId = "aaaaaaaaaaaaaaaaaaaaaaaa";
  const ownerScopeHash =
    "sha256:" +
    crypto
      .createHash("sha256")
      .update("owner\u0000" + ownerId)
      .digest("hex");
  const expected = {
    ownerId,
    callSessionId: "exact-call",
    turnId: "exact-turn",
    candidate: candidateBindingFixture(),
  };
  const event = {
    ownerScopeHash,
    stage: "provider.attempt.completed",
    facts: {
      callSessionRefHash: traceRef("call_session", expected.callSessionId),
      logicalTurnRefHash: traceRef("logical_turn", expected.turnId),
      ...traceCandidateFacts(expected.candidate),
      effectPlane: "provider",
      outcome: "completed",
      provider: "xai",
      model: "grok-4.5",
      providerStatus: "completed",
      attemptRole: "primary",
      attemptRefHash: traceRef("provider_attempt", "exact-attempt"),
    },
  };

  assert.deepEqual(
    internal.completedProviderAttempt({ ledger: { trace: [event] } }, expected),
    { provider: "xai", model: "grok-4.5" },
  );
  for (const mutated of [
    { ...event, ownerScopeHash: "sha256:" + "f".repeat(64) },
    {
      ...event,
      facts: {
        ...event.facts,
        callSessionRefHash: traceRef("call_session", "foreign-call"),
      },
    },
    {
      ...event,
      facts: {
        ...event.facts,
        logicalTurnRefHash: traceRef("logical_turn", "foreign-turn"),
      },
    },
    {
      ...event,
      facts: {
        ...event.facts,
        providerStatus: "failed",
      },
    },
    {
      ...event,
      facts: { ...event.facts, candidateDigest: "sha256:" + "f".repeat(64) },
    },
    { ...event, facts: { ...event.facts, attemptRefHash: undefined } },
  ]) {
    assert.throws(
      () =>
        internal.completedProviderAttempt(
          { ledger: { trace: [mutated] } },
          expected,
        ),
      (error) => error.code === "wing_completed_provider_attempt_not_observed",
    );
  }
  assert.throws(
    () =>
      internal.completedProviderAttempt(
        { ledger: { trace: [event, event] } },
        expected,
      ),
    (error) => error.code === "wing_completed_provider_attempt_not_observed",
  );
});

test("official GlassHive stop receipt is bound without inventing response identifiers", () => {
  const internal = privateRunnerBindings();
  const root = privateRoot();
  const { scenario, observation } = observedJourneyFixture(root);
  observation.probe.response.payload = {
    workRef: observation.probe.work.workRef,
    action: "stop",
    status: "accepted",
    state: "stopping",
    confirmationPending: true,
    idempotentReplay: false,
    updatedAt: observation.runAt,
  };

  const projected = internal.projectObservedJourney(
    observation,
    scenario,
    root,
  );
  const manifest = runner.readPrivateJson(
    projected.manifest,
    "observed_manifest",
  );
  const verifier = require("./mpv_061_full_journey_semantic_qa.js");

  assert.equal(
    verifier.assessManifest(manifest, {
      evidenceRoot: root,
      identityDigests: observation.candidate,
    }).result.status,
    "PASS",
  );
  assert.match(
    manifest.voice.wingProbe.cleanupReceiptRef,
    /^sha256:[a-f0-9]{64}$/,
  );
});

test("fallback evidence must be the same independently captured ledger event", () => {
  const internal = privateRunnerBindings();
  const root = privateRoot();
  const { scenario, observation } = observedJourneyFixture(root);
  observation.ledger.trace = observation.ledger.trace.filter(
    (event) => event.stage !== scenario.observation.fallbackStage,
  );

  assert.throws(
    () => internal.projectObservedJourney(observation, scenario, root),
    (error) => error.code === "provider_fallback_not_observed",
  );
  assert.equal(fs.existsSync(scenario.outputs.manifest), false);
});

test("controlled classifier fallback is bound to the trusted Wing launch turn", () => {
  const internal = privateRunnerBindings();
  const root = privateRoot();
  const { scenario, observation } = observedJourneyFixture(root);
  const wrongTurnRef = traceRef("logical_turn", "observed-turn-1");
  for (const event of observation.ledger.trace) {
    if (
      [
        "attempt.history.complete",
        "provider.request.forwarded",
        "provider.attempt.completed",
        scenario.observation.fallbackStage,
      ].includes(event.stage)
    ) {
      event.facts.logicalTurnRefHash = wrongTurnRef;
    }
  }

  assert.throws(
    () => internal.projectObservedJourney(observation, scenario, root),
    (error) => error.code === "provider_fallback_not_observed",
  );
  assert.equal(fs.existsSync(scenario.outputs.manifest), false);
});

test("caller manifest is rejected before synthetic account creation or restart", async () => {
  const root = privateRoot();
  const scenario = scenarioFixture(root);
  scenario.observation = {
    manifestProjection: { path: "/private/forged-acceptance.json" },
  };
  const source = scenarioPath(root, scenario);
  let created = false;

  const result = await runner.runInstalledJourney(
    [
      "--local-qa",
      "--allow-synthetic-account",
      "--allow-runtime-restart",
      "--evidence-root",
      root,
      "--scenario",
      source,
    ],
    {
      environment: {
        MPV061_CONTRACT_MONGO_URI: "mongodb://127.0.0.1:27017/test-only",
        VIVENTIUM_QA_ALLOW_MPV061_RUNTIME_RESTART: "1",
      },
      createRuntime: () => {
        created = true;
        throw new Error("runtime must never be created");
      },
    },
  );

  assert.equal(result.status, "BLOCKED");
  assert.equal(result.blocker, "caller_supplied_manifest_forbidden");
  assert.equal(created, false);
});

test("pending callbacks and unknown delivery never become successful evidence", () => {
  for (const mutate of [
    (observation) => {
      observation.ledger.callbacks[0].state = "pending";
    },
    (observation) => {
      observation.ledger.deliveries[0].state = "unknown";
    },
    (observation) => {
      observation.fallback[0].facts.primaryProviderStatus = "pending";
    },
  ]) {
    const internal = privateRunnerBindings();
    const root = privateRoot();
    const { scenario, observation } = observedJourneyFixture(root);
    mutate(observation);

    assert.throws(
      () => internal.projectObservedJourney(observation, scenario, root),
      (error) =>
        [
          "worker_callback_delivery_not_observed",
          "provider_fallback_not_observed",
        ].includes(error.code),
    );
    assert.equal(fs.existsSync(scenario.outputs.manifest), false);
  }
});

test("restart refuses foreign-owned active work and unavailable authenticated Main", async () => {
  for (const [foreign, responseStatus] of [
    [true, 200],
    [false, 503],
  ]) {
    const internal = privateRunnerBindings();
    const ownerId = "aaaaaaaaaaaaaaaaaaaaaaaa";
    const workers = [
      {
        ownerId: foreign ? "bbbbbbbbbbbbbbbbbbbbbbbb" : ownerId,
        workRef: "synthetic-work-a",
        externalState: "running",
      },
      { ownerId, workRef: "synthetic-work-b", externalState: "running" },
    ];
    const runtime = Object.create(internal.InstalledJourneyRuntime.prototype);
    runtime.seeded = { userId: ownerId, callSessionId: "surviving-owner-call" };
    runtime.restartConsent = true;
    runtime.environment = { VIVENTIUM_QA_ALLOW_MPV061_RUNTIME_RESTART: "1" };
    runtime.corePage = {
      async evaluate() {
        return { status: responseStatus, payload: { work: workers } };
      },
    };
    runtime.snapshot = async () => ({
      ledger: { work: workers, callbacks: [], deliveries: [], trace: [] },
      sessions: [
        {
          userId: ownerId,
          callSessionId: "surviving-owner-call",
          conversationId: "surviving-owner-conversation",
        },
      ],
    });
    let invoked = false;
    runtime.restartExecutor = () => {
      invoked = true;
      return { status: 0 };
    };

    await assert.rejects(
      () => runtime.coordinateRuntimeRestart(workers),
      (error) =>
        error.code ===
        (foreign
          ? "restart_active_undelivered_workers_required"
          : "restart_main_availability_not_observed"),
    );
    assert.equal(invoked, false);
  }
});

test("recoverable cleanup blocks when the reviewed owner schedule changes", async () => {
  const fixture = residueFixture();
  const root = privateRoot();
  fixture.helpers.inspectSyntheticSchedules = () => ({
    total: 1,
    bootstrap: 0,
    unsafe: 1,
  });
  const reviewed = [
    {
      __qa_rowid: 11,
      user_id: fixture.seeded.userId,
      title: "Reviewed reminder",
    },
  ];
  const backup = privateFile(root, "reviewed-backup.json", {
    schema: "viventium.voice.qa.schedule-recovery.v1",
    ownerId: fixture.seeded.userId,
    failureCode: "unsafe_synthetic_schedule_detected",
    rows: reviewed,
  });
  let deleted = false;

  await assert.rejects(
    () =>
      runner.cleanupExactSyntheticOwner(
        fixture.database,
        fixture.seeded,
        FixtureObjectId,
        "http://127.0.0.1:3300",
        fixture.helpers,
        {
          freshProof: fixture.proof,
          searchIndex: fixture.searchIndex,
          vectorIndex: fixture.vectorIndex,
          fileStorage: fixture.fileStorage,
          schedulerDatabase: fixture.schedulerDatabase,
          failureRecord: {
            status: "FAIL",
            blocker: "unsafe_synthetic_schedule_detected",
            recoveryPath: backup,
          },
          readScheduleRows: () => [
            { ...reviewed[0], title: "Changed after review" },
          ],
          deleteScheduleRows: () => {
            deleted = true;
          },
        },
      ),
    blockerIs("synthetic_schedule_recovery_scope_mismatch"),
  );
  assert.equal(deleted, false);
  assert.equal(fixture.deleted.length, 0);
});

test("a sibling worker's observed file handoff cannot certify attachment isolation", () => {
  const internal = privateRunnerBindings();
  const root = privateRoot();
  const { scenario, observation } = observedJourneyFixture(root);
  observation.ledger.capabilities[0].hostToolResources = {
    files: { fileIds: [String(observation.uploads[1].file._id)] },
  };

  assert.throws(
    () => internal.projectObservedJourney(observation, scenario, root),
    (error) => error.code === "worker_input_handoff_not_observed",
  );
  assert.equal(fs.existsSync(scenario.outputs.manifest), false);
});

test("a terminal delivery cannot borrow another callback's signed identity", () => {
  const internal = privateRunnerBindings();
  const root = privateRoot();
  const { scenario, observation } = observedJourneyFixture(root);
  observation.ledger.deliveries[0].terminalCallbackId =
    "foreign-terminal-callback";

  assert.throws(
    () => internal.projectObservedJourney(observation, scenario, root),
    (error) => error.code === "worker_callback_identity_not_bound",
  );
  assert.equal(fs.existsSync(scenario.outputs.manifest), false);
});

test("an unsolicited owner call cannot be hidden by a hard-coded zero", () => {
  const internal = privateRunnerBindings();
  const root = privateRoot();
  const { scenario, observation } = observedJourneyFixture(root);
  observation.sessions = [
    observation.initialSession,
    observation.reconnectSession,
    {
      userId: observation.ownerId,
      callSessionId: "observed-unsolicited-call",
      conversationId: observation.conversationId,
    },
  ];

  assert.throws(
    () => internal.projectObservedJourney(observation, scenario, root),
    (error) => error.code === "unsolicited_result_call_observed",
  );
  assert.equal(fs.existsSync(scenario.outputs.manifest), false);
});

test("an unrelated trace stage cannot masquerade as a completed provider attempt", () => {
  const internal = privateRunnerBindings();
  const ownerId = "aaaaaaaaaaaaaaaaaaaaaaaa";
  const expected = {
    ownerId,
    callSessionId: "exact-call",
    turnId: "exact-turn",
    candidate: candidateBindingFixture(),
  };
  const event = {
    ownerScopeHash:
      "sha256:" +
      crypto
        .createHash("sha256")
        .update("owner\u0000" + ownerId)
        .digest("hex"),
    stage: "prompt.layers.verified",
    facts: {
      callSessionRefHash: traceRef("call_session", expected.callSessionId),
      logicalTurnRefHash: traceRef("logical_turn", expected.turnId),
      ...traceCandidateFacts(expected.candidate),
      effectPlane: "provider",
      outcome: "completed",
      provider: "xai",
      model: "grok-4.5",
      providerStatus: "completed",
      attemptRole: "primary",
      attemptRefHash: traceRef("provider_attempt", "exact-attempt"),
    },
  };

  assert.throws(
    () =>
      internal.completedProviderAttempt(
        { ledger: { trace: [event] } },
        expected,
      ),
    (error) => error.code === "wing_completed_provider_attempt_not_observed",
  );
});

test("protected restart refuses a missing owner call before invoking activation", async () => {
  const internal = privateRunnerBindings();
  const root = privateRoot();
  const identity = privateFile(root, "restart-call-identity.json", {
    ownerBindingSha256: "a".repeat(64),
  });
  const ownerId = "aaaaaaaaaaaaaaaaaaaaaaaa";
  const workers = [
    { ownerId, workRef: "synthetic-work-a", externalState: "running" },
    { ownerId, workRef: "synthetic-work-b", externalState: "running" },
  ];
  const runtime = Object.create(internal.InstalledJourneyRuntime.prototype);
  runtime.seeded = { userId: ownerId, callSessionId: "owner-call" };
  runtime.scenario = { observation: { runtimeIdentityFile: identity } };
  runtime.restartPlan = {
    executable: path.join(runner.REPOSITORY_ROOT, "bin", "viventium"),
    arguments: [
      "dev-runtime",
      "activate-current",
      "--validate",
      "--restart",
      "--allow-protected-folder",
      "--allow-dirty-local-testing",
    ],
  };
  runtime.restartConsent = true;
  runtime.environment = { VIVENTIUM_QA_ALLOW_MPV061_RUNTIME_RESTART: "1" };
  runtime.snapshot = async () => ({
    ledger: { work: workers, callbacks: [], deliveries: [], trace: [] },
    sessions: [],
  });
  runtime.corePage = {
    evaluate: async () => ({ status: 200, payload: { work: workers } }),
  };
  let invoked = false;
  runtime.restartExecutor = () => {
    invoked = true;
    fs.writeFileSync(
      identity,
      JSON.stringify({ ownerBindingSha256: "b".repeat(64) }),
      { mode: 0o600 },
    );
    return { status: 0 };
  };

  await assert.rejects(
    () => runtime.coordinateRuntimeRestart(workers),
    (error) => error.code === "restart_call_continuity_unobserved",
  );
  assert.equal(invoked, false);
});

test("full evidence cannot claim a restart preserved an unverified call", () => {
  const internal = privateRunnerBindings();
  const root = privateRoot();
  const { scenario, observation } = observedJourneyFixture(root);
  observation.runtime.restart.survivingCallSessionId = "different-call";

  assert.throws(
    () => internal.projectObservedJourney(observation, scenario, root),
    (error) => error.code === "restart_call_continuity_unobserved",
  );
  assert.equal(fs.existsSync(scenario.outputs.manifest), false);
});

test("passive Wing waits for its actual signed owner-scoped ambient transcript receipt", async () => {
  const { runtime, turn } = passiveTurnFixture();
  const segment = runtime.signedResponses[0].finalSegments[0];
  const filters = [];
  runtime.db = {
    collection(name) {
      return {
        async findOne(filter) {
          filters.push({ name, filter });
          if (name === "viventiumcallsessions") {
            return {
              mode: "wing",
              userId: runtime.seeded.userId,
              callModeRevision: 1,
            };
          }
          if (name === "messages") {
            return {
              user: runtime.seeded.userId,
              metadata: {
                viventium: {
                  type: "voice_ambient_transcript",
                  mode: "wing",
                  ingressKind: "ambient_participant",
                  callSessionId: runtime.seeded.callSessionId,
                  turnId: segment.turnId,
                  speakerSegments: [segment],
                },
              },
            };
          }
          throw new Error("passive Wing has no listen-only ingress row");
        },
      };
    },
  };

  const window = await runtime.observeTurn(turn, Date.now());

  assert.equal(window.denial.durable, true);
  assert.equal(window.denial.ingressStatus, "ambient_participant");
  assert.ok(
    filters.some(
      ({ name, filter }) =>
        name === "messages" &&
        filter.user === runtime.seeded.userId &&
        filter["metadata.viventium.callSessionId"] ===
          runtime.seeded.callSessionId &&
        filter["metadata.viventium.turnId"] === segment.turnId,
    ),
  );
  assert.equal(
    filters.some(({ name }) => name === "viventiumvoiceingressevents"),
    false,
  );
});

test("Listen-Only waits for its actual owner-only durable transcript receipt", async () => {
  const { runtime, turn } = passiveTurnFixture();
  const segment = runtime.signedResponses[0].finalSegments[0];
  turn.kind = "listenOnlyDenial";
  turn.mode = "listen_only";
  turn.directlyAddressed = true;
  const filters = [];
  runtime.db = {
    collection(name) {
      return {
        async findOne(filter) {
          filters.push({ name, filter });
          if (name === "viventiumcallsessions") {
            return {
              mode: "listen_only",
              userId: runtime.seeded.userId,
              callModeRevision: 1,
            };
          }
          if (name === "messages") {
            return {
              user: runtime.seeded.userId,
              metadata: {
                viventium: {
                  type: "listen_only_transcript",
                  mode: "listen_only",
                  ingressKind: "listen_only_owner",
                  callSessionId: runtime.seeded.callSessionId,
                  turnId: segment.turnId,
                  speakerSegments: [segment],
                },
              },
            };
          }
          throw new Error(
            "Listen-Only stores its current receipt in owner messages",
          );
        },
      };
    },
  };

  const window = await runtime.observeTurn(turn, Date.now());

  assert.equal(window.denial.durable, true);
  assert.equal(window.denial.ingressStatus, "listen_only_owner");
  assert.ok(
    filters.some(
      ({ name, filter }) =>
        name === "messages" &&
        filter.user === runtime.seeded.userId &&
        filter["metadata.viventium.ingressKind"] === "listen_only_owner",
    ),
  );
  assert.equal(
    filters.some(({ name }) => name === "viventiumvoiceingressevents"),
    false,
  );
});

test("cleanup refuses a call-session collision before deleting any owner's data", async () => {
  const fixture = residueFixture();
  fixture.rows.viventiumcallsessions.push({
    _id: "colliding-personal-call",
    userId: "bbbbbbbbbbbbbbbbbbbbbbbb",
    callSessionId: "synthetic-call",
  });

  await assert.rejects(
    () =>
      runner.cleanupExactSyntheticOwner(
        fixture.database,
        fixture.seeded,
        FixtureObjectId,
        "http://127.0.0.1:3300",
        fixture.helpers,
        {
          freshProof: fixture.proof,
          searchIndex: fixture.searchIndex,
          vectorIndex: fixture.vectorIndex,
          fileStorage: fixture.fileStorage,
          schedulerDatabase: fixture.schedulerDatabase,
        },
      ),
    blockerIs("synthetic_cleanup_session_unverified"),
  );
  assert.equal(fixture.deleted.length, 0);
  assert.equal(fixture.indexed.length, 0);
  assert.equal(fixture.vectors.length, 0);
  assert.equal(fixture.storedFiles.length, 0);
  assert.equal(fixture.rows.viventiumcallsessions.length, 3);
});

test("cleanup refuses foreign voice ingress attached to the synthetic call", async () => {
  const fixture = residueFixture();
  fixture.rows.viventiumvoiceingressevents.push({
    _id: "colliding-personal-ingress",
    userId: "bbbbbbbbbbbbbbbbbbbbbbbb",
    callSessionId: "synthetic-call",
  });

  await assert.rejects(
    () =>
      runner.cleanupExactSyntheticOwner(
        fixture.database,
        fixture.seeded,
        FixtureObjectId,
        "http://127.0.0.1:3300",
        fixture.helpers,
        {
          freshProof: fixture.proof,
          searchIndex: fixture.searchIndex,
          vectorIndex: fixture.vectorIndex,
          fileStorage: fixture.fileStorage,
          schedulerDatabase: fixture.schedulerDatabase,
        },
      ),
    blockerIs("synthetic_cleanup_session_unverified"),
  );
  assert.equal(fixture.deleted.length, 0);
  assert.equal(fixture.indexed.length, 0);
  assert.equal(fixture.rows.viventiumvoiceingressevents.length, 3);
});

test("terminal delivery uses the production voiceCallSessionId binding", () => {
  const internal = privateRunnerBindings();
  const root = privateRoot();
  const { scenario, observation } = observedJourneyFixture(root);
  for (const delivery of observation.ledger.deliveries) {
    delivery.voiceCallSessionId = delivery.callSessionId;
    delete delivery.callSessionId;
  }

  const projected = internal.projectObservedJourney(
    observation,
    scenario,
    root,
  );
  const manifest = runner.readPrivateJson(
    projected.manifest,
    "observed_manifest",
  );
  const verifier = require("./mpv_061_full_journey_semantic_qa.js");

  assert.equal(
    verifier.assessManifest(manifest, {
      evidenceRoot: root,
      identityDigests: observation.candidate,
    }).result.status,
    "PASS",
  );
});

test("production callbacks bind artifacts through verified owner orchestration traces", () => {
  const internal = privateRunnerBindings();
  const root = privateRoot();
  const { scenario, observation } = observedJourneyFixture(root);
  const reference = (kind, value) =>
    "sha256:" +
    crypto
      .createHash("sha256")
      .update(kind + "\u0000" + value)
      .digest("hex");
  observation.workerTraces = observation.workers.map((worker, index) => ({
    workRef: worker.workRef,
    originRef: worker.originRef,
    response: {
      version: 2,
      traceRef: reference("origin", worker.originRef),
      workRef: reference("work", worker.workRef),
      completionClaims: { allowed: true },
      ledger: { chain: { fullChainVerified: true } },
      integrity: {
        ownerScoped: true,
        completionClaimable: true,
        artifactRefs: { status: "verified" },
      },
      current: {
        workState: "completed",
        artifactRefs: {
          available: true,
          refs: [
            {
              artifactRef:
                "artifact_sha256:" +
                observation.artifacts[index].observed.sha256,
              fingerprint:
                "sha256:" + observation.artifacts[index].observed.sha256,
            },
          ],
        },
      },
    },
  }));
  for (let index = 0; index < observation.ledger.callbacks.length; index += 1) {
    delete observation.ledger.callbacks[index].artifactId;
    delete observation.ledger.callbacks[index].artifactSha256;
    delete observation.ledger.deliveries[index].artifactId;
    delete observation.ledger.deliveries[index].artifactSha256;
    observation.ledger.deliveries[index].voiceCallSessionId =
      observation.ledger.deliveries[index].callSessionId;
    delete observation.ledger.deliveries[index].callSessionId;
  }

  const projected = internal.projectObservedJourney(
    observation,
    scenario,
    root,
  );
  const manifest = runner.readPrivateJson(
    projected.manifest,
    "observed_manifest",
  );
  const verifier = require("./mpv_061_full_journey_semantic_qa.js");

  assert.equal(
    verifier.assessManifest(manifest, {
      evidenceRoot: root,
      identityDigests: observation.candidate,
    }).result.status,
    "PASS",
  );
});

test("a verified worker trace with another artifact cannot be hidden by callback claims", () => {
  const internal = privateRunnerBindings();
  const root = privateRoot();
  const { scenario, observation } = observedJourneyFixture(root);
  observation.workerTraces = observation.workers.map((worker) => ({
    workRef: worker.workRef,
    originRef: worker.originRef,
    response: {
      current: {
        artifactRefs: {
          available: true,
          refs: [
            {
              artifactRef: "artifact_sha256:" + "f".repeat(64),
              fingerprint: "sha256:" + "f".repeat(64),
            },
          ],
        },
      },
    },
  }));

  assert.throws(
    () => internal.projectObservedJourney(observation, scenario, root),
    (error) => error.code === "worker_artifact_delivery_not_bound",
  );
  assert.equal(fs.existsSync(scenario.outputs.manifest), false);
});

test("repair fence: private Mongo handoff is generated and never becomes enumerable runner output", () => {
  const root = privateRoot();
  const secret = "mongodb://127.0.0.1:27017/private-repair-fence";
  const handoff = preparer.writePrivateRuntimeHandoff(root, secret);
  const metadata = fs.statSync(handoff);
  assert.equal(metadata.mode & 0o777, 0o600);
  assert.deepEqual(JSON.parse(fs.readFileSync(handoff, "utf8")), {
    schema: "viventium.voice.mpv-061.runtime-handoff.v1",
    MONGO_URI: secret,
  });

  const scenario = scenarioFixture(root);
  delete scenario.runtime.mongoUriEnv;
  scenario.runtime.mongoUriFile = handoff;
  const validated = runner.validateScenario(scenario, root, {});
  assert.equal(validated.runtime.mongoUri, secret);
  assert.equal(JSON.stringify(validated).includes(secret), false);
});

test("repair fence: every mode is armed before speech and both control turns target alpha", () => {
  assert.equal(runner.EXECUTION_TURNS.length, 8);
  assert.equal(runner.EXECUTION_TURNS.at(-1).kind, "unverifiedWingDenial");
  for (const turn of preparer.SCENARIO_TURNS) {
    assert.equal(typeof turn.mode, "string");
  }
  for (const turn of preparer.SCENARIO_TURNS.filter((item) =>
    ["authorizedCallControl", "trustedWingControl"].includes(item.kind),
  )) {
    assert.match(turn.expectedTranscript, /mission alpha/i);
    assert.doesNotMatch(turn.expectedTranscript, /mission bravo only/i);
  }
  const timing = runner.assertPrearmedTurnTiming(
    {
      kind: "trustedWingControl",
      mode: "wing",
      armAfterMs: 10_000,
      startAfterMs: 20_000,
    },
    1_000,
    { mode: "wing", armedAtMs: 11_500, callModeRevision: 4 },
  );
  assert.equal(timing.armedBeforeSpeech, true);
});

test("repair fence: directly addressed unverified Wing speech is a durable zero-effect denial", () => {
  const internal = privateRunnerBindings();
  const window = {
    kind: "unverifiedWingDenial",
    mode: "wing",
    directlyAddressed: true,
    transcriptDelta: 1,
    scheduleDelta: 0,
    unsafeScheduleCount: 0,
    segment: {
      turnId: "unverified-turn",
      speaker: {
        attribution: "unverified",
        actorTrust: "shared_mic_unverified",
        participantIdentity: "owner-participant",
      },
    },
    denial: {
      durable: true,
      engagement: {
        transportObserved: true,
        responseStatus: 403,
        code: "voice_engagement_not_authorized",
        turnId: "unverified-turn",
      },
      ingressStatus: "ambient_participant",
    },
    ...Object.fromEntries(
      [
        "mission",
        "action",
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
      ].map((field) => [field + "Delta", 0]),
    ),
  };
  assert.equal(
    internal.assertUnverifiedWingDenial(window, {
      ownerParticipantIdentity: "owner-participant",
      speakerAttributionState: "shared_mic_unverified",
    }).kind,
    "unverifiedWingDenial",
  );
  window.denial.engagement.responseStatus = 200;
  assert.throws(
    () =>
      internal.assertUnverifiedWingDenial(window, {
        ownerParticipantIdentity: "owner-participant",
        speakerAttributionState: "shared_mic_unverified",
      }),
    (error) => error.code === "unverified_wing_denial_not_observed",
  );
});

test("repair fence: sent attachment identity must bind only to its intended worker", () => {
  const internal = privateRunnerBindings();
  const ownerId = "aaaaaaaaaaaaaaaaaaaaaaaa";
  const upload = {
    worker: "A",
    targetWorkRef: "work-alpha",
    file: { _id: "mongo-file-a", file_id: "file-a", user: ownerId },
    message: {
      user: ownerId,
      conversationId: "linked-conversation",
      isCreatedByUser: true,
      attachments: [{ file_id: "file-a" }],
    },
  };
  const authorization = {
    ownerId,
    workRef: "work-alpha",
    hostToolResources: {
      file_search: { files: [{ file_id: "file-a" }] },
    },
  };
  const sibling = {
    ownerId,
    workRef: "work-bravo",
    hostToolResources: { file_search: { files: [] } },
  };
  assert.equal(
    internal.assertAttachmentDispatchBinding({
      upload,
      authorization,
      siblingAuthorizations: [sibling],
      ownerId,
    }).targetWorkRef,
    "work-alpha",
  );
  sibling.hostToolResources.file_search.files.push({ file_id: "file-a" });
  assert.throws(
    () =>
      internal.assertAttachmentDispatchBinding({
        upload,
        authorization,
        siblingAuthorizations: [sibling],
        ownerId,
      }),
    (error) => error.code === "attachment_leaked_to_sibling_worker",
  );
});

test("repair fence: attachment labels follow launch objective order, not Mongo insertion order", () => {
  const ownerId = "aaaaaaaaaaaaaaaaaaaaaaaa";
  const alpha = { ownerId, workRef: "work-alpha" };
  const bravo = { ownerId, workRef: "work-bravo" };
  const window = {
    before: { ledger: { work: [] } },
    after: {
      ledger: {
        work: [bravo, alpha],
        bindings: [
          { ownerId, workRef: bravo.workRef, objectiveOrdinal: 1 },
          { ownerId, workRef: alpha.workRef, objectiveOrdinal: 0 },
        ],
      },
    },
  };
  assert.deepEqual(
    runner
      .orderedMissionWorkers(window, ownerId)
      .map((worker) => worker.workRef),
    ["work-alpha", "work-bravo"],
  );
  window.after.ledger.bindings[0].objectiveOrdinal = 0;
  assert.throws(
    () => runner.orderedMissionWorkers(window, ownerId),
    blockerIs("worker_launch_order_unobserved"),
  );
});

test("repair fence: strict fallback uses the parent private-FD control before runtime mutation", async () => {
  const policy = {
    required: true,
    controlledTrigger: {
      kind: "mpv_061_parent_private_fd_v1",
      caseId: "MPV-061",
      targetTurnKind: "trustedWingLaunch",
      approvalWaitMs: 750,
    },
    reason: "parent_approved_pre_model_fault",
  };
  assert.deepEqual(runner.assertFallbackPolicy(policy, "diagnostic"), policy);
  assert.deepEqual(runner.assertFallbackPolicy(policy, "strict"), policy);
  const root = privateRoot();
  const scenario = scenarioFixture(root);
  const source = scenarioPath(root, scenario);
  let candidateInspected = false;
  let runtimeCreated = false;
  const result = await runner.runInstalledJourney(
    [
      "--local-qa",
      "--allow-synthetic-account",
      "--allow-runtime-restart",
      "--evidence-root",
      root,
      "--scenario",
      source,
    ],
    {
      environment: { VIVENTIUM_QA_ALLOW_MPV061_RUNTIME_RESTART: "1" },
      inspectCandidate() {
        candidateInspected = true;
      },
      createRuntime() {
        runtimeCreated = true;
      },
    },
  );
  assert.equal(result.status, "BLOCKED");
  assert.notEqual(result.blocker, "controlled_fallback_trigger_unavailable");
  assert.equal(candidateInspected, true);
  assert.equal(runtimeCreated, false);
});

test("MPV-061 classifier fault parent receives exact scope only through private FD", async () => {
  const root = privateRoot();
  const child = new EventEmitter();
  child.stdout = new EventEmitter();
  child.stderr = new EventEmitter();
  child.killed = false;
  child.kill = () => {
    child.killed = true;
  };
  let observedSpawn;
  const control = runner.startClassifierFaultParent({
    evidenceRoot: root,
    environment: {
      PATH: process.env.PATH,
      VIVENTIUM_APP_SUPPORT_DIR: "/private/fixture",
    },
    seeded: {
      userId: "a".repeat(24),
      email: "viventium-voice-qa-mpv-061-exact@example.com",
      callSessionId: "call-synthetic-1",
    },
    identityDigests: measuredCandidateFixture(),
    routes: {
      primary: { provider: "xai", model: "grok-4.5" },
      fallback: { provider: "openAI", model: "gpt-5.6-terra" },
    },
    spawnProcess(executable, args, options) {
      observedSpawn = {
        executable,
        args,
        scope: JSON.parse(fs.readFileSync(options.stdio[3], "utf8")),
      };
      return child;
    },
  });
  child.stdout.emit(
    "data",
    Buffer.from(
      JSON.stringify({
        event: "armed",
        caseId: "MPV-061",
        controlId: "mpv061_" + "a".repeat(24),
      }) + "\n",
    ),
  );
  assert.equal((await control.armed).event, "armed");
  child.stdout.emit(
    "data",
    Buffer.from(
      JSON.stringify({
        event: "receipt",
        caseId: "MPV-061",
        controlId: "mpv061_" + "a".repeat(24),
        receiptDigest: "sha256:" + "b".repeat(64),
        receiptExpiresAt: "2026-08-26T12:15:00.000Z",
      }) + "\n",
    ),
  );
  child.emit("exit", 0);
  assert.equal((await control.receipt).event, "receipt");
  assert.equal(observedSpawn.args.join(" ").includes("token"), false);
  assert.deepEqual(observedSpawn.args, ["serve", "--scope-fd", "3"]);
  assert.equal(observedSpawn.scope.caseId, "MPV-061");
  assert.equal(observedSpawn.scope.ownerId, "a".repeat(24));
  assert.equal(
    fs.existsSync(path.join(root, "mpv-061-classifier-fault-scope.json")),
    false,
  );
});

test("MPV-061 classifier control cleanup is receipt-bound and removes one row", () => {
  const root = privateRoot();
  let observed;
  const result = runner.cleanupClassifierFaultReceipt({
    evidenceRoot: root,
    environment: { PATH: process.env.PATH },
    receipt: {
      controlId: "mpv061_" + "a".repeat(24),
      receiptDigest: "sha256:" + "b".repeat(64),
    },
    spawnExecutor(executable, args, options) {
      observed = {
        executable,
        args,
        scope: JSON.parse(fs.readFileSync(options.stdio[3], "utf8")),
      };
      return { status: 0, stdout: '{"removed":1}\n', stderr: "" };
    },
  });
  assert.deepEqual(result, { removed: 1 });
  assert.equal(observed.scope.receiptDigest, "sha256:" + "b".repeat(64));
  assert.deepEqual(observed.args, ["cleanup", "--scope-fd", "3"]);
});

test("repair fence: cleanup-only is explicit and SIGINT or SIGTERM requests one recoverable interruption", () => {
  assert.equal(runner.parseArguments(["--cleanup-only"]).cleanupOnly, true);
  for (const signal of ["SIGINT", "SIGTERM"]) {
    const processLike = new EventEmitter();
    const observed = [];
    const recovery = runner.createSignalRecovery(processLike);
    recovery.bindRuntime({
      requestInterruption(value) {
        observed.push(value);
      },
    });
    recovery.install();
    processLike.emit(signal);
    processLike.emit(signal);
    assert.deepEqual(observed, [signal]);
    assert.throws(
      () => recovery.throwIfRequested(),
      blockerIs("journey_interrupted"),
    );
    recovery.uninstall();
  }
});

test("repair fence: cleanup recovery state is private, replaceable, and candidate bound", () => {
  const root = privateRoot();
  const target = path.join(root, "cleanup-state.v1.json");
  const candidate = candidateBindingFixture("diagnostic");
  const base = {
    schema: "viventium.voice.mpv-061.cleanup-state.v1",
    caseId: "MPV-061",
    status: "armed",
    scenarioBindingSha256: "a".repeat(64),
    candidate,
    owner: {
      userId: "aaaaaaaaaaaaaaaaaaaaaaaa",
      email: "viventium-voice-qa-recovery@example.com",
      insertedAtMs: 1_780_000_000_000,
      acknowledged: true,
      callSessionId: "synthetic-call",
      browserCapability: "b".repeat(43),
      syntheticPassword: "private-cleanup-password",
    },
  };
  runner.writeCleanupRecoveryState(target, base, root);
  runner.writeCleanupRecoveryState(target, { ...base, status: "ready" }, root);
  assert.equal(fs.statSync(target).mode & 0o777, 0o600);
  const recovered = runner.readCleanupRecoveryState(target, {
    scenarioBindingSha256: base.scenarioBindingSha256,
  });
  assert.equal(recovered.status, "ready");
  assert.equal(recovered.owner.syntheticPassword, "private-cleanup-password");
  assert.equal(
    JSON.stringify(
      runner.sanitizePublicResult({
        ...recovered,
        status: "BLOCKED",
        blocker: "journey_interrupted",
      }),
    ).includes("private-cleanup-password"),
    false,
  );
});

test("repair fence: armed cleanup state can recover a session created before interruption", async () => {
  const internal = privateRunnerBindings();
  const root = privateRoot();
  const scenario = scenarioFixture(root);
  const candidate = candidateBindingFixture("diagnostic");
  const runtime = Object.create(internal.InstalledJourneyRuntime.prototype);
  runtime.scenario = scenario;
  runtime.evidenceRoot = root;
  runtime.environment = {};
  runtime.identityDigests = candidate;
  runtime.scenarioBindingSha256 = "a".repeat(64);
  runtime.browsers = [];
  runtime.ObjectId = class ObjectId {
    constructor(value) {
      this.value = value;
    }
  };
  runtime.db = {
    collection(name) {
      return {
        async countDocuments() {
          return name === "viventiumcallsessions" ? 1 : 0;
        },
      };
    },
  };
  const restored = await runtime.restoreCleanupState({
    schema: "viventium.voice.mpv-061.cleanup-state.v1",
    caseId: "MPV-061",
    status: "armed",
    scenarioBindingSha256: "a".repeat(64),
    candidate,
    owner: {
      userId: "aaaaaaaaaaaaaaaaaaaaaaaa",
      email: "viventium-voice-qa-recovery@example.com",
      insertedAtMs: 1_780_000_000_000,
      acknowledged: true,
      callSessionId: "",
    },
  });
  assert.equal(restored.status, "armed");
  assert.equal(runtime.seeded.userId, "aaaaaaaaaaaaaaaaaaaaaaaa");
});

test("repair fence: cleanup-only skips candidate execution and reports verified zero residue", async () => {
  const root = privateRoot();
  const scenario = scenarioFixture(root);
  const source = scenarioPath(root, scenario);
  let recovered = 0;
  let runtimeCreated = false;
  const result = await runner.runInstalledJourney(
    [
      "--local-qa",
      "--cleanup-only",
      "--evidence-root",
      root,
      "--scenario",
      source,
    ],
    {
      createRuntime() {
        runtimeCreated = true;
      },
      async recoverCleanupOnly(context) {
        recovered += 1;
        assert.equal(
          context.scenario.outputs.cleanupState,
          scenario.outputs.cleanupState,
        );
        return { zeroResidue: true };
      },
    },
  );
  assert.deepEqual(result, {
    caseId: "MPV-061",
    status: "CLEANUP_COMPLETE",
    releaseReady: false,
    receiptEligible: false,
    releaseLabel: "PRE-GATE / NOT READY",
  });
  assert.equal(recovered, 1);
  assert.equal(runtimeCreated, false);
});

test("repair fence: cleanup-only uses cleanup prerequisites, not the full Voice preflight", async () => {
  const root = privateRoot();
  const scenario = scenarioFixture(root);
  const candidate = candidateBindingFixture("diagnostic");
  runner.writeCleanupRecoveryState(
    scenario.outputs.cleanupState,
    {
      schema: "viventium.voice.mpv-061.cleanup-state.v1",
      caseId: "MPV-061",
      status: "ready",
      scenarioBindingSha256: "a".repeat(64),
      candidate,
      owner: {
        userId: "aaaaaaaaaaaaaaaaaaaaaaaa",
        email: "viventium-voice-qa-recovery@example.com",
        insertedAtMs: 1_780_000_000_000,
        acknowledged: true,
        callSessionId: "synthetic-call",
        browserCapability: "b".repeat(43),
        syntheticPassword: "private-cleanup-password",
      },
    },
    root,
  );
  const calls = [];
  const receipt = await runner.recoverCleanupOnly({
    scenario,
    evidenceRoot: root,
    environment: {},
    scenarioBindingSha256: "a".repeat(64),
    createRuntime: () => ({
      async preflight() {
        throw new Error(
          "full Voice preflight must not run during cleanup-only",
        );
      },
      async preflightCleanup() {
        calls.push("preflight-cleanup");
      },
      async restoreCleanupState() {
        calls.push("restore");
      },
      async cleanup() {
        calls.push("cleanup");
        return { zeroResidue: true };
      },
    }),
  });
  assert.equal(receipt.zeroResidue, true);
  assert.deepEqual(calls, ["preflight-cleanup", "restore", "cleanup"]);
});

test("repair fence: failed cleanup restore closes resources without deleting", async () => {
  const root = privateRoot();
  const scenario = scenarioFixture(root);
  const candidate = candidateBindingFixture("diagnostic");
  runner.writeCleanupRecoveryState(
    scenario.outputs.cleanupState,
    {
      schema: "viventium.voice.mpv-061.cleanup-state.v1",
      caseId: "MPV-061",
      status: "armed",
      scenarioBindingSha256: "a".repeat(64),
      candidate,
      owner: {
        userId: "aaaaaaaaaaaaaaaaaaaaaaaa",
        email: "viventium-voice-qa-recovery@example.com",
        insertedAtMs: 1_780_000_000_000,
        acknowledged: true,
        callSessionId: "",
      },
    },
    root,
  );
  let closed = 0;
  let deleted = false;
  await assert.rejects(
    () =>
      runner.recoverCleanupOnly({
        scenario,
        evidenceRoot: root,
        environment: {},
        scenarioBindingSha256: "a".repeat(64),
        createRuntime: () => ({
          async preflightCleanup() {},
          async restoreCleanupState() {
            throw new runner.JourneyBlocked("cleanup_state_incomplete");
          },
          async cleanup() {
            deleted = true;
          },
          async closeResources() {
            closed += 1;
          },
        }),
      }),
    blockerIs("cleanup_state_incomplete"),
  );
  assert.equal(closed, 1);
  assert.equal(deleted, false);
});

test("repair fence: a signal bound during execution reaches cleanup exactly once", async () => {
  const root = privateRoot();
  const scenario = scenarioFixture(root);
  const candidate = candidateBindingFixture("diagnostic");
  scenario.candidate = candidate;
  const source = scenarioPath(root, scenario);
  const processLike = new EventEmitter();
  const recovery = runner.createSignalRecovery(processLike);
  recovery.install();
  let interrupted = false;
  let cleanupCount = 0;
  const result = await runner.runInstalledJourney(
    [
      "--local-qa",
      "--allow-synthetic-account",
      "--allow-runtime-restart",
      "--candidate-mode",
      "diagnostic",
      "--evidence-root",
      root,
      "--scenario",
      source,
    ],
    {
      environment: {
        VIVENTIUM_QA_ALLOW_DIAGNOSTIC_CANDIDATE: "1",
        VIVENTIUM_QA_ALLOW_MPV061_RUNTIME_RESTART: "1",
      },
      inspectCandidate: () => candidate,
      signalRecovery: recovery,
      createRuntime: () => ({
        requestInterruption(signal) {
          interrupted = signal === "SIGTERM";
        },
        async preflight() {},
        async execute() {
          processLike.emit("SIGTERM");
          if (interrupted)
            throw new runner.JourneyBlocked("journey_interrupted");
          throw new Error("signal was not bound to the active runtime");
        },
        async cleanup() {
          cleanupCount += 1;
        },
      }),
    },
  );
  recovery.uninstall();
  assert.equal(result.status, "BLOCKED");
  assert.equal(result.blocker, "journey_interrupted");
  assert.equal(interrupted, true);
  assert.equal(cleanupCount, 1);
});

test("repair fence: interruption after owner insert arms recovery before setup stops", async () => {
  const internal = privateRunnerBindings();
  const root = privateRoot();
  const scenario = scenarioFixture(root);
  scenario.runtime.voice = {
    stt: { provider: "fixture-stt" },
    tts: { provider: "fixture-tts" },
  };
  const candidate = candidateBindingFixture("diagnostic");
  const runtime = new internal.InstalledJourneyRuntime({
    scenario,
    evidenceRoot: root,
    identityDigests: candidate,
    environment: {},
    restartPlan: null,
    scenarioBindingSha256: "a".repeat(64),
  });
  const ownerId = "aaaaaaaaaaaaaaaaaaaaaaaa";
  const email = "viventium-voice-qa-interrupted@example.com";
  let insertedOwner = null;
  let seedContinued = false;
  runtime.db = {
    collection(name) {
      assert.equal(name, "users");
      return {
        async insertOne(document) {
          insertedOwner = document;
          runtime.requestInterruption("SIGTERM");
          return { acknowledged: true, insertedId: document._id };
        },
        async findOne() {
          return insertedOwner;
        },
      };
    },
  };
  runtime.helpers = {
    async seedCallSession(database) {
      const createdAt = new Date();
      await database.collection("users").insertOne({
        _id: ownerId,
        email,
        createdAt,
      });
      seedContinued = true;
      return {
        userId: ownerId,
        email,
        callSessionId: "synthetic-call",
        browserCapability: "b".repeat(43),
        syntheticPassword: "private-cleanup-password",
      };
    },
  };

  await assert.rejects(
    () => runtime.execute(),
    (error) => error.code === "journey_interrupted",
  );
  assert.equal(seedContinued, false);
  assert.equal(
    runner.readCleanupRecoveryState(scenario.outputs.cleanupState, {
      scenarioBindingSha256: "a".repeat(64),
    }).status,
    "armed",
  );
});
