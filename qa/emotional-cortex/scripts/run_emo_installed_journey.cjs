#!/usr/bin/env node
"use strict";

/*
 * Installed emotional journeys are deliberately unusable without an independent,
 * owner-bound parent authority. This process neither mints evidence nor owns
 * fixture, fault, restart, browser, GlassHive, or Telegram capabilities.
 */

const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const {
  blockedError,
  assertSelectedQaAccount,
} = require("../../parallel-orchestrator/scripts/run_installed_parallel_work_journey.cjs");
const sharedComputer = require("../../telegram-document-attachments/scripts/run_tgdoc_010_installed_journey.cjs");
const {
  authenticateParentComputerAuthority,
  assertTrustedComputerAdapter,
  observeTrustedComputer,
} = sharedComputer;

const ROOT = path.resolve(__dirname, "../../..");
const CASE_047 = "EMO-UC-047";
const CASE_048 = "EMO-UC-048";
const CASE_IDS = new Set([CASE_047, CASE_048]);
const RELEASE_LABEL = "PRE-GATE / NOT READY";
const INSTALLED_SYNTHETIC_DOMAIN = "example.com";
const DISPOSABLE_SYNTHETIC_DOMAIN = "local-qa.invalid";
const DISPOSABLE_EMO_048_LOCAL_PART = /^emo-uc-048-[a-f0-9]{32}$/;
const SHA256 = /^[a-f0-9]{64}$/;
const SHA256_REF = /^sha256:[a-f0-9]{64}$/;
const OWNER_ID = /^[a-f0-9]{24}$/;
const SIGNATURE = /^ed25519:[A-Za-z0-9_-]{86}$/;
const SAFE_CODE = /^[a-z][a-z0-9_:-]{0,119}$/;
const MAX_CLOCK_SKEW_MS = 30_000;
const MAX_SELECTION_AGE_MS = 5_000;
const SKY_METHODS = Object.freeze([
  "get_app_state",
  "click",
  "paste",
  "press_key",
]);
const BOUNDARIES = Object.freeze([
  "cortex_ledger_first_write",
  "web_replay_persistence",
  "web_redis_publish_ack",
  "telegram_promoted_parent_presentation",
]);
const REQUIRED_SPECIALISTS = new Set([
  "emotional_resonance",
  "product_help",
  "productivity",
  "red_team",
  "research",
]);
const SCENARIOS = Object.freeze([
  {
    name: "all_agents_before_delegation",
    scope: "all_agents",
    enabled: true,
    workers: 0,
  },
  {
    name: "all_agents_during_workers",
    scope: "all_agents",
    enabled: true,
    workers: 2,
  },
  {
    name: "conscious_agent_during_workers",
    scope: "conscious_agent",
    enabled: true,
    workers: 2,
  },
  {
    name: "off_during_workers",
    scope: "all_agents",
    enabled: false,
    workers: 2,
  },
]);
const REQUIRED_SERVICES = Object.freeze({
  [CASE_047]: Object.freeze(["glasshive-runtime", "librechat-core"]),
  [CASE_048]: Object.freeze(["librechat-core", "telegram-bot"]),
});
const CAPABILITIES = new Set([
  "parent_control",
  "browser",
  "glasshive",
  "evidence",
]);
const READ_ONLY_OPERATIONS = new Set([
  "parent_control:status",
  "parent_control:inspect_owner",
  "browser:observe_visible_response",
  "browser:observe_linked_conversation",
  "browser:observe_visible_insight",
  "glasshive:observe_running_workers",
  "evidence:observe_feelings_scenario",
  "evidence:observe_active_feelings_request",
  "evidence:observe_provider_fallback",
  "evidence:observe_phase_b_continuity",
  "evidence:observe_specialist_independence",
  "evidence:observe_completed_graph",
  "evidence:observe_first_persistence_failure",
  "evidence:observe_settled_delivery",
  "evidence:observe_replayed_delivery",
  "evidence:observe_consumed_fault_boundaries",
  "evidence:observe_typed_terminal_probe",
]);
const PROHIBITED_VERIFIER_ENVIRONMENT = Object.freeze([
  "VIVENTIUM_APP_SUPPORT_DIR",
  "VIVENTIUM_RUNTIME_DIR",
  "VIVENTIUM_RUNTIME_PROFILE",
  "VIVENTIUM_LOCAL_QA_CASE_ID",
  "VIVENTIUM_LOCAL_QA_CASE_TOKEN",
  "VIVENTIUM_LOCAL_QA_SESSION_REF",
  "VIVENTIUM_LOCAL_QA_MODE",
  "VIVENTIUM_LOCAL_QA_COMPONENT_ARTIFACT_DIGEST",
]);
const EMO_047_GATES = Object.freeze([
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
]);
const EMO_048_CHECKS = Object.freeze([
  "active-local-qa-authority",
  "all-four-fault-boundaries",
  "exact-insight-identity",
  "restart-service-acknowledgements",
  "append-only-persistence-ledger",
  "exact-presentation-receipts",
  "exactly-once-linked-visibility",
  "typed-terminal-outcome",
]);
const EMO_048_EVIDENCE = Object.freeze({
  "completion-record": "completion_record",
  "fault-controls": "fault_controls",
  "restart-acknowledgements": "restart_acknowledgements",
  "persistence-ledger": "persistence_ledger",
  "presentation-records": "presentation_records",
  "visibility-records": "visibility_records",
  "terminal-outcome": "terminal_outcome",
  "web-settled": "browser_screenshot",
  "web-replayed": "browser_screenshot",
  "telegram-settled": "telegram_screenshot",
  "telegram-replayed": "telegram_screenshot",
});
const EMO_047_RECEIPT_BRIDGE = String.raw`
import importlib.util
import json
import os
import sys
from pathlib import Path


def load(name, source):
    specification = importlib.util.spec_from_file_location(name, source)
    if specification is None or specification.loader is None:
        raise ValueError("registered semantic verifier unavailable")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


source = Path(sys.argv[1]).resolve(strict=True)
manifest = Path(sys.argv[2])
root = Path(sys.argv[3])
receipt_path = Path(sys.argv[4])
verifier = load("viventium_emo047_registered_semantic_verifier", source)
gate_path = source.parents[3] / "scripts" / "viventium" / "parallel_work_release_gate.py"
gate = load("viventium_emo047_registered_release_gate", gate_path)
registration = gate.REGISTERED_SEMANTIC_VERIFIERS.get(verifier.CASE_ID)
if (
    not isinstance(registration, dict)
    or registration.get("id") != verifier.VERIFIER_ID
    or (source.parents[3] / registration["path"]).resolve(strict=True) != source
):
    raise ValueError("registered semantic verifier unavailable")

checked = verifier._utc_now()
authority = verifier.probe_live_authority(now=checked)
private_root = verifier._private_root(root)
relative = manifest.relative_to(private_root).as_posix()
descriptor, relative = verifier._private_descriptor(relative, root=private_root)
try:
    _, evidence = authority.parent_control.read_private_evidence_fd(descriptor)
finally:
    os.close(descriptor)
result = verifier.assess_manifest(
    evidence,
    evidence_root=private_root,
    expected_candidate_digest=authority.candidate_digest,
    expected_artifact_digest=authority.artifact_digest,
    installed_owner_proven=True,
    now=checked,
)
if result.get("status") == "PASS":
    target = receipt_path.resolve(strict=False)
    if target.parent != private_root or receipt_path.is_symlink():
        raise ValueError("private verifier receipt path invalid")
    receipt = verifier.receipt_manifest(result=result)
    receipt["verifier"] = {"id": verifier.VERIFIER_ID, "manifest": relative}
    descriptor = os.open(
        target,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8", closefd=False) as stream:
            json.dump(receipt, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(descriptor)
    finally:
        os.close(descriptor)
print(json.dumps({key: value for key, value in result.items() if not key.startswith("_")}, sort_keys=True))
raise SystemExit(0 if result.get("status") == "PASS" else 1)
`;

