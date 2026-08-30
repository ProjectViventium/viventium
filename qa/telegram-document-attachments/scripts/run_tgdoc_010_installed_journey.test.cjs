"use strict";

const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawn, spawnSync } = require("node:child_process");
const test = require("node:test");

const journey = require("./run_tgdoc_010_installed_journey.cjs");
const ROOT = path.resolve(__dirname, "../../..");
const RUNNER = path.join(__dirname, "run_tgdoc_010_installed_journey.cjs");
const COMPUTER_BRIDGE_SECRET = "synthetic-computer-bridge-source-test-secret-32-bytes";
const EXTERNAL_COMPUTER_KEYS = crypto.generateKeyPairSync("ed25519");

function externalComputerAuthority() {
  const publicKeyBytes = EXTERNAL_COMPUTER_KEYS.publicKey.export({ type: "spki", format: "der" });
  return {
    publicKey: EXTERNAL_COMPUTER_KEYS.publicKey,
    keyId: hash(publicKeyBytes),
    peerProcessId: process.ppid,
    sessionRef: "sky_external_owner_bound_session",
    unitTestHarness: {
      kind: "node_test_only",
      processId: process.pid,
      parentProcessId: process.ppid,
      testFile: __filename,
    },
  };
}

function externallySigned(payload) {
  return `ed25519:${crypto.sign(null, Buffer.from(canonicalJson(payload)), EXTERNAL_COMPUTER_KEYS.privateKey).toString("base64url")}`;
}

function exactActiveSelection(scenario, changes = {}) {
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
      ...(scenario.conversation ? { conversationRefHash: hash(scenario.conversation.conversationId) } : {}),
    },
    ...changes,
  };
}

function externallySignedComputerBridge(scenario, { selections, actionChanges } = {}) {
  const authority = externalComputerAuthority();
  const issuedAtMs = Date.now() - 1000;
  const unsignedProvenance = {
    contractVersion: 1,
    caseId: scenario.caseId,
    provider: "@oai/sky",
    controlPlane: "computer_plugin_node_repl",
    interface: "sky.get_app_state/sky-primitives",
    skyMethods: ["click", "press_key", "paste", "type_text"],
    ownerId: scenario.owner.ownerId,
    telegramUserId: scenario.owner.telegramUserId,
    telegramChatId: scenario.owner.telegramChatId,
    appBundleId: scenario.telegram.bundleId,
    sessionRef: authority.sessionRef,
    authorityKeyId: authority.keyId,
    peerProcessId: authority.peerProcessId,
    issuedAtMs,
    expiresAtMs: issuedAtMs + 60000,
  };
  const calls = [];
  let selectionIndex = 0;
  const driver = {
    provenance: { ...unsignedProvenance, proof: externallySigned(unsignedProvenance) },
    async get_app_state(request) {
      calls.push({ kind: "get_app_state", request });
      const selection = selections?.[Math.min(selectionIndex, selections.length - 1)] ||
        exactActiveSelection(scenario);
      selectionIndex += 1;
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
      return { ...unsigned, proof: externallySigned(unsigned) };
    },
    async do_action(request) {
      calls.push({ kind: "do_action", request });
      const unsigned = {
        source: `@oai/sky.${request.skyMethod}`,
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
        activeSelection: exactActiveSelection(scenario),
        action: request.action,
        skyMethod: request.skyMethod,
        status: request.action === "telegram.delete_synthetic_messages" ? "deleted" : "sent",
        ...(actionChanges || {}),
      };
      return { ...unsigned, proof: externallySigned(unsigned) };
    },
  };
  return { authority, driver, calls };
}

function callerMintedComputerBridge(scenario, peerProcessId) {
  const keys = crypto.generateKeyPairSync("ed25519");
  const baseline = externallySignedComputerBridge(scenario);
  const authority = {
    publicKey: keys.publicKey,
    keyId: hash(keys.publicKey.export({ type: "spki", format: "der" })),
    peerProcessId,
    sessionRef: "sky_caller_invented_session",
  };
  const sign = (unsigned) => `ed25519:${crypto.sign(
    null,
    Buffer.from(canonicalJson(unsigned)),
    keys.privateKey,
  ).toString("base64url")}`;
  const { proof: _discarded, ...previous } = baseline.driver.provenance;
  const provenance = {
    ...previous,
    sessionRef: authority.sessionRef,
    authorityKeyId: authority.keyId,
    peerProcessId,
  };
  const driver = {
    ...baseline.driver,
    provenance: { ...provenance, proof: sign(provenance) },
    async get_app_state(request) {
      const observed = await baseline.driver.get_app_state(request);
      const { proof: _ignored, ...unsigned } = observed;
      const forged = { ...unsigned, peerProcessId, sessionRef: authority.sessionRef };
      return { ...forged, proof: sign(forged) };
    },
  };
  return { authority, driver };
}

function hash(value) {
  return crypto.createHash("sha256").update(value).digest("hex");
}

function privateRoot(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "tgdoc-010-source-test-"));
  fs.chmodSync(root, 0o700);
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  return root;
}

function privateFile(location, bytes) {
  fs.mkdirSync(path.dirname(location), { recursive: true, mode: 0o700 });
  fs.chmodSync(path.dirname(location), 0o700);
  fs.writeFileSync(location, bytes, { mode: 0o600 });
  fs.chmodSync(location, 0o600);
  return location;
}

function diagnosticEnv(extra = {}) {
  return {
    PATH: process.env.PATH || "",
    VIVENTIUM_QA_ALLOW_TGDOC_010_DIAGNOSTIC: "1",
    VIVENTIUM_QA_ALLOW_TGDOC_010_TELEGRAM_MUTATION: "1",
    VIVENTIUM_QA_ALLOW_TGDOC_010_RESTART: "1",
    VIVENTIUM_QA_ALLOW_TGDOC_010_COMPUTER_BRIDGE: "1",
    VIVENTIUM_QA_OWNER_EMAIL: "owner@example.com",
    VIVENTIUM_QA_OWNER_TELEGRAM_USER_ID: "900001",
    VIVENTIUM_QA_OWNER_TELEGRAM_CHAT_ID: "900002",
    VIVENTIUM_QA_OWNER_TELEGRAM_ACCOUNT_LABEL: "Personal account",
    VIVENTIUM_QA_ALLOW_LOCAL_JWT: "1",
    VIVENTIUM_QA_EMAIL: "qa@example.com",
    JWT_SECRET: "synthetic-source-test-access-secret",
    JWT_REFRESH_SECRET: "synthetic-source-test-refresh-secret",
    ...extra,
  };
}

function scenarioAt(root) {
  const inputSpecs = [
    ["document", "document.txt", "TGDOC-DOC-01", "synthetic public document\n", "", ""],
    ["image", "same-name.png", "TGDOC-IMAGE-01", "synthetic public image one\n", "album-one", "TGDOC-010 synthetic album"],
    ["image", "same-name.png", "TGDOC-IMAGE-02", "synthetic public image two\n", "album-one", ""],
    ["audio", "audio.wav", "TGDOC-AUDIO-01", "synthetic public audio\n", "", ""],
    ["video", "video.mp4", "TGDOC-VIDEO-01", "synthetic public video\n", "", ""],
    ["prior_artifact", "prior.html", "TGDOC-PRIOR-01", "<html>synthetic public artifact</html>\n", "", ""],
  ];
  const inputs = inputSpecs.map(([family, filename, visibleIdentity, content, groupId, caption], index) => {
    const sourcePath = privateFile(path.join(root, "fixtures", String(index), filename), Buffer.from(content));
    return {
      family,
      filename,
      visibleIdentity,
      sourcePath,
      ownerId: "qa-owner-alpha",
      sha256: hash(Buffer.from(content)),
      sizeBytes: Buffer.byteLength(content),
      groupId,
      caption,
      position: index,
    };
  });
  return {
    contractVersion: 1,
    caseId: "TGDOC-010",
    classification: "synthetic_public_safe",
    owner: {
      ownerId: "qa-owner-alpha",
      email: "qa@example.com",
      telegramUserId: "700001",
      telegramChatId: "700002",
      synthetic: true,
    },
    telegram: {
      bundleId: "ru.keepcoder.Telegram",
      accountLabel: "TGDOC synthetic QA account",
      chatLabel: "TGDOC synthetic QA bot",
    },
    runtime: {
      clientUrl: "http://127.0.0.1:3080",
      apiUrl: "http://127.0.0.1:3080",
      installedRoot: path.join(root, "installed"),
      runtimeRoot: path.join(root, "runtime"),
      artifactIdentityPath: path.join(root, "runtime", "identity.json"),
      runtimeOwnerStatePath: path.join(root, "runtime", "owner.json"),
      glassHiveDbPath: path.join(root, "runtime", "glasshive.sqlite3"),
      coreTracePath: path.join(root, "runtime", "core.jsonl"),
      mainAgentId: "qa-main-agent",
      primaryProviderId: "provider-primary",
      fallbackProviderId: "provider-fallback",
      requiredToolIds: ["tool.file.read", "tool.url.fetch"],
    },
    inputs,
    mission: {
      marker: "TGDOC-010-SYNTHETIC",
      sourceUrl: "https://example.com/tgdoc-010-synthetic",
      outputIdentity: "TGDOC-OUTPUT-01.html",
      controlInstruction: "Preserve every authorized input and include the synthetic URL result.",
      minimumRuntimeOverlapMs: 100,
    },
    restart: {
      supported: true,
      executable: path.join(root, "installed", "bin", "viventium"),
      arguments: ["dev-runtime", "activate-current", "--validate", "--restart", "--allow-dirty-local-testing"],
      services: ["core", "glasshive", "telegram", "worker"],
    },
  };
}

