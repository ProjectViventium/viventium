#!/usr/bin/env node
"use strict";

/*
 * TR-026 installed-user trigger. All desktop operations are delegated to an
 * explicitly injected, externally signed Computer plugin driver backed by
 * @oai/sky. The existing Python verifier independently owns semantic acceptance.
 */

const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { fork, spawnSync } = require("node:child_process");

const CASE_ID = "TR-026";
const CONTRACT_VERSION = 1;
const REPO_ROOT = path.resolve(__dirname, "../../..");
const LIBRECHAT_ROOT = path.join(REPO_ROOT, "viventium_v0_4", "LibreChat");
const VERIFIER = path.join(__dirname, "tr026_installed_journey_semantic_verifier.py");
const DELAY_MS = 280;
const REQUIRED_SERVICES = Object.freeze(["librechat-core", "telegram-bot"]);
const REQUIRED_VERIFIER_GATES = Object.freeze([
  "installed-owner-source-component-build-runtime",
  "telegram-user-12346-before-stale-send-12347",
  "authoritative-signed-280ms-race-audit",
  "pre-commit-revision-and-post-commit-correction",
  "source-order-admission-parity",
  "post-commit-normal-follow-up",
  "direct-telegram-desktop-visible-and-reopened",
  "original-user-order-and-one-persisted-final-answer",
  "signed-restarted-core-and-telegram-services",
]);
const computerBoundary = require(path.join(
  REPO_ROOT,
  "qa",
  "telegram-document-attachments",
  "scripts",
  "run_tgdoc_010_installed_journey.cjs",
));
const {
  SKY_ACTION_METHODS,
  authenticateParentComputerAuthority,
  assertTrustedComputerAdapter,
  observeTrustedComputer,
  assertActiveSelectedTelegramContext,
  verifyExternalComputerProof,
  cleanupOwnerScopedSyntheticTelegramRecords,
} = computerBoundary;
const SAFE_COMPONENT = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/;
const SHA256 = /^[a-f0-9]{64}$/;
const SESSION_REF = /^qa_[a-f0-9]{24}$/;
const MAX_PRIVATE_FILE_BYTES = 32 * 1024 * 1024;
const PNG_SIGNATURE = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);

function blockedError(code) {
  const error = new Error(String(code || "installed_journey_prerequisite_unavailable"));
  error.name = "InstalledTelegramRapidSegmentJourneyBlockedError";
  error.blocked = true;
  return error;
}

function sha256(value) {
  return crypto.createHash("sha256").update(value).digest("hex");
}

function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

function parseArgs(argv = process.argv.slice(2)) {
  const args = {
    dryRun: false,
    localQa: false,
    allowTelegramMutation: false,
    allowRuntimeRestart: false,
    evidenceRoot: "",
    scenarioPath: "",
    timeoutMs: 120000,
    qaRunId: `${CASE_ID}-${crypto.randomUUID()}`,
  };
  const seen = new Set();
  const flags = new Map([
    ["--dry-run", "dryRun"],
    ["--local-qa", "localQa"],
    ["--allow-telegram-mutation", "allowTelegramMutation"],
    ["--allow-runtime-restart", "allowRuntimeRestart"],
  ]);
  const options = new Map([
    ["--evidence-root", "evidenceRoot"],
    ["--scenario", "scenarioPath"],
    ["--timeout-ms", "timeoutMs"],
  ]);

  for (let index = 0; index < argv.length; index += 1) {
    const argument = String(argv[index]);
    const equals = argument.indexOf("=");
    const name = equals < 0 ? argument : argument.slice(0, equals);
    if (seen.has(name)) throw blockedError("duplicate_argument");
    seen.add(name);
    if (flags.has(name)) {
      if (equals >= 0) throw blockedError("invalid_flag_value");
      args[flags.get(name)] = true;
      continue;
    }
    if (!options.has(name)) throw blockedError("unknown_argument");
    const value = equals < 0 ? argv[++index] : argument.slice(equals + 1);
    if (!String(value || "").trim()) throw blockedError("missing_argument_value");
    args[options.get(name)] = value;
  }

  if (
    args.dryRun &&
    (args.localQa ||
      args.allowTelegramMutation ||
      args.allowRuntimeRestart ||
      args.evidenceRoot ||
      args.scenarioPath)
  ) {
    throw blockedError("dry_run_rejects_live_arguments");
  }
  args.timeoutMs = Number(args.timeoutMs);
  if (!Number.isSafeInteger(args.timeoutMs) || args.timeoutMs < 1000 || args.timeoutMs > 600000) {
    throw blockedError("journey_timeout_invalid");
  }
  return args;
}

function dryRunPlan(args) {
  if (args?.dryRun !== true) throw blockedError("dry_run_required");
  return {
    caseId: CASE_ID,
    status: "DRY_RUN",
    sideEffects: false,
    accessesDatabase: false,
    accessesDesktop: false,
    sendsTelegramMessages: false,
    restartsRuntime: false,
    releaseReady: false,
    receiptEligible: false,
  };
}

function assertExecutionConsents(args, environment, restart = { supported: true }) {
  if (args?.localQa !== true) throw blockedError("local_qa_opt_in_required");
  if (environment?.VIVENTIUM_QA_ALLOW_TR026_INSTALLED_JOURNEY !== "1") {
    throw blockedError("installed_journey_opt_in_required");
  }
  if (environment.CI || environment.NODE_ENV === "production") {
    throw blockedError("local_installed_qa_only");
  }
  if (
    args.allowTelegramMutation !== true ||
    environment.VIVENTIUM_QA_ALLOW_TR026_TELEGRAM_MUTATION !== "1"
  ) {
    throw blockedError("telegram_mutation_consent_required");
  }
  if (restart?.supported !== true) throw blockedError("runtime_restart_unsupported");
  if (
    args.allowRuntimeRestart !== true ||
    environment.VIVENTIUM_QA_ALLOW_TR026_RUNTIME_RESTART !== "1"
  ) {
    throw blockedError("runtime_restart_consent_required");
  }
}

function canonicalTemporaryAlias(location) {
  const absolute = path.resolve(String(location || ""));
  const temporary = path.resolve(os.tmpdir());
  const relative = path.relative(temporary, absolute);
  if (relative && relative !== ".." && !relative.startsWith(`..${path.sep}`)) {
    return path.join(fs.realpathSync(temporary), relative);
  }
  return absolute;
}

function pathInside(candidate, root) {
  const relative = path.relative(root, candidate);
  return relative !== ".." && !relative.startsWith(`..${path.sep}`) && !path.isAbsolute(relative);
}

function assertNoSymlinkComponents(location, blocker) {
  const absolute = canonicalTemporaryAlias(location);
  const filesystemRoot = path.parse(absolute).root;
  let current = filesystemRoot;
  for (const component of absolute.slice(filesystemRoot.length).split(path.sep).filter(Boolean)) {
    current = path.join(current, component);
    let metadata;
    try {
      metadata = fs.lstatSync(current);
    } catch (error) {
      if (error?.code === "ENOENT") throw blockedError("private_path_unavailable");
      throw error;
    }
    if (metadata.isSymbolicLink()) throw blockedError(blocker);
  }
  return absolute;
}

function assertPrivateEvidenceRoot(location) {
  if (!String(location || "").trim()) throw blockedError("evidence_root_required");
  const requested = canonicalTemporaryAlias(location);
  if (pathInside(requested, fs.realpathSync(REPO_ROOT))) {
    throw blockedError("evidence_root_inside_repository");
  }
  if (requested === path.parse(requested).root) throw blockedError("evidence_root_invalid");
  let exact;
  try {
    exact = assertNoSymlinkComponents(requested, "evidence_root_symlink_forbidden");
  } catch (error) {
    if (error?.message === "private_path_unavailable") throw blockedError("evidence_root_unavailable");
    throw error;
  }
  const metadata = fs.statSync(exact);
  if (!metadata.isDirectory() || metadata.uid !== process.getuid() || (metadata.mode & 0o777) !== 0o700) {
    throw blockedError("evidence_root_not_private");
  }
  return fs.realpathSync(exact);
}

function readPrivateFile(location, { root, label, maxBytes = MAX_PRIVATE_FILE_BYTES }) {
  const supplied = canonicalTemporaryAlias(location);
  const privateRoot = fs.realpathSync(canonicalTemporaryAlias(root));
  if (!pathInside(supplied, privateRoot) || supplied === privateRoot) {
    throw blockedError(`${label}_outside_private_evidence`);
  }
  let exact;
  try {
    exact = assertNoSymlinkComponents(supplied, `${label}_symlink_forbidden`);
  } catch (error) {
    if (error?.message === "private_path_unavailable") throw blockedError(`${label}_unavailable`);
    throw error;
  }

  const descriptor = fs.openSync(exact, fs.constants.O_RDONLY | (fs.constants.O_NOFOLLOW || 0));
  try {
    const before = fs.fstatSync(descriptor);
    if (
      !before.isFile() ||
      before.uid !== process.getuid() ||
      (before.mode & 0o777) !== 0o600 ||
      before.nlink !== 1
    ) {
      throw blockedError(`${label}_not_private`);
    }
    if (before.size < 1 || before.size > maxBytes) throw blockedError(`${label}_size_invalid`);
    const bytes = fs.readFileSync(descriptor);
    const after = fs.fstatSync(descriptor);
    if (
      bytes.length !== before.size ||
      before.dev !== after.dev ||
      before.ino !== after.ino ||
      before.size !== after.size ||
      before.mtimeMs !== after.mtimeMs
    ) {
      throw blockedError(`${label}_changed_during_read`);
    }
    return { bytes, path: exact, metadata: before };
  } finally {
    fs.closeSync(descriptor);
  }
}

function readPrivateScenario(location, root) {
  if (!String(location || "").trim()) throw blockedError("scenario_unavailable");
  const { bytes } = readPrivateFile(location, { root, label: "scenario", maxBytes: 1024 * 1024 });
  try {
    const scenario = JSON.parse(bytes.toString("utf8"));
    if (!scenario || typeof scenario !== "object" || Array.isArray(scenario)) {
      throw blockedError("scenario_invalid");
    }
    return scenario;
  } catch (error) {
    if (error?.blocked) throw error;
    throw blockedError("scenario_invalid");
  }
}

function writePrivateEvidence(root, name, payload) {
  if (!SAFE_COMPONENT.test(String(name || ""))) throw blockedError("private_evidence_path_invalid");
  const directory = assertPrivateEvidenceRoot(root);
  const target = path.join(directory, name);
  try {
    if (fs.lstatSync(target).isSymbolicLink()) throw blockedError("private_evidence_symlink_forbidden");
    throw blockedError("private_evidence_already_exists");
  } catch (error) {
    if (error?.blocked) throw error;
    if (error?.code !== "ENOENT") throw blockedError("private_evidence_write_unavailable");
  }

  const bytes = Buffer.isBuffer(payload)
    ? payload
    : Buffer.from(`${JSON.stringify(payload, null, 2)}\n`, "utf8");
  let descriptor;
  try {
    descriptor = fs.openSync(
      target,
      fs.constants.O_WRONLY |
        fs.constants.O_CREAT |
        fs.constants.O_EXCL |
        (fs.constants.O_NOFOLLOW || 0),
      0o600,
    );
    fs.writeFileSync(descriptor, bytes);
    fs.fchmodSync(descriptor, 0o600);
    fs.fsyncSync(descriptor);
  } catch (error) {
    if (error?.code === "EEXIST") throw blockedError("private_evidence_already_exists");
    throw error;
  } finally {
    if (descriptor !== undefined) fs.closeSync(descriptor);
  }
  return { path: target, sha256: sha256(bytes), sizeBytes: bytes.length };
}

function positiveSafeInteger(value) {
  return Number.isSafeInteger(value) && value > 0;
}

function exactNumericIdentity(value, { signed = false } = {}) {
  const text = String(value || "");
  if (!(signed ? /^-?\d{4,20}$/ : /^\d{4,20}$/).test(text)) return false;
  const number = Number(text);
  return Number.isSafeInteger(number) && number !== 0;
}

function assertSyntheticOwner(scenario, environment) {
  const owner = scenario?.owner || {};
  const personalEmail = String(environment?.VIVENTIUM_QA_OWNER_EMAIL || "").trim().toLowerCase();
  const personalUserId = String(environment?.VIVENTIUM_QA_OWNER_TELEGRAM_USER_ID || "").trim();
  const personalChatId = String(environment?.VIVENTIUM_QA_OWNER_TELEGRAM_CHAT_ID || "").trim();
  if (!personalEmail || !personalUserId || !personalChatId) {
    throw blockedError("personal_owner_identity_guard_required");
  }
  const email = String(owner.email || "").trim().toLowerCase();
  if (email === personalEmail) throw blockedError("personal_owner_account_refused");
  if (String(owner.telegramUserId || "") === personalUserId) {
    throw blockedError("personal_telegram_account_refused");
  }
  if (String(owner.telegramChatId || "") === personalChatId) {
    throw blockedError("personal_telegram_chat_refused");
  }
  const [local, domain, ...additional] = email.split("@");
  if (
    owner.synthetic !== true ||
    !/^[a-f0-9]{24}$/.test(String(owner.ownerId || "")) ||
    !local ||
    additional.length ||
    !new Set(["example.com", "viventium.local", "localhost"]).has(domain) ||
    !exactNumericIdentity(owner.telegramUserId) ||
    !exactNumericIdentity(owner.telegramChatId, { signed: true }) ||
    !Number.isSafeInteger(owner.telegramThreadId) ||
    owner.telegramThreadId < 0
  ) {
    throw blockedError("synthetic_owner_identity_required");
  }
}