function object(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function text(value) {
  return typeof value === "string" ? value.trim() : "";
}

function sha256(value) {
  return crypto.createHash("sha256").update(value).digest("hex");
}

function canonicalJson(value) {
  if (Array.isArray(value))
    return "[" + value.map(canonicalJson).join(",") + "]";
  if (object(value)) {
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

function parseArguments(argv = process.argv.slice(2)) {
  const supplied = new Map();
  let mode = "";
  for (const value of argv) {
    if (value === "--live" || value === "--dry-run") {
      if (mode) throw blockedError("conflicting_execution_modes");
      mode = value.slice(2);
      continue;
    }
    if (value === "--allow-restart") {
      if (supplied.has("allow-restart"))
        throw blockedError("duplicate_argument");
      supplied.set("allow-restart", "true");
      continue;
    }
    if (!value.startsWith("--") || !value.includes("=")) {
      throw blockedError("unknown_argument");
    }
    const boundary = value.indexOf("=");
    const key = value.slice(2, boundary);
    if (!new Set(["case", "qa-email", "owner-id", "evidence-root"]).has(key)) {
      throw blockedError("unknown_argument");
    }
    if (supplied.has(key)) throw blockedError("duplicate_argument");
    supplied.set(key, value.slice(boundary + 1));
  }
  const caseId = supplied.get("case") || CASE_047;
  if (!CASE_IDS.has(caseId)) throw blockedError("unsupported_case");
  return {
    caseId,
    mode: mode || "dry-run",
    qaEmail: text(supplied.get("qa-email")).toLowerCase(),
    ownerId: text(supplied.get("owner-id")),
    evidenceRoot: text(supplied.get("evidence-root")),
    allowRestart: supplied.get("allow-restart") === "true",
    qaRunId: caseId + "-" + crypto.randomUUID(),
  };
}

function dryRunPlan(args) {
  if (args?.mode !== "dry-run") throw blockedError("dry_run_required");
  return {
    caseId: args.caseId,
    status: "DRY_RUN",
    sideEffects: false,
    invokesModels: false,
    opensBrowser: false,
    mutatesAccount: false,
    restartsRuntime: false,
    releaseReady: false,
    receiptEligible: false,
    releaseLabel: RELEASE_LABEL,
    independentVerifier:
      args.caseId === CASE_047 ? "run_emo_uc_047.py" : "run_emo_uc_048.py",
  };
}

function assertLiveOptIn(args, environment) {
  if (
    args?.mode !== "live" ||
    environment?.VIVENTIUM_QA_ALLOW_INSTALLED_EMOTIONAL_JOURNEY !== "1"
  ) {
    throw blockedError("installed_emotional_journey_requires_explicit_opt_in");
  }
  if (environment.CI || environment.NODE_ENV === "production") {
    throw blockedError("local_installed_qa_only");
  }
  if (environment.VIVENTIUM_QA_ALLOW_SYNTHETIC_FIXTURES !== "1") {
    throw blockedError("synthetic_fixture_consent_required");
  }
  if (environment.VIVENTIUM_QA_ALLOW_EMOTIONAL_COMPUTER !== "1") {
    throw blockedError("computer_consent_required");
  }
  const personal = text(environment.VIVENTIUM_QA_OWNER_EMAIL).toLowerCase();
  const configured = text(environment.VIVENTIUM_QA_EMAIL).toLowerCase();
  if (!personal || !configured)
    throw blockedError("explicit_owner_identity_guard_required");
  if (!text(args.qaEmail) || text(args.qaEmail).toLowerCase() !== configured) {
    throw blockedError("configured_synthetic_owner_mismatch");
  }
  if (configured === personal)
    throw blockedError("personal_owner_account_refused");
  if (environment.VIVENTIUM_QA_ALLOW_EMOTIONAL_FAULTS !== "1") {
    throw blockedError("emotional_faults_require_explicit_permission");
  }
  if (args.caseId === CASE_048) {
    if (
      args.allowRestart !== true ||
      environment.VIVENTIUM_QA_ALLOW_COORDINATED_RESTART !== "1"
    ) {
      throw blockedError("coordinated_restart_requires_explicit_permission");
    }
  }
}

function assertSyntheticOwner(owner, environment, expectedOwnerId, caseId) {
  if (!object(owner) || !OWNER_ID.test(text(owner.ownerId))) {
    throw blockedError("explicit_synthetic_owner_required");
  }
  const email = text(owner.email).toLowerCase();
  const personal = text(environment?.VIVENTIUM_QA_OWNER_EMAIL).toLowerCase();
  const configured = text(environment?.VIVENTIUM_QA_EMAIL).toLowerCase();
  const personalTelegramUserId = text(
    environment?.VIVENTIUM_QA_OWNER_TELEGRAM_USER_ID,
  );
  const personalTelegramChatId = text(
    environment?.VIVENTIUM_QA_OWNER_TELEGRAM_CHAT_ID,
  );
  if (!personal || !personalTelegramUserId || !personalTelegramChatId) {
    throw blockedError("personal_owner_identity_guard_required");
  }
  if (email === personal) {
    throw blockedError("personal_owner_account_refused");
  }
  if (text(owner.telegramUserId) === personalTelegramUserId) {
    throw blockedError("personal_telegram_account_refused");
  }
  if (text(owner.telegramChatId) === personalTelegramChatId) {
    throw blockedError("personal_telegram_chat_refused");
  }
  const role = text(owner.role).toUpperCase();
  if (role === "ADMIN") throw blockedError("admin_account_refused");
  if (role !== "USER") throw blockedError("non_admin_synthetic_role_required");
  if (owner.synthetic !== true)
    throw blockedError("explicit_synthetic_owner_required");
  if (!configured || email !== configured)
    throw blockedError("configured_synthetic_owner_mismatch");
  if (owner.viventiumApprovalStatus !== "approved") {
    throw blockedError("approved_synthetic_owner_required");
  }
  if (owner.locked === true || owner.isLocked === true || owner.banned === true) {
    throw blockedError("locked_qa_account_refused");
  }
  const [local, domain, ...unexpected] = email.split("@");
  if (
    !local ||
    unexpected.length ||
    (domain !== INSTALLED_SYNTHETIC_DOMAIN &&
      (domain !== DISPOSABLE_SYNTHETIC_DOMAIN ||
        !DISPOSABLE_EMO_048_LOCAL_PART.test(local) ||
        (caseId && caseId !== CASE_048)))
  ) {
    throw blockedError("synthetic_qa_account_required");
  }
  if (expectedOwnerId && owner.ownerId !== expectedOwnerId) {
    throw blockedError("configured_synthetic_owner_mismatch");
  }
  if (
    !/^\d{4,20}$/.test(text(owner.telegramUserId)) ||
    !/^-?\d{4,20}$/.test(text(owner.telegramChatId))
  ) {
    throw blockedError("synthetic_telegram_identity_required");
  }
  assertSelectedQaAccount({ qaEmail: configured }, environment, {
    ...owner,
    _id: owner.ownerId,
  });
  return owner;
}

function assertExternalAuthority(authority) {
  try {
    if (
      !object(authority) ||
      !(authority.publicKey instanceof crypto.KeyObject) ||
      authority.publicKey.type !== "public" ||
      authority.publicKey.asymmetricKeyType !== "ed25519" ||
      !Number.isSafeInteger(authority.peerProcessId) ||
      authority.peerProcessId <= 1 ||
      authority.peerProcessId === process.pid ||
      authority.peerProcessId !== process.ppid ||
      !/^sky_[A-Za-z0-9_-]{8,64}$/.test(text(authority.sessionRef)) ||
      authority.keyId !==
        sha256(authority.publicKey.export({ type: "spki", format: "der" }))
    ) {
      throw blockedError("external_computer_authority_required");
    }
    if (typeof sharedComputer.assertExternalComputerAuthority !== "function") {
      throw blockedError("external_computer_authority_required");
    }
    sharedComputer.assertExternalComputerAuthority(authority);
    return authority;
  } catch {
    throw blockedError("external_computer_authority_required");
  }
}

async function assertIndependentParentComputerAuthority(authority) {
  if (
    !object(authority) ||
    Object.hasOwn(authority, "unitTestHarness") ||
    (object(authority.transport) &&
      Object.hasOwn(authority.transport, "unitTestHarness")) ||
    typeof authenticateParentComputerAuthority !== "function" ||
    typeof sharedComputer.assertExternalComputerAuthority !== "function"
  ) {
    throw blockedError("independent_parent_computer_authority_unavailable");
  }
  try {
    await authenticateParentComputerAuthority(authority);
    return assertExternalAuthority(authority);
  } catch {
    throw blockedError("independent_parent_computer_authority_unavailable");
  }
}

function verifyParentSignature(authority, payload, proof) {
  if (
    typeof sharedComputer.verifyExternalComputerProof !== "function" ||
    !SIGNATURE.test(text(proof)) ||
    !sharedComputer.verifyExternalComputerProof(
      authority.publicKey,
      payload,
      proof,
    )
  ) {
    return false;
  }
  return true;
}

function assertParentOwnedComputerBridge(driver, owner, identity, authority) {
  const parent = assertExternalAuthority(authority);
  if (
    !object(driver) ||
    typeof driver.get_app_state !== "function" ||
    typeof assertTrustedComputerAdapter !== "function" ||
    typeof observeTrustedComputer !== "function"
  ) {
    throw blockedError("computer_bridge_unavailable");
  }
  const provenance = driver.provenance;
  if (
    !object(provenance) ||
    provenance.contractVersion !== 1 ||
    provenance.caseId !== identity?.caseId ||
    provenance.provider !== "@oai/sky" ||
    provenance.controlPlane !== "computer_plugin_node_repl" ||
    provenance.interface !== "sky.get_app_state/sky-primitives" ||
    !Array.isArray(provenance.skyMethods) ||
    new Set(provenance.skyMethods).size !== provenance.skyMethods.length ||
    ["click", "paste", "press_key"].some(
      (method) => !provenance.skyMethods.includes(method),
    ) ||
    provenance.skyMethods.some(
      (method) => !sharedComputer.SKY_ACTION_METHODS?.includes(method),
    ) ||
    provenance.appBundleId !== "ru.keepcoder.Telegram"
  ) {
    throw blockedError("computer_bridge_provenance_invalid");
  }
  if (
    provenance.ownerId !== owner?.ownerId ||
    provenance.telegramUserId !== owner.telegramUserId ||
    provenance.telegramChatId !== owner.telegramChatId
  ) {
    throw blockedError("computer_bridge_owner_mismatch");
  }
  if (
    provenance.sessionRef !== parent.sessionRef ||
    provenance.qaSessionRef !== identity.sessionRef ||
    provenance.peerProcessId !== parent.peerProcessId ||
    provenance.authorityKeyId !== parent.keyId
  ) {
    throw blockedError("computer_bridge_session_mismatch");
  }
  const now = Date.now();
  if (
    !Number.isSafeInteger(provenance.issuedAtMs) ||
    !Number.isSafeInteger(provenance.expiresAtMs) ||
    provenance.issuedAtMs > now ||
    provenance.expiresAtMs <= now ||
    provenance.expiresAtMs - provenance.issuedAtMs > 900_000
  ) {
    throw blockedError("computer_bridge_attestation_expired");
  }
  const { proof, ...unsigned } = provenance;
  if (!verifyParentSignature(parent, unsigned, proof)) {
    throw blockedError("computer_bridge_authentication_failed");
  }
  try {
    return assertTrustedComputerAdapter(driver, owner, parent, {
      caseId: identity.caseId,
      appBundleId: provenance.appBundleId,
    });
  } catch (error) {
    if (error?.message === "computer_desktop_driver_unavailable") {
      throw blockedError("computer_bridge_unavailable");
    }
    throw error;
  }
}

function assertActiveOwnerChat(selection, owner, nowMs = Date.now()) {
  if (
    !object(selection) ||
    selection.source !== "computer_ui_active_selection" ||
    !Number.isSafeInteger(selection.observedAtMs) ||
    selection.observedAtMs > nowMs + 1000 ||
    nowMs - selection.observedAtMs > MAX_SELECTION_AGE_MS
  ) {
    throw blockedError("active_telegram_selection_stale");
  }
  const account = selection.account;
  if (
    !object(account) ||
    account.selected !== true ||
    account.evidence !== "active_account_control" ||
    account.ownerId !== owner?.ownerId ||
    String(account.telegramUserId) !== String(owner.telegramUserId) ||
    account.label !== owner.accountLabel
  ) {
    throw blockedError("active_telegram_account_mismatch");
  }
  const chat = selection.chat;
  if (
    !object(chat) ||
    chat.selected !== true ||
    chat.evidence !== "active_chat_header" ||
    chat.ownerId !== owner.ownerId ||
    String(chat.telegramChatId) !== String(owner.telegramChatId) ||
    chat.label !== owner.chatLabel ||
    (owner.conversationId &&
      chat.conversationRefHash !== sha256(owner.conversationId))
  ) {
    throw blockedError("active_telegram_chat_mismatch");
  }
  if (
    typeof sharedComputer.assertActiveSelectedTelegramContext !== "function"
  ) {
    throw blockedError("external_computer_authority_required");
  }
  sharedComputer.assertActiveSelectedTelegramContext(
    { activeSelection: selection },
    {
      owner: {
        ownerId: owner.ownerId,
        telegramUserId: owner.telegramUserId,
        telegramChatId: owner.telegramChatId,
      },
      telegram: {
        accountLabel: owner.accountLabel,
        chatLabel: owner.chatLabel,
      },
      ...(owner.conversationId
        ? { conversation: { conversationId: owner.conversationId } }
        : {}),
    },
    { nowMs, maxAgeMs: MAX_SELECTION_AGE_MS },
  );
  return selection;
}

async function observeComputer(bridge, owner, method, details = {}) {
  if (
    !SKY_METHODS.includes(method) ||
    !bridge?.binding ||
    (method !== "get_app_state" &&
      !bridge.provenance?.skyMethods?.includes(method))
  ) {
    throw blockedError("computer_sky_method_unsupported");
  }
  let observed;
  try {
    observed = await observeTrustedComputer(
      bridge,
      method === "get_app_state"
        ? {
            kind: "state",
            ...(details.phase ? { phase: details.phase } : {}),
            ...(details.includeScreenshot === true
              ? { includeScreenshot: true }
              : {}),
          }
        : {
            kind: "action",
            skyMethod: method,
            logicalAction: "telegram.send_text",
            payload: details,
          },
    );
  } catch (error) {
    const mapped = new Map([
      [
        "computer_desktop_observation_provenance_invalid",
        "computer_observation_challenge_mismatch",
      ],
      [
        "computer_desktop_observation_authentication_failed",
        "computer_observation_authentication_failed",
      ],
      [
        "computer_desktop_active_account_mismatch",
        "active_telegram_account_mismatch",
      ],
      [
        "computer_desktop_active_chat_mismatch",
        "active_telegram_chat_mismatch",
      ],
      [
        "computer_desktop_active_selection_unavailable",
        "active_telegram_selection_stale",
      ],
    ]).get(error?.message);
    if (mapped) throw blockedError(mapped);
    throw error;
  }
  if (!object(observed) || observed.source !== "@oai/sky." + method) {
    throw blockedError("computer_observation_provenance_invalid");
  }
  const request =
    method === "get_app_state"
      ? {
          ...(details.phase ? { phase: details.phase } : {}),
          ...(details.includeScreenshot === true
            ? { includeScreenshot: true }
            : {}),
          app: bridge.provenance.appBundleId,
          ownerId: owner.ownerId,
          telegramUserId: owner.telegramUserId,
          telegramChatId: owner.telegramChatId,
          sessionRef: bridge.provenance.sessionRef,
          challenge: observed.challenge,
        }
      : {
          ...details,
          action: "telegram.send_text",
          skyMethod: method,
          app: bridge.provenance.appBundleId,
          ownerId: owner.ownerId,
          telegramUserId: owner.telegramUserId,
          telegramChatId: owner.telegramChatId,
          accountLabel: owner.accountLabel,
          chatLabel: owner.chatLabel,
          sessionRef: bridge.provenance.sessionRef,
          selectionChallenge: observed.selectionChallenge,
          selectionSha256: observed.selectionSha256,
          challenge: observed.challenge,
        };
  if (observed.requestSha256 !== sha256(canonicalJson(request))) {
    throw blockedError("computer_observation_request_mismatch");
  }
  if (
    observed.contractVersion !== 1 ||
    observed.app !== bridge.provenance.appBundleId ||
    observed.caseId !== bridge.provenance.caseId ||
    observed.ownerId !== owner.ownerId ||
    observed.telegramUserId !== owner.telegramUserId ||
    observed.telegramChatId !== owner.telegramChatId ||
    observed.sessionRef !== bridge.provenance.sessionRef ||
    observed.qaSessionRef !== bridge.provenance.qaSessionRef ||
    observed.peerProcessId !== bridge.authority.peerProcessId ||
    !Number.isSafeInteger(observed.observedAtMs) ||
    Math.abs(Date.now() - observed.observedAtMs) > MAX_CLOCK_SKEW_MS ||
    (method !== "get_app_state" &&
      (observed.action !== "telegram.send_text" ||
        observed.skyMethod !== method))
  ) {
    throw blockedError("computer_observation_owner_or_selection_mismatch");
  }
  const { proof, screenshotBytes, ...unsigned } = observed;
  if (!verifyParentSignature(bridge.authority, unsigned, proof)) {
    throw blockedError("computer_observation_authentication_failed");
  }
  if (
    screenshotBytes !== undefined &&
    (!Buffer.isBuffer(screenshotBytes) ||
      observed.screenshotSha256 !== sha256(screenshotBytes))
  ) {
    throw blockedError("computer_observation_capture_invalid");
  }
  assertActiveOwnerChat(observed.activeSelection, owner);
  return observed;
}

function assertObservedTelegramScreenshot(observed) {
  const bytes = observed?.screenshotBytes;
  if (
    observed?.source !== "@oai/sky.get_app_state" ||
    !Buffer.isBuffer(bytes) ||
    bytes.length < 128 ||
    bytes.length > 100 * 1024 * 1024 ||
    !SHA256.test(text(observed.screenshotSha256)) ||
    sha256(bytes) !== observed.screenshotSha256 ||
    !bytes.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]))
  ) {
    throw blockedError("private_installed_surface_capture_unavailable");
  }
  return {
    challenge: observed.challenge,
    screenshotSha256: observed.screenshotSha256,
  };
}

