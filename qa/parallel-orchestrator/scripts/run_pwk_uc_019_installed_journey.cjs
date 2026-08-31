#!/usr/bin/env node
"use strict";

/*
 * Deliberately opt-in installed PWK-UC-019 acceptance. Surface observations,
 * provider authority, capability grants, and lifecycle facts must originate
 * from the current owner-scoped installation. Fixture tests never contact it.
 */

const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const {
  blockedError,
  createEphemeralBrowserSession,
  assertEphemeralSessionSafety,
  assertSelectedQaAccount,
  assertLoopbackUrl,
  assertMeasuredCandidate,
  assertDiagnosticCandidate,
  preparePrivateEvidenceRoot,
  writePrivateEvidence,
  openReadOnlyGlassHiveStore,
  readScopedRuntimeEvidence,
  assessRuntimeOverlap,
  assessMainResponsiveness,
  assessSteerIsolation,
  assessTerminalDeliveries,
  assessArtifacts,
  assertRestartReadiness,
} = require("./run_installed_parallel_work_journey.cjs");
const {
  SKY_ACTION_METHODS,
  authenticateParentComputerAuthority,
  assertTrustedComputerAdapter,
  observeTrustedComputer,
  verifyExternalComputerProof,
} = require("../../telegram-document-attachments/scripts/run_tgdoc_010_installed_journey.cjs");

const CASE_ID = "PWK-UC-019";
const RELEASE_LABEL = "PRE-GATE / NOT READY";
const ROOT = path.resolve(__dirname, "../../..");
const LIBRECHAT_ROOT = path.join(ROOT, "viventium_v0_4", "LibreChat");
const SEMANTIC_VERIFIER = path.join(__dirname, "installed_journey_qa.py");
const PRIVATE_DIRECTORY_MODE = 0o700;
const PRIVATE_FILE_MODE = 0o600;
const MAX_SCENARIO_BYTES = 512 * 1024;
const MAX_FIXTURE_BYTES = 32 * 1024 * 1024;
const SHA256 = /^[a-f0-9]{64}$/;
const PREFIXED_SHA256 = /^sha256:[a-f0-9]{64}$/;
const SAFE_CODE = /^[a-z][a-z0-9_:.-]{0,119}$/;
const REQUIRED_CAPABILITIES = Object.freeze([
  "saved_memory",
  "conversation_recall",
  "files",
  "media",
  "broker_tool",
  "browser",
  "computer",
  "connected_account",
]);
const REQUIRED_CHECKS = Object.freeze([
  "installed-identity",
  "audible-call",
  "linked-chat",
  "active-work-ui",
  "telegram-attachment-ingress",
  "exact-input-hashes-and-order",
  "memory-and-recall",
  "connected-or-broker-tool",
  "two-distinct-missions",
  "main-responsive-quick-turn",
  "spoken-steer-a-only",
  "hangup-and-reconnect",
  "callback-delivery-once",
  "two-distinct-artifacts",
  "two-headed-browser-windows",
  "passive-wing-denial",
  "listen-only-denial",
  "redacted-end-to-end-trace",
  "request-pinned-feelings-parity",
  "native-provider-receipts",
  "configured-provider-fallback-truth",
  "authorized-browser-computer-parity",
  "owner-scoped-connected-account-permissions",
  "queue-message-worker-reuse",
  "synthetic-owner-zero-residue",
]);
const SEMANTIC_REQUIRED_CHECKS = REQUIRED_CHECKS;
const NATIVE_PRODUCERS = Object.freeze([
  "core.native_receipt",
  "glasshive.native_provider_receipt",
]);
const MAX_NATIVE_ATTESTATION_MS = 10 * 60 * 1000;
const POST_CLEANUP_RECEIPT_AUTHORITY = Symbol("pwk019.post_cleanup_receipt");
const DESKTOP_ACTIONS = new Set([
  "telegram.send_grouped_attachments",
  "telegram.observe_delivered_artifact",
  "voice.observe_call",
  "voice.observe_playback",
]);
const CLEANUP_COLLECTIONS = Object.freeze([
  { name: "messages", ownerField: "user", ownerType: "string" },
  { name: "conversations", ownerField: "user", ownerType: "string" },
  { name: "files", ownerField: "user", ownerType: "object" },
  { name: "memoryentries", ownerField: "userId", ownerType: "object" },
  { name: "sessions", ownerField: "user", ownerType: "object" },
  { name: "viventiumcallsessions", ownerField: "userId", ownerType: "string" },
  { name: "viventiumvoicetasks", ownerField: "userId", ownerType: "string" },
  {
    name: "viventium_external_work",
    ownerField: "ownerId",
    ownerType: "string",
  },
  {
    name: "viventium_glasshive_callback_bindings",
    ownerField: "ownerId",
    ownerType: "string",
  },
  {
    name: "viventium_glasshive_mission_evidence",
    ownerField: "ownerId",
    ownerType: "string",
  },
  {
    name: "viventium_glasshive_capability_authorizations",
    ownerField: "ownerId",
    ownerType: "string",
  },
  {
    name: "viventium_glasshive_callback_results",
    ownerField: "ownerId",
    ownerType: "string",
  },
  {
    name: "viventiumglasshivecallbackdeliveries",
    ownerField: "userId",
    ownerType: "string",
  },
  {
    name: "viventium_scheduler_dispatch_intents",
    ownerField: "userId",
    ownerType: "string",
  },
  {
    name: "viventiumglasshivecallbackeffectoutboxes",
    ownerField: "ownerId",
    ownerType: "string",
  },
  {
    name: "viventiumorchestrationtraceevents",
    ownerField: "ownerScopeHash",
    ownerType: "hash",
  },
]);
const CALL_CHILD_COLLECTIONS = Object.freeze([
  "viventiumvoicespeakersegments",
  "viventiumvoiceingressevents",
]);
const SEMANTIC_PRODUCERS = Object.freeze({
  installed_identity: "runtime.installed_identity",
  telegram_observation: "telegram.desktop_capture",
  attachment_hash: "telegram.upload_ledger",
  browser_observation: "browser.headed_capture",
  voice_transcript: "voice.call_transcript",
  denial_receipt: "voice.surface_authority",
  native_receipt: "core.native_receipt",
  delivery_ledger: "core.delivery_ledger",
  trace_export: "core.origin_trace",
  glasshive_rows: "glasshive.lifecycle_rows",
  isolation_probe: "glasshive.worker_isolation",
  artifact_hash: "glasshive.artifact_ledger",
  capability_ledger: "glasshive.capability_audit",
  cleanup_receipt: "runner.synthetic_cleanup",
});
const SEMANTIC_SURFACES = Object.freeze({
  installed_identity: "runtime",
  voice_recording: "voice",
  voice_transcript: "voice",
  telegram_screenshot: "telegram",
  telegram_observation: "telegram",
  attachment_hash: "telegram",
  attachment_bytes: "telegram",
  browser_screenshot: "web",
  browser_observation: "web",
  denial_receipt: "voice",
  native_receipt: "core",
  delivery_ledger: "core",
  trace_export: "core",
  glasshive_rows: "glasshive",
  isolation_probe: "glasshive",
  artifact_hash: "glasshive",
  artifact_bytes: "glasshive",
  capability_ledger: "glasshive",
  cleanup_receipt: "runtime",
});
const SEMANTIC_MINIMUMS = Object.freeze({
  installed_identity: 1,
  voice_recording: 1,
  voice_transcript: 1,
  telegram_screenshot: 1,
  telegram_observation: 1,
  browser_screenshot: 3,
  browser_observation: 3,
  attachment_hash: 1,
  attachment_bytes: 2,
  capability_ledger: 6,
  native_receipt: 1,
  glasshive_rows: 1,
  delivery_ledger: 1,
  artifact_hash: 2,
  artifact_bytes: 2,
  isolation_probe: 1,
  denial_receipt: 2,
  trace_export: 1,
  cleanup_receipt: 1,
});

function digest(value) {
  return crypto.createHash("sha256").update(value).digest("hex");
}

function canonicalJson(value) {
  if (Array.isArray(value)) {
    return "[" + value.map(canonicalJson).join(",") + "]";
  }
  if (value && typeof value === "object") {
    return (
      "{" +
      Object.keys(value)
        .sort()
        .map((key) => JSON.stringify(key) + ":" + canonicalJson(value[key]))
        .join(",") +
      "}"
    );
  }
  return JSON.stringify(value);
}

function exactKeys(value, expected) {
  return (
    object(value) &&
    Object.keys(value).sort().join("\0") === [...expected].sort().join("\0")
  );
}

function publicKeyIdentity(authority, expectedProducer) {
  if (
    !object(authority) ||
    authority.producer !== expectedProducer ||
    !(authority.publicKey instanceof crypto.KeyObject) ||
    authority.publicKey.type !== "public" ||
    authority.publicKey.asymmetricKeyType !== "ed25519"
  ) {
    throw blockedError("native_producer_authority_unavailable");
  }
  const publicKeySpki = authority.publicKey.export({
    type: "spki",
    format: "der",
  });
  const keyId = digest(publicKeySpki);
  if (authority.keyId !== keyId) {
    throw blockedError("native_producer_authority_identity_mismatch");
  }
  return { keyId, publicKeySpki };
}

function nativeProducerBinding(receipt, authority, issuedAtMs, expiresAtMs) {
  if (!new Set(["main", "worker"]).has(receipt?.actor)) {
    throw blockedError("native_producer_attestation_binding_mismatch");
  }
  const producer =
    receipt?.actor === "main"
      ? "core.native_receipt"
      : "glasshive.native_provider_receipt";
  const identity = publicKeyIdentity(authority, producer);
  return {
    contractVersion: 1,
    producer,
    keyId: identity.keyId,
    actor: receipt?.actor,
    ownerRefHash: digest(String(receipt?.ownerId || "")),
    surface: receipt?.surface,
    workRefHash:
      receipt?.actor === "worker"
        ? digest(String(receipt?.workRef || ""))
        : null,
    runRefHash:
      receipt?.actor === "worker"
        ? digest(String(receipt?.runRef || ""))
        : null,
    snapshotHash: receipt?.snapshotHash,
    nativeRequestSha256: receipt?.nativeRequestSha256,
    providerAttemptRefHash: digest(String(receipt?.providerAttemptRef || "")),
    providerRefHash: digest(String(receipt?.provider || "")),
    modelRefHash: digest(String(receipt?.model || "")),
    capsuleOccurrenceCount: receipt?.capsuleOccurrenceCount,
    issuedAtMs,
    expiresAtMs,
  };
}

function verifyNativeProducerAttestation(
  receipt,
  attestation,
  authority,
  nowMs = Date.now(),
) {
  const fields = [
    "contractVersion",
    "producer",
    "keyId",
    "actor",
    "ownerRefHash",
    "surface",
    "workRefHash",
    "runRefHash",
    "snapshotHash",
    "nativeRequestSha256",
    "providerAttemptRefHash",
    "providerRefHash",
    "modelRefHash",
    "capsuleOccurrenceCount",
    "issuedAtMs",
    "expiresAtMs",
    "proof",
  ];
  if (!exactKeys(attestation, fields)) {
    throw blockedError("native_producer_attestation_unavailable");
  }
  const expected = nativeProducerBinding(
    receipt,
    authority,
    attestation.issuedAtMs,
    attestation.expiresAtMs,
  );
  const { proof, ...unsigned } = attestation;
  if (canonicalJson(unsigned) !== canonicalJson(expected)) {
    throw blockedError("native_producer_attestation_binding_mismatch");
  }
  if (
    !Number.isSafeInteger(attestation.issuedAtMs) ||
    !Number.isSafeInteger(attestation.expiresAtMs) ||
    attestation.issuedAtMs > nowMs + 1000 ||
    attestation.expiresAtMs <= nowMs ||
    attestation.expiresAtMs - attestation.issuedAtMs > MAX_NATIVE_ATTESTATION_MS
  ) {
    throw blockedError("native_producer_attestation_expired");
  }
  if (!verifyExternalComputerProof(authority.publicKey, unsigned, proof)) {
    throw blockedError("native_producer_attestation_authentication_failed");
  }
  return Object.freeze({ ...unsigned, proof });
}