function validateScenario(scenario, environment = process.env) {
  if (
    scenario?.contractVersion !== CONTRACT_VERSION ||
    scenario.caseId !== CASE_ID ||
    scenario.classification !== "synthetic_public_safe"
  ) {
    throw blockedError("scenario_invalid");
  }
  assertSyntheticOwner(scenario, environment);
  if (!/^[A-Za-z0-9_-]{8,160}$/.test(String(scenario.conversation?.conversationId || ""))) {
    throw blockedError("owner_scoped_conversation_required");
  }
  if (
    scenario.telegram?.bundleId !== "ru.keepcoder.Telegram" ||
    !String(scenario.telegram.accountLabel || "").trim() ||
    !String(scenario.telegram.chatLabel || "").trim()
  ) {
    throw blockedError("owner_safe_telegram_identity_unavailable");
  }

  const first = scenario.source?.first;
  const revision = scenario.source?.revision;
  const postCommit = scenario.source?.postCommit;
  if (
    !positiveSafeInteger(first?.messageId) ||
    !positiveSafeInteger(revision?.messageId) ||
    revision.messageId !== first.messageId + 1
  ) {
    throw blockedError("adjacent_source_message_ids_required");
  }
  if (
    !positiveSafeInteger(first.updateId) ||
    !positiveSafeInteger(revision.updateId) ||
    revision.updateId !== first.updateId + 1
  ) {
    throw blockedError("exact_telegram_update_binding_required");
  }
  if (
    !positiveSafeInteger(postCommit?.messageId) ||
    postCommit.messageId <= revision.messageId ||
    !positiveSafeInteger(postCommit.updateId) ||
    postCommit.updateId <= revision.updateId
  ) {
    throw blockedError("post_commit_source_message_required");
  }
  for (const segment of [first, revision, postCommit]) {
    const text = String(segment.text || "");
    if (!text.includes(CASE_ID) || text.length > 2048) {
      throw blockedError("synthetic_telegram_segment_required");
    }
  }
  if (
    !/^[A-Za-z0-9_-]{3,80}$/.test(String(scenario.source.expectedReplyMarker || "")) ||
    !/^[A-Za-z0-9_-]{3,80}$/.test(String(scenario.source.staleReplyMarker || "")) ||
    scenario.source.expectedReplyMarker === scenario.source.staleReplyMarker
  ) {
    throw blockedError("synthetic_revision_markers_required");
  }

  const workRefs = scenario.workers?.workRefs;
  if (
    !Array.isArray(workRefs) ||
    workRefs.length !== 2 ||
    new Set(workRefs).size !== 2 ||
    workRefs.some((value) => !/^[A-Za-z0-9_:-]{4,160}$/.test(String(value || "")))
  ) {
    throw blockedError("two_owner_scoped_workers_required");
  }

  const runtime = scenario.runtime || {};
  if (
    !path.isAbsolute(String(runtime.installedRoot || "")) ||
    path.resolve(runtime.installedRoot) !== REPO_ROOT ||
    ["runtimeRoot", "artifactIdentityPath", "runtimeOwnerStatePath", "glassHiveDbPath"].some(
      (field) => !path.isAbsolute(String(runtime[field] || "")),
    )
  ) {
    throw blockedError("installed_runtime_identity_inputs_required");
  }

  if (
    scenario.evidence?.producer !== "independent_installed_runtime_observer" ||
    !SAFE_COMPONENT.test(String(scenario.evidence.manifestName || "")) ||
    !String(scenario.evidence.manifestName).endsWith(".json")
  ) {
    throw blockedError("independent_installed_evidence_producer_required");
  }

  const restart = scenario.restart || {};
  const restartArguments = Array.isArray(restart.arguments) ? restart.arguments : [];
  const allowedRestartArguments = new Set([
    "dev-runtime",
    "activate-current",
    "--validate",
    "--restart",
    "--allow-protected-folder",
    "--allow-dirty-local-testing",
  ]);
  if (
    restart.supported !== true ||
    path.resolve(String(restart.executable || "")) !== path.join(REPO_ROOT, "bin", "viventium") ||
    restartArguments[0] !== "dev-runtime" ||
    restartArguments[1] !== "activate-current" ||
    !restartArguments.includes("--validate") ||
    !restartArguments.includes("--restart") ||
    restartArguments.some((argument) => !allowedRestartArguments.has(argument)) ||
    new Set(restartArguments).size !== restartArguments.length ||
    canonicalJson(restart.services) !== canonicalJson(REQUIRED_SERVICES)
  ) {
    throw blockedError("runtime_restart_unsupported");
  }
  if (!restartArguments.includes("--allow-dirty-local-testing")) {
    throw blockedError("runtime_restart_dirty_checkout_protection_required");
  }
  return scenario;
}

function assertComputerDesktopDriver(driver, scenario, identity, options = {}) {
  if (!driver || typeof driver !== "object") {
    throw blockedError("computer_plugin_desktop_driver_unavailable");
  }
  const trusted = assertTrustedComputerAdapter(driver, scenario, options.authority, {
    caseId: CASE_ID,
    environment: options.environment || {},
    ...(Number.isSafeInteger(options.nowMs) ? { nowMs: options.nowMs } : {}),
    ...(typeof options.processProbe === "function" ? { processProbe: options.processProbe } : {}),
  });
  const provenance = trusted.provenance;
  if (
    !SHA256.test(String(provenance.ownerRefHash || "")) ||
    !SHA256.test(String(provenance.candidateDigest || "")) ||
    !SHA256.test(String(provenance.artifactDigest || "")) ||
    provenance.qaOwnerRefHash !== sha256(String(scenario?.owner?.ownerId || "")) ||
    provenance.conversationRefHash !== sha256(String(scenario?.conversation?.conversationId || "")) ||
    provenance.telegramChatRefHash !== sha256(String(scenario?.owner?.telegramChatId || "")) ||
    (identity &&
      (provenance.ownerRefHash !== identity.ownerRefHash ||
        provenance.candidateDigest !== identity.candidateDigest ||
        provenance.artifactDigest !== identity.artifactDigest))
  ) {
    throw blockedError("computer_plugin_desktop_driver_unavailable");
  }
  return trusted;
}

function assertComputerAction(observation, adapter, action) {
  try {
    if (
      !adapter?.binding || typeof adapter.verify !== "function" ||
      !observation || typeof observation !== "object"
    ) {
      throw blockedError("computer_plugin_desktop_observation_untrusted");
    }
    const isState = action === "get_app_state";
    const source = isState ? "@oai/sky.get_app_state" : `@oai/sky.${observation.skyMethod}`;
    if (
      observation.source !== source ||
      (!isState &&
        (!SKY_ACTION_METHODS.includes(observation.skyMethod) || observation.action !== action)) ||
      observation.app !== adapter.binding.appBundleId ||
      observation.ownerId !== adapter.binding.ownerId ||
      String(observation.telegramUserId || "") !== adapter.binding.telegramUserId ||
      String(observation.telegramChatId || "") !== adapter.binding.telegramChatId ||
      observation.sessionRef !== adapter.authority.sessionRef ||
      observation.peerProcessId !== adapter.authority.peerProcessId
    ) {
      throw blockedError("computer_plugin_desktop_observation_untrusted");
    }
    const { proof, screenshotBytes, ...unsigned } = observation;
    if (
      !adapter.verify(unsigned, proof) ||
      (screenshotBytes !== undefined &&
        (!Buffer.isBuffer(screenshotBytes) || sha256(screenshotBytes) !== observation.screenshotSha256))
    ) {
      throw blockedError("computer_plugin_desktop_observation_untrusted");
    }
    return observation;
  } catch {
    throw blockedError("computer_plugin_desktop_observation_untrusted");
  }
}

async function readOwnerBoundComputerState(adapter, scenario, request = {}) {
  const observed = await observeTrustedComputer(adapter, {
    kind: "state",
    ...(request.phase ? { phase: request.phase } : {}),
    ...(request.includeScreenshot === true ? { includeScreenshot: true } : {}),
  });
  assertActiveSelectedTelegramContext(observed, scenario);
  return assertComputerAction(observed, adapter, "get_app_state");
}

async function performOwnerBoundComputerAction(adapter, scenario, action) {
  const primitive = action?.skyMethod ||
    (action?.action === "telegram.reopen_conversation" ? "click" : "press_key");
  const { action: logicalAction, skyMethod: _ignored, ...payload } = action || {};
  const observed = await observeTrustedComputer(adapter, {
    kind: "action",
    skyMethod: primitive,
    logicalAction,
    payload,
  });
  assertActiveSelectedTelegramContext(observed, scenario);
  return assertComputerAction(observed, adapter, logicalAction);
}

function assertOwnerScopedTelegramChatBinding(scenario, mapping, record) {
  if (
    !mapping ||
    !record ||
    String(mapping.libreChatUserId || "") !== scenario?.owner?.ownerId ||
    String(mapping.telegramUserId || "") !== scenario.owner.telegramUserId ||
    String(record.telegramUserId || "") !== scenario.owner.telegramUserId ||
    String(record.telegramChatId || "") !== scenario.owner.telegramChatId ||
    record.conversationId !== scenario.conversation.conversationId
  ) {
    throw blockedError("owner_safe_telegram_identity_unavailable");
  }
  return record;
}

function assertIndependentObserverReady(
  ready,
  scenario,
  identity,
  desktopDriver,
  {
    currentProcessId = process.pid,
    expectedProcessId,
    expectedNonce,
    ...unsupported
  } = {},
) {
  try {
    const provenance = desktopDriver?.driver?.provenance || desktopDriver?.provenance;
    if (
      !ready ||
      ready.contractVersion !== CONTRACT_VERSION ||
      ready.caseId !== CASE_ID ||
      ready.producer !== scenario?.evidence?.producer ||
      ready.manifestName !== scenario.evidence.manifestName ||
      ready.ownerRefHash !== identity?.ownerRefHash ||
      ready.qaOwnerRefHash !== sha256(String(scenario.owner.ownerId || "")) ||
      ready.conversationRefHash !== sha256(String(scenario.conversation.conversationId || "")) ||
      ready.candidateDigest !== identity.candidateDigest ||
      ready.artifactDigest !== identity.artifactDigest ||
      ready.computerProvenanceSha256 !== sha256(canonicalJson(provenance)) ||
      !positiveSafeInteger(ready.processId) ||
      ready.processId === currentProcessId ||
      ready.processId !== expectedProcessId ||
      currentProcessId !== process.pid ||
      ready.parentProcessId !== currentProcessId ||
      !/^[a-f0-9]{64}$/.test(String(expectedNonce || "")) ||
      ready.observerNonce !== expectedNonce ||
      unsupported.processProbe !== undefined
    ) {
      throw blockedError("independent_installed_evidence_producer_unavailable");
    }
    const observerPublicKey = crypto.createPublicKey({
      key: Buffer.from(String(ready.observerPublicKey || ""), "base64url"),
      format: "der",
      type: "spki",
    });
    const { proof, ...unsigned } = ready;
    if (!verifyExternalComputerProof(observerPublicKey, unsigned, proof)) {
      throw blockedError("independent_installed_evidence_producer_unavailable");
    }
    process.kill(ready.processId, 0);
    return ready;
  } catch {
    throw blockedError("independent_installed_evidence_producer_unavailable");
  }
}

function signedObserverMessage(payload, privateKey) {
  return {
    ...payload,
    proof: `ed25519:${crypto.sign(
      null,
      Buffer.from(canonicalJson(payload), "utf8"),
      privateKey,
    ).toString("base64url")}`,
  };
}

function assertObserverComputerAncestry(parentProcessId, signerProcessId) {
  if (
    !positiveSafeInteger(parentProcessId) || parentProcessId !== process.ppid ||
    !positiveSafeInteger(signerProcessId) || signerProcessId === process.pid
  ) {
    throw blockedError("independent_installed_evidence_producer_unavailable");
  }
  const parent = spawnSync(
    "/bin/ps",
    ["-p", String(parentProcessId), "-o", "uid=", "-o", "ppid="],
    { encoding: "utf8", timeout: 3000, maxBuffer: 1024, env: { PATH: "/usr/bin:/bin" } },
  );
  const match = /^\s*(\d+)\s+(\d+)\s*$/.exec(String(parent.stdout || ""));
  if (
    parent.status !== 0 || !match ||
    Number(match[1]) !== process.getuid() || Number(match[2]) !== signerProcessId
  ) {
    throw blockedError("independent_installed_evidence_producer_unavailable");
  }
  process.kill(signerProcessId, 0);
}