function observedTelegramIdentity(scenario) {
  return {
    source: "telegram_desktop_accessibility",
    bundleId: scenario.telegram.bundleId,
    accountLabel: scenario.telegram.accountLabel,
    chatLabel: scenario.telegram.chatLabel,
    telegramUserId: scenario.owner.telegramUserId,
    telegramChatId: scenario.owner.telegramChatId,
    ownerId: scenario.owner.ownerId,
    linkedOwnerId: scenario.owner.ownerId,
    accountVisible: true,
    chatVisible: true,
    activeSelectionVerified: true,
  };
}

function computerBridgeProvenance(scenario, nowMs = Date.now(), changes = {}) {
  const authority = externalComputerAuthority();
  const unsigned = {
    contractVersion: 1,
    caseId: "TGDOC-010",
    provider: "@oai/sky",
    controlPlane: "computer_plugin_node_repl",
    interface: "sky.get_app_state/sky-primitives",
    skyMethods: ["click", "press_key", "paste", "type_text"],
    ownerId: scenario.owner.ownerId,
    telegramUserId: scenario.owner.telegramUserId,
    telegramChatId: scenario.owner.telegramChatId,
    appBundleId: scenario.telegram.bundleId,
    sessionRef: authority.sessionRef,
    authorityKeyId: authority.keyId,
    peerProcessId: authority.peerProcessId,
    issuedAtMs: nowMs - 1000,
    expiresAtMs: nowMs + 60000,
    ...changes,
  };
  return {
    ...unsigned,
    proof: externallySigned(unsigned),
  };
}

function sourceOnlyComputerBridge(scenario, { screenshotBytes, actionStatus, provenanceChanges } = {}) {
  const calls = [];
  const driver = {
    provenance: computerBridgeProvenance(scenario, Date.now(), provenanceChanges),
    async get_app_state(request) {
      calls.push({ kind: "get_app_state", request });
      const text = [
        scenario.telegram.accountLabel,
        scenario.telegram.chatLabel,
        scenario.mission.marker,
      ].join("\n");
      const unsigned = {
        source: "@oai/sky.get_app_state",
        app: request.app,
        ownerId: scenario.owner.ownerId,
        telegramUserId: scenario.owner.telegramUserId,
        telegramChatId: scenario.owner.telegramChatId,
        sessionRef: driver.provenance.sessionRef,
        peerProcessId: driver.provenance.peerProcessId,
        challenge: request.challenge,
        observedAtMs: Date.now(),
        activeSelection: exactActiveSelection(scenario),
        text,
        screenshotSha256: screenshotBytes ? hash(screenshotBytes) : "",
      };
      return {
        ...unsigned,
        ...(screenshotBytes ? { screenshotBytes } : {}),
        proof: externallySigned(unsigned),
      };
    },
    async do_action(request) {
      calls.push({ kind: "do_action", request });
      const unsigned = {
        source: `@oai/sky.${request.skyMethod}`,
        app: request.app,
        ownerId: scenario.owner.ownerId,
        telegramUserId: scenario.owner.telegramUserId,
        telegramChatId: scenario.owner.telegramChatId,
        sessionRef: driver.provenance.sessionRef,
        peerProcessId: driver.provenance.peerProcessId,
        challenge: request.challenge,
        selectionChallenge: request.selectionChallenge,
        selectionSha256: request.selectionSha256,
        observedAtMs: Date.now(),
        activeSelection: exactActiveSelection(scenario),
        action: request.action,
        skyMethod: request.skyMethod,
        status: actionStatus || (request.action === "telegram.send_grouped_attachments" ? "sent" : "opened"),
      };
      return {
        ...unsigned,
        proof: externallySigned(unsigned),
      };
    },
  };
  return { driver, calls };
}

function observedInputs(scenario) {
  const inputs = journey.inspectSyntheticInputs(scenario, { evidenceRoot: path.dirname(path.dirname(scenario.inputs[0].sourcePath)) });
  return inputs.map((input, index) => ({
    ownerId: scenario.owner.ownerId,
    workRef: "work-alpha",
    runRef: "run-alpha",
    fileId: `file-alpha-${index}`,
    filename: input.filename,
    family: input.family,
    visibleIdentity: input.visibleIdentity,
    position: input.position,
    groupId: input.groupId,
    caption: input.caption,
    bytes: Buffer.from(input.bytes),
    sha256: input.sha256,
    sizeBytes: input.sizeBytes,
  }));
}

function observedMission(scenario) {
  return {
    ownerId: scenario.owner.ownerId,
    workRef: "work-alpha",
    runRef: "run-alpha",
    workerRef: "worker-alpha",
    originSurface: "telegram",
    sourceWindow: { startedAtMs: 1000, endedAtMs: 4000 },
    workerWindow: { startedAtMs: 1800, endedAtMs: 5000 },
    runtimeInvokedAtMs: 1800,
    lease: {
      ownerId: scenario.owner.ownerId,
      workerRef: "worker-alpha",
      runRef: "run-alpha",
      acquiredAtMs: 1600,
      confirmedAtMs: 1700,
      releasedAtMs: 5100,
    },
  };
}

function observedBrokerReceipts(scenario, inputDigest) {
  return scenario.runtime.requiredToolIds.map((toolId, index) => ({
    receiptId: `tool-receipt-${index}`,
    ownerId: scenario.owner.ownerId,
    workRef: "work-alpha",
    runRef: "run-alpha",
    toolId,
    authorized: true,
    state: "completed",
    inputManifestSha256: inputDigest,
    observedAtMs: 2000 + index,
  }));
}

function observedFallback(scenario, inputDigest) {
  return {
    ownerId: scenario.owner.ownerId,
    workRef: "work-alpha",
    runRef: "run-alpha",
    attempts: [
      {
        attemptId: "attempt-primary",
        providerId: scenario.runtime.primaryProviderId,
        state: "provider_unavailable",
        inputManifestSha256: inputDigest,
      },
      {
        attemptId: "attempt-fallback",
        providerId: scenario.runtime.fallbackProviderId,
        state: "completed",
        inputManifestSha256: inputDigest,
      },
    ],
  };
}

function observedActiveFallback(scenario, inputDigest, mission) {
  const fallback = observedFallback(scenario, inputDigest);
  const attempt = fallback.attempts[1];
  attempt.state = "running";
  attempt.runtimeInvokedAtMs = 2000;
  attempt.lease = {
    leaseId: "lease-synthetic-fallback",
    ownerId: scenario.owner.ownerId,
    workerRef: mission.workerRef,
    runRef: mission.runRef,
    acquiredAtMs: 1600,
    confirmedAtMs: 1700,
    releasedAtMs: null,
    pid: 44001,
    processStartIdentity: "synthetic-worker-start",
  };
  fallback.terminalCallbackObserved = false;
  fallback.artifactObserved = false;
  return fallback;
}

function observedRestart(scenario, inputDigest) {
  return {
    ownerId: scenario.owner.ownerId,
    workRef: "work-alpha",
    runRef: "run-alpha",
    supported: true,
    performed: true,
    recovered: true,
    beforeRuntimeIdentity: "runtime-before",
    afterRuntimeIdentity: "runtime-after",
    beforeInputManifestSha256: inputDigest,
    afterInputManifestSha256: inputDigest,
    services: [...scenario.restart.services],
  };
}

function observedArtifact(scenario) {
  const bytes = Buffer.from("<html>TGDOC-010 synthetic worker result</html>\n");
  const base = {
    ownerId: scenario.owner.ownerId,
    workRef: "work-alpha",
    runRef: "run-alpha",
    artifactId: "artifact-alpha",
    filename: scenario.mission.outputIdentity,
    bytes,
    sha256: hash(bytes),
  };
  return {
    worker: { ...base },
    telegram: {
      ...base,
      bytes: Buffer.from(bytes),
      visible: true,
      opened: true,
      assistantBubbleCount: 1,
      artifactDeliveryCount: 1,
      deliveryReceipts: [{ receiptId: "delivery-alpha", state: "sent", ownerId: base.ownerId, workRef: base.workRef }],
    },
    activeWork: { ...base, bytes: Buffer.from(bytes), visible: true, opened: true, headed: true },
  };
}

function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

function syntheticTraceRows(ownerId, originRef, workRef) {
  const prefixed = (value) => `sha256:${hash(value)}`;
  const ownerScopeHash = prefixed(`owner\0${ownerId}`);
  const originRefHash = prefixed(`origin\0${originRef}`);
  const workRefHash = prefixed(`work\0${workRef}`);
  let previousEventHash = `sha256:${"0".repeat(64)}`;
  return ["source.bound", "runtime.invoked", "work.completed", "callback.delivery.sent"].map((stage, index) => {
    const facts = { workRefHash };
    const row = {
      schemaVersion: 1,
      ownerScopeHash,
      originRefHash,
      sequence: index + 1,
      stage,
      at: new Date(1750000000000 + index * 1000).toISOString(),
      facts,
      eventKeyHash: prefixed(`event-${index}`),
      contentHash: prefixed(canonicalJson({ schemaVersion: 1, stage, facts })),
      previousEventHash,
    };
    row.eventHash = prefixed(canonicalJson(row));
    previousEventHash = row.eventHash;
    return row;
  });
}

test("dry-run is inert, source-only, and never release-ready or receipt-eligible", () => {
  const result = journey.dryRunPlan(journey.parseArgs(["--dry-run"]));

  assert.equal(result.caseId, "TGDOC-010");
  assert.equal(result.status, "DRY_RUN");
  assert.equal(result.sideEffects, false);
  assert.equal(result.releaseReady, false);
  assert.equal(result.receiptEligible, false);
  assert.equal(result.releaseLabel, "PRE-GATE / NOT READY");
  assert.equal(result.launchesBrowser, false);
  assert.equal(result.accessesDatabase, false);
  assert.equal(result.sendsTelegramMessages, false);
  assert.equal(result.restartsRuntime, false);
});

