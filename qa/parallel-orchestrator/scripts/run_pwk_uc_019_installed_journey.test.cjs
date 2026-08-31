"use strict";

const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const test = require("node:test");

const journey = require("./run_pwk_uc_019_installed_journey.cjs");
const RUNNER = path.join(__dirname, "run_pwk_uc_019_installed_journey.cjs");
const BRIDGE_SECRET = "synthetic-source-test-desktop-bridge-secret-32-bytes";
const BRIDGE_KEYS = crypto.generateKeyPairSync("ed25519");

function nativeProducerAuthority(producer) {
  const keys = crypto.generateKeyPairSync("ed25519");
  return {
    keys,
    authority: {
      producer,
      publicKey: keys.publicKey,
      keyId: sha256(keys.publicKey.export({ type: "spki", format: "der" })),
    },
  };
}

const CORE_NATIVE_AUTHORITY = nativeProducerAuthority("core.native_receipt");
const GLASSHIVE_NATIVE_AUTHORITY = nativeProducerAuthority(
  "glasshive.native_provider_receipt",
);

function sha256(value) {
  return crypto.createHash("sha256").update(value).digest("hex");
}

const BRIDGE_AUTHORITY = Object.freeze({
  publicKey: BRIDGE_KEYS.publicKey,
  keyId: sha256(BRIDGE_KEYS.publicKey.export({ type: "spki", format: "der" })),
  peerProcessId: process.ppid,
  sessionRef: "sky_synthetic019session",
  unitTestHarness: Object.freeze({
    kind: "node_test_only",
    processId: process.pid,
    parentProcessId: process.ppid,
    testFile: __filename,
  }),
});

function desktopOwner(ownerId, changes = {}) {
  return {
    ownerId,
    telegramUserId: "700019",
    telegramChatId: "800019",
    accountLabel: "Synthetic Worker QA",
    chatLabel: "Synthetic Viventium Chat",
    appBundleId: "ru.keepcoder.Telegram",
    ...changes,
  };
}

function signExternalDesktopProof(payload) {
  return (
    "ed25519:" +
    crypto
      .sign(
        null,
        Buffer.from(journey.canonicalJson(payload)),
        BRIDGE_KEYS.privateKey,
      )
      .toString("base64url")
  );
}

function opaque(kind, value) {
  return `sha256:${sha256(`${kind}\0${value}`)}`;
}

function signNativeProducerReceipt(receipt, producerAuthority) {
  const nowMs = Date.now();
  const { authority, keys } = producerAuthority;
  const unsigned = {
    contractVersion: 1,
    producer: authority.producer,
    keyId: authority.keyId,
    actor: receipt.actor,
    ownerRefHash: sha256(receipt.ownerId),
    surface: receipt.surface,
    workRefHash: receipt.actor === "worker" ? sha256(receipt.workRef) : null,
    runRefHash: receipt.actor === "worker" ? sha256(receipt.runRef) : null,
    snapshotHash: receipt.snapshotHash,
    nativeRequestSha256: receipt.nativeRequestSha256,
    providerAttemptRefHash: sha256(receipt.providerAttemptRef),
    providerRefHash: sha256(receipt.provider),
    modelRefHash: sha256(receipt.model),
    capsuleOccurrenceCount: receipt.capsuleOccurrenceCount,
    issuedAtMs: nowMs - 1000,
    expiresAtMs: nowMs + 60000,
  };
  return {
    ...unsigned,
    proof:
      "ed25519:" +
      crypto
        .sign(
          null,
          Buffer.from(journey.canonicalJson(unsigned)),
          keys.privateKey,
        )
        .toString("base64url"),
  };
}

function temporaryRoot(t) {
  const root = fs.mkdtempSync(
    path.join(os.tmpdir(), "pwk-uc-019-source-test-"),
  );
  fs.chmodSync(root, 0o700);
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  return root;
}

function safeEnvironment(changes = {}) {
  return {
    VIVENTIUM_QA_ALLOW_PWK_UC_019: "1",
    VIVENTIUM_QA_ALLOW_SYNTHETIC_FIXTURES: "1",
    VIVENTIUM_QA_ALLOW_PWK_UC_019_COMPUTER: "1",
    VIVENTIUM_QA_ALLOW_LOCAL_JWT: "1",
    VIVENTIUM_QA_OWNER_EMAIL: "owner@example.com",
    VIVENTIUM_QA_EMAIL: "worker-qa@example.com",
    JWT_SECRET: "synthetic-test-access-signing-material",
    JWT_REFRESH_SECRET: "synthetic-test-refresh-signing-material",
    ...changes,
  };
}

function liveArguments(root, changes = {}) {
  return {
    mode: "live",
    caseId: "PWK-UC-019",
    scenarioPath: path.join(root, "scenario.json"),
    outputDir: path.join(root, "evidence"),
    qaEmail: "worker-qa@example.com",
    clientBase: "http://127.0.0.1:3080",
    apiBase: "http://127.0.0.1:3080",
    playgroundBase: "http://127.0.0.1:3300",
    timeoutMs: 120000,
    candidateMode: "strict",
    allowRestart: false,
    headless: false,
    ...changes,
  };
}

function workRows() {
  return [0, 1].map((index) => ({
    ownerId: "synthetic-owner-019",
    originRef: "origin-shared",
    workRef: `work-${index}`,
    workerRef: `worker-${index}`,
    runRef: `run-${index}`,
    attemptRef: `attempt-${index}`,
    leaseRef: `lease-${index}`,
    containerRef: `container-${index}`,
    workspaceRef: sha256(`workspace-${index}`),
    executorRef: `executor-${index}`,
    executionMode: "docker",
    state: "completed",
    runtimeInvokedAt: `2026-08-25T12:00:0${index}.000Z`,
    attemptRuntimeInvokedAt: `2026-08-25T12:00:0${index}.000Z`,
    leaseAcquiredAt: "2026-08-25T11:59:59.000Z",
    leaseConfirmedAt: `2026-08-25T12:00:0${index}.500Z`,
    finishedAt: `2026-08-25T12:00:1${index}.000Z`,
    attemptFinishedAt: `2026-08-25T12:00:1${index}.000Z`,
    leaseReleasedAt: `2026-08-25T12:00:1${index}.000Z`,
    attemptNumber: 1,
  }));
}

function traceEvents(rows) {
  const ownerScopeHash = opaque("owner", "synthetic-owner-019");
  const originRefHash = opaque("origin", "origin-shared");
  const definitions = [
    { stage: "source.bound", facts: {} },
    ...rows.flatMap((row, index) => {
      const identity = {
        workRefHash: opaque("work", row.workRef),
        runRefHash: opaque("run", row.runRef),
      };
      const producer = {
        ...identity,
        attemptNumber: 1,
        producerTraceContractVersion: 2,
      };
      return [
        {
          stage: "prompt.layers.verified",
          facts: {
            ...producer,
            promptLayerContractVersion: 1,
            promptProducerScope: "glasshive.worker_prompt_registry",
            unknownPromptLayerCount: 0,
          },
        },
        { stage: "work.admitted", facts: producer },
        { stage: "runtime.invoked", facts: producer },
        {
          stage: "provider.request.forwarded",
          facts: {
            ...identity,
            provider: "openai",
            providerStatus: "completed",
            providerRequestRefHash: opaque(
              "provider_request",
              `request-${index}`,
            ),
          },
        },
        {
          stage: "work.completed",
          facts: { ...producer, state: "completed", terminal: true },
        },
        {
          stage: "callback.accepted",
          facts: { ...identity, attemptNumber: 1 },
        },
        {
          stage: "callback.delivery.sent",
          facts: { ...identity, attemptNumber: 1 },
        },
      ];
    }),
  ];
  let previousEventHash = `sha256:${"0".repeat(64)}`;
  return definitions.map((definition, index) => {
    const contentHash = `sha256:${sha256(
      journey.canonicalJson({
        schemaVersion: 1,
        stage: definition.stage,
        facts: definition.facts,
      }),
    )}`;
    const event = {
      schemaVersion: 1,
      ownerScopeHash,
      originRefHash,
      sequence: index + 1,
      stage: definition.stage,
      at: new Date(
        Date.parse("2026-08-25T12:01:00.000Z") + index * 1000,
      ).toISOString(),
      facts: definition.facts,
      eventKeyHash: `sha256:${sha256(`event-${index}`)}`,
      contentHash,
      previousEventHash,
    };
    event.eventHash = `sha256:${sha256(journey.canonicalJson(event))}`;
    previousEventHash = event.eventHash;
    return event;
  });
}

