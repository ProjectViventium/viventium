"use strict";

const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const test = require("node:test");

const journey = require("./run_tr026_installed_journey.cjs");
const ROOT = path.resolve(__dirname, "../../..");
const RUNNER = path.join(__dirname, "run_tr026_installed_journey.cjs");
const SESSION_REF = `qa_${"c".repeat(24)}`;
const ARTIFACT_REF = "c".repeat(16);
const EXTERNAL_COMPUTER_KEYS = crypto.generateKeyPairSync("ed25519");

function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

function externalComputerAuthority() {
  return {
    publicKey: EXTERNAL_COMPUTER_KEYS.publicKey,
    keyId: crypto.createHash("sha256")
      .update(EXTERNAL_COMPUTER_KEYS.publicKey.export({ type: "spki", format: "der" }))
      .digest("hex"),
    peerProcessId: process.ppid,
    sessionRef: "sky_external_tr026_owner_session",
    unitTestHarness: {
      kind: "node_test_only",
      processId: process.pid,
      parentProcessId: process.ppid,
      testFile: __filename,
    },
  };
}

function signExternalComputer(payload) {
  return `ed25519:${crypto.sign(null, Buffer.from(canonicalJson(payload)), EXTERNAL_COMPUTER_KEYS.privateKey).toString("base64url")}`;
}

function activeSelection(scenario, changes = {}) {
  return {
    source: "computer_ui_active_selection",
    observedAtMs: Date.now(),
    account: {
      selected: true,
      ownerId: scenario.owner.ownerId,
      telegramUserId: scenario.owner.telegramUserId,
      label: scenario.telegram.accountLabel,
      evidence: "active_account_control",
    },
    chat: {
      selected: true,
      ownerId: scenario.owner.ownerId,
      telegramChatId: scenario.owner.telegramChatId,
      label: scenario.telegram.chatLabel,
      evidence: "active_chat_header",
      conversationRefHash: digest(scenario.conversation.conversationId),
    },
    ...changes,
  };
}

function externalComputerBridge(scenario, identity = installedIdentity(), options = {}) {
  const authority = externalComputerAuthority();
  const issuedAtMs = Date.now() - 1000;
  const unsignedProvenance = {
    contractVersion: 1,
    caseId: "TR-026",
    provider: "@oai/sky",
    controlPlane: "computer_plugin_node_repl",
    interface: "sky.get_app_state/sky-primitives",
    skyMethods: ["click", "press_key"],
    ownerId: scenario.owner.ownerId,
    telegramUserId: scenario.owner.telegramUserId,
    telegramChatId: scenario.owner.telegramChatId,
    appBundleId: scenario.telegram.bundleId,
    sessionRef: authority.sessionRef,
    authorityKeyId: authority.keyId,
    peerProcessId: authority.peerProcessId,
    ownerRefHash: identity.ownerRefHash,
    candidateDigest: identity.candidateDigest,
    artifactDigest: identity.artifactDigest,
    qaOwnerRefHash: digest(scenario.owner.ownerId),
    conversationRefHash: digest(scenario.conversation.conversationId),
    telegramChatRefHash: digest(scenario.owner.telegramChatId),
    issuedAtMs,
    expiresAtMs: issuedAtMs + 60000,
  };
  const calls = [];
  let index = 0;
  const driver = {
    provenance: { ...unsignedProvenance, proof: signExternalComputer(unsignedProvenance) },
    async get_app_state(request) {
      calls.push({ kind: "get_app_state", request });
      const selection = options.selections?.[Math.min(index, options.selections.length - 1)] ||
        activeSelection(scenario);
      index += 1;
      const unsigned = {
        source: "@oai/sky.get_app_state",
        app: request.app,
        ownerId: scenario.owner.ownerId,
        telegramUserId: scenario.owner.telegramUserId,
        telegramChatId: scenario.owner.telegramChatId,
        sessionRef: authority.sessionRef,
        peerProcessId: authority.peerProcessId,
        challenge: request.challenge,
        observedAtMs: Date.now(),
        activeSelection: selection,
        text: `${scenario.telegram.accountLabel}\n${scenario.telegram.chatLabel}`,
      };
      return { ...unsigned, proof: signExternalComputer(unsigned) };
    },
    async do_action(request) {
      calls.push({ kind: "do_action", request });
      const unsigned = {
        source: `@oai/sky.${request.skyMethod}`,
        skyMethod: request.skyMethod,
        app: request.app,
        ownerId: scenario.owner.ownerId,
        telegramUserId: scenario.owner.telegramUserId,
        telegramChatId: scenario.owner.telegramChatId,
        sessionRef: authority.sessionRef,
        peerProcessId: authority.peerProcessId,
        challenge: request.challenge,
        selectionChallenge: request.selectionChallenge,
        selectionSha256: request.selectionSha256,
        observedAtMs: Date.now(),
        activeSelection: activeSelection(scenario),
        action: request.action,
        status: "sent",
      };
      return { ...unsigned, proof: signExternalComputer(unsigned) };
    },
  };
  return { authority, driver, calls };
}

function digest(value) {
  return crypto.createHash("sha256").update(String(value)).digest("hex");
}

function installedIdentity() {
  return {
    verified: true,
    ownerRefHash: digest("synthetic-installed-owner"),
    candidateDigest: digest("candidate"),
    artifactDigest: digest("artifact"),
  };
}

function privateRoot(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "viventium-tr026-runner-"));
  fs.chmodSync(root, 0o700);
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  return root;
}

function privateFile(location, payload) {
  fs.writeFileSync(location, JSON.stringify(payload), { mode: 0o600 });
  fs.chmodSync(location, 0o600);
  return location;
}

function safeEnvironment(extra = {}) {
  return {
    PATH: process.env.PATH || "",
    VIVENTIUM_QA_ALLOW_TR026_INSTALLED_JOURNEY: "1",
    VIVENTIUM_QA_ALLOW_TR026_TELEGRAM_MUTATION: "1",
    VIVENTIUM_QA_ALLOW_TR026_RUNTIME_RESTART: "1",
    VIVENTIUM_QA_OWNER_EMAIL: "owner@example.com",
    VIVENTIUM_QA_OWNER_TELEGRAM_USER_ID: "900001",
    VIVENTIUM_QA_OWNER_TELEGRAM_CHAT_ID: "900002",
    VIVENTIUM_QA_OWNER_TELEGRAM_ACCOUNT_LABEL: "Personal account",
    ...extra,
  };
}

function scenarioAt(root) {
  return {
    contractVersion: 1,
    caseId: "TR-026",
    classification: "synthetic_public_safe",
    owner: {
      synthetic: true,
      ownerId: "507f1f77bcf86cd799439011",
      email: "qa-tr026@example.com",
      telegramUserId: "700001",
      telegramChatId: "700002",
      telegramThreadId: 0,
    },
    conversation: { conversationId: "tr026-synthetic-conversation" },
    telegram: {
      bundleId: "ru.keepcoder.Telegram",
      accountLabel: "TR-026 synthetic QA account",
      chatLabel: "TR-026 synthetic QA bot",
    },
    source: {
      first: {
        messageId: 4101,
        updateId: 880001,
        text: "TR-026 synthetic original request",
      },
      revision: {
        messageId: 4102,
        updateId: 880002,
        text: "TR-026 synthetic revised request: REVISED_SAFE",
      },
      postCommit: {
        messageId: 4105,
        updateId: 880005,
        text: "TR-026 synthetic post-commit control",
      },
      expectedReplyMarker: "REVISED_SAFE",
      staleReplyMarker: "STALE_SAFE",
    },
    workers: { workRefs: ["work-tr026-alpha", "work-tr026-bravo"] },
    runtime: {
      installedRoot: ROOT,
      runtimeRoot: path.join(root, "runtime"),
      artifactIdentityPath: path.join(root, "identity.json"),
      runtimeOwnerStatePath: path.join(root, "owner.json"),
      glassHiveDbPath: path.join(root, "glasshive.sqlite3"),
    },
    restart: {
      supported: true,
      executable: path.join(ROOT, "bin", "viventium"),
      arguments: [
        "dev-runtime",
        "activate-current",
        "--validate",
        "--restart",
        "--allow-protected-folder",
        "--allow-dirty-local-testing",
      ],
      services: ["librechat-core", "telegram-bot"],
    },
    evidence: {
      producer: "independent_installed_runtime_observer",
      manifestName: "independent-tr026-manifest.json",
    },
  };
}