test("CLI dry-run does not create evidence or access an installed service", (t) => {
  const root = privateRoot(t);
  const untouched = path.join(root, "must-not-exist");
  const completed = spawnSync("node", [RUNNER, "--dry-run"], {
    cwd: ROOT,
    encoding: "utf8",
    env: { PATH: process.env.PATH || "", VIVENTIUM_QA_PRIVATE_DIR: untouched },
  });

  assert.equal(completed.status, 0, completed.stderr);
  assert.equal(JSON.parse(completed.stdout).sideEffects, false);
  assert.equal(fs.existsSync(untouched), false);
});

test("local diagnostic and Telegram mutation require separate explicit opt-ins", () => {
  assert.throws(
    () => journey.assertLocalDiagnosticOptIn({ localQa: false }, diagnosticEnv()),
    /local_qa_opt_in_required/,
  );
  assert.throws(
    () => journey.assertLocalDiagnosticOptIn({ localQa: true }, diagnosticEnv({ VIVENTIUM_QA_ALLOW_TGDOC_010_DIAGNOSTIC: "" })),
    /diagnostic_opt_in_required/,
  );
  assert.throws(
    () => journey.assertLocalDiagnosticOptIn({ localQa: true }, diagnosticEnv({ CI: "1" })),
    /local_diagnostic_only/,
  );
  assert.doesNotThrow(() => journey.assertLocalDiagnosticOptIn({ localQa: true }, diagnosticEnv()));
  assert.throws(
    () => journey.assertTelegramMutationConsent({ allowTelegramMutation: false }, diagnosticEnv()),
    /telegram_mutation_consent_required/,
  );
  assert.throws(
    () => journey.assertTelegramMutationConsent(
      { allowTelegramMutation: true },
      diagnosticEnv({ VIVENTIUM_QA_ALLOW_TGDOC_010_TELEGRAM_MUTATION: "" }),
    ),
    /telegram_mutation_consent_required/,
  );
});

test("restart is a third independent explicit consent and unsupported plans fail closed", () => {
  assert.throws(
    () => journey.assertRestartConsent({ allowRuntimeRestart: false }, diagnosticEnv(), { supported: true }),
    /runtime_restart_consent_required/,
  );
  assert.throws(
    () => journey.assertRestartConsent(
      { allowRuntimeRestart: true },
      diagnosticEnv({ VIVENTIUM_QA_ALLOW_TGDOC_010_RESTART: "" }),
      { supported: true },
    ),
    /runtime_restart_consent_required/,
  );
  assert.throws(
    () => journey.assertRestartConsent({ allowRuntimeRestart: true }, diagnosticEnv(), { supported: false }),
    /runtime_restart_unsupported/,
  );
});

test("desktop interaction requires an explicitly consented signed Computer Sky bridge for the exact synthetic owner", (t) => {
  const scenario = scenarioAt(privateRoot(t));
  const { driver } = sourceOnlyComputerBridge(scenario);

  const trusted = journey.assertAuthenticatedComputerDesktopDriver(driver, scenario, diagnosticEnv(), {
    authority: externalComputerAuthority(),
  });
  assert.equal(trusted.provenance.provider, "@oai/sky");

  assert.throws(
    () => journey.assertAuthenticatedComputerDesktopDriver(null, scenario, diagnosticEnv(), {
      authority: externalComputerAuthority(),
    }),
    /computer_desktop_driver_unavailable/,
  );
  assert.throws(
    () => journey.assertAuthenticatedComputerDesktopDriver(
      driver,
      scenario,
      diagnosticEnv({ VIVENTIUM_QA_ALLOW_TGDOC_010_COMPUTER_BRIDGE: "" }),
      { authority: externalComputerAuthority() },
    ),
    /computer_desktop_bridge_opt_in_required/,
  );

  for (const [reason, changes] of [
    ["computer_desktop_driver_provenance_invalid", { provider: "fake-desktop-controller" }],
    ["computer_desktop_driver_provenance_invalid", { controlPlane: "shell" }],
    ["computer_desktop_driver_owner_mismatch", { ownerId: "another-owner" }],
    ["computer_desktop_driver_owner_mismatch", { telegramUserId: "999999" }],
    ["computer_desktop_driver_owner_mismatch", { appBundleId: "com.other.app" }],
    ["computer_desktop_driver_attestation_expired", { expiresAtMs: Date.now() - 1 }],
  ]) {
    const variant = { ...driver, provenance: computerBridgeProvenance(scenario, Date.now(), changes) };
    assert.throws(
      () => journey.assertAuthenticatedComputerDesktopDriver(variant, scenario, diagnosticEnv(), {
        authority: externalComputerAuthority(),
      }),
      new RegExp(reason),
      reason,
    );
  }

  const forged = { ...driver, provenance: { ...driver.provenance, proof: `hmac-sha256:${"0".repeat(64)}` } };
  assert.throws(
    () => journey.assertAuthenticatedComputerDesktopDriver(forged, scenario, diagnosticEnv(), {
      authority: externalComputerAuthority(),
    }),
    /computer_desktop_driver_authentication_failed/,
  );
});

test("self-minted HMAC bridge and copied owner labels cannot replace an externally pinned Computer authority", (t) => {
  const scenario = scenarioAt(privateRoot(t));
  const selfMinted = sourceOnlyComputerBridge(scenario);

  assert.throws(
    () => journey.assertAuthenticatedComputerDesktopDriver(
      selfMinted.driver,
      scenario,
      diagnosticEnv(),
      { secret: COMPUTER_BRIDGE_SECRET },
    ),
    /computer_desktop_external_authority_required/,
  );

  const genuine = externallySignedComputerBridge(scenario);
  const trusted = journey.assertAuthenticatedComputerDesktopDriver(
    genuine.driver,
    scenario,
    diagnosticEnv(),
    { authority: genuine.authority },
  );
  assert.equal(trusted.provenance.authorityKeyId, genuine.authority.keyId);
});

test("caller-generated Ed25519 cannot authenticate the runner itself or a borrowed parent PID", (t) => {
  const scenario = scenarioAt(privateRoot(t));

  for (const peerProcessId of [process.pid, process.ppid]) {
    const forged = callerMintedComputerBridge(scenario, peerProcessId);
    assert.throws(
      () => journey.assertAuthenticatedComputerDesktopDriver(
        forged.driver,
        scenario,
        diagnosticEnv(),
        { authority: forged.authority },
      ),
      /computer_desktop_external_authority_required|computer_desktop_parent_transport_unavailable/,
      `caller-owned key must not become trusted via PID ${peerProcessId}`,
    );
  }
});

test("caller-provided processProbe cannot fake a live Computer signer or production transport", (t) => {
  const scenario = scenarioAt(privateRoot(t));
  const forged = callerMintedComputerBridge(scenario, 2147483000);

  assert.throws(
    () => journey.assertAuthenticatedComputerDesktopDriver(
      forged.driver,
      scenario,
      diagnosticEnv(),
      {
        authority: forged.authority,
        processProbe() {},
      },
    ),
    /computer_desktop_external_authority_required|computer_desktop_process_probe_override_forbidden/,
  );
});