function sampleWav() {
  const bytes = Buffer.alloc(44 + 3200);
  bytes.write("RIFF", 0, "ascii");
  bytes.writeUInt32LE(bytes.length - 8, 4);
  bytes.write("WAVE", 8, "ascii");
  bytes.write("fmt ", 12, "ascii");
  bytes.writeUInt32LE(16, 16);
  bytes.writeUInt16LE(1, 20);
  bytes.writeUInt16LE(1, 22);
  bytes.writeUInt32LE(16000, 24);
  bytes.writeUInt32LE(32000, 28);
  bytes.writeUInt16LE(2, 32);
  bytes.writeUInt16LE(16, 34);
  bytes.write("data", 36, "ascii");
  bytes.writeUInt32LE(3200, 40);
  for (let offset = 44; offset < bytes.length; offset += 2) {
    bytes.writeInt16LE(offset % 8 === 0 ? 1200 : -1200, offset);
  }
  return bytes;
}

function validObservation() {
  const rows = workRows();
  const snapshotHash = sha256("one-request-pinned-feelings-capsule");
  const logicalTurnHash = sha256("assistant-main-available");
  const mainCapabilities = [
    "saved_memory",
    "conversation_recall",
    "files",
    "media",
    "broker_tool",
    "browser",
    "computer",
    "connected_account",
  ].map((kind) => ({
    kind,
    capabilityId: `capability-${kind}`,
    authorized: true,
    scopeRef: "scope-synthetic-owner",
  }));
  const inputs = [
    { kind: "document", bytes: Buffer.from("synthetic grouped document\n") },
    { kind: "image", bytes: Buffer.from("synthetic grouped media bytes\n") },
  ].map((input, index) => ({
    ...input,
    position: index,
    fileId: `synthetic-file-${index}`,
    ownerId: rows[0].ownerId,
    workRef: rows[0].workRef,
    runRef: rows[0].runRef,
    groupRef: "group-019",
    byteSha256: sha256(input.bytes),
    sizeBytes: input.bytes.length,
  }));
  const artifacts = rows.map((row, index) => {
    const bytes = Buffer.from(
      `<html><body>synthetic-result-${index}</body></html>`,
    );
    return {
      ownerId: row.ownerId,
      workRef: row.workRef,
      runRef: row.runRef,
      bytes,
      byteSha256: sha256(bytes),
      mediaType: "text/html",
      headed: true,
      visible: true,
      windowId: 100 + index,
      screenshotSha256: sha256(`window-${index}`),
      observations: [
        { surface: "web", byteSha256: sha256(bytes), verified: true },
        { surface: "telegram", byteSha256: sha256(bytes), verified: true },
      ],
      deliveryReceipt: {
        observed: true,
        ownerId: row.ownerId,
        workRef: row.workRef,
      },
    };
  });
  const observation = {
    caseId: "PWK-UC-019",
    candidate: {
      candidateDigest: sha256("candidate"),
      artifactDigest: sha256("installed-artifact"),
      installed: true,
    },
    ownerId: rows[0].ownerId,
    ownerEmail: "worker-qa@example.com",
    rows,
    quickTurn: {
      visible: true,
      finalReplyCount: 1,
      exactAnswer: true,
      logicalTurnHash,
      submittedAtMs: Date.parse("2026-08-25T12:00:03.000Z"),
      visibleAtMs: Date.parse("2026-08-25T12:00:04.000Z"),
      timingTimeline: {
        complete: true,
        turnIdHash: logicalTurnHash.slice(0, 16),
        submittedAtMs: Date.parse("2026-08-25T12:00:03.000Z"),
        domVisibleAtMs: Date.parse("2026-08-25T12:00:04.000Z"),
        presentationCommittedAtMs: Date.parse(
          "2026-08-25T12:00:03.900Z",
        ),
        counts: {
          providerAttempts: 1,
          providerOutputs: 1,
          toolInvocations: 0,
        },
      },
    },
    maxQuickLatencyMs: 10000,
    nativeReceipts: [
      {
        actor: "main",
        ownerId: rows[0].ownerId,
        surface: "voice",
        snapshotHash,
        capsuleOccurrenceCount: 1,
        materialized: true,
        receiptSource: "core.native_receipt",
        nativeRequestSha256: sha256("main-native-request"),
        providerAttemptRef: "provider-main",
        provider: "configured-primary",
        model: "configured-model",
      },
      ...rows.map((row) => ({
        actor: "worker",
        ownerId: row.ownerId,
        workRef: row.workRef,
        runRef: row.runRef,
        surface: "voice",
        snapshotHash,
        capsuleOccurrenceCount: 1,
        materialized: true,
        receiptSource: "glasshive.native_provider_receipt",
        nativeRequestSha256: sha256(`native-${row.runRef}`),
        providerAttemptRef: `provider-${row.runRef}`,
        provider: "configured-primary",
        model: "configured-model",
      })),
    ],
    routes: {
      originSurface: "voice",
      configured: [
        { provider: "configured-primary", model: "configured-model" },
      ],
      attempts: [
        {
          provider: "configured-primary",
          model: "configured-model",
          outcome: "used",
          observed: true,
        },
      ],
    },
    capabilityManifest: {
      ownerId: rows[0].ownerId,
      scopeRef: "scope-synthetic-owner",
      main: mainCapabilities,
      workers: rows.map((row) => ({
        ownerId: row.ownerId,
        workRef: row.workRef,
        runRef: row.runRef,
        scopeRef: "scope-synthetic-owner",
        capabilities: structuredClone(mainCapabilities),
      })),
    },
    capabilityReceipts: [
      {
        kind: "saved_memory",
        lane: "saved_memory",
        receiptId: "memory-saved",
        source: "core.memory_audit",
      },
      {
        kind: "conversation_recall",
        lane: "conversation_recall",
        receiptId: "memory-recall",
        source: "core.recall_audit",
      },
      {
        kind: "broker_tool",
        lane: "broker",
        receiptId: "broker-selected",
        source: "glasshive.capability_audit",
        selectedByModel: true,
      },
      {
        kind: "connected_account",
        lane: "connected_account",
        receiptId: "connected-read",
        source: "glasshive.capability_audit",
        selectedByModel: true,
        permission: "read",
        effects: "read_only",
      },
    ].map((receipt) => ({
      ...receipt,
      ownerId: rows[0].ownerId,
      workRef: rows[0].workRef,
      runRef: rows[0].runRef,
      capabilityId: `capability-${receipt.kind}`,
      scopeRef: "scope-synthetic-owner",
      authorized: true,
      observed: true,
      requestRef: `request-${receipt.receiptId}`,
      responseRef: `response-${receipt.receiptId}`,
    })),
    attachments: {
      ownerId: rows[0].ownerId,
      workRef: rows[0].workRef,
      runRef: rows[0].runRef,
      groupRef: "group-019",
      source: "telegram.desktop_capture",
      inputs,
      siblingInputIds: [],
    },
    actions: [
      {
        action: "steer",
        workRef: rows[0].workRef,
        ownerId: rows[0].ownerId,
        status: "accepted",
        source: "voice",
        receiptId: "steer-a",
        observed: true,
      },
      {
        action: "queue",
        workRef: rows[0].workRef,
        ownerId: rows[0].ownerId,
        status: "accepted",
        source: "voice",
        receiptId: "queue-a",
        observed: true,
        reused: true,
        workerRef: rows[0].workerRef,
      },
      {
        action: "message",
        workRef: rows[0].workRef,
        ownerId: rows[0].ownerId,
        status: "accepted",
        source: "voice",
        receiptId: "message-a",
        observed: true,
        reused: true,
        workerRef: rows[0].workerRef,
      },
    ],
    siblingState: { before: "sibling-unchanged", after: "sibling-unchanged" },
    callbacks: rows.map((row, index) => {
      const callbackRef = `callback-${row.runRef}`;
      const canonicalCallbackRef = `callback_sha256:${sha256(callbackRef)}`;
      const followUpMessageId = `follow-up-${index}`;
      return {
        ownerId: row.ownerId,
        originRef: row.originRef,
        workRef: row.workRef,
        runRef: row.runRef,
        callbackRef,
        event: "run.completed",
        callbackAttemptNumber: row.attemptNumber,
        callbackAttempts: 1,
        callbackDeliveryGeneration: 1,
        callbackResultRevision: 1,
        callbackResultDigest: `sha256:${sha256(`result-${index}`)}`,
        acceptedAt: "2026-08-25T12:00:22.000Z",
        deliveredAt: null,
        callbackStatus: "http_accepted",
        missionEvidenceCount: 1,
        missionEvidenceOwnerId: row.ownerId,
        missionEvidenceOriginRef: row.originRef,
        missionEvidenceWorkRef: row.workRef,
        missionEvidenceRunRef: row.runRef,
        missionEvidenceEvent: "run.completed",
        missionEvidenceCallbackRef: canonicalCallbackRef,
        missionEvidenceAttemptNumber: row.attemptNumber,
        missionEvidenceState: "completed",
        missionEvidenceWorkState: "completed",
        missionEvidenceWorkTerminal: true,
        missionEvidenceErrorCode: "",
        followUpMessageId,
        webPresentationMessageId: followUpMessageId,
        webPresentedAt: "2026-08-25T12:00:23.000Z",
        persistedMessageCount: 1,
        persistedMessageId: followUpMessageId,
        persistedMessageHasContent: true,
        visibleMessageCount: 1,
        visibleMessageId: followUpMessageId,
        visibleMessageHasContent: true,
        observed: true,
      };
    }),
    artifacts,
    voice: {
      ownerId: rows[0].ownerId,
      mode: "call",
      recording: sampleWav(),
      receivedAudioPackets: 3,
      receivedAudioEnergy: 2,
      source: "voice.call_capture",
      sessions: ["call-original", "call-reconnected"],
      segments: [
        { speaker: "user", action: "launch", workRef: rows[0].workRef },
        { speaker: "user", action: "launch", workRef: rows[1].workRef },
        { speaker: "main", action: "quick_answer" },
        { speaker: "user", action: "steer", workRef: rows[0].workRef },
        { speaker: "user", action: "hangup" },
        { speaker: "user", action: "reconnect" },
        { speaker: "main", action: "completion", workRef: rows[0].workRef },
        { speaker: "main", action: "completion", workRef: rows[1].workRef },
      ].map((segment, index) => ({
        ...segment,
        sequence: index + 1,
        ownerId: rows[0].ownerId,
        utteranceRef: `utterance-${index}`,
        verified: true,
      })),
    },
    denials: ["passive_wing", "listen_only"].map((mode) => ({
      ownerId: rows[0].ownerId,
      mode,
      decision: "denied",
      attemptedAction: "launch",
      workRowsCreated: 0,
      toolCalls: 0,
      source: "voice.surface_authority",
      observed: true,
    })),
    surfaces: {
      linkedChat: { visible: true, headed: true, ownerId: rows[0].ownerId },
      activeWork: {
        visible: true,
        headed: true,
        ownerId: rows[0].ownerId,
        workRefs: rows.map((row) => row.workRef),
      },
      telegram: {
        visible: true,
        signed: true,
        ownerId: rows[0].ownerId,
        source: "@oai/sky.get_app_state",
      },
    },
    trace: {
      ownerId: rows[0].ownerId,
      originRef: "origin-shared",
      source: "core.immutable_trace",
      events: traceEvents(rows),
    },
    semanticVerifier: {
      verified: true,
      caseId: "PWK-UC-019",
      candidateDigest: sha256("candidate"),
      artifactDigest: sha256("installed-artifact"),
      surface: "voice",
    },
    cleanup: { zeroResidue: true },
  };
  observation.nativeProducerAuthorities = {
    "core.native_receipt": CORE_NATIVE_AUTHORITY.authority,
    "glasshive.native_provider_receipt": GLASSHIVE_NATIVE_AUTHORITY.authority,
  };
  for (const receipt of observation.nativeReceipts) {
    const producerAuthority =
      receipt.actor === "main"
        ? CORE_NATIVE_AUTHORITY
        : GLASSHIVE_NATIVE_AUTHORITY;
    receipt.producerAttestation = signNativeProducerReceipt(
      receipt,
      producerAuthority,
    );
  }
  return observation;
}