async function sendTelegramText(bridge, owner, value) {
  if (!text(value) || Buffer.byteLength(value, "utf8") > 4096) {
    throw blockedError("synthetic_telegram_message_invalid");
  }
  await observeComputer(bridge, owner, "paste", { text: value });
  await observeComputer(bridge, owner, "press_key", { key: "Enter" });
  return { submitted: true, ownerId: owner.ownerId };
}

function assertIdentity(identity) {
  if (
    !object(identity) ||
    !CASE_IDS.has(identity.caseId) ||
    !OWNER_ID.test(text(identity.ownerId)) ||
    !/^qa_[a-f0-9]{24}$/.test(text(identity.sessionRef)) ||
    !SHA256.test(text(identity.candidateDigest)) ||
    !SHA256.test(text(identity.artifactDigest)) ||
    !SHA256_REF.test(text(identity.componentArtifactDigest))
  ) {
    throw blockedError("candidate_or_session_binding_invalid");
  }
  return identity;
}

function assertExactServiceAcknowledgements(status, identity) {
  const expected = assertIdentity(identity);
  if (
    !object(status) ||
    status.caseId !== expected.caseId ||
    status.sessionRef !== expected.sessionRef ||
    status.candidateDigest !== expected.candidateDigest ||
    status.artifactDigest !== expected.artifactDigest ||
    status.componentArtifactDigest !== expected.componentArtifactDigest
  ) {
    throw blockedError("candidate_or_session_binding_invalid");
  }
  const services = REQUIRED_SERVICES[expected.caseId];
  const exact = (values) =>
    Array.isArray(values) &&
    values.length === services.length &&
    new Set(values).size === services.length &&
    services.every((service) => values.includes(service));
  if (
    status.restartState !== "ready" ||
    !exact(status.requiredServices) ||
    !exact(status.acknowledgedServices) ||
    !Array.isArray(status.missingServices) ||
    status.missingServices.length ||
    !SHA256_REF.test(text(status.serviceAckDigest))
  ) {
    throw blockedError("exact_service_acknowledgements_unavailable");
  }
  return {
    serviceCount: services.length,
    serviceAckDigest: status.serviceAckDigest,
  };
}

function assessPinnedCapsules(observation, ownerId) {
  if (
    !object(observation) ||
    observation.ownerId !== ownerId ||
    !Array.isArray(observation.scenarios) ||
    observation.scenarios.length !== SCENARIOS.length
  ) {
    throw blockedError("all_feelings_scope_scenarios_required");
  }
  const privacy = observation.privacyAudit;
  if (
    !object(privacy) ||
    privacy.hostPluginDenylistEnabled !== true ||
    [
      "privateStateMountCount",
      "privateStatePersistenceCount",
      "privateCapsuleProjectionCount",
      "feelingsMcpServerCount",
      "workerFeelingsPluginCount",
    ].some((field) => privacy[field] !== 0)
  ) {
    throw blockedError("feelings_private_state_isolation_failed");
  }
  const seen = new Set();
  const workers = new Set();
  let workerCount = 0;
  for (const expected of SCENARIOS) {
    const matching = observation.scenarios.filter(
      (scenario) => scenario?.name === expected.name,
    );
    if (matching.length !== 1 || seen.has(expected.name)) {
      throw blockedError("all_feelings_scope_scenarios_required");
    }
    const scenario = matching[0];
    seen.add(expected.name);
    if (
      scenario.scope !== expected.scope ||
      scenario.feelingsEnabled !== expected.enabled ||
      (expected.enabled && !SHA256.test(text(scenario.snapshotHash))) ||
      (!expected.enabled && scenario.snapshotHash !== "none")
    ) {
      throw blockedError("request_pinned_feeling_snapshot_invalid");
    }
    const main = scenario.main;
    if (
      !object(main) ||
      main.ownerId !== ownerId ||
      main.snapshotHash !== scenario.snapshotHash ||
      main.capsuleOccurrenceCount !== (expected.enabled ? 1 : 0) ||
      main.winningNativeReceiptVerified !== true
    ) {
      throw blockedError("main_pinned_capsule_or_native_receipt_invalid");
    }
    if (
      !Array.isArray(scenario.workers) ||
      scenario.workers.length !== expected.workers
    ) {
      throw blockedError("direct_worker_pinned_capsule_invalid");
    }
    for (const worker of scenario.workers) {
      if (
        worker?.hostPluginDenylistEnabled !== true ||
        worker.privateStateMountCount !== 0 ||
        worker.feelingsMcpServerCount !== 0
      ) {
        throw blockedError("feelings_private_state_isolation_failed");
      }
      const expectedCount =
        expected.enabled && expected.scope === "all_agents" ? 1 : 0;
      if (worker.capsuleOccurrenceCount !== expectedCount) {
        throw blockedError(
          expectedCount
            ? "direct_worker_pinned_capsule_invalid"
            : "direct_worker_scope_violation",
        );
      }
      if (
        worker.ownerId !== ownerId ||
        worker.snapshotHash !== scenario.snapshotHash ||
        worker.nativeReceiptVerified !== true ||
        !text(worker.workRef) ||
        !text(worker.runRef) ||
        workers.has(worker.workRef)
      ) {
        throw blockedError("direct_worker_pinned_capsule_invalid");
      }
      workers.add(worker.workRef);
      workerCount += 1;
    }
  }
  return {
    scenarioCount: SCENARIOS.length,
    mainReceiptCount: SCENARIOS.length,
    workerReceiptCount: workerCount,
    allAgentsDirectWorkerCount: 2,
    pinned: true,
  };
}

