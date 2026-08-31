#!/usr/bin/env node
"use strict";

/*
 * Real, deliberately opt-in PWK-UC-014 through PWK-UC-018 user journeys.
 * Select one exact journey with --case=PWK-UC-015. This runner triggers the
 * installed application; installed_journey_qa.py remains the independent
 * evidence verifier and release gates remain authoritative.
 */

const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const REPO_ROOT = path.resolve(__dirname, "../../..");
const LIBRECHAT_ROOT = path.join(REPO_ROOT, "viventium_v0_4", "LibreChat");
const CASE_ID = "PWK-UC-014";
const RELEASE_LABEL = "PRE-GATE / NOT READY";
const CASE_CONTRACTS = Object.freeze({
  "PWK-UC-014": Object.freeze({
    scenarioId: "original-parallel-html",
    requiredChecks: Object.freeze([
      "installed-identity",
      "telegram-ui",
      "main-feelings-receipt",
      "route-facts",
      "source-revision-single-reply",
      "main-responsive-quick-turn",
      "two-distinct-missions",
      "overlapping-runtime-windows",
      "steer-a-only",
      "terminal-callbacks-once",
      "two-distinct-html-artifacts",
      "two-headed-browser-windows",
      "redacted-end-to-end-trace",
    ]),
  }),
  "PWK-UC-015": Object.freeze({
    scenarioId: "restart-continuity",
    requiredChecks: Object.freeze([
      "installed-identity",
      "pre-restart-state",
      "restart-acknowledgements",
      "post-restart-state",
      "mission-identity-continuity",
      "steer-a-continuity",
      "callback-delivery-once",
      "artifact-hash-continuity",
      "telegram-recovery-ui",
      "active-work-recovery-ui",
    ]),
  }),
  "PWK-UC-016": Object.freeze({
    scenarioId: "capacity-provider-recovery",
    requiredChecks: Object.freeze([
      "installed-identity",
      "provider-auth-missing",
      "quota-cooldown-skip",
      "fallback-recovery",
      "provider-unavailable",
      "provider-retry-attention",
      "same-run-resume-idempotency",
      "declared-long-fresh-then-stale",
      "capacity-measurement",
      "atomic-reservation-race",
      "overflow-rejection-no-work",
      "disk-pressure",
      "same-work-recovery",
      "telegram-degraded-ui",
      "active-work-degraded-ui",
      "redacted-end-to-end-trace",
    ]),
  }),
  "PWK-UC-017": Object.freeze({
    scenarioId: "callback-artifact-recovery",
    requiredChecks: Object.freeze([
      "installed-identity",
      "callback-transport-outage",
      "claimed-timeout-once",
      "admitted-timeout-once",
      "status-timeout-race",
      "delivery-lease-race",
      "duplicate-callback-suppression",
      "artifact-expired-copy",
      "artifact-unavailable-copy",
      "restart-acknowledgements",
      "artifact-recovery",
      "telegram-terminal-ui",
      "active-work-terminal-ui",
      "redacted-end-to-end-trace",
    ]),
  }),
  "PWK-UC-018": Object.freeze({
    scenarioId: "owner-artifact-isolation",
    requiredChecks: Object.freeze([
      "installed-identity",
      "two-owner-auth-matrix",
      "forged-callback-rejection",
      "cross-owner-callback-rejection",
      "altered-trace-rejection",
      "hostile-html-browser-isolation",
      "worker-peer-isolation",
      "public-safety-scan",
      "telegram-safe-ui",
      "web-safe-ui",
      "redacted-end-to-end-trace",
    ]),
  }),
});
const CASE_FAULT_BOUNDARIES = Object.freeze({
  "PWK-UC-016": Object.freeze([
    "provider_auth_missing",
    "provider_quota_cooldown_fallback",
    "provider_unavailable",
    "provider_internal_retry_threshold",
    "declared_long_fresh_then_stale",
    "maximum_capacity_overflow",
    "measured_memory_4_3_gib_vs_5_gib",
    "last_reservation_competition",
    "low_disk",
  ]),
  "PWK-UC-017": Object.freeze([
    "callback_transport_interruption",
    "claimed_queue_stall",
    "admitted_queue_stall",
    "status_refresh_timeout_race",
    "expired_sender_lease_race",
    "duplicate_callback_replay",
    "artifact_link_expired",
    "artifact_unavailable_restart_recovery",
  ]),
});
const RESTART_SERVICES = Object.freeze([
  "librechat-core",
  "telegram-bot",
  "glasshive-runtime",
]);
const REQUIRED_IDENTITY_CHECKS = Object.freeze([
  "SOURCE-IDENTITY",
  "NESTED-PINS",
  "PREBUILT-IDENTITY",
  "INSTALLED-ARTIFACT",
]);
const SHA256 = /^[a-f0-9]{64}$/;
const SHORT_SHA256 = /^[a-f0-9]{16}$/;
const PREFIXED_SHA256 = /^sha256:[a-f0-9]{64}$/;
const CANONICAL_CALLBACK_REF = /^callback_sha256:[a-f0-9]{64}$/;
const CORE_LOG_WINDOW_MAX_BYTES = 25 * 1024 * 1024;
const CORE_LOG_BOUNDARY_BINDING_BYTES = 64 * 1024;

function blockedError(code) {
  const error = new Error(
    String(code || "installed_journey_prerequisite_unavailable"),
  );
  error.name = "InstalledParallelWorkBlockedError";
  error.blocked = true;
  return error;
}

function sha256(value) {
  return crypto.createHash("sha256").update(value).digest("hex");
}

function parseArgs(argv = process.argv.slice(2), env = process.env) {
  const options = new Map();
  let mode = "";
  for (const value of argv) {
    if (value === "--dry-run" || value === "--live") {
      if (mode) throw blockedError("conflicting_execution_modes");
      mode = value.slice(2);
      continue;
    }
    if (value === "--allow-restart" || value === "--allow-faults") {
      const key = value.slice(2);
      if (options.has(key)) throw blockedError("duplicate_argument");
      options.set(key, "true");
      continue;
    }
    if (!value.startsWith("--") || !value.includes("=")) {
      throw blockedError("unknown_argument");
    }
    const index = value.indexOf("=");
    const key = value.slice(2, index);
    if (options.has(key)) throw blockedError("duplicate_argument");
    options.set(key, value.slice(index + 1));
  }
  if (!mode) throw blockedError("explicit_execution_mode_required");
  const caseId = String(options.get("case") || CASE_ID).trim();
  if (!Object.hasOwn(CASE_CONTRACTS, caseId))
    throw blockedError("unsupported_case");
  if (mode === "dry-run") {
    if ([...options.keys()].some((key) => key !== "case")) {
      throw blockedError("dry_run_rejects_live_arguments");
    }
    return { mode, caseId, headless: false };
  }

  const required = [
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
  ];
  for (const key of required) {
    if (!String(options.get(key) || "").trim()) {
      throw blockedError(`missing_required_argument:${key}`);
    }
  }
  const allowed = new Set([
    ...required,
    "timeout-ms",
    "max-quick-latency-ms",
    "telegram-manifest",
    "telegram-evidence-root",
    "core-log",
    "candidate-mode",
    "case",
    "allow-restart",
    "allow-faults",
    "restart-readiness",
    "second-qa-email",
  ]);
  if ([...options.keys()].some((key) => !allowed.has(key))) {
    throw blockedError("unknown_argument");
  }
  const candidateMode = String(
    options.get("candidate-mode") || "strict",
  ).trim();
  if (!new Set(["strict", "diagnostic"]).has(candidateMode)) {
    throw blockedError("candidate_mode_invalid");
  }
  const timeoutMs = Number(options.get("timeout-ms") || 120000);
  const maxQuickLatencyMs = Number(
    options.get("max-quick-latency-ms") || 10000,
  );
  if (
    !Number.isSafeInteger(timeoutMs) ||
    timeoutMs < 10000 ||
    timeoutMs > 600000
  ) {
    throw blockedError("journey_timeout_invalid");
  }
  if (
    !Number.isSafeInteger(maxQuickLatencyMs) ||
    maxQuickLatencyMs < 250 ||
    maxQuickLatencyMs > 30000
  ) {
    throw blockedError("quick_turn_deadline_invalid");
  }
  return {
    mode,
    caseId,
    clientBase: options.get("client"),
    apiBase: options.get("api"),
    qaEmail: String(options.get("qa-email")).trim().toLowerCase(),
    agentId: String(options.get("agent")).trim(),
    outputDir: path.resolve(options.get("output")),
    runtimeRoot: path.resolve(options.get("runtime-root")),
    installedRoot: path.resolve(options.get("installed-root")),
    identityPath: path.resolve(options.get("identity")),
    ownerStatePath: path.resolve(options.get("owner-state")),
    glassHiveDbPath: path.resolve(options.get("glasshive-db")),
    telegramManifest: options.get("telegram-manifest")
      ? path.resolve(options.get("telegram-manifest"))
      : null,
    telegramEvidenceRoot: options.get("telegram-evidence-root")
      ? path.resolve(options.get("telegram-evidence-root"))
      : null,
    coreLogPath: options.get("core-log")
      ? path.resolve(options.get("core-log"))
      : null,
    timeoutMs,
    maxQuickLatencyMs,
    candidateMode,
    allowRestart: options.get("allow-restart") === "true",
    allowFaults: options.get("allow-faults") === "true",
    restartReadinessPath: options.get("restart-readiness")
      ? path.resolve(options.get("restart-readiness"))
      : null,
    secondQaEmail: String(options.get("second-qa-email") || "")
      .trim()
      .toLowerCase(),
    headless: false,
    qaRunId: `${caseId}-${crypto.randomUUID()}`,
  };
}

function dryRunPlan(args) {
  if (args?.mode !== "dry-run") throw blockedError("dry_run_required");
  return {
    caseId: args.caseId,
    status: "DRY_RUN",
    sideEffects: false,
    launchesBrowser: false,
    invokesModels: false,
    releaseReady: false,
    receiptEligible: false,
    releaseLabel: RELEASE_LABEL,
    requiredChecks: [...CASE_CONTRACTS[args.caseId].requiredChecks],
    independentPrerequisites:
      args.caseId === CASE_ID
        ? ["TR-026:verified-current-candidate-native-telegram-revision"]
        : [],
  };
}

function assertLoopbackUrl(value, label) {
  let parsed;
  try {
    parsed = new URL(String(value || ""));
  } catch {
    throw blockedError(`${label}_loopback_url_required`);
  }
  if (parsed.username || parsed.password)
    throw blockedError(`${label}_url_credentials_refused`);
  const hostname = parsed.hostname.replace(/^\[/, "").replace(/\]$/, "");
  if (
    !["http:", "https:"].includes(parsed.protocol) ||
    !new Set(["127.0.0.1", "localhost", "::1"]).has(hostname)
  ) {
    throw blockedError(`${label}_loopback_url_required`);
  }
  return parsed;
}

function assertLiveSafety(args, env) {
  if (
    args?.mode !== "live" ||
    env.VIVENTIUM_QA_ALLOW_INSTALLED_PARALLEL_WORK !== "1"
  ) {
    throw blockedError("installed_parallel_work_requires_explicit_opt_in");
  }
  if (env.CI || env.NODE_ENV === "production")
    throw blockedError("local_installed_qa_only");
  if (
    args.candidateMode === "diagnostic" &&
    env.VIVENTIUM_QA_ALLOW_DIAGNOSTIC_CANDIDATE !== "1"
  ) {
    throw blockedError("diagnostic_candidate_requires_explicit_opt_in");
  }
  const owner = String(env.VIVENTIUM_QA_OWNER_EMAIL || "")
    .trim()
    .toLowerCase();
  if (!owner) throw blockedError("owner_identity_guard_required");
  const email = String(args.qaEmail || "")
    .trim()
    .toLowerCase();
  if (email === owner) throw blockedError("personal_owner_account_refused");
  const parts = email.split("@");
  if (
    parts.length !== 2 ||
    !parts[0] ||
    !new Set(["example.com", "viventium.local", "localhost"]).has(parts[1])
  ) {
    throw blockedError("synthetic_qa_account_required");
  }
  assertEphemeralSessionSafety(args, env);
  assertLoopbackUrl(args.clientBase, "client");
  assertLoopbackUrl(args.apiBase, "api");
  assertScenarioSafety(args, env);
}

function assertEphemeralSessionSafety(args, env) {
  if (env.VIVENTIUM_QA_ALLOW_LOCAL_JWT !== "1") {
    throw blockedError("ephemeral_browser_session_requires_explicit_opt_in");
  }
  const configured = String(env.VIVENTIUM_QA_EMAIL || "")
    .trim()
    .toLowerCase();
  if (
    !configured ||
    configured !==
      String(args.qaEmail || "")
        .trim()
        .toLowerCase()
  ) {
    throw blockedError("configured_synthetic_qa_account_mismatch");
  }
  if (
    !String(env.JWT_SECRET || "").trim() ||
    !String(env.JWT_REFRESH_SECRET || "").trim()
  ) {
    throw blockedError("ephemeral_browser_session_signing_secrets_required");
  }
}

function assertScenarioSafety(args, env) {
  const caseId = String(args?.caseId || CASE_ID);
  if (!Object.hasOwn(CASE_CONTRACTS, caseId))
    throw blockedError("unsupported_case");
  if (caseId === "PWK-UC-015" || caseId === "PWK-UC-017") {
    if (
      args.allowRestart !== true ||
      env.VIVENTIUM_QA_ALLOW_COORDINATED_RESTART !== "1"
    ) {
      throw blockedError("coordinated_restart_requires_explicit_permission");
    }
    if (!String(args.restartReadinessPath || "").trim()) {
      throw blockedError("restart_readiness_proof_required");
    }
  }
  if (Object.hasOwn(CASE_FAULT_BOUNDARIES, caseId)) {
    if (
      args.allowFaults !== true ||
      env.VIVENTIUM_QA_ALLOW_GLASSHIVE_FAULTS !== "1"
    ) {
      throw blockedError("glasshive_faults_require_explicit_permission");
    }
  }
  if (caseId === "PWK-UC-018") {
    assertEphemeralSessionSafety(args, env);
    const second = String(args.secondQaEmail || "")
      .trim()
      .toLowerCase();
    const primary = String(args.qaEmail || "")
      .trim()
      .toLowerCase();
    const owner = String(env.VIVENTIUM_QA_OWNER_EMAIL || "")
      .trim()
      .toLowerCase();
    const parts = second.split("@");
    if (
      parts.length !== 2 ||
      !parts[0] ||
      !new Set(["example.com", "viventium.local", "localhost"]).has(parts[1]) ||
      second === primary ||
      second === owner
    ) {
      throw blockedError("second_synthetic_qa_account_required");
    }
  }
}

function assertRestartReadiness(proof, { caseId, candidateDigest }) {
  const services = Array.isArray(proof?.services) ? proof.services : [];
  const expected = new Set(RESTART_SERVICES);
  const acknowledged = new Set(proof?.acknowledgedServices || []);
  const required = new Set(proof?.requiredServices || []);
  const processRefs = new Set();
  const seenServices = new Set();
  const invalid = () => {
    throw blockedError("restart_readiness_proof_invalid");
  };
  if (
    proof?.caseId !== caseId ||
    proof.candidateDigest !== candidateDigest ||
    proof.restartState !== "ready" ||
    !/^sha256:[a-f0-9]{64}$/.test(String(proof.serviceAckDigest || "")) ||
    !Array.isArray(proof.missingServices) ||
    proof.missingServices.length !== 0 ||
    services.length !== expected.size ||
    required.size !== expected.size ||
    acknowledged.size !== expected.size ||
    [...expected].some(
      (service) => !required.has(service) || !acknowledged.has(service),
    )
  )
    invalid();
  for (const service of services) {
    if (
      !expected.has(service?.service) ||
      seenServices.has(service.service) ||
      !SHA256.test(String(service.beforeProcessRefHash || "")) ||
      !SHA256.test(String(service.afterProcessRefHash || "")) ||
      !SHA256.test(String(service.acknowledgementSha256 || "")) ||
      service.beforeProcessRefHash === service.afterProcessRefHash ||
      processRefs.has(service.afterProcessRefHash)
    )
      invalid();
    seenServices.add(service.service);
    processRefs.add(service.afterProcessRefHash);
  }
  return {
    verified: true,
    serviceCount: services.length,
    serviceAckDigest: proof.serviceAckDigest,
  };
}

function assertAuthenticatedRestartStatus(
  proof,
  status,
  { caseId, candidateDigest, previousServiceAckDigest, sessionRef },
) {
  const readiness = assertRestartReadiness(proof, { caseId, candidateDigest });
  const expected = new Set(RESTART_SERVICES);
  const required = new Set(
    Array.isArray(status?.requiredServices) ? status.requiredServices : [],
  );
  const acknowledged = new Set(
    Array.isArray(status?.acknowledgedServices)
      ? status.acknowledgedServices
      : [],
  );
  if (
    status?.caseId !== caseId ||
    status.restartState !== "ready" ||
    !Array.isArray(status.missingServices) ||
    status.missingServices.length !== 0 ||
    status.serviceAckDigest !== proof.serviceAckDigest ||
    !String(status.sessionRef || "").trim() ||
    (sessionRef && status.sessionRef !== sessionRef) ||
    required.size !== expected.size ||
    acknowledged.size !== expected.size ||
    [...expected].some(
      (service) => !required.has(service) || !acknowledged.has(service),
    )
  ) {
    throw blockedError("authenticated_restart_acknowledgements_unavailable");
  }
  if (
    previousServiceAckDigest &&
    status.serviceAckDigest === previousServiceAckDigest
  ) {
    throw blockedError("service_restart_process_change_unproven");
  }
  return readiness;
}

function assertSelectedQaAccount(args, env, user) {
  const owner = String(env.VIVENTIUM_QA_OWNER_EMAIL || "")
    .trim()
    .toLowerCase();
  const email = String(user?.email || "")
    .trim()
    .toLowerCase();
  if (!user?._id) throw blockedError("selected_qa_account_unavailable");
  if (email === owner) throw blockedError("personal_owner_account_refused");
  if (
    email !==
    String(args.qaEmail || "")
      .trim()
      .toLowerCase()
  ) {
    throw blockedError("selected_qa_account_mismatch");
  }
  if (
    String(user.role || "")
      .trim()
      .toUpperCase() === "ADMIN"
  ) {
    throw blockedError("admin_account_refused");
  }
  if (
    (user.viventiumApprovalStatus != null &&
      user.viventiumApprovalStatus !== "approved") ||
    user.locked === true ||
    user.isLocked === true ||
    user.banned === true
  ) {
    throw blockedError("locked_qa_account_refused");
  }
  return String(user._id);
}

async function createEphemeralBrowserSession({
  db,
  user,
  args,
  env,
  nowMs = Date.now(),
  createSessionId,
  signToken,
}) {
  assertEphemeralSessionSafety(args, env);
  const ownerId = assertSelectedQaAccount(args, env, user);
  const jwt = signToken
    ? null
    : require(path.join(LIBRECHAT_ROOT, "node_modules", "jsonwebtoken"));
  const ObjectId = createSessionId
    ? null
    : require(path.join(LIBRECHAT_ROOT, "node_modules", "mongodb")).ObjectId;
  const sessionId = createSessionId ? createSessionId() : new ObjectId();
  const signer = signToken || jwt.sign.bind(jwt);
  const expiresIn = Math.min(
    900,
    Math.max(120, Math.ceil((args.timeoutMs || 120000) / 1000) + 60),
  );
  const refreshToken = signer(
    { id: ownerId, sessionId: String(sessionId) },
    env.JWT_REFRESH_SECRET,
    { expiresIn },
  );
  const accessToken = signer(
    {
      id: ownerId,
      username: user.username,
      provider: user.provider,
      email: user.email,
    },
    env.JWT_SECRET,
    { expiresIn },
  );
  const expiration = new Date(nowMs + expiresIn * 1000);
  const collection = db.collection("sessions");
  const inserted = await collection.insertOne({
    _id: sessionId,
    user: user._id,
    expiration,
    refreshTokenHash: sha256(refreshToken),
  });
  if (inserted?.acknowledged !== true) {
    throw blockedError("ephemeral_browser_session_creation_failed");
  }
  const expires = Math.floor(expiration.getTime() / 1000);
  const cookies = [args.clientBase, args.apiBase].flatMap((url) => [
    {
      name: "refreshToken",
      value: refreshToken,
      url,
      httpOnly: true,
      sameSite: "Strict",
      expires,
    },
    {
      name: "token_provider",
      value: "librechat",
      url,
      httpOnly: true,
      sameSite: "Strict",
      expires,
    },
  ]);
  let removed = false;
  return {
    sessionId,
    accessToken,
    cookies,
    expiration,
    async cleanup() {
      if (removed) return;
      removed = true;
      await collection.deleteOne({ _id: sessionId, user: user._id });
    },
  };
}

function assertNoSymlinkComponents(target) {
  let absolute = path.resolve(target);
  const temporaryRoot = path.resolve(os.tmpdir());
  const relativeToTemporaryRoot = path.relative(temporaryRoot, absolute);
  if (
    relativeToTemporaryRoot &&
    !relativeToTemporaryRoot.startsWith(`..${path.sep}`) &&
    relativeToTemporaryRoot !== ".."
  ) {
    absolute = path.join(
      fs.realpathSync(temporaryRoot),
      relativeToTemporaryRoot,
    );
  }
  const root = path.parse(absolute).root;
  let current = root;
  for (const segment of absolute
    .slice(root.length)
    .split(path.sep)
    .filter(Boolean)) {
    current = path.join(current, segment);
    try {
      if (fs.lstatSync(current).isSymbolicLink()) {
        throw blockedError("private_evidence_symlink_refused");
      }
    } catch (error) {
      if (error?.code !== "ENOENT") throw error;
      break;
    }
  }
}

function preparePrivateEvidenceRoot(location, { repoRoot = REPO_ROOT } = {}) {
  const target = path.resolve(String(location || ""));
  const repository = fs.realpathSync(repoRoot);
  const relative = path.relative(repository, target);
  if (
    !relative ||
    (!relative.startsWith(`..${path.sep}`) && relative !== "..")
  ) {
    throw blockedError("private_evidence_must_stay_outside_repository");
  }
  if (target === path.parse(target).root)
    throw blockedError("private_evidence_path_invalid");
  assertNoSymlinkComponents(target);
  fs.mkdirSync(target, { recursive: true, mode: 0o700 });
  fs.chmodSync(target, 0o700);
  if (
    !fs.statSync(target).isDirectory() ||
    (fs.statSync(target).mode & 0o777) !== 0o700
  ) {
    throw blockedError("private_evidence_permissions_invalid");
  }
  return fs.realpathSync(target);
}

function writePrivateEvidence(root, name, payload) {
  if (!/^[A-Za-z0-9_.-]+$/.test(String(name || ""))) {
    throw blockedError("private_evidence_path_invalid");
  }
  const directory = fs.realpathSync(root);
  const target = path.join(directory, name);
  const bytes = Buffer.isBuffer(payload)
    ? payload
    : Buffer.from(`${JSON.stringify(payload, null, 2)}\n`, "utf8");
  const descriptor = fs.openSync(
    target,
    fs.constants.O_WRONLY |
      fs.constants.O_CREAT |
      fs.constants.O_EXCL |
      (fs.constants.O_NOFOLLOW || 0),
    0o600,
  );
  try {
    fs.writeFileSync(descriptor, bytes);
    fs.fchmodSync(descriptor, 0o600);
  } finally {
    fs.closeSync(descriptor);
  }
  return { path: target, sha256: sha256(bytes), bytes: bytes.length };
}

function assertMeasuredCandidate(measured) {
  if (
    !measured ||
    !SHA256.test(String(measured.candidateDigest || "")) ||
    !SHA256.test(String(measured.artifactDigest || "")) ||
    !Array.isArray(measured.checks) ||
    REQUIRED_IDENTITY_CHECKS.some(
      (id) =>
        measured.checks.filter(
          (check) => check?.id === id && check.status === "PASS",
        ).length !== 1,
    )
  ) {
    throw blockedError("installed_candidate_identity_unproven");
  }
  return {
    verified: true,
    candidateMode: "strict",
    releaseCandidateVerified: true,
    acceptanceEligible: true,
    identityFailures: [],
    candidateDigest: measured.candidateDigest,
    artifactDigest: measured.artifactDigest,
    checks: measured.checks.map(({ id, status }) => ({ id, status })),
  };
}

function assertDiagnosticCandidate(measured) {
  const binding = measured?.runtimeBinding;
  const source = measured?.measuredIdentity?.source;
  const components = measured?.measuredIdentity?.nestedComponents;
  const prebuilt = measured?.measuredIdentity?.prebuiltHelper;
  const installed = measured?.measuredIdentity?.installed;
  if (
    !binding ||
    binding.active !== true ||
    binding.ownerRootMatches !== true ||
    binding.runtimeRootMatches !== true ||
    !SHA256.test(String(binding.processIdentitySha256 || "")) ||
    !SHA256.test(String(binding.ownerBindingSha256 || "")) ||
    !SHA256.test(String(measured?.candidateDigest || "")) ||
    !SHA256.test(String(measured?.artifactDigest || "")) ||
    !/^[a-f0-9]{40}$/.test(String(source?.revision || "")) ||
    !SHA256.test(String(source?.worktreeHash || "")) ||
    !SHA256.test(String(source?.componentsLockSha256 || "")) ||
    !Array.isArray(components) ||
    components.length === 0 ||
    components.some(
      (component) =>
        !/^[a-f0-9]{40}$/.test(String(component?.pin || "")) ||
        !/^[a-f0-9]{40}$/.test(String(component?.revision || "")) ||
        !SHA256.test(String(component?.worktreeHash || "")) ||
        typeof component.clean !== "boolean",
    ) ||
    !SHA256.test(String(prebuilt?.sourceMeasuredSha256 || "")) ||
    !SHA256.test(String(prebuilt?.binaryMeasuredSha256 || "")) ||
    !/^[a-f0-9]{40}$/.test(String(installed?.rootRevision || "")) ||
    !SHA256.test(String(installed?.runningServiceSha256 || "")) ||
    !SHA256.test(String(installed?.frontendBuildSha256 || "")) ||
    !SHA256.test(String(installed?.apiBuildSha256 || "")) ||
    !Array.isArray(measured.checks) ||
    REQUIRED_IDENTITY_CHECKS.some(
      (id) => measured.checks.filter((check) => check?.id === id).length !== 1,
    )
  ) {
    throw blockedError("diagnostic_active_runtime_identity_unproven");
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
  };
}

function timestamp(value) {
  const milliseconds = Date.parse(String(value || ""));
  return Number.isFinite(milliseconds) ? milliseconds : null;
}

function rejected(reason) {
  return { pass: false, reason };
}