function signedBridge(ownerId, changes = {}) {
  const owner = desktopOwner(ownerId);
  const now = Date.now();
  const unsigned = {
    contractVersion: 1,
    caseId: "PWK-UC-019",
    provider: "@oai/sky",
    controlPlane: "computer_plugin_node_repl",
    interface: "sky.get_app_state/sky-primitives",
    skyMethods: ["press_key", "click"],
    ownerId,
    telegramUserId: owner.telegramUserId,
    telegramChatId: owner.telegramChatId,
    appBundleId: owner.appBundleId,
    sessionRef: BRIDGE_AUTHORITY.sessionRef,
    authorityKeyId: BRIDGE_AUTHORITY.keyId,
    peerProcessId: BRIDGE_AUTHORITY.peerProcessId,
    issuedAtMs: now - 1000,
    expiresAtMs: now + 60000,
    ...changes,
  };
  function activeSelection() {
    return {
      source: "computer_ui_active_selection",
      observedAtMs: Date.now(),
      account: {
        selected: true,
        ownerId,
        telegramUserId: owner.telegramUserId,
        label: owner.accountLabel,
        evidence: "active_account_control",
      },
      chat: {
        selected: true,
        ownerId,
        telegramChatId: owner.telegramChatId,
        label: owner.chatLabel,
        evidence: "active_chat_header",
      },
    };
  }
  return {
    provenance: {
      ...unsigned,
      proof: signExternalDesktopProof(unsigned),
    },
    async get_app_state(request) {
      const payload = {
        source: "@oai/sky.get_app_state",
        app: owner.appBundleId,
        ownerId,
        telegramUserId: owner.telegramUserId,
        telegramChatId: owner.telegramChatId,
        sessionRef: unsigned.sessionRef,
        peerProcessId: BRIDGE_AUTHORITY.peerProcessId,
        challenge: request.challenge,
        observedAtMs: Date.now(),
        activeSelection: activeSelection(),
        visible: true,
      };
      return { ...payload, proof: signExternalDesktopProof(payload) };
    },
    async do_action(request) {
      const payload = {
        source: "@oai/sky." + request.skyMethod,
        app: owner.appBundleId,
        ownerId,
        telegramUserId: owner.telegramUserId,
        telegramChatId: owner.telegramChatId,
        sessionRef: unsigned.sessionRef,
        peerProcessId: BRIDGE_AUTHORITY.peerProcessId,
        challenge: request.challenge,
        observedAtMs: Date.now(),
        activeSelection: activeSelection(),
        action: request.action,
        skyMethod: request.skyMethod,
        selectionChallenge: request.selectionChallenge,
        selectionSha256: request.selectionSha256,
      };
      return { ...payload, proof: signExternalDesktopProof(payload) };
    },
  };
}