function observedIdentity(scenario) {
  return {
    source: "computer_plugin_sky",
    bundleId: scenario.telegram.bundleId,
    accountLabel: scenario.telegram.accountLabel,
    chatLabel: scenario.telegram.chatLabel,
    ownerId: scenario.owner.ownerId,
    linkedOwnerId: scenario.owner.ownerId,
    telegramUserId: scenario.owner.telegramUserId,
    telegramChatId: scenario.owner.telegramChatId,
    accountVisible: true,
    chatVisible: true,
    activeSelectionVerified: true,
  };
}

function computerDesktopDriver(scenario, identity = {}) {
  return {
    provenance: {
      contractVersion: 1,
      provider: "@oai/sky",
      plugin: "computer",
      transport: "owner_private_bridge",
      parentVerified: true,
      ownerRefHash: identity.ownerRefHash || digest("synthetic-installed-owner"),
      candidateDigest: identity.candidateDigest || digest("candidate"),
      artifactDigest: identity.artifactDigest || digest("artifact"),
      qaOwnerRefHash: digest(scenario.owner.ownerId),
      conversationRefHash: digest(scenario.conversation.conversationId),
      telegramChatRefHash: digest(scenario.owner.telegramChatId),
    },
    async inspectTelegram() {},
    async sendTelegramText() {},
    async captureTelegramWindow() {},
    async reopenTelegramConversation() {},
  };
}

function trustedIngress(scenario, stage) {
  const segment = scenario.source[stage];
  return {
    source: "installed_telegram_ingress_ledger",
    ownerId: scenario.owner.ownerId,
    ownerUserId: Number(scenario.owner.telegramUserId),
    chatId: Number(scenario.owner.telegramChatId),
    threadId: scenario.owner.telegramThreadId,
    conversationId: scenario.conversation.conversationId,
    messageId: segment.messageId,
    sourceSequence: segment.messageId,
    updateId: segment.updateId,
    observedAt: "2026-08-25T12:00:00.000Z",
  };
}

function workerSnapshot(scenario, state = "running") {
  return scenario.workers.workRefs.map((workRef, index) => ({
    source: "installed_glasshive_read_only_store",
    ownerId: scenario.owner.ownerId,
    workRef,
    workerRef: `worker-${index}`,
    runRef: `run-${index}`,
    state,
    runtimeInvokedAt: "2026-08-25T11:59:00.000Z",
    cancelRequested: false,
  }));
}

function rapidObservation(scenario) {
  const turnRefHash = digest("synthetic-logical-turn");
  return {
    source: "installed_mongo_and_telegram_desktop",
    ownerId: scenario.owner.ownerId,
    conversationId: scenario.conversation.conversationId,
    turnRefHash,
    initialTurnRefHash: turnRefHash,
    correctedTurnRefHash: turnRefHash,
    initialRevision: 1,
    correctedRevision: 2,
    sourceMessageIds: [scenario.source.first.messageId, scenario.source.revision.messageId],
    sourceSequences: [scenario.source.first.messageId, scenario.source.revision.messageId],
    userBubbles: [
      { role: "user", messageId: scenario.source.first.messageId, text: scenario.source.first.text },
      { role: "user", messageId: scenario.source.revision.messageId, text: scenario.source.revision.text },
    ],
    assistantBubbleCount: 1,
    finalReplies: [{ messageId: 4104, text: "✅ REVISED_SAFE", revision: 2 }],
    staleReplyVisible: false,
    staleReplyRetracted: true,
    reopenedMatches: true,
  };
}

function postCommitObservation(scenario, turnRefHash) {
  return {
    source: "installed_mongo_and_telegram_desktop",
    ownerId: scenario.owner.ownerId,
    conversationId: scenario.conversation.conversationId,
    previousTurnRefHash: turnRefHash,
    followUpTurnRefHash: digest("synthetic-follow-up-turn"),
    followUpRevision: 1,
    previousCommittedAt: "2026-08-25T12:00:01.000Z",
    sourceObservedAt: "2026-08-25T12:00:02.000Z",
    sourceMessageId: scenario.source.postCommit.messageId,
    sourceSequence: scenario.source.postCommit.messageId,
  };
}

function auditRecords(eventDigest = digest("synthetic-authenticated-source")) {
  return [
    {
      schema_version: 3,
      case_id: "TR-026",
      artifact_ref: ARTIFACT_REF,
      session_ref: SESSION_REF,
      chain_index: 1,
      outcome: "claimed",
      reason: "exact_structured_target",
      configured_delay_ms: 280,
      event_digest: eventDigest,
    },
    {
      schema_version: 3,
      case_id: "TR-026",
      artifact_ref: ARTIFACT_REF,
      session_ref: SESSION_REF,
      chain_index: 2,
      outcome: "delay_requested",
      reason: "core_admission_boundary",
      configured_delay_ms: 280,
      event_digest: eventDigest,
    },
  ];
}

function verifiedResult(identity, turnRefHash) {
  return {
    caseId: "TR-026",
    status: "PASS",
    ready: true,
    surface: "telegram",
    candidateDigest: identity.candidateDigest,
    artifactDigest: identity.artifactDigest,
    blockers: [],
    gates: journey.REQUIRED_VERIFIER_GATES.map((id) => ({ id, status: "PASS" })),
    manifest: {
      caseId: "TR-026",
      candidate: {
        candidateDigest: identity.candidateDigest,
        artifactDigest: identity.artifactDigest,
      },
      correlation: {
        ownerRefHash: identity.ownerRefHash,
        sessionRef: SESSION_REF,
        turnRefHash,
      },
    },
  };
}

test("dry-run remains inert and never creates private or installed state", (t) => {
  const root = privateRoot(t);
  const untouched = path.join(root, "must-not-exist");
  const result = spawnSync("node", [RUNNER, "--dry-run"], {
    cwd: ROOT,
    encoding: "utf8",
    env: { PATH: process.env.PATH || "", VIVENTIUM_QA_PRIVATE_DIR: untouched },
  });

  assert.equal(result.status, 0, result.stderr);
  const payload = JSON.parse(result.stdout);
  assert.equal(payload.caseId, "TR-026");
  assert.equal(payload.status, "DRY_RUN");
  assert.equal(payload.sideEffects, false);
  assert.equal(payload.sendsTelegramMessages, false);
  assert.equal(payload.restartsRuntime, false);
  assert.equal(payload.accessesDatabase, false);
  assert.equal(payload.receiptEligible, false);
  assert.equal(fs.existsSync(untouched), false);
});

