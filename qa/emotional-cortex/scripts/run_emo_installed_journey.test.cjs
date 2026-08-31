"use strict";

const assert = require("node:assert/strict");
const { spawn } = require("node:child_process");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { test } = require("node:test");

const RUNNER = path.join(__dirname, "run_emo_installed_journey.cjs");
const SHARED_COMPUTER_RUNNER = path.resolve(
  __dirname,
  "../../telegram-document-attachments/scripts/run_tgdoc_010_installed_journey.cjs",
);
const OWNER_ID = "1".repeat(24);
const CANDIDATE_DIGEST = "a".repeat(64);
const ARTIFACT_DIGEST = "b".repeat(64);
const COMPONENT_DIGEST = "sha256:" + "c".repeat(64);
const SESSION_REF = "qa_" + "d".repeat(24);
const SKY_SESSION_REF = "sky_emotionalqa1234";
const CASE_047 = "EMO-UC-047";
const CASE_048 = "EMO-UC-048";
const QA_EMAIL = "qa@example.com";
const LOCAL_QA_DOMAIN = "local-qa.invalid";

function testEmail(localPart, domain = LOCAL_QA_DOMAIN) {
  return `${localPart}@${domain}`;
}
const EMO_047_GATES = [
  "installed-owner-and-candidate",
  "exact-live-service-acknowledgements",
  "authoritative-feelings-control",
  "request-pinned-state-and-version",
  "final-layer-capsule-once",
  "winning-native-provider-receipts",
  "direct-worker-scope-parity",
  "telegram-visible-semantic-grounding",
  "fallback-exact-capsule-and-capabilities",
  "phase-b-independent-continuity",
  "specialist-affect-independence",
  "disabled-state-safety",
  "private-state-and-plugin-isolation",
];
const EMO_048_CHECKS = [
  "active-local-qa-authority",
  "all-four-fault-boundaries",
  "exact-insight-identity",
  "restart-service-acknowledgements",
  "append-only-persistence-ledger",
  "exact-presentation-receipts",
  "exactly-once-linked-visibility",
  "typed-terminal-outcome",
];
const BOUNDARIES = [
  "cortex_ledger_first_write",
  "web_replay_persistence",
  "web_redis_publish_ack",
  "telegram_promoted_parent_presentation",
];

function runner() {
  return require(RUNNER);
}

function sha256(value) {
  return crypto.createHash("sha256").update(value).digest("hex");
}

function canonical(value) {
  if (Array.isArray(value)) return "[" + value.map(canonical).join(",") + "]";
  if (value && typeof value === "object") {
    return (
      "{" +
      Object.keys(value)
        .sort()
        .map((key) => JSON.stringify(key) + ":" + canonical(value[key]))
        .join(",") +
      "}"
    );
  }
  return JSON.stringify(value);
}

function owner(overrides = {}) {
  return {
    ownerId: OWNER_ID,
    email: QA_EMAIL,
    role: "USER",
    synthetic: true,
    viventiumApprovalStatus: "approved",
    telegramUserId: "123456789",
    telegramChatId: "-100123456789",
    accountLabel: "Synthetic emotional QA",
    chatLabel: "Synthetic linked chat",
    conversationId: "synthetic_emotional_conversation",
    ...overrides,
  };
}

function identity(caseId = CASE_047) {
  return {
    caseId,
    ownerId: OWNER_ID,
    sessionRef: SESSION_REF,
    candidateDigest: CANDIDATE_DIGEST,
    artifactDigest: ARTIFACT_DIGEST,
    componentArtifactDigest: COMPONENT_DIGEST,
  };
}

function environment(caseId = CASE_047) {
  return {
    VIVENTIUM_QA_ALLOW_INSTALLED_EMOTIONAL_JOURNEY: "1",
    VIVENTIUM_QA_ALLOW_SYNTHETIC_FIXTURES: "1",
    VIVENTIUM_QA_ALLOW_EMOTIONAL_COMPUTER: "1",
    VIVENTIUM_QA_ALLOW_COORDINATED_RESTART: caseId === CASE_048 ? "1" : "0",
    VIVENTIUM_QA_ALLOW_EMOTIONAL_FAULTS: "1",
    VIVENTIUM_QA_OWNER_EMAIL: testEmail("actual-owner", "private.invalid"),
    VIVENTIUM_QA_OWNER_TELEGRAM_USER_ID: "987654321",
    VIVENTIUM_QA_OWNER_TELEGRAM_CHAT_ID: "-100987654321",
    VIVENTIUM_QA_EMAIL: QA_EMAIL,
  };
}

function privateSemanticFixture(root, caseId, overrides = {}) {
  const current = { ...identity(caseId), ...overrides.identity };
  const runAt = new Date().toISOString();
  const artifactIdentityDigest = "sha256:" + "8".repeat(64);
  const ownerScopeHash = "sha256:" + sha256("owner\0" + current.ownerId);
  const entries = [];
  const documents = {};

  function addEvidence(id, kind, payload) {
    const relative = id + (Buffer.isBuffer(payload) ? ".png" : ".json");
    const bytes = Buffer.isBuffer(payload)
      ? payload
      : Buffer.from(JSON.stringify(payload) + "\n", "utf8");
    fs.writeFileSync(path.join(root, relative), bytes, { mode: 0o600 });
    const entry = { kind, path: relative, sha256: sha256(bytes) };
    entries.push(caseId === CASE_048 ? { id, ...entry } : entry);
    if (!Buffer.isBuffer(payload)) documents[id] = payload;
  }

  if (caseId === CASE_047) {
    const shared = {
      caseId,
      contractVersion: 1,
      sessionRef: current.sessionRef,
      artifactIdentityDigest,
      componentArtifactDigest: current.componentArtifactDigest,
    };
    addEvidence("feelings_control_projection", "feelings_control_projection", {
      ...shared,
      synthetic: true,
    });
    addEvidence("feelings_semantic_receipts", "feelings_semantic_receipts", shared);
    addEvidence(
      "feelings_service_acknowledgement",
      "feelings_service_acknowledgement",
      { ...shared, serviceAckDigest: "sha256:" + "9".repeat(64) },
    );
  } else {
    addEvidence("completion-record", "completion_record", {
      caseId,
      ownerId: current.ownerId,
    });
    addEvidence("fault-controls", "fault_controls", {
      caseId,
      fixtureRef: "emo048_fixture_" + "3".repeat(24),
      sessionRef: current.sessionRef,
      controls: BOUNDARIES.map((boundary) => ({
        boundary,
        ownerScopeHash,
        syntheticScope: true,
      })),
    });
    addEvidence("restart-acknowledgements", "restart_acknowledgements", {
      caseId,
      sessionRef: current.sessionRef,
      checkpoints: [
        {
          services: ["librechat-core", "telegram-bot"].map((serviceId) => ({
            caseId,
            serviceId,
            sessionRef: current.sessionRef,
            artifactIdentityDigest,
            componentArtifactDigest: current.componentArtifactDigest,
          })),
        },
      ],
    });
    for (const [id, kind] of [
      ["persistence-ledger", "persistence_ledger"],
      ["presentation-records", "presentation_records"],
      ["visibility-records", "visibility_records"],
      ["terminal-outcome", "terminal_outcome"],
    ]) {
      addEvidence(id, kind, { caseId });
    }
    for (const [id, kind] of [
      ["web-settled", "browser_screenshot"],
      ["web-replayed", "browser_screenshot"],
      ["telegram-settled", "telegram_screenshot"],
      ["telegram-replayed", "telegram_screenshot"],
    ]) {
      addEvidence(id, kind, Buffer.from("synthetic-" + id));
    }
  }

  const manifest =
    caseId === CASE_047
      ? {
          caseId,
          contractVersion: 1,
          environment: "installed_local_production",
          runAt,
          candidate: {
            candidateDigest: current.candidateDigest,
            artifactDigest: current.artifactDigest,
          },
          evidence: entries,
        }
      : {
          capturedAt: runAt,
          caseId,
          contractVersion: 1,
          evidence: entries,
          fixtureRef: "emo048_fixture_" + "3".repeat(24),
        };
  const evidencePath = path.join(
    root,
    caseId === CASE_047 ? "manifest.json" : "capture.json",
  );
  fs.writeFileSync(evidencePath, JSON.stringify(manifest) + "\n", {
    mode: 0o600,
  });
  const receipt = {
    caseId,
    contractVersion: 1,
    evidence: entries
      .map(({ id, ...entry }) => entry)
      .sort((left, right) =>
        left.kind === right.kind
          ? left.path.localeCompare(right.path)
          : left.kind.localeCompare(right.kind),
      ),
    runAt,
    status: "PASS",
    surface: "telegram",
    verifier: {
      id: caseId === CASE_047 ? "emo047-semantic-v1" : "emo048-semantic-v1",
      manifest: path.basename(evidencePath),
    },
  };
  const output =
    caseId === CASE_047
      ? {
          artifactDigest: current.artifactDigest,
          blockers: [],
          candidateDigest: current.candidateDigest,
          caseId,
          contractVersion: 1,
          counts: {
            fallbackAttemptCount: 2,
            mainReceiptCount: 4,
            phaseBReceiptCount: 1,
            scenarioCount: 4,
            semanticPassCount: 4,
            specialistReceiptCount: 5,
            workerReceiptCount: 6,
          },
          gates: EMO_047_GATES.map((id) => ({ id, status: "PASS" })),
          ready: true,
          runAt,
          serviceAckDigest: "sha256:" + "9".repeat(64),
          status: "PASS",
          surface: "telegram",
        }
      : {
          caseId,
          checks: EMO_048_CHECKS.map((id) => ({ id, status: "PASS" })),
          failureCodes: [],
          status: "PASS",
        };

  const serviceAckDigest =
    caseId === CASE_047
      ? output.serviceAckDigest
      : "sha256:" +
        sha256(canonical(documents["restart-acknowledgements"].checkpoints.at(-1).services));
  return {
    current,
    documents,
    evidencePath,
    manifest,
    output,
    receipt,
    runAt,
    serviceStatus: status(caseId, { serviceAckDigest }),
  };
}

function writePrivateVerifierReceipt(args, receipt) {
  const target = args[args.length - 1];
  fs.writeFileSync(target, JSON.stringify(receipt) + "\n", {
    flag: "wx",
    mode: 0o600,
  });
  return target;
}

function rewritePrivateSemanticDocument(fixture, identifier, mutate) {
  const entry = fixture.manifest.evidence.find((item) =>
    Object.hasOwn(item, "id") ? item.id === identifier : item.kind === identifier,
  );
  mutate(fixture.documents[identifier]);
  const location = path.join(path.dirname(fixture.evidencePath), entry.path);
  const bytes = Buffer.from(JSON.stringify(fixture.documents[identifier]) + "\n");
  fs.writeFileSync(location, bytes, { mode: 0o600 });
  entry.sha256 = sha256(bytes);
  fixture.receipt.evidence = fixture.manifest.evidence
    .map(({ id, ...item }) => item)
    .sort((left, right) =>
      left.kind === right.kind
        ? left.path.localeCompare(right.path)
        : left.kind.localeCompare(right.kind),
    );
  fs.writeFileSync(fixture.evidencePath, JSON.stringify(fixture.manifest) + "\n", {
    mode: 0o600,
  });
}