test("dry-run is inert, headed-only, pre-gate, and lists every PWK-UC-019 acceptance guard", () => {
  const args = journey.parseArguments(["--dry-run"]);
  const result = journey.dryRunPlan(args);
  assert.equal(result.caseId, "PWK-UC-019");
  assert.equal(result.status, "DRY_RUN");
  assert.equal(result.releaseLabel, "PRE-GATE / NOT READY");
  assert.equal(result.releaseReady, false);
  assert.equal(result.receiptEligible, false);
  assert.equal(result.sideEffects, false);
  assert.equal(result.launchesBrowser, false);
  assert.equal(result.invokesModels, false);
  for (const check of [
    "audible-call",
    "telegram-attachment-ingress",
    "memory-and-recall",
    "connected-or-broker-tool",
    "two-distinct-missions",
    "spoken-steer-a-only",
    "hangup-and-reconnect",
    "passive-wing-denial",
    "listen-only-denial",
    "request-pinned-feelings-parity",
    "native-provider-receipts",
    "queue-message-worker-reuse",
    "redacted-end-to-end-trace",
    "synthetic-owner-zero-residue",
  ])
    assert.ok(result.requiredChecks.includes(check), check);
});

test("semantic verifier contract covers all 25 PWK-UC-019 guards", () => {
  assert.equal(journey.REQUIRED_CHECKS.length, 25);
  assert.deepEqual(
    [...journey.SEMANTIC_REQUIRED_CHECKS].sort(),
    [...journey.REQUIRED_CHECKS].sort(),
  );
});

test("command-line dry-run never reads services or creates an evidence directory", (t) => {
  const root = temporaryRoot(t);
  const untouched = path.join(root, "never-created");
  const result = spawnSync(process.execPath, [RUNNER, "--dry-run"], {
    encoding: "utf8",
    env: { PATH: process.env.PATH || "", VIVENTIUM_QA_PRIVATE_DIR: untouched },
  });
  assert.equal(result.status, 0, result.stderr);
  assert.equal(JSON.parse(result.stdout).caseId, "PWK-UC-019");
  assert.equal(fs.existsSync(untouched), false);
});

test("execution mode, live arguments, and restart consent are explicit", () => {
  assert.throws(
    () => journey.parseArguments([]),
    /explicit_execution_mode_required/,
  );
  assert.throws(
    () => journey.parseArguments(["--dry-run", "--live"]),
    /conflicting_execution_modes/,
  );
  assert.throws(
    () => journey.parseArguments(["--dry-run", "--allow-restart"]),
    /dry_run_rejects_live_arguments/,
  );
  assert.throws(
    () => journey.parseArguments(["--live"]),
    /missing_required_argument/,
  );
});

for (const [name, update, code] of [
  [
    "missing local opt-in",
    { VIVENTIUM_QA_ALLOW_PWK_UC_019: "" },
    "installed_worker_parity_requires_explicit_opt_in",
  ],
  [
    "missing synthetic consent",
    { VIVENTIUM_QA_ALLOW_SYNTHETIC_FIXTURES: "" },
    "synthetic_fixture_consent_required",
  ],
  [
    "missing owner guard",
    { VIVENTIUM_QA_OWNER_EMAIL: "" },
    "owner_identity_guard_required",
  ],
  [
    "missing ephemeral opt-in",
    { VIVENTIUM_QA_ALLOW_LOCAL_JWT: "" },
    "ephemeral_browser_session_requires_explicit_opt_in",
  ],
  [
    "wrong synthetic account",
    { VIVENTIUM_QA_EMAIL: "other@example.com" },
    "configured_synthetic_qa_account_mismatch",
  ],
  ["production", { NODE_ENV: "production" }, "local_installed_qa_only"],
  ["CI", { CI: "1" }, "local_installed_qa_only"],
]) {
  test(`live safety rejects ${name} before any installed access`, (t) => {
    assert.throws(
      () =>
        journey.assertLiveOptIn(
          liveArguments(temporaryRoot(t)),
          safeEnvironment(update),
        ),
      new RegExp(code),
    );
  });
}

test("personal, non-synthetic, non-loopback, and headless journeys fail closed", (t) => {
  const root = temporaryRoot(t);
  assert.throws(
    () =>
      journey.assertLiveOptIn(
        liveArguments(root, { qaEmail: "owner@example.com" }),
        safeEnvironment(),
      ),
    /personal_owner_account_refused/,
  );
  assert.throws(
    () =>
      journey.assertLiveOptIn(
        liveArguments(root, { qaEmail: "worker-qa@invalid" }),
        safeEnvironment(),
      ),
    /synthetic_qa_account_required/,
  );
  assert.throws(
    () =>
      journey.assertLiveOptIn(
        liveArguments(root, { clientBase: "https://example.com" }),
        safeEnvironment(),
      ),
    /loopback_url_required/,
  );
  assert.throws(
    () =>
      journey.assertLiveOptIn(
        liveArguments(root, { headless: true }),
        safeEnvironment(),
      ),
    /headed_browser_required/,
  );
});

test("coordinated restart remains unavailable without independent explicit opt-in", (t) => {
  const args = liveArguments(temporaryRoot(t), { allowRestart: true });
  assert.throws(
    () => journey.assertLiveOptIn(args, safeEnvironment()),
    /coordinated_restart_requires_explicit_permission/,
  );
  assert.doesNotThrow(() =>
    journey.assertLiveOptIn(
      args,
      safeEnvironment({
        VIVENTIUM_QA_ALLOW_COORDINATED_RESTART: "1",
      }),
    ),
  );
});

test("signed Computer adapter is owner-bound, fresh, and exclusively Sky-backed", () => {
  const ownerId = "synthetic-owner-019";
  const adapter = signedBridge(ownerId);
  const bridge = journey.assertSignedDesktopAdapter(
    adapter,
    desktopOwner(ownerId),
    safeEnvironment(),
    {
      authority: BRIDGE_AUTHORITY,
    },
  );
  assert.equal(bridge.provenance.provider, "@oai/sky");
  assert.throws(
    () =>
      journey.assertSignedDesktopAdapter(
        null,
        desktopOwner(ownerId),
        safeEnvironment(),
        {
          authority: BRIDGE_AUTHORITY,
        },
      ),
    /computer_desktop_driver_unavailable/,
  );
  assert.throws(
    () =>
      journey.assertSignedDesktopAdapter(
        adapter,
        desktopOwner("another-owner"),
        safeEnvironment(),
        {
          authority: BRIDGE_AUTHORITY,
        },
      ),
    /computer_desktop_driver_owner_mismatch/,
  );
  assert.throws(
    () =>
      journey.assertSignedDesktopAdapter(
        signedBridge(ownerId, {
          expiresAtMs: Date.now() - 1,
        }),
        desktopOwner(ownerId),
        safeEnvironment(),
        { authority: BRIDGE_AUTHORITY },
      ),
    /computer_desktop_driver_attestation_expired/,
  );
  adapter.provenance.proof = "ed25519:" + "0".repeat(86);
  assert.throws(
    () =>
      journey.assertSignedDesktopAdapter(
        adapter,
        desktopOwner(ownerId),
        safeEnvironment(),
        {
          authority: BRIDGE_AUTHORITY,
        },
      ),
    /computer_desktop_driver_authentication_failed/,
  );
});

test("every desktop action and observation must have a signed fresh owner-bound challenge", async () => {
  const ownerId = "synthetic-owner-019";
  const adapter = signedBridge(ownerId);
  const bridge = journey.assertSignedDesktopAdapter(
    adapter,
    desktopOwner(ownerId),
    safeEnvironment(),
    {
      authority: BRIDGE_AUTHORITY,
    },
  );
  const observed = await journey.observeSignedDesktop(bridge, {
    method: "get_app_state",
    app: "ru.keepcoder.Telegram",
  });
  assert.equal(observed.source, "@oai/sky.get_app_state");
  const performed = await journey.observeSignedDesktop(bridge, {
    method: "press_key",
    app: "ru.keepcoder.Telegram",
    action: "telegram.send_grouped_attachments",
  });
  assert.equal(performed.source, "@oai/sky.press_key");
  await assert.rejects(
    () =>
      journey.observeSignedDesktop(bridge, {
        method: "do_action",
        action: "unsupported",
      }),
    /computer_desktop_action_unsupported/,
  );
});

test("a caller-owned HMAC cannot impersonate the external Computer authority", () => {
  const ownerId = "synthetic-owner-019";
  assert.throws(
    () =>
      journey.assertSignedDesktopAdapter(
        signedBridge(ownerId),
        desktopOwner(ownerId),
        safeEnvironment(),
        {
          secret: BRIDGE_SECRET,
        },
      ),
    /computer_desktop_external_authority_required/,
  );
});