test("parser rejects duplicate, unknown, unsafe, and mixed dry-run options", () => {
  assert.throws(() => journey.parseArgs(["--local-qa", "--local-qa"]), /duplicate_argument/);
  assert.throws(() => journey.parseArgs(["--unknown"]), /unknown_argument/);
  assert.throws(() => journey.parseArgs(["--dry-run", "--local-qa"]), /dry_run_rejects_live_arguments/);
  assert.throws(() => journey.parseArgs(["--timeout-ms", "12"]), /journey_timeout_invalid/);
});

test("local QA, Telegram mutation, and restart require three independent explicit consents", () => {
  const args = { localQa: true, allowTelegramMutation: true, allowRuntimeRestart: true };
  const restart = { supported: true };

  assert.doesNotThrow(() => journey.assertExecutionConsents(args, safeEnvironment(), restart));
  for (const [flag, reason] of [
    ["localQa", "local_qa_opt_in_required"],
    ["allowTelegramMutation", "telegram_mutation_consent_required"],
    ["allowRuntimeRestart", "runtime_restart_consent_required"],
  ]) {
    assert.throws(
      () => journey.assertExecutionConsents({ ...args, [flag]: false }, safeEnvironment(), restart),
      new RegExp(reason),
    );
  }
  for (const [variable, reason] of [
    ["VIVENTIUM_QA_ALLOW_TR026_INSTALLED_JOURNEY", "installed_journey_opt_in_required"],
    ["VIVENTIUM_QA_ALLOW_TR026_TELEGRAM_MUTATION", "telegram_mutation_consent_required"],
    ["VIVENTIUM_QA_ALLOW_TR026_RUNTIME_RESTART", "runtime_restart_consent_required"],
  ]) {
    assert.throws(
      () => journey.assertExecutionConsents(args, safeEnvironment({ [variable]: "" }), restart),
      new RegExp(reason),
    );
  }
  assert.throws(
    () => journey.assertExecutionConsents(args, safeEnvironment({ CI: "1" }), restart),
    /local_installed_qa_only/,
  );
  assert.throws(
    () => journey.assertExecutionConsents(args, safeEnvironment(), { supported: false }),
    /runtime_restart_unsupported/,
  );
});

test("unconsented CLI exits typed BLOCKED before evidence, Telegram, restart, or QA control", (t) => {
  const root = privateRoot(t);
  const untouched = path.join(root, "must-not-exist");
  const completed = spawnSync("node", [RUNNER, "--evidence-root", untouched], {
    cwd: ROOT,
    encoding: "utf8",
    env: { PATH: process.env.PATH || "" },
  });

  assert.equal(completed.status, 2);
  const payload = JSON.parse(completed.stdout);
  assert.equal(payload.status, "BLOCKED");
  assert.equal(payload.blocker, "local_qa_opt_in_required");
  assert.equal(payload.releaseReady, false);
  assert.equal(payload.receiptEligible, false);
  assert.equal(fs.existsSync(untouched), false);
  assert.equal(completed.stdout.includes(untouched), false);
});

test("private evidence requires an existing owner-only directory outside the repository", (t) => {
  const root = privateRoot(t);
  const readable = path.join(root, "readable");
  fs.mkdirSync(readable, { mode: 0o755 });
  fs.chmodSync(readable, 0o755);
  const linked = path.join(root, "linked");
  fs.symlinkSync(readable, linked, "dir");

  assert.equal(journey.assertPrivateEvidenceRoot(root), fs.realpathSync(root));
  assert.throws(() => journey.assertPrivateEvidenceRoot(ROOT), /evidence_root_inside_repository/);
  assert.throws(() => journey.assertPrivateEvidenceRoot(readable), /evidence_root_not_private/);
  assert.throws(() => journey.assertPrivateEvidenceRoot(linked), /evidence_root_symlink_forbidden/);
  assert.throws(() => journey.assertPrivateEvidenceRoot(path.join(root, "missing")), /evidence_root_unavailable/);
});

test("scenario and evidence files remain exact-owner 0600, unlinked, and non-overwriting", (t) => {
  const root = privateRoot(t);
  const scenarioPath = privateFile(path.join(root, "scenario.json"), scenarioAt(root));
  assert.equal(journey.readPrivateScenario(scenarioPath, root).caseId, "TR-026");

  const written = journey.writePrivateEvidence(root, "observed.json", { private: true });
  assert.equal(fs.statSync(written.path).mode & 0o777, 0o600);
  assert.throws(() => journey.writePrivateEvidence(root, "observed.json", {}), /private_evidence_already_exists/);
  assert.throws(() => journey.writePrivateEvidence(root, "../outside.json", {}), /private_evidence_path_invalid/);

  fs.chmodSync(scenarioPath, 0o644);
  assert.throws(() => journey.readPrivateScenario(scenarioPath, root), /scenario_not_private/);
  fs.chmodSync(scenarioPath, 0o600);
  const linked = path.join(root, "scenario-link.json");
  fs.symlinkSync(scenarioPath, linked);
  assert.throws(() => journey.readPrivateScenario(linked, root), /scenario_symlink_forbidden/);
});

test("scenario binds a nonpersonal owner, one conversation, adjacent actual source IDs, and two workers", (t) => {
  const scenario = scenarioAt(privateRoot(t));
  assert.doesNotThrow(() => journey.validateScenario(scenario, safeEnvironment()));

  for (const [reason, mutate] of [
    ["personal_owner_account_refused", (value) => { value.owner.email = "owner@example.com"; }],
    ["personal_telegram_account_refused", (value) => { value.owner.telegramUserId = "900001"; }],
    ["personal_telegram_chat_refused", (value) => { value.owner.telegramChatId = "900002"; }],
    ["synthetic_owner_identity_required", (value) => { value.owner.synthetic = false; }],
    ["owner_scoped_conversation_required", (value) => { value.conversation.conversationId = ""; }],
    ["adjacent_source_message_ids_required", (value) => { value.source.revision.messageId = 4103; }],
    ["exact_telegram_update_binding_required", (value) => { value.source.revision.updateId = 0; }],
    ["post_commit_source_message_required", (value) => { value.source.postCommit.messageId = 4102; }],
    ["two_owner_scoped_workers_required", (value) => { value.workers.workRefs[1] = value.workers.workRefs[0]; }],
    ["independent_installed_evidence_producer_required", (value) => { value.evidence.producer = "fixture"; }],
    ["runtime_restart_unsupported", (value) => { value.restart.arguments = ["restart"]; }],
  ]) {
    const modified = structuredClone(scenario);
    mutate(modified);
    assert.throws(() => journey.validateScenario(modified, safeEnvironment()), new RegExp(reason), reason);
  }
});

test("restart uses only the installed CLI and explicitly acknowledges protected dirty local checkout", (t) => {
  const scenario = scenarioAt(privateRoot(t));
  scenario.restart.arguments = scenario.restart.arguments.filter(
    (argument) => argument !== "--allow-dirty-local-testing",
  );

  assert.throws(
    () => journey.validateScenario(scenario, safeEnvironment()),
    /runtime_restart_dirty_checkout_protection_required/,
  );

  scenario.restart.arguments.push("--allow-dirty-local-testing");
  assert.doesNotThrow(() => journey.validateScenario(scenario, safeEnvironment()));

  for (const mutate of [
    (value) => { value.restart.arguments.push("--unexpected"); },
    (value) => { value.restart.arguments.push("--restart"); },
    (value) => { value.restart.arguments[1] = "status"; },
    (value) => { value.restart.executable = path.join(ROOT, "bin", "different"); },
  ]) {
    const changed = structuredClone(scenario);
    mutate(changed);
    assert.throws(
      () => journey.validateScenario(changed, safeEnvironment()),
      /runtime_restart_unsupported/,
    );
  }
});