function verifyIndependentComputerObservation(observer, observation) {
  try {
    if (!observation || typeof observation !== "object") {
      throw blockedError("independent_observer_computer_observation_untrusted");
    }
    const stateSource = observation.source === "@oai/sky.get_app_state";
    if (
      (!stateSource &&
        (!SKY_ACTION_METHODS.includes(observation.skyMethod) ||
          observation.source !== `@oai/sky.${observation.skyMethod}`)) ||
      observation.app !== observer.scenario.telegram.bundleId ||
      observation.ownerId !== observer.scenario.owner.ownerId ||
      String(observation.telegramUserId || "") !== observer.scenario.owner.telegramUserId ||
      String(observation.telegramChatId || "") !== observer.scenario.owner.telegramChatId ||
      observation.sessionRef !== observer.provenance.sessionRef ||
      observation.peerProcessId !== observer.provenance.peerProcessId ||
      !/^[a-f0-9]{64}$/.test(String(observation.challenge || "")) ||
      observer.consumedChallenges.has(observation.challenge) ||
      !Number.isSafeInteger(observation.observedAtMs) ||
      Math.abs(Date.now() - observation.observedAtMs) > 30000
    ) {
      throw blockedError("independent_observer_computer_observation_untrusted");
    }
    assertActiveSelectedTelegramContext(observation, observer.scenario);
    const { proof, screenshotBytes, ...unsigned } = observation;
    if (
      !verifyExternalComputerProof(observer.computerPublicKey, unsigned, proof) ||
      (screenshotBytes !== undefined &&
        (!Buffer.isBuffer(screenshotBytes) || sha256(screenshotBytes) !== observation.screenshotSha256))
    ) {
      throw blockedError("independent_observer_computer_observation_untrusted");
    }
    observer.consumedChallenges.add(observation.challenge);
    observer.observations.push(observation);
    if (observer.observations.length > 128) {
      throw blockedError("independent_observer_computer_observation_untrusted");
    }
    return observation;
  } catch {
    throw blockedError("independent_observer_computer_observation_untrusted");
  }
}

function loadIndependentRuntimeAuthority() {
  const script = [
    "import importlib.util,json,sys",
    "spec=importlib.util.spec_from_file_location('tr026_independent_runtime_authority',sys.argv[1])",
    "module=importlib.util.module_from_spec(spec)",
    "sys.modules[spec.name]=module",
    "spec.loader.exec_module(module)",
    "authority=module.probe_live_authority()",
    "json.dump({'candidateDigest':authority.candidate_digest,'artifactDigest':authority.artifact_digest,'ownerRefHash':authority.owner_ref_hash,'session':authority.session,'serviceStatus':authority.service_status,'acknowledgements':authority.acknowledgements,'audit':authority.live_audit,'installedIdentity':module._identity_projection(authority)},sys.stdout,separators=(',',':'))",
  ].join(";");
  const observed = spawnSync("python3", ["-c", script, VERIFIER], {
    encoding: "utf8",
    timeout: 15000,
    maxBuffer: 2 * 1024 * 1024,
    env: { PATH: process.env.PATH || "", PYTHONDONTWRITEBYTECODE: "1" },
  });
  if (observed.status !== 0) {
    throw blockedError("independent_installed_runtime_authority_unavailable");
  }
  try {
    return JSON.parse(String(observed.stdout || ""));
  } catch {
    throw blockedError("independent_installed_runtime_authority_unavailable");
  }
}

function ownerScopedObservedTrace(record, kind, observer, authority) {
  if (
    !record ||
    record.kind !== kind ||
    record.caseId !== CASE_ID ||
    record.ownerId !== observer.scenario.owner.ownerId ||
    record.conversationId !== observer.scenario.conversation.conversationId ||
    record.sessionRef !== authority.session.sessionRef ||
    record.candidateDigest !== authority.candidateDigest ||
    record.artifactDigest !== authority.artifactDigest ||
    !record.payload || typeof record.payload !== "object" || Array.isArray(record.payload) ||
    !Number.isFinite(Date.parse(String(record.observedAt || ""))) ||
    Date.parse(record.observedAt) < Date.parse(authority.session.startedAt)
  ) {
    throw blockedError("independent_installed_runtime_trace_unavailable");
  }
  return record.payload;
}

function signedRuntimeDocument(kind, payload, observer, authority, observedAt) {
  const unsigned = {
    artifactDigest: authority.artifactDigest,
    candidateDigest: authority.candidateDigest,
    caseId: CASE_ID,
    contractVersion: CONTRACT_VERSION,
    kind,
    observedAt,
    ownerRefHash: authority.ownerRefHash,
    payload,
    sessionRef: authority.session.sessionRef,
  };
  const token = Buffer.from(String(authority.session.caseToken || ""), "base64url");
  if (token.length !== 32) {
    throw blockedError("independent_installed_runtime_authority_unavailable");
  }
  const proof = `hmac-sha256:${crypto.createHmac("sha256", token)
    .update(canonicalJson(unsigned))
    .digest("hex")}`;
  const name = `observer-${observer.nonce.slice(0, 12)}-${kind}.json`;
  const written = writePrivateEvidence(observer.evidenceRoot, name, { ...unsigned, proof });
  return { kind, path: path.basename(written.path), sha256: written.sha256 };
}

async function produceIndependentObserverManifest(observer) {
  const authority = loadIndependentRuntimeAuthority();
  if (
    authority.candidateDigest !== observer.identity.candidateDigest ||
    authority.artifactDigest !== observer.identity.artifactDigest ||
    authority.ownerRefHash !== observer.identity.ownerRefHash ||
    !SESSION_REF.test(String(authority.session?.sessionRef || "")) ||
    !String(observer.mongoUri || "").trim()
  ) {
    throw blockedError("independent_installed_runtime_authority_unavailable");
  }
  const captures = new Map();
  for (const observation of observer.observations) {
    if (observation.source === "@oai/sky.get_app_state" && observation.phase) {
      if (captures.has(observation.phase)) {
        throw blockedError("independent_observer_computer_observation_untrusted");
      }
      captures.set(observation.phase, observation);
    }
  }
  const phaseKinds = [
    ["before_correction", "telegram_ui_before"],
    ["settled", "telegram_ui_settled"],
    ["reopened", "telegram_ui_reopened"],
  ];
  const reopened = observer.observations.find((observation) =>
    observation.action === "telegram.reopen_conversation" && observation.skyMethod === "click",
  );
  if (!reopened || phaseKinds.some(([phase]) => !captures.has(phase))) {
    throw blockedError("independent_observer_computer_capture_unavailable");
  }

  const { MongoClient } = require(path.join(LIBRECHAT_ROOT, "node_modules", "mongodb"));
  const mongo = new MongoClient(observer.mongoUri, { serverSelectionTimeoutMS: 5000 });
  let documents;
  try {
    await mongo.connect();
    const databaseName = new URL(observer.mongoUri).pathname.replace(/^\//, "") || "LibreChatViventium";
    const database = mongo.db(databaseName);
    const owner = await database.collection("users").findOne({ email: observer.scenario.owner.email });
    if (
      !owner?._id || String(owner._id) !== observer.scenario.owner.ownerId ||
      String(owner.role || "").toUpperCase() === "ADMIN"
    ) {
      throw blockedError("independent_observer_owner_binding_unavailable");
    }
    const traceRows = await database.collection("viventiumorchestrationtraceevents").find({
      caseId: CASE_ID,
      ownerId: observer.scenario.owner.ownerId,
      conversationId: observer.scenario.conversation.conversationId,
      sessionRef: authority.session.sessionRef,
      kind: { $in: ["telegram_source_trace", "core_revision_trace"] },
    }).limit(3).toArray();
    if (traceRows.length !== 2) {
      throw blockedError("independent_installed_runtime_trace_unavailable");
    }
    const sourceTrace = ownerScopedObservedTrace(
      traceRows.find((record) => record.kind === "telegram_source_trace"),
      "telegram_source_trace",
      observer,
      authority,
    );
    const coreTrace = ownerScopedObservedTrace(
      traceRows.find((record) => record.kind === "core_revision_trace"),
      "core_revision_trace",
      observer,
      authority,
    );
    const historyRow = await database.collection("viventiumorchestrationtraceevents").findOne({
      caseId: CASE_ID,
      ownerId: observer.scenario.owner.ownerId,
      conversationId: observer.scenario.conversation.conversationId,
      sessionRef: authority.session.sessionRef,
      kind: "mongo_history",
    });
    const history = ownerScopedObservedTrace(historyRow, "mongo_history", observer, authority);
    documents = { sourceTrace, coreTrace, history };
  } finally {
    await mongo.close().catch(() => {});
  }

  const evidence = [];
  const visibleCaptures = [];
  for (const [phase, kind] of phaseKinds) {
    const capture = captures.get(phase);
    if (
      capture.windowVisible !== true || !Array.isArray(capture.bubbles) ||
      !Buffer.isBuffer(capture.screenshotBytes) ||
      !capture.screenshotBytes.subarray(0, PNG_SIGNATURE.length).equals(PNG_SIGNATURE)
    ) {
      throw blockedError("independent_observer_computer_capture_unavailable");
    }
    const name = `observer-${observer.nonce.slice(0, 12)}-${kind}.png`;
    const file = writePrivateEvidence(observer.evidenceRoot, name, capture.screenshotBytes);
    evidence.push({ kind, path: path.basename(file.path), sha256: file.sha256 });
    visibleCaptures.push({
      phase,
      screenshotKind: kind,
      screenshotSha256: file.sha256,
      captureOrigin: "native_desktop_window_capture",
      observedAt: new Date(capture.observedAtMs).toISOString(),
      windowVisible: true,
      bubbles: capture.bubbles,
    });
  }
  const observedAt = new Date().toISOString();
  const payloads = {
    installed_identity: authority.installedIdentity,
    service_acknowledgements: {
      requiredServices: authority.serviceStatus.requiredServices,
      acknowledgedServices: authority.serviceStatus.acknowledgedServices,
      missingServices: authority.serviceStatus.missingServices,
      restartState: authority.serviceStatus.restartState,
      serviceAckDigest: authority.serviceStatus.serviceAckDigest,
      acknowledgements: authority.acknowledgements,
    },
    telegram_race_audit: { records: authority.audit },
    telegram_source_trace: documents.sourceTrace,
    core_revision_trace: documents.coreTrace,
    mongo_history: documents.history,
    telegram_ui_observation: {
      bundleId: observer.scenario.telegram.bundleId,
      captureMethod: "telegram_desktop_accessibility",
      surface: "telegram",
      captures: visibleCaptures,
      reopenAction: {
        method: "native_conversation_reopen",
        performedAt: new Date(reopened.observedAtMs).toISOString(),
      },
    },
  };
  for (const [kind, payload] of Object.entries(payloads)) {
    evidence.push(signedRuntimeDocument(kind, payload, observer, authority, observedAt));
  }
  const turnRefHash = documents.sourceTrace.turnRefHash;
  if (!SHA256.test(String(turnRefHash || ""))) {
    throw blockedError("independent_installed_runtime_trace_unavailable");
  }
  const manifest = {
    caseId: CASE_ID,
    contractVersion: CONTRACT_VERSION,
    environment: "installed_local_production",
    runAt: new Date().toISOString(),
    candidate: {
      candidateDigest: authority.candidateDigest,
      artifactDigest: authority.artifactDigest,
    },
    correlation: {
      ownerRefHash: authority.ownerRefHash,
      sessionRef: authority.session.sessionRef,
      turnRefHash,
    },
    evidence,
  };
  const written = writePrivateEvidence(observer.evidenceRoot, observer.scenario.evidence.manifestName, manifest);
  return {
    produced: true,
    manifestName: path.basename(written.path),
    manifestSha256: written.sha256,
  };
}

function startIndependentObserverChild() {
  let observer = null;
  process.on("disconnect", () => process.exit(0));
  process.on("message", async (message) => {
    try {
      if (message?.type === "bootstrap") {
        if (observer || !message.scenario || !message.identity) {
          throw blockedError("independent_installed_evidence_producer_unavailable");
        }
        assertObserverComputerAncestry(message.parentProcessId, message.provenance?.peerProcessId);
        const computerPublicKey = crypto.createPublicKey({
          key: Buffer.from(String(message.computerPublicKey || ""), "base64url"),
          format: "der",
          type: "spki",
        });
        const { proof, ...unsignedProvenance } = message.provenance;
        if (
          !verifyExternalComputerProof(computerPublicKey, unsignedProvenance, proof) ||
          message.provenance.authorityKeyId !== sha256(computerPublicKey.export({ type: "spki", format: "der" })) ||
          message.provenance.ownerId !== message.scenario.owner.ownerId ||
          message.provenance.caseId !== CASE_ID ||
          message.provenance.ownerRefHash !== message.identity.ownerRefHash ||
          message.provenance.candidateDigest !== message.identity.candidateDigest ||
          message.provenance.artifactDigest !== message.identity.artifactDigest ||
          !/^[a-f0-9]{64}$/.test(String(message.nonce || ""))
        ) {
          throw blockedError("independent_installed_evidence_producer_unavailable");
        }
        const keys = crypto.generateKeyPairSync("ed25519");
        observer = {
          scenario: message.scenario,
          identity: message.identity,
          evidenceRoot: assertPrivateEvidenceRoot(message.evidenceRoot),
          mongoUri: String(message.mongoUri || ""),
          provenance: message.provenance,
          computerPublicKey,
          privateKey: keys.privateKey,
          nonce: message.nonce,
          consumedChallenges: new Set(),
          observations: [],
        };
        const ready = {
          contractVersion: CONTRACT_VERSION,
          caseId: CASE_ID,
          producer: message.scenario.evidence.producer,
          manifestName: message.scenario.evidence.manifestName,
          ownerRefHash: message.identity.ownerRefHash,
          qaOwnerRefHash: sha256(message.scenario.owner.ownerId),
          conversationRefHash: sha256(message.scenario.conversation.conversationId),
          candidateDigest: message.identity.candidateDigest,
          artifactDigest: message.identity.artifactDigest,
          computerProvenanceSha256: sha256(canonicalJson(message.provenance)),
          processId: process.pid,
          parentProcessId: process.ppid,
          observerNonce: message.nonce,
          observerPublicKey: keys.publicKey.export({ type: "spki", format: "der" }).toString("base64url"),
        };
        process.send({ type: "ready", ready: signedObserverMessage(ready, keys.privateKey) });
        return;
      }
      if (!observer || !/^[a-f0-9]{32}$/.test(String(message?.requestId || ""))) {
        throw blockedError("independent_installed_evidence_producer_unavailable");
      }
      if (message.type === "observe") {
        verifyIndependentComputerObservation(observer, message.observation);
        process.send(signedObserverMessage({
          type: "response",
          requestId: message.requestId,
          observerNonce: observer.nonce,
          processId: process.pid,
          accepted: true,
        }, observer.privateKey));
        return;
      }
      if (message.type === "produce") {
        const produced = await produceIndependentObserverManifest(observer);
        process.send(signedObserverMessage({
          type: "response",
          requestId: message.requestId,
          observerNonce: observer.nonce,
          processId: process.pid,
          ...produced,
        }, observer.privateKey));
        return;
      }
      throw blockedError("independent_installed_evidence_producer_unavailable");
    } catch (error) {
      if (observer && /^[a-f0-9]{32}$/.test(String(message?.requestId || ""))) {
        process.send(signedObserverMessage({
          type: "response",
          requestId: message.requestId,
          observerNonce: observer.nonce,
          processId: process.pid,
          accepted: false,
          blocker: error?.blocked
            ? String(error.message)
            : "independent_installed_evidence_producer_unavailable",
        }, observer.privateKey));
      } else {
        process.send({
          type: "observer_error",
          blocker: error?.blocked
            ? String(error.message)
            : "independent_installed_evidence_producer_unavailable",
        });
      }
    }
  });
}

async function startIndependentEvidenceObserver({
  scenario,
  identity,
  desktopDriver,
  evidenceRoot,
  runtimeEnvironment,
  timeoutMs = 5000,
}) {
  const adapter = assertComputerDesktopDriver(desktopDriver, scenario, identity);
  const privateEvidenceRoot = assertPrivateEvidenceRoot(evidenceRoot);
  const nonce = crypto.randomBytes(32).toString("hex");
  const child = fork(__filename, ["--independent-observer"], {
    cwd: REPO_ROOT,
    env: { PATH: process.env.PATH || "", NODE_NO_WARNINGS: "1" },
    execArgv: [],
    silent: true,
    serialization: "advanced",
  });
  let ready;
  try {
    ready = await new Promise((resolve, reject) => {
      let settled = false;
      const finish = (error, value) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        child.off("message", receive);
        child.off("error", fail);
        child.off("exit", exited);
        if (error) reject(error);
        else resolve(value);
      };
      const fail = () => finish(blockedError("independent_installed_evidence_producer_unavailable"));
      const exited = () => fail();
      const receive = (message) => {
        if (message?.type === "observer_error") {
          return finish(blockedError(message.blocker));
        }
        if (message?.type !== "ready") return;
        try {
          const verified = assertIndependentObserverReady(
            message.ready,
            scenario,
            identity,
            adapter,
            { expectedProcessId: child.pid, expectedNonce: nonce },
          );
          finish(null, verified);
        } catch (error) {
          finish(error);
        }
      };
      const timer = setTimeout(fail, Math.min(Math.max(timeoutMs, 250), 10000));
      child.on("message", receive);
      child.once("error", fail);
      child.once("exit", exited);
      child.send({
        type: "bootstrap",
        parentProcessId: process.pid,
        nonce,
        scenario,
        identity,
        evidenceRoot: privateEvidenceRoot,
        mongoUri: String(runtimeEnvironment?.MONGO_URI || ""),
        provenance: adapter.driver.provenance,
        computerPublicKey: adapter.authority.publicKey.export({ type: "spki", format: "der" }).toString("base64url"),
      });
    });
  } catch (error) {
    if (child.connected) child.disconnect();
    if (child.exitCode === null) child.kill();
    throw error;
  }
  const observerPublicKey = crypto.createPublicKey({
    key: Buffer.from(ready.observerPublicKey, "base64url"),
    format: "der",
    type: "spki",
  });
  async function request(type, payload = {}) {
    return new Promise((resolve, reject) => {
      const requestId = crypto.randomBytes(16).toString("hex");
      const finish = (error, value) => {
        clearTimeout(timer);
        child.off("message", receive);
        if (error) reject(error);
        else resolve(value);
      };
      const receive = (message) => {
        if (message?.type !== "response" || message.requestId !== requestId) return;
        const { proof, ...unsigned } = message;
        if (
          message.processId !== child.pid ||
          message.observerNonce !== nonce ||
          !verifyExternalComputerProof(observerPublicKey, unsigned, proof)
        ) {
          return finish(blockedError("independent_installed_evidence_producer_unavailable"));
        }
        if (message.accepted === false) {
          return finish(blockedError(message.blocker));
        }
        return finish(null, message);
      };
      const timer = setTimeout(
        () => finish(blockedError("independent_installed_evidence_producer_unavailable")),
        Math.min(Math.max(timeoutMs, 250), 30000),
      );
      child.on("message", receive);
      try {
        child.send({ type, requestId, ...payload });
      } catch {
        finish(blockedError("independent_installed_evidence_producer_unavailable"));
      }
    });
  }
  return {
    ready,
    observe(observation) {
      return request("observe", { observation });
    },
    produce() {
      return request("produce");
    },
    async close() {
      if (!child.connected && child.exitCode !== null) return;
      await new Promise((resolve) => {
        let completed = false;
        const finish = () => {
          if (completed) return;
          completed = true;
          clearTimeout(timer);
          resolve();
        };
        const timer = setTimeout(() => {
          if (child.exitCode === null) child.kill();
          finish();
        }, 1000);
        child.once("exit", finish);
        if (child.connected) child.disconnect();
        else if (child.exitCode !== null) finish();
      });
    },
  };
}