function assertParentLaunchInjection(injection, context) {
  if (
    !object(injection) ||
    !object(injection.launchGrant) ||
    !object(injection.nativeProducerAuthorities)
  ) {
    throw blockedError("installed_parent_launch_injection_owner_unavailable");
  }
  const expectedAuthorityKeys = [...NATIVE_PRODUCERS];
  if (
    Object.keys(injection.nativeProducerAuthorities).sort().join("\0") !==
    expectedAuthorityKeys.sort().join("\0")
  ) {
    throw blockedError("installed_parent_launch_injection_owner_unavailable");
  }
  const producerKeys = {};
  const authorities = {};
  for (const producer of NATIVE_PRODUCERS) {
    const identity = publicKeyIdentity(
      injection.nativeProducerAuthorities[producer],
      producer,
    );
    producerKeys[producer] = identity.keyId;
    authorities[producer] = Object.freeze({
      producer,
      keyId: identity.keyId,
      publicKey: injection.nativeProducerAuthorities[producer].publicKey,
    });
  }
  const grantFields = [
    "contractVersion",
    "caseId",
    "ownerRefHash",
    "qaRunRefHash",
    "candidateDigest",
    "artifactDigest",
    "desktopAuthorityKeyId",
    "desktopSessionRefHash",
    "nativeProducerKeyIds",
    "issuedAtMs",
    "expiresAtMs",
    "proof",
  ];
  const grant = injection.launchGrant;
  const nowMs = Number.isSafeInteger(context?.nowMs)
    ? context.nowMs
    : Date.now();
  const { proof, ...unsigned } = grant;
  let desktopKeyId = "";
  try {
    const desktopKey = context?.desktopAuthority?.publicKey;
    if (
      !(desktopKey instanceof crypto.KeyObject) ||
      desktopKey.type !== "public" ||
      desktopKey.asymmetricKeyType !== "ed25519"
    ) {
      throw new Error("invalid desktop key");
    }
    desktopKeyId = digest(desktopKey.export({ type: "spki", format: "der" }));
  } catch {
    throw blockedError(
      "installed_parent_launch_injection_authentication_failed",
    );
  }
  if (
    !exactKeys(grant, grantFields) ||
    !exactKeys(grant.nativeProducerKeyIds, NATIVE_PRODUCERS) ||
    grant.contractVersion !== 1 ||
    grant.caseId !== CASE_ID ||
    grant.ownerRefHash !==
      digest(String(context?.scenario?.owner?.ownerId || "")) ||
    grant.qaRunRefHash !== digest(String(context?.args?.qaRunId || "")) ||
    grant.candidateDigest !== context?.identity?.candidateDigest ||
    grant.artifactDigest !== context?.identity?.artifactDigest ||
    grant.desktopAuthorityKeyId !== context?.desktopAuthority?.keyId ||
    grant.desktopAuthorityKeyId !== desktopKeyId ||
    grant.desktopSessionRefHash !==
      digest(String(context?.desktopAuthority?.sessionRef || "")) ||
    canonicalJson(grant.nativeProducerKeyIds) !== canonicalJson(producerKeys) ||
    !Number.isSafeInteger(grant.issuedAtMs) ||
    !Number.isSafeInteger(grant.expiresAtMs) ||
    grant.issuedAtMs > nowMs + 1000 ||
    grant.expiresAtMs <= nowMs ||
    grant.expiresAtMs - grant.issuedAtMs > MAX_NATIVE_ATTESTATION_MS ||
    !verifyExternalComputerProof(
      context?.desktopAuthority?.publicKey,
      unsigned,
      proof,
    )
  ) {
    throw blockedError(
      "installed_parent_launch_injection_authentication_failed",
    );
  }
  return Object.freeze({
    grant: Object.freeze({ ...unsigned, proof }),
    nativeProducerAuthorities: Object.freeze(authorities),
  });
}

function scopeHash(kind, value) {
  return "sha256:" + digest(String(kind) + "\0" + String(value));
}

