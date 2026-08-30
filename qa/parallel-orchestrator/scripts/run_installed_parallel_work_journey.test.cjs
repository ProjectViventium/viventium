#!/usr/bin/env node
"use strict";

const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const { DatabaseSync } = require("node:sqlite");
const test = require("node:test");

const journey = require("./run_installed_parallel_work_journey.cjs");
const REPO_ROOT = path.resolve(__dirname, "../../..");
const BASE_TIME = Date.parse("2026-08-25T12:00:00.000Z");

function digest(value) {
  return crypto.createHash("sha256").update(value).digest("hex");
}

function stableJson(value) {
  if (Array.isArray(value)) return `[${value.map(stableJson).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${stableJson(value[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

function prefixedDigest(value) {
  return `sha256:${digest(value)}`;
}

function traceFixture(mutateDefinitions = null) {
  const ownerId = "qa-owner";
  const originRef = "origin_alpha";
  const workRef = "work_alpha";
  const runRef = "run_alpha";
  const ownerScopeHash = prefixedDigest(`owner\0${ownerId}`);
  const originRefHash = prefixedDigest(`origin\0${originRef}`);
  const identity = {
    workRefHash: prefixedDigest(`work\0${workRef}`),
    runRefHash: prefixedDigest(`run\0${runRef}`),
  };
  const producer = {
    ...identity,
    attemptNumber: 1,
    producerTraceContractVersion: 2,
  };
  const callbackRef = `callback_sha256:${digest("callback-alpha")}`;
  const followUpMessageId = "follow-up-alpha";
  const callbackFacts = {
    ...identity,
    callbackRefHash: prefixedDigest(`callback\0${callbackRef}`),
    callbackEvent: "run.completed",
    state: "completed",
    terminal: true,
    attemptNumber: 1,
  };
  const definitions = [
    { stage: "source.bound", facts: {} },
    {
      stage: "prompt.layers.verified",
      facts: {
        ...producer,
        promptProducerScope: "glasshive.worker_prompt_registry",
      },
    },
    { stage: "work.admitted", facts: producer },
    { stage: "runtime.invoked", facts: producer },
    {
      stage: "provider.request.forwarded",
      facts: {
        ...identity,
        providerStatus: "completed",
        providerRequestRefHash: prefixedDigest("provider-request"),
      },
    },
    { stage: "work.completed", facts: producer },
    { stage: "callback.accepted", facts: callbackFacts },
    {
      stage: "callback.delivery.sent",
      facts: {
        ...callbackFacts,
        deliveryRefHash: prefixedDigest(
          `delivery\0main-web:${followUpMessageId}`,
        ),
        surface: "web",
        deliveryState: "sent",
      },
    },
  ];
  if (typeof mutateDefinitions === "function") mutateDefinitions(definitions);
  let previousEventHash = `sha256:${"0".repeat(64)}`;
  const rows = definitions.map(({ stage, facts }, index) => {
    const contentHash = prefixedDigest(
      stableJson({ schemaVersion: 1, stage, facts }),
    );
    const row = {
      schemaVersion: 1,
      ownerScopeHash,
      originRefHash,
      sequence: index + 1,
      stage,
      at: new Date(BASE_TIME + index * 1000).toISOString(),
      facts,
      eventKeyHash: prefixedDigest(`event-${index}`),
      contentHash,
      previousEventHash,
    };
    row.eventHash = prefixedDigest(stableJson(row));
    previousEventHash = row.eventHash;
    return row;
  });
  return {
    rows,
    ownerId,
    originRef,
    workRef,
    runRef,
    callbackRef,
    attemptNumber: 1,
    followUpMessageId,
  };
}

function tempRoot(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "viventium-pwk-fixture-"));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  return root;
}

function liveArgs(outputDir, overrides = {}) {
  return {
    mode: "live",
    caseId: "PWK-UC-014",
    clientBase: "http://127.0.0.1:3190",
    apiBase: "http://127.0.0.1:3180",
    qaEmail: "qa@example.com",
    agentId: "agent_main_synthetic",
    outputDir,
    runtimeRoot: path.join(outputDir, "..", "runtime"),
    installedRoot: REPO_ROOT,
    identityPath: path.join(outputDir, "..", "identity.json"),
    ownerStatePath: path.join(outputDir, "..", "owner.json"),
    glassHiveDbPath: path.join(outputDir, "..", "glasshive.sqlite3"),
    timeoutMs: 120000,
    maxQuickLatencyMs: 10000,
    qaRunId: "PWK-UC-014-fixture-safe",
    candidateMode: "strict",
    ...overrides,
  };
}

function safeEnv(overrides = {}) {
  return {
    VIVENTIUM_QA_ALLOW_INSTALLED_PARALLEL_WORK: "1",
    VIVENTIUM_QA_ALLOW_LOCAL_JWT: "1",
    VIVENTIUM_QA_OWNER_EMAIL: "owner@example.com",
    VIVENTIUM_QA_EMAIL: "qa@example.com",
    JWT_SECRET: "synthetic-access-signing-secret-for-local-fixtures",
    JWT_REFRESH_SECRET: "synthetic-refresh-signing-secret-for-local-fixtures",
    ...overrides,
  };
}

function runtimeRows() {
  return [
    {
      ownerId: "qa-owner",
      originRef: "origin_alpha",
      workRef: "work_alpha",
      workerRef: "worker_alpha",
      runRef: "run_alpha",
      attemptRef: "attempt_alpha",
      leaseRef: "lease_alpha",
      executorRef: "executor_alpha",
      containerRef: "container_alpha",
      workspaceRef: "workspace_alpha",
      workspaceRoot: "/private/fixture/alpha",
      resourceClass: "light",
      executionMode: "docker",
      state: "completed",
      attemptState: "completed",
      runtimeInvokedAt: new Date(BASE_TIME).toISOString(),
      attemptRuntimeInvokedAt: new Date(BASE_TIME).toISOString(),
      finishedAt: new Date(BASE_TIME + 14000).toISOString(),
      attemptFinishedAt: new Date(BASE_TIME + 14000).toISOString(),
      leaseAcquiredAt: new Date(BASE_TIME - 1000).toISOString(),
      leaseReleasedAt: new Date(BASE_TIME + 13500).toISOString(),
      leaseConfirmedAt: new Date(BASE_TIME + 250).toISOString(),
      attemptNumber: 1,
    },
    {
      ownerId: "qa-owner",
      originRef: "origin_bravo",
      workRef: "work_bravo",
      workerRef: "worker_bravo",
      runRef: "run_bravo",
      attemptRef: "attempt_bravo",
      leaseRef: "lease_bravo",
      executorRef: "executor_bravo",
      containerRef: "container_bravo",
      workspaceRef: "workspace_bravo",
      workspaceRoot: "/private/fixture/bravo",
      resourceClass: "light",
      executionMode: "docker",
      state: "completed",
      attemptState: "completed",
      runtimeInvokedAt: new Date(BASE_TIME + 2000).toISOString(),
      attemptRuntimeInvokedAt: new Date(BASE_TIME + 2000).toISOString(),
      finishedAt: new Date(BASE_TIME + 16500).toISOString(),
      attemptFinishedAt: new Date(BASE_TIME + 16500).toISOString(),
      leaseAcquiredAt: new Date(BASE_TIME + 1000).toISOString(),
      leaseReleasedAt: new Date(BASE_TIME + 16000).toISOString(),
      leaseConfirmedAt: new Date(BASE_TIME + 2500).toISOString(),
      attemptNumber: 1,
    },
  ];
}

function validEvidence() {
  const rows = runtimeRows();
  const logicalTurnHash = digest("assistant-main-available");
  return {
    caseId: "PWK-UC-014",
    identity: {
      verified: true,
      candidateDigest: "a".repeat(64),
      artifactDigest: "b".repeat(64),
    },
    feelings: { userVisible: true, receiptVerified: true },
    routeFacts: { userVisible: true, receiptVerified: true },
    runtimeRows: rows,
    quickTurn: {
      submittedAtMs: BASE_TIME + 3000,
      visibleAtMs: BASE_TIME + 6000,
      finalReplyCount: 1,
      visible: true,
      exactAnswer: true,
      logicalTurnHash,
      timingTimeline: {
        complete: true,
        turnIdHash: logicalTurnHash.slice(0, 16),
        submittedAtMs: BASE_TIME + 3000,
        domVisibleAtMs: BASE_TIME + 6000,
        presentationCommittedAtMs: BASE_TIME + 5900,
        counts: {
          providerAttempts: 1,
          providerOutputs: 1,
          toolInvocations: 0,
        },
      },
    },
    telegram: {
      verified: true,
      nativeDesktop: true,
      revisionBeforeCommit: true,
      finalReplyCount: 1,
      delayMs: 280,
    },
    actions: [
      {
        ownerId: "qa-owner",
        workRef: "work_alpha",
        action: "steer",
        status: "accepted",
      },
    ],
    callbacks: rows.map((row, index) => {
      const callbackRef = `callback_${index}`;
      const followUpMessageId = `follow-up-${index}`;
      return {
        ownerId: row.ownerId,
        originRef: row.originRef,
        workRef: row.workRef,
        runRef: row.runRef,
        callbackRef,
        canonicalCallbackRef: `callback_sha256:${digest(callbackRef)}`,
        event: "run.completed",
        callbackAttemptNumber: row.attemptNumber,
        callbackAttempts: 1,
        callbackDeliveryGeneration: 1,
        callbackResultRevision: 1,
        callbackResultDigest: prefixedDigest(`result-${index}`),
        acceptedAt: new Date(BASE_TIME + 18000 + index).toISOString(),
        deliveredAt: null,
        callbackStatus: "http_accepted",
        missionEvidenceCount: 1,
        missionEvidenceOwnerId: row.ownerId,
        missionEvidenceOriginRef: row.originRef,
        missionEvidenceWorkRef: row.workRef,
        missionEvidenceRunRef: row.runRef,
        missionEvidenceEvent: "run.completed",
        missionEvidenceCallbackRef: `callback_sha256:${digest(callbackRef)}`,
        missionEvidenceAttemptNumber: row.attemptNumber,
        missionEvidenceState: "completed",
        missionEvidenceWorkState: "completed",
        missionEvidenceWorkTerminal: true,
        missionEvidenceErrorCode: "",
        followUpMessageId,
        webPresentationMessageId: followUpMessageId,
        webPresentedAt: new Date(BASE_TIME + 19000 + index).toISOString(),
        persistedMessageCount: 1,
        persistedMessageId: followUpMessageId,
        persistedMessageHasContent: true,
        visibleMessageCount: 1,
        visibleMessageId: followUpMessageId,
        visibleMessageHasContent: true,
      };
    }),
    artifacts: rows.map((row, index) => {
      const bytes = Buffer.from(
        `<!doctype html><html><body>synthetic ${index}</body></html>`,
      );
      return {
        ownerId: row.ownerId,
        workRef: row.workRef,
        runRef: row.runRef,
        bytes,
        byteSha256: digest(bytes),
        mediaType: "text/html",
        windowId: index + 101,
        headed: true,
        visible: true,
        screenshotSha256: digest(`capture-${index}`),
      };
    }),
    traces: rows.map((row) => ({
      workRef: row.workRef,
      ownerScoped: true,
      hashChainVerified: true,
      completionClaimable: true,
    })),
    maxQuickLatencyMs: 10000,
  };
}

function validQuickTimingEvents(
  assistantMessageId = "assistant-main-available",
) {
  const turnIdHash = digest(assistantMessageId).slice(0, 16);
  const turnStartedAtMs = BASE_TIME + 3100;
  const boundary = (stage, observedAtMs) => ({
    event: "viventium_text_turn_boundary",
    turnIdHash,
    stage,
    observedAtMs,
    fromTurnStartMs: observedAtMs - turnStartedAtMs,
  });
  const invocationId = `${turnIdHash}.1`;
  const providerAttemptIdHash = "c".repeat(16);
  return [
    boundary("controller_admission", BASE_TIME + 3100),
    boundary("concurrency_admitted", BASE_TIME + 3120),
    boundary("client_initialization_start", BASE_TIME + 3140),
    boundary("client_initialization_end", BASE_TIME + 3160),
    boundary("main_pipeline_start", BASE_TIME + 3170),
    {
      event: "viventium_text_main_provider_attempt_start",
      turnIdHash,
      invocationId,
      attemptIndex: 1,
      providerAttemptIdHash,
      observedAtMs: BASE_TIME + 3200,
      fromTurnStartMs: 100,
    },
    {
      event: "viventium_text_main_first_provider_output",
      turnIdHash,
      invocationId,
      attemptIndex: 1,
      providerAttemptIdHash,
      outputKind: "provider_token",
      observedAtMs: BASE_TIME + 5000,
      fromTurnStartMs: 1900,
      fromAttemptStartMs: 1800,
    },
    {
      event: "viventium_text_main_provider_attempt_end",
      turnIdHash,
      invocationId,
      attemptIndex: 1,
      providerAttemptIdHash,
      toolCallCount: 0,
      observedAtMs: BASE_TIME + 5500,
      fromTurnStartMs: 2400,
      fromAttemptStartMs: 2300,
    },
    boundary("main_pipeline_complete", BASE_TIME + 5600),
    boundary("assistant_durable", BASE_TIME + 5700),
    boundary("final_event_emitted", BASE_TIME + 5800),
    boundary("presentation_committed", BASE_TIME + 5900),
  ];
}

function coreLogLine(event) {
  return `[VIVENTIUM][TextTurnTiming] ${JSON.stringify(event)}\n`;
}

function ptyCoreLogLine(event) {
  return `\u001b[32m[VIVENTIUM][TextTurnTiming] ${JSON.stringify(event)}\u001b[39m\n`;
}

function writeQuickTimingLog(t, events, { beforeCapture = "" } = {}) {
  const root = tempRoot(t);
  const logPath = path.join(root, "core.log");
  fs.writeFileSync(logPath, beforeCapture, "utf8");
  const window = journey.captureCoreLogWindow(logPath);
  fs.appendFileSync(logPath, events.map(coreLogLine).join(""), "utf8");
  return window;
}

function restartProof(caseId) {
  return {
    caseId,
    candidateDigest: "a".repeat(64),
    restartState: "ready",
    serviceAckDigest: `sha256:${digest(`${caseId}-acknowledgement`)}`,
    requiredServices: ["librechat-core", "telegram-bot", "glasshive-runtime"],
    acknowledgedServices: [
      "librechat-core",
      "telegram-bot",
      "glasshive-runtime",
    ],
    missingServices: [],
    services: ["librechat-core", "telegram-bot", "glasshive-runtime"].map(
      (service) => ({
        service,
        beforeProcessRefHash: digest(`${caseId}-${service}-before`),
        afterProcessRefHash: digest(`${caseId}-${service}-after`),
        acknowledgementSha256: digest(`${caseId}-${service}-ack`),
      }),
    ),
  };
}

function consumedFaults(caseId) {
  return journey.CASE_FAULT_BOUNDARIES[caseId].map((boundary, index) => ({
    boundary,
    ownerId: "qa-owner",
    status: "consumed",
    effectCount: 1,
    consumedAt: new Date(BASE_TIME + 18000 + index).toISOString(),
    controlRef: `qac_sha256:${digest(`${caseId}-${boundary}`)}`,
  }));
}

test("PWK-UC-016 uses only the prepared exact fixture and includes both liveness boundaries", () => {
  assert.deepEqual(journey.CASE_FAULT_BOUNDARIES["PWK-UC-016"].slice(3, 5), [
    "provider_internal_retry_threshold",
    "declared_long_fresh_then_stale",
  ]);
  const source = fs.readFileSync(
    path.join(__dirname, "run_installed_parallel_work_journey.cjs"),
    "utf8",
  );
  const body = source
    .split("async runCapacityProviderRecoveryJourney()", 2)[1]
    .split("async runCallbackArtifactRecoveryJourney()", 1)[0];
  assert.equal(body.includes("submitParallelRequest("), false);
  assert.equal(body.includes("observeFaultAfterRealUserTurn("), false);
  assert.equal(body.includes("exactFixtureMission(fixture)"), true);
  assert.equal(body.includes("resumeExactFixtureLostResponse("), true);
  assert.equal(body.includes("provider_internal_retry_threshold"), true);
  assert.equal(body.includes("declared_long_fresh_then_stale"), true);
});

test("PWK-UC-015 asks for explicit durable background work before testing restart", () => {
  const source = fs.readFileSync(
    path.join(__dirname, "run_installed_parallel_work_journey.cjs"),
    "utf8",
  );
  const body = source
    .split("async runRestartContinuityJourney()", 2)[1]
    .split("async runCapacityProviderRecoveryJourney()", 1)[0];
  assert.match(
    body,
    /Please have a background Worker create a distinct HTML vitals card while you stay available here\./,
  );
  assert.match(
    body,
    /Please have a separate background Worker create an HTML ledger while you stay available here\./,
  );
  assert.equal(
    body.includes("const missionToken = sha256(args.qaRunId).slice(0, 16)"),
    true,
  );
  assert.equal(body.includes("for QA run ${missionToken}"), true);
  assert.equal(body.includes("as independent work"), false);
});

test("installed Worker-card control reveals Active work before exact card lookup", () => {
  const source = fs.readFileSync(
    path.join(__dirname, "run_installed_parallel_work_journey.cjs"),
    "utf8",
  );
  const body = source
    .split("async function exactOwnerWorkCard(row)", 2)[1]
    .split("async function submitVisibleUserTurn", 1)[0];

  assert.match(
    body,
    /getByRole\("button", \{\s*name: "Active work",\s*exact: true/,
  );
  assert.match(body, /getAttribute\("aria-expanded"\)/);
  assert.match(body, /await activeWorkControl\.click\(\)/);
  assert.ok(
    body.indexOf("await heading.waitFor") < body.indexOf("await cards.count"),
  );
});

function scenarioEvidence(caseId) {
  const base = validEvidence();
  base.caseId = caseId;
  const surfaces = { webVisible: true, telegramVisible: true };
  if (caseId === "PWK-UC-015") {
    base.scenario = {
      caseId,
      scenarioId: "restart-continuity",
      observed: true,
      restart: restartProof(caseId),
      before: {
        rows: runtimeRows().map((row) => ({ ...row, state: "running" })),
        actions: base.actions,
        terminalCallbackCount: 0,
      },
      after: { rows: runtimeRows(), actions: base.actions },
      turns: ["substantial-a", "substantial-b", "quick-c", "continuation"].map(
        (kind) => ({
          kind,
          userVisible: true,
          replyCount: 1,
        }),
      ),
      continuation: {
        workRef: base.runtimeRows[0].workRef,
        workCountBefore: 2,
        workCountAfter: 2,
        receiptVerified: true,
      },
      reopenedArtifactHashes: base.artifacts.map(
        (artifact) => artifact.byteSha256,
      ),
      surfaces,
    };
  }
  if (caseId === "PWK-UC-016") {
    const availableBytes = Math.round(4.3 * 1024 ** 3);
    const requiredBytes = 5 * 1024 ** 3;
    base.scenario = {
      caseId,
      scenarioId: "capacity-provider-recovery",
      observed: true,
      faults: consumedFaults(caseId),
      capacity: {
        measurement: {
          availableBytes,
          requiredBytes,
          shortageBytes: requiredBytes - availableBytes,
          nextRetryAt: new Date(BASE_TIME + 30000).toISOString(),
        },
        reservationAttempts: [
          {
            requestRef: "request-a",
            slotRef: "slot-one",
            outcome: "reserved",
            workRef: "work_alpha",
          },
          {
            requestRef: "request-b",
            slotRef: "slot-one",
            outcome: "rejected",
            workRef: null,
          },
        ],
        overflow: { outcome: "rejected", workRows: 0, runRows: 0 },
        disk: { state: "critical" },
      },
      provider: {
        missingAuthObserved: true,
        unavailableObserved: true,
        cooldownSkipped: true,
        primaryAttemptCountDuringCooldown: 0,
        fallbackInvoked: true,
        fallbackConfigured: true,
      },
      providerLiveness: {
        retryAttention: {
          internalRetryCount: 3,
          state: "needs_input",
          visibleLabel: "Needs attention",
          failureClass: "provider_progress_stalled",
          computeReleased: true,
          workRef: "work_alpha",
          runRef: "run_alpha",
          route: ["synthetic", "local", "synthetic"],
          sessionRefHash: digest("session-alpha"),
          workspaceRef: digest("workspace-alpha"),
        },
        resume: {
          operationRef: digest("resume-operation"),
          responseSha256: digest("resume-response"),
          replaySha256: digest("resume-response"),
          stableReplay: true,
          sameRun: true,
          sameRoute: true,
          sameSession: true,
          sameWorkspace: true,
        },
        declaredLong: {
          declared: true,
          freshProgressExtended: true,
          staleAttention: true,
          state: "needs_input",
          visibleLabel: "Needs attention",
          sameRun: true,
        },
      },
      recovery: {
        workRef: "work_alpha",
        sameWork: true,
        sameRun: true,
        finalState: "needs_input",
      },
      surfaces,
    };
    base.runtimeRows = [base.runtimeRows[0]];
  }
  if (caseId === "PWK-UC-017") {
    base.scenario = {
      caseId,
      scenarioId: "callback-artifact-recovery",
      observed: true,
      faults: consumedFaults(caseId),
      restart: restartProof(caseId),
      delivery: {
        timeouts: [
          { state: "claimed", terminalTransitions: 1 },
          { state: "admitted", terminalTransitions: 1 },
        ],
        transportInterrupted: true,
        staleRefreshApplied: false,
        expiredSenderDelivered: false,
        currentSenderDeliveryCount: 1,
        duplicatePresentations: 0,
      },
      artifactFailures: [
        { kind: "expired", userVisible: true },
        { kind: "unavailable", userVisible: true },
      ],
      recoveredArtifactSha256: base.artifacts[0].byteSha256,
      surfaces,
    };
  }
  if (caseId === "PWK-UC-018") {
    const bytes = Buffer.from(
      "<!doctype html><html><body>fixture<script>window.fixtureAttempt=1</script></body></html>",
    );
    base.artifacts[0] = {
      ...base.artifacts[0],
      bytes,
      byteSha256: digest(bytes),
    };
    const other = "qa-second-owner";
    const operations = [
      {
        actorOwnerId: "qa-owner",
        targetOwnerId: "qa-owner",
        operation: "list",
        outcome: "allowed",
        returnedWorkCount: 2,
      },
    ];
    for (const [actorOwnerId, targetOwnerId] of [
      ["qa-owner", other],
      [other, "qa-owner"],
    ]) {
      for (const operation of ["list", "inspect", "control", "callback"]) {
        operations.push({
          actorOwnerId,
          targetOwnerId,
          operation,
          outcome: "denied",
          returnedWorkCount: 0,
        });
      }
    }
    base.scenario = {
      caseId,
      scenarioId: "owner-artifact-isolation",
      observed: true,
      ownerMatrix: { ownerId: "qa-owner", otherOwnerId: other, operations },
      rejections: [
        "forged_callback",
        "cross_owner_callback",
        "altered_trace",
      ].map((attack) => ({
        attack,
        ownerId: "qa-owner",
        outcome: "denied",
        effectsCreated: 0,
      })),
      hostileArtifact: {
        bytes,
        sandboxed: true,
        hostAuthority: false,
        scriptExecuted: false,
        visible: true,
      },
      workerIsolation: {
        peerAccessDenied: true,
        hostAccessDenied: true,
        auditVerified: true,
        workers: base.runtimeRows.map((row) => ({
          contractVersion: 1,
          producerScope: "glasshive.worker_isolation",
          ownerRefHash: prefixedDigest(`owner\0${row.ownerId}`),
          workRefHash: prefixedDigest(`work\0${row.workRef}`),
          runRefHash: prefixedDigest(`run\0${row.runRef}`),
          workerRefHash: prefixedDigest(`worker\0${row.workerRef}`),
          attemptRefHash: prefixedDigest(`attempt\0${row.attemptRef}`),
          leaseRefHash: prefixedDigest(`lease\0${row.leaseRef}`),
          containerRefHash: prefixedDigest(`container\0${row.containerRef}`),
          workspaceRefHash: prefixedDigest(`workspace\0${row.workspaceRoot}`),
          homeRefHash: prefixedDigest(`home\0fixture-home-${row.workerRef}`),
          networkRefHash: prefixedDigest(
            `network\0fixture-network-${row.workerRef}`,
          ),
          pidNamespaceRefHash: prefixedDigest(
            `pid_namespace\0${row.containerRef}`,
          ),
          executionMode: "isolated_container",
          hostStateReadable: false,
          serviceEnvironmentReadable: false,
          dockerSocketReadable: false,
          ambientAuthority: false,
          peerAccessDenied: true,
          hostAccessDenied: true,
          peerProbes: base.runtimeRows
            .filter((peer) => peer.runRef !== row.runRef)
            .map((peer) => ({
              workRefHash: prefixedDigest(`work\0${peer.workRef}`),
              reachable: false,
            })),
        })),
      },
      publicSafety: {
        scannedArtifactSha256: digest(bytes),
        findingCount: 0,
        privateLeakCount: 0,
        hostAuthorityExecutionCount: 0,
      },
      surfaces,
    };
  }
  return base;
}

test("dry-run requires no account, browser, model, evidence directory, or live opt-in", () => {
  const parsed = journey.parseArgs(["--dry-run"], {});
  assert.equal(parsed.mode, "dry-run");
  assert.equal(parsed.caseId, "PWK-UC-014");
  const plan = journey.dryRunPlan(parsed);
  assert.equal(plan.status, "DRY_RUN");
  assert.equal(plan.sideEffects, false);
  assert.equal(plan.launchesBrowser, false);
  assert.equal(plan.invokesModels, false);
  assert.equal(plan.caseId, "PWK-UC-014");
  assert.ok(plan.requiredChecks.includes("overlapping-runtime-windows"));
  assert.ok(plan.requiredChecks.includes("source-revision-single-reply"));
});

test("CLI dry-run stays inert and prints only the public-safe plan", () => {
  const result = spawnSync(
    process.execPath,
    [
      path.join(__dirname, "run_installed_parallel_work_journey.cjs"),
      "--dry-run",
    ],
    { encoding: "utf8", env: { PATH: process.env.PATH } },
  );
  assert.equal(result.status, 0, result.stderr);
  const output = JSON.parse(result.stdout);
  assert.equal(output.status, "DRY_RUN");
  assert.equal(output.sideEffects, false);
});

test("live argument parsing requires every explicit installed-runtime boundary", (t) => {
  const root = tempRoot(t);
  const argv = [
    "--live",
    "--client=http://127.0.0.1:3190",
    "--api=http://127.0.0.1:3180",
    "--qa-email=qa@example.com",
    "--agent=agent_main_synthetic",
    `--output=${path.join(root, "evidence")}`,
    `--runtime-root=${path.join(root, "runtime")}`,
    `--installed-root=${REPO_ROOT}`,
    `--identity=${path.join(root, "identity.json")}`,
    `--owner-state=${path.join(root, "owner.json")}`,
    `--glasshive-db=${path.join(root, "glasshive.sqlite3")}`,
  ];
  const parsed = journey.parseArgs(argv, safeEnv());
  assert.equal(parsed.mode, "live");
  assert.equal(parsed.qaEmail, "qa@example.com");
  assert.equal(parsed.headless, false);
  assert.equal(parsed.candidateMode, "strict");
  assert.match(parsed.qaRunId, /^PWK-UC-014-[A-Za-z0-9-]+$/);
  for (const key of [
    "client",
    "api",
    "qa-email",
    "agent",
    "output",
    "runtime-root",
    "installed-root",
    "identity",
    "owner-state",
    "glasshive-db",
  ]) {
    assert.throws(
      () =>
        journey.parseArgs(
          argv.filter((item) => !item.startsWith(`--${key}=`)),
          safeEnv(),
        ),
      /missing_required_argument/,
    );
  }
  const diagnostic = journey.parseArgs(
    [...argv, "--candidate-mode=diagnostic"],
    safeEnv(),
  );
  assert.equal(diagnostic.candidateMode, "diagnostic");
  assert.throws(
    () =>
      journey.parseArgs([...argv, "--candidate-mode=permissive"], safeEnv()),
    /candidate_mode_invalid/,
  );
  assert.throws(
    () =>
      journey.parseArgs(
        [...argv, "--receipt-manifest=fixture.json"],
        safeEnv(),
      ),
    /unknown_argument/,
  );
});

test("live mode refuses missing opt-in, production, personal accounts, and non-synthetic domains", (t) => {
  const root = tempRoot(t);
  const args = liveArgs(path.join(root, "evidence"));
  assert.throws(
    () =>
      journey.assertLiveSafety(
        args,
        safeEnv({ VIVENTIUM_QA_ALLOW_INSTALLED_PARALLEL_WORK: "" }),
      ),
    /installed_parallel_work_requires_explicit_opt_in/,
  );
  assert.throws(
    () => journey.assertLiveSafety(args, safeEnv({ CI: "true" })),
    /local_installed_qa_only/,
  );
  assert.throws(
    () => journey.assertLiveSafety(args, safeEnv({ NODE_ENV: "production" })),
    /local_installed_qa_only/,
  );
  assert.throws(
    () =>
      journey.assertLiveSafety(args, safeEnv({ VIVENTIUM_QA_OWNER_EMAIL: "" })),
    /owner_identity_guard_required/,
  );
  assert.throws(
    () =>
      journey.assertLiveSafety(
        { ...args, qaEmail: "owner@example.com" },
        safeEnv(),
      ),
    /personal_owner_account_refused/,
  );
  assert.throws(
    () =>
      journey.assertLiveSafety(
        { ...args, qaEmail: ["person", "not-synthetic.invalid"].join("@") },
        safeEnv(),
      ),
    /synthetic_qa_account_required/,
  );
  assert.throws(
    () =>
      journey.assertLiveSafety(
        args,
        safeEnv({ VIVENTIUM_QA_ALLOW_LOCAL_JWT: "" }),
      ),
    /ephemeral_browser_session_requires_explicit_opt_in/,
  );
  assert.throws(
    () => journey.assertLiveSafety(args, safeEnv({ JWT_REFRESH_SECRET: "" })),
    /ephemeral_browser_session_signing_secrets_required/,
  );
  assert.throws(
    () =>
      journey.assertLiveSafety(
        args,
        safeEnv({ VIVENTIUM_QA_EMAIL: "wrong@example.com" }),
      ),
    /configured_synthetic_qa_account_mismatch/,
  );
});

test("selected account must exactly match the explicit non-admin synthetic account", (t) => {
  const args = liveArgs(path.join(tempRoot(t), "evidence"));
  assert.doesNotThrow(() =>
    journey.assertSelectedQaAccount(args, safeEnv(), {
      _id: "qa-owner",
      email: "qa@example.com",
      role: "USER",
    }),
  );
  assert.throws(
    () =>
      journey.assertSelectedQaAccount(args, safeEnv(), {
        _id: "qa-owner",
        email: "qa@example.com",
        role: "ADMIN",
      }),
    /admin_account_refused/,
  );
  assert.throws(
    () =>
      journey.assertSelectedQaAccount(args, safeEnv(), {
        _id: "qa-owner",
        email: "other@example.com",
        role: "USER",
      }),
    /selected_qa_account_mismatch/,
  );
  assert.throws(
    () =>
      journey.assertSelectedQaAccount(args, safeEnv(), {
        _id: "qa-owner",
        email: "owner@example.com",
        role: "USER",
      }),
    /personal_owner_account_refused/,
  );
});

test("all user and artifact URLs must be loopback with no embedded credentials", (t) => {
  const args = liveArgs(path.join(tempRoot(t), "evidence"));
  for (const remote of [
    "https://example.com",
    "http://127.0.0.1.example.com",
    "file:///tmp/item",
    "http://user@127.0.0.1:3190",
  ]) {
    assert.throws(
      () =>
        journey.assertLiveSafety({ ...args, clientBase: remote }, safeEnv()),
      /loopback|credentials/,
    );
  }
  assert.doesNotThrow(() =>
    journey.assertLoopbackUrl("http://[::1]:3190", "client"),
  );
});

test("evidence must stay outside the repository, refuse symlinks, and be owner-only", (t) => {
  const root = tempRoot(t);
  assert.throws(
    () =>
      journey.preparePrivateEvidenceRoot(REPO_ROOT, { repoRoot: REPO_ROOT }),
    /private_evidence_must_stay_outside_repository/,
  );
  const evidence = path.join(root, "private-evidence");
  journey.preparePrivateEvidenceRoot(evidence, { repoRoot: REPO_ROOT });
  assert.equal(fs.statSync(evidence).mode & 0o777, 0o700);
  const written = journey.writePrivateEvidence(evidence, "one.json", {
    private: true,
  });
  assert.equal(fs.statSync(written.path).mode & 0o777, 0o600);
  assert.equal(written.sha256, digest(fs.readFileSync(written.path)));
  assert.throws(
    () => journey.writePrivateEvidence(evidence, "../escaped.json", {}),
    /private_evidence_path_invalid/,
  );
  const linked = path.join(root, "linked-evidence");
  fs.symlinkSync(evidence, linked);
  assert.throws(
    () => journey.preparePrivateEvidenceRoot(linked, { repoRoot: REPO_ROOT }),
    /private_evidence_symlink_refused/,
  );
});

test("candidate identity requires every existing source, pin, prebuilt, and active-runtime check", () => {
  const measured = {
    candidateDigest: "a".repeat(64),
    artifactDigest: "b".repeat(64),
    checks: [
      { id: "SOURCE-IDENTITY", status: "PASS" },
      { id: "NESTED-PINS", status: "PASS" },
      { id: "PREBUILT-IDENTITY", status: "PASS" },
      { id: "INSTALLED-ARTIFACT", status: "PASS" },
    ],
  };
  assert.equal(journey.assertMeasuredCandidate(measured).verified, true);
  for (const id of measured.checks.map((check) => check.id)) {
    const broken = structuredClone(measured);
    broken.checks.find((check) => check.id === id).status = "FAIL";
    assert.throws(
      () => journey.assertMeasuredCandidate(broken),
      /installed_candidate_identity_unproven/,
    );
  }
  assert.throws(
    () =>
      journey.assertMeasuredCandidate({
        ...measured,
        candidateDigest: "forged",
      }),
    /installed_candidate_identity_unproven/,
  );
});

test("diagnostic candidate mode needs a second explicit opt-in and can never loosen strict identity", (t) => {
  const args = liveArgs(path.join(tempRoot(t), "evidence"), {
    candidateMode: "diagnostic",
  });
  assert.throws(
    () => journey.assertLiveSafety(args, safeEnv()),
    /diagnostic_candidate_requires_explicit_opt_in/,
  );
  assert.doesNotThrow(() =>
    journey.assertLiveSafety(
      args,
      safeEnv({ VIVENTIUM_QA_ALLOW_DIAGNOSTIC_CANDIDATE: "1" }),
    ),
  );
  const dirty = {
    candidateDigest: "c".repeat(64),
    artifactDigest: "d".repeat(64),
    checks: [
      {
        id: "SOURCE-IDENTITY",
        status: "FAIL",
        reason: "source_identity_mismatch",
      },
      { id: "NESTED-PINS", status: "FAIL", reason: "nested_pin_mismatch" },
      { id: "PREBUILT-IDENTITY", status: "PASS", reason: "" },
      {
        id: "INSTALLED-ARTIFACT",
        status: "FAIL",
        reason: "installed_artifact_mismatch",
      },
    ],
    runtimeBinding: {
      active: true,
      ownerRootMatches: true,
      runtimeRootMatches: true,
      processIdentitySha256: "e".repeat(64),
      ownerBindingSha256: "f".repeat(64),
    },
    measuredIdentity: {
      source: {
        revision: "a".repeat(40),
        clean: false,
        worktreeHash: "1".repeat(64),
        componentsLockSha256: "2".repeat(64),
      },
      nestedComponents: [
        {
          name: "component-safe",
          pin: "b".repeat(40),
          revision: "c".repeat(40),
          clean: false,
          worktreeHash: "3".repeat(64),
        },
      ],
      prebuiltHelper: {
        sourceMeasuredSha256: "4".repeat(64),
        binaryMeasuredSha256: "5".repeat(64),
      },
      installed: {
        rootRevision: "d".repeat(40),
        runningServiceSha256: "6".repeat(64),
        frontendBuildSha256: "7".repeat(64),
        apiBuildSha256: "8".repeat(64),
      },
    },
  };
  assert.throws(
    () => journey.assertMeasuredCandidate(dirty),
    /installed_candidate_identity_unproven/,
  );
  const accepted = journey.assertDiagnosticCandidate(dirty);
  assert.equal(accepted.verified, true);
  assert.equal(accepted.candidateMode, "diagnostic");
  assert.equal(accepted.releaseCandidateVerified, false);
  assert.equal(accepted.acceptanceEligible, false);
  assert.equal(accepted.runtimeBinding.active, true);
  assert.deepEqual(
    accepted.identityFailures.map((failure) => failure.id),
    ["SOURCE-IDENTITY", "NESTED-PINS", "INSTALLED-ARTIFACT"],
  );
  for (const key of ["active", "ownerRootMatches", "runtimeRootMatches"]) {
    const unbound = structuredClone(dirty);
    unbound.runtimeBinding[key] = false;
    assert.throws(
      () => journey.assertDiagnosticCandidate(unbound),
      /diagnostic_active_runtime_identity_unproven/,
    );
  }
  const missingProcess = structuredClone(dirty);
  missingProcess.runtimeBinding.processIdentitySha256 = "not-a-process-proof";
  assert.throws(
    () => journey.assertDiagnosticCandidate(missingProcess),
    /diagnostic_active_runtime_identity_unproven/,
  );
});

test("a complete diagnostic journey remains PARTIAL, exposes every identity failure, and cannot issue a receipt", () => {
  const evidence = validEvidence();
  evidence.identity = {
    ...evidence.identity,
    candidateMode: "diagnostic",
    releaseCandidateVerified: false,
    acceptanceEligible: false,
    runtimeBinding: {
      active: true,
      ownerBindingSha256: "c".repeat(64),
      processIdentitySha256: "d".repeat(64),
    },
    identityFailures: [
      {
        id: "SOURCE-IDENTITY",
        status: "FAIL",
        reason: "source_identity_mismatch",
      },
      { id: "NESTED-PINS", status: "FAIL", reason: "nested_pin_mismatch" },
    ],
    measuredIdentity: {
      source: { worktreeHash: "e".repeat(64) },
      nestedComponents: [{ worktreeHash: "f".repeat(64) }],
      prebuiltHelper: { binaryMeasuredSha256: "1".repeat(64) },
      installed: { runningServiceSha256: "2".repeat(64) },
    },
  };
  const evaluated = journey.evaluateJourneyEvidence(evidence, "qa-owner");
  assert.equal(evaluated.status, "PARTIAL");
  assert.equal(evaluated.pass, false);
  assert.equal(evaluated.diagnosticPass, true);
  assert.equal(evaluated.receiptEligible, false);
  assert.ok(
    evaluated.blockers.includes(
      "diagnostic_candidate_cannot_close_release_gate",
    ),
  );
  assert.ok(evaluated.blockers.includes("source_identity_mismatch"));
  assert.ok(evaluated.blockers.includes("nested_pin_mismatch"));
  const summary = journey.buildPublicSummary({
    result: evaluated,
    evidence,
    qaRunId: "PWK-UC-014-fixture-safe",
  });
  assert.equal(summary.candidateMode, "diagnostic");
  assert.equal(summary.diagnosticPass, true);
  assert.equal(summary.releaseReady, false);
  assert.equal(summary.receiptEligible, false);
  assert.equal(summary.releaseLabel, "PRE-GATE / NOT READY");
  assert.equal(summary.identityFailures.length, 2);
  assert.equal(summary.measuredSourceWorktreeSha256, "e".repeat(64));
  assert.equal(summary.measuredRunningServiceSha256, "2".repeat(64));
  assert.equal("attestation" in summary, false);
  assert.equal("receiptManifest" in summary, false);
});

test("actual overlap derives only from invoked, leased, distinct isolated runtimes", () => {
  const result = journey.assessRuntimeOverlap(runtimeRows(), "qa-owner");
  assert.equal(result.pass, true);
  assert.equal(result.overlapMs, 11500);
  assert.equal(result.workCount, 2);
});

for (const [name, change] of [
  [
    "UI running without invocation",
    (rows) => {
      rows[0].runtimeInvokedAt = null;
    },
  ],
  [
    "attempt missing invocation",
    (rows) => {
      rows[0].attemptRuntimeInvokedAt = null;
    },
  ],
  [
    "attempt and run invocation mismatch",
    (rows) => {
      rows[0].attemptRuntimeInvokedAt = new Date(BASE_TIME + 10).toISOString();
    },
  ],
  [
    "missing lease",
    (rows) => {
      rows[0].leaseRef = "";
    },
  ],
  [
    "unconfirmed executor",
    (rows) => {
      rows[0].leaseConfirmedAt = null;
    },
  ],
  [
    "startup confirmation before dispatch",
    (rows) => {
      rows[0].leaseConfirmedAt = new Date(BASE_TIME - 1).toISOString();
    },
  ],
  [
    "lease release before startup confirmation",
    (rows) => {
      rows[0].leaseReleasedAt = new Date(BASE_TIME + 100).toISOString();
    },
  ],
  [
    "startup confirmation after runtime end",
    (rows) => {
      rows[0].leaseConfirmedAt = new Date(BASE_TIME + 15000).toISOString();
    },
  ],
  [
    "lease release after runtime end",
    (rows) => {
      rows[0].leaseReleasedAt = new Date(BASE_TIME + 15000).toISOString();
    },
  ],
  [
    "terminal runtime without lease release",
    (rows) => {
      rows[0].leaseReleasedAt = null;
    },
  ],
  [
    "terminal runtime with invalid lease release",
    (rows) => {
      rows[0].leaseReleasedAt = "invalid";
    },
  ],
  [
    "reused worker",
    (rows) => {
      rows[1].workerRef = rows[0].workerRef;
    },
  ],
  [
    "reused workspace",
    (rows) => {
      rows[1].workspaceRef = rows[0].workspaceRef;
    },
  ],
  [
    "missing scheduler executor",
    (rows) => {
      rows[0].executorRef = "";
    },
  ],
  [
    "reused container",
    (rows) => {
      rows[1].containerRef = rows[0].containerRef;
    },
  ],
  [
    "unisolated host worker",
    (rows) => {
      rows[0].executionMode = "host";
    },
  ],
  [
    "wrong account",
    (rows) => {
      rows[0].ownerId = "another-owner";
    },
  ],
  [
    "serialized runtime",
    (rows) => {
      rows[1].runtimeInvokedAt = rows[0].finishedAt;
      rows[1].attemptRuntimeInvokedAt = rows[0].finishedAt;
    },
  ],
]) {
  test(`overlap rejects ${name}`, () => {
    const rows = runtimeRows();
    change(rows);
    const result = journey.assessRuntimeOverlap(rows, "qa-owner");
    assert.equal(result.pass, false);
    assert.ok(result.reason);
  });
}

test("overlap rejects execution serialized inside the release-to-terminal gap", () => {
  const rows = runtimeRows();
  rows[0].leaseReleasedAt = new Date(BASE_TIME + 1000).toISOString();
  rows[0].finishedAt = new Date(BASE_TIME + 3000).toISOString();
  rows[0].attemptFinishedAt = rows[0].finishedAt;
  rows[1].runtimeInvokedAt = new Date(BASE_TIME + 2000).toISOString();
  rows[1].attemptRuntimeInvokedAt = rows[1].runtimeInvokedAt;
  rows[1].leaseAcquiredAt = new Date(BASE_TIME + 1500).toISOString();
  rows[1].leaseConfirmedAt = new Date(BASE_TIME + 2250).toISOString();
  rows[1].leaseReleasedAt = new Date(BASE_TIME + 4000).toISOString();
  rows[1].finishedAt = new Date(BASE_TIME + 5000).toISOString();
  rows[1].attemptFinishedAt = rows[1].finishedAt;

  assert.equal(journey.assessRuntimeOverlap(rows, "qa-owner").pass, false);
});

test("live overlap does not require a lease release before either runtime ends", () => {
  const rows = runtimeRows();
  for (const row of rows) {
    row.state = "running";
    row.attemptState = "running";
    row.finishedAt = null;
    row.attemptFinishedAt = null;
    row.leaseReleasedAt = null;
  }

  assert.equal(journey.assessRuntimeOverlap(rows, "qa-owner").pass, true);
});

test("real runtime overlap accepts the naturally selected resource class", () => {
  const rows = runtimeRows();
  rows[0].resourceClass = "standard";
  rows[1].resourceClass = "large";
  assert.equal(journey.assessRuntimeOverlap(rows, "qa-owner").pass, true);
});

test("one real GlassHive scheduler can own two genuinely overlapping isolated workers", () => {
  const rows = runtimeRows();
  rows[1].executorRef = rows[0].executorRef;
  assert.equal(journey.assessRuntimeOverlap(rows, "qa-owner").pass, true);
});

test("quick Main answer comparison is exact after trimming", () => {
  assert.equal(journey.isExactQuickMainAnswer("MAIN_AVAILABLE"), true);
  assert.equal(journey.isExactQuickMainAnswer("  MAIN_AVAILABLE\n"), true);
  assert.equal(journey.isExactQuickMainAnswer("prefix MAIN_AVAILABLE"), false);
  assert.equal(journey.isExactQuickMainAnswer("MAIN_AVAILABLE suffix"), false);
  assert.equal(journey.isExactQuickMainAnswer(null), false);
});

test("one complete ordered privacy-safe quick-turn timing timeline is accepted", (t) => {
  const assistantMessageId = "assistant-main-available";
  const timeline = journey.readQuickTurnTimingTimeline(
    writeQuickTimingLog(t, validQuickTimingEvents(assistantMessageId)),
    assistantMessageId,
    {
      submittedAtMs: BASE_TIME + 3000,
      visibleAtMs: BASE_TIME + 6000,
    },
  );

  assert.equal(timeline.complete, true);
  assert.equal(timeline.turnIdHash, digest(assistantMessageId).slice(0, 16));
  assert.deepEqual(timeline.counts, {
    providerAttempts: 1,
    providerOutputs: 1,
    toolInvocations: 0,
  });
  assert.equal(timeline.presentationCommittedAtMs, BASE_TIME + 5900);
  assert.equal(timeline.domVisibleAtMs, BASE_TIME + 6000);
  assert.equal(timeline.durations.clientInitializationMs, 20);
  assert.equal(timeline.durations.pipelineStartToFirstProviderActivityMs, 30);
  assert.equal(timeline.durations.durableToFinalEmitMs, 100);
  const serialized = JSON.stringify(timeline);
  assert.equal(serialized.includes(assistantMessageId), false);
});

test("Core timing and native-route receipts accept PTY SGR log wrappers", (t) => {
  const assistantMessageId = "assistant-main-available";
  const root = tempRoot(t);
  const logPath = path.join(root, "core.log");
  fs.writeFileSync(logPath, "", "utf8");
  const window = journey.captureCoreLogWindow(logPath);
  const receipt = {
    event: "viventium_text_main_winning_native_provider_receipt",
    turnIdHash: digest(assistantMessageId).slice(0, 16),
    provider: "synthetic-provider",
    model: "synthetic-model",
    snapshotHash: digest("snapshot"),
    nativeRequestSha256: digest("request"),
  };
  fs.appendFileSync(
    logPath,
    [...validQuickTimingEvents(assistantMessageId), receipt]
      .map(ptyCoreLogLine)
      .join(""),
    "utf8",
  );

  const timeline = journey.readQuickTurnTimingTimeline(
    window,
    assistantMessageId,
    {
      submittedAtMs: BASE_TIME + 3000,
      visibleAtMs: BASE_TIME + 6000,
    },
  );

  assert.equal(timeline.complete, true);
  assert.equal(
    journey.winningNativeReceipt(window, assistantMessageId)?.model,
    "synthetic-model",
  );
});

test("Core timing receipts reject non-SGR trailing bytes", (t) => {
  const assistantMessageId = "assistant-main-available";
  const root = tempRoot(t);
  const logPath = path.join(root, "core.log");
  fs.writeFileSync(logPath, "", "utf8");
  const window = journey.captureCoreLogWindow(logPath);
  fs.appendFileSync(
    logPath,
    validQuickTimingEvents(assistantMessageId)
      .map((event) => `${coreLogLine(event).trimEnd()}unexpected\n`)
      .join(""),
    "utf8",
  );

  const timeline = journey.readQuickTurnTimingTimeline(
    window,
    assistantMessageId,
    {
      submittedAtMs: BASE_TIME + 3000,
      visibleAtMs: BASE_TIME + 6000,
    },
  );

  assert.equal(timeline.complete, false);
  assert.equal(timeline.reason, "quick_turn_timing_event_missing");
});

test("Core timing proof excludes every matching event written before launch capture", (t) => {
  const assistantMessageId = "assistant-main-available";
  const root = tempRoot(t);
  const logPath = path.join(root, "core.log");
  fs.writeFileSync(
    logPath,
    validQuickTimingEvents(assistantMessageId).map(coreLogLine).join(""),
    "utf8",
  );
  const window = journey.captureCoreLogWindow(logPath);

  const timeline = journey.readQuickTurnTimingTimeline(
    window,
    assistantMessageId,
    {
      submittedAtMs: BASE_TIME + 3000,
      visibleAtMs: BASE_TIME + 6000,
    },
  );

  assert.equal(timeline.complete, false);
  assert.equal(timeline.reason, "quick_turn_timing_event_missing");
});

test("Core timing proof discards a pre-launch partial line completed after capture", (t) => {
  const assistantMessageId = "assistant-main-available";
  const root = tempRoot(t);
  const logPath = path.join(root, "core.log");
  const events = validQuickTimingEvents(assistantMessageId);
  fs.writeFileSync(logPath, coreLogLine(events[0]).trimEnd(), "utf8");
  const window = journey.captureCoreLogWindow(logPath);
  fs.appendFileSync(logPath, `\n${events.map(coreLogLine).join("")}`, "utf8");

  const timeline = journey.readQuickTurnTimingTimeline(
    window,
    assistantMessageId,
    {
      submittedAtMs: BASE_TIME + 3000,
      visibleAtMs: BASE_TIME + 6000,
    },
  );

  assert.equal(timeline.complete, true);
});

test("Core timing proof reads only a bounded fresh suffix of a log larger than 25 MiB", (t) => {
  const assistantMessageId = "assistant-main-available";
  const prior = Buffer.alloc(25 * 1024 * 1024 + 1, 0x78);
  prior[prior.length - 1] = 0x0a;
  const timeline = journey.readQuickTurnTimingTimeline(
    writeQuickTimingLog(t, validQuickTimingEvents(assistantMessageId), {
      beforeCapture: prior,
    }),
    assistantMessageId,
    {
      submittedAtMs: BASE_TIME + 3000,
      visibleAtMs: BASE_TIME + 6000,
    },
  );

  assert.equal(timeline.complete, true);
});

for (const [name, expectedReason, alterLog] of [
  [
    "replacement",
    "core_log_window_changed",
    (logPath) => {
      fs.renameSync(logPath, `${logPath}.rotated`);
      fs.writeFileSync(logPath, "replacement\n", "utf8");
    },
  ],
  [
    "truncation",
    "core_log_window_truncated",
    (logPath) => fs.truncateSync(logPath, 0),
  ],
  [
    "fresh-window overflow",
    "core_log_window_oversized",
    (logPath) =>
      fs.truncateSync(
        logPath,
        fs.statSync(logPath).size + 25 * 1024 * 1024 + 1,
      ),
  ],
]) {
  test(`Core timing proof fails closed on ${name}`, (t) => {
    const assistantMessageId = "assistant-main-available";
    const root = tempRoot(t);
    const logPath = path.join(root, "core.log");
    fs.writeFileSync(logPath, "prior-complete-line\n", "utf8");
    const window = journey.captureCoreLogWindow(logPath);
    alterLog(logPath);
    const timeline = journey.readQuickTurnTimingTimeline(
      window,
      assistantMessageId,
      {
        submittedAtMs: BASE_TIME + 3000,
        visibleAtMs: BASE_TIME + 6000,
      },
    );
    assert.equal(timeline.complete, false);
    assert.equal(timeline.reason, expectedReason);
  });
}

test("Core timing proof rejects same-inode truncation followed by regrowth", (t) => {
  const assistantMessageId = "assistant-main-available";
  const root = tempRoot(t);
  const logPath = path.join(root, "core.log");
  const prior = "prior-complete-line\n";
  fs.writeFileSync(logPath, prior, "utf8");
  const window = journey.captureCoreLogWindow(logPath);
  fs.truncateSync(logPath, 0);
  fs.writeFileSync(logPath, "x".repeat(Buffer.byteLength(prior)), "utf8");
  fs.appendFileSync(
    logPath,
    validQuickTimingEvents(assistantMessageId).map(coreLogLine).join(""),
    "utf8",
  );

  const timeline = journey.readQuickTurnTimingTimeline(
    window,
    assistantMessageId,
    {
      submittedAtMs: BASE_TIME + 3000,
      visibleAtMs: BASE_TIME + 6000,
    },
  );

  assert.equal(timeline.complete, false);
  assert.equal(timeline.reason, "core_log_window_truncated");
});

test("native route receipts use the same post-launch Core log window", (t) => {
  const assistantMessageId = "assistant-route";
  const event = {
    event: "viventium_text_main_winning_native_provider_receipt",
    turnIdHash: digest(assistantMessageId).slice(0, 16),
    provider: "synthetic-provider",
    model: "synthetic-model",
    snapshotHash: digest("snapshot"),
    nativeRequestSha256: digest("request"),
  };
  const root = tempRoot(t);
  const logPath = path.join(root, "core.log");
  fs.writeFileSync(logPath, coreLogLine(event), "utf8");
  const window = journey.captureCoreLogWindow(logPath);
  assert.equal(journey.winningNativeReceipt(window, assistantMessageId), null);
  fs.appendFileSync(logPath, coreLogLine(event), "utf8");
  assert.equal(
    journey.winningNativeReceipt(window, assistantMessageId)?.model,
    "synthetic-model",
  );
});

test("browser visibility may race ahead of the later authoritative presentation commit", (t) => {
  const assistantMessageId = "assistant-main-available";
  const events = validQuickTimingEvents(assistantMessageId);
  const presentation = events.find(
    (event) => event.stage === "presentation_committed",
  );
  presentation.observedAtMs = BASE_TIME + 6100;
  presentation.fromTurnStartMs = 3000;
  const timeline = journey.readQuickTurnTimingTimeline(
    writeQuickTimingLog(t, events),
    assistantMessageId,
    {
      submittedAtMs: BASE_TIME + 3000,
      visibleAtMs: BASE_TIME + 6000,
    },
  );

  assert.equal(timeline.complete, true);
  assert.equal(timeline.durations.presentationCommitToDomObservationMs, -100);
});

test("presentation acknowledgement timestamp may precede final emission by one millisecond", (t) => {
  const assistantMessageId = "assistant-main-available";
  const events = validQuickTimingEvents(assistantMessageId);
  const presentation = events.find(
    (event) => event.stage === "presentation_committed",
  );
  presentation.observedAtMs = BASE_TIME + 5799;
  presentation.fromTurnStartMs = 2699;
  const timeline = journey.readQuickTurnTimingTimeline(
    writeQuickTimingLog(t, events),
    assistantMessageId,
    {
      submittedAtMs: BASE_TIME + 3000,
      visibleAtMs: BASE_TIME + 6000,
    },
  );

  assert.equal(timeline.complete, true);
  assert.equal(timeline.durations.finalEmitToPresentationCommitMs, -1);
});

test("presentation acknowledgement cannot predate the durable assistant", (t) => {
  const assistantMessageId = "assistant-main-available";
  const events = validQuickTimingEvents(assistantMessageId);
  const presentation = events.find(
    (event) => event.stage === "presentation_committed",
  );
  presentation.observedAtMs = BASE_TIME + 5699;
  presentation.fromTurnStartMs = 2599;
  const timeline = journey.readQuickTurnTimingTimeline(
    writeQuickTimingLog(t, events),
    assistantMessageId,
    {
      submittedAtMs: BASE_TIME + 3000,
      visibleAtMs: BASE_TIME + 6000,
    },
  );

  assert.equal(timeline.complete, false);
  assert.equal(timeline.reason, "quick_turn_timing_order_invalid");
});

test("streamed browser visibility may precede later durable telemetry", (t) => {
  const assistantMessageId = "assistant-main-available";
  const timeline = journey.readQuickTurnTimingTimeline(
    writeQuickTimingLog(t, validQuickTimingEvents(assistantMessageId)),
    assistantMessageId,
    {
      submittedAtMs: BASE_TIME + 3000,
      visibleAtMs: BASE_TIME + 5650,
    },
  );

  assert.equal(timeline.complete, true);
  assert.equal(timeline.stages.browser_visible_final_answer, BASE_TIME + 5650);
  assert.equal(timeline.durations.presentationCommitToDomObservationMs, -250);
});

test("paired hashed tool boundaries match the model-reported tool count", (t) => {
  const assistantMessageId = "assistant-main-available";
  const events = validQuickTimingEvents(assistantMessageId);
  const turnIdHash = events[0].turnIdHash;
  const providerEnd = events.find(
    (event) => event.event === "viventium_text_main_provider_attempt_end",
  );
  providerEnd.toolCallCount = 1;
  const toolBase = {
    turnIdHash,
    invocationId: `${turnIdHash}.1`,
    attemptIndex: 1,
    toolIndex: 1,
    toolInvocationIdHash: "d".repeat(16),
    fromAttemptStartMs: 2320,
  };
  events.splice(events.length - 4, 0, {
    ...toolBase,
    event: "viventium_text_main_tool_start",
    observedAtMs: BASE_TIME + 5520,
    fromTurnStartMs: 2420,
  });
  events.splice(events.length - 4, 0, {
    ...toolBase,
    event: "viventium_text_main_tool_end",
    observedAtMs: BASE_TIME + 5550,
    fromTurnStartMs: 2450,
    fromAttemptStartMs: 2350,
  });
  const timeline = journey.readQuickTurnTimingTimeline(
    writeQuickTimingLog(t, events),
    assistantMessageId,
    {
      submittedAtMs: BASE_TIME + 3000,
      visibleAtMs: BASE_TIME + 6000,
    },
  );

  assert.equal(timeline.complete, true);
  assert.equal(timeline.counts.toolInvocations, 1);
  assert.equal(
    timeline.tools[0].completedAtMs - timeline.tools[0].startedAtMs,
    30,
  );
});

for (const [name, expectedReason, mutate] of [
  [
    "missing event",
    "quick_turn_timing_event_missing",
    (events) =>
      events.filter((event) => event.stage !== "presentation_committed"),
  ],
  [
    "duplicate event",
    "quick_turn_timing_event_duplicate",
    (events) => [...events, { ...events[1] }],
  ],
  [
    "unsafe field",
    "quick_turn_timing_event_unsafe",
    (events) => {
      events[0].messageText = "private-message-text";
      return events;
    },
  ],
  [
    "mismatched turn identity",
    "quick_turn_timing_identity_mismatch",
    (events) => {
      const end = events.find(
        (event) => event.event === "viventium_text_main_provider_attempt_end",
      );
      end.turnIdHash = "f".repeat(16);
      return events;
    },
  ],
  [
    "improper ordering",
    "quick_turn_timing_order_invalid",
    (events) => {
      const final = events.find(
        (event) => event.stage === "final_event_emitted",
      );
      final.observedAtMs = BASE_TIME + 5699;
      final.fromTurnStartMs = 2599;
      return events;
    },
  ],
  [
    "unmatched tool completion",
    "quick_turn_timing_tool_pair_mismatch",
    (events) => {
      const turnIdHash = events[0].turnIdHash;
      events.splice(events.length - 4, 0, {
        event: "viventium_text_main_tool_end",
        turnIdHash,
        invocationId: `${turnIdHash}.1`,
        attemptIndex: 1,
        toolIndex: 1,
        toolInvocationIdHash: "d".repeat(16),
        observedAtMs: BASE_TIME + 5550,
        fromTurnStartMs: 2450,
        fromAttemptStartMs: 2350,
      });
      return events;
    },
  ],
]) {
  test(`quick-turn timing rejects ${name}`, (t) => {
    const assistantMessageId = "assistant-main-available";
    const events = mutate(validQuickTimingEvents(assistantMessageId));
    const timeline = journey.readQuickTurnTimingTimeline(
      writeQuickTimingLog(t, events),
      assistantMessageId,
      {
        submittedAtMs: BASE_TIME + 3000,
        visibleAtMs: BASE_TIME + 6000,
      },
    );
    assert.equal(timeline.complete, false);
    assert.equal(timeline.reason, expectedReason);
  });
}

test("quick reply must be visibly committed once while both actual runtimes are active", () => {
  const rows = runtimeRows();
  const valid = journey.assessMainResponsiveness({
    rows,
    quickTurn: validEvidence().quickTurn,
    maxQuickLatencyMs: 10000,
  });
  assert.equal(valid.pass, true);
  assert.equal(valid.latencyMs, 3000);
  for (const invalid of [
    { visibleAtMs: BASE_TIME + 19000 },
    { finalReplyCount: 2 },
    { visible: false },
    { submittedAtMs: BASE_TIME - 1000 },
    { exactAnswer: false },
    { timingTimeline: { complete: false } },
    {
      timingTimeline: {
        ...validEvidence().quickTurn.timingTimeline,
        turnIdHash: "f".repeat(16),
      },
    },
  ]) {
    assert.equal(
      journey.assessMainResponsiveness({
        rows,
        quickTurn: { ...validEvidence().quickTurn, ...invalid },
        maxQuickLatencyMs: 10000,
      }).pass,
      false,
    );
  }
});

test("same-run resume waits through transient queued capacity re-admission", () => {
  const queuedResume = {
    ...runtimeRows()[0],
    currentRunRef: "run_alpha",
    currentRunState: "queued",
    state: "queued",
    runtimeInvokedAt: null,
    finishedAt: null,
    queueBlocker: "host_capacity",
    capacityShortageJson: '{"memory_bytes":1024}',
  };

  assert.equal(journey.runtimePrerequisiteBlocker([queuedResume]), null);
  assert.equal(
    journey.runtimePrerequisiteBlocker([
      {
        ...queuedResume,
        currentRunState: "failed",
        state: "failed",
      },
    ]),
    "worker_capacity_unavailable",
  );
});

test("typed capacity, provider, and authentication blockers stop the runner without false running claims", () => {
  assert.equal(journey.runtimePrerequisiteBlocker(runtimeRows()), null);
  assert.equal(
    journey.runtimePrerequisiteBlocker([
      {
        ...runtimeRows()[0],
        state: "failed",
        runtimeInvokedAt: null,
        queueBlocker: "host_capacity",
        capacityShortageJson: '{"memory_bytes":1024}',
      },
    ]),
    "worker_capacity_unavailable",
  );
  assert.equal(
    journey.runtimePrerequisiteBlocker([
      {
        ...runtimeRows()[0],
        state: "queued",
        runtimeInvokedAt: null,
        providerFailureClass: "provider_quota_exhausted",
      },
    ]),
    "worker_provider_quota_exhausted",
  );
  assert.equal(
    journey.runtimePrerequisiteBlocker([
      {
        ...runtimeRows()[0],
        state: "failed",
        failureClass: "provider_authentication_missing",
      },
    ]),
    "worker_provider_authentication_missing",
  );
});

test("steer succeeds exactly once for A and never changes sibling B", () => {
  const proof = journey.assessSteerIsolation(
    validEvidence().actions,
    runtimeRows(),
    "qa-owner",
  );
  assert.equal(proof.pass, true);
  assert.equal(
    journey.assessSteerIsolation(
      [
        ...validEvidence().actions,
        { ...validEvidence().actions[0], workRef: "work_bravo" },
      ],
      runtimeRows(),
      "qa-owner",
    ).pass,
    false,
  );
  assert.equal(
    journey.assessSteerIsolation(
      [{ ...validEvidence().actions[0], status: "pending" }],
      runtimeRows(),
      "qa-owner",
    ).pass,
    false,
  );
});

test("each completed runtime requires one HTTP-accepted callback and one completed visible Web presentation", () => {
  const evidence = validEvidence();
  assert.equal(
    journey.assessTerminalDeliveries(
      evidence.callbacks,
      evidence.runtimeRows,
      "qa-owner",
    ).pass,
    true,
  );
  assert.equal(
    journey.assessTerminalDeliveries(
      [...evidence.callbacks, evidence.callbacks[0]],
      evidence.runtimeRows,
      "qa-owner",
    ).pass,
    false,
  );
});

test("two missions may share one Main-authored Web message only with independent exact evidence", () => {
  const evidence = validEvidence();
  const sharedMessageId = "follow-up-coalesced";
  const callbacks = evidence.callbacks.map((callback) => ({
    ...callback,
    followUpMessageId: sharedMessageId,
    webPresentationMessageId: sharedMessageId,
    persistedMessageId: sharedMessageId,
    visibleMessageId: sharedMessageId,
  }));
  assert.equal(
    journey.assessTerminalDeliveries(
      callbacks,
      evidence.runtimeRows,
      "qa-owner",
    ).pass,
    true,
  );

  callbacks[1].missionEvidenceCount = 0;
  assert.equal(
    journey.assessTerminalDeliveries(
      callbacks,
      evidence.runtimeRows,
      "qa-owner",
    ).pass,
    false,
  );
});

test("coalesced Web presentation never permits two missions to share callback identity", () => {
  const evidence = validEvidence();
  const callbacks = structuredClone(evidence.callbacks);
  callbacks[1].callbackRef = callbacks[0].callbackRef;
  callbacks[1].canonicalCallbackRef = callbacks[0].canonicalCallbackRef;
  callbacks[1].missionEvidenceCallbackRef =
    callbacks[0].missionEvidenceCallbackRef;
  assert.equal(
    journey.assessTerminalDeliveries(
      callbacks,
      evidence.runtimeRows,
      "qa-owner",
    ).pass,
    false,
  );
});

test("coalesced Web presentation rejects raw and canonical aliases of one callback", () => {
  const evidence = validEvidence();
  const callbacks = structuredClone(evidence.callbacks);
  const canonicalCallbackRef = callbacks[0].canonicalCallbackRef;
  callbacks[1].callbackRef = canonicalCallbackRef;
  callbacks[1].canonicalCallbackRef = canonicalCallbackRef;
  callbacks[1].missionEvidenceCallbackRef = canonicalCallbackRef;
  assert.equal(
    journey.assessTerminalDeliveries(
      callbacks,
      evidence.runtimeRows,
      "qa-owner",
    ).pass,
    false,
  );
});

for (const [name, mutate] of [
  [
    "legacy delivered transport state",
    (item) => (item.callbackStatus = "delivered"),
  ],
  [
    "transport delivered timestamp",
    (item) => (item.deliveredAt = item.acceptedAt),
  ],
  ["missing acceptance time", (item) => (item.acceptedAt = null)],
  [
    "acceptance before runtime finish",
    (item) => (item.acceptedAt = new Date(BASE_TIME + 1000).toISOString()),
  ],
  ["zero callback attempt", (item) => (item.callbackAttemptNumber = 0)],
  ["wrong callback attempt", (item) => (item.callbackAttemptNumber = 2)],
  ["zero callback send attempts", (item) => (item.callbackAttempts = 0)],
  ["zero delivery generation", (item) => (item.callbackDeliveryGeneration = 0)],
  ["zero result revision", (item) => (item.callbackResultRevision = 0)],
  [
    "invalid result digest",
    (item) => (item.callbackResultDigest = "private-result"),
  ],
  [
    "mismatched raw callback identity",
    (item) => (item.callbackRef = "callback-other"),
  ],
  ["duplicate mission evidence", (item) => (item.missionEvidenceCount = 2)],
  ["missing mission evidence", (item) => (item.missionEvidenceCount = 0)],
  [
    "wrong mission owner",
    (item) => (item.missionEvidenceOwnerId = "other-owner"),
  ],
  [
    "wrong mission origin",
    (item) => (item.missionEvidenceOriginRef = "origin-other"),
  ],
  [
    "wrong mission work",
    (item) => (item.missionEvidenceWorkRef = "work-other"),
  ],
  ["wrong mission run", (item) => (item.missionEvidenceRunRef = "run-other")],
  ["wrong mission event", (item) => (item.missionEvidenceEvent = "run.failed")],
  [
    "wrong canonical callback",
    (item) =>
      (item.missionEvidenceCallbackRef = `callback_sha256:${"f".repeat(64)}`),
  ],
  ["wrong evidence attempt", (item) => (item.missionEvidenceAttemptNumber = 2)],
  [
    "unfinished mission evidence",
    (item) => (item.missionEvidenceState = "pending"),
  ],
  [
    "failed mission state",
    (item) => (item.missionEvidenceWorkState = "failed"),
  ],
  ["nonterminal mission", (item) => (item.missionEvidenceWorkTerminal = false)],
  ["mission error", (item) => (item.missionEvidenceErrorCode = "failed")],
  ["missing follow-up", (item) => (item.followUpMessageId = "")],
  [
    "mismatched Web presentation",
    (item) => (item.webPresentationMessageId = "other-message"),
  ],
  [
    "presentation before transport acceptance",
    (item) => (item.webPresentedAt = new Date(BASE_TIME + 17000).toISOString()),
  ],
  ["duplicate persisted message", (item) => (item.persistedMessageCount = 2)],
  [
    "wrong persisted message",
    (item) => (item.persistedMessageId = "other-message"),
  ],
  [
    "empty persisted message",
    (item) => (item.persistedMessageHasContent = false),
  ],
  ["duplicate visible message", (item) => (item.visibleMessageCount = 2)],
  [
    "wrong visible message",
    (item) => (item.visibleMessageId = "other-message"),
  ],
  ["empty visible message", (item) => (item.visibleMessageHasContent = false)],
]) {
  test(`terminal Web proof rejects ${name}`, () => {
    const evidence = validEvidence();
    const callbacks = structuredClone(evidence.callbacks);
    mutate(callbacks[0]);
    assert.equal(
      journey.assessTerminalDeliveries(
        callbacks,
        evidence.runtimeRows,
        "qa-owner",
      ).pass,
      false,
    );
  });
}

test("artifact proof requires different real HTML bytes and two headed visible OS windows", () => {
  const evidence = validEvidence();
  assert.equal(
    journey.assessArtifacts(
      evidence.artifacts,
      evidence.runtimeRows,
      "qa-owner",
    ).pass,
    true,
  );
  assert.equal(
    journey.assessArtifacts(
      [
        { ...evidence.artifacts[0] },
        {
          ...evidence.artifacts[1],
          bytes: evidence.artifacts[0].bytes,
          byteSha256: evidence.artifacts[0].byteSha256,
        },
      ],
      evidence.runtimeRows,
      "qa-owner",
    ).pass,
    false,
  );
  assert.equal(
    journey.assessArtifacts(
      [
        evidence.artifacts[0],
        { ...evidence.artifacts[1], windowId: evidence.artifacts[0].windowId },
      ],
      evidence.runtimeRows,
      "qa-owner",
    ).pass,
    false,
  );
  assert.equal(
    journey.assessArtifacts(
      [evidence.artifacts[0], { ...evidence.artifacts[1], headed: false }],
      evidence.runtimeRows,
      "qa-owner",
    ).pass,
    false,
  );
  assert.equal(
    journey.assessArtifacts(
      [
        evidence.artifacts[0],
        { ...evidence.artifacts[1], bytes: Buffer.from("not html") },
      ],
      evidence.runtimeRows,
      "qa-owner",
    ).pass,
    false,
  );
});

test("full PASS requires the existing independently verified Telegram native 280 ms proof", () => {
  const pass = journey.evaluateJourneyEvidence(validEvidence(), "qa-owner");
  assert.equal(pass.status, "PASS");
  assert.equal(pass.pass, true);

  const missing = validEvidence();
  missing.telegram = null;
  const partial = journey.evaluateJourneyEvidence(missing, "qa-owner");
  assert.equal(partial.status, "PARTIAL");
  assert.equal(partial.pass, false);
  assert.ok(
    partial.blockers.includes("telegram_native_revision_proof_unavailable"),
  );

  const forged = validEvidence();
  forged.telegram = { ...forged.telegram, verified: false };
  assert.equal(
    journey.evaluateJourneyEvidence(forged, "qa-owner").status,
    "PARTIAL",
  );
});

test("missing candidate identity is BLOCKED and a real serialized run is FAIL", () => {
  const blocked = validEvidence();
  blocked.identity.verified = false;
  assert.equal(
    journey.evaluateJourneyEvidence(blocked, "qa-owner").status,
    "BLOCKED",
  );

  const failed = validEvidence();
  failed.runtimeRows[1].runtimeInvokedAt = failed.runtimeRows[0].finishedAt;
  failed.runtimeRows[1].attemptRuntimeInvokedAt =
    failed.runtimeRows[0].finishedAt;
  assert.equal(
    journey.evaluateJourneyEvidence(failed, "qa-owner").status,
    "FAIL",
  );
});

test("public reports include only hashes and counters, never owner, prompts, tokens, paths, or raw work refs", () => {
  const evidence = validEvidence();
  evidence.rawPrompt = "private synthetic prompt should never appear";
  evidence.secret = "private-secret-value";
  evidence.ownerEmail = "qa@example.com";
  const evaluated = journey.evaluateJourneyEvidence(evidence, "qa-owner");
  const summary = journey.buildPublicSummary({
    result: evaluated,
    evidence,
    qaRunId: "PWK-UC-014-fixture-safe",
  });
  const serialized = JSON.stringify(summary);
  for (const forbidden of [
    "qa-owner",
    "qa@example.com",
    "private synthetic prompt",
    "private-secret-value",
    "work_alpha",
    "run_alpha",
    "/private/fixture",
  ]) {
    assert.equal(serialized.includes(forbidden), false, forbidden);
  }
  assert.equal(summary.status, "PASS");
  assert.equal(summary.releaseReady, false);
  assert.equal(summary.releaseLabel, "PRE-GATE / NOT READY");
  assert.equal(summary.artifactCount, 2);
});

test("trace completion requires an exact owner-scoped immutable hash chain", () => {
  const valid = traceFixture();
  assert.equal(
    journey.verifyTraceRows(
      valid.rows,
      valid.ownerId,
      valid.originRef,
      valid.workRef,
      valid.runRef,
      valid.callbackRef,
      valid.attemptNumber,
      valid.followUpMessageId,
    ),
    true,
  );
  for (const change of [
    (rows) => {
      rows[0].ownerScopeHash = prefixedDigest("other-owner");
    },
    (rows) => {
      rows[1].previousEventHash = prefixedDigest("broken-chain");
    },
    (rows) => {
      rows[1].facts = { workRefHash: prefixedDigest("wrong-work") };
    },
    (rows) => {
      rows[2].stage = "callback.delivery.pending";
    },
    (rows) => {
      rows[2].sequence = 6;
    },
  ]) {
    const altered = structuredClone(valid.rows);
    change(altered);
    assert.equal(
      journey.verifyTraceRows(
        altered,
        valid.ownerId,
        valid.originRef,
        valid.workRef,
        valid.runRef,
      ),
      false,
    );
  }
  assert.equal(
    journey.verifyTraceRows(
      Array.from({ length: 101 }, () => valid.rows[0]),
      valid.ownerId,
      valid.originRef,
      valid.workRef,
      valid.runRef,
    ),
    false,
  );
});

for (const [name, mutate] of [
  [
    "duplicate callback acceptance",
    (definitions) => {
      const accepted = definitions.find(
        (item) => item.stage === "callback.accepted",
      );
      definitions.push(structuredClone(accepted));
    },
  ],
  [
    "missing accepted callback identity",
    (definitions) => {
      delete definitions.find((item) => item.stage === "callback.accepted")
        .facts.callbackRefHash;
    },
  ],
  [
    "missing accepted work identity",
    (definitions) => {
      delete definitions.find((item) => item.stage === "callback.accepted")
        .facts.workRefHash;
    },
  ],
  [
    "mismatched delivery callback identity",
    (definitions) => {
      definitions.find(
        (item) => item.stage === "callback.delivery.sent",
      ).facts.callbackRefHash = prefixedDigest(
        "callback\0callback_sha256:" + "f".repeat(64),
      );
    },
  ],
  [
    "mismatched delivery attempt",
    (definitions) => {
      definitions.find(
        (item) => item.stage === "callback.delivery.sent",
      ).facts.attemptNumber = 2;
    },
  ],
  [
    "wrong callback event",
    (definitions) => {
      definitions.find(
        (item) => item.stage === "callback.accepted",
      ).facts.callbackEvent = "run.failed";
    },
  ],
  [
    "wrong callback terminal state",
    (definitions) => {
      definitions.find(
        (item) => item.stage === "callback.accepted",
      ).facts.state = "failed";
    },
  ],
  [
    "nonterminal callback",
    (definitions) => {
      definitions.find(
        (item) => item.stage === "callback.accepted",
      ).facts.terminal = false;
    },
  ],
  [
    "missing Web delivery reference",
    (definitions) => {
      delete definitions.find((item) => item.stage === "callback.delivery.sent")
        .facts.deliveryRefHash;
    },
  ],
  [
    "mismatched Web delivery reference",
    (definitions) => {
      definitions.find(
        (item) => item.stage === "callback.delivery.sent",
      ).facts.deliveryRefHash = prefixedDigest(
        "delivery\0main-web:other-follow-up",
      );
    },
  ],
  [
    "wrong terminal surface",
    (definitions) => {
      definitions.find(
        (item) => item.stage === "callback.delivery.sent",
      ).facts.surface = "telegram";
    },
  ],
  [
    "wrong delivery state",
    (definitions) => {
      definitions.find(
        (item) => item.stage === "callback.delivery.sent",
      ).facts.deliveryState = "failed";
    },
  ],
  [
    "delivery before callback acceptance",
    (definitions) => {
      const accepted = definitions.findIndex(
        (item) => item.stage === "callback.accepted",
      );
      const delivered = definitions.findIndex(
        (item) => item.stage === "callback.delivery.sent",
      );
      [definitions[accepted], definitions[delivered]] = [
        definitions[delivered],
        definitions[accepted],
      ];
    },
  ],
]) {
  test(`terminal trace rejects ${name}`, () => {
    const fixture = traceFixture(mutate);
    assert.equal(
      journey.verifyTraceRows(
        fixture.rows,
        fixture.ownerId,
        fixture.originRef,
        fixture.workRef,
        fixture.runRef,
        fixture.callbackRef,
        fixture.attemptNumber,
        fixture.followUpMessageId,
      ),
      false,
    );
  });
}

test("Telegram race facts are read from independently verified documents, never manufactured", (t) => {
  const root = journey.preparePrivateEvidenceRoot(
    path.join(tempRoot(t), "telegram-proof"),
    { repoRoot: REPO_ROOT },
  );
  const identity = validEvidence().identity;
  const logicalTurnHash = digest("actual-logical-turn");
  const source = {
    payload: {
      events: [{ event: "core_ingestion_admitted", delayMs: 280 }],
    },
  };
  const history = {
    payload: {
      beforeReopen: {
        messages: [
          { role: "user", turnRefHash: logicalTurnHash },
          { role: "user", turnRefHash: logicalTurnHash },
          { role: "assistant", turnRefHash: logicalTurnHash, revision: 2 },
        ],
      },
    },
  };
  const visible = {
    payload: {
      bundleId: "ru.keepcoder.Telegram",
      surface: "telegram",
      captures: [
        { captureOrigin: "native_desktop_window_capture", windowVisible: true },
      ],
    },
  };
  const revisions = {
    payload: {
      scenarios: [{ initialRevision: 1, correctedRevision: 2 }],
    },
  };
  const evidence = [
    ["telegram_source_trace", "source.json", source],
    ["mongo_history", "history.json", history],
    ["telegram_ui_observation", "visible.json", visible],
    ["core_revision_trace", "revisions.json", revisions],
  ].map(([kind, name, document]) => {
    const saved = journey.writePrivateEvidence(root, name, document);
    return { kind, path: name, sha256: saved.sha256 };
  });
  const manifest = {
    candidate: {
      candidateDigest: identity.candidateDigest,
      artifactDigest: identity.artifactDigest,
    },
    correlation: { turnRefHash: logicalTurnHash },
    evidence,
  };
  const result = {
    caseId: "TR-026",
    status: "PASS",
    ready: true,
    surface: "telegram",
    candidateDigest: identity.candidateDigest,
    artifactDigest: identity.artifactDigest,
    gates: [
      "authoritative-signed-280ms-race-audit",
      "pre-commit-revision-and-post-commit-correction",
      "direct-telegram-desktop-visible-and-reopened",
      "original-user-order-and-one-persisted-final-answer",
    ].map((id) => ({ id, status: "PASS" })),
  };
  assert.deepEqual(
    journey.deriveTelegramProof({
      result,
      manifest,
      evidenceRoot: root,
      identity,
      logicalTurnHash,
    }),
    {
      verified: true,
      nativeDesktop: true,
      revisionBeforeCommit: true,
      finalReplyCount: 1,
      delayMs: 280,
    },
  );
  const wrongTurn = journey.deriveTelegramProof({
    result,
    manifest,
    evidenceRoot: root,
    identity,
    logicalTurnHash: digest("wrong-turn"),
  });
  assert.equal(wrongTurn, null);
  const forged = structuredClone(manifest);
  forged.evidence[0].sha256 = digest("fabricated-document");
  assert.equal(
    journey.deriveTelegramProof({
      result,
      manifest: forged,
      evidenceRoot: root,
      identity,
      logicalTurnHash,
    }),
    null,
  );
});

test("read-only SQLite observation is exact-owner scoped and cannot mutate the runtime database", (t) => {
  const root = tempRoot(t);
  const location = path.join(root, "runtime.sqlite3");
  const writable = new DatabaseSync(location);
  writable.exec(`
    CREATE TABLE workers (worker_id TEXT PRIMARY KEY, owner_id TEXT, resource_class TEXT, execution_mode TEXT, workspace_root TEXT, workspace_dir TEXT);
    CREATE TABLE delegations (work_ref TEXT PRIMARY KEY, owner_id TEXT, origin_ref TEXT, worker_id TEXT, current_run_id TEXT);
    CREATE TABLE runs (
      run_id TEXT PRIMARY KEY,
      worker_id TEXT,
      state TEXT,
      queued_at TEXT,
      runtime_invoked_at TEXT,
      ended_at TEXT,
      queue_blocker_class TEXT,
      failure_class TEXT,
      capacity_available_json TEXT,
      capacity_required_json TEXT,
      capacity_shortage_json TEXT,
      capacity_next_retry_at TEXT,
      provider_route_failure_class TEXT
    );
    CREATE TABLE run_attempts (attempt_id TEXT PRIMARY KEY, run_id TEXT, attempt_number INTEGER, state TEXT, runtime_invoked_at TEXT, ended_at TEXT, lease_id TEXT);
    CREATE TABLE host_run_leases (lease_id TEXT PRIMARY KEY, owner_id TEXT, worker_id TEXT, run_id TEXT, executor_id TEXT, startup_container_id TEXT, startup_confirmed_at TEXT, acquired_at TEXT, released_at TEXT);
    CREATE TABLE callback_outbox (
      callback_id TEXT PRIMARY KEY,
      run_id TEXT,
      attempt_number INTEGER,
      event_type TEXT,
      result_revision INTEGER,
      result_digest TEXT,
      status TEXT,
      attempts INTEGER,
      http_accepted_at TEXT,
      delivered_at TEXT,
      delivery_generation INTEGER
    );
    CREATE TABLE active_work_action_uses (action_use_id TEXT PRIMARY KEY, owner_id TEXT, work_ref TEXT, action TEXT, status TEXT, created_at TEXT);
  `);
  for (const row of runtimeRows()) {
    writable
      .prepare("INSERT INTO workers VALUES (?, ?, ?, ?, ?, ?)")
      .run(
        row.workerRef,
        row.ownerId,
        row.resourceClass,
        row.executionMode,
        row.workspaceRoot,
        row.workspaceRoot,
      );
    writable
      .prepare("INSERT INTO delegations VALUES (?, ?, ?, ?, ?)")
      .run(row.workRef, row.ownerId, row.originRef, row.workerRef, row.runRef);
    writable
      .prepare(
        "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
      )
      .run(
        row.runRef,
        row.workerRef,
        row.state,
        row.runtimeInvokedAt,
        row.runtimeInvokedAt,
        row.finishedAt,
        "",
        "",
        "{}",
        "{}",
        "{}",
        null,
        "",
      );
    writable
      .prepare("INSERT INTO run_attempts VALUES (?, ?, ?, ?, ?, ?, ?)")
      .run(
        row.attemptRef,
        row.runRef,
        row.attemptNumber,
        row.attemptState,
        row.attemptRuntimeInvokedAt,
        row.attemptFinishedAt,
        row.leaseRef,
      );
    writable
      .prepare("INSERT INTO host_run_leases VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)")
      .run(
        row.leaseRef,
        row.ownerId,
        row.workerRef,
        row.runRef,
        row.executorRef,
        row.containerRef,
        row.leaseConfirmedAt,
        row.leaseAcquiredAt,
        row.leaseReleasedAt,
      );
    writable
      .prepare(
        "INSERT INTO callback_outbox VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
      )
      .run(
        `callback-${row.workRef}`,
        row.runRef,
        row.attemptNumber,
        "run.completed",
        1,
        prefixedDigest(`result-${row.workRef}`),
        "http_accepted",
        1,
        row.finishedAt,
        null,
        1,
      );
  }
  writable
    .prepare("INSERT INTO active_work_action_uses VALUES (?, ?, ?, ?, ?, ?)")
    .run(
      "action-alpha",
      "qa-owner",
      "work_alpha",
      "steer",
      "accepted",
      new Date(BASE_TIME + 7000).toISOString(),
    );
  writable
    .prepare("INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)")
    .run(
      "run_alpha_live",
      "worker_alpha",
      "running",
      new Date(BASE_TIME + 17000).toISOString(),
      new Date(BASE_TIME + 18000).toISOString(),
      null,
      "",
      "",
      "{}",
      "{}",
      "{}",
      null,
      "",
    );
  writable
    .prepare("INSERT INTO run_attempts VALUES (?, ?, ?, ?, ?, ?, ?)")
    .run(
      "attempt_alpha_live",
      "run_alpha_live",
      1,
      "running",
      new Date(BASE_TIME + 18000).toISOString(),
      null,
      "lease_alpha_live",
    );
  writable
    .prepare("INSERT INTO host_run_leases VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)")
    .run(
      "lease_alpha_live",
      "qa-owner",
      "worker_alpha",
      "run_alpha_live",
      "executor_alpha_live",
      "container_alpha_live",
      new Date(BASE_TIME + 18250).toISOString(),
      new Date(BASE_TIME + 17500).toISOString(),
      null,
    );
  writable
    .prepare("INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)")
    .run(
      "run_alpha_queued_continuation",
      "worker_alpha",
      "queued",
      new Date(BASE_TIME + 19000).toISOString(),
      null,
      null,
      "admission_pending",
      "",
      "{}",
      "{}",
      "{}",
      null,
      "",
    );
  writable
    .prepare("UPDATE delegations SET current_run_id = ? WHERE work_ref = ?")
    .run("run_alpha_queued_continuation", "work_alpha");
  writable
    .prepare("INSERT INTO workers VALUES (?, ?, ?, ?, ?, ?)")
    .run(
      "worker_other",
      "other-owner",
      "light",
      "docker",
      "/private/other",
      "/private/other",
    );
  writable
    .prepare("INSERT INTO delegations VALUES (?, ?, ?, ?, ?)")
    .run(
      "work_other",
      "other-owner",
      "origin_other",
      "worker_other",
      "run_other",
    );
  writable.close();

  const store = journey.openReadOnlyGlassHiveStore(location);
  t.after(() => store.close());
  const observed = journey.readScopedRuntimeEvidence(store, {
    ownerId: "qa-owner",
    workRefs: ["work_alpha", "work_bravo"],
  });
  assert.equal(observed.rows.length, 2);
  assert.equal(observed.callbacks.length, 1);
  assert.equal(
    observed.callbacks.every(
      (callback) =>
        callback.callbackStatus === "http_accepted" &&
        callback.callbackAttemptNumber === 1 &&
        callback.callbackDeliveryGeneration === 1 &&
        callback.deliveredAt == null,
    ),
    true,
  );
  assert.equal(observed.actions.length, 1);
  assert.equal(
    observed.rows.every((row) => row.ownerId === "qa-owner"),
    true,
  );
  const alpha = observed.rows.find((row) => row.workRef === "work_alpha");
  assert.equal(alpha.runRef, "run_alpha_live");
  assert.equal(alpha.state, "running");
  assert.equal(alpha.currentRunRef, "run_alpha_queued_continuation");
  assert.equal(alpha.currentRunState, "queued");
  assert.equal(JSON.stringify(observed).includes("other-owner"), false);
  assert.throws(
    () => store.exec("DELETE FROM delegations"),
    /readonly|read.only/i,
  );
  assert.throws(
    () =>
      journey.readScopedRuntimeEvidence(store, {
        ownerId: "qa-owner",
        workRefs: ["work_alpha", "work_other"],
      }),
    /owner_scoped_mission_evidence_incomplete/,
  );
});

test("fixture driver submits real user-side stages rather than treating verifier output as a trigger", async () => {
  const evidence = validEvidence();
  const calls = [];
  const driver = {
    async login() {
      calls.push("login");
    },
    async submitAndObserve(stage, prompt) {
      calls.push(`prompt:${stage}`);
      assert.equal(typeof prompt, "string");
      assert.ok(prompt.length > 0);
      if (stage === "quick") return evidence.quickTurn;
      return stage === "feelings" ? evidence.feelings : evidence.routeFacts;
    },
    async submitParallelRequest(prompt) {
      calls.push("launch");
      assert.match(prompt, /two simple.*html/i);
      return { conversationId: "conversation-safe" };
    },
    async waitForConcurrentWorkers() {
      calls.push("running");
      return evidence.runtimeRows;
    },
    async steerFirstWorker() {
      calls.push("steer");
      return evidence.actions;
    },
    async waitForTerminalWorkers() {
      calls.push("completed");
      return evidence.runtimeRows;
    },
    async collectCallbacks() {
      calls.push("callbacks");
      return evidence.callbacks;
    },
    async collectTraces() {
      calls.push("traces");
      return evidence.traces;
    },
    async openArtifactWindows() {
      calls.push("windows");
      return evidence.artifacts;
    },
    async verifyTelegramRevision() {
      calls.push("telegram");
      return evidence.telegram;
    },
    async close() {
      calls.push("close");
    },
  };
  const result = await journey.executeInstalledJourney({
    driver,
    args: liveArgs(path.join(os.tmpdir(), "viventium-unused-fixture")),
    identity: evidence.identity,
    ownerId: "qa-owner",
  });
  assert.equal(result.status, "PASS");
  assert.deepEqual(calls, [
    "login",
    "prompt:feelings",
    "prompt:route",
    "launch",
    "running",
    "prompt:quick",
    "steer",
    "completed",
    "callbacks",
    "traces",
    "windows",
    "telegram",
    "close",
  ]);
});

test("fixture driver always closes and reports prerequisites honestly without fake receipts", async () => {
  let closed = false;
  const result = await journey.executeInstalledJourney({
    driver: {
      async login() {
        throw journey.blockedError("provider_authentication_unavailable");
      },
      async close() {
        closed = true;
      },
    },
    args: liveArgs(path.join(os.tmpdir(), "viventium-unused-fixture")),
    identity: validEvidence().identity,
    ownerId: "qa-owner",
  });
  assert.equal(closed, true);
  assert.equal(result.status, "BLOCKED");
  assert.equal(result.pass, false);
  assert.deepEqual(result.blockers, ["provider_authentication_unavailable"]);
});

test("every installed case has an explicit dry-run contract and unknown cases fail closed", () => {
  const expectedChecks = {
    "PWK-UC-014": "overlapping-runtime-windows",
    "PWK-UC-015": "restart-acknowledgements",
    "PWK-UC-016": "atomic-reservation-race",
    "PWK-UC-017": "duplicate-callback-suppression",
    "PWK-UC-018": "two-owner-auth-matrix",
  };
  for (const [caseId, requiredCheck] of Object.entries(expectedChecks)) {
    const args = journey.parseArgs(["--dry-run", `--case=${caseId}`], {});
    const plan = journey.dryRunPlan(args);
    assert.equal(plan.caseId, caseId);
    assert.equal(plan.receiptEligible, false);
    assert.equal(plan.releaseReady, false);
    assert.ok(plan.requiredChecks.includes(requiredCheck));
  }
  assert.throws(
    () => journey.parseArgs(["--dry-run", "--case=PWK-UC-019"], {}),
    /unsupported_case/,
  );
});

test("PWK-UC-014 emits a natural request with no artificial delay or internal worker plan", async () => {
  const evidence = validEvidence();
  let emitted = "";
  const driver = {
    async login() {},
    async submitAndObserve(stage) {
      if (stage === "quick") return evidence.quickTurn;
      return stage === "feelings" ? evidence.feelings : evidence.routeFacts;
    },
    async submitParallelRequest(prompt) {
      emitted = prompt;
      return {};
    },
    async waitForConcurrentWorkers() {
      return evidence.runtimeRows;
    },
    async steerFirstWorker() {
      return evidence.actions;
    },
    async waitForTerminalWorkers() {
      return evidence.runtimeRows;
    },
    async collectCallbacks() {
      return evidence.callbacks;
    },
    async collectTraces() {
      return evidence.traces;
    },
    async openArtifactWindows() {
      return evidence.artifacts;
    },
    async verifyTelegramRevision() {
      return evidence.telegram;
    },
    async close() {},
  };
  const result = await journey.executeInstalledJourney({
    driver,
    args: liveArgs(path.join(os.tmpdir(), "viventium-natural-prompt")),
    identity: evidence.identity,
    ownerId: "qa-owner",
  });
  assert.equal(result.status, "PASS");
  assert.match(emitted, /two (simple|small).*html/i);
  assert.match(emitted, /keep (yourself|main) (free|available)/i);
  assert.doesNotMatch(
    emitted,
    /20\s*(seconds?|s)\b|sleep|delay|keep.*runtime.*active/i,
  );
  assert.doesNotMatch(
    emitted,
    /resource class|\bdocker\b|\blease\b|\bhost\b|start both immediately/i,
  );
  assert.doesNotMatch(emitted, /PWK Alpha|PWK Bravo|alpha-|bravo-|\.html\b/i);
});

test("restart and fault journeys require separate explicit live permissions", () => {
  const output = path.join(os.tmpdir(), "viventium-case-safety");
  const base = liveArgs(output, { caseId: "PWK-UC-015", allowRestart: false });
  assert.throws(
    () => journey.assertScenarioSafety(base, safeEnv()),
    /coordinated_restart_requires_explicit_permission/,
  );
  assert.throws(
    () =>
      journey.assertScenarioSafety(
        { ...base, allowRestart: true },
        safeEnv({ VIVENTIUM_QA_ALLOW_COORDINATED_RESTART: "1" }),
      ),
    /restart_readiness_proof_required/,
  );
  assert.throws(
    () =>
      journey.assertScenarioSafety(
        liveArgs(output, { caseId: "PWK-UC-016", allowFaults: false }),
        safeEnv(),
      ),
    /glasshive_faults_require_explicit_permission/,
  );
});

test("restart readiness is exact-case, candidate-bound, service-complete, and process-new", () => {
  const candidateDigest = "a".repeat(64);
  const proof = {
    caseId: "PWK-UC-015",
    candidateDigest,
    restartState: "ready",
    serviceAckDigest: `sha256:${"b".repeat(64)}`,
    requiredServices: ["librechat-core", "telegram-bot", "glasshive-runtime"],
    acknowledgedServices: [
      "librechat-core",
      "telegram-bot",
      "glasshive-runtime",
    ],
    missingServices: [],
    services: [
      ["librechat-core", "11", "21"],
      ["telegram-bot", "12", "22"],
      ["glasshive-runtime", "13", "23"],
    ].map(([service, beforeProcessRefHash, afterProcessRefHash]) => ({
      service,
      beforeProcessRefHash: digest(beforeProcessRefHash),
      afterProcessRefHash: digest(afterProcessRefHash),
      acknowledgementSha256: digest(service),
    })),
  };
  assert.equal(
    journey.assertRestartReadiness(proof, {
      caseId: "PWK-UC-015",
      candidateDigest,
    }).verified,
    true,
  );
  assert.throws(
    () =>
      journey.assertRestartReadiness(
        { ...proof, caseId: "PWK-UC-017" },
        { caseId: "PWK-UC-015", candidateDigest },
      ),
    /restart_readiness_proof_invalid/,
  );
  assert.throws(
    () =>
      journey.assertRestartReadiness(
        {
          ...proof,
          services: proof.services.map((service) => ({
            ...service,
            afterProcessRefHash: service.beforeProcessRefHash,
          })),
        },
        { caseId: "PWK-UC-015", candidateDigest },
      ),
    /restart_readiness_proof_invalid/,
  );
});

test("private restart paperwork cannot replace authenticated current service acknowledgements", () => {
  const proof = restartProof("PWK-UC-017");
  const trusted = {
    caseId: proof.caseId,
    restartState: "ready",
    requiredServices: proof.requiredServices,
    acknowledgedServices: proof.acknowledgedServices,
    missingServices: [],
    serviceAckDigest: proof.serviceAckDigest,
    sessionRef: "qa_synthetic_session",
  };
  assert.equal(
    journey.assertAuthenticatedRestartStatus(proof, trusted, {
      caseId: proof.caseId,
      candidateDigest: proof.candidateDigest,
      previousServiceAckDigest: `sha256:${digest("earlier-acknowledgements")}`,
      sessionRef: trusted.sessionRef,
    }).verified,
    true,
  );
  for (const [status, previous, expected] of [
    [
      { ...trusted, serviceAckDigest: `sha256:${digest("forged")}` },
      "",
      /authenticated_restart_acknowledgements_unavailable/,
    ],
    [
      { ...trusted, caseId: "PWK-UC-016" },
      "",
      /authenticated_restart_acknowledgements_unavailable/,
    ],
    [
      trusted,
      proof.serviceAckDigest,
      /service_restart_process_change_unproven/,
    ],
  ]) {
    assert.throws(
      () =>
        journey.assertAuthenticatedRestartStatus(proof, status, {
          caseId: proof.caseId,
          candidateDigest: proof.candidateDigest,
          previousServiceAckDigest: previous,
          sessionRef: trusted.sessionRef,
        }),
      expected,
    );
  }
});

test("cases 015 through 018 execute distinct real scenario drivers", async () => {
  const expected = {
    "PWK-UC-015": ["runRestartContinuityJourney"],
    "PWK-UC-016": ["runCapacityProviderRecoveryJourney"],
    "PWK-UC-017": ["runCallbackArtifactRecoveryJourney"],
    "PWK-UC-018": ["runOwnerArtifactIsolationJourney"],
  };
  for (const [caseId, callsExpected] of Object.entries(expected)) {
    const calls = [];
    const driver = {
      async login() {
        calls.push("login");
      },
      async [callsExpected[0]]() {
        calls.push(callsExpected[0]);
        return {
          caseId,
          scenarioId: journey.CASE_CONTRACTS[caseId].scenarioId,
          observed: true,
        };
      },
      async close() {
        calls.push("close");
      },
    };
    const args = liveArgs(
      path.join(os.tmpdir(), `viventium-${caseId.toLowerCase()}`),
      { caseId },
    );
    const result = await journey.executeInstalledJourney({
      driver,
      args,
      identity: validEvidence().identity,
      ownerId: "qa-owner",
    });
    assert.deepEqual(calls, ["login", ...callsExpected, "close"]);
    assert.equal(result.evidence.caseId, caseId);
    assert.equal(
      result.evidence.scenario.scenarioId,
      journey.CASE_CONTRACTS[caseId].scenarioId,
    );
  }
});

test("case-specific evaluation rejects generic PWK-UC-014 or unobserved scenario evidence", () => {
  for (const caseId of [
    "PWK-UC-015",
    "PWK-UC-016",
    "PWK-UC-017",
    "PWK-UC-018",
  ]) {
    const wrong = journey.evaluateJourneyEvidence(
      { ...validEvidence(), caseId },
      "qa-owner",
    );
    assert.notEqual(wrong.status, "PASS");
    assert.ok(wrong.blockers.some((value) => value.includes("scenario")));

    const unobserved = journey.evaluateJourneyEvidence(
      {
        caseId,
        identity: validEvidence().identity,
        scenario: {
          scenarioId: journey.CASE_CONTRACTS[caseId].scenarioId,
          observed: false,
        },
      },
      "qa-owner",
    );
    assert.notEqual(unobserved.status, "PASS");
  }
});

test("two-owner journey requires a distinct synthetic non-admin account", () => {
  const args = liveArgs(path.join(os.tmpdir(), "viventium-owner-isolation"), {
    caseId: "PWK-UC-018",
    secondQaEmail: "qa-second@example.com",
  });
  const env = safeEnv();
  assert.doesNotThrow(() => journey.assertScenarioSafety(args, env));
  assert.throws(
    () =>
      journey.assertScenarioSafety(
        { ...args, secondQaEmail: args.qaEmail },
        env,
      ),
    /second_synthetic_qa_account_required/,
  );
  assert.throws(
    () => journey.assertScenarioSafety(args, safeEnv({ JWT_SECRET: "" })),
    /ephemeral_browser_session_signing_secrets_required/,
  );
});

test("ephemeral browser authentication rejects admin, locked, mismatched, and unsigned accounts", async () => {
  const args = liveArgs(
    path.join(os.tmpdir(), "viventium-ephemeral-rejection"),
  );
  const user = {
    _id: "qa-owner",
    email: "qa@example.com",
    role: "USER",
    viventiumApprovalStatus: "approved",
  };
  const db = {
    collection() {
      throw new Error("no_session_write_expected");
    },
  };
  for (const [candidate, env, expected] of [
    [{ ...user, role: "ADMIN" }, safeEnv(), /admin_account_refused/],
    [
      { ...user, viventiumApprovalStatus: "pending" },
      safeEnv(),
      /locked_qa_account_refused/,
    ],
    [
      { ...user, email: "different@example.com" },
      safeEnv(),
      /selected_qa_account_mismatch/,
    ],
    [
      user,
      safeEnv({ JWT_SECRET: "" }),
      /ephemeral_browser_session_signing_secrets_required/,
    ],
    [
      user,
      safeEnv({ JWT_REFRESH_SECRET: "" }),
      /ephemeral_browser_session_signing_secrets_required/,
    ],
  ]) {
    await assert.rejects(
      journey.createEphemeralBrowserSession({ db, user: candidate, args, env }),
      expected,
    );
  }
});

test("ephemeral session uses exact owner, short-lived httpOnly cookies, and idempotent cleanup", async () => {
  const inserted = [];
  const removed = [];
  const sessions = {
    async insertOne(row) {
      inserted.push(row);
      return { acknowledged: true };
    },
    async deleteOne(selector) {
      removed.push(selector);
      return { deletedCount: 1 };
    },
  };
  const db = {
    collection(name) {
      assert.equal(name, "sessions");
      return sessions;
    },
  };
  const args = liveArgs(path.join(os.tmpdir(), "viventium-ephemeral-cleanup"));
  const user = {
    _id: "qa-owner",
    email: "qa@example.com",
    username: "synthetic",
    provider: "local",
    role: "USER",
    viventiumApprovalStatus: "approved",
  };
  const auth = await journey.createEphemeralBrowserSession({
    db,
    user,
    args,
    env: safeEnv(),
    nowMs: BASE_TIME,
    createSessionId: () => "synthetic-session-id",
    signToken: (payload, secret, options) => {
      assert.ok(secret.startsWith("synthetic-"));
      assert.ok(options.expiresIn <= 900);
      return `${payload.sessionId ? "refresh" : "access"}-fixture-token`;
    },
  });
  assert.equal(inserted.length, 1);
  assert.equal(inserted[0].user, user._id);
  assert.equal(inserted[0]._id, "synthetic-session-id");
  assert.equal(inserted[0].refreshTokenHash, digest("refresh-fixture-token"));
  assert.ok(inserted[0].expiration.getTime() - BASE_TIME <= 900000);
  assert.equal(auth.cookies.length, 4);
  assert.ok(
    auth.cookies.every(
      (cookie) => cookie.httpOnly === true && cookie.sameSite === "Strict",
    ),
  );
  await auth.cleanup();
  await auth.cleanup();
  assert.deepEqual(removed, [
    { _id: "synthetic-session-id", user: "qa-owner" },
  ]);
});

test("ephemeral session cleanup remains owner-scoped after browser startup failure", async () => {
  let deleted;
  const db = {
    collection() {
      return {
        async insertOne() {
          return { acknowledged: true };
        },
        async deleteOne(selector) {
          deleted = selector;
          return { deletedCount: 1 };
        },
      };
    },
  };
  const auth = await journey.createEphemeralBrowserSession({
    db,
    user: { _id: "qa-owner", email: "qa@example.com", role: "USER" },
    args: liveArgs(path.join(os.tmpdir(), "viventium-ephemeral-failure")),
    env: safeEnv(),
    createSessionId: () => "session-failure",
    signToken: () => "fixture-token",
  });
  try {
    throw new Error("browser_launch_failed");
  } catch {
    await auth.cleanup();
  }
  assert.deepEqual(deleted, { _id: "session-failure", user: "qa-owner" });
});

test("each case accepts only its complete scenario-specific runtime and visible evidence", () => {
  for (const caseId of [
    "PWK-UC-015",
    "PWK-UC-016",
    "PWK-UC-017",
    "PWK-UC-018",
  ]) {
    const result = journey.evaluateJourneyEvidence(
      scenarioEvidence(caseId),
      "qa-owner",
    );
    assert.equal(result.caseId, caseId);
    assert.equal(
      result.status,
      "PASS",
      `${caseId}: ${result.blockers.join(",")}`,
    );
    assert.equal(result.receiptEligible, false);
  }
});

test("restart continuity retains the live generation and exact queued continuation", () => {
  const evidence = scenarioEvidence("PWK-UC-015");
  const continuationRunRef = "run_alpha_queued_continuation";
  for (const rows of [
    evidence.scenario.before.rows,
    evidence.scenario.after.rows,
  ]) {
    rows[0].currentRunRef = continuationRunRef;
    rows[0].currentRunState = "queued";
  }
  evidence.runtimeRows[0].runRef = continuationRunRef;
  evidence.runtimeRows[0].currentRunRef = continuationRunRef;
  evidence.runtimeRows[0].currentRunState = "completed";

  const continuity = journey.assessRestartContinuity(evidence, "qa-owner");
  assert.equal(continuity.pass, true, continuity.reason);

  const replacedAcrossRestart = structuredClone(evidence);
  replacedAcrossRestart.scenario.after.rows[0].currentRunRef =
    "run_alpha_wrong_continuation";
  assert.equal(
    journey.assessRestartContinuity(replacedAcrossRestart, "qa-owner").reason,
    "exact_restart_mission_identity_continuity_required",
  );

  const unrelatedTerminal = structuredClone(evidence);
  unrelatedTerminal.runtimeRows[0].runRef = "run_alpha_unrelated_terminal";
  assert.equal(
    journey.assessRestartContinuity(unrelatedTerminal, "qa-owner").reason,
    "exact_restart_mission_identity_continuity_required",
  );
});

test("blocked public summary reports unobserved evidence counts as unknown", () => {
  const evidence = scenarioEvidence("PWK-UC-015");
  delete evidence.runtimeRows;
  delete evidence.callbacks;
  delete evidence.artifacts;
  const summary = journey.buildPublicSummary({
    result: {
      status: "BLOCKED",
      pass: false,
      releaseReady: false,
      receiptEligible: false,
      blockers: ["fixture_blocker"],
    },
    evidence,
    qaRunId: "PWK-UC-015-blocked-fixture",
  });
  assert.equal(summary.runtimeCount, null);
  assert.equal(summary.callbackCount, null);
  assert.equal(summary.artifactCount, null);
});

for (const [name, caseId, mutate, expected] of [
  [
    "restart callback before the coordinated restart",
    "PWK-UC-015",
    (value) => {
      value.scenario.before.terminalCallbackCount = 1;
    },
    "pre_and_post_restart",
  ],
  [
    "replacement mission after restart",
    "PWK-UC-015",
    (value) => {
      value.scenario.after.rows[0].workRef = "replacement";
    },
    "mission_identity",
  ],
  [
    "duplicate mission instead of continuation",
    "PWK-UC-015",
    (value) => {
      value.scenario.continuation.workCountAfter = 3;
    },
    "continuation",
  ],
  [
    "missing consumed provider fault",
    "PWK-UC-016",
    (value) => {
      value.scenario.faults.pop();
    },
    "fault_coverage",
  ],
  [
    "manufactured capacity shortage",
    "PWK-UC-016",
    (value) => {
      value.scenario.capacity.measurement.shortageBytes += 1;
    },
    "capacity_shortage",
  ],
  [
    "two last-slot reservation winners",
    "PWK-UC-016",
    (value) => {
      value.scenario.capacity.reservationAttempts[1].outcome = "reserved";
      value.scenario.capacity.reservationAttempts[1].workRef = "work_bravo";
    },
    "reservation",
  ],
  [
    "overflow that created hidden work",
    "PWK-UC-016",
    (value) => {
      value.scenario.capacity.overflow.workRows = 1;
    },
    "overflow",
  ],
  [
    "primary route attempted during quota cooldown",
    "PWK-UC-016",
    (value) => {
      value.scenario.provider.primaryAttemptCountDuringCooldown = 1;
    },
    "cooldown",
  ],
  [
    "duplicate claimed terminal transition",
    "PWK-UC-017",
    (value) => {
      value.scenario.delivery.timeouts[0].terminalTransitions = 2;
    },
    "timeout_once",
  ],
  [
    "stale callback sender delivery",
    "PWK-UC-017",
    (value) => {
      value.scenario.delivery.expiredSenderDelivered = true;
    },
    "sender_lease",
  ],
  [
    "unobserved unavailable-artifact wording",
    "PWK-UC-017",
    (value) => {
      value.scenario.artifactFailures[1].userVisible = false;
    },
    "artifact_copy",
  ],
  [
    "cross-owner worker access",
    "PWK-UC-018",
    (value) => {
      value.scenario.ownerMatrix.operations[1].outcome = "allowed";
    },
    "cross_owner",
  ],
  [
    "unaudited worker-isolation success flags",
    "PWK-UC-018",
    (value) => {
      value.scenario.workerIsolation = {
        peerAccessDenied: true,
        hostAccessDenied: true,
      };
    },
    "worker_peer_and_host_isolation",
  ],
  [
    "hostile artifact with executable authority",
    "PWK-UC-018",
    (value) => {
      value.scenario.hostileArtifact.scriptExecuted = true;
    },
    "browser_isolation",
  ],
  [
    "private data in the hostile artifact",
    "PWK-UC-018",
    (value) => {
      value.scenario.publicSafety.privateLeakCount = 1;
    },
    "safety_scan",
  ],
]) {
  test(`case evidence rejects ${name}`, () => {
    const evidence = scenarioEvidence(caseId);
    mutate(evidence);
    const result = journey.evaluateJourneyEvidence(evidence, "qa-owner");
    assert.equal(result.status, "FAIL");
    assert.ok(
      result.blockers.some((blocker) => blocker.includes(expected)),
      result.blockers.join(","),
    );
  });
}

test("every diagnostic scenario remains PRE-GATE with no receipt or release readiness", () => {
  for (const caseId of [
    "PWK-UC-015",
    "PWK-UC-016",
    "PWK-UC-017",
    "PWK-UC-018",
  ]) {
    const evidence = scenarioEvidence(caseId);
    evidence.identity = {
      ...evidence.identity,
      candidateMode: "diagnostic",
      identityFailures: [
        { id: "NESTED-PINS", status: "FAIL", reason: "nested_pin_mismatch" },
      ],
    };
    const result = journey.evaluateJourneyEvidence(evidence, "qa-owner");
    assert.equal(result.status, "PARTIAL", caseId);
    assert.equal(result.diagnosticPass, true, caseId);
    assert.ok(
      result.blockers.includes(
        "diagnostic_candidate_cannot_close_release_gate",
      ),
    );
    const summary = journey.buildPublicSummary({
      result,
      evidence,
      qaRunId: `${caseId}-fixture`,
    });
    assert.equal(summary.releaseReady, false);
    assert.equal(summary.receiptEligible, false);
    assert.equal(summary.releaseLabel, "PRE-GATE / NOT READY");
  }
});

test("case-specific native Telegram and headed browser gaps remain honest PARTIAL blockers", () => {
  for (const caseId of [
    "PWK-UC-015",
    "PWK-UC-016",
    "PWK-UC-017",
    "PWK-UC-018",
  ]) {
    const evidence = scenarioEvidence(caseId);
    evidence.scenario.surfaces = { webVisible: false, telegramVisible: false };
    const result = journey.evaluateJourneyEvidence(evidence, "qa-owner");
    assert.equal(result.status, "PARTIAL", caseId);
    assert.ok(
      result.blockers.includes("headed_browser_scenario_proof_unavailable"),
    );
    assert.ok(
      result.blockers.includes("native_telegram_scenario_proof_unavailable"),
    );
  }
});

function isolationAuditFixture(t) {
  const root = tempRoot(t);
  const store = new DatabaseSync(path.join(root, "worker-isolation.sqlite3"));
  t.after(() => store.close());
  store.exec(`
    CREATE TABLE workers (worker_id TEXT PRIMARY KEY, owner_id TEXT, tenant_id TEXT);
    CREATE TABLE delegations (
      work_ref TEXT PRIMARY KEY, worker_id TEXT, owner_id TEXT, tenant_id TEXT,
      current_run_id TEXT
    );
    CREATE TABLE events (
      event_id TEXT PRIMARY KEY, project_id TEXT, worker_id TEXT, tenant_id TEXT,
      run_id TEXT, event_type TEXT, payload_json TEXT, created_at TEXT
    );
    CREATE TABLE work_trace_events (
      trace_event_id TEXT PRIMARY KEY, run_id TEXT, work_ref TEXT, tenant_id TEXT,
      owner_id TEXT, sequence INTEGER, event_type TEXT, payload_json TEXT,
      previous_event_sha256 TEXT, event_sha256 TEXT, created_at TEXT
    );
  `);
  const rows = runtimeRows();
  for (const row of rows) {
    store
      .prepare("INSERT INTO workers VALUES (?, ?, ?)")
      .run(row.workerRef, row.ownerId, "local");
    store
      .prepare("INSERT INTO delegations VALUES (?, ?, ?, ?, ?)")
      .run(row.workRef, row.workerRef, row.ownerId, "local", row.runRef);
    const peer = rows.find((candidate) => candidate.workRef !== row.workRef);
    const fingerprint = (kind, value) => prefixedDigest(`${kind}\0${value}`);
    const payload = {
      contractVersion: 1,
      producerScope: "glasshive.worker_isolation",
      ownerRefHash: fingerprint("owner", row.ownerId),
      workRefHash: fingerprint("work", row.workRef),
      runRefHash: fingerprint("run", row.runRef),
      workerRefHash: fingerprint("worker", row.workerRef),
      attemptRefHash: fingerprint("attempt", row.attemptRef),
      leaseRefHash: fingerprint("lease", row.leaseRef),
      containerRefHash: fingerprint("container", row.containerRef),
      workspaceRefHash: fingerprint("workspace", row.workspaceRoot),
      homeRefHash: fingerprint("home", `fixture-home-${row.workerRef}`),
      networkRefHash: fingerprint(
        "network",
        `fixture-network-${row.workerRef}`,
      ),
      pidNamespaceRefHash: fingerprint("pid_namespace", row.containerRef),
      executionMode: "isolated_container",
      hostStateReadable: false,
      serviceEnvironmentReadable: false,
      dockerSocketReadable: false,
      ambientAuthority: false,
      peerAccessDenied: true,
      hostAccessDenied: true,
      peerProbes: [
        { workRefHash: fingerprint("work", peer.workRef), reachable: false },
      ],
    };
    const correlation = digest(
      stableJson({
        ownerRefHash: payload.ownerRefHash,
        workRefHash: payload.workRefHash,
        runRefHash: payload.runRefHash,
        attemptRefHash: payload.attemptRefHash,
        leaseRefHash: payload.leaseRefHash,
        containerRefHash: payload.containerRefHash,
        peers: payload.peerProbes.map((entry) => entry.workRefHash),
      }),
    );
    const eventId = `evt_isolation_${correlation}`;
    const traceEventId = `trace_isolation_${correlation}`;
    const createdAt = new Date(BASE_TIME + 4000).toISOString();
    const eventHash = digest(
      stableJson({
        createdAt,
        eventType: "worker.isolation_probe",
        payload,
        previousEventSha256: "",
        runId: row.runRef,
        sequence: 1,
        traceEventId,
        workRef: row.workRef,
      }),
    );
    store
      .prepare("INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?)")
      .run(
        eventId,
        "fixture-project",
        row.workerRef,
        "local",
        row.runRef,
        "worker.isolation_probe",
        JSON.stringify(payload),
        createdAt,
      );
    store
      .prepare(
        "INSERT INTO work_trace_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
      )
      .run(
        traceEventId,
        row.runRef,
        row.workRef,
        "local",
        row.ownerId,
        1,
        "worker.isolation_probe",
        JSON.stringify(payload),
        "",
        eventHash,
        createdAt,
      );
  }
  return { store, rows };
}

test("worker isolation requires exact owner-bound confirmed generation and immutable audit chain", (t) => {
  const { store, rows } = isolationAuditFixture(t);
  const evidence = journey.readWorkerIsolationEvidence(store, {
    ownerId: "qa-owner",
    rows,
  });
  assert.equal(evidence.peerAccessDenied, true);
  assert.equal(evidence.hostAccessDenied, true);
  assert.equal(evidence.auditVerified, true);
  assert.equal(evidence.workers.length, 2);
});

test("worker isolation ignores truthful single-worker observations once exact sibling evidence exists", (t) => {
  const { store, rows } = isolationAuditFixture(t);
  const row = rows[0];
  const existing = store
    .prepare("SELECT payload_json, created_at FROM events WHERE run_id = ?")
    .get(row.runRef);
  const payload = JSON.parse(existing.payload_json);
  payload.peerProbes = [];
  payload.peerAccessDenied = false;
  const correlation = digest(
    stableJson({
      ownerRefHash: payload.ownerRefHash,
      workRefHash: payload.workRefHash,
      runRefHash: payload.runRefHash,
      attemptRefHash: payload.attemptRefHash,
      leaseRefHash: payload.leaseRefHash,
      containerRefHash: payload.containerRefHash,
      peers: [],
    }),
  );
  const eventId = `evt_isolation_${correlation}`;
  const traceEventId = `trace_isolation_${correlation}`;
  const previous = store
    .prepare(
      "SELECT sequence, event_sha256 FROM work_trace_events WHERE run_id = ? ORDER BY sequence DESC LIMIT 1",
    )
    .get(row.runRef);
  const createdAt = new Date(BASE_TIME + 5000).toISOString();
  const eventHash = digest(
    stableJson({
      createdAt,
      eventType: "worker.isolation_probe",
      payload,
      previousEventSha256: previous.event_sha256,
      runId: row.runRef,
      sequence: previous.sequence + 1,
      traceEventId,
      workRef: row.workRef,
    }),
  );
  store
    .prepare("INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?)")
    .run(
      eventId,
      "fixture-project",
      row.workerRef,
      "local",
      row.runRef,
      "worker.isolation_probe",
      JSON.stringify(payload),
      createdAt,
    );
  store
    .prepare(
      "INSERT INTO work_trace_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
    )
    .run(
      traceEventId,
      row.runRef,
      row.workRef,
      "local",
      row.ownerId,
      previous.sequence + 1,
      "worker.isolation_probe",
      JSON.stringify(payload),
      previous.event_sha256,
      eventHash,
      createdAt,
    );

  const evidence = journey.readWorkerIsolationEvidence(store, {
    ownerId: "qa-owner",
    rows,
  });
  assert.equal(evidence.auditVerified, true);
  assert.equal(evidence.workers.length, 2);
  assert.ok(evidence.workers.every((worker) => worker.peerProbes.length === 1));
});

for (const [label, mutate] of [
  [
    "wrong owner",
    (store, rows) => {
      store
        .prepare("UPDATE work_trace_events SET owner_id = ? WHERE run_id = ?")
        .run("fixture-other-owner", rows[0].runRef);
    },
  ],
  [
    "replaced container generation",
    (store, rows) => {
      const event = store
        .prepare("SELECT event_id, payload_json FROM events WHERE run_id = ?")
        .get(rows[0].runRef);
      const payload = JSON.parse(event.payload_json);
      payload.containerRefHash = prefixedDigest(
        "container\0replacement-container",
      );
      store
        .prepare("UPDATE events SET payload_json = ? WHERE event_id = ?")
        .run(JSON.stringify(payload), event.event_id);
    },
  ],
  [
    "forged immutable event digest",
    (store, rows) => {
      store
        .prepare(
          "UPDATE work_trace_events SET event_sha256 = ? WHERE run_id = ?",
        )
        .run("f".repeat(64), rows[0].runRef);
    },
  ],
  [
    "missing real sibling probe",
    (store, rows) => {
      const event = store
        .prepare("SELECT event_id, payload_json FROM events WHERE run_id = ?")
        .get(rows[0].runRef);
      const payload = JSON.parse(event.payload_json);
      payload.peerProbes = [];
      store
        .prepare("UPDATE events SET payload_json = ? WHERE event_id = ?")
        .run(JSON.stringify(payload), event.event_id);
    },
  ],
]) {
  test(`worker isolation rejects ${label} without trusting standalone success flags`, (t) => {
    const { store, rows } = isolationAuditFixture(t);
    mutate(store, rows);
    assert.throws(
      () =>
        journey.readWorkerIsolationEvidence(store, {
          ownerId: "qa-owner",
          rows,
        }),
      /worker_peer_isolation_probe_unavailable|worker_peer_or_host_isolation_unproven/,
    );
  });
}

test("parent fault fixture refuses an exact candidate session owned by another account", async () => {
  const calls = [];
  const args = liveArgs(path.join(os.tmpdir(), "viventium-fault-scope"), {
    caseId: "PWK-UC-016",
    allowFaults: true,
  });
  const invokeControl = async (command) => {
    calls.push(command);
    if (command === "status") {
      return {
        caseId: args.caseId,
        restartState: "ready",
        missingServices: [],
        sessionRef: "qa_session_synthetic",
      };
    }
    if (command === "prepare-glasshive") {
      return {
        caseId: args.caseId,
        status: "ready",
        scopeHashes: { owner: `sha256:${digest("unrelated-owner")}` },
      };
    }
    return { status: "clean" };
  };
  await assert.rejects(
    journey.withGlassHiveFaultFixture({
      args,
      ownerId: "qa-owner",
      ownerAccount: { email: "worker@example.com", role: "USER" },
      signingSecret: "synthetic-owner-scope-signing-secret",
      invokeControl,
      perform: async () => {},
    }),
    /controlled_fixture_owner_mismatch/,
  );
  assert.deepEqual(calls, [
    "status",
    "prepare-glasshive",
    "clear-glasshive",
    "cleanup-glasshive",
  ]);
});

test("selected fixture owner scope is HMAC-bound and contains no credential", () => {
  const scope = journey.createFixtureOwnerScope({
    caseId: "PWK-UC-016",
    sessionRef: "qa_session_synthetic",
    ownerId: "synthetic-owner-id",
    user: { email: "worker@example.com", role: "USER" },
    signingSecret: "synthetic-owner-scope-signing-secret",
    nowMs: 1787500800000,
    nonce: "a".repeat(32),
  });
  assert.equal(scope.ownerId, "synthetic-owner-id");
  assert.equal(scope.ownerEmail, "worker@example.com");
  assert.equal(scope.ownerRole, "USER");
  assert.equal(scope.expiresAtMs - scope.issuedAtMs, 30000);
  assert.match(scope.attestation, /^sha256:[a-f0-9]{64}$/);
  assert.equal(
    JSON.stringify(scope).includes("synthetic-owner-scope-signing-secret"),
    false,
  );

  const forged = { ...scope, ownerId: "different-synthetic-owner" };
  assert.notEqual(
    journey.fixtureOwnerScopeAttestation(
      forged,
      "synthetic-owner-scope-signing-secret",
    ),
    scope.attestation,
  );
});

test("default fault fixture transport forwards the signed owner scope over stdin", async (t) => {
  const root = tempRoot(t);
  const binRoot = path.join(root, "bin");
  const executable = path.join(binRoot, "viventium");
  const ownerId = "synthetic-owner-id";
  const ownerHash = journey.nestedScopeHash("owner", ownerId);
  fs.mkdirSync(binRoot, { recursive: true });
  fs.writeFileSync(
    executable,
    `#!/usr/bin/env node
"use strict";
const fs = require("node:fs");
const command = process.argv[3];
if (command === "status") {
  process.stdout.write(JSON.stringify({caseId:"PWK-UC-016",restartState:"ready",missingServices:[],sessionRef:"qa_session_synthetic"}));
} else if (command === "prepare-glasshive") {
  const scope = JSON.parse(fs.readFileSync(0, "utf8"));
  if (scope.ownerId !== "synthetic-owner-id" || !scope.attestation) process.exit(12);
  process.stdout.write(JSON.stringify({caseId:"PWK-UC-016",status:"ready",scopeHashes:{owner:${JSON.stringify(ownerHash)}}}));
} else {
  process.stdout.write(JSON.stringify({status:"clean"}));
}
`,
    { mode: 0o700 },
  );

  const result = await journey.withGlassHiveFaultFixture({
    args: { caseId: "PWK-UC-016", allowFaults: true, installedRoot: root },
    ownerId,
    ownerAccount: { email: "worker@example.com", role: "USER" },
    signingSecret: "synthetic-owner-scope-signing-secret",
    perform: async ({ fixture }) => fixture.status,
  });
  assert.equal(result, "ready");
});

test("parent fault fixtures clear every armed boundary and clean up after scenario failure", async () => {
  const calls = [];
  const args = liveArgs(path.join(os.tmpdir(), "viventium-fault-cleanup"), {
    caseId: "PWK-UC-017",
    allowFaults: true,
  });
  const invokeControl = async (command) => {
    calls.push(command);
    if (command === "status") {
      return {
        caseId: args.caseId,
        restartState: "ready",
        missingServices: [],
        sessionRef: "qa_session_synthetic",
      };
    }
    if (command === "prepare-glasshive") {
      return {
        caseId: args.caseId,
        status: "ready",
        scopeHashes: { owner: journey.nestedScopeHash("owner", "qa-owner") },
      };
    }
    return { status: "clean" };
  };
  await assert.rejects(
    journey.withGlassHiveFaultFixture({
      args,
      ownerId: "qa-owner",
      ownerAccount: { email: "worker@example.com", role: "USER" },
      signingSecret: "synthetic-owner-scope-signing-secret",
      invokeControl,
      perform: async () => {
        throw journey.blockedError("fault_effect_not_observed");
      },
    }),
    /fault_effect_not_observed/,
  );
  assert.deepEqual(calls, [
    "status",
    "prepare-glasshive",
    "clear-glasshive",
    "cleanup-glasshive",
  ]);
});

test("consumed fault proof requires one exact owner, case, boundary, and applied effect", (t) => {
  const root = tempRoot(t);
  const location = path.join(root, "fault-ledger.sqlite3");
  const writable = new DatabaseSync(location);
  writable.exec(`
    CREATE TABLE local_qa_fault_controls (
      control_ref TEXT PRIMARY KEY, case_id TEXT, boundary TEXT, owner_hash TEXT,
      status TEXT, consumed_at TEXT, consumption_count INTEGER
    );
    CREATE TABLE local_qa_fault_audit (
      audit_ref TEXT PRIMARY KEY, control_ref TEXT, action TEXT
    );
  `);
  const controlRef = `qac_sha256:${digest("exact-local-control")}`;
  const consumedAt = new Date(BASE_TIME).toISOString();
  writable
    .prepare("INSERT INTO local_qa_fault_controls VALUES (?, ?, ?, ?, ?, ?, ?)")
    .run(
      controlRef,
      "PWK-UC-016",
      "provider_auth_missing",
      journey.nestedScopeHash("owner", "qa-owner"),
      "consumed",
      consumedAt,
      1,
    );
  writable
    .prepare("INSERT INTO local_qa_fault_audit VALUES (?, ?, ?)")
    .run("audit-fixture", controlRef, "effect_applied");
  writable.close();
  const store = journey.openReadOnlyGlassHiveStore(location);
  t.after(() => store.close());
  assert.deepEqual(
    journey.readConsumedFaultObservation(store, {
      caseId: "PWK-UC-016",
      ownerId: "qa-owner",
      controlRef,
      expectedBoundary: "provider_auth_missing",
    }),
    {
      boundary: "provider_auth_missing",
      controlRef,
      status: "consumed",
      ownerId: "qa-owner",
      consumedAt,
      effectCount: 1,
    },
  );
  for (const changed of [
    { ownerId: "other-owner" },
    { caseId: "PWK-UC-017" },
    { expectedBoundary: "provider_unavailable" },
  ]) {
    assert.equal(
      journey.readConsumedFaultObservation(store, {
        caseId: "PWK-UC-016",
        ownerId: "qa-owner",
        controlRef,
        expectedBoundary: "provider_auth_missing",
        ...changed,
      }),
      null,
    );
  }
});

test("capacity proof is derived from exact owner-scoped durable measurements, never invented", () => {
  const availableBytes = Math.floor(4.3 * 1024 ** 3);
  const requiredBytes = 5 * 1024 ** 3;
  const rows = [
    {
      ownerId: "qa-owner",
      workRef: "work_alpha",
      capacityClass: "resource_pressure",
      availableJson: JSON.stringify({ memoryBytes: availableBytes }),
      requiredJson: JSON.stringify({ memoryBytes: requiredBytes }),
      shortageJson: JSON.stringify({
        memoryBytes: requiredBytes - availableBytes,
      }),
      reservationJson: "{}",
      nextRetryAt: new Date(BASE_TIME + 15000).toISOString(),
    },
  ];
  assert.deepEqual(journey.deriveMeasuredCapacityShortage(rows, "qa-owner"), {
    availableBytes,
    requiredBytes,
    shortageBytes: requiredBytes - availableBytes,
    nextRetryAt: rows[0].nextRetryAt,
  });
  assert.throws(
    () =>
      journey.deriveMeasuredCapacityShortage(
        [{ ...rows[0], ownerId: "other-owner" }],
        "qa-owner",
      ),
    /measured_owner_scoped_capacity_shortage_unavailable/,
  );
  assert.throws(
    () =>
      journey.deriveMeasuredCapacityShortage(
        [{ ...rows[0], shortageJson: JSON.stringify({ memoryBytes: 1 }) }],
        "qa-owner",
      ),
    /measured_owner_scoped_capacity_shortage_unavailable/,
  );
});

test("queue timeout proof binds actual terminal events to distinct consumed run-scoped controls", () => {
  const faults = ["claimed_queue_stall", "admitted_queue_stall"].map(
    (boundary, index) => ({
      boundary,
      ownerId: "qa-owner",
      status: "consumed",
      effectCount: 1,
      consumedAt: new Date(BASE_TIME + index * 1000).toISOString(),
      controlRef: `qac_sha256:${digest(boundary)}`,
    }),
  );
  const events = ["claimed", "admitted"].map((state, index) => ({
    ownerId: "qa-owner",
    runRef: `run_${state}`,
    eventType: "run.failed",
    createdAt: new Date(BASE_TIME + 2000 + index * 1000).toISOString(),
    payloadJson: JSON.stringify({
      failureClass: "queue_wait_timeout",
      timeoutAt: new Date(BASE_TIME + 1500 + index * 1000).toISOString(),
    }),
  }));
  const runHashes = new Map(
    faults.map((fault, index) => [
      fault.controlRef,
      journey.nestedScopeHash("run", events[index].runRef),
    ]),
  );
  const options = {
    faults,
    events,
    ownerId: "qa-owner",
    lookupRunHash: (controlRef) => runHashes.get(controlRef),
  };
  assert.deepEqual(journey.deriveQueueTimeoutTransitions(options), [
    { state: "claimed", terminalTransitions: 1 },
    { state: "admitted", terminalTransitions: 1 },
  ]);
  for (const [changed, expected] of [
    [
      { events: [events[0], events[0]] },
      /exact_claimed_and_admitted_terminal_transitions_unavailable/,
    ],
    [
      { events: events.map((event) => ({ ...event, ownerId: "other-owner" })) },
      /exact_claimed_and_admitted_terminal_transitions_unavailable/,
    ],
    [
      { lookupRunHash: () => runHashes.get(faults[0].controlRef) },
      /exact_claimed_and_admitted_terminal_transitions_unavailable/,
    ],
    [
      {
        events: events.map((event) => ({
          ...event,
          payloadJson: JSON.stringify({ failureClass: "other" }),
        })),
      },
      /exact_claimed_and_admitted_terminal_transitions_unavailable/,
    ],
  ]) {
    assert.throws(
      () => journey.deriveQueueTimeoutTransitions({ ...options, ...changed }),
      expected,
    );
  }
});

test("reservation proof joins real owner launch receipts, admitted capacity, and the exact lease", () => {
  const observedAt = new Date(BASE_TIME).toISOString();
  const ownerId = "qa-owner";
  const capacityRows = [
    {
      ownerId,
      workRef: "work_alpha",
      runRef: "run_alpha",
      requestRef: "capacity_attempt_actual",
      capacityClass: "admission_reserved",
      reservationJson: JSON.stringify({ memoryBytes: 3 * 1024 ** 3 }),
      observedAt: new Date(BASE_TIME + 2000).toISOString(),
    },
  ];
  const bindingRows = [
    {
      ownerId,
      originRef: "origin_accepted",
      sourceEventId: "source_same_user_turn",
      workRef: "work_alpha",
      launchState: "accepted",
      createdAt: new Date(BASE_TIME + 1000),
    },
    {
      ownerId,
      originRef: "origin_rejected",
      sourceEventId: "source_same_user_turn",
      workRef: "",
      launchState: "not_dispatched",
      preDispatchFailureCode: "host_capacity",
      preDispatchFailedAt: new Date(BASE_TIME + 3000),
      createdAt: new Date(BASE_TIME + 1000),
    },
  ];
  const leaseRows = [
    {
      ownerId,
      workRef: "work_alpha",
      runRef: "run_alpha",
      leaseRef: "lease_actual",
      acquiredAt: new Date(BASE_TIME + 2000).toISOString(),
      reservedMemoryBytes: 3 * 1024 ** 3,
    },
  ];
  const options = { capacityRows, bindingRows, leaseRows, ownerId, observedAt };
  assert.deepEqual(journey.deriveAtomicReservationAttempts(options), [
    {
      requestRef: "origin_accepted",
      slotRef: "lease_actual",
      outcome: "reserved",
      workRef: "work_alpha",
    },
    {
      requestRef: "origin_rejected",
      slotRef: "lease_actual",
      outcome: "rejected",
      workRef: null,
    },
  ]);
  for (const changed of [
    { bindingRows: [bindingRows[0]] },
    {
      bindingRows: bindingRows.map((row) => ({
        ...row,
        ownerId: "other-owner",
      })),
    },
    {
      bindingRows: [
        bindingRows[0],
        { ...bindingRows[1], sourceEventId: "different_turn" },
      ],
    },
    {
      bindingRows: [
        bindingRows[0],
        { ...bindingRows[1], preDispatchFailureCode: "provider_unavailable" },
      ],
    },
    {
      bindingRows: [
        bindingRows[0],
        { ...bindingRows[1], workRef: "hidden_work" },
      ],
    },
    {
      capacityRows: [
        { ...capacityRows[0], capacityClass: "resource_pressure" },
      ],
    },
    { leaseRows: [{ ...leaseRows[0], runRef: "other_run" }] },
    { leaseRows: [{ ...leaseRows[0], reservedMemoryBytes: 1 }] },
  ]) {
    assert.throws(
      () => journey.deriveAtomicReservationAttempts({ ...options, ...changed }),
      /atomic_reservation_race_user_request_evidence_unavailable/,
    );
  }
});

test("hostile artifact safety uses actual captured bytes and blocks private disclosures", () => {
  const clean = Buffer.from(
    "<!doctype html><html><body><script>window.fixtureAttempt=1</script></body></html>",
  );
  const safe = journey.scanHostileArtifactBytes(clean, [
    "synthetic-private-marker",
  ]);
  assert.equal(safe.scannedArtifactSha256, digest(clean));
  assert.equal(safe.findingCount, 0);
  const unsafe = Buffer.from(
    "<html><script>synthetic-private-marker</script></html>",
  );
  assert.throws(
    () =>
      journey.scanHostileArtifactBytes(unsafe, ["synthetic-private-marker"]),
    /hostile_artifact_private_disclosure_detected/,
  );
});

test("HTML artifacts resolve from real opaque signed-link labels without inventing filenames", () => {
  assert.equal(
    journey.artifactRelativePath({
      href: "/v1/link-refs/opaque_synthetic_reference",
      ariaLabel: "Open reports/actual-generated-result.html",
      base: "http://127.0.0.1:3190",
    }),
    "reports/actual-generated-result.html",
  );
  assert.equal(
    journey.artifactRelativePath({
      href: "/v1/workers/synthetic/artifacts/open?path=output%2Fresult.htm",
      ariaLabel: "Open output/result.htm",
      base: "http://127.0.0.1:3190",
    }),
    "output/result.htm",
  );
  assert.throws(
    () =>
      journey.artifactRelativePath({
        href: "/v1/link-refs/opaque_synthetic_reference",
        ariaLabel: "Open ../../outside.html",
        base: "http://127.0.0.1:3190",
      }),
    /owner_scoped_artifact_path_unavailable/,
  );
  assert.throws(
    () =>
      journey.artifactRelativePath({
        href: "/v1/workers/synthetic/artifacts/open?path=output%2Fother.htm",
        ariaLabel: "Open output/result.htm",
        base: "http://127.0.0.1:3190",
      }),
    /owner_scoped_artifact_path_unavailable/,
  );
});

test("cross-owner callback denial uses a genuine per-run signature, not an unsigned malformed probe", () => {
  const payload = {
    event: "run.completed",
    worker_id: "worker_synthetic",
    run_id: "run_synthetic",
    work_ref: "work_synthetic",
    origin_ref: "origin_synthetic",
    callback_ts: BASE_TIME / 1000,
  };
  const signature = journey.signScopedCallbackPayload(
    payload,
    "fixture-signing-material",
  );
  const derived = crypto
    .createHmac("sha256", "fixture-signing-material")
    .update("worker_synthetic:run_synthetic")
    .digest("hex");
  const expected = crypto
    .createHmac("sha256", derived)
    .update(stableJson(payload))
    .digest("hex");
  assert.equal(signature, `sha256=${expected}`);
  assert.notEqual(
    journey.signScopedCallbackPayload(
      { ...payload, origin_ref: "origin_other" },
      "fixture-signing-material",
    ),
    signature,
  );
  assert.throws(
    () => journey.signScopedCallbackPayload(payload, ""),
    /signed_cross_owner_callback_authority_unavailable/,
  );
  assert.throws(
    () =>
      journey.signScopedCallbackPayload(
        { ...payload, worker_id: "" },
        "fixture-signing-material",
      ),
    /signed_cross_owner_callback_identity_unavailable/,
  );
});