function assertOwnerSafeTelegramIdentity(scenario, environment, observed) {
  assertSyntheticOwner(scenario, environment);
  const personalLabel = String(environment?.VIVENTIUM_QA_OWNER_TELEGRAM_ACCOUNT_LABEL || "").trim();
  if (!personalLabel) throw blockedError("personal_owner_identity_guard_required");
  if (observed?.activeSelectionVerified !== true) {
    throw blockedError("computer_desktop_active_selection_unavailable");
  }
  if (
    observed?.source !== "computer_plugin_sky" ||
    observed.bundleId !== scenario.telegram.bundleId ||
    observed.accountVisible !== true ||
    observed.chatVisible !== true ||
    observed.accountLabel !== scenario.telegram.accountLabel ||
    observed.accountLabel === personalLabel ||
    observed.chatLabel !== scenario.telegram.chatLabel ||
    observed.ownerId !== scenario.owner.ownerId ||
    observed.linkedOwnerId !== scenario.owner.ownerId ||
    String(observed.telegramUserId || "") !== scenario.owner.telegramUserId ||
    String(observed.telegramChatId || "") !== scenario.owner.telegramChatId
  ) {
    throw blockedError("owner_safe_telegram_identity_unavailable");
  }
  return observed;
}

function timestamp(value) {
  if (typeof value !== "string") return Number.NaN;
  return Date.parse(value);
}

function bindTrustedIngress(scenario, event, stage) {
  const expected = scenario?.source?.[stage];
  if (
    !expected ||
    event?.source !== "installed_telegram_ingress_ledger" ||
    event.ownerId !== scenario.owner.ownerId ||
    event.ownerUserId !== Number(scenario.owner.telegramUserId) ||
    event.chatId !== Number(scenario.owner.telegramChatId) ||
    event.threadId !== scenario.owner.telegramThreadId ||
    event.conversationId !== scenario.conversation.conversationId ||
    event.messageId !== expected.messageId ||
    event.sourceSequence !== event.messageId ||
    event.updateId !== expected.updateId ||
    !Number.isFinite(timestamp(event.observedAt))
  ) {
    throw blockedError("trusted_telegram_ingress_binding_invalid");
  }
  return event;
}

function buildArmScope(scenario, first) {
  const observed = bindTrustedIngress(scenario, first, "first");
  const target = scenario.source.revision;
  if (target.messageId !== observed.sourceSequence + 1 || target.updateId !== observed.updateId + 1) {
    throw blockedError("trusted_telegram_ingress_binding_invalid");
  }
  return {
    contractVersion: CONTRACT_VERSION,
    caseId: CASE_ID,
    ownerUserId: observed.ownerUserId,
    chatId: observed.chatId,
    threadId: observed.threadId,
    staleSourceSequence: observed.sourceSequence,
    sourceSequence: target.messageId,
    updateId: target.updateId,
    ttlSeconds: 120,
  };
}

function assertArmReceipt(receipt, session) {
  if (
    receipt?.armed !== true ||
    !/^[a-f0-9]{16}$/.test(String(receipt.artifactRef || "")) ||
    receipt.delayMs !== DELAY_MS ||
    !SESSION_REF.test(String(receipt.sessionRef || "")) ||
    receipt.sessionRef !== session?.sessionRef
  ) {
    throw blockedError("authentic_280ms_race_control_unavailable");
  }
  return receipt;
}

function assertRestartReady(status, session) {
  if (
    status?.sessionRef !== session?.sessionRef ||
    status.restartState !== "ready" ||
    canonicalJson(status.requiredServices) !== canonicalJson(REQUIRED_SERVICES) ||
    canonicalJson(status.acknowledgedServices) !== canonicalJson(REQUIRED_SERVICES) ||
    !Array.isArray(status.missingServices) ||
    status.missingServices.length
  ) {
    throw blockedError("installed_core_and_telegram_restart_unacknowledged");
  }
  return status;
}

function assessAuthenticatedAudit(audit, armed, scope, expectedEventDigest) {
  const records = audit?.evidence;
  if (
    audit?.caseId !== CASE_ID ||
    audit.sessionRef !== armed?.sessionRef ||
    !SHA256.test(String(expectedEventDigest || "")) ||
    scope?.sourceSequence !== scope.staleSourceSequence + 1 ||
    !Array.isArray(records) ||
    records.length !== 2
  ) {
    throw blockedError("authenticated_280ms_race_audit_unavailable");
  }

  const expected = [
    ["claimed", "exact_structured_target"],
    ["delay_requested", "core_admission_boundary"],
  ];
  for (const [index, record] of records.entries()) {
    if (
      record?.schema_version !== 3 ||
      record.case_id !== CASE_ID ||
      record.artifact_ref !== armed.artifactRef ||
      record.session_ref !== armed.sessionRef ||
      record.chain_index !== index + 1 ||
      record.outcome !== expected[index][0] ||
      record.reason !== expected[index][1] ||
      record.configured_delay_ms !== DELAY_MS ||
      record.event_digest !== expectedEventDigest
    ) {
      throw blockedError("authenticated_280ms_race_audit_unavailable");
    }
  }
  return { delayMs: DELAY_MS, eventDigest: expectedEventDigest, recordCount: records.length };
}