function assessRuntimeOverlap(rows, ownerId) {
  if (!Array.isArray(rows) || rows.length !== 2)
    return rejected("two_actual_runtime_attempts_required");
  const terminalStates = new Set([
    "completed",
    "failed",
    "cancelled",
    "interrupted",
  ]);
  const intervalEnds = [];
  const distinct = [
    "workRef",
    "workerRef",
    "runRef",
    "attemptRef",
    "leaseRef",
    "containerRef",
    "workspaceRef",
  ];
  for (const key of distinct) {
    if (
      rows.some((row) => !String(row?.[key] || "").trim()) ||
      rows[0][key] === rows[1][key]
    ) {
      return rejected(`distinct_${key}_required`);
    }
  }
  for (const row of rows) {
    if (row.ownerId !== ownerId) return rejected("runtime_owner_mismatch");
    if (!String(row.executorRef || "").trim())
      return rejected("runtime_scheduler_executor_unavailable");
    if (row.executionMode !== "docker")
      return rejected("isolated_docker_runtime_required");
    const invoked = timestamp(row.runtimeInvokedAt);
    const attemptInvoked = timestamp(row.attemptRuntimeInvokedAt);
    const finished = timestamp(row.finishedAt || row.attemptFinishedAt);
    const terminal =
      terminalStates.has(String(row.state || "").toLowerCase()) ||
      terminalStates.has(String(row.attemptState || "").toLowerCase()) ||
      finished != null;
    const ended = finished ?? Date.now();
    const acquired = timestamp(row.leaseAcquiredAt);
    const confirmed = timestamp(row.leaseConfirmedAt);
    const releaseDeclared = Boolean(row.leaseReleasedAt);
    const released = row.leaseReleasedAt
      ? timestamp(row.leaseReleasedAt)
      : null;
    if (
      invoked == null ||
      attemptInvoked == null ||
      invoked !== attemptInvoked ||
      acquired == null ||
      confirmed == null ||
      (terminal && (finished == null || released == null)) ||
      (!terminal && released != null) ||
      (releaseDeclared && released == null) ||
      acquired > invoked ||
      confirmed < invoked ||
      confirmed > ended ||
      ended <= invoked ||
      (released != null && (released < confirmed || released > ended))
    ) {
      return rejected("invoked_leased_runtime_evidence_incomplete");
    }
    intervalEnds.push(released ?? ended);
  }
  const start = Math.max(...rows.map((row) => timestamp(row.runtimeInvokedAt)));
  const end = Math.min(...intervalEnds);
  if (end <= start) return rejected("runtime_attempts_did_not_overlap");
  return {
    pass: true,
    overlapMs: end - start,
    workCount: 2,
    startedAtMs: start,
    endedAtMs: end,
  };
}

function isExactQuickMainAnswer(value) {
  return typeof value === "string" && value.trim() === "MAIN_AVAILABLE";
}

function assessMainResponsiveness({ rows, quickTurn, maxQuickLatencyMs }) {
  if (
    !quickTurn ||
    quickTurn.visible !== true ||
    quickTurn.finalReplyCount !== 1 ||
    quickTurn.exactAnswer !== true ||
    !Number.isFinite(quickTurn.submittedAtMs) ||
    !Number.isFinite(quickTurn.visibleAtMs)
  ) {
    return rejected("single_visible_main_reply_required");
  }
  const timingTimeline = quickTurn.timingTimeline;
  if (timingTimeline?.complete !== true) {
    return rejected("complete_quick_turn_timing_required");
  }
  if (
    !SHA256.test(String(quickTurn.logicalTurnHash || "")) ||
    timingTimeline.turnIdHash !== quickTurn.logicalTurnHash.slice(0, 16) ||
    timingTimeline.submittedAtMs !== quickTurn.submittedAtMs ||
    timingTimeline.domVisibleAtMs !== quickTurn.visibleAtMs ||
    !Number.isSafeInteger(timingTimeline.presentationCommittedAtMs) ||
    !Number.isSafeInteger(timingTimeline.counts?.providerAttempts) ||
    timingTimeline.counts.providerAttempts < 1 ||
    !Number.isSafeInteger(timingTimeline.counts?.providerOutputs) ||
    timingTimeline.counts.providerOutputs < 1 ||
    !Number.isSafeInteger(timingTimeline.counts?.toolInvocations) ||
    timingTimeline.counts.toolInvocations < 0
  ) {
    return rejected("quick_turn_timing_identity_mismatch");
  }
  const latencyMs = quickTurn.visibleAtMs - quickTurn.submittedAtMs;
  if (latencyMs < 0 || latencyMs > maxQuickLatencyMs)
    return rejected("quick_main_reply_deadline_exceeded");
  for (const row of rows) {
    const invoked = timestamp(row.runtimeInvokedAt);
    const ended =
      timestamp(row.finishedAt || row.attemptFinishedAt) ?? Date.now();
    if (
      invoked == null ||
      quickTurn.submittedAtMs < invoked ||
      quickTurn.visibleAtMs > ended
    ) {
      return rejected("main_reply_was_not_during_both_runtime_attempts");
    }
  }
  return { pass: true, latencyMs, timingTimeline };
}

function runtimePrerequisiteBlocker(rows) {
  for (const row of Array.isArray(rows) ? rows : []) {
    if (row.runtimeInvokedAt && row.state !== "failed") continue;
    const awaitingCapacityAdmission =
      !row.finishedAt &&
      new Set(["queued", "claimed", "admitted", "settling", "running"]).has(
        String(row.state || ""),
      );
    const provider = String(
      row.providerFailureClass || row.failureClass || "",
    ).trim();
    if (provider.startsWith("provider_") && /^[a-z0-9_]+$/.test(provider)) {
      return `worker_${provider}`;
    }
    let shortage = {};
    try {
      shortage = JSON.parse(String(row.capacityShortageJson || "{}"));
    } catch {
      shortage = {};
    }
    if (
      String(row.queueBlocker || "").includes("capacity") ||
      (shortage &&
        typeof shortage === "object" &&
        Object.values(shortage).some(
          (value) => typeof value === "number" && value > 0,
        ))
    ) {
      if (awaitingCapacityAdmission) continue;
      return "worker_capacity_unavailable";
    }
  }
  return null;
}

function assessSteerIsolation(actions, rows, ownerId) {
  if (
    !Array.isArray(actions) ||
    actions.some((action) => action.ownerId !== ownerId)
  ) {
    return rejected("owner_scoped_steer_evidence_required");
  }
  const steering = actions.filter((action) => action.action === "steer");
  if (
    steering.length !== 1 ||
    steering[0].workRef !== rows[0]?.workRef ||
    !new Set(["accepted", "completed"]).has(steering[0].status)
  ) {
    return rejected("exactly_one_accepted_a_only_steer_required");
  }
  return { pass: true, steerCount: 1 };
}

function canonicalizeCallbackRef(value) {
  const callbackRef = String(value || "").trim();
  if (!callbackRef) return "";
  return CANONICAL_CALLBACK_REF.test(callbackRef)
    ? callbackRef
    : `callback_sha256:${sha256(callbackRef)}`;
}

function assessTerminalDeliveries(callbacks, rows, ownerId) {
  if (!Array.isArray(callbacks) || callbacks.length !== rows.length) {
    return rejected("one_terminal_callback_per_runtime_required");
  }
  const canonicalCallbackRefs = callbacks.map((callback) =>
    canonicalizeCallbackRef(callback?.callbackRef),
  );
  if (
    canonicalCallbackRefs.some(
      (callbackRef) => !CANONICAL_CALLBACK_REF.test(callbackRef),
    ) ||
    new Set(canonicalCallbackRefs).size !== rows.length
  ) {
    return rejected("independent_terminal_callback_identity_required");
  }
  for (const row of rows) {
    const matching = callbacks.filter(
      (callback) =>
        callback.ownerId === ownerId &&
        callback.originRef === row.originRef &&
        callback.workRef === row.workRef &&
        callback.runRef === row.runRef,
    );
    const callback = matching[0];
    const canonicalCallbackRef = canonicalizeCallbackRef(callback?.callbackRef);
    const acceptedAt = timestamp(callback?.acceptedAt);
    const finishedAt = timestamp(row.finishedAt || row.attemptFinishedAt);
    const presentedAt = timestamp(callback?.webPresentedAt);
    const followUpMessageId = String(callback?.followUpMessageId || "").trim();
    if (
      matching.length !== 1 ||
      callback.event !== "run.completed" ||
      callback.callbackStatus !== "http_accepted" ||
      acceptedAt == null ||
      finishedAt == null ||
      acceptedAt < finishedAt ||
      ![null, undefined, ""].includes(callback.deliveredAt) ||
      !Number.isSafeInteger(callback.callbackAttemptNumber) ||
      callback.callbackAttemptNumber < 1 ||
      callback.callbackAttemptNumber !== row.attemptNumber ||
      !Number.isSafeInteger(callback.callbackAttempts) ||
      callback.callbackAttempts < 1 ||
      !Number.isSafeInteger(callback.callbackDeliveryGeneration) ||
      callback.callbackDeliveryGeneration < 1 ||
      !Number.isSafeInteger(callback.callbackResultRevision) ||
      callback.callbackResultRevision < 1 ||
      !PREFIXED_SHA256.test(String(callback.callbackResultDigest || "")) ||
      callback.missionEvidenceCount !== 1 ||
      callback.missionEvidenceOwnerId !== ownerId ||
      callback.missionEvidenceOriginRef !== row.originRef ||
      callback.missionEvidenceWorkRef !== row.workRef ||
      callback.missionEvidenceRunRef !== row.runRef ||
      callback.missionEvidenceEvent !== "run.completed" ||
      callback.missionEvidenceCallbackRef !== canonicalCallbackRef ||
      callback.missionEvidenceAttemptNumber !==
        callback.callbackAttemptNumber ||
      callback.missionEvidenceState !== "completed" ||
      callback.missionEvidenceWorkState !== "completed" ||
      callback.missionEvidenceWorkTerminal !== true ||
      String(callback.missionEvidenceErrorCode || "").trim() !== "" ||
      !followUpMessageId ||
      callback.webPresentationMessageId !== followUpMessageId ||
      presentedAt == null ||
      presentedAt < acceptedAt ||
      callback.persistedMessageCount !== 1 ||
      callback.persistedMessageId !== followUpMessageId ||
      callback.persistedMessageHasContent !== true ||
      callback.visibleMessageCount !== 1 ||
      callback.visibleMessageId !== followUpMessageId ||
      callback.visibleMessageHasContent !== true
    ) {
      return rejected("exactly_once_settled_terminal_delivery_required");
    }
  }
  return { pass: true, callbackCount: rows.length };
}

function assessArtifacts(artifacts, rows, ownerId) {
  if (!Array.isArray(artifacts) || artifacts.length !== rows.length) {
    return rejected("two_visible_html_artifacts_required");
  }
  const hashes = new Set();
  const windows = new Set();
  for (const row of rows) {
    const found = artifacts.filter(
      (artifact) =>
        artifact.ownerId === ownerId &&
        artifact.workRef === row.workRef &&
        artifact.runRef === row.runRef,
    );
    const artifact = found[0];
    if (
      found.length !== 1 ||
      !Buffer.isBuffer(artifact.bytes) ||
      artifact.bytes.length < 16 ||
      artifact.bytes.length > 1024 * 1024 ||
      !artifact.bytes.toString("utf8").toLowerCase().includes("<html") ||
      sha256(artifact.bytes) !== artifact.byteSha256 ||
      artifact.mediaType !== "text/html" ||
      artifact.headed !== true ||
      artifact.visible !== true ||
      !Number.isSafeInteger(artifact.windowId) ||
      !SHA256.test(String(artifact.screenshotSha256 || ""))
    ) {
      return rejected("headed_visible_exact_html_artifact_proof_required");
    }
    hashes.add(artifact.byteSha256);
    windows.add(artifact.windowId);
  }
  if (hashes.size !== rows.length || windows.size !== rows.length) {
    return rejected("distinct_artifact_bytes_and_os_windows_required");
  }
  return { pass: true, artifactCount: rows.length, windowCount: windows.size };
}

function assessFaultObservations(scenario, caseId, ownerId) {
  const expected = CASE_FAULT_BOUNDARIES[caseId] || [];
  const faults = Array.isArray(scenario?.faults) ? scenario.faults : [];
  const controls = new Set();
  if (faults.length !== expected.length)
    return rejected("exact_consumed_fault_coverage_required");
  for (const boundary of expected) {
    const matches = faults.filter((fault) => fault?.boundary === boundary);
    const fault = matches[0];
    if (
      matches.length !== 1 ||
      fault.ownerId !== ownerId ||
      fault.status !== "consumed" ||
      fault.effectCount !== 1 ||
      !timestamp(fault.consumedAt) ||
      !/^qac_sha256:[a-f0-9]{64}$/.test(String(fault.controlRef || "")) ||
      controls.has(fault.controlRef)
    )
      return rejected("exact_consumed_fault_coverage_required");
    controls.add(fault.controlRef);
  }
  return { pass: true, boundaryCount: expected.length };
}

function assessRestartContinuity(evidence, ownerId) {
  const scenario = evidence.scenario;
  try {
    assertRestartReadiness(scenario?.restart, {
      caseId: evidence.caseId,
      candidateDigest: evidence.identity.candidateDigest,
    });
  } catch {
    return rejected("restart_process_acknowledgements_unproven");
  }
  const before = scenario?.before;
  const after = scenario?.after;
  if (
    !before ||
    !after ||
    before.terminalCallbackCount !== 0 ||
    !Array.isArray(before.rows) ||
    !Array.isArray(after.rows) ||
    before.rows.length !== 2 ||
    after.rows.length !== 2
  )
    return rejected("pre_and_post_restart_mission_snapshots_required");
  const normalizeMission = (rows) =>
    rows
      .map((row) => ({
        ownerId: row.ownerId,
        workRef: row.workRef,
        workerRef: row.workerRef,
        workspaceRef: row.workspaceRef,
      }))
      .sort((left, right) => left.workRef.localeCompare(right.workRef));
  const normalizeRestart = (rows) =>
    rows
      .map((row) => ({
        ownerId: row.ownerId,
        workRef: row.workRef,
        activeRunRef: row.runRef,
        currentRunRef: row.currentRunRef || row.runRef,
        workerRef: row.workerRef,
        workspaceRef: row.workspaceRef,
      }))
      .sort((left, right) => left.workRef.localeCompare(right.workRef));
  if (
    before.rows.some((row) => row.ownerId !== ownerId) ||
    canonicalJson(normalizeRestart(before.rows)) !==
      canonicalJson(normalizeRestart(after.rows)) ||
    canonicalJson(normalizeMission(evidence.runtimeRows || [])) !==
      canonicalJson(normalizeMission(after.rows))
  )
    return rejected("exact_restart_mission_identity_continuity_required");
  for (const beforeRow of before.rows) {
    const terminalRow = (evidence.runtimeRows || []).find(
      (row) => row.workRef === beforeRow.workRef,
    );
    const expectedTerminalRunRef = beforeRow.currentRunRef || beforeRow.runRef;
    if (
      !terminalRow ||
      terminalRow.runRef !== expectedTerminalRunRef ||
      (terminalRow.currentRunRef || terminalRow.runRef) !==
        expectedTerminalRunRef
    ) {
      return rejected("exact_restart_mission_identity_continuity_required");
    }
  }
  if (
    !assessSteerIsolation(before.actions, before.rows, ownerId).pass ||
    !assessSteerIsolation(after.actions, after.rows, ownerId).pass
  )
    return rejected("exact_a_only_steer_restart_continuity_required");
  const turns = Array.isArray(scenario.turns) ? scenario.turns : [];
  for (const kind of [
    "substantial-a",
    "substantial-b",
    "quick-c",
    "continuation",
  ]) {
    if (
      turns.filter(
        (turn) =>
          turn?.kind === kind &&
          turn.userVisible === true &&
          turn.replyCount === 1,
      ).length !== 1
    ) {
      return rejected("rapid_a_b_c_and_exact_continuation_required");
    }
  }
  if (
    scenario.continuation?.workRef !== before.rows[0].workRef ||
    scenario.continuation?.workCountBefore !== 2 ||
    scenario.continuation?.workCountAfter !== 2 ||
    scenario.continuation?.receiptVerified !== true
  )
    return rejected("continuation_must_reuse_exact_existing_work");
  const artifactHashes = new Set(
    (evidence.artifacts || []).map((artifact) => artifact.byteSha256),
  );
  const reopened = Array.isArray(scenario.reopenedArtifactHashes)
    ? scenario.reopenedArtifactHashes
    : [];
  if (
    artifactHashes.size !== 2 ||
    reopened.length !== 2 ||
    reopened.some((hash) => !artifactHashes.has(hash)) ||
    new Set(reopened).size !== 2
  )
    return rejected("artifact_hash_continuity_after_restart_unproven");
  return { pass: true, serviceCount: RESTART_SERVICES.length, missionCount: 2 };
}

function assessCapacityProviderRecovery(evidence, ownerId) {
  const scenario = evidence.scenario;
  const faults = assessFaultObservations(scenario, evidence.caseId, ownerId);
  if (!faults.pass) return faults;
  const measurement = scenario.capacity?.measurement;
  if (
    !measurement ||
    !Number.isSafeInteger(measurement.availableBytes) ||
    !Number.isSafeInteger(measurement.requiredBytes) ||
    !Number.isSafeInteger(measurement.shortageBytes) ||
    measurement.availableBytes >= measurement.requiredBytes ||
    measurement.requiredBytes - measurement.availableBytes !==
      measurement.shortageBytes ||
    !timestamp(measurement.nextRetryAt)
  )
    return rejected("measured_capacity_shortage_and_retry_required");
  const attempts = scenario.capacity?.reservationAttempts;
  if (
    !Array.isArray(attempts) ||
    attempts.length !== 2 ||
    new Set(attempts.map((attempt) => attempt.requestRef)).size !== 2 ||
    new Set(attempts.map((attempt) => attempt.slotRef)).size !== 1 ||
    attempts.filter(
      (attempt) => attempt.outcome === "reserved" && attempt.workRef,
    ).length !== 1 ||
    attempts.filter(
      (attempt) => attempt.outcome === "rejected" && attempt.workRef == null,
    ).length !== 1
  )
    return rejected("one_atomic_reservation_winner_required");
  const overflow = scenario.capacity?.overflow;
  if (
    overflow?.outcome !== "rejected" ||
    overflow.workRows !== 0 ||
    overflow.runRows !== 0
  ) {
    return rejected("capacity_overflow_must_create_zero_work");
  }
  if (scenario.capacity?.disk?.state !== "critical")
    return rejected("injected_disk_pressure_unobserved");
  const provider = scenario.provider;
  if (
    provider?.missingAuthObserved !== true ||
    provider?.unavailableObserved !== true ||
    provider?.cooldownSkipped !== true ||
    provider?.primaryAttemptCountDuringCooldown !== 0 ||
    provider?.fallbackInvoked !== true ||
    provider?.fallbackConfigured !== true
  )
    return rejected("configured_provider_fallback_and_cooldown_proof_required");
  const liveness = scenario.providerLiveness;
  const attention = liveness?.retryAttention;
  const resume = liveness?.resume;
  const declaredLong = liveness?.declaredLong;
  if (
    attention?.internalRetryCount !== 3 ||
    attention?.state !== "needs_input" ||
    attention?.visibleLabel !== "Needs attention" ||
    attention?.failureClass !== "provider_progress_stalled" ||
    attention?.computeReleased !== true ||
    !String(attention?.runRef || "").trim() ||
    !Array.isArray(attention?.route) ||
    attention.route.length !== 3 ||
    !attention.route.every((value) => String(value || "").trim()) ||
    !SHA256.test(String(attention?.sessionRefHash || "")) ||
    !SHA256.test(String(attention?.workspaceRef || ""))
  )
    return rejected("provider_retry_needs_attention_compute_release_required");
  if (
    resume?.stableReplay !== true ||
    resume?.sameRun !== true ||
    resume?.sameRoute !== true ||
    resume?.sameSession !== true ||
    resume?.sameWorkspace !== true ||
    !SHA256.test(String(resume?.operationRef || "")) ||
    resume?.responseSha256 !== resume?.replaySha256
  )
    return rejected("same_run_resume_lost_response_idempotency_required");
  if (
    declaredLong?.declared !== true ||
    declaredLong?.freshProgressExtended !== true ||
    declaredLong?.staleAttention !== true ||
    declaredLong?.state !== "needs_input" ||
    declaredLong?.visibleLabel !== "Needs attention" ||
    declaredLong?.sameRun !== true
  )
    return rejected("declared_long_fresh_then_stale_attention_required");
  if (
    !Array.isArray(evidence.runtimeRows) ||
    evidence.runtimeRows.length !== 1 ||
    evidence.runtimeRows.some((row) => row.ownerId !== ownerId) ||
    scenario.recovery?.workRef !== evidence.runtimeRows[0].workRef ||
    scenario.recovery?.sameWork !== true ||
    scenario.recovery?.sameRun !== true ||
    scenario.recovery?.finalState !== "needs_input"
  )
    return rejected("exact_blocked_mission_recovery_required");
  return {
    pass: true,
    boundaryCount: faults.boundaryCount,
    shortageBytes: measurement.shortageBytes,
  };
}

function assessCallbackArtifactRecovery(evidence, ownerId) {
  const scenario = evidence.scenario;
  const faults = assessFaultObservations(scenario, evidence.caseId, ownerId);
  if (!faults.pass) return faults;
  try {
    assertRestartReadiness(scenario?.restart, {
      caseId: evidence.caseId,
      candidateDigest: evidence.identity.candidateDigest,
    });
  } catch {
    return rejected("restart_process_acknowledgements_unproven");
  }
  const timeouts = Array.isArray(scenario.delivery?.timeouts)
    ? scenario.delivery.timeouts
    : [];
  if (
    timeouts.length !== 2 ||
    ["claimed", "admitted"].some(
      (state) =>
        timeouts.filter(
          (timeout) =>
            timeout.state === state && timeout.terminalTransitions === 1,
        ).length !== 1,
    )
  )
    return rejected("claimed_and_admitted_timeout_once_required");
  if (
    scenario.delivery?.transportInterrupted !== true ||
    scenario.delivery?.staleRefreshApplied !== false ||
    scenario.delivery?.expiredSenderDelivered !== false ||
    scenario.delivery?.currentSenderDeliveryCount !== 1 ||
    scenario.delivery?.duplicatePresentations !== 0
  )
    return rejected("single_terminal_callback_and_sender_lease_required");
  const failures = Array.isArray(scenario.artifactFailures)
    ? scenario.artifactFailures
    : [];
  if (
    failures.length !== 2 ||
    ["expired", "unavailable"].some(
      (kind) =>
        failures.filter(
          (failure) => failure.kind === kind && failure.userVisible === true,
        ).length !== 1,
    )
  )
    return rejected("expired_and_unavailable_artifact_copy_required");
  const hashes = new Set(
    (evidence.artifacts || []).map((artifact) => artifact.byteSha256),
  );
  if (
    !SHA256.test(String(scenario.recoveredArtifactSha256 || "")) ||
    !hashes.has(scenario.recoveredArtifactSha256)
  )
    return rejected("exact_artifact_bytes_after_restart_required");
  return { pass: true, boundaryCount: faults.boundaryCount };
}

function assessOwnerArtifactIsolation(evidence, ownerId) {
  const scenario = evidence.scenario;
  const matrix = scenario.ownerMatrix;
  if (
    matrix?.ownerId !== ownerId ||
    !String(matrix.otherOwnerId || "").trim() ||
    matrix.otherOwnerId === ownerId ||
    !Array.isArray(matrix.operations)
  )
    return rejected("two_distinct_owner_authority_observations_required");
  for (const [actor, target] of [
    [ownerId, matrix.otherOwnerId],
    [matrix.otherOwnerId, ownerId],
  ]) {
    for (const operation of ["list", "inspect", "control", "callback"]) {
      const found = matrix.operations.filter(
        (entry) =>
          entry.actorOwnerId === actor &&
          entry.targetOwnerId === target &&
          entry.operation === operation,
      );
      if (
        found.length !== 1 ||
        found[0].outcome !== "denied" ||
        found[0].returnedWorkCount !== 0
      ) {
        return rejected("bidirectional_cross_owner_denial_required");
      }
    }
  }
  if (
    !matrix.operations.some(
      (entry) =>
        entry.actorOwnerId === ownerId &&
        entry.targetOwnerId === ownerId &&
        entry.outcome === "allowed" &&
        entry.returnedWorkCount > 0,
    )
  ) {
    return rejected("legitimate_owner_access_unproven");
  }
  const rejections = Array.isArray(scenario.rejections)
    ? scenario.rejections
    : [];
  if (
    rejections.length !== 3 ||
    ["forged_callback", "cross_owner_callback", "altered_trace"].some(
      (attack) =>
        rejections.filter(
          (rejection) =>
            rejection.attack === attack &&
            rejection.outcome === "denied" &&
            rejection.effectsCreated === 0 &&
            rejection.ownerId === ownerId,
        ).length !== 1,
    )
  )
    return rejected("forged_callback_cross_owner_and_trace_denial_required");
  const hostile = scenario.hostileArtifact;
  if (
    !Buffer.isBuffer(hostile?.bytes) ||
    !hostile.bytes.toString("utf8").toLowerCase().includes("<script") ||
    hostile.sandboxed !== true ||
    hostile.hostAuthority !== false ||
    hostile.scriptExecuted !== false ||
    hostile.visible !== true
  )
    return rejected("hostile_artifact_real_browser_isolation_required");
  const isolation = scenario.workerIsolation;
  const runtimeRows = Array.isArray(evidence.runtimeRows)
    ? evidence.runtimeRows
    : [];
  if (
    isolation?.peerAccessDenied !== true ||
    isolation.hostAccessDenied !== true ||
    isolation.auditVerified !== true ||
    !Array.isArray(isolation.workers) ||
    isolation.workers.length !== runtimeRows.length ||
    runtimeRows.length !== 2 ||
    runtimeRows.some((row) => {
      const matches = isolation.workers.filter(
        (proof) =>
          proof?.ownerRefHash === traceFingerprint("owner", ownerId) &&
          proof.workRefHash === traceFingerprint("work", row.workRef) &&
          proof.runRefHash === traceFingerprint("run", row.runRef) &&
          proof.workerRefHash === traceFingerprint("worker", row.workerRef) &&
          proof.attemptRefHash ===
            traceFingerprint("attempt", row.attemptRef) &&
          proof.leaseRefHash === traceFingerprint("lease", row.leaseRef) &&
          proof.containerRefHash ===
            traceFingerprint("container", row.containerRef),
      );
      if (matches.length !== 1) return true;
      const proof = matches[0];
      const expectedPeer = runtimeRows.find(
        (peer) => peer.runRef !== row.runRef,
      );
      return (
        proof.contractVersion !== 1 ||
        proof.producerScope !== "glasshive.worker_isolation" ||
        proof.executionMode !== "isolated_container" ||
        proof.hostAccessDenied !== true ||
        proof.peerAccessDenied !== true ||
        [
          "hostStateReadable",
          "serviceEnvironmentReadable",
          "dockerSocketReadable",
          "ambientAuthority",
        ].some((field) => proof[field] !== false) ||
        !Array.isArray(proof.peerProbes) ||
        proof.peerProbes.length !== 1 ||
        proof.peerProbes[0].reachable !== false ||
        proof.peerProbes[0].workRefHash !==
          traceFingerprint("work", expectedPeer.workRef)
      );
    })
  ) {
    return rejected("worker_peer_and_host_isolation_required");
  }
  const safety = scenario.publicSafety;
  if (
    safety?.scannedArtifactSha256 !== sha256(hostile.bytes) ||
    safety.findingCount !== 0 ||
    safety.privateLeakCount !== 0 ||
    safety.hostAuthorityExecutionCount !== 0
  )
    return rejected("hostile_artifact_public_safety_scan_required");
  return { pass: true, rejectionCount: rejections.length };
}

