#!/usr/bin/env node
"use strict";

/*
 * Explicitly consented, installed TGDOC-010 trigger. This is diagnostic-only:
 * worker_bee_file_parity_qa.py remains the independent acceptance verifier.
 */

const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const REPO_ROOT = path.resolve(__dirname, "../../..");
const LIBRECHAT_ROOT = path.join(REPO_ROOT, "viventium_v0_4", "LibreChat");
const {
  assertEphemeralSessionSafety,
  assertSelectedQaAccount,
  createEphemeralBrowserSession,
} = require(path.join(
  REPO_ROOT,
  "qa",
  "parallel-orchestrator",
  "scripts",
  "run_installed_parallel_work_journey.cjs",
));
const CASE_ID = "TGDOC-010";
const RELEASE_LABEL = "PRE-GATE / NOT READY";
const REQUIRED_FAMILIES = new Set(["document", "image", "audio", "video", "prior_artifact"]);
const REQUIRED_RESTART_SERVICES = Object.freeze(["core", "glasshive", "telegram", "worker"]);
const SHA256 = /^[a-f0-9]{64}$/;
const SAFE_NAME = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/;
const MAX_PRIVATE_FILE_BYTES = 32 * 1024 * 1024;
const SKY_ACTION_METHODS = Object.freeze([
  "click",
  "drag",
  "paste",
  "perform_secondary_action",
  "press_key",
  "scroll",
  "select_text",
  "set_value",
  "type_text",
]);
const SKY_ACTION_METHOD_SET = new Set(SKY_ACTION_METHODS);
const AUTHENTICATED_PARENT_COMPUTER_AUTHORITIES = new WeakMap();
const VERIFIED_COMPUTER_ADAPTERS = new WeakSet();
const COMPUTER_AUTHORITY_CHALLENGE = "viventium.computer.authority.challenge.v1";
const COMPUTER_AUTHORITY_RESPONSE = "viventium.computer.authority.response.v1";
const VERIFIED_COMPUTER_APPLICATIONS = new Map();
const MAX_COMPUTER_APPLICATION_ANCESTRY = 12;

function blockedError(code) {
  const error = new Error(String(code || "installed_journey_prerequisite_unavailable"));
  error.name = "InstalledTelegramDocumentJourneyBlockedError";
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
  const result = {
    dryRun: false,
    localQa: false,
    allowTelegramMutation: false,
    allowRuntimeRestart: false,
    evidenceRoot: "",
    scenarioPath: "",
    timeoutMs: 180000,
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
    const raw = String(argv[index]);
    const equals = raw.indexOf("=");
    const key = equals === -1 ? raw : raw.slice(0, equals);
    if (seen.has(key)) throw blockedError("duplicate_argument");
    seen.add(key);
    if (flags.has(key)) {
      if (equals !== -1) throw blockedError("invalid_flag_value");
      result[flags.get(key)] = true;
      continue;
    }
    if (!options.has(key)) throw blockedError("unknown_argument");
    const value = equals === -1 ? argv[++index] : raw.slice(equals + 1);
    if (!String(value || "").trim()) throw blockedError("missing_argument_value");
    result[options.get(key)] = value;
  }
  if (result.dryRun && (result.localQa || result.allowTelegramMutation || result.allowRuntimeRestart || result.evidenceRoot || result.scenarioPath)) {
    throw blockedError("dry_run_rejects_live_arguments");
  }
  result.timeoutMs = Number(result.timeoutMs);
  if (!Number.isSafeInteger(result.timeoutMs) || result.timeoutMs < 1000 || result.timeoutMs > 600000) {
    throw blockedError("journey_timeout_invalid");
  }
  return result;
}

function dryRunPlan(args) {
  if (!args?.dryRun) throw blockedError("dry_run_required");
  return {
    caseId: CASE_ID,
    status: "DRY_RUN",
    sideEffects: false,
    launchesBrowser: false,
    accessesDatabase: false,
    sendsTelegramMessages: false,
    restartsRuntime: false,
    releaseReady: false,
    receiptEligible: false,
    releaseLabel: RELEASE_LABEL,
    requiredFamilies: [...REQUIRED_FAMILIES],
  };
}

function assertLocalDiagnosticOptIn(args, environment) {
  if (args?.localQa !== true) throw blockedError("local_qa_opt_in_required");
  if (environment?.VIVENTIUM_QA_ALLOW_TGDOC_010_DIAGNOSTIC !== "1") {
    throw blockedError("diagnostic_opt_in_required");
  }
  if (environment.CI || environment.NODE_ENV === "production") {
    throw blockedError("local_diagnostic_only");
  }
}

function assertTelegramMutationConsent(args, environment) {
  if (
    args?.allowTelegramMutation !== true ||
    environment?.VIVENTIUM_QA_ALLOW_TGDOC_010_TELEGRAM_MUTATION !== "1"
  ) {
    throw blockedError("telegram_mutation_consent_required");
  }
}

function assertRestartConsent(args, environment, restart) {
  if (restart?.supported !== true) throw blockedError("runtime_restart_unsupported");
  if (
    args?.allowRuntimeRestart !== true ||
    environment?.VIVENTIUM_QA_ALLOW_TGDOC_010_RESTART !== "1"
  ) {
    throw blockedError("runtime_restart_consent_required");
  }
}

function ephemeralBrowserSessionArgs(scenario, args) {
  return {
    qaEmail: String(scenario?.owner?.email || "").trim().toLowerCase(),
    clientBase: String(scenario?.runtime?.clientUrl || "").trim(),
    apiBase: String(scenario?.runtime?.apiUrl || "").trim(),
    timeoutMs: args?.timeoutMs,
  };
}

function assertTrustedEphemeralSessionConfiguration(scenario, installed, requested = {}) {
  const configured = String(installed?.VIVENTIUM_QA_EMAIL || "").trim().toLowerCase();
  if (!configured || configured !== String(scenario?.owner?.email || "").trim().toLowerCase()) {
    throw blockedError("configured_synthetic_qa_account_mismatch");
  }
  const trusted = { VIVENTIUM_QA_EMAIL: configured };
  for (const name of ["JWT_SECRET", "JWT_REFRESH_SECRET"]) {
    const actual = String(installed?.[name] || "").trim();
    if (!actual) throw blockedError("ephemeral_browser_session_signing_secrets_required");
    const supplied = String(requested?.[name] || "").trim();
    if (supplied && supplied !== actual) {
      throw blockedError("untrusted_runtime_signing_secret_refused");
    }
    trusted[name] = actual;
  }
  const suppliedQaEmail = String(requested?.VIVENTIUM_QA_EMAIL || "").trim().toLowerCase();
  if (suppliedQaEmail && suppliedQaEmail !== configured) {
    throw blockedError("configured_synthetic_qa_account_mismatch");
  }
  return trusted;
}

/**
 * @typedef {Object} AuthenticatedComputerDesktopDriver
 * @property {Object} provenance Exact short-lived, owner-bound Computer-plugin attestation.
 * @property {(request: Object) => Promise<Object>} get_app_state Parent Computer Sky observation.
 * @property {(request: Object) => Promise<Object>} do_action Parent-owned logical dispatcher
 *   that calls only a real sky.click/press_key/type_text/paste/etc. primitive.
 */

function inspectedProcessIdentity(processId) {
  if (!Number.isSafeInteger(processId) || processId <= 1) {
    throw blockedError("computer_desktop_external_authority_required");
  }
  const measured = spawnSync(
    "/bin/ps",
    ["-p", String(processId), "-o", "uid=", "-o", "ppid=", "-o", "lstart=", "-o", "args="],
    {
      encoding: "utf8",
      timeout: 3000,
      maxBuffer: 32768,
      env: { PATH: "/usr/bin:/bin", LC_ALL: "C" },
    },
  );
  const matched = /^\s*(\d+)\s+(\d+)\s+((?:Sun|Mon|Tue|Wed|Thu|Fri|Sat)\s+[A-Za-z]{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+\d{4})\s+(.+?)\s*$/.exec(
    String(measured.stdout || ""),
  );
  if (measured.status !== 0 || !matched) {
    throw blockedError("computer_desktop_external_authority_required");
  }
  const executable = spawnSync("/bin/ps", ["-p", String(processId), "-o", "comm="], {
    encoding: "utf8",
    timeout: 3000,
    maxBuffer: 32768,
    env: { PATH: "/usr/bin:/bin", LC_ALL: "C" },
  });
  const commandPath = String(executable.stdout || "").trim();
  if (executable.status !== 0 || !commandPath || commandPath.includes("\n")) {
    throw blockedError("computer_desktop_external_authority_required");
  }
  return {
    processId,
    userId: Number(matched[1]),
    parentProcessId: Number(matched[2]),
    startedAt: matched[3],
    command: matched[4],
    executable: commandPath,
  };
}

function parentProcessIdentity() {
  const parent = inspectedProcessIdentity(process.ppid);
  if (
    parent.processId === process.pid ||
    parent.userId !== process.getuid() ||
    !parent.command
  ) {
    throw blockedError("computer_desktop_external_authority_required");
  }
  return parent;
}

function exactNodeTestHarness(authority, parent) {
  const harness = authority?.unitTestHarness;
  if (!harness) return false;
  try {
    const current = inspectedProcessIdentity(process.pid);
    const entry = fs.realpathSync(String(process.argv[1] || ""));
    const declared = fs.realpathSync(String(harness.testFile || ""));
    return (
      harness.kind === "node_test_only" &&
      harness.processId === process.pid &&
      harness.parentProcessId === process.ppid &&
      current.userId === process.getuid() &&
      current.parentProcessId === process.ppid &&
      parent.userId === process.getuid() &&
      entry === declared &&
      pathInside(entry, fs.realpathSync(REPO_ROOT)) &&
      /\.test\.cjs$/.test(entry) &&
      current.command.includes(path.basename(entry)) &&
      /(?:^|\s)--test(?:\s|=|$)/.test(parent.command)
    );
  } catch {
    return false;
  }
}

function exactParentNodeTestHarness(harness, parent, grandparent) {
  if (!harness) return false;
  try {
    const declared = fs.realpathSync(String(harness.testFile || ""));
    return (
      harness.kind === "node_test_only_parent_transport" &&
      harness.parentProcessId === process.ppid &&
      harness.grandparentProcessId === parent.parentProcessId &&
      parent.userId === process.getuid() &&
      grandparent.userId === process.getuid() &&
      grandparent.processId === parent.parentProcessId &&
      pathInside(declared, fs.realpathSync(REPO_ROOT)) &&
      /\.test\.cjs$/.test(declared) &&
      parent.command.includes(path.basename(declared)) &&
      /(?:^|\s)--test(?:\s|=|$)/.test(grandparent.command)
    );
  } catch {
    return false;
  }
}

function assertCanonicalComputerExecutable(bundle, executable) {
  if (
    !path.isAbsolute(executable) ||
    !pathInside(executable, bundle) ||
    fs.realpathSync(executable) !== executable ||
    !fs.statSync(executable).isFile()
  ) {
    throw blockedError("computer_desktop_control_plane_untrusted");
  }
  let current = bundle;
  for (const part of path.relative(bundle, executable).split(path.sep)) {
    current = path.join(current, part);
    if (fs.lstatSync(current).isSymbolicLink()) {
      throw blockedError("computer_desktop_control_plane_untrusted");
    }
  }
}

function assertComputerBundleIdentity(executable) {
  try {
    if (!path.isAbsolute(executable)) {
      throw blockedError("computer_desktop_control_plane_untrusted");
    }
    let bundle = path.dirname(executable);
    while (path.extname(bundle) !== ".app" && path.dirname(bundle) !== bundle) {
      bundle = path.dirname(bundle);
    }
    if (
      path.extname(bundle) !== ".app" ||
      fs.lstatSync(bundle).isSymbolicLink() ||
      fs.realpathSync(bundle) !== bundle
    ) {
      throw blockedError("computer_desktop_control_plane_untrusted");
    }
    assertCanonicalComputerExecutable(bundle, executable);
    const metadata = fs.statSync(bundle);
    const identity = `${bundle}:${metadata.dev}:${metadata.ino}:${metadata.mtimeMs}`;
    let application = VERIFIED_COMPUTER_APPLICATIONS.get(identity);
    if (!application) {
      const signed = spawnSync("/usr/bin/codesign", ["--verify", "--strict", bundle], {
        encoding: "utf8",
        timeout: 15000,
        maxBuffer: 32768,
        env: { PATH: "/usr/bin:/bin", LC_ALL: "C" },
      });
      if (signed.status !== 0) {
        throw blockedError("computer_desktop_control_plane_untrusted");
      }
      const assessed = spawnSync("/usr/sbin/spctl", ["--assess", "--type", "execute", bundle], {
        encoding: "utf8",
        timeout: 20000,
        maxBuffer: 32768,
        env: { PATH: "/usr/bin:/bin", LC_ALL: "C" },
      });
      if (assessed.status !== 0) {
        throw blockedError("computer_desktop_control_plane_untrusted");
      }
      const signature = spawnSync("/usr/bin/codesign", ["--display", "--verbose=2", bundle], {
        encoding: "utf8",
        timeout: 5000,
        maxBuffer: 32768,
        env: { PATH: "/usr/bin:/bin", LC_ALL: "C" },
      });
      const signatureDetails = `${signature.stdout || ""}\n${signature.stderr || ""}`;
      const identifier = /(?:^|\n)Identifier=([^\n]+)(?:\n|$)/.exec(signatureDetails)?.[1];
      const team = /(?:^|\n)TeamIdentifier=([^\n]+)(?:\n|$)/.exec(signatureDetails)?.[1];
      if (
        signature.status !== 0 ||
        !/^[A-Za-z0-9][A-Za-z0-9.-]{1,254}$/.test(String(identifier || "")) ||
        !/^[A-Z0-9]{10}$/.test(String(team || ""))
      ) {
        throw blockedError("computer_desktop_control_plane_untrusted");
      }
      const plist = path.join(bundle, "Contents", "Info.plist");
      const declaredExecutable = spawnSync(
        "/usr/libexec/PlistBuddy",
        ["-c", "Print :CFBundleExecutable", plist],
        {
          encoding: "utf8",
          timeout: 3000,
          maxBuffer: 4096,
          env: { PATH: "/usr/bin:/bin", LC_ALL: "C" },
        },
      );
      const executableName = String(declaredExecutable.stdout || "").trim();
      if (
        declaredExecutable.status !== 0 ||
        !executableName ||
        executableName.includes("\n") ||
        path.basename(executableName) !== executableName
      ) {
        throw blockedError("computer_desktop_control_plane_untrusted");
      }
      const applicationExecutable = path.join(bundle, "Contents", "MacOS", executableName);
      assertCanonicalComputerExecutable(bundle, applicationExecutable);
      application = Object.freeze({
        bundle,
        identifier,
        team,
        applicationExecutable,
      });
      VERIFIED_COMPUTER_APPLICATIONS.set(identity, application);
    }
    return application;
  } catch (error) {
    if (error?.blocked) throw error;
    throw blockedError("computer_desktop_control_plane_untrusted");
  }
}

function assertComputerControlPlane(parent, transport) {
  let grandparent;
  try {
    grandparent = inspectedProcessIdentity(parent.parentProcessId);
  } catch {
    throw blockedError("computer_desktop_control_plane_untrusted");
  }
  if (
    parent.processId !== process.ppid ||
    parent.userId !== process.getuid() ||
    grandparent.userId !== process.getuid() ||
    grandparent.processId !== parent.parentProcessId
  ) {
    throw blockedError("computer_desktop_control_plane_untrusted");
  }
  if (exactParentNodeTestHarness(transport?.unitTestHarness, parent, grandparent)) {
    return { parent, grandparent, unitTestOnly: true };
  }
  const application = assertComputerBundleIdentity(parent.executable);
  const ancestry = [parent];
  let ancestor = grandparent;
  for (let depth = 0; depth < MAX_COMPUTER_APPLICATION_ANCESTRY; depth += 1) {
    const child = ancestry.at(-1);
    if (
      ancestor.processId !== child.parentProcessId ||
      ancestor.userId !== process.getuid()
    ) {
      throw blockedError("computer_desktop_control_plane_untrusted");
    }
    assertCanonicalComputerExecutable(application.bundle, ancestor.executable);
    ancestry.push(ancestor);
    if (ancestor.executable === application.applicationExecutable) {
      return {
        bundle: application.bundle,
        bundleIdentifier: application.identifier,
        signingTeam: application.team,
        ancestry,
        unitTestOnly: false,
      };
    }
    if (ancestor.parentProcessId <= 1) break;
    try {
      ancestor = inspectedProcessIdentity(ancestor.parentProcessId);
    } catch {
      throw blockedError("computer_desktop_control_plane_untrusted");
    }
  }
  throw blockedError("computer_desktop_control_plane_untrusted");
}

function validateExternalComputerAuthorityShape(authority) {
  if (
    !authority ||
    typeof authority !== "object" ||
    !(authority.publicKey instanceof crypto.KeyObject) ||
    authority.publicKey.type !== "public" ||
    authority.publicKey.asymmetricKeyType !== "ed25519" ||
    !Number.isSafeInteger(authority.peerProcessId) ||
    authority.peerProcessId <= 1 ||
    authority.peerProcessId === process.pid ||
    authority.peerProcessId !== process.ppid ||
    !/^sky_[A-Za-z0-9_-]{8,64}$/.test(String(authority.sessionRef || "")) ||
    authority.keyId !== sha256(authority.publicKey.export({ type: "spki", format: "der" }))
  ) {
    throw blockedError("computer_desktop_external_authority_required");
  }
}

function assertExternalComputerAuthority(authority, options = {}) {
  if (options.processProbe !== undefined) {
    throw blockedError("computer_desktop_process_probe_override_forbidden");
  }
  validateExternalComputerAuthorityShape(authority);
  const parent = parentProcessIdentity();
  const grant = AUTHENTICATED_PARENT_COMPUTER_AUTHORITIES.get(authority);
  if (grant) {
    const controlPlane = assertComputerControlPlane(parent, authority.transport);
    const parentIdentityDigest = sha256(canonicalJson(controlPlane));
    if (
      grant.keyId === authority.keyId &&
      grant.sessionRef === authority.sessionRef &&
      grant.peerProcessId === process.ppid &&
      grant.parentIdentityDigest === parentIdentityDigest &&
      Number.isSafeInteger(grant.expiresAtMs) &&
      grant.expiresAtMs > Date.now()
    ) {
      return authority;
    }
  }
  if (exactNodeTestHarness(authority, parent)) return authority;
  throw blockedError("computer_desktop_parent_transport_unavailable");
}

async function authenticateParentComputerAuthority(authority, { timeoutMs = 3000, ...unsupported } = {}) {
  if (Object.hasOwn(unsupported, "processProbe")) {
    throw blockedError("computer_desktop_process_probe_override_forbidden");
  }
  validateExternalComputerAuthorityShape(authority);
  const parent = parentProcessIdentity();
  const transport = authority.transport;
  if (
    !Number.isSafeInteger(timeoutMs) || timeoutMs < 100 || timeoutMs > 10000 ||
    !transport ||
    transport.kind !== "inherited_parent_ipc" ||
    transport.controlPlane !== "computer_plugin_node_repl" ||
    transport.parentProcessId !== process.ppid ||
    transport.channel !== process.channel ||
    !process.channel || process.connected !== true || typeof process.send !== "function"
  ) {
    throw blockedError("computer_desktop_parent_transport_unavailable");
  }
  const controlPlane = assertComputerControlPlane(parent, transport);
  const parentIdentityDigest = sha256(canonicalJson(controlPlane));
  const challenge = crypto.randomBytes(32).toString("hex");
  const request = {
    type: COMPUTER_AUTHORITY_CHALLENGE,
    contractVersion: 1,
    controlPlane: "computer_plugin_node_repl",
    challenge,
    runnerProcessId: process.pid,
    parentProcessId: process.ppid,
    parentIdentityDigest,
    authorityKeyId: authority.keyId,
    sessionRef: authority.sessionRef,
  };
  const response = await new Promise((resolve, reject) => {
    let settled = false;
    const finish = (error, value) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      process.off("message", receive);
      if (error) reject(error);
      else resolve(value);
    };
    const receive = (message) => {
      if (message?.type !== COMPUTER_AUTHORITY_RESPONSE || message.challenge !== challenge) return;
      finish(null, message);
    };
    const timer = setTimeout(() => {
      finish(blockedError("computer_desktop_parent_transport_unavailable"));
    }, timeoutMs);
    process.on("message", receive);
    try {
      process.send(request, (error) => {
        if (error) finish(blockedError("computer_desktop_parent_transport_unavailable"));
      });
    } catch {
      finish(blockedError("computer_desktop_parent_transport_unavailable"));
    }
  });
  const now = Date.now();
  const { proof, ...unsigned } = response;
  if (
    response.contractVersion !== 1 ||
    response.controlPlane !== "computer_plugin_node_repl" ||
    response.runnerProcessId !== process.pid ||
    response.parentProcessId !== process.ppid ||
    response.parentIdentityDigest !== parentIdentityDigest ||
    response.authorityKeyId !== authority.keyId ||
    response.sessionRef !== authority.sessionRef ||
    !Number.isSafeInteger(response.issuedAtMs) ||
    !Number.isSafeInteger(response.expiresAtMs) ||
    response.issuedAtMs > now + 1000 ||
    response.expiresAtMs <= now ||
    response.expiresAtMs - response.issuedAtMs > 900000 ||
    !verifyExternalComputerProof(authority.publicKey, unsigned, proof)
  ) {
    throw blockedError("computer_desktop_parent_authority_authentication_failed");
  }
  AUTHENTICATED_PARENT_COMPUTER_AUTHORITIES.set(authority, Object.freeze({
    keyId: authority.keyId,
    sessionRef: authority.sessionRef,
    peerProcessId: process.ppid,
    parentIdentityDigest,
    expiresAtMs: response.expiresAtMs,
  }));
  return authority;
}