async function inheritedParentComputerProbe(t, { unitTestParent = false } = {}) {
  const scenario = scenarioAt(privateRoot(t));
  const signer = crypto.generateKeyPairSync("ed25519");
  const signerPublic = signer.publicKey.export({ type: "spki", format: "der" });
  const keyId = hash(signerPublic);
  const sessionRef = "sky_separate_parent_owned_ipc_session";
  const issuedAtMs = Date.now();
  const provenance = {
    contractVersion: 1,
    caseId: scenario.caseId,
    provider: "@oai/sky",
    controlPlane: "computer_plugin_node_repl",
    interface: "sky.get_app_state/sky-primitives",
    skyMethods: ["click", "press_key"],
    ownerId: scenario.owner.ownerId,
    telegramUserId: scenario.owner.telegramUserId,
    telegramChatId: scenario.owner.telegramChatId,
    appBundleId: scenario.telegram.bundleId,
    sessionRef,
    authorityKeyId: keyId,
    peerProcessId: process.pid,
    issuedAtMs,
    expiresAtMs: issuedAtMs + 60000,
  };
  const sign = (payload) => `ed25519:${crypto.sign(
    null,
    Buffer.from(canonicalJson(payload)),
    signer.privateKey,
  ).toString("base64url")}`;
  const childSource = [
    "'use strict';",
    "const crypto=require('node:crypto');",
    "const journey=require(process.argv[1]);",
    "process.once('message',async(input)=>{",
    "try{",
    "const transport={kind:'inherited_parent_ipc',controlPlane:'computer_plugin_node_repl',parentProcessId:process.ppid,channel:process.channel,...(input.unitTestHarness?{unitTestHarness:input.unitTestHarness}:{})};",
    "const authority={publicKey:crypto.createPublicKey({key:Buffer.from(input.publicKey,'base64url'),format:'der',type:'spki'}),keyId:input.keyId,peerProcessId:process.ppid,sessionRef:input.sessionRef,transport};",
    "await journey.authenticateParentComputerAuthority(authority,{timeoutMs:2000});",
    "const driver={provenance:input.provenance,get_app_state(request){return new Promise((resolve)=>{const handler=(message)=>{if(message.type==='fixture.observation'&&message.challenge===request.challenge){process.off('message',handler);resolve(message.observation)}};process.on('message',handler);process.send({type:'fixture.observe',request})})},async do_action(){throw new Error('unused')}};",
    "const adapter=journey.assertTrustedComputerAdapter(driver,input.scenario,authority,{caseId:'TGDOC-010',environment:{VIVENTIUM_QA_ALLOW_TGDOC_010_COMPUTER_BRIDGE:'1'}});",
    "const observation=await journey.observeTrustedComputer(adapter,{kind:'state'});",
    "process.send({type:'fixture.result',accepted:observation.source==='@oai/sky.get_app_state',ownerId:observation.ownerId,peerProcessId:observation.peerProcessId})",
    "}catch(error){process.send({type:'fixture.result',accepted:false,blocker:error.message})}",
    "});",
  ].join("");
  const child = spawn(process.execPath, ["-e", childSource, RUNNER], {
    cwd: ROOT,
    env: { PATH: process.env.PATH || "" },
    stdio: ["ignore", "pipe", "pipe", "ipc"],
  });
  t.after(() => {
    if (child.connected) child.disconnect();
    if (child.exitCode === null) child.kill();
  });
  const outcome = await new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error("parent IPC signer test timed out")), 4000);
    child.on("error", (error) => { clearTimeout(timeout); reject(error); });
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
          expiresAtMs: now + 30000,
        };
        child.send({ ...response, proof: sign(response) });
        return;
      }
      if (message.type === "fixture.observe") {
        const request = message.request;
        const unsigned = {
          source: "@oai/sky.get_app_state",
          app: request.app,
          ownerId: scenario.owner.ownerId,
          telegramUserId: scenario.owner.telegramUserId,
          telegramChatId: scenario.owner.telegramChatId,
          sessionRef,
          peerProcessId: process.pid,
          challenge: request.challenge,
          observedAtMs: Date.now(),
          activeSelection: exactActiveSelection(scenario),
        };
        child.send({
          type: "fixture.observation",
          challenge: request.challenge,
          observation: { ...unsigned, proof: sign(unsigned) },
        });
        return;
      }
      if (message.type === "fixture.result") {
        clearTimeout(timeout);
        resolve(message);
      }
    });
    child.send({
      publicKey: signerPublic.toString("base64url"),
      keyId,
      sessionRef,
      scenario,
      provenance: { ...provenance, proof: sign(provenance) },
      ...(unitTestParent ? {
        unitTestHarness: {
          kind: "node_test_only_parent_transport",
          parentProcessId: process.pid,
          grandparentProcessId: process.ppid,
          testFile: __filename,
        },
      } : {}),
    });
  });

  return { outcome, scenario };
}

test("an arbitrary same-user parent Node process cannot self-declare the Computer control plane", async (t) => {
  const { outcome } = await inheritedParentComputerProbe(t);
  assert.equal(outcome.accepted, false, "a user-spawned parent must not become Computer authority");
  assert.match(outcome.blocker, /computer_desktop_control_plane_untrusted/);
});

test("Computer origin derives signed application trust without a vendor, install path, or fixed process genealogy", () => {
  const source = fs.readFileSync(RUNNER, "utf8");

  for (const machineSpecificTrustRoot of [
    "/Applications/ChatGPT.app",
    "com.openai.codex",
    "2DC432GLL2",
    "expectedNode",
    "expectedRepl",
    "expectedHost",
    "expectedApplication",
  ]) {
    assert.equal(source.includes(machineSpecificTrustRoot), false, machineSpecificTrustRoot);
  }

  assert.equal(source.includes("/usr/sbin/spctl"), true);
  assert.equal(source.includes("--verify"), true);
  assert.equal(source.includes("inherited_parent_ipc"), true);
});

test("a separately signed parent IPC challenge works only inside the exact guarded node:test fixture", async (t) => {
  const { outcome, scenario } = await inheritedParentComputerProbe(t, { unitTestParent: true });

  assert.equal(outcome.accepted, true, outcome.blocker);
  assert.equal(outcome.ownerId, scenario.owner.ownerId);
  assert.equal(outcome.peerProcessId, process.pid);
});

test("every action rechecks the signed ACTIVE account and chat; sidebar labels or account swaps never authorize a send", async (t) => {
  const scenario = scenarioAt(privateRoot(t));
  const personal = exactActiveSelection(scenario);
  personal.account.telegramUserId = "900001";
  personal.account.label = "Personal account";
  const exploit = externallySignedComputerBridge(scenario, { selections: [personal] });
  const trusted = journey.assertAuthenticatedComputerDesktopDriver(
    exploit.driver,
    scenario,
    diagnosticEnv(),
    { authority: exploit.authority },
  );

  await assert.rejects(
    () => journey.performComputerDesktopAction(trusted, scenario, {
      action: "telegram.send_grouped_attachments",
      caption: "synthetic owner-isolated attachment",
      attachments: [],
    }),
    /computer_desktop_active_account_mismatch/,
  );
  assert.deepEqual(exploit.calls.map((call) => call.kind), ["get_app_state"]);

  const changedChat = exactActiveSelection(scenario);
  changedChat.chat.telegramChatId = "900002";
  const chatExploit = externallySignedComputerBridge(scenario, { selections: [changedChat] });
  const chatTrusted = journey.assertAuthenticatedComputerDesktopDriver(
    chatExploit.driver,
    scenario,
    diagnosticEnv(),
    { authority: chatExploit.authority },
  );
  await assert.rejects(
    () => journey.performComputerDesktopAction(chatTrusted, scenario, {
      action: "telegram.send_grouped_attachments",
      caption: "synthetic",
      attachments: [],
    }),
    /computer_desktop_active_chat_mismatch/,
  );
  assert.equal(chatExploit.calls.some((call) => call.kind === "do_action"), false);
});

test("unsigned, stale, replayed, substituted-key, and peer-mismatched Computer observations fail closed", async (t) => {
  const scenario = scenarioAt(privateRoot(t));
  const { authority, driver } = externallySignedComputerBridge(scenario);
  const trusted = journey.assertAuthenticatedComputerDesktopDriver(driver, scenario, diagnosticEnv(), { authority });
  const original = driver.get_app_state;

  for (const [reason, mutate] of [
    ["computer_desktop_observation_authentication_failed", (value) => { value.proof = `ed25519:${Buffer.alloc(64).toString("base64url")}`; }],
    ["computer_desktop_observation_peer_mismatch", (value) => { value.peerProcessId = process.pid; }],
    ["computer_desktop_observation_provenance_invalid", (value) => { value.challenge = "replayed"; }],
    ["computer_desktop_active_selection_unavailable", (value) => { delete value.activeSelection; }],
  ]) {
    driver.get_app_state = async (request) => {
      const observation = await original.call(driver, request);
      mutate(observation);
      return observation;
    };
    await assert.rejects(() => journey.readComputerDesktopState(trusted, scenario), new RegExp(reason), reason);
  }
});

test("Computer desktop observations and typed actions require fresh signed exact-owner Sky provenance", async (t) => {
  const scenario = scenarioAt(privateRoot(t));
  const { driver, calls } = sourceOnlyComputerBridge(scenario);
  const trusted = journey.assertAuthenticatedComputerDesktopDriver(driver, scenario, diagnosticEnv(), {
    authority: externalComputerAuthority(),
  });

  const observed = await journey.readComputerDesktopState(trusted, scenario);
  assert.equal(observed.source, "@oai/sky.get_app_state");
  assert.equal(observed.app, scenario.telegram.bundleId);

  const action = await journey.performComputerDesktopAction(trusted, scenario, {
    action: "telegram.send_grouped_attachments",
    caption: "synthetic source-only caption",
    attachments: [{ filename: "synthetic.txt", sha256: hash("synthetic") }],
  });
  assert.equal(action.status, "sent");
  assert.deepEqual(calls.map((item) => item.kind), ["get_app_state", "get_app_state", "do_action"]);
  assert.equal(calls[2].request.app, scenario.telegram.bundleId);
  assert.equal(calls[2].request.skyMethod, "press_key");

  const original = driver.get_app_state;
  driver.get_app_state = async (request) => ({
    ...(await original.call(driver, request)),
    telegramChatId: "999999",
  });
  await assert.rejects(
    () => journey.readComputerDesktopState(trusted, scenario),
    /computer_desktop_observation_owner_mismatch/,
  );
});

test("Computer screenshot evidence accepts only signed Sky PNG bytes and remains private", async (t) => {
  const root = privateRoot(t);
  const scenario = scenarioAt(root);
  const png = Buffer.concat([
    Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
    Buffer.alloc(160, 1),
  ]);
  const { driver } = sourceOnlyComputerBridge(scenario, { screenshotBytes: png });
  const trusted = journey.assertAuthenticatedComputerDesktopDriver(driver, scenario, diagnosticEnv(), {
    authority: externalComputerAuthority(),
  });
  const observed = await journey.readComputerDesktopState(trusted, scenario);
  const captured = journey.writeObservedComputerCapture(root, "signed-telegram.png", observed);

  assert.equal(captured.sha256, hash(png));
  assert.equal(fs.statSync(captured.path).mode & 0o777, 0o600);
  assert.throws(
    () => journey.writeObservedComputerCapture(root, "invalid.png", { ...observed, screenshotBytes: Buffer.from("fake") }),
    /computer_desktop_capture_unavailable/,
  );
});

test("installed CLI blocks before any runtime or desktop access when no authenticated Computer bridge was injected", async (t) => {
  const root = privateRoot(t);
  const scenario = scenarioAt(root);
  const scenarioPath = privateFile(path.join(root, "scenario.json"), Buffer.from(JSON.stringify(scenario)));

  const result = await journey.main([
    "--local-qa",
    "--allow-telegram-mutation",
    "--allow-runtime-restart",
    "--scenario", scenarioPath,
    "--evidence-root", root,
  ], diagnosticEnv());

  assert.equal(result.status, "BLOCKED");
  assert.equal(result.blocker, "computer_desktop_driver_unavailable");
  assert.equal(result.releaseReady, false);
  assert.equal(result.receiptEligible, false);
});