test("visible Telegram account and chat must match the exact installed owner mapping", (t) => {
  const scenario = scenarioAt(privateRoot(t));
  assert.doesNotThrow(() => journey.assertOwnerSafeTelegramIdentity(scenario, safeEnvironment(), observedIdentity(scenario)));

  for (const mutate of [
    (value) => { value.source = "fixture"; },
    (value) => { value.accountVisible = false; },
    (value) => { value.chatVisible = false; },
    (value) => { value.ownerId = "different-owner"; },
    (value) => { value.linkedOwnerId = "different-owner"; },
    (value) => { value.accountLabel = "Personal account"; },
    (value) => { value.telegramChatId = "700003"; },
  ]) {
    const observed = observedIdentity(scenario);
    mutate(observed);
    assert.throws(
      () => journey.assertOwnerSafeTelegramIdentity(scenario, safeEnvironment(), observed),
      /owner_safe_telegram_identity_unavailable/,
    );
  }
});

test("an existing trusted Telegram chat must already belong to the exact owner and conversation", (t) => {
  const scenario = scenarioAt(privateRoot(t));
  const mapping = {
    telegramUserId: scenario.owner.telegramUserId,
    libreChatUserId: scenario.owner.ownerId,
  };
  const chat = {
    telegramUserId: scenario.owner.telegramUserId,
    telegramChatId: scenario.owner.telegramChatId,
    conversationId: scenario.conversation.conversationId,
  };

  assert.equal(journey.assertOwnerScopedTelegramChatBinding(scenario, mapping, chat), chat);
  for (const mutate of [
    (value) => { value.mapping.libreChatUserId = "different-owner"; },
    (value) => { value.mapping.telegramUserId = "700003"; },
    (value) => { value.chat.telegramUserId = "700003"; },
    (value) => { value.chat.telegramChatId = "700004"; },
    (value) => { value.chat.conversationId = "different-conversation"; },
    (value) => { value.chat = undefined; },
  ]) {
    const changed = structuredClone({ mapping, chat });
    mutate(changed);
    assert.throws(
      () => journey.assertOwnerScopedTelegramChatBinding(scenario, changed.mapping, changed.chat),
      /owner_safe_telegram_identity_unavailable/,
    );
  }
});

test("desktop interaction requires an externally signed owner-bound Computer Sky driver", (t) => {
  const scenario = scenarioAt(privateRoot(t));
  const identity = installedIdentity();
  const computer = externalComputerBridge(scenario, identity);
  const trusted = journey.assertComputerDesktopDriver(
    computer.driver,
    scenario,
    identity,
    { authority: computer.authority },
  );

  assert.equal(trusted.driver, computer.driver);
  assert.equal(journey.assertComputerDesktopDriver(trusted, scenario, identity), trusted);

  for (const mutate of [
    (value) => { value.provenance.provider = "fake-computer"; },
    (value) => { value.provenance.controlPlane = "shell"; },
    (value) => { value.provenance.interface = "fake.desktop"; },
    (value) => { value.provenance.ownerRefHash = digest("different-installed-owner"); },
    (value) => { value.provenance.qaOwnerRefHash = digest("different-qa-owner"); },
    (value) => { value.provenance.conversationRefHash = digest("different-conversation"); },
    (value) => { value.provenance.telegramChatRefHash = digest("different-chat"); },
    (value) => { value.provenance.candidateDigest = digest("different-candidate"); },
    (value) => { value.provenance.artifactDigest = digest("different-artifact"); },
    (value) => { value.get_app_state = undefined; },
    (value) => { value.do_action = undefined; },
  ]) {
    const source = externalComputerBridge(scenario, identity);
    const changed = source.driver;
    mutate(changed);
    assert.throws(
      () => journey.assertComputerDesktopDriver(changed, scenario, identity, { authority: source.authority }),
      /computer_plugin_desktop_driver_unavailable|computer_desktop_driver_/,
    );
  }

  assert.throws(
    () => journey.assertComputerDesktopDriver(undefined, scenario, identity),
    /computer_plugin_desktop_driver_unavailable/,
  );
});

test("self-declared parentVerified and copied database identity cannot authorize Computer access", (t) => {
  const scenario = scenarioAt(privateRoot(t));
  const identity = installedIdentity();
  const forged = computerDesktopDriver(scenario, identity);

  assert.throws(
    () => journey.assertComputerDesktopDriver(forged, scenario, identity),
    /computer_desktop_external_authority_required/,
  );

  const genuine = externalComputerBridge(scenario, identity);
  const trusted = journey.assertComputerDesktopDriver(
    genuine.driver,
    scenario,
    identity,
    { authority: genuine.authority },
  );
  assert.equal(trusted.provenance.authorityKeyId, genuine.authority.keyId);
});

test("TR-026 refuses visible sidebar labels when the ACTIVE selected Telegram account or chat differs", async (t) => {
  const scenario = scenarioAt(privateRoot(t));
  const selectedPersonal = activeSelection(scenario);
  selectedPersonal.account.telegramUserId = "900001";
  selectedPersonal.account.label = "Personal account";
  const exploit = externalComputerBridge(scenario, installedIdentity(), { selections: [selectedPersonal] });
  const trusted = journey.assertComputerDesktopDriver(
    exploit.driver,
    scenario,
    installedIdentity(),
    { authority: exploit.authority },
  );

  await assert.rejects(
    () => journey.performOwnerBoundComputerAction(trusted, scenario, {
      action: "telegram.send_text",
      text: "TR-026 synthetic owner-isolated text",
      stage: "first",
    }),
    /computer_desktop_active_account_mismatch/,
  );
  assert.equal(exploit.calls.some((item) => item.kind === "do_action"), false);

  const forged = observedIdentity(scenario);
  delete forged.activeSelectionVerified;
  assert.throws(
    () => journey.assertOwnerSafeTelegramIdentity(scenario, safeEnvironment(), forged),
    /computer_desktop_active_selection_unavailable/,
  );
});

test("the independent observer is a real owner-bound child process and rejects forged Computer evidence", async (t) => {
  const root = privateRoot(t);
  const scenario = scenarioAt(root);
  const identity = installedIdentity();
  const computer = externalComputerBridge(scenario, identity);
  const trusted = journey.assertComputerDesktopDriver(
    computer.driver,
    scenario,
    identity,
    { authority: computer.authority },
  );

  const observer = await journey.startIndependentEvidenceObserver({
    scenario,
    identity,
    desktopDriver: trusted,
    evidenceRoot: root,
    runtimeEnvironment: {},
    timeoutMs: 2000,
  });
  t.after(async () => { await observer.close(); });

  assert.notEqual(observer.ready.processId, process.pid);
  assert.equal(observer.ready.parentProcessId, process.pid);
  assert.equal(observer.ready.qaOwnerRefHash, digest(scenario.owner.ownerId));
  assert.equal(observer.ready.candidateDigest, identity.candidateDigest);

  const observed = await journey.readOwnerBoundComputerState(trusted, scenario);
  const accepted = await observer.observe(observed);
  assert.equal(accepted.accepted, true);

  const forged = { ...observed, proof: `ed25519:${Buffer.alloc(64).toString("base64url")}` };
  await assert.rejects(
    () => observer.observe(forged),
    /independent_observer_computer_observation_untrusted/,
  );
});