function exactInsightSurfaces(surfaces, ownerId) {
  return (
    Array.isArray(surfaces) &&
    surfaces.length === 2 &&
    new Set(surfaces.map((surface) => surface?.surface)).size === 2 &&
    ["web", "telegram"].every((name) =>
      surfaces.some(
        (surface) =>
          surface?.surface === name &&
          surface.ownerId === ownerId &&
          surface.visibleCount === 1,
      ),
    )
  );
}

function assessInsightRecovery(observation, ownerId) {
  if (
    !object(observation) ||
    observation.ownerId !== ownerId ||
    !object(observation.graph) ||
    observation.graph.status !== "completed" ||
    !text(observation.graph.completionId) ||
    !SHA256.test(text(observation.graph.resultSha256))
  ) {
    throw blockedError("completed_emotional_insight_unavailable");
  }
  const first = observation.firstFailure;
  if (
    !object(first) ||
    first.errorCode !== "cortex_insight_delivery_ledger_write_failed" ||
    first.retryable !== true ||
    first.outboxState !== "pending" ||
    first.terminalPresentationCount !== 0
  ) {
    throw blockedError("first_persistence_failure_unproven");
  }
  if (
    !Array.isArray(observation.boundaries) ||
    observation.boundaries.length !== BOUNDARIES.length ||
    new Set(observation.boundaries.map((row) => row?.boundary)).size !==
      BOUNDARIES.length ||
    BOUNDARIES.some(
      (boundary) =>
        !observation.boundaries.some(
          (row) => row?.boundary === boundary && row.state === "consumed",
        ),
    )
  ) {
    throw blockedError("all_emotional_fault_boundaries_required");
  }
  const restart = observation.restart;
  if (
    !object(restart) ||
    restart.parentAuthorized !== true ||
    restart.occurredWhilePending !== true ||
    !SHA256.test(text(restart.beforeCoreProcessRefHash)) ||
    !SHA256.test(text(restart.afterCoreProcessRefHash)) ||
    restart.beforeCoreProcessRefHash === restart.afterCoreProcessRefHash ||
    !SHA256_REF.test(text(restart.beforeServiceAckDigest)) ||
    !SHA256_REF.test(text(restart.afterServiceAckDigest)) ||
    restart.beforeServiceAckDigest === restart.afterServiceAckDigest
  ) {
    throw blockedError("authorized_pending_core_restart_unproven");
  }
  const delivery = observation.delivery;
  if (
    !object(delivery) ||
    delivery.status !== "sent" ||
    delivery.presentationCount !== 1 ||
    delivery.resultSha256 !== observation.graph.resultSha256 ||
    !text(delivery.messageId) ||
    !exactInsightSurfaces(delivery.surfaces, ownerId)
  ) {
    throw blockedError("linked_insight_delivery_not_exactly_once");
  }
  const replay = observation.replay;
  if (
    !object(replay) ||
    replay.resultSha256 !== observation.graph.resultSha256 ||
    replay.presentationCount !== 1 ||
    replay.messageId !== delivery.messageId ||
    !exactInsightSurfaces(replay.surfaces, ownerId)
  ) {
    throw blockedError("insight_replay_was_not_idempotent");
  }
  if (
    !object(observation.terminalProbe) ||
    observation.terminalProbe.status !== "dropped" ||
    !/^[a-z][a-z0-9_]{0,95}$/.test(text(observation.terminalProbe.reason))
  ) {
    throw blockedError("typed_terminal_drop_unproven");
  }
  return {
    boundaries: BOUNDARIES.length,
    completed: true,
    restartedWhilePending: true,
    surfaces: 2,
    deliveredExactlyOnce: true,
    replayDuplicated: false,
    typedTerminalProbe: true,
  };
}

function assertPrivateEvidenceRoot(location) {
  if (!text(location)) throw blockedError("private_evidence_root_required");
  let root;
  let metadata;
  try {
    root = fs.realpathSync(path.resolve(location));
    metadata = fs.lstatSync(path.resolve(location));
  } catch {
    throw blockedError("private_evidence_path_invalid");
  }
  const repository = fs.realpathSync(ROOT);
  const relative = path.relative(repository, root);
  if (
    !relative ||
    (!relative.startsWith(".." + path.sep) && relative !== "..")
  ) {
    throw blockedError("private_evidence_must_stay_outside_repository");
  }
  if (
    metadata.isSymbolicLink() ||
    !metadata.isDirectory() ||
    metadata.uid !== process.getuid() ||
    (metadata.mode & 0o777) !== 0o700
  ) {
    throw blockedError("private_evidence_permissions_invalid");
  }
  return root;
}

function assertExistingPrivateEvidence(location, root) {
  const privateRoot = assertPrivateEvidenceRoot(root);
  const original = path.resolve(text(location));
  let suppliedRelative = path.relative(privateRoot, original);
  if (
    suppliedRelative === ".." ||
    suppliedRelative.startsWith(".." + path.sep) ||
    path.isAbsolute(suppliedRelative)
  ) {
    suppliedRelative = path.relative(path.resolve(text(root)), original);
  }
  if (
    !suppliedRelative ||
    suppliedRelative === ".." ||
    suppliedRelative.startsWith(".." + path.sep) ||
    path.isAbsolute(suppliedRelative)
  ) {
    throw blockedError("private_evidence_path_invalid");
  }
  const supplied = path.join(privateRoot, suppliedRelative);
  let metadata;
  let resolved;
  try {
    let parent = privateRoot;
    for (const segment of suppliedRelative.split(path.sep).slice(0, -1)) {
      parent = path.join(parent, segment);
      const directory = fs.lstatSync(parent);
      if (
        directory.isSymbolicLink() ||
        !directory.isDirectory() ||
        directory.uid !== process.getuid() ||
        (directory.mode & 0o777) !== 0o700
      ) {
        throw blockedError("private_evidence_permissions_invalid");
      }
    }
    metadata = fs.lstatSync(supplied);
    if (metadata.isSymbolicLink())
      throw blockedError("private_evidence_path_invalid");
    resolved = fs.realpathSync(supplied);
  } catch (error) {
    if (error?.blocked) throw error;
    throw blockedError("private_evidence_path_invalid");
  }
  const relative = path.relative(privateRoot, resolved);
  if (
    !relative ||
    relative === ".." ||
    relative.startsWith(".." + path.sep) ||
    path.isAbsolute(relative)
  ) {
    throw blockedError("private_evidence_path_invalid");
  }
  if (
    !metadata.isFile() ||
    metadata.uid !== process.getuid() ||
    (metadata.mode & 0o777) !== 0o600 ||
    metadata.nlink !== 1 ||
    metadata.size > 100 * 1024 * 1024
  ) {
    throw blockedError("private_evidence_permissions_invalid");
  }
  return resolved;
}

function exactObjectKeys(value, expected) {
  return (
    object(value) &&
    Object.keys(value).length === expected.length &&
    expected.every((key) => Object.hasOwn(value, key))
  );
}

function readPrivateEvidenceSnapshot(location, root, maxBytes = 100 * 1024 * 1024) {
  const exact = assertExistingPrivateEvidence(location, root);
  const descriptor = fs.openSync(
    exact,
    fs.constants.O_RDONLY | (fs.constants.O_NOFOLLOW || 0),
  );
  try {
    const before = fs.fstatSync(descriptor);
    if (
      !before.isFile() ||
      before.uid !== process.getuid() ||
      (before.mode & 0o777) !== 0o600 ||
      before.nlink !== 1 ||
      before.size <= 0 ||
      before.size > maxBytes
    ) {
      throw blockedError("private_evidence_permissions_invalid");
    }
    const bytes = fs.readFileSync(descriptor);
    const after = fs.fstatSync(descriptor);
    const current = fs.lstatSync(exact);
    if (
      bytes.length !== before.size ||
      before.dev !== after.dev ||
      before.ino !== after.ino ||
      before.size !== after.size ||
      before.mtimeMs !== after.mtimeMs ||
      current.isSymbolicLink() ||
      current.dev !== before.dev ||
      current.ino !== before.ino ||
      current.nlink !== 1
    ) {
      throw blockedError("private_evidence_path_invalid");
    }
    return { bytes, sha256: sha256(bytes), path: exact };
  } finally {
    fs.closeSync(descriptor);
  }
}

function readPrivateJsonEvidence(location, root) {
  const snapshot = readPrivateEvidenceSnapshot(location, root, 256 * 1024);
  const parsed = JSON.parse(snapshot.bytes.toString("utf8"));
  if (!object(parsed)) throw blockedError("private_evidence_path_invalid");
  return { ...snapshot, parsed };
}