test("production installed execution rejects the explicit node:test Computer fixture authority", async (t) => {
  const root = privateRoot(t);
  const scenario = scenarioAt(root);
  const scenarioPath = privateFile(path.join(root, "scenario.json"), Buffer.from(JSON.stringify(scenario)));
  const fixture = externallySignedComputerBridge(scenario);

  const result = await journey.main([
    "--local-qa",
    "--allow-telegram-mutation",
    "--allow-runtime-restart",
    "--scenario", scenarioPath,
    "--evidence-root", root,
  ], diagnosticEnv(), {
    desktopDriver: fixture.driver,
    computerAuthority: fixture.authority,
  });

  assert.equal(result.status, "BLOCKED");
  assert.equal(result.blocker, "computer_desktop_test_authority_forbidden");
  assert.equal(fixture.calls.length, 0);
});

test("installed runner contains no forbidden desktop automation fallback", () => {
  const source = fs.readFileSync(RUNNER, "utf8");

  for (const forbidden of [
    "osascript",
    "AppleScript",
    "System Events",
    "clipboard",
    "keystroke",
    "screencapture",
    "CGEvent",
  ]) {
    assert.equal(source.includes(forbidden), false, forbidden);
  }
  assert.equal(source.includes("@oai/sky"), true);
  assert.equal(source.includes("get_app_state"), true);
  assert.equal(source.includes("do_action"), true);
  assert.equal(source.includes("@oai/sky.do_action"), false);
});

test("ephemeral browser authentication requires independent JWT consent, exact nonpersonal QA owner, and trusted signing secrets", (t) => {
  const scenario = scenarioAt(privateRoot(t));
  const args = journey.ephemeralBrowserSessionArgs(scenario, { timeoutMs: 180000 });

  assert.equal(args.qaEmail, scenario.owner.email);
  assert.equal(args.clientBase, scenario.runtime.clientUrl);
  assert.equal(args.apiBase, scenario.runtime.apiUrl);
  assert.doesNotThrow(() => journey.assertEphemeralSessionSafety(args, diagnosticEnv()));

  for (const [reason, changes] of [
    ["ephemeral_browser_session_requires_explicit_opt_in", { VIVENTIUM_QA_ALLOW_LOCAL_JWT: "" }],
    ["configured_synthetic_qa_account_mismatch", { VIVENTIUM_QA_EMAIL: "other@example.com" }],
    ["ephemeral_browser_session_signing_secrets_required", { JWT_SECRET: "" }],
    ["ephemeral_browser_session_signing_secrets_required", { JWT_REFRESH_SECRET: "" }],
  ]) {
    assert.throws(
      () => journey.assertEphemeralSessionSafety(args, diagnosticEnv(changes)),
      new RegExp(reason),
      reason,
    );
  }
});

test("reviewed short-lived synthetic-owner session stores only a token hash and always deletes the exact session", async (t) => {
  const scenario = scenarioAt(privateRoot(t));
  const args = journey.ephemeralBrowserSessionArgs(scenario, { timeoutMs: 180000 });
  const calls = [];
  const sessionId = { toString: () => "source-test-session" };
  const user = {
    _id: scenario.owner.ownerId,
    email: scenario.owner.email,
    role: "USER",
    username: "synthetic-qa",
    provider: "local",
  };
  const database = {
    collection(name) {
      assert.equal(name, "sessions");
      return {
        async insertOne(value) {
          calls.push({ kind: "insert", value });
          return { acknowledged: true };
        },
        async deleteOne(value) {
          calls.push({ kind: "delete", value });
          return { deletedCount: 1 };
        },
      };
    },
  };

  const session = await journey.createEphemeralBrowserSession({
    db: database,
    user,
    args,
    env: diagnosticEnv(),
    nowMs: 1750000000000,
    createSessionId: () => sessionId,
    signToken(payload, secret, options) {
      assert.ok(options.expiresIn >= 120 && options.expiresIn <= 900);
      return `${payload.sessionId ? "refresh" : "access"}-source-test-token`;
    },
  });

  assert.equal(calls[0].kind, "insert");
  assert.equal(calls[0].value.user, scenario.owner.ownerId);
  assert.equal(calls[0].value.refreshTokenHash, hash("refresh-source-test-token"));
  assert.equal(JSON.stringify(calls[0].value).includes("refresh-source-test-token"), false);
  assert.equal(session.cookies.length, 4);

  await session.cleanup();
  await session.cleanup();
  assert.deepEqual(calls[1], {
    kind: "delete",
    value: { _id: sessionId, user: scenario.owner.ownerId },
  });
  assert.equal(calls.length, 2);
});

test("ephemeral browser sessions accept only the exact installed QA identity and installed signing secrets", (t) => {
  const scenario = scenarioAt(privateRoot(t));
  const installed = {
    VIVENTIUM_QA_EMAIL: scenario.owner.email,
    JWT_SECRET: "trusted-installed-access-secret",
    JWT_REFRESH_SECRET: "trusted-installed-refresh-secret",
  };

  const trusted = journey.assertTrustedEphemeralSessionConfiguration(scenario, installed, {
    VIVENTIUM_QA_ALLOW_LOCAL_JWT: "1",
  });
  assert.equal(trusted.JWT_SECRET, installed.JWT_SECRET);
  assert.equal(trusted.JWT_REFRESH_SECRET, installed.JWT_REFRESH_SECRET);

  for (const [reason, installedChanges, requestedChanges] of [
    ["configured_synthetic_qa_account_mismatch", { VIVENTIUM_QA_EMAIL: "other@example.com" }, {}],
    ["ephemeral_browser_session_signing_secrets_required", { JWT_SECRET: "" }, {}],
    ["ephemeral_browser_session_signing_secrets_required", { JWT_REFRESH_SECRET: "" }, {}],
    ["untrusted_runtime_signing_secret_refused", {}, { JWT_SECRET: "caller-supplied-secret" }],
    ["untrusted_runtime_signing_secret_refused", {}, { JWT_REFRESH_SECRET: "caller-supplied-secret" }],
  ]) {
    assert.throws(
      () => journey.assertTrustedEphemeralSessionConfiguration(
        scenario,
        { ...installed, ...installedChanges },
        requestedChanges,
      ),
      new RegExp(reason),
      reason,
    );
  }
});

test("restart scenarios refuse to discard or overwrite uncommitted nested checkout changes", (t) => {
  const scenario = scenarioAt(privateRoot(t));

  assert.doesNotThrow(() => journey.validateScenario(scenario, diagnosticEnv()));

  scenario.restart.arguments = scenario.restart.arguments.filter(
    (argument) => argument !== "--allow-dirty-local-testing",
  );
  assert.throws(() => journey.validateScenario(scenario, diagnosticEnv()), /runtime_restart_dirty_checkout_protection_required/);
});

test("private evidence rejects repository roots, readable directories, and any symlink without changing them", (t) => {
  const root = privateRoot(t);
  const openRoot = path.join(root, "group-readable");
  fs.mkdirSync(openRoot, { mode: 0o755 });
  fs.chmodSync(openRoot, 0o755);

  assert.throws(() => journey.assertPrivateEvidenceRoot(ROOT), /evidence_root_inside_repository/);
  assert.throws(() => journey.assertPrivateEvidenceRoot(openRoot), /evidence_root_not_private/);
  assert.equal(fs.statSync(openRoot).mode & 0o777, 0o755);

  const linkedRoot = path.join(root, "linked");
  fs.symlinkSync(openRoot, linkedRoot, "dir");
  assert.throws(() => journey.assertPrivateEvidenceRoot(linkedRoot), /evidence_root_symlink_forbidden/);
  assert.equal(journey.assertPrivateEvidenceRoot(root), fs.realpathSync(root));
});

test("private scenarios are exact-owner, single-link 0600 files under the private evidence root", (t) => {
  const root = privateRoot(t);
  const scenarioPath = privateFile(path.join(root, "scenario.json"), Buffer.from(JSON.stringify(scenarioAt(root))));

  assert.equal(journey.readPrivateScenario(scenarioPath, root).caseId, "TGDOC-010");
  fs.chmodSync(scenarioPath, 0o644);
  assert.throws(() => journey.readPrivateScenario(scenarioPath, root), /scenario_not_private/);
  fs.chmodSync(scenarioPath, 0o600);
  const linked = path.join(root, "linked-scenario.json");
  fs.symlinkSync(scenarioPath, linked);
  assert.throws(() => journey.readPrivateScenario(linked, root), /scenario_symlink_forbidden/);
});

test("private evidence is written once as 0600 and refuses overwrite, traversal, and links", (t) => {
  const root = privateRoot(t);
  const written = journey.writePrivateEvidence(root, "observed.json", { observed: true });

  assert.equal(fs.statSync(written.path).mode & 0o777, 0o600);
  assert.match(written.sha256, /^[a-f0-9]{64}$/);
  assert.throws(() => journey.writePrivateEvidence(root, "observed.json", { observed: false }), /private_evidence_already_exists/);
  assert.throws(() => journey.writePrivateEvidence(root, "../outside.json", {}), /private_evidence_path_invalid/);

  const linked = path.join(root, "linked.json");
  fs.symlinkSync(written.path, linked);
  assert.throws(() => journey.writePrivateEvidence(root, "linked.json", {}), /private_evidence_symlink_forbidden/);
});