function object(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function text(value) {
  return typeof value === "string" ? value.trim() : "";
}

function safeCode(value) {
  const candidate = text(value);
  return SAFE_CODE.test(candidate)
    ? candidate
    : "installed_worker_parity_blocked";
}

function parseArguments(argv = process.argv.slice(2)) {
  let mode = "";
  const supplied = new Map();
  for (const entry of argv) {
    if (entry === "--dry-run" || entry === "--live") {
      if (mode) throw blockedError("conflicting_execution_modes");
      mode = entry.slice(2);
      continue;
    }
    if (entry === "--allow-restart") {
      if (supplied.has("allow-restart"))
        throw blockedError("duplicate_argument");
      supplied.set("allow-restart", "true");
      continue;
    }
    if (!entry.startsWith("--") || !entry.includes("=")) {
      throw blockedError("unknown_argument");
    }
    const boundary = entry.indexOf("=");
    const key = entry.slice(2, boundary);
    if (supplied.has(key)) throw blockedError("duplicate_argument");
    supplied.set(key, entry.slice(boundary + 1));
  }
  if (!mode) throw blockedError("explicit_execution_mode_required");
  if (mode === "dry-run") {
    if (supplied.size !== 0)
      throw blockedError("dry_run_rejects_live_arguments");
    return { mode, caseId: CASE_ID, headless: false };
  }
  const allowed = new Set([
    "scenario",
    "output",
    "timeout-ms",
    "max-quick-latency-ms",
    "candidate-mode",
    "allow-restart",
  ]);
  if ([...supplied.keys()].some((key) => !allowed.has(key))) {
    throw blockedError("unknown_argument");
  }
  for (const required of ["scenario", "output"]) {
    if (!text(supplied.get(required))) {
      throw blockedError("missing_required_argument:" + required);
    }
  }
  const timeoutMs = Number(supplied.get("timeout-ms") || 180000);
  const maxQuickLatencyMs = Number(
    supplied.get("max-quick-latency-ms") || 10000,
  );
  if (
    !Number.isSafeInteger(timeoutMs) ||
    timeoutMs < 10000 ||
    timeoutMs > 900000
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
  const candidateMode = text(supplied.get("candidate-mode") || "strict");
  if (!new Set(["strict", "diagnostic"]).has(candidateMode)) {
    throw blockedError("candidate_mode_invalid");
  }
  return {
    mode,
    caseId: CASE_ID,
    scenarioPath: path.resolve(supplied.get("scenario")),
    outputDir: path.resolve(supplied.get("output")),
    candidateMode,
    timeoutMs,
    maxQuickLatencyMs,
    allowRestart: supplied.get("allow-restart") === "true",
    headless: false,
    qaRunId: CASE_ID + "-" + crypto.randomUUID(),
  };
}

function dryRunPlan(args) {
  if (args?.mode !== "dry-run") throw blockedError("dry_run_required");
  return {
    caseId: CASE_ID,
    status: "DRY_RUN",
    sideEffects: false,
    launchesBrowser: false,
    invokesModels: false,
    releaseReady: false,
    receiptEligible: false,
    releaseLabel: RELEASE_LABEL,
    requiredChecks: [...REQUIRED_CHECKS],
    restart: "explicit separate opt-in only",
    desktopProvider: "@oai/sky",
  };
}

function assertLiveOptIn(args, environment) {
  if (
    args?.mode !== "live" ||
    environment?.VIVENTIUM_QA_ALLOW_PWK_UC_019 !== "1"
  ) {
    throw blockedError("installed_worker_parity_requires_explicit_opt_in");
  }
  if (environment.VIVENTIUM_QA_ALLOW_SYNTHETIC_FIXTURES !== "1") {
    throw blockedError("synthetic_fixture_consent_required");
  }
  if (environment.CI || environment.NODE_ENV === "production") {
    throw blockedError("local_installed_qa_only");
  }
  if (args.headless !== false) throw blockedError("headed_browser_required");
  const owner = text(environment.VIVENTIUM_QA_OWNER_EMAIL).toLowerCase();
  if (!owner) throw blockedError("owner_identity_guard_required");
  const email = text(args.qaEmail).toLowerCase();
  if (email === owner) throw blockedError("personal_owner_account_refused");
  const parts = email.split("@");
  if (
    parts.length !== 2 ||
    !parts[0] ||
    !new Set(["example.com", "viventium.local", "localhost"]).has(parts[1])
  ) {
    throw blockedError("synthetic_qa_account_required");
  }
  if (environment.VIVENTIUM_QA_ALLOW_LOCAL_JWT !== "1") {
    throw blockedError("ephemeral_browser_session_requires_explicit_opt_in");
  }
  assertEphemeralSessionSafety(args, environment);
  assertLoopbackUrl(args.clientBase, "client");
  assertLoopbackUrl(args.apiBase, "api");
  assertLoopbackUrl(args.playgroundBase, "playground");
  if (
    args.candidateMode === "diagnostic" &&
    environment.VIVENTIUM_QA_ALLOW_DIAGNOSTIC_CANDIDATE !== "1"
  ) {
    throw blockedError("diagnostic_candidate_requires_explicit_opt_in");
  }
  if (
    args.allowRestart &&
    environment.VIVENTIUM_QA_ALLOW_COORDINATED_RESTART !== "1"
  ) {
    throw blockedError("coordinated_restart_requires_explicit_permission");
  }
}

function assertSignedDesktopAdapter(driver, owner, environment, options = {}) {
  if (environment?.VIVENTIUM_QA_ALLOW_PWK_UC_019_COMPUTER !== "1") {
    throw blockedError("computer_desktop_adapter_opt_in_required");
  }
  if (typeof options.processProbe === "function") {
    throw blockedError("computer_desktop_external_authority_required");
  }
  if (
    !object(owner) ||
    !text(owner.ownerId) ||
    !text(String(owner.telegramUserId || "")) ||
    !text(String(owner.telegramChatId || "")) ||
    !text(owner.accountLabel) ||
    !text(owner.chatLabel)
  ) {
    throw blockedError("computer_desktop_owner_binding_invalid");
  }
  return assertTrustedComputerAdapter(driver, owner, options.authority, {
    caseId: CASE_ID,
    appBundleId: owner.appBundleId || "ru.keepcoder.Telegram",
    environment,
    ...(Number.isSafeInteger(options.nowMs) ? { nowMs: options.nowMs } : {}),
  });
}

function assertProductionDesktopAuthority(authority) {
  if (authority?.unitTestHarness || authority?.transport?.unitTestHarness) {
    throw blockedError("computer_desktop_test_authority_forbidden");
  }
}

async function observeSignedDesktop(bridge, request) {
  if (!object(bridge) || !object(request)) {
    throw blockedError("computer_desktop_observation_unavailable");
  }
  if (request.method === "get_app_state") {
    return observeTrustedComputer(bridge, { kind: "state" });
  }
  if (
    !SKY_ACTION_METHODS.includes(request.method) ||
    !DESKTOP_ACTIONS.has(text(request.action))
  ) {
    throw blockedError("computer_desktop_action_unsupported");
  }
  const { method, action, ...payload } = request;
  return observeTrustedComputer(bridge, {
    kind: "action",
    skyMethod: method,
    logicalAction: action,
    payload,
  });
}

function assessFeelingsParity(receipts, rows, ownerId, producerAuthorities) {
  if (!Array.isArray(receipts) || receipts.length !== 3) {
    throw blockedError("three_native_provider_receipts_required");
  }
  const main = receipts.filter((receipt) => receipt?.actor === "main");
  const workers = receipts.filter((receipt) => receipt?.actor === "worker");
  if (main.length !== 1 || workers.length !== 2) {
    throw blockedError("three_native_provider_receipts_required");
  }
  const expected = new Set(rows.map((row) => row.workRef));
  const observed = new Set();
  const snapshotHashes = new Set();
  const nativeRequests = new Set();
  for (const receipt of receipts) {
    if (receipt.ownerId !== ownerId) {
      throw blockedError("native_provider_receipt_owner_mismatch");
    }
    const source =
      receipt.actor === "main"
        ? "core.native_receipt"
        : "glasshive.native_provider_receipt";
    if (
      receipt.receiptSource !== source ||
      receipt.materialized !== true ||
      !SHA256.test(String(receipt.nativeRequestSha256 || "")) ||
      !text(receipt.providerAttemptRef) ||
      !text(receipt.provider) ||
      !text(receipt.model)
    ) {
      throw blockedError("native_provider_receipt_unobserved");
    }
    if (receipt.capsuleOccurrenceCount !== 1) {
      throw blockedError("native_feelings_capsule_must_appear_once");
    }
    if (!SHA256.test(String(receipt.snapshotHash || ""))) {
      throw blockedError("request_pinned_feelings_capsule_mismatch");
    }
    if (receipt.surface !== "voice") {
      throw blockedError("native_provider_receipt_surface_mismatch");
    }
    snapshotHashes.add(receipt.snapshotHash);
    nativeRequests.add(receipt.nativeRequestSha256);
    if (receipt.actor === "worker") {
      const exact = rows.find(
        (row) =>
          row.workRef === receipt.workRef && row.runRef === receipt.runRef,
      );
      if (!exact || observed.has(receipt.workRef)) {
        throw blockedError("native_provider_receipt_worker_mismatch");
      }
      observed.add(receipt.workRef);
    }
  }
  if (snapshotHashes.size !== 1) {
    throw blockedError("request_pinned_feelings_capsule_mismatch");
  }
  if (
    nativeRequests.size !== receipts.length ||
    observed.size !== expected.size ||
    [...expected].some((workRef) => !observed.has(workRef))
  ) {
    throw blockedError("native_provider_receipt_worker_mismatch");
  }
  for (const receipt of receipts) {
    const producer = receipt.receiptSource;
    verifyNativeProducerAttestation(
      receipt,
      receipt.producerAttestation,
      producerAuthorities?.[producer],
    );
  }
  return {
    pass: true,
    receiptCount: receipts.length,
    snapshotHash: [...snapshotHashes][0],
  };
}

function assessRouteParity(routes, receipts) {
  if (
    !object(routes) ||
    routes.originSurface !== "voice" ||
    !Array.isArray(routes.configured) ||
    !routes.configured.length ||
    !Array.isArray(routes.attempts) ||
    !routes.attempts.length
  ) {
    throw blockedError("configured_provider_route_evidence_unavailable");
  }
  const key = (route) => text(route?.provider) + "\0" + text(route?.model);
  const authorized = new Set(routes.configured.map(key));
  if (
    [...authorized].some(
      (route) => route.startsWith("\0") || route.endsWith("\0"),
    )
  ) {
    throw blockedError("configured_provider_route_evidence_unavailable");
  }
  for (const receipt of receipts) {
    if (!authorized.has(key(receipt))) {
      throw blockedError("unconfigured_provider_route_refused");
    }
  }
  let fallbackObserved = false;
  for (const attempt of routes.attempts) {
    if (attempt?.observed !== true || !authorized.has(key(attempt))) {
      throw blockedError("provider_attempt_receipt_unverified");
    }
    if (attempt.fallback === true) {
      if (
        routes.configured.length < 2 ||
        key(attempt) === key(routes.configured[0])
      ) {
        throw blockedError("unauthorized_provider_fallback_refused");
      }
      fallbackObserved = true;
    }
  }
  for (const receipt of receipts) {
    const matching = routes.attempts.some(
      (attempt) => key(attempt) === key(receipt) && attempt.outcome === "used",
    );
    if (!matching) throw blockedError("provider_attempt_receipt_unverified");
  }
  return { pass: true, fallbackObserved, routeCount: authorized.size };
}

function assessCapabilityParity(manifest, receipts, rows) {
  if (
    !object(manifest) ||
    !Array.isArray(manifest.main) ||
    !Array.isArray(manifest.workers) ||
    manifest.workers.length !== rows.length ||
    !Array.isArray(receipts)
  ) {
    throw blockedError("owner_scoped_capability_manifest_unavailable");
  }
  const ownerId = rows[0]?.ownerId;
  if (manifest.ownerId !== ownerId || !text(manifest.scopeRef)) {
    throw blockedError("owner_scoped_capability_manifest_unavailable");
  }
  const main = new Map();
  for (const item of manifest.main) {
    if (
      !object(item) ||
      item.authorized !== true ||
      item.scopeRef !== manifest.scopeRef ||
      !text(item.kind) ||
      !text(item.capabilityId) ||
      main.has(item.capabilityId)
    ) {
      throw blockedError("authorized_main_capability_manifest_invalid");
    }
    main.set(item.capabilityId, item);
  }
  for (const required of REQUIRED_CAPABILITIES) {
    if (![...main.values()].some((item) => item.kind === required)) {
      throw blockedError("authorized_" + required + "_capability_unavailable");
    }
  }
  const seenWorkers = new Set();
  for (const projection of manifest.workers) {
    const matching = rows.find(
      (row) =>
        row.workRef === projection?.workRef &&
        row.runRef === projection?.runRef,
    );
    if (
      !matching ||
      projection.ownerId !== ownerId ||
      projection.scopeRef !== manifest.scopeRef ||
      seenWorkers.has(projection.workRef) ||
      !Array.isArray(projection.capabilities)
    ) {
      throw blockedError("worker_capability_owner_scope_mismatch");
    }
    seenWorkers.add(projection.workRef);
    const granted = new Set();
    for (const grant of projection.capabilities) {
      const source = main.get(grant?.capabilityId);
      if (
        !source ||
        grant.kind !== source.kind ||
        grant.authorized !== true ||
        grant.scopeRef !== manifest.scopeRef
      ) {
        throw blockedError("worker_capability_authority_exceeds_main");
      }
      if (granted.has(grant.capabilityId)) {
        throw blockedError("worker_capability_parity_incomplete");
      }
      granted.add(grant.capabilityId);
    }
    if (
      granted.size !== main.size ||
      [...main.keys()].some((id) => !granted.has(id))
    ) {
      throw blockedError("worker_capability_parity_incomplete");
    }
  }
  const approvedReceipts = [];
  for (const receipt of receipts) {
    const work = rows.find(
      (row) =>
        row.workRef === receipt?.workRef && row.runRef === receipt?.runRef,
    );
    if (
      !work ||
      receipt.ownerId !== ownerId ||
      receipt.scopeRef !== manifest.scopeRef ||
      !main.has(receipt.capabilityId) ||
      main.get(receipt.capabilityId).kind !== receipt.kind
    ) {
      throw blockedError("capability_receipt_owner_scope_mismatch");
    }
    if (
      receipt.authorized !== true ||
      !text(receipt.requestRef) ||
      !text(receipt.responseRef) ||
      !text(receipt.receiptId) ||
      !text(receipt.source)
    ) {
      throw blockedError("capability_receipt_authorization_unverified");
    }
    approvedReceipts.push(receipt);
  }
  const saved = approvedReceipts.filter(
    (receipt) =>
      receipt.kind === "saved_memory" &&
      receipt.lane === "saved_memory" &&
      receipt.source === "core.memory_audit" &&
      receipt.observed === true,
  );
  if (saved.length !== 1)
    throw blockedError("saved_memory_lane_receipt_unavailable");
  const recall = approvedReceipts.filter(
    (receipt) =>
      receipt.kind === "conversation_recall" &&
      receipt.lane === "conversation_recall" &&
      receipt.source === "core.recall_audit" &&
      receipt.observed === true,
  );
  if (recall.length !== 1) {
    throw blockedError("conversation_recall_lane_receipt_unavailable");
  }
  const chosen = approvedReceipts.filter(
    (receipt) =>
      new Set(["broker_tool", "browser", "computer"]).has(receipt.kind) &&
      receipt.source === "glasshive.capability_audit" &&
      receipt.selectedByModel === true &&
      receipt.observed === true,
  );
  if (!chosen.length)
    throw blockedError("model_selected_tool_receipt_unavailable");
  const connected = approvedReceipts.filter(
    (receipt) =>
      receipt.kind === "connected_account" &&
      receipt.source === "glasshive.capability_audit" &&
      receipt.observed === true,
  );
  if (connected.length !== 1 || !text(connected[0].permission)) {
    throw blockedError("connected_account_permission_unverified");
  }
  if (
    connected[0].permission !== "read" ||
    connected[0].effects !== "read_only" ||
    connected[0].selectedByModel !== true
  ) {
    throw blockedError("connected_account_permission_exceeded");
  }
  return {
    pass: true,
    workerCount: manifest.workers.length,
    capabilityCount: main.size,
    receiptCount: approvedReceipts.length,
  };
}

function assessAttachmentParity(attachments, rows) {
  const selected = rows[0];
  if (
    !object(attachments) ||
    attachments.ownerId !== selected?.ownerId ||
    attachments.workRef !== selected.workRef ||
    attachments.runRef !== selected.runRef ||
    attachments.source !== "telegram.desktop_capture" ||
    !text(attachments.groupRef) ||
    !Array.isArray(attachments.inputs) ||
    attachments.inputs.length < 2
  ) {
    throw blockedError("grouped_attachment_ingress_unavailable");
  }
  if (
    !Array.isArray(attachments.siblingInputIds) ||
    attachments.siblingInputIds.length !== 0
  ) {
    throw blockedError("attachment_leaked_to_sibling_worker");
  }
  const seen = new Set();
  let mediaFound = false;
  let fileFound = false;
  for (const [position, input] of attachments.inputs.entries()) {
    if (input?.position !== position) {
      throw blockedError("grouped_attachment_order_mismatch");
    }
    if (
      input.ownerId !== selected.ownerId ||
      input.workRef !== selected.workRef ||
      input.runRef !== selected.runRef ||
      input.groupRef !== attachments.groupRef
    ) {
      throw blockedError("attachment_owner_scope_mismatch");
    }
    if (!text(input.fileId) || seen.has(input.fileId)) {
      throw blockedError("grouped_attachment_file_identity_invalid");
    }
    if (
      !Buffer.isBuffer(input.bytes) ||
      input.bytes.length === 0 ||
      input.bytes.length > MAX_FIXTURE_BYTES ||
      input.sizeBytes !== input.bytes.length ||
      digest(input.bytes) !== input.byteSha256
    ) {
      throw blockedError("attachment_exact_bytes_unverified");
    }
    seen.add(input.fileId);
    mediaFound ||= new Set(["image", "audio", "video"]).has(input.kind);
    fileFound ||= new Set(["document", "file"]).has(input.kind);
  }
  if (!mediaFound || !fileFound) {
    throw blockedError("grouped_file_and_media_parity_unavailable");
  }
  return { pass: true, fileCount: attachments.inputs.length };
}

function assessControlParity(actions, rows, siblingState) {
  const ownerId = rows[0]?.ownerId;
  const isolated = assessSteerIsolation(actions, rows, ownerId);
  if (!isolated.pass) throw blockedError(isolated.reason);
  const steer = actions.find((action) => action.action === "steer");
  if (
    steer?.source !== "voice" ||
    steer.observed !== true ||
    !text(steer.receiptId)
  ) {
    throw blockedError("spoken_owner_scoped_steer_receipt_unavailable");
  }
  if (!object(siblingState) || siblingState.before !== siblingState.after) {
    throw blockedError("sibling_worker_changed_during_steer");
  }
  for (const kind of ["queue", "message"]) {
    const matches = actions.filter((action) => action?.action === kind);
    if (
      matches.length !== 1 ||
      matches[0].ownerId !== ownerId ||
      matches[0].workRef !== rows[0].workRef ||
      matches[0].workerRef !== rows[0].workerRef ||
      matches[0].status !== "accepted" ||
      matches[0].observed !== true ||
      matches[0].reused !== true ||
      !text(matches[0].receiptId)
    ) {
      throw blockedError("existing_worker_queue_message_reuse_unverified");
    }
  }
  return { pass: true, actionCount: 3 };
}

function audibleRecording(bytes) {
  if (
    !Buffer.isBuffer(bytes) ||
    bytes.length <= 46 ||
    bytes.length > MAX_FIXTURE_BYTES ||
    bytes.toString("ascii", 0, 4) !== "RIFF" ||
    bytes.toString("ascii", 8, 12) !== "WAVE" ||
    bytes.toString("ascii", 36, 40) !== "data" ||
    bytes.readUInt32LE(40) > bytes.length - 44 ||
    bytes.readUInt16LE(34) !== 16
  ) {
    return false;
  }
  const end = 44 + bytes.readUInt32LE(40);
  for (let offset = 44; offset + 1 < end; offset += 2) {
    if (Math.abs(bytes.readInt16LE(offset)) > 16) return true;
  }
  return false;
}

function assessVoiceJourney(voice, rows) {
  if (
    !object(voice) ||
    voice.ownerId !== rows[0]?.ownerId ||
    voice.mode !== "call" ||
    voice.source !== "voice.call_capture" ||
    !Array.isArray(voice.segments) ||
    !Array.isArray(voice.sessions) ||
    voice.sessions.length !== 2 ||
    voice.sessions[0] === voice.sessions[1]
  ) {
    throw blockedError("owner_scoped_voice_call_unavailable");
  }
  if (!audibleRecording(voice.recording)) {
    throw blockedError("audible_voice_recording_unavailable");
  }
  if (
    !Number.isFinite(voice.receivedAudioPackets) ||
    voice.receivedAudioPackets <= 0 ||
    !Number.isFinite(voice.receivedAudioEnergy) ||
    voice.receivedAudioEnergy <= 0
  ) {
    throw blockedError("audible_voice_playback_unobserved");
  }
  if (
    voice.segments.some(
      (segment) => !new Set(["user", "main"]).has(segment?.speaker),
    )
  ) {
    throw blockedError("main_must_be_the_only_assistant_voice");
  }
  if (
    voice.segments.some(
      (segment, index) =>
        segment?.ownerId !== voice.ownerId ||
        segment.sequence !== index + 1 ||
        segment.verified !== true ||
        !text(segment.utteranceRef),
    )
  ) {
    throw blockedError("verified_owner_voice_unavailable");
  }
  const launch = voice.segments.filter(
    (segment) => segment.action === "launch" && segment.speaker === "user",
  );
  const quick = voice.segments.filter(
    (segment) =>
      segment.action === "quick_answer" && segment.speaker === "main",
  );
  const steering = voice.segments.filter(
    (segment) => segment.action === "steer" && segment.speaker === "user",
  );
  const hangup = voice.segments.filter(
    (segment) => segment.action === "hangup",
  );
  const reconnect = voice.segments.filter(
    (segment) => segment.action === "reconnect",
  );
  const completion = voice.segments.filter(
    (segment) => segment.action === "completion" && segment.speaker === "main",
  );
  if (
    launch.length !== 2 ||
    new Set(launch.map((segment) => segment.workRef)).size !== 2 ||
    rows.some(
      (row) => !launch.some((segment) => segment.workRef === row.workRef),
    )
  ) {
    throw blockedError("voice_worker_launch_not_exactly_once");
  }
  if (
    completion.length !== 2 ||
    new Set(completion.map((segment) => segment.workRef)).size !== 2 ||
    rows.some(
      (row) => !completion.some((segment) => segment.workRef === row.workRef),
    )
  ) {
    throw blockedError("voice_worker_completion_not_exactly_once");
  }
  if (
    quick.length !== 1 ||
    steering.length !== 1 ||
    steering[0].workRef !== rows[0].workRef ||
    hangup.length !== 1 ||
    reconnect.length !== 1 ||
    Math.max(...launch.map((segment) => segment.sequence)) >=
      quick[0].sequence ||
    quick[0].sequence >= steering[0].sequence ||
    steering[0].sequence >= hangup[0].sequence ||
    hangup[0].sequence >= reconnect[0].sequence ||
    reconnect[0].sequence >=
      Math.min(...completion.map((segment) => segment.sequence))
  ) {
    throw blockedError("voice_hangup_reconnect_order_invalid");
  }
  return { pass: true, segmentCount: voice.segments.length, callCount: 2 };
}

function assessSurfaceDenials(denials, ownerId) {
  if (!Array.isArray(denials) || denials.length !== 2) {
    throw blockedError("passive_surface_denial_receipts_unavailable");
  }
  const modes = new Set();
  for (const receipt of denials) {
    if (
      !new Set(["passive_wing", "listen_only"]).has(receipt?.mode) ||
      modes.has(receipt.mode) ||
      receipt.ownerId !== ownerId ||
      receipt.source !== "voice.surface_authority" ||
      receipt.observed !== true ||
      receipt.decision !== "denied" ||
      receipt.attemptedAction !== "launch"
    ) {
      throw blockedError("passive_surface_denial_receipts_unavailable");
    }
    if (receipt.workRowsCreated !== 0 || receipt.toolCalls !== 0) {
      throw blockedError("passive_surface_created_work_or_used_tools");
    }
    modes.add(receipt.mode);
  }
  return { pass: true, denialCount: modes.size };
}

function assessArtifactParity(artifacts, rows, ownerId) {
  const result = assessArtifacts(artifacts, rows, ownerId);
  if (!result.pass) throw blockedError(result.reason);
  for (const artifact of artifacts) {
    if (
      !Array.isArray(artifact.observations) ||
      artifact.observations.length < 2 ||
      !artifact.observations.some((item) => item.surface === "web") ||
      !artifact.observations.some((item) => item.surface === "telegram") ||
      artifact.observations.some(
        (item) =>
          item.verified !== true || item.byteSha256 !== artifact.byteSha256,
      )
    ) {
      throw blockedError("cross_surface_artifact_bytes_mismatch");
    }
    if (
      !object(artifact.deliveryReceipt) ||
      artifact.deliveryReceipt.observed !== true ||
      artifact.deliveryReceipt.ownerId !== ownerId ||
      artifact.deliveryReceipt.workRef !== artifact.workRef
    ) {
      throw blockedError("artifact_delivery_receipt_unavailable");
    }
  }
  return result;
}

function containsPrivateTraceFields(value) {
  if (Array.isArray(value)) return value.some(containsPrivateTraceFields);
  if (!object(value)) return false;
  const forbidden = new Set([
    "prompt",
    "messages",
    "messageText",
    "rawPrompt",
    "capsule",
    "token",
    "accessToken",
    "refreshToken",
    "secret",
    "credentials",
    "ownerEmail",
    "privateState",
  ]);
  return Object.entries(value).some(
    ([key, item]) => forbidden.has(key) || containsPrivateTraceFields(item),
  );
}

function assessImmutableTrace(trace, rows) {
  if (
    !object(trace) ||
    trace.ownerId !== rows[0]?.ownerId ||
    !text(trace.originRef) ||
    trace.source !== "core.immutable_trace" ||
    !Array.isArray(trace.events) ||
    trace.events.length < 5 ||
    trace.events.length > 100
  ) {
    throw blockedError("owner_scoped_immutable_trace_unavailable");
  }
  if (trace.events.some((event) => containsPrivateTraceFields(event?.facts))) {
    throw blockedError("trace_contains_unredacted_private_data");
  }
  const ownerScopeHash = scopeHash("owner", trace.ownerId);
  const originRefHash = scopeHash("origin", trace.originRef);
  let previousEventHash = "sha256:" + "0".repeat(64);
  const sourceEvents = [];
  const coverage = new Map(
    rows.map((row) => [scopeHash("work", row.workRef), new Set()]),
  );
  const runtimeAt = new Map();
  const providerAt = new Map();
  for (const [index, event] of trace.events.entries()) {
    if (!object(event) || !object(event.facts)) {
      throw blockedError("immutable_trace_hash_chain_invalid");
    }
    const expectedContent =
      "sha256:" +
      digest(
        canonicalJson({
          schemaVersion: 1,
          stage: event.stage,
          facts: event.facts,
        }),
      );
    const { eventHash, ...unsigned } = event;
    const expectedEvent = "sha256:" + digest(canonicalJson(unsigned));
    if (
      event.schemaVersion !== 1 ||
      event.ownerScopeHash !== ownerScopeHash ||
      event.originRefHash !== originRefHash ||
      event.sequence !== index + 1 ||
      event.previousEventHash !== previousEventHash ||
      event.contentHash !== expectedContent ||
      eventHash !== expectedEvent ||
      !PREFIXED_SHA256.test(String(event.eventKeyHash || ""))
    ) {
      throw blockedError("immutable_trace_hash_chain_invalid");
    }
    const workHash = event.facts.workRefHash;
    if (event.stage === "source.bound") sourceEvents.push(event);
    if (workHash) {
      const work = rows.find(
        (row) => scopeHash("work", row.workRef) === workHash,
      );
      if (!work) throw blockedError("immutable_trace_cross_owner_or_worker");
      if (
        event.facts.runRefHash &&
        event.facts.runRefHash !== scopeHash("run", work.runRef)
      ) {
        throw blockedError("immutable_trace_cross_owner_or_worker");
      }
      coverage.get(workHash).add(event.stage);
      if (
        [
          "prompt.layers.verified",
          "work.admitted",
          "runtime.invoked",
          "work.completed",
        ].includes(event.stage) &&
        event.facts.producerTraceContractVersion !== 2
      ) {
        throw blockedError("immutable_trace_v2_producer_contract_unavailable");
      }
      if (
        event.stage === "prompt.layers.verified" &&
        event.facts.promptProducerScope !== "glasshive.worker_prompt_registry"
      ) {
        throw blockedError("immutable_trace_v2_producer_contract_unavailable");
      }
      if (event.stage === "runtime.invoked")
        runtimeAt.set(workHash, Date.parse(event.at));
      if (event.stage === "provider.request.forwarded") {
        if (
          event.facts.providerStatus !== "completed" ||
          !PREFIXED_SHA256.test(
            String(event.facts.providerRequestRefHash || ""),
          )
        ) {
          throw blockedError("immutable_trace_provider_forwarding_unavailable");
        }
        providerAt.set(workHash, Date.parse(event.at));
      }
    }
    previousEventHash = eventHash;
  }
  const requiredStages = [
    "prompt.layers.verified",
    "work.admitted",
    "runtime.invoked",
    "provider.request.forwarded",
    "work.completed",
    "callback.accepted",
    "callback.delivery.sent",
  ];
  if (
    sourceEvents.length !== 1 ||
    rows.some(
      (row) =>
        requiredStages.some(
          (stage) => !coverage.get(scopeHash("work", row.workRef))?.has(stage),
        ) ||
        !Number.isFinite(runtimeAt.get(scopeHash("work", row.workRef))) ||
        !Number.isFinite(providerAt.get(scopeHash("work", row.workRef))) ||
        providerAt.get(scopeHash("work", row.workRef)) <
          runtimeAt.get(scopeHash("work", row.workRef)),
    )
  ) {
    throw blockedError("immutable_trace_terminal_coverage_incomplete");
  }
  return { pass: true, eventCount: trace.events.length, traceCount: 1 };
}

function buildSemanticTraceExport(trace, rows, correlation) {
  assessImmutableTrace(trace, rows);
  const logicalTurnRefHash = text(correlation?.logicalTurnRefHash);
  const turnRevision = Number(correlation?.turnRevision);
  if (
    !SHA256.test(logicalTurnRefHash) ||
    !Number.isSafeInteger(turnRevision) ||
    turnRevision < 1
  ) {
    throw blockedError("immutable_trace_turn_binding_unavailable");
  }
  const stages = [
    ["source.bound", "source.observed"],
    ["work.admitted", "work.admitted"],
    ["runtime.invoked", "runtime.invoked"],
    ["provider.request.forwarded", "provider.request.forwarded"],
    ["callback.accepted", "callback.accepted"],
    ["callback.delivery.sent", "delivery.sent"],
  ];
  const events = [];
  let previousSha256 = "0".repeat(64);
  for (const row of rows) {
    const sourceWorkHash = scopeHash("work", row.workRef);
    const sourceRunHash = scopeHash("run", row.runRef);
    for (const [stage, eventType] of stages) {
      const source = trace.events.find(
        (event) =>
          event.stage === stage &&
          (stage === "source.bound" ||
            (event.facts?.workRefHash === sourceWorkHash &&
              event.facts?.runRefHash === sourceRunHash)),
      );
      if (!source)
        throw blockedError("immutable_trace_semantic_projection_incomplete");
      const event = {
        sequence: events.length + 1,
        eventType,
        ownerRefHash: digest(trace.ownerId),
        originSurface: "voice",
        logicalTurnRefHash,
        turnRevision,
        workRefHash: digest(row.workRef),
        runRefHash: digest(row.runRef),
        previousSha256,
      };
      event.eventSha256 = digest(canonicalJson(event));
      previousSha256 = event.eventSha256;
      events.push(event);
    }
  }
  return {
    id: "trace_export-0",
    kind: "trace_export",
    observed: true,
    producer: "core.origin_trace",
    payload: {
      contractVersion: 2,
      producerTraceContractVersion: 2,
      promptProducerScope: "glasshive.worker_prompt_registry",
      fullChainVerified: true,
      overflowCount: 0,
      eventCount: events.length,
      events,
      chainSha256: previousSha256,
    },
  };
}

function assessVisibleSurfaces(surfaces, rows, ownerId) {
  if (
    surfaces?.linkedChat?.visible !== true ||
    surfaces.linkedChat.headed !== true ||
    surfaces.linkedChat.ownerId !== ownerId
  ) {
    throw blockedError("owner_scoped_linked_chat_not_visible");
  }
  const active = surfaces.activeWork;
  if (
    active?.visible !== true ||
    active.headed !== true ||
    active.ownerId !== ownerId ||
    !Array.isArray(active.workRefs) ||
    active.workRefs.length !== rows.length ||
    rows.some((row) => !active.workRefs.includes(row.workRef))
  ) {
    throw blockedError("owner_scoped_active_work_not_visible");
  }
  if (
    surfaces.telegram?.visible !== true ||
    surfaces.telegram.signed !== true ||
    surfaces.telegram.ownerId !== ownerId ||
    surfaces.telegram.source !== "@oai/sky.get_app_state"
  ) {
    throw blockedError("signed_owner_scoped_telegram_observation_unavailable");
  }
}

function assertSemanticVerifierReceipt(observation) {
  const verifier = observation.semanticVerifier;
  if (
    !object(verifier) ||
    verifier.verified !== true ||
    verifier.caseId !== CASE_ID ||
    verifier.surface !== "voice" ||
    verifier.candidateDigest !== observation.candidate?.candidateDigest ||
    verifier.artifactDigest !== observation.candidate?.artifactDigest
  ) {
    throw blockedError("independent_semantic_verifier_receipt_unavailable");
  }
  return verifier;
}

function evaluateCapabilityJourney(observation, options = {}) {
  if (
    !object(observation) ||
    observation.caseId !== CASE_ID ||
    !text(observation.ownerId) ||
    !Array.isArray(observation.rows) ||
    observation.rows.length !== 2 ||
    !object(observation.candidate) ||
    observation.candidate.installed !== true ||
    !SHA256.test(String(observation.candidate.candidateDigest || "")) ||
    !SHA256.test(String(observation.candidate.artifactDigest || ""))
  ) {
    throw blockedError(
      "installed_owner_scoped_capability_evidence_unavailable",
    );
  }
  if (observation.cleanup?.zeroResidue !== true) {
    throw blockedError("synthetic_cleanup_receipt_unavailable");
  }
  const overlap = assessRuntimeOverlap(observation.rows, observation.ownerId);
  if (!overlap.pass) throw blockedError(overlap.reason);
  const responsiveness = assessMainResponsiveness({
    rows: observation.rows,
    quickTurn: observation.quickTurn,
    maxQuickLatencyMs: observation.maxQuickLatencyMs || 10000,
  });
  if (!responsiveness.pass) throw blockedError(responsiveness.reason);
  const feelings = assessFeelingsParity(
    observation.nativeReceipts,
    observation.rows,
    observation.ownerId,
    observation.nativeProducerAuthorities,
  );
  const routes = assessRouteParity(
    observation.routes,
    observation.nativeReceipts,
  );
  const capabilities = assessCapabilityParity(
    observation.capabilityManifest,
    observation.capabilityReceipts,
    observation.rows,
  );
  const attachments = assessAttachmentParity(
    observation.attachments,
    observation.rows,
  );
  const controls = assessControlParity(
    observation.actions,
    observation.rows,
    observation.siblingState,
  );
  const voice = assessVoiceJourney(observation.voice, observation.rows);
  const denials = assessSurfaceDenials(
    observation.denials,
    observation.ownerId,
  );
  const callbacks = assessTerminalDeliveries(
    observation.callbacks,
    observation.rows,
    observation.ownerId,
  );
  if (!callbacks.pass) throw blockedError(callbacks.reason);
  if (observation.callbacks.some((receipt) => receipt.observed !== true)) {
    throw blockedError("terminal_callback_receipt_unobserved");
  }
  const artifacts = assessArtifactParity(
    observation.artifacts,
    observation.rows,
    observation.ownerId,
  );
  assessVisibleSurfaces(
    observation.surfaces,
    observation.rows,
    observation.ownerId,
  );
  const trace = assessImmutableTrace(observation.trace, observation.rows);
  assertSemanticVerifierReceipt(observation);
  const diagnostic = options.candidateMode === "diagnostic";
  return {
    caseId: CASE_ID,
    status: diagnostic ? "PRE_GATE_COMPLETE" : "PASS",
    pass: !diagnostic,
    releaseReady: false,
    receiptEligible: !diagnostic,
    releaseLabel: RELEASE_LABEL,
    workerCount: overlap.workCount,
    overlapMs: overlap.overlapMs,
    quickResponseMs: responsiveness.latencyMs,
    nativeReceiptCount: feelings.receiptCount,
    capabilityCount: capabilities.capabilityCount,
    capabilityReceiptCount: capabilities.receiptCount,
    attachmentCount: attachments.fileCount,
    actionCount: controls.actionCount,
    voiceSegmentCount: voice.segmentCount,
    deniedSurfaceCount: denials.denialCount,
    callbackCount: callbacks.callbackCount,
    artifactCount: artifacts.artifactCount,
    windowCount: artifacts.windowCount,
    traceCount: trace.traceCount,
    fallbackObserved: routes.fallbackObserved,
    candidateDigest: observation.candidate.candidateDigest,
    artifactDigest: observation.candidate.artifactDigest,
  };
}

function buildPublicSummary({ result, observation = {}, qaRunId }) {
  const clean = {
    caseId: CASE_ID,
    status: text(result?.status) || "BLOCKED",
    pass: result?.pass === true,
    releaseReady: false,
    receiptEligible: result?.receiptEligible === true,
    releaseLabel: RELEASE_LABEL,
    qaRunId: text(qaRunId) || CASE_ID,
  };
  for (const field of [
    "workerCount",
    "overlapMs",
    "quickResponseMs",
    "nativeReceiptCount",
    "capabilityCount",
    "capabilityReceiptCount",
    "attachmentCount",
    "actionCount",
    "voiceSegmentCount",
    "deniedSurfaceCount",
    "callbackCount",
    "artifactCount",
    "windowCount",
    "traceCount",
  ]) {
    if (Number.isSafeInteger(result?.[field])) clean[field] = result[field];
  }
  for (const field of ["candidateDigest", "artifactDigest"]) {
    if (SHA256.test(String(result?.[field] || "")))
      clean[field] = result[field];
  }
  if (typeof result?.fallbackObserved === "boolean") {
    clean.fallbackObserved = result.fallbackObserved;
  }
  if (result?.blocker) clean.blocker = safeCode(result.blocker);
  if (observation?.cleanup?.zeroResidue === true) clean.zeroResidue = true;
  return clean;
}

async function cleanupSyntheticResidue(database, fixture) {
  if (
    !database ||
    typeof database.collection !== "function" ||
    !object(fixture) ||
    !text(fixture.ownerId) ||
    !Array.isArray(fixture.created)
  ) {
    throw blockedError("synthetic_cleanup_scope_invalid");
  }
  const baselineIds =
    fixture.baselineIds instanceof Set ? fixture.baselineIds : new Set();
  const allowedCollections = new Set([
    ...CLEANUP_COLLECTIONS.map((item) => item.name),
    ...CALL_CHILD_COLLECTIONS,
  ]);
  const ownedCallSessionIds =
    fixture.ownedCallSessionIds instanceof Set
      ? fixture.ownedCallSessionIds
      : new Set();
  for (const record of fixture.created) {
    if (
      !object(record) ||
      !allowedCollections.has(record.collection) ||
      !text(String(record.id || "")) ||
      !text(record.ownerField) ||
      baselineIds.has(String(record.id))
    ) {
      throw blockedError("synthetic_cleanup_scope_invalid");
    }
    const isCallChild = CALL_CHILD_COLLECTIONS.includes(record.collection);
    if (
      isCallChild &&
      (record.ownerField !== "callSessionId" ||
        !ownedCallSessionIds.has(String(record.ownerValue || "")) ||
        String(record.boundOwnerId || "") !== String(fixture.ownerId))
    ) {
      throw blockedError("synthetic_cleanup_owner_mismatch");
    }
    if (!isCallChild) {
      const expected =
        record.ownerField === "ownerScopeHash"
          ? scopeHash("owner", fixture.ownerId)
          : fixture.ownerId;
      if (String(record.ownerValue || "") !== String(expected)) {
        throw blockedError("synthetic_cleanup_owner_mismatch");
      }
    }
  }
  for (const record of [...fixture.created].reverse()) {
    const filter = { _id: record.id, [record.ownerField]: record.ownerValue };
    const result = await database
      .collection(record.collection)
      .deleteOne(filter);
    if (result?.acknowledged !== true || result.deletedCount !== 1) {
      throw blockedError("synthetic_cleanup_delete_unverified");
    }
    const remaining = await database
      .collection(record.collection)
      .countDocuments(filter);
    if (remaining !== 0)
      throw blockedError("synthetic_cleanup_residue_detected");
  }
  if (Array.isArray(fixture.residueObservers)) {
    for (const observer of fixture.residueObservers) {
      if (!observer || typeof observer.verify !== "function") {
        throw blockedError("synthetic_cleanup_residue_observer_unavailable");
      }
      const result = await observer.verify({
        ownerId: fixture.ownerId,
        created: fixture.created,
      });
      if (!object(result) || result.remaining !== 0) {
        throw blockedError("synthetic_cleanup_residue_detected");
      }
    }
  }
  return { zeroResidue: true, removed: fixture.created.length };
}

async function executeCapabilityJourney(driver, options = {}) {
  let observation;
  let failure;
  let cleanup;
  if (
    !driver ||
    typeof driver.start !== "function" ||
    typeof driver.cleanup !== "function"
  ) {
    failure = blockedError("installed_capability_driver_unavailable");
  } else {
    try {
      observation = await driver.start();
      if (object(observation?.semanticVerifier)) {
        throw blockedError("semantic_receipt_created_before_cleanup");
      }
    } catch (error) {
      failure = error;
    }
    try {
      cleanup = await driver.cleanup();
      if (!object(cleanup) || cleanup.zeroResidue !== true) {
        throw blockedError("synthetic_cleanup_residue_detected");
      }
      if (observation) observation.cleanup = cleanup;
    } catch (error) {
      failure = error?.blocked
        ? error
        : blockedError("synthetic_cleanup_residue_detected");
    }
  }
  let result;
  if (!failure && observation) {
    try {
      if (typeof driver.finalizeAfterCleanup !== "function") {
        throw blockedError("post_cleanup_semantic_verifier_unavailable");
      }
      observation = await driver.finalizeAfterCleanup(observation, cleanup);
      result = evaluateCapabilityJourney(observation, options);
    } catch (error) {
      failure = error;
    }
  }
  if (failure || !result) {
    if (observation) delete observation.semanticVerifier;
    if (driver && typeof driver.discardSemanticArtifacts === "function") {
      try {
        await driver.discardSemanticArtifacts(observation);
      } catch {
        failure = blockedError("stale_semantic_receipt_cleanup_failed");
      }
    }
    result = {
      caseId: CASE_ID,
      status: "BLOCKED",
      pass: false,
      releaseReady: false,
      receiptEligible: false,
      releaseLabel: RELEASE_LABEL,
      blocker: safeCode(
        failure?.blocked
          ? failure.message
          : "installed_capability_journey_failed",
      ),
    };
  }
  return { ...result, ...(observation ? { observation } : {}) };
}

function assertPrivateFile(location, maximum = MAX_SCENARIO_BYTES) {
  let resolved;
  let stat;
  try {
    if (fs.lstatSync(location).isSymbolicLink()) {
      throw blockedError("private_input_symlink_refused");
    }
    resolved = fs.realpathSync(location);
    stat = fs.statSync(resolved);
  } catch (error) {
    if (error?.blocked) throw error;
    throw blockedError("private_input_unavailable");
  }
  const relative = path.relative(fs.realpathSync(ROOT), resolved);
  if (
    !relative ||
    (!relative.startsWith(".." + path.sep) && relative !== "..")
  ) {
    throw blockedError("private_input_must_stay_outside_repository");
  }
  if (
    !stat.isFile() ||
    stat.size < 1 ||
    stat.size > maximum ||
    stat.mode & 0o077
  ) {
    throw blockedError("private_input_owner_permissions_required");
  }
  return resolved;
}

function readPrivateScenario(location) {
  try {
    const scenario = JSON.parse(
      fs.readFileSync(assertPrivateFile(location), "utf8"),
    );
    if (!object(scenario)) throw new Error("invalid");
    return scenario;
  } catch (error) {
    if (error?.blocked) throw error;
    throw blockedError("private_installed_scenario_invalid");
  }
}

function validateScenario(scenario, args, environment) {
  if (
    !object(scenario) ||
    scenario.contractVersion !== 1 ||
    scenario.caseId !== CASE_ID ||
    scenario.classification !== "synthetic_public_safe" ||
    !object(scenario.owner) ||
    scenario.owner.synthetic !== true ||
    !text(scenario.owner.ownerId) ||
    !text(String(scenario.owner.telegramUserId || "")) ||
    !text(String(scenario.owner.telegramChatId || "")) ||
    !object(scenario.telegram) ||
    scenario.telegram.appBundleId !== "ru.keepcoder.Telegram" ||
    !text(scenario.telegram.accountLabel) ||
    !text(scenario.telegram.chatLabel) ||
    !object(scenario.runtime) ||
    !object(scenario.voice) ||
    !Array.isArray(scenario.files) ||
    scenario.files.length < 2
  ) {
    throw blockedError("private_installed_scenario_invalid");
  }
  args.qaEmail = text(scenario.owner.email).toLowerCase();
  args.clientBase = text(scenario.runtime.clientBase);
  args.apiBase = text(scenario.runtime.apiBase);
  args.playgroundBase = text(scenario.runtime.playgroundBase);
  args.agentId = text(scenario.runtime.agentId);
  args.runtimeRoot = path.resolve(text(scenario.runtime.runtimeRoot));
  args.installedRoot = path.resolve(text(scenario.runtime.installedRoot));
  args.identityPath = path.resolve(text(scenario.runtime.identityPath));
  args.ownerStatePath = path.resolve(text(scenario.runtime.ownerStatePath));
  args.glassHiveDbPath = path.resolve(text(scenario.runtime.glassHiveDbPath));
  args.coreLogPath = text(scenario.runtime.coreLogPath)
    ? path.resolve(scenario.runtime.coreLogPath)
    : "";
  assertLiveOptIn(args, environment);
  if (!args.agentId) throw blockedError("configured_main_agent_unavailable");
  if (!text(scenario.voice.audioPath))
    throw blockedError("synthetic_voice_audio_unavailable");
  scenario.voice.audioPath = assertPrivateFile(
    scenario.voice.audioPath,
    MAX_FIXTURE_BYTES,
  );
  for (const input of scenario.files) {
    if (!object(input) || !text(input.path) || !text(input.kind)) {
      throw blockedError("synthetic_grouped_file_fixture_unavailable");
    }
    input.path = assertPrivateFile(input.path, MAX_FIXTURE_BYTES);
  }
  if (!Array.isArray(scenario.voice.turns) || scenario.voice.turns.length < 8) {
    throw blockedError("synthetic_voice_turn_fixture_unavailable");
  }
  return scenario;
}

function parseEnvironmentFile(location) {
  if (!fs.existsSync(location)) return {};
  const values = {};
  for (const raw of fs.readFileSync(location, "utf8").split(/\r?\n/)) {
    const entry = raw.trim();
    if (!entry || entry.startsWith("#")) continue;
    const separator = entry.indexOf("=");
    if (separator < 1) continue;
    const key = entry.slice(0, separator).trim();
    let value = entry.slice(separator + 1).trim();
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

function readInstalledEnvironment(args, supplied) {
  let runtimeRoot;
  try {
    runtimeRoot = fs.realpathSync(args.runtimeRoot);
  } catch {
    throw blockedError("installed_runtime_root_unavailable");
  }
  const installed = {
    ...parseEnvironmentFile(path.join(runtimeRoot, "runtime.env")),
    ...parseEnvironmentFile(path.join(runtimeRoot, "runtime.local.env")),
    ...parseEnvironmentFile(
      path.join(runtimeRoot, "service-env", "librechat.env"),
    ),
    ...parseEnvironmentFile(
      path.join(runtimeRoot, "service-env", "librechat.owner.env"),
    ),
    ...parseEnvironmentFile(
      path.join(runtimeRoot, "service-env", "glasshive.env"),
    ),
  };
  for (const field of [
    "JWT_SECRET",
    "JWT_REFRESH_SECRET",
    "VIVENTIUM_QA_EMAIL",
  ]) {
    if (
      supplied[field] &&
      installed[field] &&
      supplied[field] !== installed[field]
    ) {
      throw blockedError(
        "untrusted_runtime_signing_or_account_override_refused",
      );
    }
  }
  const merged = { ...installed, ...supplied };
  if (!text(merged.MONGO_URI))
    throw blockedError("installed_mongo_uri_unavailable");
  let database;
  try {
    database = fs.realpathSync(text(merged.WPR_DB_PATH));
    if (database !== fs.realpathSync(args.glassHiveDbPath)) {
      throw blockedError("installed_glasshive_database_identity_unproven");
    }
  } catch (error) {
    if (error?.blocked) throw error;
    throw blockedError("installed_glasshive_database_identity_unproven");
  }
  return merged;
}

function measureInstalledCandidate(args) {
  const script = path.join(
    ROOT,
    "scripts",
    "viventium",
    "parallel_work_release_gate.py",
  );
  const probe = [
    "import importlib.util,json,sys",
    "from pathlib import Path",
    "s=importlib.util.spec_from_file_location('pwk_uc_019_identity',sys.argv[1])",
    "m=importlib.util.module_from_spec(s)",
    "sys.modules[s.name]=m",
    "s.loader.exec_module(m)",
    "i=json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))",
    "r=Path(sys.argv[3])",
    "p=Path(sys.argv[4])",
    "n=Path(sys.argv[5])",
    "o=Path(sys.argv[6])",
    "d=Path(sys.argv[7])",
    "checks,_=m._artifact_identity_checks(r,i,p,n,o)",
    "candidate,artifact=m._qa_candidate_digests(i)",
    "active=m._runtime_owner_state_proves_active(n,o)",
    "owner=json.loads(o.read_text(encoding='utf-8'))",
    "measured=m._public_artifact_identity(m._measured_artifact_identity(r,p,n,o))",
    "dc=m._canonical_hash({'source':measured.get('source'),'nestedComponents':measured.get('nestedComponents'),'prebuiltHelper':measured.get('prebuiltHelper')})",
    "da=m._canonical_hash(measured.get('installed'))",
    "binding={'active':active,'ownerRootMatches':active and Path(str(owner.get('repoRoot') or '')).resolve(strict=True)==n.resolve(strict=True),'runtimeRootMatches':active and Path(str(owner.get('runtimeDir') or '')).resolve(strict=True)==d.resolve(strict=True),'ownerBindingSha256':str(owner.get('ownerBindingSha256') or ''),'processIdentitySha256':m._canonical_hash({'pid':str(owner.get('ownerPid') or ''),'startedAt':str(owner.get('ownerProcessStartedAt') or ''),'executable':str(owner.get('ownerExecutablePath') or '')}) if active else ''}",
    "print(json.dumps({'candidateDigest':candidate,'artifactDigest':artifact,'diagnosticCandidateDigest':dc,'diagnosticArtifactDigest':da,'checks':[{'id':item.check_id,'status':item.status,'reason':item.reason} for item in checks],'runtimeBinding':binding,'measuredIdentity':measured}))",
  ].join(";");
  const checked = spawnSync(
    "python3",
    [
      "-c",
      probe,
      script,
      args.identityPath,
      ROOT,
      path.join(args.runtimeRoot, "prompt-bundle.json"),
      args.installedRoot,
      args.ownerStatePath,
      args.runtimeRoot,
    ],
    { encoding: "utf8", timeout: 30000, maxBuffer: 1024 * 1024 },
  );
  if (checked.status !== 0)
    throw blockedError("installed_candidate_identity_unproven");
  try {
    const measured = JSON.parse(checked.stdout);
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

function assertResidueObservers(observers) {
  if (!object(observers)) {
    throw blockedError("synthetic_owner_cleanup_observers_unavailable");
  }
  for (const kind of [
    "search",
    "vector",
    "storage",
    "scheduler",
    "glasshive",
  ]) {
    if (
      !object(observers[kind]) ||
      typeof observers[kind].capture !== "function" ||
      typeof observers[kind].removeAndVerify !== "function" ||
      typeof observers[kind].verify !== "function"
    ) {
      throw blockedError("synthetic_" + kind + "_cleanup_observer_unavailable");
    }
  }
  return observers;
}

async function waitFor(check, timeoutMs, blocker) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const observed = await check();
    if (observed) return observed;
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw blockedError(blocker);
}

function ownerValue(entry, ownerId, ObjectId) {
  if (entry.ownerType === "hash") return scopeHash("owner", ownerId);
  if (entry.ownerType === "object") return new ObjectId(ownerId);
  return ownerId;
}

async function captureOwnerBaseline(database, ownerId, ObjectId) {
  const baseline = new Map();
  const allIds = new Set();
  for (const entry of CLEANUP_COLLECTIONS) {
    const filter = { [entry.ownerField]: ownerValue(entry, ownerId, ObjectId) };
    const rows = await database
      .collection(entry.name)
      .find(filter)
      .project({ _id: 1 })
      .limit(10001)
      .toArray();
    if (rows.length > 10000)
      throw blockedError("synthetic_owner_baseline_too_large");
    const identifiers = new Set(rows.map((row) => String(row._id)));
    baseline.set(entry.name, identifiers);
    for (const id of identifiers) allIds.add(id);
  }
  return { byCollection: baseline, ids: allIds };
}

async function discoverSyntheticResidue(database, ownerId, ObjectId, baseline) {
  const created = [];
  const ownedCallSessionIds = new Set();
  for (const entry of CLEANUP_COLLECTIONS) {
    const value = ownerValue(entry, ownerId, ObjectId);
    const rows = await database
      .collection(entry.name)
      .find({ [entry.ownerField]: value })
      .project(
        entry.name === "viventiumcallsessions"
          ? { _id: 1, callSessionId: 1 }
          : { _id: 1 },
      )
      .limit(10001)
      .toArray();
    if (rows.length > 10000)
      throw blockedError("synthetic_cleanup_scope_too_large");
    const previous = baseline.byCollection.get(entry.name) || new Set();
    for (const row of rows) {
      if (!previous.has(String(row._id))) {
        const record = {
          collection: entry.name,
          id: row._id,
          ownerField: entry.ownerField,
          ownerValue: value,
        };
        if (entry.name === "viventiumcallsessions") {
          if (!text(row.callSessionId)) {
            throw blockedError("synthetic_call_cleanup_identity_unverified");
          }
          record.callSessionId = row.callSessionId;
          ownedCallSessionIds.add(row.callSessionId);
        }
        created.push(record);
      }
    }
  }
  if (ownedCallSessionIds.size) {
    const callSessionIds = Array.from(ownedCallSessionIds);
    for (const collection of CALL_CHILD_COLLECTIONS) {
      const rows = await database
        .collection(collection)
        .find({ callSessionId: { $in: callSessionIds } })
        .project({ _id: 1, callSessionId: 1 })
        .limit(10001)
        .toArray();
      if (rows.length > 10000)
        throw blockedError("synthetic_cleanup_scope_too_large");
      for (const row of rows) {
        if (!ownedCallSessionIds.has(String(row.callSessionId || ""))) {
          throw blockedError("synthetic_cleanup_owner_mismatch");
        }
        created.push({
          collection,
          id: row._id,
          ownerField: "callSessionId",
          ownerValue: row.callSessionId,
          boundOwnerId: ownerId,
        });
      }
    }
  }
  return created;
}

function privateReceipt(location) {
  try {
    const stat = fs.lstatSync(location);
    if (
      stat.isSymbolicLink() ||
      !stat.isFile() ||
      stat.mode & 0o077 ||
      stat.size > MAX_SCENARIO_BYTES
    ) {
      throw new Error("unsafe");
    }
    const parsed = JSON.parse(fs.readFileSync(location, "utf8"));
    return object(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

function observeWorkerNativeReceipt(store, row, authentication = {}) {
  let source;
  try {
    source = store
      .prepare(
        "SELECT w.bootstrap_bundle_json AS bundle, " +
          "r.provider_route_runtime AS runtime, r.provider_route_model AS model " +
          "FROM workers w JOIN runs r ON r.worker_id = w.worker_id " +
          "WHERE w.owner_id = ? AND w.worker_id = ? AND r.run_id = ?",
      )
      .get(row.ownerId, row.workerRef, row.runRef);
  } catch {
    throw blockedError("worker_native_provider_receipt_unavailable");
  }
  if (!source || !row.workspaceRoot || !text(source.runtime)) {
    throw blockedError("worker_native_provider_receipt_unavailable");
  }
  let projection;
  try {
    projection = JSON.parse(
      String(source.bundle || "{}"),
    ).viventium_feelings_projection;
  } catch {
    projection = null;
  }
  if (
    !object(projection) ||
    projection.version !== 1 ||
    projection.enabled !== true ||
    projection.scope !== "all_agents" ||
    projection.expected_capsule_count !== 1 ||
    !SHA256.test(String(projection.snapshot_sha256 || ""))
  ) {
    throw blockedError("worker_request_pinned_feelings_projection_unavailable");
  }
  const receiptRef = digest(String(source.runtime) + "\0" + row.runRef);
  const file = path.join(
    path.dirname(row.workspaceRoot),
    "state",
    "native-provider-authority-receipts",
    receiptRef + ".json",
  );
  const receipt = privateReceipt(file);
  if (
    receipt?.protocol !== "glasshive.native_provider_authority_receipt.v1" ||
    receipt.run_id !== row.runRef ||
    receipt.runtime !== source.runtime ||
    receipt.materialized !== true ||
    receipt.feeling_capsule_count !== 1 ||
    !SHA256.test(String(receipt.authority_sha256 || "")) ||
    !text(receipt.model)
  ) {
    throw blockedError("worker_native_provider_receipt_unavailable");
  }
  const observed = {
    actor: "worker",
    ownerId: row.ownerId,
    workRef: row.workRef,
    runRef: row.runRef,
    surface: "voice",
    snapshotHash: projection.snapshot_sha256,
    capsuleOccurrenceCount: receipt.feeling_capsule_count,
    materialized: true,
    receiptSource: "glasshive.native_provider_receipt",
    nativeRequestSha256: receipt.authority_sha256,
    providerAttemptRef: row.attemptRef,
    provider: source.runtime,
    model: receipt.model,
  };
  observed.producerAttestation = verifyNativeProducerAttestation(
    observed,
    authentication.attestation,
    authentication.authority,
  );
  return observed;
}

function observeMainNativeReceipt(
  coreLogPath,
  assistantMessageId,
  ownerId,
  authentication = {},
) {
  if (!coreLogPath || !text(assistantMessageId)) {
    throw blockedError("main_native_provider_receipt_unavailable");
  }
  let stats;
  try {
    stats = fs.statSync(coreLogPath);
  } catch {
    throw blockedError("main_native_provider_receipt_unavailable");
  }
  if (!stats.isFile() || stats.size > 25 * 1024 * 1024) {
    throw blockedError("main_native_provider_receipt_unavailable");
  }
  const expected = digest(String(assistantMessageId)).slice(0, 16);
  let winner = null;
  for (const line of fs.readFileSync(coreLogPath, "utf8").split(/\r?\n/)) {
    const start = line.indexOf("{");
    if (start < 0) continue;
    try {
      const receipt = JSON.parse(line.slice(start));
      if (
        receipt.event ===
          "viventium_text_main_winning_native_provider_receipt" &&
        receipt.turnIdHash === expected &&
        receipt.capsuleOccurrenceCount === 1 &&
        SHA256.test(String(receipt.snapshotHash || "")) &&
        SHA256.test(String(receipt.nativeRequestSha256 || ""))
      ) {
        winner = receipt;
      }
    } catch {
      // Non-JSON framework lines are never treated as provider evidence.
    }
  }
  if (!winner || !text(winner.provider) || !text(winner.model)) {
    throw blockedError("main_native_provider_receipt_unavailable");
  }
  const observed = {
    actor: "main",
    ownerId,
    surface: "voice",
    snapshotHash: winner.snapshotHash,
    capsuleOccurrenceCount: winner.capsuleOccurrenceCount,
    materialized: true,
    receiptSource: "core.native_receipt",
    nativeRequestSha256: winner.nativeRequestSha256,
    providerAttemptRef: text(winner.attemptRef) || winner.nativeRequestSha256,
    provider: winner.provider,
    model: winner.model,
  };
  observed.producerAttestation = verifyNativeProducerAttestation(
    observed,
    authentication.attestation,
    authentication.authority,
  );
  return observed;
}

function readOwnerTrace(database, ownerId, originRef) {
  return database
    .collection("viventiumorchestrationtraceevents")
    .find({
      ownerScopeHash: scopeHash("owner", ownerId),
      originRefHash: scopeHash("origin", originRef),
    })
    .project({ _id: 0, __v: 0, createdAt: 0 })
    .sort({ sequence: 1 })
    .limit(101)
    .toArray();
}

function readVoiceSegments(database, ownerId, sessionIds) {
  if (!Array.isArray(sessionIds) || !sessionIds.length) {
    throw blockedError("owner_scoped_voice_session_unavailable");
  }
  return database
    .collection("viventiumvoicespeakersegments")
    .find({ callSessionId: { $in: sessionIds } })
    .sort({ createdAt: 1, _id: 1 })
    .limit(201)
    .toArray()
    .then((rows) =>
      rows
        .map((row) => row.payload)
        .filter(
          (payload) =>
            object(payload) &&
            payload.speaker?.actorTrust === "owner_participant" &&
            payload.speaker?.attribution === "verified" &&
            payload.ownerId === ownerId,
        ),
    );
}

function requireObservedCollector(collectors, name) {
  if (!object(collectors) || typeof collectors[name] !== "function") {
    throw blockedError("installed_" + name + "_producer_unavailable");
  }
  return collectors[name];
}

function authenticatedNativeSemanticEvidence(observation) {
  const existing = observation.semanticEvidence.filter(
    (item) => item?.kind === "native_receipt",
  );
  if (existing.length !== 1 || !object(existing[0].payload)) {
    throw blockedError("authenticated_native_semantic_evidence_unavailable");
  }
  const producerAttestations = observation.nativeReceipts.map((receipt) => {
    const authority =
      observation.nativeProducerAuthorities?.[receipt.receiptSource];
    const identity = publicKeyIdentity(authority, receipt.receiptSource);
    const verified = verifyNativeProducerAttestation(
      receipt,
      receipt.producerAttestation,
      authority,
    );
    return {
      publicKeySpki: identity.publicKeySpki.toString("base64url"),
      attestation: verified,
    };
  });
  const routeTruth = {
    originSurface: observation.routes?.originSurface,
    configured: (observation.routes?.configured || []).map((route) => ({
      providerRefHash: digest(String(route.provider || "")),
      modelRefHash: digest(String(route.model || "")),
    })),
    attempts: (observation.routes?.attempts || []).map((attempt) => ({
      providerRefHash: digest(String(attempt.provider || "")),
      modelRefHash: digest(String(attempt.model || "")),
      outcome: text(attempt.outcome),
      observed: attempt.observed === true,
      fallback: attempt.fallback === true,
    })),
  };
  return {
    ...existing[0],
    payload: {
      ...existing[0].payload,
      producerAttestations,
      routeTruth,
    },
  };
}

function cleanupSemanticEvidence(observation, cleanup) {
  if (!object(cleanup) || cleanup.zeroResidue !== true) {
    throw blockedError("synthetic_cleanup_residue_detected");
  }
  return {
    id: "cleanup-receipt",
    kind: "cleanup_receipt",
    producer: "runner.synthetic_cleanup",
    observed: true,
    payload: {
      ownerRefHash: digest(String(observation.ownerId)),
      zeroResidue: true,
      completedAt: new Date().toISOString(),
    },
  };
}

async function writeSemanticManifest(observation, args) {
  if (
    !Array.isArray(observation.semanticEvidence) ||
    !object(observation.correlation) ||
    !SHA256.test(String(observation.correlation.logicalTurnRefHash || "")) ||
    !Number.isSafeInteger(observation.correlation.turnRevision) ||
    observation.correlation.turnRevision < 1
  ) {
    throw blockedError("independent_semantic_evidence_unavailable");
  }
  const counts = new Map();
  const entries = [];
  const stamp = new Date().toISOString();
  const ownerRefHash = digest(String(observation.ownerId));
  const turn = observation.correlation.logicalTurnRefHash;
  for (const item of observation.semanticEvidence) {
    if (
      !object(item) ||
      !text(item.kind) ||
      !Object.hasOwn(SEMANTIC_SURFACES, item.kind) ||
      item.observed !== true ||
      !text(item.id) ||
      (SEMANTIC_PRODUCERS[item.kind] &&
        item.producer !== SEMANTIC_PRODUCERS[item.kind])
    ) {
      throw blockedError("independent_semantic_evidence_producer_unverified");
    }
    const metadata = {
      candidateDigest: observation.candidate.candidateDigest,
      artifactDigest: observation.candidate.artifactDigest,
      ownerRefHash,
      originSurface: "voice",
      surface: SEMANTIC_SURFACES[item.kind],
      logicalTurnRefHash: turn,
      turnRevision: observation.correlation.turnRevision,
      observedAt: stamp,
      workRefHash: item.workRef ? digest(String(item.workRef)) : null,
      runRefHash: item.runRef ? digest(String(item.runRef)) : null,
    };
    let content;
    let suffix;
    if (Buffer.isBuffer(item.bytes)) {
      content = item.bytes;
      suffix = new Set(["telegram_screenshot", "browser_screenshot"]).has(
        item.kind,
      )
        ? ".png"
        : item.kind === "voice_recording"
          ? ".wav"
          : item.kind === "artifact_bytes"
            ? ".html"
            : ".bin";
    } else if (object(item.payload)) {
      suffix = ".json";
      content = Buffer.from(
        JSON.stringify({
          contractVersion: 1,
          schema: "pwk.installed-journey-evidence.v1",
          kind: item.kind,
          producer: item.producer,
          ...metadata,
          payload: item.payload,
        }),
      );
    } else {
      throw blockedError("independent_semantic_evidence_bytes_unavailable");
    }
    const filename = item.id + suffix;
    if (!/^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(filename)) {
      throw blockedError("private_semantic_evidence_name_invalid");
    }
    writePrivateEvidence(args.outputDir, filename, content);
    entries.push({
      id: item.id,
      kind: item.kind,
      path: filename,
      sha256: digest(content),
      ...metadata,
    });
    counts.set(item.kind, (counts.get(item.kind) || 0) + 1);
  }
  for (const [kind, minimum] of Object.entries(SEMANTIC_MINIMUMS)) {
    if ((counts.get(kind) || 0) < minimum) {
      throw blockedError("independent_semantic_evidence_missing:" + kind);
    }
  }
  const identifiers = entries.map((entry) => entry.id);
  const manifest = {
    contractVersion: 1,
    caseId: CASE_ID,
    candidateDigest: observation.candidate.candidateDigest,
    artifactDigest: observation.candidate.artifactDigest,
    correlation: {
      ownerRefHash,
      surface: "voice",
      logicalTurnRefHash: turn,
      turnRevision: observation.correlation.turnRevision,
    },
    runAt: stamp,
    checks: SEMANTIC_REQUIRED_CHECKS.map((id) => ({
      id,
      evidence: identifiers,
    })),
    evidence: entries,
  };
  writePrivateEvidence(args.outputDir, "pwk-uc-019-manifest.json", manifest);
  return path.join(args.outputDir, "pwk-uc-019-manifest.json");
}

function verifyIndependentSemantics(manifestPath, args, authority) {
  if (authority !== POST_CLEANUP_RECEIPT_AUTHORITY) {
    throw blockedError("semantic_receipt_requires_completed_cleanup");
  }
  const command = [
    SEMANTIC_VERIFIER,
    "--case-id",
    CASE_ID,
    "--manifest",
    manifestPath,
    "--evidence-root",
    args.outputDir,
    "--artifact-identity",
    args.identityPath,
    "--installed-root",
    args.installedRoot,
    "--runtime-owner-state",
    args.ownerStatePath,
  ];
  if (args.candidateMode !== "diagnostic") {
    command.push("--receipt-manifest", "pwk-uc-019-receipt.json");
  }
  const evaluated = spawnSync("python3", command, {
    encoding: "utf8",
    timeout: Math.min(args.timeoutMs, 120000),
    maxBuffer: 2 * 1024 * 1024,
    env: {
      ...process.env,
      VIVENTIUM_QA_NODE_EXECUTABLE: process.execPath,
    },
  });
  if (evaluated.status !== 0) {
    throw blockedError(
      "independent_semantic_verifier_rejected_installed_evidence",
    );
  }
  let result;
  try {
    result = JSON.parse(evaluated.stdout);
  } catch {
    throw blockedError("independent_semantic_verifier_receipt_unavailable");
  }
  if (
    result?.caseId !== CASE_ID ||
    result.status !== "PASS" ||
    result.checkCount !== SEMANTIC_REQUIRED_CHECKS.length ||
    !Number.isSafeInteger(result.evidenceCount) ||
    result.evidenceCount < 1
  ) {
    throw blockedError("independent_semantic_verifier_receipt_unavailable");
  }
  return {
    verified: true,
    caseId: CASE_ID,
    surface: "voice",
    candidateDigest: result.candidateDigest,
    artifactDigest: result.artifactDigest,
  };
}

function indexNativeProducerAttestations(value, rows) {
  if (
    !exactKeys(value, ["main", "workers"]) ||
    !object(value.main) ||
    !Array.isArray(value.workers) ||
    value.workers.length !== rows.length
  ) {
    throw blockedError("native_producer_attestation_bundle_unavailable");
  }
  const workers = new Map();
  for (const item of value.workers) {
    if (
      !exactKeys(item, ["runRef", "attestation"]) ||
      !text(item.runRef) ||
      !object(item.attestation) ||
      workers.has(item.runRef)
    ) {
      throw blockedError("native_producer_attestation_bundle_unavailable");
    }
    workers.set(item.runRef, item.attestation);
  }
  if (rows.some((row) => !workers.has(row.runRef))) {
    throw blockedError("native_producer_attestation_bundle_unavailable");
  }
  return { main: value.main, workers };
}

class InstalledCapabilityDriver {
  constructor({
    args,
    scenario,
    environment,
    bridge,
    identity,
    nativeProducerAuthorities,
    injection = {},
  }) {
    this.args = args;
    this.scenario = scenario;
    this.environment = environment;
    this.bridge = bridge;
    this.identity = identity;
    this.nativeProducerAuthorities = nativeProducerAuthorities;
    this.injection = injection;
    this.collectors = injection.collectors;
    this.observers = assertResidueObservers(injection.residueObservers);
    for (const name of [
      "startAudibleCall",
      "observeVoiceLaunch",
      "observeActiveCapabilityJourney",
      "observeCompletedCapabilityJourney",
      "observeNativeProducerAttestations",
      ...(args.allowRestart ? ["observeExternalRestart"] : []),
    ]) {
      requireObservedCollector(this.collectors, name);
    }
    this.browser = null;
    this.mongo = null;
    this.store = null;
    this.database = null;
    this.session = null;
    this.baseline = null;
    this.ownerId = scenario.owner.ownerId;
    this.ObjectId = null;
    this.created = [];
    this.semanticArtifacts = new Set();
    this.started = false;
  }

  async connect() {
    const { MongoClient, ObjectId } = require(
      path.join(LIBRECHAT_ROOT, "node_modules", "mongodb"),
    );
    const { chromium } = require(
      path.join(LIBRECHAT_ROOT, "node_modules", "playwright"),
    );
    this.ObjectId = ObjectId;
    this.mongo = new MongoClient(this.environment.MONGO_URI, {
      serverSelectionTimeoutMS: 5000,
    });
    await this.mongo.connect();
    const databaseName =
      new URL(this.environment.MONGO_URI).pathname.replace(/^\//, "") ||
      "LibreChatViventium";
    this.database = this.mongo.db(databaseName);
    const user = await this.database.collection("users").findOne(
      { email: this.args.qaEmail },
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
    const ownerId = assertSelectedQaAccount(this.args, this.environment, user);
    if (ownerId !== this.ownerId)
      throw blockedError("selected_qa_account_owner_mismatch");
    this.baseline = await captureOwnerBaseline(
      this.database,
      ownerId,
      ObjectId,
    );
    for (const observer of Object.values(this.observers)) {
      const captured = await observer.capture({ ownerId });
      if (!object(captured) || captured.ownerId !== ownerId) {
        throw blockedError("synthetic_owner_cleanup_baseline_unverified");
      }
    }
    // The shared owner-verified helper opens DatabaseSync with { readOnly: true }.
    this.store = openReadOnlyGlassHiveStore(this.args.glassHiveDbPath);
    const options = {
      channel: "chrome",
      headless: false,
      args: [
        "--use-fake-ui-for-media-stream",
        "--use-fake-device-for-media-stream",
        "--use-file-for-fake-audio-capture=" + this.scenario.voice.audioPath,
      ],
    };
    this.browser = await chromium.launch(options);
    this.context = await this.browser.newContext({
      viewport: { width: 1440, height: 1080 },
      acceptDownloads: true,
    });
    await this.context.grantPermissions(["microphone"], {
      origin: this.args.playgroundBase,
    });
    this.session = await createEphemeralBrowserSession({
      db: this.database,
      user,
      args: this.args,
      env: this.environment,
    });
    await this.context.addCookies(this.session.cookies);
    this.page = await this.context.newPage();
    const target =
      this.args.clientBase +
      "/c/new?agent_id=" +
      encodeURIComponent(this.args.agentId);
    const refresh = this.page.waitForResponse(
      (response) => {
        try {
          return (
            response.request().method() === "POST" &&
            new URL(response.url()).pathname === "/api/auth/refresh"
          );
        } catch {
          return false;
        }
      },
      { timeout: Math.min(this.args.timeoutMs, 30000) },
    );
    await this.page.goto(target, { waitUntil: "domcontentloaded" });
    if ((await refresh).status() !== 200) {
      throw blockedError("ephemeral_browser_session_refresh_rejected");
    }
    if (new URL(this.page.url()).pathname === "/login") {
      throw blockedError("ephemeral_browser_session_refresh_rejected");
    }
    this.started = true;
  }

  async captureVisible(name, target = this.page) {
    const bytes = await target.screenshot({ fullPage: true });
    if (!Buffer.isBuffer(bytes) || bytes.length < 128) {
      throw blockedError("headed_user_surface_capture_unavailable");
    }
    writePrivateEvidence(this.args.outputDir, name + ".png", bytes);
    return { bytes, sha256: digest(bytes), headed: true, visible: true };
  }

  async ownerApi(endpoint, options = {}) {
    const base = assertLoopbackUrl(this.args.apiBase, "api");
    const destination = new URL(endpoint, base);
    if (
      destination.origin !== base.origin ||
      !destination.pathname.startsWith("/api/viventium/")
    ) {
      throw blockedError("owner_scoped_local_api_boundary_invalid");
    }
    return this.context.request.fetch(destination.toString(), {
      method: options.method || "GET",
      maxRedirects: 0,
      headers: { Authorization: "Bearer " + this.session.accessToken },
      ...(options.data ? { data: options.data } : {}),
    });
  }

  async observeOwnerWork(expected) {
    const observed = await waitFor(
      async () => {
        const records = await this.database
          .collection("viventium_glasshive_callback_bindings")
          .find({
            ownerId: this.ownerId,
            createdAt: { $gte: new Date(this.launchedAtMs - 1500) },
            workRef: { $nin: ["", null] },
          })
          .project({ _id: 1, workRef: 1, originRef: 1 })
          .sort({ createdAt: 1, _id: 1 })
          .limit(expected + 1)
          .toArray();
        if (records.length > expected) {
          throw blockedError("unexpected_duplicate_or_sibling_mission_created");
        }
        return records.length === expected ? records : null;
      },
      this.args.timeoutMs,
      "two_owner_scoped_missions_unavailable",
    );
    this.workRefs = observed.map((row) => String(row.workRef));
    if (new Set(this.workRefs).size !== expected) {
      throw blockedError("two_distinct_owner_scoped_missions_required");
    }
    return observed;
  }

  async observeConcurrentWorkers() {
    return waitFor(
      () => {
        const observed = readScopedRuntimeEvidence(this.store, {
          ownerId: this.ownerId,
          workRefs: this.workRefs,
        });
        const overlap = assessRuntimeOverlap(observed.rows, this.ownerId);
        if (observed.rows.some((row) => row.finishedAt)) {
          throw blockedError("worker_finished_before_live_capability_parity");
        }
        return overlap.pass ? observed.rows : null;
      },
      this.args.timeoutMs,
      "concurrent_leased_runtime_invocations_unavailable",
    );
  }

  async observeTerminalWorkers() {
    return waitFor(
      () => {
        const observed = readScopedRuntimeEvidence(this.store, {
          ownerId: this.ownerId,
          workRefs: this.workRefs,
        });
        return observed.rows.every(
          (row) =>
            row.state === "completed" &&
            text(row.runtimeInvokedAt) &&
            text(row.finishedAt),
        )
          ? observed
          : null;
      },
      this.args.timeoutMs,
      "terminal_worker_runtime_receipts_unavailable",
    );
  }

  async start() {
    await this.connect();
    const telegram = await observeSignedDesktop(this.bridge, {
      method: "get_app_state",
      app: text(this.scenario.telegram?.appBundleId),
    });
    if (telegram.visible !== true)
      throw blockedError("synthetic_telegram_window_unavailable");
    const openCall = requireObservedCollector(
      this.collectors,
      "startAudibleCall",
    );
    const call = await openCall({
      page: this.page,
      context: this.context,
      ownerId: this.ownerId,
      scenario: this.scenario,
      database: this.database,
      captureVisible: this.captureVisible.bind(this),
    });
    if (
      !object(call) ||
      call.ownerId !== this.ownerId ||
      call.observed !== true
    ) {
      throw blockedError("audible_owner_scoped_call_unavailable");
    }
    this.launchedAtMs = Date.now();
    const launch = requireObservedCollector(
      this.collectors,
      "observeVoiceLaunch",
    );
    const mainLaunch = await launch({
      ownerId: this.ownerId,
      call,
      scenario: this.scenario,
      database: this.database,
      page: this.page,
    });
    if (!object(mainLaunch) || mainLaunch.ownerId !== this.ownerId) {
      throw blockedError("voice_owner_launch_observation_unavailable");
    }
    await this.observeOwnerWork(2);
    const activeRows = await this.observeConcurrentWorkers();
    const adapterAction = await observeSignedDesktop(this.bridge, {
      method: "press_key",
      app: text(this.scenario.telegram?.appBundleId),
      action: "telegram.send_grouped_attachments",
      files: this.scenario.files.map((item) => ({
        kind: item.kind,
        path: item.path,
      })),
    });
    if (adapterAction.ownerId !== this.ownerId) {
      throw blockedError("telegram_attachment_owner_mismatch");
    }
    const observeActive = requireObservedCollector(
      this.collectors,
      "observeActiveCapabilityJourney",
    );
    const active = await observeActive({
      ownerId: this.ownerId,
      rows: activeRows,
      call,
      scenario: this.scenario,
      page: this.page,
      database: this.database,
      store: this.store,
      session: this.session,
      bridge: this.bridge,
      args: this.args,
    });
    if (!object(active) || active.ownerId !== this.ownerId) {
      throw blockedError("installed_active_capability_observation_unavailable");
    }
    if (this.args.allowRestart) {
      const restart = requireObservedCollector(
        this.collectors,
        "observeExternalRestart",
      );
      const proof = await restart({
        ownerId: this.ownerId,
        rows: activeRows,
        candidateDigest: this.identity.candidateDigest,
      });
      assertRestartReadiness(proof, {
        caseId: CASE_ID,
        candidateDigest: this.identity.candidateDigest,
      });
    }
    const terminal = await this.observeTerminalWorkers();
    const observeCompleted = requireObservedCollector(
      this.collectors,
      "observeCompletedCapabilityJourney",
    );
    const completed = await observeCompleted({
      ownerId: this.ownerId,
      rows: terminal.rows,
      callbacks: terminal.callbacks,
      actions: terminal.actions,
      scenario: this.scenario,
      database: this.database,
      store: this.store,
      page: this.page,
      context: this.context,
      bridge: this.bridge,
      captureVisible: this.captureVisible.bind(this),
      ownerApi: this.ownerApi.bind(this),
    });
    if (!object(completed) || completed.ownerId !== this.ownerId) {
      throw blockedError(
        "installed_completed_capability_observation_unavailable",
      );
    }
    const collectNativeAttestations = requireObservedCollector(
      this.collectors,
      "observeNativeProducerAttestations",
    );
    const nativeAttestations = indexNativeProducerAttestations(
      await collectNativeAttestations({
        ownerId: this.ownerId,
        assistantMessageId: text(mainLaunch.assistantMessageId),
        rows: terminal.rows.map((row) => ({
          ownerId: row.ownerId,
          workRef: row.workRef,
          runRef: row.runRef,
          attemptRef: row.attemptRef,
        })),
      }),
      terminal.rows,
    );
    const observation = {
      ...active,
      ...completed,
      caseId: CASE_ID,
      ownerId: this.ownerId,
      ownerEmail: this.args.qaEmail,
      candidate: {
        candidateDigest: this.identity.candidateDigest,
        artifactDigest: this.identity.artifactDigest,
        installed: true,
      },
      rows: terminal.rows,
      maxQuickLatencyMs: this.args.maxQuickLatencyMs,
      nativeProducerAuthorities: this.nativeProducerAuthorities,
      nativeReceipts: [
        observeMainNativeReceipt(
          this.args.coreLogPath,
          text(mainLaunch.assistantMessageId),
          this.ownerId,
          {
            authority: this.nativeProducerAuthorities?.["core.native_receipt"],
            attestation: nativeAttestations.main,
          },
        ),
        ...terminal.rows.map((row) =>
          observeWorkerNativeReceipt(this.store, row, {
            authority:
              this.nativeProducerAuthorities?.[
                "glasshive.native_provider_receipt"
              ],
            attestation: nativeAttestations.workers.get(row.runRef),
          }),
        ),
      ],
    };
    const originRefs = new Set(terminal.rows.map((row) => row.originRef));
    if (originRefs.size !== 1) {
      throw blockedError("single_shared_origin_trace_unavailable");
    }
    observation.trace = {
      ownerId: this.ownerId,
      originRef: terminal.rows[0].originRef,
      source: "core.immutable_trace",
      events: await readOwnerTrace(
        this.database,
        this.ownerId,
        terminal.rows[0].originRef,
      ),
    };
    if (!Array.isArray(observation.semanticEvidence)) {
      throw blockedError("independent_semantic_evidence_unavailable");
    }
    observation.semanticEvidence = [
      ...observation.semanticEvidence.filter(
        (item) => item?.kind !== "trace_export",
      ),
      buildSemanticTraceExport(
        observation.trace,
        terminal.rows,
        observation.correlation,
      ),
    ];
    return observation;
  }

  async finalizeAfterCleanup(observation, cleanup) {
    if (cleanup?.zeroResidue !== true || object(observation.semanticVerifier)) {
      throw blockedError("post_cleanup_semantic_verifier_unavailable");
    }
    const authenticatedNative =
      authenticatedNativeSemanticEvidence(observation);
    observation.semanticEvidence = [
      ...observation.semanticEvidence.filter(
        (item) =>
          item?.kind !== "native_receipt" && item?.kind !== "cleanup_receipt",
      ),
      authenticatedNative,
      cleanupSemanticEvidence(observation, cleanup),
    ];
    const manifest = await writeSemanticManifest(observation, this.args);
    this.semanticArtifacts.add(manifest);
    const receipt = path.join(this.args.outputDir, "pwk-uc-019-receipt.json");
    this.semanticArtifacts.add(receipt);
    observation.semanticVerifier = verifyIndependentSemantics(
      manifest,
      this.args,
      POST_CLEANUP_RECEIPT_AUTHORITY,
    );
    return observation;
  }

  async discardSemanticArtifacts(observation) {
    if (observation) delete observation.semanticVerifier;
    const failures = [];
    for (const location of this.semanticArtifacts) {
      try {
        const stat = fs.lstatSync(location);
        if (stat.isSymbolicLink() || !stat.isFile() || stat.mode & 0o077) {
          throw new Error("unsafe semantic artifact");
        }
        fs.unlinkSync(location);
      } catch (error) {
        if (error?.code !== "ENOENT") failures.push(error);
      }
    }
    this.semanticArtifacts.clear();
    if (failures.length) {
      throw blockedError("stale_semantic_receipt_cleanup_failed");
    }
  }

  async cleanup() {
    const failures = [];
    if (this.database && this.baseline && this.ObjectId) {
      try {
        const created = await discoverSyntheticResidue(
          this.database,
          this.ownerId,
          this.ObjectId,
          this.baseline,
        );
        for (const observer of Object.values(this.observers)) {
          const removed = await observer.removeAndVerify({
            ownerId: this.ownerId,
            created,
          });
          if (!object(removed) || removed.remaining !== 0) {
            throw blockedError("synthetic_cleanup_residue_detected");
          }
        }
        if (this.session) {
          await this.session.cleanup();
          const index = created.findIndex(
            (item) =>
              item.collection === "sessions" &&
              String(item.id) === String(this.session.sessionId),
          );
          if (index >= 0) created.splice(index, 1);
          this.session = null;
        }
        await cleanupSyntheticResidue(this.database, {
          ownerId: this.ownerId,
          created,
          baselineIds: this.baseline.ids,
          ownedCallSessionIds: new Set(
            created
              .filter((record) => record.collection === "viventiumcallsessions")
              .map((record) => record.callSessionId),
          ),
          residueObservers: Object.values(this.observers),
        });
        const remaining = await discoverSyntheticResidue(
          this.database,
          this.ownerId,
          this.ObjectId,
          this.baseline,
        );
        if (remaining.length)
          throw blockedError("synthetic_cleanup_residue_detected");
      } catch (error) {
        failures.push(error);
      }
    } else if (this.session) {
      await this.session.cleanup().catch((error) => failures.push(error));
    }
    if (this.browser) {
      await this.browser.close().catch((error) => failures.push(error));
    }
    if (this.store) {
      try {
        this.store.close();
      } catch (error) {
        failures.push(error);
      }
    }
    if (this.mongo) {
      await this.mongo.close().catch((error) => failures.push(error));
    }
    if (failures.length) {
      const failure = failures[0];
      throw blockedError(
        failure?.blocked
          ? failure.message
          : "synthetic_cleanup_residue_detected",
      );
    }
    return { zeroResidue: true };
  }
}

async function runInstalledJourney(
  argv = process.argv.slice(2),
  environment = process.env,
  injection = {},
) {
  let args;
  try {
    args = parseArguments(argv);
    if (args.mode === "dry-run") return dryRunPlan(args);
    if (environment.VIVENTIUM_QA_ALLOW_PWK_UC_019 !== "1") {
      throw blockedError("installed_worker_parity_requires_explicit_opt_in");
    }
    if (environment.VIVENTIUM_QA_ALLOW_SYNTHETIC_FIXTURES !== "1") {
      throw blockedError("synthetic_fixture_consent_required");
    }
    if (!object(injection.launchGrant)) {
      throw blockedError("installed_parent_launch_injection_owner_unavailable");
    }
    args.outputDir = preparePrivateEvidenceRoot(args.outputDir, {
      repoRoot: ROOT,
    });
    fs.chmodSync(args.outputDir, PRIVATE_DIRECTORY_MODE);
    if (fs.readdirSync(args.outputDir).length !== 0) {
      throw blockedError("private_evidence_output_must_be_empty");
    }
    const scenario = readPrivateScenario(args.scenarioPath);
    const runtimeRoot = text(scenario?.runtime?.runtimeRoot);
    if (!runtimeRoot) throw blockedError("installed_runtime_root_unavailable");
    args.runtimeRoot = path.resolve(runtimeRoot);
    const installed = readInstalledEnvironment(
      {
        ...args,
        glassHiveDbPath: path.resolve(text(scenario?.runtime?.glassHiveDbPath)),
      },
      environment,
    );
    validateScenario(scenario, args, installed);
    assertProductionDesktopAuthority(injection.desktopAuthority);
    await authenticateParentComputerAuthority(injection.desktopAuthority);
    const bridge = assertSignedDesktopAdapter(
      injection.desktopAdapter,
      {
        ownerId: scenario.owner.ownerId,
        telegramUserId: scenario.owner.telegramUserId,
        telegramChatId: scenario.owner.telegramChatId,
        accountLabel: scenario.telegram.accountLabel,
        chatLabel: scenario.telegram.chatLabel,
        appBundleId: scenario.telegram.appBundleId,
        ...(scenario.conversation?.conversationId
          ? { conversationId: scenario.conversation.conversationId }
          : {}),
      },
      installed,
      { authority: injection.desktopAuthority },
    );
    const identity = measureInstalledCandidate(args);
    const parentLaunch = assertParentLaunchInjection(injection, {
      args,
      scenario,
      identity,
      desktopAuthority: injection.desktopAuthority,
    });
    const driver = new InstalledCapabilityDriver({
      args,
      scenario,
      environment: installed,
      bridge,
      identity,
      nativeProducerAuthorities: parentLaunch.nativeProducerAuthorities,
      injection,
    });
    const result = await executeCapabilityJourney(driver, {
      candidateMode: args.candidateMode,
    });
    if (result.observation) {
      const summary = buildPublicSummary({
        result,
        observation: result.observation,
        qaRunId: args.qaRunId,
      });
      writePrivateEvidence(args.outputDir, "pwk-uc-019-result.json", summary);
      const file = path.join(args.outputDir, "pwk-uc-019-result.json");
      fs.chmodSync(file, PRIVATE_FILE_MODE);
    }
    return buildPublicSummary({
      result,
      observation: result.observation,
      qaRunId: args.qaRunId,
    });
  } catch (error) {
    return buildPublicSummary({
      result: {
        status: "BLOCKED",
        blocker: error?.blocked
          ? error.message
          : "installed_worker_parity_blocked",
      },
      qaRunId: args?.qaRunId,
    });
  }
}

if (require.main === module) {
  const injected =
    globalThis[Symbol.for("viventium.pwk.uc019.sky.adapter.v1")] || {};
  runInstalledJourney(process.argv.slice(2), process.env, injected)
    .then((result) => {
      process.stdout.write(JSON.stringify(result) + "\n");
      if (
        !new Set(["DRY_RUN", "PASS", "PRE_GATE_COMPLETE"]).has(result.status)
      ) {
        process.exitCode = 2;
      }
    })
    .catch(() => {
      process.stdout.write(
        JSON.stringify({
          caseId: CASE_ID,
          status: "BLOCKED",
          releaseReady: false,
          receiptEligible: false,
          releaseLabel: RELEASE_LABEL,
          blocker: "installed_worker_parity_blocked",
        }) + "\n",
      );
      process.exitCode = 2;
    });
}

module.exports = {
  CASE_ID,
  REQUIRED_CHECKS,
  SEMANTIC_REQUIRED_CHECKS,
  REQUIRED_CAPABILITIES,
  PRIVATE_DIRECTORY_MODE,
  PRIVATE_FILE_MODE,
  parseArguments,
  dryRunPlan,
  assertLiveOptIn,
  assertSignedDesktopAdapter,
  assertProductionDesktopAuthority,
  assertParentLaunchInjection,
  observeSignedDesktop,
  verifyNativeProducerAttestation,
  assessFeelingsParity,
  assessRouteParity,
  assessCapabilityParity,
  assessAttachmentParity,
  assessControlParity,
  assessVoiceJourney,
  assessSurfaceDenials,
  assessArtifactParity,
  assessImmutableTrace,
  buildSemanticTraceExport,
  evaluateCapabilityJourney,
  buildPublicSummary,
  cleanupSyntheticResidue,
  executeCapabilityJourney,
  readPrivateScenario,
  validateScenario,
  readInstalledEnvironment,
  measureInstalledCandidate,
  observeWorkerNativeReceipt,
  observeMainNativeReceipt,
  captureOwnerBaseline,
  discoverSyntheticResidue,
  writeSemanticManifest,
  verifyIndependentSemantics,
  InstalledCapabilityDriver,
  runInstalledJourney,
  createEphemeralBrowserSession,
  assertEphemeralSessionSafety,
  openReadOnlyGlassHiveStore,
  canonicalJson,
  blockedError,
};