function normalizedVerifierEvidence(entries, root, { identified = false } = {}) {
  if (!Array.isArray(entries) || entries.length === 0) {
    throw blockedError("independent_semantic_verifier_did_not_pass");
  }
  const documents = new Map();
  const normalized = [];
  const paths = new Set();
  const identifiers = new Set();
  for (const entry of entries) {
    if (
      !exactObjectKeys(
        entry,
        identified ? ["id", "kind", "path", "sha256"] : ["kind", "path", "sha256"],
      ) ||
      !text(entry.kind) ||
      !SHA256.test(text(entry.sha256)) ||
      !text(entry.path) ||
      path.isAbsolute(entry.path) ||
      entry.path.split("/").some((part) => !part || part === "." || part === "..")
    ) {
      throw blockedError("independent_semantic_verifier_did_not_pass");
    }
    const identifier = identified ? entry.id : entry.kind;
    if (
      !text(identifier) ||
      (identified && identifiers.has(identifier)) ||
      paths.has(entry.path)
    ) {
      throw blockedError("independent_semantic_verifier_did_not_pass");
    }
    const snapshot = readPrivateEvidenceSnapshot(path.join(root, entry.path), root);
    if (snapshot.sha256 !== entry.sha256) {
      throw blockedError("independent_semantic_verifier_did_not_pass");
    }
    if (!new Set(["browser_screenshot", "telegram_screenshot"]).has(entry.kind)) {
      const parsed = JSON.parse(snapshot.bytes.toString("utf8"));
      if (!object(parsed)) {
        throw blockedError("independent_semantic_verifier_did_not_pass");
      }
      documents.set(identifier, parsed);
    }
    normalized.push({
      kind: entry.kind,
      path: entry.path,
      sha256: entry.sha256,
    });
    identifiers.add(identifier);
    paths.add(entry.path);
  }
  normalized.sort((left, right) => {
    const kind = left.kind < right.kind ? -1 : left.kind > right.kind ? 1 : 0;
    return kind || (left.path < right.path ? -1 : left.path > right.path ? 1 : 0);
  });
  return { documents, entries: normalized, identifiers };
}

function assertVerifierEvidenceBinding(caseId, manifest, session, root, fixtureRef) {
  if (manifest.caseId !== caseId || manifest.contractVersion !== 1) {
    throw blockedError("independent_semantic_verifier_did_not_pass");
  }
  const identified = caseId === CASE_048;
  const normalized = normalizedVerifierEvidence(manifest.evidence, root, {
    identified,
  });
  if (caseId === CASE_047) {
    const required = [
      "feelings_control_projection",
      "feelings_semantic_receipts",
      "feelings_service_acknowledgement",
    ];
    if (
      !exactObjectKeys(manifest, [
        "candidate",
        "caseId",
        "contractVersion",
        "environment",
        "evidence",
        "runAt",
      ]) ||
      manifest.environment !== "installed_local_production" ||
      !exactObjectKeys(manifest.candidate, ["candidateDigest", "artifactDigest"]) ||
      manifest.candidate.candidateDigest !== session.candidateDigest ||
      manifest.candidate.artifactDigest !== session.artifactDigest ||
      normalized.entries.length !== required.length ||
      normalized.identifiers.size !== required.length ||
      required.some((kind) => !normalized.identifiers.has(kind))
    ) {
      throw blockedError("independent_semantic_verifier_did_not_pass");
    }
    let artifactIdentityDigest = "";
    for (const kind of required) {
      const document = normalized.documents.get(kind);
      if (
        document?.caseId !== caseId ||
        document.sessionRef !== session.sessionRef ||
        document.componentArtifactDigest !== session.componentArtifactDigest ||
        !SHA256_REF.test(text(document.artifactIdentityDigest)) ||
        (artifactIdentityDigest &&
          document.artifactIdentityDigest !== artifactIdentityDigest) ||
        (Object.hasOwn(document, "ownerId") &&
          document.ownerId !== session.ownerId)
      ) {
        throw blockedError("independent_semantic_verifier_did_not_pass");
      }
      artifactIdentityDigest = document.artifactIdentityDigest;
    }
    if (normalized.documents.get("feelings_control_projection").synthetic !== true) {
      throw blockedError("independent_semantic_verifier_did_not_pass");
    }
    return normalized;
  }

  if (
    !exactObjectKeys(manifest, [
      "capturedAt",
      "caseId",
      "contractVersion",
      "evidence",
      "fixtureRef",
    ]) ||
    !/^emo048_fixture_[a-f0-9]{24}$/.test(text(manifest.fixtureRef)) ||
    (fixtureRef && manifest.fixtureRef !== fixtureRef) ||
    normalized.identifiers.size !== Object.keys(EMO_048_EVIDENCE).length ||
    Object.entries(EMO_048_EVIDENCE).some(
      ([id, kind]) =>
        !normalized.identifiers.has(id) ||
        !manifest.evidence.some((entry) => entry.id === id && entry.kind === kind),
    )
  ) {
    throw blockedError("independent_semantic_verifier_did_not_pass");
  }
  const completion = normalized.documents.get("completion-record");
  const controls = normalized.documents.get("fault-controls");
  const restart = normalized.documents.get("restart-acknowledgements");
  const ownerScopeHash = "sha256:" + sha256("owner\0" + session.ownerId);
  if (
    completion?.caseId !== caseId ||
    completion.ownerId !== session.ownerId ||
    controls?.caseId !== caseId ||
    controls.fixtureRef !== manifest.fixtureRef ||
    controls.sessionRef !== session.sessionRef ||
    !Array.isArray(controls.controls) ||
    controls.controls.length !== BOUNDARIES.length ||
    new Set(controls.controls.map((entry) => entry?.boundary)).size !==
      BOUNDARIES.length ||
    controls.controls.some(
      (entry) =>
        !BOUNDARIES.includes(entry?.boundary) ||
        entry.ownerScopeHash !== ownerScopeHash ||
        entry.syntheticScope !== true,
    ) ||
    restart?.caseId !== caseId ||
    restart.sessionRef !== session.sessionRef ||
    !Array.isArray(restart.checkpoints) ||
    restart.checkpoints.length === 0
  ) {
    throw blockedError("independent_semantic_verifier_did_not_pass");
  }
  let artifactIdentityDigest = "";
  for (const checkpoint of restart.checkpoints) {
    if (!Array.isArray(checkpoint?.services) || checkpoint.services.length !== 2) {
      throw blockedError("independent_semantic_verifier_did_not_pass");
    }
    const services = new Set();
    for (const service of checkpoint.services) {
      if (
        service?.caseId !== caseId ||
        !REQUIRED_SERVICES[caseId].includes(service.serviceId) ||
        services.has(service.serviceId) ||
        service.sessionRef !== session.sessionRef ||
        service.componentArtifactDigest !== session.componentArtifactDigest ||
        !SHA256_REF.test(text(service.artifactIdentityDigest)) ||
        (artifactIdentityDigest &&
          service.artifactIdentityDigest !== artifactIdentityDigest)
      ) {
        throw blockedError("independent_semantic_verifier_did_not_pass");
      }
      artifactIdentityDigest = service.artifactIdentityDigest;
      services.add(service.serviceId);
    }
  }
  return normalized;
}

function assertSemanticVerifierOutput(caseId, output, session, documents) {
  if (caseId === CASE_047) {
    const expectedCounts = {
      fallbackAttemptCount: 2,
      mainReceiptCount: 4,
      phaseBReceiptCount: 1,
      scenarioCount: 4,
      semanticPassCount: 4,
      specialistReceiptCount: REQUIRED_SPECIALISTS.size,
      workerReceiptCount: 6,
    };
    if (
      !exactObjectKeys(output, [
        "artifactDigest",
        "blockers",
        "candidateDigest",
        "caseId",
        "contractVersion",
        "counts",
        "gates",
        "ready",
        "runAt",
        "serviceAckDigest",
        "status",
        "surface",
      ]) ||
      output.caseId !== caseId ||
      output.contractVersion !== 1 ||
      output.status !== "PASS" ||
      output.ready !== true ||
      output.surface !== "telegram" ||
      output.candidateDigest !== session.candidateDigest ||
      output.artifactDigest !== session.artifactDigest ||
      !Array.isArray(output.blockers) ||
      output.blockers.length !== 0 ||
      !exactObjectKeys(output.counts, Object.keys(expectedCounts)) ||
      Object.entries(expectedCounts).some(
        ([name, count]) => output.counts[name] !== count,
      ) ||
      !Array.isArray(output.gates) ||
      output.gates.length !== EMO_047_GATES.length ||
      output.gates.some(
        (gate, index) =>
          !exactObjectKeys(gate, ["id", "status"]) ||
          gate.id !== EMO_047_GATES[index] ||
          gate.status !== "PASS",
      ) ||
      output.serviceAckDigest !==
        documents.get("feelings_service_acknowledgement")?.serviceAckDigest
    ) {
      throw blockedError("independent_semantic_verifier_did_not_pass");
    }
    return;
  }
  if (
    !exactObjectKeys(output, ["caseId", "checks", "failureCodes", "status"]) ||
    output.caseId !== caseId ||
    output.status !== "PASS" ||
    !Array.isArray(output.failureCodes) ||
    output.failureCodes.length !== 0 ||
    !Array.isArray(output.checks) ||
    output.checks.length !== EMO_048_CHECKS.length ||
    output.checks.some(
      (check, index) =>
        !exactObjectKeys(check, ["id", "status"]) ||
        check.id !== EMO_048_CHECKS[index] ||
        check.status !== "PASS",
    )
  ) {
    throw blockedError("independent_semantic_verifier_did_not_pass");
  }
}

function assertGeneratedVerifierReceipt({
  caseId,
  receiptPath,
  evidencePath,
  evidenceRoot,
  manifest,
  evidence,
  output,
}) {
  const receipt = readPrivateJsonEvidence(receiptPath, evidenceRoot).parsed;
  const verifierId =
    caseId === CASE_047 ? "emo047-semantic-v1" : "emo048-semantic-v1";
  const expectedRunAt = caseId === CASE_047 ? output.runAt : manifest.capturedAt;
  if (
    !exactObjectKeys(receipt, [
      "caseId",
      "contractVersion",
      "evidence",
      "runAt",
      "status",
      "surface",
      "verifier",
    ]) ||
    receipt.caseId !== caseId ||
    receipt.contractVersion !== 1 ||
    receipt.status !== "PASS" ||
    receipt.surface !== "telegram" ||
    !exactObjectKeys(receipt.verifier, ["id", "manifest"]) ||
    receipt.verifier.id !== verifierId ||
    receipt.verifier.manifest !== path.relative(evidenceRoot, evidencePath) ||
    !Number.isFinite(Date.parse(receipt.runAt)) ||
    Date.parse(receipt.runAt) !== Date.parse(expectedRunAt) ||
    canonicalJson(receipt.evidence) !== canonicalJson(evidence.entries)
  ) {
    throw blockedError("independent_semantic_verifier_did_not_pass");
  }
  normalizedVerifierEvidence(receipt.evidence, evidenceRoot);
  return receipt;
}