function verifyExternalComputerProof(publicKey, payload, proof) {
  if (
    !(publicKey instanceof crypto.KeyObject) ||
    publicKey.type !== "public" ||
    publicKey.asymmetricKeyType !== "ed25519" ||
    !payload ||
    typeof payload !== "object" ||
    Array.isArray(payload) ||
    !/^ed25519:[A-Za-z0-9_-]{86}$/.test(String(proof || ""))
  ) {
    return false;
  }
  try {
    const signature = Buffer.from(String(proof).slice("ed25519:".length), "base64url");
    return signature.length === 64 && crypto.verify(
      null,
      Buffer.from(canonicalJson(payload), "utf8"),
      publicKey,
      signature,
    );
  } catch {
    return false;
  }
}

function assertAuthenticatedComputerDesktopDriver(
  driver,
  scenario,
  environment,
  { authority, nowMs = Date.now(), processProbe } = {},
) {
  if (!driver || typeof driver !== "object") throw blockedError("computer_desktop_driver_unavailable");
  if (
    scenario?.caseId === CASE_ID &&
    environment?.VIVENTIUM_QA_ALLOW_TGDOC_010_COMPUTER_BRIDGE !== "1"
  ) {
    throw blockedError("computer_desktop_bridge_opt_in_required");
  }
  const externalAuthority = assertExternalComputerAuthority(authority, { processProbe });
  if (typeof driver.get_app_state !== "function" || typeof driver.do_action !== "function") {
    throw blockedError("computer_desktop_driver_unavailable");
  }
  const provenance = driver.provenance;
  if (
    !provenance ||
    provenance.contractVersion !== 1 ||
    provenance.caseId !== scenario?.caseId ||
    provenance.provider !== "@oai/sky" ||
    provenance.controlPlane !== "computer_plugin_node_repl" ||
    provenance.interface !== "sky.get_app_state/sky-primitives" ||
    !Array.isArray(provenance.skyMethods) ||
    provenance.skyMethods.length < 1 ||
    provenance.skyMethods.some((method) => !SKY_ACTION_METHOD_SET.has(method)) ||
    new Set(provenance.skyMethods).size !== provenance.skyMethods.length ||
    !/^sky_[A-Za-z0-9_-]{8,64}$/.test(String(provenance.sessionRef || ""))
  ) {
    throw blockedError("computer_desktop_driver_provenance_invalid");
  }
  if (
    provenance.ownerId !== scenario?.owner?.ownerId ||
    provenance.telegramUserId !== scenario.owner.telegramUserId ||
    provenance.telegramChatId !== scenario.owner.telegramChatId ||
    provenance.appBundleId !== scenario?.telegram?.bundleId
  ) {
    throw blockedError("computer_desktop_driver_owner_mismatch");
  }
  if (
    provenance.sessionRef !== externalAuthority.sessionRef ||
    provenance.peerProcessId !== externalAuthority.peerProcessId ||
    provenance.authorityKeyId !== externalAuthority.keyId
  ) {
    throw blockedError("computer_desktop_driver_peer_mismatch");
  }
  if (
    !Number.isSafeInteger(provenance.issuedAtMs) ||
    !Number.isSafeInteger(provenance.expiresAtMs) ||
    provenance.issuedAtMs > nowMs ||
    provenance.expiresAtMs <= nowMs ||
    provenance.expiresAtMs - provenance.issuedAtMs > 900000
  ) {
    throw blockedError("computer_desktop_driver_attestation_expired");
  }
  const { proof, ...unsigned } = provenance;
  if (!verifyExternalComputerProof(externalAuthority.publicKey, unsigned, proof)) {
    throw blockedError("computer_desktop_driver_authentication_failed");
  }
  const consumedChallenges = new Set();
  const adapter = Object.freeze({
    driver,
    provenance: Object.freeze({ ...unsigned }),
    authority: Object.freeze({
      publicKey: externalAuthority.publicKey,
      keyId: externalAuthority.keyId,
      peerProcessId: externalAuthority.peerProcessId,
      sessionRef: externalAuthority.sessionRef,
    }),
    binding: Object.freeze({
      caseId: scenario.caseId,
      ownerId: scenario.owner.ownerId,
      telegramUserId: String(scenario.owner.telegramUserId),
      telegramChatId: String(scenario.owner.telegramChatId),
      appBundleId: scenario.telegram.bundleId,
      accountLabel: scenario.telegram.accountLabel,
      chatLabel: scenario.telegram.chatLabel,
      ...(scenario.conversation?.conversationId
        ? { conversationId: scenario.conversation.conversationId }
        : {}),
    }),
    verify(payload, signed) {
      return verifyExternalComputerProof(externalAuthority.publicKey, payload, signed);
    },
    assertParentBoundary() {
      assertExternalComputerAuthority(externalAuthority);
    },
    consumeChallenge(challenge) {
      if (consumedChallenges.has(challenge)) {
        throw blockedError("computer_desktop_observation_replayed");
      }
      consumedChallenges.add(challenge);
      if (consumedChallenges.size > 512) {
        consumedChallenges.delete(consumedChallenges.values().next().value);
      }
    },
  });
  VERIFIED_COMPUTER_ADAPTERS.add(adapter);
  return adapter;
}

function assertActiveSelectedTelegramContext(
  observed,
  scenario,
  { nowMs = Date.now(), maxAgeMs = 5000 } = {},
) {
  const selection = observed?.activeSelection;
  if (
    !selection ||
    selection.source !== "computer_ui_active_selection" ||
    !Number.isSafeInteger(selection.observedAtMs) ||
    selection.observedAtMs > nowMs + 1000 ||
    nowMs - selection.observedAtMs > maxAgeMs
  ) {
    throw blockedError("computer_desktop_active_selection_unavailable");
  }
  const account = selection.account;
  if (
    !account ||
    account.selected !== true ||
    account.evidence !== "active_account_control" ||
    account.ownerId !== scenario?.owner?.ownerId ||
    String(account.telegramUserId || "") !== String(scenario.owner.telegramUserId) ||
    account.label !== scenario?.telegram?.accountLabel
  ) {
    throw blockedError("computer_desktop_active_account_mismatch");
  }
  const chat = selection.chat;
  if (
    !chat ||
    chat.selected !== true ||
    chat.evidence !== "active_chat_header" ||
    chat.ownerId !== scenario.owner.ownerId ||
    String(chat.telegramChatId || "") !== String(scenario.owner.telegramChatId) ||
    chat.label !== scenario.telegram.chatLabel ||
    (scenario.conversation?.conversationId &&
      chat.conversationRefHash !== sha256(String(scenario.conversation.conversationId)))
  ) {
    throw blockedError("computer_desktop_active_chat_mismatch");
  }
  return selection;
}

function assertComputerDesktopObservation(bridge, scenario, observed, { source, challenge, action }) {
  if (!observed || typeof observed !== "object" || observed.source !== source) {
    throw blockedError("computer_desktop_observation_unavailable");
  }
  if (
    observed.app !== scenario.telegram.bundleId ||
    observed.ownerId !== scenario.owner.ownerId ||
    observed.telegramUserId !== scenario.owner.telegramUserId ||
    observed.telegramChatId !== scenario.owner.telegramChatId ||
    observed.sessionRef !== bridge.provenance.sessionRef
  ) {
    throw blockedError("computer_desktop_observation_owner_mismatch");
  }
  if (observed.peerProcessId !== bridge.authority.peerProcessId) {
    throw blockedError("computer_desktop_observation_peer_mismatch");
  }
  if (
    observed.challenge !== challenge ||
    !Number.isSafeInteger(observed.observedAtMs) ||
    Math.abs(Date.now() - observed.observedAtMs) > 30000 ||
    (action && observed.action !== action)
  ) {
    throw blockedError("computer_desktop_observation_provenance_invalid");
  }
  assertActiveSelectedTelegramContext(observed, scenario);
  const { proof, screenshotBytes, ...unsigned } = observed;
  if (!bridge.verify(unsigned, proof)) {
    throw blockedError("computer_desktop_observation_authentication_failed");
  }
  bridge.consumeChallenge(challenge);
  if (
    screenshotBytes !== undefined &&
    (!Buffer.isBuffer(screenshotBytes) || sha256(screenshotBytes) !== observed.screenshotSha256)
  ) {
    throw blockedError("computer_desktop_capture_unavailable");
  }
  return observed;
}

async function readComputerDesktopState(bridge, scenario, request = {}) {
  if (typeof bridge?.assertParentBoundary !== "function") {
    throw blockedError("computer_desktop_parent_transport_unavailable");
  }
  bridge.assertParentBoundary();
  if (
    request.phase !== undefined &&
    !/^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(String(request.phase))
  ) {
    throw blockedError("computer_desktop_observation_provenance_invalid");
  }
  const challenge = crypto.randomBytes(32).toString("hex");
  const observed = await bridge.driver.get_app_state({
    ...(request.phase ? { phase: request.phase } : {}),
    ...(request.includeScreenshot === true ? { includeScreenshot: true } : {}),
    app: scenario.telegram.bundleId,
    ownerId: scenario.owner.ownerId,
    telegramUserId: scenario.owner.telegramUserId,
    telegramChatId: scenario.owner.telegramChatId,
    sessionRef: bridge.provenance.sessionRef,
    challenge,
  });
  return assertComputerDesktopObservation(bridge, scenario, observed, {
    source: "@oai/sky.get_app_state",
    challenge,
  });
}

function skyMethodForLogicalAction(action) {
  const methods = new Map([
    ["telegram.send_grouped_attachments", "press_key"],
    ["telegram.open_delivered_artifact", "click"],
    ["telegram.delete_synthetic_messages", "press_key"],
    ["telegram.send_text", "press_key"],
    ["telegram.reopen_conversation", "click"],
  ]);
  return action?.skyMethod || methods.get(action?.action) || "";
}

async function performComputerDesktopAction(bridge, scenario, action) {
  if (
    !action || typeof action !== "object" ||
    !new Set([
      "telegram.send_grouped_attachments",
      "telegram.open_delivered_artifact",
      "telegram.delete_synthetic_messages",
      "telegram.send_text",
      "telegram.reopen_conversation",
    ])
      .has(action.action)
  ) {
    throw blockedError("computer_desktop_action_unsupported");
  }
  const skyMethod = skyMethodForLogicalAction(action);
  if (
    !SKY_ACTION_METHOD_SET.has(skyMethod) ||
    !bridge.provenance.skyMethods.includes(skyMethod)
  ) {
    throw blockedError("computer_desktop_sky_primitive_unsupported");
  }
  const selected = await readComputerDesktopState(bridge, scenario);
  const selectionSha256 = sha256(canonicalJson(selected.activeSelection));
  const challenge = crypto.randomBytes(32).toString("hex");
  const observed = await bridge.driver.do_action({
    ...action,
    skyMethod,
    app: scenario.telegram.bundleId,
    ownerId: scenario.owner.ownerId,
    telegramUserId: scenario.owner.telegramUserId,
    telegramChatId: scenario.owner.telegramChatId,
    accountLabel: scenario.telegram.accountLabel,
    chatLabel: scenario.telegram.chatLabel,
    sessionRef: bridge.provenance.sessionRef,
    selectionChallenge: selected.challenge,
    selectionSha256,
    challenge,
  });
  const verified = assertComputerDesktopObservation(bridge, scenario, observed, {
    source: `@oai/sky.${skyMethod}`,
    challenge,
    action: action.action,
  });
  if (
    verified.skyMethod !== skyMethod ||
    verified.selectionChallenge !== selected.challenge ||
    verified.selectionSha256 !== selectionSha256 ||
    verified.observedAtMs < selected.observedAtMs ||
    verified.observedAtMs - selected.observedAtMs > 5000
  ) {
    throw blockedError("computer_desktop_action_selection_binding_invalid");
  }
  bridge.assertParentBoundary();
  return verified;
}

function assertTrustedComputerAdapter(driver, owner, authority, options = {}) {
  if (options.processProbe !== undefined) {
    throw blockedError("computer_desktop_process_probe_override_forbidden");
  }
  const ownerFields = owner?.owner && owner?.telegram ? owner : {
    caseId: options.caseId,
    owner: {
      ownerId: owner?.ownerId,
      telegramUserId: owner?.telegramUserId,
      telegramChatId: owner?.telegramChatId,
      email: owner?.email,
      synthetic: owner?.synthetic,
    },
    telegram: {
      bundleId: options.appBundleId || owner?.appBundleId || "ru.keepcoder.Telegram",
      accountLabel: owner?.accountLabel,
      chatLabel: owner?.chatLabel,
    },
    ...(owner?.conversationId ? { conversation: { conversationId: owner.conversationId } } : {}),
  };
  if (options.caseId && ownerFields.caseId !== options.caseId) {
    throw blockedError("computer_desktop_driver_provenance_invalid");
  }
  if (driver && typeof driver === "object" && VERIFIED_COMPUTER_ADAPTERS.has(driver)) {
    driver.assertParentBoundary();
    if (
      driver.binding.caseId !== ownerFields.caseId ||
      driver.binding.ownerId !== ownerFields.owner.ownerId ||
      driver.binding.telegramUserId !== String(ownerFields.owner.telegramUserId) ||
      driver.binding.telegramChatId !== String(ownerFields.owner.telegramChatId) ||
      driver.binding.appBundleId !== ownerFields.telegram.bundleId ||
      driver.binding.accountLabel !== ownerFields.telegram.accountLabel ||
      driver.binding.chatLabel !== ownerFields.telegram.chatLabel ||
      (ownerFields.conversation?.conversationId &&
        driver.binding.conversationId !== ownerFields.conversation.conversationId)
    ) {
      throw blockedError("computer_desktop_driver_owner_mismatch");
    }
    return driver;
  }
  return assertAuthenticatedComputerDesktopDriver(
    driver,
    ownerFields,
    options.environment || {},
    { authority, nowMs: options.nowMs },
  );
}

async function observeTrustedComputer(adapter, request = {}, options = {}) {
  const binding = adapter?.binding;
  if (!binding) throw blockedError("computer_desktop_driver_unavailable");
  const scenario = {
    caseId: binding.caseId,
    owner: {
      ownerId: binding.ownerId,
      telegramUserId: binding.telegramUserId,
      telegramChatId: binding.telegramChatId,
    },
    telegram: {
      bundleId: binding.appBundleId,
      accountLabel: binding.accountLabel,
      chatLabel: binding.chatLabel,
    },
    ...(binding.conversationId ? { conversation: { conversationId: binding.conversationId } } : {}),
  };
  if (!request.kind || request.kind === "state" || request.skyMethod === "get_app_state") {
    return readComputerDesktopState(adapter, scenario, {
      phase: request.phase,
      includeScreenshot: request.includeScreenshot,
    });
  }
  if (request.kind !== "action") throw blockedError("computer_desktop_action_unsupported");
  return performComputerDesktopAction(adapter, scenario, {
    ...(request.payload || {}),
    action: request.logicalAction || request.action,
    skyMethod: request.skyMethod,
    ...(options.actionOptions || {}),
  });
}