function assessRapidRevision({ scenario, first, revision, observation }) {
  const original = bindTrustedIngress(scenario, first, "first");
  const corrected = bindTrustedIngress(scenario, revision, "revision");
  if (
    observation?.source !== "installed_mongo_and_telegram_desktop" ||
    observation.ownerId !== scenario.owner.ownerId ||
    observation.conversationId !== scenario.conversation.conversationId ||
    canonicalJson(observation.sourceMessageIds) !==
      canonicalJson([original.messageId, corrected.messageId]) ||
    canonicalJson(observation.sourceSequences) !==
      canonicalJson([original.sourceSequence, corrected.sourceSequence])
  ) {
    throw blockedError("trusted_source_order_unproven");
  }
  const expectedUserBubbles = [
    { role: "user", messageId: original.messageId, text: scenario.source.first.text },
    { role: "user", messageId: corrected.messageId, text: scenario.source.revision.text },
  ];
  if (
    !Array.isArray(observation.userBubbles) ||
    canonicalJson(observation.userBubbles) !== canonicalJson(expectedUserBubbles)
  ) {
    throw blockedError("original_telegram_user_messages_missing");
  }
  if (
    !SHA256.test(String(observation.turnRefHash || "")) ||
    observation.initialTurnRefHash !== observation.turnRefHash ||
    observation.correctedTurnRefHash !== observation.turnRefHash ||
    observation.initialRevision !== 1 ||
    observation.correctedRevision !== 2
  ) {
    throw blockedError("one_revised_logical_turn_required");
  }
  if (
    observation.assistantBubbleCount !== 1 ||
    !Array.isArray(observation.finalReplies) ||
    observation.finalReplies.length !== 1 ||
    observation.finalReplies[0]?.revision !== 2 ||
    !positiveSafeInteger(observation.finalReplies[0].messageId)
  ) {
    throw blockedError("exactly_one_final_revised_reply_required");
  }

  const finalText = String(observation.finalReplies[0].text || "").trim();
  if (!/^\p{Extended_Pictographic}/u.test(finalText)) {
    throw blockedError("emoji_leading_revised_reply_required");
  }
  if (!finalText.includes(scenario.source.expectedReplyMarker)) {
    throw blockedError("revised_reply_content_unproven");
  }
  if (
    observation.staleReplyVisible !== false ||
    observation.staleReplyRetracted !== true ||
    finalText.includes(scenario.source.staleReplyMarker)
  ) {
    throw blockedError("stale_first_reply_visible");
  }
  if (observation.reopenedMatches !== true) throw blockedError("reopened_telegram_revision_unproven");
  return {
    turnRefHash: observation.turnRefHash,
    finalReplyCount: 1,
    revision: 2,
    finalReplySha256: sha256(finalText),
  };
}

function assessPostCommitControl(scenario, observation, previousTurnRefHash) {
  const committedAt = timestamp(observation?.previousCommittedAt);
  const observedAt = timestamp(observation?.sourceObservedAt);
  if (
    observation?.source !== "installed_mongo_and_telegram_desktop" ||
    observation.ownerId !== scenario.owner.ownerId ||
    observation.conversationId !== scenario.conversation.conversationId ||
    observation.previousTurnRefHash !== previousTurnRefHash ||
    !SHA256.test(String(observation.followUpTurnRefHash || "")) ||
    observation.followUpTurnRefHash === previousTurnRefHash ||
    observation.followUpRevision !== 1 ||
    observation.sourceMessageId !== scenario.source.postCommit.messageId ||
    observation.sourceSequence !== observation.sourceMessageId ||
    !Number.isFinite(committedAt) ||
    !Number.isFinite(observedAt) ||
    committedAt >= observedAt
  ) {
    throw blockedError("post_commit_normal_follow_up_unproven");
  }
  return { revision: 1, turnRefHash: observation.followUpTurnRefHash };
}

function assessWorkersUnaffected(before, after, scenario) {
  if (!Array.isArray(before) || !Array.isArray(after) || before.length !== 2 || after.length !== 2) {
    throw blockedError("two_owner_scoped_workers_affected");
  }
  const expected = scenario?.workers?.workRefs || [];
  for (const [index, original] of before.entries()) {
    const current = after[index];
    if (
      original?.source !== "installed_glasshive_read_only_store" ||
      current?.source !== "installed_glasshive_read_only_store" ||
      original.ownerId !== scenario.owner.ownerId ||
      current.ownerId !== scenario.owner.ownerId ||
      original.workRef !== expected[index] ||
      current.workRef !== expected[index] ||
      !String(original.workerRef || "").trim() ||
      current.workerRef !== original.workerRef ||
      !String(original.runRef || "").trim() ||
      current.runRef !== original.runRef ||
      original.state !== "running" ||
      !new Set(["running", "completed"]).has(current.state) ||
      original.cancelRequested !== false ||
      current.cancelRequested !== false ||
      !Number.isFinite(timestamp(original.runtimeInvokedAt))
    ) {
      throw blockedError("two_owner_scoped_workers_affected");
    }
  }
  return { workerCount: 2, workRefHashes: expected.map((value) => sha256(value)) };
}

function assessIndependentVerifier(result, identity, sessionRef, turnRefHash) {
  if (
    result?.caseId !== CASE_ID ||
    result.status !== "PASS" ||
    result.ready !== true ||
    result.surface !== "telegram" ||
    result.candidateDigest !== identity?.candidateDigest ||
    result.artifactDigest !== identity?.artifactDigest ||
    !Array.isArray(result.blockers) ||
    result.blockers.length ||
    !Array.isArray(result.gates) ||
    result.gates.length !== REQUIRED_VERIFIER_GATES.length ||
    REQUIRED_VERIFIER_GATES.some(
      (gate, index) => result.gates[index]?.id !== gate || result.gates[index].status !== "PASS",
    ) ||
    result.manifest?.caseId !== CASE_ID ||
    result.manifest.candidate?.candidateDigest !== identity.candidateDigest ||
    result.manifest.candidate?.artifactDigest !== identity.artifactDigest ||
    result.manifest.correlation?.sessionRef !== sessionRef ||
    !SHA256.test(String(identity.ownerRefHash || "")) ||
    result.manifest.correlation.ownerRefHash !== identity.ownerRefHash ||
    result.manifest.correlation.turnRefHash !== turnRefHash
  ) {
    throw blockedError("independent_semantic_verifier_evidence_unavailable");
  }
  return result;
}

function parseRuntimeEnv(location) {
  let raw;
  try {
    raw = fs.readFileSync(location, "utf8");
  } catch (error) {
    if (error?.code === "ENOENT") return {};
    throw blockedError("installed_runtime_environment_unavailable");
  }
  const result = {};
  for (const line of raw.split(/\r?\n/)) {
    const match = /^([A-Z][A-Z0-9_]*)=(.*)$/.exec(line.trim());
    if (!match) continue;
    let value = match[2].trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    result[match[1]] = value;
  }
  return result;
}

function loadReadOnlyRuntimeEnvironment(scenario, environment) {
  let runtimeRoot;
  try {
    runtimeRoot = fs.realpathSync(scenario.runtime.runtimeRoot);
  } catch {
    throw blockedError("installed_runtime_environment_unavailable");
  }
  const values = {
    ...parseRuntimeEnv(path.join(runtimeRoot, "runtime.env")),
    ...parseRuntimeEnv(path.join(runtimeRoot, "runtime.local.env")),
    ...parseRuntimeEnv(path.join(runtimeRoot, "service-env", "librechat.env")),
    ...parseRuntimeEnv(path.join(runtimeRoot, "service-env", "librechat.owner.env")),
    ...parseRuntimeEnv(path.join(runtimeRoot, "service-env", "glasshive.env")),
    ...environment,
  };
  if (!String(values.MONGO_URI || "").trim()) throw blockedError("installed_mongo_uri_unavailable");
  try {
    if (
      !String(values.WPR_DB_PATH || "").trim() ||
      fs.realpathSync(values.WPR_DB_PATH) !== fs.realpathSync(scenario.runtime.glassHiveDbPath)
    ) {
      throw blockedError("installed_glasshive_database_identity_unproven");
    }
  } catch (error) {
    if (error?.blocked) throw error;
    throw blockedError("installed_glasshive_database_identity_unproven");
  }
  return values;
}

function pythonExecutable(environment) {
  return String(environment?.VIVENTIUM_QA_PYTHON_BIN || "python3");
}

function measureInstalledCandidate(scenario, environment) {
  const script = path.join(REPO_ROOT, "scripts", "viventium", "parallel_work_release_gate.py");
  const probe = [
    "import importlib.util,json,sys",
    "from pathlib import Path",
    "spec=importlib.util.spec_from_file_location('tr026_installed_candidate_probe',sys.argv[1])",
    "module=importlib.util.module_from_spec(spec)",
    "sys.modules[spec.name]=module",
    "spec.loader.exec_module(module)",
    "identity=json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))",
    "installed=Path(sys.argv[3]).resolve(strict=True)",
    "owner_path=Path(sys.argv[4]).resolve(strict=True)",
    "runtime=Path(sys.argv[5]).resolve(strict=True)",
    "owner=json.loads(owner_path.read_text(encoding='utf-8'))",
    "active=module._runtime_owner_state_proves_active(installed,owner_path)",
    "root_ok=Path(str(owner.get('repoRoot') or '')).resolve(strict=True)==installed",
    "runtime_ok=Path(str(owner.get('runtimeDir') or '')).resolve(strict=True)==runtime",
    "candidate,artifact=module._qa_candidate_digests(identity)",
    "owner_hash=module._owner_binding_sha256(owner)",
    "print(json.dumps({'verified':bool(active and root_ok and runtime_ok),'candidateDigest':candidate,'artifactDigest':artifact,'ownerRefHash':owner_hash}))",
  ].join(";");
  const result = spawnSync(
    pythonExecutable(environment),
    [
      "-c",
      probe,
      script,
      scenario.runtime.artifactIdentityPath,
      scenario.runtime.installedRoot,
      scenario.runtime.runtimeOwnerStatePath,
      scenario.runtime.runtimeRoot,
    ],
    {
      encoding: "utf8",
      timeout: 30000,
      maxBuffer: 1024 * 1024,
      env: { ...environment, PYTHONDONTWRITEBYTECODE: "1" },
    },
  );
  if (result.status !== 0) throw blockedError("installed_candidate_identity_unproven");
  try {
    const identity = JSON.parse(result.stdout);
    if (
      identity.verified !== true ||
      !SHA256.test(String(identity.candidateDigest || "")) ||
      !SHA256.test(String(identity.artifactDigest || "")) ||
      !SHA256.test(String(identity.ownerRefHash || ""))
    ) {
      throw blockedError("installed_candidate_identity_unproven");
    }
    return identity;
  } catch (error) {
    if (error?.blocked) throw error;
    throw blockedError("installed_candidate_identity_unproven");
  }
}

function openReadOnlyGlassHiveStore(location) {
  let exact;
  try {
    exact = fs.realpathSync(location);
    if (!fs.statSync(exact).isFile()) throw blockedError("glasshive_runtime_database_unavailable");
  } catch (error) {
    if (error?.blocked) throw error;
    throw blockedError("glasshive_runtime_database_unavailable");
  }
  const { DatabaseSync } = require("node:sqlite");
  return new DatabaseSync(exact, { readOnly: true });
}

async function waitFor(check, { timeoutMs, blocker, pollMs = 40 }) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const value = await check();
    if (value) return value;
    await new Promise((resolve) => setTimeout(resolve, pollMs));
  }
  throw blockedError(blocker);
}

function invokeQaControl(scenario, operation, { input, sessionRef, environment, timeoutMs } = {}) {
  const executable = scenario.restart.executable;
  const commands = {
    activate: ["qa-control", "activate", "--case-id", CASE_ID, "--expires-in-seconds", "900"],
    status: ["qa-control", "status"],
    arm: ["qa-control", "arm-telegram-race"],
    audit: ["qa-control", "audit-telegram-race"],
    cleanup: ["qa-control", "cleanup-telegram-race"],
    clear: ["qa-control", "clear", "--session-ref", String(sessionRef || "")],
  };
  if (!Object.hasOwn(commands, operation)) throw blockedError("unsupported_qa_control_operation");
  if (operation === "clear" && !SESSION_REF.test(String(sessionRef || ""))) {
    throw blockedError("exact_qa_session_reference_required");
  }
  const completed = spawnSync(executable, commands[operation], {
    cwd: REPO_ROOT,
    encoding: "utf8",
    input: input ? `${JSON.stringify(input)}\n` : undefined,
    timeout: Math.min(timeoutMs || 30000, 30000),
    maxBuffer: 1024 * 1024,
    env: { ...environment, PYTHONDONTWRITEBYTECODE: "1" },
  });
  if (completed.status !== 0) throw blockedError(`installed_qa_control_${operation}_unavailable`);
  try {
    const output = JSON.parse(completed.stdout);
    if (!output || typeof output !== "object" || Array.isArray(output)) {
      throw blockedError(`installed_qa_control_${operation}_unavailable`);
    }
    return output;
  } catch (error) {
    if (error?.blocked) throw error;
    throw blockedError(`installed_qa_control_${operation}_unavailable`);
  }
}

function sourceOrderScope(scenario) {
  return sha256(
    [
      "viventium.telegram-source-order.v2",
      "telegram-interactive-v1",
      scenario.owner.ownerId,
      scenario.owner.telegramUserId,
      scenario.owner.telegramChatId,
      scenario.owner.telegramThreadId ? String(scenario.owner.telegramThreadId) : "",
    ].join("\0"),
  );
}