test("scenario requires all owner-scoped attachment families, same-name media, one caption, URL, providers, tools, and restart", (t) => {
  const root = privateRoot(t);
  const scenario = scenarioAt(root);

  assert.doesNotThrow(() => journey.validateScenario(scenario, diagnosticEnv()));

  const variants = [
    ["missing_attachment_family", (value) => { value.inputs = value.inputs.filter((input) => input.family !== "video"); }],
    ["same_name_attachment_proof_required", (value) => { value.inputs[2].filename = "different-name.png"; }],
    ["captioned_media_group_required", (value) => { value.inputs[1].caption = ""; }],
    ["synthetic_url_required", (value) => { value.mission.sourceUrl = "https://outside.invalid/private"; }],
    ["required_provider_unavailable", (value) => { value.runtime.fallbackProviderId = ""; }],
    ["required_tool_unavailable", (value) => { value.runtime.requiredToolIds = []; }],
    ["runtime_restart_unsupported", (value) => { value.restart.supported = false; }],
    ["owner_scoped_synthetic_attachment_required", (value) => { value.inputs[0].ownerId = "other-owner"; }],
  ];
  for (const [reason, mutate] of variants) {
    const altered = structuredClone(scenario);
    mutate(altered);
    assert.throws(() => journey.validateScenario(altered, diagnosticEnv()), new RegExp(reason), reason);
  }
});

test("personal owner account and Telegram identity are rejected before any Telegram mutation", (t) => {
  const scenario = scenarioAt(privateRoot(t));

  assert.doesNotThrow(() => journey.assertOwnerSafeTelegramIdentity(scenario, diagnosticEnv(), observedTelegramIdentity(scenario)));

  for (const [reason, mutate] of [
    ["personal_owner_account_refused", (value) => { value.owner.email = "owner@example.com"; }],
    ["personal_telegram_account_refused", (value) => { value.owner.telegramUserId = "900001"; }],
    ["personal_telegram_chat_refused", (value) => { value.owner.telegramChatId = "900002"; }],
    ["owner_safe_telegram_identity_unavailable", (value, observed) => { observed.accountVisible = false; }],
    ["owner_safe_telegram_identity_unavailable", (value, observed) => { observed.ownerId = "other-owner"; }],
    ["owner_safe_telegram_identity_unavailable", (value, observed) => { observed.accountLabel = "Personal account"; }],
    ["computer_desktop_active_selection_unavailable", (value, observed) => {
      delete observed.activeSelectionVerified;
    }],
  ]) {
    const altered = structuredClone(scenario);
    const observed = observedTelegramIdentity(altered);
    mutate(altered, observed);
    assert.throws(
      () => journey.assertOwnerSafeTelegramIdentity(altered, diagnosticEnv(), observed),
      new RegExp(reason),
      reason,
    );
  }

  const inactiveSidebarLabel = observedTelegramIdentity(scenario);
  inactiveSidebarLabel.visibleText = [scenario.telegram.accountLabel, "Personal account"];
  assert.doesNotThrow(
    () => journey.assertOwnerSafeTelegramIdentity(scenario, diagnosticEnv(), inactiveSidebarLabel),
  );
});

test("synthetic fixture bytes are measured from owner-private files and never inferred from declarations", (t) => {
  const root = privateRoot(t);
  const scenario = scenarioAt(root);
  const measured = journey.inspectSyntheticInputs(scenario, { evidenceRoot: root });

  assert.equal(measured.length, scenario.inputs.length);
  assert.equal(measured[1].filename, measured[2].filename);
  assert.notEqual(measured[1].sha256, measured[2].sha256);

  privateFile(scenario.inputs[0].sourcePath, Buffer.from("different bytes"));
  assert.throws(() => journey.inspectSyntheticInputs(scenario, { evidenceRoot: root }), /synthetic_attachment_bytes_mismatch/);
});

test("installed attachment metadata comes only from observed upload records, persisted caption, and visible Telegram identity", (t) => {
  const scenario = scenarioAt(privateRoot(t));
  const expected = scenario.inputs[1];
  const caption = `${expected.caption} [group:${expected.groupId}] ${expected.visibleIdentity}`;
  const observed = {
    file: { type: "image/png", metadata: {} },
    reference: {
      file_id: "file-alpha-1",
      media_group_index: 1,
      media_group_id: expected.groupId,
      caption: expected.caption,
    },
    userMessage: { text: caption },
    visibleText: [caption],
    expected,
    position: 1,
  };

  assert.deepEqual(journey.deriveObservedUploadMetadata(observed), {
    family: "image",
    visibleIdentity: expected.visibleIdentity,
    position: 1,
    groupId: expected.groupId,
    caption: expected.caption,
  });

  for (const [reason, mutate] of [
    ["telegram_upload_order_evidence_unavailable", (value) => { delete value.reference.media_group_index; }],
    ["telegram_upload_visible_identity_unavailable", (value) => { value.visibleText = []; }],
    ["telegram_upload_family_evidence_unavailable", (value) => { value.file.type = ""; }],
    ["telegram_media_group_evidence_unavailable", (value) => {
      delete value.reference.media_group_id;
      value.userMessage.text = expected.visibleIdentity;
      value.visibleText = [expected.visibleIdentity];
    }],
    ["telegram_group_caption_evidence_unavailable", (value) => {
      value.reference.caption = "";
      value.userMessage.text = `[group:${expected.groupId}] ${expected.visibleIdentity}`;
      value.visibleText = [value.userMessage.text];
    }],
  ]) {
    const variant = structuredClone(observed);
    mutate(variant);
    assert.throws(() => journey.deriveObservedUploadMetadata(variant), new RegExp(reason), reason);
  }
});

test("ordered upload identities, owner scope, exact bytes, and worker materialization must all match", (t) => {
  const root = privateRoot(t);
  const scenario = scenarioAt(root);
  const expected = journey.inspectSyntheticInputs(scenario, { evidenceRoot: root });
  const uploads = observedInputs(scenario);
  const worker = uploads.map((input) => ({ ...input, bytes: Buffer.from(input.bytes) }));

  const result = journey.assessOrderedInputParity({ scenario, expected, uploads, workerInputs: worker });
  assert.equal(result.inputCount, expected.length);
  assert.match(result.inputManifestSha256, /^[a-f0-9]{64}$/);

  for (const [reason, mutate] of [
    ["telegram_upload_order_mismatch", (items) => { [items[0], items[1]] = [items[1], items[0]]; }],
    ["telegram_upload_owner_mismatch", (items) => { items[0].ownerId = "other-owner"; }],
    ["telegram_upload_identity_missing", (items) => { items[0].fileId = ""; }],
    ["telegram_upload_bytes_mismatch", (items) => { items[0].bytes = Buffer.from("wrong bytes"); }],
  ]) {
    const altered = uploads.map((input) => ({ ...input, bytes: Buffer.from(input.bytes) }));
    mutate(altered);
    assert.throws(
      () => journey.assessOrderedInputParity({ scenario, expected, uploads: altered, workerInputs: worker }),
      new RegExp(reason),
      reason,
    );
  }

  const wrongWorker = worker.map((input) => ({ ...input, bytes: Buffer.from(input.bytes) }));
  wrongWorker[1].fileId = wrongWorker[2].fileId;
  assert.throws(
    () => journey.assessOrderedInputParity({ scenario, expected, uploads, workerInputs: wrongWorker }),
    /worker_upload_identity_mismatch/,
  );
});

test("exactly one intended mission requires a real owner-bound active runtime overlap", (t) => {
  const scenario = scenarioAt(privateRoot(t));
  const mission = observedMission(scenario);

  assert.equal(journey.assessOwnerScopedMission([mission], scenario).overlapMs, 2200);
  assert.throws(() => journey.assessOwnerScopedMission([mission, mission], scenario), /exactly_one_owner_scoped_mission_required/);

  const outsideWindow = structuredClone(mission);
  outsideWindow.workerWindow.startedAtMs = 4500;
  outsideWindow.runtimeInvokedAtMs = 4500;
  assert.throws(() => journey.assessOwnerScopedMission([outsideWindow], scenario), /worker_runtime_overlap_unavailable/);

  const otherOwner = structuredClone(mission);
  otherOwner.ownerId = "other-owner";
  assert.throws(() => journey.assessOwnerScopedMission([otherOwner], scenario), /worker_owner_scope_mismatch/);
});

test("broker and tool evidence must be actual exact-scope authorized completed receipts", (t) => {
  const scenario = scenarioAt(privateRoot(t));
  const mission = observedMission(scenario);
  const inputDigest = hash("input manifest");
  const receipts = observedBrokerReceipts(scenario, inputDigest);

  assert.equal(journey.assessAuthorizedBrokerReceipts(receipts, scenario, mission, inputDigest).receiptCount, 2);

  for (const [reason, mutate] of [
    ["required_tool_receipt_unavailable", (items) => items.pop()],
    ["broker_receipt_not_authorized", (items) => { items[0].authorized = false; }],
    ["broker_receipt_owner_scope_mismatch", (items) => { items[0].ownerId = "other-owner"; }],
    ["broker_receipt_input_manifest_mismatch", (items) => { items[0].inputManifestSha256 = hash("wrong"); }],
  ]) {
    const altered = structuredClone(receipts);
    mutate(altered);
    assert.throws(
      () => journey.assessAuthorizedBrokerReceipts(altered, scenario, mission, inputDigest),
      new RegExp(reason),
      reason,
    );
  }
});