function runIndependentVerifier(
  caseId,
  {
    evidenceRoot,
    evidencePath,
    identity,
    owner,
    fixtureRef,
    serviceStatus,
    spawn = spawnSync,
  } = {},
) {
  if (!CASE_IDS.has(caseId)) throw blockedError("unsupported_case");
  try {
    const session = assertIdentity(identity);
    if (
      session.caseId !== caseId ||
      !object(owner) ||
      owner.synthetic !== true ||
      owner.ownerId !== session.ownerId
    ) {
      throw blockedError("independent_semantic_verifier_did_not_pass");
    }
    const acknowledgement = assertExactServiceAcknowledgements(
      serviceStatus,
      session,
    );
    const root = assertPrivateEvidenceRoot(evidenceRoot);
    const evidence = assertExistingPrivateEvidence(evidencePath, evidenceRoot);
    const manifestSnapshot = readPrivateJsonEvidence(evidence, root);
    const manifest = manifestSnapshot.parsed;
    const boundEvidence = assertVerifierEvidenceBinding(
      caseId,
      manifest,
      session,
      root,
      fixtureRef,
    );
    const evidenceAckDigest =
      caseId === CASE_047
        ? boundEvidence.documents.get("feelings_service_acknowledgement")
            ?.serviceAckDigest
        : "sha256:" +
          sha256(
            canonicalJson(
              boundEvidence.documents
                .get("restart-acknowledgements")
                .checkpoints.at(-1).services,
            ),
          );
    if (evidenceAckDigest !== acknowledgement.serviceAckDigest) {
      throw blockedError("independent_semantic_verifier_did_not_pass");
    }
    const receipt = path.join(
      root,
      caseId === CASE_047
        ? "emo-uc-047-independent-receipt.json"
        : "emo-uc-048-independent-receipt.json",
    );
    try {
      fs.lstatSync(receipt);
      throw blockedError("independent_semantic_verifier_did_not_pass");
    } catch (error) {
      if (error?.blocked || error?.code !== "ENOENT") throw error;
    }
    const script = path.join(
      __dirname,
      caseId === CASE_047 ? "run_emo_uc_047.py" : "run_emo_uc_048.py",
    );
    const arguments_ =
      caseId === CASE_047
        ? ["-c", EMO_047_RECEIPT_BRIDGE, script, evidence, root, receipt]
        : [
            script,
            "--capture",
            evidence,
            "--evidence-root",
            root,
            "--receipt",
            receipt,
          ];
    const verifierEnvironment = { ...process.env };
    for (const key of PROHIBITED_VERIFIER_ENVIRONMENT)
      delete verifierEnvironment[key];
    const outcome = spawn("python3", arguments_, {
      cwd: ROOT,
      encoding: "utf8",
      env: verifierEnvironment,
      timeout: 120_000,
      maxBuffer: 256 * 1024,
      windowsHide: true,
    });
    if (outcome?.error || outcome.status !== 0) {
      throw blockedError("independent_semantic_verifier_did_not_pass");
    }
    const parsed = JSON.parse(text(outcome.stdout));
    assertSemanticVerifierOutput(caseId, parsed, session, boundEvidence.documents);
    if (readPrivateJsonEvidence(evidence, root).sha256 !== manifestSnapshot.sha256) {
      throw blockedError("independent_semantic_verifier_did_not_pass");
    }
    assertGeneratedVerifierReceipt({
      caseId,
      receiptPath: receipt,
      evidencePath: evidence,
      evidenceRoot: root,
      manifest,
      evidence: boundEvidence,
      output: parsed,
    });
    return parsed;
  } catch {
    throw blockedError("independent_semantic_verifier_did_not_pass");
  }
}

function createAuthenticatedCapabilityContext({ authority, identity, owner }) {
  const parent = assertExternalAuthority(authority);
  const session = assertIdentity(identity);
  if (!object(owner) || owner.ownerId !== session.ownerId) {
    throw blockedError("external_capability_owner_or_session_mismatch");
  }
  return {
    authority: parent,
    identity: session,
    owner,
    consumedChallenges: new Set(),
  };
}

async function invokeAuthenticatedCapability(
  context,
  name,
  capability,
  action,
  payload = {},
) {
  if (
    !CAPABILITIES.has(name) ||
    !object(capability) ||
    typeof capability.invoke !== "function"
  ) {
    throw blockedError("authenticated_external_capability_unavailable");
  }
  if (!SAFE_CODE.test(text(action)) || !object(payload)) {
    throw blockedError("external_capability_action_invalid");
  }
  const challenge = crypto.randomBytes(32).toString("hex");
  const request = {
    capability: name,
    action,
    caseId: context.identity.caseId,
    ownerId: context.owner.ownerId,
    sessionRef: context.identity.sessionRef,
    candidateDigest: context.identity.candidateDigest,
    artifactDigest: context.identity.artifactDigest,
    componentArtifactDigest: context.identity.componentArtifactDigest,
    challenge,
    payload,
  };
  const result = await capability.invoke(request);
  if (
    !object(result) ||
    result.contractVersion !== 1 ||
    result.capability !== name ||
    result.action !== action ||
    result.caseId !== context.identity.caseId ||
    result.ownerId !== context.owner.ownerId ||
    result.sessionRef !== context.identity.sessionRef ||
    result.candidateDigest !== context.identity.candidateDigest ||
    result.artifactDigest !== context.identity.artifactDigest ||
    result.componentArtifactDigest !==
      context.identity.componentArtifactDigest ||
    result.peerProcessId !== context.authority.peerProcessId
  ) {
    throw blockedError("external_capability_owner_or_session_mismatch");
  }
  if (result.requestSha256 !== sha256(canonicalJson(request))) {
    throw blockedError("external_capability_request_mismatch");
  }
  if (
    result.challenge !== challenge ||
    context.consumedChallenges.has(challenge) ||
    !Number.isSafeInteger(result.observedAtMs) ||
    Math.abs(Date.now() - result.observedAtMs) > MAX_CLOCK_SKEW_MS ||
    !object(result.result)
  ) {
    throw blockedError("external_capability_receipt_invalid");
  }
  const { proof, ...unsigned } = result;
  if (!verifyParentSignature(context.authority, unsigned, proof)) {
    throw blockedError("external_capability_authentication_failed");
  }
  context.consumedChallenges.add(challenge);
  return result.result;
}

async function invokeOwnerGuardedCapability({
  context,
  bridge,
  owner,
  capabilities,
  name,
  action,
  payload = {},
}) {
  if (
    !object(owner) ||
    owner.ownerId !== context?.owner?.ownerId ||
    !object(capabilities)
  ) {
    throw blockedError("external_capability_owner_or_session_mismatch");
  }
  if (!READ_ONLY_OPERATIONS.has(name + ":" + action)) {
    await observeComputer(bridge, owner, "get_app_state");
  }
  return invokeAuthenticatedCapability(
    context,
    name,
    capabilities[name],
    action,
    payload,
  );
}

async function cleanupSyntheticEffects({
  caseId,
  owner,
  fixtureRef,
  baselineStateDigest,
  invoke,
}) {
  if (
    !CASE_IDS.has(caseId) ||
    !object(owner) ||
    !OWNER_ID.test(text(owner.ownerId)) ||
    owner.synthetic !== true
  ) {
    throw blockedError("synthetic_owner_cleanup_unverified");
  }
  if (typeof invoke !== "function" || !text(fixtureRef)) {
    throw blockedError("synthetic_owner_cleanup_unverified");
  }
  if (caseId === CASE_047 && !SHA256.test(text(baselineStateDigest))) {
    throw blockedError("synthetic_owner_cleanup_unverified");
  }
  const scope = { ownerId: owner.ownerId, fixtureRef };
  const cleared = await invoke("parent_control", "clear_faults", scope);
  if (
    !object(cleared) ||
    cleared.ownerId !== owner.ownerId ||
    !Number.isSafeInteger(cleared.cleared) ||
    cleared.cleared < 0
  ) {
    throw blockedError("synthetic_owner_cleanup_unverified");
  }
  if (caseId === CASE_047) {
    const restored = await invoke("parent_control", "restore_feelings", {
      ...scope,
      expectedStateDigest: baselineStateDigest,
    });
    if (
      !object(restored) ||
      restored.ownerId !== owner.ownerId ||
      restored.fixtureRef !== fixtureRef ||
      restored.restored !== true ||
      restored.restoredStateDigest !== baselineStateDigest
    ) {
      throw blockedError("synthetic_owner_cleanup_unverified");
    }
  }
  const result = await invoke("parent_control", "cleanup_fixture", scope);
  if (
    !object(result) ||
    result.cleaned !== true ||
    result.ownerId !== owner.ownerId ||
    result.remainingRecords !== 0
  ) {
    throw blockedError("synthetic_owner_cleanup_unverified");
  }
  return { cleaned: true, remainingRecords: 0 };
}