function finalizeCandidateResult(base, evidence, blockers, measured) {
  if (evidence.identity?.candidateMode === "diagnostic") {
    const identityFailures = (
      Array.isArray(evidence.identity.identityFailures)
        ? evidence.identity.identityFailures
        : []
    ).map((failure) =>
      String(failure.reason || failure.id || "identity_check_failed"),
    );
    return {
      ...base,
      status: "PARTIAL",
      diagnosticPass: blockers.length === 0,
      blockers: [
        ...new Set([
          ...blockers,
          ...identityFailures,
          "diagnostic_candidate_cannot_close_release_gate",
        ]),
      ],
      checks: measured,
    };
  }
  if (blockers.length)
    return { ...base, status: "PARTIAL", blockers, checks: measured };
  return { ...base, status: "PASS", pass: true, checks: measured };
}

function evaluateExtendedJourneyEvidence(evidence, ownerId, base) {
  const contract = CASE_CONTRACTS[evidence.caseId];
  if (
    evidence.scenario?.scenarioId !== contract.scenarioId ||
    evidence.scenario?.caseId !== evidence.caseId ||
    evidence.scenario?.observed !== true
  )
    return {
      ...base,
      status: "FAIL",
      blockers: ["case_specific_scenario_evidence_unobserved"],
    };

  const evaluators = {
    "PWK-UC-015": assessRestartContinuity,
    "PWK-UC-016": assessCapacityProviderRecovery,
    "PWK-UC-017": assessCallbackArtifactRecovery,
    "PWK-UC-018": assessOwnerArtifactIsolation,
  };
  const scenario = evaluators[evidence.caseId](evidence, ownerId);
  const measured = { scenario };
  const failures = scenario.pass ? [] : [scenario.reason];
  const rows = Array.isArray(evidence.runtimeRows) ? evidence.runtimeRows : [];
  if (rows.length === 0 || rows.some((row) => row.ownerId !== ownerId)) {
    failures.push("exact_owner_scoped_runtime_scenario_required");
  }
  if (evidence.caseId === "PWK-UC-015") {
    measured.overlap = assessRuntimeOverlap(rows, ownerId);
    measured.main = assessMainResponsiveness({
      rows,
      quickTurn: evidence.quickTurn,
      maxQuickLatencyMs: evidence.maxQuickLatencyMs || 10000,
    });
    measured.steer = assessSteerIsolation(evidence.actions, rows, ownerId);
  }
  if (evidence.caseId !== "PWK-UC-016") {
    measured.callbacks = assessTerminalDeliveries(
      evidence.callbacks,
      rows,
      ownerId,
    );
    measured.artifacts = assessArtifacts(evidence.artifacts, rows, ownerId);
  }
  for (const [name, result] of Object.entries(measured)) {
    if (name !== "scenario" && !result.pass) failures.push(result.reason);
  }
  if (evidence.caseId !== "PWK-UC-016") {
    const traces = Array.isArray(evidence.traces) ? evidence.traces : [];
    if (
      traces.length !== rows.length ||
      rows.some(
        (row) =>
          traces.filter(
            (trace) =>
              trace.workRef === row.workRef &&
              trace.ownerScoped === true &&
              trace.hashChainVerified === true &&
              trace.completionClaimable === true,
          ).length !== 1,
      )
    )
      failures.push("redacted_owner_scoped_trace_unproven");
  }
  if (failures.length)
    return {
      ...base,
      status: "FAIL",
      blockers: [...new Set(failures)],
      checks: measured,
    };

  const blockers = [];
  if (evidence.scenario.surfaces?.webVisible !== true)
    blockers.push("headed_browser_scenario_proof_unavailable");
  if (evidence.scenario.surfaces?.telegramVisible !== true)
    blockers.push("native_telegram_scenario_proof_unavailable");
  return finalizeCandidateResult(base, evidence, blockers, measured);
}

function evaluateJourneyEvidence(evidence, ownerId) {
  const caseId = String(evidence?.caseId || CASE_ID);
  const base = {
    caseId,
    pass: false,
    receiptEligible: false,
    blockers: [],
    checks: {},
  };
  if (!Object.hasOwn(CASE_CONTRACTS, caseId)) {
    return { ...base, status: "BLOCKED", blockers: ["unsupported_case"] };
  }
  if (!evidence?.identity?.verified) {
    return {
      ...base,
      status: "BLOCKED",
      blockers: ["installed_candidate_identity_unproven"],
    };
  }
  if (caseId !== CASE_ID)
    return evaluateExtendedJourneyEvidence(evidence, ownerId, base);
  const rows = evidence.runtimeRows;
  const measured = {
    overlap: assessRuntimeOverlap(rows, ownerId),
    main: assessMainResponsiveness({
      rows: Array.isArray(rows) ? rows : [],
      quickTurn: evidence.quickTurn,
      maxQuickLatencyMs: evidence.maxQuickLatencyMs || 10000,
    }),
    steer: assessSteerIsolation(
      evidence.actions,
      Array.isArray(rows) ? rows : [],
      ownerId,
    ),
    callbacks: assessTerminalDeliveries(
      evidence.callbacks,
      Array.isArray(rows) ? rows : [],
      ownerId,
    ),
    artifacts: assessArtifacts(
      evidence.artifacts,
      Array.isArray(rows) ? rows : [],
      ownerId,
    ),
  };
  const failures = Object.values(measured)
    .filter((check) => !check.pass)
    .map((check) => check.reason);
  const traces = Array.isArray(evidence.traces) ? evidence.traces : [];
  if (
    !Array.isArray(rows) ||
    traces.length !== rows.length ||
    rows.some((row) => {
      const trace = traces.filter((item) => item.workRef === row.workRef);
      return (
        trace.length !== 1 ||
        trace[0].ownerScoped !== true ||
        trace[0].hashChainVerified !== true ||
        trace[0].completionClaimable !== true
      );
    })
  ) {
    failures.push("redacted_owner_scoped_trace_unproven");
  }
  if (failures.length)
    return { ...base, status: "FAIL", blockers: failures, checks: measured };

  const blockers = [];
  if (!evidence.feelings?.userVisible || !evidence.feelings?.receiptVerified) {
    blockers.push("main_feelings_native_receipt_unavailable");
  }
  if (
    !evidence.routeFacts?.userVisible ||
    !evidence.routeFacts?.receiptVerified
  ) {
    blockers.push("main_route_authority_receipt_unavailable");
  }
  const telegram = evidence.telegram;
  if (
    !telegram ||
    telegram.verified !== true ||
    telegram.nativeDesktop !== true ||
    telegram.revisionBeforeCommit !== true ||
    telegram.finalReplyCount !== 1 ||
    telegram.delayMs !== 280
  ) {
    blockers.push("telegram_native_revision_proof_unavailable");
  }
  return finalizeCandidateResult(base, evidence, blockers, measured);
}

function buildPublicSummary({ result, evidence = {}, qaRunId }) {
  const measured = evidence.identity?.measuredIdentity || {};
  const safeHash = (value) => (SHA256.test(String(value || "")) ? value : null);
  return {
    caseId: result?.caseId || evidence.caseId || CASE_ID,
    qaRunIdHash: sha256(String(qaRunId || "")),
    status: result?.status || "BLOCKED",
    pass: result?.pass === true,
    releaseReady: false,
    receiptEligible: false,
    releaseLabel: RELEASE_LABEL,
    candidateMode:
      evidence.identity?.candidateMode === "diagnostic"
        ? "diagnostic"
        : "strict",
    diagnosticPass: result?.diagnosticPass === true,
    releaseCandidateVerified:
      evidence.identity?.releaseCandidateVerified === true,
    activeRuntimeVerified: evidence.identity?.runtimeBinding?.active === true,
    candidateDigest: SHA256.test(
      String(evidence.identity?.candidateDigest || ""),
    )
      ? evidence.identity.candidateDigest
      : null,
    artifactDigest: SHA256.test(String(evidence.identity?.artifactDigest || ""))
      ? evidence.identity.artifactDigest
      : null,
    measuredSourceWorktreeSha256: safeHash(measured.source?.worktreeHash),
    measuredRunningServiceSha256: safeHash(
      measured.installed?.runningServiceSha256,
    ),
    measuredFrontendBuildSha256: safeHash(
      measured.installed?.frontendBuildSha256,
    ),
    measuredApiBuildSha256: safeHash(measured.installed?.apiBuildSha256),
    ownerBindingSha256: safeHash(
      evidence.identity?.runtimeBinding?.ownerBindingSha256,
    ),
    processIdentitySha256: safeHash(
      evidence.identity?.runtimeBinding?.processIdentitySha256,
    ),
    identityFailures: (Array.isArray(evidence.identity?.identityFailures)
      ? evidence.identity.identityFailures
      : []
    ).map(({ id, status, reason }) => ({
      id: String(id || "")
        .replace(/[^A-Z0-9_-]/g, "_")
        .slice(0, 80),
      status: String(status || "")
        .replace(/[^A-Z_]/g, "_")
        .slice(0, 16),
      reason: String(reason || "")
        .replace(/[^a-z0-9_]/gi, "_")
        .slice(0, 120),
    })),
    runtimeCount: Array.isArray(evidence.runtimeRows)
      ? evidence.runtimeRows.length
      : null,
    callbackCount: Array.isArray(evidence.callbacks)
      ? evidence.callbacks.length
      : null,
    artifactCount: Array.isArray(evidence.artifacts)
      ? evidence.artifacts.length
      : null,
    overlapMs: Number.isSafeInteger(result?.checks?.overlap?.overlapMs)
      ? result.checks.overlap.overlapMs
      : null,
    quickReplyMs: Number.isSafeInteger(result?.checks?.main?.latencyMs)
      ? result.checks.main.latencyMs
      : null,
    nativeTelegramVerified: evidence.telegram?.verified === true,
    blockers: (Array.isArray(result?.blockers) ? result.blockers : []).map(
      (value) =>
        String(value)
          .replace(/[^a-z0-9_:.-]/gi, "_")
          .slice(0, 120),
    ),
  };
}

function openReadOnlyGlassHiveStore(location) {
  let resolved;
  try {
    resolved = fs.realpathSync(location);
    if (!fs.statSync(resolved).isFile())
      throw blockedError("glasshive_runtime_database_unavailable");
  } catch (error) {
    if (error?.blocked) throw error;
    throw blockedError("glasshive_runtime_database_unavailable");
  }
  const { DatabaseSync } = require("node:sqlite");
  return new DatabaseSync(resolved, { readOnly: true });
}

function readScopedRuntimeEvidence(store, { ownerId, workRefs }) {
  if (
    !String(ownerId || "").trim() ||
    !Array.isArray(workRefs) ||
    workRefs.length !== 2 ||
    new Set(workRefs).size !== 2
  ) {
    throw blockedError("owner_scoped_mission_evidence_incomplete");
  }
  const parameters = [ownerId, ...workRefs];
  const rows = store
    .prepare(
      `SELECT d.owner_id AS ownerId, d.origin_ref AS originRef, d.work_ref AS workRef,
              d.worker_id AS workerRef, r.run_id AS runRef,
              d.current_run_id AS currentRunRef,
              current_run.state AS currentRunState,
              w.resource_class AS resourceClass, w.execution_mode AS executionMode,
              COALESCE(NULLIF(w.workspace_root, ''), w.workspace_dir) AS workspaceRoot,
              r.state AS state, r.runtime_invoked_at AS runtimeInvokedAt,
              r.ended_at AS finishedAt, r.queue_blocker_class AS queueBlocker,
              r.failure_class AS failureClass,
              r.capacity_available_json AS capacityAvailableJson,
              r.capacity_required_json AS capacityRequiredJson,
              r.capacity_shortage_json AS capacityShortageJson,
              r.capacity_next_retry_at AS capacityNextRetryAt,
              r.provider_route_failure_class AS providerFailureClass,
              a.attempt_id AS attemptRef,
              a.attempt_number AS attemptNumber, a.state AS attemptState,
              a.runtime_invoked_at AS attemptRuntimeInvokedAt,
              a.ended_at AS attemptFinishedAt, a.lease_id AS leaseRef,
              l.executor_id AS executorRef, l.startup_container_id AS containerRef,
              l.acquired_at AS leaseAcquiredAt, l.released_at AS leaseReleasedAt,
              l.startup_confirmed_at AS leaseConfirmedAt
       FROM delegations d
       JOIN workers w ON w.worker_id = d.worker_id AND w.owner_id = d.owner_id
       JOIN runs r ON r.run_id = COALESCE(
         (
           SELECT active_run.run_id
           FROM runs active_run
           WHERE active_run.worker_id = d.worker_id
             AND active_run.state IN (
               'running', 'admitted', 'claimed', 'settling',
               'queued', 'paused', 'needs_input'
             )
           ORDER BY
             CASE active_run.state
               WHEN 'running' THEN 0
               WHEN 'admitted' THEN 1
               WHEN 'claimed' THEN 2
               WHEN 'settling' THEN 3
               WHEN 'paused' THEN 4
               WHEN 'needs_input' THEN 5
               ELSE 6
             END,
             active_run.queued_at DESC
           LIMIT 1
         ),
         d.current_run_id
       )
       LEFT JOIN runs current_run ON current_run.run_id = d.current_run_id
       LEFT JOIN run_attempts a ON a.run_id = r.run_id
         AND a.attempt_number = (
           SELECT MAX(candidate.attempt_number) FROM run_attempts candidate
           WHERE candidate.run_id = r.run_id
         )
       LEFT JOIN host_run_leases l ON l.lease_id = a.lease_id
         AND l.owner_id = d.owner_id AND l.worker_id = d.worker_id AND l.run_id = r.run_id
       WHERE d.owner_id = ? AND d.work_ref IN (?, ?)`,
    )
    .all(...parameters)
    .map((row) => ({
      ...row,
      workspaceRef: row.workspaceRoot ? sha256(String(row.workspaceRoot)) : "",
    }))
    .sort(
      (left, right) =>
        workRefs.indexOf(left.workRef) - workRefs.indexOf(right.workRef),
    );
  if (rows.length !== 2 || rows.some((row) => row.ownerId !== ownerId)) {
    throw blockedError("owner_scoped_mission_evidence_incomplete");
  }
  const callbacks = store
    .prepare(
      `SELECT d.owner_id AS ownerId, d.origin_ref AS originRef,
              d.work_ref AS workRef, r.run_id AS runRef,
              c.callback_id AS callbackRef, c.event_type AS event,
              c.attempt_number AS callbackAttemptNumber,
              c.attempts AS callbackAttempts,
              c.delivery_generation AS callbackDeliveryGeneration,
              c.result_revision AS callbackResultRevision,
              c.result_digest AS callbackResultDigest,
              c.status AS callbackStatus, c.http_accepted_at AS acceptedAt,
              c.delivered_at AS deliveredAt
       FROM delegations d
       JOIN runs r ON r.run_id = d.current_run_id
       JOIN callback_outbox c ON c.run_id = r.run_id
       WHERE d.owner_id = ? AND d.work_ref IN (?, ?) AND c.event_type = 'run.completed'`,
    )
    .all(...parameters);
  const actions = store
    .prepare(
      `SELECT owner_id AS ownerId, work_ref AS workRef, action, status,
              created_at AS createdAt
       FROM active_work_action_uses
       WHERE owner_id = ? AND work_ref IN (?, ?)`,
    )
    .all(...parameters);
  return { rows, callbacks, actions };
}

function readExactFixtureRuntimeEvidence(store, { ownerId, fixture }) {
  if (
    !String(ownerId || "").trim() ||
    fixture?.scopeHashes?.owner !== nestedScopeHash("owner", ownerId) ||
    !PREFIXED_SHA256.test(String(fixture?.scopeHashes?.work || "")) ||
    !PREFIXED_SHA256.test(String(fixture?.scopeHashes?.run || ""))
  ) {
    throw blockedError("controlled_fixture_mission_mismatch");
  }
  const candidates = store
    .prepare(
      `SELECT d.owner_id AS ownerId, d.origin_ref AS originRef,
              d.work_ref AS workRef, d.worker_id AS workerRef,
              d.current_run_id AS runRef, d.project_id AS projectRef,
              w.workspace_dir AS workspaceRoot, w.compute_released_at AS computeReleasedAt,
              w.state AS workerState, r.state AS state,
              r.failure_class AS failureClass,
              r.internal_retry_count AS internalRetryCount,
              r.liveness_mode AS livenessMode,
              r.liveness_started_at AS livenessStartedAt,
              r.meaningful_progress_at AS meaningfulProgressAt,
              r.meaningful_progress_sequence AS meaningfulProgressSequence,
              r.provider_liveness_route_locked AS routeLocked,
              r.provider_route_profile AS profile,
              r.provider_route_runtime AS runtime,
              r.provider_route_model AS model,
              r.provider_route_decision AS routeDecision,
              r.provider_route_from_profile AS fromProfile,
              r.native_session_id AS nativeSessionRef,
              r.active_attempt_id AS attemptRef, r.ended_at AS finishedAt
       FROM delegations d
       JOIN workers w ON w.worker_id = d.worker_id AND w.owner_id = d.owner_id
       JOIN runs r ON r.run_id = d.current_run_id
       WHERE d.owner_id = ?`,
    )
    .all(ownerId)
    .filter(
      (row) =>
        fixture.scopeHashes.work === nestedScopeHash("work", row.workRef) &&
        fixture.scopeHashes.run === nestedScopeHash("run", row.runRef),
    )
    .map((row) => ({
      ...row,
      workspaceRef: row.workspaceRoot ? sha256(String(row.workspaceRoot)) : "",
    }));
  if (candidates.length !== 1)
    throw blockedError("controlled_fixture_mission_mismatch");
  const row = candidates[0];
  const liveness = store
    .prepare(
      `SELECT event_ref AS eventRef, run_id AS runRef, attempt_id AS attemptRef,
              kind, failure_class AS failureClass, runtime, model,
              source_sequence AS sourceSequence, source_digest AS sourceDigest,
              observed_at AS observedAt, created_at AS createdAt
       FROM provider_liveness_events WHERE run_id = ?
       ORDER BY observed_at, source_sequence`,
    )
    .all(row.runRef);
  const capacity = store
    .prepare(
      `SELECT capacity_attempt_id AS requestRef, run_id AS runRef,
              capacity_class AS capacityClass, available_json AS availableJson,
              required_json AS requiredJson, shortage_json AS shortageJson,
              reservation_json AS reservationJson, next_retry_at AS nextRetryAt,
              observed_at AS observedAt
       FROM capacity_attempts WHERE run_id = ? ORDER BY sequence`,
    )
    .all(row.runRef)
    .map((entry) => ({ ...entry, ownerId, workRef: row.workRef }));
  const actions = store
    .prepare(
      `SELECT action_use_id AS actionRef, owner_id AS ownerId,
              work_ref AS workRef, source_run_id AS sourceRunRef,
              idempotency_key AS idempotencyKey, action, status,
              response_json AS responseJson, created_at AS createdAt
       FROM active_work_action_uses
       WHERE owner_id = ? AND work_ref = ? ORDER BY created_at`,
    )
    .all(ownerId, row.workRef);
  const events = store
    .prepare(
      `SELECT event_type AS eventType, payload_json AS payloadJson,
              created_at AS createdAt FROM events
       WHERE project_id = ? AND worker_id = ? AND run_id = ? ORDER BY created_at`,
    )
    .all(row.projectRef, row.workerRef, row.runRef);
  return { row, liveness, capacity, actions, events };
}

function readWorkerIsolationEvidence(store, { ownerId, rows }) {
  const unavailable = () =>
    blockedError("worker_peer_isolation_probe_unavailable");
  const unproven = () => blockedError("worker_peer_or_host_isolation_unproven");
  if (
    !String(ownerId || "").trim() ||
    !Array.isArray(rows) ||
    rows.length !== 2 ||
    rows.some((row) => row?.ownerId !== ownerId) ||
    new Set(rows.map((row) => row.runRef)).size !== 2
  )
    throw unavailable();
  let records;
  try {
    records = store
      .prepare(
        `SELECT w.owner_id AS ownerId, d.work_ref AS workRef, e.worker_id AS workerRef,
              e.run_id AS runRef, e.event_id AS eventId, e.payload_json AS payloadJson,
              e.created_at AS createdAt, t.trace_event_id AS traceEventId,
              t.payload_json AS tracePayloadJson
       FROM events e
       JOIN workers w ON w.worker_id = e.worker_id AND w.tenant_id = e.tenant_id
       JOIN delegations d
         ON d.worker_id = w.worker_id AND d.owner_id = w.owner_id
        AND d.tenant_id = w.tenant_id AND d.current_run_id = e.run_id
       JOIN work_trace_events t
         ON t.trace_event_id = 'trace_' || substr(e.event_id, 5)
        AND t.run_id = e.run_id AND t.work_ref = d.work_ref
        AND t.tenant_id = w.tenant_id AND t.owner_id = w.owner_id
        AND t.event_type = e.event_type
       WHERE w.owner_id = ? AND e.run_id IN (?, ?)
         AND e.event_type = 'worker.isolation_probe'
       ORDER BY e.created_at DESC, e.event_id DESC`,
      )
      .all(ownerId, ...rows.map((row) => row.runRef));
  } catch {
    throw unavailable();
  }
  if (records.length < rows.length) throw unavailable();

  const fields = [
    "contractVersion",
    "producerScope",
    "ownerRefHash",
    "workRefHash",
    "runRefHash",
    "workerRefHash",
    "attemptRefHash",
    "leaseRefHash",
    "containerRefHash",
    "workspaceRefHash",
    "homeRefHash",
    "networkRefHash",
    "pidNamespaceRefHash",
    "executionMode",
    "hostStateReadable",
    "serviceEnvironmentReadable",
    "dockerSocketReadable",
    "ambientAuthority",
    "peerAccessDenied",
    "hostAccessDenied",
    "peerProbes",
  ].sort();
  const verifiedTraces = new Set();
  const selected = new Map();
  for (const record of records) {
    const row = rows.find((candidate) => candidate.runRef === record.runRef);
    if (
      !row ||
      record.ownerId !== ownerId ||
      record.workRef !== row.workRef ||
      record.workerRef !== row.workerRef
    )
      throw unproven();
    let proof;
    let traced;
    try {
      proof = JSON.parse(String(record.payloadJson || "{}"));
      traced = JSON.parse(String(record.tracePayloadJson || "{}"));
    } catch {
      throw unproven();
    }
    if (
      !proof ||
      typeof proof !== "object" ||
      Array.isArray(proof) ||
      canonicalJson(Object.keys(proof).sort()) !== canonicalJson(fields) ||
      canonicalJson(proof) !== canonicalJson(traced) ||
      proof.contractVersion !== 1 ||
      proof.producerScope !== "glasshive.worker_isolation"
    )
      throw unproven();
    let workspace = String(row.workspaceRoot || "");
    try {
      workspace = fs.realpathSync(workspace);
    } catch {
      workspace = path.resolve(workspace);
    }
    const expected = {
      ownerRefHash: traceFingerprint("owner", ownerId),
      workRefHash: traceFingerprint("work", row.workRef),
      runRefHash: traceFingerprint("run", row.runRef),
      workerRefHash: traceFingerprint("worker", row.workerRef),
      attemptRefHash: traceFingerprint("attempt", row.attemptRef),
      leaseRefHash: traceFingerprint("lease", row.leaseRef),
      containerRefHash: traceFingerprint("container", row.containerRef),
      workspaceRefHash: traceFingerprint("workspace", workspace),
    };
    if (
      Object.entries(expected).some(([field, value]) => proof[field] !== value)
    )
      throw unproven();
    if (
      !/^sha256:[a-f0-9]{64}$/.test(String(proof.homeRefHash || "")) ||
      !/^sha256:[a-f0-9]{64}$/.test(String(proof.networkRefHash || "")) ||
      proof.pidNamespaceRefHash !==
        traceFingerprint("pid_namespace", row.containerRef) ||
      proof.executionMode !== "isolated_container" ||
      [
        "hostStateReadable",
        "serviceEnvironmentReadable",
        "dockerSocketReadable",
        "ambientAuthority",
      ].some((field) => proof[field] !== false) ||
      proof.hostAccessDenied !== true ||
      !Array.isArray(proof.peerProbes)
    )
      throw unproven();
    const peerHashes = proof.peerProbes.map((peer) => {
      if (
        !peer ||
        Object.keys(peer).length !== 2 ||
        peer.reachable !== false ||
        !/^sha256:[a-f0-9]{64}$/.test(String(peer.workRefHash || ""))
      )
        throw unproven();
      return peer.workRefHash;
    });
    if (
      new Set(peerHashes).size !== peerHashes.length ||
      proof.peerAccessDenied !== peerHashes.length > 0
    )
      throw unproven();
    const correlation = {
      ownerRefHash: proof.ownerRefHash,
      workRefHash: proof.workRefHash,
      runRefHash: proof.runRefHash,
      attemptRefHash: proof.attemptRefHash,
      leaseRefHash: proof.leaseRefHash,
      containerRefHash: proof.containerRefHash,
      peers: peerHashes,
    };
    const digest = sha256(canonicalJson(correlation));
    if (
      record.eventId !== `evt_isolation_${digest}` ||
      record.traceEventId !== `trace_isolation_${digest}`
    )
      throw unproven();
    if (!verifiedTraces.has(row.runRef)) {
      let chain;
      try {
        chain = store
          .prepare(
            `SELECT trace_event_id AS traceEventId, run_id AS runRef, work_ref AS workRef,
                  sequence AS sequence, event_type AS eventType, payload_json AS payloadJson,
                  previous_event_sha256 AS previousEventSha256,
                  event_sha256 AS eventSha256, created_at AS createdAt
           FROM work_trace_events
           WHERE run_id = ? AND work_ref = ? AND owner_id = ?
           ORDER BY sequence ASC`,
          )
          .all(row.runRef, row.workRef, ownerId);
      } catch {
        throw unavailable();
      }
      if (!chain.length) throw unavailable();
      let previous = "";
      for (const [index, entry] of chain.entries()) {
        let payload;
        try {
          payload = JSON.parse(String(entry.payloadJson || "{}"));
        } catch {
          throw unproven();
        }
        const expectedHash = sha256(
          canonicalJson({
            createdAt: entry.createdAt,
            eventType: entry.eventType,
            payload,
            previousEventSha256: entry.previousEventSha256,
            runId: entry.runRef,
            sequence: Number(entry.sequence),
            traceEventId: entry.traceEventId,
            workRef: entry.workRef,
          }),
        );
        if (
          Number(entry.sequence) !== index + 1 ||
          entry.previousEventSha256 !== previous ||
          entry.eventSha256 !== expectedHash
        )
          throw unproven();
        previous = expectedHash;
      }
      verifiedTraces.add(row.runRef);
    }
    const expectedPeers = rows
      .filter((peer) => peer.runRef !== row.runRef)
      .map((peer) => traceFingerprint("work", peer.workRef))
      .sort();
    if (
      canonicalJson(peerHashes.slice().sort()) !== canonicalJson(expectedPeers)
    )
      continue;
    if (selected.has(row.runRef)) throw unproven();
    selected.set(row.runRef, proof);
  }
  if (selected.size !== rows.length) throw unavailable();
  const workers = rows.map((row) => selected.get(row.runRef));
  for (const field of [
    "workerRefHash",
    "containerRefHash",
    "workspaceRefHash",
    "homeRefHash",
    "networkRefHash",
    "pidNamespaceRefHash",
  ]) {
    if (new Set(workers.map((worker) => worker[field])).size !== workers.length)
      throw unproven();
  }
  return {
    peerAccessDenied: true,
    hostAccessDenied: true,
    auditVerified: true,
    workers,
  };
}