function createComputer(caseId = CASE_047) {
  const { publicKey, privateKey } = crypto.generateKeyPairSync("ed25519");
  const keyId = sha256(publicKey.export({ type: "spki", format: "der" }));
  const peerProcessId = process.ppid > 1 ? process.ppid : process.pid + 100;
  const authority = {
    publicKey,
    keyId,
    peerProcessId,
    sessionRef: SKY_SESSION_REF,
    unitTestHarness: {
      kind: "node_test_only",
      processId: process.pid,
      parentProcessId: process.ppid,
      testFile: __filename,
    },
  };
  const selectedOwner = owner();
  const now = Date.now();
  const unsigned = {
    contractVersion: 1,
    caseId,
    provider: "@oai/sky",
    controlPlane: "computer_plugin_node_repl",
    interface: "sky.get_app_state/sky-primitives",
    skyMethods: ["click", "paste", "press_key"],
    sessionRef: SKY_SESSION_REF,
    qaSessionRef: SESSION_REF,
    ownerId: OWNER_ID,
    telegramUserId: selectedOwner.telegramUserId,
    telegramChatId: selectedOwner.telegramChatId,
    appBundleId: "ru.keepcoder.Telegram",
    peerProcessId,
    authorityKeyId: keyId,
    issuedAtMs: now - 500,
    expiresAtMs: now + 60_000,
  };
  function sign(value) {
    return (
      "ed25519:" +
      crypto
        .sign(null, Buffer.from(canonical(value), "utf8"), privateKey)
        .toString("base64url")
    );
  }
  function selection(overrides = {}) {
    return {
      source: "computer_ui_active_selection",
      observedAtMs: Date.now(),
      account: {
        selected: true,
        evidence: "active_account_control",
        ownerId: OWNER_ID,
        telegramUserId: selectedOwner.telegramUserId,
        label: selectedOwner.accountLabel,
      },
      chat: {
        selected: true,
        evidence: "active_chat_header",
        ownerId: OWNER_ID,
        telegramChatId: selectedOwner.telegramChatId,
        label: selectedOwner.chatLabel,
        conversationRefHash: sha256(selectedOwner.conversationId),
      },
      ...overrides,
    };
  }
  const calls = [];
  const driver = {
    provenance: { ...unsigned, proof: sign(unsigned) },
  };
  for (const method of ["get_app_state", "click", "paste", "press_key"]) {
    driver[method] = async (request) => {
      calls.push({ method, request });
      const observed = {
        contractVersion: 1,
        source: "@oai/sky." + method,
        app: "ru.keepcoder.Telegram",
        caseId,
        ownerId: OWNER_ID,
        telegramUserId: selectedOwner.telegramUserId,
        telegramChatId: selectedOwner.telegramChatId,
        sessionRef: SKY_SESSION_REF,
        qaSessionRef: SESSION_REF,
        peerProcessId,
        challenge: request.challenge,
        requestSha256: sha256(canonical(request)),
        observedAtMs: Date.now(),
        activeSelection: selection(),
      };
      if (request.selectionSha256) {
        observed.selectionSha256 = request.selectionSha256;
      }
      if (request.action) {
        observed.action = request.action;
        observed.skyMethod = request.skyMethod;
        observed.selectionChallenge = request.selectionChallenge;
      }
      if (method === "get_app_state" && request.includeScreenshot === true) {
        const screenshotBytes = Buffer.concat([
          Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
          Buffer.alloc(128, request.phase === "replayed" ? 2 : 1),
        ]);
        observed.screenshotSha256 = sha256(screenshotBytes);
        return { ...observed, screenshotBytes, proof: sign(observed) };
      }
      return { ...observed, proof: sign(observed) };
    };
  }
  driver.do_action = async (request) => {
    const primitive = driver[request.skyMethod];
    if (typeof primitive !== "function") {
      throw new Error("unsupported real Sky primitive");
    }
    return primitive(request);
  };
  return {
    authority,
    privateKey,
    sign,
    driver,
    calls,
    owner: selectedOwner,
    selection,
  };
}

function signedCapabilities(fixture, caseId, handler) {
  return Object.fromEntries(
    ["parent_control", "browser", "glasshive", "evidence"].map((name) => [
      name,
      {
        async invoke(request) {
          const result = await handler(name, request.action, request.payload);
          const unsigned = {
            contractVersion: 1,
            capability: name,
            action: request.action,
            caseId,
            ownerId: OWNER_ID,
            sessionRef: SESSION_REF,
            candidateDigest: CANDIDATE_DIGEST,
            artifactDigest: ARTIFACT_DIGEST,
            componentArtifactDigest: COMPONENT_DIGEST,
            peerProcessId: fixture.authority.peerProcessId,
            challenge: request.challenge,
            requestSha256: sha256(canonical(request)),
            observedAtMs: Date.now(),
            result,
          };
          return { ...unsigned, proof: fixture.sign(unsigned) };
        },
      },
    ]),
  );
}

function status(caseId = CASE_047, overrides = {}) {
  const services =
    caseId === CASE_047
      ? ["glasshive-runtime", "librechat-core"]
      : ["librechat-core", "telegram-bot"];
  return {
    caseId,
    sessionRef: SESSION_REF,
    candidateDigest: CANDIDATE_DIGEST,
    artifactDigest: ARTIFACT_DIGEST,
    componentArtifactDigest: COMPONENT_DIGEST,
    restartState: "ready",
    requiredServices: services,
    acknowledgedServices: [...services],
    missingServices: [],
    serviceAckDigest: "sha256:" + "e".repeat(64),
    ...overrides,
  };
}

function worker(name, snapshotHash, capsuleOccurrenceCount) {
  return {
    ownerId: OWNER_ID,
    workRef: "work_" + sha256(name).slice(0, 24),
    runRef: "run_" + sha256(name + "-run").slice(0, 24),
    snapshotHash,
    capsuleOccurrenceCount,
    nativeReceiptVerified: true,
    privateStateMountCount: 0,
    feelingsMcpServerCount: 0,
    hostPluginDenylistEnabled: true,
  };
}

function pinnedObservations() {
  return {
    ownerId: OWNER_ID,
    scenarios: [
      {
        name: "all_agents_before_delegation",
        scope: "all_agents",
        feelingsEnabled: true,
        snapshotHash: "f".repeat(64),
        main: {
          ownerId: OWNER_ID,
          snapshotHash: "f".repeat(64),
          capsuleOccurrenceCount: 1,
          winningNativeReceiptVerified: true,
        },
        workers: [],
      },
      {
        name: "all_agents_during_workers",
        scope: "all_agents",
        feelingsEnabled: true,
        snapshotHash: "0".repeat(64),
        main: {
          ownerId: OWNER_ID,
          snapshotHash: "0".repeat(64),
          capsuleOccurrenceCount: 1,
          winningNativeReceiptVerified: true,
        },
        workers: [
          worker("all-agents-a", "0".repeat(64), 1),
          worker("all-agents-b", "0".repeat(64), 1),
        ],
      },
      {
        name: "conscious_agent_during_workers",
        scope: "conscious_agent",
        feelingsEnabled: true,
        snapshotHash: "2".repeat(64),
        main: {
          ownerId: OWNER_ID,
          snapshotHash: "2".repeat(64),
          capsuleOccurrenceCount: 1,
          winningNativeReceiptVerified: true,
        },
        workers: [
          worker("conscious-a", "2".repeat(64), 0),
          worker("conscious-b", "2".repeat(64), 0),
        ],
      },
      {
        name: "off_during_workers",
        scope: "all_agents",
        feelingsEnabled: false,
        snapshotHash: "none",
        main: {
          ownerId: OWNER_ID,
          snapshotHash: "none",
          capsuleOccurrenceCount: 0,
          winningNativeReceiptVerified: true,
        },
        workers: [worker("off-a", "none", 0), worker("off-b", "none", 0)],
      },
    ],
    privacyAudit: {
      hostPluginDenylistEnabled: true,
      privateStateMountCount: 0,
      privateStatePersistenceCount: 0,
      privateCapsuleProjectionCount: 0,
      feelingsMcpServerCount: 0,
      workerFeelingsPluginCount: 0,
    },
  };
}

function insightObservations(overrides = {}) {
  return {
    ownerId: OWNER_ID,
    fixtureRef: "emo048_fixture_" + "3".repeat(24),
    graph: {
      status: "completed",
      completionId: "completion_" + "4".repeat(24),
      resultSha256: "5".repeat(64),
    },
    firstFailure: {
      errorCode: "cortex_insight_delivery_ledger_write_failed",
      retryable: true,
      outboxState: "pending",
      terminalPresentationCount: 0,
    },
    boundaries: BOUNDARIES.map((boundary) => ({ boundary, state: "consumed" })),
    restart: {
      parentAuthorized: true,
      beforeCoreProcessRefHash: "6".repeat(64),
      afterCoreProcessRefHash: "7".repeat(64),
      beforeServiceAckDigest: "sha256:" + "8".repeat(64),
      afterServiceAckDigest: "sha256:" + "9".repeat(64),
      occurredWhilePending: true,
    },
    delivery: {
      status: "sent",
      resultSha256: "5".repeat(64),
      presentationCount: 1,
      messageId: "message_" + "a".repeat(24),
      surfaces: [
        { surface: "web", visibleCount: 1, ownerId: OWNER_ID },
        { surface: "telegram", visibleCount: 1, ownerId: OWNER_ID },
      ],
    },
    replay: {
      resultSha256: "5".repeat(64),
      presentationCount: 1,
      messageId: "message_" + "a".repeat(24),
      surfaces: [
        { surface: "web", visibleCount: 1, ownerId: OWNER_ID },
        { surface: "telegram", visibleCount: 1, ownerId: OWNER_ID },
      ],
    },
    terminalProbe: {
      status: "dropped",
      reason: "presentation_permanently_rejected",
    },
    ...overrides,
  };
}

test("defaults to a non-mutating EMO-UC-047 dry run", () => {
  const args = runner().parseArguments([]);
  assert.equal(args.caseId, CASE_047);
  assert.equal(args.mode, "dry-run");
  assert.deepEqual(runner().dryRunPlan(args), {
    caseId: CASE_047,
    status: "DRY_RUN",
    sideEffects: false,
    invokesModels: false,
    opensBrowser: false,
    mutatesAccount: false,
    restartsRuntime: false,
    releaseReady: false,
    receiptEligible: false,
    releaseLabel: "PRE-GATE / NOT READY",
    independentVerifier: "run_emo_uc_047.py",
  });
});

test("selects EMO-UC-048 without enabling a live journey", () => {
  const args = runner().parseArguments(["--case=EMO-UC-048"]);
  assert.equal(args.mode, "dry-run");
  assert.equal(
    runner().dryRunPlan(args).independentVerifier,
    "run_emo_uc_048.py",
  );
});