test("independent observer never accepts a fake process, substituted key, foreign owner, or parent-written ready record", (t) => {
  const root = privateRoot(t);
  const scenario = scenarioAt(root);
  const identity = installedIdentity();
  const computer = externalComputerBridge(scenario, identity);
  const forgedReady = {
    contractVersion: 1,
    caseId: "TR-026",
    producer: scenario.evidence.producer,
    manifestName: scenario.evidence.manifestName,
    ownerRefHash: identity.ownerRefHash,
    qaOwnerRefHash: digest(scenario.owner.ownerId),
    conversationRefHash: digest(scenario.conversation.conversationId),
    candidateDigest: identity.candidateDigest,
    artifactDigest: identity.artifactDigest,
    computerProvenanceSha256: digest(canonicalJson(computer.driver.provenance)),
    processId: process.ppid,
    parentProcessId: process.pid,
    observerNonce: "f".repeat(64),
    observerPublicKey: "fake",
    proof: "ed25519:fake",
  };

  assert.throws(
    () => journey.assertIndependentObserverReady(forgedReady, scenario, identity, computer.driver, {
      currentProcessId: process.pid,
      expectedProcessId: process.ppid,
      expectedNonce: "f".repeat(64),
    }),
    /independent_installed_evidence_producer_unavailable/,
  );
});

test("every desktop observation is bound to its exact external Computer action and signature", async (t) => {
  const scenario = scenarioAt(privateRoot(t));
  const computer = externalComputerBridge(scenario, installedIdentity());
  const adapter = journey.assertComputerDesktopDriver(
    computer.driver,
    scenario,
    installedIdentity(),
    { authority: computer.authority },
  );
  const observed = await journey.readOwnerBoundComputerState(adapter, scenario);

  assert.equal(journey.assertComputerAction(observed, adapter, "get_app_state"), observed);
  for (const mutate of [
    (value) => { value.source = "synthetic_desktop"; },
    (value) => { value.ownerId = "different-owner"; },
    (value) => { value.proof = `ed25519:${Buffer.alloc(64).toString("base64url")}`; },
  ]) {
    const changed = structuredClone(observed);
    mutate(changed);
    assert.throws(
      () => journey.assertComputerAction(changed, adapter, "get_app_state"),
      /computer_plugin_desktop_observation_untrusted/,
    );
  }
});

test("independent evidence observer binds its real signed process, exact owner, candidate, and Computer bridge", async (t) => {
  const scenario = scenarioAt(privateRoot(t));
  const identity = installedIdentity();
  const computer = externalComputerBridge(scenario, identity);
  const desktop = journey.assertComputerDesktopDriver(
    computer.driver,
    scenario,
    identity,
    { authority: computer.authority },
  );
  const observer = await journey.startIndependentEvidenceObserver({
    scenario,
    identity,
    desktopDriver: desktop,
    evidenceRoot: path.dirname(scenario.runtime.runtimeRoot),
    runtimeEnvironment: {},
    timeoutMs: 2000,
  });
  t.after(async () => observer.close());
  const ready = observer.ready;
  const checks = {
    currentProcessId: process.pid,
    expectedProcessId: ready.processId,
    expectedNonce: ready.observerNonce,
  };

  assert.equal(
    journey.assertIndependentObserverReady(ready, scenario, identity, desktop, checks),
    ready,
  );
  for (const mutate of [
    (value) => { value.producer = "fixture_observer"; },
    (value) => { value.manifestName = "different.json"; },
    (value) => { value.ownerRefHash = digest("different-owner"); },
    (value) => { value.qaOwnerRefHash = digest("different-qa-owner"); },
    (value) => { value.conversationRefHash = digest("different-conversation"); },
    (value) => { value.candidateDigest = digest("different-candidate"); },
    (value) => { value.artifactDigest = digest("different-artifact"); },
    (value) => { value.computerProvenanceSha256 = digest("different-computer"); },
    (value) => { value.processId = process.pid; },
    (value) => { value.processId = 0; },
    (value) => { value.parentProcessId = process.ppid; },
    (value) => { value.observerNonce = "f".repeat(64); },
    (value) => { value.proof = `ed25519:${Buffer.alloc(64).toString("base64url")}`; },
  ]) {
    const changed = structuredClone(ready);
    mutate(changed);
    assert.throws(
      () => journey.assertIndependentObserverReady(changed, scenario, identity, desktop, checks),
      /independent_installed_evidence_producer_unavailable/,
    );
  }

});

test("trusted ingress binds exact owner, conversation, message, update, chat, thread, and source sequence", (t) => {
  const scenario = scenarioAt(privateRoot(t));
  const ingress = trustedIngress(scenario, "first");
  assert.deepEqual(journey.bindTrustedIngress(scenario, ingress, "first"), ingress);

  for (const mutate of [
    (value) => { value.source = "fabricated_request"; },
    (value) => { value.ownerId = "other-owner"; },
    (value) => { value.ownerUserId += 1; },
    (value) => { value.chatId += 1; },
    (value) => { value.threadId += 1; },
    (value) => { value.conversationId = "other-conversation"; },
    (value) => { value.messageId += 1; },
    (value) => { value.updateId += 1; },
    (value) => { value.sourceSequence = 100; },
    (value) => { value.observedAt = "not-a-time"; },
  ]) {
    const changed = structuredClone(ingress);
    mutate(changed);
    assert.throws(() => journey.bindTrustedIngress(scenario, changed, "first"), /trusted_telegram_ingress_binding_invalid/);
  }
});

test("arm envelope is derived from authenticated first ingress and the exact one-shot target", (t) => {
  const scenario = scenarioAt(privateRoot(t));
  const scope = journey.buildArmScope(scenario, trustedIngress(scenario, "first"));

  assert.deepEqual(scope, {
    contractVersion: 1,
    caseId: "TR-026",
    ownerUserId: 700001,
    chatId: 700002,
    threadId: 0,
    staleSourceSequence: 4101,
    sourceSequence: 4102,
    updateId: 880002,
    ttlSeconds: 120,
  });
  assert.equal(Object.hasOwn(scope, "conversationId"), false);
  assert.equal(Object.hasOwn(scope, "caseToken"), false);

  assert.doesNotThrow(() => journey.assertArmReceipt(
    { armed: true, artifactRef: ARTIFACT_REF, delayMs: 280, sessionRef: SESSION_REF },
    { sessionRef: SESSION_REF },
  ));
  assert.throws(
    () => journey.assertArmReceipt(
      { armed: true, artifactRef: ARTIFACT_REF, delayMs: 279, sessionRef: SESSION_REF },
      { sessionRef: SESSION_REF },
    ),
    /authentic_280ms_race_control_unavailable/,
  );
});

test("audit must prove one exact authenticated event was claimed and delayed by 280ms", (t) => {
  const scenario = scenarioAt(privateRoot(t));
  const scope = journey.buildArmScope(scenario, trustedIngress(scenario, "first"));
  const eventDigest = digest("synthetic-authenticated-source");
  const armed = { artifactRef: ARTIFACT_REF, sessionRef: SESSION_REF, delayMs: 280 };
  const audit = { caseId: "TR-026", sessionRef: SESSION_REF, evidence: auditRecords(eventDigest) };

  assert.equal(journey.assessAuthenticatedAudit(audit, armed, scope, eventDigest).delayMs, 280);

  for (const mutate of [
    (value) => { value.evidence[0].event_digest = digest("other-event"); },
    (value) => { value.evidence[1].configured_delay_ms = 279; },
    (value) => { value.evidence[1].artifact_ref = "d".repeat(16); },
    (value) => { value.evidence[1].reason = "fixture"; },
    (value) => { value.evidence.reverse(); },
    (value) => { value.evidence = value.evidence.slice(0, 1); },
  ]) {
    const changed = structuredClone(audit);
    mutate(changed);
    assert.throws(
      () => journey.assessAuthenticatedAudit(changed, armed, scope, eventDigest),
      /authenticated_280ms_race_audit_unavailable/,
    );
  }
});