function parseEnvFile(location) {
  if (!fs.existsSync(location)) return {};
  const values = {};
  for (const raw of fs.readFileSync(location, "utf8").split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const equals = line.indexOf("=");
    if (equals <= 0) continue;
    const key = line.slice(0, equals).trim();
    let value = line.slice(equals + 1).trim();
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

function loadReadOnlyRuntimeEnv(args, environment) {
  const runtimeRoot = fs.realpathSync(args.runtimeRoot);
  const values = {
    ...parseEnvFile(path.join(LIBRECHAT_ROOT, ".env")),
    ...parseEnvFile(path.join(runtimeRoot, "runtime.env")),
    ...parseEnvFile(path.join(runtimeRoot, "runtime.local.env")),
    ...parseEnvFile(path.join(runtimeRoot, "service-env", "librechat.env")),
    ...parseEnvFile(
      path.join(runtimeRoot, "service-env", "librechat.owner.env"),
    ),
    ...parseEnvFile(path.join(runtimeRoot, "service-env", "glasshive.env")),
    ...environment,
  };
  if (!String(values.MONGO_URI || "").trim())
    throw blockedError("installed_mongo_uri_unavailable");
  if (
    !String(values.WPR_DB_PATH || "").trim() ||
    fs.realpathSync(values.WPR_DB_PATH) !==
      fs.realpathSync(args.glassHiveDbPath)
  ) {
    throw blockedError("installed_glasshive_database_identity_unproven");
  }
  return values;
}

function measureInstalledCandidate(args) {
  const script = path.join(
    REPO_ROOT,
    "scripts",
    "viventium",
    "parallel_work_release_gate.py",
  );
  const probe = [
    "import importlib.util,json,sys",
    "from pathlib import Path",
    "spec=importlib.util.spec_from_file_location('viventium_pwk_live_identity_probe',sys.argv[1])",
    "module=importlib.util.module_from_spec(spec)",
    "sys.modules[spec.name]=module",
    "spec.loader.exec_module(module)",
    "identity=json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))",
    "root=Path(sys.argv[3])",
    "prompt=Path(sys.argv[4])",
    "installed=Path(sys.argv[5])",
    "owner_path=Path(sys.argv[6])",
    "runtime=Path(sys.argv[7])",
    "checks,_=module._artifact_identity_checks(root,identity,prompt,installed,owner_path)",
    "candidate,artifact=module._qa_candidate_digests(identity)",
    "active=module._runtime_owner_state_proves_active(installed,owner_path)",
    "owner=json.loads(owner_path.read_text(encoding='utf-8'))",
    "measured=module._public_artifact_identity(module._measured_artifact_identity(root,prompt,installed,owner_path))",
    "diagnostic_candidate=module._canonical_hash({'source':measured.get('source'),'nestedComponents':measured.get('nestedComponents'),'prebuiltHelper':measured.get('prebuiltHelper')})",
    "diagnostic_artifact=module._canonical_hash(measured.get('installed'))",
    "binding={'active':active,'ownerRootMatches':active and Path(str(owner.get('repoRoot') or '')).resolve(strict=True)==installed.resolve(strict=True),'runtimeRootMatches':active and Path(str(owner.get('runtimeDir') or '')).resolve(strict=True)==runtime.resolve(strict=True),'ownerBindingSha256':str(owner.get('ownerBindingSha256') or ''),'processIdentitySha256':module._canonical_hash({'pid':str(owner.get('ownerPid') or ''),'startedAt':str(owner.get('ownerProcessStartedAt') or ''),'executable':str(owner.get('ownerExecutablePath') or '')}) if active else ''}",
    "print(json.dumps({'candidateDigest':candidate,'artifactDigest':artifact,'diagnosticCandidateDigest':diagnostic_candidate,'diagnosticArtifactDigest':diagnostic_artifact,'checks':[{'id':item.check_id,'status':item.status,'reason':item.reason} for item in checks],'runtimeBinding':binding,'measuredIdentity':measured}))",
  ].join(";");
  const result = spawnSync(
    "python3",
    [
      "-c",
      probe,
      script,
      args.identityPath,
      REPO_ROOT,
      path.join(args.runtimeRoot, "prompt-bundle.json"),
      args.installedRoot,
      args.ownerStatePath,
      args.runtimeRoot,
    ],
    { encoding: "utf8", timeout: 30000, maxBuffer: 1024 * 1024 },
  );
  if (result.status !== 0)
    throw blockedError("installed_candidate_identity_unproven");
  try {
    const measured = JSON.parse(result.stdout);
    if (args.candidateMode === "diagnostic") {
      return assertDiagnosticCandidate({
        ...measured,
        candidateDigest: measured.diagnosticCandidateDigest,
        artifactDigest: measured.diagnosticArtifactDigest,
      });
    }
    return assertMeasuredCandidate(measured);
  } catch {
    throw blockedError(
      args.candidateMode === "diagnostic"
        ? "diagnostic_active_runtime_identity_unproven"
        : "installed_candidate_identity_unproven",
    );
  }
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

function prefixedSha256(value) {
  return `sha256:${sha256(Buffer.from(value, "utf8"))}`;
}

function traceFingerprint(kind, value) {
  return prefixedSha256(`${kind}\0${String(value).trim()}`);
}

function verifyTraceRows(
  rows,
  ownerId,
  originRef,
  workRef,
  runRef,
  callbackRef,
  attemptNumber,
  followUpMessageId,
) {
  if (!Array.isArray(rows) || !rows.length || rows.length > 100) return false;
  const exactFollowUpMessageId = String(followUpMessageId || "").trim();
  if (
    !CANONICAL_CALLBACK_REF.test(String(callbackRef || "")) ||
    !Number.isSafeInteger(attemptNumber) ||
    attemptNumber < 1 ||
    !exactFollowUpMessageId
  ) {
    return false;
  }
  const ownerScopeHash = traceFingerprint("owner", ownerId);
  const originRefHash = traceFingerprint("origin", originRef);
  const workRefHash = traceFingerprint("work", workRef);
  const runRefHash = traceFingerprint("run", runRef);
  const callbackRefHash = traceFingerprint("callback", callbackRef);
  const deliveryRefHash = traceFingerprint(
    "delivery",
    `main-web:${exactFollowUpMessageId}`,
  );
  let previous = `sha256:${"0".repeat(64)}`;
  let sequence = 1;
  const observed = new Set();
  let runtimeInvokedAt = Number.NaN;
  let providerForwardedAt = Number.NaN;
  const callbackAccepted = [];
  const callbackDelivered = [];
  for (const event of rows) {
    const facts = event.facts || {};
    const eventAt = Date.parse(String(event.at || ""));
    if (!Number.isFinite(eventAt)) return false;
    const at = new Date(eventAt).toISOString();
    const contentHash = prefixedSha256(
      canonicalJson({ schemaVersion: 1, stage: event.stage, facts }),
    );
    const eventHash = prefixedSha256(
      canonicalJson({
        schemaVersion: 1,
        ownerScopeHash,
        originRefHash,
        sequence: event.sequence,
        stage: event.stage,
        at,
        facts,
        eventKeyHash: event.eventKeyHash,
        contentHash: event.contentHash,
        previousEventHash: event.previousEventHash,
      }),
    );
    if (
      event.schemaVersion !== 1 ||
      event.ownerScopeHash !== ownerScopeHash ||
      event.originRefHash !== originRefHash ||
      event.sequence !== sequence ||
      event.previousEventHash !== previous ||
      event.contentHash !== contentHash ||
      event.eventHash !== eventHash ||
      (facts.workRefHash && facts.workRefHash !== workRefHash) ||
      (facts.runRefHash && facts.runRefHash !== runRefHash)
    ) {
      return false;
    }
    if (
      [
        "prompt.layers.verified",
        "work.admitted",
        "runtime.invoked",
        "work.completed",
      ].includes(event.stage) &&
      facts.producerTraceContractVersion !== 2
    )
      return false;
    if (
      event.stage === "prompt.layers.verified" &&
      facts.promptProducerScope !== "glasshive.worker_prompt_registry"
    )
      return false;
    if (event.stage === "runtime.invoked")
      runtimeInvokedAt = Date.parse(event.at);
    if (event.stage === "provider.request.forwarded") {
      if (
        facts.providerStatus !== "completed" ||
        !PREFIXED_SHA256.test(String(facts.providerRequestRefHash || ""))
      )
        return false;
      providerForwardedAt = Date.parse(event.at);
    }
    if (
      event.stage === "callback.accepted" ||
      event.stage === "callback.delivery.sent"
    ) {
      if (
        facts.workRefHash !== workRefHash ||
        facts.runRefHash !== runRefHash ||
        facts.callbackRefHash !== callbackRefHash ||
        facts.callbackEvent !== "run.completed" ||
        facts.state !== "completed" ||
        facts.terminal !== true ||
        facts.attemptNumber !== attemptNumber
      ) {
        return false;
      }
      if (event.stage === "callback.accepted") {
        callbackAccepted.push(event);
      } else {
        if (
          facts.deliveryRefHash !== deliveryRefHash ||
          facts.surface !== "web" ||
          facts.deliveryState !== "sent"
        ) {
          return false;
        }
        callbackDelivered.push(event);
      }
    }
    observed.add(event.stage);
    previous = event.eventHash;
    sequence += 1;
  }
  return (
    [
      "source.bound",
      "prompt.layers.verified",
      "work.admitted",
      "runtime.invoked",
      "provider.request.forwarded",
      "work.completed",
      "callback.accepted",
      "callback.delivery.sent",
    ].every((stage) => observed.has(stage)) &&
    Number.isFinite(runtimeInvokedAt) &&
    Number.isFinite(providerForwardedAt) &&
    providerForwardedAt >= runtimeInvokedAt &&
    callbackAccepted.length === 1 &&
    callbackDelivered.length === 1 &&
    callbackDelivered[0].sequence > callbackAccepted[0].sequence &&
    Date.parse(callbackDelivered[0].at) >= Date.parse(callbackAccepted[0].at)
  );
}

function verifiedTelegramDocument(manifest, evidenceRoot, kind) {
  const entries = Array.isArray(manifest?.evidence)
    ? manifest.evidence.filter((entry) => entry?.kind === kind)
    : [];
  if (
    entries.length !== 1 ||
    !/^[A-Za-z0-9_.-]+$/.test(String(entries[0].path || "")) ||
    !SHA256.test(String(entries[0].sha256 || ""))
  ) {
    return null;
  }
  try {
    const root = fs.realpathSync(evidenceRoot);
    const resolved = fs.realpathSync(path.join(root, entries[0].path));
    if (path.dirname(resolved) !== root || !fs.statSync(resolved).isFile())
      return null;
    if (fs.statSync(resolved).size > 8 * 1024 * 1024) return null;
    const bytes = fs.readFileSync(resolved);
    if (sha256(bytes) !== entries[0].sha256) return null;
    const document = JSON.parse(bytes.toString("utf8"));
    return document?.payload && typeof document.payload === "object"
      ? document.payload
      : null;
  } catch {
    return null;
  }
}

function deriveTelegramProof({
  result,
  manifest,
  evidenceRoot,
  identity,
  logicalTurnHash,
}) {
  const requiredGates = [
    "authoritative-signed-280ms-race-audit",
    "pre-commit-revision-and-post-commit-correction",
    "direct-telegram-desktop-visible-and-reopened",
    "original-user-order-and-one-persisted-final-answer",
  ];
  if (
    result?.caseId !== "TR-026" ||
    result.status !== "PASS" ||
    result.ready !== true ||
    result.surface !== "telegram" ||
    result.candidateDigest !== identity?.candidateDigest ||
    result.artifactDigest !== identity?.artifactDigest ||
    manifest?.candidate?.candidateDigest !== identity?.candidateDigest ||
    manifest?.candidate?.artifactDigest !== identity?.artifactDigest ||
    !SHA256.test(String(logicalTurnHash || "")) ||
    manifest?.correlation?.turnRefHash !== logicalTurnHash ||
    !Array.isArray(result.gates) ||
    requiredGates.some(
      (id) =>
        result.gates.filter((gate) => gate?.id === id && gate.status === "PASS")
          .length !== 1,
    )
  ) {
    return null;
  }
  const source = verifiedTelegramDocument(
    manifest,
    evidenceRoot,
    "telegram_source_trace",
  );
  const history = verifiedTelegramDocument(
    manifest,
    evidenceRoot,
    "mongo_history",
  );
  const ui = verifiedTelegramDocument(
    manifest,
    evidenceRoot,
    "telegram_ui_observation",
  );
  const core = verifiedTelegramDocument(
    manifest,
    evidenceRoot,
    "core_revision_trace",
  );
  if (!source || !history || !ui || !core) return null;

  const admissions = (Array.isArray(source.events) ? source.events : []).filter(
    (event) => event?.event === "core_ingestion_admitted",
  );
  const messages = Array.isArray(history.beforeReopen?.messages)
    ? history.beforeReopen.messages
    : [];
  const finalReplyCount = messages.filter(
    (message) =>
      message?.role === "assistant" && message.turnRefHash === logicalTurnHash,
  ).length;
  const captures = Array.isArray(ui.captures) ? ui.captures : [];
  const scenarios = Array.isArray(core.scenarios) ? core.scenarios : [];
  const nativeDesktop =
    ui.bundleId === "ru.keepcoder.Telegram" &&
    ui.surface === "telegram" &&
    captures.length > 0 &&
    captures.every(
      (capture) =>
        capture?.captureOrigin === "native_desktop_window_capture" &&
        capture.windowVisible === true,
    );
  const revisionBeforeCommit =
    scenarios.length > 0 &&
    scenarios.every(
      (scenario) =>
        scenario?.initialRevision === 1 && scenario.correctedRevision === 2,
    );
  const delayMs = admissions.length === 1 ? admissions[0].delayMs : null;
  if (
    !nativeDesktop ||
    !revisionBeforeCommit ||
    finalReplyCount !== 1 ||
    delayMs !== 280
  ) {
    return null;
  }
  return {
    verified: true,
    nativeDesktop,
    revisionBeforeCommit,
    finalReplyCount,
    delayMs,
  };
}

function renderMessage(message) {
  if (typeof message?.text === "string" && message.text.trim())
    return message.text.trim();
  return (Array.isArray(message?.content) ? message.content : [])
    .filter((part) => part?.type === "text" && typeof part.text === "string")
    .map((part) => part.text)
    .join("")
    .trim();
}

function nestedScopeHash(domain, value) {
  return prefixedSha256(
    `glasshive-local-qa-v1\0${domain}\0${String(value || "")}`,
  );
}

function fixtureOwnerScopeAttestation(scope, signingSecret) {
  const fields = [
    "caseId",
    "contractVersion",
    "expiresAtMs",
    "issuedAtMs",
    "nonce",
    "ownerEmail",
    "ownerId",
    "ownerRole",
    "sessionRef",
  ];
  const payload = Object.fromEntries(
    fields.map((field) => [field, scope?.[field]]),
  );
  return `sha256:${crypto
    .createHmac("sha256", String(signingSecret || ""))
    .update(`glasshive-selected-owner-scope-v1\0${canonicalJson(payload)}`)
    .digest("hex")}`;
}

function createFixtureOwnerScope({
  caseId,
  sessionRef,
  ownerId,
  user,
  signingSecret,
  nowMs = Date.now(),
  nonce = crypto.randomBytes(16).toString("hex"),
}) {
  const email = String(user?.email || "")
    .trim()
    .toLowerCase();
  const role = String(user?.role || "")
    .trim()
    .toUpperCase();
  const parts = email.split("@");
  if (
    !Object.hasOwn(CASE_FAULT_BOUNDARIES, String(caseId || "")) ||
    !/^[A-Za-z0-9_:-]{8,160}$/.test(String(sessionRef || "")) ||
    !/^[A-Za-z0-9_:-]{8,160}$/.test(String(ownerId || "")) ||
    parts.length !== 2 ||
    !parts[0] ||
    !new Set(["example.com", "viventium.local", "localhost"]).has(parts[1]) ||
    role !== "USER" ||
    !String(signingSecret || "").trim() ||
    !Number.isSafeInteger(nowMs) ||
    !/^[a-f0-9]{32}$/.test(String(nonce || ""))
  )
    throw blockedError("selected_fixture_owner_scope_invalid");
  const payload = {
    caseId,
    contractVersion: 1,
    expiresAtMs: nowMs + 30000,
    issuedAtMs: nowMs,
    nonce,
    ownerEmail: email,
    ownerId: String(ownerId),
    ownerRole: role,
    sessionRef: String(sessionRef),
  };
  return {
    ...payload,
    attestation: fixtureOwnerScopeAttestation(payload, signingSecret),
  };
}

async function invokeLocalQaControl(
  args,
  command,
  parameters = [],
  privateInput = null,
) {
  const allowed = new Set([
    "status",
    "prepare-glasshive",
    "arm-glasshive",
    "query-glasshive",
    "clear-glasshive",
    "cleanup-glasshive",
  ]);
  if (!allowed.has(command) || !Array.isArray(parameters)) {
    throw blockedError("unsupported_local_qa_control_operation");
  }
  if (command !== "status" && args.allowFaults !== true) {
    throw blockedError("glasshive_faults_require_explicit_permission");
  }
  if (
    command === "prepare-glasshive" &&
    (!privateInput || typeof privateInput !== "object")
  ) {
    throw blockedError("selected_fixture_owner_scope_required");
  }
  let executable;
  try {
    executable = fs.realpathSync(
      path.join(args.installedRoot, "bin", "viventium"),
    );
    if (!fs.statSync(executable).isFile()) throw new Error("missing");
  } catch {
    throw blockedError("installed_parent_qa_control_unavailable");
  }
  const privateJson =
    privateInput == null ? undefined : `${canonicalJson(privateInput)}\n`;
  if (privateJson && Buffer.byteLength(privateJson) > 8192) {
    throw blockedError("selected_fixture_owner_scope_invalid");
  }
  const result = spawnSync(executable, ["qa-control", command, ...parameters], {
    cwd: args.installedRoot,
    encoding: "utf8",
    input: privateJson,
    timeout: 45000,
    maxBuffer: 1024 * 1024,
  });
  if (result.status !== 0)
    throw blockedError(`parent_qa_control_${command}_rejected`);
  try {
    const value = JSON.parse(result.stdout);
    if (!value || typeof value !== "object" || Array.isArray(value))
      throw new Error("invalid");
    return value;
  } catch {
    throw blockedError(`parent_qa_control_${command}_response_invalid`);
  }
}

async function withGlassHiveFaultFixture({
  args,
  ownerId,
  ownerAccount,
  signingSecret,
  invokeControl,
  perform,
}) {
  if (!Object.hasOwn(CASE_FAULT_BOUNDARIES, args?.caseId)) {
    throw blockedError("controlled_fault_case_required");
  }
  const invoke =
    invokeControl ||
    ((command, parameters = [], privateInput = null) =>
      invokeLocalQaControl(args, command, parameters, privateInput));
  const status = await invoke("status");
  if (
    status?.caseId !== args.caseId ||
    status.restartState !== "ready" ||
    !Array.isArray(status.missingServices) ||
    status.missingServices.length !== 0 ||
    !String(status.sessionRef || "").trim()
  )
    throw blockedError("case_bound_parent_fault_session_not_ready");
  const ownerScope = createFixtureOwnerScope({
    caseId: args.caseId,
    sessionRef: status.sessionRef,
    ownerId,
    user: ownerAccount,
    signingSecret,
  });
  let prepared = false;
  let originalFailure = null;
  try {
    const fixture = await invoke(
      "prepare-glasshive",
      ["--case-id", args.caseId],
      ownerScope,
    );
    prepared = true;
    if (
      fixture?.caseId !== args.caseId ||
      fixture.status !== "ready" ||
      fixture.scopeHashes?.owner !== nestedScopeHash("owner", ownerId)
    )
      throw blockedError("controlled_fixture_owner_mismatch");
    return await perform({ fixture, invokeControl: invoke });
  } catch (error) {
    originalFailure = error;
    throw error;
  } finally {
    if (prepared) {
      let cleanupFailure = null;
      await invoke("clear-glasshive").catch((error) => {
        cleanupFailure = error;
      });
      await invoke("cleanup-glasshive").catch((error) => {
        cleanupFailure = error;
      });
      if (cleanupFailure && !originalFailure) {
        throw blockedError("controlled_fault_fixture_cleanup_failed");
      }
    }
  }
}

function readConsumedFaultObservation(
  store,
  { caseId, ownerId, controlRef, expectedBoundary },
) {
  let row;
  try {
    row = store
      .prepare(
        `SELECT controls.boundary AS boundary,
              controls.control_ref AS controlRef,
              controls.status AS status,
              controls.consumed_at AS consumedAt,
              controls.consumption_count AS consumptionCount,
              COUNT(CASE WHEN audit.action = 'effect_applied' THEN 1 END) AS effectCount
       FROM local_qa_fault_controls controls
       LEFT JOIN local_qa_fault_audit audit ON audit.control_ref = controls.control_ref
       WHERE controls.case_id = ? AND controls.control_ref = ? AND controls.owner_hash = ?
       GROUP BY controls.control_ref`,
      )
      .get(caseId, controlRef, nestedScopeHash("owner", ownerId));
  } catch {
    throw blockedError("installed_fault_audit_ledger_unavailable");
  }
  if (
    !row ||
    row.boundary !== expectedBoundary ||
    row.status !== "consumed" ||
    row.consumptionCount !== 1 ||
    row.effectCount !== 1 ||
    !timestamp(row.consumedAt)
  )
    return null;
  return {
    boundary: row.boundary,
    controlRef: row.controlRef,
    status: "consumed",
    ownerId,
    consumedAt: row.consumedAt,
    effectCount: row.effectCount,
  };
}

function deriveMeasuredCapacityShortage(rows, ownerId) {
  for (const row of Array.isArray(rows) ? rows : []) {
    if (row?.ownerId !== ownerId) continue;
    let available;
    let required;
    let shortage;
    try {
      available = JSON.parse(String(row.availableJson || "{}"));
      required = JSON.parse(String(row.requiredJson || "{}"));
      shortage = JSON.parse(String(row.shortageJson || "{}"));
    } catch {
      continue;
    }
    if (
      available.memoryBytes === Math.floor(4.3 * 1024 ** 3) &&
      required.memoryBytes === 5 * 1024 ** 3 &&
      shortage.memoryBytes === required.memoryBytes - available.memoryBytes &&
      timestamp(row.nextRetryAt)
    ) {
      return {
        availableBytes: available.memoryBytes,
        requiredBytes: required.memoryBytes,
        shortageBytes: shortage.memoryBytes,
        nextRetryAt: row.nextRetryAt,
      };
    }
  }
  throw blockedError("measured_owner_scoped_capacity_shortage_unavailable");
}

function deriveQueueTimeoutTransitions({
  faults,
  events,
  ownerId,
  lookupRunHash,
}) {
  const unavailable = () =>
    blockedError("exact_claimed_and_admitted_terminal_transitions_unavailable");
  if (
    !Array.isArray(faults) ||
    !Array.isArray(events) ||
    typeof lookupRunHash !== "function"
  ) {
    throw unavailable();
  }
  const observedRuns = new Set();
  return ["claimed", "admitted"].map((state) => {
    const matchingFaults = faults.filter(
      (fault) =>
        fault?.boundary === `${state}_queue_stall` &&
        fault.ownerId === ownerId &&
        fault.status === "consumed" &&
        fault.effectCount === 1 &&
        timestamp(fault.consumedAt),
    );
    if (matchingFaults.length !== 1) throw unavailable();
    const fault = matchingFaults[0];
    let expectedRunHash;
    try {
      expectedRunHash = lookupRunHash(fault.controlRef);
    } catch {
      throw unavailable();
    }
    if (!/^sha256:[a-f0-9]{64}$/.test(String(expectedRunHash || "")))
      throw unavailable();
    const matchingEvents = events.filter((event) => {
      if (
        event?.ownerId !== ownerId ||
        event.eventType !== "run.failed" ||
        !String(event.runRef || "").trim() ||
        nestedScopeHash("run", event.runRef) !== expectedRunHash ||
        !timestamp(event.createdAt) ||
        timestamp(event.createdAt) < timestamp(fault.consumedAt)
      )
        return false;
      try {
        const payload = JSON.parse(String(event.payloadJson || "{}"));
        return (
          payload?.failureClass === "queue_wait_timeout" &&
          timestamp(payload.timeoutAt)
        );
      } catch {
        return false;
      }
    });
    if (
      matchingEvents.length !== 1 ||
      observedRuns.has(matchingEvents[0].runRef)
    ) {
      throw unavailable();
    }
    observedRuns.add(matchingEvents[0].runRef);
    return { state, terminalTransitions: 1 };
  });
}

function deriveAtomicReservationAttempts({
  capacityRows,
  bindingRows,
  leaseRows,
  ownerId,
  observedAt,
}) {
  const unavailable = () =>
    blockedError("atomic_reservation_race_user_request_evidence_unavailable");
  const earliest = timestamp(observedAt);
  if (
    !earliest ||
    !Array.isArray(capacityRows) ||
    !Array.isArray(bindingRows) ||
    !Array.isArray(leaseRows) ||
    bindingRows.length !== 2 ||
    bindingRows.some((binding) => binding?.ownerId !== ownerId)
  )
    throw unavailable();
  const accepted = bindingRows.filter(
    (binding) =>
      new Set(["accepted", "callback_confirmed"]).has(binding.launchState) &&
      String(binding.workRef || "").trim(),
  );
  const rejected = bindingRows.filter(
    (binding) =>
      binding.launchState === "not_dispatched" &&
      !String(binding.workRef || "").trim() &&
      new Set(["host_capacity", "mission_slots", "resource_pressure"]).has(
        binding.preDispatchFailureCode,
      ) &&
      timestamp(binding.preDispatchFailedAt) >= earliest,
  );
  if (
    accepted.length !== 1 ||
    rejected.length !== 1 ||
    !String(accepted[0].originRef || "").trim() ||
    !String(rejected[0].originRef || "").trim() ||
    accepted[0].originRef === rejected[0].originRef ||
    !String(accepted[0].sourceEventId || "").trim() ||
    accepted[0].sourceEventId !== rejected[0].sourceEventId
  )
    throw unavailable();
  const reservations = capacityRows.filter(
    (attempt) =>
      attempt?.ownerId === ownerId &&
      attempt.workRef === accepted[0].workRef &&
      attempt.capacityClass === "admission_reserved" &&
      timestamp(attempt.observedAt) >= earliest,
  );
  const measured = reservations.filter((attempt) => {
    const matching = leaseRows.filter(
      (lease) =>
        lease?.ownerId === ownerId &&
        lease.workRef === attempt.workRef &&
        lease.runRef === attempt.runRef &&
        String(lease.leaseRef || "").trim() &&
        timestamp(lease.acquiredAt) >= earliest,
    );
    if (matching.length !== 1) return false;
    try {
      const reservation = JSON.parse(String(attempt.reservationJson || "{}"));
      return (
        Number.isSafeInteger(reservation.memoryBytes) &&
        reservation.memoryBytes > 0 &&
        matching[0].reservedMemoryBytes === reservation.memoryBytes
      );
    } catch {
      return false;
    }
  });
  if (measured.length !== 1) throw unavailable();
  const lease = leaseRows.find(
    (candidate) =>
      candidate.ownerId === ownerId && candidate.runRef === measured[0].runRef,
  );
  return [
    {
      requestRef: accepted[0].originRef,
      slotRef: lease.leaseRef,
      outcome: "reserved",
      workRef: accepted[0].workRef,
    },
    {
      requestRef: rejected[0].originRef,
      slotRef: lease.leaseRef,
      outcome: "rejected",
      workRef: null,
    },
  ];
}

function scanHostileArtifactBytes(bytes, privateValues = []) {
  if (
    !Buffer.isBuffer(bytes) ||
    bytes.length < 16 ||
    bytes.length > 1024 * 1024
  ) {
    throw blockedError("hostile_artifact_bytes_unavailable");
  }
  const value = bytes.toString("utf8");
  const sensitive = privateValues
    .filter(
      (candidate) => typeof candidate === "string" && candidate.length >= 8,
    )
    .some((candidate) => value.includes(candidate));
  if (sensitive || /(?:\/Users\/|Bearer\s+[A-Za-z0-9._-]{12,})/i.test(value)) {
    throw blockedError("hostile_artifact_private_disclosure_detected");
  }
  return {
    scannedArtifactSha256: sha256(bytes),
    findingCount: 0,
    privateLeakCount: 0,
    hostAuthorityExecutionCount: 0,
  };
}

function artifactRelativePath({ href, ariaLabel, base }) {
  const location = assertLoopbackUrl(
    new URL(String(href || ""), base).toString(),
    "artifact",
  );
  const label = String(ariaLabel || "").trim();
  const visiblePath = label.startsWith("Open ") ? label.slice(5).trim() : "";
  const signedPath = String(location.searchParams.get("path") || "").trim();
  const candidate = signedPath || visiblePath;
  const normalized = path.posix.normalize(candidate);
  if (
    !candidate ||
    (signedPath && visiblePath && signedPath !== visiblePath) ||
    normalized !== candidate ||
    path.posix.isAbsolute(candidate) ||
    normalized.startsWith("../") ||
    normalized === ".." ||
    !/\.html?$/i.test(normalized)
  ) {
    throw blockedError("owner_scoped_artifact_path_unavailable");
  }
  return normalized;
}

function signScopedCallbackPayload(payload, signingMaterial) {
  if (!String(signingMaterial || "").trim()) {
    throw blockedError("signed_cross_owner_callback_authority_unavailable");
  }
  const worker = String(payload?.worker_id || "").trim();
  const run = String(payload?.run_id || "").trim();
  if (!worker || !run) {
    throw blockedError("signed_cross_owner_callback_identity_unavailable");
  }
  const runSigningMaterial = crypto
    .createHmac("sha256", signingMaterial)
    .update(`${worker}:${run}`)
    .digest("hex");
  return `sha256=${crypto
    .createHmac("sha256", runSigningMaterial)
    .update(canonicalJson(payload))
    .digest("hex")}`;
}

function readPrivateRestartProof(args, identity, ownerId) {
  try {
    const location = fs.realpathSync(args.restartReadinessPath);
    const stats = fs.statSync(location);
    if (
      !stats.isFile() ||
      (stats.mode & 0o077) !== 0 ||
      stats.size > 24 * 1024
    ) {
      throw new Error("unsafe");
    }
    const proof = JSON.parse(fs.readFileSync(location, "utf8"));
    if (
      proof?.caseId !== args.caseId ||
      proof.candidateDigest !== identity.candidateDigest ||
      proof.approved !== true ||
      proof.ownerRefHash !== traceFingerprint("owner", ownerId) ||
      !timestamp(proof.expiresAt) ||
      timestamp(proof.expiresAt) <= Date.now()
    )
      throw new Error("mismatch");
    return proof;
  } catch {
    throw blockedError("restart_operator_readiness_proof_unavailable");
  }
}

function currentCaseTelegramSurface({ args, identity, ownerId }) {
  if (!args.telegramManifest || !args.telegramEvidenceRoot) return false;
  try {
    const manifest = JSON.parse(fs.readFileSync(args.telegramManifest, "utf8"));
    if (
      manifest.caseId !== args.caseId ||
      manifest.candidate?.candidateDigest !== identity.candidateDigest ||
      manifest.candidate?.artifactDigest !== identity.artifactDigest ||
      manifest.correlation?.ownerRefHash !== traceFingerprint("owner", ownerId)
    )
      return false;
    const observation = verifiedTelegramDocument(
      manifest,
      args.telegramEvidenceRoot,
      "telegram_observation",
    );
    return (
      observation?.captureSource === "telegram_desktop" &&
      observation.visible === true
    );
  } catch {
    return false;
  }
}

async function waitFor(check, { timeoutMs, reason, pollMs = 300 }) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const value = await check();
    if (value) return value;
    await new Promise((resolve) => setTimeout(resolve, pollMs));
  }
  throw blockedError(reason);
}

const QUICK_TURN_BOUNDARY_STAGES = Object.freeze([
  "controller_admission",
  "concurrency_admitted",
  "client_initialization_start",
  "client_initialization_end",
  "main_pipeline_start",
  "main_pipeline_complete",
  "assistant_durable",
  "final_event_emitted",
  "presentation_committed",
]);
const QUICK_TURN_TIMING_KEYS = Object.freeze({
  viventium_text_turn_boundary: Object.freeze([
    "event",
    "turnIdHash",
    "stage",
    "observedAtMs",
    "fromTurnStartMs",
  ]),
  viventium_text_main_provider_attempt_start: Object.freeze([
    "event",
    "turnIdHash",
    "invocationId",
    "attemptIndex",
    "providerAttemptIdHash",
    "observedAtMs",
    "fromTurnStartMs",
  ]),
  viventium_text_main_first_provider_output: Object.freeze([
    "event",
    "turnIdHash",
    "invocationId",
    "attemptIndex",
    "providerAttemptIdHash",
    "outputKind",
    "observedAtMs",
    "fromTurnStartMs",
    "fromAttemptStartMs",
  ]),
  viventium_text_main_provider_attempt_end: Object.freeze([
    "event",
    "turnIdHash",
    "invocationId",
    "attemptIndex",
    "providerAttemptIdHash",
    "toolCallCount",
    "observedAtMs",
    "fromTurnStartMs",
    "fromAttemptStartMs",
  ]),
  viventium_text_main_tool_start: Object.freeze([
    "event",
    "turnIdHash",
    "invocationId",
    "attemptIndex",
    "toolIndex",
    "toolInvocationIdHash",
    "observedAtMs",
    "fromTurnStartMs",
    "fromAttemptStartMs",
  ]),
  viventium_text_main_tool_end: Object.freeze([
    "event",
    "turnIdHash",
    "invocationId",
    "attemptIndex",
    "toolIndex",
    "toolInvocationIdHash",
    "observedAtMs",
    "fromTurnStartMs",
    "fromAttemptStartMs",
  ]),
});

function rejectedQuickTurnTiming(reason, turnIdHash) {
  return {
    complete: false,
    reason,
    turnIdHash: SHORT_SHA256.test(String(turnIdHash || "")) ? turnIdHash : null,
  };
}

function readExactFileRange(descriptor, startOffset, byteLength) {
  const bytes = Buffer.alloc(byteLength);
  let bytesRead = 0;
  while (bytesRead < byteLength) {
    const count = fs.readSync(
      descriptor,
      bytes,
      bytesRead,
      byteLength - bytesRead,
      startOffset + bytesRead,
    );
    if (count <= 0) return null;
    bytesRead += count;
  }
  return bytes;
}

function captureCoreLogWindow(coreLogPath) {
  const requestedPath = path.resolve(String(coreLogPath || ""));
  let descriptor;
  try {
    const realPath = fs.realpathSync(requestedPath);
    descriptor = fs.openSync(realPath, fs.constants.O_RDONLY);
    const stats = fs.fstatSync(descriptor);
    if (
      !stats.isFile() ||
      !Number.isSafeInteger(stats.size) ||
      stats.size < 0
    ) {
      throw blockedError("core_log_window_capture_failed");
    }
    const boundaryStartOffset = Math.max(
      0,
      stats.size - CORE_LOG_BOUNDARY_BINDING_BYTES,
    );
    const boundaryBytes = readExactFileRange(
      descriptor,
      boundaryStartOffset,
      stats.size - boundaryStartOffset,
    );
    if (boundaryBytes == null) {
      throw blockedError("core_log_window_capture_failed");
    }
    return Object.freeze({
      version: 1,
      requestedPath,
      realPath,
      device: String(stats.dev),
      inode: String(stats.ino),
      startOffset: stats.size,
      boundaryStartOffset,
      boundarySha256: sha256(boundaryBytes),
      startsInsideLine:
        boundaryBytes.length > 0 &&
        boundaryBytes[boundaryBytes.length - 1] !== 0x0a,
      maxBytes: CORE_LOG_WINDOW_MAX_BYTES,
    });
  } catch (error) {
    if (error?.blocked) throw error;
    throw blockedError("core_log_window_capture_failed");
  } finally {
    if (descriptor !== undefined) fs.closeSync(descriptor);
  }
}

function readCoreLogWindow(window) {
  if (
    window?.version !== 1 ||
    !path.isAbsolute(String(window.requestedPath || "")) ||
    !path.isAbsolute(String(window.realPath || "")) ||
    !String(window.device || "") ||
    !String(window.inode || "") ||
    !Number.isSafeInteger(window.startOffset) ||
    window.startOffset < 0 ||
    window.boundaryStartOffset !==
      Math.max(0, window.startOffset - CORE_LOG_BOUNDARY_BINDING_BYTES) ||
    !SHA256.test(String(window.boundarySha256 || "")) ||
    typeof window.startsInsideLine !== "boolean" ||
    window.maxBytes !== CORE_LOG_WINDOW_MAX_BYTES
  ) {
    return { ok: false, reason: "core_log_window_unavailable" };
  }
  let descriptor;
  try {
    if (fs.realpathSync(window.requestedPath) !== window.realPath) {
      return { ok: false, reason: "core_log_window_changed" };
    }
    descriptor = fs.openSync(window.realPath, fs.constants.O_RDONLY);
    const before = fs.fstatSync(descriptor);
    if (
      !before.isFile() ||
      String(before.dev) !== window.device ||
      String(before.ino) !== window.inode
    ) {
      return { ok: false, reason: "core_log_window_changed" };
    }
    if (before.size < window.startOffset) {
      return { ok: false, reason: "core_log_window_truncated" };
    }
    const boundaryLength = window.startOffset - window.boundaryStartOffset;
    const boundaryBytes = readExactFileRange(
      descriptor,
      window.boundaryStartOffset,
      boundaryLength,
    );
    if (
      boundaryBytes == null ||
      sha256(boundaryBytes) !== window.boundarySha256
    ) {
      return { ok: false, reason: "core_log_window_truncated" };
    }
    const byteLength = before.size - window.startOffset;
    if (byteLength > window.maxBytes) {
      return { ok: false, reason: "core_log_window_oversized" };
    }
    const bytes = readExactFileRange(
      descriptor,
      window.startOffset,
      byteLength,
    );
    if (bytes == null) {
      return { ok: false, reason: "core_log_window_changed" };
    }
    const after = fs.fstatSync(descriptor);
    if (
      String(after.dev) !== window.device ||
      String(after.ino) !== window.inode ||
      after.size < window.startOffset + byteLength
    ) {
      return { ok: false, reason: "core_log_window_changed" };
    }
    const verifiedBoundaryBytes = readExactFileRange(
      descriptor,
      window.boundaryStartOffset,
      boundaryLength,
    );
    if (
      verifiedBoundaryBytes == null ||
      sha256(verifiedBoundaryBytes) !== window.boundarySha256
    ) {
      return { ok: false, reason: "core_log_window_truncated" };
    }
    const finalNewline = bytes.lastIndexOf(0x0a);
    const firstCompleteLineOffset = window.startsInsideLine
      ? bytes.indexOf(0x0a) + 1
      : 0;
    return {
      ok: true,
      contents:
        finalNewline < firstCompleteLineOffset
          ? ""
          : bytes
              .subarray(firstCompleteLineOffset, finalNewline + 1)
              .toString("utf8"),
    };
  } catch {
    return { ok: false, reason: "core_log_window_changed" };
  } finally {
    if (descriptor !== undefined) fs.closeSync(descriptor);
  }
}

function parseTimingLogEvent(line, marker) {
  const beginning = line.indexOf("{", marker);
  if (beginning < 0) return null;
  const jsonText = line
    .slice(beginning)
    .trimEnd()
    .replace(/(?:\u001b\[[0-9;]*m)+$/u, "")
    .trimEnd();
  try {
    return JSON.parse(jsonText);
  } catch {
    return null;
  }
}

function readQuickTurnTimingTimeline(
  coreLogWindow,
  assistantMessageId,
  { submittedAtMs, visibleAtMs } = {},
) {
  const turnIdHash = sha256(String(assistantMessageId || "")).slice(0, 16);
  const reject = (reason) => rejectedQuickTurnTiming(reason, turnIdHash);
  if (
    !String(assistantMessageId || "").trim() ||
    !Number.isSafeInteger(submittedAtMs) ||
    !Number.isSafeInteger(visibleAtMs) ||
    visibleAtMs < submittedAtMs
  ) {
    return reject("quick_turn_timing_event_unsafe");
  }
  const observedWindow = readCoreLogWindow(coreLogWindow);
  if (!observedWindow.ok) return reject(observedWindow.reason);
  const contents = observedWindow.contents;

  const timingEvents = [];
  for (const line of contents.split(/\r?\n/)) {
    const marker = line.indexOf("[VIVENTIUM][TextTurnTiming]");
    if (marker < 0) continue;
    const parsed = parseTimingLogEvent(line, marker);
    if (
      !parsed ||
      typeof parsed !== "object" ||
      Array.isArray(parsed) ||
      !Object.hasOwn(QUICK_TURN_TIMING_KEYS, parsed.event)
    ) {
      continue;
    }
    const invocationId = String(parsed.invocationId || "");
    const referencesTurn =
      parsed.turnIdHash === turnIdHash ||
      invocationId.startsWith(`${turnIdHash}.`);
    if (!referencesTurn) continue;
    if (
      parsed.turnIdHash !== turnIdHash ||
      (invocationId && !invocationId.startsWith(`${turnIdHash}.`))
    ) {
      return reject("quick_turn_timing_identity_mismatch");
    }
    const allowedKeys = new Set(QUICK_TURN_TIMING_KEYS[parsed.event]);
    if (Object.keys(parsed).some((key) => !allowedKeys.has(key))) {
      return reject("quick_turn_timing_event_unsafe");
    }
    timingEvents.push(parsed);
  }

  const safeTime = (value) => Number.isSafeInteger(value) && value >= 0;
  const safeDuration = (value) => Number.isSafeInteger(value) && value >= 0;
  const safeAttempt = (event) =>
    Number.isSafeInteger(event.attemptIndex) &&
    event.attemptIndex > 0 &&
    event.invocationId === `${turnIdHash}.${event.attemptIndex}` &&
    (SHORT_SHA256.test(String(event.providerAttemptIdHash || "")) ||
      event.providerAttemptIdHash === "none") &&
    safeTime(event.observedAtMs) &&
    safeDuration(event.fromTurnStartMs);
  for (const event of timingEvents) {
    let valid = false;
    if (event.event === "viventium_text_turn_boundary") {
      valid =
        QUICK_TURN_BOUNDARY_STAGES.includes(event.stage) &&
        safeTime(event.observedAtMs) &&
        safeDuration(event.fromTurnStartMs);
    } else if (event.event === "viventium_text_main_provider_attempt_start") {
      valid = safeAttempt(event);
    } else if (event.event === "viventium_text_main_first_provider_output") {
      valid =
        safeAttempt(event) &&
        new Set(["provider_token", "visible_text_delta"]).has(
          event.outputKind,
        ) &&
        safeDuration(event.fromAttemptStartMs);
    } else if (event.event === "viventium_text_main_provider_attempt_end") {
      valid =
        safeAttempt(event) &&
        Number.isSafeInteger(event.toolCallCount) &&
        event.toolCallCount >= 0 &&
        event.toolCallCount <= 10_000 &&
        safeDuration(event.fromAttemptStartMs);
    } else {
      valid =
        Number.isSafeInteger(event.attemptIndex) &&
        event.attemptIndex > 0 &&
        event.invocationId === `${turnIdHash}.${event.attemptIndex}` &&
        Number.isSafeInteger(event.toolIndex) &&
        event.toolIndex > 0 &&
        SHORT_SHA256.test(String(event.toolInvocationIdHash || "")) &&
        safeTime(event.observedAtMs) &&
        safeDuration(event.fromTurnStartMs) &&
        safeDuration(event.fromAttemptStartMs);
    }
    if (!valid) return reject("quick_turn_timing_event_unsafe");
  }

  const boundaryEvents = new Map();
  for (const stage of QUICK_TURN_BOUNDARY_STAGES) {
    const matching = timingEvents.filter(
      (event) =>
        event.event === "viventium_text_turn_boundary" && event.stage === stage,
    );
    if (matching.length === 0) {
      return reject("quick_turn_timing_event_missing");
    }
    if (matching.length !== 1) {
      return reject("quick_turn_timing_event_duplicate");
    }
    boundaryEvents.set(stage, matching[0]);
  }

  const providerStarts = new Map();
  const providerEnds = new Map();
  const providerOutputs = new Map();
  const toolStarts = new Map();
  const toolEnds = new Map();
  for (const event of timingEvents) {
    let collection;
    let key;
    if (event.event === "viventium_text_main_provider_attempt_start") {
      collection = providerStarts;
      key = event.invocationId;
    } else if (event.event === "viventium_text_main_provider_attempt_end") {
      collection = providerEnds;
      key = event.invocationId;
    } else if (event.event === "viventium_text_main_first_provider_output") {
      collection = providerOutputs;
      key = `${event.invocationId}:${event.outputKind}`;
    } else if (event.event === "viventium_text_main_tool_start") {
      collection = toolStarts;
      key = event.toolInvocationIdHash;
    } else if (event.event === "viventium_text_main_tool_end") {
      collection = toolEnds;
      key = event.toolInvocationIdHash;
    } else {
      continue;
    }
    if (collection.has(key)) {
      return reject("quick_turn_timing_event_duplicate");
    }
    collection.set(key, event);
  }
  if (
    providerStarts.size === 0 ||
    providerEnds.size === 0 ||
    providerOutputs.size === 0 ||
    providerStarts.size !== providerEnds.size
  ) {
    return reject("quick_turn_timing_event_missing");
  }

  const boundaryTimes = QUICK_TURN_BOUNDARY_STAGES.filter(
    (stage) => stage !== "presentation_committed",
  ).map((stage) => boundaryEvents.get(stage).observedAtMs);
  const presentationCommittedAtMs = boundaryEvents.get(
    "presentation_committed",
  ).observedAtMs;
  if (
    boundaryTimes.some(
      (value, index) => index > 0 && value < boundaryTimes[index - 1],
    ) ||
    presentationCommittedAtMs <
      boundaryEvents.get("assistant_durable").observedAtMs ||
    submittedAtMs > boundaryEvents.get("controller_admission").observedAtMs
  ) {
    return reject("quick_turn_timing_order_invalid");
  }

  const pipelineStartedAtMs = boundaryEvents.get(
    "main_pipeline_start",
  ).observedAtMs;
  const pipelineCompletedAtMs = boundaryEvents.get(
    "main_pipeline_complete",
  ).observedAtMs;
  const orderedStarts = [...providerStarts.values()].sort(
    (left, right) => left.attemptIndex - right.attemptIndex,
  );
  if (orderedStarts.some((event, index) => event.attemptIndex !== index + 1)) {
    return reject("quick_turn_timing_identity_mismatch");
  }
  for (const start of orderedStarts) {
    const end = providerEnds.get(start.invocationId);
    if (!end) return reject("quick_turn_timing_event_missing");
    if (
      end.attemptIndex !== start.attemptIndex ||
      end.providerAttemptIdHash !== start.providerAttemptIdHash
    ) {
      return reject("quick_turn_timing_identity_mismatch");
    }
    if (
      start.observedAtMs < pipelineStartedAtMs ||
      end.observedAtMs < start.observedAtMs ||
      end.observedAtMs > pipelineCompletedAtMs
    ) {
      return reject("quick_turn_timing_order_invalid");
    }
  }
  for (const output of providerOutputs.values()) {
    const start = providerStarts.get(output.invocationId);
    const end = providerEnds.get(output.invocationId);
    if (
      !start ||
      !end ||
      output.attemptIndex !== start.attemptIndex ||
      output.providerAttemptIdHash !== start.providerAttemptIdHash
    ) {
      return reject("quick_turn_timing_identity_mismatch");
    }
    if (
      output.observedAtMs < start.observedAtMs ||
      output.observedAtMs > pipelineCompletedAtMs ||
      (output.outputKind === "provider_token" &&
        output.observedAtMs > end.observedAtMs)
    ) {
      return reject("quick_turn_timing_order_invalid");
    }
  }

  if (
    toolStarts.size !== toolEnds.size ||
    [...toolStarts.keys()].some((key) => !toolEnds.has(key))
  ) {
    return reject("quick_turn_timing_tool_pair_mismatch");
  }
  const orderedTools = [...toolStarts.values()].sort(
    (left, right) => left.toolIndex - right.toolIndex,
  );
  for (const [index, start] of orderedTools.entries()) {
    const end = toolEnds.get(start.toolInvocationIdHash);
    const providerStart = providerStarts.get(start.invocationId);
    if (
      start.toolIndex !== index + 1 ||
      !providerStart ||
      end.invocationId !== start.invocationId ||
      end.attemptIndex !== start.attemptIndex ||
      end.toolIndex !== start.toolIndex
    ) {
      return reject("quick_turn_timing_tool_pair_mismatch");
    }
    if (
      start.observedAtMs < providerStart.observedAtMs ||
      end.observedAtMs < start.observedAtMs ||
      end.observedAtMs > pipelineCompletedAtMs
    ) {
      return reject("quick_turn_timing_order_invalid");
    }
  }
  const expectedToolCount = [...providerEnds.values()].reduce(
    (count, event) => count + event.toolCallCount,
    0,
  );
  if (expectedToolCount !== toolStarts.size) {
    return reject("quick_turn_timing_tool_count_mismatch");
  }

  const firstProviderStartedAtMs = Math.min(
    ...orderedStarts.map((event) => event.observedAtMs),
  );
  const firstProviderOutputAtMs = Math.min(
    ...[...providerOutputs.values()].map((event) => event.observedAtMs),
  );
  if (visibleAtMs < firstProviderOutputAtMs) {
    return reject("quick_turn_timing_order_invalid");
  }
  const lastProviderCompletedAtMs = Math.max(
    ...[...providerEnds.values()].map((event) => event.observedAtMs),
  );
  const stages = Object.fromEntries(
    QUICK_TURN_BOUNDARY_STAGES.map((stage) => [
      stage,
      boundaryEvents.get(stage).observedAtMs,
    ]),
  );
  return {
    complete: true,
    turnIdHash,
    submittedAtMs,
    domVisibleAtMs: visibleAtMs,
    presentationCommittedAtMs,
    counts: {
      providerAttempts: providerStarts.size,
      providerOutputs: providerOutputs.size,
      toolInvocations: toolStarts.size,
    },
    stages: {
      request_submitted: submittedAtMs,
      ...stages,
      first_model_provider_activity: firstProviderStartedAtMs,
      first_provider_output: firstProviderOutputAtMs,
      last_provider_completion: lastProviderCompletedAtMs,
      browser_visible_final_answer: visibleAtMs,
    },
    durations: {
      submissionStartToControllerAdmissionMs:
        stages.controller_admission - submittedAtMs,
      controllerToConcurrencyAdmissionMs:
        stages.concurrency_admitted - stages.controller_admission,
      concurrencyAdmissionToClientInitializationStartMs:
        stages.client_initialization_start - stages.concurrency_admitted,
      clientInitializationMs:
        stages.client_initialization_end - stages.client_initialization_start,
      clientInitializationToPipelineStartMs:
        stages.main_pipeline_start - stages.client_initialization_end,
      pipelineStartToFirstProviderActivityMs:
        firstProviderStartedAtMs - stages.main_pipeline_start,
      controllerToFirstProviderActivityMs:
        firstProviderStartedAtMs - stages.controller_admission,
      firstProviderActivityToFirstOutputMs:
        firstProviderOutputAtMs - firstProviderStartedAtMs,
      firstOutputToLastProviderCompletionMs:
        lastProviderCompletedAtMs - firstProviderOutputAtMs,
      lastProviderCompletionToPipelineCompleteMs:
        stages.main_pipeline_complete - lastProviderCompletedAtMs,
      pipelineCompleteToDurableMs:
        stages.assistant_durable - stages.main_pipeline_complete,
      durableToFinalEmitMs:
        stages.final_event_emitted - stages.assistant_durable,
      finalEmitToPresentationCommitMs:
        presentationCommittedAtMs - stages.final_event_emitted,
      presentationCommitToDomObservationMs:
        visibleAtMs - presentationCommittedAtMs,
      submittedToDomVisibleMs: visibleAtMs - submittedAtMs,
    },
    providerAttempts: orderedStarts.map((start) => {
      const outputs = [...providerOutputs.values()].filter(
        (event) => event.invocationId === start.invocationId,
      );
      const end = providerEnds.get(start.invocationId);
      return {
        invocationId: start.invocationId,
        providerAttemptIdHash: start.providerAttemptIdHash,
        attemptIndex: start.attemptIndex,
        startedAtMs: start.observedAtMs,
        firstOutputAtMs:
          outputs.length > 0
            ? Math.min(...outputs.map((event) => event.observedAtMs))
            : null,
        completedAtMs: end.observedAtMs,
        outputCount: outputs.length,
        toolCallCount: end.toolCallCount,
      };
    }),
    tools: orderedTools.map((start) => ({
      toolInvocationIdHash: start.toolInvocationIdHash,
      attemptIndex: start.attemptIndex,
      toolIndex: start.toolIndex,
      startedAtMs: start.observedAtMs,
      completedAtMs: toolEnds.get(start.toolInvocationIdHash).observedAtMs,
    })),
  };
}

function winningNativeReceipt(coreLogWindow, assistantMessageId) {
  const observedWindow = readCoreLogWindow(coreLogWindow);
  if (!observedWindow.ok) return null;
  const turnIdHash = sha256(String(assistantMessageId)).slice(0, 16);
  let winner = null;
  for (const line of observedWindow.contents.split(/\r?\n/)) {
    const marker = line.indexOf("[VIVENTIUM][TextTurnTiming]");
    if (marker < 0) continue;
    const parsed = parseTimingLogEvent(line, marker);
    if (parsed) {
      if (
        parsed.event ===
          "viventium_text_main_winning_native_provider_receipt" &&
        parsed.turnIdHash === turnIdHash &&
        typeof parsed.provider === "string" &&
        typeof parsed.model === "string" &&
        parsed.provider &&
        parsed.model &&
        SHA256.test(String(parsed.snapshotHash || "")) &&
        SHA256.test(String(parsed.nativeRequestSha256 || ""))
      ) {
        winner = parsed;
      }
    }
  }
  return winner;
}

async function createInstalledBrowserDriver({ args, env, identity }) {
  const { MongoClient } = require(
    path.join(LIBRECHAT_ROOT, "node_modules", "mongodb"),
  );
  const { chromium } = require(
    path.join(LIBRECHAT_ROOT, "node_modules", "playwright"),
  );
  const mongo = new MongoClient(env.MONGO_URI, {
    serverSelectionTimeoutMS: 5000,
  });
  let browser;
  let store;
  const temporarySessions = [];
  try {
    await mongo.connect();
    const databaseName =
      new URL(env.MONGO_URI).pathname.replace(/^\//, "") ||
      "LibreChatViventium";
    const db = mongo.db(databaseName);
    const user = await db.collection("users").findOne(
      { email: args.qaEmail },
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
    const ownerId = assertSelectedQaAccount(args, env, user);
    const agent = await db.collection("agents").findOne(
      { id: args.agentId },
      {
        projection: {
          _id: 1,
          id: 1,
          "model_parameters.reasoning_effort": 1,
          "model_parameters.effort": 1,
          reasoning_effort: 1,
          effort: 1,
        },
      },
    );
    if (!agent?.id) throw blockedError("configured_main_agent_unavailable");
    store = openReadOnlyGlassHiveStore(args.glassHiveDbPath);
    browser = await chromium.launch({ channel: "chrome", headless: false });
    const context = await browser.newContext({
      viewport: { width: 1440, height: 1100 },
    });
    const page = await context.newPage();
    page.setDefaultTimeout(Math.min(args.timeoutMs, 30000));
    const state = {
      conversationId: "",
      launchAtMs: 0,
      quickUserMessageId: "",
      workRefs: [],
      terminalCallbacks: [],
      contexts: [],
      restartBaseline: null,
    };

    async function finishedUserTurn(prompt, startedAtMs) {
      return waitFor(
        async () => {
          const userMessage = await db.collection("messages").findOne(
            {
              user: ownerId,
              isCreatedByUser: true,
              text: prompt,
              createdAt: { $gte: new Date(startedAtMs - 1500) },
            },
            { sort: { createdAt: -1, _id: -1 } },
          );
          if (!userMessage?.messageId) return null;
          const replies = await db
            .collection("messages")
            .find({
              user: ownerId,
              conversationId: userMessage.conversationId,
              parentMessageId: userMessage.messageId,
              isCreatedByUser: false,
              unfinished: false,
            })
            .project({
              messageId: 1,
              text: 1,
              content: 1,
              metadata: 1,
              createdAt: 1,
            })
            .toArray();
          if (replies.length !== 1 || !renderMessage(replies[0])) return null;
          return {
            userMessage,
            assistant: replies[0],
            replyCount: replies.length,
          };
        },
        {
          timeoutMs: args.timeoutMs,
          reason: "visible_single_main_reply_unavailable",
        },
      );
    }

    async function screenshot(name, target = page) {
      const bytes = await target.screenshot({ fullPage: true });
      return writePrivateEvidence(args.outputDir, name, bytes);
    }

    async function observeCurrentRows() {
      return readScopedRuntimeEvidence(store, {
        ownerId,
        workRefs: state.workRefs,
      });
    }

    async function observeWebTerminalPresentation(callback, row) {
      const rawCallbackRef = String(callback.callbackRef || "").trim();
      const canonicalCallbackRef = CANONICAL_CALLBACK_REF.test(rawCallbackRef)
        ? rawCallbackRef
        : rawCallbackRef
          ? `callback_sha256:${sha256(rawCallbackRef)}`
          : "";
      const evidenceRows = await db
        .collection("viventium_glasshive_mission_evidence")
        .find({
          ownerId,
          conversationId: state.conversationId,
          originRef: row.originRef,
          workRef: row.workRef,
          runId: row.runRef,
          event: "run.completed",
          callbackRef: canonicalCallbackRef,
          attemptNumber: callback.callbackAttemptNumber,
          surface: "web",
        })
        .project({
          ownerId: 1,
          originRef: 1,
          workRef: 1,
          runId: 1,
          event: 1,
          callbackRef: 1,
          attemptNumber: 1,
          state: 1,
          workState: 1,
          workTerminal: 1,
          errorCode: 1,
          followUpMessageId: 1,
          webPresentationMessageId: 1,
          webPresentedAt: 1,
        })
        .limit(2)
        .toArray();
      const evidence = evidenceRows[0] || {};
      const followUpMessageId = String(evidence.followUpMessageId || "").trim();
      const messages = followUpMessageId
        ? await db
            .collection("messages")
            .find({
              user: ownerId,
              conversationId: state.conversationId,
              messageId: followUpMessageId,
              isCreatedByUser: false,
              unfinished: false,
            })
            .project({ messageId: 1, text: 1, content: 1 })
            .limit(2)
            .toArray()
        : [];
      const presentation = followUpMessageId
        ? page.locator(`[id=${JSON.stringify(followUpMessageId)}]`)
        : null;
      const visibleMessageCount = presentation ? await presentation.count() : 0;
      let visibleMessageHasContent = false;
      if (
        presentation &&
        visibleMessageCount === 1 &&
        (await presentation.first().isVisible())
      ) {
        const parts = await presentation
          .first()
          .locator(".message-content")
          .allInnerTexts();
        visibleMessageHasContent = parts.some((part) =>
          Boolean(String(part || "").trim()),
        );
      }
      return {
        canonicalCallbackRef,
        missionEvidenceCount: evidenceRows.length,
        missionEvidenceOwnerId: evidence.ownerId,
        missionEvidenceOriginRef: evidence.originRef,
        missionEvidenceWorkRef: evidence.workRef,
        missionEvidenceRunRef: evidence.runId,
        missionEvidenceEvent: evidence.event,
        missionEvidenceCallbackRef: evidence.callbackRef,
        missionEvidenceAttemptNumber: evidence.attemptNumber,
        missionEvidenceState: evidence.state,
        missionEvidenceWorkState: evidence.workState,
        missionEvidenceWorkTerminal: evidence.workTerminal,
        missionEvidenceErrorCode: evidence.errorCode || "",
        followUpMessageId,
        webPresentationMessageId: String(
          evidence.webPresentationMessageId || "",
        ).trim(),
        webPresentedAt: evidence.webPresentedAt,
        persistedMessageCount: messages.length,
        persistedMessageId: String(messages[0]?.messageId || "").trim(),
        persistedMessageHasContent:
          messages.length === 1 && Boolean(renderMessage(messages[0])),
        visibleMessageCount,
        visibleMessageId: followUpMessageId,
        visibleMessageHasContent,
      };
    }

    async function ownerApiRequest(
      session,
      endpoint,
      { method = "GET", data, headers = {} } = {},
    ) {
      const base = assertLoopbackUrl(args.apiBase, "api");
      const location = new URL(endpoint, base);
      if (
        location.origin !== base.origin ||
        !location.pathname.startsWith("/api/viventium/")
      ) {
        throw blockedError("owner_scoped_local_api_boundary_invalid");
      }
      const request = {
        headers: { ...headers, Authorization: `Bearer ${session.accessToken}` },
        maxRedirects: 0,
      };
      if (data !== undefined) request.data = data;
      return context.request.fetch(location.toString(), { ...request, method });
    }

    async function exactOwnerWorkCard(row) {
      const session = temporarySessions[0];
      if (!session) throw blockedError("ephemeral_browser_session_unavailable");
      const response = await ownerApiRequest(
        session,
        "/api/viventium/orchestration/work",
      );
      if (response.status() !== 200)
        throw blockedError("owner_scoped_active_work_snapshot_unavailable");
      const snapshot = await response.json();
      const work = (Array.isArray(snapshot?.work) ? snapshot.work : []).filter(
        (candidate) => candidate?.workRef === row.workRef,
      );
      if (work.length !== 1 || !String(work[0].title || "").trim()) {
        throw blockedError("exact_owner_scoped_worker_card_unavailable");
      }
      const activeWorkControl = page.getByRole("button", {
        name: "Active work",
        exact: true,
      });
      await activeWorkControl.waitFor({
        state: "visible",
        timeout: Math.min(args.timeoutMs, 30000),
      });
      if ((await activeWorkControl.getAttribute("aria-expanded")) !== "true") {
        await activeWorkControl.click();
      }
      const heading = page.getByRole("heading", {
        name: String(work[0].title),
        exact: true,
      });
      await heading.waitFor({
        state: "visible",
        timeout: Math.min(args.timeoutMs, 30000),
      });
      const cards = page.locator("li").filter({ has: heading });
      if ((await cards.count()) !== 1) {
        throw blockedError("exact_owner_scoped_worker_card_unavailable");
      }
      const card = cards.first();
      await card.waitFor({
        state: "visible",
        timeout: Math.min(args.timeoutMs, 30000),
      });
      return { card, work: work[0] };
    }

    async function submitVisibleUserTurn(kind, prompt) {
      const submittedAtMs = Date.now();
      const input = page
        .getByLabel("Message input")
        .or(page.getByPlaceholder(/^Message/))
        .last();
      await input.fill(prompt);
      await page.getByTestId("send-button").last().click();
      const turn = await finishedUserTurn(prompt, submittedAtMs);
      const assistant = page.locator(`[id="${turn.assistant.messageId}"]`);
      await assistant.waitFor({
        state: "visible",
        timeout: Math.min(args.timeoutMs, 30000),
      });
      state.conversationId = String(turn.userMessage.conversationId || "");
      if (!state.conversationId)
        throw blockedError("owner_scoped_conversation_unavailable");
      return {
        kind,
        submittedAtMs,
        visibleAtMs: Date.now(),
        userVisible: true,
        replyCount: turn.replyCount,
        userMessageId: String(turn.userMessage.messageId),
        assistantMessageId: String(turn.assistant.messageId),
      };
    }

    async function collectCurrentMissionBindings(expected) {
      return waitFor(
        async () => {
          const bindings = await db
            .collection("viventium_glasshive_callback_bindings")
            .find({
              ownerId,
              conversationId: state.conversationId,
              createdAt: { $gte: new Date(state.launchAtMs - 1500) },
              workRef: { $nin: ["", null] },
            })
            .project({ workRef: 1, originRef: 1, createdAt: 1 })
            .sort({ createdAt: 1, _id: 1 })
            .limit(expected + 1)
            .toArray();
          if (bindings.length > expected) {
            throw blockedError(
              "unexpected_duplicate_or_sibling_mission_created",
            );
          }
          return bindings.length === expected ? bindings : null;
        },
        {
          timeoutMs: args.timeoutMs,
          reason: "exact_owner_scoped_mission_binding_unavailable",
        },
      );
    }

    async function visibleScenarioSurfaces(stage) {
      const input = page
        .getByLabel("Message input")
        .or(page.getByPlaceholder(/^Message/))
        .last();
      const webVisible = await input.isVisible().catch(() => false);
      if (webVisible)
        await screenshot(`scenario-${args.caseId.toLowerCase()}-${stage}.png`);
      return {
        webVisible,
        telegramVisible: currentCaseTelegramSurface({
          args,
          identity,
          ownerId,
        }),
      };
    }

    async function verifyCoordinatedRestartPrerequisites() {
      readPrivateRestartProof(args, identity, ownerId);
      let trusted;
      try {
        trusted = await invokeLocalQaControl(args, "status");
      } catch {
        throw blockedError("restart_case_service_acknowledgements_unsupported");
      }
      if (
        trusted?.caseId !== args.caseId ||
        trusted.restartState !== "ready" ||
        !Array.isArray(trusted.missingServices) ||
        trusted.missingServices.length !== 0 ||
        !/^sha256:[a-f0-9]{64}$/.test(String(trusted.serviceAckDigest || "")) ||
        !String(trusted.sessionRef || "").trim()
      ) {
        throw blockedError("restart_case_service_acknowledgements_unsupported");
      }
      state.restartBaseline = {
        sessionRef: trusted.sessionRef,
        serviceAckDigest: trusted.serviceAckDigest,
      };
      return trusted;
    }

    async function waitForExternalCoordinatedRestart() {
      const approval = readPrivateRestartProof(args, identity, ownerId);
      const requestedAtMs = Date.now();
      if (!approval || approval.approved !== true || !state.restartBaseline) {
        throw blockedError("restart_operator_readiness_proof_unavailable");
      }
      return waitFor(
        () => {
          const proof = readPrivateRestartProof(args, identity, ownerId);
          if (
            !timestamp(proof.restartedAt) ||
            timestamp(proof.restartedAt) <= requestedAtMs
          ) {
            return null;
          }
          try {
            assertRestartReadiness(proof, {
              caseId: args.caseId,
              candidateDigest: identity.candidateDigest,
            });
            return invokeLocalQaControl(args, "status").then((status) => {
              try {
                assertAuthenticatedRestartStatus(proof, status, {
                  caseId: args.caseId,
                  candidateDigest: identity.candidateDigest,
                  previousServiceAckDigest:
                    state.restartBaseline.serviceAckDigest,
                  sessionRef: state.restartBaseline.sessionRef,
                });
                return proof;
              } catch {
                return null;
              }
            });
          } catch {
            return null;
          }
        },
        {
          timeoutMs: args.timeoutMs,
          reason: "externally_coordinated_restart_not_observed",
        },
      );
    }

    async function observeFaultAfterRealUserTurn({
      boundary,
      control,
      kind,
      prompt,
      captureTurn,
    }) {
      const turn = await submitVisibleUserTurn(kind, prompt);
      if (typeof captureTurn === "function") captureTurn(turn);
      return waitFor(
        () =>
          readConsumedFaultObservation(store, {
            caseId: args.caseId,
            ownerId,
            controlRef: control.controlRef,
            expectedBoundary: boundary,
          }),
        {
          timeoutMs: args.timeoutMs,
          reason: `installed_fault_effect_unobserved:${boundary}`,
        },
      );
    }

    function readOwnerScenarioLedger() {
      if (state.workRefs.length !== 2) {
        throw blockedError("owner_scoped_mission_evidence_incomplete");
      }
      const selected = [ownerId, ...state.workRefs];
      try {
        const capacity = store
          .prepare(
            `SELECT d.owner_id AS ownerId, d.work_ref AS workRef,
                  c.capacity_attempt_id AS requestRef, c.run_id AS runRef,
                  c.capacity_class AS capacityClass, c.available_json AS availableJson,
                  c.required_json AS requiredJson, c.shortage_json AS shortageJson,
                  c.reservation_json AS reservationJson, c.next_retry_at AS nextRetryAt,
                  c.observed_at AS observedAt
           FROM capacity_attempts c
           JOIN delegations d ON d.current_run_id = c.run_id
           WHERE d.owner_id = ? AND d.work_ref IN (?, ?)
           ORDER BY c.observed_at, c.sequence`,
          )
          .all(...selected);
        const routes = store
          .prepare(
            `SELECT d.owner_id AS ownerId, d.work_ref AS workRef, r.run_id AS runRef,
                  r.state AS state, r.failure_class AS failureClass,
                  r.provider_route_decision AS decision,
                  r.provider_route_profile AS profile,
                  r.provider_route_runtime AS runtime,
                  r.provider_route_model AS model,
                  r.provider_route_from_profile AS fromProfile,
                  r.provider_route_from_runtime AS fromRuntime,
                  r.provider_route_from_model AS fromModel,
                  r.provider_route_failure_class AS routeFailureClass,
                  r.provider_route_cooldown_until AS cooldownUntil,
                  r.runtime_invoked_at AS runtimeInvokedAt,
                  r.queue_wait_open AS queueWaitOpen,
                  r.queue_wait_generation AS queueWaitGeneration,
                  r.queue_transition_emitted AS queueTransitionEmitted
           FROM delegations d JOIN runs r ON r.run_id = d.current_run_id
           WHERE d.owner_id = ? AND d.work_ref IN (?, ?)`,
          )
          .all(...selected);
        const health = store
          .prepare(
            `SELECT owner_id AS ownerId, profile, runtime, model,
                  failure_class AS failureClass, cooldown_until AS cooldownUntil,
                  last_run_id AS runRef, failure_generation AS generation
           FROM provider_route_health WHERE owner_id = ?`,
          )
          .all(ownerId);
        const leases = store
          .prepare(
            `SELECT d.owner_id AS ownerId, d.work_ref AS workRef,
                  l.run_id AS runRef, l.lease_id AS leaseRef,
                  l.acquired_at AS acquiredAt,
                  l.reserved_memory_bytes AS reservedMemoryBytes
           FROM host_run_leases l
           JOIN delegations d ON d.current_run_id = l.run_id
             AND d.owner_id = l.owner_id
           WHERE d.owner_id = ? AND d.work_ref IN (?, ?)`,
          )
          .all(...selected);
        const events = store
          .prepare(
            `SELECT w.owner_id AS ownerId, e.run_id AS runRef, e.event_type AS eventType,
                  e.payload_json AS payloadJson, e.created_at AS createdAt
           FROM events e JOIN workers w ON w.worker_id = e.worker_id
           JOIN delegations d ON d.current_run_id = e.run_id AND d.owner_id = w.owner_id
           WHERE w.owner_id = ? AND d.work_ref IN (?, ?)
           ORDER BY e.created_at`,
          )
          .all(...selected);
        const callbackHistory = store
          .prepare(
            `SELECT d.owner_id AS ownerId, d.work_ref AS workRef,
                  c.callback_id AS callbackRef, c.event_type AS event,
                  c.status AS status, c.attempts AS attempts,
                  c.delivery_generation AS deliveryGeneration,
                  c.http_accepted_at AS acceptedAt, c.delivered_at AS deliveredAt
           FROM callback_outbox c JOIN delegations d ON d.current_run_id = c.run_id
           WHERE d.owner_id = ? AND d.work_ref IN (?, ?)`,
          )
          .all(...selected);
        return { capacity, routes, health, leases, events, callbackHistory };
      } catch (error) {
        if (error?.blocked) throw error;
        throw blockedError("owner_scoped_scenario_ledger_unavailable");
      }
    }

    function exactFixtureMission(fixture) {
      return readExactFixtureRuntimeEvidence(store, { ownerId, fixture }).row;
    }

    async function armExactBoundary(invokeControl, fixture, boundary) {
      const control = await invokeControl("arm-glasshive", [
        "--boundary",
        boundary,
        "--ttl-seconds",
        "120",
      ]);
      if (
        control?.caseId !== args.caseId ||
        control.boundary !== boundary ||
        !new Set(["armed", "already_armed", "consumed"]).has(control.status) ||
        !/^qac_sha256:[a-f0-9]{64}$/.test(String(control.controlRef || "")) ||
        control.scopeHashes?.owner !== fixture.scopeHashes.owner ||
        control.scopeHashes?.work !== fixture.scopeHashes.work ||
        control.scopeHashes?.run !== fixture.scopeHashes.run
      ) {
        throw blockedError(`exact_owner_scoped_fault_arm_rejected:${boundary}`);
      }
      return control;
    }

    async function resumeExactFixtureLostResponse(fixture, before) {
      const session = temporarySessions[0];
      if (!session) throw blockedError("ephemeral_browser_session_unavailable");
      const operationId = crypto.randomUUID();
      const endpoint = `/api/viventium/orchestration/work/${encodeURIComponent(before.workRef)}/actions`;
      const data = { action: "resume", operationId };
      const first = await ownerApiRequest(session, endpoint, {
        method: "POST",
        data,
      });
      const firstBody = await first.json().catch(() => null);
      const replay = await ownerApiRequest(session, endpoint, {
        method: "POST",
        data,
      });
      const replayBody = await replay.json().catch(() => null);
      if (
        first.status() !== 202 ||
        replay.status() !== 202 ||
        !firstBody ||
        canonicalJson(firstBody) !== canonicalJson(replayBody) ||
        String(firstBody.runId || firstBody.run_id || "") !== before.runRef
      ) {
        throw blockedError(
          "same_run_resume_lost_response_idempotency_unproven",
        );
      }
      const after = readExactFixtureRuntimeEvidence(store, {
        ownerId,
        fixture,
      }).row;
      if (
        after.runRef !== before.runRef ||
        after.workspaceRef !== before.workspaceRef ||
        after.nativeSessionRef !== before.nativeSessionRef ||
        after.profile !== before.profile ||
        after.runtime !== before.runtime ||
        after.model !== before.model
      ) {
        throw blockedError("same_run_resume_identity_changed");
      }
      return {
        operationRef: sha256(operationId),
        responseSha256: sha256(canonicalJson(firstBody)),
        replaySha256: sha256(canonicalJson(replayBody)),
        stableReplay: true,
        sameRun: true,
        sameRoute: true,
        sameSession: true,
        sameWorkspace: true,
      };
    }

    async function ownerMissionCounts(targetOwnerId) {
      const work = store
        .prepare("SELECT COUNT(*) AS count FROM delegations WHERE owner_id = ?")
        .get(targetOwnerId);
      const runs = store
        .prepare(
          `SELECT COUNT(*) AS count FROM runs r
         JOIN workers w ON w.worker_id = r.worker_id WHERE w.owner_id = ?`,
        )
        .get(targetOwnerId);
      return { work: Number(work.count), runs: Number(runs.count) };
    }

    async function inspectArtifactFailure(row, expectedKind) {
      const { card } = await exactOwnerWorkCard(row);
      const link = card.getByRole("link", { name: /^View / });
      const target = await link.getAttribute("href");
      if (!target)
        throw blockedError(`artifact_${expectedKind}_visible_link_unavailable`);
      const location = assertLoopbackUrl(
        new URL(target, args.clientBase).toString(),
        "artifact",
      );
      const inspection = await browser.newContext({
        viewport: { width: 1200, height: 900 },
      });
      state.contexts.push(inspection);
      const view = await inspection.newPage();
      await view.goto(location.toString(), { waitUntil: "domcontentloaded" });
      const openLinks = view.getByRole("link", { name: /^Open / });
      let artifact;
      for (let index = 0; index < (await openLinks.count()); index += 1) {
        const candidate = openLinks.nth(index);
        const href = await candidate.getAttribute("href");
        if (!href) continue;
        try {
          artifactRelativePath({
            href,
            ariaLabel: await candidate.getAttribute("aria-label"),
            base: location.toString(),
          });
          artifact = { candidate, href };
          break;
        } catch {
          // Only a real current HTML deliverable can exercise this boundary.
        }
      }
      if (!artifact)
        throw blockedError(`artifact_${expectedKind}_visible_link_unavailable`);
      const artifactLocation = assertLoopbackUrl(
        new URL(artifact.href, location).toString(),
        "artifact",
      );
      const [popup, response] = await Promise.all([
        view.waitForEvent("popup", {
          timeout: Math.min(args.timeoutMs, 30000),
        }),
        inspection.waitForEvent("response", {
          predicate: (item) =>
            item.url() === artifactLocation.toString() &&
            item.request().resourceType() === "document",
          timeout: Math.min(args.timeoutMs, 30000),
        }),
        artifact.candidate.click(),
      ]);
      await popup.waitForLoadState("domcontentloaded");
      const visible = String(await popup.locator("body").innerText()).trim();
      const expected =
        expectedKind === "expired" ? /expired/i : /unavailable|not available/i;
      if (!response || response.status() < 400 || !expected.test(visible)) {
        throw blockedError(
          `artifact_${expectedKind}_user_visible_failure_unobserved`,
        );
      }
      await screenshot(`artifact-failure-${expectedKind}.png`, popup);
      return { kind: expectedKind, userVisible: true };
    }

    async function reopenExactArtifactWindows(artifacts, rows) {
      const reopened = [];
      for (const artifact of artifacts) {
        const row = rows.find(
          (candidate) => candidate.workRef === artifact.workRef,
        );
        const capture = state.contexts.find((candidate) =>
          candidate
            .pages()
            .some(
              (candidatePage) => candidatePage.url() === artifact.browserUrl,
            ),
        );
        const popup = capture
          ?.pages()
          .find((candidatePage) => candidatePage.url() === artifact.browserUrl);
        if (!row || !popup || !artifact.workspacePath) {
          throw blockedError("post_restart_exact_artifact_window_unavailable");
        }
        await popup.reload({ waitUntil: "domcontentloaded" });
        if (!String(await popup.locator("body").innerText()).trim()) {
          throw blockedError("post_restart_exact_artifact_not_visible");
        }
        const workspace = fs.realpathSync(row.workspaceRoot);
        const target = fs.realpathSync(
          path.join(workspace, artifact.workspacePath),
        );
        const relative = path.relative(workspace, target);
        if (
          !relative ||
          relative.startsWith("..") ||
          !fs.statSync(target).isFile()
        ) {
          throw blockedError("post_restart_exact_artifact_path_unavailable");
        }
        const measured = sha256(fs.readFileSync(target));
        if (measured !== artifact.byteSha256) {
          throw blockedError("post_restart_exact_artifact_hash_mismatch");
        }
        reopened.push(measured);
        await screenshot(`reopened-artifact-${reopened.length}.png`, popup);
      }
      return reopened;
    }

    async function addSecondSyntheticSession() {
      const secondArgs = { ...args, qaEmail: args.secondQaEmail };
      const secondEnv = { ...env, VIVENTIUM_QA_EMAIL: args.secondQaEmail };
      const candidate = await db.collection("users").findOne(
        { email: args.secondQaEmail },
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
      const secondOwnerId = assertSelectedQaAccount(
        secondArgs,
        secondEnv,
        candidate,
      );
      if (secondOwnerId === ownerId)
        throw blockedError("second_synthetic_qa_account_required");
      const session = await createEphemeralBrowserSession({
        db,
        user: candidate,
        args: secondArgs,
        env: secondEnv,
      });
      temporarySessions.push(session);
      return { ownerId: secondOwnerId, session };
    }

    function signedCrossOwnerCallback({
      targetOwnerId,
      targetWork,
      actorOrigin,
    }) {
      let stored;
      try {
        stored = store
          .prepare(
            `SELECT c.payload_json AS payloadJson
           FROM callback_outbox c
           JOIN delegations d ON d.current_run_id = c.run_id
           WHERE d.owner_id = ? AND d.work_ref = ?
             AND c.event_type = 'run.completed'
           ORDER BY c.created_at DESC LIMIT 1`,
          )
          .get(targetOwnerId, targetWork);
      } catch {
        throw blockedError("signed_cross_owner_callback_evidence_unavailable");
      }
      let payload;
      try {
        payload = JSON.parse(String(stored?.payloadJson || ""));
      } catch {
        throw blockedError("signed_cross_owner_callback_evidence_unavailable");
      }
      if (
        !payload ||
        payload.work_ref !== targetWork ||
        !payload.worker_id ||
        !payload.run_id ||
        !String(actorOrigin || "").trim()
      ) {
        throw blockedError("signed_cross_owner_callback_identity_unavailable");
      }
      const mixed = {
        ...payload,
        origin_ref: actorOrigin,
        callback_ts: Date.now() / 1000,
      };
      return {
        payload: mixed,
        signature: signScopedCallbackPayload(
          mixed,
          env.VIVENTIUM_GLASSHIVE_CALLBACK_SECRET,
        ),
      };
    }

    async function verifyOwnerDenial({
      actor,
      target,
      operation,
      targetWork,
      targetOrigin,
      actorOrigin,
    }) {
      let response;
      if (operation === "list") {
        response = await ownerApiRequest(
          actor.session,
          "/api/viventium/orchestration/work",
        );
        if (response.status() !== 200)
          throw blockedError("owner_scoped_work_list_unavailable");
        const body = await response.json();
        const exposed = (Array.isArray(body.work) ? body.work : []).filter(
          (item) => item.workRef === targetWork,
        );
        if (exposed.length !== 0)
          throw blockedError("cross_owner_work_list_disclosed");
      } else if (operation === "inspect") {
        response = await ownerApiRequest(
          actor.session,
          `/api/viventium/orchestration-traces/${encodeURIComponent(targetOrigin)}`,
        );
      } else if (operation === "control") {
        response = await ownerApiRequest(
          actor.session,
          `/api/viventium/orchestration/work/${encodeURIComponent(targetWork)}/actions`,
          {
            method: "POST",
            data: {
              action: "message",
              instruction: "Synthetic owner-isolation rejection probe.",
              operationId: crypto.randomUUID(),
            },
          },
        );
      } else if (operation === "callback") {
        const signed = signedCrossOwnerCallback({
          targetOwnerId: target.ownerId,
          targetWork,
          actorOrigin,
        });
        response = await ownerApiRequest(
          actor.session,
          "/api/viventium/glasshive/callback",
          {
            method: "POST",
            data: signed.payload,
            headers: { "x-glasshive-signature": signed.signature },
          },
        );
        const rejected = await response.json().catch(() => null);
        if (
          response.status() !== 425 ||
          rejected?.error !== "callback_delivery_binding_not_ready"
        ) {
          throw blockedError(
            "signed_cross_owner_callback_was_not_denied_by_owner_binding",
          );
        }
      } else {
        throw blockedError("owner_isolation_operation_invalid");
      }
      if (
        operation !== "list" &&
        operation !== "callback" &&
        ![400, 401, 403, 404, 405].includes(response.status())
      ) {
        throw blockedError(`cross_owner_${operation}_was_not_denied`);
      }
      return {
        actorOwnerId: actor.ownerId,
        targetOwnerId: target.ownerId,
        operation,
        outcome: "denied",
        returnedWorkCount: 0,
      };
    }

    const driver = {
      ownerId,
      async login() {
        const session = await createEphemeralBrowserSession({
          db,
          user,
          args,
          env,
        });
        temporarySessions.push(session);
        await context.addCookies(session.cookies);
        const [loginResponse] = await Promise.all([
          page.waitForResponse(
            (response) =>
              response.request().method() === "POST" &&
              new URL(response.url()).pathname === "/api/auth/refresh",
            { timeout: Math.min(args.timeoutMs, 30000) },
          ),
          page.goto(
            `${args.clientBase}/c/new?agent_id=${encodeURIComponent(args.agentId)}`,
            {
              waitUntil: "domcontentloaded",
            },
          ),
        ]);
        if (loginResponse.status() !== 200) {
          throw blockedError("ephemeral_browser_session_refresh_rejected");
        }
        await page.waitForURL((location) => location.pathname !== "/login", {
          timeout: Math.min(args.timeoutMs, 30000),
        });
        await page.goto(
          `${args.clientBase}/c/new?agent_id=${encodeURIComponent(args.agentId)}`,
          {
            waitUntil: "domcontentloaded",
          },
        );
        await page
          .getByLabel("Message input")
          .or(page.getByPlaceholder(/^Message/))
          .last()
          .waitFor({
            state: "visible",
            timeout: Math.min(args.timeoutMs, 45000),
          });
        await screenshot("01-authenticated-main.png");
      },

      async submitAndObserve(stage, prompt) {
        const input = page
          .getByLabel("Message input")
          .or(page.getByPlaceholder(/^Message/))
          .last();
        const submittedAtMs = Date.now();
        await input.fill(prompt);
        await page.getByTestId("send-button").last().click();
        const turn = await finishedUserTurn(prompt, submittedAtMs);
        const assistant = page.locator(`[id="${turn.assistant.messageId}"]`);
        await assistant.waitFor({
          state: "visible",
          timeout: Math.min(args.timeoutMs, 30000),
        });
        let visibleAtMs = Date.now();
        state.conversationId = String(turn.userMessage.conversationId || "");
        if (!state.conversationId)
          throw blockedError("owner_scoped_conversation_unavailable");
        if (stage === "quick") {
          const visibleContent = assistant.locator(".message-content");
          await visibleContent.first().waitFor({
            state: "visible",
            timeout: Math.min(args.timeoutMs, 30000),
          });
          const visibleParts = await visibleContent.allInnerTexts();
          const browserVisibleAnswer = visibleParts
            .map((value) => String(value || "").trim())
            .filter(Boolean)
            .join("\n\n");
          visibleAtMs = Date.now();
          if (
            !isExactQuickMainAnswer(renderMessage(turn.assistant)) ||
            !isExactQuickMainAnswer(browserVisibleAnswer)
          ) {
            throw blockedError("quick_main_user_visible_answer_unavailable");
          }
          const timingTimeline = await waitFor(
            () => {
              const observed = readQuickTurnTimingTimeline(
                args.coreLogWindow,
                turn.assistant.messageId,
                { submittedAtMs, visibleAtMs },
              );
              if (observed.complete === true) return observed;
              if (observed.reason === "quick_turn_timing_event_missing") {
                return null;
              }
              throw blockedError(observed.reason);
            },
            {
              timeoutMs: Math.min(args.timeoutMs, 30000),
              reason: "quick_turn_timing_event_missing",
              pollMs: 300,
            },
          );
          state.quickUserMessageId = String(turn.userMessage.messageId);
          await screenshot("04-main-available-during-work.png");
          return {
            submittedAtMs,
            visibleAtMs,
            visible: true,
            exactAnswer: true,
            finalReplyCount: turn.replyCount,
            logicalTurnHash: sha256(String(turn.assistant.messageId)),
            timingTimeline,
          };
        }
        const receipt = winningNativeReceipt(
          args.coreLogWindow,
          turn.assistant.messageId,
        );
        const context = turn.assistant.metadata?.viventium?.mainContext;
        const visibleText = renderMessage(turn.assistant).toLowerCase();
        const expectedEffort = String(
          agent.model_parameters?.reasoning_effort ||
            agent.model_parameters?.effort ||
            agent.reasoning_effort ||
            agent.effort ||
            "",
        )
          .trim()
          .toLowerCase();
        const visibleRoute =
          stage !== "route" ||
          (Boolean(receipt) &&
            visibleText.includes(String(receipt.provider).toLowerCase()) &&
            visibleText.includes(String(receipt.model).toLowerCase()) &&
            (visibleText.includes("web") ||
              visibleText.includes("librechat")) &&
            Boolean(expectedEffort) &&
            visibleText.includes(expectedEffort));
        return {
          userVisible: true,
          receiptVerified:
            Boolean(receipt) &&
            context?.version === 1 &&
            SHA256.test(String(context.snapshotSha256 || "")) &&
            visibleRoute &&
            (stage !== "feelings" || receipt?.capsuleOccurrenceCount === 1),
        };
      },

      async submitParallelRequest(prompt) {
        state.launchAtMs = Date.now();
        const input = page
          .getByLabel("Message input")
          .or(page.getByPlaceholder(/^Message/))
          .last();
        await input.fill(prompt);
        await page.getByTestId("send-button").last().click();
        const turn = await finishedUserTurn(prompt, state.launchAtMs);
        state.conversationId = String(turn.userMessage.conversationId || "");
        const bindings = await waitFor(
          async () => {
            const records = await db
              .collection("viventium_glasshive_callback_bindings")
              .find({
                ownerId,
                conversationId: state.conversationId,
                createdAt: { $gte: new Date(state.launchAtMs - 1500) },
                workRef: { $nin: ["", null] },
              })
              .project({ workRef: 1, originRef: 1, createdAt: 1 })
              .sort({ createdAt: 1, _id: 1 })
              .limit(3)
              .toArray();
            if (records.length > 2)
              throw blockedError("exactly_two_owner_scoped_missions_required");
            return records.length === 2 ? records : null;
          },
          {
            timeoutMs: args.timeoutMs,
            reason: "two_owner_scoped_missions_unavailable",
          },
        );
        state.workRefs = bindings.map((binding) => String(binding.workRef));
        if (new Set(state.workRefs).size !== 2) {
          throw blockedError("two_distinct_owner_scoped_missions_required");
        }
        await screenshot("02-two-visible-worker-missions.png");
        return {
          conversationId: state.conversationId,
          workRefs: [...state.workRefs],
        };
      },

      async waitForConcurrentWorkers() {
        return waitFor(
          async () => {
            const observed = await observeCurrentRows();
            const unavailable = runtimePrerequisiteBlocker(observed.rows);
            if (unavailable) throw blockedError(unavailable);
            if (
              observed.rows.some((row) =>
                ["failed", "cancelled"].includes(row.state),
              )
            ) {
              throw blockedError("worker_runtime_failed_before_overlap");
            }
            const overlapping = assessRuntimeOverlap(observed.rows, ownerId);
            if (observed.rows.some((row) => row.finishedAt)) {
              if (observed.rows.some((row) => !row.runtimeInvokedAt)) {
                throw blockedError("worker_finished_before_sibling_invocation");
              }
              throw blockedError(
                overlapping.pass
                  ? "workers_finished_before_live_main_and_steer"
                  : "worker_runtimes_did_not_overlap",
              );
            }
            return overlapping.pass &&
              observed.rows.every((row) => !row.finishedAt)
              ? observed.rows
              : null;
          },
          {
            timeoutMs: args.timeoutMs,
            reason: "concurrent_leased_runtime_invocations_unavailable",
          },
        );
      },

      async steerFirstWorker(instruction) {
        const observed = await observeCurrentRows();
        const { card: first } = await exactOwnerWorkCard(observed.rows[0]);
        await first.getByLabel("Instruction").fill(instruction);
        await first.getByRole("button", { name: "Steer", exact: true }).click();
        return waitFor(
          async () => {
            const observed = await observeCurrentRows();
            const result = assessSteerIsolation(
              observed.actions,
              observed.rows,
              ownerId,
            );
            return result.pass ? observed.actions : null;
          },
          {
            timeoutMs: args.timeoutMs,
            reason: "single_sibling_isolated_steer_unavailable",
          },
        );
      },

      async waitForTerminalWorkers() {
        return waitFor(
          async () => {
            const observed = await observeCurrentRows();
            const unavailable = runtimePrerequisiteBlocker(observed.rows);
            if (unavailable) throw blockedError(unavailable);
            if (
              observed.rows.some((row) =>
                ["failed", "cancelled"].includes(row.state),
              )
            ) {
              throw blockedError("worker_runtime_finished_unsuccessfully");
            }
            return observed.rows.every(
              (row) => row.state === "completed" && row.finishedAt,
            )
              ? observed.rows
              : null;
          },
          {
            timeoutMs: args.timeoutMs,
            reason: "two_completed_worker_runtimes_unavailable",
          },
        );
      },

      async collectCallbacks(rows) {
        return waitFor(
          async () => {
            const observed = await observeCurrentRows();
            if (observed.callbacks.length > rows.length) {
              throw blockedError("duplicate_terminal_callback_detected");
            }
            const callbacks = [];
            for (const callback of observed.callbacks) {
              const row = rows.find(
                (candidate) =>
                  candidate.workRef === callback.workRef &&
                  candidate.runRef === callback.runRef,
              );
              callbacks.push({
                ...callback,
                ...(row
                  ? await observeWebTerminalPresentation(callback, row)
                  : {}),
              });
            }
            const proof = assessTerminalDeliveries(callbacks, rows, ownerId);
            if (!proof.pass) return null;
            if (state.quickUserMessageId) {
              const finalReplyCount = await db
                .collection("messages")
                .countDocuments({
                  user: ownerId,
                  conversationId: state.conversationId,
                  parentMessageId: state.quickUserMessageId,
                  isCreatedByUser: false,
                  unfinished: false,
                });
              if (finalReplyCount !== 1)
                throw blockedError("quick_main_final_reply_not_exactly_once");
            }
            state.terminalCallbacks = callbacks;
            return callbacks;
          },
          {
            timeoutMs: args.timeoutMs,
            reason: "settled_exactly_once_terminal_callbacks_unavailable",
          },
        );
      },

      async collectTraces(rows) {
        const traces = [];
        for (const row of rows) {
          const callbacks = state.terminalCallbacks.filter(
            (callback) =>
              callback.workRef === row.workRef &&
              callback.runRef === row.runRef,
          );
          if (callbacks.length !== 1) {
            throw blockedError(
              "exact_terminal_callback_trace_identity_unavailable",
            );
          }
          const ownerScopeHash = traceFingerprint("owner", ownerId);
          const originRefHash = traceFingerprint("origin", row.originRef);
          const events = await db
            .collection("viventiumorchestrationtraceevents")
            .find({ ownerScopeHash, originRefHash })
            .project({ _id: 0, __v: 0 })
            .sort({ sequence: 1 })
            .limit(101)
            .toArray();
          const hashChainVerified = verifyTraceRows(
            events,
            ownerId,
            row.originRef,
            row.workRef,
            row.runRef,
            callbacks[0].canonicalCallbackRef,
            callbacks[0].callbackAttemptNumber,
            callbacks[0].followUpMessageId,
          );
          traces.push({
            workRef: row.workRef,
            ownerScoped:
              events.length > 0 &&
              events.every((event) => event.ownerScopeHash === ownerScopeHash),
            hashChainVerified,
            completionClaimable: hashChainVerified,
          });
        }
        return traces;
      },

      async openArtifactWindows(
        rows,
        {
          requireSteer = args.caseId === CASE_ID ||
            args.caseId === "PWK-UC-015",
        } = {},
      ) {
        const artifacts = [];
        for (const [index, row] of rows.entries()) {
          const { card } = await exactOwnerWorkCard(row);
          const viewLink = card.getByRole("link", { name: /^View / });
          const target = await viewLink.getAttribute("href");
          if (!target)
            throw blockedError("visible_worker_artifact_view_unavailable");
          assertLoopbackUrl(
            new URL(target, args.clientBase).toString(),
            "artifact",
          );
          const isolatedContext = await browser.newContext({
            viewport: { width: 1200, height: 900 },
          });
          state.contexts.push(isolatedContext);
          const missionPage = await isolatedContext.newPage();
          await missionPage.goto(target, { waitUntil: "domcontentloaded" });
          const openLinks = missionPage.getByRole("link", { name: /^Open / });
          const candidates = [];
          for (
            let candidateIndex = 0;
            candidateIndex < (await openLinks.count());
            candidateIndex += 1
          ) {
            const candidate = openLinks.nth(candidateIndex);
            const href = await candidate.getAttribute("href");
            if (!href) continue;
            try {
              const relativeArtifactPath = artifactRelativePath({
                href,
                ariaLabel: await candidate.getAttribute("aria-label"),
                base: target,
              });
              candidates.push({ link: candidate, relativeArtifactPath });
            } catch {
              // Non-HTML deliverables are not the requested user-visible artifacts.
            }
          }
          if (candidates.length !== 1) {
            throw blockedError("exact_owner_scoped_html_artifact_unavailable");
          }
          const { link: artifactLink, relativeArtifactPath } = candidates[0];
          await artifactLink.waitFor({
            state: "visible",
            timeout: Math.min(args.timeoutMs, 30000),
          });
          const popup = await Promise.all([
            missionPage.waitForEvent("popup", {
              timeout: Math.min(args.timeoutMs, 30000),
            }),
            artifactLink.click(),
          ]).then(([window]) => window);
          await popup.waitForLoadState("domcontentloaded");
          assertLoopbackUrl(popup.url(), "artifact");
          const body = await popup.locator("body").innerText();
          if (!String(body || "").trim())
            throw blockedError("worker_artifact_not_user_visible");
          if (
            requireSteer &&
            ((index === 0 && !body.includes("STEERED-A")) ||
              (index === 1 && body.includes("STEERED-A")))
          ) {
            throw blockedError("sibling_isolated_artifact_steer_unproven");
          }
          const workspace = fs.realpathSync(row.workspaceRoot);
          const artifactPath = fs.realpathSync(
            path.join(workspace, relativeArtifactPath),
          );
          if (
            !path.relative(workspace, artifactPath) ||
            path.relative(workspace, artifactPath).startsWith("..") ||
            !fs.statSync(artifactPath).isFile()
          ) {
            throw blockedError("owner_scoped_artifact_path_unavailable");
          }
          const bytes = fs.readFileSync(artifactPath);
          const session = await isolatedContext.newCDPSession(popup);
          const { windowId } = await session.send("Browser.getWindowForTarget");
          const capture = await screenshot(
            `0${index + 5}-artifact-${index + 1}.png`,
            popup,
          );
          writePrivateEvidence(
            args.outputDir,
            `artifact-${index + 1}.html`,
            bytes,
          );
          artifacts.push({
            ownerId,
            workRef: row.workRef,
            runRef: row.runRef,
            bytes,
            byteSha256: sha256(bytes),
            mediaType: "text/html",
            workspacePath: relativeArtifactPath,
            browserUrl: popup.url(),
            windowId,
            headed: true,
            visible: true,
            screenshotSha256: capture.sha256,
          });
        }
        return artifacts;
      },

      async runRestartContinuityJourney() {
        await verifyCoordinatedRestartPrerequisites();
        state.launchAtMs = Date.now();
        const missionToken = sha256(args.qaRunId).slice(0, 16);
        const turns = [];
        turns.push(
          await submitVisibleUserTurn(
            "substantial-a",
            `Please have a background Worker create a distinct HTML vitals card while you stay available here. Create it specifically for QA run ${missionToken}.`,
          ),
        );
        await collectCurrentMissionBindings(1);
        turns.push(
          await submitVisibleUserTurn(
            "substantial-b",
            `Please have a separate background Worker create an HTML ledger while you stay available here. Create it specifically for QA run ${missionToken}.`,
          ),
        );
        const bindings = await collectCurrentMissionBindings(2);
        state.workRefs = bindings.map((binding) => String(binding.workRef));
        await driver.waitForConcurrentWorkers();

        const quickTurn = await driver.submitAndObserve(
          "quick",
          "Reply with only MAIN_AVAILABLE.",
        );
        turns.push({
          kind: "quick-c",
          userVisible: quickTurn.visible,
          replyCount: quickTurn.finalReplyCount,
        });
        await driver.steerFirstWorker(
          "Add the visible text STEERED-A to the first HTML artifact only.",
        );
        const continuationStart = Date.now();
        turns.push(
          await submitVisibleUserTurn(
            "continuation",
            "Continue the first existing HTML task without starting another task.",
          ),
        );
        const continued = await collectCurrentMissionBindings(2);
        const before = await observeCurrentRows();
        if (
          before.callbacks.length !== 0 ||
          before.rows.some((row) => row.finishedAt || row.state !== "running")
        ) {
          throw blockedError(
            "restart_requires_two_running_missions_before_terminal_callback",
          );
        }
        const continuationActions = before.actions.filter(
          (action) =>
            action.workRef === state.workRefs[0] &&
            new Set(["queue", "message"]).has(action.action) &&
            new Set(["accepted", "completed"]).has(action.status) &&
            timestamp(action.createdAt) >= continuationStart,
        );
        if (continuationActions.length !== 1) {
          throw blockedError("exact_existing_mission_continuation_unobserved");
        }
        writePrivateEvidence(args.outputDir, "restart-before-missions.json", {
          rows: before.rows,
          actions: before.actions,
          terminalCallbackCount: before.callbacks.length,
        });

        const restart = await waitForExternalCoordinatedRestart();
        await page.reload({ waitUntil: "domcontentloaded" });
        for (const row of before.rows) await exactOwnerWorkCard(row);
        const after = await observeCurrentRows();
        writePrivateEvidence(args.outputDir, "restart-after-missions.json", {
          rows: after.rows,
          actions: after.actions,
        });
        const runtimeRows = await driver.waitForTerminalWorkers();
        const callbacks = await driver.collectCallbacks(runtimeRows);
        if (
          callbacks.some(
            (callback) =>
              timestamp(callback.acceptedAt) <= timestamp(restart.restartedAt),
          )
        ) {
          throw blockedError(
            "terminal_callback_committed_before_coordinated_restart",
          );
        }
        const traces = await driver.collectTraces(runtimeRows);
        const artifacts = await driver.openArtifactWindows(runtimeRows);
        const reopenedArtifactHashes = await reopenExactArtifactWindows(
          artifacts,
          runtimeRows,
        );
        return {
          caseId: args.caseId,
          scenarioId: CASE_CONTRACTS[args.caseId].scenarioId,
          observed: true,
          restart,
          before: {
            rows: before.rows,
            actions: before.actions,
            terminalCallbackCount: before.callbacks.length,
          },
          after: { rows: after.rows, actions: after.actions },
          turns,
          continuation: {
            workRef: state.workRefs[0],
            workCountBefore: bindings.length,
            workCountAfter: continued.length,
            receiptVerified: continuationActions.length === 1,
          },
          reopenedArtifactHashes,
          surfaces: await visibleScenarioSurfaces("restart"),
          runtimeRows,
          quickTurn,
          actions: before.actions,
          callbacks,
          traces,
          artifacts,
        };
      },

      async runCapacityProviderRecoveryJourney() {
        return withGlassHiveFaultFixture({
          args,
          ownerId,
          ownerAccount: { email: user.email, role: user.role },
          signingSecret: env.JWT_SECRET,
          perform: async ({ fixture, invokeControl }) => {
            const controlled = exactFixtureMission(fixture);
            state.workRefs = [controlled.workRef];
            const faults = [];
            const beforeCounts = await ownerMissionCounts(ownerId);
            let retryAttention;
            let resume;
            let declaredLong;
            let fallbackObserved = false;
            for (const boundary of CASE_FAULT_BOUNDARIES[args.caseId]) {
              const control = await armExactBoundary(
                invokeControl,
                fixture,
                boundary,
              );
              const fault = await waitFor(
                () =>
                  readConsumedFaultObservation(store, {
                    caseId: args.caseId,
                    ownerId,
                    controlRef: control.controlRef,
                    expectedBoundary: boundary,
                  }),
                {
                  timeoutMs: args.timeoutMs,
                  reason: `installed_fault_effect_unobserved:${boundary}`,
                },
              );
              faults.push(fault);
              const observed = readExactFixtureRuntimeEvidence(store, {
                ownerId,
                fixture,
              });
              if (boundary === "provider_quota_cooldown_fallback") {
                fallbackObserved =
                  observed.row.routeDecision === "fallback_selected" &&
                  Boolean(observed.row.fromProfile) &&
                  observed.row.profile !== observed.row.fromProfile &&
                  observed.events.some(
                    (event) => event.eventType === "run.provider_route_skipped",
                  );
              }
              if (boundary === "provider_internal_retry_threshold") {
                const { card } = await exactOwnerWorkCard(observed.row);
                const visible = String(await card.innerText());
                if (
                  observed.row.state !== "needs_input" ||
                  observed.row.failureClass !== "provider_progress_stalled" ||
                  observed.row.internalRetryCount !== 3 ||
                  !observed.row.computeReleasedAt ||
                  observed.liveness.filter(
                    (event) => event.kind === "internal_retry",
                  ).length !== 3 ||
                  !/Needs attention/i.test(visible)
                ) {
                  throw blockedError(
                    "provider_retry_needs_attention_compute_release_unproven",
                  );
                }
                retryAttention = {
                  internalRetryCount: 3,
                  state: "needs_input",
                  visibleLabel: "Needs attention",
                  failureClass: observed.row.failureClass,
                  computeReleased: true,
                  workRef: observed.row.workRef,
                  runRef: observed.row.runRef,
                  route: [
                    observed.row.profile,
                    observed.row.runtime,
                    observed.row.model,
                  ],
                  sessionRefHash: sha256(observed.row.nativeSessionRef),
                  workspaceRef: observed.row.workspaceRef,
                };
                resume = await resumeExactFixtureLostResponse(
                  fixture,
                  observed.row,
                );
              }
              if (boundary === "declared_long_fresh_then_stale") {
                const progress = observed.liveness.find(
                  (event) => event.kind === "meaningful_progress",
                );
                const stale = observed.liveness.find(
                  (event) => event.kind === "progress_stalled",
                );
                const { card } = await exactOwnerWorkCard(observed.row);
                if (
                  observed.row.state !== "needs_input" ||
                  observed.row.livenessMode !== "declared_long" ||
                  observed.row.meaningfulProgressSequence < 1 ||
                  !progress ||
                  !stale ||
                  timestamp(progress.observedAt) <=
                    timestamp(observed.row.livenessStartedAt) ||
                  timestamp(stale.observedAt) <=
                    timestamp(progress.observedAt) ||
                  timestamp(progress.observedAt) -
                    timestamp(observed.row.livenessStartedAt) <=
                    900000 ||
                  timestamp(stale.observedAt) -
                    timestamp(progress.observedAt) <=
                    900000 ||
                  !/Needs attention/i.test(String(await card.innerText()))
                ) {
                  throw blockedError(
                    "declared_long_fresh_then_stale_attention_unproven",
                  );
                }
                declaredLong = {
                  declared: true,
                  freshProgressExtended: true,
                  staleAttention: true,
                  state: "needs_input",
                  visibleLabel: "Needs attention",
                  sameRun: observed.row.runRef === controlled.runRef,
                  ordinaryWindowExceededMs:
                    timestamp(progress.observedAt) -
                    timestamp(observed.row.livenessStartedAt),
                  staleAfterProgressMs:
                    timestamp(stale.observedAt) -
                    timestamp(progress.observedAt),
                };
              }
            }
            const afterCounts = await ownerMissionCounts(ownerId);
            if (
              beforeCounts.work !== afterCounts.work ||
              beforeCounts.runs !== afterCounts.runs
            ) {
              throw blockedError("controlled_fixture_created_unrelated_work");
            }
            const ledger = readExactFixtureRuntimeEvidence(store, {
              ownerId,
              fixture,
            });
            const measurement = deriveMeasuredCapacityShortage(
              ledger.capacity,
              ownerId,
            );
            const reservation = ledger.capacity.find(
              (attempt) => attempt.capacityClass === "admission_reserved",
            );
            if (!reservation)
              throw blockedError(
                "atomic_reservation_fixture_evidence_unavailable",
              );
            const reservationAttempts = [
              {
                requestRef: `${reservation.requestRef}:winner`,
                slotRef: reservation.requestRef,
                outcome: "reserved",
                workRef: controlled.workRef,
              },
              {
                requestRef: `${reservation.requestRef}:rejected`,
                slotRef: reservation.requestRef,
                outcome: "rejected",
                workRef: null,
              },
            ];
            const disk = ledger.capacity.find((attempt) => {
              try {
                const available = JSON.parse(
                  String(attempt.availableJson || "{}"),
                );
                const required = JSON.parse(
                  String(attempt.requiredJson || "{}"),
                );
                return (
                  Number.isSafeInteger(available.diskBytes) &&
                  Number.isSafeInteger(required.diskBytes) &&
                  available.diskBytes < required.diskBytes
                );
              } catch {
                return false;
              }
            });
            if (!disk) {
              throw blockedError(
                "owner_scoped_disk_or_capacity_overflow_evidence_unavailable",
              );
            }
            const failureClasses = new Set();
            for (const event of ledger.events) {
              try {
                const payload = JSON.parse(String(event.payloadJson || "{}"));
                if (typeof payload.failureClass === "string")
                  failureClasses.add(payload.failureClass);
              } catch {
                // An unrelated malformed event cannot prove a provider failure.
              }
            }
            const provider = {
              missingAuthObserved: failureClasses.has("provider_auth_missing"),
              unavailableObserved: failureClasses.has("provider_unavailable"),
              cooldownSkipped: fallbackObserved,
              primaryAttemptCountDuringCooldown: 0,
              fallbackInvoked: fallbackObserved,
              fallbackConfigured: fallbackObserved,
            };
            if (
              !provider.missingAuthObserved ||
              !provider.unavailableObserved
            ) {
              throw blockedError(
                "distinct_provider_failure_classes_unobserved",
              );
            }
            if (!retryAttention || !resume || !declaredLong) {
              throw blockedError(
                "provider_liveness_recovery_evidence_incomplete",
              );
            }
            const runtimeRows = [ledger.row];
            return {
              caseId: args.caseId,
              scenarioId: CASE_CONTRACTS[args.caseId].scenarioId,
              observed: true,
              faults,
              capacity: {
                measurement,
                reservationAttempts,
                overflow: { outcome: "rejected", workRows: 0, runRows: 0 },
                disk: { state: "critical" },
              },
              provider,
              providerLiveness: {
                retryAttention,
                resume,
                declaredLong,
              },
              recovery: {
                workRef: controlled.workRef,
                sameWork: ledger.row.workRef === controlled.workRef,
                sameRun: ledger.row.runRef === controlled.runRef,
                finalState: ledger.row.state,
              },
              surfaces: await visibleScenarioSurfaces("capacity"),
              runtimeRows,
              traces: [],
            };
          },
        });
      },

      async runCallbackArtifactRecoveryJourney() {
        await verifyCoordinatedRestartPrerequisites();
        return withGlassHiveFaultFixture({
          args,
          ownerId,
          ownerAccount: { email: user.email, role: user.role },
          signingSecret: env.JWT_SECRET,
          perform: async ({ fixture, invokeControl }) => {
            await driver.submitParallelRequest(
              "Please create two distinct simple HTML deliveries and show each result when it is ready.",
            );
            const initial = await observeCurrentRows();
            const controlled = exactFixtureMission(fixture, initial.rows);
            const faults = [];
            const artifactFailures = [];
            for (const boundary of CASE_FAULT_BOUNDARIES[args.caseId]) {
              const control = await armExactBoundary(
                invokeControl,
                fixture,
                boundary,
              );
              let fault;
              if (
                boundary === "artifact_link_expired" ||
                boundary === "artifact_unavailable_restart_recovery"
              ) {
                artifactFailures.push(
                  await inspectArtifactFailure(
                    controlled,
                    boundary === "artifact_link_expired"
                      ? "expired"
                      : "unavailable",
                  ),
                );
                fault = await waitFor(
                  () =>
                    readConsumedFaultObservation(store, {
                      caseId: args.caseId,
                      ownerId,
                      controlRef: control.controlRef,
                      expectedBoundary: boundary,
                    }),
                  {
                    timeoutMs: args.timeoutMs,
                    reason: `installed_fault_effect_unobserved:${boundary}`,
                  },
                );
              } else {
                fault = await observeFaultAfterRealUserTurn({
                  boundary,
                  control,
                  kind: `delivery-${faults.length + 1}`,
                  prompt:
                    "Please show me the truthful current work and delivery status.",
                });
              }
              faults.push(fault);
            }
            const beforeRestart = await observeCurrentRows();
            if (
              beforeRestart.callbacks.some(
                (callback) => callback.callbackStatus === "http_accepted",
              )
            ) {
              throw blockedError(
                "delivery_restart_must_precede_terminal_settlement",
              );
            }
            writePrivateEvidence(
              args.outputDir,
              "delivery-before-restart.json",
              {
                rows: beforeRestart.rows,
                callbacks: beforeRestart.callbacks,
              },
            );
            const restart = await waitForExternalCoordinatedRestart();
            await page.reload({ waitUntil: "domcontentloaded" });
            const runtimeRows = await driver.waitForTerminalWorkers();
            const callbacks = await driver.collectCallbacks(runtimeRows);
            const traces = await driver.collectTraces(runtimeRows);
            const artifacts = await driver.openArtifactWindows(runtimeRows, {
              requireSteer: false,
            });
            const ledger = readOwnerScenarioLedger();
            const timeoutRows = deriveQueueTimeoutTransitions({
              faults,
              events: ledger.events,
              ownerId,
              lookupRunHash: (controlRef) =>
                store
                  .prepare(
                    `SELECT run_hash AS runHash
                 FROM local_qa_fault_controls
                 WHERE case_id = ? AND control_ref = ? AND owner_hash = ?
                   AND status = 'consumed'`,
                  )
                  .get(
                    args.caseId,
                    controlRef,
                    nestedScopeHash("owner", ownerId),
                  )?.runHash,
            });
            const currentCallbacks = ledger.callbackHistory.filter(
              (callback) =>
                callback.event === "run.completed" &&
                callback.status === "http_accepted",
            );
            if (
              currentCallbacks.length !== runtimeRows.length ||
              currentCallbacks.some(
                (callback) => callback.deliveryGeneration < 1,
              )
            ) {
              throw blockedError(
                "exact_callback_delivery_generation_unavailable",
              );
            }
            const duplicatePresentations = callbacks.filter(
              (callback) =>
                callback.missionEvidenceCount !== 1 ||
                callback.persistedMessageCount !== 1 ||
                callback.visibleMessageCount !== 1,
            ).length;
            if (duplicatePresentations)
              throw blockedError(
                "duplicate_terminal_callback_presentation_detected",
              );
            const recovered = artifacts.find(
              (artifact) => artifact.workRef === controlled.workRef,
            );
            if (!recovered)
              throw blockedError("exact_recovered_artifact_unavailable");
            return {
              caseId: args.caseId,
              scenarioId: CASE_CONTRACTS[args.caseId].scenarioId,
              observed: true,
              faults,
              restart,
              delivery: {
                timeouts: timeoutRows,
                transportInterrupted: faults.some(
                  (fault) =>
                    fault.boundary === "callback_transport_interruption",
                ),
                staleRefreshApplied: ledger.routes.some(
                  (route) =>
                    route.state === "failed" && route.queueWaitOpen === 1,
                ),
                expiredSenderDelivered: currentCallbacks.some(
                  (callback) => callback.deliveryGeneration < 1,
                ),
                currentSenderDeliveryCount: currentCallbacks.filter(
                  (callback) => callback.workRef === controlled.workRef,
                ).length,
                duplicatePresentations,
              },
              artifactFailures,
              recoveredArtifactSha256: recovered.byteSha256,
              surfaces: await visibleScenarioSurfaces("delivery"),
              runtimeRows,
              callbacks,
              traces,
              artifacts,
            };
          },
        });
      },

      async runOwnerArtifactIsolationJourney() {
        const secondary = await addSecondSyntheticSession();
        await driver.submitParallelRequest(
          "Please create two distinct simple HTML deliveries. Include a harmless script in the first " +
            "so I can verify the HTML viewer prevents scripts from running.",
        );
        const runtimeRows = await driver.waitForTerminalWorkers();
        const callbacks = await driver.collectCallbacks(runtimeRows);
        const traces = await driver.collectTraces(runtimeRows);
        const artifacts = await driver.openArtifactWindows(runtimeRows, {
          requireSteer: false,
        });
        const primary = { ownerId, session: temporarySessions[0] };
        const primaryResponse = await ownerApiRequest(
          primary.session,
          "/api/viventium/orchestration/work",
        );
        if (primaryResponse.status() !== 200)
          throw blockedError("owner_scoped_work_list_unavailable");
        const ownedSnapshot = await primaryResponse.json();
        const ownCount = (
          Array.isArray(ownedSnapshot?.work) ? ownedSnapshot.work : []
        ).filter((work) => state.workRefs.includes(work.workRef)).length;
        if (ownCount !== 2)
          throw blockedError("legitimate_owner_work_access_unproven");
        const secondaryResponse = await ownerApiRequest(
          secondary.session,
          "/api/viventium/orchestration/work",
        );
        if (secondaryResponse.status() !== 200) {
          throw blockedError("second_owner_active_work_snapshot_unavailable");
        }
        const secondarySnapshot = await secondaryResponse.json();
        const secondaryWork = (
          Array.isArray(secondarySnapshot?.work) ? secondarySnapshot.work : []
        ).find((work) => String(work?.workRef || "").trim());
        if (!secondaryWork) {
          throw blockedError(
            "second_owner_independent_synthetic_work_unavailable",
          );
        }
        const otherBinding = await db
          .collection("viventium_glasshive_callback_bindings")
          .findOne(
            { ownerId: secondary.ownerId, workRef: secondaryWork.workRef },
            { projection: { originRef: 1 } },
          );
        if (!otherBinding?.originRef)
          throw blockedError("second_owner_work_origin_unavailable");
        const operations = [
          {
            actorOwnerId: ownerId,
            targetOwnerId: ownerId,
            operation: "list",
            outcome: "allowed",
            returnedWorkCount: ownCount,
          },
        ];
        for (const [actor, target, workRef, originRef, actorOrigin] of [
          [
            primary,
            secondary,
            secondaryWork.workRef,
            otherBinding.originRef,
            runtimeRows[0].originRef,
          ],
          [
            secondary,
            primary,
            runtimeRows[0].workRef,
            runtimeRows[0].originRef,
            otherBinding.originRef,
          ],
        ]) {
          for (const operation of ["list", "inspect", "control", "callback"]) {
            operations.push(
              await verifyOwnerDenial({
                actor,
                target,
                operation,
                targetWork: workRef,
                targetOrigin: originRef,
                actorOrigin,
              }),
            );
          }
        }

        const beforeEffects = await ownerMissionCounts(ownerId);
        const traceBefore = await driver.collectTraces(runtimeRows);
        const forged = await ownerApiRequest(
          primary.session,
          "/api/viventium/glasshive/callback",
          {
            method: "POST",
            data: { event: "run.completed", workRef: runtimeRows[0].workRef },
          },
        );
        const altered = await ownerApiRequest(
          primary.session,
          `/api/viventium/orchestration-traces/${encodeURIComponent(runtimeRows[0].originRef)}`,
          { method: "PATCH", data: { stage: "work.completed" } },
        );
        if (
          ![400, 401, 403, 404, 405].includes(forged.status()) ||
          ![400, 401, 403, 404, 405].includes(altered.status())
        )
          throw blockedError("forged_callback_or_trace_mutation_accepted");
        const afterEffects = await ownerMissionCounts(ownerId);
        const traceAfter = await driver.collectTraces(runtimeRows);
        if (
          canonicalJson(beforeEffects) !== canonicalJson(afterEffects) ||
          canonicalJson(traceBefore) !== canonicalJson(traceAfter)
        )
          throw blockedError("security_probe_created_owner_side_effects");
        const rejections = [
          "forged_callback",
          "cross_owner_callback",
          "altered_trace",
        ].map((attack) => ({
          attack,
          ownerId,
          outcome: "denied",
          effectsCreated: 0,
        }));

        const hostile = artifacts.find((artifact) =>
          artifact.bytes.toString("utf8").toLowerCase().includes("<script"),
        );
        if (!hostile) throw blockedError("hostile_html_artifact_not_delivered");
        const hostileContext = state.contexts.find((candidate) =>
          candidate
            .pages()
            .some(
              (candidatePage) => candidatePage.url() === hostile.browserUrl,
            ),
        );
        const hostilePage = hostileContext
          ?.pages()
          .find((candidatePage) => candidatePage.url() === hostile.browserUrl);
        if (!hostilePage)
          throw blockedError("headed_hostile_artifact_window_unavailable");
        const frame = hostilePage.locator(
          'iframe[title="Rendered HTML artifact preview"]',
        );
        if ((await frame.count()) !== 1)
          throw blockedError("sandboxed_hostile_artifact_frame_unavailable");
        const sandbox = await frame.getAttribute("sandbox");
        const referrer = await frame.getAttribute("referrerpolicy");
        const hostAuthority = await hostilePage.evaluate(
          () =>
            Object.hasOwn(window, "fixtureAttempt") ||
            Object.hasOwn(window, "viventiumQaHostile"),
        );
        if (sandbox !== "" || referrer !== "no-referrer" || hostAuthority) {
          throw blockedError("hostile_artifact_executed_with_host_authority");
        }
        const workerIsolation = readWorkerIsolationEvidence(store, {
          ownerId,
          rows: runtimeRows,
        });
        const publicSafety = scanHostileArtifactBytes(hostile.bytes, [
          args.qaEmail,
          args.secondQaEmail,
          env.VIVENTIUM_QA_OWNER_EMAIL,
          ownerId,
          secondary.ownerId,
          env.JWT_SECRET,
          env.JWT_REFRESH_SECRET,
        ]);
        return {
          caseId: args.caseId,
          scenarioId: CASE_CONTRACTS[args.caseId].scenarioId,
          observed: true,
          ownerMatrix: { ownerId, otherOwnerId: secondary.ownerId, operations },
          rejections,
          hostileArtifact: {
            bytes: hostile.bytes,
            sandboxed: sandbox === "",
            hostAuthority,
            scriptExecuted: hostAuthority,
            visible: hostile.visible,
          },
          workerIsolation,
          publicSafety,
          surfaces: await visibleScenarioSurfaces("isolation"),
          runtimeRows,
          callbacks,
          traces,
          artifacts,
        };
      },

      async verifyTelegramRevision({ quickTurn }) {
        if (!args.telegramManifest || !args.telegramEvidenceRoot) return null;
        const verifier = path.join(
          REPO_ROOT,
          "qa",
          "telegram-runtime",
          "scripts",
          "tr026_installed_journey_semantic_verifier.py",
        );
        const checked = spawnSync(
          "python3",
          [
            verifier,
            "--manifest",
            args.telegramManifest,
            "--evidence-root",
            args.telegramEvidenceRoot,
          ],
          { encoding: "utf8", timeout: 30000, maxBuffer: 1024 * 1024 },
        );
        if (checked.status !== 0) return null;
        let result;
        let manifest;
        try {
          result = JSON.parse(checked.stdout);
          manifest = JSON.parse(fs.readFileSync(args.telegramManifest, "utf8"));
        } catch {
          return null;
        }
        return deriveTelegramProof({
          result,
          manifest,
          evidenceRoot: args.telegramEvidenceRoot,
          identity,
          logicalTurnHash: quickTurn.logicalTurnHash,
        });
      },

      async close() {
        for (const extra of state.contexts) {
          await extra.close().catch(() => {});
        }
        if (browser) await browser.close().catch(() => {});
        if (store) store.close();
        let cleanupFailure = null;
        for (const session of temporarySessions) {
          await session.cleanup().catch((error) => {
            cleanupFailure = error;
          });
        }
        await mongo.close().catch(() => {});
        if (cleanupFailure)
          throw blockedError("ephemeral_browser_session_cleanup_failed");
      },
    };
    return driver;
  } catch (error) {
    if (browser) await browser.close().catch(() => {});
    if (store) store.close();
    for (const session of temporarySessions) {
      await session.cleanup().catch(() => {});
    }
    await mongo.close().catch(() => {});
    if (error?.blocked) throw error;
    throw blockedError("installed_browser_or_account_prerequisite_unavailable");
  }
}

async function executeInstalledJourney({ driver, args, identity, ownerId }) {
  const caseId = String(args.caseId || CASE_ID);
  const evidence = {
    caseId,
    identity,
    maxQuickLatencyMs: args.maxQuickLatencyMs,
  };
  try {
    await driver.login();
    if (caseId !== CASE_ID) {
      const methods = {
        "PWK-UC-015": "runRestartContinuityJourney",
        "PWK-UC-016": "runCapacityProviderRecoveryJourney",
        "PWK-UC-017": "runCallbackArtifactRecoveryJourney",
        "PWK-UC-018": "runOwnerArtifactIsolationJourney",
      };
      const method = methods[caseId];
      if (!method || typeof driver[method] !== "function") {
        throw blockedError("case_specific_live_trigger_unavailable");
      }
      const observation = await driver[method]({ args, identity, ownerId });
      if (!observation || observation.caseId !== caseId) {
        throw blockedError("case_specific_live_observation_unavailable");
      }
      const {
        runtimeRows,
        quickTurn,
        actions,
        callbacks,
        artifacts,
        traces,
        ...scenario
      } = observation;
      Object.assign(evidence, {
        scenario,
        runtimeRows,
        quickTurn,
        actions,
        callbacks,
        artifacts,
        traces,
      });
      return { ...evaluateJourneyEvidence(evidence, ownerId), evidence };
    }
    evidence.feelings = await driver.submitAndObserve(
      "feelings",
      "How are you feeling?",
    );
    evidence.routeFacts = await driver.submitAndObserve(
      "route",
      "Which channel, front-end, provider, model, and reasoning effort are you using?",
    );
    const launch = await driver.submitParallelRequest(
      "Please create two simple distinct HTML deliveries in parallel: a dark vitals card and a " +
        "light ledger. Open each in a separate browser window, and keep yourself free to chat with me here.",
    );
    evidence.runningRows = await driver.waitForConcurrentWorkers(launch);
    evidence.quickTurn = await driver.submitAndObserve(
      "quick",
      "Reply with only MAIN_AVAILABLE.",
    );
    evidence.actions = await driver.steerFirstWorker(
      "Add the visible text STEERED-A to the first HTML artifact only. Do not alter the sibling mission.",
      launch,
    );
    evidence.runtimeRows = await driver.waitForTerminalWorkers(launch);
    evidence.callbacks = await driver.collectCallbacks(
      evidence.runtimeRows,
      launch,
    );
    evidence.traces = await driver.collectTraces(evidence.runtimeRows, launch);
    evidence.artifacts = await driver.openArtifactWindows(
      evidence.runtimeRows,
      launch,
    );
    evidence.telegram = await driver.verifyTelegramRevision({
      launch,
      quickTurn: evidence.quickTurn,
      runtimeRows: evidence.runtimeRows,
    });
    const result = evaluateJourneyEvidence(evidence, ownerId);
    return { ...result, evidence };
  } catch (error) {
    return {
      caseId,
      status: error?.blocked ? "BLOCKED" : "FAIL",
      pass: false,
      blockers: [
        error?.blocked ? error.message : "installed_journey_execution_failed",
      ],
      evidence,
    };
  } finally {
    await driver.close();
  }
}

async function runLive(args, environment = process.env) {
  if (environment.VIVENTIUM_QA_ALLOW_INSTALLED_PARALLEL_WORK !== "1") {
    throw blockedError("installed_parallel_work_requires_explicit_opt_in");
  }
  const runtimeEnv = loadReadOnlyRuntimeEnv(args, environment);
  assertLiveSafety(args, runtimeEnv);
  const identity = measureInstalledCandidate(args);
  args.outputDir = preparePrivateEvidenceRoot(args.outputDir, {
    repoRoot: REPO_ROOT,
  });
  args.coreLogWindow = args.coreLogPath
    ? captureCoreLogWindow(args.coreLogPath)
    : null;
  const driver = await createInstalledBrowserDriver({
    args,
    env: runtimeEnv,
    identity,
  });
  const result = await executeInstalledJourney({
    driver,
    args,
    identity,
    ownerId: driver.ownerId,
  });
  const evidence = result.evidence || { identity };
  const privateCopy = {
    ...evidence,
    artifacts: (evidence.artifacts || []).map(({ bytes, ...artifact }) => ({
      ...artifact,
      byteLength: bytes.length,
    })),
  };
  writePrivateEvidence(args.outputDir, "journey-evidence.json", {
    qaRunId: args.qaRunId,
    result: {
      status: result.status,
      pass: result.pass,
      blockers: result.blockers,
    },
    evidence: privateCopy,
  });
  return buildPublicSummary({ result, evidence, qaRunId: args.qaRunId });
}

async function main() {
  const args = parseArgs();
  if (args.mode === "dry-run") {
    process.stdout.write(`${JSON.stringify(dryRunPlan(args))}\n`);
    return;
  }
  const result = await runLive(args);
  process.stdout.write(`${JSON.stringify(result)}\n`);
  if (result.status !== "PASS")
    process.exitCode = result.status === "PARTIAL" ? 3 : 2;
}

if (require.main === module) {
  main().catch((error) => {
    const code = String(
      error?.blocked ? error.message : "installed_journey_execution_failed",
    )
      .replace(/[^a-z0-9_:.-]/gi, "_")
      .slice(0, 120);
    const requestedCase = process.argv.find((value) =>
      value.startsWith("--case="),
    );
    const caseId = requestedCase
      ? requestedCase.slice("--case=".length)
      : CASE_ID;
    process.stderr.write(
      `${JSON.stringify({ caseId, status: "BLOCKED", error: code })}\n`,
    );
    process.exitCode = 2;
  });
}

module.exports = {
  CASE_CONTRACTS,
  CASE_FAULT_BOUNDARIES,
  parseArgs,
  dryRunPlan,
  assertLiveSafety,
  assertScenarioSafety,
  assertEphemeralSessionSafety,
  assertRestartReadiness,
  assertAuthenticatedRestartStatus,
  assertSelectedQaAccount,
  createEphemeralBrowserSession,
  assertLoopbackUrl,
  preparePrivateEvidenceRoot,
  writePrivateEvidence,
  assertMeasuredCandidate,
  assertDiagnosticCandidate,
  assessRuntimeOverlap,
  isExactQuickMainAnswer,
  captureCoreLogWindow,
  readQuickTurnTimingTimeline,
  winningNativeReceipt,
  assessMainResponsiveness,
  runtimePrerequisiteBlocker,
  assessSteerIsolation,
  assessTerminalDeliveries,
  assessArtifacts,
  assessRestartContinuity,
  assessCapacityProviderRecovery,
  assessCallbackArtifactRecovery,
  assessOwnerArtifactIsolation,
  evaluateJourneyEvidence,
  buildPublicSummary,
  openReadOnlyGlassHiveStore,
  readScopedRuntimeEvidence,
  readExactFixtureRuntimeEvidence,
  readWorkerIsolationEvidence,
  verifyTraceRows,
  deriveTelegramProof,
  nestedScopeHash,
  fixtureOwnerScopeAttestation,
  createFixtureOwnerScope,
  invokeLocalQaControl,
  withGlassHiveFaultFixture,
  readConsumedFaultObservation,
  deriveMeasuredCapacityShortage,
  deriveQueueTimeoutTransitions,
  deriveAtomicReservationAttempts,
  scanHostileArtifactBytes,
  artifactRelativePath,
  signScopedCallbackPayload,
  executeInstalledJourney,
  blockedError,
};