test("a caller-generated Ed25519 key cannot impersonate the Computer signer in the runner process", () => {
  const ownerId = "synthetic-owner-019";
  const callerKeys = crypto.generateKeyPairSync("ed25519");
  const callerAuthority = {
    publicKey: callerKeys.publicKey,
    keyId: sha256(callerKeys.publicKey.export({ type: "spki", format: "der" })),
    peerProcessId: process.pid,
    sessionRef: "sky_caller_forged_session",
  };
  const adapter = signedBridge(ownerId);
  const { proof, ...unsigned } = adapter.provenance;
  const forged = {
    ...unsigned,
    authorityKeyId: callerAuthority.keyId,
    peerProcessId: callerAuthority.peerProcessId,
    sessionRef: callerAuthority.sessionRef,
  };
  adapter.provenance = {
    ...forged,
    proof:
      "ed25519:" +
      crypto
        .sign(
          null,
          Buffer.from(journey.canonicalJson(forged)),
          callerKeys.privateKey,
        )
        .toString("base64url"),
  };

  assert.throws(
    () =>
      journey.assertSignedDesktopAdapter(
        adapter,
        desktopOwner(ownerId),
        safeEnvironment(),
        {
          authority: callerAuthority,
        },
      ),
    /computer_desktop_external_authority_required/,
  );
});

test("a borrowed parent PID without an authenticated parent IPC grant cannot authorize Computer actions", () => {
  const ownerId = "synthetic-owner-019";
  const callerKeys = crypto.generateKeyPairSync("ed25519");
  const callerAuthority = {
    publicKey: callerKeys.publicKey,
    keyId: sha256(callerKeys.publicKey.export({ type: "spki", format: "der" })),
    peerProcessId: process.ppid,
    sessionRef: "sky_borrowed_parent_session",
  };
  const adapter = signedBridge(ownerId);
  const { proof, ...unsigned } = adapter.provenance;
  const forged = {
    ...unsigned,
    authorityKeyId: callerAuthority.keyId,
    peerProcessId: callerAuthority.peerProcessId,
    sessionRef: callerAuthority.sessionRef,
  };
  adapter.provenance = {
    ...forged,
    proof:
      "ed25519:" +
      crypto
        .sign(
          null,
          Buffer.from(journey.canonicalJson(forged)),
          callerKeys.privateKey,
        )
        .toString("base64url"),
  };

  assert.throws(
    () =>
      journey.assertSignedDesktopAdapter(
        adapter,
        desktopOwner(ownerId),
        safeEnvironment(),
        {
          authority: callerAuthority,
        },
      ),
    /computer_desktop_parent_transport_unavailable/,
  );
});

test("a caller-supplied process probe cannot manufacture external Computer authority", () => {
  const ownerId = "synthetic-owner-019";

  assert.throws(
    () =>
      journey.assertSignedDesktopAdapter(
        signedBridge(ownerId),
        desktopOwner(ownerId),
        safeEnvironment(),
        {
          authority: BRIDGE_AUTHORITY,
          processProbe: () => true,
        },
      ),
    /computer_desktop_external_authority_required/,
  );
});

test("live Worker acceptance rejects both direct and inherited-transport source-test Computer authorities", () => {
  assert.throws(
    () => journey.assertProductionDesktopAuthority(BRIDGE_AUTHORITY),
    /computer_desktop_test_authority_forbidden/,
  );
  assert.throws(
    () =>
      journey.assertProductionDesktopAuthority({
        transport: { unitTestHarness: { kind: "node_test_only" } },
      }),
    /computer_desktop_test_authority_forbidden/,
  );
  assert.doesNotThrow(() =>
    journey.assertProductionDesktopAuthority({
      transport: { kind: "inherited_parent_ipc" },
    }),
  );
});

test("an invented sky.do_action primitive cannot receive user-level desktop authority", async () => {
  const ownerId = "synthetic-owner-019";
  const bridge = journey.assertSignedDesktopAdapter(
    signedBridge(ownerId),
    desktopOwner(ownerId),
    safeEnvironment(),
    {
      authority: BRIDGE_AUTHORITY,
    },
  );

  await assert.rejects(
    () =>
      journey.observeSignedDesktop(bridge, {
        method: "do_action",
        action: "telegram.send_grouped_attachments",
      }),
    /computer_desktop_action_unsupported|computer_desktop_sky_primitive_unsupported/,
  );
});

test("desktop state without a proved actively selected account and chat fails closed", async () => {
  const ownerId = "synthetic-owner-019";
  const adapter = signedBridge(ownerId);
  const readState = adapter.get_app_state;
  adapter.get_app_state = async (request) => {
    const observed = await readState(request);
    const { proof, activeSelection, ...unsigned } = observed;
    return { ...unsigned, proof: signExternalDesktopProof(unsigned) };
  };
  const bridge = journey.assertSignedDesktopAdapter(
    adapter,
    desktopOwner(ownerId),
    safeEnvironment(),
    {
      authority: BRIDGE_AUTHORITY,
    },
  );

  await assert.rejects(
    () =>
      journey.observeSignedDesktop(bridge, {
        method: "get_app_state",
        app: "synthetic.telegram",
      }),
    /computer_desktop_active_selection_unavailable/,
  );
});

test("Main and both direct Workers receive one identical pinned Feelings native receipt", () => {
  const evidence = validObservation();
  const result = journey.assessFeelingsParity(
    evidence.nativeReceipts,
    evidence.rows,
    evidence.ownerId,
    evidence.nativeProducerAuthorities,
  );
  assert.equal(result.pass, true);
  assert.equal(result.receiptCount, 3);
});

for (const [name, mutate, code] of [
  [
    "missing Worker receipt",
    (value) => value.nativeReceipts.pop(),
    "three_native_provider_receipts_required",
  ],
  [
    "different pinned capsule",
    (value) => {
      value.nativeReceipts[1].snapshotHash = sha256("different");
    },
    "request_pinned_feelings_capsule_mismatch",
  ],
  [
    "duplicate capsule",
    (value) => {
      value.nativeReceipts[2].capsuleOccurrenceCount = 2;
    },
    "native_feelings_capsule_must_appear_once",
  ],
  [
    "unmaterialized provider receipt",
    (value) => {
      value.nativeReceipts[1].materialized = false;
    },
    "native_provider_receipt_unobserved",
  ],
  [
    "wrong owner",
    (value) => {
      value.nativeReceipts[1].ownerId = "other";
    },
    "native_provider_receipt_owner_mismatch",
  ],
  [
    "wrong worker",
    (value) => {
      value.nativeReceipts[1].workRef = "unknown";
    },
    "native_provider_receipt_worker_mismatch",
  ],
]) {
  test(`Feelings parity rejects ${name}`, () => {
    const evidence = validObservation();
    mutate(evidence);
    assert.throws(
      () =>
        journey.assessFeelingsParity(
          evidence.nativeReceipts,
          evidence.rows,
          evidence.ownerId,
          evidence.nativeProducerAuthorities,
        ),
      new RegExp(code),
    );
  });
}

test("provider route uses only actual configured primary or explicitly authorized fallback", () => {
  const evidence = validObservation();
  assert.equal(
    journey.assessRouteParity(evidence.routes, evidence.nativeReceipts).pass,
    true,
  );
  evidence.routes.configured.push({
    provider: "configured-fallback",
    model: "fallback-model",
  });
  evidence.routes.attempts = [
    {
      provider: "configured-primary",
      model: "configured-model",
      outcome: "used",
      observed: true,
    },
    {
      provider: "configured-primary",
      model: "configured-model",
      outcome: "quota_exhausted",
      observed: true,
    },
    {
      provider: "configured-fallback",
      model: "fallback-model",
      outcome: "used",
      observed: true,
      fallback: true,
    },
  ];
  evidence.nativeReceipts[2].provider = "configured-fallback";
  evidence.nativeReceipts[2].model = "fallback-model";
  assert.equal(
    journey.assessRouteParity(evidence.routes, evidence.nativeReceipts)
      .fallbackObserved,
    true,
  );
  evidence.nativeReceipts[2].provider = "unauthorized-provider";
  assert.throws(
    () => journey.assessRouteParity(evidence.routes, evidence.nativeReceipts),
    /unconfigured_provider_route_refused/,
  );
});