test("revision keeps both exact user messages and one emoji-leading revised answer without stale text", (t) => {
  const scenario = scenarioAt(privateRoot(t));
  const observation = rapidObservation(scenario);
  const result = journey.assessRapidRevision({
    scenario,
    first: trustedIngress(scenario, "first"),
    revision: trustedIngress(scenario, "revision"),
    observation,
  });
  assert.equal(result.finalReplyCount, 1);
  assert.equal(result.revision, 2);

  for (const [reason, mutate] of [
    ["trusted_source_order_unproven", (value) => { value.sourceSequences[1] = 101; }],
    ["original_telegram_user_messages_missing", (value) => { value.userBubbles.pop(); }],
    ["original_telegram_user_messages_missing", (value) => { value.userBubbles.reverse(); }],
    ["original_telegram_user_messages_missing", (value) => { value.userBubbles[0].text = "altered source"; }],
    ["one_revised_logical_turn_required", (value) => { value.correctedTurnRefHash = digest("other-turn"); }],
    ["exactly_one_final_revised_reply_required", (value) => { value.finalReplies.push(structuredClone(value.finalReplies[0])); }],
    ["emoji_leading_revised_reply_required", (value) => { value.finalReplies[0].text = "REVISED_SAFE"; }],
    ["revised_reply_content_unproven", (value) => { value.finalReplies[0].text = "✅ unrelated answer"; }],
    ["stale_first_reply_visible", (value) => { value.staleReplyVisible = true; }],
    ["stale_first_reply_visible", (value) => { value.finalReplies[0].text = "✅ REVISED_SAFE STALE_SAFE"; }],
    ["reopened_telegram_revision_unproven", (value) => { value.reopenedMatches = false; }],
  ]) {
    const changed = structuredClone(observation);
    mutate(changed);
    assert.throws(
      () => journey.assessRapidRevision({
        scenario,
        first: trustedIngress(scenario, "first"),
        revision: trustedIngress(scenario, "revision"),
        observation: changed,
      }),
      new RegExp(reason),
      reason,
    );
  }
});

test("post-commit source opens a different first-revision turn after the prior commit", (t) => {
  const scenario = scenarioAt(privateRoot(t));
  const turnRefHash = digest("synthetic-logical-turn");
  const observation = postCommitObservation(scenario, turnRefHash);

  assert.equal(journey.assessPostCommitControl(scenario, observation, turnRefHash).revision, 1);
  for (const mutate of [
    (value) => { value.followUpTurnRefHash = turnRefHash; },
    (value) => { value.followUpRevision = 2; },
    (value) => { value.sourceObservedAt = value.previousCommittedAt; },
    (value) => { value.sourceSequence = 101; },
    (value) => { value.ownerId = "other-owner"; },
  ]) {
    const changed = structuredClone(observation);
    mutate(changed);
    assert.throws(
      () => journey.assessPostCommitControl(scenario, changed, turnRefHash),
      /post_commit_normal_follow_up_unproven/,
    );
  }
});

test("two owner-scoped workers keep their identities and never fail or cancel during the race", (t) => {
  const scenario = scenarioAt(privateRoot(t));
  const before = workerSnapshot(scenario);
  const after = workerSnapshot(scenario, "completed");

  assert.equal(journey.assessWorkersUnaffected(before, after, scenario).workerCount, 2);
  for (const mutate of [
    (value) => { value.pop(); },
    (value) => { value[0].ownerId = "other-owner"; },
    (value) => { value[0].workerRef = "different-worker"; },
    (value) => { value[0].runRef = "different-run"; },
    (value) => { value[0].state = "cancelled"; },
    (value) => { value[0].cancelRequested = true; },
  ]) {
    const changed = structuredClone(after);
    mutate(changed);
    assert.throws(
      () => journey.assessWorkersUnaffected(before, changed, scenario),
      /two_owner_scoped_workers_affected/,
    );
  }
});

test("independent verifier must own PASS and bind all exact gates, candidate, session, and turn", () => {
  const identity = installedIdentity();
  const turnRefHash = digest("turn");
  const verified = verifiedResult(identity, turnRefHash);

  assert.doesNotThrow(() => journey.assessIndependentVerifier(verified, identity, SESSION_REF, turnRefHash));
  for (const mutate of [
    (value) => { value.status = "BLOCKED"; },
    (value) => { value.ready = false; },
    (value) => { value.artifactDigest = digest("different-artifact"); },
    (value) => { value.manifest.correlation.ownerRefHash = digest("different-installed-owner"); },
    (value) => { value.manifest.correlation.sessionRef = `qa_${"d".repeat(24)}`; },
    (value) => { value.manifest.correlation.turnRefHash = digest("different-turn"); },
    (value) => { value.gates[0].status = "FAIL"; },
    (value) => { value.gates.pop(); },
  ]) {
    const changed = structuredClone(verified);
    mutate(changed);
    assert.throws(
      () => journey.assessIndependentVerifier(changed, identity, SESSION_REF, turnRefHash),
      /independent_semantic_verifier_evidence_unavailable/,
    );
  }
});

test("public and private summaries redact identities, raw text, tokens, and machine paths", () => {
  const secret = "synthetic-token-that-must-never-appear";
  const privatePath = path.join(os.tmpdir(), "synthetic-private-location");
  const sensitiveReferences = [
    "synthetic-session-reference",
    "synthetic-artifact-reference",
    "synthetic-worker-reference",
    "synthetic-run-reference",
    "synthetic-work-reference",
  ];
  const result = journey.buildPublicSummary({
    result: {
      status: "BLOCKED",
      blocker: `missing ${secret} ${privatePath}`,
      evidence: {
        ownerId: "synthetic-owner-identity",
        caseToken: secret,
        conversationId: "synthetic-conversation-identity",
        text: "synthetic private user text",
      },
    },
    qaRunId: "synthetic-run-identity",
  });

  const serialized = JSON.stringify(result);
  assert.equal(result.status, "BLOCKED");
  assert.equal(result.receiptEligible, false);
  for (const forbidden of [secret, privatePath, "synthetic-owner-identity", "synthetic-conversation-identity", "synthetic private user text"]) {
    assert.equal(serialized.includes(forbidden), false, forbidden);
  }

  const redacted = JSON.stringify(journey.redactPrivateEvidence({
    ownerId: "synthetic-owner-identity",
    caseToken: secret,
    runtimePath: privatePath,
    text: "synthetic private user text",
    sessionRef: sensitiveReferences[0],
    artifactRef: sensitiveReferences[1],
    workerRef: sensitiveReferences[2],
    runRef: sensitiveReferences[3],
    workRef: sensitiveReferences[4],
    nested: { conversationId: "synthetic-conversation-identity", configuredDelayMs: 280 },
  }));
  for (const forbidden of [
    secret,
    privatePath,
    "synthetic-owner-identity",
    "synthetic-conversation-identity",
    "synthetic private user text",
    ...sensitiveReferences,
  ]) {
    assert.equal(redacted.includes(forbidden), false, forbidden);
  }
  assert.equal(redacted.includes("280"), true);
});