function interactionMetadata(message) {
  return message?.metadata?.viventium?.interactionContext || {};
}

function deliveryMetadata(message) {
  return message?.metadata?.viventium?.deliveryAcknowledgement || {};
}

function telegramPresentationId(message, scenario) {
  const acknowledgement = deliveryMetadata(message);
  const values = Array.isArray(acknowledgement.presentation_refs)
    ? acknowledgement.presentation_refs
    : [acknowledgement.presentation_ref];
  const selected = values
    .map((value) => /^telegram:([^:]+):(\d+)$/.exec(String(value || "")))
    .filter((match) => match && match[1] === scenario.owner.telegramChatId)
    .map((match) => Number(match[2]));
  return selected.length === 1 && positiveSafeInteger(selected[0]) ? selected[0] : null;
}

function saveComputerCapture(capture, { desktopDriver, evidenceRoot, qaRunId, phase }) {
  const observation = assertComputerAction(capture, desktopDriver, "get_app_state");
  const bytes = observation.screenshotBytes;
  if (
    observation.phase !== phase ||
    observation.windowVisible !== true ||
    !Array.isArray(observation.bubbles) ||
    !Buffer.isBuffer(bytes) ||
    bytes.length < 128 ||
    !bytes.subarray(0, PNG_SIGNATURE.length).equals(PNG_SIGNATURE)
  ) {
    throw blockedError("computer_plugin_telegram_capture_unavailable");
  }
  const written = writePrivateEvidence(evidenceRoot, `${qaRunId}-${phase}.png`, bytes);
  return {
    phase,
    observedAt: new Date(observation.observedAtMs).toISOString(),
    bubbles: observation.bubbles,
    screenshotSha256: written.sha256,
  };
}

function trustedComputerIdentity(observed, state, scenario) {
  const action = assertComputerAction(observed, state.desktopDriver, "get_app_state");
  const selection = assertActiveSelectedTelegramContext(action, scenario);
  return {
    source: "computer_plugin_sky",
    bundleId: action.app,
    accountLabel: selection.account.label,
    chatLabel: selection.chat.label,
    accountVisible: selection.account.selected === true,
    chatVisible: selection.chat.selected === true,
    activeSelectionVerified: true,
    ownerId: selection.account.ownerId,
    linkedOwnerId: selection.chat.ownerId,
    telegramUserId: String(selection.account.telegramUserId),
    telegramChatId: String(selection.chat.telegramChatId),
    visibleText: typeof action.text === "string" ? action.text.split(/\r?\n/) : [],
    expectedChatRefHash: sha256(selection.chat.telegramChatId),
  };
}

function exactWorkerRows(store, scenario) {
  const rows = store
    .prepare(
      `SELECT d.owner_id AS ownerId, d.work_ref AS workRef,
              d.worker_id AS workerRef, d.current_run_id AS runRef,
              r.state AS state, r.runtime_invoked_at AS runtimeInvokedAt,
              w.work_stop_requested_at AS stopRequestedAt
       FROM delegations d
       JOIN workers w ON w.worker_id = d.worker_id AND w.owner_id = d.owner_id
       JOIN runs r ON r.run_id = d.current_run_id
       WHERE d.owner_id = ? AND d.work_ref IN (?, ?)`,
    )
    .all(scenario.owner.ownerId, ...scenario.workers.workRefs)
    .map((row) => ({
      source: "installed_glasshive_read_only_store",
      ownerId: row.ownerId,
      workRef: row.workRef,
      workerRef: row.workerRef,
      runRef: row.runRef,
      state: row.state,
      runtimeInvokedAt: row.runtimeInvokedAt,
      cancelRequested: Boolean(row.stopRequestedAt),
    }))
    .sort(
      (left, right) =>
        scenario.workers.workRefs.indexOf(left.workRef) - scenario.workers.workRefs.indexOf(right.workRef),
    );
  if (rows.length !== 2) throw blockedError("two_owner_scoped_workers_affected");
  return rows;
}