test("rejects unsupported cases, duplicate arguments, and conflicting modes", () => {
  assert.throws(
    () => runner().parseArguments(["--case=EMO-UC-049"]),
    /unsupported_case/,
  );
  assert.throws(
    () => runner().parseArguments(["--case=EMO-UC-047", "--case=EMO-UC-048"]),
    /duplicate_argument/,
  );
  assert.throws(
    () => runner().parseArguments(["--dry-run", "--live"]),
    /conflicting_execution_modes/,
  );
});

test("requires separate installed, synthetic-account, and Computer consent", () => {
  const args = { mode: "live", caseId: CASE_047, qaEmail: owner().email };
  for (const name of [
    "VIVENTIUM_QA_ALLOW_INSTALLED_EMOTIONAL_JOURNEY",
    "VIVENTIUM_QA_ALLOW_SYNTHETIC_FIXTURES",
    "VIVENTIUM_QA_ALLOW_EMOTIONAL_COMPUTER",
  ]) {
    const env = environment();
    delete env[name];
    assert.throws(
      () => runner().assertLiveOptIn(args, env),
      /requires_explicit|consent_required|computer_consent_required/,
    );
  }
});

test("EMO-UC-048 requires explicit parent-controlled restart and fault consent", () => {
  const args = {
    mode: "live",
    caseId: CASE_048,
    qaEmail: owner().email,
    allowRestart: false,
  };
  assert.throws(
    () => runner().assertLiveOptIn(args, environment(CASE_048)),
    /coordinated_restart_requires_explicit_permission/,
  );
  args.allowRestart = true;
  const denied = environment(CASE_048);
  delete denied.VIVENTIUM_QA_ALLOW_EMOTIONAL_FAULTS;
  assert.throws(
    () => runner().assertLiveOptIn(args, denied),
    /emotional_faults_require_explicit_permission/,
  );
});

test("EMO-UC-047 requires explicit consent for its parent-controlled provider fault", () => {
  const args = { mode: "live", caseId: CASE_047, qaEmail: owner().email };
  const env = environment();
  delete env.VIVENTIUM_QA_ALLOW_EMOTIONAL_FAULTS;
  assert.throws(
    () => runner().assertLiveOptIn(args, env),
    /emotional_faults_require_explicit_permission/,
  );
});

test("refuses the real owner even if that account is falsely marked synthetic", () => {
  const env = environment();
  const real = owner({ email: env.VIVENTIUM_QA_OWNER_EMAIL, synthetic: true });
  assert.throws(
    () =>
      runner().assertSyntheticOwner(real, {
        ...env,
        VIVENTIUM_QA_EMAIL: real.email,
      }),
    /personal_owner_account_refused/,
  );
});

test("rejects administrator, unmarked, unrelated, and non-synthetic-domain accounts", () => {
  for (const [candidate, expected] of [
    [owner({ role: "ADMIN" }), /admin_account_refused/],
    [owner({ synthetic: false }), /explicit_synthetic_owner_required/],
    [
      owner({ email: "different@example.com" }),
      /configured_synthetic_owner_mismatch/,
    ],
    [
      owner({ email: testEmail("someone", "business.invalid") }),
      /synthetic_qa_account_required/,
    ],
  ]) {
    const env = environment();
    if (candidate.email.endsWith("business.invalid"))
      env.VIVENTIUM_QA_EMAIL = candidate.email;
    assert.throws(
      () => runner().assertSyntheticOwner(candidate, env),
      expected,
    );
  }
});

test("requires the explicit non-administrator USER role", () => {
  for (const role of [undefined, "OWNER", "SUPERADMIN", "service_account"]) {
    assert.throws(
      () => runner().assertSyntheticOwner(owner({ role }), environment()),
      /non_admin_synthetic_role_required/,
    );
  }
});

test("accepts the canonical parent-generated local-qa.invalid synthetic owner", () => {
  const candidate = owner({
    email: testEmail("emo-uc-048-" + "a".repeat(32)),
  });
  const env = { ...environment(CASE_048), VIVENTIUM_QA_EMAIL: candidate.email };
  assert.equal(runner().assertSyntheticOwner(candidate, env).ownerId, OWNER_ID);
});

test("refuses the canonical EMO-UC-048 disposable owner for another case", () => {
  const candidate = owner({
    email: testEmail("emo-uc-048-" + "a".repeat(32)),
  });
  assert.throws(
    () =>
      runner().assertSyntheticOwner(
        candidate,
        { ...environment(), VIVENTIUM_QA_EMAIL: candidate.email },
        OWNER_ID,
        CASE_047,
      ),
    /synthetic_qa_account_required/,
  );
});

test("rejects ordinary configured example.com and viventium.local identities without explicit approval", () => {
  for (const email of ["ordinary@example.com", "ordinary@viventium.local"]) {
    const candidate = owner({ email, viventiumApprovalStatus: undefined });
    const env = { ...environment(), VIVENTIUM_QA_EMAIL: email };
    assert.throws(
      () => runner().assertSyntheticOwner(candidate, env),
      /approved_synthetic_owner_required|synthetic_qa_account_required/,
    );
  }
});

test("rejects approved identities on ordinary non-installed synthetic domains", () => {
  for (const email of ["approved@viventium.local", "approved@localhost"]) {
    const candidate = owner({ email });
    assert.throws(
      () =>
        runner().assertSyntheticOwner(candidate, {
          ...environment(),
          VIVENTIUM_QA_EMAIL: email,
        }),
      /synthetic_qa_account_required/,
    );
  }
});

test("rejects noncanonical configured local-qa.invalid destructive fixture identities", () => {
  for (const email of [
    testEmail("ordinary"),
    testEmail("emo-uc-048-short"),
    testEmail("emo-uc-047-" + "a".repeat(32)),
    testEmail("emo-uc-048-" + "a".repeat(31)),
    testEmail("emo-uc-048-" + "a".repeat(33)),
  ]) {
    const candidate = owner({ email, viventiumApprovalStatus: "approved" });
    const env = { ...environment(CASE_048), VIVENTIUM_QA_EMAIL: email };
    assert.throws(
      () => runner().assertSyntheticOwner(candidate, env),
      /synthetic_qa_account_required/,
    );
  }
});

test("rejects configured synthetic accounts that are unapproved, locked, or banned", () => {
  for (const overrides of [
    { viventiumApprovalStatus: "pending" },
    { viventiumApprovalStatus: "denied" },
    { viventiumApprovalStatus: "approved", locked: true },
    { viventiumApprovalStatus: "approved", isLocked: true },
    { viventiumApprovalStatus: "approved", banned: true },
  ]) {
    assert.throws(
      () => runner().assertSyntheticOwner(owner(overrides), environment()),
      /approved_synthetic_owner_required|locked_qa_account_refused/,
    );
  }
});

test("requires explicit personal Telegram guards and rejects either personal Telegram identity", () => {
  for (const missing of [
    "VIVENTIUM_QA_OWNER_TELEGRAM_USER_ID",
    "VIVENTIUM_QA_OWNER_TELEGRAM_CHAT_ID",
  ]) {
    const env = environment();
    delete env[missing];
    assert.throws(
      () => runner().assertSyntheticOwner(owner(), env),
      /personal_owner_identity_guard_required/,
    );
  }
  const env = environment();
  assert.throws(
    () =>
      runner().assertSyntheticOwner(
        owner({ telegramUserId: env.VIVENTIUM_QA_OWNER_TELEGRAM_USER_ID }),
        env,
      ),
    /personal_telegram_account_refused/,
  );
  assert.throws(
    () =>
      runner().assertSyntheticOwner(
        owner({ telegramChatId: env.VIVENTIUM_QA_OWNER_TELEGRAM_CHAT_ID }),
        env,
      ),
    /personal_telegram_chat_refused/,
  );
});

test("accepts only the exact approved configured example.com owner", () => {
  assert.equal(runner().assertSyntheticOwner(owner(), environment()).ownerId, OWNER_ID);
  assert.throws(
    () =>
      runner().assertSyntheticOwner(owner({ email: "ordinary@example.com" }), environment()),
    /configured_synthetic_owner_mismatch/,
  );
});

test("accepts only an external parent-owned Ed25519 authority", () => {
  const fixture = createComputer();
  assert.equal(
    runner().assertExternalAuthority(fixture.authority).keyId,
    fixture.authority.keyId,
  );
  assert.throws(
    () =>
      runner().assertExternalAuthority({
        ...fixture.authority,
        peerProcessId: process.pid,
      }),
    /external_computer_authority_required/,
  );
  const rsa = crypto.generateKeyPairSync("rsa", {
    modulusLength: 2048,
  }).publicKey;
  assert.throws(
    () =>
      runner().assertExternalAuthority({
        ...fixture.authority,
        publicKey: rsa,
      }),
    /external_computer_authority_required/,
  );
});

test("uses the final shared trusted Computer adapter without inventing runner-side Sky primitives", async () => {
  const fixture = createComputer();
  const primitives = new Map(
    ["click", "paste", "press_key"].map((name) => [name, fixture.driver[name]]),
  );
  const parentDriver = {
    provenance: fixture.driver.provenance,
    get_app_state: fixture.driver.get_app_state,
    async do_action(request) {
      const primitive = primitives.get(request.skyMethod);
      if (!primitive) throw new Error("unsupported real Sky primitive");
      return primitive(request);
    },
  };
  const trusted = runner().assertParentOwnedComputerBridge(
    parentDriver,
    fixture.owner,
    identity(),
    fixture.authority,
  );
  assert.equal(trusted.binding.caseId, CASE_047);
  assert.equal(trusted.binding.ownerId, OWNER_ID);
  const observed = await require(SHARED_COMPUTER_RUNNER).observeTrustedComputer(
    trusted,
    { kind: "state" },
  );
  assert.equal(observed.ownerId, OWNER_ID);
  assert.equal(observed.source, "@oai/sky.get_app_state");
});

test("rejects caller-generated Ed25519 keys that merely claim an unrelated live parent PID", async () => {
  const fixture = createComputer();
  await assert.rejects(
    () => runner().assertIndependentParentComputerAuthority(fixture.authority),
    /independent_parent_computer_authority_unavailable/,
  );
});