test("TR-026 synthetic cleanup deletes only exact owner-bound run messages and keeps the existing conversation", async (t) => {
  const scenario = scenarioAt(privateRoot(t));
  const owner = { _id: scenario.owner.ownerId, email: scenario.owner.email, role: "USER" };
  const inventory = {
    ownerId: scenario.owner.ownerId,
    conversationId: scenario.conversation.conversationId,
    startedAtMs: 1000,
    createdConversation: false,
    telegramMessageIds: [scenario.source.first.messageId, scenario.source.revision.messageId],
    messages: [{
      _id: "tr026-message-one",
      user: scenario.owner.ownerId,
      conversationId: scenario.conversation.conversationId,
      messageId: "tr026-source-message-one",
      createdAt: new Date(2000),
    }],
    ingress: [{
      _id: "tr026-ingress-one",
      telegramUserId: scenario.owner.telegramUserId,
      telegramChatId: scenario.owner.telegramChatId,
      conversationId: scenario.conversation.conversationId,
      createdAt: new Date(2000),
    }],
    conversations: [],
  };
  const removed = [];
  const database = {
    collection(name) {
      return {
        async findOne(query) {
          if (name === "users") return owner;
          return (name === "messages" ? inventory.messages : inventory.ingress)
            .find((record) => record._id === query._id) || null;
        },
        async deleteOne(query) {
          removed.push({ name, query });
          return { deletedCount: 1 };
        },
      };
    },
  };

  const result = await journey.cleanupOwnerScopedSyntheticTelegramRecords({
    database,
    scenario,
    environment: safeEnvironment(),
    owner,
    inventory,
    async removeRemote(messageIds) { return { deleted: true, messageIds }; },
  });

  assert.equal(result.cleaned, true);
  assert.equal(removed.some((entry) => entry.name === "conversations"), false);
  assert.equal(removed[0].query.user, scenario.owner.ownerId);

  const crossAccount = structuredClone(inventory);
  crossAccount.ingress[0].telegramChatId = "900002";
  await assert.rejects(
    () => journey.cleanupOwnerScopedSyntheticTelegramRecords({
      database,
      scenario,
      environment: safeEnvironment(),
      owner,
      inventory: crossAccount,
      async removeRemote() { throw new Error("foreign chat must remain untouched"); },
    }),
    /synthetic_telegram_cleanup_owner_mismatch/,
  );
});

test("fixture driver executes authentic stages in order and cleans up without emitting a receipt", async (t) => {
  const scenario = scenarioAt(privateRoot(t));
  const identity = installedIdentity();
  const rapid = rapidObservation(scenario);
  const eventDigest = digest("synthetic-authenticated-source");
  const calls = [];
  const driver = {
    async preflightInstalledCandidate() { calls.push("preflight"); return identity; },
    async assertComputerDesktopProvenance() { calls.push("computer"); return { provider: "@oai/sky", verified: true }; },
    async probeTelegramIdentity() { calls.push("identity"); return observedIdentity(scenario); },
    async requireIndependentEvidenceProducer() { calls.push("producer"); },
    async observeWorkers(stage) { calls.push(`workers:${stage}`); return workerSnapshot(scenario, stage === "after" ? "completed" : "running"); },
    async activateQaControl() { calls.push("activate"); return { caseId: "TR-026", sessionRef: SESSION_REF }; },
    async restartRuntime(stage) { calls.push(`restart:${stage}`); return { restarted: true }; },
    async requireRestartReady() { calls.push("ready"); return { sessionRef: SESSION_REF, restartState: "ready", requiredServices: ["librechat-core", "telegram-bot"], acknowledgedServices: ["librechat-core", "telegram-bot"], missingServices: [] }; },
    async sendTelegramSegment(stage) { calls.push(`send:${stage}`); return { sent: true, source: "computer_plugin_sky" }; },
    async observeTrustedIngress(stage) { calls.push(`ingress:${stage}`); return trustedIngress(scenario, stage); },
    async armTelegramRace(scope) { calls.push("arm"); assert.equal(scope.sourceSequence, 4102); return { armed: true, artifactRef: ARTIFACT_REF, delayMs: 280, sessionRef: SESSION_REF }; },
    async observeRapidRevision() { calls.push("revision"); return rapid; },
    async observePostCommitControl() { calls.push("post-commit"); return postCommitObservation(scenario, rapid.turnRefHash); },
    async expectedAuditEventDigest() { calls.push("event-digest"); return eventDigest; },
    async auditTelegramRace() { calls.push("audit"); return { caseId: "TR-026", sessionRef: SESSION_REF, evidence: auditRecords(eventDigest) }; },
    async verifyIndependentEvidence() { calls.push("verify"); return verifiedResult(identity, rapid.turnRefHash); },
    async cleanupSyntheticTelegramConversation() {
      calls.push("synthetic-cleanup");
      return {
        cleaned: true,
        ownerId: scenario.owner.ownerId,
        conversationId: scenario.conversation.conversationId,
      };
    },
    async cleanupTelegramRace() { calls.push("cleanup"); return { cleaned: true, sessionRef: SESSION_REF }; },
    async clearQaControl() { calls.push("clear"); return { cleared: true, sessionRef: SESSION_REF }; },
    async close() { calls.push("close"); },
  };

  const result = await journey.executeInstalledJourney({ driver, scenario, environment: safeEnvironment() });

  assert.equal(result.status, "PASS");
  assert.equal(result.receiptEligible, false);
  assert.deepEqual(calls, [
    "preflight", "computer", "identity", "producer", "workers:before", "activate", "restart:activate", "ready",
    "send:first", "ingress:first", "arm", "send:revision", "ingress:revision", "revision",
    "send:postCommit", "ingress:postCommit", "post-commit", "event-digest", "audit",
    "workers:after", "verify", "synthetic-cleanup", "cleanup", "clear", "restart:cleanup", "close",
  ]);
});

test("missing supported installed evidence producer blocks before activation, restart, and Telegram mutation", async (t) => {
  const scenario = scenarioAt(privateRoot(t));
  const calls = [];
  const driver = {
    async preflightInstalledCandidate() { calls.push("preflight"); return installedIdentity(); },
    async assertComputerDesktopProvenance() { calls.push("computer"); return { provider: "@oai/sky", verified: true }; },
    async probeTelegramIdentity() { calls.push("identity"); return observedIdentity(scenario); },
    async requireIndependentEvidenceProducer() { calls.push("producer"); throw journey.blockedError("independent_installed_evidence_producer_unavailable"); },
    async activateQaControl() { calls.push("FORBIDDEN_ACTIVATION"); },
    async sendTelegramSegment() { calls.push("FORBIDDEN_TELEGRAM"); },
    async restartRuntime() { calls.push("FORBIDDEN_RESTART"); },
    async close() { calls.push("close"); },
  };

  const result = await journey.executeInstalledJourney({ driver, scenario, environment: safeEnvironment() });

  assert.equal(result.status, "BLOCKED");
  assert.equal(result.blocker, "independent_installed_evidence_producer_unavailable");
  assert.equal(result.receiptEligible, false);
  assert.deepEqual(calls, ["preflight", "computer", "identity", "producer", "close"]);
});