async function createInstalledDriver({ scenario, args, environment, evidenceRoot, desktopDriver }) {
  desktopDriver = assertComputerDesktopDriver(desktopDriver, scenario);
  const runtimeEnvironment = loadReadOnlyRuntimeEnvironment(scenario, environment);
  let MongoClient;
  try {
    ({ MongoClient } = require(path.join(LIBRECHAT_ROOT, "node_modules", "mongodb")));
  } catch {
    throw blockedError("installed_mongo_driver_unavailable");
  }
  const mongo = new MongoClient(runtimeEnvironment.MONGO_URI, { serverSelectionTimeoutMS: 5000 });
  const state = {
    desktopDriver,
    database: null,
    store: null,
    mapping: null,
    telegramChatBinding: null,
    ownerId: "",
    user: null,
    identity: null,
    session: null,
    launchedAt: 0,
    ingress: new Map(),
    captures: new Map(),
    stale: null,
    final: null,
    followUp: null,
    observer: null,
    ingressRecords: new Map(),
  };

  async function ownerMessages() {
    return state.database
      .collection("messages")
      .find({
        user: state.ownerId,
        conversationId: scenario.conversation.conversationId,
        createdAt: { $gte: new Date(state.launchedAt - 1000) },
      })
      .sort({ createdAt: 1 })
      .limit(32)
      .toArray();
  }

  async function capturePhase(phase) {
    const captured = await readOwnerBoundComputerState(desktopDriver, scenario, {
      phase,
      includeScreenshot: true,
    });
    if (!state.observer || (await state.observer.observe(captured))?.accepted !== true) {
      throw blockedError("independent_observer_computer_observation_untrusted");
    }
    const observation = saveComputerCapture(captured, {
      desktopDriver,
      evidenceRoot,
      qaRunId: args.qaRunId,
      phase,
    });
    state.captures.set(phase, observation);
    return observation;
  }

  return {
    async preflightInstalledCandidate() {
      const identity = measureInstalledCandidate(scenario, environment);
      await mongo.connect();
      const databaseName = new URL(runtimeEnvironment.MONGO_URI).pathname.replace(/^\//, "") ||
        "LibreChatViventium";
      state.database = mongo.db(databaseName);
      const user = await state.database.collection("users").findOne(
        { email: scenario.owner.email },
        { projection: { _id: 1, email: 1, role: 1 } },
      );
      if (
        !user?._id ||
        String(user._id) !== scenario.owner.ownerId ||
        String(user.email || "").trim().toLowerCase() !== scenario.owner.email ||
        String(user.role || "").toUpperCase() === "ADMIN"
      ) {
        throw blockedError("synthetic_linked_owner_unavailable");
      }
      state.ownerId = String(user._id);
      state.user = user;
      state.mapping = await state.database.collection("telegramusermappings").findOne(
        { telegramUserId: scenario.owner.telegramUserId, libreChatUserId: user._id },
        { projection: { telegramUserId: 1, libreChatUserId: 1 } },
      );
      if (
        !state.mapping ||
        String(state.mapping.libreChatUserId) !== state.ownerId ||
        String(state.mapping.telegramUserId) !== scenario.owner.telegramUserId
      ) {
        throw blockedError("owner_safe_telegram_identity_unavailable");
      }
      const conversation = await state.database.collection("conversations").findOne(
        { user: state.ownerId, conversationId: scenario.conversation.conversationId },
        { projection: { conversationId: 1, user: 1 } },
      );
      if (!conversation || conversation.conversationId !== scenario.conversation.conversationId) {
        throw blockedError("owner_scoped_conversation_required");
      }
      state.telegramChatBinding = assertOwnerScopedTelegramChatBinding(
        scenario,
        state.mapping,
        await state.database.collection("viventiumtelegramingressevents").findOne(
          {
            telegramUserId: scenario.owner.telegramUserId,
            telegramChatId: scenario.owner.telegramChatId,
            conversationId: scenario.conversation.conversationId,
          },
          { projection: { telegramUserId: 1, telegramChatId: 1, conversationId: 1 } },
        ),
      );
      state.store = openReadOnlyGlassHiveStore(scenario.runtime.glassHiveDbPath);
      state.identity = identity;
      return identity;
    },

    async assertComputerDesktopProvenance() {
      assertComputerDesktopDriver(desktopDriver, scenario, state.identity);
      return { provider: "@oai/sky", verified: true };
    },

    async probeTelegramIdentity() {
      const observed = await readOwnerBoundComputerState(desktopDriver, scenario);
      return trustedComputerIdentity(observed, state, scenario);
    },

    async requireIndependentEvidenceProducer() {
      state.observer = await startIndependentEvidenceObserver({
        scenario,
        identity: state.identity,
        desktopDriver,
        evidenceRoot,
        runtimeEnvironment,
        timeoutMs: Math.min(args.timeoutMs, 10000),
      });
      return {
        verified: true,
        producer: scenario.evidence.producer,
        processId: state.observer.ready.processId,
      };
    },

    async observeWorkers() {
      return exactWorkerRows(state.store, scenario);
    },

    async activateQaControl() {
      const session = invokeQaControl(scenario, "activate", {
        environment,
        timeoutMs: args.timeoutMs,
      });
      if (session.caseId !== CASE_ID || !SESSION_REF.test(String(session.sessionRef || ""))) {
        throw blockedError("exact_tr026_local_qa_session_unavailable");
      }
      state.session = session;
      return session;
    },

    async restartRuntime() {
      const completed = spawnSync(scenario.restart.executable, scenario.restart.arguments, {
        cwd: REPO_ROOT,
        encoding: "utf8",
        timeout: args.timeoutMs,
        maxBuffer: 1024 * 1024,
        env: { ...environment, PYTHONDONTWRITEBYTECODE: "1" },
      });
      if (completed.status !== 0) throw blockedError("consented_installed_runtime_restart_unavailable");
      return { restarted: true };
    },

    async requireRestartReady() {
      return invokeQaControl(scenario, "status", { environment, timeoutMs: args.timeoutMs });
    },

    async sendTelegramSegment(stage) {
      const segment = scenario.source[stage];
      if (!segment) throw blockedError("supported_telegram_segment_unavailable");
      if (stage === "first") state.launchedAt = Date.now();
      const sent = await performOwnerBoundComputerAction(desktopDriver, scenario, {
        action: "telegram.send_text",
        text: segment.text,
        stage,
      });
      if ((sent.sent !== true && sent.status !== "sent") || sent.stage !== stage) {
        throw blockedError("computer_plugin_telegram_user_ingress_unavailable");
      }
      if (!state.observer || (await state.observer.observe(sent))?.accepted !== true) {
        throw blockedError("independent_observer_computer_observation_untrusted");
      }
      if (stage === "revision") {
        await waitFor(async () => {
          const messages = await ownerMessages();
          const stale = messages.find((message) => {
            const context = interactionMetadata(message);
            return (
              message.isCreatedByUser !== true &&
              context.revision === 1 &&
              deliveryMetadata(message).state === "committed" &&
              String(message.text || "").includes(scenario.source.staleReplyMarker)
            );
          });
          if (!stale) return null;
          const capture = await capturePhase("before_correction");
          if (!capture.bubbles.some((bubble) => String(bubble.text || "").includes(scenario.source.staleReplyMarker))) {
            throw blockedError("computer_plugin_stale_presentation_unavailable");
          }
          state.stale = stale;
          return capture;
        }, {
          timeoutMs: Math.min(args.timeoutMs, 1000),
          blocker: "computer_plugin_stale_presentation_unavailable",
          pollMs: 15,
        });
      }
      return { sent: true, source: "computer_plugin_sky" };
    },

    async observeTrustedIngress(stage) {
      const segment = scenario.source[stage];
      const observed = await waitFor(async () => {
        const record = await state.database.collection("viventiumtelegramingressevents").findOne(
          {
            telegramUserId: scenario.owner.telegramUserId,
            telegramChatId: scenario.owner.telegramChatId,
            telegramMessageId: String(segment.messageId),
            telegramUpdateId: String(segment.updateId),
            conversationId: scenario.conversation.conversationId,
            createdAt: { $gte: new Date(state.launchedAt - 1000) },
          },
          {
            projection: {
              telegramUserId: 1,
              telegramChatId: 1,
              telegramMessageId: 1,
              telegramUpdateId: 1,
              conversationId: 1,
              createdAt: 1,
            },
          },
        );
        if (!record) return null;
        const message = await state.database.collection("messages").findOne({
          user: state.ownerId,
          conversationId: scenario.conversation.conversationId,
          isCreatedByUser: true,
          text: segment.text,
          createdAt: { $gte: new Date(state.launchedAt - 1000) },
        });
        if (!message) return null;
        const context = interactionMetadata(message);
        if (
          context.source_order_scope !== sourceOrderScope(scenario) ||
          Number(context.source_sequence) !== segment.messageId
        ) {
          throw blockedError("trusted_telegram_ingress_binding_invalid");
        }
        state.ingressRecords.set(stage, record);
        return {
          source: "installed_telegram_ingress_ledger",
          ownerId: state.ownerId,
          ownerUserId: Number(record.telegramUserId),
          chatId: Number(record.telegramChatId),
          threadId: scenario.owner.telegramThreadId,
          conversationId: record.conversationId,
          messageId: Number(record.telegramMessageId),
          sourceSequence: Number(context.source_sequence),
          updateId: Number(record.telegramUpdateId),
          observedAt: new Date(record.createdAt).toISOString(),
        };
      }, {
        timeoutMs: args.timeoutMs,
        blocker: "trusted_telegram_ingress_binding_unavailable",
      });
      state.ingress.set(stage, observed);
      return observed;
    },

    async armTelegramRace(scope) {
      return invokeQaControl(scenario, "arm", {
        input: scope,
        environment,
        timeoutMs: args.timeoutMs,
      });
    },

    async observeRapidRevision() {
      const current = await waitFor(async () => {
        const messages = await ownerMessages();
        const users = scenario.source.first.text === scenario.source.revision.text
          ? []
          : [scenario.source.first.text, scenario.source.revision.text]
              .map((text) => messages.filter((message) => message.isCreatedByUser === true && message.text === text));
        if (users.length !== 2 || users.some((items) => items.length !== 1)) return null;
        const currentReplies = messages.filter((message) => {
          const context = interactionMetadata(message);
          const acknowledgement = deliveryMetadata(message);
          return (
            message.isCreatedByUser !== true &&
            context.revision === 2 &&
            acknowledgement.revision === 2 &&
            acknowledgement.state === "committed" &&
            message.unfinished === false
          );
        });
        if (currentReplies.length > 1) throw blockedError("exactly_one_final_revised_reply_required");
        if (currentReplies.length !== 1) return null;
        return { users: users.map((items) => items[0]), reply: currentReplies[0] };
      }, { timeoutMs: args.timeoutMs, blocker: "exactly_one_final_revised_reply_required" });

      if (!state.stale || !state.captures.has("before_correction")) {
        throw blockedError("computer_plugin_stale_presentation_unavailable");
      }
      const initialContext = interactionMetadata(state.stale);
      const correctedContext = interactionMetadata(current.reply);
      const settled = await capturePhase("settled");
      const reopened = await performOwnerBoundComputerAction(desktopDriver, scenario, {
        action: "telegram.reopen_conversation",
      });
      if (reopened.performed !== true && reopened.status !== "opened") {
        throw blockedError("reopened_telegram_revision_unproven");
      }
      if (!state.observer || (await state.observer.observe(reopened))?.accepted !== true) {
        throw blockedError("independent_observer_computer_observation_untrusted");
      }
      const reopenCapture = await capturePhase("reopened");
      const assistantBubbles = settled.bubbles.filter((bubble) => bubble.role === "assistant");
      const finalMessageId = telegramPresentationId(current.reply, scenario);
      if (!finalMessageId) throw blockedError("exactly_one_final_revised_reply_required");
      state.final = current.reply;

      return {
        source: "installed_mongo_and_telegram_desktop",
        ownerId: state.ownerId,
        conversationId: scenario.conversation.conversationId,
        turnRefHash: sha256(String(correctedContext.logical_turn_id || "")),
        initialTurnRefHash: sha256(String(initialContext.logical_turn_id || "")),
        correctedTurnRefHash: sha256(String(correctedContext.logical_turn_id || "")),
        initialRevision: Number(initialContext.revision),
        correctedRevision: Number(correctedContext.revision),
        sourceMessageIds: [state.ingress.get("first")?.messageId, state.ingress.get("revision")?.messageId],
        sourceSequences: current.users.map((message) => Number(interactionMetadata(message).source_sequence)),
        userBubbles: settled.bubbles
          .filter((bubble) => bubble.role === "user")
          .map((bubble) => ({ role: "user", messageId: bubble.messageId, text: bubble.text })),
        assistantBubbleCount: assistantBubbles.length,
        finalReplies: assistantBubbles
          .filter((bubble) => bubble.messageId === finalMessageId && bubble.text === current.reply.text)
          .map((bubble) => ({
            messageId: bubble.messageId,
            text: bubble.text,
            revision: Number(correctedContext.revision),
          })),
        staleReplyVisible: settled.bubbles.some((bubble) =>
          String(bubble.text || "").includes(scenario.source.staleReplyMarker),
        ),
        staleReplyRetracted:
          !settled.bubbles.some((bubble) => String(bubble.text || "").includes(scenario.source.staleReplyMarker)) &&
          state.captures.get("before_correction").bubbles.some((bubble) =>
            String(bubble.text || "").includes(scenario.source.staleReplyMarker),
          ),
        reopenedMatches: canonicalJson(settled.bubbles) === canonicalJson(reopenCapture.bubbles),
      };
    },

    async observePostCommitControl() {
      const prior = state.final;
      const acknowledgement = deliveryMetadata(prior);
      const committedAt = Number(acknowledgement.presentation_committed_at);
      if (!positiveSafeInteger(committedAt)) {
        throw blockedError("post_commit_normal_follow_up_unproven");
      }
      const controlIngress = state.ingress.get("postCommit");
      const followUp = await waitFor(async () => {
        const messages = await ownerMessages();
        return messages.find((message) => {
          const context = interactionMetadata(message);
          const receipt = deliveryMetadata(message);
          return (
            message.isCreatedByUser !== true &&
            context.revision === 1 &&
            receipt.state === "committed" &&
            context.logical_turn_id !== interactionMetadata(prior).logical_turn_id &&
            Number(context.source_sequence) === scenario.source.postCommit.messageId
          );
        });
      }, { timeoutMs: args.timeoutMs, blocker: "post_commit_normal_follow_up_unproven" });
      state.followUp = followUp;
      return {
        source: "installed_mongo_and_telegram_desktop",
        ownerId: state.ownerId,
        conversationId: scenario.conversation.conversationId,
        previousTurnRefHash: sha256(String(interactionMetadata(prior).logical_turn_id || "")),
        followUpTurnRefHash: sha256(String(interactionMetadata(followUp).logical_turn_id || "")),
        followUpRevision: Number(interactionMetadata(followUp).revision),
        previousCommittedAt: new Date(committedAt).toISOString(),
        sourceObservedAt: controlIngress?.observedAt,
        sourceMessageId: controlIngress?.messageId,
        sourceSequence: controlIngress?.sourceSequence,
      };
    },

    async expectedAuditEventDigest(scope) {
      const sessionScript = path.join(REPO_ROOT, "scripts", "viventium", "local_qa_runtime_control.py");
      const componentScript = path.join(
        REPO_ROOT,
        "viventium_v0_4",
        "telegram-viventium",
        "TelegramVivBot",
        "utils",
        "tr026_local_qa.py",
      );
      const probe = [
        "import importlib.util,json,sys",
        "from pathlib import Path",
        "spec=importlib.util.spec_from_file_location('tr026_audit_session_probe',sys.argv[1])",
        "session=importlib.util.module_from_spec(spec)",
        "sys.modules[spec.name]=session",
        "spec.loader.exec_module(session)",
        "component_spec=importlib.util.spec_from_file_location('tr026_audit_component_probe',sys.argv[2])",
        "component=importlib.util.module_from_spec(component_spec)",
        "sys.modules[component_spec.name]=component",
        "component_spec.loader.exec_module(component)",
        "state=session._read_state(Path(sys.argv[3]))",
        "scope=json.load(sys.stdin)",
        "event=component.SyntheticTelegramSourceEvent(update_id=scope['updateId'],chat_id=scope['chatId'],thread_id=scope['threadId'],source_sequence=scope['sourceSequence'],owner_user_id=scope['ownerUserId'])",
        "print(component._event_digest(event,component._token_digest(state['caseToken'])))",
      ].join(";");
      const measured = spawnSync(
        pythonExecutable(environment),
        ["-c", probe, sessionScript, componentScript, path.join(scenario.runtime.runtimeRoot, "local-qa", "active.json")],
        {
          encoding: "utf8",
          input: `${JSON.stringify(scope)}\n`,
          timeout: 15000,
          maxBuffer: 4096,
          env: { ...environment, PYTHONDONTWRITEBYTECODE: "1" },
        },
      );
      const digest = String(measured.stdout || "").trim();
      if (measured.status !== 0 || !SHA256.test(digest)) {
        throw blockedError("authenticated_telegram_source_event_digest_unavailable");
      }
      return digest;
    },

    async auditTelegramRace() {
      return invokeQaControl(scenario, "audit", { environment, timeoutMs: args.timeoutMs });
    },

    async verifyIndependentEvidence() {
      if (!state.observer) {
        throw blockedError("independent_installed_evidence_producer_unavailable");
      }
      const produced = await state.observer.produce();
      if (
        produced?.produced !== true ||
        produced.manifestName !== scenario.evidence.manifestName ||
        !SHA256.test(String(produced.manifestSha256 || ""))
      ) {
        throw blockedError("independent_semantic_verifier_evidence_unavailable");
      }
      const manifestPath = path.join(evidenceRoot, scenario.evidence.manifestName);
      const file = readPrivateFile(manifestPath, {
        root: evidenceRoot,
        label: "independent_manifest",
      });
      if (sha256(file.bytes) !== produced.manifestSha256) {
        throw blockedError("independent_semantic_verifier_evidence_unavailable");
      }
      let manifest;
      try {
        manifest = JSON.parse(file.bytes.toString("utf8"));
      } catch {
        throw blockedError("independent_semantic_verifier_evidence_unavailable");
      }
      const verified = spawnSync(
        pythonExecutable(environment),
        [VERIFIER, "--manifest", manifestPath, "--evidence-root", evidenceRoot],
        {
          encoding: "utf8",
          timeout: Math.min(args.timeoutMs, 30000),
          maxBuffer: 1024 * 1024,
          env: { ...environment, PYTHONDONTWRITEBYTECODE: "1" },
        },
      );
      if (verified.status !== 0) {
        throw blockedError("independent_semantic_verifier_evidence_unavailable");
      }
      try {
        return { ...JSON.parse(verified.stdout), manifest };
      } catch {
        throw blockedError("independent_semantic_verifier_evidence_unavailable");
      }
    },

    async cleanupTelegramRace() {
      return invokeQaControl(scenario, "cleanup", { environment, timeoutMs: args.timeoutMs });
    },

    async clearQaControl(sessionRef) {
      return invokeQaControl(scenario, "clear", {
        sessionRef,
        environment,
        timeoutMs: args.timeoutMs,
      });
    },

    async cleanupSyntheticTelegramConversation() {
      if (
        !state.database || !state.user || !positiveSafeInteger(state.launchedAt) ||
        state.ingressRecords.size < 1
      ) {
        throw blockedError("synthetic_telegram_cleanup_unverified");
      }
      const records = [...state.ingressRecords.values()];
      const sourceMessages = await state.database.collection("messages").find({
        user: state.ownerId,
        conversationId: scenario.conversation.conversationId,
        createdAt: { $gte: new Date(state.launchedAt) },
      }).limit(33).toArray();
      if (sourceMessages.length > 32) {
        throw blockedError("synthetic_telegram_cleanup_scope_invalid");
      }
      const sourceById = new Map(
        [...state.ingress.keys()].map((stage) => [scenario.source[stage].messageId, scenario.source[stage].text]),
      );
      const turnIds = new Set(
        [state.stale, state.final, state.followUp]
          .map((message) => String(interactionMetadata(message).logical_turn_id || "").trim())
          .filter(Boolean),
      );
      const messages = sourceMessages.filter((message) => {
        const context = interactionMetadata(message);
        if (message.isCreatedByUser === true) {
          return (
            sourceById.has(Number(context.source_sequence)) &&
            sourceById.get(Number(context.source_sequence)) === message.text
          );
        }
        return turnIds.has(String(context.logical_turn_id || ""));
      });
      if (messages.filter((message) => message.isCreatedByUser === true).length !== records.length) {
        throw blockedError("synthetic_telegram_cleanup_unverified");
      }
      const telegramMessageIds = [...new Set([
        ...records.map((record) => Number(record.telegramMessageId)),
        ...messages
          .filter((message) => message.isCreatedByUser !== true)
          .map((message) => telegramPresentationId(message, scenario))
          .filter((value) => positiveSafeInteger(value)),
      ])];
      return cleanupOwnerScopedSyntheticTelegramRecords({
        database: state.database,
        scenario,
        environment,
        owner: state.user,
        inventory: {
          ownerId: state.ownerId,
          conversationId: scenario.conversation.conversationId,
          startedAtMs: state.launchedAt,
          createdConversation: false,
          messages,
          ingress: records,
          conversations: [],
          telegramMessageIds,
        },
        async removeRemote(messageIds) {
          const removed = await performOwnerBoundComputerAction(desktopDriver, scenario, {
            action: "telegram.delete_synthetic_messages",
            messageIds,
          });
          if (
            removed.status !== "deleted" ||
            canonicalJson(removed.deletedMessageIds) !== canonicalJson(messageIds)
          ) {
            throw blockedError("synthetic_telegram_remote_cleanup_unverified");
          }
          return { deleted: true, messageIds };
        },
      });
    },

    async close() {
      if (state.observer) await state.observer.close();
      if (state.store) state.store.close();
      await mongo.close().catch(() => {});
    },
  };
}

function diagnosticResult(status, blocker = "") {
  return {
    caseId: CASE_ID,
    status,
    ...(blocker ? { blocker } : {}),
    releaseReady: false,
    receiptEligible: false,
  };
}

function requiredMethod(driver, name) {
  if (typeof driver?.[name] !== "function") {
    throw blockedError(
      name === "assertComputerDesktopProvenance"
        ? "computer_plugin_desktop_driver_unavailable"
        : "installed_journey_driver_capability_unavailable",
    );
  }
  return driver[name].bind(driver);
}

async function executeInstalledJourney({ driver, scenario, environment = process.env }) {
  const evidence = {};
  let session = null;
  let activated = false;
  let armed = false;
  let telegramTouched = false;
  let result;
  try {
    evidence.identity = await requiredMethod(driver, "preflightInstalledCandidate")();
    if (
      evidence.identity?.verified !== true ||
      !SHA256.test(String(evidence.identity.ownerRefHash || "")) ||
      !SHA256.test(String(evidence.identity.candidateDigest || "")) ||
      !SHA256.test(String(evidence.identity.artifactDigest || ""))
    ) {
      throw blockedError("installed_candidate_identity_unproven");
    }
    const desktop = await requiredMethod(driver, "assertComputerDesktopProvenance")();
    if (desktop?.provider !== "@oai/sky" || desktop.verified !== true) {
      throw blockedError("computer_plugin_desktop_driver_unavailable");
    }
    evidence.telegramIdentity = assertOwnerSafeTelegramIdentity(
      scenario,
      environment,
      await requiredMethod(driver, "probeTelegramIdentity")(),
    );
    await requiredMethod(driver, "requireIndependentEvidenceProducer")();
    evidence.workersBefore = await requiredMethod(driver, "observeWorkers")("before");

    session = await requiredMethod(driver, "activateQaControl")();
    if (session?.caseId !== CASE_ID || !SESSION_REF.test(String(session.sessionRef || ""))) {
      throw blockedError("exact_tr026_local_qa_session_unavailable");
    }
    activated = true;
    if ((await requiredMethod(driver, "restartRuntime")("activate"))?.restarted !== true) {
      throw blockedError("consented_installed_runtime_restart_unavailable");
    }
    evidence.restart = assertRestartReady(
      await requiredMethod(driver, "requireRestartReady")(),
      session,
    );

    telegramTouched = true;
    const firstSend = await requiredMethod(driver, "sendTelegramSegment")("first");
    if (firstSend?.sent !== true || firstSend.source !== "computer_plugin_sky") {
      throw blockedError("computer_plugin_telegram_user_ingress_unavailable");
    }
    evidence.first = bindTrustedIngress(
      scenario,
      await requiredMethod(driver, "observeTrustedIngress")("first"),
      "first",
    );
    evidence.scope = buildArmScope(scenario, evidence.first);
    evidence.arm = assertArmReceipt(
      await requiredMethod(driver, "armTelegramRace")(evidence.scope),
      session,
    );
    armed = true;

    const revisionSend = await requiredMethod(driver, "sendTelegramSegment")("revision");
    if (revisionSend?.sent !== true || revisionSend.source !== "computer_plugin_sky") {
      throw blockedError("computer_plugin_telegram_user_ingress_unavailable");
    }
    evidence.revision = bindTrustedIngress(
      scenario,
      await requiredMethod(driver, "observeTrustedIngress")("revision"),
      "revision",
    );
    evidence.rapidObservation = await requiredMethod(driver, "observeRapidRevision")(
      evidence.first,
      evidence.revision,
    );
    evidence.rapid = assessRapidRevision({
      scenario,
      first: evidence.first,
      revision: evidence.revision,
      observation: evidence.rapidObservation,
    });

    const postCommitSend = await requiredMethod(driver, "sendTelegramSegment")("postCommit");
    if (postCommitSend?.sent !== true || postCommitSend.source !== "computer_plugin_sky") {
      throw blockedError("computer_plugin_telegram_user_ingress_unavailable");
    }
    evidence.postCommitIngress = bindTrustedIngress(
      scenario,
      await requiredMethod(driver, "observeTrustedIngress")("postCommit"),
      "postCommit",
    );
    evidence.postCommit = assessPostCommitControl(
      scenario,
      await requiredMethod(driver, "observePostCommitControl")(evidence.postCommitIngress),
      evidence.rapid.turnRefHash,
    );

    const eventDigest = await requiredMethod(driver, "expectedAuditEventDigest")(evidence.scope);
    evidence.audit = assessAuthenticatedAudit(
      await requiredMethod(driver, "auditTelegramRace")(),
      evidence.arm,
      evidence.scope,
      eventDigest,
    );
    evidence.workersAfter = await requiredMethod(driver, "observeWorkers")("after");
    evidence.workers = assessWorkersUnaffected(evidence.workersBefore, evidence.workersAfter, scenario);
    evidence.verifier = assessIndependentVerifier(
      await requiredMethod(driver, "verifyIndependentEvidence")(),
      evidence.identity,
      session.sessionRef,
      evidence.rapid.turnRefHash,
    );
    // The independent verifier separately requires normal and reversed source admission,
    // including the exact typed source_order_superseded lower-sequence outcome.
    result = { ...diagnosticResult("PASS"), evidence };
  } catch (error) {
    result = {
      ...diagnosticResult(
        "BLOCKED",
        error?.blocked ? error.message : "installed_journey_execution_failed",
      ),
      evidence,
    };
  } finally {
    let cleanupFailure = false;
    let syntheticCleanupFailure = false;
    if (telegramTouched) {
      try {
        const cleanup = await requiredMethod(driver, "cleanupSyntheticTelegramConversation")();
        if (
          cleanup?.cleaned !== true ||
          cleanup.ownerId !== scenario.owner.ownerId ||
          cleanup.conversationId !== scenario.conversation.conversationId
        ) {
          syntheticCleanupFailure = true;
        } else {
          evidence.syntheticCleanup = cleanup;
        }
      } catch {
        syntheticCleanupFailure = true;
      }
    }
    if (armed) {
      try {
        const cleanup = await requiredMethod(driver, "cleanupTelegramRace")();
        if (cleanup?.cleaned !== true || cleanup.sessionRef !== session.sessionRef) {
          cleanupFailure = true;
        }
      } catch {
        cleanupFailure = true;
      }
    }
    if (activated && session?.sessionRef) {
      let cleared = false;
      try {
        const clear = await requiredMethod(driver, "clearQaControl")(session.sessionRef);
        if (clear?.cleared === true && clear.sessionRef === session.sessionRef) {
          cleared = true;
        } else {
          cleanupFailure = true;
        }
      } catch {
        cleanupFailure = true;
      }
      if (cleared) {
        try {
          if ((await requiredMethod(driver, "restartRuntime")("cleanup"))?.restarted !== true) {
            cleanupFailure = true;
          }
        } catch {
          cleanupFailure = true;
        }
      }
    }
    try {
      if (typeof driver?.close === "function") await driver.close();
    } catch {
      cleanupFailure = true;
    }
    if (cleanupFailure || syntheticCleanupFailure) {
      result = {
        ...diagnosticResult(
          "BLOCKED",
          syntheticCleanupFailure
            ? "synthetic_telegram_cleanup_unverified"
            : "installed_qa_control_cleanup_unavailable",
        ),
        evidence,
      };
    }
  }
  return result;
}

function redactPrivateEvidence(value, key = "") {
  if (Array.isArray(value)) return value.map((item) => redactPrivateEvidence(item, key));
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([name, item]) => [name, redactPrivateEvidence(item, name)]),
    );
  }
  if (
    typeof value === "string" &&
    /token|secret|password|email|ownerid|userid|chatid|conversation|path|root|text|label|messageid|updateid|sessionref|artifactref|workerref|runref|workref/i.test(key)
  ) {
    return { sha256: sha256(value) };
  }
  if (
    typeof value === "number" &&
    /owner|user|chat|conversation|message|update|sourceSequence|staleSourceSequence/i.test(key)
  ) {
    return { sha256: sha256(String(value)) };
  }
  return value;
}