function writeObservedComputerCapture(root, name, observed) {
  const bytes = observed?.screenshotBytes;
  if (
    observed?.source !== "@oai/sky.get_app_state" ||
    !Buffer.isBuffer(bytes) || bytes.length < 128 ||
    sha256(bytes) !== observed.screenshotSha256 ||
    !bytes.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]))
  ) {
    throw blockedError("computer_desktop_capture_unavailable");
  }
  return writePrivateEvidence(root, name, bytes);
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

function assertNoSymlinkComponents(location, code = "evidence_root_symlink_forbidden") {
  const absolute = canonicalTemporaryAlias(location);
  const root = path.parse(absolute).root;
  let current = root;
  for (const component of absolute.slice(root.length).split(path.sep).filter(Boolean)) {
    current = path.join(current, component);
    let metadata;
    try {
      metadata = fs.lstatSync(current);
    } catch (error) {
      if (error?.code === "ENOENT") throw blockedError("private_path_unavailable");
      throw error;
    }
    if (metadata.isSymbolicLink()) throw blockedError(code);
  }
  return absolute;
}

function pathInside(candidate, root) {
  const relative = path.relative(root, candidate);
  return relative !== ".." && !relative.startsWith(`..${path.sep}`) && !path.isAbsolute(relative);
}