test("authenticates separate signed parent IPC but never promotes its test harness into installed authority", async (t) => {
  const signer = crypto.generateKeyPairSync("ed25519");
  const publicKey = signer.publicKey.export({ type: "spki", format: "der" });
  const keyId = sha256(publicKey);
  const childSource = [
    "'use strict';",
    "const crypto=require('node:crypto');",
    "const journey=require(process.argv[1]);",
    "const shared=require(process.argv[2]);",
    "process.once('message',async(input)=>{",
    "try{",
    "const authority={publicKey:crypto.createPublicKey({key:Buffer.from(input.publicKey,'base64url'),format:'der',type:'spki'}),keyId:input.keyId,peerProcessId:process.ppid,sessionRef:input.sessionRef,transport:{kind:'inherited_parent_ipc',controlPlane:'computer_plugin_node_repl',parentProcessId:process.ppid,channel:process.channel,unitTestHarness:input.unitTestHarness}};",
    "await shared.authenticateParentComputerAuthority(authority,{timeoutMs:2000});",
    "try{await journey.assertIndependentParentComputerAuthority(authority);process.send({type:'fixture.result',authenticated:true,accepted:true})}catch(error){process.send({type:'fixture.result',authenticated:true,accepted:false,blocker:error.message,parentProcessId:authority.peerProcessId})}",
    "}catch(error){process.send({type:'fixture.result',authenticated:false,accepted:false,blocker:error.message})}",
    "});",
  ].join("");
  const child = spawn(
    process.execPath,
    ["-e", childSource, RUNNER, SHARED_COMPUTER_RUNNER],
    {
      cwd: path.resolve(__dirname, "../../.."),
      env: { PATH: process.env.PATH || "" },
      stdio: ["ignore", "pipe", "pipe", "ipc"],
    },
  );
  t.after(() => {
    if (child.connected) child.disconnect();
    if (child.exitCode === null) child.kill();
  });
  const result = await new Promise((resolve, reject) => {
    const timer = setTimeout(
      () => reject(new Error("external parent IPC authentication timed out")),
      4000,
    );
    child.on("error", (error) => {
      clearTimeout(timer);
      reject(error);
    });
    child.on("message", (message) => {
      if (message.type === "viventium.computer.authority.challenge.v1") {
        const now = Date.now();
        const response = {
          type: "viventium.computer.authority.response.v1",
          contractVersion: 1,
          controlPlane: message.controlPlane,
          challenge: message.challenge,
          runnerProcessId: message.runnerProcessId,
          parentProcessId: message.parentProcessId,
          parentIdentityDigest: message.parentIdentityDigest,
          authorityKeyId: message.authorityKeyId,
          sessionRef: message.sessionRef,
          issuedAtMs: now,
          expiresAtMs: now + 30_000,
        };
        child.send({
          ...response,
          proof:
            "ed25519:" +
            crypto
              .sign(null, Buffer.from(canonical(response)), signer.privateKey)
              .toString("base64url"),
        });
        return;
      }
      if (message.type === "fixture.result") {
        clearTimeout(timer);
        resolve(message);
      }
    });
    child.send({
      publicKey: publicKey.toString("base64url"),
      keyId,
      sessionRef: SKY_SESSION_REF,
      unitTestHarness: {
        kind: "node_test_only_parent_transport",
        parentProcessId: process.pid,
        grandparentProcessId: process.ppid,
        testFile: __filename,
      },
    });
  });
  assert.equal(result.authenticated, true, result.blocker);
  assert.equal(result.accepted, false);
  assert.match(
    result.blocker,
    /independent_parent_computer_authority_unavailable/,
  );
  assert.equal(result.parentProcessId, process.pid);
});

test("rejects Ed25519 provenance signed by a caller-controlled replacement key", () => {
  const fixture = createComputer();
  const attacker = crypto.generateKeyPairSync("ed25519").privateKey;
  const { proof, ...unsigned } = fixture.driver.provenance;
  void proof;
  fixture.driver.provenance.proof =
    "ed25519:" +
    crypto
      .sign(null, Buffer.from(canonical(unsigned), "utf8"), attacker)
      .toString("base64url");
  assert.throws(
    () =>
      runner().assertParentOwnedComputerBridge(
        fixture.driver,
        fixture.owner,
        identity(),
        fixture.authority,
      ),
    /computer_bridge_authentication_failed/,
  );
});

test("rejects an imaginary Sky method contract", () => {
  const fixture = createComputer();
  const unsigned = {
    ...fixture.driver.provenance,
    interface: "sky.get_app_state/imaginary_action",
  };
  delete unsigned.proof;
  fixture.driver.provenance = { ...unsigned, proof: fixture.sign(unsigned) };
  assert.throws(
    () =>
      runner().assertParentOwnedComputerBridge(
        fixture.driver,
        fixture.owner,
        identity(),
        fixture.authority,
      ),
    /computer_bridge_provenance_invalid/,
  );
});

test("rejects undeclared real Sky primitives even when parent provenance is signed", () => {
  const fixture = createComputer();
  const unsigned = {
    ...fixture.driver.provenance,
    skyMethods: ["click", "press_key"],
  };
  delete unsigned.proof;
  fixture.driver.provenance = { ...unsigned, proof: fixture.sign(unsigned) };
  assert.throws(
    () =>
      runner().assertParentOwnedComputerBridge(
        fixture.driver,
        fixture.owner,
        identity(),
        fixture.authority,
      ),
    /computer_bridge_provenance_invalid/,
  );
});

test("requires the shared Sky state reader and authenticated parent-owned dispatcher", () => {
  for (const name of ["get_app_state", "do_action"]) {
    const fixture = createComputer();
    delete fixture.driver[name];
    assert.throws(
      () =>
        runner().assertParentOwnedComputerBridge(
          fixture.driver,
          fixture.owner,
          identity(),
          fixture.authority,
        ),
      /computer_bridge_unavailable/,
    );
  }
});

test("rejects a signed Computer bridge bound to another owner or QA session", () => {
  for (const updates of [
    { ownerId: "2".repeat(24) },
    { qaSessionRef: "qa_" + "f".repeat(24) },
  ]) {
    const fixture = createComputer();
    const unsigned = { ...fixture.driver.provenance, ...updates };
    delete unsigned.proof;
    fixture.driver.provenance = { ...unsigned, proof: fixture.sign(unsigned) };
    assert.throws(
      () =>
        runner().assertParentOwnedComputerBridge(
          fixture.driver,
          fixture.owner,
          identity(),
          fixture.authority,
        ),
      /computer_bridge_owner_mismatch|computer_bridge_session_mismatch/,
    );
  }
});

test("rejects expired signed Computer provenance", () => {
  const fixture = createComputer();
  const unsigned = {
    ...fixture.driver.provenance,
    expiresAtMs: Date.now() - 1,
  };
  delete unsigned.proof;
  fixture.driver.provenance = { ...unsigned, proof: fixture.sign(unsigned) };
  assert.throws(
    () =>
      runner().assertParentOwnedComputerBridge(
        fixture.driver,
        fixture.owner,
        identity(),
        fixture.authority,
      ),
    /computer_bridge_attestation_expired/,
  );
});

test("rejects a visible but not actively selected Telegram account", () => {
  const fixture = createComputer();
  const selection = fixture.selection();
  selection.account.selected = false;
  assert.throws(
    () => runner().assertActiveOwnerChat(selection, fixture.owner),
    /active_telegram_account_mismatch/,
  );
});

test("rejects a visible but different active Telegram chat", () => {
  const fixture = createComputer();
  const selection = fixture.selection();
  selection.chat.telegramChatId = "-100999999999";
  assert.throws(
    () => runner().assertActiveOwnerChat(selection, fixture.owner),
    /active_telegram_chat_mismatch/,
  );
});

test("rejects stale active-owner and chat observations", () => {
  const fixture = createComputer();
  assert.throws(
    () =>
      runner().assertActiveOwnerChat(
        fixture.selection({ observedAtMs: Date.now() - 6000 }),
        fixture.owner,
      ),
    /active_telegram_selection_stale/,
  );
});

test("uses a fresh signed owner/chat selection before every actual Sky mutation", async () => {
  const fixture = createComputer();
  const bridge = runner().assertParentOwnedComputerBridge(
    fixture.driver,
    fixture.owner,
    identity(),
    fixture.authority,
  );
  await runner().sendTelegramText(
    bridge,
    fixture.owner,
    "Synthetic user question",
  );
  assert.deepEqual(
    fixture.calls.map(({ method }) => method),
    ["get_app_state", "paste", "get_app_state", "press_key"],
  );
  assert.notEqual(
    fixture.calls[0].request.challenge,
    fixture.calls[2].request.challenge,
  );
  assert.match(fixture.calls[1].request.selectionSha256, /^[a-f0-9]{64}$/);
  assert.match(fixture.calls[3].request.selectionSha256, /^[a-f0-9]{64}$/);
});

test("rejects a forged or replayed per-action Computer receipt", async () => {
  const fixture = createComputer();
  const bridge = runner().assertParentOwnedComputerBridge(
    fixture.driver,
    fixture.owner,
    identity(),
    fixture.authority,
  );
  const original = fixture.driver.get_app_state;
  fixture.driver.get_app_state = async (request) => {
    const result = await original(request);
    return { ...result, challenge: "f".repeat(64) };
  };
  await assert.rejects(
    () => runner().observeComputer(bridge, fixture.owner, "get_app_state"),
    /computer_observation_challenge_mismatch/,
  );
});

test("rejects a signed Computer receipt for different action text or key input", async () => {
  const fixture = createComputer();
  const bridge = runner().assertParentOwnedComputerBridge(
    fixture.driver,
    fixture.owner,
    identity(),
    fixture.authority,
  );
  const original = fixture.driver.paste;
  fixture.driver.paste = async (request) => {
    const result = await original(request);
    const unsigned = { ...result, requestSha256: sha256("different action") };
    delete unsigned.proof;
    return { ...unsigned, proof: fixture.sign(unsigned) };
  };
  await assert.rejects(
    () =>
      runner().observeComputer(bridge, fixture.owner, "paste", {
        text: "expected text",
      }),
    /computer_observation_request_mismatch/,
  );
});

test("requires a genuine signed owner-bound Telegram screenshot for each insight delivery phase", async () => {
  const fixture = createComputer(CASE_048);
  const bridge = runner().assertParentOwnedComputerBridge(
    fixture.driver,
    fixture.owner,
    identity(CASE_048),
    fixture.authority,
  );
  const observed = await runner().observeComputer(
    bridge,
    fixture.owner,
    "get_app_state",
    { phase: "settled", includeScreenshot: true },
  );
  assert.equal(
    runner().assertObservedTelegramScreenshot(observed).screenshotSha256,
    observed.screenshotSha256,
  );
  for (const invalid of [
    { ...observed, screenshotBytes: undefined },
    { ...observed, screenshotBytes: Buffer.from("not a screenshot") },
    { ...observed, screenshotSha256: "9".repeat(64) },
  ]) {
    assert.throws(
      () => runner().assertObservedTelegramScreenshot(invalid),
      /private_installed_surface_capture_unavailable/,
    );
  }
});

test("requires exact candidate-bound live service acknowledgements", () => {
  assert.equal(
    runner().assertExactServiceAcknowledgements(status(), identity())
      .serviceCount,
    2,
  );
  assert.throws(
    () =>
      runner().assertExactServiceAcknowledgements(
        status(CASE_047, { acknowledgedServices: ["librechat-core"] }),
        identity(),
      ),
    /exact_service_acknowledgements_unavailable/,
  );
  assert.throws(
    () =>
      runner().assertExactServiceAcknowledgements(
        status(CASE_047, { candidateDigest: "f".repeat(64) }),
        identity(),
      ),
    /candidate_or_session_binding_invalid/,
  );
  assert.throws(
    () =>
      runner().assertExactServiceAcknowledgements(
        status(CASE_047, { serviceAckDigest: "sha256:" + "x".repeat(64) }),
        identity(),
      ),
    /exact_service_acknowledgements_unavailable/,
  );
});