function safeBlocker(value) {
  const candidate = String(value || "");
  return /^[a-z][a-z0-9_]{0,119}$/.test(candidate)
    ? candidate
    : "installed_journey_execution_failed";
}

function buildPublicSummary({ result, qaRunId }) {
  const evidence = result?.evidence || {};
  const status = result?.status === "PASS" ? "PASS" : "BLOCKED";
  return {
    ...diagnosticResult(status, status === "BLOCKED" ? safeBlocker(result?.blocker) : ""),
    qaRunRefHash: sha256(String(qaRunId || CASE_ID)),
    candidateDigest: SHA256.test(String(evidence.identity?.candidateDigest || ""))
      ? evidence.identity.candidateDigest
      : null,
    artifactDigest: SHA256.test(String(evidence.identity?.artifactDigest || ""))
      ? evidence.identity.artifactDigest
      : null,
    revisedReplyCount: evidence.rapid?.finalReplyCount === 1 ? 1 : 0,
    unaffectedWorkerCount: evidence.workers?.workerCount === 2 ? 2 : 0,
    authenticatedDelayMs: evidence.audit?.delayMs === DELAY_MS ? DELAY_MS : null,
    computerPluginVerified: evidence.telegramIdentity?.source === "computer_plugin_sky",
  };
}

async function main(argv = process.argv.slice(2), environment = process.env, options = {}) {
  let args;
  try {
    args = parseArgs(argv);
    if (args.dryRun) return dryRunPlan(args);
    assertExecutionConsents(args, environment);
    const evidenceRoot = assertPrivateEvidenceRoot(args.evidenceRoot);
    const scenario = validateScenario(readPrivateScenario(args.scenarioPath, evidenceRoot), environment);
    assertExecutionConsents(args, environment, scenario.restart);

    if (
      options.desktopDriver &&
      (options.computerAuthority?.unitTestHarness ||
        options.computerAuthority?.transport?.unitTestHarness)
    ) {
      throw blockedError("computer_desktop_test_authority_forbidden");
    }
    if (options.desktopDriver && options.computerAuthority) {
      await authenticateParentComputerAuthority(options.computerAuthority);
    }
    const desktopDriver = assertComputerDesktopDriver(options.desktopDriver, scenario, undefined, {
      authority: options.computerAuthority,
      environment,
    });
    const driver = await createInstalledDriver({
      scenario,
      args,
      environment,
      evidenceRoot,
      desktopDriver,
    });
    const result = await executeInstalledJourney({ driver, scenario, environment });
    writePrivateEvidence(
      evidenceRoot,
      `${args.qaRunId}-installed-journey.json`,
      redactPrivateEvidence({ caseId: CASE_ID, status: result.status, blocker: result.blocker, evidence: result.evidence }),
    );
    return buildPublicSummary({ result, qaRunId: args.qaRunId });
  } catch (error) {
    return buildPublicSummary({
      result: diagnosticResult(
        "BLOCKED",
        error?.blocked ? error.message : "installed_journey_execution_failed",
      ),
      qaRunId: args?.qaRunId || CASE_ID,
    });
  }
}

if (require.main === module && process.argv[2] === "--independent-observer") {
  if (process.argv.length !== 3 || !process.connected || typeof process.send !== "function") {
    process.exitCode = 2;
  } else {
    startIndependentObserverChild();
  }
} else if (require.main === module) {
  main()
    .then((result) => {
      process.stdout.write(`${JSON.stringify(result)}\n`);
      if (!["DRY_RUN", "PASS"].includes(result.status)) process.exitCode = 2;
    })
    .catch(() => {
      process.stdout.write(
        `${JSON.stringify(diagnosticResult("BLOCKED", "installed_journey_execution_failed"))}\n`,
      );
      process.exitCode = 2;
    });
}

module.exports = {
  REQUIRED_VERIFIER_GATES,
  parseArgs,
  dryRunPlan,
  assertExecutionConsents,
  assertPrivateEvidenceRoot,
  readPrivateScenario,
  writePrivateEvidence,
  validateScenario,
  assertComputerDesktopDriver,
  assertComputerAction,
  readOwnerBoundComputerState,
  performOwnerBoundComputerAction,
  assertOwnerScopedTelegramChatBinding,
  assertIndependentObserverReady,
  startIndependentEvidenceObserver,
  assertOwnerSafeTelegramIdentity,
  cleanupOwnerScopedSyntheticTelegramRecords,
  bindTrustedIngress,
  buildArmScope,
  assertArmReceipt,
  assessAuthenticatedAudit,
  assessRapidRevision,
  assessPostCommitControl,
  assessWorkersUnaffected,
  assessIndependentVerifier,
  openReadOnlyGlassHiveStore,
  createInstalledDriver,
  executeInstalledJourney,
  redactPrivateEvidence,
  buildPublicSummary,
  blockedError,
  main,
};