function assertPrivateEvidenceRoot(location) {
  if (!String(location || "").trim()) throw blockedError("evidence_root_required");
  const target = canonicalTemporaryAlias(location);
  const repository = fs.realpathSync(REPO_ROOT);
  if (pathInside(target, repository)) throw blockedError("evidence_root_inside_repository");
  if (target === path.parse(target).root) throw blockedError("evidence_root_invalid");
  let exact;
  try {
    exact = assertNoSymlinkComponents(target);
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

function readPrivateFile(location, { root, label, maxBytes = MAX_PRIVATE_FILE_BYTES } = {}) {
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
    if (before.size <= 0 || before.size > maxBytes) throw blockedError(`${label}_size_invalid`);
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

function readPrivateScenario(location, evidenceRoot) {
  if (!String(location || "").trim()) throw blockedError("scenario_unavailable");
  const { bytes } = readPrivateFile(location, { root: evidenceRoot, label: "scenario", maxBytes: 1024 * 1024 });
  try {
    const value = JSON.parse(bytes.toString("utf8"));
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      throw blockedError("scenario_invalid");
    }
    return value;
  } catch (error) {
    if (error?.blocked) throw error;
    throw blockedError("scenario_invalid");
  }
}

function writePrivateEvidence(root, name, payload) {
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/.test(String(name || ""))) {
    throw blockedError("private_evidence_path_invalid");
  }
  const directory = assertPrivateEvidenceRoot(root);
  const target = path.join(directory, name);
  try {
    if (fs.lstatSync(target).isSymbolicLink()) {
      throw blockedError("private_evidence_symlink_forbidden");
    }
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

function prefixedSha256(value) {
  return `sha256:${sha256(Buffer.from(value, "utf8"))}`;
}

function verifyIndependentTraceRows(rows, ownerId, originRef, workRef) {
  if (!Array.isArray(rows) || !rows.length || rows.length > 200) return false;
  const ownerScopeHash = prefixedSha256(`owner\0${String(ownerId).trim()}`);
  const originRefHash = prefixedSha256(`origin\0${String(originRef).trim()}`);
  const workRefHash = prefixedSha256(`work\0${String(workRef).trim()}`);
  let previousEventHash = `sha256:${"0".repeat(64)}`;
  let completed = false;
  let delivered = false;
  for (const [index, row] of rows.entries()) {
    let at;
    try {
      at = new Date(row.at).toISOString();
    } catch {
      return false;
    }
    const facts = row.facts || {};
    const contentHash = prefixedSha256(
      canonicalJson({ schemaVersion: 1, stage: row.stage, facts }),
    );
    const eventHash = prefixedSha256(
      canonicalJson({
        schemaVersion: 1,
        ownerScopeHash,
        originRefHash,
        sequence: row.sequence,
        stage: row.stage,
        at,
        facts,
        eventKeyHash: row.eventKeyHash,
        contentHash: row.contentHash,
        previousEventHash: row.previousEventHash,
      }),
    );
    if (
      row.schemaVersion !== 1 ||
      row.ownerScopeHash !== ownerScopeHash ||
      row.originRefHash !== originRefHash ||
      row.sequence !== index + 1 ||
      row.previousEventHash !== previousEventHash ||
      row.contentHash !== contentHash ||
      row.eventHash !== eventHash ||
      (facts.workRefHash && facts.workRefHash !== workRefHash)
    ) {
      return false;
    }
    if (row.stage === "work.completed") completed = true;
    if (row.stage === "callback.delivery.sent") delivered = true;
    previousEventHash = row.eventHash;
  }
  return completed && delivered;
}

function assertLoopbackUrl(value, code) {
  let parsed;
  try {
    parsed = new URL(String(value || ""));
  } catch {
    throw blockedError(code);
  }
  const hostname = parsed.hostname.replace(/^\[/, "").replace(/\]$/, "");
  if (
    !new Set(["http:", "https:"]).has(parsed.protocol) ||
    !new Set(["127.0.0.1", "localhost", "::1"]).has(hostname) ||
    parsed.username ||
    parsed.password
  ) {
    throw blockedError(code);
  }
  return parsed;
}

function assertSyntheticUrl(value) {
  let parsed;
  try {
    parsed = new URL(String(value || ""));
  } catch {
    throw blockedError("synthetic_url_required");
  }
  if (
    !new Set(["http:", "https:"]).has(parsed.protocol) ||
    !new Set(["example.com", "localhost", "127.0.0.1"]).has(parsed.hostname) ||
    parsed.username ||
    parsed.password
  ) {
    throw blockedError("synthetic_url_required");
  }
  return parsed;
}

function assertSyntheticAccount(scenario, environment) {
  const owner = scenario?.owner || {};
  const email = String(owner.email || "").trim().toLowerCase();
  const personalEmail = String(environment?.VIVENTIUM_QA_OWNER_EMAIL || "").trim().toLowerCase();
  const personalTelegramId = String(environment?.VIVENTIUM_QA_OWNER_TELEGRAM_USER_ID || "").trim();
  const personalTelegramChatId = String(environment?.VIVENTIUM_QA_OWNER_TELEGRAM_CHAT_ID || "").trim();
  if (!personalEmail || !personalTelegramId || !personalTelegramChatId) {
    throw blockedError("personal_owner_identity_guard_required");
  }
  if (email === personalEmail) throw blockedError("personal_owner_account_refused");
  if (String(owner.telegramUserId || "") === personalTelegramId) {
    throw blockedError("personal_telegram_account_refused");
  }
  if (String(owner.telegramChatId || "") === personalTelegramChatId) {
    throw blockedError("personal_telegram_chat_refused");
  }
  const [localPart, domain, ...remaining] = email.split("@");
  if (
    owner.synthetic !== true ||
    !String(owner.ownerId || "").trim() ||
    !localPart ||
    remaining.length ||
    !new Set(["example.com", "viventium.local", "localhost"]).has(domain) ||
    !/^\d{4,20}$/.test(String(owner.telegramUserId || "")) ||
    !/^-?\d{4,20}$/.test(String(owner.telegramChatId || ""))
  ) {
    throw blockedError("synthetic_owner_identity_required");
  }
}

async function cleanupOwnerScopedSyntheticTelegramRecords({
  database,
  scenario,
  environment,
  owner,
  inventory,
  removeRemote,
}) {
  assertSyntheticAccount(scenario, environment);
  const ownerId = String(scenario.owner.ownerId);
  if (
    !database ||
    typeof database.collection !== "function" ||
    !owner?._id ||
    String(owner._id) !== ownerId ||
    String(owner.email || "").trim().toLowerCase() !== String(scenario.owner.email).toLowerCase() ||
    String(owner.role || "").toUpperCase() === "ADMIN" ||
    inventory?.ownerId !== ownerId ||
    !String(inventory.conversationId || "").trim() ||
    !Number.isSafeInteger(inventory.startedAtMs) ||
    inventory.startedAtMs < 0 ||
    !Array.isArray(inventory.messages) ||
    !Array.isArray(inventory.ingress) ||
    !Array.isArray(inventory.conversations) ||
    !Array.isArray(inventory.telegramMessageIds) ||
    inventory.messages.length > 64 ||
    inventory.ingress.length > 64 ||
    inventory.conversations.length > 1 ||
    inventory.telegramMessageIds.length > 64 ||
    new Set(inventory.telegramMessageIds).size !== inventory.telegramMessageIds.length ||
    inventory.telegramMessageIds.some((value) => !Number.isSafeInteger(value) || value < 1) ||
    typeof removeRemote !== "function"
  ) {
    throw blockedError("synthetic_telegram_cleanup_scope_invalid");
  }
  if (
    (inventory.createdConversation === true && inventory.conversations.length !== 1) ||
    (inventory.createdConversation !== true && inventory.conversations.length !== 0)
  ) {
    throw blockedError("synthetic_telegram_cleanup_conversation_unverified");
  }

  const freshOwner = await database.collection("users").findOne({
    _id: owner._id,
    email: scenario.owner.email,
  });
  if (
    !freshOwner?._id ||
    String(freshOwner._id) !== ownerId ||
    String(freshOwner.email || "").trim().toLowerCase() !== String(scenario.owner.email).toLowerCase() ||
    String(freshOwner.role || "").toUpperCase() === "ADMIN"
  ) {
    throw blockedError("synthetic_telegram_cleanup_owner_mismatch");
  }

  const entries = [];
  for (const record of inventory.messages) {
    const createdAtMs = new Date(record?.createdAt || 0).getTime();
    if (
      !record?._id ||
      String(record.user || "") !== ownerId ||
      record.conversationId !== inventory.conversationId ||
      !String(record.messageId || "").trim() ||
      !Number.isFinite(createdAtMs) ||
      createdAtMs < inventory.startedAtMs
    ) {
      throw blockedError("synthetic_telegram_cleanup_owner_mismatch");
    }
    entries.push({
      collection: "messages",
      filter: {
        _id: record._id,
        user: ownerId,
        conversationId: inventory.conversationId,
      },
    });
  }
  for (const record of inventory.ingress) {
    const createdAtMs = new Date(record?.createdAt || 0).getTime();
    if (
      !record?._id ||
      String(record.telegramUserId || "") !== String(scenario.owner.telegramUserId) ||
      String(record.telegramChatId || "") !== String(scenario.owner.telegramChatId) ||
      record.conversationId !== inventory.conversationId ||
      !Number.isFinite(createdAtMs) ||
      createdAtMs < inventory.startedAtMs
    ) {
      throw blockedError("synthetic_telegram_cleanup_owner_mismatch");
    }
    entries.push({
      collection: "viventiumtelegramingressevents",
      filter: {
        _id: record._id,
        telegramUserId: String(scenario.owner.telegramUserId),
        telegramChatId: String(scenario.owner.telegramChatId),
        conversationId: inventory.conversationId,
      },
    });
  }
  for (const record of inventory.conversations) {
    const createdAtMs = new Date(record?.createdAt || 0).getTime();
    if (
      !record?._id ||
      String(record.user || "") !== ownerId ||
      record.conversationId !== inventory.conversationId ||
      !Number.isFinite(createdAtMs) ||
      createdAtMs < inventory.startedAtMs
    ) {
      throw blockedError("synthetic_telegram_cleanup_owner_mismatch");
    }
    entries.push({
      collection: "conversations",
      filter: {
        _id: record._id,
        user: ownerId,
        conversationId: inventory.conversationId,
      },
    });
  }
  for (const entry of entries) {
    if (!await database.collection(entry.collection).findOne(entry.filter)) {
      throw blockedError("synthetic_telegram_cleanup_owner_mismatch");
    }
  }

  if (inventory.telegramMessageIds.length) {
    const remote = await removeRemote([...inventory.telegramMessageIds]);
    if (
      remote?.deleted !== true ||
      canonicalJson(remote.messageIds) !== canonicalJson(inventory.telegramMessageIds)
    ) {
      throw blockedError("synthetic_telegram_remote_cleanup_unverified");
    }
  }
  for (const entry of entries) {
    if (entry.collection === "conversations") {
      const remaining = await database.collection("messages").countDocuments({
        user: ownerId,
        conversationId: inventory.conversationId,
      });
      if (remaining !== 0) throw blockedError("synthetic_telegram_cleanup_conversation_not_empty");
    }
    const removed = await database.collection(entry.collection).deleteOne(entry.filter);
    if (removed?.deletedCount !== 1) {
      throw blockedError("synthetic_telegram_cleanup_delete_unverified");
    }
  }
  return {
    cleaned: true,
    ownerId,
    conversationId: inventory.conversationId,
    removedMessageCount: inventory.messages.length,
    removedIngressCount: inventory.ingress.length,
    removedConversationCount: inventory.conversations.length,
  };
}

function validateScenario(scenario, environment = process.env) {
  if (
    scenario?.contractVersion !== 1 ||
    scenario.caseId !== CASE_ID ||
    scenario.classification !== "synthetic_public_safe" ||
    !Array.isArray(scenario.inputs) ||
    scenario.inputs.length < REQUIRED_FAMILIES.size
  ) {
    throw blockedError("scenario_invalid");
  }
  assertSyntheticAccount(scenario, environment);
  const families = new Set(scenario.inputs.map((input) => input?.family));
  if ([...REQUIRED_FAMILIES].some((family) => !families.has(family))) {
    throw blockedError("missing_attachment_family");
  }
  for (const [index, input] of scenario.inputs.entries()) {
    if (
      !REQUIRED_FAMILIES.has(input.family) ||
      input.position !== index ||
      input.ownerId !== scenario.owner.ownerId ||
      !SAFE_NAME.test(String(input.filename || "")) ||
      !SAFE_NAME.test(String(input.visibleIdentity || "")) ||
      !SHA256.test(String(input.sha256 || "")) ||
      !Number.isSafeInteger(input.sizeBytes) ||
      input.sizeBytes < 1 ||
      input.sizeBytes > MAX_PRIVATE_FILE_BYTES
    ) {
      throw blockedError("owner_scoped_synthetic_attachment_required");
    }
  }
  const sameNames = new Map();
  const groups = new Map();
  for (const input of scenario.inputs) {
    const named = sameNames.get(input.filename) || [];
    named.push(input);
    sameNames.set(input.filename, named);
    if (input.groupId) {
      const grouped = groups.get(input.groupId) || [];
      grouped.push(input);
      groups.set(input.groupId, grouped);
    } else if (input.caption) {
      throw blockedError("captioned_media_group_required");
    }
  }
  if (![...sameNames.values()].some((items) => items.length >= 2 && new Set(items.map((item) => item.sha256)).size === items.length)) {
    throw blockedError("same_name_attachment_proof_required");
  }
  if (![...groups.values()].some((items) => items.length >= 2 && items.filter((item) => String(item.caption || "").trim()).length === 1)) {
    throw blockedError("captioned_media_group_required");
  }

  const runtime = scenario.runtime || {};
  assertLoopbackUrl(runtime.clientUrl, "local_client_url_required");
  assertLoopbackUrl(runtime.apiUrl, "local_api_url_required");
  if (
    !String(runtime.primaryProviderId || "").trim() ||
    !String(runtime.fallbackProviderId || "").trim() ||
    runtime.primaryProviderId === runtime.fallbackProviderId
  ) {
    throw blockedError("required_provider_unavailable");
  }
  if (
    !Array.isArray(runtime.requiredToolIds) ||
    !runtime.requiredToolIds.length ||
    new Set(runtime.requiredToolIds).size !== runtime.requiredToolIds.length ||
    runtime.requiredToolIds.some((toolId) => !/^[A-Za-z0-9._:-]{1,160}$/.test(String(toolId || "")))
  ) {
    throw blockedError("required_tool_unavailable");
  }
  if (scenario.telegram?.bundleId !== "ru.keepcoder.Telegram" || !scenario.telegram.accountLabel || !scenario.telegram.chatLabel) {
    throw blockedError("owner_safe_telegram_identity_unavailable");
  }
  assertSyntheticUrl(scenario.mission?.sourceUrl);
  if (
    !SAFE_NAME.test(String(scenario.mission.outputIdentity || "")) ||
    !String(scenario.mission.marker || "").includes(CASE_ID) ||
    !Number.isSafeInteger(scenario.mission.minimumRuntimeOverlapMs) ||
    scenario.mission.minimumRuntimeOverlapMs < 1
  ) {
    throw blockedError("synthetic_mission_scenario_invalid");
  }
  if (
    scenario.restart?.supported !== true ||
    !String(scenario.restart.executable || "").trim() ||
    !Array.isArray(scenario.restart.arguments) ||
    !scenario.restart.arguments.includes("--restart") ||
    canonicalJson(scenario.restart.services) !== canonicalJson(REQUIRED_RESTART_SERVICES)
  ) {
    throw blockedError("runtime_restart_unsupported");
  }
  if (!scenario.restart.arguments.includes("--allow-dirty-local-testing")) {
    throw blockedError("runtime_restart_dirty_checkout_protection_required");
  }
  return scenario;
}

function assertOwnerSafeTelegramIdentity(scenario, environment, observed) {
  assertSyntheticAccount(scenario, environment);
  const personalLabel = String(environment?.VIVENTIUM_QA_OWNER_TELEGRAM_ACCOUNT_LABEL || "").trim();
  if (!personalLabel) throw blockedError("personal_owner_identity_guard_required");
  if (observed?.activeSelectionVerified !== true) {
    throw blockedError("computer_desktop_active_selection_unavailable");
  }
  if (
    !observed ||
    observed.source !== "telegram_desktop_accessibility" ||
    observed.bundleId !== scenario.telegram.bundleId ||
    observed.accountVisible !== true ||
    observed.chatVisible !== true ||
    observed.accountLabel !== scenario.telegram.accountLabel ||
    observed.chatLabel !== scenario.telegram.chatLabel ||
    observed.accountLabel === personalLabel ||
    observed.telegramUserId !== scenario.owner.telegramUserId ||
    observed.telegramChatId !== scenario.owner.telegramChatId ||
    observed.ownerId !== scenario.owner.ownerId ||
    observed.linkedOwnerId !== scenario.owner.ownerId
  ) {
    throw blockedError("owner_safe_telegram_identity_unavailable");
  }
  return observed;
}

function inspectSyntheticInputs(scenario, { evidenceRoot }) {
  const root = fs.realpathSync(canonicalTemporaryAlias(evidenceRoot));
  return scenario.inputs.map((input) => {
    const { bytes } = readPrivateFile(input.sourcePath, {
      root,
      label: "synthetic_attachment",
      maxBytes: MAX_PRIVATE_FILE_BYTES,
    });
    if (bytes.length !== input.sizeBytes || sha256(bytes) !== input.sha256) {
      throw blockedError("synthetic_attachment_bytes_mismatch");
    }
    if (path.basename(input.sourcePath) !== input.filename) {
      throw blockedError("synthetic_attachment_filename_mismatch");
    }
    return { ...input, bytes };
  });
}

function deriveObservedUploadMetadata({ file, reference, userMessage, visibleText, expected, position }) {
  const rawOrdinal = reference?.media_group_index ?? reference?.viventium_media_group_index ??
    file?.media_group_index ?? file?.viventium_media_group_index;
  const ordinal = Number(rawOrdinal);
  if (rawOrdinal == null || !Number.isSafeInteger(ordinal) || ordinal !== position) {
    throw blockedError("telegram_upload_order_evidence_unavailable");
  }

  const declaredFamily = String(reference?.family || file?.family || file?.metadata?.family || "").trim();
  const provenance = String(
    reference?.source || reference?.context || file?.source || file?.context || file?.metadata?.source || "",
  ).trim();
  const mime = String(reference?.type || file?.type || file?.mimetype || "").trim().toLowerCase();
  let family = "";
  if (REQUIRED_FAMILIES.has(declaredFamily)) {
    family = declaredFamily;
  } else if (new Set(["artifact", "worker_artifact", "prior_artifact", "execute_code"]).has(provenance)) {
    family = "prior_artifact";
  } else if (mime.startsWith("image/")) {
    family = "image";
  } else if (mime.startsWith("audio/")) {
    family = "audio";
  } else if (mime.startsWith("video/")) {
    family = "video";
  } else if (mime.includes("/")) {
    family = "document";
  }
  if (!family) throw blockedError("telegram_upload_family_evidence_unavailable");

  const labels = Array.isArray(visibleText) ? visibleText.map((item) => String(item || "")) : [];
  const visibleLabel = labels.find((item) => item.includes(String(expected?.visibleIdentity || "")));
  if (!visibleLabel || !String(expected?.visibleIdentity || "").trim()) {
    throw blockedError("telegram_upload_visible_identity_unavailable");
  }
  const visibleStart = visibleLabel.indexOf(expected.visibleIdentity);
  const visibleIdentity = visibleLabel.slice(visibleStart, visibleStart + expected.visibleIdentity.length);

  const text = String(userMessage?.text || "");
  let groupId = String(
    reference?.media_group_id || reference?.groupId || file?.media_group_id ||
    file?.metadata?.media_group_id || userMessage?.metadata?.viventium?.mediaGroupId || "",
  ).trim();
  if (expected?.groupId && !groupId) {
    const marker = `[group:${expected.groupId}]`;
    const start = text.indexOf(marker);
    if (start < 0 || !labels.some((item) => item.includes(marker))) {
      throw blockedError("telegram_media_group_evidence_unavailable");
    }
    groupId = text.slice(start + "[group:".length, start + marker.length - 1);
  }
  if (expected?.groupId && !groupId) throw blockedError("telegram_media_group_evidence_unavailable");

  let caption = String(reference?.caption || file?.caption || file?.metadata?.caption || "");
  if (expected?.caption) {
    const actual = caption || text;
    const start = actual.indexOf(expected.caption);
    if (start < 0 || !labels.some((item) => item.includes(expected.caption))) {
      throw blockedError("telegram_group_caption_evidence_unavailable");
    }
    caption = actual.slice(start, start + expected.caption.length);
  }
  return { family, visibleIdentity, position: ordinal, groupId, caption };
}

function observedFallbackAttemptManifests(attempts, observedRows, expectedDigest) {
  if (!Array.isArray(attempts) || !Array.isArray(observedRows)) {
    throw blockedError("fallback_input_manifest_evidence_unavailable");
  }
  return attempts.map((attempt) => {
    const matches = observedRows.filter((row) =>
      Number(row?.attemptNumber ?? row?.attempt_number) === Number(attempt.ordinal) ||
      String(row?.attemptId || row?.attempt_id || "") === String(attempt.attemptId || ""),
    );
    if (matches.length !== 1) throw blockedError("fallback_input_manifest_evidence_unavailable");
    const digest = String(matches[0].inputManifestSha256 || matches[0].input_manifest_sha256 || "");
    if (!SHA256.test(digest)) throw blockedError("fallback_input_manifest_evidence_unavailable");
    if (digest !== expectedDigest) throw blockedError("fallback_input_manifest_mismatch");
    return digest;
  });
}

function assessCoordinatedRestartStatus(status, restart = {}) {
  const expected = new Set(["glasshive-runtime", "librechat-core", "telegram-bot"]);
  const required = Array.isArray(status?.requiredServices) ? status.requiredServices : [];
  const acknowledged = Array.isArray(status?.acknowledgedServices) ? status.acknowledgedServices : [];
  const coordinatedCaseId = String(restart.coordinatedQaCaseId || status?.caseId || "");
  if (
    !new Set(["PWK-UC-016", "PWK-UC-017"]).has(coordinatedCaseId) ||
    status?.caseId !== coordinatedCaseId ||
    status.restartState !== "ready" ||
    !/^qa_[A-Za-z0-9_-]{8,64}$/.test(String(status.sessionRef || "")) ||
    !/^sha256:[a-f0-9]{64}$/.test(String(status.serviceAckDigest || "")) ||
    !Array.isArray(status.missingServices) || status.missingServices.length !== 0 ||
    required.length !== expected.size || acknowledged.length !== expected.size ||
    new Set(required).size !== expected.size || new Set(acknowledged).size !== expected.size ||
    [...expected].some((service) => !required.includes(service) || !acknowledged.includes(service))
  ) {
    throw blockedError("runtime_restart_unsupported");
  }
  const serviceNames = new Map([
    ["librechat-core", "core"],
    ["glasshive-runtime", "glasshive"],
    ["telegram-bot", "telegram"],
  ]);
  return {
    caseId: coordinatedCaseId,
    sessionRef: status.sessionRef,
    serviceAckDigest: status.serviceAckDigest,
    services: REQUIRED_RESTART_SERVICES.filter((service) =>
      [...serviceNames.entries()].some(([actual, normalized]) =>
        normalized === service && acknowledged.includes(actual),
      ),
    ),
  };
}

function observedArtifactIdentity(rows, workerBytes) {
  if (!Array.isArray(rows) || !Buffer.isBuffer(workerBytes) || !workerBytes.length) {
    throw blockedError("delivered_artifact_identity_unavailable");
  }
  const digest = sha256(workerBytes);
  const expected = `artifact_sha256:${digest}`;
  const matches = [];
  for (const row of rows) {
    let payload;
    try {
      payload = JSON.parse(String(row?.payload || row?.payload_json || "{}"));
    } catch {
      throw blockedError("delivered_artifact_identity_unavailable");
    }
    const details = payload?.artifactRefs;
    if (details?.available !== true || !Array.isArray(details.refs)) continue;
    for (const artifact of details.refs) {
      if (
        artifact?.artifactRef === expected &&
        artifact.fingerprint === `sha256:${digest}` &&
        artifact.sizeBytes === workerBytes.length &&
        new Set(["available", "completed", "ready"]).has(artifact.state)
      ) {
        matches.push(artifact.artifactRef);
      }
    }
  }
  if (matches.length !== 1) throw blockedError("delivered_artifact_identity_unavailable");
  return matches[0];
}

function assessOrderedInputParity({ scenario, expected, uploads, workerInputs }) {
  if (!Array.isArray(uploads) || uploads.length !== expected.length) {
    throw blockedError("telegram_upload_count_mismatch");
  }
  if (!Array.isArray(workerInputs) || workerInputs.length !== expected.length) {
    throw blockedError("worker_materialized_file_unavailable");
  }
  const fileIds = new Set();
  const normalized = [];
  for (const [index, source] of expected.entries()) {
    const uploaded = uploads[index];
    if (uploaded?.position !== index) throw blockedError("telegram_upload_order_mismatch");
    if (uploaded.ownerId !== scenario.owner.ownerId) throw blockedError("telegram_upload_owner_mismatch");
    if (!String(uploaded.fileId || "").trim() || fileIds.has(uploaded.fileId)) {
      throw blockedError("telegram_upload_identity_missing");
    }
    fileIds.add(uploaded.fileId);
    if (
      !Buffer.isBuffer(uploaded.bytes) ||
      uploaded.bytes.length !== source.sizeBytes ||
      sha256(uploaded.bytes) !== source.sha256 ||
      uploaded.sha256 !== source.sha256 ||
      uploaded.sizeBytes !== source.sizeBytes
    ) {
      throw blockedError("telegram_upload_bytes_mismatch");
    }
    if (
      uploaded.family !== source.family ||
      uploaded.filename !== source.filename ||
      uploaded.visibleIdentity !== source.visibleIdentity ||
      uploaded.groupId !== source.groupId ||
      uploaded.caption !== source.caption
    ) {
      throw blockedError("telegram_upload_metadata_mismatch");
    }
    const worker = workerInputs[index];
    if (
      !worker ||
      worker.ownerId !== scenario.owner.ownerId ||
      worker.fileId !== uploaded.fileId ||
      worker.position !== index ||
      worker.workRef !== uploaded.workRef ||
      worker.runRef !== uploaded.runRef
    ) {
      throw blockedError("worker_upload_identity_mismatch");
    }
    if (
      !Buffer.isBuffer(worker.bytes) ||
      worker.bytes.length !== source.sizeBytes ||
      sha256(worker.bytes) !== source.sha256 ||
      worker.sha256 !== source.sha256 ||
      worker.sizeBytes !== source.sizeBytes
    ) {
      throw blockedError("worker_upload_bytes_mismatch");
    }
    normalized.push({
      byteSha256: source.sha256,
      captionSha256: source.caption ? sha256(source.caption) : "",
      family: source.family,
      fileRefHash: sha256(String(uploaded.fileId)),
      groupRefHash: source.groupId ? sha256(String(source.groupId)) : "",
      nameSha256: sha256(source.filename),
      ownerRefHash: sha256(scenario.owner.ownerId),
      position: index,
      sizeBytes: source.sizeBytes,
      telegramEvidenceId: `telegram-input-${index}`,
      visibleIdentity: source.visibleIdentity,
      workerEvidenceId: `worker-input-${index}`,
    });
  }
  return {
    inputCount: normalized.length,
    inputManifestSha256: sha256(canonicalJson(normalized)),
    records: normalized,
    fileIds: [...fileIds],
  };
}

function assessOwnerScopedMission(missions, scenario) {
  if (!Array.isArray(missions) || missions.length !== 1) {
    throw blockedError("exactly_one_owner_scoped_mission_required");
  }
  const mission = missions[0];
  if (mission.ownerId !== scenario.owner.ownerId || mission.originSurface !== "telegram") {
    throw blockedError("worker_owner_scope_mismatch");
  }
  if (![mission.workRef, mission.runRef, mission.workerRef].every((value) => String(value || "").trim())) {
    throw blockedError("intended_worker_identity_unavailable");
  }
  const lease = mission.lease || {};
  if (
    lease.ownerId !== mission.ownerId ||
    lease.workerRef !== mission.workerRef ||
    lease.runRef !== mission.runRef ||
    !Number.isFinite(mission.runtimeInvokedAtMs) ||
    !Number.isFinite(lease.acquiredAtMs) ||
    !Number.isFinite(lease.confirmedAtMs) ||
    lease.acquiredAtMs > mission.runtimeInvokedAtMs ||
    lease.confirmedAtMs > mission.runtimeInvokedAtMs
  ) {
    throw blockedError("owner_scoped_worker_runtime_lease_unavailable");
  }
  const source = mission.sourceWindow || {};
  const worker = mission.workerWindow || {};
  if (
    ![source.startedAtMs, source.endedAtMs, worker.startedAtMs, worker.endedAtMs].every(Number.isFinite)
  ) {
    throw blockedError("worker_runtime_overlap_unavailable");
  }
  const overlapMs = Math.min(source.endedAtMs, worker.endedAtMs) - Math.max(source.startedAtMs, worker.startedAtMs);
  if (overlapMs < scenario.mission.minimumRuntimeOverlapMs) {
    throw blockedError("worker_runtime_overlap_unavailable");
  }
  return { ...mission, overlapMs };
}

function assertMissionScope(value, mission, reason) {
  if (
    value?.ownerId !== mission.ownerId ||
    value.workRef !== mission.workRef ||
    value.runRef !== mission.runRef
  ) {
    throw blockedError(reason);
  }
}

function assessAuthorizedBrokerReceipts(receipts, scenario, mission, inputManifestSha256) {
  if (!Array.isArray(receipts)) throw blockedError("required_tool_receipt_unavailable");
  const byTool = new Map();
  const identities = new Set();
  for (const receipt of receipts) {
    assertMissionScope(receipt, mission, "broker_receipt_owner_scope_mismatch");
    if (receipt.authorized !== true || receipt.state !== "completed") {
      throw blockedError("broker_receipt_not_authorized");
    }
    if (receipt.inputManifestSha256 !== inputManifestSha256) {
      throw blockedError("broker_receipt_input_manifest_mismatch");
    }
    if (!String(receipt.receiptId || "").trim() || identities.has(receipt.receiptId)) {
      throw blockedError("broker_receipt_identity_unavailable");
    }
    identities.add(receipt.receiptId);
    byTool.set(receipt.toolId, receipt);
  }
  if (
    byTool.size !== scenario.runtime.requiredToolIds.length ||
    scenario.runtime.requiredToolIds.some((toolId) => !byTool.has(toolId))
  ) {
    throw blockedError("required_tool_receipt_unavailable");
  }
  return { receiptCount: receipts.length, toolIds: [...byTool.keys()] };
}

function assessProviderFallback(fallback, scenario, mission, inputManifestSha256) {
  assertMissionScope(fallback, mission, "fallback_mission_scope_mismatch");
  if (!Array.isArray(fallback.attempts) || fallback.attempts.length !== 2) {
    throw blockedError("provider_fallback_evidence_unavailable");
  }
  const [primary, recovered] = fallback.attempts;
  if (
    primary.providerId !== scenario.runtime.primaryProviderId ||
    !new Set(["provider_unavailable", "quota_cooldown", "rate_limited"]).has(primary.state)
  ) {
    throw blockedError("primary_provider_failure_unproven");
  }
  if (recovered.providerId !== scenario.runtime.fallbackProviderId || recovered.state !== "completed") {
    throw blockedError("fallback_provider_unavailable");
  }
  if (
    !String(primary.attemptId || "").trim() ||
    !String(recovered.attemptId || "").trim() ||
    primary.attemptId === recovered.attemptId ||
    fallback.attempts.some((attempt) => attempt.inputManifestSha256 !== inputManifestSha256)
  ) {
    throw blockedError("fallback_input_manifest_mismatch");
  }
  return { attemptCount: 2, fallbackProviderIdHash: sha256(recovered.providerId) };
}

function assertActiveFallbackAttempt(fallback, scenario, mission, inputManifestSha256) {
  assertMissionScope(fallback, mission, "fallback_mission_scope_mismatch");
  if (!Array.isArray(fallback.attempts) || fallback.attempts.length !== 2) {
    throw blockedError("provider_fallback_evidence_unavailable");
  }
  const [primary, current] = fallback.attempts;
  if (
    primary.providerId !== scenario.runtime.primaryProviderId ||
    !new Set(["provider_unavailable", "quota_cooldown", "rate_limited"]).has(primary.state)
  ) {
    throw blockedError("primary_provider_failure_unproven");
  }
  if (
    current.providerId !== scenario.runtime.fallbackProviderId ||
    !String(current.attemptId || "").trim() ||
    current.state !== "running" ||
    !Number.isSafeInteger(current.runtimeInvokedAtMs) ||
    current.runtimeInvokedAtMs < 1
  ) {
    throw blockedError("fallback_attempt_not_active");
  }
  if (fallback.attempts.some((attempt) => attempt.inputManifestSha256 !== inputManifestSha256)) {
    throw blockedError("fallback_input_manifest_mismatch");
  }
  const lease = current.lease;
  if (
    !lease ||
    !String(lease.leaseId || "").trim() ||
    lease.ownerId !== mission.ownerId ||
    lease.workerRef !== mission.workerRef ||
    lease.runRef !== mission.runRef ||
    !Number.isSafeInteger(lease.acquiredAtMs) ||
    !Number.isSafeInteger(lease.confirmedAtMs) ||
    lease.acquiredAtMs > current.runtimeInvokedAtMs ||
    lease.confirmedAtMs > current.runtimeInvokedAtMs ||
    lease.releasedAtMs !== null ||
    !Number.isSafeInteger(lease.pid) ||
    lease.pid <= 1 ||
    !String(lease.processStartIdentity || "").trim()
  ) {
    throw blockedError("fallback_attempt_lease_unavailable");
  }
  if (fallback.terminalCallbackObserved !== false) {
    throw blockedError("restart_after_terminal_callback_refused");
  }
  if (fallback.artifactObserved !== false) {
    throw blockedError("restart_after_artifact_creation_refused");
  }
  return current;
}

function assessRestartPreservation(restart, scenario, mission, inputManifestSha256) {
  if (restart?.supported !== true || scenario.restart?.supported !== true) {
    throw blockedError("runtime_restart_unsupported");
  }
  assertMissionScope(restart, mission, "restart_mission_scope_mismatch");
  if (
    restart.performed !== true ||
    restart.recovered !== true ||
    !String(restart.beforeRuntimeIdentity || "").trim() ||
    !String(restart.afterRuntimeIdentity || "").trim() ||
    restart.beforeRuntimeIdentity === restart.afterRuntimeIdentity ||
    canonicalJson(restart.services) !== canonicalJson(scenario.restart.services)
  ) {
    throw blockedError("runtime_restart_recovery_unavailable");
  }
  if (
    restart.beforeInputManifestSha256 !== inputManifestSha256 ||
    restart.afterInputManifestSha256 !== inputManifestSha256
  ) {
    throw blockedError("restart_input_manifest_mismatch");
  }
  return { recovered: true, serviceCount: restart.services.length };
}

function captureTelegramDownloadBaseline(directory, filename) {
  if (!SAFE_NAME.test(String(filename || ""))) {
    throw blockedError("telegram_artifact_download_path_invalid");
  }
  let root;
  try {
    root = fs.realpathSync(directory);
    const metadata = fs.statSync(root);
    if (!metadata.isDirectory() || metadata.uid !== process.getuid()) {
      throw blockedError("telegram_artifact_download_root_unavailable");
    }
  } catch (error) {
    if (error?.blocked) throw error;
    throw blockedError("telegram_artifact_download_root_unavailable");
  }
  const target = path.join(root, filename);
  try {
    const metadata = fs.lstatSync(target);
    if (!metadata.isFile() || metadata.isSymbolicLink() || metadata.uid !== process.getuid()) {
      throw blockedError("telegram_artifact_download_path_invalid");
    }
    return {
      exists: true,
      root,
      filename,
      device: metadata.dev,
      inode: metadata.ino,
      sizeBytes: metadata.size,
      modifiedAtMs: metadata.mtimeMs,
      changedAtMs: metadata.ctimeMs,
      observedAtMs: Date.now(),
    };
  } catch (error) {
    if (error?.blocked) throw error;
    if (error?.code !== "ENOENT") throw blockedError("telegram_artifact_download_path_invalid");
    return { exists: false, root, filename, observedAtMs: Date.now() };
  }
}

function readFreshTelegramDownload({
  directory,
  filename,
  baseline,
  actionObservedAtMs,
  ownerId,
  expectedOwnerId,
  expectedSha256,
}) {
  if (!String(ownerId || "").trim() || ownerId !== expectedOwnerId) {
    throw blockedError("telegram_artifact_download_owner_mismatch");
  }
  if (
    !SAFE_NAME.test(String(filename || "")) ||
    !SHA256.test(String(expectedSha256 || "")) ||
    !Number.isSafeInteger(actionObservedAtMs)
  ) {
    throw blockedError("telegram_artifact_download_path_invalid");
  }
  let root;
  try {
    root = fs.realpathSync(directory);
    if (root !== baseline?.root || filename !== baseline.filename) {
      throw blockedError("telegram_artifact_download_path_invalid");
    }
  } catch (error) {
    if (error?.blocked) throw error;
    throw blockedError("telegram_artifact_download_unavailable");
  }
  const target = path.join(root, filename);
  let descriptor;
  try {
    descriptor = fs.openSync(target, fs.constants.O_RDONLY | (fs.constants.O_NOFOLLOW || 0));
    const metadata = fs.fstatSync(descriptor);
    if (
      !metadata.isFile() ||
      metadata.uid !== process.getuid() ||
      metadata.size < 1 ||
      metadata.size > MAX_PRIVATE_FILE_BYTES ||
      !pathInside(fs.realpathSync(target), root)
    ) {
      throw blockedError("telegram_artifact_download_path_invalid");
    }
    const unchanged = baseline.exists === true &&
      metadata.dev === baseline.device &&
      metadata.ino === baseline.inode &&
      metadata.size === baseline.sizeBytes &&
      metadata.mtimeMs === baseline.modifiedAtMs &&
      metadata.ctimeMs === baseline.changedAtMs;
    if (
      unchanged ||
      Math.max(metadata.ctimeMs, metadata.mtimeMs) < actionObservedAtMs
    ) {
      throw blockedError("telegram_artifact_download_stale");
    }
    const bytes = fs.readFileSync(descriptor);
    if (sha256(bytes) !== expectedSha256) {
      throw blockedError("telegram_artifact_download_hash_mismatch");
    }
    return { bytes, sha256: expectedSha256, ownerId, createdAtMs: Math.max(metadata.ctimeMs, metadata.mtimeMs) };
  } catch (error) {
    if (error?.blocked) throw error;
    if (error?.code === "ENOENT") throw blockedError("telegram_artifact_download_unavailable");
    throw blockedError("telegram_artifact_download_path_invalid");
  } finally {
    if (descriptor !== undefined) fs.closeSync(descriptor);
  }
}

function assessDeliveredArtifact(delivery, scenario, mission) {
  const worker = delivery?.worker;
  const telegram = delivery?.telegram;
  const activeWork = delivery?.activeWork;
  if (!worker || !telegram || !activeWork) throw blockedError("delivered_artifact_unavailable");
  for (const value of [worker, telegram, activeWork]) {
    assertMissionScope(value, mission, "artifact_owner_scope_mismatch");
    if (value.artifactId !== worker.artifactId || value.filename !== scenario.mission.outputIdentity) {
      throw blockedError("artifact_identity_mismatch");
    }
  }
  if (!Buffer.isBuffer(worker.bytes) || !worker.bytes.length || sha256(worker.bytes) !== worker.sha256) {
    throw blockedError("worker_artifact_bytes_unavailable");
  }
  if (!Buffer.isBuffer(telegram.bytes) || sha256(telegram.bytes) !== worker.sha256 || telegram.sha256 !== worker.sha256) {
    throw blockedError("telegram_artifact_bytes_mismatch");
  }
  if (!Buffer.isBuffer(activeWork.bytes) || sha256(activeWork.bytes) !== worker.sha256 || activeWork.sha256 !== worker.sha256) {
    throw blockedError("active_work_artifact_bytes_mismatch");
  }
  if (
    telegram.visible !== true ||
    telegram.opened !== true ||
    telegram.assistantBubbleCount !== 1 ||
    telegram.artifactDeliveryCount !== 1 ||
    !Array.isArray(telegram.deliveryReceipts) ||
    telegram.deliveryReceipts.length !== 1 ||
    telegram.deliveryReceipts[0]?.state !== "sent" ||
    telegram.deliveryReceipts[0]?.ownerId !== mission.ownerId ||
    telegram.deliveryReceipts[0]?.workRef !== mission.workRef
  ) {
    throw blockedError("exactly_once_telegram_delivery_required");
  }
  if (activeWork.visible !== true || activeWork.opened !== true || activeWork.headed !== true) {
    throw blockedError("headed_active_work_artifact_unavailable");
  }
  return { artifactSha256: worker.sha256, deliveryCount: 1, artifactBytes: worker.bytes.length };
}

function assertRequiredCapabilities(observed, scenario) {
  if (
    !Array.isArray(observed?.providerIds) ||
    !observed.providerIds.includes(scenario.runtime.primaryProviderId) ||
    !observed.providerIds.includes(scenario.runtime.fallbackProviderId)
  ) {
    throw blockedError("required_provider_unavailable");
  }
  if (
    !Array.isArray(observed.toolIds) ||
    scenario.runtime.requiredToolIds.some((toolId) => !observed.toolIds.includes(toolId))
  ) {
    throw blockedError("required_tool_unavailable");
  }
  if (observed.restartSupported !== true) throw blockedError("runtime_restart_unsupported");
  return observed;
}

function diagnosticResult(status, blocker = "") {
  return {
    caseId: CASE_ID,
    status,
    ...(blocker ? { blocker } : {}),
    releaseReady: false,
    receiptEligible: false,
    releaseLabel: RELEASE_LABEL,
  };
}

async function executeInstalledJourney({ driver, scenario, fixtures, environment = process.env }) {
  const evidence = {};
  let telegramTouched = false;
  let result;
  try {
    evidence.identity = await driver.preflightInstalledCandidate();
    if (
      evidence.identity?.verified !== true ||
      !SHA256.test(String(evidence.identity.candidateDigest || "")) ||
      !SHA256.test(String(evidence.identity.artifactDigest || ""))
    ) {
      throw blockedError("installed_candidate_identity_unproven");
    }
    evidence.telegramIdentity = assertOwnerSafeTelegramIdentity(
      scenario,
      environment,
      await driver.probeTelegramIdentity(),
    );
    evidence.capabilities = assertRequiredCapabilities(await driver.probeRequiredCapabilities(), scenario);
    telegramTouched = true;
    evidence.trigger = await driver.sendGroupedTelegramAttachments(fixtures, scenario);
    if (evidence.trigger?.visible !== true || evidence.trigger.groupCount !== 1 || evidence.trigger.urlVisible !== true) {
      throw blockedError("grouped_telegram_user_trigger_unavailable");
    }
    evidence.ingress = await driver.observeTelegramIngress(evidence.trigger);
    if (evidence.ingress?.ownerId !== scenario.owner.ownerId || evidence.ingress.logicalTurnCount !== 1) {
      throw blockedError("exactly_one_owner_scoped_telegram_turn_required");
    }
    evidence.mission = assessOwnerScopedMission(await driver.observeOwnerScopedMission(evidence.ingress), scenario);
    evidence.workerInputs = await driver.observeWorkerMaterialization(evidence.mission, evidence.ingress);
    evidence.parity = assessOrderedInputParity({
      scenario,
      expected: fixtures,
      uploads: evidence.ingress.uploads,
      workerInputs: evidence.workerInputs,
    });
    evidence.control = await driver.steerMission(evidence.mission, scenario.mission.controlInstruction);
    assertMissionScope(evidence.control, evidence.mission, "worker_control_scope_mismatch");
    if (evidence.control.accepted !== true) throw blockedError("worker_control_receipt_unavailable");
    evidence.brokerReceipts = await driver.observeAuthorizedBrokerReceipts(evidence.mission, evidence.parity);
    evidence.broker = assessAuthorizedBrokerReceipts(
      evidence.brokerReceipts,
      scenario,
      evidence.mission,
      evidence.parity.inputManifestSha256,
    );
    evidence.activeFallback = await driver.observeProviderFallback(
      evidence.mission,
      evidence.parity,
      "before_restart",
    );
    evidence.activeFallbackAttempt = assertActiveFallbackAttempt(
      evidence.activeFallback,
      scenario,
      evidence.mission,
      evidence.parity.inputManifestSha256,
    );
    evidence.restart = await driver.restartMissionRuntime(
      evidence.mission,
      evidence.parity,
      evidence.activeFallback,
    );
    evidence.restartCheck = assessRestartPreservation(
      evidence.restart,
      scenario,
      evidence.mission,
      evidence.parity.inputManifestSha256,
    );
    evidence.fallback = await driver.observeProviderFallback(
      evidence.mission,
      evidence.parity,
      "after_restart",
    );
    evidence.fallbackCheck = assessProviderFallback(
      evidence.fallback,
      scenario,
      evidence.mission,
      evidence.parity.inputManifestSha256,
    );
    evidence.artifact = await driver.openDeliveredArtifact(evidence.mission);
    evidence.artifactCheck = assessDeliveredArtifact(evidence.artifact, scenario, evidence.mission);
    evidence.trace = await driver.collectIndependentTrace(evidence.mission);
    assertMissionScope(evidence.trace, evidence.mission, "independent_trace_scope_mismatch");
    if (evidence.trace.verified !== true) throw blockedError("independent_runtime_trace_unavailable");
    result = { ...diagnosticResult("PRE_GATE_COMPLETE"), evidence };
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
    if (telegramTouched) {
      try {
        if (typeof driver?.cleanupSyntheticTelegramConversation !== "function") {
          throw blockedError("synthetic_telegram_cleanup_unavailable");
        }
        const cleanup = await driver.cleanupSyntheticTelegramConversation();
        if (
          cleanup?.cleaned !== true ||
          cleanup.ownerId !== scenario.owner.ownerId ||
          !String(cleanup.conversationId || "").trim()
        ) {
          throw blockedError("synthetic_telegram_cleanup_unverified");
        }
        evidence.syntheticCleanup = cleanup;
      } catch {
        cleanupFailure = true;
      }
    }
    try {
      if (typeof driver?.close === "function") await driver.close();
    } catch {
      cleanupFailure = true;
    }
    if (cleanupFailure) {
      result = {
        ...diagnosticResult("BLOCKED", "synthetic_telegram_cleanup_unverified"),
        evidence,
      };
    }
  }
  return result;
}

function buildPublicSummary({ result, qaRunId }) {
  const evidence = result?.evidence || {};
  const safeHash = (value) => (SHA256.test(String(value || "")) ? value : null);
  const safeCount = (value) => (Number.isSafeInteger(value) && value >= 0 ? value : 0);
  return {
    ...diagnosticResult(
      result?.status === "PRE_GATE_COMPLETE" ? "PRE_GATE_COMPLETE" : "BLOCKED",
      result?.blocker
        ? String(result.blocker).replace(/[^a-z0-9_:.-]/gi, "_").slice(0, 120)
        : "",
    ),
    qaRunIdHash: sha256(String(qaRunId || "")),
    candidateDigest: safeHash(evidence.identity?.candidateDigest),
    artifactDigest: safeHash(evidence.identity?.artifactDigest),
    inputCount: safeCount(evidence.parity?.inputCount),
    inputManifestSha256: safeHash(evidence.parity?.inputManifestSha256),
    brokerReceiptCount: safeCount(evidence.broker?.receiptCount),
    workerRuntimeOverlapMs: safeCount(evidence.mission?.overlapMs),
    deliveredArtifactSha256: safeHash(evidence.artifactCheck?.artifactSha256),
    deliveryCount: safeCount(evidence.artifactCheck?.deliveryCount),
  };
}

function parseRuntimeEnv(location) {
  if (!fs.existsSync(location)) return {};
  const metadata = fs.statSync(location);
  if (!metadata.isFile() || metadata.size > 256 * 1024) {
    throw blockedError("installed_runtime_environment_unavailable");
  }
  const values = {};
  for (const raw of fs.readFileSync(location, "utf8").split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const separator = line.indexOf("=");
    if (separator < 1) continue;
    const key = line.slice(0, separator).trim();
    let value = line.slice(separator + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    values[key] = value;
  }
  return values;
}

function loadReadOnlyRuntimeEnvironment(scenario, environment) {
  let runtimeRoot;
  try {
    runtimeRoot = fs.realpathSync(scenario.runtime.runtimeRoot);
  } catch {
    throw blockedError("installed_runtime_environment_unavailable");
  }
  const installed = {
    ...parseRuntimeEnv(path.join(LIBRECHAT_ROOT, ".env")),
    ...parseRuntimeEnv(path.join(runtimeRoot, "runtime.env")),
    ...parseRuntimeEnv(path.join(runtimeRoot, "runtime.local.env")),
    ...parseRuntimeEnv(path.join(runtimeRoot, "service-env", "librechat.env")),
    ...parseRuntimeEnv(path.join(runtimeRoot, "service-env", "librechat.owner.env")),
    ...parseRuntimeEnv(path.join(runtimeRoot, "service-env", "glasshive.env")),
  };
  const trustedSession = assertTrustedEphemeralSessionConfiguration(scenario, installed, environment);
  const values = {
    ...installed,
    ...environment,
    ...trustedSession,
  };
  if (!String(values.MONGO_URI || "").trim()) {
    throw blockedError("installed_mongo_uri_unavailable");
  }
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

function measureInstalledCandidate(scenario) {
  const gate = path.join(REPO_ROOT, "scripts", "viventium", "parallel_work_release_gate.py");
  const probe = [
    "import importlib.util,json,sys",
    "from pathlib import Path",
    "spec=importlib.util.spec_from_file_location('tgd010_installed_candidate_probe',sys.argv[1])",
    "module=importlib.util.module_from_spec(spec)",
    "sys.modules[spec.name]=module",
    "spec.loader.exec_module(module)",
    "identity=json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))",
    "installed=Path(sys.argv[3]).resolve(strict=True)",
    "owner_path=Path(sys.argv[4]).resolve(strict=True)",
    "runtime=Path(sys.argv[5]).resolve(strict=True)",
    "owner=json.loads(owner_path.read_text(encoding='utf-8'))",
    "active=module._runtime_owner_state_proves_active(installed,owner_path)",
    "root_matches=Path(str(owner.get('repoRoot') or '')).resolve(strict=True)==installed",
    "runtime_matches=Path(str(owner.get('runtimeDir') or '')).resolve(strict=True)==runtime",
    "candidate,artifact=module._qa_candidate_digests(identity)",
    "print(json.dumps({'verified':bool(active and root_matches and runtime_matches),'candidateDigest':candidate,'artifactDigest':artifact}))",
  ].join(";");
  const result = spawnSync(
    "python3",
    [
      "-c",
      probe,
      gate,
      scenario.runtime.artifactIdentityPath,
      scenario.runtime.installedRoot,
      scenario.runtime.runtimeOwnerStatePath,
      scenario.runtime.runtimeRoot,
    ],
    { encoding: "utf8", timeout: 30000, maxBuffer: 1024 * 1024 },
  );
  if (result.status !== 0) throw blockedError("installed_candidate_identity_unproven");
  try {
    const measured = JSON.parse(result.stdout);
    if (
      measured.verified !== true ||
      !SHA256.test(String(measured.candidateDigest || "")) ||
      !SHA256.test(String(measured.artifactDigest || ""))
    ) {
      throw blockedError("installed_candidate_identity_unproven");
    }
    return measured;
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

async function waitFor(check, { timeoutMs, blocker, pollMs = 250 }) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const value = await check();
    if (value) return value;
    await new Promise((resolve) => setTimeout(resolve, pollMs));
  }
  throw blockedError(blocker);
}

function exactRestartPlan(scenario) {
  let installedRoot;
  let executable;
  try {
    installedRoot = fs.realpathSync(scenario.runtime.installedRoot);
    executable = fs.realpathSync(scenario.restart.executable);
    const expected = fs.realpathSync(path.join(installedRoot, "bin", "viventium"));
    if (executable !== expected) throw blockedError("runtime_restart_unsupported");
    fs.accessSync(executable, fs.constants.X_OK);
  } catch (error) {
    if (error?.blocked) throw error;
    throw blockedError("runtime_restart_unsupported");
  }
  const argumentsValue = scenario.restart.arguments;
  const allowedArguments = new Set([
    "dev-runtime",
    "activate-current",
    "--validate",
    "--restart",
    "--allow-protected-folder",
    "--allow-dirty-local-testing",
  ]);
  if (
    argumentsValue[0] !== "dev-runtime" ||
    argumentsValue[1] !== "activate-current" ||
    !argumentsValue.includes("--validate") ||
    !argumentsValue.includes("--restart") ||
    argumentsValue.some((argument) => !allowedArguments.has(argument)) ||
    new Set(argumentsValue).size !== argumentsValue.length
  ) {
    throw blockedError("runtime_restart_unsupported");
  }
  if (!argumentsValue.includes("--allow-dirty-local-testing")) {
    throw blockedError("runtime_restart_dirty_checkout_protection_required");
  }
  return { executable, arguments: [...argumentsValue] };
}

function readOwnerScopedUploadBytes(file, ownerId, runtimeEnvironment, scenario) {
  const roots = [scenario.runtime.uploadRoot, runtimeEnvironment.WPR_LIBRECHAT_UPLOADS_ROOT]
    .map((value) => String(value || "").trim())
    .filter(Boolean);
  const fileId = String(file?.file_id || file?.fileId || "").trim();
  if (!fileId || !roots.length) throw blockedError("owner_scoped_upload_bytes_unavailable");
  const cleanOwnerId = String(ownerId);
  for (const root of roots) {
    let ownerRoot;
    try {
      ownerRoot = fs.realpathSync(path.join(root, cleanOwnerId));
    } catch {
      continue;
    }
    const candidates = [];
    const declared = String(file.filepath || "").split("?", 1)[0];
    if (declared.startsWith(`/uploads/${cleanOwnerId}/`)) {
      candidates.push(path.join(root, declared.slice("/uploads/".length)));
    }
    for (const entry of fs.readdirSync(ownerRoot, { withFileTypes: true })) {
      if (entry.isFile() && (entry.name === fileId || entry.name.startsWith(`${fileId}__`))) {
        candidates.push(path.join(ownerRoot, entry.name));
      }
    }
    const unique = [...new Set(candidates)];
    for (const candidate of unique) {
      try {
        const exact = fs.realpathSync(candidate);
        if (!pathInside(exact, ownerRoot) || fs.lstatSync(candidate).isSymbolicLink()) continue;
        const metadata = fs.statSync(exact);
        if (!metadata.isFile() || metadata.size <= 0 || metadata.size > MAX_PRIVATE_FILE_BYTES) continue;
        return fs.readFileSync(exact);
      } catch {
        continue;
      }
    }
  }
  throw blockedError("owner_scoped_upload_bytes_unavailable");
}

function sourceWindowFromIngress(trigger, userMessage, assistantMessage) {
  const startedAtMs = Number(trigger.submittedAtMs);
  const endedAtMs = new Date(assistantMessage?.createdAt || userMessage?.createdAt || 0).getTime();
  if (!Number.isFinite(startedAtMs) || !Number.isFinite(endedAtMs) || endedAtMs <= startedAtMs) {
    throw blockedError("telegram_source_runtime_window_unavailable");
  }
  return { startedAtMs, endedAtMs };
}

function ownerScopedMissionRows(store, ownerId, workRef, sourceWindow) {
  const rows = store.prepare(
    `SELECT d.owner_id AS ownerId, d.origin_ref AS originRef, d.work_ref AS workRef,
            d.current_run_id AS runRef, d.origin_surface AS originSurface,
            d.worker_id AS workerRef, w.workspace_root AS workspaceRoot,
            w.workspace_dir AS workspaceDirectory, w.bootstrap_bundle_json AS bootstrapBundle,
            r.state AS runState, r.runtime_invoked_at AS runtimeInvokedAt,
            r.ended_at AS runtimeEndedAt, r.provider_route_failure_class AS providerFailureClass,
            a.attempt_id AS attemptRef, a.runtime_invoked_at AS attemptInvokedAt,
            l.owner_id AS leaseOwnerId, l.worker_id AS leaseWorkerRef,
            l.run_id AS leaseRunRef, l.acquired_at AS leaseAcquiredAt,
            l.startup_confirmed_at AS leaseConfirmedAt, l.released_at AS leaseReleasedAt,
            l.pid AS leasePid, l.process_start_identity AS leaseProcessStartIdentity
       FROM delegations d
       JOIN workers w ON w.worker_id = d.worker_id AND w.owner_id = d.owner_id
       JOIN runs r ON r.run_id = d.current_run_id
       LEFT JOIN run_attempts a ON a.run_id = r.run_id AND a.attempt_number = (
         SELECT MAX(candidate.attempt_number) FROM run_attempts candidate WHERE candidate.run_id = r.run_id
       )
       LEFT JOIN host_run_leases l ON l.lease_id = a.lease_id
         AND l.owner_id = d.owner_id AND l.worker_id = d.worker_id AND l.run_id = r.run_id
      WHERE d.owner_id = ? AND d.work_ref = ?`,
  ).all(ownerId, workRef);
  return rows.map((row) => {
    const runtimeInvokedAtMs = new Date(row.runtimeInvokedAt || 0).getTime();
    const runtimeEndedAtMs = row.runtimeEndedAt
      ? new Date(row.runtimeEndedAt).getTime()
      : Date.now();
    return {
      ...row,
      sourceWindow,
      workerWindow: { startedAtMs: runtimeInvokedAtMs, endedAtMs: runtimeEndedAtMs },
      runtimeInvokedAtMs,
      lease: {
        ownerId: row.leaseOwnerId,
        workerRef: row.leaseWorkerRef,
        runRef: row.leaseRunRef,
        acquiredAtMs: new Date(row.leaseAcquiredAt || 0).getTime(),
        confirmedAtMs: new Date(row.leaseConfirmedAt || 0).getTime(),
        releasedAtMs: row.leaseReleasedAt ? new Date(row.leaseReleasedAt).getTime() : null,
      },
    };
  });
}

function parseJsonLine(raw) {
  const start = raw.indexOf("{");
  if (start < 0) return null;
  try {
    const value = JSON.parse(raw.slice(start));
    return value && typeof value === "object" && !Array.isArray(value) ? value : null;
  } catch {
    return null;
  }
}

function exactUploadedReferences(message) {
  const direct = Array.isArray(message?.files) ? message.files : [];
  const recorded = Array.isArray(message?.metadata?.viventium?.uploadedFiles)
    ? message.metadata.viventium.uploadedFiles
    : [];
  const candidates = direct.length ? direct : recorded;
  if (!candidates.length) throw blockedError("telegram_upload_ledger_unavailable");
  const references = candidates.map((item) => ({
    ...(item && typeof item === "object" && !Array.isArray(item) ? item : {}),
    fileId: String(typeof item === "string" ? item : item?.file_id || item?.fileId || "").trim(),
  }));
  if (
    references.some((item) => !item.fileId) ||
    new Set(references.map((item) => item.fileId)).size !== references.length
  ) {
    throw blockedError("telegram_upload_identity_missing");
  }
  return references;
}

async function createInstalledDriver({ scenario, args, environment, evidenceRoot, computerBridge }) {
  if (
    !computerBridge || typeof computerBridge.verify !== "function" ||
    computerBridge.provenance?.provider !== "@oai/sky"
  ) {
    throw blockedError("computer_desktop_driver_unavailable");
  }
  if (environment?.VIVENTIUM_QA_ALLOW_LOCAL_JWT !== "1") {
    throw blockedError("ephemeral_browser_session_requires_explicit_opt_in");
  }
  const runtimeEnvironment = loadReadOnlyRuntimeEnvironment(scenario, environment);
  const sessionArgs = ephemeralBrowserSessionArgs(scenario, args);
  assertEphemeralSessionSafety(sessionArgs, runtimeEnvironment);
  const restartPlan = exactRestartPlan(scenario);
  const { MongoClient } = require(path.join(LIBRECHAT_ROOT, "node_modules", "mongodb"));
  const { chromium } = require(path.join(LIBRECHAT_ROOT, "node_modules", "playwright"));
  const mongo = new MongoClient(runtimeEnvironment.MONGO_URI, { serverSelectionTimeoutMS: 5000 });
  const state = {
    database: null,
    ownerId: "",
    userObjectId: null,
    user: null,
    mapping: null,
    telegramChatBinding: null,
    agent: null,
    store: null,
    browser: null,
    page: null,
    trigger: null,
    ingress: null,
    conversationId: "",
    sourceWindow: null,
    traceBaselineBytes: 0,
    captures: [],
    ephemeralSessions: [],
    restartReadiness: null,
    desktopObservation: null,
    launchedAt: 0,
    mission: null,
    ingressRecords: [],
    createdConversation: null,
  };

  async function connectOwnerScopedRuntime() {
    await mongo.connect();
    const databaseName = new URL(runtimeEnvironment.MONGO_URI).pathname.replace(/^\//, "") || "LibreChatViventium";
    state.database = mongo.db(databaseName);
    const user = await state.database.collection("users").findOne(
      { email: scenario.owner.email },
      {
        projection: {
          _id: 1,
          email: 1,
          role: 1,
          username: 1,
          provider: 1,
          viventiumApprovalStatus: 1,
          locked: 1,
          isLocked: 1,
          banned: 1,
        },
      },
    );
    const selectedOwnerId = assertSelectedQaAccount(sessionArgs, runtimeEnvironment, user);
    if (
      selectedOwnerId !== scenario.owner.ownerId ||
      String(user.email || "").trim().toLowerCase() !== scenario.owner.email
    ) {
      throw blockedError("synthetic_linked_owner_unavailable");
    }
    state.ownerId = selectedOwnerId;
    state.userObjectId = user._id;
    state.user = user;
    state.mapping = await state.database.collection("telegramusermappings").findOne(
      { telegramUserId: scenario.owner.telegramUserId, libreChatUserId: user._id },
      { projection: { telegramUserId: 1, libreChatUserId: 1, telegramUsername: 1 } },
    );
    if (
      !state.mapping ||
      String(state.mapping.libreChatUserId) !== state.ownerId ||
      state.mapping.telegramUserId !== scenario.owner.telegramUserId
    ) {
      throw blockedError("owner_safe_telegram_identity_unavailable");
    }
    state.telegramChatBinding = await state.database.collection("viventiumtelegramingressevents").findOne(
      {
        telegramUserId: scenario.owner.telegramUserId,
        telegramChatId: scenario.owner.telegramChatId,
      },
      { projection: { telegramUserId: 1, telegramChatId: 1 } },
    );
    if (
      !state.telegramChatBinding ||
      state.telegramChatBinding.telegramUserId !== state.mapping.telegramUserId ||
      state.telegramChatBinding.telegramChatId !== scenario.owner.telegramChatId
    ) {
      throw blockedError("owner_safe_telegram_identity_unavailable");
    }
    state.agent = await state.database.collection("agents").findOne(
      { id: scenario.runtime.mainAgentId },
      {
        projection: {
          id: 1,
          provider: 1,
          model: 1,
          fallback_llm_provider: 1,
          fallback_llm_model: 1,
          tools: 1,
          glasshive_options: 1,
        },
      },
    );
    if (!state.agent?.id) throw blockedError("configured_main_agent_unavailable");
    state.store = openReadOnlyGlassHiveStore(scenario.runtime.glassHiveDbPath);
  }

  async function ensureHeadedBrowser() {
    if (state.page) return state.page;
    state.browser = await chromium.launch({ channel: "chrome", headless: false });
    const context = await state.browser.newContext({ viewport: { width: 1440, height: 1080 } });
    const page = await context.newPage();
    page.setDefaultTimeout(Math.min(args.timeoutMs, 30000));
    const session = await createEphemeralBrowserSession({
      db: state.database,
      user: state.user,
      args: sessionArgs,
      env: runtimeEnvironment,
    });
    state.ephemeralSessions.push(session);
    await context.addCookies(session.cookies);
    const [response] = await Promise.all([
      page.waitForResponse(
        (item) => item.request().method() === "POST" && new URL(item.url()).pathname === "/api/auth/refresh",
        { timeout: Math.min(args.timeoutMs, 30000) },
      ),
      page.goto(
        `${scenario.runtime.clientUrl}/c/new?agent_id=${encodeURIComponent(scenario.runtime.mainAgentId)}`,
        { waitUntil: "domcontentloaded" },
      ),
    ]);
    if (response.status() !== 200) throw blockedError("ephemeral_browser_session_refresh_rejected");
    await page.waitForURL(
      (location) => location.pathname !== "/login",
      { timeout: Math.min(args.timeoutMs, 30000) },
    );
    state.page = page;
    return page;
  }

  async function inspectTelegramUi() {
    const observed = await readComputerDesktopState(computerBridge, scenario);
    if (typeof observed.text !== "string" || Buffer.byteLength(observed.text, "utf8") > 2 * 1024 * 1024) {
      throw blockedError("computer_desktop_observation_unavailable");
    }
    const labels = observed.text.split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
    const selection = assertActiveSelectedTelegramContext(observed, scenario);
    state.desktopObservation = observed;
    return {
      source: "telegram_desktop_accessibility",
      bundleId: observed.app,
      accountLabel: selection.account.label,
      chatLabel: selection.chat.label,
      telegramUserId: String(selection.account.telegramUserId),
      telegramChatId: String(selection.chat.telegramChatId),
      ownerId: selection.account.ownerId,
      linkedOwnerId: selection.chat.ownerId,
      accountVisible: selection.account.selected,
      chatVisible: selection.chat.selected,
      activeSelectionVerified: true,
      activeSelectionSha256: sha256(canonicalJson(selection)),
      visibleText: labels,
    };
  }

  function scenarioCaption() {
    const captioned = scenario.inputs.find((input) => String(input.caption || "").trim());
    if (!captioned) throw blockedError("captioned_media_group_required");
    return `${captioned.caption} [group:${captioned.groupId}] ${scenario.mission.marker}: ` +
      "Delegate these exact ordered attachments to one Worker Bee. " +
      `Input identities: ${scenario.inputs.map((input) => input.visibleIdentity).join(", ")}. ` +
      `Use the authorized source ${scenario.mission.sourceUrl}. ` +
      `Create and deliver ${scenario.mission.outputIdentity}.`;
  }

  function materializedWorkerFiles(mission, ingress) {
    let bundle;
    try {
      bundle = JSON.parse(String(mission.bootstrapBundle || "{}"));
    } catch {
      throw blockedError("worker_upload_projection_unavailable");
    }
    const selected = bundle?.viventium_delegation_packet?.selected_files;
    const files = Array.isArray(bundle?.files)
      ? bundle.files.filter((item) => String(item?.path || "").startsWith("uploads/"))
      : [];
    if (
      !Array.isArray(selected) ||
      selected.length !== ingress.uploads.length ||
      files.length !== ingress.uploads.length ||
      selected.some((item, index) => item?.ordinal !== index || item.ref !== ingress.uploads[index].fileId)
    ) {
      throw blockedError("worker_upload_projection_unavailable");
    }
    let workspace;
    try {
      workspace = fs.realpathSync(mission.workspaceRoot || mission.workspaceDirectory);
    } catch {
      throw blockedError("worker_workspace_unavailable");
    }
    return files.map((file, index) => {
      const source = ingress.uploads[index];
      let exact;
      try {
        exact = fs.realpathSync(path.join(workspace, file.path));
      } catch {
        throw blockedError("worker_materialized_file_unavailable");
      }
      if (!pathInside(exact, workspace) || !fs.statSync(exact).isFile()) {
        throw blockedError("worker_materialized_file_unavailable");
      }
      const bytes = fs.readFileSync(exact);
      return {
        ...source,
        ownerId: mission.ownerId,
        workRef: mission.workRef,
        runRef: mission.runRef,
        bytes,
        sha256: sha256(bytes),
        sizeBytes: bytes.length,
      };
    });
  }

  function missionGrant(mission) {
    try {
      const bundle = JSON.parse(String(mission.bootstrapBundle || "{}"));
      const broker = bundle.glasshive_capability_broker;
      if (!broker || !String(broker.grant_id || "").trim()) {
        throw blockedError("authorized_capability_broker_unavailable");
      }
      return broker;
    } catch (error) {
      if (error?.blocked) throw error;
      throw blockedError("authorized_capability_broker_unavailable");
    }
  }

  function readBrokerTrace(mission, parity) {
    const grant = missionGrant(mission);
    let bytes;
    try {
      const metadata = fs.statSync(scenario.runtime.coreTracePath);
      if (!metadata.isFile() || metadata.size > 32 * 1024 * 1024) {
        throw blockedError("authorized_broker_trace_unavailable");
      }
      bytes = fs.readFileSync(scenario.runtime.coreTracePath).subarray(state.traceBaselineBytes);
    } catch (error) {
      if (error?.blocked) throw error;
      throw blockedError("authorized_broker_trace_unavailable");
    }
    const allowedHostTools = new Set(Array.isArray(grant.allowed_host_tools) ? grant.allowed_host_tools : []);
    const rows = [];
    for (const line of bytes.toString("utf8").split(/\r?\n/)) {
      const item = parseJsonLine(line);
      if (!item || String(item.userId || "") !== mission.ownerId || String(item.grantId || "") !== grant.grant_id) {
        continue;
      }
      const toolId = String(item.toolId || item.toolName || "").trim();
      if (!scenario.runtime.requiredToolIds.includes(toolId)) continue;
      const receiptId = String(item.receiptId || item.invocationId || item.toolCallId || "").trim();
      if (!receiptId) throw blockedError("authorized_tool_receipt_unavailable");
      rows.push({
        receiptId,
        ownerId: mission.ownerId,
        workRef: mission.workRef,
        runRef: mission.runRef,
        toolId,
        authorized: allowedHostTools.has(toolId) || item.authorizationVerified === true,
        state: item.outcome === "success" || item.state === "completed" ? "completed" : "failed",
        inputManifestSha256: String(item.inputManifestSha256 || ""),
        observedAtMs: new Date(item.timestamp || item.observedAt || 0).getTime(),
      });
    }
    if (rows.some((row) => row.inputManifestSha256 !== parity.inputManifestSha256)) {
      throw blockedError("broker_receipt_input_manifest_mismatch");
    }
    return rows;
  }

  function readFallbackRows(mission, parity) {
    const attempts = state.store.prepare(
      `SELECT a.attempt_id AS attemptId, a.attempt_number AS ordinal, a.state,
              a.terminal_reason AS terminalReason,
              a.runtime_invoked_at AS runtimeInvokedAt,
              a.lease_id AS leaseId,
              l.owner_id AS leaseOwnerId, l.worker_id AS leaseWorkerRef,
              l.run_id AS leaseRunRef, l.acquired_at AS leaseAcquiredAt,
              l.startup_confirmed_at AS leaseConfirmedAt,
              l.released_at AS leaseReleasedAt, l.pid AS leasePid,
              l.process_start_identity AS leaseProcessStartIdentity
         FROM run_attempts a
         LEFT JOIN host_run_leases l ON l.lease_id = a.lease_id
        WHERE a.run_id = ? ORDER BY a.attempt_number`,
    ).all(mission.runRef);
    const switches = state.store.prepare(
      `SELECT payload_json AS payload FROM events
        WHERE worker_id = ? AND run_id = ? AND event_type = 'run.provider_route_switched'
        ORDER BY created_at`,
    ).all(mission.workerRef, mission.runRef);
    if (attempts.length < 2 || attempts.length > 8 || switches.length !== 1) {
      throw blockedError("provider_fallback_evidence_unavailable");
    }
    const providerEvents = state.store.prepare(
      `SELECT payload_json AS payload FROM work_trace_events
        WHERE owner_id = ? AND work_ref = ? AND run_id = ?
          AND event_type = 'provider.invoked'
        ORDER BY sequence`,
    ).all(mission.ownerId, mission.workRef, mission.runRef);
    const providerTrace = providerEvents.map((event) => {
      try {
        return JSON.parse(String(event.payload || "{}"));
      } catch {
        throw blockedError("fallback_input_manifest_evidence_unavailable");
      }
    });
    const observedManifests = observedFallbackAttemptManifests(
      attempts,
      providerTrace,
      parity.inputManifestSha256,
    );
    const fallbackIndex = attempts.length - 1;
    const fallbackAttempt = attempts[fallbackIndex];
    let switched;
    try {
      switched = JSON.parse(String(switches[0].payload || "{}"));
    } catch {
      throw blockedError("provider_fallback_evidence_unavailable");
    }
    const structuredFailure = String(switched.failureClass || "");
    const primaryState = structuredFailure === "provider_quota_exhausted"
      ? "quota_cooldown"
      : structuredFailure === "rate_limited"
        ? "rate_limited"
        : structuredFailure === "provider_unavailable"
          ? "provider_unavailable"
          : "unknown";
    return {
      ownerId: mission.ownerId,
      workRef: mission.workRef,
      runRef: mission.runRef,
      attempts: [
        {
          attemptId: attempts[0].attemptId,
          providerId: String(switched.fromProfile || ""),
          state: primaryState,
          inputManifestSha256: observedManifests[0],
        },
        {
          attemptId: fallbackAttempt.attemptId,
          providerId: String(switched.toProfile || ""),
          state: fallbackAttempt.state,
          inputManifestSha256: observedManifests[fallbackIndex],
          runtimeInvokedAtMs: new Date(fallbackAttempt.runtimeInvokedAt || 0).getTime(),
          lease: {
            leaseId: String(fallbackAttempt.leaseId || ""),
            ownerId: fallbackAttempt.leaseOwnerId,
            workerRef: fallbackAttempt.leaseWorkerRef,
            runRef: fallbackAttempt.leaseRunRef,
            acquiredAtMs: new Date(fallbackAttempt.leaseAcquiredAt || 0).getTime(),
            confirmedAtMs: new Date(fallbackAttempt.leaseConfirmedAt || 0).getTime(),
            releasedAtMs: fallbackAttempt.leaseReleasedAt
              ? new Date(fallbackAttempt.leaseReleasedAt).getTime()
              : null,
            pid: fallbackAttempt.leasePid,
            processStartIdentity: String(fallbackAttempt.leaseProcessStartIdentity || ""),
          },
        },
      ],
    };
  }

  function readRuntimeIdentity() {
    try {
      const owner = JSON.parse(fs.readFileSync(scenario.runtime.runtimeOwnerStatePath, "utf8"));
      if (!owner.ownerPid || !owner.ownerProcessStartedAt) {
        throw blockedError("runtime_restart_identity_unavailable");
      }
      return sha256(canonicalJson({ pid: owner.ownerPid, startedAt: owner.ownerProcessStartedAt }));
    } catch (error) {
      if (error?.blocked) throw error;
      throw blockedError("runtime_restart_identity_unavailable");
    }
  }

  function readCoordinatedRestartStatus() {
    const result = spawnSync(restartPlan.executable, ["qa-control", "status"], {
      cwd: scenario.runtime.installedRoot,
      env: runtimeEnvironment,
      encoding: "utf8",
      timeout: Math.min(args.timeoutMs, 30000),
      maxBuffer: 1024 * 1024,
    });
    if (result.status !== 0) throw blockedError("runtime_restart_unsupported");
    try {
      return assessCoordinatedRestartStatus(JSON.parse(String(result.stdout || "")), scenario.restart);
    } catch (error) {
      if (error?.blocked) throw error;
      throw blockedError("runtime_restart_unsupported");
    }
  }

  function observedWorkerProcessIdentity(mission) {
    const pid = Number(mission?.leasePid);
    const started = String(mission?.leaseProcessStartIdentity || "").trim();
    if (!Number.isSafeInteger(pid) || pid <= 1 || !started) {
      throw blockedError("runtime_restart_worker_identity_unavailable");
    }
    return sha256(canonicalJson({ pid, started }));
  }

  async function privateBrowserScreenshot(name, page = state.page) {
    const bytes = await page.screenshot({ fullPage: true });
    const written = writePrivateEvidence(evidenceRoot, name, bytes);
    state.captures.push(written);
    return written;
  }

  const driver = {
    async preflightInstalledCandidate() {
      const identity = measureInstalledCandidate(scenario);
      await connectOwnerScopedRuntime();
      try {
        state.traceBaselineBytes = fs.statSync(scenario.runtime.coreTracePath).size;
      } catch {
        throw blockedError("authorized_broker_trace_unavailable");
      }
      if (!String(scenario.telegram.downloadDirectory || "").trim()) {
        throw blockedError("telegram_artifact_download_root_unavailable");
      }
      return identity;
    },

    async probeTelegramIdentity() {
      return await inspectTelegramUi();
    },

    async probeRequiredCapabilities() {
      await ensureHeadedBrowser();
      state.restartReadiness = readCoordinatedRestartStatus();
      const providerIds = [
        state.agent.provider,
        state.agent.fallback_llm_provider,
        state.agent.glasshive_options?.fallback_profile,
      ].map((value) => String(value || "").trim()).filter(Boolean);
      const toolIds = (Array.isArray(state.agent.tools) ? state.agent.tools : [])
        .map((item) => String(typeof item === "string" ? item : item?.id || item?.name || "").trim())
        .filter(Boolean);
      return {
        providerIds: [...new Set(providerIds)],
        toolIds: [...new Set(toolIds)],
        restartSupported: Boolean(restartPlan.executable && state.restartReadiness),
      };
    },

    async sendGroupedTelegramAttachments(fixtures) {
      assertOwnerSafeTelegramIdentity(scenario, environment, await inspectTelegramUi());
      const caption = scenarioCaption();
      const submittedAtMs = Date.now();
      state.launchedAt = submittedAtMs;
      assertTelegramMutationConsent(args, environment);
      const result = await performComputerDesktopAction(computerBridge, scenario, {
        action: "telegram.send_grouped_attachments",
        caption,
        attachments: fixtures.map((item) => ({
          family: item.family,
          filename: item.filename,
          position: item.position,
          sha256: item.sha256,
          sizeBytes: item.sizeBytes,
          sourcePath: item.sourcePath,
          visibleIdentity: item.visibleIdentity,
        })),
      });
      if (result.status !== "sent") throw blockedError("grouped_telegram_user_trigger_unavailable");
      const visible = await inspectTelegramUi();
      const capture = writeObservedComputerCapture(
        evidenceRoot,
        `${args.qaRunId}-telegram-sent.png`,
        state.desktopObservation,
      );
      state.captures.push(capture);
      const visibleGroups = visible.visibleText.filter((item) =>
        item.includes(scenario.mission.marker) && item.includes(scenario.mission.sourceUrl),
      ).length;
      state.trigger = {
        submittedAtMs,
        caption,
        visible: visible.chatVisible,
        groupCount: visibleGroups,
        urlVisible: visible.visibleText.some((item) => item.includes(scenario.mission.sourceUrl)),
      };
      return state.trigger;
    },

    async observeTelegramIngress(trigger) {
      return waitFor(async () => {
        const events = await state.database.collection("viventiumtelegramingressevents").find({
          telegramUserId: scenario.owner.telegramUserId,
          telegramChatId: scenario.owner.telegramChatId,
          createdAt: { $gte: new Date(trigger.submittedAtMs - 1000) },
        }).project({
          conversationId: 1,
          createdAt: 1,
          traceId: 1,
          telegramUserId: 1,
          telegramChatId: 1,
          telegramMessageId: 1,
        }).limit(2).toArray();
        if (events.length > 1) throw blockedError("telegram_group_created_multiple_turns");
        if (events.length !== 1 || !events[0].conversationId) return null;
        const userMessage = await state.database.collection("messages").findOne({
          user: state.ownerId,
          conversationId: events[0].conversationId,
          isCreatedByUser: true,
          text: trigger.caption,
          createdAt: { $gte: new Date(trigger.submittedAtMs - 1000) },
        });
        if (!userMessage?.messageId) return null;
        const assistant = await state.database.collection("messages").findOne({
          user: state.ownerId,
          conversationId: userMessage.conversationId,
          parentMessageId: userMessage.messageId,
          isCreatedByUser: false,
          unfinished: false,
        });
        if (!assistant?.messageId) return null;
        const references = exactUploadedReferences(userMessage);
        const fileIds = references.map((item) => item.fileId);
        if (fileIds.length !== scenario.inputs.length) throw blockedError("telegram_upload_count_mismatch");
        const rows = await state.database.collection("files").find({
          file_id: { $in: fileIds },
          $or: [{ user: state.ownerId }, { user: state.userObjectId }],
        }).toArray();
        if (rows.length !== fileIds.length) throw blockedError("telegram_upload_owner_mismatch");
        const observedUi = await inspectTelegramUi();
        assertOwnerSafeTelegramIdentity(scenario, environment, observedUi);
        const uploads = references.map((reference, position) => {
          const fileId = reference.fileId;
          const file = rows.find((row) => row.file_id === fileId);
          if (!file) throw blockedError("telegram_upload_identity_missing");
          const bytes = readOwnerScopedUploadBytes(file, state.ownerId, runtimeEnvironment, scenario);
          const metadata = deriveObservedUploadMetadata({
            file,
            reference,
            userMessage,
            visibleText: observedUi.visibleText,
            expected: scenario.inputs[position],
            position,
          });
          return {
            ownerId: state.ownerId,
            workRef: "",
            runRef: "",
            fileId,
            filename: String(file.filename || file.originalname || ""),
            ...metadata,
            bytes,
            sha256: sha256(bytes),
            sizeBytes: bytes.length,
          };
        });
        state.conversationId = String(userMessage.conversationId);
        state.ingressRecords = events;
        const conversation = await state.database.collection("conversations").findOne({
          user: state.ownerId,
          conversationId: state.conversationId,
        });
        if (
          conversation &&
          new Date(conversation.createdAt || 0).getTime() >= state.launchedAt
        ) {
          state.createdConversation = conversation;
        }
        state.sourceWindow = sourceWindowFromIngress(trigger, userMessage, assistant);
        state.ingress = {
          ownerId: state.ownerId,
          logicalTurnCount: 1,
          uploads,
          userMessageId: String(userMessage.messageId),
          assistantMessageId: String(assistant.messageId),
          sourceWindow: state.sourceWindow,
        };
        return state.ingress;
      }, { timeoutMs: args.timeoutMs, blocker: "owner_scoped_telegram_ingress_unavailable" });
    },

    async observeOwnerScopedMission(ingress) {
      return waitFor(async () => {
        const bindings = await state.database.collection("viventium_glasshive_callback_bindings").find({
          ownerId: state.ownerId,
          conversationId: state.conversationId,
          createdAt: { $gte: new Date(state.trigger.submittedAtMs - 1000) },
        }).project({ workRef: 1, originRef: 1 }).limit(2).toArray();
        if (bindings.length > 1) throw blockedError("exactly_one_owner_scoped_mission_required");
        if (bindings.length !== 1 || !bindings[0].workRef) return null;
        const missions = ownerScopedMissionRows(
          state.store,
          state.ownerId,
          String(bindings[0].workRef),
          ingress.sourceWindow,
        );
        if (missions.length !== 1 || !missions[0].runtimeInvokedAtMs) return null;
        if (["failed", "cancelled"].includes(missions[0].runState)) {
          throw blockedError("intended_worker_runtime_failed");
        }
        for (const upload of ingress.uploads) {
          upload.workRef = missions[0].workRef;
          upload.runRef = missions[0].runRef;
        }
        state.mission = missions[0];
        return missions;
      }, { timeoutMs: args.timeoutMs, blocker: "owner_scoped_worker_runtime_unavailable" });
    },

    async observeWorkerMaterialization(mission, ingress) {
      return waitFor(async () => {
        try {
          return materializedWorkerFiles(mission, ingress);
        } catch (error) {
          if (error?.message === "worker_materialized_file_unavailable") return null;
          throw error;
        }
      }, { timeoutMs: args.timeoutMs, blocker: "worker_materialized_file_unavailable" });
    },

    async steerMission(mission, instruction) {
      const page = await ensureHeadedBrowser();
      await page.goto(`${scenario.runtime.clientUrl}/c/${encodeURIComponent(state.conversationId)}`, {
        waitUntil: "domcontentloaded",
      });
      const card = page.locator("li").filter({ hasText: scenario.mission.marker }).first();
      await card.waitFor({ state: "visible", timeout: Math.min(args.timeoutMs, 30000) });
      await card.getByLabel("Instruction").fill(instruction);
      await card.getByRole("button", { name: "Steer", exact: true }).click();
      return waitFor(async () => {
        const rows = state.store.prepare(
          `SELECT owner_id AS ownerId, work_ref AS workRef,
                  source_run_id AS runRef, action, status
             FROM active_work_action_uses
            WHERE owner_id = ? AND work_ref = ? AND action = 'steer'`,
        ).all(mission.ownerId, mission.workRef);
        if (rows.length > 1) throw blockedError("duplicate_worker_control_detected");
        if (rows.length !== 1 || !["accepted", "completed"].includes(rows[0].status)) return null;
        return {
          ownerId: rows[0].ownerId,
          workRef: rows[0].workRef,
          runRef: rows[0].runRef,
          accepted: true,
        };
      }, { timeoutMs: args.timeoutMs, blocker: "worker_control_receipt_unavailable" });
    },

    async observeAuthorizedBrokerReceipts(mission, parity) {
      return waitFor(async () => {
        const receipts = readBrokerTrace(mission, parity);
        if (receipts.length > scenario.runtime.requiredToolIds.length) {
          throw blockedError("duplicate_authorized_tool_receipt");
        }
        return receipts.length === scenario.runtime.requiredToolIds.length ? receipts : null;
      }, { timeoutMs: args.timeoutMs, blocker: "required_tool_receipt_unavailable" });
    },

    async observeProviderFallback(mission, parity, stage = "before_restart") {
      return waitFor(async () => {
        try {
          const fallback = readFallbackRows(mission, parity);
          const terminalCount = await state.database.collection("viventiumglasshivecallbackdeliveries")
            .countDocuments({
              userId: mission.ownerId,
              workRef: mission.workRef,
              runId: mission.runRef,
              event: { $in: ["run.completed", "run.failed", "run.cancelled"] },
            });
          const artifacts = state.store.prepare(
            `SELECT COUNT(*) AS count FROM work_trace_events
              WHERE owner_id = ? AND work_ref = ? AND run_id = ?
                AND event_type = 'artifact.observed'`,
          ).get(mission.ownerId, mission.workRef, mission.runRef);
          fallback.terminalCallbackObserved = Number(terminalCount) > 0;
          fallback.artifactObserved = Number(artifacts?.count || 0) > 0;
          if (stage === "after_restart") {
            return fallback.attempts[1].state === "completed" ? fallback : null;
          }
          if (fallback.attempts[1].state === "completed") {
            throw blockedError("fallback_attempt_not_active");
          }
          if (fallback.attempts[1].state !== "running") return null;
          assertActiveFallbackAttempt(
            fallback,
            scenario,
            mission,
            parity.inputManifestSha256,
          );
          return fallback;
        } catch (error) {
          if (error?.message === "provider_fallback_evidence_unavailable") return null;
          throw error;
        }
      }, { timeoutMs: args.timeoutMs, blocker: "provider_fallback_evidence_unavailable" });
    },

    async restartMissionRuntime(mission, parity, beforeFallback) {
      const requestedAttempt = assertActiveFallbackAttempt(
        beforeFallback,
        scenario,
        mission,
        parity.inputManifestSha256,
      );
      const currentFallback = await driver.observeProviderFallback(mission, parity, "before_restart");
      const currentAttempt = assertActiveFallbackAttempt(
        currentFallback,
        scenario,
        mission,
        parity.inputManifestSha256,
      );
      if (currentAttempt.attemptId !== requestedAttempt.attemptId) {
        throw blockedError("fallback_attempt_changed_before_restart");
      }
      const beforeServiceReadiness = readCoordinatedRestartStatus();
      const beforeWorkerIdentity = observedWorkerProcessIdentity({
        leasePid: currentAttempt.lease.pid,
        leaseProcessStartIdentity: currentAttempt.lease.processStartIdentity,
      });
      const beforeRuntimeIdentity = readRuntimeIdentity();
      const beforeFiles = materializedWorkerFiles(mission, state.ingress);
      const before = assessOrderedInputParity({
        scenario,
        expected: inspectSyntheticInputs(scenario, { evidenceRoot }),
        uploads: state.ingress.uploads,
        workerInputs: beforeFiles,
      });
      state.store.close();
      state.store = null;
      const restarted = spawnSync(restartPlan.executable, restartPlan.arguments, {
        cwd: scenario.runtime.installedRoot,
        env: runtimeEnvironment,
        encoding: "utf8",
        timeout: Math.min(args.timeoutMs, 180000),
        maxBuffer: 2 * 1024 * 1024,
      });
      if (restarted.status !== 0) throw blockedError("runtime_restart_recovery_unavailable");
      const afterRuntimeIdentity = await waitFor(async () => {
        try {
          const current = readRuntimeIdentity();
          return current !== beforeRuntimeIdentity ? current : null;
        } catch {
          return null;
        }
      }, { timeoutMs: args.timeoutMs, blocker: "runtime_restart_identity_unavailable" });
      const afterServiceReadiness = await waitFor(async () => {
        try {
          const current = readCoordinatedRestartStatus();
          if (
            current.caseId !== beforeServiceReadiness.caseId ||
            current.sessionRef !== beforeServiceReadiness.sessionRef ||
            current.serviceAckDigest === beforeServiceReadiness.serviceAckDigest
          ) {
            return null;
          }
          return current;
        } catch {
          return null;
        }
      }, { timeoutMs: args.timeoutMs, blocker: "runtime_restart_service_acknowledgements_unavailable" });
      state.store = openReadOnlyGlassHiveStore(scenario.runtime.glassHiveDbPath);
      const recovered = ownerScopedMissionRows(state.store, mission.ownerId, mission.workRef, mission.sourceWindow);
      if (recovered.length !== 1 || recovered[0].runRef !== mission.runRef) {
        throw blockedError("restart_mission_scope_mismatch");
      }
      const afterWorkerIdentity = observedWorkerProcessIdentity(recovered[0]);
      if (afterWorkerIdentity === beforeWorkerIdentity) {
        throw blockedError("runtime_restart_worker_identity_unavailable");
      }
      const afterFiles = materializedWorkerFiles(recovered[0], state.ingress);
      const after = assessOrderedInputParity({
        scenario,
        expected: inspectSyntheticInputs(scenario, { evidenceRoot }),
        uploads: state.ingress.uploads,
        workerInputs: afterFiles,
      });
      return {
        ownerId: mission.ownerId,
        workRef: mission.workRef,
        runRef: mission.runRef,
        supported: true,
        performed: true,
        recovered: true,
        beforeRuntimeIdentity,
        afterRuntimeIdentity,
        beforeInputManifestSha256: before.inputManifestSha256,
        afterInputManifestSha256: after.inputManifestSha256,
        services: REQUIRED_RESTART_SERVICES.filter((service) =>
          service === "worker" || afterServiceReadiness.services.includes(service),
        ),
      };
    },

    async openDeliveredArtifact(mission) {
      const deliveries = await waitFor(async () => {
        const rows = await state.database.collection("viventiumglasshivecallbackdeliveries").find({
          userId: mission.ownerId,
          workRef: mission.workRef,
          runId: mission.runRef,
          surface: "telegram",
          event: "run.completed",
          telegramUserId: scenario.owner.telegramUserId,
          telegramChatId: scenario.owner.telegramChatId,
        }).project({
          deliveryId: 1,
          status: 1,
          userId: 1,
          workRef: 1,
          telegramSentMessageIds: 1,
          traceIdentityVerified: 1,
          callbackMessageId: 1,
        }).limit(2).toArray();
        if (rows.length > 1) throw blockedError("duplicate_telegram_delivery_detected");
        if (rows.length !== 1 || rows[0].status !== "sent") return null;
        if (
          rows[0].traceIdentityVerified !== true ||
          !Array.isArray(rows[0].telegramSentMessageIds) ||
          rows[0].telegramSentMessageIds.length !== 1
        ) {
          throw blockedError("verified_telegram_delivery_receipt_unavailable");
        }
        return rows;
      }, { timeoutMs: args.timeoutMs, blocker: "verified_telegram_delivery_receipt_unavailable" });

      const page = await ensureHeadedBrowser();
      await page.goto(`${scenario.runtime.clientUrl}/c/${encodeURIComponent(state.conversationId)}`, {
        waitUntil: "domcontentloaded",
      });
      const card = page.locator("li").filter({ hasText: scenario.mission.marker }).first();
      await card.waitFor({ state: "visible", timeout: Math.min(args.timeoutMs, 30000) });
      await privateBrowserScreenshot(`${args.qaRunId}-active-work.png`, page);
      const link = card.getByRole("link", { name: `Open ${scenario.mission.outputIdentity}` });
      await link.waitFor({ state: "visible", timeout: Math.min(args.timeoutMs, 30000) });
      const [response] = await Promise.all([
        page.waitForResponse(
          (item) => item.request().method() === "GET" && item.url().includes(encodeURIComponent(scenario.mission.outputIdentity)),
          { timeout: Math.min(args.timeoutMs, 30000) },
        ),
        link.click(),
      ]);
      if (response.status() !== 200) throw blockedError("active_work_artifact_download_unavailable");
      const browserBytes = Buffer.from(await response.body());
      await privateBrowserScreenshot(`${args.qaRunId}-artifact-open.png`, page);

      let workspace;
      let artifactPath;
      try {
        workspace = fs.realpathSync(mission.workspaceRoot || mission.workspaceDirectory);
        artifactPath = fs.realpathSync(path.join(workspace, scenario.mission.outputIdentity));
      } catch {
        throw blockedError("worker_artifact_bytes_unavailable");
      }
      if (!pathInside(artifactPath, workspace) || !fs.statSync(artifactPath).isFile()) {
        throw blockedError("worker_artifact_bytes_unavailable");
      }
      const workerBytes = fs.readFileSync(artifactPath);
      const artifactTrace = state.store.prepare(
        `SELECT payload_json AS payload FROM work_trace_events
          WHERE owner_id = ? AND work_ref = ? AND run_id = ?
            AND event_type = 'artifact.observed'
          ORDER BY sequence DESC LIMIT 1`,
      ).all(mission.ownerId, mission.workRef, mission.runRef);
      const workerArtifactId = observedArtifactIdentity(artifactTrace, workerBytes);

      assertOwnerSafeTelegramIdentity(scenario, environment, await inspectTelegramUi());
      const downloadBaseline = captureTelegramDownloadBaseline(
        scenario.telegram.downloadDirectory,
        scenario.mission.outputIdentity,
      );
      const openStartedAtMs = Date.now();
      const openedAction = await performComputerDesktopAction(computerBridge, scenario, {
        action: "telegram.open_delivered_artifact",
        artifactId: workerArtifactId,
        filename: scenario.mission.outputIdentity,
      });
      if (openedAction.status !== "opened") {
        throw blockedError("telegram_artifact_open_unavailable");
      }
      const opened = await waitFor(async () => {
        try {
          return readFreshTelegramDownload({
            directory: scenario.telegram.downloadDirectory,
            filename: scenario.mission.outputIdentity,
            baseline: downloadBaseline,
            actionObservedAtMs: openStartedAtMs,
            ownerId: openedAction.activeSelection?.account?.ownerId,
            expectedOwnerId: mission.ownerId,
            expectedSha256: sha256(workerBytes),
          }).bytes;
        } catch (error) {
          if (
            error?.message === "telegram_artifact_download_unavailable" ||
            error?.message === "telegram_artifact_download_stale"
          ) {
            return null;
          }
          throw error;
        }
      }, { timeoutMs: args.timeoutMs, blocker: "telegram_artifact_download_unavailable" });
      const visible = await inspectTelegramUi();
      const telegramCapture = writeObservedComputerCapture(
        evidenceRoot,
        `${args.qaRunId}-telegram-result.png`,
        state.desktopObservation,
      );
      state.captures.push(telegramCapture);
      const advertisedArtifactId = String(response.headers()["x-artifact-id"] || "").trim();
      if (advertisedArtifactId && advertisedArtifactId !== workerArtifactId) {
        throw blockedError("delivered_artifact_identity_unavailable");
      }
      const assistantRows = await state.database.collection("messages").countDocuments({
        user: mission.ownerId,
        conversationId: state.conversationId,
        messageId: deliveries[0].callbackMessageId,
        isCreatedByUser: false,
      });
      const common = {
        ownerId: mission.ownerId,
        workRef: mission.workRef,
        runRef: mission.runRef,
        filename: scenario.mission.outputIdentity,
      };
      return {
        worker: { ...common, artifactId: workerArtifactId, bytes: workerBytes, sha256: sha256(workerBytes) },
        telegram: {
          ...common,
          artifactId: `artifact_sha256:${sha256(opened)}`,
          bytes: opened,
          sha256: sha256(opened),
          visible: visible.visibleText.some((item) => item.includes(scenario.mission.outputIdentity)),
          opened: true,
          assistantBubbleCount: assistantRows,
          artifactDeliveryCount: deliveries[0].telegramSentMessageIds.length,
          deliveryReceipts: deliveries.map((receipt) => ({
            receiptId: receipt.deliveryId,
            state: receipt.status,
            ownerId: receipt.userId,
            workRef: receipt.workRef,
          })),
        },
        activeWork: {
          ...common,
          artifactId: `artifact_sha256:${sha256(browserBytes)}`,
          bytes: browserBytes,
          sha256: sha256(browserBytes),
          visible: true,
          opened: true,
          headed: true,
        },
      };
    },

    async collectIndependentTrace(mission) {
      if (!String(mission.originRef || "").trim()) {
        throw blockedError("independent_runtime_trace_unavailable");
      }
      const ownerScopeHash = prefixedSha256(`owner\0${mission.ownerId}`);
      const originRefHash = prefixedSha256(`origin\0${mission.originRef}`);
      const events = await state.database.collection("viventiumorchestrationtraceevents").find({
        ownerScopeHash,
        originRefHash,
      }).project({ _id: 0, __v: 0, createdAt: 0 }).sort({ sequence: 1 }).limit(201).toArray();
      const verified = verifyIndependentTraceRows(events, mission.ownerId, mission.originRef, mission.workRef);
      if (!verified) throw blockedError("independent_runtime_trace_unavailable");
      return {
        ownerId: mission.ownerId,
        workRef: mission.workRef,
        runRef: mission.runRef,
        verified,
        eventCount: events.length,
        events,
      };
    },

    async cleanupSyntheticTelegramConversation() {
      if (
        !state.database || !state.user || !state.launchedAt ||
        !String(state.conversationId || "").trim() ||
        !state.ingress?.userMessageId || !state.ingress?.assistantMessageId ||
        !Array.isArray(state.ingressRecords) || state.ingressRecords.length !== 1
      ) {
        throw blockedError("synthetic_telegram_cleanup_unverified");
      }
      const deliveryRows = state.mission
        ? await state.database.collection("viventiumglasshivecallbackdeliveries").find({
          userId: state.ownerId,
          workRef: state.mission.workRef,
          runId: state.mission.runRef,
          surface: "telegram",
          telegramUserId: scenario.owner.telegramUserId,
          telegramChatId: scenario.owner.telegramChatId,
        }).project({ callbackMessageId: 1, telegramSentMessageIds: 1 }).limit(3).toArray()
        : [];
      if (deliveryRows.length > 1) {
        throw blockedError("synthetic_telegram_cleanup_scope_invalid");
      }
      const expectedMessageIds = [...new Set([
        state.ingress.userMessageId,
        state.ingress.assistantMessageId,
        ...deliveryRows.map((row) => String(row.callbackMessageId || "").trim()).filter(Boolean),
      ])];
      const messages = await state.database.collection("messages").find({
        user: state.ownerId,
        conversationId: state.conversationId,
        messageId: { $in: expectedMessageIds },
        createdAt: { $gte: new Date(state.launchedAt) },
      }).limit(expectedMessageIds.length + 1).toArray();
      if (
        messages.length !== expectedMessageIds.length ||
        expectedMessageIds.some((messageId) =>
          messages.filter((message) => message.messageId === messageId).length !== 1,
        )
      ) {
        throw blockedError("synthetic_telegram_cleanup_unverified");
      }
      const telegramMessageIds = [...new Set([
        ...state.ingressRecords.map((row) => Number(row.telegramMessageId)),
        ...deliveryRows.flatMap((row) =>
          Array.isArray(row.telegramSentMessageIds) ? row.telegramSentMessageIds.map(Number) : [],
        ),
      ])];
      return cleanupOwnerScopedSyntheticTelegramRecords({
        database: state.database,
        scenario,
        environment,
        owner: state.user,
        inventory: {
          ownerId: state.ownerId,
          conversationId: state.conversationId,
          startedAtMs: state.launchedAt,
          createdConversation: Boolean(state.createdConversation),
          telegramMessageIds,
          messages,
          ingress: state.ingressRecords,
          conversations: state.createdConversation ? [state.createdConversation] : [],
        },
        async removeRemote(messageIds) {
          const removed = await performComputerDesktopAction(computerBridge, scenario, {
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
      if (state.browser) await state.browser.close().catch(() => {});
      if (state.store) state.store.close();
      let cleanupFailure = null;
      for (const session of state.ephemeralSessions) {
        await session.cleanup().catch((error) => { cleanupFailure = error; });
      }
      await mongo.close().catch(() => {});
      if (cleanupFailure) throw blockedError("ephemeral_browser_session_cleanup_failed");
    },
  };

  return driver;
}

function privateEvidenceSnapshot(result) {
  return JSON.parse(JSON.stringify(result, (_key, value) => {
    if (value?.type === "Buffer" && Array.isArray(value.data)) {
      const bytes = Buffer.from(value.data);
      return { byteSha256: sha256(bytes), sizeBytes: bytes.length };
    }
    return value;
  }));
}

async function main(argv = process.argv.slice(2), environment = process.env, injection = {}) {
  let args;
  try {
    args = parseArgs(argv);
    if (args.dryRun) return dryRunPlan(args);
    assertLocalDiagnosticOptIn(args, environment);
    assertTelegramMutationConsent(args, environment);
    const evidenceRoot = assertPrivateEvidenceRoot(args.evidenceRoot);
    const scenario = validateScenario(readPrivateScenario(args.scenarioPath, evidenceRoot), environment);
    assertRestartConsent(args, environment, scenario.restart);
    const fixtures = inspectSyntheticInputs(scenario, { evidenceRoot });
    if (
      injection.desktopDriver &&
      (injection.computerAuthority?.unitTestHarness ||
        injection.computerAuthority?.transport?.unitTestHarness)
    ) {
      throw blockedError("computer_desktop_test_authority_forbidden");
    }
    if (
      injection.desktopDriver && injection.computerAuthority &&
      !AUTHENTICATED_PARENT_COMPUTER_AUTHORITIES.has(injection.computerAuthority)
    ) {
      await authenticateParentComputerAuthority(injection.computerAuthority);
    }
    const computerBridge = assertAuthenticatedComputerDesktopDriver(
      injection.desktopDriver,
      scenario,
      environment,
      { authority: injection.computerAuthority },
    );
    const driver = await createInstalledDriver({ scenario, args, environment, evidenceRoot, computerBridge });
    const result = await executeInstalledJourney({ driver, scenario, fixtures, environment });
    writePrivateEvidence(
      evidenceRoot,
      `${args.qaRunId}-installed-journey.json`,
      privateEvidenceSnapshot(result),
    );
    return buildPublicSummary({ result, qaRunId: args.qaRunId });
  } catch (error) {
    return buildPublicSummary({
      result: diagnosticResult("BLOCKED", error?.blocked ? error.message : "installed_journey_execution_failed"),
      qaRunId: args?.qaRunId || CASE_ID,
    });
  }
}

if (require.main === module) {
  main().then((result) => {
    process.stdout.write(`${JSON.stringify(result)}\n`);
    if (!["DRY_RUN", "PRE_GATE_COMPLETE"].includes(result.status)) process.exitCode = 2;
  }).catch(() => {
    process.stdout.write(`${JSON.stringify(diagnosticResult("BLOCKED", "installed_journey_execution_failed"))}\n`);
    process.exitCode = 2;
  });
}

module.exports = {
  parseArgs,
  dryRunPlan,
  assertLocalDiagnosticOptIn,
  assertTelegramMutationConsent,
  assertRestartConsent,
  SKY_ACTION_METHODS,
  authenticateParentComputerAuthority,
  assertExternalComputerAuthority,
  verifyExternalComputerProof,
  assertTrustedComputerAdapter,
  observeTrustedComputer,
  assertAuthenticatedComputerDesktopDriver,
  assertActiveSelectedTelegramContext,
  assertComputerDesktopObservation,
  readComputerDesktopState,
  performComputerDesktopAction,
  writeObservedComputerCapture,
  ephemeralBrowserSessionArgs,
  assertEphemeralSessionSafety,
  assertTrustedEphemeralSessionConfiguration,
  createEphemeralBrowserSession,
  assertPrivateEvidenceRoot,
  readPrivateScenario,
  writePrivateEvidence,
  validateScenario,
  assertOwnerSafeTelegramIdentity,
  cleanupOwnerScopedSyntheticTelegramRecords,
  inspectSyntheticInputs,
  deriveObservedUploadMetadata,
  observedFallbackAttemptManifests,
  assessCoordinatedRestartStatus,
  observedArtifactIdentity,
  assessOrderedInputParity,
  assessOwnerScopedMission,
  assessAuthorizedBrokerReceipts,
  assessProviderFallback,
  assertActiveFallbackAttempt,
  captureTelegramDownloadBaseline,
  readFreshTelegramDownload,
  assessRestartPreservation,
  assessDeliveredArtifact,
  verifyIndependentTraceRows,
  openReadOnlyGlassHiveStore,
  createInstalledDriver,
  executeInstalledJourney,
  buildPublicSummary,
  blockedError,
  main,
};