test("full Worker manifests preserve each authorized Main capability without extra grants", () => {
  const evidence = validObservation();
  const result = journey.assessCapabilityParity(
    evidence.capabilityManifest,
    evidence.capabilityReceipts,
    evidence.rows,
  );
  assert.equal(result.pass, true);
  assert.equal(result.workerCount, 2);
});

for (const [name, mutate, code] of [
  [
    "saved memory absent",
    (value) => {
      value.capabilityReceipts = value.capabilityReceipts.filter(
        (row) => row.kind !== "saved_memory",
      );
    },
    "saved_memory_lane_receipt_unavailable",
  ],
  [
    "recall absent",
    (value) => {
      value.capabilityReceipts = value.capabilityReceipts.filter(
        (row) => row.kind !== "conversation_recall",
      );
    },
    "conversation_recall_lane_receipt_unavailable",
  ],
  [
    "lane conflation",
    (value) => {
      value.capabilityReceipts[1].lane = "saved_memory";
    },
    "conversation_recall_lane_receipt_unavailable",
  ],
  [
    "missing Computer",
    (value) => {
      value.capabilityManifest.workers[1].capabilities =
        value.capabilityManifest.workers[1].capabilities.filter(
          (row) => row.kind !== "computer",
        );
    },
    "worker_capability_parity_incomplete",
  ],
  [
    "extra authority",
    (value) => {
      value.capabilityManifest.workers[0].capabilities.push({
        kind: "extra",
        capabilityId: "unauthorized",
        authorized: true,
        scopeRef: "scope-synthetic-owner",
      });
    },
    "worker_capability_authority_exceeds_main",
  ],
  [
    "unobserved tool use",
    (value) => {
      value.capabilityReceipts[2].observed = false;
    },
    "model_selected_tool_receipt_unavailable",
  ],
  [
    "forced tool use",
    (value) => {
      value.capabilityReceipts[2].selectedByModel = false;
    },
    "model_selected_tool_receipt_unavailable",
  ],
  [
    "connected write",
    (value) => {
      value.capabilityReceipts[3].effects = "write";
    },
    "connected_account_permission_exceeded",
  ],
  [
    "missing connected permission",
    (value) => {
      value.capabilityReceipts[3].permission = "";
    },
    "connected_account_permission_unverified",
  ],
  [
    "sibling receipt leak",
    (value) => {
      value.capabilityReceipts[0].ownerId = "other";
    },
    "capability_receipt_owner_scope_mismatch",
  ],
]) {
  test(`capability parity rejects ${name}`, () => {
    const evidence = validObservation();
    mutate(evidence);
    assert.throws(
      () =>
        journey.assessCapabilityParity(
          evidence.capabilityManifest,
          evidence.capabilityReceipts,
          evidence.rows,
        ),
      new RegExp(code),
    );
  });
}

test("grouped synthetic files retain exact owner, Worker, bytes, IDs, and order", () => {
  const evidence = validObservation();
  assert.equal(
    journey.assessAttachmentParity(evidence.attachments, evidence.rows).pass,
    true,
  );
  evidence.attachments.inputs.reverse();
  assert.throws(
    () => journey.assessAttachmentParity(evidence.attachments, evidence.rows),
    /grouped_attachment_order_mismatch/,
  );
});

for (const [name, mutate, code] of [
  [
    "changed bytes",
    (value) => {
      value.attachments.inputs[0].bytes = Buffer.from("altered");
    },
    "attachment_exact_bytes_unverified",
  ],
  [
    "sibling disclosure",
    (value) => {
      value.attachments.siblingInputIds = ["synthetic-file-0"];
    },
    "attachment_leaked_to_sibling_worker",
  ],
  [
    "cross-owner file",
    (value) => {
      value.attachments.inputs[0].ownerId = "other";
    },
    "attachment_owner_scope_mismatch",
  ],
  [
    "duplicate file",
    (value) => {
      value.attachments.inputs[1].fileId = value.attachments.inputs[0].fileId;
    },
    "grouped_attachment_file_identity_invalid",
  ],
]) {
  test(`file parity rejects ${name}`, () => {
    const evidence = validObservation();
    mutate(evidence);
    assert.throws(
      () => journey.assessAttachmentParity(evidence.attachments, evidence.rows),
      new RegExp(code),
    );
  });
}

test("speech Steer affects A only and Queue/Message reuse the same existing Worker", () => {
  const evidence = validObservation();
  assert.equal(
    journey.assessControlParity(
      evidence.actions,
      evidence.rows,
      evidence.siblingState,
    ).pass,
    true,
  );
  evidence.actions[1].workerRef = "a-different-worker";
  assert.throws(
    () =>
      journey.assessControlParity(
        evidence.actions,
        evidence.rows,
        evidence.siblingState,
      ),
    /existing_worker_queue_message_reuse_unverified/,
  );
});

test("an actual audible call preserves owner speech, one Main voice, and reconnect order", () => {
  const evidence = validObservation();
  assert.equal(
    journey.assessVoiceJourney(evidence.voice, evidence.rows).pass,
    true,
  );
  evidence.voice.segments[2].speaker = "worker";
  assert.throws(
    () => journey.assessVoiceJourney(evidence.voice, evidence.rows),
    /main_must_be_the_only_assistant_voice/,
  );
});

for (const [name, mutate, code] of [
  [
    "silent audio",
    (value) => value.voice.recording.fill(0, 44),
    "audible_voice_recording_unavailable",
  ],
  [
    "missing audio energy",
    (value) => {
      value.voice.receivedAudioEnergy = 0;
    },
    "audible_voice_playback_unobserved",
  ],
  [
    "wrong action order",
    (value) => {
      value.voice.segments[4].action = "reconnect";
    },
    "voice_hangup_reconnect_order_invalid",
  ],
  [
    "duplicate completion",
    (value) => {
      value.voice.segments[7].workRef = value.rows[0].workRef;
    },
    "voice_worker_completion_not_exactly_once",
  ],
  [
    "unverified owner speaker",
    (value) => {
      value.voice.segments[0].verified = false;
    },
    "verified_owner_voice_unavailable",
  ],
]) {
  test(`audible Voice proof rejects ${name}`, () => {
    const evidence = validObservation();
    mutate(evidence);
    assert.throws(
      () => journey.assessVoiceJourney(evidence.voice, evidence.rows),
      new RegExp(code),
    );
  });
}

test("passive Wing and Listen-Only both deny launch with zero side effects", () => {
  const evidence = validObservation();
  assert.equal(
    journey.assessSurfaceDenials(evidence.denials, evidence.ownerId).pass,
    true,
  );
  evidence.denials[0].workRowsCreated = 1;
  assert.throws(
    () => journey.assessSurfaceDenials(evidence.denials, evidence.ownerId),
    /passive_surface_created_work_or_used_tools/,
  );
});

test("artifacts use distinct headed windows and exact cross-surface bytes", () => {
  const evidence = validObservation();
  assert.equal(
    journey.assessArtifactParity(
      evidence.artifacts,
      evidence.rows,
      evidence.ownerId,
    ).pass,
    true,
  );
  evidence.artifacts[0].observations[1].byteSha256 = sha256(
    "different surface bytes",
  );
  assert.throws(
    () =>
      journey.assessArtifactParity(
        evidence.artifacts,
        evidence.rows,
        evidence.ownerId,
      ),
    /cross_surface_artifact_bytes_mismatch/,
  );
});

test("one immutable owner-scoped trace binds both completed Workers and callbacks", () => {
  const evidence = validObservation();
  assert.equal(
    journey.assessImmutableTrace(evidence.trace, evidence.rows).pass,
    true,
  );
  evidence.trace.events[2].facts.workRefHash = opaque("work", "forged");
  assert.throws(
    () => journey.assessImmutableTrace(evidence.trace, evidence.rows),
    /immutable_trace_hash_chain_invalid/,
  );
});