test("accepts four scope scenarios with one pinned Main capsule and exact direct Worker parity", () => {
  assert.deepEqual(
    runner().assessPinnedCapsules(pinnedObservations(), OWNER_ID),
    {
      scenarioCount: 4,
      mainReceiptCount: 4,
      workerReceiptCount: 6,
      allAgentsDirectWorkerCount: 2,
      pinned: true,
    },
  );
});

test("rejects a missing, duplicate, or contradictory direct Worker Feeling capsule", () => {
  for (const change of [
    (value) => {
      value.scenarios[1].workers[0].capsuleOccurrenceCount = 0;
    },
    (value) => {
      value.scenarios[1].workers[0].capsuleOccurrenceCount = 2;
    },
    (value) => {
      value.scenarios[1].workers[0].snapshotHash = "f".repeat(64);
    },
    (value) => {
      value.scenarios[1].workers[0].nativeReceiptVerified = false;
    },
  ]) {
    const observation = pinnedObservations();
    change(observation);
    assert.throws(
      () => runner().assessPinnedCapsules(observation, OWNER_ID),
      /direct_worker_pinned_capsule_invalid/,
    );
  }
});

test("rejects conscious-only or disabled capsules reaching direct Workers", () => {
  for (const index of [2, 3]) {
    const observation = pinnedObservations();
    observation.scenarios[index].workers[0].capsuleOccurrenceCount = 1;
    assert.throws(
      () => runner().assessPinnedCapsules(observation, OWNER_ID),
      /direct_worker_scope_violation/,
    );
  }
});

test("preserves the Feelings plugin denylist and blocks private state projection", () => {
  for (const change of [
    (value) => {
      value.privacyAudit.hostPluginDenylistEnabled = false;
    },
    (value) => {
      value.privacyAudit.privateStateMountCount = 1;
    },
    (value) => {
      value.scenarios[1].workers[0].feelingsMcpServerCount = 1;
    },
  ]) {
    const observation = pinnedObservations();
    change(observation);
    assert.throws(
      () => runner().assessPinnedCapsules(observation, OWNER_ID),
      /feelings_private_state_isolation_failed/,
    );
  }
});

test("accepts a completed insight that survives failure, restart, recovery, and replay exactly once", () => {
  assert.deepEqual(
    runner().assessInsightRecovery(insightObservations(), OWNER_ID),
    {
      boundaries: 4,
      completed: true,
      restartedWhilePending: true,
      surfaces: 2,
      deliveredExactlyOnce: true,
      replayDuplicated: false,
      typedTerminalProbe: true,
    },
  );
});

test("rejects recovery without the real completed graph or first typed persistence failure", () => {
  const incomplete = insightObservations();
  incomplete.graph.status = "running";
  assert.throws(
    () => runner().assessInsightRecovery(incomplete, OWNER_ID),
    /completed_emotional_insight_unavailable/,
  );
  const noFailure = insightObservations();
  noFailure.firstFailure.retryable = false;
  assert.throws(
    () => runner().assessInsightRecovery(noFailure, OWNER_ID),
    /first_persistence_failure_unproven/,
  );
});

test("rejects missing fault boundaries and a restart after terminal delivery", () => {
  const missing = insightObservations();
  missing.boundaries.pop();
  assert.throws(
    () => runner().assessInsightRecovery(missing, OWNER_ID),
    /all_emotional_fault_boundaries_required/,
  );
  const late = insightObservations();
  late.restart.occurredWhilePending = false;
  assert.throws(
    () => runner().assessInsightRecovery(late, OWNER_ID),
    /authorized_pending_core_restart_unproven/,
  );
});

test("rejects unchanged Core identity, synthetic restart declarations, and stale acknowledgements", () => {
  for (const change of [
    (value) => {
      value.restart.afterCoreProcessRefHash =
        value.restart.beforeCoreProcessRefHash;
    },
    (value) => {
      value.restart.parentAuthorized = false;
    },
    (value) => {
      value.restart.afterServiceAckDigest =
        value.restart.beforeServiceAckDigest;
    },
  ]) {
    const observation = insightObservations();
    change(observation);
    assert.throws(
      () => runner().assessInsightRecovery(observation, OWNER_ID),
      /authorized_pending_core_restart_unproven/,
    );
  }
});

test("rejects duplicate, cross-owner, mismatched, or missing linked-surface insight delivery", () => {
  for (const change of [
    (value) => {
      value.delivery.presentationCount = 2;
    },
    (value) => {
      value.delivery.surfaces[0].ownerId = "2".repeat(24);
    },
    (value) => {
      value.delivery.surfaces.pop();
    },
    (value) => {
      value.delivery.resultSha256 = "7".repeat(64);
    },
  ]) {
    const observation = insightObservations();
    change(observation);
    assert.throws(
      () => runner().assessInsightRecovery(observation, OWNER_ID),
      /linked_insight_delivery_not_exactly_once/,
    );
  }
});

test("rejects replay duplication and an untyped terminal drop", () => {
  const replay = insightObservations();
  replay.replay.surfaces[1].visibleCount = 2;
  assert.throws(
    () => runner().assessInsightRecovery(replay, OWNER_ID),
    /insight_replay_was_not_idempotent/,
  );
  const terminal = insightObservations();
  terminal.terminalProbe.reason = "private user content";
  assert.throws(
    () => runner().assessInsightRecovery(terminal, OWNER_ID),
    /typed_terminal_drop_unproven/,
  );
});

test("refuses evidence inside the public repository", () => {
  assert.throws(
    () => runner().assertPrivateEvidenceRoot(__dirname),
    /private_evidence_must_stay_outside_repository/,
  );
});