async function executePinnedFeelingsJourney({
  invoke,
  bridge,
  owner,
  fixtureRef,
  evidenceRoot,
}) {
  if (!text(fixtureRef)) {
    throw blockedError("parent_owned_synthetic_fixture_unavailable");
  }
  const scenarios = [];
  let privacyAudit;
  const scope = { ownerId: owner.ownerId, fixtureRef };
  async function configure(expected) {
    const configuration = await invoke("parent_control", "configure_feelings", {
      ...scope,
      scenario: expected.name,
      scope: expected.scope,
      enabled: expected.enabled,
    });
    if (
      configuration.ownerId !== owner.ownerId ||
      configuration.scenario !== expected.name
    ) {
      throw blockedError("parent_feelings_configuration_unverified");
    }
  }
  async function observeWorkers(expected) {
    const active = await invoke("glasshive", "observe_running_workers", {
      ...scope,
      scenario: expected.name,
    });
    if (
      active.ownerId !== owner.ownerId ||
      !Array.isArray(active.workers) ||
      active.workers.length !== 2 ||
      active.workers.some(
        (worker) =>
          worker?.ownerId !== owner.ownerId ||
          worker.runtimeInvoked !== true ||
          worker.leaseActive !== true,
      )
    ) {
      throw blockedError("two_real_running_direct_workers_required");
    }
  }
  async function captureScenario(expected) {
    const visible = await invoke("browser", "observe_visible_response", {
      ...scope,
      scenario: expected.name,
    });
    if (visible.ownerId !== owner.ownerId || visible.visible !== true) {
      throw blockedError("visible_feelings_answer_unavailable");
    }
    const captured = await invoke("evidence", "observe_feelings_scenario", {
      ...scope,
      scenario: expected.name,
    });
    if (
      !object(captured.scenario) ||
      captured.scenario.name !== expected.name
    ) {
      throw blockedError("provider_bound_feelings_observation_unavailable");
    }
    scenarios.push(captured.scenario);
    privacyAudit = captured.privacyAudit || privacyAudit;
  }
  const first = SCENARIOS[0];
  const second = SCENARIOS[1];
  await configure(first);
  const armed = await invoke("parent_control", "arm_provider_fallback", {
    ...scope,
    scenario: first.name,
    failureClass: "provider_quota_exhausted",
    holdUntilSecondRequestPinned: true,
  });
  if (
    armed.ownerId !== owner.ownerId ||
    armed.state !== "armed" ||
    armed.failureClass !== "provider_quota_exhausted" ||
    armed.heldUntilSecondRequestPinned !== true
  ) {
    throw blockedError("parent_owned_provider_fallback_unverified");
  }
  await sendTelegramText(bridge, owner, "How are you feeling?");
  const firstActive = await invoke(
    "evidence",
    "observe_active_feelings_request",
    { ...scope, scenario: first.name },
  );
  if (
    firstActive.ownerId !== owner.ownerId ||
    !SHA256_REF.test(text(firstActive.requestRef)) ||
    !SHA256.test(text(firstActive.snapshotHash)) ||
    firstActive.active !== true ||
    firstActive.providerStarted !== true ||
    firstActive.presentationCommitted !== false
  ) {
    throw blockedError("first_pinned_request_not_active");
  }
  await configure(second);
  const changed = await invoke(
    "parent_control",
    "advance_synthetic_feelings_state",
    {
      ...scope,
      requestRef: firstActive.requestRef,
      expectedSnapshotHash: firstActive.snapshotHash,
    },
  );
  if (
    changed.ownerId !== owner.ownerId ||
    changed.changed !== true ||
    changed.previousSnapshotHash !== firstActive.snapshotHash ||
    !SHA256.test(text(changed.snapshotHash)) ||
    changed.snapshotHash === firstActive.snapshotHash
  ) {
    throw blockedError("synthetic_feelings_state_change_unverified");
  }
  await sendTelegramText(
    bridge,
    owner,
    "Please create two distinct small HTML pages in parallel and remain available to chat. How are you feeling?",
  );
  await observeWorkers(second);
  const secondActive = await invoke(
    "evidence",
    "observe_active_feelings_request",
    { ...scope, scenario: second.name },
  );
  if (
    secondActive.ownerId !== owner.ownerId ||
    !SHA256_REF.test(text(secondActive.requestRef)) ||
    secondActive.requestRef === firstActive.requestRef ||
    secondActive.snapshotHash !== changed.snapshotHash ||
    secondActive.active !== true ||
    secondActive.presentationCommitted !== false
  ) {
    throw blockedError("second_overlapping_pinned_request_unverified");
  }
  const released = await invoke("parent_control", "release_provider_fallback", {
    ...scope,
    requestRef: firstActive.requestRef,
    secondRequestRef: secondActive.requestRef,
  });
  if (
    released.ownerId !== owner.ownerId ||
    released.requestRef !== firstActive.requestRef ||
    released.released !== true
  ) {
    throw blockedError("parent_owned_provider_fallback_unverified");
  }
  await captureScenario(first);
  const fallback = await invoke("evidence", "observe_provider_fallback", {
    ...scope,
    requestRef: firstActive.requestRef,
  });
  if (
    fallback.ownerId !== owner.ownerId ||
    fallback.requestRef !== firstActive.requestRef ||
    fallback.snapshotHash !== firstActive.snapshotHash ||
    fallback.failureClass !== "provider_quota_exhausted" ||
    fallback.fallbackUsed !== true ||
    fallback.retryAfterHonored !== true ||
    fallback.capabilitiesPreserved !== true
  ) {
    throw blockedError("request_pinned_provider_fallback_unverified");
  }
  await captureScenario(second);
  if (
    scenarios[0].snapshotHash !== firstActive.snapshotHash ||
    scenarios[1].snapshotHash !== secondActive.snapshotHash
  ) {
    throw blockedError("overlapping_request_snapshot_mismatch");
  }
  const phaseB = await invoke("evidence", "observe_phase_b_continuity", {
    ...scope,
    requestRef: secondActive.requestRef,
  });
  if (
    phaseB.ownerId !== owner.ownerId ||
    phaseB.requestRef !== secondActive.requestRef ||
    phaseB.snapshotHash !== secondActive.snapshotHash ||
    !SHA256_REF.test(text(phaseB.mainNativeSessionRef)) ||
    !SHA256_REF.test(text(phaseB.phaseBNativeSessionRef)) ||
    phaseB.mainNativeSessionRef === phaseB.phaseBNativeSessionRef ||
    phaseB.mainWorkerInterrupted !== false ||
    phaseB.mainWorkerReplaced !== false
  ) {
    throw blockedError("independent_phase_b_continuity_unverified");
  }
  const specialists = await invoke(
    "evidence",
    "observe_specialist_independence",
    { ...scope, requestRef: secondActive.requestRef },
  );
  if (
    specialists.ownerId !== owner.ownerId ||
    specialists.requestRef !== secondActive.requestRef ||
    !Array.isArray(specialists.specialists) ||
    specialists.specialists.length !== REQUIRED_SPECIALISTS.size ||
    new Set(specialists.specialists.map((entry) => entry?.specialistId))
      .size !== REQUIRED_SPECIALISTS.size ||
    specialists.specialists.some(
      (entry) =>
        !REQUIRED_SPECIALISTS.has(entry?.specialistId) ||
        entry.capsuleOccurrenceCount !== 0 ||
        entry.skipReason !== "specialist_cortex_independent",
    )
  ) {
    throw blockedError("specialist_affect_independence_unverified");
  }
  for (const expected of SCENARIOS.slice(2)) {
    await configure(expected);
    await sendTelegramText(
      bridge,
      owner,
      "Please create two distinct small HTML pages in parallel and remain available to chat.",
    );
    await observeWorkers(expected);
    await sendTelegramText(bridge, owner, "How are you feeling?");
    await captureScenario(expected);
  }
  const observation = { ownerId: owner.ownerId, scenarios, privacyAudit };
  const checks = {
    ...assessPinnedCapsules(observation, owner.ownerId),
    overlappingRequests: true,
    providerFallback: true,
    phaseBIndependent: true,
    specialistReceiptCount: REQUIRED_SPECIALISTS.size,
  };
  const capture = await invoke("evidence", "capture_feelings_evidence", {
    ...scope,
    evidenceRoot,
  });
  if (capture.ownerId !== owner.ownerId || !text(capture.evidencePath)) {
    throw blockedError("external_feelings_evidence_producer_unavailable");
  }
  return { checks, evidencePath: capture.evidencePath };
}

async function executeInsightRecoveryJourney({
  invoke,
  bridge,
  owner,
  identity,
  evidenceRoot,
}) {
  const prepared = await invoke("parent_control", "prepare_fixture", {
    ownerId: owner.ownerId,
  });
  if (
    prepared.ownerId !== owner.ownerId ||
    !/^emo048_fixture_[a-f0-9]{24}$/.test(text(prepared.fixtureRef))
  ) {
    throw blockedError("parent_owned_synthetic_fixture_unavailable");
  }
  const fixture = { ownerId: owner.ownerId, fixtureRef: prepared.fixtureRef };
  for (const boundary of BOUNDARIES) {
    const armed = await invoke("parent_control", "arm_fault", {
      ...fixture,
      boundary,
    });
    if (
      armed.ownerId !== owner.ownerId ||
      armed.boundary !== boundary ||
      armed.state !== "armed"
    ) {
      throw blockedError("parent_owned_fault_boundary_unverified");
    }
  }
  const linked = await invoke(
    "browser",
    "observe_linked_conversation",
    fixture,
  );
  if (linked.ownerId !== owner.ownerId || linked.linked !== true) {
    throw blockedError("linked_browser_conversation_unavailable");
  }
  await sendTelegramText(
    bridge,
    owner,
    "Help me understand the emotional tension in this synthetic situation.",
  );
  const graph = await invoke("evidence", "observe_completed_graph", fixture);
  if (graph.status !== "completed" || !SHA256.test(text(graph.resultSha256))) {
    throw blockedError("completed_emotional_insight_unavailable");
  }
  const firstFailure = await invoke(
    "evidence",
    "observe_first_persistence_failure",
    {
      ...fixture,
      completionId: graph.completionId,
    },
  );
  if (
    firstFailure.outboxState !== "pending" ||
    firstFailure.terminalPresentationCount !== 0
  ) {
    throw blockedError("first_persistence_failure_unproven");
  }
  const restart = await invoke("parent_control", "restart_core", {
    ...fixture,
    completionId: graph.completionId,
    requiredState: "pending",
  });
  if (
    restart.parentAuthorized !== true ||
    restart.occurredWhilePending !== true
  ) {
    throw blockedError("authorized_pending_core_restart_unproven");
  }
  const afterStatus = await invoke("parent_control", "status", fixture);
  const acknowledgements = assertExactServiceAcknowledgements(
    afterStatus,
    identity,
  );
  if (acknowledgements.serviceAckDigest !== restart.afterServiceAckDigest) {
    throw blockedError("authorized_pending_core_restart_unproven");
  }
  async function observeVisiblePhase(phase) {
    const telegram = assertObservedTelegramScreenshot(
      await observeComputer(bridge, owner, "get_app_state", {
        phase,
        includeScreenshot: true,
      }),
    );
    const web = await invoke("browser", "observe_visible_insight", {
      ...fixture,
      phase,
    });
    if (
      web.ownerId !== owner.ownerId ||
      web.visibleCount !== 1 ||
      web.evidenceId !== "web-" + phase ||
      !SHA256.test(text(web.screenshotSha256))
    ) {
      throw blockedError(
        phase === "settled"
          ? "linked_insight_delivery_not_exactly_once"
          : "insight_replay_was_not_idempotent",
      );
    }
    for (const capture of [
      {
        surface: "telegram",
        screenshotSha256: telegram.screenshotSha256,
        computerChallenge: telegram.challenge,
      },
      {
        surface: "web",
        screenshotSha256: web.screenshotSha256,
        browserEvidenceId: web.evidenceId,
      },
    ]) {
      const stored = await invoke("evidence", "record_surface_observation", {
        ...fixture,
        phase,
        ...capture,
      });
      if (
        stored.ownerId !== owner.ownerId ||
        stored.fixtureRef !== fixture.fixtureRef ||
        stored.phase !== phase ||
        stored.surface !== capture.surface ||
        stored.evidenceId !== capture.surface + "-" + phase ||
        stored.screenshotSha256 !== capture.screenshotSha256
      ) {
        throw blockedError("private_installed_surface_capture_unavailable");
      }
    }
  }
  await observeVisiblePhase("settled");
  const delivery = await invoke("evidence", "observe_settled_delivery", {
    ...fixture,
    resultSha256: graph.resultSha256,
  });
  const replayed = await invoke("parent_control", "replay_completion", {
    ...fixture,
    completionId: graph.completionId,
  });
  if (replayed.ownerId !== owner.ownerId || replayed.replayed !== true) {
    throw blockedError("insight_replay_unavailable");
  }
  await observeVisiblePhase("replayed");
  const replay = await invoke("evidence", "observe_replayed_delivery", fixture);
  const controls = await invoke(
    "evidence",
    "observe_consumed_fault_boundaries",
    fixture,
  );
  const terminalProbe = await invoke(
    "evidence",
    "observe_typed_terminal_probe",
    fixture,
  );
  const observation = {
    ...fixture,
    graph,
    firstFailure,
    boundaries: controls.boundaries,
    restart,
    delivery,
    replay,
    terminalProbe,
  };
  const checks = {
    ...assessInsightRecovery(observation, owner.ownerId),
    privateSurfaceCaptures: 4,
  };
  const capture = await invoke("evidence", "capture_insight_evidence", {
    ...fixture,
    evidenceRoot,
  });
  if (
    capture.ownerId !== owner.ownerId ||
    capture.fixtureRef !== prepared.fixtureRef ||
    !text(capture.evidencePath)
  ) {
    throw blockedError("external_insight_evidence_producer_unavailable");
  }
  return {
    fixtureRef: prepared.fixtureRef,
    checks,
    evidencePath: capture.evidencePath,
  };
}