test("semantic trace export is derived from the verified V2 Core ledger", () => {
  const evidence = validObservation();
  const exported = journey.buildSemanticTraceExport(
    evidence.trace,
    evidence.rows,
    { logicalTurnRefHash: sha256("logical-turn-019"), turnRevision: 3 },
  );
  assert.equal(exported.producer, "core.origin_trace");
  assert.equal(exported.payload.contractVersion, 2);
  assert.equal(exported.payload.producerTraceContractVersion, 2);
  assert.equal(exported.payload.fullChainVerified, true);
  assert.equal(exported.payload.overflowCount, 0);
  assert.equal(exported.payload.eventCount, exported.payload.events.length);
  assert.equal(
    exported.payload.events.filter(
      (event) => event.eventType === "provider.request.forwarded",
    ).length,
    evidence.rows.length,
  );
});

test("trace rejects raw private prompt, history, token, or private state fields", () => {
  const evidence = validObservation();
  evidence.trace.events[1].facts.prompt = "unrelated private conversation";
  assert.throws(
    () => journey.assessImmutableTrace(evidence.trace, evidence.rows),
    /trace_contains_unredacted_private_data/,
  );
});

test("complete genuine capability evidence passes every PWK-UC-019 guard", () => {
  const evidence = validObservation();
  const result = journey.evaluateCapabilityJourney(evidence, {
    candidateMode: "strict",
  });
  assert.equal(result.caseId, "PWK-UC-019");
  assert.equal(result.status, "PASS");
  assert.equal(result.pass, true);
  assert.equal(result.workerCount, 2);
  assert.equal(result.nativeReceiptCount, 3);
  assert.equal(result.releaseReady, false);
  assert.equal(result.releaseLabel, "PRE-GATE / NOT READY");
});

test("diagnostic candidates cannot create a release-eligible acceptance result", () => {
  const result = journey.evaluateCapabilityJourney(validObservation(), {
    candidateMode: "diagnostic",
  });
  assert.equal(result.status, "PRE_GATE_COMPLETE");
  assert.equal(result.releaseReady, false);
  assert.equal(result.receiptEligible, false);
});

test("missing independent semantic verification cannot become PASS", () => {
  const evidence = validObservation();
  evidence.semanticVerifier.verified = false;
  assert.throws(
    () =>
      journey.evaluateCapabilityJourney(evidence, { candidateMode: "strict" }),
    /independent_semantic_verifier_receipt_unavailable/,
  );
});

test("the evaluator cannot create PASS before zero-residue cleanup", () => {
  const evidence = validObservation();
  delete evidence.cleanup;
  assert.throws(
    () =>
      journey.evaluateCapabilityJourney(evidence, { candidateMode: "strict" }),
    /synthetic_cleanup_receipt_unavailable/,
  );
});

test("the semantic receipt writer has a private post-cleanup capability", () => {
  assert.throws(
    () => journey.verifyIndependentSemantics("unread.json", {}),
    /semantic_receipt_requires_completed_cleanup/,
  );
});

test("native Main and Worker receipts require producer-signed owner-bound attestations", () => {
  const observation = validObservation();
  const receipt = observation.nativeReceipts[1];
  const { keys, authority } = nativeProducerAuthority(
    "glasshive.native_provider_receipt",
  );
  const nowMs = Date.now();
  const unsigned = {
    contractVersion: 1,
    producer: authority.producer,
    keyId: authority.keyId,
    actor: receipt.actor,
    ownerRefHash: sha256(receipt.ownerId),
    surface: receipt.surface,
    workRefHash: sha256(receipt.workRef),
    runRefHash: sha256(receipt.runRef),
    snapshotHash: receipt.snapshotHash,
    nativeRequestSha256: receipt.nativeRequestSha256,
    providerAttemptRefHash: sha256(receipt.providerAttemptRef),
    providerRefHash: sha256(receipt.provider),
    modelRefHash: sha256(receipt.model),
    capsuleOccurrenceCount: 1,
    issuedAtMs: nowMs - 1000,
    expiresAtMs: nowMs + 60000,
  };
  const attestation = {
    ...unsigned,
    proof:
      "ed25519:" +
      crypto
        .sign(
          null,
          Buffer.from(journey.canonicalJson(unsigned)),
          keys.privateKey,
        )
        .toString("base64url"),
  };

  assert.equal(
    journey.verifyNativeProducerAttestation(
      receipt,
      attestation,
      authority,
      nowMs,
    ).keyId,
    authority.keyId,
  );
  assert.throws(
    () =>
      journey.verifyNativeProducerAttestation(
        { ...receipt, ownerId: "another-owner" },
        attestation,
        authority,
        nowMs,
      ),
    /native_producer_attestation_binding_mismatch/,
  );
  assert.throws(
    () =>
      journey.verifyNativeProducerAttestation(
        receipt,
        { ...unsigned, proof: "ed25519:" + "0".repeat(86) },
        authority,
        nowMs,
      ),
    /native_producer_attestation_authentication_failed/,
  );
});

test("public results never expose emails, raw prompts, secrets, paths, or binary evidence", () => {
  const evidence = validObservation();
  evidence.accessToken = "synthetic-access-secret-never-export";
  evidence.rawPrompt = "private synthetic conversation that must not appear";
  const summary = journey.buildPublicSummary({
    result: journey.evaluateCapabilityJourney(evidence, {
      candidateMode: "strict",
    }),
    observation: evidence,
    qaRunId: "synthetic-run-019",
  });
  const rendered = JSON.stringify(summary);
  for (const forbidden of [
    evidence.ownerEmail,
    evidence.accessToken,
    evidence.rawPrompt,
    "synthetic grouped document",
  ])
    assert.equal(rendered.includes(forbidden), false, forbidden);
});

test("synthetic cleanup never deletes baseline or cross-owner records and proves zero residue", async () => {
  const removed = [];
  const fixture = {
    ownerId: "synthetic-owner-019",
    created: [
      {
        collection: "messages",
        id: "message-new",
        ownerField: "user",
        ownerValue: "synthetic-owner-019",
      },
      {
        collection: "conversations",
        id: "conversation-new",
        ownerField: "user",
        ownerValue: "synthetic-owner-019",
      },
    ],
    baselineIds: new Set(["message-original"]),
  };
  const database = {
    collection(name) {
      return {
        async deleteOne(filter) {
          removed.push({ name, filter });
          return { acknowledged: true, deletedCount: 1 };
        },
        async countDocuments() {
          return 0;
        },
      };
    },
  };
  const result = await journey.cleanupSyntheticResidue(database, fixture);
  assert.equal(result.zeroResidue, true);
  assert.equal(removed.length, 2);
  assert.ok(removed.every((row) => row.filter.user === "synthetic-owner-019"));
  fixture.created.push({
    collection: "messages",
    id: "other-owner",
    ownerField: "user",
    ownerValue: "another-owner",
  });
  await assert.rejects(
    () => journey.cleanupSyntheticResidue(database, fixture),
    /synthetic_cleanup_owner_mismatch/,
  );
});

test("synthetic Voice children are removed only for an owned newly created call", async () => {
  const removed = [];
  const database = {
    collection(name) {
      return {
        async deleteOne(filter) {
          removed.push({ name, filter });
          return { acknowledged: true, deletedCount: 1 };
        },
        async countDocuments() {
          return 0;
        },
      };
    },
  };
  const fixture = {
    ownerId: "synthetic-owner-019",
    ownedCallSessionIds: new Set(["synthetic-call-019"]),
    baselineIds: new Set(),
    created: [
      {
        collection: "viventiumvoicespeakersegments",
        id: "synthetic-segment-019",
        ownerField: "callSessionId",
        ownerValue: "synthetic-call-019",
        boundOwnerId: "synthetic-owner-019",
      },
    ],
  };
  const result = await journey.cleanupSyntheticResidue(database, fixture);
  assert.equal(result.zeroResidue, true);
  assert.deepEqual(removed[0].filter, {
    _id: "synthetic-segment-019",
    callSessionId: "synthetic-call-019",
  });

  fixture.created[0].ownerValue = "different-owner-call";
  await assert.rejects(
    () => journey.cleanupSyntheticResidue(database, fixture),
    /synthetic_cleanup_owner_mismatch/,
  );
  fixture.created[0].ownerValue = "synthetic-call-019";
  fixture.created[0].boundOwnerId = "different-owner";
  await assert.rejects(
    () => journey.cleanupSyntheticResidue(database, fixture),
    /synthetic_cleanup_owner_mismatch/,
  );
});