test("missing Computer sky provenance blocks before desktop access, control activation, restart, or mutation", async (t) => {
  const scenario = scenarioAt(privateRoot(t));
  const calls = [];
  const driver = {
    async preflightInstalledCandidate() { calls.push("preflight"); return installedIdentity(); },
    async assertComputerDesktopProvenance() { calls.push("computer"); throw journey.blockedError("computer_plugin_desktop_driver_unavailable"); },
    async probeTelegramIdentity() { calls.push("FORBIDDEN_DESKTOP"); },
    async activateQaControl() { calls.push("FORBIDDEN_ACTIVATION"); },
    async sendTelegramSegment() { calls.push("FORBIDDEN_TELEGRAM"); },
    async restartRuntime() { calls.push("FORBIDDEN_RESTART"); },
    async close() { calls.push("close"); },
  };

  const result = await journey.executeInstalledJourney({ driver, scenario, environment: safeEnvironment() });

  assert.equal(result.status, "BLOCKED");
  assert.equal(result.blocker, "computer_plugin_desktop_driver_unavailable");
  assert.deepEqual(calls, ["preflight", "computer", "close"]);
});

test("fully consented CLI without an injected Computer driver blocks before installed service access", async (t) => {
  const root = privateRoot(t);
  const scenario = scenarioAt(root);
  const scenarioPath = privateFile(path.join(root, "scenario.json"), scenario);

  const result = await journey.main(
    [
      "--local-qa",
      "--allow-telegram-mutation",
      "--allow-runtime-restart",
      "--evidence-root",
      root,
      "--scenario",
      scenarioPath,
    ],
    safeEnvironment(),
  );

  assert.equal(result.status, "BLOCKED");
  assert.equal(result.blocker, "computer_plugin_desktop_driver_unavailable");
  assert.deepEqual(fs.readdirSync(root), ["scenario.json"]);
});

test("a failed independent verifier cannot become PASS and still clears the armed installed session", async (t) => {
  const scenario = scenarioAt(privateRoot(t));
  const identity = installedIdentity();
  const rapid = rapidObservation(scenario);
  const eventDigest = digest("synthetic-authenticated-source");
  const calls = [];
  const driver = {
    async preflightInstalledCandidate() { return identity; },
    async assertComputerDesktopProvenance() { return { provider: "@oai/sky", verified: true }; },
    async probeTelegramIdentity() { return observedIdentity(scenario); },
    async requireIndependentEvidenceProducer() {},
    async observeWorkers(stage) { return workerSnapshot(scenario, stage === "after" ? "completed" : "running"); },
    async activateQaControl() { return { caseId: "TR-026", sessionRef: SESSION_REF }; },
    async restartRuntime(stage) { calls.push(`restart:${stage}`); return { restarted: true }; },
    async requireRestartReady() { return { sessionRef: SESSION_REF, restartState: "ready", requiredServices: ["librechat-core", "telegram-bot"], acknowledgedServices: ["librechat-core", "telegram-bot"], missingServices: [] }; },
    async sendTelegramSegment() { return { sent: true, source: "computer_plugin_sky" }; },
    async observeTrustedIngress(stage) { return trustedIngress(scenario, stage); },
    async armTelegramRace() { return { armed: true, artifactRef: ARTIFACT_REF, delayMs: 280, sessionRef: SESSION_REF }; },
    async observeRapidRevision() { return rapid; },
    async observePostCommitControl() { return postCommitObservation(scenario, rapid.turnRefHash); },
    async expectedAuditEventDigest() { return eventDigest; },
    async auditTelegramRace() { return { caseId: "TR-026", sessionRef: SESSION_REF, evidence: auditRecords(eventDigest) }; },
    async verifyIndependentEvidence() { return { status: "BLOCKED", ready: false }; },
    async cleanupSyntheticTelegramConversation() {
      calls.push("synthetic-cleanup");
      return {
        cleaned: true,
        ownerId: scenario.owner.ownerId,
        conversationId: scenario.conversation.conversationId,
      };
    },
    async cleanupTelegramRace() { calls.push("cleanup"); return { cleaned: true, sessionRef: SESSION_REF }; },
    async clearQaControl() { calls.push("clear"); return { cleared: true, sessionRef: SESSION_REF }; },
    async close() { calls.push("close"); },
  };

  const result = await journey.executeInstalledJourney({ driver, scenario, environment: safeEnvironment() });

  assert.equal(result.status, "BLOCKED");
  assert.equal(result.blocker, "independent_semantic_verifier_evidence_unavailable");
  assert.deepEqual(calls, [
    "restart:activate", "synthetic-cleanup", "cleanup", "clear", "restart:cleanup", "close",
  ]);
});

test("a no-op, mismatched-session, or failed cleanup never becomes PASS", async (t) => {
  const scenario = scenarioAt(privateRoot(t));
  const identity = installedIdentity();
  const rapid = rapidObservation(scenario);
  const eventDigest = digest("synthetic-authenticated-source");

  for (const failure of ["cleanup", "cleanup-session", "clear", "clear-session", "restart"]) {
    const calls = [];
    const driver = {
      async preflightInstalledCandidate() { return identity; },
      async assertComputerDesktopProvenance() { return { provider: "@oai/sky", verified: true }; },
      async probeTelegramIdentity() { return observedIdentity(scenario); },
      async requireIndependentEvidenceProducer() {},
      async observeWorkers(stage) { return workerSnapshot(scenario, stage === "after" ? "completed" : "running"); },
      async activateQaControl() { return { caseId: "TR-026", sessionRef: SESSION_REF }; },
      async restartRuntime(stage) {
        calls.push(`restart:${stage}`);
        return { restarted: !(failure === "restart" && stage === "cleanup") };
      },
      async requireRestartReady() { return { sessionRef: SESSION_REF, restartState: "ready", requiredServices: ["librechat-core", "telegram-bot"], acknowledgedServices: ["librechat-core", "telegram-bot"], missingServices: [] }; },
      async sendTelegramSegment() { return { sent: true, source: "computer_plugin_sky" }; },
      async observeTrustedIngress(stage) { return trustedIngress(scenario, stage); },
      async armTelegramRace() { return { armed: true, artifactRef: ARTIFACT_REF, delayMs: 280, sessionRef: SESSION_REF }; },
      async observeRapidRevision() { return rapid; },
      async observePostCommitControl() { return postCommitObservation(scenario, rapid.turnRefHash); },
      async expectedAuditEventDigest() { return eventDigest; },
      async auditTelegramRace() { return { caseId: "TR-026", sessionRef: SESSION_REF, evidence: auditRecords(eventDigest) }; },
      async verifyIndependentEvidence() { return verifiedResult(identity, rapid.turnRefHash); },
      async cleanupSyntheticTelegramConversation() {
        return {
          cleaned: true,
          ownerId: scenario.owner.ownerId,
          conversationId: scenario.conversation.conversationId,
        };
      },
      async cleanupTelegramRace() {
        calls.push("cleanup");
        return {
          cleaned: failure !== "cleanup",
          sessionRef: failure === "cleanup-session" ? `qa_${"d".repeat(24)}` : SESSION_REF,
        };
      },
      async clearQaControl() {
        calls.push("clear");
        return {
          cleared: failure !== "clear",
          sessionRef: failure === "clear-session" ? `qa_${"d".repeat(24)}` : SESSION_REF,
        };
      },
      async close() { calls.push("close"); },
    };

    const result = await journey.executeInstalledJourney({ driver, scenario, environment: safeEnvironment() });

    assert.equal(result.status, "BLOCKED", failure);
    assert.equal(result.blocker, "installed_qa_control_cleanup_unavailable", failure);
    assert.ok(calls.includes("cleanup"), failure);
    assert.ok(calls.includes("clear"), failure);
    assert.ok(calls.includes("close"), failure);
  }
});