test("provider fallback and supported restart must preserve the same mission and exact input manifest", (t) => {
  const scenario = scenarioAt(privateRoot(t));
  const mission = observedMission(scenario);
  const inputDigest = hash("input manifest");
  const fallback = observedFallback(scenario, inputDigest);
  const restart = observedRestart(scenario, inputDigest);

  assert.equal(journey.assessProviderFallback(fallback, scenario, mission, inputDigest).attemptCount, 2);
  assert.equal(journey.assessRestartPreservation(restart, scenario, mission, inputDigest).recovered, true);

  const wrongProvider = structuredClone(fallback);
  wrongProvider.attempts[1].providerId = "unapproved-provider";
  assert.throws(() => journey.assessProviderFallback(wrongProvider, scenario, mission, inputDigest), /fallback_provider_unavailable/);

  const changedInput = structuredClone(restart);
  changedInput.afterInputManifestSha256 = hash("changed inputs");
  assert.throws(() => journey.assessRestartPreservation(changedInput, scenario, mission, inputDigest), /restart_input_manifest_mismatch/);

  const unsupported = structuredClone(restart);
  unsupported.supported = false;
  assert.throws(() => journey.assessRestartPreservation(unsupported, scenario, mission, inputDigest), /runtime_restart_unsupported/);
});

test("restart is rejected after fallback completion, released lease, terminal callback, or existing artifact", (t) => {
  const scenario = scenarioAt(privateRoot(t));
  const mission = observedMission(scenario);
  mission.lease.releasedAtMs = null;
  const manifest = hash("synthetic exact inputs");
  const fallback = observedFallback(scenario, manifest);
  fallback.attempts[1].state = "running";
  fallback.attempts[1].runtimeInvokedAtMs = 2000;
  fallback.attempts[1].lease = {
    leaseId: "lease-synthetic-fallback",
    ownerId: scenario.owner.ownerId,
    workerRef: mission.workerRef,
    runRef: mission.runRef,
    acquiredAtMs: 1600,
    confirmedAtMs: 1700,
    releasedAtMs: null,
    pid: 44001,
    processStartIdentity: "synthetic-worker-start",
  };
  fallback.terminalCallbackObserved = false;
  fallback.artifactObserved = false;

  assert.equal(
    journey.assertActiveFallbackAttempt(fallback, scenario, mission, manifest).attemptId,
    "attempt-fallback",
  );

  for (const [reason, mutate] of [
    ["fallback_attempt_not_active", (value) => { value.attempts[1].state = "completed"; }],
    ["fallback_attempt_lease_unavailable", (value) => { value.attempts[1].lease.releasedAtMs = 2200; }],
    ["fallback_attempt_lease_unavailable", (value) => { value.attempts[1].lease.ownerId = "another-owner"; }],
    ["restart_after_terminal_callback_refused", (value) => { value.terminalCallbackObserved = true; }],
    ["restart_after_artifact_creation_refused", (value) => { value.artifactObserved = true; }],
  ]) {
    const changed = structuredClone(fallback);
    mutate(changed);
    assert.throws(
      () => journey.assertActiveFallbackAttempt(changed, scenario, mission, manifest),
      new RegExp(reason),
      reason,
    );
  }
});

test("a preexisting Telegram download never proves delivery, even when its bytes and filename match", (t) => {
  const root = privateRoot(t);
  const scenario = scenarioAt(root);
  const directory = path.join(root, "downloads");
  fs.mkdirSync(directory, { mode: 0o700 });
  const target = privateFile(path.join(directory, scenario.mission.outputIdentity), Buffer.from("synthetic artifact"));
  fs.utimesSync(target, new Date(Date.now() - 10000), new Date(Date.now() - 10000));
  const baseline = journey.captureTelegramDownloadBaseline(directory, scenario.mission.outputIdentity);
  const openedAtMs = Date.now();

  assert.throws(
    () => journey.readFreshTelegramDownload({
      directory,
      filename: scenario.mission.outputIdentity,
      baseline,
      actionObservedAtMs: openedAtMs,
      ownerId: scenario.owner.ownerId,
      expectedOwnerId: scenario.owner.ownerId,
      expectedSha256: hash("synthetic artifact"),
    }),
    /telegram_artifact_download_stale/,
  );

  fs.writeFileSync(target, "synthetic artifact", { mode: 0o600 });
  fs.utimesSync(target, new Date(openedAtMs + 1000), new Date(openedAtMs + 1000));
  const current = journey.readFreshTelegramDownload({
    directory,
    filename: scenario.mission.outputIdentity,
    baseline,
    actionObservedAtMs: openedAtMs,
    ownerId: scenario.owner.ownerId,
    expectedOwnerId: scenario.owner.ownerId,
    expectedSha256: hash("synthetic artifact"),
  });
  assert.equal(current.bytes.toString(), "synthetic artifact");
  assert.throws(
    () => journey.readFreshTelegramDownload({
      directory,
      filename: scenario.mission.outputIdentity,
      baseline,
      actionObservedAtMs: openedAtMs,
      ownerId: "another-owner",
      expectedOwnerId: scenario.owner.ownerId,
      expectedSha256: hash("synthetic artifact"),
    }),
    /telegram_artifact_download_owner_mismatch/,
  );
});

test("provider fallback input digests must be independently recorded for each exact installed attempt", () => {
  const digest = hash("actual installed input manifest");
  const attempts = [
    { attemptId: "attempt-primary", ordinal: 1 },
    { attemptId: "attempt-fallback", ordinal: 2 },
  ];
  const traces = [
    { attemptNumber: 1, inputManifestSha256: digest },
    { attemptNumber: 2, inputManifestSha256: digest },
  ];

  assert.deepEqual(journey.observedFallbackAttemptManifests(attempts, traces, digest), [digest, digest]);
  assert.throws(
    () => journey.observedFallbackAttemptManifests(attempts, traces.slice(0, 1), digest),
    /fallback_input_manifest_evidence_unavailable/,
  );
  assert.throws(
    () => journey.observedFallbackAttemptManifests(
      attempts,
      [traces[0], { ...traces[1], inputManifestSha256: hash("changed") }],
      digest,
    ),
    /fallback_input_manifest_mismatch/,
  );
});

test("restart support requires real coordinated installed-service acknowledgements", () => {
  const status = {
    caseId: "PWK-UC-017",
    restartState: "ready",
    sessionRef: "qa_synthetic_fixture",
    requiredServices: ["glasshive-runtime", "librechat-core", "telegram-bot"],
    acknowledgedServices: ["glasshive-runtime", "librechat-core", "telegram-bot"],
    missingServices: [],
    serviceAckDigest: `sha256:${hash("real acknowledged service processes")}`,
  };

  assert.deepEqual(
    journey.assessCoordinatedRestartStatus(status, { coordinatedQaCaseId: "PWK-UC-017" }).services,
    ["core", "glasshive", "telegram"],
  );

  for (const mutate of [
    (value) => { value.caseId = "TR-026"; },
    (value) => { value.restartState = "waiting"; },
    (value) => { value.acknowledgedServices.pop(); },
    (value) => { value.serviceAckDigest = ""; },
  ]) {
    const altered = structuredClone(status);
    mutate(altered);
    assert.throws(
      () => journey.assessCoordinatedRestartStatus(altered, { coordinatedQaCaseId: "PWK-UC-017" }),
      /runtime_restart_unsupported/,
    );
  }
});

test("artifact identity must exist in the exact owner-scoped installed immutable artifact trace", () => {
  const bytes = Buffer.from("actual owner-scoped artifact bytes");
  const digest = hash(bytes);
  const rows = [{
    payload: JSON.stringify({
      artifactRefs: {
        available: true,
        overflowCount: 0,
        refs: [{
          artifactRef: `artifact_sha256:${digest}`,
          fingerprint: `sha256:${digest}`,
          kind: "html",
          state: "available",
          sizeBytes: bytes.length,
        }],
      },
    }),
  }];

  assert.equal(journey.observedArtifactIdentity(rows, bytes), `artifact_sha256:${digest}`);
  assert.throws(() => journey.observedArtifactIdentity([], bytes), /delivered_artifact_identity_unavailable/);
  assert.throws(
    () => journey.observedArtifactIdentity(rows, Buffer.from("different bytes")),
    /delivered_artifact_identity_unavailable/,
  );
});

test("delivered artifact must open on both surfaces with identical real bytes and one delivery", (t) => {
  const scenario = scenarioAt(privateRoot(t));
  const mission = observedMission(scenario);
  const delivery = observedArtifact(scenario);

  assert.equal(journey.assessDeliveredArtifact(delivery, scenario, mission).deliveryCount, 1);

  const wrongBytes = {
    ...delivery,
    activeWork: { ...delivery.activeWork, bytes: Buffer.from("wrong artifact") },
  };
  assert.throws(() => journey.assessDeliveredArtifact(wrongBytes, scenario, mission), /active_work_artifact_bytes_mismatch/);

  const duplicate = {
    ...delivery,
    telegram: { ...delivery.telegram, deliveryReceipts: [...delivery.telegram.deliveryReceipts, ...delivery.telegram.deliveryReceipts] },
  };
  assert.throws(() => journey.assessDeliveredArtifact(duplicate, scenario, mission), /exactly_once_telegram_delivery_required/);
});