test("missing real capability collectors fail before any installed connection", () => {
  const observers = Object.fromEntries(
    ["search", "vector", "storage", "scheduler", "glasshive"].map((name) => [
      name,
      {
        async capture() {},
        async removeAndVerify() {},
        async verify() {},
      },
    ]),
  );
  assert.throws(
    () =>
      new journey.InstalledCapabilityDriver({
        args: { allowRestart: false },
        scenario: { owner: { ownerId: "synthetic-owner-019" } },
        injection: { residueObservers: observers, collectors: {} },
      }),
    /installed_startAudibleCall_producer_unavailable/,
  );
});

test("cleanup remains mandatory after execution, provider, or browser failure", async () => {
  let cleaned = false;
  const driver = {
    async start() {
      throw journey.blockedError("authorized_connected_account_unavailable");
    },
    async cleanup() {
      cleaned = true;
      return { zeroResidue: true };
    },
  };
  const result = await journey.executeCapabilityJourney(driver, {
    candidateMode: "strict",
  });
  assert.equal(result.status, "BLOCKED");
  assert.equal(result.blocker, "authorized_connected_account_unavailable");
  assert.equal(cleaned, true);
});

test("cleanup failure overrides an otherwise successful journey", async () => {
  let discarded = false;
  const driver = {
    async start() {
      return validObservation();
    },
    async cleanup() {
      throw journey.blockedError("synthetic_cleanup_residue_detected");
    },
    async discardSemanticArtifacts(observation) {
      discarded = true;
      delete observation.semanticVerifier;
    },
  };
  const result = await journey.executeCapabilityJourney(driver, {
    candidateMode: "strict",
  });
  assert.equal(result.status, "BLOCKED");
  assert.equal(result.blocker, "synthetic_cleanup_residue_detected");
  assert.equal(result.receiptEligible, false);
  assert.equal(result.observation?.semanticVerifier, undefined);
  assert.equal(discarded, true);
});

test("semantic verification and PASS happen only after complete cleanup", async () => {
  const order = [];
  const observation = validObservation();
  delete observation.semanticVerifier;
  const driver = {
    async start() {
      order.push("start");
      return observation;
    },
    async cleanup() {
      order.push("cleanup");
      return { zeroResidue: true };
    },
    async finalizeAfterCleanup(value, cleanup) {
      order.push("finalize");
      assert.equal(cleanup.zeroResidue, true);
      value.semanticVerifier = {
        verified: true,
        caseId: "PWK-UC-019",
        candidateDigest: value.candidate.candidateDigest,
        artifactDigest: value.candidate.artifactDigest,
        surface: "voice",
      };
      return value;
    },
  };
  const result = await journey.executeCapabilityJourney(driver, {
    candidateMode: "strict",
  });
  assert.deepEqual(order, ["start", "cleanup", "finalize"]);
  assert.equal(result.status, "PASS");
  assert.equal(result.observation.cleanup.zeroResidue, true);
});

test("a stale semantic PASS created before cleanup fails closed", async () => {
  let discarded = false;
  const driver = {
    async start() {
      return validObservation();
    },
    async cleanup() {
      return { zeroResidue: true };
    },
    async finalizeAfterCleanup() {
      throw new Error("must not finalize a stale receipt");
    },
    async discardSemanticArtifacts(observation) {
      discarded = true;
      delete observation.semanticVerifier;
    },
  };
  const result = await journey.executeCapabilityJourney(driver, {
    candidateMode: "strict",
  });
  assert.equal(result.status, "BLOCKED");
  assert.equal(result.blocker, "semantic_receipt_created_before_cleanup");
  assert.equal(result.receiptEligible, false);
  assert.equal(result.observation?.semanticVerifier, undefined);
  assert.equal(discarded, true);
});

test("production launch injection is parent-signed and pins both native producers", () => {
  const ownerId = "synthetic-owner-019";
  const qaRunId = "pwk-uc-019-synthetic-run";
  const identity = {
    candidateDigest: sha256("candidate"),
    artifactDigest: sha256("installed-artifact"),
  };
  const core = nativeProducerAuthority("core.native_receipt");
  const glasshive = nativeProducerAuthority(
    "glasshive.native_provider_receipt",
  );
  const nowMs = Date.now();
  const unsigned = {
    contractVersion: 1,
    caseId: "PWK-UC-019",
    ownerRefHash: sha256(ownerId),
    qaRunRefHash: sha256(qaRunId),
    candidateDigest: identity.candidateDigest,
    artifactDigest: identity.artifactDigest,
    desktopAuthorityKeyId: BRIDGE_AUTHORITY.keyId,
    desktopSessionRefHash: sha256(BRIDGE_AUTHORITY.sessionRef),
    nativeProducerKeyIds: {
      "core.native_receipt": core.authority.keyId,
      "glasshive.native_provider_receipt": glasshive.authority.keyId,
    },
    issuedAtMs: nowMs - 1000,
    expiresAtMs: nowMs + 60000,
  };
  const injection = {
    launchGrant: {
      ...unsigned,
      proof: signExternalDesktopProof(unsigned),
    },
    nativeProducerAuthorities: {
      "core.native_receipt": core.authority,
      "glasshive.native_provider_receipt": glasshive.authority,
    },
  };
  const context = {
    args: { qaRunId },
    scenario: { owner: { ownerId } },
    identity,
    desktopAuthority: BRIDGE_AUTHORITY,
    nowMs,
  };

  assert.equal(
    journey.assertParentLaunchInjection(injection, context)
      .nativeProducerAuthorities["core.native_receipt"].keyId,
    core.authority.keyId,
  );
  assert.throws(
    () => journey.assertParentLaunchInjection({}, context),
    /installed_parent_launch_injection_owner_unavailable/,
  );
  injection.launchGrant.ownerRefHash = sha256("another-owner");
  assert.throws(
    () => journey.assertParentLaunchInjection(injection, context),
    /installed_parent_launch_injection_authentication_failed/,
  );
});

test("live CLI without the external parent owner returns typed BLOCKED before filesystem access", async (t) => {
  const root = temporaryRoot(t);
  const outputDir = path.join(root, "must-not-exist");
  const result = await journey.runInstalledJourney(
    [
      "--live",
      `--scenario=${path.join(root, "unread-scenario.json")}`,
      `--output=${outputDir}`,
    ],
    safeEnvironment(),
    {},
  );
  assert.equal(result.status, "BLOCKED");
  assert.equal(
    result.blocker,
    "installed_parent_launch_injection_owner_unavailable",
  );
  assert.equal(result.receiptEligible, false);
  assert.equal(fs.existsSync(outputDir), false);
});

test("runner imports shared secure auth helpers without invented provider or timing constraints", () => {
  const source = fs.readFileSync(RUNNER, "utf8");
  for (const required of [
    "run_installed_parallel_work_journey.cjs",
    "createEphemeralBrowserSession",
    "assertEphemeralSessionSafety",
    "@oai/sky",
    "headless: false",
    "installed_journey_qa.py",
    "readOnly: true",
    "PRE-GATE / NOT READY",
  ])
    assert.equal(source.includes(required), true, required);
  for (const forbidden of [
    "at least 20 seconds",
    "both with the light resource class",
    "VIVENTIUM_QA_PASSWORD",
    "localStorage.setItem",
    "recentChat",
    "conversationHistory",
    "Gemini",
  ])
    assert.equal(source.includes(forbidden), false, forbidden);
});