function safeBlocker(value) {
  const result = text(value);
  return SAFE_CODE.test(result)
    ? result
    : "installed_emotional_journey_blocked";
}

function buildPublicSummary({ caseId, status, blocker, checks } = {}) {
  const safeChecks = {};
  if (object(checks)) {
    for (const [key, value] of Object.entries(checks)) {
      if (
        /^[A-Za-z][A-Za-z0-9]{0,47}$/.test(key) &&
        (typeof value === "boolean" || Number.isSafeInteger(value))
      ) {
        safeChecks[key] = value;
      }
    }
  }
  return {
    caseId: CASE_IDS.has(caseId) ? caseId : CASE_047,
    status: new Set(["DRY_RUN", "BLOCKED", "FAIL", "PRE_GATE_COMPLETE"]).has(
      status,
    )
      ? status
      : "BLOCKED",
    ...(blocker ? { blocker: safeBlocker(blocker) } : {}),
    ...(Object.keys(safeChecks).length ? { checks: safeChecks } : {}),
    releaseReady: false,
    receiptEligible: false,
    releaseLabel: RELEASE_LABEL,
  };
}

async function runInstalledJourney(
  argv = process.argv.slice(2),
  environment = process.env,
  injection = {},
) {
  let args;
  let cleanup;
  let result;
  try {
    args = parseArguments(argv);
    if (args.mode === "dry-run") return dryRunPlan(args);
    assertLiveOptIn(args, environment);
    const selectedOwner = assertSyntheticOwner(
      injection.owner,
      environment,
      args.ownerId || undefined,
      args.caseId,
    );
    const identity = assertIdentity(injection.identity);
    if (
      identity.caseId !== args.caseId ||
      identity.ownerId !== selectedOwner.ownerId
    ) {
      throw blockedError("candidate_or_session_binding_invalid");
    }
    await assertIndependentParentComputerAuthority(injection.authority);
    if (
      !object(injection.capabilities) ||
      [...CAPABILITIES].some(
        (name) => typeof injection.capabilities[name]?.invoke !== "function",
      )
    ) {
      throw blockedError("authenticated_external_capability_unavailable");
    }
    const evidenceRoot = assertPrivateEvidenceRoot(args.evidenceRoot);
    const context = createAuthenticatedCapabilityContext({
      authority: injection.authority,
      identity,
      owner: selectedOwner,
    });
    const bridge = assertParentOwnedComputerBridge(
      injection.desktopDriver,
      selectedOwner,
      identity,
      injection.authority,
    );
    const invoke = (name, action, payload = {}) =>
      invokeOwnerGuardedCapability({
        context,
        bridge,
        owner: selectedOwner,
        capabilities: injection.capabilities,
        name,
        action,
        payload,
      });
    const current = await invoke("parent_control", "status", {
      ownerId: selectedOwner.ownerId,
    });
    assertExactServiceAcknowledgements(current, identity);
    const confirmed = await invoke("parent_control", "inspect_owner", {
      ownerId: selectedOwner.ownerId,
    });
    assertSyntheticOwner(
      confirmed,
      environment,
      selectedOwner.ownerId,
      args.caseId,
    );
    await observeComputer(bridge, selectedOwner, "get_app_state");
    if (args.caseId === CASE_047) {
      const fixture = await invoke("parent_control", "prepare_fixture", {
        ownerId: selectedOwner.ownerId,
      });
      if (
        fixture.ownerId !== selectedOwner.ownerId ||
        !text(fixture.fixtureRef) ||
        !SHA256.test(text(fixture.baselineStateDigest))
      ) {
        throw blockedError("parent_owned_synthetic_fixture_unavailable");
      }
      cleanup = {
        caseId: args.caseId,
        owner: selectedOwner,
        fixtureRef: fixture.fixtureRef,
        baselineStateDigest: fixture.baselineStateDigest,
        invoke,
      };
      result = await executePinnedFeelingsJourney({
        invoke,
        bridge,
        owner: selectedOwner,
        fixtureRef: fixture.fixtureRef,
        evidenceRoot,
      });
    } else {
      cleanup = {
        caseId: args.caseId,
        owner: selectedOwner,
        fixtureRef: "pending_parent_fixture",
        invoke,
      };
      const originalInvoke = invoke;
      const trackedInvoke = async (name, action, payload = {}) => {
        const answer = await originalInvoke(name, action, payload);
        if (
          name === "parent_control" &&
          action === "prepare_fixture" &&
          text(answer.fixtureRef)
        ) {
          cleanup.fixtureRef = answer.fixtureRef;
        }
        return answer;
      };
      result = await executeInsightRecoveryJourney({
        invoke: trackedInvoke,
        bridge,
        owner: selectedOwner,
        identity,
        evidenceRoot,
      });
    }
    const verifierStatus = await invoke("parent_control", "status", {
      ownerId: selectedOwner.ownerId,
    });
    assertExactServiceAcknowledgements(verifierStatus, identity);
    runIndependentVerifier(args.caseId, {
      evidenceRoot,
      evidencePath: result.evidencePath,
      identity,
      owner: selectedOwner,
      fixtureRef: result.fixtureRef || cleanup?.fixtureRef,
      serviceStatus: verifierStatus,
    });
    const finalStatus = await invoke("parent_control", "status", {
      ownerId: selectedOwner.ownerId,
    });
    assertExactServiceAcknowledgements(finalStatus, identity);
    result = buildPublicSummary({
      caseId: args.caseId,
      status: "PRE_GATE_COMPLETE",
      checks: result.checks,
    });
  } catch (error) {
    result = buildPublicSummary({
      caseId: args?.caseId,
      status: "BLOCKED",
      blocker: error?.blocked
        ? error.message
        : "installed_emotional_journey_blocked",
    });
  } finally {
    if (cleanup && cleanup.fixtureRef !== "pending_parent_fixture") {
      try {
        await cleanupSyntheticEffects(cleanup);
      } catch {
        result = buildPublicSummary({
          caseId: cleanup.caseId,
          status: "BLOCKED",
          blocker: "synthetic_owner_cleanup_unverified",
        });
      }
    }
  }
  return result;
}

if (require.main === module) {
  const injection =
    globalThis[Symbol.for("viventium.emotional.installed_journey.parent.v1")] ||
    {};
  runInstalledJourney(process.argv.slice(2), process.env, injection)
    .then((result) => {
      process.stdout.write(JSON.stringify(result) + "\n");
      if (!new Set(["DRY_RUN", "PRE_GATE_COMPLETE"]).has(result.status))
        process.exitCode = 2;
    })
    .catch(() => {
      process.stdout.write(
        JSON.stringify(
          buildPublicSummary({
            status: "BLOCKED",
            blocker: "installed_emotional_journey_blocked",
          }),
        ) + "\n",
      );
      process.exitCode = 2;
    });
}

module.exports = {
  CASE_047,
  CASE_048,
  BOUNDARIES,
  SKY_METHODS,
  parseArguments,
  dryRunPlan,
  assertLiveOptIn,
  assertSyntheticOwner,
  assertExternalAuthority,
  assertIndependentParentComputerAuthority,
  assertParentOwnedComputerBridge,
  assertActiveOwnerChat,
  observeComputer,
  assertObservedTelegramScreenshot,
  sendTelegramText,
  assertExactServiceAcknowledgements,
  assessPinnedCapsules,
  assessInsightRecovery,
  assertPrivateEvidenceRoot,
  assertExistingPrivateEvidence,
  runIndependentVerifier,
  createAuthenticatedCapabilityContext,
  invokeAuthenticatedCapability,
  invokeOwnerGuardedCapability,
  cleanupSyntheticEffects,
  executePinnedFeelingsJourney,
  executeInsightRecoveryJourney,
  buildPublicSummary,
  runInstalledJourney,
  canonicalJson,
};