test("synthetic cleanup refuses foreign records and never deletes a preexisting conversation", async (t) => {
  const scenario = scenarioAt(privateRoot(t));
  const owner = { _id: scenario.owner.ownerId, email: scenario.owner.email, role: "USER" };
  const startedAtMs = 1000;
  const inventory = {
    ownerId: scenario.owner.ownerId,
    conversationId: "synthetic-existing-conversation",
    startedAtMs,
    createdConversation: false,
    telegramMessageIds: [4101, 4102],
    messages: [{
      _id: "message-one",
      user: scenario.owner.ownerId,
      conversationId: "synthetic-existing-conversation",
      messageId: "synthetic-message-one",
      createdAt: new Date(2000),
    }],
    ingress: [{
      _id: "ingress-one",
      telegramUserId: scenario.owner.telegramUserId,
      telegramChatId: scenario.owner.telegramChatId,
      conversationId: "synthetic-existing-conversation",
      createdAt: new Date(2000),
    }],
    conversations: [],
  };
  const deletes = [];
  const database = {
    collection(name) {
      return {
        async findOne(query) {
          if (name === "users") {
            assert.equal(query.email, scenario.owner.email);
            return owner;
          }
          const records = name === "messages" ? inventory.messages : inventory.ingress;
          return records.find((record) => record._id === query._id) || null;
        },
        async deleteOne(query) {
          deletes.push({ name, query });
          return { deletedCount: 1 };
        },
      };
    },
  };
  let remoteCalls = 0;
  const cleaned = await journey.cleanupOwnerScopedSyntheticTelegramRecords({
    database,
    scenario,
    environment: diagnosticEnv(),
    owner,
    inventory,
    async removeRemote(messageIds) {
      remoteCalls += 1;
      assert.deepEqual(messageIds, [4101, 4102]);
      return { deleted: true, messageIds };
    },
  });

  assert.equal(cleaned.cleaned, true);
  assert.equal(remoteCalls, 1);
  assert.equal(deletes.some((entry) => entry.name === "conversations"), false);
  assert.deepEqual(deletes[0].query, {
    _id: "message-one",
    user: scenario.owner.ownerId,
    conversationId: "synthetic-existing-conversation",
  });

  const unsafe = structuredClone(inventory);
  unsafe.messages[0].user = "different-owner";
  await assert.rejects(
    () => journey.cleanupOwnerScopedSyntheticTelegramRecords({
      database,
      scenario,
      environment: diagnosticEnv(),
      owner,
      inventory: unsafe,
      async removeRemote() { throw new Error("foreign data must not be deleted"); },
    }),
    /synthetic_telegram_cleanup_owner_mismatch/,
  );
  assert.equal(remoteCalls, 1);
});

test("owner-scoped runtime trace must have an exact immutable hash chain and genuine completion stages", () => {
  const rows = syntheticTraceRows("qa-owner-alpha", "origin-alpha", "work-alpha");

  assert.equal(journey.verifyIndependentTraceRows(rows, "qa-owner-alpha", "origin-alpha", "work-alpha"), true);

  const forged = structuredClone(rows);
  forged[2].facts.workRefHash = `sha256:${hash("another mission")}`;
  assert.equal(journey.verifyIndependentTraceRows(forged, "qa-owner-alpha", "origin-alpha", "work-alpha"), false);

  const missingDelivery = rows.slice(0, -1);
  assert.equal(journey.verifyIndependentTraceRows(missingDelivery, "qa-owner-alpha", "origin-alpha", "work-alpha"), false);
});

test("fixture driver executes a genuine grouped Telegram-to-Worker trigger sequence without receipt fabrication", async (t) => {
  const root = privateRoot(t);
  const scenario = scenarioAt(root);
  const fixtures = journey.inspectSyntheticInputs(scenario, { evidenceRoot: root });
  const uploads = observedInputs(scenario);
  const workerInputs = uploads.map((input) => ({ ...input, bytes: Buffer.from(input.bytes) }));
  const inputDigest = journey.assessOrderedInputParity({ scenario, expected: fixtures, uploads, workerInputs }).inputManifestSha256;
  const mission = observedMission(scenario);
  const calls = [];
  const driver = {
    async preflightInstalledCandidate() { calls.push("candidate"); return { verified: true, candidateDigest: hash("candidate"), artifactDigest: hash("artifact") }; },
    async probeTelegramIdentity() { calls.push("identity"); return observedTelegramIdentity(scenario); },
    async probeRequiredCapabilities() { calls.push("capabilities"); return { providerIds: [scenario.runtime.primaryProviderId, scenario.runtime.fallbackProviderId], toolIds: [...scenario.runtime.requiredToolIds], restartSupported: true }; },
    async sendGroupedTelegramAttachments() { calls.push("telegram-send"); return { visible: true, groupCount: 1, urlVisible: true }; },
    async observeTelegramIngress() { calls.push("ingress"); return { ownerId: scenario.owner.ownerId, logicalTurnCount: 1, uploads }; },
    async observeOwnerScopedMission() { calls.push("mission"); return [mission]; },
    async observeWorkerMaterialization() { calls.push("worker-files"); return workerInputs; },
    async steerMission() { calls.push("steer"); return { ownerId: scenario.owner.ownerId, workRef: mission.workRef, runRef: mission.runRef, accepted: true }; },
    async observeAuthorizedBrokerReceipts() { calls.push("broker"); return observedBrokerReceipts(scenario, inputDigest); },
    async observeProviderFallback(_mission, _parity, stage) {
      calls.push(stage === "before_restart" ? "fallback-active" : "fallback-completed");
      return stage === "before_restart"
        ? observedActiveFallback(scenario, inputDigest, mission)
        : observedFallback(scenario, inputDigest);
    },
    async restartMissionRuntime() { calls.push("restart"); return observedRestart(scenario, inputDigest); },
    async openDeliveredArtifact() { calls.push("artifact"); return observedArtifact(scenario); },
    async collectIndependentTrace() { calls.push("trace"); return { ownerId: scenario.owner.ownerId, workRef: mission.workRef, runRef: mission.runRef, verified: true }; },
    async cleanupSyntheticTelegramConversation() {
      calls.push("synthetic-cleanup");
      return { cleaned: true, ownerId: scenario.owner.ownerId, conversationId: "synthetic-conversation" };
    },
    async close() { calls.push("close"); },
  };

  const result = await journey.executeInstalledJourney({ driver, scenario, fixtures, environment: diagnosticEnv() });

  assert.equal(result.status, "PRE_GATE_COMPLETE");
  assert.equal(result.releaseReady, false);
  assert.equal(result.receiptEligible, false);
  assert.equal(result.releaseLabel, "PRE-GATE / NOT READY");
  assert.deepEqual(calls, [
    "candidate", "identity", "capabilities", "telegram-send", "ingress", "mission",
    "worker-files", "steer", "broker", "fallback-active", "restart", "fallback-completed",
    "artifact", "trace", "synthetic-cleanup", "close",
  ]);
  assert.equal(Object.hasOwn(result, "receipt"), false);
});

test("missing provider, tool, owner identity, or restart support blocks before Telegram is touched", async (t) => {
  const root = privateRoot(t);
  const scenario = scenarioAt(root);
  const fixtures = journey.inspectSyntheticInputs(scenario, { evidenceRoot: root });

  for (const [reason, identity, capabilities] of [
    ["computer_desktop_active_selection_unavailable", null, null],
    ["required_provider_unavailable", observedTelegramIdentity(scenario), { providerIds: [scenario.runtime.primaryProviderId], toolIds: scenario.runtime.requiredToolIds, restartSupported: true }],
    ["required_tool_unavailable", observedTelegramIdentity(scenario), { providerIds: [scenario.runtime.primaryProviderId, scenario.runtime.fallbackProviderId], toolIds: [], restartSupported: true }],
    ["runtime_restart_unsupported", observedTelegramIdentity(scenario), { providerIds: [scenario.runtime.primaryProviderId, scenario.runtime.fallbackProviderId], toolIds: scenario.runtime.requiredToolIds, restartSupported: false }],
  ]) {
    let sent = false;
    let closed = false;
    const result = await journey.executeInstalledJourney({
      driver: {
        async preflightInstalledCandidate() { return { verified: true, candidateDigest: hash("candidate"), artifactDigest: hash("artifact") }; },
        async probeTelegramIdentity() { return identity; },
        async probeRequiredCapabilities() { return capabilities; },
        async sendGroupedTelegramAttachments() { sent = true; },
        async close() { closed = true; },
      },
      scenario,
      fixtures,
      environment: diagnosticEnv(),
    });

    assert.equal(result.status, "BLOCKED", reason);
    assert.equal(result.blocker, reason);
    assert.equal(sent, false, reason);
    assert.equal(closed, true, reason);
    assert.equal(result.receiptEligible, false, reason);
  }
});

test("public diagnostic summary contains only hashes, counts, status, and safe blocker labels", (t) => {
  const scenario = scenarioAt(privateRoot(t));
  const summary = journey.buildPublicSummary({
    result: {
      caseId: "TGDOC-010",
      status: "BLOCKED",
      blocker: "required_tool_unavailable",
      evidence: {
        ownerId: scenario.owner.ownerId,
        email: scenario.owner.email,
        telegramChatId: scenario.owner.telegramChatId,
        workRef: "work-alpha",
        sourcePath: scenario.inputs[0].sourcePath,
        desktopBridgeSecret: COMPUTER_BRIDGE_SECRET,
        jwtAccessSecret: diagnosticEnv().JWT_SECRET,
        jwtRefreshSecret: diagnosticEnv().JWT_REFRESH_SECRET,
        accessToken: "synthetic-private-access-token",
        refreshToken: "synthetic-private-refresh-token",
      },
    },
    qaRunId: "synthetic-run-alpha",
  });
  const publicText = JSON.stringify(summary);

  assert.equal(summary.releaseReady, false);
  assert.equal(summary.receiptEligible, false);
  assert.equal(summary.releaseLabel, "PRE-GATE / NOT READY");
  for (const forbidden of [
    scenario.owner.ownerId,
    scenario.owner.email,
    scenario.owner.telegramChatId,
    "work-alpha",
    scenario.inputs[0].sourcePath,
    COMPUTER_BRIDGE_SECRET,
    diagnosticEnv().JWT_SECRET,
    diagnosticEnv().JWT_REFRESH_SECRET,
    "synthetic-private-access-token",
    "synthetic-private-refresh-token",
  ]) {
    assert.equal(publicText.includes(forbidden), false, forbidden);
  }
});