test("refuses public, missing, or symlinked externally produced evidence", () => {
  const root = fs.mkdtempSync(
    path.join(os.tmpdir(), "viventium-emo-installed-"),
  );
  fs.chmodSync(root, 0o700);
  try {
    const real = path.join(root, "real.json");
    fs.writeFileSync(real, "{}\n", { mode: 0o600 });
    fs.chmodSync(real, 0o644);
    assert.throws(
      () => runner().assertExistingPrivateEvidence(real, root),
      /private_evidence_permissions_invalid/,
    );
    fs.chmodSync(real, 0o600);
    const linked = path.join(root, "linked.json");
    fs.symlinkSync(real, linked);
    assert.throws(
      () => runner().assertExistingPrivateEvidence(linked, root),
      /private_evidence_path_invalid/,
    );
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test("rejects symlinked and nonprivate intermediate evidence directories", () => {
  const root = fs.mkdtempSync(
    path.join(os.tmpdir(), "viventium-emo-private-path-"),
  );
  fs.chmodSync(root, 0o700);
  try {
    const nested = path.join(root, "nested");
    fs.mkdirSync(nested, { mode: 0o700 });
    const evidence = path.join(nested, "evidence.json");
    fs.writeFileSync(evidence, "{}\n", { mode: 0o600 });
    fs.chmodSync(nested, 0o755);
    assert.throws(
      () => runner().assertExistingPrivateEvidence(evidence, root),
      /private_evidence_permissions_invalid/,
    );
    fs.chmodSync(nested, 0o700);
    const alias = path.join(root, "alias");
    fs.symlinkSync(nested, alias);
    assert.throws(
      () =>
        runner().assertExistingPrivateEvidence(
          path.join(alias, "evidence.json"),
          root,
        ),
      /private_evidence_permissions_invalid|private_evidence_path_invalid/,
    );
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test("invokes the existing independent EMO-UC-047 semantic verifier", () => {
  const root = fs.mkdtempSync(
    path.join(os.tmpdir(), "viventium-emo-installed-"),
  );
  fs.chmodSync(root, 0o700);
  try {
    const evidence = privateSemanticFixture(root, CASE_047);
    let observed;
    const result = runner().runIndependentVerifier(CASE_047, {
      evidenceRoot: root,
      evidencePath: evidence.evidencePath,
      identity: identity(),
      owner: owner(),
      serviceStatus: evidence.serviceStatus,
      spawn(command, args, options) {
        observed = { command, args, options };
        writePrivateVerifierReceipt(args, evidence.receipt);
        return {
          status: 0,
          stdout: JSON.stringify(evidence.output),
          stderr: "",
        };
      },
    });
    assert.equal(result.status, "PASS");
    assert.equal(observed.command, "python3");
    assert.equal(observed.args[0], "-c");
    assert.match(observed.args[2], /run_emo_uc_047\.py$/);
    assert.equal(observed.args[3], fs.realpathSync(evidence.evidencePath));
    assert.equal(observed.args[4], fs.realpathSync(root));
    assert.equal(path.dirname(observed.args[5]), fs.realpathSync(root));
    assert.equal(result.candidateDigest, CANDIDATE_DIGEST);
    assert.equal(result.artifactDigest, ARTIFACT_DIGEST);
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test("invokes the existing independent EMO-UC-048 semantic verifier and its private receipt", () => {
  const root = fs.mkdtempSync(
    path.join(os.tmpdir(), "viventium-emo-installed-"),
  );
  fs.chmodSync(root, 0o700);
  try {
    const evidence = privateSemanticFixture(root, CASE_048);
    let observed;
    const result = runner().runIndependentVerifier(CASE_048, {
      evidenceRoot: root,
      evidencePath: evidence.evidencePath,
      identity: identity(CASE_048),
      owner: owner(),
      serviceStatus: evidence.serviceStatus,
      fixtureRef: evidence.manifest.fixtureRef,
      spawn(command, args) {
        observed = { command, args };
        writePrivateVerifierReceipt(args, evidence.receipt);
        return {
          status: 0,
          stdout: JSON.stringify(evidence.output),
          stderr: "",
        };
      },
    });
    assert.match(observed.args[0], /run_emo_uc_048\.py$/);
    assert.deepEqual(observed.args.slice(1, 5), [
      "--capture",
      fs.realpathSync(evidence.evidencePath),
      "--evidence-root",
      fs.realpathSync(root),
    ]);
    assert.equal(observed.args[5], "--receipt");
    assert.equal(path.dirname(observed.args[6]), fs.realpathSync(root));
    assert.deepEqual(result, evidence.output);
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test("refuses failed, malformed, cross-case, or caller-declared semantic PASS", () => {
  const root = fs.mkdtempSync(
    path.join(os.tmpdir(), "viventium-emo-installed-"),
  );
  fs.chmodSync(root, 0o700);
  try {
    const evidencePath = path.join(root, "manifest.json");
    fs.writeFileSync(evidencePath, "{}\n", { mode: 0o600 });
    for (const output of [
      {
        status: 2,
        stdout: JSON.stringify({ caseId: CASE_047, status: "BLOCKED" }),
      },
      {
        status: 0,
        stdout: JSON.stringify({ caseId: CASE_048, status: "PASS" }),
      },
      {
        status: 0,
        stdout: JSON.stringify({ caseId: CASE_047, status: "PARTIAL" }),
      },
      { status: 0, stdout: "not json" },
    ]) {
      assert.throws(
        () =>
          runner().runIndependentVerifier(CASE_047, {
            evidenceRoot: root,
            evidencePath,
            identity: identity(),
            owner: owner(),
            serviceStatus: status(),
            spawn: () => ({ stderr: "", ...output }),
          }),
        /independent_semantic_verifier_did_not_pass/,
      );
    }
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test("rejects forged semantic PASS output when no private verifier receipt was generated", () => {
  for (const caseId of [CASE_047, CASE_048]) {
    const root = fs.mkdtempSync(
      path.join(os.tmpdir(), "viventium-emo-forged-receipt-"),
    );
    fs.chmodSync(root, 0o700);
    try {
      const evidence = privateSemanticFixture(root, caseId);
      assert.throws(
        () =>
          runner().runIndependentVerifier(caseId, {
            evidenceRoot: root,
            evidencePath: evidence.evidencePath,
            identity: identity(caseId),
            owner: owner(),
            serviceStatus: evidence.serviceStatus,
            fixtureRef: evidence.manifest.fixtureRef,
            spawn: () => ({
              status: 0,
              stdout: JSON.stringify(evidence.output),
              stderr: "",
            }),
          }),
        /independent_semantic_verifier_did_not_pass/,
      );
    } finally {
      fs.rmSync(root, { recursive: true, force: true });
    }
  }
});

test("rejects forged semantic PASS output for another owner, session, candidate, or artifact", () => {
  for (const caseId of [CASE_047, CASE_048]) {
    for (const mismatch of ["owner", "session", "candidate", "artifact", "verifier"]) {
      const root = fs.mkdtempSync(
        path.join(os.tmpdir(), "viventium-emo-cross-owner-"),
      );
      fs.chmodSync(root, 0o700);
      try {
        const evidence = privateSemanticFixture(root, caseId);
        const selectedOwner =
          mismatch === "owner" && caseId === CASE_047
            ? owner({ ownerId: "2".repeat(24) })
            : owner();
        const expectedIdentity = identity(caseId);
        if (mismatch === "owner" && caseId === CASE_048) {
          rewritePrivateSemanticDocument(evidence, "completion-record", (document) => {
            document.ownerId = "2".repeat(24);
          });
        }
        if (mismatch === "session") {
          rewritePrivateSemanticDocument(
            evidence,
            caseId === CASE_047
              ? "feelings_semantic_receipts"
              : "fault-controls",
            (document) => {
              document.sessionRef = "qa_" + "e".repeat(24);
            },
          );
        }
        if (mismatch === "candidate") {
          expectedIdentity.candidateDigest = "f".repeat(64);
        }
        if (mismatch === "artifact") {
          expectedIdentity.artifactDigest = "0".repeat(64);
        }
        if (mismatch === "verifier") {
          evidence.receipt.verifier.id =
            caseId === CASE_047 ? "emo048-semantic-v1" : "emo047-semantic-v1";
        }
        assert.throws(
          () =>
            runner().runIndependentVerifier(caseId, {
              evidenceRoot: root,
              evidencePath: evidence.evidencePath,
              identity: expectedIdentity,
              owner: selectedOwner,
              serviceStatus: evidence.serviceStatus,
              fixtureRef: evidence.manifest.fixtureRef,
              spawn(_command, args) {
                writePrivateVerifierReceipt(args, evidence.receipt);
                return {
                  status: 0,
                  stdout: JSON.stringify(evidence.output),
                  stderr: "",
                };
              },
            }),
          /independent_semantic_verifier_did_not_pass/,
          caseId + ":" + mismatch,
        );
      } finally {
        fs.rmSync(root, { recursive: true, force: true });
      }
    }
  }
});

test("rejects preexisting, symlinked, public, and multiply linked verifier receipts", () => {
  for (const caseId of [CASE_047, CASE_048]) {
    for (const failure of ["preexisting", "symlink", "public", "hardlink"]) {
      const root = fs.mkdtempSync(
        path.join(os.tmpdir(), "viventium-emo-receipt-guard-"),
      );
      fs.chmodSync(root, 0o700);
      try {
        const evidence = privateSemanticFixture(root, caseId);
        const receiptPath = path.join(
          root,
          caseId === CASE_047
            ? "emo-uc-047-independent-receipt.json"
            : "emo-uc-048-independent-receipt.json",
        );
        let invoked = false;
        if (failure === "preexisting") {
          fs.writeFileSync(receiptPath, JSON.stringify(evidence.receipt), {
            mode: 0o600,
          });
        }
        assert.throws(
          () =>
            runner().runIndependentVerifier(caseId, {
              evidenceRoot: root,
              evidencePath: evidence.evidencePath,
              identity: identity(caseId),
              owner: owner(),
              serviceStatus: evidence.serviceStatus,
              fixtureRef: evidence.manifest.fixtureRef,
              spawn(_command, args) {
                invoked = true;
                const target = args.at(-1);
                if (failure === "symlink" || failure === "hardlink") {
                  const original = path.join(root, "other-private-receipt.json");
                  fs.writeFileSync(original, JSON.stringify(evidence.receipt), {
                    mode: 0o600,
                  });
                  if (failure === "symlink") fs.symlinkSync(original, target);
                  else fs.linkSync(original, target);
                } else {
                  writePrivateVerifierReceipt(args, evidence.receipt);
                  if (failure === "public") fs.chmodSync(target, 0o644);
                }
                return {
                  status: 0,
                  stdout: JSON.stringify(evidence.output),
                  stderr: "",
                };
              },
            }),
          /independent_semantic_verifier_did_not_pass/,
          caseId + ":" + failure,
        );
        assert.equal(invoked, failure !== "preexisting");
      } finally {
        fs.rmSync(root, { recursive: true, force: true });
      }
    }
  }
});

test("rejects forged case, verifier registration, source manifest, timestamp, and receipt evidence", () => {
  for (const caseId of [CASE_047, CASE_048]) {
    for (const [failure, mutate] of [
      ["case", (receipt) => (receipt.caseId = caseId === CASE_047 ? CASE_048 : CASE_047)],
      ["status", (receipt) => (receipt.status = "FAIL")],
      ["contract", (receipt) => (receipt.contractVersion = 2)],
      ["surface", (receipt) => (receipt.surface = "web")],
      ["verifier", (receipt) => (receipt.verifier.id = "forged-semantic-v1")],
      ["manifest", (receipt) => (receipt.verifier.manifest = "different-owner.json")],
      ["timestamp", (receipt) => (receipt.runAt = "2020-01-01T00:00:00.000Z")],
      ["evidence", (receipt) => (receipt.evidence[0].sha256 = "0".repeat(64))],
      ["extra-field", (receipt) => (receipt.ownerId = OWNER_ID)],
    ]) {
      const root = fs.mkdtempSync(
        path.join(os.tmpdir(), "viventium-emo-receipt-binding-"),
      );
      fs.chmodSync(root, 0o700);
      try {
        const evidence = privateSemanticFixture(root, caseId);
        mutate(evidence.receipt);
        assert.throws(
          () =>
            runner().runIndependentVerifier(caseId, {
              evidenceRoot: root,
              evidencePath: evidence.evidencePath,
              identity: identity(caseId),
              owner: owner(),
              serviceStatus: evidence.serviceStatus,
              fixtureRef: evidence.manifest.fixtureRef,
              spawn(_command, args) {
                writePrivateVerifierReceipt(args, evidence.receipt);
                return {
                  status: 0,
                  stdout: JSON.stringify(evidence.output),
                  stderr: "",
                };
              },
            }),
          /independent_semantic_verifier_did_not_pass/,
          caseId + ":" + failure,
        );
      } finally {
        fs.rmSync(root, { recursive: true, force: true });
      }
    }
  }
});

test("requires every real semantic gate and rejects forged Python output fields", () => {
  for (const caseId of [CASE_047, CASE_048]) {
    for (const failure of ["missing-check", "failed-check", "extra-owner", "declared-failure"]) {
      const root = fs.mkdtempSync(
        path.join(os.tmpdir(), "viventium-emo-output-binding-"),
      );
      fs.chmodSync(root, 0o700);
      try {
        const evidence = privateSemanticFixture(root, caseId);
        const checks = caseId === CASE_047 ? evidence.output.gates : evidence.output.checks;
        if (failure === "missing-check") checks.pop();
        if (failure === "failed-check") checks[0].status = "FAIL";
        if (failure === "extra-owner") evidence.output.ownerId = OWNER_ID;
        if (failure === "declared-failure") {
          if (caseId === CASE_047) evidence.output.blockers.push("forged-pass");
          else evidence.output.failureCodes.push("forged-pass");
        }
        assert.throws(
          () =>
            runner().runIndependentVerifier(caseId, {
              evidenceRoot: root,
              evidencePath: evidence.evidencePath,
              identity: identity(caseId),
              owner: owner(),
              serviceStatus: evidence.serviceStatus,
              fixtureRef: evidence.manifest.fixtureRef,
              spawn(_command, args) {
                writePrivateVerifierReceipt(args, evidence.receipt);
                return {
                  status: 0,
                  stdout: JSON.stringify(evidence.output),
                  stderr: "",
                };
              },
            }),
          /independent_semantic_verifier_did_not_pass/,
          caseId + ":" + failure,
        );
      } finally {
        fs.rmSync(root, { recursive: true, force: true });
      }
    }
  }
});

test("binds EMO-UC-048 receipt evidence to the exact owner scope, fixture, and active service artifacts", () => {
  for (const failure of [
    "owner-scope",
    "synthetic-scope",
    "fixture",
    "component",
    "service-session",
    "service-acknowledgement",
  ]) {
    const root = fs.mkdtempSync(
      path.join(os.tmpdir(), "viventium-emo-insight-scope-"),
    );
    fs.chmodSync(root, 0o700);
    try {
      const evidence = privateSemanticFixture(root, CASE_048);
      if (failure === "owner-scope" || failure === "synthetic-scope") {
        rewritePrivateSemanticDocument(evidence, "fault-controls", (document) => {
          if (failure === "owner-scope") {
            document.controls[0].ownerScopeHash = "sha256:" + "f".repeat(64);
          } else {
            document.controls[0].syntheticScope = false;
          }
        });
      }
      if (failure === "component" || failure === "service-session") {
        rewritePrivateSemanticDocument(
          evidence,
          "restart-acknowledgements",
          (document) => {
            const service = document.checkpoints[0].services[0];
            if (failure === "component") {
              service.componentArtifactDigest = "sha256:" + "f".repeat(64);
            } else {
              service.sessionRef = "qa_" + "e".repeat(24);
            }
          },
        );
      }
      if (failure === "service-acknowledgement") {
        evidence.serviceStatus.serviceAckDigest = "sha256:" + "f".repeat(64);
      }
      const fixtureRef =
        failure === "fixture"
          ? "emo048_fixture_" + "4".repeat(24)
          : evidence.manifest.fixtureRef;
      assert.throws(
        () =>
          runner().runIndependentVerifier(CASE_048, {
            evidenceRoot: root,
            evidencePath: evidence.evidencePath,
            identity: identity(CASE_048),
            owner: owner(),
            serviceStatus: evidence.serviceStatus,
            fixtureRef,
            spawn(_command, args) {
              writePrivateVerifierReceipt(args, evidence.receipt);
              return {
                status: 0,
                stdout: JSON.stringify(evidence.output),
                stderr: "",
              };
            },
          }),
        /independent_semantic_verifier_did_not_pass/,
        failure,
      );
    } finally {
      fs.rmSync(root, { recursive: true, force: true });
    }
  }
});

test("parent capability receipts reject unsigned, forged, cross-owner, and replayed operations", async () => {
  const fixture = createComputer(CASE_048);
  const session = identity(CASE_048);
  const calls = [];
  const capability = {
    async invoke(request) {
      calls.push(request);
      const unsigned = {
        contractVersion: 1,
        capability: "parent_control",
        action: request.action,
        caseId: CASE_048,
        ownerId: OWNER_ID,
        sessionRef: SESSION_REF,
        candidateDigest: CANDIDATE_DIGEST,
        artifactDigest: ARTIFACT_DIGEST,
        componentArtifactDigest: COMPONENT_DIGEST,
        peerProcessId: fixture.authority.peerProcessId,
        challenge: request.challenge,
        requestSha256: sha256(canonical(request)),
        observedAtMs: Date.now(),
        result: { ready: true },
      };
      return { ...unsigned, proof: fixture.sign(unsigned) };
    },
  };
  const context = runner().createAuthenticatedCapabilityContext({
    authority: fixture.authority,
    identity: session,
    owner: fixture.owner,
  });
  assert.deepEqual(
    await runner().invokeAuthenticatedCapability(
      context,
      "parent_control",
      capability,
      "status",
    ),
    { ready: true },
  );
  assert.match(calls[0].challenge, /^[a-f0-9]{64}$/);
  capability.invoke = async (request) => ({
    contractVersion: 1,
    capability: "parent_control",
    action: request.action,
    caseId: CASE_048,
    ownerId: "2".repeat(24),
    sessionRef: SESSION_REF,
    candidateDigest: CANDIDATE_DIGEST,
    artifactDigest: ARTIFACT_DIGEST,
    componentArtifactDigest: COMPONENT_DIGEST,
    peerProcessId: fixture.authority.peerProcessId,
    challenge: request.challenge,
    requestSha256: sha256(canonical(request)),
    observedAtMs: Date.now(),
    result: {},
    proof: "ed25519:" + "a".repeat(86),
  });
  await assert.rejects(
    () =>
      runner().invokeAuthenticatedCapability(
        context,
        "parent_control",
        capability,
        "status",
      ),
    /external_capability_owner_or_session_mismatch/,
  );
});

test("rejects a valid parent signature for a different capability operation payload", async () => {
  const fixture = createComputer(CASE_048);
  const context = runner().createAuthenticatedCapabilityContext({
    authority: fixture.authority,
    identity: identity(CASE_048),
    owner: fixture.owner,
  });
  const capability = {
    async invoke(request) {
      const unsigned = {
        contractVersion: 1,
        capability: "parent_control",
        action: request.action,
        caseId: CASE_048,
        ownerId: OWNER_ID,
        sessionRef: SESSION_REF,
        candidateDigest: CANDIDATE_DIGEST,
        artifactDigest: ARTIFACT_DIGEST,
        componentArtifactDigest: COMPONENT_DIGEST,
        peerProcessId: fixture.authority.peerProcessId,
        challenge: request.challenge,
        requestSha256: sha256("different restart payload"),
        observedAtMs: Date.now(),
        result: { parentAuthorized: true },
      };
      return { ...unsigned, proof: fixture.sign(unsigned) };
    },
  };
  await assert.rejects(
    () =>
      runner().invokeAuthenticatedCapability(
        context,
        "parent_control",
        capability,
        "restart_core",
        { ownerId: OWNER_ID, requiredState: "pending" },
      ),
    /external_capability_request_mismatch/,
  );
});

test("rejects genuinely signed parent capability receipts for another installed artifact", async () => {
  const fixture = createComputer(CASE_047);
  const context = runner().createAuthenticatedCapabilityContext({
    authority: fixture.authority,
    identity: identity(),
    owner: fixture.owner,
  });
  const capability = {
    async invoke(request) {
      const unsigned = {
        contractVersion: 1,
        capability: "parent_control",
        action: request.action,
        caseId: CASE_047,
        ownerId: OWNER_ID,
        sessionRef: SESSION_REF,
        candidateDigest: CANDIDATE_DIGEST,
        artifactDigest: "9".repeat(64),
        componentArtifactDigest: COMPONENT_DIGEST,
        peerProcessId: fixture.authority.peerProcessId,
        challenge: request.challenge,
        requestSha256: sha256(canonical(request)),
        observedAtMs: Date.now(),
        result: { ready: true },
      };
      return { ...unsigned, proof: fixture.sign(unsigned) };
    },
  };
  await assert.rejects(
    () =>
      runner().invokeAuthenticatedCapability(
        context,
        "parent_control",
        capability,
        "status",
      ),
    /external_capability_owner_or_session_mismatch/,
  );
});

test("requires a fresh genuine selected synthetic chat before every parent-owned mutation", async () => {
  const fixture = createComputer(CASE_047);
  const bridge = runner().assertParentOwnedComputerBridge(
    fixture.driver,
    fixture.owner,
    identity(),
    fixture.authority,
  );
  const context = runner().createAuthenticatedCapabilityContext({
    authority: fixture.authority,
    identity: identity(),
    owner: fixture.owner,
  });
  const invoked = [];
  const capabilities = signedCapabilities(
    fixture,
    CASE_047,
    async (name, action) => {
      invoked.push(action);
      return { ownerId: OWNER_ID, ready: true };
    },
  );
  const request = { context, bridge, owner: fixture.owner, capabilities };
  await runner().invokeOwnerGuardedCapability({
    ...request,
    name: "parent_control",
    action: "status",
  });
  assert.equal(fixture.calls.length, 0);
  await runner().invokeOwnerGuardedCapability({
    ...request,
    name: "parent_control",
    action: "prepare_fixture",
  });
  await runner().invokeOwnerGuardedCapability({
    ...request,
    name: "parent_control",
    action: "arm_fault",
  });
  assert.deepEqual(invoked, ["status", "prepare_fixture", "arm_fault"]);
  assert.equal(fixture.calls.length, 2);

  const genuine = fixture.driver.get_app_state;
  fixture.driver.get_app_state = async (value) => {
    const observed = await genuine(value);
    const { proof, ...unsigned } = observed;
    void proof;
    unsigned.activeSelection.chat.telegramChatId = "-100999999999";
    return { ...unsigned, proof: fixture.sign(unsigned) };
  };
  await assert.rejects(
    () =>
      runner().invokeOwnerGuardedCapability({
        ...request,
        name: "parent_control",
        action: "configure_feelings",
      }),
    /active_telegram_chat_mismatch/,
  );
  assert.deepEqual(invoked, ["status", "prepare_fixture", "arm_fault"]);
});

test("EMO-UC-047 triggers four real Telegram scope journeys and six leased direct Workers", async () => {
  const fixture = createComputer(CASE_047);
  const bridge = runner().assertParentOwnedComputerBridge(
    fixture.driver,
    fixture.owner,
    identity(),
    fixture.authority,
  );
  const observations = pinnedObservations();
  const firstRequestRef = "sha256:" + "1".repeat(64);
  const secondRequestRef = "sha256:" + "2".repeat(64);
  const calls = [];
  const result = await runner().executePinnedFeelingsJourney({
    bridge,
    owner: fixture.owner,
    fixtureRef: "fixture_047",
    evidenceRoot: "/private/synthetic-evidence",
    async invoke(name, action, payload) {
      calls.push({ name, action, payload });
      if (action === "configure_feelings") {
        return { ownerId: OWNER_ID, scenario: payload.scenario };
      }
      if (action === "arm_provider_fallback") {
        return {
          ownerId: OWNER_ID,
          state: "armed",
          failureClass: "provider_quota_exhausted",
          heldUntilSecondRequestPinned: true,
        };
      }
      if (action === "observe_active_feelings_request") {
        const first = payload.scenario === "all_agents_before_delegation";
        return {
          ownerId: OWNER_ID,
          requestRef: first ? firstRequestRef : secondRequestRef,
          snapshotHash: first ? "f".repeat(64) : "0".repeat(64),
          active: true,
          providerStarted: true,
          presentationCommitted: false,
        };
      }
      if (action === "advance_synthetic_feelings_state") {
        return {
          ownerId: OWNER_ID,
          previousSnapshotHash: "f".repeat(64),
          snapshotHash: "0".repeat(64),
          changed: true,
        };
      }
      if (action === "release_provider_fallback") {
        return {
          ownerId: OWNER_ID,
          requestRef: firstRequestRef,
          released: true,
        };
      }
      if (action === "observe_provider_fallback") {
        return {
          ownerId: OWNER_ID,
          requestRef: firstRequestRef,
          snapshotHash: "f".repeat(64),
          failureClass: "provider_quota_exhausted",
          fallbackUsed: true,
          retryAfterHonored: true,
          capabilitiesPreserved: true,
        };
      }
      if (action === "observe_phase_b_continuity") {
        return {
          ownerId: OWNER_ID,
          requestRef: secondRequestRef,
          snapshotHash: "0".repeat(64),
          mainNativeSessionRef: "sha256:" + "3".repeat(64),
          phaseBNativeSessionRef: "sha256:" + "4".repeat(64),
          mainWorkerInterrupted: false,
          mainWorkerReplaced: false,
        };
      }
      if (action === "observe_specialist_independence") {
        return {
          ownerId: OWNER_ID,
          requestRef: secondRequestRef,
          specialists: [
            "emotional_resonance",
            "product_help",
            "productivity",
            "red_team",
            "research",
          ].map((specialistId) => ({
            specialistId,
            capsuleOccurrenceCount: 0,
            skipReason: "specialist_cortex_independent",
          })),
        };
      }
      if (action === "observe_running_workers") {
        return {
          ownerId: OWNER_ID,
          workers: [
            { ownerId: OWNER_ID, runtimeInvoked: true, leaseActive: true },
            { ownerId: OWNER_ID, runtimeInvoked: true, leaseActive: true },
          ],
        };
      }
      if (action === "observe_visible_response")
        return { ownerId: OWNER_ID, visible: true };
      if (action === "observe_feelings_scenario") {
        return {
          scenario: observations.scenarios.find(
            (scenario) => scenario.name === payload.scenario,
          ),
          privacyAudit: observations.privacyAudit,
        };
      }
      if (action === "capture_feelings_evidence") {
        return {
          ownerId: OWNER_ID,
          evidencePath: "/private/synthetic-evidence/manifest.json",
        };
      }
      throw new Error("unexpected operation");
    },
  });
  assert.equal(result.checks.workerReceiptCount, 6);
  assert.equal(result.checks.overlappingRequests, true);
  assert.equal(result.checks.providerFallback, true);
  assert.equal(result.checks.phaseBIndependent, true);
  assert.equal(result.checks.specialistReceiptCount, 5);
  const actionOrder = calls.map(({ action }) => action);
  assert.ok(
    actionOrder.indexOf("arm_provider_fallback") <
      actionOrder.indexOf("advance_synthetic_feelings_state"),
  );
  assert.ok(
    actionOrder.indexOf("advance_synthetic_feelings_state") <
      actionOrder.indexOf("release_provider_fallback"),
  );
  assert.equal(
    calls.filter(({ action }) => action === "observe_active_feelings_request")
      .length,
    2,
  );
  assert.equal(
    calls.filter(({ action }) => action === "configure_feelings").length,
    4,
  );
  assert.equal(
    calls.filter(({ action }) => action === "observe_running_workers").length,
    3,
  );
  assert.equal(
    fixture.calls.filter(({ method }) => method === "paste").length,
    6,
  );
  assert.equal(
    fixture.calls.filter(({ method }) => method === "press_key").length,
    6,
  );
  assert.equal(
    fixture.calls.filter(({ method }) => method === "get_app_state").length,
    12,
  );
});

test("EMO-UC-048 restarts only after a real failed completion and replays visible delivery once", async () => {
  const fixture = createComputer(CASE_048);
  const bridge = runner().assertParentOwnedComputerBridge(
    fixture.driver,
    fixture.owner,
    identity(CASE_048),
    fixture.authority,
  );
  const observation = insightObservations();
  const calls = [];
  const result = await runner().executeInsightRecoveryJourney({
    bridge,
    owner: fixture.owner,
    identity: identity(CASE_048),
    evidenceRoot: "/private/synthetic-evidence",
    async invoke(name, action, payload) {
      calls.push({ name, action, payload });
      if (action === "prepare_fixture")
        return { ownerId: OWNER_ID, fixtureRef: observation.fixtureRef };
      if (action === "arm_fault")
        return {
          ownerId: OWNER_ID,
          boundary: payload.boundary,
          state: "armed",
        };
      if (action === "observe_linked_conversation")
        return { ownerId: OWNER_ID, linked: true };
      if (action === "observe_completed_graph") return observation.graph;
      if (action === "observe_first_persistence_failure")
        return observation.firstFailure;
      if (action === "restart_core") return observation.restart;
      if (action === "status") {
        return status(CASE_048, {
          serviceAckDigest: observation.restart.afterServiceAckDigest,
        });
      }
      if (action === "observe_visible_insight")
        return {
          ownerId: OWNER_ID,
          visibleCount: 1,
          screenshotSha256: sha256("web-" + payload.phase),
          evidenceId: "web-" + payload.phase,
        };
      if (action === "record_surface_observation") {
        return {
          ownerId: OWNER_ID,
          fixtureRef: observation.fixtureRef,
          phase: payload.phase,
          surface: payload.surface,
          evidenceId: payload.surface + "-" + payload.phase,
          screenshotSha256: payload.screenshotSha256,
        };
      }
      if (action === "observe_settled_delivery") return observation.delivery;
      if (action === "replay_completion")
        return { ownerId: OWNER_ID, replayed: true };
      if (action === "observe_replayed_delivery") return observation.replay;
      if (action === "observe_consumed_fault_boundaries")
        return { boundaries: observation.boundaries };
      if (action === "observe_typed_terminal_probe")
        return observation.terminalProbe;
      if (action === "capture_insight_evidence") {
        return {
          ownerId: OWNER_ID,
          fixtureRef: observation.fixtureRef,
          evidencePath: "/private/synthetic-evidence/capture.json",
        };
      }
      throw new Error("unexpected operation");
    },
  });
  const order = calls.map(({ action }) => action);
  assert.equal(result.checks.deliveredExactlyOnce, true);
  assert.equal(result.checks.privateSurfaceCaptures, 4);
  assert.equal(
    calls.filter(({ action }) => action === "record_surface_observation")
      .length,
    4,
  );
  assert.deepEqual(
    fixture.calls
      .filter(({ request }) => request.includeScreenshot === true)
      .map(({ request }) => request.phase),
    ["settled", "replayed"],
  );
  assert.equal(order.filter((action) => action === "arm_fault").length, 4);
  assert.ok(
    order.indexOf("observe_first_persistence_failure") <
      order.indexOf("restart_core"),
  );
  assert.ok(
    order.indexOf("restart_core") < order.indexOf("observe_settled_delivery"),
  );
  assert.ok(
    order.indexOf("observe_settled_delivery") <
      order.indexOf("replay_completion"),
  );
});

test("cleanup clears parent-owned faults and removes only the exact synthetic owner", async () => {
  const calls = [];
  const result = await runner().cleanupSyntheticEffects({
    caseId: CASE_048,
    owner: owner(),
    fixtureRef: "emo048_fixture_" + "3".repeat(24),
    async invoke(name, action, payload) {
      calls.push({ name, action, payload });
      if (action === "clear_faults") return { cleared: 4, ownerId: OWNER_ID };
      return { cleaned: true, ownerId: OWNER_ID, remainingRecords: 0 };
    },
  });
  assert.deepEqual(
    calls.map(({ action }) => action),
    ["clear_faults", "cleanup_fixture"],
  );
  assert.equal(
    calls.every(({ payload }) => payload.ownerId === OWNER_ID),
    true,
  );
  assert.deepEqual(result, { cleaned: true, remainingRecords: 0 });
});

test("EMO-UC-047 restores the exact parent-owned Feelings baseline before synthetic cleanup", async () => {
  const calls = [];
  const baselineStateDigest = "8".repeat(64);
  const result = await runner().cleanupSyntheticEffects({
    caseId: CASE_047,
    owner: owner(),
    fixtureRef: "fixture_047",
    baselineStateDigest,
    async invoke(name, action, payload) {
      calls.push({ name, action, payload });
      if (action === "clear_faults") return { cleared: 1, ownerId: OWNER_ID };
      if (action === "restore_feelings") {
        return {
          ownerId: OWNER_ID,
          fixtureRef: "fixture_047",
          restored: true,
          restoredStateDigest: baselineStateDigest,
        };
      }
      return { cleaned: true, ownerId: OWNER_ID, remainingRecords: 0 };
    },
  });
  assert.deepEqual(
    calls.map(({ action }) => action),
    ["clear_faults", "restore_feelings", "cleanup_fixture"],
  );
  assert.equal(calls[1].payload.expectedStateDigest, baselineStateDigest);
  assert.deepEqual(result, { cleaned: true, remainingRecords: 0 });
});

test("EMO-UC-047 refuses fixture deletion when exact Feelings restoration is unverified", async () => {
  const actions = [];
  await assert.rejects(
    () =>
      runner().cleanupSyntheticEffects({
        caseId: CASE_047,
        owner: owner(),
        fixtureRef: "fixture_047",
        baselineStateDigest: "8".repeat(64),
        async invoke(name, action) {
          actions.push(action);
          if (action === "clear_faults")
            return { cleared: 1, ownerId: OWNER_ID };
          return {
            ownerId: OWNER_ID,
            fixtureRef: "fixture_047",
            restored: true,
            restoredStateDigest: "7".repeat(64),
          };
        },
      }),
    /synthetic_owner_cleanup_unverified/,
  );
  assert.deepEqual(actions, ["clear_faults", "restore_feelings"]);
});

test("cleanup rejects cross-owner acknowledgements and retained synthetic records", async () => {
  for (const reply of [
    { cleaned: true, ownerId: "2".repeat(24), remainingRecords: 0 },
    { cleaned: true, ownerId: OWNER_ID, remainingRecords: 1 },
  ]) {
    await assert.rejects(
      () =>
        runner().cleanupSyntheticEffects({
          caseId: CASE_047,
          owner: owner(),
          fixtureRef: "fixture_047",
          invoke: async () => reply,
        }),
      /synthetic_owner_cleanup_unverified/,
    );
  }
});

test("a locally generated fake parent key blocks before all Computer and account operations", async () => {
  const root = fs.mkdtempSync(
    path.join(os.tmpdir(), "viventium-emo-installed-"),
  );
  fs.chmodSync(root, 0o700);
  try {
    const fixture = createComputer(CASE_047);
    const actions = [];
    const capabilities = signedCapabilities(
      fixture,
      CASE_047,
      async (name, action) => {
        actions.push(action);
        if (action === "status") return status();
        if (action === "inspect_owner") return fixture.owner;
        if (action === "prepare_fixture")
          return { ownerId: OWNER_ID, fixtureRef: "fixture_047" };
        if (action === "configure_feelings")
          return { ownerId: OWNER_ID, scenario: "wrong_scenario" };
        if (action === "cleanup_fixture")
          return {
            cleaned: true,
            ownerId: "2".repeat(24),
            remainingRecords: 0,
          };
        return {};
      },
    );
    const result = await runner().runInstalledJourney(
      [
        "--live",
        "--case=EMO-UC-047",
        "--qa-email=" + fixture.owner.email,
        "--owner-id=" + OWNER_ID,
        "--evidence-root=" + root,
      ],
      environment(),
      {
        owner: fixture.owner,
        identity: identity(),
        authority: fixture.authority,
        desktopDriver: fixture.driver,
        capabilities,
      },
    );
    assert.equal(actions.length, 0);
    assert.equal(fixture.calls.length, 0);
    assert.equal(result.status, "BLOCKED");
    assert.equal(
      result.blocker,
      "independent_parent_computer_authority_unavailable",
    );
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test("private user text, owner email, paths, and receipt bodies never enter the public summary", () => {
  const summary = runner().buildPublicSummary({
    caseId: CASE_048,
    status: "BLOCKED",
    blocker: "safe_blocker",
    ownerEmail: testEmail("owner", "private.invalid"),
    insight: "sensitive personal insight",
    evidenceRoot: "/private/secret/path",
    checks: { completed: true, secret: "sensitive personal insight" },
  });
  const serialized = JSON.stringify(summary);
  assert.equal(serialized.includes(testEmail("owner", "private.invalid")), false);
  assert.equal(serialized.includes("sensitive personal insight"), false);
  assert.equal(serialized.includes("/private/secret/path"), false);
  assert.equal(summary.checks.completed, true);
  assert.equal(summary.releaseReady, false);
  assert.equal(summary.receiptEligible, false);
  assert.equal(summary.releaseLabel, "PRE-GATE / NOT READY");
});

test("standalone live execution fails closed before account or runtime mutation", async () => {
  const result = await runner().runInstalledJourney(
    ["--live", "--case=EMO-UC-047", "--qa-email=emo-installed@example.com"],
    environment(),
    {},
  );
  assert.equal(result.status, "BLOCKED");
  assert.equal(result.releaseReady, false);
  assert.equal(result.receiptEligible, false);
});
